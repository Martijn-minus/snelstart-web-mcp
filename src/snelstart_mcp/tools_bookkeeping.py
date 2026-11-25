from datetime import date
from functools import partial
from uuid import UUID

import httpx
from pydantic import JsonValue, ValidationError

from .client import Client
from .config import SnelStartError, SnelStartHTTPError
from .dates import window
from .enums import (
    AttachmentKind,
    BookingLookupFailure,
    EntryKind,
    PaymentDirection,
    RelationKind,
    SalesStatus,
    YearEndSection,
)
from .models import ApiPage, JsonObject
from .models.api import (
    IcpReturnListing,
    InvoiceSearchBody,
    InvoiceSearchTerm,
    PurchaseDetailIdentity,
)
from .models.requests import (
    ArticleDetailsRequest,
    AttachmentListRequest,
    BankEntriesRequest,
    DateRangeRequest,
    DocumentRequest,
    EntryDetailRequest,
    EntryRequest,
    IcpReturnsRequest,
    LedgerAccountDetailsRequest,
    LedgerRequest,
    PageRequest,
    PaymentMatchRequest,
    PurchaseSearchRequest,
    RelationSearchRequest,
    SalesSearchRequest,
    ThroughDateRequest,
    YearEndRequest,
)
from .models.responses import (
    AttachmentListResponse,
    BankEntryListEvidence,
    DataResponse,
    DownloadResponse,
    EntryDetailResponse,
    IcpReturnPage,
    JsonResponse,
)
from .tooling import READ, Register
from .year_data import bank_entries_between, purchases_between

LEDGER_ENTRIES = "GET /Grootboek/GetGrootboekMutaties"
CHART_OF_ACCOUNTS = "GET /Grootboek/GetAllMinimal"
ICP_RETURN_DETAILS = "GET /IcpAangiftes/GetByPublicIdentifier"
PURCHASE_DETAILS = "GET /Purchases/Get"
PURCHASE_DETAILS_BY_INVOICE = "GET /Purchases/GetByFactuurNummerIdentifier"
PURCHASE_PAYMENTS = "GET /Purchases/GetInkoopBetalingen"
PURCHASE_ATTACHMENTS = "GET /Purchases/GetAttachmentsWithIdentifier"
MAX_CHECKED_PURCHASE_ROWS = 5_000
MAX_CHECKED_PURCHASE_PAGES = 64
ENTRY_DETAILS = {
    EntryKind.PURCHASE: (PURCHASE_DETAILS, "journaalpostIdentifier"),
    EntryKind.JOURNAL: ("GET /MemoriaalBoekingen/GetDetails", "publicIdentifier"),
    EntryKind.OPENING_BALANCE: ("GET /BalansBoekingen/GetDetails", "publicIdentifier"),
    EntryKind.BANK: (
        "GET /KasBankBoeking/GetKasBankboekingDetails",
        "kasBankboekingIdentifier",
    ),
}
ATTACHMENT_ROUTES = {
    AttachmentKind.PURCHASE: (PURCHASE_ATTACHMENTS, "journaalpostIdentifier"),
    AttachmentKind.BANK: ("GET /KasBankBoeking/GetAttachments", "journaalpostIdentifier"),
    AttachmentKind.JOURNAL: ("GET /MemoriaalBoekingen/GetAttachments", "publicIdentifier"),
}
ATTACHMENT_OPERATIONS = frozenset(operation for operation, _ in ATTACHMENT_ROUTES.values())
OPENING_BALANCE_ATTACHMENTS_UNAVAILABLE = (
    "Attachment lookup is unavailable for opening balance bookings through this MCP."
)


class PurchaseDetailRejected(SnelStartError):
    """The purchase detail endpoint rejected a booking which may appear in search."""


class BankDetailUnavailable(SnelStartError):
    """The source bank detail could not be retrieved."""


