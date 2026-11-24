"""Require a human to confirm the exact write outside the MCP client."""

import hmac
import json
from time import time
from uuid import UUID, uuid4

from pydantic import TypeAdapter, ValidationError

from .config import SnelStartError, Store
from .models.approval import PendingWrite, WriteIntent

FILE = "write-approvals.json"
LIFETIME = 600
APPROVED_LIFETIME = 120
MAX_PENDING = 24
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
    preview = _preview(intent)
    if len(preview) > MAX_PREVIEW:
        raise SnelStartError("This write is too large to review as one operation.")
    with store.locked():
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
        f"Local confirmation required. Ask the user to run 'snelstart-mcp writes approve "
        f"{approval_id}' in their terminal for this profile. After they confirm, retry the "
        f"same request with approval_id {approval_id}."
    )


def approve_write(store: Store, approval_id: UUID) -> None:
    with store.locked():
        record = _records(store).get(approval_id)
    if record is None or record.approved:
        raise SnelStartError("This approval request is unavailable or has expired.")
    if store.settings().administration_id != record.intent.administration_id:
        raise SnelStartError("The selected administration differs from the write request.")

    try:
        with (
            open("/dev/tty", encoding="utf-8") as answer,
            open("/dev/tty", "w", buffering=1, encoding="utf-8") as terminal,
        ):
            terminal.write("Review this SnelStart write before confirming:\n")
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

    with store.locked():
        records = _records(store)
        latest = records.get(approval_id)
        if (
            latest != record
            or store.settings().administration_id != record.intent.administration_id
        ):
            raise SnelStartError("The approval request or active administration changed.")
        record.approved = True
        record.expires = time() + APPROVED_LIFETIME
        records[approval_id] = record
        _save(store, records)
