"""Bounded booking reads, bank exports and deterministic invoice matching."""

import hashlib
import json
import os
import re
import tempfile
from bisect import bisect_right
from collections import Counter, defaultdict
from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from itertools import chain
from pathlib import Path
from uuid import UUID

import httpx
from pydantic import JsonValue

from .config import SnelStartError, SnelStartHTTPError, Store
from .enums import (
    AttachmentKind,
    BookingLookupFailure,
    BookingLookupStatus,
    DocumentStatus,
    EntryKind,
    InvoiceKind,
    ReconciliationStatus,
)
from .models import JsonObject
from .models.review import (
    BankExportRequest,
    BankExportResponse,
    BankJournalCoverage,
    BankReconciliationEntry,
    BookingBatchRequest,
    BookingBatchResponse,
    BookingLookup,
    InvoiceEvidence,
    ReconciliationReport,
    ReconciliationRequest,
)
from .tools_bookkeeping import (
    BankDetailUnavailable,
    PurchaseDetailRejected,
    read_booking_attachments,
    read_booking_entry,
)
from .year_data import (
    BANK_JOURNALS,
    bank_entries_between,
    booking_date,
    purchases_between,
    sales_between,
)

MAX_BATCH_BYTES = 512 * 1024
MAX_BANK_EXPORT_BYTES = 512 * 1024**2
MAX_RECONCILIATION_ROWS = 20_000
MAX_COMPARABLE_INVOICES = 100
MAX_DISPLAYED_CANDIDATES = 10
WORDS = re.compile(r"[^\W_]+", re.UNICODE)


def booking_batch(read, administration: UUID, request: BookingBatchRequest) -> BookingBatchResponse:
    entries = []
    remaining = MAX_BATCH_BYTES
    for ref in request.entries:
        status = BookingLookupStatus.FOUND
        details = None
        reason = None
        failure_code = None
        bank_list_evidence = None
        attachments = None
        attachment_lookup_error = None
        try:
            lookup = read_booking_entry(read, ref)
            details = lookup.data
            if lookup.bank_list_evidence is not None:
                status, reason, failure_code = (
                    BookingLookupStatus.FAILED,
                    lookup.reason,
                    lookup.failure_code,
                )
                size = len(lookup.bank_list_evidence.model_dump_json().encode())
                if size <= remaining:
                    bank_list_evidence = lookup.bank_list_evidence
                    remaining -= size
                else:
                    reason = "Bank detail unavailable and list evidence exceeds the remaining batch size. Read the booking separately."
            elif details is None:
                status = BookingLookupStatus.MISSING
            else:
                size = len(json.dumps(details, ensure_ascii=False).encode())
                if size > remaining:
                    status = BookingLookupStatus.TOO_LARGE
                    details = None
                    reason = "Use the single-booking tool to read this record separately."
                else:
                    remaining -= size
        except PurchaseDetailRejected as error:
            status, reason = BookingLookupStatus.FAILED, str(error)
            failure_code = BookingLookupFailure.PURCHASE_DETAIL_REJECTED
        except BankDetailUnavailable as error:
            status, reason = BookingLookupStatus.FAILED, str(error)
            failure_code = BookingLookupFailure.BANK_DETAIL_UNAVAILABLE
        except SnelStartHTTPError as error:
            status = (
                BookingLookupStatus.MISSING
                if error.status_code in (404, 410)
                else BookingLookupStatus.FAILED
            )
            reason = f"SnelStart returned HTTP {error.status_code}."
        except SnelStartError as error:
            status, reason = BookingLookupStatus.FAILED, str(error)
        except httpx.HTTPError:
            status, reason = BookingLookupStatus.FAILED, "SnelStart is unavailable."
        if (
            request.include_attachments
            and status is BookingLookupStatus.FOUND
            and ref.kind is not EntryKind.OPENING_BALANCE
        ):
            try:
                linked = read_booking_attachments(read, AttachmentKind(ref.kind), ref.entry_id)
                size = len(json.dumps(linked, ensure_ascii=False).encode())
                if size > remaining:
                    attachment_lookup_error = (
                        "Use snelstart_list_attachments to read the files separately."
                    )
                else:
                    attachments = linked
                    remaining -= size
            except SnelStartHTTPError as error:
                attachment_lookup_error = f"SnelStart returned HTTP {error.status_code}."
            except SnelStartError as error:
                attachment_lookup_error = str(error)
            except httpx.HTTPError:
                attachment_lookup_error = "SnelStart is unavailable."
        entries.append(
            BookingLookup(
                kind=ref.kind,
                entry_id=ref.entry_id,
                purchase_invoice_id=ref.purchase_invoice_id,
                status=status,
                details=details,
                reason=reason,
                failure_code=failure_code,
                bank_list_evidence=bank_list_evidence,
                attachments=attachments,
                attachment_lookup_error=attachment_lookup_error,
            )
        )
    return BookingBatchResponse(
        administration_id=administration,
        complete=all(
            row.status in (BookingLookupStatus.FOUND, BookingLookupStatus.MISSING)
            and row.attachment_lookup_error is None
            for row in entries
        ),
        entries=entries,
    )


