"""Upload an explicitly selected sales email attachment to SnelStart's signed blob URL."""

import os
import re
import stat
from contextlib import closing
from http.client import HTTPException, HTTPSConnection
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .config import SnelStartError
from .purchase_upload import STORAGE_HOST

MAX_ATTACHMENT_BYTES = 10_000_000
ATTACHMENT_TYPES = {
    ".doc": "application/msword",
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".ppt": "application/vnd.ms-powerpoint",
    ".txt": "text/plain",
    ".xls": "application/vnd.ms-excel",
}


def read_attachment(path: Path, max_bytes: int) -> bytes:
    if not path.is_absolute() or path.suffix.lower() not in ATTACHMENT_TYPES:
        raise SnelStartError(
            "Use an absolute path to a file type supported by SnelStart sales email."
        )
    if len(path.name) > 150 or any(ord(char) < 32 or char in '<>:"/\\|?*' for char in path.name):
        raise SnelStartError("The attachment filename contains unsupported characters.")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise SnelStartError("Provide a regular file for the sales email attachment.")
        contents = stream.read(max_bytes + 1)
    if not contents or len(contents) > max_bytes:
        raise SnelStartError("Sales email attachments must be nonempty and total at most 10 MB.")
    return contents


def upload_attachment(url: object, path: Path, contents: bytes) -> str:
    target = urlsplit(url) if isinstance(url, str) else urlsplit("")
    query = parse_qs(target.query)
    location = unquote(target.path)
    if (
        target.scheme != "https"
        or target.netloc != STORAGE_HOST
        or target.fragment
        or not re.fullmatch(r"/bestanden-\d{8}-\d+-\d+/[^/\\]+", location)
        or not location.endswith("_" + path.name)
        or not query.get("sig")
        or not any("w" in grant or "c" in grant for grant in query.get("sp", []))
    ):
        raise SnelStartError(
            "SnelStart returned an unexpected sales attachment upload destination."
        )
    try:
        with closing(HTTPSConnection(STORAGE_HOST, timeout=30)) as connection:
            connection.request(
                "PUT",
                f"{target.path}?{target.query}",
                body=contents,
                headers={
                    "Content-Type": ATTACHMENT_TYPES[path.suffix.lower()],
                    "If-None-Match": "*",
                    "x-ms-blob-type": "BlockBlob",
                },
            )
            with closing(connection.getresponse()) as response:
                if response.status != 201:
                    raise SnelStartError(
                        f"SnelStart attachment storage returned HTTP {response.status}."
                    )
    except (HTTPException, OSError, ValueError):
        raise SnelStartError(
            "Could not upload the sales email attachment to SnelStart storage."
        ) from None
    if not isinstance(url, str):
        raise SnelStartError("SnelStart did not return a sales attachment upload URL.")
    return url
