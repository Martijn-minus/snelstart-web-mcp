"""Submit purchase PDFs to SnelStart's asynchronous recognition workflow."""

import os
import re
import stat
from contextlib import closing
from hashlib import sha256
from http.client import HTTPException, HTTPSConnection
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import httpx

from .approval import require_approval
from .client import Client
from .config import SnelStartError
from .models.approval import WriteIntent
from .models.requests import PurchaseUploadRequest, UploadStatusRequest
from .models.responses import PurchaseUploadResponse, UploadStatusResponse
from .tooling import READ, WRITE, Register

UPLOAD_URL = "GET /Attachments/GetAttachmentUploadUriNew"
SUBMIT_PURCHASE = "POST /Purchases/CreateInkoopVoorBijlage"
UPLOAD_STATUS = "GET /Purchases/GetInkoopVoorBijlageStatus"
RECEIPTS = "purchase-uploads.json"
STORAGE_HOST = "filetransferprdsnelstart.blob.core.windows.net"
MAX_PDF_BYTES = 25 * 1024 * 1024


def _check_upload_access(client: Client, administration_id: str) -> None:
    if client.read_only:
        raise SnelStartError("Writing is disabled in live read-only mode.")
    settings = client.store.settings()
    if str(settings.administration_id) != administration_id:
        raise SnelStartError("Select the specified administration before uploading a purchase.")
    if not settings.allow_writes and not {UPLOAD_URL, SUBMIT_PURCHASE} <= (
        settings.approved_write_operations()
    ):
        raise SnelStartError(
            "Writing is disabled for purchase uploads. "
            "Grant the upload URL and purchase submission operations locally."
        )


def _read_pdf(path: Path) -> bytes:
    if not path.is_absolute() or path.suffix.lower() != ".pdf":
        raise SnelStartError("Provide an absolute path to a PDF file.")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise SnelStartError("Provide a regular PDF file.")
        data = stream.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise SnelStartError("The PDF exceeds 25 MiB.")
    if not data.startswith(b"%PDF-"):
        raise SnelStartError("The file has no PDF header.")
    return data


def _upload_to_storage(url: object, pdf: bytes) -> str:
    target = urlsplit(url) if isinstance(url, str) else urlsplit("")
    query = parse_qs(target.query)
    path = unquote(target.path)
    if (
        target.scheme != "https"
        or target.netloc != STORAGE_HOST
        or target.fragment
        or not re.fullmatch(r"/bestanden-\d{8}-\d+-\d+/.+\.pdf", path, re.IGNORECASE)
        or any(segment in {".", ".."} for segment in path.split("/"))
        or not query.get("sig")
        or not any("w" in permission or "c" in permission for permission in query.get("sp", []))
    ):
        raise SnelStartError("SnelStart returned an unexpected PDF upload destination.")

    # Use a separate connection. The signed URL authenticates the storage request.
    # http.client follows no redirects and does not log URLs by default.
    try:
        with closing(HTTPSConnection(STORAGE_HOST, timeout=30)) as connection:
            connection.request(
                "PUT",
                f"{target.path}?{target.query}",
                body=pdf,
                headers={
                    "Content-Type": "application/pdf",
                    "If-None-Match": "*",
                    "x-ms-blob-type": "BlockBlob",
                },
            )
            with closing(connection.getresponse()) as response:
                if response.status != 201:
                    raise SnelStartError(
                        f"PDF storage rejected the upload (HTTP {response.status})."
                    )
    except (HTTPException, OSError, ValueError):
        raise SnelStartError("Could not upload the PDF to SnelStart storage.") from None
    return target._replace(query="").geturl()


def submit_purchase_pdf(client: Client, administration_id: str, path: Path, pdf: bytes) -> dict:
    _check_upload_access(client, administration_id)
    checksum = sha256(pdf).hexdigest()
    key = f"{administration_id}/{checksum}"
    store = client.store
    with store.locked():
        receipts = store.read(RECEIPTS)
        if key in receipts:
            previous_id = receipts[key]
            if not isinstance(previous_id, str) or not previous_id:
                raise SnelStartError(
                    "This PDF has an unresolved submission. Check SnelStart before retrying."
                )
            return {"instance_id": previous_id, "sha256": checksum, "already_submitted": True}
        receipts[key] = None
        store.write(RECEIPTS, receipts)

    try:
        destination = client.request(
            UPLOAD_URL, {"filename": path.name}, expected_administration=administration_id
        )
        _check_upload_access(client, administration_id)
        uploaded_path = _upload_to_storage(destination, pdf)
        _check_upload_access(client, administration_id)
    except Exception:
        # Purchase processing has not been requested. A fresh upload can safely restart.
        with store.locked():
            receipts = store.read(RECEIPTS)
            receipts.pop(key, None)
            store.write(RECEIPTS, receipts)
        raise

    try:
        result = client.request(
            SUBMIT_PURCHASE, {"pathUrl": uploaded_path}, expected_administration=administration_id
        )
        instance_id = result.get("instanceId") if isinstance(result, dict) else None
        if not isinstance(instance_id, str) or not instance_id:
            raise SnelStartError("SnelStart returned no purchase processing ID.")
    except (httpx.HTTPError, SnelStartError):
        # The POST may have been accepted before the response was lost.
        raise SnelStartError(
            "Could not confirm the purchase submission. Check SnelStart before retrying."
        ) from None
    receipt = {"instance_id": instance_id, "sha256": checksum, "already_submitted": False}
    try:
        with store.locked():
            receipts = store.read(RECEIPTS)
            receipts[key] = instance_id
            store.write(RECEIPTS, receipts)
    except (OSError, SnelStartError):
        receipt["tracking_saved"] = False
    return receipt


def register_purchase_upload_tools(tool: Register, client: Client) -> None:
    @tool(annotations=WRITE)
    def snelstart_upload_purchase_pdf(request: PurchaseUploadRequest) -> PurchaseUploadResponse:
        """Submit a PDF after one-use local approval of its path and SHA-256."""
        administration = str(request.administration_id)
        _check_upload_access(client, administration)
        pdf = _read_pdf(request.file_path)
        require_approval(
            client.store,
            WriteIntent(
                tool="snelstart_upload_purchase_pdf",
                operation=SUBMIT_PURCHASE,
                administration_id=request.administration_id,
                details={
                    "file_path": str(request.file_path),
                    "sha256": sha256(pdf).hexdigest(),
                    "bytes": len(pdf),
                },
            ),
            request.approval_id,
        )
        return PurchaseUploadResponse.model_validate(
            submit_purchase_pdf(client, administration, request.file_path, pdf)
        )

    @tool(annotations=READ)
    def snelstart_purchase_upload_status(request: UploadStatusRequest) -> UploadStatusResponse:
        """Read the processing status of a submitted purchase PDF."""
        result = client.request(
            UPLOAD_STATUS,
            {"instanceId": request.instance_id},
            expected_administration=str(request.administration_id),
        )
        status = result.get("status") if isinstance(result, dict) else None
        if not isinstance(status, (str, int)) or isinstance(status, bool):
            raise SnelStartError("SnelStart returned no purchase processing status.")
        return UploadStatusResponse(instance_id=request.instance_id, status=status)