def _read_bank_list_evidence(read, request: EntryDetailRequest) -> EntryDetailResponse:
    failure = "SnelStart returned HTTP 500 for the bank detail."
    context = request.bank_list_context
    if context is None:
        raise BankDetailUnavailable(
            f"{failure} Provide bank_list_context with the journal ID and booking date "
            "from the bank list or export to check list-level evidence."
        ) from None

    try:
        _, rows = bank_entries_between(
            read,
            str(context.journal_id),
            context.booking_date,
            context.booking_date,
            max_rows=1_000,
            max_pages=12,
        )
    except (SnelStartError, httpx.HTTPError):
        raise BankDetailUnavailable(
            f"{failure} SnelStart could not verify the bank list for the supplied journal and date."
        ) from None

    identifier = str(request.entry_id)
    matches = [
        row
        for row in rows
        if isinstance(value := row.get("identifier"), str) and value.lower() == identifier
    ]
    if len(matches) != 1:
        raise BankDetailUnavailable(
            f"{failure} No unique matching booking ID was verified in the supplied journal and date."
        ) from None
    return EntryDetailResponse(
        data=None,
        failure_code=BookingLookupFailure.BANK_DETAIL_UNAVAILABLE,
        reason=failure,
        bank_list_evidence=BankEntryListEvidence(
            journal_id=context.journal_id, booking_date=context.booking_date, entry=matches[0]
        ),
    )


def read_booking_entry(read, request: EntryDetailRequest) -> EntryDetailResponse:
    operation, parameter = ENTRY_DETAILS[request.kind]
    try:
        return EntryDetailResponse(data=read(operation, {parameter: str(request.entry_id)}))
    except SnelStartHTTPError as error:
        if request.kind is EntryKind.BANK and error.status_code == 500:
            return _read_bank_list_evidence(read, request)
        if request.kind is not EntryKind.PURCHASE or error.status_code != 400:
            raise

    rejected = "SnelStart rejected the purchase detail lookup (HTTP 400)."
    guidance = "The purchase search row can still provide list-level evidence."
    if request.purchase_invoice_id is None:
        raise PurchaseDetailRejected(
            f"{rejected} Use publicIdentifier as entry_id and, if available, "
            f"factuurnummeridentifier from the same row as purchase_invoice_id. {guidance}"
        )
    try:
        details = read(
            PURCHASE_DETAILS_BY_INVOICE,
            {"factuurNummerIdentifier": str(request.purchase_invoice_id)},
        )
    except SnelStartHTTPError as error:
        raise PurchaseDetailRejected(
            f"{rejected} The invoice lookup returned HTTP {error.status_code}. {guidance}"
        ) from None
    try:
        identity = PurchaseDetailIdentity.model_validate(details)
    except ValidationError:
        identity = None
    if identity is None or (
        identity.publicIdentifier != request.entry_id
        or identity.factuurNummerIdentifier != request.purchase_invoice_id
    ):
        raise PurchaseDetailRejected(
            f"{rejected} The invoice lookup did not verify both identifiers. {guidance}"
        )
    return EntryDetailResponse(data=details)


def ledger_query(ledger_id: UUID, through_date: date, query: str = "") -> JsonObject:
    return {
        "grootboekIdentifier": str(ledger_id),
        "dateTo": window(through_date, through_date)[1],
        "searchTerm": query,
        "sortDescending": True,
    }


def read_purchase_page(read, request: PurchaseSearchRequest) -> ApiPage:
    invoice_number = request.invoice_number
    query = request.query.strip()
    numeric_query = query.isascii() and query.isdecimal()
    if request.start_date.year < 1900 or request.through_date.year > 9998:
        raise SnelStartError("Choose dates from 1900 through 9998 for checked purchase searches.")
    scan = partial(
        purchases_between,
        read,
        request.start_date,
        request.through_date,
        max_rows=MAX_CHECKED_PURCHASE_ROWS,
        max_pages=MAX_CHECKED_PURCHASE_PAGES,
    )
    purchases = scan(query=request.query if invoice_number is None else "")
    if not purchases and invoice_number is None and numeric_query:
        invoice_number = query
        purchases = scan()

    matches = []
    for row in purchases:
        if request.review_only and row.get("isTeControlerenInkoop") is not True:
            continue
        if invoice_number is not None:
            number = row.get("factuurnummer")
            if type(number) not in (int, str) or str(number).strip() != invoice_number:
                continue
        matches.append(row)
    return ApiPage.model_validate(
        {
            "totalMatchCount": len(matches),
            "resultList": matches[request.skip : request.skip + request.take],
            "searchTerm": invoice_number if invoice_number is not None else request.query,
        }
    )


