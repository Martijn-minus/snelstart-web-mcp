# Using the SnelStart MCP

Read the [README](README.md) for setup, tool arguments and examples. Run package commands from this directory. Keep code, identifiers and tool documentation in English. Use the user's language when discussing accounting results.

## Confirm the administration

Recommend making and verifying a backup before bookkeeping work. Let the user choose live read-only access, offline access to a year archive, or live access with local write permissions. Create a backup or change access only on request. In offline mode call `snelstart_snapshot_info` first and include the archive cutoff date and coverage in the result.

1. Start with `snelstart_status` to see the selected administration and write permissions. `uv run --frozen snelstart-mcp doctor` also shows the selected name and available administrations.
2. Use `snelstart_list_administrations` when you need to identify a UUID. Confirm the intended administration before accessing records or changing the active selection.
3. Use the existing authorized sign-in. For a new profile, start browser OAuth with `uv run --frozen --extra browser snelstart-mcp login --method browser`. Use macOS Passwords or Keychain autofill on the official sign-in page when available. Keep passwords, tokens, HAR captures, downloaded documents and backup files private.

## Choose the tool for the task

| Task | Tools |
| --- | --- |
| Find and review a purchase | `snelstart_search_purchases`, then `snelstart_get_entry` with `kind: "purchase"`. Read recorded settlements with `snelstart_purchase_payments`. |
| Download the purchase PDF | Call `snelstart_list_attachments` with the purchase UUID, then `snelstart_download_document` with the PDF's attachment identifier. |
| Check bank transactions | Get journal UUIDs with `snelstart_bank_journals`, then use `snelstart_export_bank_entries` for checked coverage across journals or `snelstart_get_entries` for a mixed batch of booking details. `snelstart_reconcile_bank` provides evidence and candidates for human review. |
| Check figures or tax returns | Use `snelstart_balance_sheet`, `snelstart_financial_result`, or `snelstart_vat_returns` as appropriate. |
| Submit a new purchase PDF | On an explicit request, call `snelstart_upload_purchase_pdf` for the named administration and file. Use the returned ID with `snelstart_purchase_upload_status`. |
| Archive a year | Call `snelstart_create_year_archive`, then verify the returned archive with `snelstart_verify_archive`. Report the scope recorded in the manifest. |

Use ISO dates (`YYYY-MM-DD`). Read all relevant pages before reporting totals. Verify payment against the available bank evidence when the user asks whether an invoice was paid. When no dedicated read tool fits, use `snelstart_list_operations` to find the exact catalog operation and pass it to `snelstart_read`.

## Handle requested writes

Check the target administration, record and write permissions first. Include the target UUID in every write request. If the MCP returns an approval ID, ask the user to review it with `snelstart-mcp writes approve ID` in their own terminal. The assistant must not run the confirmation command or enter the confirmation value. After the user confirms, retry exactly the same request with the returned `approval_id`. Verify the result through a read or processing-status call. If the outcome is uncertain, check SnelStart and the local audit log before retrying.

Check `snelstart_mutation_receipts` for the outcome and use `snelstart_verify_mutation` when a supported read-back is available. Report the verification label and reconcile an unresolved receipt before asking about another write.

## Test changes

Run `uv run --frozen pytest -q tests` for the local suite and `uv run --frozen --extra browser basedpyright` for type checking. The opt-in live contract uses the isolated `mcp-test` administration and read-only bookkeeping requests.
