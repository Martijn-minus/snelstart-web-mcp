"""Check the public package source and upgrade a uv-managed installation."""

import subprocess
import sys
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from shutil import which
from time import monotonic

import httpx
from packaging.version import Version

from .config import SnelStartError
from .enums import UpdateStatus
from .models.responses import ToolUpdateResponse
from .models.update import GitHubComparison, InstalledSource, PyPIProject, UpdateCheckResponse
from .version import PACKAGE, installed_version, version_label

REPOSITORY = "Martijn-minus/snelstart-web-mcp"
UPSTREAM = f"https://github.com/{REPOSITORY}"
CHECK_INTERVAL = 3600
RETRY_INTERVAL = 60


def _check_pypi(version: str) -> UpdateCheckResponse:
    try:
        response = httpx.get(
            f"https://pypi.org/pypi/{PACKAGE}/json",
            timeout=2.0,
            follow_redirects=False,
            trust_env=False,
        )
        if response.status_code == 404:
            return UpdateCheckResponse(
                status=UpdateStatus.UNAVAILABLE,
                installed_version=version,
                message="No release is listed on PyPI yet.",
            )
        response.raise_for_status()
        latest = PyPIProject.model_validate_json(response.content).info.version
        available = Version(latest) > Version(version)
    except (httpx.HTTPError, ValueError):
        return UpdateCheckResponse(
            status=UpdateStatus.UNAVAILABLE,
            installed_version=version,
            message="Could not check PyPI for updates. Try again later.",
        )
    message = (
        f"SnelStart MCP {version_label(latest)} is available. Run 'snelstart-mcp update', then reconnect."
        if available
        else "You are on the latest PyPI release or newer."
    )
    return UpdateCheckResponse(
        status=UpdateStatus.AVAILABLE if available else UpdateStatus.CURRENT,
        installed_version=version,
        latest_version=latest,
        message=message,
    )


def _check_update() -> UpdateCheckResponse:
    version = None
    commit = None
    try:
        package = distribution(PACKAGE)
        version = package.version
        metadata = package.read_text("direct_url.json")
        if metadata is None:
            return _check_pypi(version)
        source = InstalledSource.model_validate_json(metadata)
    except (OSError, ValueError, PackageNotFoundError):
        source = None

    if source is None or source.url not in {UPSTREAM, UPSTREAM + ".git"} or not source.vcs_info:
        return UpdateCheckResponse(
            status=UpdateStatus.UNAVAILABLE,
            installed_version=version,
            message="Update checks are available for installations from the official GitHub repository.",
        )

    commit = source.vcs_info.commit_id
    if source.vcs_info.requested_revision not in {None, "main", "refs/heads/main"}:
        return UpdateCheckResponse(
            status=UpdateStatus.UNAVAILABLE,
            installed_version=version,
            installed_commit=commit,
            message="This installation is pinned to a Git revision. Use its installation source to update.",
        )

    try:
        response = httpx.get(
            f"https://api.github.com/repos/{REPOSITORY}/compare/{commit}...main",
            params={"per_page": 1},
            headers={"Accept": "application/vnd.github+json"},
            timeout=2.0,
            follow_redirects=False,
            trust_env=False,
        )
        response.raise_for_status()
        comparison = GitHubComparison.model_validate_json(response.content)
    except (httpx.HTTPError, ValueError):
        status = UpdateStatus.UNAVAILABLE
        message = "Could not check GitHub for updates. Try again later."
    else:
        if comparison.status == "ahead":
            status = UpdateStatus.AVAILABLE
            message = "SnelStart MCP update available. Run 'snelstart-mcp update' locally, then reconnect the MCP client."
        elif comparison.status == "identical":
            status = UpdateStatus.CURRENT
            message = "You are using the latest published GitHub revision."
        else:
            status = UpdateStatus.UNAVAILABLE
            message = "This installation differs from the public main branch. Check its source before updating."
    return UpdateCheckResponse(
        status=status, installed_version=version, installed_commit=commit, message=message
    )


class UpdateChecker:
    def __init__(self, *, running_version: str | None = None) -> None:
        self._running_version = running_version
        self._result: UpdateCheckResponse | None = None
        self._expires_at = 0.0

    def check(self, *, refresh: bool = False) -> UpdateCheckResponse:
        if self._running_version is not None:
            installed = installed_version()
            if installed is not None and installed != self._running_version:
                return UpdateCheckResponse(
                    status=UpdateStatus.RECONNECT_REQUIRED,
                    running_version=self._running_version,
                    installed_version=installed,
                    message=f"Reconnect the MCP client to load SnelStart MCP {version_label(installed)}.",
                )
        if refresh or self._result is None or monotonic() >= self._expires_at:
            self._result = _check_update().model_copy(
                update={"running_version": self._running_version}
            )
            interval = (
                RETRY_INTERVAL
                if self._result.status is UpdateStatus.UNAVAILABLE
                else CHECK_INTERVAL
            )
            self._expires_at = monotonic() + interval
        return self._result


def update_tool() -> ToolUpdateResponse:
    uv = which("uv")
    if not uv:
        raise SnelStartError("Install uv and make sure it is on your PATH to update this tool.")
    try:
        directory = subprocess.run(
            [uv, "tool", "dir"], check=True, capture_output=True, text=True
        ).stdout.strip()
        if not directory or (Path(directory) / PACKAGE).resolve() != Path(sys.prefix).resolve():
            raise SnelStartError(
                "This executable is outside the active uv tool installation. "
                "Use the installation method that provided it. For a source checkout, "
                "pull the repository and run 'uv sync --locked'."
            )
        subprocess.run([uv, "tool", "upgrade", PACKAGE], check=True, stdout=sys.stderr)
    except (OSError, subprocess.CalledProcessError):
        raise SnelStartError(
            "The uv tool update failed. Check the uv output and try again."
        ) from None
    return ToolUpdateResponse(package=PACKAGE, completed=True)
