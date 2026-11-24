"""Display calendar releases alongside their package versions."""

from datetime import date
from importlib.metadata import PackageNotFoundError, version

from packaging.version import InvalidVersion, Version

PACKAGE = "snelstart-web-mcp"


def installed_version() -> str | None:
    try:
        return version(PACKAGE)
    except PackageNotFoundError:
        return None


def version_label(value: str | None) -> str:
    if not value:
        return "unknown version"
    try:
        parts = Version(value).release
        if len(parts) == 3 and parts[0] >= 2000:
            release_date = date(*parts)
            return f"{value} ({release_date.day} {release_date:%B %Y})"
    except (InvalidVersion, ValueError):
        pass
    return value
