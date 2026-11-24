"""Input and output contracts for an offline year snapshot."""

from datetime import date
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field, JsonValue, model_validator

from ..enums import ArchiveDataset
from .requests import ToolRequest


class SnapshotReadRequest(ToolRequest):
    dataset: ArchiveDataset
    section: str | None = None
    group_index: Annotated[int, Field(ge=0)] | None = None
    skip: Annotated[int, Field(ge=0)] = 0
    take: Annotated[int, Field(ge=1, le=100)] = 50

    @model_validator(mode="after")
    def one_selection(self):
        if self.section is not None and self.group_index is not None:
            raise ValueError("Choose a section or a journal group.")
        return self


class SnapshotInfo(BaseModel):
    mode: Literal["offline"] = "offline"
    read_only: Literal[True] = True
    archive: str
    path: Path
    year: int
    through_date: date
    size_bytes: int = Field(ge=0)
    created_at: AwareDatetime | None = None
    mcp_administration_id: UUID | None = None
    bacpac_included: bool
    datasets: list[ArchiveDataset]
    excluded: list[str] = Field(default_factory=list)


class SnapshotPage(BaseModel):
    archive: str
    year: int
    through_date: date
    created_at: AwareDatetime | None
    mcp_administration_id: UUID | None
    dataset: ArchiveDataset
    total: int
    next_skip: int | None
    data: list[JsonValue]
