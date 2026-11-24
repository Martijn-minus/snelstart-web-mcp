import sqlite3
import stat
from contextlib import closing
from uuid import UUID

from snelstart_mcp.audit import INSERT_EVENT, SCHEMA, AuditLog
from snelstart_mcp.config import Store
from snelstart_mcp.enums import AuditOutcome

FIRST = UUID("11111111-1111-4111-8111-111111111111")
SECOND = UUID("22222222-2222-4222-8222-222222222222")


def test_call_completion_stays_with_the_administration_at_start(tmp_path):
    store = Store(tmp_path / "profile")
    log = AuditLog(store)
    assert not log.report(FIRST, 10).summary.exists
    assert not log.directory.exists()

    profile_call = log.start("snelstart_status")
    log.finish(profile_call, "snelstart_status", AuditOutcome.OK, 1)
    store.write("config.json", {"administration_id": str(FIRST)})
    call = log.start("snelstart_select_administration")
    store.write("config.json", {"administration_id": str(SECOND)})
    log.finish(call, "snelstart_select_administration", AuditOutcome.OK, 5)
    failed = log.start("snelstart_status")
    log.finish(failed, "snelstart_status", AuditOutcome.ERROR, 1)

    first = log.report(FIRST, 10)
    second = log.report(SECOND, 10)
    profile = log.report(None, 10)
    assert first.summary.succeeded == second.summary.failed == profile.summary.succeeded == 1
    assert first.calls[0].administration_id_after == SECOND
    assert second.calls[0].call_id == failed.call_id
    assert profile.calls[0].call_id == profile_call.call_id
    for report in (first, second, profile):
        assert report.summary.total_calls == 1
        assert stat.S_IMODE(report.summary.database.stat().st_mode) == 0o600
    assert stat.S_IMODE(log.directory.stat().st_mode) == 0o700


def test_legacy_audit_import_keeps_outcomes_and_picks_up_late_finishes(tmp_path):
    log = AuditLog(Store(tmp_path / "profile"))
    at = "2026-01-01T00:00:00+00:00"

    with closing(sqlite3.connect(log.legacy_path)) as db, db:
        db.executescript(SCHEMA)
        db.executemany(
            INSERT_EVENT,
            [
                ("switch", at, "select", str(FIRST), "start", None),
                ("switch", at, "select", str(SECOND), "ok", 1),
                ("old-pending", at, "read", str(FIRST), "start", None),
                ("other", at, "read", str(SECOND), "start", None),
                ("other", at, "read", str(SECOND), "interrupted", 1),
                ("profile", at, "status", None, "start", None),
            ],
        )
    original = log.legacy_path.read_bytes()
    assert log.report(FIRST, 10).summary.pending == 1
    assert log.report(SECOND, 10).summary.interrupted == 1
    assert log.report(None, 10).summary.total_calls == 1
    assert log.legacy_path.read_bytes() == original

    with closing(sqlite3.connect(log.legacy_path)) as db, db:
        db.execute(INSERT_EVENT, ("old-pending", at, "read", str(FIRST), "error", 6))

    for _ in range(2):
        report = log.report(FIRST, 10)
        assert report.summary.total_calls == 2
        assert report.summary.succeeded == report.summary.failed == 1
        assert report.summary.pending == 0
        assert {event.call_id for event in report.calls} == {"switch", "old-pending"}
    assert log.report(SECOND, 10).summary.total_calls == 1
