"""Local audit storage and CLI contracts."""

from pathlib import Path
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from ..enums import AuditOutcome, MutationStatus
from . import Sha256
from .requests import ToolRequest


class AuditCallStart(BaseModel, frozen=True):
    call_id: str
    administration_id: UUID | None
    tool: str = "unknown_tool"


class AuditCallResponse(BaseModel):
    call_id: str
    started_at: str
    tool: str
    administration_id: UUID | None
    administration_id_after: UUID | None
    outcome: AuditOutcome
    elapsed_ms: int | None


class AuditSummary(BaseModel):
    database: Path
    exists: bool
    total_calls: int = 0
    succeeded: int = 0
    failed: int = 0
    pending: int = 0
    interrupted: int = 0
    latest_call: AuditCallResponse | None = None
    error: str | None = None


class MutationReceipt(BaseModel):
    receipt_id: str
    administration_id: UUID
    tool: str
    operation: str
    started_at: str
    updated_at: str
    status: MutationStatus
    request_sha256: Sha256
    response_sha256: Sha256 | None = None
    record_id: str | None = None
    record_id_from_response: bool = False
    verification: str | None = None


class MutationLookupRequest(ToolRequest):
    receipt_id: Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]


class AuditReport(BaseModel):
    administration_id: UUID | None
    summary: AuditSummary
    calls: list[AuditCallResponse]
    mutations: list[MutationReceipt] = Field(default_factory=list)
