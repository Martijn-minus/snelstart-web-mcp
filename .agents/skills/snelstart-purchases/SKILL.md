---
name: snelstart-purchases
description: Find and review SnelStart purchases, inspect invoice documents, or submit a purchase PDF for recognition when requested.
---

# Work with purchases

- For pending recognition review, use `snelstart_purchase_review_count` for the portal-wide count and `snelstart_search_purchases` with `review_only: true` to locate marked bookings in the requested dates. Pass the booking ID to `snelstart_purchase_review_item` for the recognized fields and attachments.
- Confirm the selected administration. Use an exact `invoice_number` string and preserve leading zeroes. For supplier or text search, use `query`. Use `review_only: true` for entries flagged by SnelStart. Check the reported total and all requested pages. Narrow the date range if the tool cannot verify coverage.
- Pass the search row's `publicIdentifier` as `entry_id` and its `factuurnummeridentifier`, when available, as `purchase_invoice_id` to `snelstart_get_entry` or `snelstart_get_entries`. Confirm the supplier, invoice reference and date against the original PDF. Use `snelstart_list_attachments` and `snelstart_download_document` for the document, and `snelstart_purchase_payments` for recorded settlements.
- For a requested purchase date correction, read the existing booking and VAT lines first. SnelStart's basic purchase update can recalculate VAT and net amounts. When preserving the posting, use `POST /Purchases/UpdateInkoopboekingVolledig` with the original booking lines and explicit VAT lines. Read back the corrected date and verify amounts, VAT, payments and attachment links.
- Submit a local PDF through `snelstart_upload_purchase_pdf` only on an explicit request for that administration and file. Check for an existing record before submitting. Poll `snelstart_purchase_upload_status` with the returned instance ID. Recognition sends the document to the inbox for review. Verify the supplier, currency, amounts, VAT, ledger account and any cost centre before treating it as posted or final.
- For foreign purchases, reverse charge, cost centres or early payment discounts, use `snelstart_check_purchase_posting` to check the actual ledger function and cost-centre requirement. Supply the purchase booking and invoice identifiers from the same search row to read recorded lines. Compare the source invoice, booking lines, ledger and relevant return. The legal and period-specific treatment can require current official tax guidance. The MCP has no dedicated end-to-end correction or posting workflow for these cases. Use the Web workflow or a verified, explicitly authorized generic operation.
- The Web inbox can also receive invoices through its dedicated email address. Setting up that mailbox and converting arbitrary invoice files to UBL are separate workflows.

See [reviewing a purchase](https://kennispleinweb.snelstart.nl/nl/een-inkoopfactuur-controleren) and [submitting a document for recognition](https://kennispleinweb.snelstart.nl/nl/inkoopfacturen-of-bonnetjes-automatisch-inlezen-in-snelstart-web).
