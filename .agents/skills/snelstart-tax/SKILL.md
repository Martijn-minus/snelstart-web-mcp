---
name: snelstart-tax
description: Inspect SnelStart VAT and ICP records for a period, compare the tax monitor input or VAT evidence, or determine which filing and tax-setting steps require the official interface.
---

# Review tax records

- Confirm the administration, reporting period, and return type. List stored VAT returns with `snelstart_vat_returns` and use `snelstart_vat_return_details` for the selected UUIDs. For ICP, look up the catalog's read-enabled `GET /IcpAangiftes/GetIcpAangiftes` route. Use `snelstart_supplemental_vat_years` to find years the source offers, and keep that list separate from filed supplementary returns.
- Compare return amounts with the underlying ledger and purchase or sales documents. Keep draft figures, filed figures, acknowledgements, assessments, and actual payments distinct. For the tax monitor, `snelstart_financial_result` gives the financial result used as input. Use the official interface for its complete calculation and settings.
- Treat an empty `onderbouwingVanDoorschuiving` on a historical VAT return as unconfirmed carry-forward detail. Compare the saved filing specification or available native source before drawing a conclusion about earlier periods.
- Check current official tax guidance for the relevant country and reporting period before interpreting reverse charge, KOR, margin schemes, intra-EU supplies or OSS. Record the source, period and relevant treatment. Review the transaction evidence before suggesting a correction.
- Use the official filing workflow when the task requires submission or tax-setting changes. The MCP has no dedicated verified submission workflow. A catalog write being present or accepted cannot establish that an authority received or accepted the filing.

See the SnelStart guides for [VAT](https://kennispleinweb.snelstart.nl/nl/de-btw-aangifte-in-snelstart-web), [ICP](https://kennispleinweb.snelstart.nl/nl/de-icp-aangifte-in-snelstart-web) and the [tax monitor](https://kennispleinweb.snelstart.nl/nl/wat-is-de-belastingmonitor-in-snelstart).
