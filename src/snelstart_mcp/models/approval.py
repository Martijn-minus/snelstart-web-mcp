"""Private local records for one-use bookkeeping approvals."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from . import JsonObject


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
