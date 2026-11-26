"""Read-only evidence and exports for accounting reviews."""

import hashlib
import json
import os
import tempfile
from datetime import date, timedelta
from functools import partial
from itertools import pairwise
from pathlib import Path
from uuid import UUID

from mcp.types import ToolAnnotations
from pydantic import JsonValue

from .archive_compare import compare_archives
from .client import Client
from .config import SnelStartError, Store
from .financial_review import booking_batch, export_bank_entries, reconcile_bank
from .models import JsonObject
from .models.api import SALES_BOOKING_DETAILS, SALES_BOOKING_ID_PARAMETER
from .models.responses import DataResponse
from .models.review import (
    ArchiveComparison,
    BankExportRequest,
    BankExportResponse,
    BookingBatchRequest,
    BookingBatchResponse,
    CompareArchivesRequest,
    IcpReturnDetailsRequest,
    LedgerExportAccount,
    LedgerExportRequest,
    LedgerExportResponse,
    PurchaseEvidence,
    PurchaseEvidenceRequest,
    ReconciliationReport,
    ReconciliationRequest,
    RecordDetails,
    SalesBookingDetailsRequest,
    VatReturnDetailsRequest,
)
from .tooling import READ, Register
from .tools_bookkeeping import (
    ICP_RETURN_DETAILS,
    LEDGER_ENTRIES,
    PURCHASE_ATTACHMENTS,
    PURCHASE_DETAILS,
    PURCHASE_PAYMENTS,
    attachment_metadata,
    ledger_query,
)
from .year_data import DuplicatePageRow, MissingPageRow, booking_date, entries_in_period, pages

ONE_DAY = timedelta(days=1)


def _selected_administration(client: Client) -> UUID:
    administration = client.store.settings().administration_id
    if administration is None:
        raise SnelStartError("Select an administration with snelstart_select_administration first.")
    return administration


def _fiscal_year_bounds(record: JsonValue, start_field: str, end_field: str) -> tuple[date, date]:
    year_start = record.get(start_field) if isinstance(record, dict) else None
    year_end = record.get(end_field) if isinstance(record, dict) else None
    if not isinstance(year_start, str) or not isinstance(year_end, str):
        raise SnelStartError("SnelStart returned a fiscal year without both boundary dates.")
    try:
        first, last = booking_date(year_start), booking_date(year_end)
    except SnelStartError:
        raise SnelStartError("SnelStart returned an invalid fiscal-year date.") from None
    if first > last:
        raise SnelStartError("SnelStart returned reversed fiscal-year dates.")
    return first, last


def _unlisted_fiscal_year(
    settings: JsonValue, cutoff: date, last_listed_end: date | None
) -> tuple[date, date]:
    first, last = _fiscal_year_bounds(
        settings, "currentFinancialYearStartDate", "currentFinancialYearEndDate"
    )
    if first <= cutoff <= last and (last_listed_end is None or first > last_listed_end):
        return first, last

    if cutoff > last and first.day == 1:
        try:
            reference_end = first.replace(year=first.year + 1) - ONE_DAY
            year = cutoff.year - (cutoff.month < first.month)
            projected_start = date(year, first.month, 1)
            projected_end = projected_start.replace(year=year + 1) - ONE_DAY
        except ValueError:
            raise SnelStartError("The configured fiscal-year dates cannot be extended.") from None
        # Web uses the configured start month even if its reference year is old.
        if last == reference_end and (
            last_listed_end is None or projected_start - last_listed_end == ONE_DAY
        ):
            return projected_start, projected_end

    raise SnelStartError("The settings do not establish the requested fiscal-year dates.")


