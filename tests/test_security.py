import asyncio
import io
import subprocess
from uuid import UUID

import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError

from snelstart_mcp import approval, vault
from snelstart_mcp.client import Client
from snelstart_mcp.config import SnelStartError, Store
from snelstart_mcp.models.approval import WriteIntent
from snelstart_mcp.server import create_server

ADMIN = UUID("11111111-1111-4111-8111-111111111111")
CREATE = "POST /MemoriaalBoekingen/Create"


def test_approval_matches_exact_write_and_is_consumed_once(tmp_path, monkeypatch):
    store = Store(tmp_path)
    store.write("config.json", {"administration_id": str(ADMIN)})
    intent = WriteIntent(
        tool="snelstart_write", operation=CREATE, administration_id=ADMIN, details={"number": 1}
    )
    with pytest.raises(SnelStartError, match="Local confirmation required"):
        approval.require_approval(store, intent, None)
    (identifier,) = (UUID(key) for key in store.read(approval.FILE))
    with pytest.raises(SnelStartError, match="no matching"):
        approval.require_approval(store, intent, identifier)

    shown = []

    class TerminalCapture(io.StringIO):
        def close(self):
            shown.append(self.getvalue())
            super().close()

    monkeypatch.setattr(
        approval,
        "open",
        lambda path, mode="r", **kwargs: (
            io.StringIO("APPROVE\n") if mode == "r" else TerminalCapture()
        ),
        raising=False,
    )
    approval.approve_write(store, identifier)
    assert str(ADMIN) in shown[0] and '"number": 1' in shown[0]
    with pytest.raises(SnelStartError, match="no matching"):
        approval.require_approval(
            store, intent.model_copy(update={"details": {"number": 2}}), identifier
        )
    approval.require_approval(store, intent, identifier)
    with pytest.raises(SnelStartError, match="no matching"):
        approval.require_approval(store, intent, identifier)


def test_tool_checks_administration_and_sensitive_grant_before_dispatch(tmp_path):
    store = Store(tmp_path)
    store.write("config.json", {"administration_id": str(ADMIN), "allow_writes": True})
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: pytest.fail("Unexpected API request"))
    ) as http:
        server = create_server(Client(store, http))
        request = {"operation": CREATE, "payload": {}, "administration_id": str(ADMIN)}
        with pytest.raises(ToolError, match="Local confirmation required"):
            asyncio.run(server.call_tool("snelstart_write", request))
        with pytest.raises(ToolError, match="differs from the write request"):
            asyncio.run(
                server.call_tool(
                    "snelstart_write", request | {"administration_id": str(UUID(int=2))}
                )
            )
        with pytest.raises(ToolError, match="Writing is disabled"):
            asyncio.run(
                server.call_tool(
                    "snelstart_write", request | {"operation": "POST /BtwAangiftes/Send"}
                )
            )


def test_direct_write_still_requires_the_administration_and_operation_grant(tmp_path, monkeypatch):
    store = Store(tmp_path)
    store.write(
        "config.json",
        {
            "administration_id": str(ADMIN),
            "write_permissions": {str(ADMIN): [CREATE]},
            "direct_write_administrations": [str(ADMIN)],
        },
    )
    sent = []

    def request(operation, parameters, payload, **kwargs):
        sent.append((operation, parameters, payload, kwargs))
        return {"accepted": True}

    with httpx.Client(
        transport=httpx.MockTransport(lambda req: pytest.fail("Unexpected live API request"))
    ) as http:
        client = Client(store, http)
        monkeypatch.setattr(client, "request", request)
        server = create_server(client)
        request_args = {"operation": CREATE, "payload": {}, "administration_id": str(ADMIN)}
        with pytest.raises(ToolError, match="differs from the write request"):
            asyncio.run(
                server.call_tool(
                    "snelstart_write", request_args | {"administration_id": str(UUID(int=2))}
                )
            )
        with pytest.raises(ToolError, match="Writing is disabled"):
            asyncio.run(
                server.call_tool(
                    "snelstart_write", request_args | {"operation": "POST /BtwAangiftes/Send"}
                )
            )
        assert not sent
        _, result = asyncio.run(server.call_tool("snelstart_write", request_args))
        assert result["data"] == {"accepted": True}
        assert len(sent) == 1 and sent[0][0] == CREATE
        assert sent[0][3]["expected_administration"] == str(ADMIN)
        assert store.read(approval.FILE) == {}


def test_store_migrates_legacy_secrets_and_refuses_git_profiles(tmp_path, test_vault):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    with pytest.raises(SnelStartError, match="outside Git worktrees"):
        Store(repo / "profile")
    assert not (repo / "profile").exists()

    store = Store(tmp_path / "safe")
    expected = {"refresh_token": "local-test-fixture"}
    store._write_file("tokens.json", expected)
    assert store.read("tokens.json") == expected
    assert not (store.directory / "tokens.json").exists()
    assert test_vault[(vault.SERVICE, vault.account(store.directory, "tokens.json"))]
    assert Store(store.directory).read("tokens.json") == expected


def test_failed_keyring_keeps_legacy_data_and_blocks_its_use(tmp_path, monkeypatch):
    store = Store(tmp_path)
    store._write_file("tokens.json", {"refresh_token": "local-test-fixture"})

    def unavailable():
        raise RuntimeError("internal OS diagnostics")

    monkeypatch.setattr(vault, "backend", unavailable)
    with pytest.raises(SnelStartError, match="OS secret store"):
        store.read("tokens.json")
    assert (store.directory / "tokens.json").is_file()


def test_generic_attachment_read_omits_temporary_urls(tmp_path, monkeypatch):
    store = Store(tmp_path)
    store.write("config.json", {"administration_id": str(ADMIN)})
    fixture = [
        {"attachmentIdentifier": str(ADMIN), "temporaryDownloadUrl": "https://example.test/file"}
    ]
    with httpx.Client() as http:
        client = Client(store, http, read_only=True)
        monkeypatch.setattr(client, "request", lambda *_: fixture)
        server = create_server(client)
        result = asyncio.run(
            server.call_tool(
                "snelstart_read",
                {
                    "operation": "GET /Purchases/GetAttachmentsWithIdentifier",
                    "parameters": {"journaalpostIdentifier": str(ADMIN)},
                },
            )
        )
    assert result[1]["data"] == [{"attachmentIdentifier": str(ADMIN)}]
