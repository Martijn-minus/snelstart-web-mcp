"""Validated inputs for the MCP's flat tool arguments."""

from datetime import date
from pathlib import Path
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from ..enums import (
    AttachmentKind,
    EntryKind,
    PaymentDirection,
    RelationKind,
    SalesStatus,
    YearEndSection,
)
from . import JsonObject


class ToolRequest(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)


class AdministrationRequest(ToolRequest):
    administration_id: UUID


class LimitRequest(ToolRequest):
    limit: int = 30

    @model_validator(mode="after")
    def limit_in_range(self):
        if not 1 <= self.limit <= 100:
            raise ValueError("The limit must be between 1 and 100.")
        return self


class OperationListRequest(LimitRequest):
    query: str = ""
    read_only: bool = True


class ReadOperationRequest(ToolRequest):
    operation: str
    parameters: JsonObject | None = None
    filters: JsonObject | None = None


class WriteOperationRequest(AdministrationRequest):
    operation: str
    payload: JsonObject
    parameters: JsonObject | None = None
    approval_id: UUID | None = None


class ThroughDateRequest(ToolRequest):
    through_date: date


class DateRangeRequest(ThroughDateRequest):
    start_date: date

    @model_validator(mode="after")
    def dates_in_order(self):
        if self.start_date > self.through_date:
            raise ValueError("The start date must be on or before the through date.")
        return self


class PageRequest(ToolRequest):
    query: str = ""
    skip: int = 0
    take: int = 50

    @model_validator(mode="after")
    def page_in_range(self):
        if self.skip < 0 or not 1 <= self.take <= 200:
            raise ValueError("Skip must be nonnegative. Page size must be between 1 and 200.")
        return self


class IcpReturnsRequest(ToolRequest):
    skip: int = Field(default=0, ge=0)
    take: int = Field(default=50, ge=1, le=200)


class ArticleDetailsRequest(ToolRequest):
    article_id: int = Field(gt=0)


class LedgerAccountDetailsRequest(ToolRequest):
    account_number: int = Field(ge=0)


class LedgerRequest(ThroughDateRequest):
    ledger_id: UUID
    query: str = ""
    skip: int = 0
    top: int = 50

    @model_validator(mode="after")
    def page_in_range(self):
        PageRequest(skip=self.skip, take=self.top)
        return self


class PurchaseSearchRequest(PageRequest, DateRangeRequest):
    review_only: bool = Field(
        default=False, description="Return only purchases marked for review in SnelStart."
    )
    invoice_number: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = Field(
        default=None, description="Exact purchase invoice number, including any leading zeros."
    )

    @model_validator(mode="after")
    def use_one_search_mode(self):
        if self.invoice_number is not None and self.query.strip():
            raise ValueError(
                "Use either invoice_number for an exact match or query for text search."
            )
        return self


class RelationSearchRequest(PageRequest):
    kind: RelationKind


class SalesSearchRequest(PageRequest):
    status: SalesStatus = SalesStatus.ALL


class BankEntriesRequest(PageRequest, DateRangeRequest):
    ledger_id: UUID
    marked_only: bool = False


class PaymentMatchRequest(ToolRequest):
    query: str
    direction: PaymentDirection
    open_only: bool = True

    @model_validator(mode="after")
    def specific_query(self):
        if not self.query.strip():
            raise ValueError("Provide an invoice number, name or another specific search term.")
        return self


class EntryRequest(ToolRequest):
    entry_id: UUID


class BankEntryListContext(ToolRequest):
    journal_id: UUID
    booking_date: date

    @model_validator(mode="after")
    def supported_date(self):
        if not 1900 <= self.booking_date.year <= 9998:
            raise ValueError("Choose a booking date from 1900 through 9998.")
        return self


class EntryDetailRequest(EntryRequest):
    kind: EntryKind
    purchase_invoice_id: UUID | None = Field(
        default=None,
        description="For purchases, the factuurnummeridentifier from the same purchase search row.",
        exclude_if=lambda value: value is None,
    )
    bank_list_context: BankEntryListContext | None = Field(
        default=None,
        description="For bank bookings, the journal UUID and local booking date from the bank list or export. Used if the detail endpoint returns HTTP 500.",
        exclude_if=lambda value: value is None,
    )

    @model_validator(mode="after")
    def context_matches_kind(self):
        if self.purchase_invoice_id is not None and self.kind is not EntryKind.PURCHASE:
            raise ValueError("An invoice identifier can only be used for a purchase booking.")
        if self.bank_list_context is not None and self.kind is not EntryKind.BANK:
            raise ValueError("Bank list context can only be used for a bank booking.")
        return self


class AttachmentListRequest(EntryRequest):
    kind: AttachmentKind


class DocumentRequest(ToolRequest):
    attachment_id: UUID | None = None
    invoice_number_id: int | None = None
    invoice_number: str | None = None

    @model_validator(mode="after")
    def one_document(self):
        if (self.attachment_id is None) == (self.invoice_number_id is None):
            raise ValueError("Provide exactly one attachment ID or invoice number ID.")
        if self.attachment_id is not None and self.invoice_number is not None:
            raise ValueError("The invoice number applies only to a sales invoice.")
        if self.invoice_number_id is not None and self.invoice_number_id <= 0:
            raise ValueError("The invoice number ID must be positive.")
        return self


class YearEndRequest(ToolRequest):
    year: int
    section: YearEndSection


class ArchiveCreateRequest(ThroughDateRequest):
    year: int
    live_export: bool = True
    auditfile_path: str | None = None
    attachments_zip_path: str | None = None
    bacpac_path: str | None = None
    official_zip_path: str | None = None


class ArchiveRequest(ToolRequest):
    archive: str


class PurchaseUploadRequest(AdministrationRequest):
    file_path: Path
    approval_id: UUID | None = None


class BankAttachmentRequest(AdministrationRequest):
    entry_id: UUID
    file_path: Path
    approval_id: UUID | None = None

    @model_validator(mode="after")
    def nonzero_entry_id(self):
        if not self.entry_id.int:
            raise ValueError("Provide the bank or cash booking's nonzero UUID.")
        return self


class UploadStatusRequest(AdministrationRequest):
    instance_id: str

    @model_validator(mode="after")
    def nonempty_id(self):
        if not self.instance_id.strip():
            raise ValueError("Provide the purchase processing ID returned by the upload tool.")
        return self
