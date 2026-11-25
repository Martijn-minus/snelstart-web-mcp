# Schrijfrechten en audit

[Terug naar de snelstart](../README.nl.md) · [English](writes-and-audit.md)

## Schrijfrechten instellen

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

## Schrijfopdrachten bevestigen

**Bevestigen per schrijfopdracht** staat standaard aan. Met `snelstart-mcp writes confirmations off` zet je die extra stap uit voor de geselecteerde administratie. Met `snelstart-mcp writes confirmations on` zet je haar weer aan. Zonder `on` of `off` zie je de huidige instelling. De globale en specifieke schrijfrechten blijven gelden.

Als bevestigingen aanstaan, kan je chat de voorstellen met `snelstart_open_write_review` samen in een lokaal browservenster openen. Controleer de administratie en de volledige inhoud, vink de gewenste voorstellen aan en klik op **Approve selected requests**. Zeg daarna in de chat dat die verder mag. De chat controleert de statussen met `snelstart_write_approval_status` en herhaalt binnen twee minuten precies de goedgekeurde opdrachten.

Met `snelstart-mcp writes review` open je zelf het browservenster voor de geselecteerde administratie. Zonder browser gebruik je `snelstart-mcp writes approve APPROVAL_ID` in je eigen terminal met hetzelfde profiel. Controleer de inhoud en typ `APPROVE`. Bij een PDF zijn ook het pad en de controlesom onderdeel van de bevestiging. Deze controle beveiligt de MCP-tools. Onbeperkte terminal- en bestandstoegang onder je eigen account blijft vertrouwde toegang.

### De factuurdatum van een inkoop corrigeren

`POST /Purchases/UpdateInkoopboekingBasisGegevens` kan de btw en nettobedragen herberekenen, ook als je alleen de factuurdatum aanpast. Lees het veld `write_warning` in `snelstart_list_operations` voordat je de wijziging voorbereidt. Bij ingeschakelde bevestigingen zie je de waarschuwing ook in het lokale bevestigingsscherm.

Moet de boeking inhoudelijk gelijk blijven, lees dan eerst de bestaande inkoop en bewaar de boekingsregels en btw-regels. Gebruik `POST /Purchases/UpdateInkoopboekingVolledig` met die expliciete regels en de aangepaste datum. Lees de inkoop daarna terug en vergelijk de datum, netto- en brutobedragen, btw, betalingen en gekoppelde bijlagen.

## Auditlog

Het profiel bewaart per administratie een auditdatabase met aanroepen, tijdstippen, uitkomsten en duur. Aanroepen zonder gekozen administratie komen in een afzonderlijke profieldatabase. De log laat invoer, antwoordteksten, wachtwoorden en tokens weg. Bij een onzekere uitkomst controleer je het record en de auditgeschiedenis voordat je iets opnieuw probeert.

```sh
snelstart-mcp doctor
snelstart-mcp audit --limit 10
snelstart-mcp audit --administration ADMINISTRATIE_UUID --json
```

Vanuit de MCP geeft `snelstart_audit_log` de recente aanroepen voor de gekozen administratie. Een nieuw profielbestand neemt bij het openen van de betreffende database passende oude gebeurtenissen over uit een gezamenlijke `audit.sqlite3`.
