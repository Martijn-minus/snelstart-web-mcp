"""Read local payment-provider CSVs and summarize settlement amounts."""

import csv
import io
import os
import re
import stat
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from .config import SnelStartError
from .enums import PaymentProvider, PayoutMatchStatus
from .models.workflows import (
    PaymentReportBankRequest,
    PaymentReportBankResult,
    PaymentReportPayout,
    PaymentReportRequest,
    PaymentReportResult,
    PayoutBankCandidate,
    PayoutBankComparison,
)
from .year_data import BANK_JOURNALS, bank_entries_between, booking_date

MAX_REPORT_BYTES = 12 * 1024 * 1024
MAX_REPORT_ROWS = 100_000
FIELDS = {
    PaymentProvider.STRIPE: ("automatic_payout_id", "balance_transaction_id", "currency", "net"),
    PaymentProvider.MOLLIE: ("settlement reference", "settlement currency", "settlement amount"),
    PaymentProvider.ADYEN: (
        "merchant account",
        "batch number",
        "type",
        "net currency",
        "net debit (nc)",
        "net credit (nc)",
    ),
}


@dataclass
class Payout:
    net: Decimal = Decimal(0)
    declared: Decimal | None = None
    bank_reference: str | None = None
    rows: int = 0


def _read_csv(path: Path) -> bytes:
    if not path.is_absolute() or path.suffix.lower() != ".csv":
        raise SnelStartError("Provide an absolute path to a local CSV report.")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise SnelStartError("Provide a regular CSV file.")
        contents = stream.read(MAX_REPORT_BYTES + 1)
    if len(contents) > MAX_REPORT_BYTES:
        raise SnelStartError("The report exceeds 12 MiB. Export a shorter period.")
    return contents


def _money(value: str, *, blank_is_zero: bool = False) -> Decimal:
    if not value and blank_is_zero:
        return Decimal(0)
    if not re.fullmatch(r"[+-]?\d{1,12}(?:[.,]\d{1,8})?", value):
        raise ValueError("Invalid monetary amount.")
    try:
        return Decimal(value.replace(",", "."))
    except InvalidOperation:
        raise ValueError("Invalid monetary amount.") from None


def _rows(contents: bytes, request: PaymentReportRequest):
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise SnelStartError("Use a UTF-8 CSV report.") from None
    if not text.strip():
        raise SnelStartError("The payment report is empty.")
    fields = FIELDS[request.provider]
    requested = fields
    if request.mollie_columns is not None:
        mapping = request.mollie_columns
        requested = (
            mapping.settlement_reference.casefold(),
            mapping.settlement_currency.casefold(),
            mapping.settlement_amount.casefold(),
        )
    aliases = dict(zip(requested, fields, strict=True))
    for separator in (",", ";"):
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=separator, strict=True)
        try:
            header = [name.strip().casefold() for name in next(reader, [])]
        except csv.Error:
            continue
        canonical = [aliases.get(name, name) for name in header]
        if all(header.count(field) == 1 for field in requested) and all(
            canonical.count(field) == 1 for field in fields
        ):
            return reader, canonical
    raise SnelStartError(
        f"The {request.provider.value} report must include these columns: {', '.join(requested)}."
    )


def _key(row: dict[str, str], provider: PaymentProvider) -> tuple[str, str]:
    match provider:
        case PaymentProvider.STRIPE:
            reference, currency = row["automatic_payout_id"], row["currency"]
        case PaymentProvider.MOLLIE:
            reference, currency = row["settlement reference"], row["settlement currency"]
        case PaymentProvider.ADYEN:
            merchant, batch = row["merchant account"], row["batch number"]
            if not merchant or not batch.isdecimal():
                raise ValueError("Adyen merchant and batch are required.")
            reference, currency = f"{merchant}/{batch}", row["net currency"]
    if not reference or len(reference) > 256 or not re.fullmatch(r"[A-Za-z]{3}", currency):
        raise ValueError("Payout reference and currency are required.")
    return reference, currency.upper()


def _add(
    payout: Payout, row: dict[str, str], provider: PaymentProvider, stripe_ids: set[str]
) -> None:
    match provider:
        case PaymentProvider.STRIPE:
            identifier = row["balance_transaction_id"]
            if not identifier or identifier in stripe_ids:
                raise ValueError("Missing or duplicate Stripe balance transaction ID.")
            stripe_ids.add(identifier)
            payout.net += _money(row["net"])
        case PaymentProvider.MOLLIE:
            payout.net += _money(row["settlement amount"])
        case PaymentProvider.ADYEN:
            debit = _money(row["net debit (nc)"], blank_is_zero=True)
            credit = _money(row["net credit (nc)"], blank_is_zero=True)
            if not row["type"]:
                raise ValueError("Missing Adyen journal type.")
            if row["type"].casefold() == "merchantpayout":
                if payout.declared is not None:
                    raise ValueError("Multiple Adyen payout lines in the same merchant batch.")
                payout.declared = debit - credit
                reference = re.search(
                    r"\bTX[A-Z0-9]+XT\b", row.get("modification reference", ""), re.IGNORECASE
                )
                payout.bank_reference = reference.group() if reference else None
            else:
                payout.net += credit - debit
    payout.rows += 1


