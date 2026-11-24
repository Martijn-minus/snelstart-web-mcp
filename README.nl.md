# SnelStart Web MCP

[English](README.md) · **Nederlands**

Een lokale MCP-server voor SnelStart Web. De server gebruikt de Web API, vernieuwt de aanmelding en opent de geselecteerde administratie voordat hij boekhoudgegevens opvraagt. Dit is een onafhankelijke integratie. [Officiële API-koppelingen van SnelStart](https://www.snelstart.nl/api)

## Installeren met een AI-assistent

Kopieer deze opdracht naar Codex, Claude Code of een andere assistent die lokale terminalopdrachten kan uitvoeren.

```text
Installeer SnelStart Web MCP vanaf https://github.com/Martijn-minus/snelstart-web-mcp.
Download op macOS of Linux het bestand install.sh uit de repository en voer het uit.
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

- `snelstart-reconcile` helpt bij het aansluiten van facturen, bijlagen, betalingen en terugbetalingen op originele betaalbronnen.
- `snelstart-year-end` helpt bij grootboekexports, begin- en eindbalansen en btw-vergelijkingen.

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

De MCP bewaart de lokale instellingen en tokens onder `~/.config/snelstart-mcp`. Met `SNELSTART_CONFIG_DIR` of `--config-dir PAD` vóór de subopdracht kies je een ander profiel. Met een geldig vernieuwingstoken vernieuwt de server de toegang automatisch.

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
| `snelstart_search_purchases` | Zoek inkopen op periode en zoekterm. Met `review_only: true` zie je de inkopen die SnelStart ter controle heeft gemarkeerd. |
| `snelstart_get_entry` | Lees een inkoop-, memoriaal-, beginbalans- of bankboeking op UUID. |
| `snelstart_purchase_payments` | Lees de vastgelegde betalingen en vereffeningen van een inkoop. |
| `snelstart_purchase_evidence` | Lees inkoopboekingen, betalingen en optionele bijlagegegevens voor maximaal 20 inkopen tegelijk. |
| `snelstart_list_attachments` | Zoek bijlage-ID's van inkoop-, bank- of memoriaalboekingen. |
| `snelstart_download_document` | Sla een bijlage of verkoopfactuur-pdf lokaal op en ontvang het pad en de SHA-256. |
| `snelstart_upload_purchase_pdf` | Bied één lokale pdf tot 25 MiB aan als nieuwe inkoop ter herkenning en controle. |
| `snelstart_purchase_upload_status` | Controleer de verwerking met het ontvangen `instance_id` en dezelfde administratie-UUID. |
| `snelstart_search_sales` | Zoek verkoopfacturen op klant, factuurnummer of status. |
| `snelstart_sales_booking_details` | Lees maximaal 20 verkoopboekingen op boekings-UUID. |
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

Voor een grootboekexport geef je `ledger_ids`, `start_date` en `through_date` mee. De uitvoer geeft het bestandspad, de SHA-256 en aantallen per rekening. Elke regel bevat `ledger_id` en de oorspronkelijke `entry` binnen de periode. Behandel de export als privéboekhoudgegevens.

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

Een toekenning geldt voor de gekozen handeling binnen die administratie totdat je deze intrekt. `writes on` schakelt alle toegestane schrijfhandelingen van het profiel in. `writes off` schakelt globaal schrijven uit en wist de specifieke toekenningen. Voor algemene API-operaties vind je de route en parameters met `snelstart_list_operations`. Gebruik `snelstart_read` voor leesoperaties en `snelstart_write` voor toegestane schrijfoperaties.

Het profiel bewaart per administratie een auditdatabase met aanroepen, tijdstippen, uitkomsten en duur. Aanroepen zonder gekozen administratie komen in een afzonderlijke profieldatabase. De log laat invoer, antwoordteksten, wachtwoorden en tokens weg. Bij een onzekere uitkomst controleer je het record en de auditgeschiedenis voordat je iets opnieuw probeert.

```sh
snelstart-mcp doctor
snelstart-mcp audit --limit 10
snelstart-mcp audit --administration ADMINISTRATIE_UUID --json
```

Vanuit de MCP geeft `snelstart_audit_log` de recente aanroepen voor de gekozen administratie. Een nieuw profielbestand neemt bij het openen van de betreffende database passende oude gebeurtenissen over uit een gezamenlijke `audit.sqlite3`.

## Jaararchieven en herstel

Gebruik `snelstart_create_year_archive` met `year` en `through_date`. Voeg zo nodig een officiële Web-export toe met `official_zip_path` of geef `auditfile_path`, `attachments_zip_path` en `bacpac_path` apart mee. Met `live_export: false` bundel je bestanden zonder de administratie uit te lezen.

`snelstart_list_archives` toont lokale archieven. `snelstart_verify_archive` controleert het manifest en de bestanden. `snelstart_extract_archive` pakt een gecontroleerd archief uit naar een nieuwe privémap. Voor herstel in SnelStart 12 heb je een native `.bacpac`-back-up nodig. Een geslaagde archiefcontrole bevestigt de bestandsintegriteit. Toets herstel door de back-up terug te zetten in de daarvoor bedoelde omgeving. [Web-export](https://kennispleinweb.snelstart.nl/nl/bestanden-en-bijlagen-downloaden-in-snelstart-web) · [SnelStart 12 back-ups](https://kennisplein.snelstart.nl/klanten/s/article/back-ups-maken-of-terugzetten)

## Bijwerken en ontwikkelen

```sh
snelstart-mcp --version
snelstart-mcp update --check
snelstart-mcp update
```

Bijwerken via de CLI werkt voor installaties die door `uv tool` worden beheerd. Met een oudere versie kun je beginnen met `uv tool upgrade snelstart-web-mcp`. Verbind de client opnieuw na het bijwerken. `doctor` en `snelstart_status` tonen de versie en of er een update beschikbaar is. Met `snelstart_check_update` controleer je dit direct. Versies gebruiken `YYYY.M.D.N`. Het laatste getal begint elke dag bij `1` en gaat bij elke uitgave omhoog, bijvoorbeeld van `2026.11.24.1` naar `2026.11.24.2`.

Werk je vanuit een broncheckout, dan gebruik je `uv sync --locked --extra browser` en `uv run --frozen snelstart-mcp doctor`. De Engelstalige handleiding bevat de [tests, pre-commit en uitgaveprocedure](README.md#code-and-tests).
