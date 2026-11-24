# SnelStart Web MCP

A local stdio MCP server for SnelStart Web. It uses the Web API, refreshes its sign-in and opens the selected administration before requesting accounting data. This is an unofficial integration. SnelStart documents its partner API separately. [SnelStart API integration](https://www.snelstart.nl/api)

## One-line install

With `uv` installed, run this from any directory. The browser extra enables sign-in with an installed copy of Google Chrome.

```sh
uv tool install 'snelstart-web-mcp[browser] @ git+https://github.com/Martijn-minus/snelstart-web-mcp.git'
```

Run `snelstart-mcp login --method browser`, then `snelstart-mcp doctor` to check access. Use `snelstart-mcp install codex --apply` to register with Codex, or see [client registration](#client-registration) for other clients. Run `uv tool update-shell` if the executable directory is missing from `PATH`.

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

The installer uses the absolute path of the installed executable. Keep the virtual environment at that path or update the registration if you move the repository. Preview writes no client settings. With `--apply`, file-based registrations merge into plain JSON and preserve existing settings and servers. If an existing file uses JSON with comments, merge the preview snippet in the client's config editor. Use `--client-config PATH` for a different file location or editor profile. Use `--config-dir PATH` **before** `install` to start the MCP with a separate accounting profile.

For other clients, `install stdio` prints a reusable snippet. Add `--client-config PATH --apply` to merge it into a local file that uses an `mcpServers` map.

Client configuration holds the executable and arguments. Sign-in remains in the SnelStart profile. Restart or reload the MCP connection in the client after registration. The local server supports macOS and Linux.

## Sign in

The MCP stores its local configuration and tokens under `~/.config/snelstart-mcp`. Its directory is private (`0700`) and profile files are restricted to the current user (`0600`). A valid profile refreshes access tokens automatically. Set `SNELSTART_CONFIG_DIR` or pass `--config-dir PATH` before the subcommand to use another profile.

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

The legacy `setup` and `import-har --save-password` commands store a plaintext password in the profile. Use browser OAuth or the token-only workflow for new profiles in this repository.

## Language and input

The MCP interface uses English tool names, argument names, option values, help and errors. It works the same way in a Dutch or English conversation. Set dates in ISO `YYYY-MM-DD` format. The API routes and raw data fields owned by SnelStart retain their original spelling. The user's language does not change a request or translate accounting data.

## Tools

### Administration and access

| Tool | What it does |
| --- | --- |
| `snelstart_status` | Shows the selected administration, sign-in and refresh status, and effective write settings. |
| `snelstart_list_administrations` | Lists the administrations accessible to the signed-in account. |
| `snelstart_select_administration` | Opens an administration by UUID and saves that selection locally. |
| `snelstart_list_operations` | Searches the API catalog and returns exact operation names and parameters. Set `read_only: false` to include write operations. |
| `snelstart_read` | Runs an allowlisted read. Pass query values as `parameters` and search-body fields as `filters`. |
| `snelstart_write` | Sends a permitted catalog mutation using `operation`, `payload` and optional query `parameters`. |
| `snelstart_audit_log` | Lists recent calls with the administration, outcome and elapsed time. |

The catalog records known Web API operations. Availability depends on the administration, the account's permissions and the SnelStart package.

### Purchases, sales and payments

| Tool | What it does |
| --- | --- |
| `snelstart_search_purchases` | Lists purchases for an inclusive date range. Set `review_only: true` to find entries SnelStart has flagged for review. |
| `snelstart_get_entry` | Reads details for a purchase, general journal entry, opening balance entry or bank entry by UUID. |
| `snelstart_purchase_payments` | Reads payments and settlements recorded against a purchase. |
| `snelstart_list_attachments` | Lists files linked to a purchase, bank entry or journal entry and returns their download identifiers. |
| `snelstart_download_document` | Downloads an attachment by UUID or a sales invoice PDF by invoice-number ID. Returns a private local path and checksum. |
| `snelstart_upload_purchase_pdf` | Submits a local PDF as a new purchase for SnelStart's recognition and review workflow. Returns a processing ID. |
| `snelstart_purchase_upload_status` | Reads the processing status for that ID. |
| `snelstart_search_sales` | Searches sales invoices by customer, invoice number or status. |
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
2. Call `snelstart_upload_purchase_pdf` with the selected administration UUID as `administration_id` and an absolute local PDF path as `file_path`. The tool accepts one PDF of up to 25 MiB and returns an `instance_id`.
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
| `snelstart_vat_returns` | Lists existing VAT returns in their recorded states. |
| `snelstart_supplemental_vat_years` | Lists years eligible for a supplemental VAT return. |
| `snelstart_year_end_review` | Reads open entries, open purchases, open sales or year-end bookings for a year, when available. |

For 2025 and November 2026 balances, call `snelstart_balance_sheet` separately with `2025-12-31` and `2026-11-30`. For a specific VAT return, start with `snelstart_vat_returns`. Use the numeric return ID with `snelstart_read` and `GET /BtwAangiftes/Get`.

```json
{"operation":"GET /BtwAangiftes/Get","parameters":{"id":123}}
```

ICP returns are available through `snelstart_read` with `GET /IcpAangiftes/GetIcpAangiftes` and numeric `skip` and `top` query parameters. The Tax Monitor's final reservation for income or corporate tax remains in SnelStart Web. Its financial-result input is available in the MCP. [SnelStart Tax Monitor documentation](https://kennisplein.snelstart.nl/migration/nl/snelstartweb/wat-is-de-belastingmonitor-in-snelstart)

### Archives

| Tool | What it does |
| --- | --- |
| `snelstart_create_year_archive` | Creates a local, checksummed archive of a year's supported data and any supplied official files. |
| `snelstart_list_archives` | Lists local archive names and paths. |
| `snelstart_verify_archive` | Validates the manifest, allowed archive members, sizes and SHA-256 checksums. |
| `snelstart_extract_archive` | Verifies and extracts an archive into a new private local folder. |

## Write permissions

Bookkeeping writes are disabled by default. Run these commands from the MCP directory.

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

A grant stays active until revoked. It applies to every record covered by the operation in that administration, across MCP clients sharing the profile. `writes off` disables global writing and clears all grants. The legacy `writes on` switch enables all eligible operations across the profile, subject to the SnelStart account's permissions. The server sends a failed write only once. Client-side confirmations are managed separately.

## Year archives

Call `snelstart_create_year_archive` with `year` and `through_date`. Supply `official_zip_path` to include the original audit file and attachments downloaded from SnelStart Web. Separate source files can be supplied as `auditfile_path`, `attachments_zip_path` and `bacpac_path`. Set `live_export: false` to package files without reading the administration.

The MCP export records available balance, ledger, purchase, sales, bank, general journal and VAT datasets. It checks pagination and invoice date ranges, and the archive manifest records the scope and SHA-256 of each member. A local export is a point-in-time view assembled from multiple calls. The official XAF remains the source for the journal export.

Use the returned `archive` filename with `snelstart_verify_archive` or `snelstart_extract_archive`. Archives are stored under `~/.config/snelstart-mcp/backups`. The reader also supports earlier archive files. Local extraction does not change SnelStart. A native `.bacpac` backup is needed to restore an administration in SnelStart 12. See [official Web exports](https://kennispleinweb.snelstart.nl/nl/bestanden-en-bijlagen-downloaden-in-snelstart-web) and [native backup and recovery](https://kennisplein.snelstart.nl/klanten/s/article/back-ups-maken-of-terugzetten).

## Audit log and rollback design

The server records each tool call and its outcome in the local `audit.sqlite3` database. It records the time, tool, selected administration and duration. It omits inputs, response bodies, credentials and tokens. A call without a recorded result appears as pending. A successful call does not prove a booking was changed. Actions outside the MCP are outside this log.

A verified mutation log would add an entry-specific before state, an expected change, a durable intent, and a read-after-write check. A timeout after sending a write would remain unresolved until the record can be read back. A rollback would be a new, explicit operation with a check that the record has not changed in the meantime. This is a proposed design. Automatic rollback and financial mutations are not exercised by the tests.

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
