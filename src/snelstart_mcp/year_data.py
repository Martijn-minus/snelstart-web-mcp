"""Read-only collection of a year’s accounting datasets."""

from datetime import date, datetime, timedelta
from functools import partial

from pydantic import TypeAdapter, ValidationError

from .client import Client
from .config import SnelStartError
from .dates import AMSTERDAM, window
from .enums import ArchiveDataset
from .models import ApiPage, JsonObject
from .models.api import GeneralJournalReference, JournalReference

DATASETS = frozenset(item.value for item in ArchiveDataset)
BANK_JOURNALS = "GET /KasBankBoeking/GetKasEnBankDagboeken"
BANK_ENTRIES = "GET /KasBankBoeking/GetKasBankBoekingenWithTimespan"
PURCHASE_SEARCH = "GET /Purchases/SearchAllInkopen"
MAX_EXPORT_ROWS = 100_000


def pages(
    request,
    operation: str,
    params: dict,
    key_fields: tuple[str, ...],
    body=None,
    *,
    size_param="take",
    max_rows: int = MAX_EXPORT_ROWS,
    max_pages: int | None = None,
):
    rows, keys = [], set()
    expected = None
    page_count = 0
    while len(rows) <= max_rows:
        if max_pages is not None and page_count >= max_pages:
            raise SnelStartError(f"Too many pages for {operation}. Narrow the date range.")
        query = {**params, "skip": len(rows), size_param: 100}
        result = request(operation, query, body)
        page_count += 1
        try:
            page = ApiPage.model_validate(result)
        except ValidationError:
            raise SnelStartError(f"Unexpected response while exporting {operation}.") from None
        chunk, total = page.resultList, page.totalMatchCount
        if expected is not None and expected != total:
            raise SnelStartError(f"The count changed while exporting {operation}.")
        if total > max_rows:
            raise SnelStartError(
                f"Too many rows for a local export of {operation}. Narrow the date range."
            )
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
        if start <= booking_date(value) <= end:
            result.append(row)
    return result


def booking_date(value: str) -> date:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise SnelStartError("SnelStart returned an entry with an invalid date.") from None
    return parsed.astimezone(AMSTERDAM).date() if parsed.tzinfo else parsed.date()


def _server_window(start: date, end: date) -> tuple[str, str]:
    # Allow for endpoints that parse the bounds as calendar dates.
    return window(start - timedelta(days=1), end + timedelta(days=1))


def sales_between(request, start: date, end: date) -> list[JsonObject]:
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
    return entries_in_period(sales, start, end, "invoiceDate", "date")


def purchase_search_parameters(
    first: str, last: str, *, query: str = "", review_only: bool = False
) -> JsonObject:
    return {
        "searchTerm": query,
        "paymentStatus": 0,
        "onlyTeControlerenInkopen": review_only,
        "sortDataField": 0,
        "sortDescending": True,
        "startDate": first,
        "dateUntil": last,
    }


def purchases_between(
    request,
    start: date,
    end: date,
    *,
    review_only: bool = False,
    max_rows: int = MAX_EXPORT_ROWS,
    max_pages: int | None = None,
) -> list[JsonObject]:
    first, last = _server_window(start, end)
    purchases = pages(
        request,
        PURCHASE_SEARCH,
        purchase_search_parameters(first, last, review_only=review_only),
        ("publicIdentifier", "factuurnummeridentifier"),
        max_rows=max_rows,
        max_pages=max_pages,
    )
    return entries_in_period(purchases, start, end, "factuurdatum")


def bank_entries_between(
    request, journal_id: str, start: date, end: date
) -> tuple[int, list[JsonObject]]:
    first, last = _server_window(start, end)
    rows = pages(
        request,
        BANK_ENTRIES,
        {
            "grootboekIdentifier": journal_id,
            "searchTerm": "",
            "statusFilter": 0,
            "vanaf": first,
            "totEnMet": last,
        },
        ("identifier", "publicIdentifier"),
    )
    return len(rows), entries_in_period(rows, start, end, "date")


def collect(client: Client, year: int, end: date, administration: str) -> dict:
    start = date(year, 1, 1)
    first, last = _server_window(start, end)
    request = partial(client.request, expected_administration=administration)
    banks = request(BANK_JOURNALS)
    journals = request("GET /Grootboek/GetMemoriaalAndBeginBalansDagboekenWithSaldo")
    try:
        bank_references = TypeAdapter(list[JournalReference]).validate_python(banks)
        journal_references = TypeAdapter(list[GeneralJournalReference]).validate_python(journals)
    except ValidationError:
        raise SnelStartError("SnelStart returned invalid journal references.") from None
    sales = sales_between(request, start, end)
    purchases = purchases_between(request, start, end)
    bank_rows = []
    for bank in bank_references:
        key = str(bank.grootboekIdentifier)
        _, rows = bank_entries_between(request, key, start, end)
        bank_rows.append({"journal_id": key, "entries": rows})
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
        "purchases": purchases,
        "sales": sales,
        "bank_journals": banks,
        "bank_entries": bank_rows,
        "general_journals": journals,
        "journal_and_opening_entries": journal_rows,
        "vat_returns_all_years": request("GET /BtwAangiftes/GetAll"),
    }
