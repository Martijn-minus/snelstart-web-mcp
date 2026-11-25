# Backups and data access

[Back to the quick start](../README.md) · [Nederlands](backups.nl.md)

## Choose how to access the data

| Mode | When to use it |
| --- | --- |
| Live read-only | Read current SnelStart data with `serve --read-only`. This process blocks bookkeeping writes, including PDF uploads, even if the profile has grants. It can still open a SnelStart session and produce an archive on request. |
| Offline snapshot | Read a saved year with `serve --offline-archive FILENAME`. The process starts two local-only tools and makes no network requests. |
| Live with local permissions | Use the normal server and choose the required operations with `snelstart-mcp writes configure`. The default profile starts with bookkeeping writes disabled. |

To work offline, first use `snelstart_create_year_archive` in a live read-only session with `live_export: true`, and verify the result with `snelstart_verify_archive`. Choose the returned ZIP filename. Archives with saved MCP datasets can be read, including the supported earlier archive format. In Codex, you can register the offline connection like this.

```sh
codex mcp add snelstart-readonly -- "$(command -v snelstart-mcp)" serve --read-only
codex mcp add snelstart-offline -- "$(command -v snelstart-mcp)" serve --offline-archive 'ARCHIVE_FILENAME.zip'
```

For a separate profile, place `--config-dir PATH` before `serve`. To use only offline SnelStart access in Codex, disable the live connection or SnelStart plugin and start a fresh session. The offline server reports the archive date and dataset coverage through `snelstart_snapshot_info`. Use `snelstart_snapshot_read` to page saved data. For bank and journal records, first list the groups, then select one with `group_index`.

The snapshot contains the exported datasets as of the archive's cutoff date. Use a fresh export for newer data and native SnelStart backups for restoration. The MCP process makes no network requests in offline mode. Data you ask a connected AI client to analyze may still be processed by that client or its provider.

## Year archives

The MCP mentions local backups when you ask about backups or year-end work and can create and verify them on request. `snelstart-mcp doctor` lists the local backups for the current profile, with their creation time, through date, ZIP size and whether a native BACPAC is included. Use `doctor --json` or `snelstart_list_archives` for filenames, paths and exact sizes in bytes. To check that the ZIP contains the expected files and that their contents still match the original checksums, ask Codex to verify a backup. This uses the MCP tool `snelstart_verify_archive`.

Call `snelstart_create_year_archive` with `year` and `through_date`. Supply `official_zip_path` to include the original audit file and attachments downloaded from SnelStart Web. Separate source files can be supplied as `auditfile_path`, `attachments_zip_path` and `bacpac_path`. Set `live_export: false` to package files without reading the administration.

The MCP export records available balance, ledger, purchase, sales, bank, general journal and VAT datasets. It checks pagination and invoice date ranges, and the archive manifest records the scope and SHA-256 of each member. A local export is a point-in-time view assembled from multiple calls. The official XAF remains the source for the journal export.

Use the returned `archive` filename with `snelstart_verify_archive` or `snelstart_extract_archive`. Archives are stored under `~/.config/snelstart-mcp/backups`. The reader also supports earlier archive files. Local extraction does not change SnelStart. A native `.bacpac` backup is needed to restore an administration in SnelStart 12. See [official Web exports](https://kennispleinweb.snelstart.nl/nl/bestanden-en-bijlagen-downloaden-in-snelstart-web) and [native backup and recovery](https://kennisplein.snelstart.nl/klanten/s/article/back-ups-maken-of-terugzetten).

## Archive tools

| Tool | What it does |
| --- | --- |
| `snelstart_create_year_archive` | Creates a local, checksummed archive of a year's supported data and any supplied official files. |
| `snelstart_list_archives` | Lists local year archives with their creation date, through date and whether a native BACPAC is included. |
| `snelstart_verify_archive` | Validates the manifest, allowed archive members, sizes and SHA-256 checksums. |
| `snelstart_extract_archive` | Verifies and extracts an archive into a new private local folder. |
