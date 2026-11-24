"""Append-only MCP call events, stored separately for each administration."""

import os
import sqlite3
from collections.abc import Callable
from contextlib import ExitStack, closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from .config import SnelStartError, Store
from .enums import AuditOutcome, MutationStatus
from .models.audit import (
    AuditCallResponse,
    AuditCallStart,
    AuditReport,
    AuditSummary,
    MutationReceipt,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY,
    id TEXT NOT NULL,
    at TEXT NOT NULL,
    tool TEXT NOT NULL,
    administration TEXT,
    phase TEXT NOT NULL CHECK (phase IN ('start', 'ok', 'error', 'interrupted')),
    elapsed_ms INTEGER
);
CREATE INDEX IF NOT EXISTS events_by_call ON events(id);
CREATE INDEX IF NOT EXISTS starts_by_time ON events(at, seq) WHERE phase = 'start';
CREATE TABLE IF NOT EXISTS legacy_import (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_seq INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS mutation_receipts (
    receipt_id TEXT PRIMARY KEY,
    administration_id TEXT NOT NULL,
    tool TEXT NOT NULL,
    operation TEXT NOT NULL,
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL,
    request_sha256 TEXT NOT NULL,
    response_sha256 TEXT,
    record_id TEXT,
    record_id_from_response INTEGER NOT NULL DEFAULT 0,
    verification TEXT
);
CREATE INDEX IF NOT EXISTS mutations_by_time ON mutation_receipts(started_at);
"""

INSERT_EVENT = """
INSERT INTO events(id, at, tool, administration, phase, elapsed_ms)
VALUES (?, ?, ?, ?, ?, ?)
"""

CALLS = """
SELECT s.id AS call_id, s.at AS started_at, s.tool,
       s.administration AS administration_id,
       e.administration AS administration_id_after,
       COALESCE(e.phase, 'pending') AS outcome, e.elapsed_ms
FROM events s LEFT JOIN events e ON e.id = s.id AND e.phase != 'start'
WHERE s.phase = 'start'
"""


def _connect(path: Path) -> sqlite3.Connection:
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
    finally:
        os.close(fd)
    db = sqlite3.connect(path, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA synchronous=FULL")
        db.executescript(SCHEMA)
    except sqlite3.Error:
        db.close()
        raise
    return db


def _copy_legacy(
    db: sqlite3.Connection, source: sqlite3.Connection, administration: str | None
) -> None:
    # Serialize imports into this destination and read a consistent legacy snapshot.
    with db, source:
        db.execute("BEGIN IMMEDIATE")
        source.execute("BEGIN")
        previous = db.execute("SELECT last_seq FROM legacy_import WHERE id = 1").fetchone()
        last_seq = previous[0] if previous else 0
        high_water = source.execute("SELECT COALESCE(MAX(seq), 0) FROM events").fetchone()[0]
        if high_water <= last_seq:
            return
        events = source.execute(
            "SELECT e.id, e.at, e.tool, e.administration, e.phase, e.elapsed_ms "
            "FROM events e JOIN events s ON s.id = e.id AND s.phase = 'start' "
            "WHERE e.seq > ? AND s.administration IS ? ORDER BY e.seq",
            (last_seq, administration),
        )
        db.executemany(INSERT_EVENT, events)
        db.execute(
            "INSERT INTO legacy_import(id, last_seq) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET last_seq = excluded.last_seq",
            (high_water,),
        )


def _recent(db: sqlite3.Connection, limit: int) -> list[AuditCallResponse]:
    rows = db.execute(CALLS + " ORDER BY s.at DESC, s.seq DESC LIMIT ?", (limit,))
    return [AuditCallResponse.model_validate(dict(row)) for row in rows]


def _check_limit(limit: int) -> None:
    if not 1 <= limit <= 100:
        raise SnelStartError("The limit must be between 1 and 100.")


class AuditLog:
    def __init__(self, store: Store, *, scope: Callable[[], UUID | None] | None = None):
        self.store = store
        self.scope = scope
        self.directory = store.directory / "audit"
        self.legacy_path = store.directory / "audit.sqlite3"

    def path(self, administration_id: UUID | None) -> Path:
        return self.directory / f"{administration_id or 'profile'}.sqlite3"

    def _selected(self) -> UUID | None:
        if self.scope is not None:
            return self.scope()
        try:
            return self.store.settings().administration_id
        except SnelStartError:
            return None

    @contextmanager
    def _database(self, administration_id: UUID | None, *, create: bool = False):
        path = self.path(administration_id)
        if self.directory.is_symlink() or self.legacy_path.is_symlink():
            raise OSError("Audit storage cannot use symbolic links.")
        administration = str(administration_id) if administration_id else None
        with ExitStack() as stack:
            legacy = None
            if self.legacy_path.exists():
                legacy = stack.enter_context(
                    closing(
                        sqlite3.connect(self.legacy_path.absolute().as_uri() + "?mode=ro", uri=True)
                    )
                )
            if (
                not create
                and not path.exists()
                and not path.is_symlink()
                and (
                    legacy is None
                    or not legacy.execute(
                        "SELECT 1 FROM events WHERE phase = 'start' AND administration IS ? LIMIT 1",
                        (administration,),
                    ).fetchone()
                )
            ):
                yield None
                return
            Store(self.directory)
            db = stack.enter_context(closing(_connect(path)))
            if legacy is not None:
                _copy_legacy(db, legacy, administration)
            yield db

    def _event(self, call: AuditCallStart, tool: str, phase: AuditOutcome, elapsed_ms: int | None):
        selected = call.administration_id if phase is AuditOutcome.START else self._selected()
        try:
            with self._database(call.administration_id, create=True) as db:
                assert db is not None
                with db:
                    db.execute(
                        INSERT_EVENT,
                        (
                            call.call_id,
                            datetime.now(UTC).isoformat(),
                            tool,
                            str(selected) if selected else None,
                            phase,
                            elapsed_ms,
                        ),
                    )
        except (OSError, sqlite3.Error):
            raise SnelStartError("Could not write the local audit log.") from None

    def start(self, tool: str) -> AuditCallStart:
        call = AuditCallStart(call_id=uuid4().hex, administration_id=self._selected(), tool=tool)
        self._event(call, tool, AuditOutcome.START, None)
        return call

    def finish(self, call: AuditCallStart, tool: str, phase: AuditOutcome, elapsed_ms: int) -> None:
        self._event(call, tool, phase, elapsed_ms)

    def begin_mutation(self, receipt: MutationReceipt) -> None:
        try:
            with self._database(receipt.administration_id, create=True) as db:
                assert db is not None
                with db:
                    db.execute(
                        "INSERT INTO mutation_receipts(receipt_id, administration_id, tool, operation, "
                        "started_at, updated_at, status, request_sha256, record_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            receipt.receipt_id,
                            str(receipt.administration_id),
                            receipt.tool,
                            receipt.operation,
                            receipt.started_at,
                            receipt.updated_at,
                            receipt.status,
                            receipt.request_sha256,
                            receipt.record_id,
                        ),
                    )
        except (OSError, sqlite3.Error):
            raise SnelStartError(
                "Could not save the mutation receipt. The write was not sent."
            ) from None

    def finish_mutation(self, receipt: MutationReceipt) -> None:
        try:
            with self._database(receipt.administration_id) as db:
                if db is None:
                    raise SnelStartError(
                        "Mutation receipt unavailable. Check the outcome before retrying."
                    )
                with db:
                    db.execute(
                        "UPDATE mutation_receipts SET updated_at = ?, status = ?, response_sha256 = ?, "
                        "record_id = ?, record_id_from_response = ? WHERE receipt_id = ? AND status = ?",
                        (
                            receipt.updated_at,
                            receipt.status,
                            receipt.response_sha256,
                            receipt.record_id,
                            receipt.record_id_from_response,
                            receipt.receipt_id,
                            MutationStatus.SENDING,
                        ),
                    )
        except (OSError, sqlite3.Error):
            raise SnelStartError(
                "Could not finish the mutation receipt. Check the outcome before retrying."
            ) from None

    def mark_mutation_verified(self, receipt: MutationReceipt, verification: str) -> None:
        try:
            with self._database(receipt.administration_id) as db:
                if db is None:
                    raise SnelStartError("Mutation receipt unavailable.")
                with db:
                    db.execute(
                        "UPDATE mutation_receipts SET updated_at = ?, status = ?, verification = ? "
                        "WHERE receipt_id = ? AND status IN (?, ?)",
                        (
                            datetime.now(UTC).isoformat(),
                            MutationStatus.VERIFIED,
                            verification,
                            receipt.receipt_id,
                            MutationStatus.ACCEPTED,
                            MutationStatus.UNRESOLVED,
                        ),
                    )
        except (OSError, sqlite3.Error):
            raise SnelStartError("Could not save the receipt verification.") from None

    @staticmethod
    def _receipt(row: sqlite3.Row) -> MutationReceipt:
        receipt = MutationReceipt.model_validate(dict(row))
        if receipt.status is MutationStatus.SENDING:
            receipt.status = MutationStatus.UNRESOLVED
        return receipt

    def _recent_mutations(self, db: sqlite3.Connection, limit: int) -> list[MutationReceipt]:
        return [
            self._receipt(row)
            for row in db.execute(
                "SELECT * FROM mutation_receipts ORDER BY started_at DESC, receipt_id LIMIT ?",
                (limit,),
            )
        ]

    def mutations(self, administration: UUID, limit: int) -> list[MutationReceipt]:
        _check_limit(limit)
        try:
            with self._database(administration) as db:
                if db is None:
                    return []
                return self._recent_mutations(db, limit)
        except (OSError, sqlite3.Error, ValueError):
            raise SnelStartError("Could not read the local mutation receipts.") from None

    def mutation(self, administration: UUID, receipt_id: str) -> MutationReceipt:
        try:
            with self._database(administration) as db:
                row = (
                    db.execute(
                        "SELECT * FROM mutation_receipts WHERE receipt_id = ?", (receipt_id,)
                    ).fetchone()
                    if db is not None
                    else None
                )
                if row is None:
                    raise SnelStartError(
                        "No mutation receipt in the selected administration has that ID."
                    )
                return self._receipt(row)
        except (OSError, sqlite3.Error, ValueError):
            raise SnelStartError("Could not read the local mutation receipt.") from None

    def recent(self, limit: int) -> list[AuditCallResponse]:
        _check_limit(limit)
        call = self.store.audit_call.get()
        administration_id = call.administration_id if call is not None else self._selected()
        try:
            with self._database(administration_id) as db:
                return _recent(db, limit) if db is not None else []
        except (OSError, sqlite3.Error):
            raise SnelStartError("Could not read the local audit log.") from None

    def report(self, administration_id: UUID | None, limit: int) -> AuditReport:
        _check_limit(limit)
        path = self.path(administration_id)
        summary = AuditSummary(database=path, exists=False)
        calls: list[AuditCallResponse] = []
        mutations: list[MutationReceipt] = []
        try:
            with self._database(administration_id) as db:
                if db is not None:
                    with db:
                        db.execute("BEGIN")
                        calls = _recent(db, limit)
                        mutations = self._recent_mutations(db, limit)
                        counts = dict(
                            db.execute(
                                "SELECT outcome, COUNT(*) FROM (" + CALLS + ") GROUP BY outcome"
                            ).fetchall()
                        )
                    summary = AuditSummary(
                        database=path,
                        exists=True,
                        total_calls=sum(counts.values()),
                        succeeded=counts.get(AuditOutcome.OK, 0),
                        failed=counts.get(AuditOutcome.ERROR, 0),
                        interrupted=counts.get(AuditOutcome.INTERRUPTED, 0),
                        pending=counts.get(AuditOutcome.PENDING, 0),
                        latest_call=calls[0] if calls else None,
                    )
        except (OSError, sqlite3.Error, ValueError):
            raise SnelStartError("Could not read the local audit log.") from None
        return AuditReport(
            administration_id=administration_id, summary=summary, calls=calls, mutations=mutations
        )
