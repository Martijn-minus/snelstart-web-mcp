"""Local, verifiable year archives. No SnelStart mutation is used here."""

import json
import os
import re
import shutil
import tempfile
from datetime import UTC, date, datetime
from hashlib import sha256
from importlib.resources import files
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile
from zlib import error as DecompressionError

from .client import Client
from .config import SnelStartError, Store
from .dates import AMSTERDAM
from .enums import ArchiveFormat
from .models import ArchiveManifest
from .models.responses import ArchiveInventory, ArchiveListEntry
from .year_data import DATASETS, collect

ARCHIVE_NAME = re.compile(r"snelstart-(\d{4})-[a-f0-9]{32}\.zip")
MAX_MEMBER = 2 * 1024**3
MAX_ARCHIVE = 10 * 1024**3
OFFICIAL_FORMATS = {
    "audit_file": ".xaf",
    "attachments": ".zip",
    "official_export": ".zip",
    "administration_backup": ".bacpac",
}
ARCHIVE_MEMBERS = {f"{kind}{suffix}" for kind, suffix in OFFICIAL_FORMATS.items()} | {
    f"{name}.json" for name in DATASETS
}
ARCHIVE_FORMAT = ArchiveFormat.YEAR_ARCHIVE_V2
LEGACY_ARCHIVE = json.loads(files("snelstart_mcp").joinpath("legacy_archive.json").read_text())
NATIVE_BACKUP_MEMBERS = {"administration_backup.bacpac", LEGACY_ARCHIVE["native_backup_member"]}
INVALID_ARCHIVE = (
    BadZipFile,
    ValueError,
    KeyError,
    TypeError,
    RuntimeError,
    AttributeError,
    DecompressionError,
)


def _legacy_manifest(raw: dict) -> dict:
    def rename(values, names):
        return {names.get(key, key): value for key, value in values.items()}

    manifest = rename(raw, LEGACY_ARCHIVE["manifest_keys"])
    manifest["stored_format"] = manifest["format"]
    manifest["format"] = ARCHIVE_FORMAT
    if "mcp_counts" in manifest:
        manifest["mcp_counts"] = rename(manifest["mcp_counts"], LEGACY_ARCHIVE["dataset_keys"])
    if "source_files" in manifest:
        sources = rename(manifest["source_files"], LEGACY_ARCHIVE["source_keys"])
        manifest["source_files"] = {
            key: rename(value, LEGACY_ARCHIVE["detail_keys"]) for key, value in sources.items()
        }
    if "mcp_scope" in manifest:
        scope = rename(manifest["mcp_scope"], LEGACY_ARCHIVE["scope_keys"])
        if "included" in scope:
            scope["included"] = [
                LEGACY_ARCHIVE["dataset_keys"].get(key, key) for key in scope["included"]
            ]
        manifest["mcp_scope"] = scope
    return manifest


def _record(stream, destination=None) -> dict:
    digest, size = sha256(), 0
    while chunk := stream.read(65536):
        size += len(chunk)
        if size > MAX_MEMBER:
            raise SnelStartError("Archive member exceeds 2 GiB.")
        digest.update(chunk)
        if destination is not None:
            destination.write(chunk)
    if not size:
        raise SnelStartError("Archive member is empty.")
    return {"bytes": size, "sha256": digest.hexdigest()}


def _audit_header(stream, year: int) -> dict:
    prefix = stream.read(65536)
    if b"<!DOCTYPE" in prefix.replace(b"\x00", b"").upper():
        raise SnelStartError("The audit file contains an unexpected DTD.")
    try:
        for _, node in ElementTree.iterparse(BytesIO(prefix), events=("end",)):
            if node.tag.rsplit("}", 1)[-1] == "header":
                keys = {"fiscalYear", "startDate", "endDate", "dateCreated"}
                values = {child.tag.rsplit("}", 1)[-1]: child.text for child in node}
                if values.get("fiscalYear") != str(year):
                    raise SnelStartError(
                        "The audit file fiscal year does not match the requested archive year."
                    )
                return {key: values[key] for key in sorted(keys & values.keys())}
    except ElementTree.ParseError:
        pass
    raise SnelStartError("No readable XAF audit file header was found.")


