# MCP-tools

[Terug naar de snelstart](../README.nl.md) · [English](tools.md)

Zie [jaararchieven en offline toegang](backups.nl.md) voor archief- en snapshottools.

## Inkopen, verkopen en betalingen

| Tool | Gebruik |
| --- | --- |
| `snelstart_search_purchases` | Zoek inkopen binnen de periode. Gebruik `query` voor leverancier of tekst, of `invoice_number` voor een exact factuurnummer. Met `review_only: true` beperk je beide zoekmethoden tot gemarkeerde inkopen. |
| `snelstart_get_entry` | Lees een inkoop-, memoriaal-, beginbalans- of bankboeking op UUID. |
| `snelstart_purchase_review_count` | Lees het aantal gemarkeerde inkopen en vraagposten voor de actieve administratie. |
| `snelstart_purchase_review_item` | Lees de herkende velden en optionele bijlagen van één inkoopboeking die op controle wacht. |
| `snelstart_purchase_payments` | Lees de vastgelegde betalingen en vereffeningen van een inkoop. |
| `snelstart_purchase_evidence` | Lees inkoopboekingen, betalingen en optionele bijlagegegevens voor maximaal 20 inkopen tegelijk. |
| `snelstart_attach_bank_pdf` | Koppel een lokale PDF aan een bestaande kas- of bankboeking en verifieer de koppeling en de SHA-256. |
| `snelstart_list_attachments` | Zoek bijlage-ID's van inkoop-, bank- of memoriaalboekingen. |
| `snelstart_download_document` | Sla een bijlage of verkoopfactuur-pdf lokaal op en ontvang het pad, het werkelijke aantal bytes en de SHA-256. |
| `snelstart_upload_purchase_pdf` | Bied één lokale pdf tot 25 MiB aan als nieuwe inkoop ter herkenning en controle. |
| `snelstart_purchase_upload_status` | Controleer de verwerking met het ontvangen `instance_id` en dezelfde administratie-UUID. |
| `snelstart_search_sales` | Zoek verkoopfacturen op klant, factuurnummer of status. |
| `snelstart_sales_invoice_readiness` | Controleer de bedrijfsinstellingen voor verkoopfacturen en toon de namen van lege velden. |
| `snelstart_sales_booking_details` | Lees maximaal 20 geboekte verkopen via hun niet-nulwaarde in `verkoopboekingPublicIdentifier`. Voor concepten gebruik je de zoekrijen van `snelstart_search_sales`. |
| `snelstart_search_quotations` en `snelstart_quotation_details` | Zoek offertes en lees regels, bedragen en bijlagemetadata. |
| `snelstart_preview_sales_document` | Bereken bedragen en btw voor een factuur of offerte met een bestaande klant en artikelen. |
| `snelstart_save_sales_document` | Sla een nieuwe factuur of offerte op als concept of definitief document zonder verzending. |
| `snelstart_email_new_sales_document` | Maak een nieuw verkoopdocument en vraag verzending aan met een eenmalige e-mailtekst en optionele bijlagen. |
| `snelstart_sales_email_template` en `snelstart_sent_email_history` | Lees het standaardsjabloon en de verzendstatus in SnelStart Web. |
| `snelstart_check_purchase_posting` | Controleer de grootboekfunctie en kostenplaatsinstelling bij btw-verlegging, buitenlandse inkopen en betalingskorting. |
| `snelstart_search_relations` | Zoek klanten of leveranciers op naam of nummer. |
| `snelstart_search_articles` | Zoek verkoopartikelen op code of naam. Gebruik `skip` en `take` voor meerdere pagina’s. |
| `snelstart_article_details` | Lees prijzen, btw en omzetinstellingen met het numerieke `article_id` uit de zoekresultaten. |
| `snelstart_bank_journals` | Lees bank- en kasdagboeken met hun grootboek-UUID's. |
| `snelstart_bank_entries` | Lees regels uit een dagboek voor een inclusieve periode, eventueel met een zoekterm of markeringsfilter. |
| `snelstart_find_payment_matches` | Zoek mogelijke factuurmatches voor een inkomende of uitgaande betaling. |

Een vastgelegde vereffening of een saldo van nul vraagt nog om controle met het oorspronkelijke afschrift of betaalbewijs. Loop bij een lijst met `skip` en `take` alle relevante pagina's langs voordat je een periodetotaal rapporteert.

Voor een inkoop-pdf zoek je de inkoop, gebruik je het boekings-ID als `entry_id` met `kind: "purchase"` bij `snelstart_list_attachments` en geef je `attachmentIdentifier` door als `attachment_id` aan `snelstart_download_document`.

