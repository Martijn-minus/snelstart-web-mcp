# MCP tool reference

[Back to the quick start](../README.md) · [Nederlands](tools.nl.md)

See [year archives and offline access](backups.md) for archive and snapshot tools.

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
| `snelstart_open_write_review` | Opens pending `approval_ids` together in a private local browser window for the user to review and select. |
| `snelstart_write_approval_status` | Returns the local status and expiry per supplied approval ID. |
| `snelstart_audit_log` | Lists recent calls for the selected administration with their outcome and elapsed time. |

The catalog records known Web API operations. Availability depends on the administration, the account's permissions and the SnelStart package.

### Purchases, sales and payments

| Tool | What it does |
| --- | --- |
| `snelstart_search_purchases` | Lists purchases for an inclusive date range. Use `query` for supplier or text search, or `invoice_number` for an exact reference. Set `review_only: true` to restrict either search to entries flagged for review. |
| `snelstart_get_entry` | Reads details for a purchase, general journal entry, opening balance entry or bank entry by UUID. |
| `snelstart_purchase_review_count` | Reads the portal's administration-wide number of marked purchases and question items. |
| `snelstart_purchase_review_item` | Reads recognized fields and optional attachments for an exact purchase booking awaiting review. |
| `snelstart_purchase_payments` | Reads payments and settlements recorded against a purchase. |
| `snelstart_purchase_evidence` | Reads purchase records, recorded settlements, and optional attachment metadata for up to 20 purchase UUIDs. |
| `snelstart_list_attachments` | Lists files linked to a purchase, bank entry or journal entry and returns their download identifiers. |
| `snelstart_attach_bank_pdf` | Attaches a local PDF to an existing cash or bank booking, then checks the booking link and file checksum. |
| `snelstart_download_document` | Downloads an attachment by UUID or a sales invoice PDF by invoice-number ID. Returns a private local path, the actual byte count, and SHA-256. |
| `snelstart_upload_purchase_pdf` | Submits a local PDF as a new purchase for SnelStart's recognition and review workflow. Returns a processing ID. |
| `snelstart_purchase_upload_status` | Reads the processing status for that ID. |
| `snelstart_search_sales` | Searches sales invoices by customer, invoice number or status. Treat `invoiceDate` and `date` as list dates. Use posted sales details and ledger evidence for booking dates. |
| `snelstart_sales_invoice_readiness` | Checks whether SnelStart accepts the selected administration's company settings for invoicing. Reports blank field names. |
| `snelstart_sales_booking_details` | Reads up to 20 posted sales using each row’s nonzero `verkoopboekingPublicIdentifier`. For drafts, use the rows from `snelstart_search_sales`. |
| `snelstart_search_relations` | Searches customers or suppliers by name or number. |
| `snelstart_search_articles` | Searches sales articles by code or name. Page with `skip` and `take`. |
| `snelstart_article_details` | Reads prices, VAT and revenue settings for the numeric `article_id` from search. |
| `snelstart_bank_journals` | Lists bank and cash journals, including their ledger UUIDs. |
| `snelstart_bank_entries` | Lists a journal's entries in an inclusive date range. Accepts a search term and a marked-only filter. |
| `snelstart_find_payment_matches` | Searches for candidate invoices for an incoming or outgoing payment. |
| `snelstart_search_quotations` | Searches quotations by text and status. Use the quotation UUID from `identifier`. |
| `snelstart_quotation_details` | Reads quotation lines, totals and attachment metadata by UUID. |
| `snelstart_preview_sales_document` | Calculates an invoice or quotation with SnelStart's VAT rules using an existing customer code and numeric article IDs. |
| `snelstart_save_sales_document` | Saves a new invoice or quotation as a draft or as a finished document without sending it. |
| `snelstart_email_new_sales_document` | Creates and requests delivery of a new invoice or quotation, with a one-off message and optional local attachments. |
| `snelstart_sales_email_template` | Reads the default subject, body and attachment metadata for invoice or quotation email. |
| `snelstart_sent_email_history` | Reads Web email history and delivery status by search term. |
| `snelstart_check_purchase_posting` | Checks a ledger account's function and cost-centre rule for standard, domestic reverse-charge, foreign or payment-discount purchases. |

