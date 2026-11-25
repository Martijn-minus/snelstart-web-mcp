"""Read, calculate, save and email sales documents using SnelStart Web."""

from hashlib import sha256

from pydantic import ValidationError

from .approval import require_approval
from .client import Client
from .config import SnelStartError
from .enums import (
    MailHistoryStatus,
    QuotationStatus,
    SalesDocumentKind,
    SalesEmailOutcome,
    SalesPricing,
)
from .models import ApiPage, JsonObject
from .models.approval import WriteIntent
from .models.responses import DataResponse
from .models.sales import (
    MailHistory,
    MailHistoryEntry,
    MailHistoryRequest,
    MailTemplate,
    MailTemplateRequest,
    QuotationDetailsRequest,
    QuotationSearchRequest,
    SalesDocumentPreview,
    SalesDocumentRequest,
    SalesEmailRequest,
    SalesEmailResult,
    SalesSaveRequest,
    SalesSaveResult,
)
from .sales_attachments import MAX_ATTACHMENT_BYTES, read_attachment, upload_attachment
from .tooling import READ, WRITE, Register
from .tools_bookkeeping import attachment_metadata

QUOTATION_STATUSES = {
    QuotationStatus.ALL: 0,
    QuotationStatus.INVOICED: 1,
    QuotationStatus.UNINVOICED: 2,
    QuotationStatus.DRAFT: 3,
}
MAIL_STATUSES = {
    MailHistoryStatus.ALL: 1,
    MailHistoryStatus.FAILED: 2,
    MailHistoryStatus.IN_TRANSIT: 3,
    MailHistoryStatus.DELIVERED: 4,
    MailHistoryStatus.SENT: 5,
}
ATTACHMENT_UPLOAD = "GET /Attachments/GetAttachmentUploadUriNew"


def calculate_document(
    client: Client, request: SalesDocumentRequest
) -> tuple[JsonObject, SalesDocumentPreview]:
    administration = str(request.administration_id)
    customer = client.request(
        "GET /Customers/Get",
        {"relationCode": request.customer_code},
        expected_administration=administration,
    )
    if (
        not isinstance(customer, dict)
        or type(customer.get("id")) is not int
        or customer.get("relationCode") != request.customer_code
    ):
        raise SnelStartError("SnelStart did not return the requested customer.")
    order_date = request.order_date or request.document_date
    lines: list[JsonObject] = []
    for index, line in enumerate(request.lines, start=1):
        article = client.request(
            "GET /Articles/Get",
            {"id": line.article_id},
            expected_administration=administration,
        )
        if not isinstance(article, dict) or article.get("articleId") != line.article_id:
            raise SnelStartError("SnelStart did not return the requested sales article.")
        price = (
            float(line.unit_price)
            if line.unit_price is not None
            else article.get(
                "sellingPriceIncludingVat"
                if request.pricing is SalesPricing.INCLUSIVE
                else "sellingPriceExcludingVat"
            )
        )
        description = line.description or article.get("name")
        if (
            type(price) not in {int, float}
            or not isinstance(description, str)
            or not description.strip()
        ):
            raise SnelStartError("The sales article does not have a usable price and description.")
        lines.append(
            {
                "quantity": float(line.quantity),
                "description": description,
                "article": article,
                "sellingPrice": price,
                "sellingPriceDirty": line.unit_price is not None,
                "vat": article.get("vat"),
                "lineNumber": index,
            }
        )
    payload: JsonObject = {
        "customerId": customer["id"],
        "customer": customer,
        "orderDate": f"{order_date.isoformat()}T00:00:00.000Z",
        "paymentTerm": request.payment_term_days
        if request.payment_term_days is not None
        else customer.get("paymentTerm"),
        "invoiceLines": [*lines],
        "pricingInput": int(request.pricing is SalesPricing.INCLUSIVE),
        "invoiceDiscountPercentage": float(request.discount_percent),
        "btwVerlegd": 0,
    }
    if request.reference is not None:
        payload["orderreferentie"] = request.reference
    if request.kind is SalesDocumentKind.INVOICE:
        payload["invoiceDate"] = f"{request.document_date.isoformat()}T00:00:00.000Z"
        operation = "POST /Invoices/RedetermineVat"
    else:
        if order_date != request.document_date:
            raise SnelStartError("A quotation uses its document date as its order date.")
        payload["isConceptOfferte"] = True
        operation = "POST /Quotations/RedetermineVat"
    calculation = client.request(operation, body=payload, expected_administration=administration)
    if not isinstance(calculation, dict) or calculation.get("customerId") != customer["id"]:
        raise SnelStartError("SnelStart did not return the calculation for the requested customer.")
    calculated_lines = calculation.get("invoiceLines")
    if not isinstance(calculated_lines, list) or len(calculated_lines) != len(lines):
        raise SnelStartError("SnelStart did not calculate every requested line.")
    for original, calculated in zip(lines, calculated_lines, strict=True):
        if (
            not isinstance(calculated, dict)
            or calculated.get("lineNumber") != original["lineNumber"]
        ):
            raise SnelStartError("SnelStart returned unexpected sales calculation lines.")
        original["vat"] = calculated.get("vat")
        original["totalPrice"] = calculated.get("totalPrice")
    for key in (
        "totalVat",
        "totalExcludingVatBeforeDiscount",
        "totalExcludingVatAfterDiscount",
        "totalIncludingVat",
        "invoiceDiscount",
    ):
        payload[key] = calculation.get(key)
    try:
        preview = SalesDocumentPreview.model_validate(
            {
                "administration_id": request.administration_id,
                "kind": request.kind,
                "customer_code": request.customer_code,
                "document_date": request.document_date,
                "net": payload["totalExcludingVatAfterDiscount"],
                "gross": payload["totalIncludingVat"],
                "discount": payload["invoiceDiscount"],
                "vat_breakdown": payload["totalVat"],
                "reference": request.reference,
            }
        )
    except ValidationError:
        raise SnelStartError("SnelStart returned incomplete sales totals.") from None
    if calculation.get("isInBlockedPeriod") is True:
        raise SnelStartError(
            "SnelStart reports that the sales document date is in a blocked period."
        )
    return payload, preview