def _ledger_export_periods(read, start: date, end: date) -> list[tuple[date, date]]:
    if start == end:
        return [(start, end)]

    closing_rows = pages(
        read,
        "GET /Jaarafsluiting/GetAllJaarafsluiting",
        {"searchTerm": "", "sortDataFieldName": "jaar", "status": 0, "sortDescending": True},
        ("boekjaar",),
    )
    fiscal_years = [
        _fiscal_year_bounds(row["boekjaar"], "startDate", "endDate") for row in closing_rows
    ]
    last_listed_end = max((last for _, last in fiscal_years), default=None)
    if last_listed_end is None or end > last_listed_end:
        # The active fiscal year can be absent from the year-end closing list.
        error = f"SnelStart could not verify the fiscal year for {end} from the administration settings."
        try:
            fiscal_years.append(
                _unlisted_fiscal_year(read("GET /Settings/Get"), end, last_listed_end)
            )
        except SnelStartError as failure:
            raise SnelStartError(f"{error} {failure}") from None

    periods = sorted(
        (max(first, start), min(last, end))
        for first, last in fiscal_years
        if first <= end and start <= last
    )
    if (
        not periods
        or periods[0][0] != start
        or periods[-1][1] != end
        or any(
            next_start - previous_end != ONE_DAY
            for (_, previous_end), (next_start, _) in pairwise(periods)
        )
    ):
        raise SnelStartError(
            f"SnelStart could not verify fiscal-year coverage for {start} through {end}."
        )
    return periods


def _ledger_rows(read, ledger_id: UUID, start: date, end: date) -> list[JsonObject]:
    fetch = partial(
        pages,
        read,
        LEDGER_ENTRIES,
        ledger_query(ledger_id, end),
        ("publicIdentifier",),
        size_param="top",
    )
    try:
        return fetch()
    except (DuplicatePageRow, MissingPageRow):
        # Restart this account and fiscal period at page one with a fresh set of row IDs.
        pass
    try:
        return fetch()
    except SnelStartError as error:
        raise SnelStartError(
            f"Ledger account {ledger_id}, {start} through {end}, failed after one retry. {error}"
        ) from None


