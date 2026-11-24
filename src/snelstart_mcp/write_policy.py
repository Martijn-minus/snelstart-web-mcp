"""Bookkeeping operations that need a scoped grant even when global writes are on."""

EXPLICIT_GRANT_PREFIXES = (
    "POST /BtwAangiftes/",
    "POST /IcpAangiftes/",
    "POST /Invoices/Send",
    "POST /Invoices/Resend",
    "POST /Invoices/UpdateAndSend",
    "POST /Customers/UpdateInvoiceMailAddress",
    "POST /Customers/UpdateQuotationMailAddress",
    "POST /Jaarafsluiting/",
)
EXPLICIT_GRANT_OPERATIONS = {"PUT /Settings/SaveNextInvoiceNumber"}


def needs_scoped_grant(operation: str) -> bool:
    return operation in EXPLICIT_GRANT_OPERATIONS or operation.startswith(EXPLICIT_GRANT_PREFIXES)