Voor een nieuwe upload geef je `administration_id` en het absolute `file_path` mee. Controleer daarna de verwerking en bekijk de herkende inkoop onder **Inkopen → Te controleren**. Bij beperkte schrijfrechten zijn beide opdrachten nodig voor dezelfde administratie. [Inkoopfacturen herkennen in SnelStart](https://kennispleinweb.snelstart.nl/nl/inkoopfacturen-of-bonnetjes-automatisch-inlezen-in-snelstart-web)

```sh
snelstart-mcp writes grant ADMINISTRATIE_UUID 'GET /Attachments/GetAttachmentUploadUriNew'
snelstart-mcp writes grant ADMINISTRATIE_UUID 'POST /Purchases/CreateInkoopVoorBijlage'
```

Een bevestigde herhaling levert het bestaande verwerkings-ID op. Controleer het inkoopoverzicht voordat je een upload met een onduidelijke uitkomst opnieuw verstuurt.

## Balans, resultaat en btw

| Tool | Gebruik |
| --- | --- |
| `snelstart_chart_of_accounts` | Lees het rekeningschema en de beschikbare rekening-ID’s. |
| `snelstart_ledger_account_details` | Lees een rekening op `account_number`, inclusief btw- en kostenplaatsinstellingen. Gebruik `data.publicIdentifier` bij grootboektools. De tool zoekt een ontbrekende UUID in het rekeningschema en geeft `null` als er geen eenduidige match is. |
| `snelstart_balance_sheet` | Lees de balans, winst-en-verliesrekening en rubrieken tot en met `through_date`. |
| `snelstart_financial_result` | Lees het financiële resultaat voor de periode dat als invoer dient voor de Belastingmonitor. |
| `snelstart_ledger_entries` | Lees één pagina grootboekmutaties voor een rekening. |
| `snelstart_export_ledger_entries` | Controleer de paginering en exporteer mutaties voor maximaal 20 rekeningen naar een privé-JSONL-bestand. |
| `snelstart_vat_returns` | Lees de geregistreerde btw-aangiften en hun status. |
| `snelstart_vat_return_details` | Lees de details van maximaal 20 aangiften op publieke UUID. |
| `snelstart_icp_returns` | Lees ICP-opgaven en validatiemeldingen van SnelStart. Gebruik `next_skip` voor de volgende pagina. |
| `snelstart_icp_return_details` | Lees maximaal 20 opgeslagen ICP-opgaven op hun publieke UUID’s met een niet-nulwaarde. |
| `snelstart_supplemental_vat_years` | Lees de jaren die in SnelStart voor een btw-suppletie beschikbaar zijn. |
| `snelstart_year_end_review` | Lees openstaande inkoop-, verkoop- of andere boekingen en eindejaarsboekingen, indien beschikbaar. |

Voor een grootboekexport geef je `ledger_ids`, `start_date` en `through_date` mee. Bij een periode van meerdere dagen controleert de tool de boekjaargrenzen en leest hij elk geraakt boekjaar apart. Valt de einddatum na de laatste jaarafsluiting, dan controleert de tool het lopende boekjaar via de administratie-instellingen. Als de boekjaargrenzen de gevraagde periode niet aantoonbaar dekken, geeft de tool een foutmelding. De uitvoer geeft het bestandspad, de SHA-256 en aantallen per rekening. Elke regel bevat `ledger_id` en de oorspronkelijke `entry` binnen de periode. Behandel de export als privéboekhoudgegevens.

Bij een ontbrekende of dubbele regel-ID begint de tool één keer opnieuw vanaf de eerste pagina van die rekening en boekjaarperiode. Als de tweede poging faalt, noemt de melding de rekening, datums en oorzaak. Bij een mislukte export verwijdert de tool het onvolledige bestand.

Gebruik bij btw-aangiften de publieke UUID's uit `snelstart_vat_returns` als `return_ids`. Geef voor ICP de `publicIdentifier` uit een opgeslagen rij van `snelstart_icp_returns` mee aan `snelstart_icp_return_details`. Gebruik de zoekrij voor een berekening die nog niet is opgeslagen. De uiteindelijke belastingreservering bekijk je in de Belastingmonitor van SnelStart Web. [Belastingmonitor](https://kennisplein.snelstart.nl/migration/nl/snelstartweb/wat-is-de-belastingmonitor-in-snelstart)

## Boekingscontrole en afstemming

| Tool | Gebruik |
| --- | --- |
| `snelstart_get_entries` | Haal maximaal twintig inkoop-, bank-, memoriaal- en beginbalansboekingen in één keer op. Geef per item een `kind` en `entry_id` mee. De uitkomst toont per boeking of die gevonden, afwezig, mislukt of te groot was. |
| `snelstart_export_bank_entries` | Exporteer met `journal_ids`, `start_date` en `through_date` alle gecontroleerde pagina’s naar privé-JSONL. De uitvoer bevat aantallen per dagboek en een SHA-256-controlesom. Markeringen en factuurkoppelingen blijven in de bronregels behouden. Bij een mislukte pagina vervalt de hele export. |
| `snelstart_reconcile_bank` | Bekijk geregistreerde SnelStart-koppelingen en mogelijke factuurmatches. De tool kijkt naar bedrag, datum, omschrijving en tegenpartij. Hij meldt twijfelgevallen, mogelijke dubbelen en signalen over ontbrekende bijlagen. Controleer voorgestelde matches vóór je boekt. |
| `snelstart_read_payment_report` | Lees lokaal een Adyen-, Mollie- of Stripe-CSV en bereken nettototalen per uitbetaling en valuta. |
| `snelstart_compare_payment_report` | Vergelijk uitbetalingen met ontvangsten in één bankdagboek en één periode. |
| `snelstart_compare_archives` | Vergelijk twee lokale jaararchieven met `before`, `after` en `purchases`, `sales`, `bank_entries` of `journal_and_opening_entries` als dataset. De administratie, het boekjaar, de peildatum en de dagboekdekking moeten overeenkomen. Lees de opgeslagen balans en winst-en-verliesrekening per archief via `snelstart_snapshot_read` in een offline sessie. |

Controleer bijlagen van een memoriaalboeking met `snelstart_list_attachments` en `kind: "journal"`, ook als het boekingsdetail `hasBijlagen: false` toont. Die vlag en `hasAttachments` uit het grootboek zijn aanwijzingen. Geef `include_attachments: true` mee aan `snelstart_get_entries` om de bijlagen van meerdere inkoop-, bank- en memoriaalboekingen op te vragen. Een lege lijst in `attachments` betekent dat de controle geen gekoppelde bestanden vond. Als de controle mislukt, blijven de boekingsdetails beschikbaar en rapporteert de tool `attachment_lookup_error` en `complete: false`. Voor beginbalansboekingen blijven de boekingsdetails beschikbaar en meldt de batch dat de bijlagecontrole onbeschikbaar is. Gebruik voor één beginbalans `snelstart_list_attachments` met `kind: "opening_balance"`. De tool geeft dan `data: null` en `attachment_lookup_error` terug.

Het veld `size` in de bijlagelijst komt uit SnelStart. Ook een grootte boven nul kan afwijken van het werkelijke aantal gedownloade bytes. Vergelijk voor een integriteitscontrole het aantal bytes en de SHA-256 van een onafhankelijk bewaard origineel met `bytes` en `sha256` uit `snelstart_download_document`.

De MCP controleert bij inkoopzoekopdrachten het totaal en de rij-ID's. De resultaten worden op factuurdatum (nieuwste eerst) en rij-ID gesorteerd voordat `skip` en `take` worden toegepast. Herhaalt SnelStart een rij, dan probeert de MCP kortere periodes en controleert hij het gezamenlijke totaal en de ID's. Als de volledigheid niet te verifiëren is, geeft de tool een foutmelding. Per scan geldt een limiet van 5.000 rijen en 64 aanvragen aan SnelStart. Verklein de periode of gebruik een specifiekere zoekterm als de controle mislukt.

Geef `invoice_number` als tekst op en behoud eventuele voorloopnullen. Levert een `query` met alleen cijfers via SnelStart nul resultaten op, dan probeert de MCP ook een exacte zoekactie. Met `review_only: true` worden alleen rijen met `isTeControlerenInkoop: true` meegenomen. Beide filters worden vóór `skip` en `take` toegepast.

Gebruik bij inkopen `publicIdentifier` uit de zoekrij als `entry_id` en, als het aanwezig is, `factuurnummeridentifier` uit diezelfde rij als `purchase_invoice_id`. Dit werkt ook met `snelstart_get_entry`. Bij HTTP 400 op de gewone detailroute kan de MCP via het factuur-ID dezelfde boeking ophalen en beide ID's controleren. Als `purchase_detail_rejected` terugkomt, blijft de detailbatch onvolledig. De zoekrij kan nog als bewijs voor de lijstvelden dienen.

Geeft een bankdetail HTTP 500, geef dan `bank_list_context` mee aan `snelstart_get_entry` of aan de betreffende boeking in `snelstart_get_entries`. Neem `journal_id` en de lokale `booking_date` uit de banklijst of export. De MCP controleert de paginering voor die dag en zoekt exact op `identifier`. Een gevonden rij staat in `bank_list_evidence` met `failure_code: "bank_detail_unavailable"`. Het detailveld blijft leeg en de batch meldt `complete: false`. Als de banklijst niet te verifiëren is, meldt de tool dat.

Gebruik bij betaalproviders een lokaal CSV-bestand. Voor een Nederlandstalig Mollie-rapport geef je de exacte kolomnamen op met `mollie_columns`. Geef voor de bankvergelijking `bank_journal_id`, `bank_currency`, `start_date` en `through_date` mee. Controleer kandidaten die alleen op bedrag overeenkomen met het bankafschrift. [Rapportformaten en argumenten](tools.md#payment-provider-reports)

`snelstart_mutation_receipts` en `snelstart-mcp audit` tonen de uitgevoerde schrijfoperatie, een beschikbaar boekings- of verwerkings-ID, controlesommen en de uitkomst. Een time-out blijft onopgelost. Met `snelstart_verify_mutation` kun je op basis van het `receipt_id` ondersteunde acties teruglezen, waaronder nieuw aangemaakte boekingen, geregistreerde verwijderingen en verwerkte inkoop-PDF’s. Andere acties controleer je aan de hand van de brongegevens. Een controle herhaalt de schrijfopdracht nooit.
