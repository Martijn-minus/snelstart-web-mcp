# Write permissions and audit

[Back to the quick start](../README.md) · [Nederlands](writes-and-audit.nl.md)

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

A grant stays active until revoked. `writes off` disables global writing and clears all grants. Global mode covers standard operations. Filing, emailing invoices or quotations, changing sales email destinations and year-end operations require a specific grant for the administration.

**Per-write confirmation** is required by default. To send explicitly authorized writes directly, run `snelstart-mcp writes confirmations off` for the selected administration. Use `snelstart-mcp writes confirmations on` to restore per-write confirmation and `snelstart-mcp writes confirmations` to check the setting. The setting applies to the selected administration only. Global and scoped write permissions still apply.

With confirmations enabled, the first MCP call returns an approval ID. Ask your chat to group the IDs with `snelstart_open_write_review`. In the local browser window, review the administration and exact contents. Check the individual changes you want to authorize and click **Approve selected requests**. Return to your chat and say to continue. It can check the approvals with `snelstart_write_approval_status` and repeat the exact approved requests within two minutes.

The browser window stays on the computer running the MCP and shows only the requests selected for review. You can also run `snelstart-mcp writes review` locally to open the pending approvals for the selected administration. For a terminal-only session, run `snelstart-mcp writes approve APPROVAL_ID` for the same profile, review the request and type `APPROVE`.

A change to the payload or PDF checksum requires a new approval. An approval is consumed once, including when the result is uncertain. The approval protects the MCP tool boundary. Treat unrestricted shell and filesystem access under your OS account as trusted.

### Correct a purchase invoice date

`POST /Purchases/UpdateInkoopboekingBasisGegevens` can recalculate VAT and net posting amounts even when only the invoice date changes. Check `write_warning` in `snelstart_list_operations` before preparing the write. The local approval screen also shows this warning when confirmations are enabled.

When the posting must be preserved, first read the purchase details and retain the original booking and VAT lines. Prepare `POST /Purchases/UpdateInkoopboekingVolledig` with those lines and the corrected date. Read the purchase back and compare the date, net and gross amounts, VAT, settlements and attachment links with the original.

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

`snelstart_mutation_receipts` lists recent write receipts for the selected administration. The MCP stores the operation, record or processing ID when available, request and response checksums, and outcome. It records the intent before dispatch. A timeout or interrupted call remains unresolved. Use `snelstart_verify_mutation` with the `receipt_id` to perform supported read-back checks for created bank, journal and opening-balance entries, recorded deletions, and finished purchase PDF processing. The bank PDF attachment tool verifies its own receipt after checking the linked file checksum. The verification label describes exactly what the read established. Other operations require manual verification. The CLI includes receipts in `snelstart-mcp audit`. Reversal requires an explicit new write.
