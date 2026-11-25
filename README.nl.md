# SnelStart Web MCP

[English](README.md) · **Nederlands**

[Nieuwste release](https://github.com/Martijn-minus/snelstart-web-mcp/releases/latest) · [Releasetags, nieuwste eerst](https://github.com/Martijn-minus/snelstart-web-mcp/tags)

**Deze onafhankelijke MCP maakt verbinding met SnelStart Web (`web.snelstart.nl`).** Je meldt aan met je SnelStart Web-account. De MCP gebruikt de backend van die webapp op `webapi.snelstart.nl`. SnelStart biedt voor partnerkoppelingen een aparte B2B-API. SnelStart Polaris is een afzonderlijke applicatie. [Applicaties van SnelStart](https://kennisplein.snelstart.nl/snelstartpolaris/de-verschillende-applicaties-van-snelstart) · [SnelStart B2B-API](https://www.snelstart.nl/api)

Maak en controleer een back-up voordat je begint. Kies daarna [live alleen-lezen, een offline kopie of live toegang met schrijfrechten](#kies-hoe-je-gegevens-gebruikt). Lees ook de [tekst over gebruik en aansprakelijkheid](NOTICE.md#gebruik-en-aansprakelijkheid).

## De Codex-plugin installeren

Zorg dat de [Codex CLI](https://learn.chatgpt.com/docs/cli) op je PATH staat. Plak daarna deze regel in Terminal op macOS of Linux.

```sh
curl -fsSLo install-snelstart-mcp.sh https://raw.githubusercontent.com/Martijn-minus/snelstart-web-mcp/main/install.sh && bash install-snelstart-mcp.sh --codex-plugin
```

Dit installeert de lokale MCP en de plugin **SnelStart** vanuit de marketplace van deze repository. De plugin bevat de MCP-tools, de boekhoudskills, een installatieskill en hooks. Start daarna een nieuw Codex-gesprek. Meld je zo nodig aan met `snelstart-mcp login --method browser`. In de Codex CLI kun je met `/hooks` bekijken welke hooks je wilt vertrouwen.

Zodra Codex de marketplace **SnelStart MCP** kent, kun je [de installatie in Codex openen](codex://plugins/install/snelstart?marketplace=snelstart-mcp) of **SnelStart** kiezen in die marketplace onder Plugins. [OpenAI-documentatie over plugins](https://developers.openai.com/plugins/build/plugins) · [Installatielinks voor Codex](https://learn.chatgpt.com/docs/app/commands#plugin-install)

Als je SnelStart eerder handmatig registreerde, kan Codex twee MCP-verbindingen tonen. Om alleen de plugin te gebruiken, zet je `enabled = false` onder `[mcp_servers.snelstart]` in de Codex-configuratie. Beide installaties gebruiken hetzelfde standaardprofiel. Voor een afwijkend profiel kun je `SNELSTART_CONFIG_DIR` in de lokale uitvoeromgeving instellen.

## Installeren met een AI-assistent

Kopieer deze opdracht naar Codex, Claude Code of een andere assistent die lokale terminalopdrachten kan uitvoeren.

```text
Installeer SnelStart Web MCP vanaf https://github.com/Martijn-minus/snelstart-web-mcp.
Download op macOS of Linux het bestand install.sh uit de repository en voer het uit.
Gebruik --codex-plugin als dit Codex is en ik de plugin wil. Sla dan handmatige registratie over.
Controleer of Google Chrome beschikbaar is. Start snelstart-mcp login --method browser
en laat mij in Chrome aanmelden. Registreer de MCP met snelstart-mcp install <client> --apply
voor deze client. Voeg op mijn verzoek --with-skills toe voor Codex of Claude Code
en --with-hooks voor Codex. Voer daarna snelstart-mcp doctor uit en meld welke
administratie is geselecteerd, welke schrijfrechten gelden en of er een update
beschikbaar is. Houd aanmeldgegevens privé. Laat schrijfrechten en boekingen intact.
Meld of de client opnieuw moet verbinden en of ik in Codex /hooks moet openen.
```

## Installeren op macOS of Linux

Plak deze regel in Terminal. Je kunt ook [install.sh](install.sh) downloaden en uitvoeren met `bash install.sh`.

```sh
curl -fsSLo install-snelstart-mcp.sh https://raw.githubusercontent.com/Martijn-minus/snelstart-web-mcp/main/install.sh && bash install-snelstart-mcp.sh
```

Het script zoekt Python 3.11 of nieuwer, bijvoorbeeld via Homebrew of de ontwikkeltools van macOS. Als dat nodig is, installeert het `uv` en Python 3.13 in je gebruikersaccount. Open een nieuwe terminal als het script je `PATH` heeft bijgewerkt. Heb je al `uv`, dan kun je ook direct vanaf PyPI installeren.

```sh
uv tool install 'snelstart-web-mcp[browser]'
snelstart-mcp login --method browser
snelstart-mcp doctor
snelstart-mcp install codex --apply
```

Voor aanmelden via de browser heb je Google Chrome nodig. Open na het registreren een nieuwe sessie in je MCP-client. Op Windows kun je het Linux-installatiescript en de MCP-server vanuit WSL draaien. Native Windows en Git Bash worden vanwege de Unix-bestandsvergrendeling niet ondersteund. Voor browseraanmelding via WSL moet Chrome binnen WSL draaien. Je kunt ook een [HAR-bestand met tokens importeren](#aanmelden-met-een-har-bestand). [WSL installeren](https://learn.microsoft.com/en-us/windows/wsl/install)

## Optionele boekhoudskills

De bronbestanden staan in [`.agents/skills`](.agents/skills/). Codex kan ze vanuit de repo laden. De Codex-plugin en de installer gebruiken dezelfde bron.

| Skill | Gebruik |
| --- | --- |
| `snelstart-setup` | Clientregistratie, browseraanmelding en verbindingsproblemen. |
| `snelstart-administration` | Toegang tot administraties, archiefdekking en herstelopties. |
| `snelstart-sales` | Verkoopfacturen, klanten, artikelen, credits en verzending. |
| `snelstart-purchases` | Inkopen zoeken, bewijs controleren en pdf’s aanleveren voor herkenning. |
| `snelstart-bank` | Kas- en bankdagboeken, importdekking en boekingsdetails. |
| `snelstart-reconcile` | Facturen en betalingen afstemmen met bank- en betaalprovidergegevens. |
| `snelstart-tax` | Btw, ICP, belastingmonitor en aangiftecontroles. |
| `snelstart-year-end` | Grootboekexports, begin- en eindbalansen en jaarafsluiting. |

Het [dekkingsoverzicht van het Kennisplein](docs/knowledge-base-coverage.md) koppelt elk geïndexeerd artikel aan de MCP en de relevante skills.

Kies `codex` of `claude-code`. De optie `--with-skills` registreert de MCP en installeert de skills. Gebruik `--skills-only` als de MCP al geregistreerd is. Laat `--apply` weg om de voorgestelde bestanden te bekijken. Een bestaande skill met afwijkende inhoud blijft behouden.

```sh
snelstart-mcp install codex --with-skills --apply
snelstart-mcp install codex --skills-only --apply
```

Met het Bash-script kan het ook in één keer. Open daarna een nieuwe sessie in je client.

```sh
bash install-snelstart-mcp.sh --with-skills codex
```

## Optionele Codex-hooks

De hooks geven rond schrijfopdrachten een herinnering om de administratie, de toestemming en het resultaat te controleren. Bij een beschikbare update geven ze een melding nadat `snelstart_status` of `snelstart_check_update` die heeft gevonden. De schrijfrechten van het MCP-profiel blijven leidend.

```sh
snelstart-mcp install codex --hooks-only
snelstart-mcp install codex --hooks-only --apply
```

Gebruik `--with-hooks` als je de MCP tegelijk wilt registreren. Het Bash-script accepteert ook `--with-hooks`, eventueel samen met `--with-skills codex`. De installer voegt de definities toe aan `$CODEX_HOME/hooks.json` of standaard `~/.codex/hooks.json`, met behoud van bestaande hooks. Open daarna `/hooks` in de Codex CLI om de definities te bekijken en te vertrouwen. Daar kun je ze ook uitschakelen. [Codex-documentatie over hooks](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks)

## Aanmelden

De lokale instellingen staan standaard onder `~/.config/snelstart-mcp`. Wachtwoorden en OAuth-tokens staan in macOS Sleutelhanger of Linux Secret Service. Bij het eerste gebruik verplaatst de MCP bestaande geheimen uit JSON en verwijdert hij het oude bestand nadat de veilige opslag is gelukt. Ontgrendel de sleutelopslag vóór het aanmelden. Op Linux en WSL is een werkende Secret Service vereist. Kies met `SNELSTART_CONFIG_DIR` of `--config-dir PAD` een profielmap buiten Git-repositories.

```sh
snelstart-mcp login --method browser
snelstart-mcp doctor
```

Meld je aan in het aparte Chrome-venster. Het MCP-profiel bewaart de OAuth-tokens. Heb je al opgeslagen aanmeldgegevens, dan werkt ook `snelstart-mcp login --method credentials`.

### Aanmelden met een HAR-bestand

1. Meld je aan op de officiële SnelStart Web-pagina met de netwerkopname uit.
2. Open daarna **DevTools → Network**, wis de lijst en schakel **Preserve log** in. Open de gewenste administratie en wacht op een geslaagd antwoord van `/oauth/token` voor het vernieuwen van de sessie.
3. Exporteer het HAR-bestand buiten Git. Importeer het zonder `--save-password` en controleer het profiel.

```sh
snelstart-mcp import-har /pad/naar/opname.har
snelstart-mcp doctor
```

Ook een geschoonde HAR-export kan tokens in antwoordteksten bevatten. Bewaar het bestand privé en verwijder het als je klaar bent. De oudere opdrachten `setup` en `import-har --save-password` slaan een wachtwoord als platte tekst op in het lokale profiel. Kies bij een nieuw profiel bij voorkeur browser-OAuth.

## MCP-clients registreren

```sh
snelstart-mcp install all
snelstart-mcp install codex claude-code antigravity --apply
```

Naast Codex, Claude Code en Antigravity ondersteunt de installer Claude Desktop op macOS, Cursor, VS Code, Gemini CLI, OpenCode, Windsurf en Zed. Met `install stdio` krijg je een algemeen configuratiefragment. Gebruik `--client-config PAD --apply` om dat in een ander bestaand JSON-configuratiebestand te zetten. De installer bewaart bestaande instellingen en registraties. Voor JSON met commentaar kun je het voorbeeld in de editor van de client invoegen.

Voer `snelstart-mcp install codex --apply --with-skills --with-hooks` opnieuw uit als je overstapt van een lokale checkout naar een globale installatie. De installer werkt een bekende SnelStart-registratie en de bijbehorende standaardhooks bij. Het bestaande administratieprofiel en de overige Codex-instellingen blijven behouden. Met `--config-dir PAD` vóór `install` kies je expliciet een profiel.

Controleer na registratie met `snelstart_status` de actieve administratie en de draaiende MCP-versie. Zoek zo nodig de UUID op met `snelstart_list_administrations` en kies de juiste administratie met `snelstart_select_administration`. Toolnamen en argumenten zijn in het Engels. Je kunt je vraag in het Nederlands stellen. Gebruik datums in de vorm `YYYY-MM-DD`. De CLI toont leesbare uitvoer in Terminal en JSON bij omleiding. Met `--json` en `--text` kies je expliciet.

## Inkopen, verkopen en betalingen

| Tool | Gebruik |
| --- | --- |
| `snelstart_search_purchases` | Zoek inkopen binnen de periode. Gebruik `query` voor leverancier of tekst, of `invoice_number` voor een exact factuurnummer. Met `review_only: true` beperk je beide zoekmethoden tot gemarkeerde inkopen. |
| `snelstart_get_entry` | Lees een inkoop-, memoriaal-, beginbalans- of bankboeking op UUID. |
| `snelstart_purchase_payments` | Lees de vastgelegde betalingen en vereffeningen van een inkoop. |
| `snelstart_purchase_evidence` | Lees inkoopboekingen, betalingen en optionele bijlagegegevens voor maximaal 20 inkopen tegelijk. |
| `snelstart_list_attachments` | Zoek bijlage-ID's van inkoop-, bank- of memoriaalboekingen. |
| `snelstart_download_document` | Sla een bijlage of verkoopfactuur-pdf lokaal op en ontvang het pad en de SHA-256. |
| `snelstart_upload_purchase_pdf` | Bied één lokale pdf tot 25 MiB aan als nieuwe inkoop ter herkenning en controle. |
| `snelstart_purchase_upload_status` | Controleer de verwerking met het ontvangen `instance_id` en dezelfde administratie-UUID. |
| `snelstart_search_sales` | Zoek verkoopfacturen op klant, factuurnummer of status. |
| `snelstart_sales_booking_details` | Lees maximaal 20 geboekte verkopen via hun niet-nulwaarde in `verkoopboekingPublicIdentifier`. Voor concepten gebruik je de zoekrijen van `snelstart_search_sales`. |
| `snelstart_search_relations` | Zoek klanten of leveranciers op naam of nummer. |
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
| `snelstart_chart_of_accounts` | Lees het rekeningschema en de grootboek-UUID's. |
| `snelstart_balance_sheet` | Lees de balans, winst-en-verliesrekening en rubrieken tot en met `through_date`. |
| `snelstart_financial_result` | Lees het financiële resultaat voor de periode dat als invoer dient voor de Belastingmonitor. |
| `snelstart_ledger_entries` | Lees één pagina grootboekmutaties voor een rekening. |
| `snelstart_export_ledger_entries` | Controleer de paginering en exporteer mutaties voor maximaal 20 rekeningen naar een privé-JSONL-bestand. |
| `snelstart_vat_returns` | Lees de geregistreerde btw-aangiften en hun status. |
| `snelstart_vat_return_details` | Lees de details van maximaal 20 aangiften op publieke UUID. |
| `snelstart_supplemental_vat_years` | Lees de jaren die in SnelStart voor een btw-suppletie beschikbaar zijn. |
| `snelstart_year_end_review` | Lees openstaande inkoop-, verkoop- of andere boekingen en eindejaarsboekingen, indien beschikbaar. |

Voor een grootboekexport geef je `ledger_ids`, `start_date` en `through_date` mee. Bij een periode van meerdere dagen controleert de tool de boekjaargrenzen en leest hij elk geraakt boekjaar apart. Valt de einddatum na de laatste jaarafsluiting, dan controleert de tool het lopende boekjaar via de administratie-instellingen. Als de boekjaargrenzen de gevraagde periode niet aantoonbaar dekken, geeft de tool een foutmelding. De uitvoer geeft het bestandspad, de SHA-256 en aantallen per rekening. Elke regel bevat `ledger_id` en de oorspronkelijke `entry` binnen de periode. Behandel de export als privéboekhoudgegevens.

Gebruik bij btw-aangiften de publieke UUID's uit `snelstart_vat_returns` als `return_ids`. Voor ICP kun je `snelstart_read` met `GET /IcpAangiftes/GetIcpAangiftes` en de numerieke parameters `skip` en `top` gebruiken. De uiteindelijke belastingreservering bekijk je in de Belastingmonitor van SnelStart Web. [Belastingmonitor](https://kennisplein.snelstart.nl/migration/nl/snelstartweb/wat-is-de-belastingmonitor-in-snelstart)

## Schrijfrechten en audit

Schrijfrechten staan standaard uit. Open het keuzemenu in Terminal.

```sh
snelstart-mcp writes configure
```

Het menu begint bij de actieve administratie. Gebruik `--administration UUID` voor een andere administratie. Ga met de pijltjestoetsen naar een regel en gebruik **Spatie** om een groep, een losse handeling of alle handelingen voor deze administratie aan of uit te zetten. Met **Tab** open of sluit je de details van één groep. Op de regel voor alle handelingen toont Tab alle details tegelijk. `[-]` betekent dat een deel van de groep is geselecteerd. De groep **Purchase PDF upload** bevat de twee rechten voor een inkoop-pdf.

De globale schakelaar geldt voor alle administraties. Het menu bewaart de specifieke rechten van andere administraties. Druk op **Enter** om de wijzigingen te bekijken en bevestig daarna het opslaan. Met **Esc** annuleer je.

`writes list` toont de globale schakelaar en eventuele rechten per administratie. `writes list --available` toont de exacte toegestane operatienamen. De MCP respecteert ook de rechten van het SnelStart-account.

```sh
snelstart-mcp writes list
snelstart-mcp writes list --available
snelstart-mcp writes grant ADMINISTRATIE_UUID 'POST /MemoriaalBoekingen/Create'
snelstart-mcp writes revoke ADMINISTRATIE_UUID 'POST /MemoriaalBoekingen/Create'
snelstart-mcp writes off
```

Een toekenning geldt voor de gekozen handeling binnen die administratie totdat je deze intrekt. `writes on` schakelt de standaardhandelingen in. Voor bijvoorbeeld aangiften indienen, facturen verzenden of een boekjaar afsluiten heb je een expliciet recht voor die administratie nodig. Open in de editor een groep om die rechten afzonderlijk te kiezen. `writes off` schakelt globaal schrijven uit en wist de specifieke toekenningen.

**Bevestigen per schrijfopdracht** staat standaard aan. Met `snelstart-mcp writes confirmations off` zet je die extra stap uit voor de geselecteerde administratie. Met `snelstart-mcp writes confirmations on` zet je haar weer aan. Zonder `on` of `off` zie je de huidige instelling. De globale en specifieke schrijfrechten blijven gelden.

Als bevestigingen aanstaan, kan je chat de voorstellen met `snelstart_open_write_review` samen in een lokaal browservenster openen. Controleer de administratie en de volledige inhoud, vink de gewenste voorstellen aan en klik op **Approve selected requests**. Zeg daarna in de chat dat die verder mag. De chat controleert de statussen met `snelstart_write_approval_status` en herhaalt binnen twee minuten precies de goedgekeurde opdrachten.

Met `snelstart-mcp writes review` open je zelf het browservenster voor de geselecteerde administratie. Zonder browser gebruik je `snelstart-mcp writes approve APPROVAL_ID` in je eigen terminal met hetzelfde profiel. Controleer de inhoud en typ `APPROVE`. Bij een PDF zijn ook het pad en de controlesom onderdeel van de bevestiging. Deze controle beveiligt de MCP-tools. Onbeperkte terminal- en bestandstoegang onder je eigen account blijft vertrouwde toegang.

Het profiel bewaart per administratie een auditdatabase met aanroepen, tijdstippen, uitkomsten en duur. Aanroepen zonder gekozen administratie komen in een afzonderlijke profieldatabase. De log laat invoer, antwoordteksten, wachtwoorden en tokens weg. Bij een onzekere uitkomst controleer je het record en de auditgeschiedenis voordat je iets opnieuw probeert.

```sh
snelstart-mcp doctor
snelstart-mcp audit --limit 10
snelstart-mcp audit --administration ADMINISTRATIE_UUID --json
```

Vanuit de MCP geeft `snelstart_audit_log` de recente aanroepen voor de gekozen administratie. Een nieuw profielbestand neemt bij het openen van de betreffende database passende oude gebeurtenissen over uit een gezamenlijke `audit.sqlite3`.

## Boekingscontrole en afstemming

| Tool | Gebruik |
| --- | --- |
| `snelstart_get_entries` | Haal maximaal twintig inkoop-, bank-, memoriaal- en beginbalansboekingen in één keer op. Geef per item een `kind` en `entry_id` mee. De uitkomst toont per boeking of die gevonden, afwezig, mislukt of te groot was. |
| `snelstart_export_bank_entries` | Exporteer met `journal_ids`, `start_date` en `through_date` alle gecontroleerde pagina’s naar privé-JSONL. De uitvoer bevat aantallen per dagboek en een SHA-256-controlesom. Markeringen en factuurkoppelingen blijven in de bronregels behouden. Bij een mislukte pagina vervalt de hele export. |
| `snelstart_reconcile_bank` | Bekijk geregistreerde SnelStart-koppelingen en mogelijke factuurmatches. De tool kijkt naar bedrag, datum, omschrijving en tegenpartij. Hij meldt twijfelgevallen, mogelijke dubbelen en signalen over ontbrekende bijlagen. Controleer voorgestelde matches vóór je boekt. |
| `snelstart_compare_archives` | Vergelijk twee lokale jaararchieven met `before`, `after` en `purchases`, `sales`, `bank_entries` of `journal_and_opening_entries` als dataset. De administratie, het boekjaar, de peildatum en de dagboekdekking moeten overeenkomen. Lees de opgeslagen balans en winst-en-verliesrekening per archief via `snelstart_snapshot_read` in een offline sessie. |

Controleer bijlagen van een memoriaalboeking met `snelstart_list_attachments` en `kind: "journal"`, ook als het boekingsdetail `hasBijlagen: false` toont. Die vlag en `hasAttachments` uit het grootboek zijn aanwijzingen. Geef `include_attachments: true` mee aan `snelstart_get_entries` om de bijlagen van meerdere inkoop-, bank- en memoriaalboekingen op te vragen. Een lege lijst in `attachments` betekent dat de controle geen gekoppelde bestanden vond. Als de controle mislukt, blijven de boekingsdetails beschikbaar en rapporteert de tool `attachment_lookup_error` en `complete: false`. De batch voert voor beginbalansboekingen geen bijlagecontrole uit. De bijlagelijst kan grootte nul of een standaarddatum tonen. Gebruik `snelstart_download_document` voor het werkelijke aantal bytes en de SHA-256.

De MCP controleert bij inkoopzoekopdrachten het totaal en de rij-ID's. De resultaten worden op factuurdatum (nieuwste eerst) en rij-ID gesorteerd voordat `skip` en `take` worden toegepast. Herhaalt SnelStart een rij, dan probeert de MCP kortere periodes en controleert hij het gezamenlijke totaal en de ID's. Als de volledigheid niet te verifiëren is, geeft de tool een foutmelding. Per scan geldt een limiet van 5.000 rijen en 64 aanvragen aan SnelStart. Verklein de periode of gebruik een specifiekere zoekterm als de controle mislukt.

Geef `invoice_number` als tekst op en behoud eventuele voorloopnullen. Levert een `query` met alleen cijfers via SnelStart nul resultaten op, dan probeert de MCP ook een exacte zoekactie. Met `review_only: true` worden alleen rijen met `isTeControlerenInkoop: true` meegenomen. Beide filters worden vóór `skip` en `take` toegepast.

Gebruik bij inkopen `publicIdentifier` uit de zoekrij als `entry_id` en, als het aanwezig is, `factuurnummeridentifier` uit diezelfde rij als `purchase_invoice_id`. Dit werkt ook met `snelstart_get_entry`. Bij HTTP 400 op de gewone detailroute kan de MCP via het factuur-ID dezelfde boeking ophalen en beide ID's controleren. Als `purchase_detail_rejected` terugkomt, blijft de detailbatch onvolledig. De zoekrij kan nog als bewijs voor de lijstvelden dienen.

Geeft een bankdetail HTTP 500, geef dan `bank_list_context` mee aan `snelstart_get_entry` of aan de betreffende boeking in `snelstart_get_entries`. Neem `journal_id` en de lokale `booking_date` uit de banklijst of export. De MCP controleert de paginering voor die dag en zoekt exact op `identifier`. Een gevonden rij staat in `bank_list_evidence` met `failure_code: "bank_detail_unavailable"`. Het detailveld blijft leeg en de batch meldt `complete: false`. Als de banklijst niet te verifiëren is, meldt de tool dat.

`snelstart_mutation_receipts` en `snelstart-mcp audit` tonen de uitgevoerde schrijfoperatie, een beschikbaar boekings- of verwerkings-ID, controlesommen en de uitkomst. Een time-out blijft onopgelost. Met `snelstart_verify_mutation` kun je op basis van het `receipt_id` ondersteunde acties teruglezen, waaronder nieuw aangemaakte boekingen, geregistreerde verwijderingen en verwerkte inkoop-PDF’s. Andere acties controleer je aan de hand van de brongegevens. Een controle herhaalt de schrijfopdracht nooit.

## Jaararchieven en herstel

Gebruik `snelstart_create_year_archive` met `year` en `through_date`. Voeg zo nodig een officiële Web-export toe met `official_zip_path` of geef `auditfile_path`, `attachments_zip_path` en `bacpac_path` apart mee. Met `live_export: false` bundel je bestanden zonder de administratie uit te lezen.

De MCP attendeert je op lokale back-ups als je naar back-ups of de jaarafsluiting vraagt. `snelstart-mcp doctor` toont de lokale back-ups van het huidige profiel met de aanmaakdatum, de datum tot en met, de ZIP-grootte en of er een native BACPAC bij zit. Gebruik `doctor --json` of `snelstart_list_archives` voor de bestandsnamen, paden en exacte groottes in bytes. Doctor toont ook of Chrome beschikbaar is. Met `snelstart-mcp doctor --check-browser` test je of een leeg Chrome-venster kan worden geopend en gesloten. Beide controles worden ook getoond als de verbinding met SnelStart faalt.

Vraag Codex bijvoorbeeld om je laatste back-up te controleren. Codex gebruikt dan `snelstart_verify_archive` om te controleren of alle verwachte bestanden in de ZIP aanwezig zijn en hun inhoud overeenkomt met de opgeslagen controlesommen. `snelstart_extract_archive` pakt een gecontroleerd archief uit naar een nieuwe privémap. Voor herstel in SnelStart 12 heb je een native `.bacpac`-back-up nodig. Toets herstel door de back-up terug te zetten in de daarvoor bedoelde omgeving. [Web-export](https://kennispleinweb.snelstart.nl/nl/bestanden-en-bijlagen-downloaden-in-snelstart-web) · [SnelStart 12 back-ups](https://kennisplein.snelstart.nl/klanten/s/article/back-ups-maken-of-terugzetten)

## Kies hoe je gegevens gebruikt

| Optie | Wanneer gebruiken |
| --- | --- |
| Live alleen-lezen | Lees actuele SnelStart-gegevens met `serve --read-only`. Deze sessie blokkeert boekhoudmutaties en PDF-uploads, ook als je profiel schrijfrechten heeft. Je kunt nog wel op verzoek een archief maken. |
| Offline kopie | Lees één opgeslagen jaararchief met `serve --offline-archive BESTANDSNAAM`. De MCP start alleen lokale leestools en doet geen netwerkverzoeken. |
| Live met lokale rechten | Start de gewone server en kies de benodigde rechten met `snelstart-mcp writes configure`. Bij een nieuw profiel staan boekhoudmutaties standaard uit. |

Maak voor offline werken eerst in een live alleen-lezen sessie een jaararchief met `snelstart_create_year_archive` en `live_export: true`. Controleer het met `snelstart_verify_archive` en kies de ZIP-bestandsnaam uit het resultaat. Ook eerdere archieven met opgeslagen MCP-datasets kun je openen. Registreer de offline verbinding bijvoorbeeld zo in Codex.

```sh
codex mcp add snelstart-readonly -- "$(command -v snelstart-mcp)" serve --read-only
codex mcp add snelstart-offline -- "$(command -v snelstart-mcp)" serve --offline-archive 'ARCHIEFNAAM.zip'
```

Gebruik bij een apart profiel `--config-dir PAD` vóór `serve`. Schakel de live verbinding of de SnelStart-plugin uit en start een nieuw Codex-gesprek als je alleen offline met SnelStart wilt werken. `snelstart_snapshot_info` toont de peildatum, administratie en beschikbare datasets. `snelstart_snapshot_read` leest de opgeslagen gegevens per pagina. Bij bank- en memoriaalboekingen kies je eerst een dagboekgroep en lees je die uit met `group_index`.

De kopie bevat de geëxporteerde gegevens tot de peildatum. Maak een nieuwe export als je nieuwere gegevens nodig hebt. Voor herstel gebruik je de native SnelStart-back-up. De offline MCP doet zelf geen netwerkverzoeken. Gegevens die je met je AI-client deelt, kunnen wel door die client of zijn aanbieder worden verwerkt.

## Bijwerken en ontwikkelen

```sh
snelstart-mcp --version
snelstart-mcp update --check
snelstart-mcp update
```

Bijwerken via de CLI werkt voor installaties die door `uv tool` worden beheerd. Met een oudere versie kun je beginnen met `uv tool upgrade snelstart-web-mcp`. Verbind de client opnieuw na het bijwerken. `doctor` en `snelstart_status` tonen de versie en of er een update beschikbaar is. Als de sessie nog een andere versie gebruikt dan lokaal is geïnstalleerd, toont de MCP beide versies en de status `reconnect_required`. Verbind de client dan opnieuw om de geïnstalleerde tools te laden. Met `snelstart_check_update` controleer je dit direct. Versies gebruiken `YYYY.M.D.N`. Het laatste getal begint elke dag bij `1` en gaat bij elke uitgave omhoog, bijvoorbeeld van `2026.11.24.1` naar `2026.11.24.2`.

Werk je vanuit een broncheckout, dan gebruik je `uv sync --locked --extra browser` en `uv run --frozen snelstart-mcp doctor`. De Engelstalige handleiding bevat de [tests, pre-commit en uitgaveprocedure](README.md#code-and-tests).
