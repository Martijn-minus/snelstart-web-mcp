---
name: snelstart-sales
description: Review SnelStart sales invoices, customers and articles, or prepare a requested sales invoice, credit, quotation or delivery workflow.
---

# Work with sales

- Confirm the selected administration with `snelstart_status`. Find the customer with `snelstart_search_relations` and verify its ID. Use `snelstart_search_articles` to find the intended article and `snelstart_article_details` to check its VAT, prices and revenue settings. Use the numeric `articleId` from the search.
- For invoice lookups, read all relevant pages with `snelstart_search_sales`. Read a posted invoice with its nonzero `verkoopboekingPublicIdentifier` via `snelstart_sales_booking_details`. Use the search row for a draft. To retrieve a PDF, use the invoice-number ID with `snelstart_download_document`.
- For an invoice proposal, verify the customer, invoice date, service or delivery date, due date or terms, article, quantity, unit price, discount, currency and VAT treatment. Check for an existing invoice using its reference, customer, date and amount. Use current official guidance where tax treatment needs interpretation.
- Saving and sending are separate actions. `POST /Invoices/SaveOnly` is a generic write route for saving without sending. Verify the request contract first, use `snelstart_write` only on an explicit request for the named administration, and check the returned invoice in SnelStart. A draft, a saved invoice and a delivered invoice are different states. Apply the same permission and read-back checks to an explicitly requested credit, update or payment registration.
- Custom attachments in outgoing invoices, quotation creation and document templates require the SnelStart Web interface with the current MCP. For email, Peppol or reminders, confirm the intended channel and recipient before attempting a separately requested send. A catalog route alone does not verify delivery.

See [creating and emailing an invoice](https://kennispleinweb.snelstart.nl/nl/een-factuur-maken-in-snelstart-web) for attachments and format limits, and [creating quotes](https://kennispleinweb.snelstart.nl/nl/een-offerte-maken-in-snelstart-web) for the Web workflow.
