"""Serve an exact write review in the user's local browser."""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from secrets import compare_digest, token_urlsafe
from shutil import which
from threading import Event, Lock, Thread
from time import time
from typing import cast
from urllib.parse import parse_qs
from uuid import UUID

from .approval import approve_reviewed_writes, pending_writes
from .client import write_warning
from .config import SnelStartError, Store
from .models.approval import MAX_PENDING, PendingWrite, WriteApprovalReviewResponse

REVIEW_SLOT = Lock()
MAX_FORM_BYTES = 4096
OPERATION_LABELS = {
    "POST /MemoriaalBoekingen/Create": "Create journal entry",
    "POST /MemoriaalBoekingen/Update": "Update journal entry",
    "POST /KasBankBoeking/CreateKasBankBoeking": "Create bank entry",
    "POST /KasBankBoeking/UpdateKasBankBoeking": "Update bank entry",
    "POST /KasBankBoeking/AddMarking": "Mark a bank entry for review",
    "POST /KasBankBoeking/RemoveMarking": "Remove a bank entry review mark",
    "POST /Purchases/CreateInkoopVoorBijlage": "Submit purchase invoice PDF",
    "POST /Purchases/UpdateInkoopboekingBasisGegevens": "Update purchase header",
}

STYLE = """
    :root { color-scheme: light dark; font: 16px system-ui, sans-serif; }
    body { margin: 0; padding: 2rem 1rem; line-height: 1.55; }
    main { max-width: 48rem; margin: auto; }
    h1 { font-size: 1.85rem; margin: 0 0 .4rem; line-height: 1.2; }
    p { margin: .55rem 0 1rem; }
    article { border: 1px solid GrayText; border-radius: .65rem; padding: 1rem;
              margin: 1.1rem 0; }
    article label { display: flex; align-items: baseline; gap: .7rem; font-weight: 650; }
    input[type=checkbox] { width: 1.15rem; height: 1.15rem; flex-shrink: 0; }
    dl { display: grid; grid-template-columns: max-content minmax(0, 1fr);
         margin: .7rem 0; gap: .2rem .65rem; font-size: .9rem; }
    dd { margin: 0; overflow-wrap: anywhere; }
    code { overflow-wrap: anywhere; }
    summary { cursor: pointer; font-weight: 600; font-size: .9rem; }
    pre { margin: .4rem 0 .1rem; max-height: 19rem; overflow: auto;
          padding: .6rem; background: ButtonFace; border-radius: .3rem; font-size: .84rem; }
    button { padding: .6rem .9rem; margin: .35rem .35rem .35rem 0;
             border: 1px solid GrayText; border-radius: .4rem; font: inherit; cursor: pointer; }
    button[value=approve] { background: #16599d; color: white; border-color: #16599d; }
    [role=alert] { border: 1px solid currentColor; border-radius: .4rem; padding: .7rem; }
"""


def _document(title: str, body: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)} · SnelStart MCP</title><style>{STYLE}</style>"
        f"</head><body><main><h1>{escape(title)}</h1>{body}</main></body></html>"
    )


def _review_form(records: dict[UUID, PendingWrite], *, error: str | None = None) -> str:
    first = next(iter(records.values()))
    body = [
        (
            "<p>Select each exact bookkeeping request you want to authorize once. "
            "Your chat can then send the selected requests.</p>"
        ),
        f"<p>Administration <code>{first.intent.administration_id}</code></p>",
    ]
    if error is not None:
        body.append(f'<p role="alert">{escape(error)}</p>')
    body.append('<form method="post">')
    for identifier, record in records.items():
        intent = record.intent
        label = OPERATION_LABELS.get(intent.operation, "Review bookkeeping change")
        warning = write_warning(intent.operation)
        warning_html = f'<p role="alert">{escape(warning)}</p>' if warning else ""
        details = json.dumps(intent.details, indent=2, ensure_ascii=True, sort_keys=True)
        local_time = (
            datetime.fromtimestamp(record.expires)
            .astimezone()
            .isoformat(sep=" ", timespec="seconds")
        )
        body.append(
            f'<article><label><input type="checkbox" name="approval" value="{identifier}">'
            f"{escape(label)}</label><dl>"
            f"<dt>Operation</dt><dd><code>{escape(intent.operation)}</code></dd>"
            f"<dt>Request ID</dt><dd><code>{identifier}</code></dd>"
            f"<dt>Expires</dt><dd>{local_time}</dd></dl>"
            f"{warning_html}"
            f"<details open><summary>Exact request details</summary>"
            f"<pre>{escape(details)}</pre></details></article>"
        )
    body.append(
        '<button type="submit" name="action" value="approve">Approve selected requests</button>'
        '<button type="submit" name="action" value="cancel">Cancel review</button></form>'
    )
    return _document("Review SnelStart changes", "".join(body))


class _ReviewServer(HTTPServer):
    def __init__(self, store: Store, records: dict[UUID, PendingWrite]):
        super().__init__(("127.0.0.1", 0), _ReviewHandler)
        self.store = store
        self.records = records
        self.expires = min(record.expires for record in records.values())
        self.finished = Event()
        self.timeout = 0.5
        self.host = f"127.0.0.1:{self.server_port}"
        self.origin = f"http://{self.host}"
        self.review_path = f"/review/{token_urlsafe(32)}"

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(3)
        return connection, address

    def handle_error(self, request, client_address):
        # The browser's private URL and request contents do not belong in logs.
        pass


