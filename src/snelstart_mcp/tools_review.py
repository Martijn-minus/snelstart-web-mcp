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

from .archive_compare import compare_archives
from .client import Client
from .config import SnelStartError, Store
from .financial_review import booking_batch, export_bank_entries, reconcile_bank
from .models import JsonObject
from .models.responses import DataResponse
from .models.review import (
    ArchiveComparison,
    BankExportRequest,
    BankExportResponse,
    BookingBatchRequest,
    BookingBatchResponse,
    CompareArchivesRequest,
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
    LEDGER_ENTRIES,
    PURCHASE_ATTACHMENTS,
    PURCHASE_DETAILS,
    PURCHASE_PAYMENTS,
    attachment_metadata,
    ledger_query,
)
from .year_data import booking_date, entries_in_period, pages


def _selected_administration(client: Client) -> UUID:
    administration = client.store.settings().administration_id
    if administration is None:
        raise SnelStartError("Select an administration with snelstart_select_administration first.")
    return administration


def _ledger_export_periods(read, start: date, end: date) -> list[tuple[date, date]]:
    if start == end:
        return [(start, end)]

    fiscal_years = pages(
        read,
        "GET /Jaarafsluiting/GetAllJaarafsluiting",
        {"searchTerm": "", "sortDataFieldName": "jaar", "status": 0, "sortDescending": True},
        ("boekjaar",),
    )
    periods = []
    for row in fiscal_years:
        fiscal_year = row["boekjaar"]
        year_start = fiscal_year.get("startDate") if isinstance(fiscal_year, dict) else None
        year_end = fiscal_year.get("endDate") if isinstance(fiscal_year, dict) else None
        if not isinstance(year_start, str) or not isinstance(year_end, str):
            raise SnelStartError("SnelStart returned a fiscal year without both boundary dates.")
        try:
            first, last = booking_date(year_start), booking_date(year_end)
        except SnelStartError:
            raise SnelStartError("SnelStart returned an invalid fiscal-year date.") from None
        if first > last:
            raise SnelStartError("SnelStart returned reversed fiscal-year dates.")
        first, last = max(first, start), min(last, end)
        if first <= last:
            periods.append((first, last))

    periods.sort()
    if (
        not periods
        or periods[0][0] != start
        or periods[-1][1] != end
        or any(
            next_start - previous_end != timedelta(days=1)
            for (_, previous_end), (next_start, _) in pairwise(periods)
        )
    ):
        raise SnelStartError(
            f"SnelStart could not verify fiscal-year coverage for {start} through {end}."
        )
    return periods


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
                    rows = pages(
                        read,
                        LEDGER_ENTRIES,
                        ledger_query(ledger_id, end),
                        ("publicIdentifier",),
                        size_param="top",
                    )
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
        """Read up to 20 mixed booking IDs in the selected administration. Inspect per-record status and completeness."""
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
        """Export checked ledger pages across fiscal years for up to 20 accounts within an inclusive date range. Returns a private JSONL path, row counts and checksum."""
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
        """Read the details of up to 20 sales bookings by booking UUID, as shown when expanding a sales row."""
        read = partial(
            client.request, expected_administration=str(_selected_administration(client))
        )
        return DataResponse(
            data=[
                RecordDetails(
                    identifier=identifier,
                    details=read(
                        "GET /Invoices/GetVerkoopBoekingDetailsForExpandRow",
                        {"verkoopboekingIdentifier": str(identifier)},
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