def _journals(
    read, request: BankExportRequest
) -> Iterator[tuple[BankJournalCoverage, JsonObject, list[JsonObject]]]:
    available = read(BANK_JOURNALS)
    if not isinstance(available, list) or any(not isinstance(item, dict) for item in available):
        raise SnelStartError("SnelStart returned invalid bank journal references.")
    journal_by_id = {}
    for journal in available:
        identifier = journal.get("grootboekIdentifier")
        if not isinstance(identifier, str) or identifier.lower() in journal_by_id:
            raise SnelStartError("A bank journal has a missing or duplicate ledger ID.")
        journal_by_id[identifier.lower()] = journal
    if any(str(identifier) not in journal_by_id for identifier in request.journal_ids):
        raise SnelStartError(
            "A requested cash or bank journal is unavailable in this administration."
        )
    for identifier in request.journal_ids:
        fetched, entries = bank_entries_between(
            read, str(identifier), request.start_date, request.through_date
        )
        yield (
            BankJournalCoverage(
                journal_id=identifier, fetched_rows=fetched, exported_rows=len(entries)
            ),
            journal_by_id[str(identifier)],
            entries,
        )


def export_bank_entries(
    store: Store, read, administration: UUID, request: BankExportRequest
) -> BankExportResponse:
    directory = Store(store.directory / "exports").directory
    fd, filename = tempfile.mkstemp(prefix=".pending-bank-", suffix=".jsonl", dir=directory)
    staged = Path(filename)
    path = staged.with_name(staged.name.removeprefix(".pending-"))
    digest = hashlib.sha256()
    journals = []
    total_bytes = 0
    try:
        with os.fdopen(fd, "wb") as stream:
            for coverage, journal, rows in _journals(read, request):
                identifier = str(coverage.journal_id)
                records = chain(
                    ({"journal_id": identifier, "journal": journal},),
                    ({"journal_id": identifier, "entry": entry} for entry in rows),
                )
                for row in records:
                    line = (json.dumps(row, ensure_ascii=False) + "\n").encode()
                    total_bytes += len(line)
                    if total_bytes > MAX_BANK_EXPORT_BYTES:
                        raise SnelStartError(
                            "The bank export is too large. Choose fewer journals or a shorter period."
                        )
                    stream.write(line)
                    digest.update(line)
                journals.append(coverage)
            stream.flush()
            os.fsync(stream.fileno())
        report = BankExportResponse(
            administration_id=administration,
            start_date=request.start_date,
            through_date=request.through_date,
            path=path,
            sha256=digest.hexdigest(),
            total_exported_rows=sum(item.exported_rows for item in journals),
            journals=journals,
        )
        os.link(staged, path)
        return report
    finally:
        staged.unlink(missing_ok=True)


def _text(value: JsonValue) -> str | None:
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        return str(value).strip()[:600] or None
    return None


def _first(row: JsonObject, *keys: str) -> str | None:
    return next((value for key in keys if (value := _text(row.get(key))) is not None), None)


def _cents(value: JsonValue) -> int | None:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or abs(amount) > Decimal(1000000000000):
            return None
        cents = amount * 100
        return int(cents) if cents == cents.to_integral_value() else None
    except (InvalidOperation, ValueError):
        return None


def _amount(cents: int | None) -> str | None:
    return f"{Decimal(cents).scaleb(-2):.2f}" if cents is not None else None


def _date(row: JsonObject, *fields: str) -> date:
    value = _first(row, *fields)
    if value is None:
        raise SnelStartError("SnelStart returned a record without a readable date.")
    return booking_date(value)


