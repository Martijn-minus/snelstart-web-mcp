"""Register the installed stdio server with local MCP clients."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .config import SnelStartError
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
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise SnelStartError("The client configuration must be a regular file.")
    original = path.read_bytes() if path.exists() else None
    try:
        config = {} if original is None else json.loads(original)
    except (UnicodeError, ValueError):
        raise SnelStartError(
            "The client configuration is not plain JSON. Merge the preview in the client editor."
        ) from None
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
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".snelstart-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(config, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        current = path.read_bytes() if path.exists() else None
        if path.is_symlink() or current != original:
            raise SnelStartError("The client configuration changed during registration. Try again.")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
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
                    transport = existing["transport"]
                    if all(transport.get(key) == value for key, value in entry.items()):
                        return {"client": client, "status": "already_configured", "command": argv}
                    raise SnelStartError("A different snelstart registration already exists.")
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
) -> list[dict]:
    selected = CLIENTS if "all" in clients else list(dict.fromkeys(clients))
    include_skills = with_skills or skills_only
    if include_skills and any(client not in SKILL_CLIENTS for client in selected):
        raise SnelStartError("Choose codex or claude-code when installing bundled skills.")
    if skills_only and config_path is not None:
        raise SnelStartError("The client config override applies to MCP registrations.")
    if config_path is not None and (len(selected) != 1 or selected[0] in {"codex", "claude-code"}):
        raise SnelStartError("The client config override requires one file-based client.")
    executable = Path(sys.executable).absolute().with_name("snelstart-mcp")
    if not skills_only and (not executable.is_file() or not os.access(executable, os.X_OK)):
        raise SnelStartError("Install the SnelStart MCP package before registering clients.")
    invocation = [str(executable)]
    if profile is not None:
        invocation.extend(["--config-dir", str(profile.expanduser().resolve())])
    invocation.append("serve")
    results = []
    for client in selected:
        try:
            skills = install_skills(client, apply=False) if include_skills else []
            registration: dict
            if skills_only:
                registration = {"client": client, "status": "preview"}
            else:
                registration = _register(client, invocation, apply=apply, config_path=config_path)
            if include_skills:
                if apply:
                    skills = install_skills(client, apply=True)
                    if skills_only:
                        added = any(item.status == "installed" for item in skills)
                        registration["status"] = "installed" if added else "already_configured"
                registration["skills"] = [item.model_dump(mode="json") for item in skills]
            results.append(registration)
        except SnelStartError as error:
            results.append({"client": client, "status": "error", "message": str(error)})
        except (OSError, ValueError, TypeError, KeyError):
            results.append(
                {
                    "client": client,
                    "status": "error",
                    "message": "Could not read or update the local client configuration or skills.",
                }
            )
    return results
