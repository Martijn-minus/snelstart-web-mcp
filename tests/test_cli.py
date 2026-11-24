import json
import sys
from uuid import UUID

import httpx
import pytest

from snelstart_mcp.audit import AuditLog
from snelstart_mcp.cli import main
from snelstart_mcp.client import Client
from snelstart_mcp.config import Store
from snelstart_mcp.enums import AuditOutcome, LoginMethod

ADMIN = "11111111-1111-4111-8111-111111111111"
OPERATION = "POST /MemoriaalBoekingen/Create"
OTHER = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def command(tmp_path, monkeypatch, capsys):
    profile = tmp_path / "profile"

    def run(*args):
        monkeypatch.setattr(sys, "argv", ["snelstart-mcp", "--config-dir", str(profile), *args])
        main()
        return json.loads(capsys.readouterr().out)

    return profile, run


def test_cli_browser_login_uses_the_browser_method(command, monkeypatch):
    _, run = command
    methods = []
    monkeypatch.setattr(
        "snelstart_mcp.auth.Auth.login", lambda self, method: methods.append(method)
    )
    assert run("login", "--method", "browser")["automatic_login"] is False
    assert methods == [LoginMethod.BROWSER]


def test_cli_status_and_write_setting(command):
    _, run = command
    assert run("status")["allow_writes"] is False
    assert run("writes", "on") == {"allow_writes": True}
    assert run("status")["allow_writes"] is True
    assert run("writes", "off") == {"allow_writes": False}


def test_cli_grants_and_revokes_an_exact_operation(command):
    profile, run = command
    Store(profile).write("config.json", {"administration_id": ADMIN, "existing_key": True})
    assert run("writes", "grant", ADMIN, OPERATION) == {
        "administration_id": ADMIN,
        "approved_write_operations": [OPERATION],
    }
    assert run("status")["allow_writes"] is False
    assert run("status")["approved_write_operations"] == [OPERATION]
    assert run("writes", "revoke", ADMIN, OPERATION)["approved_write_operations"] == []
    assert run("writes", "revoke", ADMIN, OPERATION)["approved_write_operations"] == []
    run("writes", "grant", ADMIN, OPERATION)
    run("writes", "off")
    assert run("status")["approved_write_operations"] == []
    assert Store(profile).read("config.json")["existing_key"] is True


def test_cli_lists_grants_for_every_administration_and_separates_available_operations(command):
    _, run = command
    other_operation = "POST /MemoriaalBoekingen/Update"
    assert run("writes", "list") == {"allow_writes": False, "write_permissions": {}}
    run("writes", "grant", ADMIN, OPERATION)
    run("writes", "grant", OTHER, other_operation)
    assert run("writes", "list") == {
        "allow_writes": False,
        "write_permissions": {ADMIN: [OPERATION], OTHER: [other_operation]},
    }
    available = run("writes", "list", "--available")["operations"]
    assert {OPERATION, other_operation} <= set(available)
    assert "GET /Purchases/Get" not in available
    assert "POST /Administrations/Open" not in available
    run("writes", "on")
    assert run("writes", "list")["allow_writes"] is True


@pytest.mark.parametrize(
    "operation",
    ["GET /Purchases/Get", "POST /Administrations/Open", "POST /Unknown"],
)
def test_cli_rejects_ineligible_permissions(command, capsys, operation):
    _, run = command
    with pytest.raises(SystemExit) as error:
        run("writes", "grant", ADMIN, operation)
    assert error.value.code == 1
    assert "allowlisted bookkeeping write operation" in capsys.readouterr().err
    assert run("status")["approved_write_operations"] == []


def test_cli_requires_disabling_global_writes_before_granting_scope(command, capsys):
    _, run = command
    run("writes", "on")
    with pytest.raises(SystemExit) as error:
        run("writes", "grant", ADMIN, OPERATION)
    assert error.value.code == 1
    assert "Turn off global writing" in capsys.readouterr().err
    assert run("status")["approved_write_operations"] == []


def test_cli_doctor_hides_transport_error_details(command, monkeypatch, capsys):
    _, run = command

    def unavailable(self):
        raise httpx.ConnectError("private token")

    monkeypatch.setattr(Client, "administrations", unavailable)
    with pytest.raises(SystemExit) as error:
        run("doctor")
    assert error.value.code == 1
    assert capsys.readouterr().err == "SnelStart is unavailable. Try again later.\n"