def _words(value: str | None) -> str:
    return " ".join(WORDS.findall((value or "").casefold()))


def _contains(text: str, value: str | None) -> bool:
    phrase = _words(value)
    return len(phrase.replace(" ", "")) >= 4 and f" {phrase} " in f" {text} "


def _invoice(
    row: JsonObject, *, purchase: bool
) -> tuple[int, date, InvoiceEvidence, set[str]] | None:
    if purchase:
        keys = ("publicIdentifier", "factuurnummeridentifier", "factuurId")
        amount = _cents(row.get("factuurbedrag"))
        number = _first(row, "factuurnummer")
        party = _first(row, "leverancierNaam")
        attachments = row.get("hasBijlagen")
        day = _date(row, "factuurdatum")
    else:
        if row.get("isConcept") is True:
            return None
        keys = (
            "factuurNummerPublicIdentifier",
            "verkoopboekingPublicIdentifier",
            "verkoopOrderId",
            "factuurNummerId",
        )
        amount = _cents(row.get("invoiceTotal", row.get("total")))
        number = _first(row, "invoiceNumber", "number")
        party = _first(row, "customerName")
        attachments = row.get("hasBijlage")
        day = _date(row, "invoiceDate", "date")
    identifiers = [value for key in keys if (value := _text(row.get(key))) is not None]
    if not identifiers or amount is None or amount <= 0:
        return None
    documents = (
        DocumentStatus.PRESENT
        if attachments is True
        else DocumentStatus.MISSING
        if attachments is False
        else DocumentStatus.UNKNOWN
    )
    return (
        -amount if purchase else amount,
        day,
        InvoiceEvidence(
            identifier=identifiers[0],
            invoice_number=number,
            kind=InvoiceKind.PURCHASE if purchase else InvoiceKind.SALE,
            invoice_date=day,
            counterparty=party,
            amount=_amount(amount),
            documents=documents,
        ),
        set(identifiers),
    )


def _recorded_links(row: JsonObject) -> list[tuple[str, InvoiceKind | None]]:
    links = row.get("invoiceKoppelingen")
    result = []
    if isinstance(links, list):
        for item in links:
            if isinstance(item, dict) and (identifier := _first(item, "invoiceIdentifier")):
                kind = (
                    InvoiceKind.PURCHASE
                    if item.get("isPurchase") is True
                    else InvoiceKind.SALE
                    if item.get("isPurchase") is False
                    else None
                )
                result.append((identifier, kind))
    purchase = _first(row, "inkoopBoekingIdentifier")
    if purchase is not None and (purchase, InvoiceKind.PURCHASE) not in result:
        result.append((purchase, InvoiceKind.PURCHASE))
    return result


def _evaluate_bank_entry(
    journal: UUID,
    row: JsonObject,
    duplicates: Counter,
    index: dict[int, list[tuple[date, InvoiceEvidence]]],
    dates: dict[int, list[date]],
    indexed_ids: dict[tuple[InvoiceKind, str], InvoiceEvidence],
) -> BankReconciliationEntry:
    day, cents = _date(row, "date"), _cents(row.get("amount"))
    description = _words(_first(row, "description"))
    transaction = row.get("bankTransactie")
    bank_reference = (
        _first(transaction, "description", "omschrijving", "paymentReference", "endToEndId")
        if isinstance(transaction, dict)
        else None
    )
    bank_name = (
        _first(transaction, "counterpartyName", "tegenrekeningNaam", "naamTegenrekening", "name")
        if isinstance(transaction, dict)
        else None
    )
    reference_text = " ".join((description, _words(bank_reference)))
    party_text = " ".join((description, _words(bank_name)))
    links = _recorded_links(row)
    candidates: list[InvoiceEvidence] = []
    candidate_count = 0
    if links:
        status = ReconciliationStatus.LINKED
        linked = {}
        for identifier, kind in links:
            for candidate_kind in (kind,) if kind else InvoiceKind:
                match = indexed_ids.get((candidate_kind, identifier))
                if match is not None:
                    linked[(match.kind, match.identifier)] = match
        candidates = list(linked.values())[:MAX_DISPLAYED_CANDIDATES]
        candidate_count = len(linked)
    elif not cents:
        status = ReconciliationStatus.INSUFFICIENT
    else:
        candidate_count = bisect_right(dates.get(cents, []), day)
        first = max(0, candidate_count - MAX_COMPARABLE_INVOICES)
        matches = []
        for _, invoice in index.get(cents, [])[first:candidate_count]:
            matches.append(
                invoice.model_copy(
                    update={
                        "reference_matches": _contains(reference_text, invoice.invoice_number),
                        "counterparty_matches": _contains(party_text, invoice.counterparty),
                    }
                )
            )
        matches.sort(
            key=lambda item: (
                item.reference_matches,
                item.counterparty_matches,
                item.invoice_date or date.min,
            ),
            reverse=True,
        )
        strong = sum(item.reference_matches or item.counterparty_matches for item in matches)
        status = (
            ReconciliationStatus.UNMATCHED
            if candidate_count == 0
            else ReconciliationStatus.SUGGESTED
            if strong == 1 and first == 0
            else ReconciliationStatus.AMBIGUOUS
        )
        candidates = matches[:MAX_DISPLAYED_CANDIDATES]
    identifier = _first(row, "identifier", "publicIdentifier")
    if identifier is None:
        raise SnelStartError("SnelStart returned a bank entry without an identifier.")
    return BankReconciliationEntry(
        journal_id=journal,
        identifier=identifier,
        date=day,
        amount=_amount(cents),
        status=status,
        possible_duplicate=bool(description and duplicates[(journal, day, cents, description)] > 1),
        recorded_link_ids=list(dict.fromkeys(identifier for identifier, _ in links)),
        candidates=candidates,
        candidate_count=candidate_count,
    )


