"""Read and atomically update a local client JSON file."""

import json
import os
import tempfile
from pathlib import Path

from .config import SnelStartError


def read_client_config(path: Path) -> tuple[dict, bytes | None]:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise SnelStartError("The client configuration must be a regular file.")
    original = path.read_bytes() if path.exists() else None
    try:
        config = {} if original is None else json.loads(original)
    except (UnicodeError, ValueError):
        raise SnelStartError(
            "The client configuration is not plain JSON. Merge the preview in the client editor."
        ) from None
    if not isinstance(config, dict):
        raise SnelStartError("The client configuration has an unexpected structure.")
    return config, original


def write_client_config(path: Path, config: dict, original: bytes | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".snelstart-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(config, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        current = path.read_bytes() if path.exists() else None
        if path.is_symlink() or current != original:
            raise SnelStartError("The client configuration changed during registration. Try again.")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
