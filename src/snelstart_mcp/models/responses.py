"""MCP and CLI output contracts."""

from pathlib import Path
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictInt, StrictStr

from . import ArchiveManifest, Sha256
from .api import OperationSpec
from .audit import AuditSummary
from .update import UpdateCheckResponse

T = TypeVar("T")


class DataResponse(BaseModel, Generic[T]):
    data: T


class ConnectionStatus(BaseModel):
    configured: bool
    automatic_login: bool
    automatic_refresh: bool
    access_token_expires_at: int | float | None
    administration_id: UUID | None
    allow_writes: bool
    approved_write_operations: list[str]
    config_directory: Path
    server_version: str | None = Field(default=None, exclude_if=lambda value: value is None)
    update: UpdateCheckResponse | None = Field(default=None, exclude_if=lambda value: value is None)


class AdministrationResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    identifier: UUID


class SelectedAdministration(BaseModel):
    identifier: UUID
    opened: bool


class OperationResponse(OperationSpec):
    operation: str


class OperationListResponse(BaseModel):
    total: int
    operations: list[OperationResponse]


class DownloadResponse(BaseModel):
    path: Path
    original_filename: str | None
    content_type: str
    bytes: int
    sha256: Sha256


class ArchiveListEntry(BaseModel):
    archive: str
    path: Path


class VerifiedArchiveResponse(ArchiveManifest, ArchiveListEntry):
    verified: bool


class CreatedArchiveResponse(VerifiedArchiveResponse):
    archive_sha256: Sha256


class ExtractedArchiveResponse(VerifiedArchiveResponse):
    directory: Path
    restore_instructions: str


class PurchaseUploadResponse(BaseModel):
    instance_id: str
    sha256: Sha256
    already_submitted: bool
    tracking_saved: bool | None = Field(default=None, exclude_if=lambda value: value is None)


class UploadStatusResponse(BaseModel):
    instance_id: str
    status: StrictStr | StrictInt


class AdministrationSummary(BaseModel):
    identifier: UUID | None
    name: str | None


class DoctorResponse(ConnectionStatus):
    connected: bool
    administration_name: str | None
    administration_count: int
    administrations: list[AdministrationSummary]
    audit: AuditSummary


class ToolUpdateResponse(BaseModel):
    package: str
    completed: bool


class SkillInstallResponse(BaseModel):
    name: str
    path: Path
    status: Literal["preview", "installed", "already_configured"]


class HarImportResponse(BaseModel):
    imported: bool
    password_saved: bool
    observed_operations: int


JsonResponse = DataResponse[JsonValue]
