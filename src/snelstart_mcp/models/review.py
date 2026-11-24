"""Contracts for bounded evidence lookups and ledger exports."""

from datetime import date
from pathlib import Path
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, JsonValue, model_validator

from ..enums import (
    ArchiveChange,
    ArchiveComparisonDataset,
    BookingLookupFailure,
    BookingLookupStatus,
    DocumentStatus,
    InvoiceKind,
    ReconciliationStatus,
)
from . import Sha256
from .requests import DateRangeRequest, EntryDetailRequest, ToolRequest


def _unique(values: list[UUID]) -> list[UUID]:
    if len(set(values)) != len(values):
        raise ValueError("Provide each identifier only once.")
    return values


Identifiers = Annotated[list[UUID], Field(min_length=1, max_length=20), AfterValidator(_unique)]


class LedgerExportRequest(DateRangeRequest):
    ledger_ids: Identifiers


class PurchaseEvidenceRequest(ToolRequest):
    purchase_ids: Identifiers
    include_attachments: bool = True


class SalesBookingDetailsRequest(ToolRequest):
    booking_ids: Identifiers


class VatReturnDetailsRequest(ToolRequest):
    return_ids: Identifiers


class PurchaseEvidence(BaseModel):
    purchase_id: UUID
    purchase: JsonValue
    payments: JsonValue
    attachments: list[JsonValue] | None


class RecordDetails(BaseModel):
    identifier: UUID
    details: JsonValue


class LedgerExportAccount(BaseModel):
    ledger_id: UUID
    fetched_rows: int
    exported_rows: int


class LedgerExportResponse(BaseModel):
    administration_id: UUID
    start_date: date
    through_date: date
    path: Path
    sha256: Sha256
    total_exported_rows: int
    ledgers: list[LedgerExportAccount]


class ReviewDateRange(DateRangeRequest):
    @model_validator(mode="after")
    def supported_range(self):
        if self.start_date.year < 1900 or self.through_date.year > 9998:
            raise ValueError("Choose dates from 1900 through 9998.")
        return self


class BookingReference(EntryDetailRequest):
    model_config = ConfigDict(frozen=True)


class BookingBatchRequest(ToolRequest):
    entries: Annotated[list[BookingReference], Field(min_length=1, max_length=20)]

    @model_validator(mode="after")
    def unique_entries(self):
        if len({(entry.kind, entry.entry_id) for entry in self.entries}) != len(self.entries):
            raise ValueError("Provide each booking reference only once.")
        return self


class BookingLookup(BookingReference):
    status: BookingLookupStatus
    details: JsonValue = None
    reason: str | None = None
    failure_code: BookingLookupFailure | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class BookingBatchResponse(BaseModel):
    administration_id: UUID
    complete: bool
    entries: list[BookingLookup]


class BankExportRequest(ReviewDateRange):
    journal_ids: Identifiers


class BankJournalCoverage(BaseModel):
    journal_id: UUID
    fetched_rows: int
    exported_rows: int


class BankExportResponse(BaseModel):
    administration_id: UUID
    start_date: date
    through_date: date
    path: Path
    sha256: Sha256
    total_exported_rows: int
    journals: list[BankJournalCoverage]
    complete: bool = True


class CompareArchivesRequest(ToolRequest):
    before: str
    after: str
    dataset: ArchiveComparisonDataset
    skip: int = Field(default=0, ge=0)
    take: int = Field(default=50, ge=1, le=100)


class BookingChange(BaseModel):
    identifier: str
    journal_id: str | None = None
    change: ArchiveChange
    fields_changed: list[str] = Field(default_factory=list)


class ArchiveComparison(BaseModel):
    before: str
    after: str
    administration_id: UUID
    year: int
    through_date: date
    dataset: ArchiveComparisonDataset
    added: int
    removed: int
    changed: int
    unchanged: int
    next_skip: int | None
    entries: list[BookingChange]


class ReconciliationRequest(BankExportRequest):
    invoice_start_date: date | None = None
    skip: int = Field(default=0, ge=0)
    take: int = Field(default=50, ge=1, le=100)

    @model_validator(mode="after")
    def invoices_start_in_time(self):
        if (
            self.invoice_start_date is not None
            and not date(1900, 1, 1) <= self.invoice_start_date <= self.start_date
        ):
            raise ValueError("The invoice start date must be at or before the first bank date.")
        return self


class InvoiceEvidence(BaseModel):
    identifier: str
    invoice_number: str | None
    kind: InvoiceKind
    invoice_date: date | None
    counterparty: str | None
    amount: str | None
    reference_matches: bool = False
    counterparty_matches: bool = False
    documents: DocumentStatus = DocumentStatus.UNKNOWN


class BankReconciliationEntry(BaseModel):
    journal_id: UUID
    identifier: str
    date: date
    amount: str | None
    status: ReconciliationStatus
    possible_duplicate: bool = False
    competing_bank_entries: bool = False
    recorded_link_ids: list[str] = Field(default_factory=list)
    candidates: list[InvoiceEvidence] = Field(default_factory=list)
    candidate_count: int = 0


class ReconciliationReport(BaseModel):
    administration_id: UUID
    start_date: date
    through_date: date
    invoice_start_date: date
    invoices_examined: int
    invoices_skipped: int
    journals: list[BankJournalCoverage]
    counts: dict[ReconciliationStatus, int]
    next_skip: int | None
    entries: list[BankReconciliationEntry]