def read_payment_report(request: PaymentReportRequest) -> PaymentReportResult:
    contents = _read_csv(request.file_path)
    payouts: dict[tuple[str, str], Payout] = {}
    stripe_ids: set[str] = set()
    source_rows = 0
    try:
        reader, header = _rows(contents, request)
        for values in reader:
            if not any(value.strip() for value in values):
                continue
            source_rows += 1
            if source_rows > MAX_REPORT_ROWS:
                raise SnelStartError("The report has too many rows. Export a shorter period.")
            if len(values) != len(header):
                raise SnelStartError(f"The report has an invalid record at line {reader.line_num}.")
            row = dict(zip(header, (value.strip() for value in values), strict=True))
            try:
                key = _key(row, request.provider)
                _add(payouts.setdefault(key, Payout()), row, request.provider, stripe_ids)
            except ValueError as error:
                raise SnelStartError(f"Invalid report line {reader.line_num}. {error}") from None
    except csv.Error:
        raise SnelStartError("The payment report is not a valid CSV file.") from None
    end = request.skip + request.take
    return PaymentReportResult(
        provider=request.provider,
        sha256=sha256(contents).hexdigest(),
        source_rows=source_rows,
        payout_count=len(payouts),
        next_skip=end if end < len(payouts) else None,
        payouts=[
            PaymentReportPayout(
                reference=reference,
                bank_reference=payout.bank_reference
                or (reference if request.provider is not PaymentProvider.ADYEN else None),
                currency=currency,
                rows=payout.rows,
                calculated_net=payout.net,
                declared_payout=payout.declared,
                difference=payout.net - payout.declared if payout.declared is not None else None,
            )
            for (reference, currency), payout in sorted(payouts.items())[request.skip : end]
        ],
    )


def _compare(
    payout: PaymentReportPayout,
    currency: str,
    bank: dict[Decimal, list[tuple[PayoutBankCandidate, str]]],
) -> PayoutBankComparison:
    candidates: list[PayoutBankCandidate] = []
    if payout.currency != currency:
        status = PayoutMatchStatus.OTHER_CURRENCY
    else:
        amount = (
            payout.declared_payout if payout.declared_payout is not None else payout.calculated_net
        )
        rows = bank.get(amount, []) if amount > 0 else []
        reference = payout.bank_reference
        pattern = (
            re.compile(rf"(?<![A-Za-z0-9]){re.escape(reference)}(?![A-Za-z0-9])", re.IGNORECASE)
            if reference and len(reference) >= 4
            else None
        )
        matched = [candidate for candidate, label in rows if pattern and pattern.search(label)]
        candidates = matched or [candidate for candidate, _ in rows]
        if len(candidates) > 1:
            status = PayoutMatchStatus.AMBIGUOUS
        elif matched:
            status = PayoutMatchStatus.REFERENCE_AND_AMOUNT
        elif candidates:
            status = PayoutMatchStatus.AMOUNT_ONLY
        else:
            status = PayoutMatchStatus.NO_CANDIDATE
    return PayoutBankComparison(
        payout=payout, status=status, candidate_count=len(candidates), candidates=candidates[:5]
    )


def compare_payment_report(read, request: PaymentReportBankRequest) -> PaymentReportBankResult:
    report = read_payment_report(request)
    identifier = str(request.bank_journal_id)
    journals = read(BANK_JOURNALS)
    if not isinstance(journals, list) or not any(
        isinstance(row, dict) and str(row.get("grootboekIdentifier")).lower() == identifier
        for row in journals
    ):
        raise SnelStartError("The requested bank journal is unavailable in this administration.")
    fetched, rows = bank_entries_between(
        read, identifier, request.start_date, request.through_date, max_rows=5_000, max_pages=64
    )
    bank: dict[Decimal, list[tuple[PayoutBankCandidate, str]]] = defaultdict(list)
    for row in rows:
        try:
            amount = _money(str(row.get("amount")))
            if amount <= 0:
                continue
            candidate = PayoutBankCandidate(
                entry_id=UUID(str(row.get("identifier") or row.get("publicIdentifier"))),
                booking_date=booking_date(str(row.get("date"))),
            )
        except ValueError:
            raise SnelStartError("A bank entry has an invalid amount or identifier.") from None
        labels = [row.get("description"), row.get("paymentReference")]
        transaction = row.get("bankTransactie")
        if isinstance(transaction, dict):
            labels.extend(
                transaction.get(field)
                for field in ("description", "omschrijving", "paymentReference", "endToEndId")
            )
        label = " ".join(value for value in labels if isinstance(value, str))
        bank[amount].append((candidate, label))
    return PaymentReportBankResult(
        provider=report.provider,
        sha256=report.sha256,
        bank_journal_id=request.bank_journal_id,
        start_date=request.start_date,
        through_date=request.through_date,
        fetched_bank_rows=fetched,
        payout_count=report.payout_count,
        next_skip=report.next_skip,
        payouts=[_compare(payout, request.bank_currency, bank) for payout in report.payouts],
    )
