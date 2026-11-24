"""Fixed values in the local CLI, MCP and SnelStart contracts."""

from enum import StrEnum


class LoginMethod(StrEnum):
    CREDENTIALS = "credentials"
    BROWSER = "browser"


class ArchiveDataset(StrEnum):
    BALANCE_AND_PROFIT_LOSS = "balance_and_profit_loss"
    CHART_OF_ACCOUNTS = "chart_of_accounts"
    PURCHASES = "purchases"
    SALES = "sales"
    BANK_JOURNALS = "bank_journals"
    BANK_ENTRIES = "bank_entries"
    GENERAL_JOURNALS = "general_journals"
    JOURNAL_AND_OPENING_ENTRIES = "journal_and_opening_entries"
    VAT_RETURNS = "vat_returns_all_years"


class ArchiveComparisonDataset(StrEnum):
    PURCHASES = ArchiveDataset.PURCHASES.value
    SALES = ArchiveDataset.SALES.value
    BANK_ENTRIES = ArchiveDataset.BANK_ENTRIES.value
    JOURNAL_AND_OPENING_ENTRIES = ArchiveDataset.JOURNAL_AND_OPENING_ENTRIES.value


class BookingLookupStatus(StrEnum):
    FOUND = "found"
    MISSING = "missing"
    FAILED = "failed"
    TOO_LARGE = "too_large"


class ArchiveChange(StrEnum):
    ADDED = "added"
    CHANGED = "changed"
    REMOVED = "removed"


class ReconciliationStatus(StrEnum):
    LINKED = "recorded_link"
    SUGGESTED = "suggested"
    AMBIGUOUS = "ambiguous"
    UNMATCHED = "unmatched"
    INSUFFICIENT = "insufficient_data"


class DocumentStatus(StrEnum):
    PRESENT = "present"
    MISSING = "missing"
    UNKNOWN = "unknown"


class InvoiceKind(StrEnum):
    PURCHASE = "purchase"
    SALE = "sale"


class MutationStatus(StrEnum):
    SENDING = "sending"
    UNRESOLVED = "unresolved"
    ACCEPTED = "accepted"
    VERIFIED = "verified"


class BrowserStatus(StrEnum):
    MISSING_EXTRA = "missing_extra"
    CHROME_NOT_FOUND = "chrome_not_found"
    DETECTED = "detected"
    READY = "ready"
    LAUNCH_FAILED = "launch_failed"


class OAuthGrant(StrEnum):
    AUTHORIZATION_CODE = "authorization_code"
    REFRESH_TOKEN = "refresh_token"


class OAuthResponseType(StrEnum):
    CODE = "code"


class CodeChallengeMethod(StrEnum):
    S256 = "S256"


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class WriteMode(StrEnum):
    ON = "on"
    OFF = "off"
    LIST = "list"
    GRANT = "grant"
    REVOKE = "revoke"
    CONFIGURE = "configure"


class RelationKind(StrEnum):
    CUSTOMERS = "customers"
    SUPPLIERS = "suppliers"


class EntryKind(StrEnum):
    PURCHASE = "purchase"
    JOURNAL = "journal"
    OPENING_BALANCE = "opening_balance"
    BANK = "bank"


class AttachmentKind(StrEnum):
    PURCHASE = "purchase"
    BANK = "bank"
    JOURNAL = "journal"


class SalesStatus(StrEnum):
    ALL = "all"
    OVERDUE = "overdue"
    OUTSTANDING = "outstanding"
    PAID = "paid"
    DRAFT = "draft"


class PaymentDirection(StrEnum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"


class YearEndSection(StrEnum):
    OPEN_ENTRIES = "open_entries"
    OPEN_PURCHASES = "open_purchases"
    OPEN_SALES = "open_sales"
    YEAR_END_ENTRIES = "year_end_entries"


class ArchiveFormat(StrEnum):
    YEAR_ARCHIVE_V2 = "snelstart-year-archive-v2"


class AuditOutcome(StrEnum):
    START = "start"
    OK = "ok"
    ERROR = "error"
    INTERRUPTED = "interrupted"
    PENDING = "pending"


class UpdateStatus(StrEnum):
    AVAILABLE = "available"
    CURRENT = "current"
    RECONNECT_REQUIRED = "reconnect_required"
    UNAVAILABLE = "unavailable"


class CodexHookEvent(StrEnum):
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