Purchase searches check the upstream total and row IDs, then sort by invoice date (newest first) and row ID before applying `skip` and `take`. If SnelStart repeats a row, the MCP tries retrieving shorter date ranges and checks their combined count and IDs. It returns an error if it cannot verify complete results. Each scan is limited to 5,000 rows and 64 upstream requests. Narrow the date range or search term if coverage fails.

For an exact purchase invoice search, pass `invoice_number` as a string and keep any leading zeros. If an all-digit `query` returns zero native matches, the MCP also tries the exact search. The exact reference and `review_only` filters are applied before `skip` and `take`.

With `review_only: true`, the MCP reads checked pages and includes rows with `isTeControlerenInkoop: true`. It reports the filtered total and applies `skip` and `take` to the marked rows. Narrow the date range if it exceeds the checked-search limit.

For an invoice review, search the period and open each purchase with `kind: "purchase"`. Pass the search row's `publicIdentifier` as `entry_id` and, when present, its `factuurnummeridentifier` as `purchase_invoice_id` to the single or batch booking tool. When the usual detail lookup returns HTTP 400, the MCP can use the invoice ID to retrieve and verify the same booking. A remaining `purchase_detail_rejected` failure leaves the batch incomplete. Use the search row as list-level evidence and report the missing detail. Read the attached invoice and recorded settlements where available. For lists with `skip` and `take`, advance through all pages before reporting a period total.

Example purchase filter for entries flagged during November 2026.

```json
{"start_date":"2026-11-01","through_date":"2026-11-30","review_only":true,"take":50}
```

#### Download a purchase PDF

1. Find the invoice with `snelstart_search_purchases` using a date range and, if available, the exact `invoice_number`.
2. Pass the purchase entry UUID as `entry_id` to `snelstart_list_attachments` with `kind: "purchase"`.
3. Pass the PDF's `attachmentIdentifier` as `attachment_id` to `snelstart_download_document`. The tool returns the path to the private local file.

#### Attach a PDF to an existing cash or bank booking

1. Confirm the administration and use the booking's nonzero `identifier` from the cash or bank journal as `entry_id`.
2. Call `snelstart_attach_bank_pdf` with the administration UUID, booking UUID and absolute local `file_path`. The maximum PDF size is 25 MiB. When local approval is enabled, review the exact booking and file checksum and retry with the returned approval ID.
3. A successful response returns the attachment UUID and verified SHA-256. The tool downloads the linked PDF for the check. Repeating the same file on the same booking verifies the original link. If the outcome is uncertain, check the booking before attempting another write.

