"""The write permission editor's selection and menu rows."""

from pydantic import BaseModel, Field


class WriteSelection(BaseModel):
    allow_writes: bool
    operations: set[str] = Field(default_factory=set)


class PermissionRow(BaseModel):
    label: str
    operations: frozenset[str] | None = None
    group: str | None = None
    detail: bool = False
