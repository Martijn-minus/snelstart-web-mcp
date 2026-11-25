"""Contracts for invoice readiness, purchase review and payment reports."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, JsonValue, StringConstraints, model_validator

from ..enums import PaymentProvider, PayoutMatchStatus
from . import JsonObject, Sha256
from .requests import EntryRequest, ToolRequest
from .review import ReviewDateRange


class SalesInvoiceReadiness(BaseModel):
    company_settings_valid: bool
    blank_company_fields: list[str]


class PurchaseReviewCount(BaseModel):
    marked_or_question_items: int = Field(ge=0)


class PurchaseReviewRequest(EntryRequest):
    include_attachments: bool = True


class PurchaseReviewItem(BaseModel):
    entry_id: UUID
    recognition: JsonObject
    attachments: list[JsonValue] | None


ReportHeading = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]


class MollieReportColumns(ToolRequest):
    settlement_reference: ReportHeading
    settlement_currency: ReportHeading
    settlement_amount: ReportHeading

    @model_validator(mode="after")
    def distinct_headings(self):
        names = (self.settlement_reference, self.settlement_currency, self.settlement_amount)
        if len({name.casefold() for name in names}) != len(names):
            raise ValueError("Use three distinct report headings.")
        return self


class PaymentReportRequest(ToolRequest):
    provider: PaymentProvider
    file_path: Path
    mollie_columns: MollieReportColumns | None = None
    skip: int = Field(default=0, ge=0)
    take: int = Field(default=50, ge=1, le=100)

    @model_validator(mode="after")
    def localized_mollie_headings(self):
        if self.mollie_columns is not None and self.provider is not PaymentProvider.MOLLIE:
            raise ValueError("Use mollie_columns only for Mollie settlement reports.")
        return self


class PaymentReportPayout(BaseModel):
    reference: str
    bank_reference: str | None = None
    currency: str
    rows: int
    calculated_net: Decimal
    declared_payout: Decimal | None = None
    difference: Decimal | None = None


class PaymentReportResult(BaseModel):
    provider: PaymentProvider
    sha256: Sha256
    source_rows: int
    payout_count: int
    next_skip: int | None
    payouts: list[PaymentReportPayout]


class PaymentReportBankRequest(PaymentReportRequest, ReviewDateRange):
    bank_journal_id: UUID
    bank_currency: Annotated[str, StringConstraints(to_upper=True, pattern=r"^[A-Za-z]{3}$")]


class PayoutBankCandidate(BaseModel):
    entry_id: UUID
    booking_date: date


class PayoutBankComparison(BaseModel):
    payout: PaymentReportPayout
    status: PayoutMatchStatus
    candidate_count: int
    candidates: list[PayoutBankCandidate]


class PaymentReportBankResult(BaseModel):
    provider: PaymentProvider
    sha256: Sha256
    bank_journal_id: UUID
    start_date: date
    through_date: date
    fetched_bank_rows: int
    payout_count: int
    next_skip: int | None
    payouts: list[PayoutBankComparison]
