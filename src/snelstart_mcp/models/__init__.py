"""Validated on-disk configuration and archive records."""

from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictBool, StringConstraints

from ..enums import ArchiveFormat

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
JsonObject = dict[str, JsonValue]


class Settings(BaseModel):
    # Older configuration files may contain local fields owned by the CLI or HAR importer.
    model_config = ConfigDict(extra="allow")

    administration_id: UUID | None = None
    session_id: UUID | None = None
    allow_writes: StrictBool = False
    write_permissions: dict[UUID, set[str]] = Field(default_factory=dict)

    def approved_write_operations(self) -> set[str]:
        if self.administration_id is None:
            return set()
        return self.write_permissions.get(self.administration_id, set())


class ArchiveFile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    bytes: Annotated[int, Field(gt=0)]
    sha256: Sha256


class ArchiveManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    format: ArchiveFormat
    year: Annotated[int, Field(strict=True, ge=1900, le=9999)]
    through_date: date
    files: Annotated[dict[str, ArchiveFile], Field(min_length=1)]


class ApiPage(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")

    totalMatchCount: Annotated[int, Field(ge=0)]
    resultList: list[JsonObject]
