---
name: snelstart-bank
description: Inspect SnelStart cash and bank journals, check imported date coverage, trace a bank booking, or diagnose missing bank transactions and payment links.
---

# Work with cash and bank journals

- Confirm the selected administration and resolve the bank or cash journal UUID with `snelstart_bank_journals`. Use `snelstart_export_bank_entries` for checked paging and a private file across one or more journals. Compare the date coverage and ending balance to an independent bank statement when checking for missing transactions.
- Use the row's `identifier` for a bank detail lookup. When a detail returns HTTP 500, recheck that ID. You can supply the journal UUID and local booking date as `bank_list_context`. A matching `bank_list_evidence` row supports its list fields and leaves detail coverage incomplete.
- Compare outgoing and incoming signs, split lines, recorded invoice links, markers and attachments with the statement and source documents. Use `snelstart_reconcile_bank` to find possible matches. An exact invoice reference or recorded link still needs the corresponding amount and payment evidence.
- If updating an explicitly requested booking, confirm the exact journal, booking and allocation. Read back the changed lines, payment links and any existing review marker. Use the attachment list when you need file evidence.
- On explicit request, use `snelstart_attach_bank_pdf` with the selected administration, booking UUID and local PDF. The tool verifies the link and SHA-256. If the outcome is uncertain, inspect the attachment list before retrying.
- Bank connection setup, consent renewal, historical import, a manual bank file import and payment initiation require the official interface. The MCP reads imported transactions. For a missing interval, compare the bank file with the dates already imported before using the official workflow.

See [manual statement import](https://kennispleinweb.snelstart.nl/nl/bankafschriften-handmatig-inlezen-in-snelstart-web) and [bank consent renewal](https://kennispleinweb.snelstart.nl/nl/de-toestemming-consent-verlengen).
