"""Allowlisted SnelStart Web API client with explicit administration context."""

import json
import os
import threading
from contextlib import nullcontext
from email.message import Message
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from urllib.parse import unquote
from uuid import UUID, uuid4

import httpx
from pydantic import JsonValue, ValidationError

from .auth import AUDIENCE, Auth
from .config import SnelStartError, SnelStartHTTPError, Store
from .enums import HttpMethod
from .models import JsonObject
from .models.api import (
    JSON_ROWS,
    JSON_VALUE,
    SALES_BOOKING_DETAILS,
    SALES_BOOKING_ID,
    SALES_BOOKING_ID_ERROR,
    SALES_BOOKING_ID_PARAMETER,
    OperationSpec,
    WebApiRequest,
)
from .models.responses import ConnectionStatus
from .mutation import send_with_receipt
from .write_policy import needs_scoped_grant

MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
READ_POST_OPERATIONS = {
    "POST /Invoices/RedetermineVat",
    "POST /Invoices/Search",
    "POST /Quotations/RedetermineVat",
}


def catalog() -> dict:
    return json.loads(files("snelstart_mcp").joinpath("catalog.json").read_text())


def write_warning(operation: str) -> str | None:
    return catalog().get(operation, {}).get("write_warning")


class Client:
    def __init__(self, store: Store, http: httpx.Client | None = None, *, read_only: bool = False):
        self.store = store
        self.read_only = read_only
        self.http = http or httpx.Client(timeout=30, follow_redirects=False, trust_env=False)
        self.auth = Auth(store, self.http)
        self._mutex = threading.RLock()
        self._opened = None
        self.session_id = str(uuid4())

    def close(self):
        self.http.close()

    def check_write_access(self, operation: str, administration: UUID) -> None:
        if self.read_only:
            raise SnelStartError("Writing is disabled in live read-only mode.")
        settings = self.store.settings()
        if settings.administration_id != administration:
            raise SnelStartError("The selected administration differs from the write request.")
        if operation in settings.approved_write_operations():
            return
        if settings.allow_writes and not needs_scoped_grant(operation):
            return
        raise SnelStartError(
            "Writing is disabled for this operation in the selected administration. "
            "Grant it locally with 'snelstart-mcp writes grant'."
        )

    def status(self) -> dict:
        settings = self.store.settings()
        credentials = self.auth.credentials()
        tokens = self.auth.stored_tokens()
        return ConnectionStatus(
            configured=bool(tokens.refresh_token or credentials.password),
            automatic_login=bool(credentials.username and credentials.password),
            automatic_refresh=bool(tokens.refresh_token),
            access_token_expires_at=tokens.expires_at,
            administration_id=settings.administration_id,
            allow_writes=not self.read_only and settings.allow_writes,
            approved_write_operations=[]
            if self.read_only
            else sorted(settings.approved_write_operations()),
            write_confirmations_required=settings.write_confirmations_required(),
            config_directory=self.store.directory,
        ).model_dump(mode="json")

    def _send(
        self,
        method: HttpMethod,
        path: str,
        params=None,
        body=None,
        administration=None,
        *,
        download: bool = False,
        read_only: bool | None = None,
    ) -> JsonValue:
        token = self.auth.access_token(administration)
        headers = {
            "Authorization": "Bearer " + token,
            "SessionId": self.session_id,
            "Accept": "application/json",
        }
        may_retry = method == HttpMethod.GET if read_only is None else read_only
        for attempt in range(2):
            request = self.http.build_request(
                method,
                AUDIENCE + path,
                params=params,
                json=body,
                headers=headers,
            )
            response = self.http.send(request, stream=download, follow_redirects=False)
            try:
                if response.status_code == 401 and attempt == 0:
                    if not may_retry:
                        raise SnelStartError(
                            "The session expired. The write request was not retried."
                        )
                    headers["Authorization"] = "Bearer " + self.auth.access_token(
                        administration, force=True
                    )
                    continue
                if response.status_code >= 300:
                    raise SnelStartHTTPError(
                        response.status_code,
                        f"SnelStart API returned HTTP {response.status_code} for {method} {path}.",
                    )
                if download:
                    return self._save_download(response)
                if response.status_code == 204 or not response.content:
                    return None
                if len(response.content) > 5_000_000:
                    raise SnelStartError("The response is too large. Request a smaller page.")
                try:
                    return JSON_VALUE.validate_json(response.content)
                except ValueError:
                    raise SnelStartError(
                        "The endpoint did not return JSON. Use snelstart_download_document for files."
                    ) from None
            finally:
                response.close()
        raise SnelStartError("SnelStart did not accept the renewed session.")

    def _save_download(self, response: httpx.Response) -> JsonObject:
        if response.status_code != 200:
            raise SnelStartError("SnelStart did not return a complete file.")
        content_type = response.headers.get("content-type", "").split(";")[0].lower()
        if content_type in {"text/html", "application/json", "application/problem+json"}:
            raise SnelStartError("SnelStart did not return a document.")
        headers = Message()
        headers["Content-Disposition"] = response.headers.get("content-disposition", "")
        original_name = unquote(headers.get_filename() or "").replace("\\", "/").split("/")[-1]
        original_name = "".join(c for c in original_name if c.isprintable())[:255]
        suffix = Path(original_name).suffix.lower()
        if suffix not in {".pdf", ".xml", ".ubl", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".zip"}:
            suffix = {
                "application/pdf": ".pdf",
                "application/xml": ".xml",
                "text/xml": ".xml",
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/tiff": ".tiff",
                "application/zip": ".zip",
            }.get(content_type, ".bin")
        directory = Store(self.store.directory / "downloads").directory
        target = directory / (uuid4().hex + suffix)
        digest = sha256()
        total = 0
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                for chunk in response.iter_bytes(65536):
                    total += len(chunk)
                    if total > MAX_DOWNLOAD_BYTES:
                        raise SnelStartError("The document exceeds 25 MiB.")
                    digest.update(chunk)
                    stream.write(chunk)
                if not total:
                    raise SnelStartError("SnelStart returned an empty file.")
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return {
            "path": str(target),
            "original_filename": original_name or None,
            "content_type": content_type,
            "bytes": total,
            "sha256": digest.hexdigest(),
        }

    def administrations(self) -> list[JsonObject]:
        with self._mutex:
            try:
                return JSON_ROWS.validate_python(self._send(HttpMethod.GET, "/Administrations/All"))
            except ValidationError:
                raise SnelStartError("SnelStart returned an invalid administration list.") from None

    def select_administration(self, identifier: str, persist: bool = True):
        identifier = str(UUID(identifier))
        with self._mutex:
            administrations = self.administrations()
            selected = next((a for a in administrations if a.get("identifier") == identifier), None)
            if not selected:
                raise SnelStartError("The administration is unavailable to this account.")
            result = self._send(
                HttpMethod.POST,
                "/Administrations/Open",
                body={
                    "administrationId": selected["id"],
                    "administrationIdentifier": identifier,
                },
            )
            if result != 0:
                raise SnelStartError("SnelStart could not open the administration.")
            self.auth.access_token(identifier)
            self._opened = identifier
            if persist:
                with self.store.locked():
                    config = self.store.read("config.json")
                    config["administration_id"] = identifier
                    self.store.write("config.json", config)
            return {"identifier": identifier, "opened": True}

    def request(
        self,
        operation: str,
        params: JsonObject | None = None,
        body: JsonValue = None,
        *,
        download: bool = False,
        expected_administration: str | None = None,
    ) -> JsonValue:
        raw_entry = catalog().get(operation)
        if not raw_entry:
            raise SnelStartError("Unknown operation. Use snelstart_list_operations first.")
        entry = OperationSpec.model_validate(raw_entry)
        if self.read_only and not entry.read_only:
            raise SnelStartError("Writing is disabled in live read-only mode.")
        command = WebApiRequest(
            operation=operation,
            parameters=params,
            body=body,
            download=download,
            expected_administration=UUID(expected_administration)
            if expected_administration
            else None,
        )
        if (
            entry.read_only
            and entry.method is not HttpMethod.GET
            and command.operation not in READ_POST_OPERATIONS
        ):
            raise SnelStartError("This operation is not allowed as a read request.")
        if command.download != raw_entry.get("binary", False):
            raise SnelStartError("Use snelstart_download_document for files.")
        # Administrative session operations are implemented separately, never as arbitrary writes.
        if operation == "GET /Administrations/All":
            administrations: list[JsonValue] = [*self.administrations()]
            return administrations
        if entry.path.startswith("/Administrations/"):
            raise SnelStartError("Use snelstart_select_administration to select an administration.")
        with self._mutex, nullcontext() if entry.read_only else self.store.locked():
            settings = self.store.settings()
            audit_call = self.store.audit_call.get()
            if (
                audit_call is not None
                and audit_call.administration_id != settings.administration_id
            ):
                raise SnelStartError(
                    "The selected administration changed during this tool call. "
                    "Check the active administration before retrying."
                )
            if not entry.read_only:
                if settings.administration_id is None:
                    raise SnelStartError("Select the administration before attempting a write.")
                self.check_write_access(command.operation, settings.administration_id)
            unknown = set(command.parameters or {}) - set(entry.query_parameters)
            if unknown:
                raise SnelStartError("Unknown query parameter. Use snelstart_list_operations.")
            missing = set(entry.required_parameters) - set(command.parameters or {})
            if missing:
                raise SnelStartError("Missing query parameters: " + ", ".join(sorted(missing)))
            if command.operation == SALES_BOOKING_DETAILS:
                try:
                    SALES_BOOKING_ID.validate_python(
                        (command.parameters or {}).get(SALES_BOOKING_ID_PARAMETER)
                    )
                except ValidationError:
                    raise SnelStartError(SALES_BOOKING_ID_ERROR) from None
            if entry.method is HttpMethod.GET and command.body is not None:
                raise SnelStartError("A GET operation does not accept a JSON body.")
            identifier = str(settings.administration_id) if settings.administration_id else None
            if (
                command.expected_administration is not None
                and settings.administration_id != command.expected_administration
            ):
                raise SnelStartError(
                    "The selected administration does not match the requested one."
                )
            if not identifier:
                raise SnelStartError(
                    "Select an administration with snelstart_select_administration first."
                )
            if self._opened != identifier:
                self.select_administration(identifier, persist=False)
            normalized: JsonObject = {
                k: (str(v).lower() if isinstance(v, bool) else "" if v is None else v)
                for k, v in (command.parameters or {}).items()
            }

            def send() -> JsonValue:
                return self._send(
                    entry.method,
                    entry.path,
                    normalized,
                    command.body,
                    identifier,
                    download=command.download,
                    read_only=entry.read_only,
                )

            if (
                not entry.read_only
                and entry.method is not HttpMethod.GET
                and audit_call is not None
            ):
                return send_with_receipt(
                    self.store,
                    audit_call,
                    UUID(identifier),
                    command.operation,
                    normalized,
                    command.body,
                    send,
                )
            return send()
