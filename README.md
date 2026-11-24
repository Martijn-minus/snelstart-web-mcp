# SnelStart Web MCP

**English** · [Nederlands](https://github.com/Martijn-minus/snelstart-web-mcp/blob/main/README.nl.md)

**This unofficial MCP connects to SnelStart Web (`web.snelstart.nl`).** It signs in with a SnelStart Web account and calls the web app’s backend at `webapi.snelstart.nl`. SnelStart provides a separate B2B API for partner integrations. SnelStart also lists Polaris as a separate application. [SnelStart applications](https://kennisplein.snelstart.nl/snelstartpolaris/de-verschillende-applicaties-van-snelstart) · [SnelStart B2B API](https://www.snelstart.nl/api)

Before starting bookkeeping work, make and verify a backup. Choose [live read-only access, a local offline snapshot, or live access with write permissions](#choose-how-to-access-the-data). Read the [usage and liability notice](NOTICE.md).

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

Paste this into Terminal. You can also download [install.sh](install.sh) and run `bash install.sh`.

```sh
curl -fsSLo install-snelstart-mcp.sh https://raw.githubusercontent.com/Martijn-minus/snelstart-web-mcp/main/install.sh && bash install-snelstart-mcp.sh
```

The script checks for Python 3.11 or newer, including Homebrew and the Python supplied by macOS developer tools. It installs `uv` if needed and uses a user-local Python 3.13 if it can't find a compatible interpreter. It installs everything in your user account. Open a new terminal if the script updates your `PATH`. If you already have `uv`, you can install directly with `uv tool install 'snelstart-web-mcp[browser]'`.

Run `snelstart-mcp login --method browser`, then `snelstart-mcp doctor` to check access. Use `snelstart-mcp install codex --apply` to register with Codex, or see [client registration](#client-registration) for other clients. Run `uv tool update-shell` if the executable directory is missing from `PATH`.

`snelstart-mcp doctor` checks the browser extra and detects Chrome. Run `snelstart-mcp doctor --check-browser` to briefly open and close a blank Chrome window with the same settings as browser sign-in. The Chrome check and local backup overview also appear if the SnelStart connection fails.

For GitHub main builds, use `uv tool install 'snelstart-web-mcp[browser] @ git+https://github.com/Martijn-minus/snelstart-web-mcp.git'`.

## Optional bookkeeping skills

- `snelstart-reconcile` guides invoice, attachment, and payment checks against bank and processor evidence.
- `snelstart-year-end` guides ledger exports, opening and closing balance checks, and VAT comparisons.

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

## Windows

The server uses Unix file locking, so native Windows and Git Bash are unsupported. On Windows, run the Linux installer and MCP server inside WSL. Browser OAuth needs Google Chrome running inside WSL. If that isn't available, use the [token-only HAR import](#token-only-har-recovery). [Microsoft WSL setup](https://learn.microsoft.com/en-us/windows/wsl/install)

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
   uv sync --frozen
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

5. Try a read with the prompt “Show the balance sheet and profit and loss through 2025-12-31 for the selected SnelStart administration.” This uses `snelstart_balance_sheet`. See the [tool reference](#tools) for other workflows and [AGENTS.md](AGENTS.md) for instructions aimed at coding agents.

Commands such as `doctor`, `status`, `login`, `writes` and `install` show a readable summary in an interactive terminal. Piped or redirected output defaults to JSON. Use `doctor --json` for explicit JSON or `doctor --text` to keep the summary when redirecting it to a file. The same flags apply to the other commands that return results.

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

## Language and input

The MCP interface uses English tool names, argument names, option values, help and errors. It works the same way in a Dutch or English conversation. Set dates in ISO `YYYY-MM-DD` format. The API routes and raw data fields owned by SnelStart retain their original spelling. The user's language does not change a request or translate accounting data.

## Tools

### Administration and access

| Tool | What it does |
| --- | --- |
| `snelstart_status` | Shows the running MCP version, selected administration, sign-in and refresh status, effective write settings, and update availability. |
| `snelstart_check_update` | Checks whether the MCP client needs to reconnect or the installed package has a public update. |
| `snelstart_list_administrations` | Lists the administrations accessible to the signed-in account. |
| `snelstart_select_administration` | Opens an administration by UUID and saves that selection locally. |
| `snelstart_list_operations` | Searches the API catalog and returns exact operation names and parameters. Set `read_only: false` to include write operations. |
| `snelstart_read` | Runs an allowlisted read. Pass query values as `parameters` and search-body fields as `filters`. |
| `snelstart_write` | Sends a permitted catalog mutation for the required `administration_id`, with `operation`, `payload`, optional `parameters` and a one-use `approval_id`. |
| `snelstart_audit_log` | Lists recent calls for the selected administration with their outcome and elapsed time. |

The catalog records known Web API operations. Availability depends on the administration, the account's permissions and the SnelStart package.

### Purchases, sales and payments

| Tool | What it does |
| --- | --- |
| `snelstart_search_purchases` | Lists purchases for an inclusive date range. Set `review_only: true` to find entries SnelStart has flagged for review. |
| `snelstart_get_entry` | Reads details for a purchase, general journal entry, opening balance entry or bank entry by UUID. |
| `snelstart_purchase_payments` | Reads payments and settlements recorded against a purchase. |
| `snelstart_purchase_evidence` | Reads purchase records, recorded settlements, and optional attachment metadata for up to 20 purchase UUIDs. |
| `snelstart_list_attachments` | Lists files linked to a purchase, bank entry or journal entry and returns their download identifiers. |
| `snelstart_download_document` | Downloads an attachment by UUID or a sales invoice PDF by invoice-number ID. Returns a private local path and checksum. |
| `snelstart_upload_purchase_pdf` | Submits a local PDF as a new purchase for SnelStart's recognition and review workflow. Returns a processing ID. |
| `snelstart_purchase_upload_status` | Reads the processing status for that ID. |
| `snelstart_search_sales` | Searches sales invoices by customer, invoice number or status. |
| `snelstart_sales_booking_details` | Reads sales booking details for up to 20 booking UUIDs. |
| `snelstart_search_relations` | Searches customers or suppliers by name or number. |
| `snelstart_bank_journals` | Lists bank and cash journals, including their ledger UUIDs. |
| `snelstart_bank_entries` | Lists a journal's entries in an inclusive date range. Accepts a search term and a marked-only filter. |
| `snelstart_find_payment_matches` | Searches for candidate invoices for an incoming or outgoing payment. |

For an invoice review, search the period, open each purchase using `kind: "purchase"`, and read its attached invoice and recorded settlements. Compare the booking to the document and check the corresponding bank entry if payment evidence is needed. For lists with `skip` and `take`, advance through all pages before reporting a period total.

Example purchase filter for entries flagged during November 2026.

```json
{"start_date":"2026-11-01","through_date":"2026-11-30","review_only":true,"take":50}
```

#### Download a purchase PDF

1. Find the invoice with `snelstart_search_purchases` using a date range and, if available, the invoice number as `query`.
2. Pass the purchase entry UUID as `entry_id` to `snelstart_list_attachments` with `kind: "purchase"`.
3. Pass the PDF's `attachmentIdentifier` as `attachment_id` to `snelstart_download_document`. The tool returns the path to the private local file.

#### Submit a new purchase PDF

1. Check that the selected administration is the one intended for the upload. For scoped write access, grant both upload operations listed below.
2. Call `snelstart_upload_purchase_pdf` with the selected administration UUID as `administration_id` and an absolute local PDF path as `file_path`. Review the path and file checksum with the local approval command, then retry with its `approval_id`. The tool accepts one PDF of up to 25 MiB and returns an `instance_id`.
3. Call `snelstart_purchase_upload_status` with that ID and the same administration UUID. Once processing completes, review the recognized invoice under **Inkopen → Te controleren**. [SnelStart purchase recognition](https://kennispleinweb.snelstart.nl/nl/inkoopfacturen-of-bonnetjes-automatisch-inlezen-in-snelstart-web)

With scoped permissions, grant both operations for the same administration.

```sh
uv run snelstart-mcp writes grant ADMINISTRATION_UUID 'GET /Attachments/GetAttachmentUploadUriNew'
uv run snelstart-mcp writes grant ADMINISTRATION_UUID 'POST /Purchases/CreateInkoopVoorBijlage'
```

The profile keeps a local receipt keyed by administration and PDF checksum. Repeating a confirmed submission returns its existing processing ID. After an unconfirmed submission, check the purchase overview before attempting to send the document again.

### Financial reports and tax

| Tool | What it does |
| --- | --- |
| `snelstart_chart_of_accounts` | Lists ledger accounts and their identifiers. |
| `snelstart_balance_sheet` | Reads the balance sheet, profit and loss, and reporting categories for a `through_date`. |
| `snelstart_financial_result` | Reads the financial result for `start_date` through `through_date` using the report called by the Tax Monitor. |
| `snelstart_ledger_entries` | Reads one page of postings for an account through a given date. |
| `snelstart_export_ledger_entries` | Reads and checks all pages for up to 20 account UUIDs, then exports the requested date range to a private JSONL file. Returns a path, SHA-256, and per-account counts. |
| `snelstart_vat_returns` | Lists existing VAT returns in their recorded states. |
| `snelstart_vat_return_details` | Reads the details of up to 20 VAT returns by public UUID. |
| `snelstart_supplemental_vat_years` | Lists years eligible for a supplemental VAT return. |
| `snelstart_year_end_review` | Reads open entries, open purchases, open sales or year-end bookings for a year, when available. |

For 2025 and November 2026 balances, call `snelstart_balance_sheet` separately with `2025-12-31` and `2026-11-30`. For detailed VAT returns, start with `snelstart_vat_returns` and pass the public identifiers as `return_ids` to `snelstart_vat_return_details`.

For a multi-account review, pass `ledger_ids`, `start_date`, and `through_date` to `snelstart_export_ledger_entries`. Each line contains `ledger_id` and the original `entry`. For a range of multiple days, the tool checks the administration's fiscal-year dates and fetches the part of each fiscal year in the range separately. If the final date is beyond the closing list, the tool verifies the active fiscal year against the administration settings. It rejects ranges with unverified fiscal-year coverage. `fetched_rows` counts the rows fetched across all parts. `exported_rows` counts the rows in the requested range. A pagination or connection failure discards the incomplete export. Treat the file as private accounting data.

```json
{"operation":"GET /BtwAangiftes/Get","parameters":{"id":123}}
```

ICP returns are available through `snelstart_read` with `GET /IcpAangiftes/GetIcpAangiftes` and numeric `skip` and `top` query parameters. The Tax Monitor's final reservation for income or corporate tax remains in SnelStart Web. Its financial-result input is available in the MCP. [SnelStart Tax Monitor documentation](https://kennisplein.snelstart.nl/migration/nl/snelstartweb/wat-is-de-belastingmonitor-in-snelstart)

### Archives

| Tool | What it does |
| --- | --- |
| `snelstart_create_year_archive` | Creates a local, checksummed archive of a year's supported data and any supplied official files. |
| `snelstart_list_archives` | Lists local year archives with their creation date, through date and whether a native BACPAC is included. |
| `snelstart_verify_archive` | Validates the manifest, allowed archive members, sizes and SHA-256 checksums. |
| `snelstart_extract_archive` | Verifies and extracts an archive into a new private local folder. |

## Write permissions

Bookkeeping writes are disabled by default. Open the permission editor in a terminal.

```sh
snelstart-mcp writes configure
```

The editor opens on the selected administration. Pass `--administration UUID` to edit another one. Move with the arrow keys and press Space to select or clear a group, an individual operation, or all standard operations for that administration. Use Tab to expand a group and choose sensitive operations individually. `[-]` marks a partial selection. Use the **Purchase PDF upload** group to select the two operations for that workflow together.

The global switch affects all administrations. The editor preserves scoped grants for other administrations. Press Enter to review the proposed changes and confirm saving, or Esc to cancel.

The command-line alternatives work without an interactive terminal.

```sh
uv run snelstart-mcp writes list
uv run snelstart-mcp writes list --available
```

- **Current permissions** are shown by `writes list`. It shows whether write access is global, scoped, or read-only, and lists scoped grants by administration UUID. `writes list --json` exposes the global switch `allow_writes` and the `write_permissions` map. In the MCP, `snelstart_status` shows the global switch and the grants for the selected administration only.
- **Available operations** are shown by `writes list --available`. Use the exact entry, including its HTTP method, when making a grant. Catalog entries describe eligible operations. SnelStart still enforces the account's own permissions.
- **Storage** is `~/.config/snelstart-mcp/config.json` by default. The same fields live in `config.json` under the directory selected with `SNELSTART_CONFIG_DIR` or `--config-dir`. Use the CLI to change the permissions for the same profile that your MCP client launches.

`snelstart_list_administrations` returns the administration UUID in the `identifier` field. The following commands grant and revoke one operation for that UUID and turn off all writes.

```sh
uv run snelstart-mcp writes grant ADMINISTRATION_UUID 'POST /MemoriaalBoekingen/Create'
uv run snelstart-mcp writes revoke ADMINISTRATION_UUID 'POST /MemoriaalBoekingen/Create'
uv run snelstart-mcp writes off
```

A grant stays active until revoked. `writes off` disables global writing and clears all grants. Global mode covers standard operations. Filing, emailing invoices, changing invoice destinations and year-end operations require a specific grant for the administration.

For each write, the first MCP call returns an approval ID. In your own terminal, run `snelstart-mcp writes approve APPROVAL_ID` for the same profile, review the operation, administration and exact content, then type `APPROVE`. The MCP client can retry the same request with `approval_id` within two minutes. A change to the payload or PDF checksum requires a new approval. An approval is consumed once, including when the result is uncertain. The approval protects the MCP tool boundary. Treat unrestricted shell and filesystem access under your OS account as trusted.

## Evidence and reconciliation

| Tool | Use |
| --- | --- |
| `snelstart_get_entries` | Read up to 20 mixed purchase, bank, journal and opening-balance bookings. Pass `entries` as objects with `kind` and `entry_id`. Each result keeps its ID and reports whether it was found, missing, failed or too large for the batch. |
| `snelstart_export_bank_entries` | Pass `journal_ids`, `start_date` and `through_date`. All checked pages are exported to a private JSONL file. The result includes the administration, row counts per journal and SHA-256. The file preserves journal metadata and original bank rows, including markings and invoice links when present. A failed page discards the export. |
| `snelstart_reconcile_bank` | Review recorded links and suggested matches for the same journal and date inputs. Use `invoice_start_date` to adjust the default 90-day invoice lookback and `skip` and `take` to page the report. |
| `snelstart_compare_archives` | Pass `before`, `after` and one of `purchases`, `sales`, `bank_entries` or `journal_and_opening_entries`. The tool compares checksummed dataset files locally. Both archives must identify the same administration, year and cutoff. Journal datasets must cover the same journals. Read an individual archived balance and profit-and-loss report with `snelstart_snapshot_read` in an offline session. |

Reconciliation reports recorded SnelStart links separately from suggestions. Suggestions use the bank entry’s signed amount, an invoice date on or before the payment date, and reference or counterparty evidence. Competing and amount-only matches remain ambiguous. Duplicate flags and missing-document indicators are review signals. Document indicators come from SnelStart’s attachment flags. Suggested matches require human review before making any bookkeeping changes.

Archive comparisons report additions, removals, and changed field names between the selected snapshots. These describe differences in the saved datasets.

## Year archives

The MCP mentions local backups when you ask about backups or year-end work and can create and verify them on request. `snelstart-mcp doctor` lists the local backups for the current profile, with their creation time, through date, ZIP size and whether a native BACPAC is included. Use `doctor --json` or `snelstart_list_archives` for filenames, paths and exact sizes in bytes. To check that the ZIP contains the expected files and that their contents still match the original checksums, ask Codex to verify a backup. This uses the MCP tool `snelstart_verify_archive`.

Call `snelstart_create_year_archive` with `year` and `through_date`. Supply `official_zip_path` to include the original audit file and attachments downloaded from SnelStart Web. Separate source files can be supplied as `auditfile_path`, `attachments_zip_path` and `bacpac_path`. Set `live_export: false` to package files without reading the administration.

The MCP export records available balance, ledger, purchase, sales, bank, general journal and VAT datasets. It checks pagination and invoice date ranges, and the archive manifest records the scope and SHA-256 of each member. A local export is a point-in-time view assembled from multiple calls. The official XAF remains the source for the journal export.

Use the returned `archive` filename with `snelstart_verify_archive` or `snelstart_extract_archive`. Archives are stored under `~/.config/snelstart-mcp/backups`. The reader also supports earlier archive files. Local extraction does not change SnelStart. A native `.bacpac` backup is needed to restore an administration in SnelStart 12. See [official Web exports](https://kennispleinweb.snelstart.nl/nl/bestanden-en-bijlagen-downloaden-in-snelstart-web) and [native backup and recovery](https://kennisplein.snelstart.nl/klanten/s/article/back-ups-maken-of-terugzetten).

## Choose how to access the data

| Mode | When to use it |
| --- | --- |
| Live read-only | Read current SnelStart data with `serve --read-only`. This process blocks bookkeeping writes, including PDF uploads, even if the profile has grants. It can still open a SnelStart session and produce an archive on request. |
| Offline snapshot | Read a saved year with `serve --offline-archive FILENAME`. The process starts two local-only tools and makes no network requests. |
| Live with local permissions | Use the normal server and choose the required operations with `snelstart-mcp writes configure`. The default profile starts with bookkeeping writes disabled. |

To work offline, first use `snelstart_create_year_archive` in a live read-only session with `live_export: true`, and verify the result with `snelstart_verify_archive`. Choose the returned ZIP filename. Archives with saved MCP datasets can be read, including the supported earlier archive format. In Codex, you can register the offline connection like this.

```sh
codex mcp add snelstart-readonly -- "$(command -v snelstart-mcp)" serve --read-only
codex mcp add snelstart-offline -- "$(command -v snelstart-mcp)" serve --offline-archive 'ARCHIVE_FILENAME.zip'
```

For a separate profile, place `--config-dir PATH` before `serve`. To use only offline SnelStart access in Codex, disable the live connection or SnelStart plugin and start a fresh session. The offline server reports the archive date and dataset coverage through `snelstart_snapshot_info`. Use `snelstart_snapshot_read` to page saved data. For bank and journal records, first list the groups, then select one with `group_index`.

The snapshot contains the exported datasets as of the archive's cutoff date. Use a fresh export for newer data and native SnelStart backups for restoration. The MCP process makes no network requests in offline mode. Data you ask a connected AI client to analyze may still be processed by that client or its provider.

## Audit log and rollback design

The server records MCP call timestamps, tool names, outcomes and durations in `audit/<administration-uuid>.sqlite3` inside the active profile. Calls made before choosing an administration go to `audit/profile.sqlite3`. A call stays in the database for the administration selected at its start, including its outcome if the selection changes. Each database uses file permissions `0600`. Inputs, response bodies, credentials and tokens are omitted. A call without a recorded result appears as pending.

When opening a scope, the MCP copies matching events from an older shared `audit.sqlite3`, including outcomes written after a switch. The original file stays in place and later reads can pick up events still written there by an older process.

`doctor` shows the selected scope's database path, outcome counts and latest call. Use `audit` to inspect local history offline.

```sh
snelstart-mcp audit --limit 10
snelstart-mcp audit --administration ADMINISTRATION_UUID --json
snelstart-mcp audit --profile
```

The log covers MCP calls made through this profile. Verify accounting changes against the affected records in SnelStart.

`snelstart_mutation_receipts` lists recent write receipts for the selected administration. The MCP stores the operation, record or processing ID when available, request and response checksums, and outcome. It records the intent before dispatch. A timeout or interrupted call remains unresolved. Use `snelstart_verify_mutation` with the `receipt_id` to perform supported read-back checks for created bank, journal and opening-balance entries, recorded deletions, and finished purchase PDF processing. The verification label describes exactly what the read established. Other operations require manual verification. The CLI includes receipts in `snelstart-mcp audit`. Reversal requires an explicit new write.

## Code and tests

The server registers separate groups for connection, bookkeeping and archive tools. The client owns administration context and API requests. Pydantic contracts live in `src/snelstart_mcp/models/` and fixed string enums in `src/snelstart_mcp/enums/`. The MCP advertises flat tool arguments for client compatibility. Year collection and archive storage are separate modules.

```sh
uv run ruff check src tests
uv run ruff format --check src tests
uv run --frozen --extra browser basedpyright
uv run pytest --cov=snelstart_mcp --cov-branch --cov-report=term-missing tests
SNELSTART_RUN_LIVE=1 uv run pytest -q tests/test_live.py
```

The live test requires exactly one administration named `mcp-test`. It signs in using a separate temporary profile, stores test tokens only in that profile and opens only the test administration. It uses read routes and verifies that bookkeeping writes are blocked.

### Pre-commit and distribution builds

From the repository root, install or run the hooks.

```sh
uv run --frozen --extra browser pre-commit install
uv run --frozen --extra browser pre-commit run --all-files
```

The hooks run BasedPyright on the package and Ruff linting and formatting on the package and tests. They also check JSON, YAML and TOML, trailing whitespace, final newlines, merge markers, large files and private keys.

The SnelStart MCP GitHub Actions workflow runs the hooks and offline tests on Python 3.11 and 3.13. It builds a wheel and source distribution, validates the metadata with Twine, and saves both files in the run's `snelstart-mcp-distributions` artifact. From the repository root, run `uv build --no-sources` to build the same formats locally. [PyPI publishing documentation](https://docs.pypi.org/publishing/publishing-to-pypi/)

### Publishing a calendar release

Set the version in `pyproject.toml` to `YYYY.M.D.N` and update `uv.lock` with `uv lock`. Use the release date and count releases from `1` each day. For example, `2026.11.24.1` is followed by `2026.11.24.2` on the same day. The first release on the next day starts at `2026.11.25.1`. Write month, day, and release number without leading zeroes. Tag the reviewed commit as `v<VERSION>`. The PyPI workflow validates the version and tag, builds the package, and publishes via the repository's `pypi` environment.

```sh
gh workflow run workflow.yml --ref "v$(uv run --frozen python -c 'from importlib.metadata import version; print(version("snelstart-web-mcp"))')"
```

The PyPI Trusted Publisher must match this repository and `workflow.yml`. [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
