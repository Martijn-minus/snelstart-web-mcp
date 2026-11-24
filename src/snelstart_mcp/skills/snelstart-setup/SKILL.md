---
name: snelstart-setup
description: Set up and diagnose the local SnelStart Codex plugin, Chrome sign-in, and access to the selected administration.
---

# Set up SnelStart

- Recommend creating and verifying a backup before starting bookkeeping work. Let the user choose live read-only (`serve --read-only`), a local offline archive (`serve --offline-archive FILENAME`), or live access with locally approved writes. Leave the choice and any changes to the user.

- Call `snelstart_status` to check the connection. If the local server cannot start, check for the `snelstart-mcp` command. With the user's approval, install the runtime using `uv tool install "snelstart-web-mcp[browser]"`. The project README also provides an installer for computers without uv. The plugin supplies the Codex registration.
- Run `snelstart-mcp doctor` to see the connection, Chrome readiness and local backups. If sign-in is required, have the user run `snelstart-mcp login --method browser` in their terminal and complete sign-in in Chrome.
- Ask the user to reconnect Codex if the local runtime was installed after the plugin. Verify the selected administration using `snelstart_status`. Use `snelstart_list_archives` when the user wants to see their backups.
- For optional hooks, point the user to the Codex CLI's `/hooks` review. Keep accounting changes subject to the user's explicit request and the local SnelStart profile's write settings.
