"""Append-only call events. No arguments, results or credentials go into the log."""

import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from uuid import uuid4

from .config import SnelStartError, Store
from .enums import AuditOutcome

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
"""


class AuditLog:
    def __init__(self, store: Store):
        self.store = store
        self.path = store.directory / "audit.sqlite3"

    def _connect(self) -> sqlite3.Connection:
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            os.fchmod(fd, 0o600)
        finally:
            os.close(fd)
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.executescript(SCHEMA)
        except sqlite3.Error:
            db.close()
            raise
        return db

    def _event(self, event_id: str, tool: str, phase: AuditOutcome, elapsed_ms: int | None = None):
        try:
            administration = self.store.settings().administration_id
        except SnelStartError:
            administration = None
        try:
            with closing(self._connect()) as db, db:
                db.execute(
                    "INSERT INTO events(id, at, tool, administration, phase, elapsed_ms) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        event_id,
                        datetime.now(UTC).isoformat(),
                        tool,
                        str(administration) if administration else None,
                        phase,
                        elapsed_ms,
                    ),
                )
        except (OSError, sqlite3.Error):
            raise SnelStartError("Could not write the local audit log.") from None

    def start(self, tool: str) -> str:
        event_id = uuid4().hex
        self._event(event_id, tool, AuditOutcome.START)
        return event_id

    def finish(self, event_id: str, tool: str, phase: AuditOutcome, elapsed_ms: int):
        self._event(event_id, tool, phase, elapsed_ms)

    def recent(self, limit: int) -> list[dict]:
        if not 1 <= limit <= 100:
            raise SnelStartError("The limit must be between 1 and 100.")
        try:
            with closing(self._connect()) as db:
                rows = db.execute(
                    "SELECT s.id AS call_id, s.at AS started_at, s.tool, "
                    "s.administration AS administration_id, "
                    "e.administration AS administration_id_after, "
                    "COALESCE(e.phase, 'pending') AS outcome, e.elapsed_ms "
                    "FROM events s LEFT JOIN events e ON e.id = s.id AND e.phase != 'start' "
                    "WHERE s.phase = 'start' ORDER BY s.seq DESC LIMIT ?",
                    (limit,),
                )
                return [dict(row) for row in rows]
        except (OSError, sqlite3.Error):
            raise SnelStartError("Could not read the local audit log.") from None
