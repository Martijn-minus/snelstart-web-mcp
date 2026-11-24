"""Register the installed stdio server with local MCP clients."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import tomlkit

from .client_config import (
    read_client_config,
    read_config_bytes,
    write_client_config,
    write_config_bytes,
)
from .config import SnelStartError
from .hook_install import install_hooks
from .skill_install import SKILL_CLIENTS, install_skills

SERVER = "snelstart"
CLIENTS = (
    "codex",
    "claude-code",
    "claude-desktop",
    "antigravity",
    "cursor",
    "vscode",
    "gemini",
    "opencode",
    "windsurf",
    "zed",
)


def _run(argv: list[str]) -> str:
    if not shutil.which(argv[0]):
        raise SnelStartError(f"The {argv[0]} CLI was not found on PATH.")
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise SnelStartError(f"The {argv[0]} CLI could not finish registration.") from None
    if result.returncode:
        raise SnelStartError(
            f"The {argv[0]} CLI exited with status {result.returncode}. "
            "Check whether the server is already registered."
        )
    return result.stdout


def _merge_file(path: Path, sections: tuple[str, ...], definition: dict) -> str:
    config, original = read_client_config(path)
    servers = config
    for key in sections:
        if not isinstance(servers, dict):
            break
        servers = servers.setdefault(key, {})
    if not isinstance(servers, dict):
        raise SnelStartError("The client configuration has an unexpected structure.")
    if SERVER in servers:
        existing = servers[SERVER]
        if isinstance(existing, dict) and all(existing.get(k) == v for k, v in definition.items()):
            return "already_configured"
        raise SnelStartError("A different snelstart registration already exists.")
    servers[SERVER] = definition
    write_client_config(path, config, original)
    return "installed"


def _client_file(client: str) -> tuple[Path, tuple[str, ...]]:
    home = Path.home()
    xdg = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    macos = sys.platform == "darwin"
    if client == "claude-desktop":
        if not macos:
            raise SnelStartError("Claude Desktop registration is supported on macOS.")
        return home / "Library/Application Support/Claude/claude_desktop_config.json", (
            "mcpServers",
        )
    if client == "antigravity":
        gemini = Path(os.environ.get("GEMINI_HOME") or home / ".gemini")
        current = gemini / "config/mcp_config.json"
        legacy = gemini / "antigravity/mcp_config.json"
        return (legacy if not current.exists() and legacy.is_file() else current), ("mcpServers",)
    if client == "vscode":
        base = home / "Library/Application Support" if macos else xdg
        return base / "Code/User/mcp.json", ("servers",)
    if client == "gemini":
        return home / ".gemini/settings.json", ("mcpServers",)
    if client == "opencode":
        root = Path(os.environ.get("OPENCODE_CONFIG_DIR") or xdg / "opencode")
        override = os.environ.get("OPENCODE_CONFIG")
        jsonc = root / "opencode.jsonc"
        path = (
            Path(override).expanduser()
            if override
            else jsonc
            if jsonc.is_file()
            else root / "opencode.json"
        )
        # The current format nests server definitions. OpenCode 1.x uses the top-level MCP map.
        version = _run(["opencode", "--version"]).strip() if shutil.which("opencode") else "2"
        sections = ("mcp",) if version.startswith("1.") else ("mcp", "servers")
        return path, sections
    if client == "zed":
        return xdg / "zed/settings.json", ("context_servers",)
    if client == "cursor":
        return home / ".cursor/mcp.json", ("mcpServers",)
    return home / ".codeium/windsurf/mcp_config.json", ("mcpServers",)


def _refresh_codex(transport: dict, invocation: list[str]) -> str:
    command = transport.get("command")
    args = transport.get("args")
    if (
        transport.get("type", "stdio") != "stdio"
        or not isinstance(command, str)
        or Path(command).name != "snelstart-mcp"
        or not isinstance(args, list)
        or (
            args != ["serve"]
            and not (
                len(args) == 3
                and args[0] == "--config-dir"
                and isinstance(args[1], str)
                and bool(args[1])
                and args[2] == "serve"
            )
        )
    ):
        raise SnelStartError("A different snelstart registration already exists.")
    # Reusing install without an explicit profile keeps the existing profile.
    new_args = args if invocation[1:] == ["serve"] else invocation[1:]
    if command == invocation[0] and args == new_args:
        return "already_configured"

    root = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    path = root / "config.toml"
    original = read_config_bytes(path)
    if original is None:
        raise SnelStartError("The SnelStart registration is outside the Codex user configuration.")
    config = tomlkit.parse(original.decode("utf-8"))
    servers = config.get("mcp_servers")
    server = servers.get(SERVER) if isinstance(servers, dict) else None
    if (
        not isinstance(server, dict)
        or server.get("command") != command
        or server.get("args") != args
        or "url" in server
    ):
        raise SnelStartError(
            "The Codex user configuration differs from the active SnelStart registration."
        )
    if command != invocation[0]:
        server["command"] = invocation[0]
    if args != new_args:
        server["args"] = new_args
    write_config_bytes(path, tomlkit.dumps(config).encode("utf-8"), original)
    return "updated"


def _register(client: str, invocation: list[str], *, apply: bool, config_path: Path | None) -> dict:
    entry = {"command": invocation[0], "args": invocation[1:]}
    argv = {
        "codex": ["codex", "mcp", "add", SERVER, "--", *invocation],
        "claude-code": ["claude", "mcp", "add", "--scope", "user", SERVER, "--", *invocation],
    }.get(client)
    if argv:
        if apply:
            if client == "codex":
                servers = json.loads(_run(["codex", "mcp", "list", "--json"]))
                existing = next((server for server in servers if server["name"] == SERVER), None)
                if existing:
                    status = _refresh_codex(existing["transport"], invocation)
                    return {"client": client, "status": status}
            _run(argv)
        return {"client": client, "status": "installed" if apply else "preview", "command": argv}

    if client == "stdio":
        if config_path is None:
            if apply:
                raise SnelStartError("Provide --client-config to apply a generic registration.")
            return {
                "client": client,
                "status": "preview",
                "snippet": {"mcpServers": {SERVER: entry}},
            }
        path, sections = config_path, ("mcpServers",)
    else:
        path, sections = _client_file(client)
    if config_path is not None:
        path = config_path.expanduser().absolute()
    if client == "vscode":
        entry["type"] = "stdio"
    if client == "opencode":
        entry = {"type": "local", "command": invocation}
    snippet = {SERVER: entry}
    for key in reversed(sections):
        snippet = {key: snippet}
    return {
        "client": client,
        "status": _merge_file(path, sections, entry) if apply else "preview",
        "config": str(path),
        "snippet": snippet,
    }


def install(
    clients: list[str],
    *,
    apply: bool,
    profile: Path | None,
    config_path: Path | None,
    with_skills: bool = False,
    skills_only: bool = False,
    with_hooks: bool = False,
    hooks_only: bool = False,
) -> list[dict]:
    selected = CLIENTS if "all" in clients else list(dict.fromkeys(clients))
    include_skills = with_skills or skills_only
    include_hooks = with_hooks or hooks_only
    addons_only = skills_only or hooks_only
    if include_skills and any(client not in SKILL_CLIENTS for client in selected):
        raise SnelStartError("Choose codex or claude-code when installing bundled skills.")
    if include_hooks and selected != ["codex"]:
        raise SnelStartError("Bundled hooks are available for Codex. Choose the codex target.")
    if addons_only and config_path is not None:
        raise SnelStartError("The client config override applies to MCP registrations.")
    if config_path is not None and (len(selected) != 1 or selected[0] in {"codex", "claude-code"}):
        raise SnelStartError("The client config override requires one file-based client.")
    executable = Path(sys.executable).absolute().with_name("snelstart-mcp")
    if not addons_only and (not executable.is_file() or not os.access(executable, os.X_OK)):
        raise SnelStartError("Install the SnelStart MCP package before registering clients.")
    invocation = [str(executable)]
    if profile is not None:
        invocation.extend(["--config-dir", str(profile.expanduser().resolve())])
    invocation.append("serve")
    results = []
    for client in selected:
        try:
            skills = install_skills(client, apply=False) if include_skills else []
            hooks = install_hooks(apply=False) if include_hooks else None
            registration: dict
            if addons_only:
                registration = {"client": client, "status": "preview"}
            else:
                registration = _register(client, invocation, apply=apply, config_path=config_path)
            if include_skills:
                if apply:
                    skills = install_skills(client, apply=True)
                registration["skills"] = [item.model_dump(mode="json") for item in skills]
            if hooks is not None:
                if apply:
                    hooks = install_hooks(apply=True)
                registration["hooks"] = hooks.model_dump(mode="json")
            if addons_only and apply:
                added = any(item.status == "installed" for item in skills) or (
                    hooks is not None and hooks.status == "installed"
                )
                if hooks is not None and hooks.status == "updated":
                    registration["status"] = "updated"
                else:
                    registration["status"] = "installed" if added else "already_configured"
            results.append(registration)
        except SnelStartError as error:
            results.append({"client": client, "status": "error", "message": str(error)})
        except (OSError, ValueError, TypeError, KeyError):
            results.append(
                {
                    "client": client,
                    "status": "error",
                    "message": "Could not read or update the local client configuration or add-ons.",
                }
            )
    return results
