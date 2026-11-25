---
name: snelstart-reconcile
description: Reconcile SnelStart purchase or sales bookings with invoices, bank statements, credits, refunds, and payment processor records. Use for suspected duplicates, open balances, unmatched payments, and missing attachments.
---

# Reconcile payments and invoices

1. Call `snelstart_status` and confirm the intended administration. Define the date range and which bank or processor accounts the check covers. Retrieve all pages for the slice under review.
2. Locate candidate purchases with `snelstart_search_purchases`, then use `snelstart_purchase_evidence` to read the booking, recorded settlements, and attachment IDs together. For posted sales, use `snelstart_search_sales` and pass a nonzero `verkoopboekingPublicIdentifier` to `snelstart_sales_booking_details`. Use the search row for a draft. Download relevant PDFs by attachment ID with `snelstart_download_document` and check that the document matches the booking and invoice number.
3. Compare those records to the bank statement and any processor settlement or remittance advice available to the user. SnelStart bank entries show what was imported. A zero open balance can result from a credit, offset, or manual settlement. A processor's paid flag can also come from a manual update. Confirm the payment date, currency, signed amount, reference, and account on independent evidence.
4. Follow refunds, credits, charges, FX conversions, and grouped payouts back to their original transactions. Track each link once. For period boundaries, record the invoice or service date and settlement date separately and check the adjacent book year if the chain crosses it.
5. Report the confirmed matches, differences, missing evidence, and uncovered periods. Link each proposed correction to the affected record and its source. Use `snelstart_find_payment_matches` for suggestions when a match is unclear.

For journal entries, verify linked files with `snelstart_list_attachments` or use `snelstart_get_entries` with `include_attachments: true`. A detail row can show `hasBijlagen: false` for a booking with a linked file. Use the download result for the actual byte count and checksum if the list shows placeholder metadata.

A review is read-only. If the user explicitly requests a specific correction, check the write grant, re-read the affected records, write once, and read the result back before reporting success. If a write times out, inspect the record and audit history before deciding whether retrying is safe.