def export_ledger_entries(client: Client, request: LedgerExportRequest) -> LedgerExportResponse:
    administration = _selected_administration(client)
    read = partial(client.request, expected_administration=str(administration))
    # The ledger endpoint only returns the fiscal year containing dateTo.
    periods = _ledger_export_periods(read, request.start_date, request.through_date)
    directory = Store(client.store.directory / "exports").directory
    fd, filename = tempfile.mkstemp(prefix="ledger-", suffix=".jsonl", dir=directory)
    path = Path(filename)
    digest = hashlib.sha256()
    accounts = []
    try:
        with os.fdopen(fd, "wb") as stream:
            for ledger_id in request.ledger_ids:
                fetched_rows = exported_rows = 0
                for start, end in reversed(periods):
                    rows = _ledger_rows(read, ledger_id, start, end)
                    selected = entries_in_period(rows, start, end, "datum")
                    fetched_rows += len(rows)
                    exported_rows += len(selected)
                    for entry in selected:
                        line = json.dumps(
                            {"ledger_id": str(ledger_id), "entry": entry}, ensure_ascii=False
                        )
                        encoded = (line + "\n").encode("utf-8")
                        stream.write(encoded)
                        digest.update(encoded)
                accounts.append(
                    LedgerExportAccount(
                        ledger_id=ledger_id, fetched_rows=fetched_rows, exported_rows=exported_rows
                    )
                )
            stream.flush()
            os.fsync(stream.fileno())
        return LedgerExportResponse(
            administration_id=administration,
            start_date=request.start_date,
            through_date=request.through_date,
            path=path,
            sha256=digest.hexdigest(),
            total_exported_rows=sum(account.exported_rows for account in accounts),
            ledgers=accounts,
        )
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def register_review_tools(tool: Register, client: Client) -> None:
    @tool(annotations=READ)
    def snelstart_get_entries(request: BookingBatchRequest) -> BookingBatchResponse:
        """Read up to 20 mixed booking IDs in the selected administration. Bank list context can recover list evidence after HTTP 500. Set include_attachments to check linked files for purchases, bank transactions and journal entries even when a detail flag is false. Listed attachment sizes can differ from the downloaded byte counts. Use snelstart_download_document for bytes and SHA-256. Inspect per-record errors and completeness."""
        administration = _selected_administration(client)
        read = partial(client.request, expected_administration=str(administration))
        return booking_batch(read, administration, request)

    @tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
    )
    def snelstart_export_bank_entries(request: BankExportRequest) -> BankExportResponse:
        """Export all checked bank and cash pages in a range to private JSONL with per-journal coverage and a checksum."""
        administration = _selected_administration(client)
        read = partial(client.request, expected_administration=str(administration))
        return export_bank_entries(client.store, read, administration, request)

    @tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def snelstart_compare_archives(request: CompareArchivesRequest) -> ArchiveComparison:
        """Compare verified booking datasets from two local archives with matching administration and cutoff."""
        return compare_archives(client.store, request)

    @tool(annotations=READ)
    def snelstart_reconcile_bank(request: ReconciliationRequest) -> ReconciliationReport:
        """Review recorded invoice links and possible matches. Reports evidence, ambiguous items, duplicates and document flags."""
        administration = _selected_administration(client)
        read = partial(client.request, expected_administration=str(administration))
        return reconcile_bank(read, administration, request)

    @tool(annotations=READ)
    def snelstart_export_ledger_entries(request: LedgerExportRequest) -> LedgerExportResponse:
        """Export checked ledger pages across fiscal years for up to 20 accounts within an inclusive date range. Retries the affected account and period once after a missing or duplicate row ID. Returns a private JSONL path, row counts and checksum."""
        return export_ledger_entries(client, request)

    @tool(annotations=READ)
    def snelstart_purchase_evidence(
        request: PurchaseEvidenceRequest,
    ) -> DataResponse[list[PurchaseEvidence]]:
        """Read purchase records, recorded settlements and optional attachment metadata for up to 20 purchase UUIDs."""
        read = partial(
            client.request, expected_administration=str(_selected_administration(client))
        )
        records = []
        for purchase_id in request.purchase_ids:
            params: JsonObject = {"journaalpostIdentifier": str(purchase_id)}
            purchase = read(PURCHASE_DETAILS, params)
            payments = read(PURCHASE_PAYMENTS, params)
            attachments = (
                attachment_metadata(read(PURCHASE_ATTACHMENTS, params))
                if request.include_attachments
                else None
            )
            records.append(
                PurchaseEvidence(
                    purchase_id=purchase_id,
                    purchase=purchase,
                    payments=payments,
                    attachments=attachments,
                )
            )
        return DataResponse(data=records)

    @tool(annotations=READ)
    def snelstart_sales_booking_details(
        request: SalesBookingDetailsRequest,
    ) -> DataResponse[list[RecordDetails]]:
        """Read up to 20 posted sales by nonzero verkoopboekingPublicIdentifier. Read draft rows with snelstart_search_sales."""
        read = partial(
            client.request, expected_administration=str(_selected_administration(client))
        )
        return DataResponse(
            data=[
                RecordDetails(
                    identifier=identifier,
                    details=read(
                        SALES_BOOKING_DETAILS,
                        {SALES_BOOKING_ID_PARAMETER: str(identifier)},
                    ),
                )
                for identifier in request.booking_ids
            ]
        )

    @tool(annotations=READ)
    def snelstart_vat_return_details(
        request: VatReturnDetailsRequest,
    ) -> DataResponse[list[RecordDetails]]:
        """Read detailed amounts and status for up to 20 VAT returns identified by snelstart_vat_returns."""
        read = partial(
            client.request, expected_administration=str(_selected_administration(client))
        )
        return DataResponse(
            data=[
                RecordDetails(
                    identifier=identifier,
                    details=read(
                        "GET /BtwAangiftes/GetByPublicIdentifier",
                        {"publicIentifier": str(identifier)},
                    ),
                )
                for identifier in request.return_ids
            ]
        )

    @tool(annotations=READ)
    def snelstart_icp_return_details(
        request: IcpReturnDetailsRequest,
    ) -> DataResponse[list[RecordDetails]]:
        """Read up to 20 persisted ICP returns by publicIdentifier from snelstart_icp_returns."""
        read = partial(
            client.request, expected_administration=str(_selected_administration(client))
        )
        results = []
        for identifier in request.return_ids:
            details = read(ICP_RETURN_DETAILS, {"publicIdentifier": str(identifier)})
            actual = details.get("publicIdentifier") if isinstance(details, dict) else None
            if not isinstance(actual, str) or actual.lower() != str(identifier):
                raise SnelStartError("SnelStart did not return the requested ICP return ID.")
            results.append(RecordDetails(identifier=identifier, details=details))
        return DataResponse(data=results)
