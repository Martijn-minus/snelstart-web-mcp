# SnelStart Web knowledge base coverage

This matrix covers bookkeeping workflows the MCP supports and gaps relevant to working with SnelStart Web. The source review screened 134 URLs in the Dutch Web knowledge base. Coverage comes from tool contracts, catalog entries and tests. Treat generic writes and delivery workflows as unverified until tested. [SnelStart Web feature overview](https://kennispleinweb.snelstart.nl/nl/functionaliteiten-in-snelstart-web)

## How to read the results

| Coverage | Meaning | Pages |
| --- | --- | --- |
| Dedicated | Dedicated MCP workflow for the article’s principal action. | 5 |
| Partial | MCP covers one or more useful steps. See the outstanding steps in the row. | 28 |
| Catalog | Related generic operations exist. The MCP lacks a validated workflow for this task. | 13 |
| Gap | The main action has no supported MCP workflow. | 8 |

Generic operation availability depends on the MCP allowlist and SnelStart account permissions. See the [tool reference](tools.md) and [write permissions](writes-and-audit.md).

## Areas for future MCP work

1. Extend the sales workflow with sending an existing saved invoice or quotation, quotation-to-invoice conversion and template editing.
2. Add bank file imports and extend payment-provider reconciliation from bank receipts to invoice allocation and ledger checks.
3. Add typed review and posting support for recognized purchases, cost centres and specialised VAT handling. Preserve the original source document and verify the posted result.
4. Expand read coverage for Tax Monitor and RGS.

## Skills

The source skills live in [`.agents/skills`](../.agents/skills/). The rows below show where a skill guides tool use, evidence checks or a handoff to SnelStart Web. Links to the original articles provide package and interface details.

- **Setup** [`snelstart-setup`](../.agents/skills/snelstart-setup/SKILL.md)
- **Administration** [`snelstart-administration`](../.agents/skills/snelstart-administration/SKILL.md)
- **Sales** [`snelstart-sales`](../.agents/skills/snelstart-sales/SKILL.md)
- **Purchases** [`snelstart-purchases`](../.agents/skills/snelstart-purchases/SKILL.md)
- **Bank** [`snelstart-bank`](../.agents/skills/snelstart-bank/SKILL.md)
- **Reconcile** [`snelstart-reconcile`](../.agents/skills/snelstart-reconcile/SKILL.md)
- **Tax** [`snelstart-tax`](../.agents/skills/snelstart-tax/SKILL.md)
- **Year-end** [`snelstart-year-end`](../.agents/skills/snelstart-year-end/SKILL.md)

## Workflow coverage

### Sales

| Knowledge base page | MCP coverage | Skill | Finding |
| --- | --- | --- | --- |
| [Een herinnering versturen vanuit SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-herinnering-versturen-vanuit-snelstart-web) | Catalog | Sales | Reminder write route exists. Recipient, content and delivery need separate verification. |
| [Een verkoopfactuur met btw verlegd maken](https://kennispleinweb.snelstart.nl/nl/een-verkoopfactuur-met-btw-verlegd-maken) | Catalog | Sales, Tax | Invoice write routes exist. Reverse-charge requirements and totals need validation. |
| [Een factuur maken in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-factuur-maken-in-snelstart-web) | Dedicated | Sales | Dedicated calculation, draft, save-only and new-document email with attachments. Existing-document sending, layout editing and specialised invoice modes remain open. |
| [Een e-factuur versturen of ontvangen](https://kennispleinweb.snelstart.nl/nl/een-e-factuur-versturen-of-ontvangen-in) | Catalog | Sales | Peppol send routes exist. No validated receiver setup, delivery or inbound workflow. |
| [Een offerte maken in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-offerte-maken-in-snelstart-web) | Dedicated | Sales | Dedicated quotation search, detail, draft, save and new-document email. Quotation conversion and layout editing remain open. |
| [Mailen vanuit SnelStart Web](https://kennispleinweb.snelstart.nl/nl/mailen-vanuit-snelstart-web) | Partial | Sales | One-off email and local attachments for a new invoice or quotation, plus template reads and sent-email status. Editing default templates and sending existing documents remain open. |
| [Een klant aanmaken in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-klant-invoeren-in-snelstart-web) | Catalog | Sales | Customer search is dedicated. Customer creation and update use generic routes. |
| [Een factuur wijzigen of verwijderen in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-factuur-wijzigen-of-verwijderen-in-snelstart-web) | Catalog | Sales | Update and delete routes exist. Payment dependencies and outcome need verification. |
| [Een factuur kopiëren in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-factuur-kopi%C3%ABren-in-snelstart-web) | Catalog | Sales | Copy and invoice write entries exist. No verified clone workflow. |
| [Een factuur maken zonder btw in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-factuur-maken-zonder-btw) | Catalog | Sales, Tax | Generic invoice writes. Zero VAT or exemption needs correct source and account treatment. |
| [Een factuur maken voor een klant in het buitenland](https://kennispleinweb.snelstart.nl/nl/een-factuur) | Catalog | Sales, Tax | Generic invoice write routes. No guided international invoice workflow. |
| [Een artikel aanmaken in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-artikel-toevoegen-in-snelstart-web) | Partial | Sales | Dedicated article search and detail reads. Creation and update use generic routes. |
| [Een creditfactuur maken of een credit inkoopfactuur boeken in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-creditfactuur-maken-in-snelstart-web) | Catalog | Sales, Purchases | Sale credit preparation and booking routes exist. No dedicated credit workflow. |
| [Het volgende factuurnummer instellen in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/volgend-factuurnummer-instellen-in-snelstart-web) | Catalog | Sales | Next-number setting requires an explicit scoped grant. |

### Purchases

| Knowledge base page | MCP coverage | Skill | Finding |
| --- | --- | --- | --- |
| [Een inkoopfactuur controleren](https://kennispleinweb.snelstart.nl/nl/een-inkoopfactuur-controleren) | Partial | Purchases | Read the review count, recognized fields and linked attachments. Editing and posting review items use generic routes. |
| [Een leverancier toevoegen in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-leverancier-toevoegen-in-snelstart-web) | Catalog | Purchases | Supplier search is dedicated. Supplier creation and update use generic routes. |
| [Een inkoopfactuur of bonnetje automatisch inlezen in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/inkoopfacturen-of-bonnetjes-automatisch-inlezen-in-snelstart-web) | Partial | Purchases | PDF submission and recognition status are dedicated. Email setup and recognition review or final posting are separate. |
| [Een inkoopfactuur met btw verlegd boeken](https://kennispleinweb.snelstart.nl/nl/een-inkoopfactuur-btw-verlegd-boeken) | Partial | Purchases, Tax | Check domestic account function 32 and read back recorded lines and VAT evidence. The reverse-charge update remains in the Web interface. |
| [Werken met kostenplaatsen in SnelStart Web. Hoe werkt dit?](https://kennispleinweb.snelstart.nl/nl/kostenplaats-toevoegen-in-snelstart-web) | Partial | Purchases | Check ledger requirements and inspect the assignment on an existing purchase. Creating cost centres and assigning them remain outside the dedicated tools. |
| [Een inkoopfactuur uit het buitenland boeken in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/hoe-boek-ik-een-inkoopfactuur-uit-het-buitenland-in-snelstart-web) | Partial | Purchases, Tax | Check EU or non-EU account function against the chosen Dutch VAT band and examine recorded lines. The Web flow can save an account line even when detail exposes no VAT lines. Posting and return treatment need separate verification. |
| [Een inkoopfactuur met betalingskorting boeken](https://kennispleinweb.snelstart.nl/nl/een-inkoopfactuur-met-betalingskorting-boeken) | Partial | Purchases, Reconcile | Check the function 102 payment-difference account and calculate the difference from the actual payment. Posting the settlement adjustment and reviewing VAT remain separate. |

### Bank and cash

| Knowledge base page | MCP coverage | Skill | Finding |
| --- | --- | --- | --- |
| [Een grootboekrekening koppelen aan een betaling in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-grootboekrekening-koppelen-aan-een-betaling) | Catalog | Bank | Bank update and ledger-link routes exist. No validated allocation workflow. |
| [Paypal afschriften inlezen in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/paypal) | Gap | Bank | No PayPal statement import. Read already imported bank entries. |
| [Een verschil in het saldo op je bank en het saldo in je dagboek bank in SnelStart](https://kennispleinweb.snelstart.nl/nl/verschil-in-saldo) | Partial | Bank | Inspect journal rows and compare them with an independent bank statement. No built-in connection balance check. |
| [Een factuur koppelen aan een betaling in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-factuur-koppelen-aan-een-betaling-in-snelstart-web) | Partial | Bank, Reconcile | Read recorded links and suggested matches. Allocation writes use generic routes. |
| [Bankafschriften handmatig inlezen in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/bankafschriften-handmatig-inlezen-in-snelstart-web) | Gap | Bank | No manual bank statement import. |
| [Een bijlage toevoegen aan een bestaande kas- of bankboeking in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-bijlage-toevoegen-aan-een) | Partial | Bank | List and download linked files. No local file-to-bank-booking upload workflow. |
| [Een factuur als betaald registreren in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-betaling-registreren-in-snelstart-web) | Partial | Reconcile | Read payment and settlement evidence. Register or unregister through generic routes. |
| [Een factuur als privé registreren in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-factuur-als-priv%C3%A9-betaald-registreren) | Partial | Bank, Reconcile | Review accounting and settlement evidence. No guided private-payment posting. |
| [Handmatig een kasstaat inboeken in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/handmatig-een-kasstaat-inboeken-in-snelstart-web) | Partial | Bank | Cash journals can be read. No guided cash-statement booking. |
| [Ontbrekende mutaties bij automatische bankkoppeling? Zo krijg je ze alsnog in je administratie](https://kennispleinweb.snelstart.nl/nl/ik-heb-een-automatische-bankkoppeling-maar-de-m) | Partial | Bank | Audit imported coverage. Recover missing entries in the official interface. |
| [Een kasboeking maken in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-kasboeking-maken-in-snelstart-web) | Partial | Bank | Read cash journal entries. Cash booking creation uses a generic write. |

### Tax and close

| Knowledge base page | MCP coverage | Skill | Finding |
| --- | --- | --- | --- |
| [Een saldoverschil op de balans](https://kennispleinweb.snelstart.nl/nl/een-saldoverschil-op-de-balans) | Dedicated | Year-end | Compare the prior close, opening balance and ledger entries. |
| [Een memoriaalboeking in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/memoriaalboeking-in-snelstart-web) | Partial | Year-end | Journal details, ledger exports and attachment reads exist. Create and edit through generic routes. |
| [De ICP-aangifte in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/de-icp-aangifte-in-snelstart-web) | Partial | Tax | Dedicated listing, source validation messages, and detail reads for persisted ICP returns. Filing is a separate workflow. |
| [Werken met marge en globalisatie in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/marge-en-globalisatie-in-snelstart-web) | Gap | Tax | No margin or globalisation workflow. |
| [De btw-aangifte in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/de-btw-aangifte-in-snelstart-web) | Partial | Tax | VAT results and detail are dedicated. No verified filing or acknowledgement workflow. Treat an empty carry-forward breakdown on a historical return as unconfirmed. Compare the saved filing or native source when relevant. |
| [Grootboekrekeningen in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/grootboekrekeningen-beheren-in-snelstart-web) | Partial | Year-end | Dedicated chart, account details by number, VAT and cost-centre settings, and ledger reads. Account creation is generic. |
| [Afschrijving bedrijfsmiddelen (activa) automatisch invoeren in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/afschrijving-bedrijfsmiddelen-automatisch) | Gap | Year-end | No fixed asset register or automatic depreciation workflow. |
| [Wat is de Belastingmonitor in SnelStart?](https://kennispleinweb.snelstart.nl/nl/wat-is-de-belastingmonitor-in-snelstart) | Partial | Tax | Financial-result input is dedicated. Tax Monitor settings and final calculation are unavailable. |
| [Je grootboekrekeningen koppelen aan het RGS (Referentie Grootboekschema)](https://kennispleinweb.snelstart.nl/nl/het-grootboekrekeningschema-koppelen-aan-rgs) | Gap | Year-end | No verified RGS mapping workflow. |
| [Beginbalans boeken in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/beginbalans-boeken-in-snelstart-web) | Partial | Year-end | Opening balances can be read. Create and update through generic routes. |
| [Het boekjaar afsluiten in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/boekjaar-afsluiten-in-snelstart-web) | Partial | Year-end | Read closing data and evidence. Closing writes are scoped catalog operations with no dedicated closure verification. |
| [De Kleineondernemersregeling en vrijgesteld van btw in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/kleineondernemersregeling-instellen-in-snelstart-web) | Gap | Tax | No supported KOR or exemption-settings workflow. |

### Reporting

| Knowledge base page | MCP coverage | Skill | Finding |
| --- | --- | --- | --- |
| [Rapportages in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/rapportages-in-snelstart-web) | Partial | Year-end | Balance, result and ledger reads are dedicated. The full dashboard and report presentation are unavailable. |
| [Een RGS Brugstaat downloaden uit SnelStart](https://kennispleinweb.snelstart.nl/nl/een-rgs-brugstaat-opmaken-in-snelstart) | Gap | Year-end | No official RGS bridge statement download. |

### Administration

| Knowledge base page | MCP coverage | Skill | Finding |
| --- | --- | --- | --- |
| [Bestanden en bijlagen downloaden in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/bestanden-en-bijlagen-downloaden-in-snelstart-web) | Partial | Administration | Individual document downloads and local year archives exist. Official bulk exports are supplied separately. |
| [Een administratie openen in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-administratie-openen-in-snelstart-web) | Dedicated | Administration | List and select an administration available to the account. |
| [Een herstelpunt van je administratie maken](https://kennispleinweb.snelstart.nl/nl/een-herstelpunt-van-een-administratie-maken-in-snelstart-web) | Gap | Administration | No supported MCP point-in-time recovery workflow. Verify local year archives separately. |
| [Een back-up van je administratie maken](https://kennispleinweb.snelstart.nl/nl/een-back-up-van-je-administratie-maken) | Partial | Administration | Local MCP year archive with integrity check. Native SnelStart backup and restore are separate. |
| [Bedrijfsgegevens invoeren of wijzigen in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/bedrijfsgegevens-invoeren-of-wijzigen-in-snelstart-web) | Catalog | Administration | Company setting read and update routes exist. |
| [Inloggen in SnelStart Web en in de SnelStart App](https://kennispleinweb.snelstart.nl/nl/inloggen-in-snelstart-web) | Dedicated | Setup | Browser sign-in and session checks for the local MCP. |

### Payment providers

| Knowledge base page | MCP coverage | Skill | Finding |
| --- | --- | --- | --- |
| [Koppelen met betaalproviders](https://kennispleinweb.snelstart.nl/nl/koppelen-met-betaalproviders) | Partial | Reconcile | Read local Adyen, Mollie and Stripe CSVs and compare payout amounts and references with bank receipts. Account connections, invoice allocation and other providers remain open. |
| [Mollie en SnelStart](https://kennispleinweb.snelstart.nl/nl/koppeling-met-mollie-en-de-verwerking-van-mollie) | Partial | Reconcile | Read localized settlement CSVs and check bank receipts. Connection setup and posting remain in SnelStart. |
