from datetime import date
from functools import partial
from uuid import UUID

from pydantic import JsonValue, ValidationError

from .client import Client
from .config import SnelStartError, SnelStartHTTPError
from .dates import window
from .enums import (
    AttachmentKind,
    EntryKind,
    PaymentDirection,
    RelationKind,
    SalesStatus,
    YearEndSection,
)
from .models import ApiPage, JsonObject
from .models.api import InvoiceSearchBody, InvoiceSearchTerm, PurchaseDetailIdentity
from .models.requests import (
    AttachmentListRequest,
    BankEntriesRequest,
    DateRangeRequest,
    DocumentRequest,
    EntryDetailRequest,
    EntryRequest,
    LedgerRequest,
    PaymentMatchRequest,
    PurchaseSearchRequest,
    RelationSearchRequest,
    SalesSearchRequest,
    ThroughDateRequest,
    YearEndRequest,
)
from .models.responses import DataResponse, DownloadResponse, JsonResponse
from .tooling import READ, Register
from .year_data import purchases_between

LEDGER_ENTRIES = "GET /Grootboek/GetGrootboekMutaties"
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


class PurchaseDetailRejected(SnelStartError):
    """The purchase detail endpoint rejected a booking which may appear in search."""


def read_booking_entry(read, request: EntryDetailRequest) -> JsonValue:
    operation, parameter = ENTRY_DETAILS[request.kind]
    try:
        return read(operation, {parameter: str(request.entry_id)})
    except SnelStartHTTPError as error:
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
    return details


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
    operation, parameter = ATTACHMENT_ROUTES[kind]
    return attachment_metadata(read(operation, {parameter: str(entry_id)}))


def register_bookkeeping_tools(tool: Register, client: Client) -> None:
    @tool(annotations=READ)
    def snelstart_chart_of_accounts() -> JsonResponse:
        """List chart of accounts and their identifiers."""
        return JsonResponse(data=client.request("GET /Grootboek/GetAllMinimal"))

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
    def snelstart_get_entry(request: EntryDetailRequest) -> JsonResponse:
        """Read a booking by UUID. For purchases, include the invoice identifier from the same search row when available. Verify journal attachments with snelstart_list_attachments even if hasBijlagen is false."""
        return JsonResponse(data=read_booking_entry(client.request, request))

    @tool(annotations=READ)
    def snelstart_vat_returns() -> JsonResponse:
        """Read existing VAT returns."""
        return JsonResponse(data=client.request("GET /BtwAangiftes/GetAll"))

    @tool(annotations=READ)
    def snelstart_search_sales(request: SalesSearchRequest) -> DataResponse[ApiPage]:
        """Search sales invoices by customer, invoice number or status."""
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
    def snelstart_list_attachments(request: AttachmentListRequest) -> JsonResponse:
        """List linked files for a purchase, bank transaction or journal entry. Size and creation date can be placeholders. Download the file for its actual byte count and checksum."""
        return JsonResponse(
            data=read_booking_attachments(client.request, request.kind, request.entry_id)
        )

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
