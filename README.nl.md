# SnelStart Web MCP

[English](README.md) · **Nederlands**

Deze onafhankelijke MCP gebruikt SnelStart Web via `webapi.snelstart.nl`. De officiële B2B-API en Polaris zijn afzonderlijke producten van SnelStart.

## Installeren met een AI-assistent

Plak dit in Codex, Claude Code of een andere assistent met lokale terminaltoegang.

```text
Installeer SnelStart Web MCP vanaf https://github.com/Martijn-minus/snelstart-web-mcp.
Volg de README voor deze client. Laat mij zelf aanmelden in Chrome.
Voer snelstart-mcp doctor uit, meld welke administratie is geselecteerd
en laat mijn boekhouding en schrijfrechten intact.
```

## Installeren in Terminal

**Codex-plugin** (macOS of Linux, met de Codex CLI geïnstalleerd)

```sh
curl -fsSLo install-snelstart-mcp.sh https://raw.githubusercontent.com/Martijn-minus/snelstart-web-mcp/main/install.sh && bash install-snelstart-mcp.sh --codex-plugin
```

**Andere MCP-clients** (macOS, Linux of Windows met WSL)

```sh
curl -fsSLo install-snelstart-mcp.sh https://raw.githubusercontent.com/Martijn-minus/snelstart-web-mcp/main/install.sh && bash install-snelstart-mcp.sh
snelstart-mcp install claude-code --apply
```

Vervang `claude-code` door de [installatienaam van jouw client](docs/installation.nl.md#mcp-clients-registreren).

## Aanmelden en beginnen

1. Voer `snelstart-mcp login --method browser` uit en meld je aan in Google Chrome.
2. Voer `snelstart-mcp doctor` uit en controleer de actieve administratie.
3. Open een nieuw gesprek en vraag: ‘Welke SnelStart-administratie is gekoppeld?’
4. [Maak en controleer een back-up](docs/backups.nl.md#jaararchieven-en-herstel) voordat je aan de boekhouding begint. Je kunt ook live alleen-lezen werken of een opgeslagen boekjaar offline openen.

## Documentatie

- [Installatie, aanmelding, clients, skills, hooks en updates](docs/installation.nl.md)
- [MCP-tools en voorbeelden](docs/tools.nl.md)
- [Back-ups, alleen-lezen en offline toegang](docs/backups.nl.md)
- [Schrijfrechten, bevestigingen en auditlog](docs/writes-and-audit.nl.md)
- [Dekking van SnelStart Web](docs/knowledge-base-coverage.md)
- [Ontwikkelen en uitgaven](docs/development.md) · [Gebruik en aansprakelijkheid](NOTICE.md#gebruik-en-aansprakelijkheid) · [Nieuwste versie](https://github.com/Martijn-minus/snelstart-web-mcp/releases/latest)
