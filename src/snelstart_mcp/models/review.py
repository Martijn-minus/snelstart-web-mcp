"""Contracts for bounded evidence lookups and ledger exports."""

from datetime import date
from pathlib import Path
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, Field, JsonValue

from . import Sha256
from .requests import DateRangeRequest, ToolRequest


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
