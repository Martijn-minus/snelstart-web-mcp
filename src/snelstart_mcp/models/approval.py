"""Records and tool contracts for one-use bookkeeping approvals."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..enums import WriteApprovalStatus
from . import JsonObject
from .requests import ToolRequest

MAX_PENDING = 24


class WriteIntent(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    tool: str
    operation: str
    administration_id: UUID
    details: JsonObject


class PendingWrite(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    intent: WriteIntent
    expires: float
    approved: bool = False


class WriteApprovalReviewRequest(ToolRequest):
    approval_ids: list[UUID] = Field(min_length=1, max_length=MAX_PENDING)

    @model_validator(mode="after")
    def distinct_approvals(self):
        if len(set(self.approval_ids)) != len(self.approval_ids):
            raise ValueError("Provide each approval ID only once.")
        return self


class WriteApprovalReviewResponse(BaseModel):
    approval_ids: list[UUID]
    expires_at: datetime
    message: str


class WriteApprovalState(BaseModel):
    approval_id: UUID
    status: WriteApprovalStatus
    expires_at: datetime | None = None


class WriteConfirmationSettings(BaseModel):
    administration_id: UUID | None
    write_confirmations_required: bool