def attachment_metadata(data: JsonValue) -> list[JsonValue]:
    if not isinstance(data, list):
        raise SnelStartError("SnelStart returned unexpected attachment metadata.")
    # Thumbnail and temporary blob URLs are not required to retrieve the document.
    fields = (
        "attachmentIdentifier",
        "attachmentId",
        "fileName",
        "originalFileName",
        "documentType",
        "size",
        "contentType",
        "extension",
        "createdOn",
    )
    attachments: list[JsonValue] = []
    for row in data:
        if not isinstance(row, dict):
            raise SnelStartError("SnelStart returned unexpected attachment metadata.")
        item = {key: row[key] for key in fields if key in row}
        for target, source in (
            ("attachmentIdentifier", "publicIdentifier"),
            ("attachmentId", "id"),
            ("fileName", "name"),
            ("size", "originalSizeInBytes"),
        ):
            if not item.get(target) and row.get(source) is not None:
                item[target] = row[source]
        if not item.get("attachmentIdentifier"):
            raise SnelStartError("A SnelStart attachment has no download ID.")
        attachments.append(item)
    return attachments


def read_booking_attachments(read, kind: AttachmentKind, entry_id: UUID) -> list[JsonValue]:
    if kind is AttachmentKind.OPENING_BALANCE:
        raise SnelStartError(OPENING_BALANCE_ATTACHMENTS_UNAVAILABLE)
    operation, parameter = ATTACHMENT_ROUTES[kind]
    return attachment_metadata(read(operation, {parameter: str(entry_id)}))


def nonzero_ledger_uuid(value: JsonValue) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        identifier = UUID(value)
    except ValueError:
        return None
    return str(identifier) if identifier.int else None


