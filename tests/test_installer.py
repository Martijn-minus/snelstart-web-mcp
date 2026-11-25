import json
import os
import sys
import tomllib
from pathlib import Path

import pytest

from snelstart_mcp import installer
from snelstart_mcp.cli import main
from snelstart_mcp.config import SnelStartError


@pytest.fixture
def environment(tmp_path, monkeypatch):
    home = tmp_path / "test home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    for variable in (
        "CODEX_HOME",
        "XDG_CONFIG_HOME",
        "GEMINI_HOME",
        "OPENCODE_CONFIG",
        "OPENCODE_CONFIG_DIR",
    ):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(installer.shutil, "which", lambda name: None)
    monkeypatch.setattr(installer.sys, "platform", "darwin")
    return home


def test_all_targets_preview_correct_client_formats_without_writing(environment, tmp_path):
    profile = tmp_path / "separate profile"
    results = installer.install(["all"], apply=False, profile=profile, config_path=None)
    previews = {item["client"]: item for item in results}
    assert set(previews) == set(installer.CLIENTS)
    assert all(item["status"] == "preview" for item in results)
    assert list(environment.iterdir()) == []
    assert not profile.exists()
    command = previews["codex"]["command"]
    assert command[:5] == ["codex", "mcp", "add", "snelstart", "--"]
    executable = command[5]
    args = ["--config-dir", str(profile), "serve"]
    assert os.access(executable, os.X_OK) and command[6:] == args
    assert previews["claude-code"]["command"] == [
        "claude",
        "mcp",
        "add",
        "--scope",
        "user",
        "snelstart",
        "--",
        executable,
        *args,
    ]
    entry = {"command": executable, "args": args}
    for target in ("antigravity", "claude-desktop", "cursor", "gemini", "windsurf"):
        assert previews[target]["snippet"] == {"mcpServers": {"snelstart": entry}}
        assert Path(previews[target]["config"]).is_relative_to(environment)
    assert previews["vscode"]["snippet"] == {"servers": {"snelstart": {**entry, "type": "stdio"}}}
    assert previews["zed"]["snippet"] == {"context_servers": {"snelstart": entry}}
    assert previews["opencode"]["snippet"] == {
        "mcp": {"servers": {"snelstart": {"type": "local", "command": [executable, *args]}}}
    }


@pytest.mark.parametrize(("client", "root"), [("codex", ".agents"), ("claude-code", ".claude")])
def test_skills_can_be_previewed_and_installed_without_mcp_registration(environment, client, root):
    options = {"profile": None, "config_path": None, "skills_only": True}
    (preview,) = installer.install([client], apply=False, **options)
    assert preview["status"] == "preview"
    assert list(environment.iterdir()) == []
    (result,) = installer.install([client], apply=True, **options)
    assert result["status"] == "installed" and "command" not in result
    assert {skill["name"] for skill in result["skills"]} == {
        "snelstart-administration",
        "snelstart-bank",
        "snelstart-purchases",
        "snelstart-reconcile",
        "snelstart-sales",
        "snelstart-setup",
        "snelstart-tax",
        "snelstart-year-end",
    }
    for skill in result["skills"]:
        path = Path(skill["path"])
        assert path == environment / root / "skills" / skill["name"] / "SKILL.md"
        source = Path(__file__).resolve().parents[1] / ".agents" / "skills" / skill["name"]
        assert path.read_bytes() == (source / "SKILL.md").read_bytes()
    (again,) = installer.install([client], apply=True, **options)
    assert again["status"] == "already_configured"


def test_with_skills_refuses_conflict_before_registering_the_server(environment, monkeypatch):
    custom = environment / ".agents/skills/snelstart-year-end/SKILL.md"
    custom.parent.mkdir(parents=True)
    custom.write_text("Custom year-end instructions.")
    monkeypatch.setattr(installer, "_run", lambda *args: pytest.fail("Unexpected registration"))
    (result,) = installer.install(
        ["codex"], apply=True, profile=None, config_path=None, with_skills=True
    )
    assert result["status"] == "error"
    assert custom.read_text() == "Custom year-end instructions."
    assert sorted(path.name for path in custom.parent.parent.iterdir()) == ["snelstart-year-end"]