def _inspect_source(kind: str, path: Path, year: int) -> dict:
    if kind == "audit_file":
        with path.open("rb") as stream:
            return _audit_header(stream, year)
    try:
        with ZipFile(path) as container:
            members = container.infolist()
            if not members or sum(info.file_size for info in members) > MAX_MEMBER:
                raise SnelStartError(f"The {kind} source file is invalid or too large.")
            if kind == "administration_backup" and "model.xml" not in container.namelist():
                raise SnelStartError("The BACPAC file has no database model.")
            if container.testzip() is not None:
                raise SnelStartError(f"The {kind} source file contains a corrupt member.")
            if kind == "official_export":
                auditfiles = [info for info in members if info.filename.lower().endswith(".xaf")]
                if len(auditfiles) != 1:
                    raise SnelStartError("The official ZIP must contain exactly one audit file.")
                with container.open(auditfiles[0]) as content:
                    return {
                        "audit_file": _audit_header(content, year),
                        "attachment_count": sum(not item.is_dir() for item in members) - 1,
                    }
    except (BadZipFile, RuntimeError, NotImplementedError):
        raise SnelStartError(f"The {kind} source file is corrupt or unreadable.") from None
    return {}


def create_archive(
    store: Store,
    year: int,
    end: date,
    *,
    client: Client | None = None,
    audit_file: str | None = None,
    attachments: str | None = None,
    administration_backup: str | None = None,
    official_export: str | None = None,
) -> dict:
    today = datetime.now(AMSTERDAM).date()
    if not 1900 <= year <= today.year or end.year != year or end > today:
        raise SnelStartError("Choose an existing year and a through date no later than today.")
    supplied = {
        "audit_file": audit_file,
        "attachments": attachments,
        "administration_backup": administration_backup,
        "official_export": official_export,
    }
    if not any(supplied.values()) and client is None:
        raise SnelStartError("Specify source files or enable the live MCP export.")
    sources = {}
    for kind, source in supplied.items():
        if not source:
            continue
        source_path = Path(source).expanduser()
        suffix = OFFICIAL_FORMATS[kind]
        if (
            not source_path.is_absolute()
            or source_path.suffix.lower() != suffix
            or source_path.is_symlink()
            or not source_path.is_file()
        ):
            raise SnelStartError(f"Provide an absolute path to a regular {suffix} file for {kind}.")
        sources[kind] = source_path.resolve(strict=True)
    directory = Store(store.directory / "backups").directory
    identifier = uuid4().hex
    path = directory / f"snelstart-{year}-{identifier}.zip"
    administration = store.settings().administration_id if client else None
    if client and administration is None:
        raise SnelStartError("Select an administration before starting a live export.")
    manifest = {
        "format": ARCHIVE_FORMAT,
        "year": year,
        "through_date": end.isoformat(),
        "created_at": datetime.now(UTC).isoformat(),
        "files": {},
        "source_files": {},
        "bacpac_included": bool(administration_backup),
        "mcp_administration_id": str(administration) if administration else None,
        "mcp_scope": {
            "included": sorted(DATASETS) if client else [],
            "excluded": [
                "complete posting lines for purchase and sales invoices",
                "complete general ledger entries",
                "documents and attachments",
                "settings and integrations",
            ]
            if client
            else [],
            "selection": "calendar year, all purchase and sales statuses, and a VAT overview for all years",
        },
    }
    with tempfile.TemporaryDirectory(dir=directory) as staging:
        stage = Path(staging)
        stable_sources = {}
        for kind, source_path in sources.items():
            name = kind + OFFICIAL_FORMATS[kind]
            staged = stage / name
            fd = os.open(staged, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as target, source_path.open("rb") as stream:
                manifest["files"][name] = _record(stream, target)
            manifest["source_files"][kind] = _inspect_source(kind, staged, year)
            stable_sources[name] = staged
        temporary = stage / "archive.zip"
        os.close(os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as archive:
            if client is not None and administration is not None:
                data = collect(client, year, end, str(administration))
                if store.settings().administration_id != administration:
                    raise SnelStartError("The selected administration changed during export.")
                manifest["mcp_counts"] = {
                    key: len(rows) for key, rows in data.items() if isinstance(rows, list)
                }
                manifest["mcp_counts"]["bank_entries"] = sum(
                    len(row["entries"]) for row in data["bank_entries"]
                )
                manifest["mcp_counts"]["journal_and_opening_entries"] = sum(
                    len(row["entries"]) for row in data["journal_and_opening_entries"]
                )
                for key, content in data.items():
                    name = key + ".json"
                    payload = json.dumps(
                        content, ensure_ascii=False, separators=(",", ":")
                    ).encode()
                    archive.writestr(name, payload)
                    manifest["files"][name] = {
                        "bytes": len(payload),
                        "sha256": sha256(payload).hexdigest(),
                    }
            for name, staged in stable_sources.items():
                archive.write(staged, arcname=name)
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        _read_verified(temporary, year)
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
            digest = sha256()
            while chunk := stream.read(65536):
                digest.update(chunk)
        os.link(temporary, path)
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    return {
        **manifest,
        "path": str(path),
        "archive": path.name,
        "verified": True,
        "archive_sha256": digest.hexdigest(),
    }


def _verified(store: Store, name: str, destination: Path | None = None) -> dict:
    match = ARCHIVE_NAME.fullmatch(name)
    if not match:
        raise SnelStartError("Provide the archive name returned by the archive tool.")
    directory = Store(store.directory / "backups").directory
    path = directory / name
    if path.is_symlink() or not path.is_file():
        raise SnelStartError("Year archive not found.")
    manifest = _read_verified(path, int(match[1]), destination)
    return {**manifest, "path": str(path), "archive": name, "verified": True}


def _read_manifest(archive: ZipFile, year: int) -> tuple[dict, ArchiveManifest]:
    entries = archive.namelist()
    if (
        len(entries) != len(set(entries))
        or archive.getinfo("manifest.json").file_size > 65536
        or sum(info.file_size for info in archive.infolist()) > MAX_ARCHIVE
    ):
        raise SnelStartError("Invalid archive manifest.")
    manifest = json.loads(archive.read("manifest.json"))
    allowed_members = ARCHIVE_MEMBERS
    if isinstance(manifest, dict) and manifest.get("format") == LEGACY_ARCHIVE["version"]:
        manifest = _legacy_manifest(manifest)
        allowed_members = set(LEGACY_ARCHIVE["files"])
    parsed = ArchiveManifest.model_validate(manifest)
    if (
        parsed.year != year
        or parsed.through_date.year != year
        or not parsed.files.keys() <= allowed_members
        or set(entries) != {*parsed.files, "manifest.json"}
    ):
        raise SnelStartError("The archive contents do not match its manifest.")
    return manifest, parsed


def _read_verified(path: Path, year: int, destination: Path | None = None) -> dict:
    try:
        with ZipFile(path) as archive:
            manifest, parsed = _read_manifest(archive, year)
            for member, expected in parsed.files.items():
                with archive.open(member) as stream:
                    if destination:
                        fd = os.open(
                            destination / member, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
                        )
                        with os.fdopen(fd, "wb") as target:
                            observed = _record(stream, target)
                    else:
                        observed = _record(stream)
                if observed != expected.model_dump():
                    raise SnelStartError(f"Checksum mismatch for {member}.")
        return manifest
    except INVALID_ARCHIVE:
        raise SnelStartError("The year archive is corrupt or has an unknown format.") from None


def verify_archive(store: Store, name: str) -> dict:
    return _verified(store, name)


def list_archives(store: Store) -> ArchiveInventory:
    directory = store.directory / "backups"
    if directory.is_symlink():
        return ArchiveInventory(directory=directory, error="The backups folder is a symbolic link.")
    try:
        candidates = list(directory.iterdir())
    except FileNotFoundError:
        candidates = []
    except OSError:
        return ArchiveInventory(
            directory=directory, error="Could not read the local backups folder."
        )

    entries = []
    for path in candidates:
        match = ARCHIVE_NAME.fullmatch(path.name)
        if match is None or path.is_symlink() or not path.is_file():
            continue
        year = int(match[1])
        try:
            with ZipFile(path) as archive:
                manifest, parsed = _read_manifest(archive, year)
            entry = ArchiveListEntry.model_validate(
                {
                    "archive": path.name,
                    "path": path,
                    "year": year,
                    "through_date": parsed.through_date,
                    "created_at": manifest.get("created_at"),
                    "mcp_administration_id": manifest.get("mcp_administration_id"),
                    "bacpac_included": bool(NATIVE_BACKUP_MEMBERS & parsed.files.keys()),
                    "manifest_readable": True,
                }
            )
        except (SnelStartError, OSError, *INVALID_ARCHIVE):
            entry = ArchiveListEntry(
                archive=path.name, path=path, year=year, manifest_readable=False
            )
        entries.append(entry)
    oldest = datetime.min.replace(tzinfo=UTC)
    entries.sort(key=lambda item: (item.created_at or oldest, item.archive), reverse=True)
    return ArchiveInventory(directory=directory, archives=entries)


def unpack_archive(store: Store, name: str) -> dict:
    directory = Store(store.directory / "extracted").directory
    target = Path(tempfile.mkdtemp(prefix="snelstart-", dir=directory))
    try:
        manifest = _verified(store, name, target)
    except BaseException:
        shutil.rmtree(target)
        raise
    return {
        **manifest,
        "directory": str(target),
        "restore_instructions": (
            "Use the BACPAC file with the restore backup option in SnelStart 12."
            if NATIVE_BACKUP_MEMBERS & manifest["files"].keys()
            else "This year archive does not contain a native administration backup."
        ),
    }
