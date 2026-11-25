---
name: snelstart-sales
description: Review SnelStart sales invoices, customers and articles, or prepare a requested sales invoice, credit, quotation or delivery workflow.
---

# Work with sales

- Use `snelstart_sales_invoice_readiness` before preparing an invoice. If the portal rejects the current company settings, have the user complete them in SnelStart Web. The blank fields are hints and can include optional settings.
- Confirm the selected administration with `snelstart_status`. Find the customer with `snelstart_search_relations` and verify its ID. Use `snelstart_search_articles` to find the intended article and `snelstart_article_details` to check its VAT, prices and revenue settings. Use the numeric `articleId` from the search.
- For invoice lookups, read all relevant pages with `snelstart_search_sales`. Read a posted invoice with its nonzero `verkoopboekingPublicIdentifier` via `snelstart_sales_booking_details`. Use the search row for a draft. To retrieve a PDF, use the invoice-number ID with `snelstart_download_document`.
- For an invoice proposal, verify the customer, invoice date, service or delivery date, due date or terms, article, quantity, unit price, discount, currency and VAT treatment. Check for an existing invoice using its reference, customer, date and amount. Use current official guidance where tax treatment needs interpretation.
- Use `snelstart_preview_sales_document` to calculate the requested invoice or quotation with SnelStart. Present the administration, recipient, dates, lines and SnelStart's calculated VAT and totals. Use `snelstart_save_sales_document` only on an explicit request to save, with the reviewed `expected_gross`. A draft uses `draft: true`. Verify the stored record in the corresponding overview.
- Use `snelstart_email_new_sales_document` only on an explicit request to create and email a new document. Verify the exact recipient, subject, body, total and each requested attachment. For an already-saved document use the Web workflow. Use `snelstart_sales_email_template` to read default content and `snelstart_sent_email_history` to verify status. Check the existing document and mail history before retrying after a sender verification or unknown result.
- For quotation review use `snelstart_search_quotations` or `snelstart_quotation_details`. For posted sales periods, use posting evidence from the ledger alongside the invoice date from the sales list, especially around period boundaries.

See [creating and emailing an invoice](https://kennispleinweb.snelstart.nl/nl/een-factuur-maken-in-snelstart-web) for attachments and format limits, and [creating quotes](https://kennispleinweb.snelstart.nl/nl/een-offerte-maken-in-snelstart-web) for the Web workflow.
