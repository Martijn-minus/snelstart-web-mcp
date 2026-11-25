"""Attach a PDF to an existing cash or bank booking and verify its contents."""

from contextlib import suppress
from functools import partial
from hashlib import sha256
from uuid import UUID

import httpx

from .approval import require_approval
from .audit import AuditLog
from .client import Client
from .config import SnelStartError
from .enums import AttachmentKind, EntryKind
from .models.approval import WriteIntent
from .models.requests import BankAttachmentRequest
from .models.responses import BankAttachmentResponse, DownloadResponse
from .purchase_upload import UPLOAD_URL, _read_pdf, _upload_to_storage
from .tooling import WRITE, Register
from .tools_bookkeeping import ENTRY_DETAILS, read_booking_attachments

ADD_ATTACHMENT = "POST /KasBankBoeking/AddAttachment"
RECEIPTS = "bank-attachments.json"
VERIFICATION = "bank_attachment_sha256_matched"


def verify_attachment(read, entry_id: UUID, attachment_id: UUID, checksum: str, size: int) -> None:
    try:
        attachments = read_booking_attachments(read, AttachmentKind.BANK, entry_id)
        if not any(
            isinstance(row, dict) and row.get("attachmentIdentifier") == str(attachment_id)
            for row in attachments
        ):
            raise SnelStartError("The attachment did not appear on the requested booking.")
        document = DownloadResponse.model_validate(
            read(
                "GET /Attachments/GetContentByIdentifier",
                {"attachmentIdentifier": str(attachment_id)},
                download=True,
            )
        )
        try:
            if document.sha256 != checksum or document.bytes != size:
                raise SnelStartError("The linked PDF did not match the submitted file.")
        finally:
            with suppress(OSError):
                document.path.unlink(missing_ok=True)
    except (httpx.HTTPError, SnelStartError, ValueError):
        raise SnelStartError(
            "Could not verify the bank attachment. Check the booking and its files before retrying."
        ) from None


def register_bank_attachment_tools(tool: Register, client: Client, audit: AuditLog) -> None:
    @tool(annotations=WRITE)
    def snelstart_attach_bank_pdf(request: BankAttachmentRequest) -> BankAttachmentResponse:
        """Attach a local PDF to an existing cash or bank booking and verify the linked file's SHA-256."""
        administration = str(request.administration_id)
        client.check_write_access(UPLOAD_URL, request.administration_id)
        client.check_write_access(ADD_ATTACHMENT, request.administration_id)
        pdf = _read_pdf(request.file_path)
        checksum = sha256(pdf).hexdigest()
        read = partial(client.request, expected_administration=administration)
        operation, parameter = ENTRY_DETAILS[EntryKind.BANK]
        booking = read(operation, {parameter: str(request.entry_id)})
        if not isinstance(booking, dict) or booking.get("identifier") != str(request.entry_id):
            raise SnelStartError("SnelStart did not return the requested bank booking.")

        store = client.store
        key = f"{administration}/{request.entry_id}/{checksum}"
        with store.locked():
            receipts = store.read(RECEIPTS)
            attached = key in receipts
            previous = receipts.get(key)
            if attached and not isinstance(previous, str):
                raise SnelStartError(
                    "This PDF has an unresolved bank attachment. Check the booking before retrying."
                )
            if not attached:
                require_approval(
                    store,
                    WriteIntent(
                        tool="snelstart_attach_bank_pdf",
                        operation=ADD_ATTACHMENT,
                        administration_id=request.administration_id,
                        details={
                            "entry_id": str(request.entry_id),
                            "file_path": str(request.file_path),
                            "bytes": len(pdf),
                            "sha256": checksum,
                        },
                    ),
                    request.approval_id,
                )
                receipts[key] = None
                store.write(RECEIPTS, receipts)

        if isinstance(previous, str):
            attachment_id = UUID(previous)
        else:
            try:
                destination = read(UPLOAD_URL, {"filename": request.file_path.name})
                client.check_write_access(ADD_ATTACHMENT, request.administration_id)
                uri = _upload_to_storage(destination, pdf)
                client.check_write_access(ADD_ATTACHMENT, request.administration_id)
            except Exception:
                # The booking has not been modified. The upload can safely be attempted again.
                with store.locked():
                    receipts = store.read(RECEIPTS)
                    receipts.pop(key, None)
                    store.write(RECEIPTS, receipts)
                raise

            try:
                result = read(
                    ADD_ATTACHMENT,
                    body={
                        "journaalpostIdentifier": str(request.entry_id),
                        "uri": uri,
                        "size": len(pdf),
                        "originalFileName": request.file_path.name,
                        "documentType": 0,
                    },
                )
                value = result.get("attachmentIdentifier") if isinstance(result, dict) else None
                attachment_id = UUID(value) if isinstance(value, str) else UUID(int=0)
                if not attachment_id.int:
                    raise SnelStartError("SnelStart returned no attachment ID.")
            except (httpx.HTTPError, SnelStartError, ValueError):
                raise SnelStartError(
                    "Could not confirm the bank attachment. Check the booking before retrying."
                ) from None
            with store.locked():
                receipts = store.read(RECEIPTS)
                receipts[key] = str(attachment_id)
                store.write(RECEIPTS, receipts)

        verify_attachment(read, request.entry_id, attachment_id, checksum, len(pdf))
        call = store.audit_call.get()
        if call is not None and not attached:
            receipt = audit.mutation(request.administration_id, call.call_id)
            audit.mark_mutation_verified(receipt, VERIFICATION)
        return BankAttachmentResponse(
            administration_id=request.administration_id,
            entry_id=request.entry_id,
            attachment_id=attachment_id,
            sha256=checksum,
            bytes=len(pdf),
            already_attached=attached,
        )
