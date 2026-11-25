import json
import re
import subprocess
import sys
from pathlib import Path

from snelstart_mcp.codex_hook import PLUGIN_TOOL_PREFIX

ROOT = Path(__file__).resolve().parents[1]


def test_marketplace_resolves_the_local_plugin_bundle():
    marketplace = json.loads((ROOT / ".agents/plugins/marketplace.json").read_bytes())
    (entry,) = marketplace["plugins"]
    bundle = (ROOT / entry["source"]["path"]).resolve()
    plugin = json.loads((bundle / ".codex-plugin/plugin.json").read_bytes())
    assert plugin["name"] == entry["name"]
    assert (bundle / plugin["skills"]).resolve() == ROOT / ".agents" / "skills"
    assert {path.parent.name for path in (bundle / plugin["skills"]).glob("*/SKILL.md")} == {
        "snelstart-administration",
        "snelstart-bank",
        "snelstart-purchases",
        "snelstart-setup",
        "snelstart-reconcile",
        "snelstart-sales",
        "snelstart-tax",
        "snelstart-year-end",
    }
    mcp = json.loads((bundle / plugin["mcpServers"]).read_bytes())
    (server,) = mcp["mcpServers"]
    assert f"mcp__{server}__" == PLUGIN_TOOL_PREFIX
    hooks = json.loads((bundle / plugin["hooks"]).read_bytes())["hooks"]
    (before,) = hooks["PreToolUse"]
    assert re.fullmatch(before["matcher"], PLUGIN_TOOL_PREFIX + "snelstart_write")
    assert not re.fullmatch(before["matcher"], "mcp__snelstart__snelstart_write")
    assert any(
        re.fullmatch(group["matcher"], PLUGIN_TOOL_PREFIX + "snelstart_status")
        for group in hooks["PostToolUse"]
    )


def test_plugin_hook_command_handles_the_plugin_namespace(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "snelstart_mcp.cli",
            "--config-dir",
            str(tmp_path / "unused"),
            "codex-hook",
        ],
        input=json.dumps(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": PLUGIN_TOOL_PREFIX + "snelstart_write",
                "tool_input": {},
            }
        ),
        capture_output=True,
        check=True,
        text=True,
    )
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert "selected administration" in output["additionalContext"]
    assert not (tmp_path / "unused").exists()