Scoped write access requires `GET /Attachments/GetAttachmentUploadUriNew` and `POST /KasBankBoeking/AddAttachment`. [SnelStart cash and bank attachments](https://kennispleinweb.snelstart.nl/nl/een-bijlage-toevoegen-aan-een)

#### Submit a new purchase PDF

1. Check that the selected administration is the one intended for the upload. For scoped write access, grant both upload operations listed below.
2. Call `snelstart_upload_purchase_pdf` with the selected administration UUID as `administration_id` and an absolute local PDF path as `file_path`. Review the path and file checksum in the local approval window, then retry with its `approval_id`. The tool accepts one PDF of up to 25 MiB and returns an `instance_id`.
3. Call `snelstart_purchase_upload_status` with that ID and the same administration UUID. Once processing completes, review the recognized invoice under **Inkopen → Te controleren**. [SnelStart purchase recognition](https://kennispleinweb.snelstart.nl/nl/inkoopfacturen-of-bonnetjes-automatisch-inlezen-in-snelstart-web)

With scoped permissions, grant both operations for the same administration.

```sh
uv run snelstart-mcp writes grant ADMINISTRATION_UUID 'GET /Attachments/GetAttachmentUploadUriNew'
uv run snelstart-mcp writes grant ADMINISTRATION_UUID 'POST /Purchases/CreateInkoopVoorBijlage'
```

The profile keeps a local receipt keyed by administration and PDF checksum. Repeating a confirmed submission returns its existing processing ID. After an unconfirmed submission, check the purchase overview before attempting to send the document again.

#### Prepare, save or email a new sales document

1. Confirm the administration, then use `snelstart_sales_invoice_readiness` to check company settings. Find the customer with `snelstart_search_relations` and use the numeric `relationCode`. Find each `articleId` with `snelstart_search_articles`.
2. Call `snelstart_preview_sales_document` with `kind` set to `invoice` or `quotation`. Supply the document date, optional order date and payment terms, and one or more lines. An omitted unit price uses the article's configured price. Supply an explicit price for a negotiated rate.
3. For save only, use `snelstart_save_sales_document` with the same inputs and `expected_gross` from the reviewed preview. Use `draft: true` to keep the document as a concept. Verify it in sales or quotations search.
4. To create and send in one step, use `snelstart_email_new_sales_document` with the same inputs and expected gross, plus the exact recipient, subject and message. Supply absolute local `attachment_paths` when requested. Files total at most 10 MB. Review the request before releasing it. Sending may create a record even when delivery is blocked. Check the sales or quotation overview and sent-mail history before retrying. Use the Web interface to send or resend a document already saved. [Invoice guide](https://kennispleinweb.snelstart.nl/nl/een-factuur-maken-in-snelstart-web) · [Quotation guide](https://kennispleinweb.snelstart.nl/nl/een-offerte-maken-in-snelstart-web) · [Email guide](https://kennispleinweb.snelstart.nl/nl/mailen-vanuit-snelstart-web)

Emailing needs a scoped grant for `POST /Invoices/Send` or `POST /Quotations/SaveAndSend` in the selected administration. Attachments also need permission for `GET /Attachments/GetAttachmentUploadUriNew`. Sending a one-off message leaves the default template alone. A result of `submitted` means SnelStart accepted the send request. Use `snelstart_sent_email_history` for SnelStart's delivery status.

#### Check a specialised purchase before posting

Use `snelstart_check_purchase_posting` with the selected administration UUID and the actual ledger account number. Select `domestic_reverse_charge`, `intra_eu`, `outside_eu` or `payment_discount` when applicable. For foreign purchases, provide the applicable Dutch VAT band as `low`, `high` or `other`. For a realised early payment discount, provide the invoice total and observed payment. The tool checks the account function and its cost-centre requirement. Include `purchase_id` and, when available, `purchase_invoice_id` from the same search row to inspect recorded ledger and VAT lines. An empty VAT detail does not establish the return treatment. The result supplies evidence for posting in the Web interface. [Domestic reverse charge](https://kennispleinweb.snelstart.nl/nl/een-inkoopfactuur-btw-verlegd-boeken) · [Foreign purchases](https://kennispleinweb.snelstart.nl/nl/hoe-boek-ik-een-inkoopfactuur-uit-het-buitenland-in-snelstart-web) · [Cost centres](https://kennispleinweb.snelstart.nl/nl/kostenplaats-toevoegen-in-snelstart-web) · [Payment discount](https://kennispleinweb.snelstart.nl/nl/een-inkoopfactuur-met-betalingskorting-boeken)

### Financial reports and tax

| Tool | What it does |
| --- | --- |
| `snelstart_chart_of_accounts` | Lists ledger accounts and their identifiers. |
| `snelstart_ledger_account_details` | Reads a ledger account by `account_number`, including VAT and cost-centre settings. Use `data.publicIdentifier` for ledger tools. The tool consults the chart if the detail response lacks a usable UUID and returns `null` if there is no unambiguous match. |
| `snelstart_balance_sheet` | Reads the balance sheet, profit and loss, and reporting categories for a `through_date`. |
| `snelstart_financial_result` | Reads the financial result for `start_date` through `through_date` using the report called by the Tax Monitor. |
| `snelstart_ledger_entries` | Reads one page of postings for an account through a given date. |
| `snelstart_export_ledger_entries` | Reads and checks all pages for up to 20 account UUIDs, then exports the requested date range to a private JSONL file. Returns a path, SHA-256, and per-account counts. |
| `snelstart_vat_returns` | Lists VAT returns in their recorded states. Status 0 is not sent, 1 sent, 2 accepted, 3 error, 4 accepted and recalculated, and 5 recorded as accepted externally. |
| `snelstart_vat_return_details` | Reads the details of up to 20 VAT returns by public UUID. |
| `snelstart_icp_returns` | Lists ICP returns with source validation messages. Pass the returned `next_skip` to read the next page. |
| `snelstart_icp_return_details` | Reads up to 20 persisted ICP returns by their nonzero public UUIDs. |
| `snelstart_supplemental_vat_years` | Lists years eligible for a supplemental VAT return. |
| `snelstart_year_end_review` | Reads open entries, open purchases, open sales or year-end bookings for a year, when available. |

For 2025 and November 2026 balances, call `snelstart_balance_sheet` separately with `2025-12-31` and `2026-11-30`. For detailed VAT returns, start with `snelstart_vat_returns` and pass the public identifiers as `return_ids` to `snelstart_vat_return_details`.

For a multi-account review, pass `ledger_ids`, `start_date`, and `through_date` to `snelstart_export_ledger_entries`. Each line contains `ledger_id` and the original `entry`. For a range of multiple days, the tool checks the administration's fiscal-year dates and fetches the part of each fiscal year in the range separately. If the final date is beyond the closing list, the tool verifies the active fiscal year against the administration settings. It rejects ranges with unverified fiscal-year coverage. `fetched_rows` counts the rows from the validated pages across all parts. `exported_rows` counts the rows in the requested range.

If a row ID is missing or repeated, the tool starts again from page one for that account and fiscal period. If the retry fails, the error names the account, dates and cause. A failed export discards the incomplete file. Treat the file as private accounting data.

```json
{"operation":"GET /BtwAangiftes/Get","parameters":{"id":123}}
```

For ICP, use `snelstart_icp_returns` and pass `publicIdentifier` from a persisted row to `snelstart_icp_return_details` as part of `return_ids`. Use the list row for a calculation that has yet to be saved. The Tax Monitor's final reservation for income or corporate tax remains in SnelStart Web. Its financial-result input is available in the MCP. [SnelStart Tax Monitor documentation](https://kennisplein.snelstart.nl/migration/nl/snelstartweb/wat-is-de-belastingmonitor-in-snelstart)

## Evidence and reconciliation

| Tool | Use |
| --- | --- |
| `snelstart_get_entries` | Read up to 20 mixed purchase, bank, journal and opening-balance bookings. Pass `entries` as objects with `kind` and `entry_id`. Each result keeps its ID and reports whether it was found, missing, failed or too large for the batch. |
| `snelstart_export_bank_entries` | Pass `journal_ids`, `start_date` and `through_date`. All checked pages are exported to a private JSONL file. The result includes the administration, row counts per journal and SHA-256. The file preserves journal metadata and original bank rows, including markings and invoice links when present. A failed page discards the export. |
| `snelstart_reconcile_bank` | Review recorded links and suggested matches for the same journal and date inputs. Use `invoice_start_date` to adjust the default 90-day invoice lookback and `skip` and `take` to page the report. |
| `snelstart_read_payment_report` | Read a local provider CSV and return paginated payout totals with a SHA-256. |
| `snelstart_compare_payment_report` | Compare payouts with positive bank entries for one journal and date range. Returns reference-and-amount evidence, amount-only candidates, ambiguity, or no candidate. |
| `snelstart_compare_archives` | Pass `before`, `after` and one of `purchases`, `sales`, `bank_entries` or `journal_and_opening_entries`. The tool compares checksummed dataset files locally. Both archives must identify the same administration, year and cutoff. Journal datasets must cover the same journals. Read an individual archived balance and profit-and-loss report with `snelstart_snapshot_read` in an offline session. |

For journal attachments, use `snelstart_list_attachments` with `kind: "journal"` even if the booking detail says `hasBijlagen: false`. Both that flag and the ledger's `hasAttachments` are hints. To check linked files for several purchases, bank transactions or journal entries, pass `include_attachments: true` to `snelstart_get_entries`. An empty `attachments` list means the lookup found no linked files. A failed lookup returns `attachment_lookup_error` and sets `complete: false` while preserving the booking details. For an opening balance, the batch keeps the booking details and reports attachment lookup as unavailable. For a single opening balance, call `snelstart_list_attachments` with `kind: "opening_balance"` to receive `data: null` and `attachment_lookup_error`.

The `size` in an attachment list is SnelStart metadata. Even a nonzero size can differ from the downloaded byte count. For a byte-for-byte check against an independently saved original, compare its byte count and SHA-256 with the `bytes` and `sha256` returned by `snelstart_download_document`.

Reconciliation reports recorded SnelStart links separately from suggestions. Suggestions use the bank entry’s signed amount, an invoice date on or before the payment date, and reference or counterparty evidence. Competing and amount-only matches remain ambiguous. Duplicate flags and missing-document indicators are review signals. Document indicators come from SnelStart’s attachment flags. Suggested matches require human review before making any bookkeeping changes.

If a bank detail returns HTTP 500, pass `bank_list_context` to `snelstart_get_entry` or to that entry in `snelstart_get_entries`. Set `journal_id` to the journal UUID and `booking_date` to the local date from the bank list or export. The MCP checks the selected day's pagination and requires the exact `identifier`. It returns a match in `bank_list_evidence` with `failure_code: "bank_detail_unavailable"`. The detail stays empty, and a batch containing that result has `complete: false`. If the list cannot be verified, the tool reports that failure.

Archive comparisons report additions, removals, and changed field names between the selected snapshots. These describe differences in the saved datasets.

### Payment-provider reports

Pass an absolute CSV path as `file_path` and choose `provider`. Use `skip` and `take` to page the payout groups. Each read is limited to 12 MiB and 100,000 report rows. The tool processes the file locally.

| Provider | Supported report |
| --- | --- |
| `stripe` | Itemized automatic payout reconciliation with `automatic_payout_id`, `balance_transaction_id`, `currency`, and `net`. The balance report for manual payouts uses a different format. [Stripe reports](https://docs.stripe.com/reports/payout-reconciliation) |
| `mollie` | Settlement CSV with `Settlement reference`, `Settlement currency`, and `Settlement amount`. For localized files set `mollie_columns` with the corresponding exact headers in `settlement_reference`, `settlement_currency`, and `settlement_amount`. [Mollie reports](https://docs.mollie.com/docs/settlement-report) |
| `adyen` | Settlement details CSV with merchant account, batch number, type, net currency, net debit, and net credit. Include `Modification Reference` to match the payout's bank reference when supplied. [Adyen reports](https://docs.adyen.com/reporting/settlement-reconciliation/transaction-level/settlement-details-report) |

To check a report against SnelStart, also pass `bank_journal_id`, `bank_currency`, `start_date`, and `through_date` to `snelstart_compare_payment_report`. Use the selected journal's currency and a range that includes the expected bank receipt. Review amount-only candidates and ambiguous results against the bank statement. When an Adyen report includes a declared payout, the result shows the difference between it and the calculated sum separately. The comparison covers bank evidence only. Invoice allocation and posting are separate steps.
