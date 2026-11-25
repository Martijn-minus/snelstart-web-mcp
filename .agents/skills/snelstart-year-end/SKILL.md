---
name: snelstart-year-end
description: Review a SnelStart book year, reconcile balances and results to ledger evidence, compare opening balances across years, or prepare a supported VAT comparison.
---

# Review a book year

- Confirm the selected administration with `snelstart_status` and agree the period. Use `snelstart_balance_sheet` at the closing date and `snelstart_financial_result` for the period. Find account numbers in `snelstart_chart_of_accounts` and use `snelstart_ledger_account_details` to retrieve the public UUID, VAT and cost-centre settings when needed.
- Export ledgers with `snelstart_export_ledger_entries` when you need complete pages for several accounts. Use batches of up to 20 accounts. The returned JSONL has one object per row with a ledger ID and original entry. Use the per-account exported counts and date range to track coverage. If exporting fails or a reported balance does not reconcile, identify the missing or changing source before closing the check.
- For opening balance differences, compare the previous close and current opening and trace the intervening journal and settlement entries. Keep prior-year corrections, current-year activity, and later corrections distinct.
- List recorded VAT returns with `snelstart_vat_returns`. Retrieve the relevant return UUIDs with `snelstart_vat_return_details` and compare their detail to the ledger. Keep figures recorded in SnelStart, independently confirmed filings, working calculations, assessments, and actual payments distinct. Check the official filing confirmation or copy where available. Use current official guidance if you need to determine a tax treatment.
- Record the date cutoff, accounts and documents covered, reconciled differences, and gaps. For a requested backup, create and verify the archive and report the scope in its manifest. Report recovery as verified only after an actual restore has been tested.

Read and report by default. Post corrections only when the user explicitly requests the specific change. Verify the relevant records before and after writing.