def test_cli_serve_starts_the_stdio_transport(command, monkeypatch):
    profile, _ = command
    launches = []

    class Server:
        def run(self, *, transport):
            launches.append(transport)

    monkeypatch.setattr("snelstart_mcp.server.create_server", lambda client: Server())
    monkeypatch.setattr(sys, "argv", ["snelstart-mcp", "--config-dir", str(profile), "serve"])
    main()
    assert launches == ["stdio"]


@pytest.mark.parametrize(
    ("selected", "expected_name"),
    [(ADMIN, "Selected fixture"), (OTHER, "Other fixture"), (None, None)],
)
def test_cli_doctor_lists_available_administrations(command, monkeypatch, selected, expected_name):
    profile, run = command
    Store(profile).write("config.json", {"administration_id": selected})
    monkeypatch.setattr(
        Client,
        "administrations",
        lambda self: [
            {"identifier": ADMIN, "administrationName": "Selected fixture", "id": 1},
            {"identifier": OTHER, "administrationName": "Other fixture", "id": 2},
        ],
    )
    output = run("doctor")
    assert output["connected"] and output["administration_count"] == 2
    assert output["administration_id"] == selected
    assert output["administration_name"] == expected_name
    assert output["audit"]["total_calls"] == 0
    assert not output["audit"]["exists"]
    assert output["administrations"] == [
        {"identifier": ADMIN, "name": "Selected fixture"},
        {"identifier": OTHER, "name": "Other fixture"},
    ]


def test_cli_doctor_prefers_text_in_the_terminal_and_accepts_json_override(
    command, monkeypatch, capsys
):
    profile, run = command
    Store(profile).write("config.json", {"administration_id": ADMIN, "allow_writes": True})
    Store(profile).write(
        "tokens.json", {"refresh_token": "fixture-token", "expires_at": 1770000000}
    )
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.setattr(
        Client,
        "administrations",
        lambda self: [
            {"identifier": ADMIN, "administrationName": "Selected [bold] fixture"},
            {"identifier": OTHER, "administrationName": "Test fixture"},
        ],
    )
    monkeypatch.setattr(sys, "argv", ["snelstart-mcp", "--config-dir", str(profile), "doctor"])
    main()
    output = capsys.readouterr().out
    assert "Connected to SnelStart" in output
    assert "Audit log" in output
    assert "Global · all eligible operations" in output
    assert "Selected [bold] fixture  · Selected" in output
    assert OTHER in output and "Administrations (2)" in output
    assert "2026" in output and "1770000000" not in output
    assert "fixture-token" not in output
    assert run("doctor", "--json")["administrations"][0]["identifier"] == ADMIN


def test_cli_text_override_works_after_a_write_subcommand(command, monkeypatch, capsys):
    profile, _ = command
    monkeypatch.setattr(
        sys, "argv", ["snelstart-mcp", "--config-dir", str(profile), "writes", "list", "--text"]
    )
    main()
    assert "Read-only" in capsys.readouterr().out


def test_cli_audit_can_inspect_another_administration_offline(command, monkeypatch):
    profile, run = command
    store = Store(profile)
    log = AuditLog(store)
    store.write("config.json", {"administration_id": OTHER})
    call = log.start("snelstart_status")
    log.finish(call, "snelstart_status", AuditOutcome.OK, 8)
    store.write("config.json", {"administration_id": ADMIN})
    monkeypatch.setattr(Client, "__init__", lambda *a: pytest.fail("Audit must stay offline"))

    selected = run("audit")
    assert selected["administration_id"] == ADMIN and selected["calls"] == []
    older = run("audit", "--administration", OTHER, "--limit", "1")
    assert older["summary"]["succeeded"] == 1
    assert older["calls"][0]["call_id"] == call.call_id
    assert store.settings().administration_id == UUID(ADMIN)


def test_cli_setup_does_not_print_credential(command, monkeypatch):
    profile, run = command
    monkeypatch.setattr("builtins.input", lambda prompt: "fixture@example.test")
    monkeypatch.setattr("getpass.getpass", lambda prompt: "test-private")
    monkeypatch.setattr("snelstart_mcp.auth.Auth.login", lambda self: {})
    output = run("setup")
    assert output["automatic_login"]
    assert "test-private" not in json.dumps(output)
    assert (profile / "credentials.json").stat().st_mode & 0o777 == 0o600
