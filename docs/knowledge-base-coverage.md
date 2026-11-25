# SnelStart Web knowledge base coverage

Reviewed 25 November 2026 against SnelStart MCP `2026.11.25.6`. The review covers all 134 URLs in the Dutch Web knowledge base sitemap and the eight public category indexes. The sitemap includes navigation and search pages as well as articles. The categories did not surface additional Dutch Web article URLs outside the sitemap. [Knowledge base](https://kennispleinweb.snelstart.nl/nl) · [Sitemap](https://kennispleinweb.snelstart.nl/sitemap.xml) · [SnelStart Web feature overview](https://kennispleinweb.snelstart.nl/nl/functionaliteiten-in-snelstart-web)

The MCP targets SnelStart Web. The audit records articles about connected or separate products when they appear in the Web knowledge base. Coverage is based on the repository's tool contracts, catalog, configuration and tests. No live account changes or delivery tests were part of this review.

## How to read the results

| Coverage | Meaning | Pages |
| --- | --- | --- |
| Dedicated | Dedicated MCP workflow for the article’s principal action. | 3 |
| Partial | MCP covers one or more useful steps. See the outstanding steps in the row. | 30 |
| Catalog | Related generic operations exist. The MCP lacks a validated workflow for this task. | 16 |
| Gap | The main action has no supported MCP workflow. | 32 |
| Reference | Help, navigation, account, external or separate-product material. | 53 |

The catalog contains 237 operations. 70 are classified as read-only. A catalog entry documents an observed Web operation. Generic availability also depends on the MCP allowlist, the selected administration, and SnelStart account permissions and subscription.

## Areas for future MCP work

1. Add a typed sales invoice workflow with totals, a draft or save step, file attachments for outbound email, and a separate explicit send step. Validate the flows in a test administration before advertising them.
2. Add bank file and processor reconciliation inputs. The current MCP reads imported bank entries. Keep bank connection, consent and payment initiation in the official interface.
3. Add typed review and posting support for recognized purchases, cost centres and specialised VAT handling. Preserve the original source document and verify the posted result.
4. Expand read coverage for ICP detail, Tax Monitor and RGS. Treat official submissions, recovery points and account administration as separate workflows.

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

## Article-by-article results

### Sales

| Knowledge base page | MCP coverage | Skill | Finding |
| --- | --- | --- | --- |
| [Een herinnering versturen vanuit SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-herinnering-versturen-vanuit-snelstart-web) | Catalog | Sales | Reminder write route exists. Recipient, content and delivery need separate verification. |
| [Een verkoopfactuur met btw verlegd maken](https://kennispleinweb.snelstart.nl/nl/een-verkoopfactuur-met-btw-verlegd-maken) | Catalog | Sales, Tax | Invoice write routes exist. Reverse-charge requirements and totals need validation. |
| [Verkopen](https://kennispleinweb.snelstart.nl/nl) | Reference | — | Category index. |
| [Een factuur maken in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-factuur-maken-in-snelstart-web) | Partial | Sales | Read sales and use a generic save route. No guided creation, outgoing attachment upload, or sales-document recognition workflow. |
| [Melding: Er is voor dit artikel in combinatie met de gekozen klant geen omzetrekening beschikbaar](https://kennispleinweb.snelstart.nl/nl/melding) | Catalog | Sales | Inspect article/customer and ledger data. No guided sales-account correction. |
| [Een e-factuur versturen of ontvangen](https://kennispleinweb.snelstart.nl/nl/een-e-factuur-versturen-of-ontvangen-in) | Catalog | Sales | Peppol send routes exist. No validated receiver setup, delivery or inbound workflow. |
| [Werking van de Snelstart Kassa](https://kennispleinweb.snelstart.nl/nl/werking-van-de-snelstart-kassa) | Reference | — | SnelStart Kassa is a separate product. |
| [Pakbon, werkbon, bevestiging of afhaalbon maken in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/pakbon-werkbon-bevestiging-of-afhaalbon) | Gap | Sales | No dedicated delivery note, work order, confirmation or collection note workflow. |
| [Een offerte maken in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-offerte-maken-in-snelstart-web) | Gap | Sales | No quotation or quotation layout workflow. |
| [Instellingen van de Snelstart Kassa](https://kennispleinweb.snelstart.nl/nl/instellingen-van-de-snelstart-kassa) | Reference | — | Separate SnelStart Kassa settings. |
| [Mailen vanuit SnelStart Web](https://kennispleinweb.snelstart.nl/nl/mailen-vanuit-snelstart-web) | Partial | Sales | Mail-related write routes exist. No end-to-end email template or custom attachment workflow. |
| [Informatie over een e-facturatie naar België vanaf 1 januari 2026](https://kennispleinweb.snelstart.nl/nl/informatie-over-een-e-facturatie-naar-belgi%C3%AB-vanaf-1-januari-2026) | Reference | Sales, Tax | Country-specific e-invoicing guidance. The MCP does not determine compliance. |
| [Een klant aanmaken in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-klant-invoeren-in-snelstart-web) | Catalog | Sales | Customer search is dedicated. Customer creation and update use generic routes. |
| [Een factuur wijzigen of verwijderen in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-factuur-wijzigen-of-verwijderen-in-snelstart-web) | Catalog | Sales | Update and delete routes exist. Payment dependencies and outcome need verification. |
| [Een factuur kopiëren in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-factuur-kopi%C3%ABren-in-snelstart-web) | Catalog | Sales | Copy and invoice write entries exist. No verified clone workflow. |
| [Een factuur maken zonder btw in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-factuur-maken-zonder-btw) | Catalog | Sales, Tax | Generic invoice writes. Zero VAT or exemption needs correct source and account treatment. |
| [Een factuur maken voor een klant in het buitenland](https://kennispleinweb.snelstart.nl/nl/een-factuur) | Catalog | Sales, Tax | Generic invoice write routes. No guided international invoice workflow. |
| [Een artikel aanmaken in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-artikel-toevoegen-in-snelstart-web) | Catalog | Sales | Generic article read, search, create and update routes. |
| [Een factuur maken naar particuliere klanten binnen de EU met buitenlandse btw](https://kennispleinweb.snelstart.nl/nl/afstandsverkopen-van-goederen-en-digitale-diensten-aan-particulieren-binnen-de-eu) | Reference | Sales, Tax | EU consumer VAT and OSS guidance. No guided OSS configuration or filing. |
| [Een creditfactuur maken of een credit inkoopfactuur boeken in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-creditfactuur-maken-in-snelstart-web) | Catalog | Sales, Purchases | Sale credit preparation and booking routes exist. No dedicated credit workflow. |
| [Het volgende factuurnummer instellen in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/volgend-factuurnummer-instellen-in-snelstart-web) | Catalog | Sales | Next-number setting requires an explicit scoped grant. |

### Purchases

| Knowledge base page | MCP coverage | Skill | Finding |
| --- | --- | --- | --- |
| [Een inkoopfactuur controleren](https://kennispleinweb.snelstart.nl/nl/een-inkoopfactuur-controleren) | Partial | Purchases | Checked review search and evidence are dedicated. Editing and posting review items use generic routes. |
| [Een leverancier toevoegen in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-leverancier-toevoegen-in-snelstart-web) | Catalog | Purchases | Supplier search is dedicated. Supplier creation and update use generic routes. |
| [Facturen inlezen via je mailbox](https://kennispleinweb.snelstart.nl/nl/inkoopfacturen-inlezen-via-je-inkopen-mailbox) | Gap | Purchases | No purchase mailbox configuration or email ingestion workflow. |
| [Melding: Uw administratie is niet goed om een bon of factuur te kunnen toevoegen.](https://kennispleinweb.snelstart.nl/nl/melding-administratie-niet-goed-ingericht-voor-bon-toevoegen) | Partial | Purchases | Check upload status and chart of accounts. Correct underlying configuration in SnelStart. |
| [Een inkoopfactuur of bonnetje automatisch inlezen in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/inkoopfacturen-of-bonnetjes-automatisch-inlezen-in-snelstart-web) | Partial | Purchases | PDF submission and recognition status are dedicated. Email setup and recognition review or final posting are separate. |
| [Een inkoopfactuur met btw verlegd boeken](https://kennispleinweb.snelstart.nl/nl/een-inkoopfactuur-btw-verlegd-boeken) | Partial | Purchases, Tax | Upload and evidence reads exist. No dedicated reverse-charge posting. |
| [Werken met kostenplaatsen in SnelStart Web. Hoe werkt dit?](https://kennispleinweb.snelstart.nl/nl/kostenplaats-toevoegen-in-snelstart-web) | Gap | Purchases | No dedicated cost-centre setup or assignment workflow. |
| [Een inkoopfactuur uit het buitenland boeken in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/hoe-boek-ik-een-inkoopfactuur-uit-het-buitenland-in-snelstart-web) | Partial | Purchases, Tax | Compare invoice, ledger and VAT evidence. No validated foreign purchase posting. |
| [Een inkoopfactuur met betalingskorting boeken](https://kennispleinweb.snelstart.nl/nl/een-inkoopfactuur-met-betalingskorting-boeken) | Partial | Purchases, Reconcile | Read invoice, payment and ledger evidence. No guided payment-discount posting. |

### Bank and cash

| Knowledge base page | MCP coverage | Skill | Finding |
| --- | --- | --- | --- |
| [Een grootboekrekening koppelen aan een betaling in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-grootboekrekening-koppelen-aan-een-betaling) | Catalog | Bank | Bank update and ledger-link routes exist. No validated allocation workflow. |
| [Paypal afschriften inlezen in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/paypal) | Gap | Bank | No PayPal statement import. Read already imported bank entries. |
| [Een verschil in het saldo op je bank en het saldo in je dagboek bank in SnelStart](https://kennispleinweb.snelstart.nl/nl/verschil-in-saldo) | Partial | Bank | Inspect journal rows and compare them with an independent bank statement. No built-in connection balance check. |
| [De bankkoppeling activeren](https://kennispleinweb.snelstart.nl/nl/de-bankkoppeling-activeren) | Gap | Bank | No bank connection activation. |
| [Een factuur koppelen aan een betaling in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-factuur-koppelen-aan-een-betaling-in-snelstart-web) | Partial | Bank, Reconcile | Read recorded links and suggested matches. Allocation writes use generic routes. |
| [SnelStart betaalpassen](https://kennispleinweb.snelstart.nl/nl/snelstart-betaalpassen) | Reference | — | Separate banking product and card controls. |
| [Historische transacties ophalen](https://kennispleinweb.snelstart.nl/nl/historische-transacties-ophalen) | Gap | Bank | Audit imported coverage. Historical retrieval is handled in SnelStart. |
| [Direct een betaling doen vanuit Snelstart Web](https://kennispleinweb.snelstart.nl/nl/direct-een-betaling-doen-vanuit-snelstart-web) | Gap | Bank | No payment initiation from a bank account. |
| [Bankafschriften handmatig inlezen in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/bankafschriften-handmatig-inlezen-in-snelstart-web) | Gap | Bank | No manual bank statement import. |
| [Het klantonderzoek (KYC)](https://kennispleinweb.snelstart.nl/nl/het-klantonderzoek-kyc) | Reference | — | Regulated customer onboarding in the banking product. |
| [Een bijlage toevoegen aan een bestaande kas- of bankboeking in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-bijlage-toevoegen-aan-een) | Partial | Bank | List and download linked files. No local file-to-bank-booking upload workflow. |
| [Een factuur als betaald registreren in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-betaling-registreren-in-snelstart-web) | Partial | Reconcile | Read payment and settlement evidence. Register or unregister through generic routes. |
| [SnelStart bankieren opzeggen](https://kennispleinweb.snelstart.nl/nl/snelstart-bankieren-opzeggen) | Reference | — | Banking product cancellation. |
| [Een factuur als privé registreren in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-factuur-als-priv%C3%A9-betaald-registreren) | Partial | Bank, Reconcile | Review accounting and settlement evidence. No guided private-payment posting. |
| [Handmatig een kasstaat inboeken in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/handmatig-een-kasstaat-inboeken-in-snelstart-web) | Partial | Bank | Cash journals can be read. No guided cash-statement booking. |
| [Ontbrekende mutaties bij automatische bankkoppeling? Zo krijg je ze alsnog in je administratie](https://kennispleinweb.snelstart.nl/nl/ik-heb-een-automatische-bankkoppeling-maar-de-m) | Partial | Bank | Audit imported coverage. Recover missing entries in the official interface. |
| [Een kasboeking maken in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-kasboeking-maken-in-snelstart-web) | Partial | Bank | Read cash journal entries. Cash booking creation uses a generic write. |
| [Wat is een UBO?](https://kennispleinweb.snelstart.nl/nl/wat-is-een-ubo) | Reference | — | UBO information for onboarding. |
| [Een bankkoppeling maken](https://kennispleinweb.snelstart.nl/nl/de-nieuwe-generatiebankkoppeling-via-psd2) | Gap | Bank | No PSD2 bank connection setup. |
| [ING bankkoppeling: wat te doen bij een dubbel IBAN-nummer?](https://kennispleinweb.snelstart.nl/nl/ing-bankkoppeling-wat-te-doen-bij-een-dubbel-iban-nummer) | Reference | Bank | Official duplicate-IBAN remediation. |
| [Een zakelijke rekening met SnelStart Bankieren](https://kennispleinweb.snelstart.nl/nl/een-zakelijke-rekening-met-snelstart-bankieren) | Reference | — | Bank account application in the banking product. |
| [Mijn huidige bankkoppeling van de Rabobank, Knab of Triodos bank stopt of werkt niet meer](https://kennispleinweb.snelstart.nl/nl/mijn-huidige-bankkoppeling-van-de-rabobank-of-triodos-werkt-niet-meer) | Reference | Bank | Provider-specific connection recovery. |
| [De toestemming (consent) verlengen](https://kennispleinweb.snelstart.nl/nl/de-toestemming-consent-verlengen) | Gap | Bank | No bank consent renewal. Inspect missing booking dates via the MCP. |

### Tax and close

| Knowledge base page | MCP coverage | Skill | Finding |
| --- | --- | --- | --- |
| [De Brexit en SnelStart](https://kennispleinweb.snelstart.nl/nl/de-brexit-en-snelstart) | Reference | Tax | Country and period-specific tax guidance. |
| [Een saldoverschil op de balans](https://kennispleinweb.snelstart.nl/nl/een-saldoverschil-op-de-balans) | Dedicated | Year-end | Compare the prior close, opening balance and ledger entries. |
| [Een memoriaalboeking in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/memoriaalboeking-in-snelstart-web) | Partial | Year-end | Journal details, ledger exports and attachment reads exist. Create and edit through generic routes. |
| [De ICP-aangifte in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/de-icp-aangifte-in-snelstart-web) | Catalog | Tax | ICP listing and generic write routes exist. No verified calculate-and-file workflow. |
| [Werken met marge en globalisatie in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/marge-en-globalisatie-in-snelstart-web) | Gap | Tax | No margin or globalisation workflow. |
| [De btw-aangifte in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/de-btw-aangifte-in-snelstart-web) | Partial | Tax | VAT results and detail are dedicated. No verified filing or acknowledgement workflow. Treat an empty carry-forward breakdown on a historical return as unconfirmed. Compare the saved filing or native source when relevant. |
| [Grootboekrekeningen in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/grootboekrekeningen-beheren-in-snelstart-web) | Partial | Year-end | Chart of accounts and ledger reads are dedicated. Account creation is generic. |
| [Afschrijving bedrijfsmiddelen (activa) automatisch invoeren in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/afschrijving-bedrijfsmiddelen-automatisch) | Gap | Year-end | No fixed asset register or automatic depreciation workflow. |
| [Wat is de Belastingmonitor in SnelStart?](https://kennispleinweb.snelstart.nl/nl/wat-is-de-belastingmonitor-in-snelstart) | Partial | Tax | Financial-result input is dedicated. Tax Monitor settings and final calculation are unavailable. |
| [Je grootboekrekeningen koppelen aan het RGS (Referentie Grootboekschema)](https://kennispleinweb.snelstart.nl/nl/het-grootboekrekeningschema-koppelen-aan-rgs) | Gap | Year-end | No verified RGS mapping workflow. |
| [Beginbalans boeken in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/beginbalans-boeken-in-snelstart-web) | Partial | Year-end | Opening balances can be read. Create and update through generic routes. |
| [Het boekjaar afsluiten in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/boekjaar-afsluiten-in-snelstart-web) | Partial | Year-end | Read closing data and evidence. Closing writes are scoped catalog operations with no dedicated closure verification. |
| [De Kleineondernemersregeling en vrijgesteld van btw in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/kleineondernemersregeling-instellen-in-snelstart-web) | Gap | Tax | No supported KOR or exemption-settings workflow. |
| [SnelStart fiscaal](https://kennispleinweb.snelstart.nl/nl/snelstart-fiscaal) | Reference | Tax | Separate SnelStart Fiscaal workflows. |

### Reporting

| Knowledge base page | MCP coverage | Skill | Finding |
| --- | --- | --- | --- |
| [Een eigen rapportage uploaden](https://kennispleinweb.snelstart.nl/nl/rapportage-uploaden) | Gap | Year-end | No custom-report upload for SnelStart Rapporten. |
| [Rapportages in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/rapportages-in-snelstart-web) | Partial | Year-end | Balance, result and ledger reads are dedicated. The full dashboard and report presentation are unavailable. |
| [Budgetgegevens importeren](https://kennispleinweb.snelstart.nl/nl/budget) | Gap | Year-end | No Excel budget import for SnelStart Rapporten. |
| [Starten met Rapporten](https://kennispleinweb.snelstart.nl/nl/starten-met-rapporten) | Reference | Year-end | Separate SnelStart Rapporten product setup. |
| [Consolideren in SnelStart Rapporten](https://kennispleinweb.snelstart.nl/nl/consolideren-in-snelstart-rapporten) | Gap | Year-end | No consolidation workflow in SnelStart Rapporten. |
| [Journaalpost en Brugstaat in Rapporten](https://kennispleinweb.snelstart.nl/nl/journaalposten-en-brugstaat-in-snelstart-rapporten) | Gap | Year-end | No SnelStart Rapporten journal or bridge statement workflow. Individual ledger data can be exported. |
| [Forecast in SnelStart Rapporten](https://kennispleinweb.snelstart.nl/nl/forecast-snelstart-rapporten) | Gap | Year-end | No SnelStart Rapporten forecasting workflow. |
| [Het financieel dashboard in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/het-financieel-dashboard-in-snelstart-web) | Partial | Year-end | Balance and result data are available. Full dashboard cards and periods are not reproduced. |
| [Een RGS Brugstaat downloaden uit SnelStart](https://kennispleinweb.snelstart.nl/nl/een-rgs-brugstaat-opmaken-in-snelstart) | Gap | Year-end | No official RGS bridge statement download. |

### Administration

| Knowledge base page | MCP coverage | Skill | Finding |
| --- | --- | --- | --- |
| [Sneltoetsen in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/gebruik-van-sneltoetsen-in-snelstart-web) | Reference | — | Browser keyboard shortcuts. |
| [Melding: u heeft geen rechten om deze pagina te bekijken](https://kennispleinweb.snelstart.nl/nl/melding-u-heeft-geen-rechten-om-deze-pagina) | Reference | Administration | Diagnose the user's SnelStart role and administration access using the official account. |
| [Mijn SnelStart-abonnement heractiveren](https://kennispleinweb.snelstart.nl/nl/mijn-snelstart-abonnement-heractiveren) | Reference | — | Subscription reactivation in Mijn SnelStart. |
| [De veiligheid van SnelStart](https://kennispleinweb.snelstart.nl/nl/informatieveiligheid) | Reference | Setup | Provider security information. |
| [E-mail omtrent onveilig wachtwoord](https://kennispleinweb.snelstart.nl/nl/mail-omtrent-onveilig-wachtwoord) | Reference | Setup | Provider password warning and official recovery. |
| [Waarom staan niet al mijn administraties in SnelStart Web?](https://kennispleinweb.snelstart.nl/nl/waarom-staan-niet-al-mijn-administraties-in-de-lijst-bij-snelstart-web) | Partial | Administration | List available administrations. Missing access must be resolved in SnelStart. |
| [Bestanden en bijlagen downloaden in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/bestanden-en-bijlagen-downloaden-in-snelstart-web) | Partial | Administration | Individual document downloads and local year archives exist. Official bulk exports are supplied separately. |
| [Trainingen over SnelStart](https://kennispleinweb.snelstart.nl/nl/trainingen-over-snelstart) | Reference | — | Training resources. |
| [Documenten uploaden in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/documenten-uploaden-in-snelstart-web) | Gap | Administration | No general-purpose user-document upload workflow. |
| [Een administratie openen in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/een-administratie-openen-in-snelstart-web) | Dedicated | Administration | List and select an administration available to the account. |
| [Systeemeisen voor SnelStart Web](https://kennispleinweb.snelstart.nl/nl/systeemeisen-voor-snelstart-web) | Reference | Setup | Host and browser requirements. |
| [Een administratie of bestand aanleveren voor onderzoek of reparatie](https://kennispleinweb.snelstart.nl/nl/een-bestand-aanleveren-voor) | Reference | Administration | Support intake and secure file submission. |
| [Een herstelpunt van je administratie maken](https://kennispleinweb.snelstart.nl/nl/een-herstelpunt-van-een-administratie-maken-in-snelstart-web) | Gap | Administration | No supported MCP point-in-time recovery workflow. Verify local year archives separately. |
| [Oeps. Deze pagina weet niets.](https://kennispleinweb.snelstart.nl/nl/kb-404) | Reference | — | Published site error template. |
| [Niet tevreden met SnelStart?](https://kennispleinweb.snelstart.nl/nl/niet-tevreden-met-snelstart) | Reference | — | Support and feedback intake. |
| [Het SnelStart abonnement bevestigen](https://kennispleinweb.snelstart.nl/nl/mijn-pakket/abonnement-bevestigen) | Reference | — | Subscription confirmation. |
| [Ik krijg een Incidentcode](https://kennispleinweb.snelstart.nl/nl/ik-krijg-een-incidentcode) | Reference | Setup | Incident code guidance and support. |
| [Veelgestelde vragen in deze periode](https://kennispleinweb.snelstart.nl/nl/veelgestelde-vragen-in-deze-periode) | Reference | — | Cross-topic FAQ index. |
| [Het administratie overzicht voor accountants](https://kennispleinweb.snelstart.nl/nl/het-accountantsdashboard) | Partial | Administration | List accessible administrations. No accountant-wide dashboard. |
| [Zoekresultaten \| SnelStart Web](https://kennispleinweb.snelstart.nl/nl/kb-search-results) | Reference | — | Published search-results page. |
| [De factuur van SnelStart inzien](https://kennispleinweb.snelstart.nl/nl/je-kopie-factuur-downloaden-in-mijnsnelstart) | Reference | — | SnelStart subscription invoices are managed in Mijn SnelStart. |
| [Inloggen met multifactorauthenticatie (MFA)](https://kennispleinweb.snelstart.nl/nl/snelstart-tweetrapsverificatie) | Reference | Setup | Complete MFA in the official sign-in flow. |
| [Starten in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/starten-in-snelstart-web) | Partial | Setup, Administration | Sign in and select available administrations. Provisioning and configuration are manual. |
| [Het wachtwoord van SnelStart](https://kennispleinweb.snelstart.nl/nl/wachtwoord-van-snelstart) | Reference | Setup | Use the official password management flow. |
| [SnelStart 12 en SnelStart Web](https://kennispleinweb.snelstart.nl/nl/snelstart-12-en-snelstart-web) | Reference | Setup | Product comparison. The MCP targets SnelStart Web. |
| [Functionaliteiten in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/functionaliteiten-in-snelstart-web) | Reference | — | Cross-package feature inventory. See the topic rows and summary below. |
| [Ik zoek een accountantskantoor dat met SnelStart werkt?](https://kennispleinweb.snelstart.nl/nl/een-accountant-of-administratiekantoor-die-met-snelstart-werkt) | Reference | — | Referral to accountants. |
| [Het pakket inOrde. Wat kan ik daarmee?](https://kennispleinweb.snelstart.nl/nl/het-pakket-inorde) | Reference | — | SnelStart subscription package information. |
| [Als accountant tijdelijk in een ander pakket werken](https://kennispleinweb.snelstart.nl/nl/als-accountant-tijdelijk-in-een-ander-pakket-werken) | Reference | — | Temporary package selection by an accountant. |
| [Ik heb rechten gekregen maar de online administratie staat niet in mijn lijst](https://kennispleinweb.snelstart.nl/nl/ik-heb-rechten-gekregen-maar-de-online-administratie-staat-niet-in-mijn-lijst) | Partial | Administration | List current access. Invitations and user permissions require SnelStart. |
| [Pakket- en verbruikskosten voor het gebruik van SnelStart](https://kennispleinweb.snelstart.nl/nl/pakket-en-verbruikskosten) | Reference | — | Subscription and usage pricing. |
| [Is er een storing?](https://kennispleinweb.snelstart.nl/nl/storingen) | Reference | Setup | Provider status and incident information. |
| [Het e-mailadres wijzigen](https://kennispleinweb.snelstart.nl/nl/e-mailadres-wijzigen) | Reference | Setup | Account email changes are made in SnelStart. |
| [Offline werken met SnelStart](https://kennispleinweb.snelstart.nl/nl/offline-werken-en-multifactorauthenticatie) | Reference | Administration | SnelStart 12 offline information. MCP archive access is a separate local mode. |
| [Een back-up van je administratie maken](https://kennispleinweb.snelstart.nl/nl/een-back-up-van-je-administratie-maken) | Partial | Administration | Local MCP year archive with integrity check. Native SnelStart backup and restore are separate. |
| [Extra gebruikers en rechten](https://kennispleinweb.snelstart.nl/nl/rechten-voor-gebruikers-aan-of-uitzetten-in-snelstart-web) | Gap | Administration | No extra-user provisioning or permission management. |
| [Ik heb een boek- of notapakket en wil overstappen naar een in-Pakket. Hoe doe ik dat?](https://kennispleinweb.snelstart.nl/nl/ik-heb-een-boek-of-notapakket-en-wil-overstappen-naar-een-in-pakket.-hoe-doe-ik-dat) | Reference | — | Subscription migration. |
| [Jaarbetaling en toch extra facturen van SnelStart?](https://kennispleinweb.snelstart.nl/nl/jaarbetaling-en-toch-extra-facturen-van-snelstart) | Reference | — | Subscription charges. |
| [Mijn abonnement gegevens inzien en/of wijzigen](https://kennispleinweb.snelstart.nl/nl/account-en-pakketgegevens-wijzigen-in-mijnsnelstart) | Reference | — | Subscription and profile data in Mijn SnelStart. |
| [Bedrijfsgegevens invoeren of wijzigen in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/bedrijfsgegevens-invoeren-of-wijzigen-in-snelstart-web) | Catalog | Administration | Company setting read and update routes exist. |
| [Accountant rechten geven tot administratie in SnelStart Web](https://kennispleinweb.snelstart.nl/nl/accountant-rechten-geven-tot-administratie-in-snelstart-web) | Gap | Administration | No accountant invitation or access-grant workflow. |
| [De veiligheid van SnelStart en de online administraties](https://kennispleinweb.snelstart.nl/nl/de-veiligheid-van-snelstart-en-de-online-administraties) | Reference | Setup | Provider security information. |
| [Je SnelStart-abonnement opzeggen](https://kennispleinweb.snelstart.nl/nl/abonnement-opzeggen-bij-snelstart) | Reference | — | Subscription cancellation. |
| [Aanmelden als Bèta-versie testgebruiker](https://kennispleinweb.snelstart.nl/nl/aanmelden-als-b%C3%A8ta-versie-testgebruiker) | Reference | — | Beta enrolment. |
| [De SnelStart App](https://kennispleinweb.snelstart.nl/nl/de-snelstart-app) | Reference | Setup | Mobile app usage and feature guide. |
| [Een administratie aan iemand overdragen](https://kennispleinweb.snelstart.nl/nl/een-administratie-overdragen-van-eigenaar) | Gap | Administration | No ownership transfer. |
| [Een nieuwe administratie toevoegen of verwijderen](https://kennispleinweb.snelstart.nl/nl/nieuwe-administratie-toevoegen-in-snelstart-web) | Gap | Administration | Account lifecycle operations are excluded from generic MCP administration writes. |
| [Inloggen in SnelStart Web en in de SnelStart App](https://kennispleinweb.snelstart.nl/nl/inloggen-in-snelstart-web) | Dedicated | Setup | Browser sign-in and session checks for the local MCP. |
| [Ik heb een idee. Wat kan ik daarmee?](https://kennispleinweb.snelstart.nl/nl/een-idee-registreren) | Reference | — | Official feedback workflow. |

### Integrations

| Knowledge base page | MCP coverage | Skill | Finding |
| --- | --- | --- | --- |
| [Koppelen met SnelStart](https://kennispleinweb.snelstart.nl/nl/koppelen-met-snelstart) | Gap | Setup | Connector provisioning belongs to the relevant provider or SnelStart interface. |
| [LoanStreet en SnelStart](https://kennispleinweb.snelstart.nl/nl/loanstreet) | Reference | — | External financing service. |
| [Koppelen met SnelStart via de API](https://kennispleinweb.snelstart.nl/nl/koppelen-met-snelstart-via-de-api) | Reference | Setup | Official public API setup is a separate integration from this MCP. |
| [Koppelen met betaalproviders](https://kennispleinweb.snelstart.nl/nl/koppelen-met-betaalproviders) | Gap | Reconcile | No direct Adyen, Mollie, MultiSafepay or other payment-provider import. |
| [Wat is Factuur Financiering en hoe gebruik ik dit?](https://kennispleinweb.snelstart.nl/nl/wat-is-factuur-financiering-en-hoe-gebruik-ik-dit) | Reference | — | Third-party invoice financing. |
| [Wat is Flow en hoe gebruik ik dit vanuit SnelStart?](https://kennispleinweb.snelstart.nl/nl/flow-your-money) | Reference | — | Separate Flow service. |
| [Een koppeling met eConnect maken](https://kennispleinweb.snelstart.nl/nl/een-koppeling-met-everbinding-maken) | Gap | Sales | No eConnect provisioning or inbound e-invoice workflow. |
| [Mollie en SnelStart](https://kennispleinweb.snelstart.nl/nl/koppeling-met-mollie-en-de-verwerking-van-mollie) | Gap | Reconcile | No Mollie connection or direct settlement import. Can verify entries already in SnelStart. |
| [Inkoopfacturen omzetten naar ubl bestanden](https://kennispleinweb.snelstart.nl/nl/inkoopfacturen-omzetten-naar-ubl-bestanden) | Gap | Purchases | No Go2UBL connector or arbitrary-file UBL conversion. |
