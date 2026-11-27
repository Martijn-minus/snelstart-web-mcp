# SnelStart Web MCP

<!-- mcp-name: io.github.martijn-minus/snelstart-web-mcp -->

**English** · [Nederlands](https://github.com/Martijn-minus/snelstart-web-mcp/blob/main/README.nl.md)

This unofficial MCP connects to SnelStart Web through `webapi.snelstart.nl`. SnelStart's official B2B API and Polaris are separate products.

## Install with an AI assistant

Paste this into Codex, Claude Code, or another assistant with local terminal access.

```text
Install SnelStart Web MCP from https://github.com/Martijn-minus/snelstart-web-mcp.
Follow the README for this client. Let me enter my credentials in my own terminal.
Run snelstart-mcp doctor, tell me which administration is selected,
and keep my bookkeeping and write permissions intact.
```

## Install from a terminal

**Codex plugin** (macOS or Linux, with the Codex CLI installed)

```sh
curl -fsSLo install-snelstart-mcp.sh https://raw.githubusercontent.com/Martijn-minus/snelstart-web-mcp/main/install.sh && bash install-snelstart-mcp.sh --codex-plugin
```

**Other MCP clients** (macOS, Linux, or Windows with WSL)

```sh
curl -fsSLo install-snelstart-mcp.sh https://raw.githubusercontent.com/Martijn-minus/snelstart-web-mcp/main/install.sh && bash install-snelstart-mcp.sh
snelstart-mcp install claude-code --apply
```

Replace `claude-code` with your [client's installer target](https://github.com/Martijn-minus/snelstart-web-mcp/blob/main/docs/installation.md#client-registration).

## Sign in and start

1. **Preferred.** Run `snelstart-mcp setup` in your own terminal and enter your SnelStart email and password. The MCP stores them in macOS Keychain or Linux Secret Service.
2. For an existing password profile, run `snelstart-mcp login --method credentials`. For interactive sign-in or MFA, run `snelstart-mcp login --method browser`.
3. Run `snelstart-mcp doctor` and check the selected administration.
4. Start a new chat and ask, “Which SnelStart administration is connected?”
5. Before bookkeeping, [create and verify a backup](https://github.com/Martijn-minus/snelstart-web-mcp/blob/main/docs/backups.md#year-archives). You can also use live read-only access or open a saved year offline.

## Documentation

- [Installation, sign-in, supported clients, skills, hooks, and updates](https://github.com/Martijn-minus/snelstart-web-mcp/blob/main/docs/installation.md)
- [MCP tools and examples](https://github.com/Martijn-minus/snelstart-web-mcp/blob/main/docs/tools.md)
- [Backups, read-only access, and offline snapshots](https://github.com/Martijn-minus/snelstart-web-mcp/blob/main/docs/backups.md)
- [Write permissions, approvals, and audit logs](https://github.com/Martijn-minus/snelstart-web-mcp/blob/main/docs/writes-and-audit.md)
- [SnelStart Web feature coverage](https://github.com/Martijn-minus/snelstart-web-mcp/blob/main/docs/knowledge-base-coverage.md)
- [Development and releases](https://github.com/Martijn-minus/snelstart-web-mcp/blob/main/docs/development.md) · [Usage and liability](https://github.com/Martijn-minus/snelstart-web-mcp/blob/main/NOTICE.md) · [Latest release](https://github.com/Martijn-minus/snelstart-web-mcp/releases/latest)