def reconcile_bank(
    read, administration: UUID, request: ReconciliationRequest
) -> ReconciliationReport:
    invoice_start = request.invoice_start_date or max(
        date(1900, 1, 1), request.start_date - timedelta(days=90)
    )
    bank = []
    coverage = []
    for counts, _, rows in _journals(read, request):
        if len(bank) + len(rows) > MAX_RECONCILIATION_ROWS:
            raise SnelStartError(
                "This reconciliation is too large. Choose a shorter period or fewer journals."
            )
        coverage.append(counts)
        bank.extend((counts.journal_id, row) for row in rows)

    sales = sales_between(read, invoice_start, request.through_date)
    purchases = purchases_between(read, invoice_start, request.through_date)
    invoice_count = len(sales) + len(purchases)
    if invoice_count > MAX_RECONCILIATION_ROWS:
        raise SnelStartError("The invoice range is too large. Choose a later invoice start date.")
    index = defaultdict(list)
    indexed_ids = {}
    skipped = 0
    for purchase, rows in ((False, sales), (True, purchases)):
        for row in rows:
            parsed = _invoice(row, purchase=purchase)
            if parsed is None:
                skipped += 1
                continue
            cents, day, evidence, identifiers = parsed
            index[cents].append((day, evidence))
            for identifier in identifiers:
                indexed_ids[(evidence.kind, identifier)] = evidence
    for bucket in index.values():
        bucket.sort(key=lambda item: item[0])
    dates = {amount: [day for day, _ in bucket] for amount, bucket in index.items()}
    duplicates = Counter(
        (journal, _date(row, "date"), _cents(row.get("amount")), _words(_first(row, "description")))
        for journal, row in bank
    )
    entries = [
        _evaluate_bank_entry(journal, row, duplicates, index, dates, indexed_ids)
        for journal, row in bank
    ]
    suggestions = Counter(
        (item.candidates[0].kind, item.candidates[0].identifier)
        for item in entries
        if item.status is ReconciliationStatus.SUGGESTED
    )
    for item in entries:
        if item.status is ReconciliationStatus.SUGGESTED:
            key = item.candidates[0].kind, item.candidates[0].identifier
            item.competing_bank_entries = suggestions[key] > 1
            if item.competing_bank_entries or item.possible_duplicate:
                item.status = ReconciliationStatus.AMBIGUOUS
    entries.sort(key=lambda item: (item.date, str(item.journal_id), item.identifier))
    page = entries[request.skip : request.skip + request.take]
    next_skip = request.skip + len(page)
    return ReconciliationReport(
        administration_id=administration,
        start_date=request.start_date,
        through_date=request.through_date,
        invoice_start_date=invoice_start,
        invoices_examined=invoice_count,
        invoices_skipped=skipped,
        journals=coverage,
        counts=dict(Counter(item.status for item in entries)),
        next_skip=next_skip if next_skip < len(entries) else None,
        entries=page,
    )