def test_cli_install_merges_preserves_settings_and_is_idempotent(
    environment, tmp_path, monkeypatch, capsys
):
    config_path = tmp_path / "alt config.json"
    other = {
        "mcpServers": {"other": {"url": "https://example.test"}},
        "unrelated": {"enabled": False},
    }
    config_path.write_text(json.dumps(other))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "snelstart-mcp",
            "install",
            "antigravity",
            "--client-config",
            str(config_path),
            "--apply",
        ],
    )
    main()
    (result,) = json.loads(capsys.readouterr().out)
    assert result["status"] == "installed"
    updated = json.loads(config_path.read_text())
    assert updated["unrelated"] == other["unrelated"]
    assert updated["mcpServers"]["other"] == other["mcpServers"]["other"]
    assert updated["mcpServers"]["snelstart"] == result["snippet"]["mcpServers"]["snelstart"]
    modified = config_path.stat().st_mtime_ns
    main()
    (again,) = json.loads(capsys.readouterr().out)
    assert again["status"] == "already_configured"
    assert config_path.stat().st_mtime_ns == modified


@pytest.mark.parametrize(
    "config",
    [
        '{"mcpServers": {"snelstart": {"command": "other"}}}',
        '{"mcpServers": []}',
        '{"mcpServers": {}, // Keep this comment\n}',
    ],
)
def test_installer_rejects_unsafe_merges_and_leaves_the_original(environment, tmp_path, config):
    config_path = tmp_path / "existing.json"
    config_path.write_text(config)
    (result,) = installer.install(["cursor"], apply=True, profile=None, config_path=config_path)
    assert result["status"] == "error"
    assert config_path.read_text() == config


def test_installer_creates_a_private_config_and_refuses_symlinks(environment, tmp_path):
    (result,) = installer.install(["cursor"], apply=True, profile=None, config_path=None)
    assert result["status"] == "installed"
    config = Path(result["config"])
    assert config.stat().st_mode & 0o777 == 0o600
    link = tmp_path / "symlink.json"
    link.symlink_to(config)
    (blocked,) = installer.install(["cursor"], apply=True, profile=None, config_path=link)
    assert blocked["status"] == "error"
    assert link.is_symlink()


@pytest.mark.parametrize("registration", ["none", "same", "different"])
def test_codex_registration_preserves_existing_settings(environment, monkeypatch, registration):
    requests = []

    def run(argv):
        requests.append(argv)
        if argv[2] == "list":
            if registration == "none":
                return "[]"
            command = Path(sys.executable).absolute().with_name("snelstart-mcp")
            if registration == "different":
                command = Path("/different")
            return json.dumps(
                [
                    {
                        "name": "snelstart",
                        "transport": {"command": str(command), "args": ["serve"]},
                    }
                ]
            )
        return ""

    monkeypatch.setattr(installer, "_run", run)
    (result,) = installer.install(["codex"], apply=True, profile=None, config_path=None)
    if registration == "none":
        assert result["status"] == "installed"
        assert requests == [["codex", "mcp", "list", "--json"], result["command"]]
    else:
        assert result["status"] == ("already_configured" if registration == "same" else "error")
        assert requests == [["codex", "mcp", "list", "--json"]]


