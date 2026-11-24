from pydantic import JsonValue

from .client import Client
from .config import SnelStartError
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
from .models.api import InvoiceSearchBody, InvoiceSearchTerm
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
                "GET /Grootboek/GetGrootboekMutaties",
                {
                    "grootboekIdentifier": str(request.ledger_id),
                    "dateTo": window(request.through_date, request.through_date)[1],
                    "searchTerm": request.query,
                    "skip": request.skip,
                    "top": request.top,
                    "sortDescending": True,
                },
            )
        )

    @tool(annotations=READ)
    def snelstart_search_purchases(request: PurchaseSearchRequest) -> DataResponse[ApiPage]:
        """Search purchase entries. Both dates in the range are inclusive."""
        start, end = window(request.start_date, request.through_date)
        return DataResponse[ApiPage](
            data=ApiPage.model_validate(
                client.request(
                    "GET /Purchases/SearchAllInkopen",
                    {
                        "searchTerm": request.query,
                        "paymentStatus": 0,
                        "onlyTeControlerenInkopen": request.review_only,
                        "skip": request.skip,
                        "take": request.take,
                        "sortDataField": 0,
                        "sortDescending": True,
                        "startDate": start,
                        "dateUntil": end,
                    },
                )
            )
        )

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
        """Read a purchase, journal, opening balance or bank entry by UUID."""
        operations = {
            EntryKind.PURCHASE: ("GET /Purchases/Get", "journaalpostIdentifier"),
            EntryKind.JOURNAL: ("GET /MemoriaalBoekingen/GetDetails", "publicIdentifier"),
            EntryKind.OPENING_BALANCE: ("GET /BalansBoekingen/GetDetails", "publicIdentifier"),
            EntryKind.BANK: (
                "GET /KasBankBoeking/GetKasBankboekingDetails",
                "kasBankboekingIdentifier",
            ),
        }
        operation, parameter = operations[request.kind]
        return JsonResponse(data=client.request(operation, {parameter: str(request.entry_id)}))

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
                "GET /Purchases/GetInkoopBetalingen",
                {
                    "journaalpostIdentifier": str(request.entry_id),
                },
            )
        )

    @tool(annotations=READ)
    def snelstart_list_attachments(request: AttachmentListRequest) -> JsonResponse:
        """List attachments for a purchase, bank transaction or journal entry."""
        operations = {
            AttachmentKind.PURCHASE: (
                "GET /Purchases/GetAttachmentsWithIdentifier",
                "journaalpostIdentifier",
            ),
            AttachmentKind.BANK: ("GET /KasBankBoeking/GetAttachments", "journaalpostIdentifier"),
            AttachmentKind.JOURNAL: ("GET /MemoriaalBoekingen/GetAttachments", "publicIdentifier"),
        }
        operation, key = operations[request.kind]
        data = client.request(operation, {key: str(request.entry_id)})
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
        return JsonResponse(data=attachments)

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
