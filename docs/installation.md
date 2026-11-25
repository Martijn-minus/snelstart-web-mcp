# Installation and configuration

[Back to the quick start](../README.md) · [Nederlands](installation.nl.md)

**This unofficial MCP connects to SnelStart Web (`web.snelstart.nl`).** It signs in with a SnelStart Web account and calls the web app’s backend at `webapi.snelstart.nl`. SnelStart provides a separate B2B API for partner integrations. SnelStart also lists Polaris as a separate application. [SnelStart applications](https://kennisplein.snelstart.nl/snelstartpolaris/de-verschillende-applicaties-van-snelstart) · [SnelStart B2B API](https://www.snelstart.nl/api)

## Install the Codex plugin

With the [Codex CLI](https://learn.chatgpt.com/docs/cli) on your PATH, paste this into Terminal on macOS or Linux.

```sh
curl -fsSLo install-snelstart-mcp.sh https://raw.githubusercontent.com/Martijn-minus/snelstart-web-mcp/main/install.sh && bash install-snelstart-mcp.sh --codex-plugin
```

This installs the local MCP runtime and the **SnelStart** plugin from this repository's marketplace. The plugin bundles MCP tools, setup and bookkeeping skills, and hooks. Start a new Codex chat after installation. Run `snelstart-mcp login --method browser` if the selected local profile still needs sign-in. Review and trust any hooks you want from `/hooks` in the Codex CLI.

After Codex knows the **SnelStart MCP** marketplace, [open the plugin install flow in Codex](codex://plugins/install/snelstart?marketplace=snelstart-mcp), or choose **SnelStart** in that marketplace in the Plugins directory. The repo marketplace distributes a local plugin. [Codex plugin packaging](https://developers.openai.com/plugins/build/plugins) · [Codex install links](https://learn.chatgpt.com/docs/app/commands#plugin-install)

If you already registered SnelStart manually, Codex can show two MCP connections. To use just the plugin, set `enabled = false` under `[mcp_servers.snelstart]` in your Codex config. Both installations use the same default local SnelStart profile. A custom profile can be supplied with `SNELSTART_CONFIG_DIR` in the local execution environment.

## Install with a coding assistant

Copy this prompt into Codex, Claude Code, or another assistant that can run local shell commands.

```text
Install the SnelStart Web MCP on this machine from https://github.com/Martijn-minus/snelstart-web-mcp.
On macOS or Linux, download and run the install.sh script from the repository root.
If this client is Codex and I want the plugin, pass --codex-plugin and skip manual registration.
Check that Google Chrome is available for browser sign-in.
Find the installed snelstart-mcp executable with uv tool dir --bin if it is outside PATH.
Run snelstart-mcp login --method browser and let me complete sign-in in Chrome.
Register the MCP with this client using snelstart-mcp install <client> --apply. Ask me
which client to use if you cannot identify it. If I requested the bundled skills,
add --with-skills for Codex or Claude Code. If I requested hooks for Codex, add
--with-hooks. Then run snelstart-mcp doctor and tell
me which administration is selected, what write access it has, and whether an
update is available. Keep credentials private and leave write permissions and
accounting records untouched. Tell me if the MCP client needs to reconnect.
```

## Install on macOS or Linux

Paste this into Terminal. You can also download [install.sh](../install.sh) and run `bash install.sh`.

```sh
curl -fsSLo install-snelstart-mcp.sh https://raw.githubusercontent.com/Martijn-minus/snelstart-web-mcp/main/install.sh && bash install-snelstart-mcp.sh
```

The script checks for Python 3.11 or newer, including Homebrew and the Python supplied by macOS developer tools. It installs `uv` if needed and uses a user-local Python 3.13 if it can't find a compatible interpreter. It installs everything in your user account. Open a new terminal if the script updates your `PATH`. If you already have `uv`, you can install directly with `uv tool install 'snelstart-web-mcp[browser]'`.

Run `snelstart-mcp login --method browser`, then `snelstart-mcp doctor` to check access. Use `snelstart-mcp install codex --apply` to register with Codex, or see [client registration](#client-registration) for other clients. Run `uv tool update-shell` if the executable directory is missing from `PATH`.

`snelstart-mcp doctor` checks the browser extra and detects Chrome. Run `snelstart-mcp doctor --check-browser` to briefly open and close a blank Chrome window with the same settings as browser sign-in. The Chrome check and local backup overview also appear if the SnelStart connection fails.

For GitHub main builds, use `uv tool install 'snelstart-web-mcp[browser] @ git+https://github.com/Martijn-minus/snelstart-web-mcp.git'`.

## Windows

The server uses Unix file locking, so native Windows and Git Bash are unsupported. On Windows, run the Linux installer and MCP server inside WSL. Browser OAuth needs Google Chrome running inside WSL. If that isn't available, use the [token-only HAR import](#token-only-har-recovery). [Microsoft WSL setup](https://learn.microsoft.com/en-us/windows/wsl/install)

## Client registration

Preview or apply a registration from the same directory.

```sh
uv run --frozen snelstart-mcp install all
uv run --frozen snelstart-mcp install codex claude-code antigravity --apply
```

| Target | Registration |
| --- | --- |
| `codex` | User registration via the `codex` CLI |
| `claude-code` | User registration via the `claude` CLI |
| `claude-desktop` | Claude Desktop user configuration on macOS |
| `antigravity` | Antigravity App, IDE and CLI user configuration |
| `cursor` | Cursor global MCP configuration |
| `vscode` | VS Code user MCP configuration for the default profile |
| `gemini` | Gemini CLI user settings |
| `opencode` | Global OpenCode settings, with a schema selected from the installed CLI version |
| `windsurf` | Windsurf Cascade global MCP configuration |
| `zed` | Zed user settings |
| `stdio` | Generic `mcpServers` registration, including the MCP settings files used by Cline and Roo Code |

The installer uses the absolute path of the installed executable. Run `snelstart-mcp install codex --apply --with-skills --with-hooks` again after moving from a source checkout to a global installation. The installer updates a recognized user-level Codex registration and any bundled hook commands that point to the old executable. It keeps the configured accounting profile and other Codex settings. Use `--config-dir PATH` **before** `install` to explicitly choose an accounting profile.

Preview writes no client settings. With `--apply`, file-based registrations merge into plain JSON and preserve existing settings and servers. If an existing file uses JSON with comments, merge the preview snippet in the client's config editor. Use `--client-config PATH` for a different file location or editor profile.

For other clients, `install stdio` prints a reusable snippet. Add `--client-config PATH --apply` to merge it into a local file that uses an `mcpServers` map.

Client configuration holds the executable and arguments. Sign-in remains in the SnelStart profile. Restart or reload the MCP connection in the client after registration. The local server supports macOS and Linux.

## Sign in

The MCP stores local settings under `~/.config/snelstart-mcp` and keeps the credentials and OAuth tokens in macOS Keychain or Linux Secret Service. On first access, the MCP migrates legacy JSON secrets and removes each old file after secure storage succeeds. Unlock the system keyring before signing in. Linux and WSL require a working Secret Service. A valid profile refreshes access tokens automatically. Use `SNELSTART_CONFIG_DIR` or `--config-dir PATH` before the subcommand to select a profile outside Git worktrees.

### Browser OAuth

With Google Chrome installed, run the following command from the MCP directory.

```sh
uv run --frozen --extra browser snelstart-mcp login --method browser
```

Complete sign-in in the separate Chrome window that opens. The MCP validates the OAuth state and exchanges the authorization code using PKCE. It stores the resulting tokens in the selected local profile. Run `uv run --frozen snelstart-mcp doctor` to verify access. Existing credential profiles can use `uv run --frozen snelstart-mcp login --method credentials`.

### Token-only HAR recovery

Follow these steps if the interactive OAuth window is unavailable.

1. Sign in to the official SnelStart Web page in Chrome with network recording off. Complete any interactive sign-in prompts there.
2. Open **DevTools → Network** after sign-in, clear the log and enable **Preserve log**. Open the intended administration and look for a successful `/oauth/token` refresh response. Export the capture outside Git once the refresh is visible.
3. Import the HAR without `--save-password` and verify the profile. HAR response bodies can contain tokens even when the export is sanitized. Keep the file private and remove it when you are done.

   ```sh
   uv run --frozen snelstart-mcp import-har /path/to/capture.har
   uv run --frozen snelstart-mcp doctor
   ```

The legacy `setup` and `import-har --save-password` commands save passwords in the system keyring. Prefer browser OAuth or token-only import for new profiles.

## Optional bookkeeping skills

The repository's [`.agents/skills`](../.agents/skills/) contains the source skills for Codex, the Codex plugin, and the package installer.

| Skill | Use |
| --- | --- |
| `snelstart-setup` | Client registration, browser sign-in and connection problems. |
| `snelstart-administration` | Administration access, archive coverage and native recovery. |
| `snelstart-sales` | Sales invoices, customer and article lookup, credits and outbound workflows. |
| `snelstart-purchases` | Purchase search, invoice evidence and PDF recognition. |
| `snelstart-bank` | Cash and bank journals, imported coverage and booking details. |
| `snelstart-reconcile` | Compare invoices and settlements with bank and payment-provider evidence. |
| `snelstart-tax` | VAT and ICP records, tax monitor inputs and filing boundaries. |
| `snelstart-year-end` | Ledger exports, opening and closing balances and year-end evidence. |

The [coverage matrix](knowledge-base-coverage.md) maps relevant SnelStart Web bookkeeping workflows to MCP capabilities and skills.

To install the package and skills together, pass `--with-skills codex` or `--with-skills claude-code` to the downloaded Bash installer. To register the MCP and install the skills in one command, use the CLI.

```sh
snelstart-mcp install codex --with-skills --apply
```

If the server is already registered, use `snelstart-mcp install codex --skills-only --apply`. Leave off `--apply` to preview the files. The installer preserves existing skills when their contents differ. Begin a fresh client session to load the new skills. [Codex skill locations](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills) · [Claude Code skills](https://code.claude.com/docs/en/skills)

## Optional Codex hooks

The hooks add a reminder to verify the administration and the requested change before a bookkeeping write, followed by a read-back reminder. They also surface an available package update after `snelstart_status` or `snelstart_check_update` reports one. The MCP profile's write permissions govern bookkeeping access.

```sh
snelstart-mcp install codex --hooks-only
snelstart-mcp install codex --hooks-only --apply
```

Use `--with-hooks` when registering the server. The Bash installer also accepts `--with-hooks`, with or without `--with-skills codex`. The installer merges the definitions into `$CODEX_HOME/hooks.json` (default `~/.codex/hooks.json`). Open `/hooks` in the Codex CLI to review and trust the definitions. You can also disable them there. [Codex hook documentation](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks)

## Check for updates

Releases use `YYYY.M.D.N`, where `N` starts at `1` each day and increases with each release. `snelstart-mcp --version` also shows the date in full.

```sh
snelstart-mcp update --check
snelstart-mcp update
```

If you installed a version before the updater existed, run `uv tool upgrade snelstart-web-mcp` once. `snelstart-mcp update` uses the active `uv tool` installation and keeps its source and extras. Reconnect the MCP client after an upgrade. From a source checkout, update the checkout and run `uv sync --locked`.

`doctor` and `snelstart_status` show the SnelStart MCP version and update availability. MCP clients also receive the running package version in `serverInfo.version` when they connect. If the running and installed versions differ, the MCP reports `reconnect_required` with both versions. Reconnect the client to load the installed tools. For PyPI installs, the update check compares package versions. For GitHub installs tracking `main`, it compares the installed public commit with the current branch. The MCP caches successful public checks for one hour. Call `snelstart_check_update` to check immediately. Checks use public package metadata and send no SnelStart account data.

## Quick start from a source checkout

1. With `uv` installed on macOS or Linux, open the repository root and install the locked dependencies.

   ```sh
   uv sync --frozen --extra browser
   uv run --frozen snelstart-mcp status
   ```

2. Follow [Sign in](#sign-in) if `status` says sign-in is required. Run `doctor` to verify access and see the selected administration, write access, token expiry, and available administration UUIDs.

   ```sh
   uv run --frozen snelstart-mcp doctor
   ```

3. Register the server in Codex and start a fresh Codex session. For another client, use its [installer target](#client-registration).

   ```sh
   uv run --frozen snelstart-mcp install codex --apply
   ```

4. In your MCP client, call `snelstart_status` and check the selected administration. If necessary, find the intended UUID with `snelstart_list_administrations` and select it with `snelstart_select_administration`.

5. Try a read with the prompt “Show the balance sheet and profit and loss through 2025-12-31 for the selected SnelStart administration.” This uses `snelstart_balance_sheet`. See the [tool reference](tools.md) for other workflows and [AGENTS.md](../AGENTS.md) for instructions aimed at coding agents.

Commands such as `doctor`, `status`, `login`, `writes` and `install` show a readable summary in an interactive terminal. Piped or redirected output defaults to JSON. Use `doctor --json` for explicit JSON or `doctor --text` to keep the summary when redirecting it to a file. The same flags apply to the other commands that return results.
