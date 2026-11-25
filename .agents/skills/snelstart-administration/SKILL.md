---
name: snelstart-administration
description: Verify access to the intended SnelStart administration, find and verify local bookkeeping archives, or plan a native backup, recovery or export.
---

# Check administration access and backup coverage

- Use `snelstart_list_administrations` to identify an administration and `snelstart_status` to confirm the one currently selected. A missing administration can reflect the account, an invitation or access in SnelStart itself. Check the official interface before assuming a local MCP configuration issue. Use that interface for user access, ownership transfer, adding or deleting an administration and subscription changes.
- For a requested export, choose the fiscal year and cutoff. Use `snelstart_create_year_archive` and `snelstart_verify_archive` for the MCP's local archive. Check the manifest for included datasets, attachments and any user-supplied native export. An archive can open offline and its files can be verified independently of the live administration.
- A native SnelStart recovery point, an official XAF or attachments export, and a restorable BACPAC have different uses. The MCP can package user-provided exports. For native creation or restoration, use the matching SnelStart interface and only report a tested restore after the restored administration has actually been checked. Do not start a restore just to verify archive integrity.
- For an audit, use the administration's local log and mutation receipts. A receipt records the attempted action and what was observed. Check unresolved outcomes against the source before repeating a write.

See [administration access](https://kennispleinweb.snelstart.nl/nl/administratiebeheer), [official file and attachment exports](https://kennispleinweb.snelstart.nl/nl/bestanden-en-bijlagen-downloaden-in-snelstart-web) and [creating a recovery point](https://kennispleinweb.snelstart.nl/nl/een-herstelpunt-van-een-administratie-maken-in-snelstart-web).
