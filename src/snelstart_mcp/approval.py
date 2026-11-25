"""Require a human to confirm the exact write outside the MCP client."""

import hmac
import json
from datetime import UTC, datetime
from time import time
from uuid import UUID, uuid4

from pydantic import TypeAdapter, ValidationError

from .client import write_warning
from .config import SnelStartError, Store
from .enums import WriteApprovalStatus
from .models.approval import MAX_PENDING, PendingWrite, WriteApprovalState, WriteIntent

FILE = "write-approvals.json"
LIFETIME = 600
APPROVED_LIFETIME = 120
MAX_PREVIEW = 256 * 1024
RECORDS = TypeAdapter(dict[UUID, PendingWrite])


def _records(store: Store) -> dict[UUID, PendingWrite]:
    try:
        records = RECORDS.validate_python(store.read(FILE))
    except ValidationError:
        raise SnelStartError("The local approval records could not be read.") from None
    now = time()
    return {key: record for key, record in records.items() if record.expires > now}


def _save(store: Store, records: dict[UUID, PendingWrite]) -> None:
    store.write(FILE, RECORDS.dump_python(records, mode="json"))


def _preview(intent: WriteIntent) -> str:
    return json.dumps(intent.model_dump(mode="json"), ensure_ascii=True, sort_keys=True)


def require_approval(store: Store, intent: WriteIntent, approval_id: UUID | None) -> None:
    with store.locked():
        settings = store.settings()
        if settings.administration_id != intent.administration_id:
            raise SnelStartError("The selected administration differs from the write request.")
        if approval_id is None and not settings.write_confirmations_required():
            return
        preview = _preview(intent)
        if len(preview) > MAX_PREVIEW:
            raise SnelStartError("This write is too large to review as one operation.")
        records = _records(store)
        if approval_id is not None:
            record = records.get(approval_id)
            if (
                record is None
                or not record.approved
                or not hmac.compare_digest(preview, _preview(record.intent))
            ):
                raise SnelStartError("This write has no matching, unused local approval.")
            del records[approval_id]
            _save(store, records)
            return
        for key, record in records.items():
            if hmac.compare_digest(preview, _preview(record.intent)):
                approval_id = key
                break
        if approval_id is None:
            if len(records) >= MAX_PENDING:
                raise SnelStartError("Too many pending writes. Wait for old requests to expire.")
            approval_id = uuid4()
            records[approval_id] = PendingWrite(intent=intent, expires=time() + LIFETIME)
            _save(store, records)
    raise SnelStartError(
        f"Local confirmation required. Approval ID: {approval_id}. "
        "Use snelstart_open_write_review to open a local browser review for this and any "
        "other pending requests. If the browser is unavailable, ask the user to run "
        f"'snelstart-mcp writes approve {approval_id}' for this profile. After the user "
        f"confirms, retry the same request with approval_id {approval_id}."
    )


def pending_writes(
    store: Store, approval_ids: list[UUID] | None = None
) -> dict[UUID, PendingWrite]:
    with store.locked():
        records = _records(store)
        administration = store.settings().administration_id
        if approval_ids is None:
            return {
                identifier: record
                for identifier, record in records.items()
                if not record.approved and record.intent.administration_id == administration
            }
        if not 1 <= len(approval_ids) <= MAX_PENDING or len(set(approval_ids)) != len(approval_ids):
            raise SnelStartError("Provide between 1 and 24 distinct approval IDs.")
        selected = {}
        for identifier in approval_ids:
            record = records.get(identifier)
            if record is None or record.approved:
                raise SnelStartError("This approval request is unavailable or has expired.")
            if record.intent.administration_id != administration:
                raise SnelStartError("The selected administration differs from the write request.")
            selected[identifier] = record
        return selected


def write_approval_states(store: Store, approval_ids: list[UUID]) -> list[WriteApprovalState]:
    with store.locked():
        records = _records(store)
        administration = store.settings().administration_id
    states = []
    for identifier in approval_ids:
        record = records.get(identifier)
        if record is None or record.intent.administration_id != administration:
            states.append(
                WriteApprovalState(approval_id=identifier, status=WriteApprovalStatus.UNAVAILABLE)
            )
            continue
        states.append(
            WriteApprovalState(
                approval_id=identifier,
                status=WriteApprovalStatus.APPROVED
                if record.approved
                else WriteApprovalStatus.PENDING,
                expires_at=datetime.fromtimestamp(record.expires, UTC),
            )
        )
    return states


def approve_reviewed_writes(store: Store, reviewed: dict[UUID, PendingWrite]) -> None:
    with store.locked():
        records = _records(store)
        administration = store.settings().administration_id
        if any(
            records.get(identifier) != record
            or record.approved
            or administration != record.intent.administration_id
            for identifier, record in reviewed.items()
        ):
            raise SnelStartError(
                "An approval request expired or the active administration changed."
            )
        expires = time() + APPROVED_LIFETIME
        for identifier, record in reviewed.items():
            records[identifier] = record.model_copy(update={"approved": True, "expires": expires})
        _save(store, records)


def approve_write(store: Store, approval_id: UUID) -> None:
    record = pending_writes(store, [approval_id])[approval_id]
    try:
        with (
            open("/dev/tty", encoding="utf-8") as answer,
            open("/dev/tty", "w", buffering=1, encoding="utf-8") as terminal,
        ):
            terminal.write("Review this SnelStart write before confirming:\n")
            if warning := write_warning(record.intent.operation):
                terminal.write(f"{warning}\n\n")
            terminal.write(
                json.dumps(
                    record.intent.model_dump(mode="json"),
                    indent=2,
                    ensure_ascii=True,
                    sort_keys=True,
                )
            )
            terminal.write("\nType APPROVE to allow this exact request once: ")
            terminal.flush()
            confirmed = answer.readline().strip() == "APPROVE"
    except OSError:
        raise SnelStartError("Open a local terminal to review and confirm this request.") from None
    if not confirmed:
        raise SnelStartError("The write was not approved.")

    approve_reviewed_writes(store, {approval_id: record})
