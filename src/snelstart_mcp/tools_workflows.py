"""Read-only entry points for sales preparation and purchase recognition."""

from mcp.types import ToolAnnotations

from .client import Client
from .config import SnelStartError
from .enums import AttachmentKind
from .models.workflows import (
    PaymentReportBankRequest,
    PaymentReportBankResult,
    PaymentReportRequest,
    PaymentReportResult,
    PurchaseReviewCount,
    PurchaseReviewItem,
    PurchaseReviewRequest,
    SalesInvoiceReadiness,
)
from .payment_reports import compare_payment_report, read_payment_report
from .tooling import READ, Register
from .tools_bookkeeping import read_booking_attachments

COMPANY_FIELDS = {
    "name": "name",
    "address": "address",
    "zip_code": "zipCode",
    "city": "city",
    "email": "email",
    "iban": "iban",
    "vat_number": "vatNumber",
    "chamber_of_commerce_number": "kvkNumber",
}


def register_workflow_tools(tool: Register, client: Client) -> None:
    @tool(annotations=READ)
    def snelstart_sales_invoice_readiness() -> SalesInvoiceReadiness:
        """Check the SnelStart Web company-settings gate for preparing sales invoices."""
        valid = client.request("GET /Validation/HasValidCompanySettings")
        if not isinstance(valid, bool):
            raise SnelStartError("SnelStart did not return an invoice readiness result.")
        company = client.request("GET /CompanySettings/GetCompanySettings")
        if not isinstance(company, dict):
            raise SnelStartError("SnelStart did not return company settings.")
        return SalesInvoiceReadiness(
            company_settings_valid=valid,
            blank_company_fields=[
                name
                for name, field in COMPANY_FIELDS.items()
                if company.get(field) is None or str(company[field]).strip() == ""
            ],
        )

    @tool(annotations=READ)
    def snelstart_purchase_review_count() -> PurchaseReviewCount:
        """Read the portal's administration-wide count of marked purchases and question items."""
        data = client.request("GET /Purchases/GetGemarkeerdeInkopenOfVraagpostenCount")
        count = data.get("aantal") if isinstance(data, dict) else None
        if type(count) is not int or count < 0:
            raise SnelStartError("SnelStart returned an invalid purchase review count.")
        return PurchaseReviewCount(marked_or_question_items=count)

    @tool(annotations=READ)
    def snelstart_purchase_review_item(request: PurchaseReviewRequest) -> PurchaseReviewItem:
        """Read recognized values and optional attachments for an exact purchase awaiting review."""
        if request.entry_id.int == 0:
            raise SnelStartError("Provide the nonzero booking ID from the purchase search.")
        identifier = str(request.entry_id)
        record = client.request("GET /Purchases/GetTeControlerenInkoop", {"identifier": identifier})
        if not isinstance(record, dict):
            raise SnelStartError("SnelStart did not return the requested purchase review item.")
        actual = record.get("publicIdentifier")
        if not isinstance(actual, str) or actual.lower() != identifier:
            raise SnelStartError("SnelStart did not return the requested purchase review item.")
        return PurchaseReviewItem(
            entry_id=request.entry_id,
            recognition=record,
            attachments=read_booking_attachments(
                client.request, AttachmentKind.PURCHASE, request.entry_id
            )
            if request.include_attachments
            else None,
        )

    @tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def snelstart_read_payment_report(request: PaymentReportRequest) -> PaymentReportResult:
        """Summarize a local Adyen, Mollie or Stripe CSV by payout and currency."""
        return read_payment_report(request)

    @tool(annotations=READ)
    def snelstart_compare_payment_report(
        request: PaymentReportBankRequest,
    ) -> PaymentReportBankResult:
        """Compare report payouts with bank entries, showing reference-and-amount matches and amount-only candidates."""
        return compare_payment_report(client.request, request)