def register_bookkeeping_tools(tool: Register, client: Client) -> None:
    @tool(annotations=READ)
    def snelstart_chart_of_accounts() -> JsonResponse:
        """List chart of accounts and their identifiers."""
        return JsonResponse(data=client.request(CHART_OF_ACCOUNTS))

    @tool(annotations=READ)
    def snelstart_ledger_account_details(
        request: LedgerAccountDetailsRequest,
    ) -> DataResponse[JsonObject]:
        """Read an account by number. publicIdentifier is its export UUID, or null if unavailable. grootboekId is an internal number."""
        account = client.request(
            "GET /Grootboek/GetGrootboekByNumber", {"number": request.account_number}
        )
        if (
            not isinstance(account, dict)
            or type(number := account.get("grootboekNumber")) is not int
            or number != request.account_number
        ):
            raise SnelStartError("SnelStart did not return the requested ledger account number.")
        public_id = nonzero_ledger_uuid(account.get("publicIdentifier"))
        if public_id is None:
            try:
                chart = client.request(CHART_OF_ACCOUNTS)
            except (SnelStartHTTPError, httpx.HTTPError):
                chart = None
            if isinstance(chart, list):
                identifiers = {
                    identifier
                    for row in chart
                    if isinstance(row, dict)
                    and type(row.get("grootboekNumber")) is int
                    and row["grootboekNumber"] == number
                    and (identifier := nonzero_ledger_uuid(row.get("grootboekId"))) is not None
                }
                if len(identifiers) == 1:
                    public_id = identifiers.pop()
        return DataResponse(data={**account, "publicIdentifier": public_id})

    @tool(annotations=READ)
    def snelstart_balance_sheet(request: ThroughDateRequest) -> JsonResponse:
        """Read the balance sheet and profit and loss through the given date."""
        return JsonResponse(
            data=client.request(
                "GET /Grootboek/GetBalansResultaatAndRubrieken",
                {
                    "datumTotEnMet": request.through_date.isoformat(),
                },
            )
        )

    @tool(annotations=READ)
    def snelstart_financial_result(request: DateRangeRequest) -> JsonResponse:
        """Read the financial result used as input by the SnelStart tax monitor."""
        return JsonResponse(
            data=client.request(
                "GET /Reporting/FinancieelResultaat",
                {
                    "startDate": request.start_date.isoformat(),
                    "endDate": request.through_date.isoformat(),
                },
            )
        )

    @tool(annotations=READ)
    def snelstart_ledger_entries(request: LedgerRequest) -> JsonResponse:
        """Read one page of ledger entries for an account UUID."""
        return JsonResponse(
            data=client.request(
                LEDGER_ENTRIES,
                {
                    **ledger_query(request.ledger_id, request.through_date, request.query),
                    "skip": request.skip,
                    "top": request.top,
                },
            )
        )

    @tool(annotations=READ)
    def snelstart_search_purchases(request: PurchaseSearchRequest) -> DataResponse[ApiPage]:
        """Search purchases with checked pagination in an inclusive date range. Use invoice_number for an exact reference and review_only to list marked entries. Narrow the date range if coverage cannot be verified."""
        return DataResponse(data=read_purchase_page(client.request, request))

    @tool(annotations=READ)
    def snelstart_search_relations(request: RelationSearchRequest) -> DataResponse[ApiPage]:
        """Search customers or suppliers by name or number."""
        group = "Customers" if request.kind == RelationKind.CUSTOMERS else "Suppliers"
        return DataResponse[ApiPage](
            data=ApiPage.model_validate(
                client.request(
                    f"GET /{group}/Search",
                    {
                        "searchTerm": request.query,
                        "skip": request.skip,
                        "take": request.take,
                        "sortDataFieldName": "name",
                        "sortDescending": False,
                    },
                )
            )
        )

    @tool(annotations=READ)
    def snelstart_search_articles(request: PageRequest) -> DataResponse[ApiPage]:
        """Search sales articles by code or name. Use skip and take to page results."""
        return DataResponse(
            data=ApiPage.model_validate(
                client.request(
                    "GET /Articles/Search",
                    {
                        "searchTerm": request.query,
                        "skip": request.skip,
                        "take": request.take,
                        "sortDataFieldName": "code",
                        "sortDescending": False,
                    },
                )
            )
        )

    @tool(annotations=READ)
    def snelstart_article_details(request: ArticleDetailsRequest) -> DataResponse[JsonObject]:
        """Read an article's prices, VAT and revenue settings by articleId from the article search."""
        article = client.request("GET /Articles/Get", {"id": request.article_id})
        if (
            not isinstance(article, dict)
            or type(identifier := article.get("articleId")) is not int
            or identifier != request.article_id
        ):
            raise SnelStartError("SnelStart did not return the requested article ID.")
        return DataResponse(data=article)

    @tool(annotations=READ)
    def snelstart_get_entry(request: EntryDetailRequest) -> EntryDetailResponse:
        """Read a booking by UUID. Use the purchase invoice ID from the search row when available. Bank list context can recover list evidence after HTTP 500. Verify journal attachments with snelstart_list_attachments even if hasBijlagen is false."""
        return read_booking_entry(client.request, request)

    @tool(annotations=READ)
    def snelstart_vat_returns() -> JsonResponse:
        """Read existing VAT returns."""
        return JsonResponse(data=client.request("GET /BtwAangiftes/GetAll"))

    @tool(annotations=READ)
    def snelstart_icp_returns(request: IcpReturnsRequest) -> IcpReturnPage:
        """Read a page of SnelStart ICP returns and source validation messages."""
        page = IcpReturnListing.model_validate(
            client.request(
                "GET /IcpAangiftes/GetIcpAangiftes", {"skip": request.skip, "top": request.take}
            )
        )
        size = len(page.icpAangiftes)
        if size > request.take:
            raise SnelStartError("SnelStart returned more ICP returns than requested.")
        return IcpReturnPage(
            data=page.icpAangiftes,
            validation_messages=page.validationMessages,
            next_skip=request.skip + size if size == request.take else None,
        )

    @tool(annotations=READ)
    def snelstart_search_sales(request: SalesSearchRequest) -> DataResponse[ApiPage]:
        """Search sales invoices by customer, invoice number or status. Use booking details and ledger entries to verify posting dates."""
        statuses = {
            SalesStatus.ALL: 0,
            SalesStatus.OVERDUE: 1,
            SalesStatus.OUTSTANDING: 2,
            SalesStatus.PAID: 3,
            SalesStatus.DRAFT: 4,
        }
        body = InvoiceSearchBody(
            query=request.query,
            global_terms=[InvoiceSearchTerm(term=part) for part in request.query.split()],
        )
        return DataResponse[ApiPage](
            data=ApiPage.model_validate(
                client.request(
                    "POST /Invoices/Search",
                    {
                        "statusFilter": statuses[request.status],
                        "skip": request.skip,
                        "take": request.take,
                        "sortDataFieldName": "invoiceDate",
                        "sortDescending": True,
                    },
                    body.model_dump(mode="json", by_alias=True),
                )
            )
        )

    @tool(annotations=READ)
    def snelstart_bank_journals() -> JsonResponse:
        """List cash and bank journals and their ledger UUIDs."""
        return JsonResponse(data=client.request("GET /KasBankBoeking/GetKasEnBankDagboeken"))

    @tool(annotations=READ)
    def snelstart_bank_entries(request: BankEntriesRequest) -> DataResponse[ApiPage]:
        """Read bank or cash entries. Both dates in the range are inclusive."""
        start, end = window(request.start_date, request.through_date)
        return DataResponse[ApiPage](
            data=ApiPage.model_validate(
                client.request(
                    "GET /KasBankBoeking/GetKasBankBoekingenWithTimespan",
                    {
                        "grootboekIdentifier": str(request.ledger_id),
                        "searchTerm": request.query,
                        "statusFilter": int(request.marked_only),
                        "skip": request.skip,
                        "take": request.take,
                        "vanaf": start,
                        "totEnMet": end,
                    },
                )
            )
        )

    @tool(annotations=READ)
    def snelstart_find_payment_matches(request: PaymentMatchRequest) -> JsonResponse:
        """Find possible invoice matches for an incoming or outgoing payment."""
        return JsonResponse(
            data=client.request(
                "GET /KasBankBoeking/SearchInvoices",
                {
                    "searchTerm": request.query,
                    "isTransactionDebit": request.direction == PaymentDirection.INCOMING,
                    "saldoFilterViewModel": int(request.open_only),
                },
            )
        )

    @tool(annotations=READ)
    def snelstart_purchase_payments(request: EntryRequest) -> JsonResponse:
        """Read payments and settlements recorded for a purchase."""
        return JsonResponse(
            data=client.request(
                PURCHASE_PAYMENTS,
                {
                    "journaalpostIdentifier": str(request.entry_id),
                },
            )
        )

    @tool(annotations=READ)
    def snelstart_list_attachments(request: AttachmentListRequest) -> AttachmentListResponse:
        """List linked files for a purchase, bank transaction or journal entry. Opening balances report attachment lookup as unavailable. Download listed files for their actual byte count and checksum."""
        if request.kind is AttachmentKind.OPENING_BALANCE:
            return AttachmentListResponse(
                data=None, attachment_lookup_error=OPENING_BALANCE_ATTACHMENTS_UNAVAILABLE
            )
        try:
            data = read_booking_attachments(client.request, request.kind, request.entry_id)
        except SnelStartHTTPError as error:
            if request.kind is AttachmentKind.JOURNAL and error.status_code == 404:
                raise SnelStartError(
                    "The journal attachment lookup returned HTTP 404. Verify the booking ID and "
                    "use kind opening_balance for an opening balance booking."
                ) from None
            raise
        return AttachmentListResponse(data=data)

    @tool(annotations=READ)
    def snelstart_download_document(request: DocumentRequest) -> DownloadResponse:
        """Download a document to a private local file. Returns its path and SHA-256."""
        if request.attachment_id is not None:
            return DownloadResponse.model_validate(
                client.request(
                    "GET /Attachments/GetContentByIdentifier",
                    {"attachmentIdentifier": str(request.attachment_id)},
                    download=True,
                )
            )
        params: JsonObject = {"factuurNummerId": request.invoice_number_id}
        if request.invoice_number:
            params["invoiceNumber"] = request.invoice_number
        return DownloadResponse.model_validate(
            client.request(
                "GET /Invoices/GetPdfByFactuurNummerId",
                params,
                download=True,
            )
        )

    @tool(annotations=READ)
    def snelstart_year_end_review(request: YearEndRequest) -> JsonResponse:
        """Read open items or existing entries for year-end review."""
        operations = {
            YearEndSection.OPEN_ENTRIES: "GetOpenstaandeBoekingen",
            YearEndSection.OPEN_PURCHASES: "GetOpenstaandeInkoopfacturen",
            YearEndSection.OPEN_SALES: "GetOpenstaandeVerkoopfacturen",
            YearEndSection.YEAR_END_ENTRIES: "GetEindjaarsboekingen",
        }
        return JsonResponse(
            data=client.request(
                f"GET /Jaarafsluiting/{operations[request.section]}",
                {"jaar": request.year},
            )
        )

    @tool(annotations=READ)
    def snelstart_supplemental_vat_years() -> JsonResponse:
        """Show years eligible for a supplemental VAT return."""
        return JsonResponse(data=client.request("GET /BtwAangiftes/GetJarenVoorJaarSuppletie"))