@pytest.mark.parametrize("explicit_profile", [False, True])
def test_codex_refresh_preserves_server_settings_and_installs_addons(
    environment, monkeypatch, explicit_profile
):
    config = environment / ".codex/config.toml"
    config.parent.mkdir()
    original = """# User settings
[mcp_servers.other]
url = "https://example.test"

[mcp_servers.snelstart]
command = "/old environment/bin/snelstart-mcp" # MCP launcher
args = ["--config-dir", "/existing profile", "serve"]
enabled = false
startup_timeout_sec = 20
enabled_tools = ["snelstart_status"]

[mcp_servers.snelstart.env]
EXAMPLE = "kept"
"""
    config.write_text(original)

    def run(argv):
        assert argv == ["codex", "mcp", "list", "--json"]
        transport = tomllib.loads(config.read_text())["mcp_servers"]["snelstart"]
        return json.dumps([{"name": "snelstart", "transport": {"type": "stdio", **transport}}])

    monkeypatch.setattr(installer, "_run", run)
    profile = environment / "explicit profile" if explicit_profile else None
    options = {"profile": profile, "config_path": None, "with_skills": True, "with_hooks": True}
    (result,) = installer.install(["codex"], apply=True, **options)
    assert result["status"] == "updated"
    assert result["hooks"]["status"] == "installed"
    assert all(skill["status"] == "installed" for skill in result["skills"])
    updated = config.read_text()
    expected = original.replace(
        "/old environment/bin/snelstart-mcp",
        str(Path(sys.executable).absolute().with_name("snelstart-mcp")),
    )
    if profile is not None:
        expected = expected.replace("/existing profile", str(profile))
    assert updated == expected
    (again,) = installer.install(["codex"], apply=True, **options)
    assert again["status"] == "already_configured"
    assert config.read_text() == updated


def test_codex_refresh_leaves_mismatched_user_config_untouched(environment, monkeypatch):
    config = environment / ".codex/config.toml"
    config.parent.mkdir()
    original = '[mcp_servers.snelstart]\ncommand = "another-server"\nargs = ["serve"]\n'
    config.write_text(original)
    active = [
        {
            "name": "snelstart",
            "transport": {"type": "stdio", "command": "/old/bin/snelstart-mcp", "args": ["serve"]},
        }
    ]
    monkeypatch.setattr(installer, "_run", lambda argv: json.dumps(active))
    (result,) = installer.install(["codex"], apply=True, profile=None, config_path=None)
    assert result["status"] == "error"
    assert config.read_text() == original


def test_legacy_antigravity_and_opencode_layouts(environment, monkeypatch):
    legacy = environment / ".gemini/antigravity/mcp_config.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("{}")
    monkeypatch.setattr(installer.shutil, "which", lambda name: "opencode")
    monkeypatch.setattr(installer, "_run", lambda argv: "1.18.15\n")
    antigravity, opencode = installer.install(
        ["antigravity", "opencode"], apply=True, profile=None, config_path=None
    )
    assert antigravity["config"] == str(legacy)
    assert "snelstart" in json.loads(legacy.read_text())["mcpServers"]
    assert json.loads(Path(opencode["config"]).read_text())["mcp"]["snelstart"]["type"] == "local"


def test_missing_client_cli_does_not_block_other_registrations(environment):
    failed, succeeded = installer.install(
        ["claude-code", "cursor"], apply=True, profile=None, config_path=None
    )
    assert failed["status"] == "error" and "not found" in failed["message"]
    assert succeeded["status"] == "installed"


def test_cli_requires_a_single_file_based_target_for_a_custom_config(environment):
    with pytest.raises(SnelStartError, match="one file-based client"):
        installer.install(["all"], apply=True, profile=None, config_path=environment / "test.json")


def test_generic_stdio_can_preview_or_merge_an_explicit_config_file(environment):
    path = environment / "client.json"
    (preview,) = installer.install(["stdio"], apply=False, profile=None, config_path=None)
    (blocked,) = installer.install(["stdio"], apply=True, profile=None, config_path=None)
    assert blocked["status"] == "error"
    (merged,) = installer.install(["stdio"], apply=True, profile=None, config_path=path)
    assert merged["status"] == "installed"
    assert json.loads(path.read_text()) == preview["snippet"]
