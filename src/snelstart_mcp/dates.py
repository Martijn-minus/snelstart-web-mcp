"""Date bounds in the accounting administration’s time zone."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from .config import SnelStartError

AMSTERDAM = ZoneInfo("Europe/Amsterdam")


def window(start: date, end: date) -> tuple[str, str]:
    if start > end:
        raise SnelStartError("The start date must be on or before the end date.")
    first = datetime.combine(start, time.min, AMSTERDAM).astimezone(UTC)
    last = datetime.combine(end, time(23, 59, 59, 999000), AMSTERDAM).astimezone(UTC)
    return first.isoformat(timespec="milliseconds"), last.isoformat(timespec="milliseconds")
