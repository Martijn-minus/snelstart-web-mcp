"""Merge the optional SnelStart hooks into Codex's user settings."""

import os
import shlex
import sys
from pathlib import Path

from .client_config import read_client_config, write_client_config
from .codex_hook import TOOL_PREFIX, UPDATE_TOOLS, WRITE_TOOLS
from .config import SnelStartError
from .enums import CodexHookEvent
from .models.hooks import CodexHookCommand, CodexHookGroup, CodexHooksInstallResponse

MODULE = "snelstart_mcp.codex_hook"


def _group(tools: tuple[str, ...], message: str) -> CodexHookGroup:
    matcher = "^" + TOOL_PREFIX + "(" + "|".join(tools) + ")$"
    command = shlex.join([str(Path(sys.executable).absolute()), "-I", "-m", MODULE])
    return CodexHookGroup(
        matcher=matcher,
        hooks=[CodexHookCommand(command=command, statusMessage=message)],
    )


def install_hooks(*, apply: bool) -> CodexHooksInstallResponse:
    root = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    path = root / "hooks.json"
    entries = {
        CodexHookEvent.PRE_TOOL_USE: [_group(WRITE_TOOLS, "Checking SnelStart write context")],
        CodexHookEvent.POST_TOOL_USE: [
            _group(WRITE_TOOLS, "Checking SnelStart write follow-up"),
            _group(UPDATE_TOOLS, "Checking SnelStart update status"),
        ],
    }
    config, original = read_client_config(path)
    events = config.setdefault("hooks", {})
    if not isinstance(events, dict):
        raise SnelStartError("The Codex hooks configuration has an unexpected structure.")

    changed = False
    for event, additions in entries.items():
        groups = events.setdefault(event.value, [])
        if not isinstance(groups, list) or any(not isinstance(group, dict) for group in groups):
            raise SnelStartError("The Codex hook groups have an unexpected structure.")
        for addition in additions:
            entry = addition.model_dump(mode="json")
            if entry in groups:
                continue
            for group in groups:
                if group.get("matcher") != addition.matcher:
                    continue
                handlers = group.get("hooks")
                if isinstance(handlers, list) and any(
                    isinstance(handler, dict)
                    and isinstance(handler.get("command"), str)
                    and handler["command"].endswith(" -m " + MODULE)
                    for handler in handlers
                ):
                    raise SnelStartError(
                        "A different bundled SnelStart hook is already configured."
                    )
            groups.append(entry)
            changed = True

    status = "already_configured"
    if changed:
        status = "preview"
        if apply:
            write_client_config(path, config, original)
            status = "installed"
    return CodexHooksInstallResponse(path=path, entries=entries, status=status)
