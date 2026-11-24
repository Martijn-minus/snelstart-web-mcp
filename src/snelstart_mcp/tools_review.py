"""Read-only evidence and exports for accounting reviews."""

import hashlib
import json
import os
import tempfile
from functools import partial
from pathlib import Path
from uuid import UUID

from .client import Client
from .config import SnelStartError, Store
from .models import JsonObject
from .models.responses import DataResponse
from .models.review import (
    LedgerExportAccount,
    LedgerExportRequest,
    LedgerExportResponse,
    PurchaseEvidence,
    PurchaseEvidenceRequest,
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
from .year_data import entries_in_period, pages


def _selected_administration(client: Client) -> UUID:
    administration = client.store.settings().administration_id
    if administration is None:
        raise SnelStartError("Select an administration with snelstart_select_administration first.")
    return administration


def export_ledger_entries(client: Client, request: LedgerExportRequest) -> LedgerExportResponse:
    administration = _selected_administration(client)
    read = partial(client.request, expected_administration=str(administration))
    directory = Store(client.store.directory / "exports").directory
    fd, filename = tempfile.mkstemp(prefix="ledger-", suffix=".jsonl", dir=directory)
    path = Path(filename)
    digest = hashlib.sha256()
    accounts = []
    try:
        with os.fdopen(fd, "wb") as stream:
            for ledger_id in request.ledger_ids:
                rows = pages(
                    read,
                    LEDGER_ENTRIES,
                    ledger_query(ledger_id, request.through_date),
                    ("publicIdentifier",),
                    size_param="top",
                )
                selected = entries_in_period(
                    rows, request.start_date, request.through_date, "datum"
                )
                for entry in selected:
                    line = json.dumps(
                        {"ledger_id": str(ledger_id), "entry": entry}, ensure_ascii=False
                    )
                    encoded = (line + "\n").encode("utf-8")
                    stream.write(encoded)
                    digest.update(encoded)
                accounts.append(
                    LedgerExportAccount(
                        ledger_id=ledger_id, fetched_rows=len(rows), exported_rows=len(selected)
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
    def snelstart_export_ledger_entries(request: LedgerExportRequest) -> LedgerExportResponse:
        """Export all checked pages for up to 20 ledger accounts, restricted to an inclusive date range. Returns a private JSONL path, row counts and checksum."""
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
