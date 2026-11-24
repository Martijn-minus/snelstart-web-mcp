"""Compare verified booking datasets across two local snapshots."""

import json
from collections import Counter
from uuid import UUID

from pydantic import JsonValue

from .config import SnelStartError, Store
from .enums import ArchiveChange, ArchiveDataset
from .models import JsonObject
from .models.review import ArchiveComparison, BookingChange, CompareArchivesRequest
from .snapshot import GROUPED_DATASETS, open_snapshot

KEYS = {
    ArchiveDataset.PURCHASES: ("publicIdentifier", "factuurnummeridentifier", "factuurId"),
    ArchiveDataset.SALES: ("factuurNummerPublicIdentifier", "verkoopOrderId", "factuurNummerId"),
    ArchiveDataset.BANK_ENTRIES: ("identifier", "publicIdentifier"),
    ArchiveDataset.JOURNAL_AND_OPENING_ENTRIES: ("publicIdentifier",),
}


def _identity(value: JsonValue | None) -> str | None:
    if not isinstance(value, (str, int)) or isinstance(value, bool) or value in ("", 0):
        return None
    text = str(value).strip()
    if not 1 <= len(text) <= 128:
        return None
    try:
        return str(UUID(text))
    except ValueError:
        return text


def _index(
    value: JsonValue, dataset: ArchiveDataset
) -> tuple[dict[tuple[str, str], JsonObject], set[str]]:
    if not isinstance(value, list):
        raise SnelStartError("The selected archive contains invalid booking rows.")
    groups: list[tuple[str, list[JsonValue]]] = []
    if dataset in GROUPED_DATASETS:
        seen = set()
        for group in value:
            if not isinstance(group, dict):
                raise SnelStartError("The selected archive contains invalid journal groups.")
            journal = group.get("journal_id", group.get("dagboek"))
            if isinstance(journal, dict):
                journal = journal.get("grootboekIdentifier")
            identifier = _identity(journal)
            entries = group.get("entries", group.get("mutaties", group.get("boekingen")))
            if identifier is None or identifier in seen or not isinstance(entries, list):
                raise SnelStartError("An archived journal ID is missing or duplicated.")
            seen.add(identifier)
            groups.append((identifier, entries))
    else:
        groups.append(("", value))

    rows = {}
    for journal, entries in groups:
        for entry in entries:
            if not isinstance(entry, dict):
                raise SnelStartError("The selected archive contains an invalid booking row.")
            identifier = next(
                (
                    text
                    for name in KEYS[dataset]
                    if (text := _identity(entry.get(name))) is not None
                ),
                None,
            )
            if identifier is None or (journal, identifier) in rows:
                raise SnelStartError("An archived booking ID is missing or duplicated.")
            rows[journal, identifier] = entry
    return rows, {journal for journal, _ in groups}


def compare_archives(store: Store, request: CompareArchivesRequest) -> ArchiveComparison:
    dataset = ArchiveDataset(request.dataset.value)
    with (
        open_snapshot(store, request.before) as before,
        open_snapshot(store, request.after) as after,
    ):
        previous, current = before.info, after.info
        administration = previous.mcp_administration_id
        if administration is None or administration != current.mcp_administration_id:
            raise SnelStartError("Both archives must identify the same administration.")
        if (previous.year, previous.through_date) != (current.year, current.through_date):
            raise SnelStartError("Both archives must cover the same year and cutoff date.")
        old, old_journals = _index(before.load(dataset), dataset)
        new, new_journals = _index(after.load(dataset), dataset)
        if old_journals != new_journals:
            raise SnelStartError("The archives contain different journal coverage.")

    changes = []
    counts: Counter[ArchiveChange] = Counter()
    unchanged = 0
    for journal, identifier in sorted(old.keys() | new.keys()):
        left, right = old.get((journal, identifier)), new.get((journal, identifier))
        fields = []
        if left is None:
            change = ArchiveChange.ADDED
        elif right is None:
            change = ArchiveChange.REMOVED
        else:
            fields = sorted(
                key
                for key in left.keys() | right.keys()
                if key not in left
                or key not in right
                or json.dumps(left[key], sort_keys=True) != json.dumps(right[key], sort_keys=True)
            )
            if not fields:
                unchanged += 1
                continue
            change = ArchiveChange.CHANGED
        counts[change] += 1
        if request.skip <= sum(counts.values()) - 1 < request.skip + request.take:
            changes.append(
                BookingChange(
                    identifier=identifier,
                    journal_id=journal or None,
                    change=change,
                    fields_changed=fields,
                )
            )
    end = request.skip + len(changes)
    return ArchiveComparison(
        before=previous.archive,
        after=current.archive,
        administration_id=administration,
        year=previous.year,
        through_date=previous.through_date,
        dataset=request.dataset,
        added=counts[ArchiveChange.ADDED],
        removed=counts[ArchiveChange.REMOVED],
        changed=counts[ArchiveChange.CHANGED],
        unchanged=unchanged,
        next_skip=end if end < sum(counts.values()) else None,
        entries=changes,
    )
