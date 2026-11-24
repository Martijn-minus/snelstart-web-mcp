"""Append-only MCP call events, stored separately for each administration."""

import os
import sqlite3
from contextlib import ExitStack, closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from .config import SnelStartError, Store
from .enums import AuditOutcome
from .models.audit import AuditCallResponse, AuditCallStart, AuditReport, AuditSummary

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
    def __init__(self, store: Store):
        self.store = store
        self.directory = store.directory / "audit"
        self.legacy_path = store.directory / "audit.sqlite3"

    def path(self, administration_id: UUID | None) -> Path:
        return self.directory / f"{administration_id or 'profile'}.sqlite3"

    def _selected(self) -> UUID | None:
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
        call = AuditCallStart(call_id=uuid4().hex, administration_id=self._selected())
        self._event(call, tool, AuditOutcome.START, None)
        return call

    def finish(self, call: AuditCallStart, tool: str, phase: AuditOutcome, elapsed_ms: int) -> None:
        self._event(call, tool, phase, elapsed_ms)

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
        try:
            with self._database(administration_id) as db:
                if db is not None:
                    with db:
                        db.execute("BEGIN")
                        calls = _recent(db, limit)
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
        return AuditReport(administration_id=administration_id, summary=summary, calls=calls)