class _ReviewHandler(BaseHTTPRequestHandler):
    @property
    def review(self) -> _ReviewServer:
        return cast(_ReviewServer, self.server)

    def log_message(self, format, *args):
        pass

    def _respond(self, status: HTTPStatus, html: str) -> None:
        content = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        # Keep the browser's Origin on the local form submission.
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
            "frame-ancestors 'none'; base-uri 'none'",
        )
        self.end_headers()
        self.wfile.write(content)

    def _can_review(self) -> bool:
        if self.headers.get_all("Host") != [self.review.host] or not compare_digest(
            self.path.encode("utf-8"), self.review.review_path.encode("ascii")
        ):
            self._respond(HTTPStatus.NOT_FOUND, _document("Review unavailable", ""))
            return False
        if self.review.finished.is_set() or time() >= self.review.expires:
            self._respond(
                HTTPStatus.GONE,
                _document("Review expired", "<p>Ask your chat to prepare a new review.</p>"),
            )
            return False
        return True

    def do_GET(self):
        if self._can_review():
            self._respond(HTTPStatus.OK, _review_form(self.review.records))

    def _read_form(self) -> tuple[str, list[UUID]]:
        lengths = self.headers.get_all("Content-Length") or []
        if (
            len(lengths) != 1
            or not lengths[0].isascii()
            or not lengths[0].isdigit()
            or len(lengths[0]) > 4
            or self.headers.get_all("Transfer-Encoding") is not None
            or self.headers.get_content_type() != "application/x-www-form-urlencoded"
        ):
            raise ValueError
        length = int(lengths[0])
        if not 0 < length <= MAX_FORM_BYTES:
            raise ValueError
        fields = parse_qs(
            self.rfile.read(length).decode("ascii"),
            strict_parsing=True,
            max_num_fields=MAX_PENDING + 1,
        )
        if set(fields) - {"action", "approval"}:
            raise ValueError
        (action,) = fields.get("action", [])
        if action not in {"approve", "cancel"}:
            raise ValueError
        identifiers = [UUID(value) for value in fields.get("approval", [])]
        if (
            len(set(identifiers)) != len(identifiers)
            or not set(identifiers) <= self.review.records.keys()
        ):
            raise ValueError
        return action, identifiers

    def do_POST(self):
        if not self._can_review():
            return
        if self.headers.get_all("Origin") != [self.review.origin]:
            self._respond(HTTPStatus.FORBIDDEN, _document("Review request blocked", ""))
            return
        try:
            action, identifiers = self._read_form()
        except (ValueError, OSError):
            self._respond(HTTPStatus.BAD_REQUEST, _document("Invalid review request", ""))
            return
        if action == "cancel":
            self.review.finished.set()
            self._respond(
                HTTPStatus.OK,
                _document("Review canceled", "<p>No requests were approved.</p>"),
            )
            return
        if not identifiers:
            self._respond(
                HTTPStatus.BAD_REQUEST,
                _review_form(self.review.records, error="Select at least one request to approve."),
            )
            return
        try:
            if self.review.finished.is_set() or time() >= self.review.expires:
                raise SnelStartError("The review has expired.")
            approve_reviewed_writes(
                self.review.store,
                {identifier: self.review.records[identifier] for identifier in identifiers},
            )
        except (SnelStartError, OSError):
            self._respond(
                HTTPStatus.CONFLICT,
                _document(
                    "Approval unavailable",
                    "<p>No requests were approved by this form. Ask your chat to check their status.</p>",
                ),
            )
            return
        self.review.finished.set()
        self._respond(
            HTTPStatus.OK,
            _document(
                "Selected requests approved",
                f"<p>Approved {len(identifiers)} of {len(self.review.records)} requests. "
                "Return to your chat and say continue so it can submit the approved requests.</p>"
                "<p>Each approval can be used once within two minutes.</p>",
            ),
        )


def _serve_review(server: _ReviewServer) -> None:
    try:
        with server:
            while not server.finished.is_set() and time() < server.expires:
                server.handle_request()
    finally:
        REVIEW_SLOT.release()


def _open_local_browser(url: str) -> bool:
    if sys.platform == "darwin":
        launcher = "/usr/bin/open"
    elif sys.platform == "linux" and (os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY")):
        launcher = which("xdg-open")
    else:
        return False
    if launcher is None:
        return False
    try:
        result = subprocess.run(
            [launcher, url],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
            check=False,
            env={key: value for key, value in os.environ.items() if key != "BROWSER"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def open_write_review(
    store: Store, approval_ids: list[UUID] | None = None
) -> tuple[WriteApprovalReviewResponse, Thread]:
    records = pending_writes(store, approval_ids)
    if not records:
        raise SnelStartError("There are no pending writes for the selected administration.")
    if not REVIEW_SLOT.acquire(blocking=False):
        raise SnelStartError("A SnelStart write review is already open in your browser.")
    try:
        server = _ReviewServer(store, records)
    except OSError:
        REVIEW_SLOT.release()
        raise SnelStartError("The local write review could not start.") from None
    thread = Thread(target=_serve_review, args=(server,), daemon=True)
    try:
        thread.start()
    except RuntimeError:
        server.server_close()
        REVIEW_SLOT.release()
        raise SnelStartError("The local write review could not start.") from None
    if not _open_local_browser(server.origin + server.review_path):
        server.finished.set()
        thread.join()
        raise SnelStartError(
            "No local browser could be opened. Use 'snelstart-mcp writes approve' in your terminal."
        )
    return (
        WriteApprovalReviewResponse(
            approval_ids=list(records),
            expires_at=datetime.fromtimestamp(server.expires, UTC),
            message="Review the selected requests in your local browser, then return to the chat.",
        ),
        thread,
    )
