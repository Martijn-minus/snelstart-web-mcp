# Back-ups en gegevenstoegang

[Terug naar de snelstart](../README.nl.md) · [English](backups.md)

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

## Jaararchieven en herstel

Gebruik `snelstart_create_year_archive` met `year` en `through_date`. Voeg zo nodig een officiële Web-export toe met `official_zip_path` of geef `auditfile_path`, `attachments_zip_path` en `bacpac_path` apart mee. Met `live_export: false` bundel je bestanden zonder de administratie uit te lezen.

De MCP attendeert je op lokale back-ups als je naar back-ups of de jaarafsluiting vraagt. `snelstart-mcp doctor` toont de lokale back-ups van het huidige profiel met de aanmaakdatum, de datum tot en met, de ZIP-grootte en of er een native BACPAC bij zit. Gebruik `doctor --json` of `snelstart_list_archives` voor de bestandsnamen, paden en exacte groottes in bytes. Doctor toont ook of Chrome beschikbaar is. Met `snelstart-mcp doctor --check-browser` test je of een leeg Chrome-venster kan worden geopend en gesloten. Beide controles worden ook getoond als de verbinding met SnelStart faalt.

Vraag Codex bijvoorbeeld om je laatste back-up te controleren. Codex gebruikt dan `snelstart_verify_archive` om te controleren of alle verwachte bestanden in de ZIP aanwezig zijn en hun inhoud overeenkomt met de opgeslagen controlesommen. `snelstart_extract_archive` pakt een gecontroleerd archief uit naar een nieuwe privémap. Voor herstel in SnelStart 12 heb je een native `.bacpac`-back-up nodig. Toets herstel door de back-up terug te zetten in de daarvoor bedoelde omgeving. [Web-export](https://kennispleinweb.snelstart.nl/nl/bestanden-en-bijlagen-downloaden-in-snelstart-web) · [SnelStart 12 back-ups](https://kennisplein.snelstart.nl/klanten/s/article/back-ups-maken-of-terugzetten)
