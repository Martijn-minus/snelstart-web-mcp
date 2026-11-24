"""Read a local accounting snapshot without creating a SnelStart client."""

import json
import os
from contextlib import contextmanager
from io import BytesIO
from stat import S_ISREG
from zipfile import ZipFile

from pydantic import JsonValue

from .backup import (
    ARCHIVE_NAME,
    INVALID_ARCHIVE,
    LEGACY_ARCHIVE,
    NATIVE_BACKUP_MEMBERS,
    _read_manifest,
    _record,
)
from .config import SnelStartError, Store
from .enums import ArchiveDataset
from .models import ArchiveFile
from .models.snapshot import SnapshotInfo, SnapshotPage, SnapshotReadRequest

MAX_DATASET_BYTES = 64 * 1024**2
MAX_PAGE_BYTES = 512 * 1024
GROUPED_DATASETS = {ArchiveDataset.BANK_ENTRIES, ArchiveDataset.JOURNAL_AND_OPENING_ENTRIES}


@contextmanager
def open_snapshot(store: Store, name: str):
    match = ARCHIVE_NAME.fullmatch(name)
    if not match:
        raise SnelStartError("Use the archive filename shown by doctor --json.")
    directory = store.directory / "backups"
    if directory.is_symlink():
        raise SnelStartError("The backups folder is a symbolic link.")
    path = directory / name
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise SnelStartError("Could not open the selected local archive.") from None
    metadata = os.fstat(fd)
    if not S_ISREG(metadata.st_mode):
        os.close(fd)
        raise SnelStartError("The selected archive must be a regular file.")
    with os.fdopen(fd, "rb") as stream:
        try:
            archive = ZipFile(stream)
        except INVALID_ARCHIVE:
            raise SnelStartError("The selected archive ZIP is unreadable.") from None
        with archive:
            try:
                manifest, parsed = _read_manifest(archive, int(match[1]))
                legacy = manifest.get("stored_format") == LEGACY_ARCHIVE["version"]
                names = {name: old for old, name in LEGACY_ARCHIVE["dataset_keys"].items()}
                members = {}
                for dataset in ArchiveDataset:
                    filename = (names[dataset.value] if legacy else dataset.value) + ".json"
                    if filename in parsed.files:
                        members[dataset] = (filename, parsed.files[filename])
                if not members:
                    raise SnelStartError(
                        "This archive contains no MCP datasets. Choose a year archive made with live_export."
                    )
                info = SnapshotInfo.model_validate(
                    {
                        **manifest,
                        "archive": name,
                        "path": path,
                        "size_bytes": metadata.st_size,
                        "bacpac_included": bool(NATIVE_BACKUP_MEMBERS & parsed.files.keys()),
                        "datasets": sorted(members),
                        "excluded": manifest.get("mcp_scope", {}).get("excluded", []),
                    }
                )
            except INVALID_ARCHIVE:
                raise SnelStartError("The selected archive has an unreadable manifest.") from None
            yield Snapshot(archive, info, members)


class Snapshot:
    def __init__(
        self,
        archive: ZipFile,
        info: SnapshotInfo,
        members: dict[ArchiveDataset, tuple[str, ArchiveFile]],
    ):
        self.archive = archive
        self.info = info
        self.members = members

    def read(self, request: SnapshotReadRequest) -> SnapshotPage:
        member = self.members.get(request.dataset)
        if member is None:
            raise SnelStartError("This dataset is unavailable in the selected archive.")
        name, expected = member
        if max(expected.bytes, self.archive.getinfo(name).file_size) > MAX_DATASET_BYTES:
            raise SnelStartError(
                "This dataset is too large to query here. Extract the ZIP locally."
            )
        try:
            with self.archive.open(name) as stream, BytesIO() as payload:
                if _record(stream, payload) != expected.model_dump():
                    raise SnelStartError(f"Checksum mismatch for {name}.")
                value = json.loads(payload.getvalue())
        except INVALID_ARCHIVE:
            raise SnelStartError("The archived dataset is unreadable.") from None

        rows = self._rows(value, request)
        page = rows[request.skip : request.skip + request.take]
        if len(json.dumps(page, ensure_ascii=False).encode()) > MAX_PAGE_BYTES:
            raise SnelStartError(
                "Choose a smaller page or select a section. Large records can be read from the extracted ZIP."
            )
        end = request.skip + len(page)
        return SnapshotPage(
            archive=self.info.archive,
            year=self.info.year,
            through_date=self.info.through_date,
            created_at=self.info.created_at,
            mcp_administration_id=self.info.mcp_administration_id,
            dataset=request.dataset,
            total=len(rows),
            next_skip=end if end < len(rows) else None,
            data=page,
        )

    @staticmethod
    def _rows(value: JsonValue, request: SnapshotReadRequest) -> list[JsonValue]:
        if request.section is not None:
            if not isinstance(value, dict) or request.section not in value:
                raise SnelStartError("The selected section is unavailable in this dataset.")
            value = value[request.section]
        elif request.dataset in GROUPED_DATASETS:
            if not isinstance(value, list):
                raise SnelStartError("The archived journals are unreadable.")
            if request.group_index is not None:
                if request.group_index >= len(value):
                    raise SnelStartError("The selected journal group is unavailable.")
                return Snapshot._entries(value[request.group_index])
            return [
                {
                    "group_index": index,
                    "journal": row.get("journal_id", row.get("dagboek"))
                    if isinstance(row, dict)
                    else None,
                    "entry_count": len(Snapshot._entries(row)),
                }
                for index, row in enumerate(value)
            ]
        elif request.group_index is not None:
            raise SnelStartError("This dataset has no journal groups.")
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            if request.section is not None:
                return [{"key": key, "value": item} for key, item in value.items()]
            return [
                {
                    "section": section,
                    "item_count": len(item) if isinstance(item, (dict, list)) else 1,
                }
                for section, item in value.items()
            ]
        return [value]

    @staticmethod
    def _entries(group: JsonValue) -> list[JsonValue]:
        if isinstance(group, dict):
            for key in ("entries", "mutaties", "boekingen"):
                rows = group.get(key)
                if isinstance(rows, list):
                    return rows
        raise SnelStartError("The archived journal entries are unreadable.")
