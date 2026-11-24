"""Package provenance and public update check results."""

from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from ..enums import UpdateStatus


class InstalledGitSource(BaseModel):
    vcs: Literal["git"]
    commit_id: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
    requested_revision: str | None = None


class InstalledSource(BaseModel):
    url: str
    vcs_info: InstalledGitSource | None = None


class GitHubComparison(BaseModel):
    status: Literal["ahead", "behind", "diverged", "identical"]


class PyPIProjectInfo(BaseModel):
    version: str


class PyPIProject(BaseModel):
    info: PyPIProjectInfo


class UpdateCheckResponse(BaseModel):
    status: UpdateStatus
    installed_version: str | None
    running_version: str | None = None
    installed_commit: str | None = None
    latest_version: str | None = None
    message: str
