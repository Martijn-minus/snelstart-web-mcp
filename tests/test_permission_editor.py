import curses
import sys
from uuid import UUID

import pytest

from snelstart_mcp import permission_editor
from snelstart_mcp.cli import main
from snelstart_mcp.config import SnelStartError, Store
from snelstart_mcp.models.permissions import WriteSelection
from snelstart_mcp.purchase_upload import SUBMIT_PURCHASE, UPLOAD_URL
from snelstart_mcp.write_access import grantable_operations

ADMIN = UUID("11111111-1111-4111-8111-111111111111")
OTHER = UUID("22222222-2222-4222-8222-222222222222")
JOURNAL = "POST /MemoriaalBoekingen/Create"


class Screen:
    def __init__(self, keys):
        self.keys = iter(keys)
        self.rendered = []

    def getmaxyx(self):
        return 12, 100

    def erase(self):
        pass

    def addnstr(self, y, x, value, width, style=None):
        self.rendered.append(value)

    def refresh(self):
        pass

    def getch(self):
        return next(self.keys)


def test_permission_menu_toggles_groups_details_and_global_access():
    groups = permission_editor.permission_groups({UPLOAD_URL, SUBMIT_PURCHASE})
    assert groups == {"Purchase PDF upload": {UPLOAD_URL, SUBMIT_PURCHASE}}
    screen = Screen(
        [
            9,  # All operation details
            curses.KEY_DOWN,  # The group
            ord(" "),  # Enable the whole group
            curses.KEY_DOWN,  # The first operation
            ord(" "),  # Disable one operation
            curses.KEY_UP,
            curses.KEY_UP,
            curses.KEY_UP,  # Global switch
            ord(" "),
            10,
        ]
    )
    selection = permission_editor._select(screen, ADMIN, WriteSelection(allow_writes=False), groups)
    assert selection == WriteSelection(allow_writes=True, operations={SUBMIT_PURCHASE})
    assert any("[-]" in item and "Purchase PDF upload" in item for item in screen.rendered)


def test_configure_saves_target_grants_and_keeps_other_administrations(tmp_path, monkeypatch):
    store = Store(tmp_path / "profile")
    store.write(
        "config.json",
        {
            "administration_id": str(ADMIN),
            "allow_writes": True,
            "write_permissions": {str(ADMIN): [JOURNAL], str(OTHER): [JOURNAL]},
            "custom_setting": "fixture",
        },
    )
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    def select(editor, administration, prior, groups):
        assert administration == ADMIN
        assert prior.allow_writes and prior.operations == {JOURNAL}
        return WriteSelection(allow_writes=False, operations=set(groups["Purchase PDF upload"]))

    monkeypatch.setattr(curses, "wrapper", select)
    monkeypatch.setattr(permission_editor.Confirm, "ask", lambda *args, **kwargs: True)
    permission_editor.configure_write_access(store, None)
    settings = store.settings()
    assert not settings.allow_writes
    assert settings.write_permissions == {ADMIN: {UPLOAD_URL, SUBMIT_PURCHASE}, OTHER: {JOURNAL}}
    assert store.read("config.json")["custom_setting"] == "fixture"


def test_declining_permission_changes_keeps_config_bytes(tmp_path, monkeypatch):
    store = Store(tmp_path / "profile")
    store.write("config.json", {"administration_id": str(ADMIN)})
    before = (store.directory / "config.json").read_bytes()
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(
        curses,
        "wrapper",
        lambda *args: WriteSelection(allow_writes=True, operations=grantable_operations()),
    )
    monkeypatch.setattr(permission_editor.Confirm, "ask", lambda *args, **kwargs: False)
    permission_editor.configure_write_access(store, None)
    assert (store.directory / "config.json").read_bytes() == before


def test_editor_rejects_a_concurrent_administration_switch(tmp_path, monkeypatch):
    store = Store(tmp_path / "profile")
    store.write("config.json", {"administration_id": str(ADMIN)})
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(curses, "wrapper", lambda *args: WriteSelection(allow_writes=True))

    def switch(*args, **kwargs):
        store.write("config.json", {"administration_id": str(OTHER)})
        return True

    monkeypatch.setattr(permission_editor.Confirm, "ask", switch)
    with pytest.raises(SnelStartError, match="active administration changed"):
        permission_editor.configure_write_access(store, None)
    settings = store.settings()
    assert settings.administration_id == OTHER
    assert not settings.allow_writes and not settings.write_permissions


def test_cli_permission_editor_requires_a_terminal(tmp_path, monkeypatch, capsys):
    profile = tmp_path / "profile"
    monkeypatch.setattr(
        sys, "argv", ["snelstart-mcp", "--config-dir", str(profile), "writes", "configure"]
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    assert "interactive terminal" in capsys.readouterr().err
    assert not (profile / "config.json").exists()
