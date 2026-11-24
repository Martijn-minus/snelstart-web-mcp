import asyncio
import json
import sys
from hashlib import sha256
from zipfile import ZipFile

import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from snelstart_mcp import backup
from snelstart_mcp.client import Client
from snelstart_mcp.config import SnelStartError, Store
from snelstart_mcp.models.snapshot import SnapshotReadRequest
from snelstart_mcp.server import create_server
from snelstart_mcp.snapshot import open_snapshot

ARCHIVE = "snelstart-2024-" + "a" * 32 + ".zip"
ARCHIVE_ADMIN = "11111111-1111-4111-8111-111111111111"
LIVE_ADMIN = "22222222-2222-4222-8222-222222222222"


def archive_fixture(store, *, legacy=False, damaged=False):
    directory = store.directory / "backups"
    directory.mkdir()
    path = directory / ARCHIVE
    filename = "bankmutaties.json" if legacy else "bank_entries.json"
    group = {
        ("dagboek" if legacy else "journal_id"): "example bank",
        ("mutaties" if legacy else "entries"): [{"amount": 1}, {"amount": 2}],
    }
    payload = json.dumps([group]).encode()
    manifest = {
        "format": backup.LEGACY_ARCHIVE["version"] if legacy else backup.ARCHIVE_FORMAT,
        "year": 2024,
        "through_date": "2024-11-30",
        "created_at": "2024-12-01T01:00:00Z",
        "mcp_administration_id": ARCHIVE_ADMIN,
        "files": {filename: {"bytes": len(payload), "sha256": sha256(payload).hexdigest()}},
    }
    if legacy:
        keys = {value: key for key, value in backup.LEGACY_ARCHIVE["manifest_keys"].items()}
        manifest = {keys.get(key, key): value for key, value in manifest.items()}
    with ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr(filename, b"[]" if damaged else payload)
    return path


@pytest.mark.parametrize("legacy", [False, True])
def test_snapshot_lists_saved_groups_and_pages_records(tmp_path, legacy):
    store = Store(tmp_path)
    archive_fixture(store, legacy=legacy)
    with open_snapshot(store, ARCHIVE) as snapshot:
        assert snapshot.info.datasets == ["bank_entries"]
        summary = snapshot.read(SnapshotReadRequest(dataset="bank_entries"))
        assert summary.data == [{"group_index": 0, "journal": "example bank", "entry_count": 2}]
        page = snapshot.read(SnapshotReadRequest(dataset="bank_entries", group_index=0, take=1))
        assert page.data == [{"amount": 1}] and page.next_skip == 1
        page = snapshot.read(SnapshotReadRequest(dataset="bank_entries", group_index=0, skip=1))
        assert page.data == [{"amount": 2}] and page.next_skip is None
        with pytest.raises(SnelStartError, match="unavailable"):
            snapshot.read(SnapshotReadRequest(dataset="sales"))


def test_snapshot_checks_member_integrity_and_rejects_symlinks(tmp_path):
    store = Store(tmp_path)
    path = archive_fixture(store, damaged=True)
    with (
        open_snapshot(store, ARCHIVE) as snapshot,
        pytest.raises(SnelStartError, match="Checksum mismatch"),
    ):
        snapshot.read(SnapshotReadRequest(dataset="bank_entries"))
    renamed = path.rename(path.with_suffix(".bak"))
    path.symlink_to(renamed)
    with pytest.raises(SnelStartError, match="Could not open"), open_snapshot(store, ARCHIVE):
        pytest.fail("Symlink was opened")


def test_snapshot_stdio_keeps_network_and_live_tools_out(tmp_path):
    store = Store(tmp_path)
    store.write("config.json", {"administration_id": LIVE_ADMIN, "allow_writes": True})
    archive_fixture(store)
    script = """
import socket
from snelstart_mcp import cli
from snelstart_mcp.updater import UpdateChecker
def blocked(*args, **kwargs):
    raise AssertionError("Offline attempted live access")
socket.socket.connect = blocked
socket.socket.connect_ex = blocked
socket.getaddrinfo = blocked
cli.Client = blocked
UpdateChecker.check = blocked
cli.main()
"""

    async def verify():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=[
                "-c",
                script,
                "--config-dir",
                str(tmp_path),
                "serve",
                "--offline-archive",
                ARCHIVE,
            ],
        )
        async with (
            stdio_client(parameters) as (reader, writer),
            ClientSession(reader, writer) as mcp,
        ):
            initialized = await mcp.initialize()
            assert initialized.serverInfo.name == "snelstart-offline"
            assert {tool.name for tool in (await mcp.list_tools()).tools} == {
                "snelstart_snapshot_info",
                "snelstart_snapshot_read",
            }
            info = await mcp.call_tool("snelstart_snapshot_info")
            assert not info.isError and info.structuredContent["mode"] == "offline"
            page = await mcp.call_tool(
                "snelstart_snapshot_read", {"dataset": "bank_entries", "group_index": 0, "take": 1}
            )
            assert not page.isError and page.structuredContent["data"] == [{"amount": 1}]

    asyncio.run(verify())
    assert (tmp_path / "audit" / f"{ARCHIVE_ADMIN}.sqlite3").is_file()
    assert not (tmp_path / "audit" / f"{LIVE_ADMIN}.sqlite3").exists()
    assert store.settings().allow_writes


def test_live_read_only_overrides_grants_only_for_the_current_process(tmp_path):
    store = Store(tmp_path)
    store.write("config.json", {"administration_id": LIVE_ADMIN, "allow_writes": True})

    def blocked(_request):
        pytest.fail("A write reached the network")

    with httpx.Client(transport=httpx.MockTransport(blocked)) as http:
        client = Client(store, http, read_only=True)
        server = create_server(client)
        names = {tool.name for tool in asyncio.run(server.list_tools())}
        assert "snelstart_read" in names and "snelstart_create_year_archive" in names
        assert "snelstart_write" not in names and "snelstart_upload_purchase_pdf" not in names
        with pytest.raises(SnelStartError, match="live read-only"):
            client.request("POST /MemoriaalBoekingen/Create", body={})
        assert client.status()["allow_writes"] is False
        assert store.settings().allow_writes
