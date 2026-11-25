# Installatie en configuratie

[Terug naar de snelstart](../README.nl.md) · [English](installation.md)

**Deze onafhankelijke MCP maakt verbinding met SnelStart Web (`web.snelstart.nl`).** Je meldt aan met je SnelStart Web-account. De MCP gebruikt de backend van die webapp op `webapi.snelstart.nl`. SnelStart biedt voor partnerkoppelingen een aparte B2B-API. SnelStart Polaris is een afzonderlijke applicatie. [Applicaties van SnelStart](https://kennisplein.snelstart.nl/snelstartpolaris/de-verschillende-applicaties-van-snelstart) · [SnelStart B2B-API](https://www.snelstart.nl/api)

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

Plak deze regel in Terminal. Je kunt ook [install.sh](../install.sh) downloaden en uitvoeren met `bash install.sh`.

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

## MCP-clients registreren

```sh
snelstart-mcp install all
snelstart-mcp install codex claude-code antigravity --apply
```

Naast Codex, Claude Code en Antigravity ondersteunt de installer Claude Desktop op macOS, Cursor, VS Code, Gemini CLI, OpenCode, Windsurf en Zed. Met `install stdio` krijg je een algemeen configuratiefragment. Gebruik `--client-config PAD --apply` om dat in een ander bestaand JSON-configuratiebestand te zetten. De installer bewaart bestaande instellingen en registraties. Voor JSON met commentaar kun je het voorbeeld in de editor van de client invoegen.

Voer `snelstart-mcp install codex --apply --with-skills --with-hooks` opnieuw uit als je overstapt van een lokale checkout naar een globale installatie. De installer werkt een bekende SnelStart-registratie en de bijbehorende standaardhooks bij. Het bestaande administratieprofiel en de overige Codex-instellingen blijven behouden. Met `--config-dir PAD` vóór `install` kies je expliciet een profiel.

Controleer na registratie met `snelstart_status` de actieve administratie en de draaiende MCP-versie. Zoek zo nodig de UUID op met `snelstart_list_administrations` en kies de juiste administratie met `snelstart_select_administration`. Toolnamen en argumenten zijn in het Engels. Je kunt je vraag in het Nederlands stellen. Gebruik datums in de vorm `YYYY-MM-DD`. De CLI toont leesbare uitvoer in Terminal en JSON bij omleiding. Met `--json` en `--text` kies je expliciet.

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

Ook een geschoonde HAR-export kan tokens in antwoordteksten bevatten. Bewaar het bestand privé en verwijder het als je klaar bent. De oudere opdrachten `setup` en `import-har --save-password` slaan het wachtwoord op in de sleutelopslag van het systeem. Kies bij een nieuw profiel bij voorkeur browser-OAuth.

## Optionele boekhoudskills

De bronbestanden staan in [`.agents/skills`](../.agents/skills/). Codex kan ze vanuit de repo laden. De Codex-plugin en de installer gebruiken dezelfde bron.

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

Het [dekkingsoverzicht](knowledge-base-coverage.md) koppelt relevante boekhoudprocessen uit SnelStart Web aan de MCP en de skills.

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

## Bijwerken en ontwikkelen

```sh
snelstart-mcp --version
snelstart-mcp update --check
snelstart-mcp update
```

Bijwerken via de CLI werkt voor installaties die door `uv tool` worden beheerd. Met een oudere versie kun je beginnen met `uv tool upgrade snelstart-web-mcp`. Verbind de client opnieuw na het bijwerken. `doctor` en `snelstart_status` tonen de versie en of er een update beschikbaar is. Als de sessie nog een andere versie gebruikt dan lokaal is geïnstalleerd, toont de MCP beide versies en de status `reconnect_required`. Verbind de client dan opnieuw om de geïnstalleerde tools te laden. Met `snelstart_check_update` controleer je dit direct. Versies gebruiken `YYYY.M.D.N`. Het laatste getal begint elke dag bij `1` en gaat bij elke uitgave omhoog, bijvoorbeeld van `2026.11.24.1` naar `2026.11.24.2`.

Werk je vanuit een broncheckout, dan gebruik je `uv sync --locked --extra browser` en `uv run --frozen snelstart-mcp doctor`. De Engelstalige ontwikkelaarshandleiding bevat de [tests, pre-commit en uitgaveprocedure](development.md#code-and-tests).