def register_sales_tools(tool: Register, client: Client) -> None:
    @tool(annotations=READ)
    def snelstart_search_quotations(request: QuotationSearchRequest) -> DataResponse[ApiPage]:
        """Search SnelStart Web quotations by text and status. Use identifier for quotation details."""
        return DataResponse[ApiPage](
            data=ApiPage.model_validate(
                client.request(
                    "GET /Quotations/Search",
                    {
                        "searchTerm": request.query,
                        "statusFilter": QUOTATION_STATUSES[request.status],
                        "skip": request.skip,
                        "take": request.take,
                        "sortDataFieldName": "modifiedOn",
                        "sortDescending": True,
                    },
                )
            )
        )

    @tool(annotations=READ)
    def snelstart_quotation_details(request: QuotationDetailsRequest) -> DataResponse[JsonObject]:
        """Read a quotation by UUID. Returns its lines, totals and attachment metadata."""
        if request.quotation_id.int == 0:
            raise SnelStartError("Provide the nonzero quotation UUID from the search results.")
        record = client.request(
            "GET /Quotations/Get", {"quotationIdentifier": str(request.quotation_id)}
        )
        if not isinstance(record, dict) or type(record.get("orderId")) is not int:
            raise SnelStartError("SnelStart did not return a quotation.")
        record["attachments"] = (
            attachment_metadata(record["attachments"]) if record.get("attachments") else []
        )
        return DataResponse(data=record)

    @tool(annotations=READ)
    def snelstart_sent_email_history(request: MailHistoryRequest) -> MailHistory:
        """Read SnelStart Web outgoing email status by subject or recipient. Excludes email bodies."""
        page = ApiPage.model_validate(
            client.request(
                "GET /Mail/Search",
                {
                    "mailStatusSearchType": MAIL_STATUSES[request.status],
                    "searchTerm": request.query,
                    "skip": request.skip,
                    "take": request.take,
                    "sortDataFieldName": "sendDate",
                    "sortDescending": True,
                },
            )
        )
        return MailHistory(
            total=page.totalMatchCount,
            skip=request.skip,
            take=request.take,
            messages=[MailHistoryEntry.model_validate(row) for row in page.resultList],
        )

    @tool(annotations=READ)
    def snelstart_sales_email_template(request: MailTemplateRequest) -> MailTemplate:
        """Read the default invoice or quotation email subject, body and attachment metadata."""
        invoice = request.kind is SalesDocumentKind.INVOICE
        settings = "InvoiceSettings" if invoice else "QuotationSettings"
        subject = client.request(f"GET /{settings}/GetMailSubject")
        body = client.request(
            "GET /InvoiceSettings/GetInvoiceMailText" if invoice else "GET /Quotations/GetMailText"
        )
        attachments = client.request(f"GET /{settings}/GetDefaultAttachments")
        if not isinstance(subject, str) or not isinstance(body, str):
            raise SnelStartError("SnelStart returned an unexpected email template.")
        return MailTemplate(
            kind=request.kind,
            subject=subject,
            message=body,
            attachments=[
                item for item in attachment_metadata(attachments or []) if isinstance(item, dict)
            ],
        )

    @tool(annotations=READ)
    def snelstart_preview_sales_document(request: SalesDocumentRequest) -> SalesDocumentPreview:
        """Calculate an invoice or quotation from existing customer and article codes without saving it."""
        return calculate_document(client, request)[1]

    @tool(annotations=WRITE)
    def snelstart_save_sales_document(request: SalesSaveRequest) -> SalesSaveResult:
        """Save a new invoice or quotation without emailing it. Review the calculated totals first."""
        operation = (
            "POST /Invoices/SaveOnly"
            if request.kind is SalesDocumentKind.INVOICE
            else "POST /Quotations/SaveOnly"
        )
        invoice_draft = request.kind is SalesDocumentKind.INVOICE and request.draft
        if invoice_draft:
            operation = "POST /Orders/Save"
        client.check_write_access(operation, request.administration_id)
        payload, preview = calculate_document(client, request)
        if preview.gross != request.expected_gross:
            raise SnelStartError("The calculated gross total differs from the approved total.")
        if (
            client.request(
                "GET /Validation/HasValidCompanySettings",
                expected_administration=str(request.administration_id),
            )
            is not True
        ):
            raise SnelStartError(
                "Complete the company settings in SnelStart Web before saving sales documents."
            )
        if request.kind is SalesDocumentKind.QUOTATION:
            payload["isConceptOfferte"] = request.draft
        require_approval(
            client.store,
            WriteIntent(
                tool="snelstart_save_sales_document",
                operation=operation,
                administration_id=request.administration_id,
                details={"payload": payload},
            ),
            request.approval_id,
        )
        response = client.request(
            operation, body=payload, expected_administration=str(request.administration_id)
        )
        if not isinstance(response, dict):
            raise SnelStartError(
                "The sales save outcome is unknown. Read the sales overview before retrying."
            )
        if invoice_draft:
            saved = type(response.get("orderId")) is int and bool(response["orderId"])
        elif request.kind is SalesDocumentKind.QUOTATION:
            saved = response.get("successful") is True
        else:
            status = response.get("status")
            saved = type(status) is int and status in {1, 5}
        if not saved:
            raise SnelStartError(
                "SnelStart did not confirm the save. Check the sales overview before retrying."
            )
        order_number = response.get("orderNumber")
        invoice_number = response.get("invoiceNumber")
        return SalesSaveResult(
            preview=preview,
            draft=request.draft,
            order_number=order_number if type(order_number) is int and order_number > 0 else None,
            invoice_number=invoice_number
            if isinstance(invoice_number, str)
            and invoice_number
            or type(invoice_number) is int
            and invoice_number
            else None,
        )

    @tool(annotations=WRITE)
    def snelstart_email_new_sales_document(request: SalesEmailRequest) -> SalesEmailResult:
        """Create and request delivery of a new invoice or quotation with a one-off message and optional local files. Use only for a new document and verify delivery separately."""
        invoice = request.kind is SalesDocumentKind.INVOICE
        operation = "POST /Invoices/Send" if invoice else "POST /Quotations/SaveAndSend"
        administration = str(request.administration_id)
        client.check_write_access(operation, request.administration_id)
        if request.attachment_paths:
            client.check_write_access(ATTACHMENT_UPLOAD, request.administration_id)
        if (
            client.request(
                "GET /Validation/HasValidCompanySettings", expected_administration=administration
            )
            is not True
        ):
            raise SnelStartError(
                "Complete the company settings in SnelStart Web before sending sales documents."
            )
        payload, preview = calculate_document(client, request)
        if preview.gross != request.expected_gross:
            raise SnelStartError("The calculated gross total differs from the approved total.")
        payload.update(
            {
                "mailAddressTo": request.recipient,
                "mailAddressCc": "",
                "mailAddressBcc": "",
                "mailSubject": request.subject,
                "mailText": request.message,
            }
        )
        if not invoice:
            payload["isConceptOfferte"] = False
        remaining = MAX_ATTACHMENT_BYTES
        files = []
        descriptors: list[JsonObject] = []
        for path in request.attachment_paths or ():
            contents = read_attachment(path, remaining)
            remaining -= len(contents)
            files.append((path, contents))
            descriptors.append(
                {"name": path.name, "size": len(contents), "sha256": sha256(contents).hexdigest()}
            )
        require_approval(
            client.store,
            WriteIntent(
                tool="snelstart_email_new_sales_document",
                operation=operation,
                administration_id=request.administration_id,
                details={"payload": payload, "attachments": [*descriptors]},
            ),
            request.approval_id,
        )
        uploaded: list[JsonObject] = []
        for path, contents in files:
            url = client.request(
                ATTACHMENT_UPLOAD, {"filename": path.name}, expected_administration=administration
            )
            uri = upload_attachment(url, path, contents)
            uploaded.append({"uri": uri, "originalFileName": path.name, "size": len(contents)})
        payload["attachments"] = [*uploaded]
        response = client.request(operation, body=payload, expected_administration=administration)
        if not isinstance(response, dict):
            raise SnelStartError(
                "The sales email outcome is unknown. Check the sales and sent-email overviews before retrying."
            )
        code = response.get("status" if invoice else "failureCode")
        outcome = SalesEmailOutcome.NOT_CONFIRMED
        if (invoice and type(code) is int and code in {6, 7}) or (not invoice and code == 10):
            outcome = SalesEmailOutcome.SENDER_VERIFICATION_REQUIRED
        elif (invoice and type(code) is int and code == 2) or (
            not invoice and response.get("successful") is True
        ):
            outcome = SalesEmailOutcome.SUBMITTED
        order_number = response.get("orderNumber")
        invoice_number = response.get("invoiceNumber")
        return SalesEmailResult(
            preview=preview,
            outcome=outcome,
            order_number=order_number if type(order_number) is int and order_number > 0 else None,
            invoice_number=invoice_number
            if isinstance(invoice_number, str)
            and invoice_number
            or type(invoice_number) is int
            and invoice_number
            else None,
            upstream_status=code if type(code) is int else None,
        )
