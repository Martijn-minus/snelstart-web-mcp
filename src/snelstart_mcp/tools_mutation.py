"""List mutation receipts and verify supported outcomes with read-only SnelStart calls."""

from functools import partial
from uuid import UUID

from mcp.types import ToolAnnotations

from .audit import AuditLog
from .client import Client
from .config import SnelStartError, SnelStartHTTPError
from .enums import EntryKind, MutationStatus
from .models.audit import MutationLookupRequest, MutationReceipt
from .models.requests import LimitRequest
from .models.responses import DataResponse
from .mutation import PURCHASE_SUBMISSION, record_identifier
from .purchase_upload import UPLOAD_STATUS
from .tooling import Register
from .tools_bookkeeping import ENTRY_DETAILS

CREATE_TYPES = {
    "POST /MemoriaalBoekingen/Create": EntryKind.JOURNAL,
    "POST /BalansBoekingen/Create": EntryKind.OPENING_BALANCE,
    "POST /KasBankBoeking/CreateKasBankBoeking": EntryKind.BANK,
}
DELETE_TYPES = {
    "DELETE /MemoriaalBoekingen/Delete": EntryKind.JOURNAL,
    "DELETE /KasBankBoeking/DeleteKasBankBoeking": EntryKind.BANK,
}


def _administration(client: Client) -> UUID:
    current = client.store.settings().administration_id
    scope = client.store.audit_call.get()
    if current is None or (scope is not None and current != scope.administration_id):
        raise SnelStartError(
            "Confirm the selected administration before reading mutation receipts."
        )
    return current


def _verify_result(client: Client, receipt: MutationReceipt) -> str | None:
    if receipt.record_id is None:
        return None
    read = partial(client.request, expected_administration=str(receipt.administration_id))
    if receipt.operation == PURCHASE_SUBMISSION and receipt.record_id_from_response:
        result = read(UPLOAD_STATUS, {"instanceId": receipt.record_id})
        status = result.get("status") if isinstance(result, dict) else None
        return (
            "purchase_processing_completed"
            if isinstance(status, str) and status.casefold() == "completed"
            else None
        )
    deleting = receipt.operation in DELETE_TYPES
    if deleting and receipt.status is not MutationStatus.ACCEPTED:
        return None
    kind = DELETE_TYPES.get(receipt.operation) if deleting else CREATE_TYPES.get(receipt.operation)
    if kind is None or (not deleting and not receipt.record_id_from_response):
        return None
    operation, key = ENTRY_DETAILS[kind]
    try:
        result = read(operation, {key: receipt.record_id})
    except SnelStartHTTPError as error:
        if error.status_code not in (404, 410):
            raise
        return "target_absent" if deleting else None
    if deleting:
        return "target_absent" if result is None else None
    return (
        "returned_record_present"
        if record_identifier(result, receipt.operation, response=True) == receipt.record_id
        else None
    )


def register_mutation_tools(tool: Register, client: Client, audit: AuditLog) -> None:
    @tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def snelstart_mutation_receipts(request: LimitRequest) -> DataResponse[list[MutationReceipt]]:
        """List recent local write receipts for the selected administration, including uncertain outcomes."""
        return DataResponse(data=audit.mutations(_administration(client), request.limit))

    @tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
    )
    def snelstart_verify_mutation(request: MutationLookupRequest) -> MutationReceipt:
        """Read back a supported mutation result, updating only its local receipt. This tool never retries a write."""
        administration = _administration(client)
        receipt = audit.mutation(administration, request.receipt_id)
        if receipt.status is MutationStatus.VERIFIED:
            return receipt
        verification = _verify_result(client, receipt)
        if verification is not None:
            audit.mark_mutation_verified(receipt, verification)
            return audit.mutation(administration, request.receipt_id)
        return receipt
