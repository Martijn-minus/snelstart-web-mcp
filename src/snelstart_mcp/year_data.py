"""Read-only collection of a year’s accounting datasets."""

from datetime import date, datetime, timedelta
from functools import partial

from pydantic import TypeAdapter, ValidationError

from .client import Client
from .config import SnelStartError
from .dates import AMSTERDAM, window
from .models import ApiPage
from .models.api import GeneralJournalReference, JournalReference

DATASETS = frozenset(
    {
        "balance_and_profit_loss",
        "chart_of_accounts",
        "purchases",
        "sales",
        "bank_journals",
        "bank_entries",
        "general_journals",
        "journal_and_opening_entries",
        "vat_returns_all_years",
    }
)


def pages(
    request,
    operation: str,
    params: dict,
    key_fields: tuple[str, ...],
    body=None,
    *,
    size_param="take",
):
    rows, keys = [], set()
    expected = None
    while len(rows) <= 100_000:
        query = {**params, "skip": len(rows), size_param: 100}
        result = request(operation, query, body)
        try:
            page = ApiPage.model_validate(result)
        except ValidationError:
            raise SnelStartError(f"Unexpected response while exporting {operation}.") from None
        chunk, total = page.resultList, page.totalMatchCount
        if expected is not None and expected != total:
            raise SnelStartError(f"The count changed while exporting {operation}.")
        if total > 100_000:
            raise SnelStartError(f"Too many rows for a local export of {operation}.")
        expected = total
        for row in chunk:
            key = next(
                ((k, str(row[k])) for k in key_fields if row.get(k) not in (None, "", 0)), None
            )
            if key is None or key in keys:
                raise SnelStartError(f"Missing or duplicate row ID while exporting {operation}.")
            keys.add(key)
            rows.append(row)
        if len(rows) == total:
            return rows
        if not chunk or len(rows) > total:
            break
    raise SnelStartError(f"Incomplete pagination while exporting {operation}.")


def entries_in_period(rows: list[dict], start: date, end: date, *date_fields: str) -> list[dict]:
    # SnelStart sends either a date, an offset timestamp or a naive local timestamp.
    result = []
    for row in rows:
        value = next((row[field] for field in date_fields if row.get(field)), None)
        if not isinstance(value, str):
            raise SnelStartError("SnelStart returned an entry without a readable date.")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise SnelStartError("SnelStart returned an entry with an invalid date.") from None
        local = parsed.astimezone(AMSTERDAM).date() if parsed.tzinfo else parsed.date()
        if start <= local <= end:
            result.append(row)
    return result


def collect(client: Client, year: int, end: date, administration: str) -> dict:
    start = date(year, 1, 1)
    # Ask for a margin in case an endpoint parses the bounds as dates rather than instants.
    first, last = window(start - timedelta(days=1), end + timedelta(days=1))
    request = partial(client.request, expected_administration=administration)
    banks = request("GET /KasBankBoeking/GetKasEnBankDagboeken")
    journals = request("GET /Grootboek/GetMemoriaalAndBeginBalansDagboekenWithSaldo")
    try:
        bank_references = TypeAdapter(list[JournalReference]).validate_python(banks)
        journal_references = TypeAdapter(list[GeneralJournalReference]).validate_python(journals)
    except ValidationError:
        raise SnelStartError("SnelStart returned invalid journal references.") from None
    sales = pages(
        request,
        "POST /Invoices/Search",
        {
            "statusFilter": 0,
            "sortDataFieldName": "invoiceDate",
            "sortDescending": True,
        },
        ("factuurNummerPublicIdentifier", "verkoopOrderId", "factuurNummerId"),
        {"rawSearchTerm": "", "globalSearchTerms": [], "columnSearchTerms": []},
    )
    purchases = pages(
        request,
        "GET /Purchases/SearchAllInkopen",
        {
            "searchTerm": "",
            "paymentStatus": 0,
            "onlyTeControlerenInkopen": False,
            "sortDataField": 0,
            "sortDescending": True,
            "startDate": first,
            "dateUntil": last,
        },
        ("publicIdentifier", "factuurnummeridentifier"),
    )
    bank_rows = []
    for bank in bank_references:
        key = str(bank.grootboekIdentifier)
        rows = pages(
            request,
            "GET /KasBankBoeking/GetKasBankBoekingenWithTimespan",
            {
                "grootboekIdentifier": key,
                "searchTerm": "",
                "statusFilter": 0,
                "vanaf": first,
                "totEnMet": last,
            },
            ("identifier", "publicIdentifier"),
        )
        bank_rows.append(
            {"journal_id": key, "entries": entries_in_period(rows, start, end, "date")}
        )
    journal_rows = []
    for journal in journal_references:
        key = str(journal.grootboekIdentifier)
        function = journal.grootboekFunctieId
        operation = {7: "GET /MemoriaalBoekingen/Search", 8: "GET /BalansBoekingen/Search"}.get(
            function
        )
        if operation is None:
            raise SnelStartError("SnelStart returned an unknown journal type.")
        params = {
            "grootboekIdentifier": key,
            "dateFrom": first,
            "dateUntil": last,
            "searchTerm": "",
            "sortDescending": True,
        }
        if function == 7:
            params["mustBeChecked"] = False
        rows = pages(request, operation, params, ("publicIdentifier",), size_param="top")
        journal_rows.append(
            {"journal_id": key, "entries": entries_in_period(rows, start, end, "datum")}
        )
    return {
        "balance_and_profit_loss": request(
            "GET /Grootboek/GetBalansResultaatAndRubrieken", {"datumTotEnMet": end.isoformat()}
        ),
        "chart_of_accounts": request("GET /Grootboek/GetAllMinimal"),
        "purchases": entries_in_period(purchases, start, end, "factuurdatum"),
        "sales": entries_in_period(sales, start, end, "invoiceDate", "date"),
        "bank_journals": banks,
        "bank_entries": bank_rows,
        "general_journals": journals,
        "journal_and_opening_entries": journal_rows,
        "vat_returns_all_years": request("GET /BtwAangiftes/GetAll"),
    }
