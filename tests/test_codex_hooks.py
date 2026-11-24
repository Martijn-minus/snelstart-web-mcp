import json
import shlex
import subprocess
from pathlib import Path

import pytest

from snelstart_mcp import installer


@pytest.fixture
def hooks_file(tmp_path, monkeypatch):
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "user with spaces")
    return Path.home() / ".codex" / "hooks.json"


def test_hooks_merge_preserves_existing_rules_and_is_idempotent(hooks_file):
    original = {
        "description": "Custom hooks",
        "hooks": {
            "PostToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "custom-check"}]}
            ],
            "SessionStart": [{"hooks": [{"type": "command", "command": "custom-startup"}]}],
        },
    }
    hooks_file.parent.mkdir(parents=True)
    hooks_file.write_text(json.dumps(original))
    before = hooks_file.read_bytes()
    options = {"profile": None, "config_path": None, "hooks_only": True}
    (preview,) = installer.install(["codex"], apply=False, **options)
    assert preview["hooks"]["status"] == "preview"
    assert hooks_file.read_bytes() == before
    (installed,) = installer.install(["codex"], apply=True, **options)
    assert installed["status"] == installed["hooks"]["status"] == "installed"
    assert "command" not in installed
    saved = json.loads(hooks_file.read_bytes())
    assert saved["description"] == original["description"]
    assert saved["hooks"]["PostToolUse"][0] == original["hooks"]["PostToolUse"][0]
    assert saved["hooks"]["SessionStart"] == original["hooks"]["SessionStart"]
    (again,) = installer.install(["codex"], apply=True, **options)
    assert again["status"] == "already_configured"
    assert json.loads(hooks_file.read_bytes()) == saved


def test_bundled_hooks_follow_the_installer_environment(hooks_file, monkeypatch):
    options = {"profile": None, "config_path": None, "hooks_only": True}
    installer.install(["codex"], apply=True, **options)
    before = hooks_file.read_bytes()
    executable = "/new environment/bin/python"
    monkeypatch.setattr(installer.sys, "executable", executable)
    (preview,) = installer.install(["codex"], apply=False, **options)
    assert preview["hooks"]["status"] == "preview"
    assert hooks_file.read_bytes() == before
    (updated,) = installer.install(["codex"], apply=True, **options)
    assert updated["status"] == updated["hooks"]["status"] == "updated"
    expected = json.loads(before)
    for groups in expected["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                hook["command"] = shlex.join([executable, *shlex.split(hook["command"])[1:]])
    assert json.loads(hooks_file.read_bytes()) == expected
    (again,) = installer.install(["codex"], apply=True, **options)
    assert again["status"] == "already_configured"


def test_installed_hook_command_limits_scope_and_does_not_echo_tool_data(hooks_file):
    (installed,) = installer.install(
        ["codex"], apply=True, profile=None, config_path=None, hooks_only=True
    )
    command = shlex.split(installed["hooks"]["entries"]["PreToolUse"][0]["hooks"][0]["command"])

    def send(event, tool, result=None):
        payload = {
            "hook_event_name": event,
            "tool_name": tool,
            "tool_input": {"payload": "private fixture"},
            "tool_response": result,
        }
        return subprocess.run(
            command, input=json.dumps(payload), check=True, capture_output=True, text=True
        ).stdout

    write_tool = "mcp__snelstart__snelstart_write"
    pre = json.loads(send("PreToolUse", write_tool))
    assert "administration" in pre["hookSpecificOutput"]["additionalContext"]
    assert "permissionDecision" not in pre["hookSpecificOutput"]
    post = json.loads(send("PostToolUse", write_tool, {"isError": True}))
    assert "audit log" in post["hookSpecificOutput"]["additionalContext"]
    assert "private fixture" not in json.dumps(post)
    assert send("PreToolUse", "mcp__other__snelstart_write") == ""
    assert send("PostToolUse", "mcp__snelstart__snelstart_bank_entries") == ""
    status = "mcp__snelstart__snelstart_status"
    assert (
        send("PostToolUse", status, {"structuredContent": {"update": {"status": "current"}}}) == ""
    )
    notice = json.loads(
        send(
            "PostToolUse",
            status,
            {
                "structuredContent": {
                    "update": {"status": "available", "message": "private fixture"}
                }
            },
        )
    )
    assert "snelstart-mcp update" in notice["systemMessage"]
    assert "private fixture" not in json.dumps(notice)
