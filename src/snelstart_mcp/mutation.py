"""Durable write intent and transport outcome without storing payloads."""

import hashlib
import json
import re
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from uuid import UUID

from pydantic import JsonValue

from .audit import AuditLog
from .config import SnelStartError, Store
from .enums import MutationStatus
from .models import JsonObject
from .models.audit import AuditCallStart, MutationReceipt

PURCHASE_SUBMISSION = "POST /Purchases/CreateInkoopVoorBijlage"
RECORD_KEYS = (
    "publicIdentifier",
    "journaalpostIdentifier",
    "kasBankboekingIdentifier",
    "attachmentIdentifier",
    "identifier",
)
PROCESSING_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")


def _hash(value: JsonValue) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def record_identifier(value: JsonValue, operation: str, *, response: bool = False) -> str | None:
    if operation == PURCHASE_SUBMISSION:
        instance = value.get("instanceId") if isinstance(value, dict) and response else None
        return instance if isinstance(instance, str) and PROCESSING_ID.fullmatch(instance) else None
    if isinstance(value, dict):
        values = [value.get(key) for key in RECORD_KEYS]
        if response:
            values.append(value.get("id"))
    else:
        values = [value] if response else []
    for candidate in values:
        if not isinstance(candidate, str):
            continue
        try:
            return str(UUID(candidate))
        except ValueError:
            continue
    return None


def send_with_receipt(
    store: Store,
    call: AuditCallStart,
    administration: UUID,
    operation: str,
    parameters: JsonObject,
    payload: JsonValue,
    send: Callable[[], JsonValue],
) -> JsonValue:
    now = datetime.now(UTC).isoformat()
    receipt = MutationReceipt(
        receipt_id=call.call_id,
        administration_id=administration,
        tool=call.tool,
        operation=operation,
        started_at=now,
        updated_at=now,
        status=MutationStatus.SENDING,
        request_sha256=_hash({"parameters": parameters, "payload": payload}),
        record_id=record_identifier(parameters, operation) or record_identifier(payload, operation),
    )
    audit = AuditLog(store)
    audit.begin_mutation(receipt)
    try:
        result = send()
    except BaseException:
        receipt.status = MutationStatus.UNRESOLVED
        receipt.updated_at = datetime.now(UTC).isoformat()
        with suppress(SnelStartError):
            audit.finish_mutation(receipt)
        raise
    identifier = (
        None
        if operation.startswith("DELETE ")
        else record_identifier(result, operation, response=True)
    )
    if identifier is not None:
        receipt.record_id = identifier
        receipt.record_id_from_response = True
    receipt.status = MutationStatus.ACCEPTED
    receipt.updated_at = datetime.now(UTC).isoformat()
    receipt.response_sha256 = _hash(result)
    audit.finish_mutation(receipt)
    return result
