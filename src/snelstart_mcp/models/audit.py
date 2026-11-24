"""Local audit storage and CLI contracts."""

from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from ..enums import AuditOutcome


class AuditCallStart(BaseModel, frozen=True):
    call_id: str
    administration_id: UUID | None


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


class AuditReport(BaseModel):
    administration_id: UUID | None
    summary: AuditSummary
    calls: list[AuditCallResponse]
