"""Private, atomic local storage shared by CLI and stdio server processes."""

import contextlib
import fcntl
import json
import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from .models import Settings


class SnelStartError(Exception):
    """A deliberately credential-free error suitable for MCP output."""


class Store:
    def __init__(self, directory: Path | None = None):
        self.directory = (
            directory
            or Path(os.environ.get("SNELSTART_CONFIG_DIR", "~/.config/snelstart-mcp")).expanduser()
        )
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.directory.is_symlink():
            raise SnelStartError("The configuration directory must not be a symbolic link.")
        self.directory.chmod(0o700)

    def read(self, name: str) -> dict:
        path = self.directory / name
        if not path.exists():
            return {}
        if path.is_symlink():
            raise SnelStartError("Configuration files must not be symbolic links.")
        path.chmod(0o600)
        try:
            data = json.loads(path.read_text())
            if not isinstance(data, dict):
                raise TypeError("Expected a JSON object")
        except (ValueError, TypeError, OSError):
            raise SnelStartError(f"Could not read {name}. Check the local configuration.") from None
        return data

    def settings(self) -> Settings:
        try:
            return Settings.model_validate(self.read("config.json"))
        except ValidationError:
            raise SnelStartError("Invalid MCP configuration. Check config.json.") from None

    def write(self, name: str, data: dict):
        fd, temporary = tempfile.mkstemp(dir=self.directory, prefix=".pending-")
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(data, stream, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.directory / name)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @contextlib.contextmanager
    def locked(self):
        # Refresh-token rotation is serialized even across separate MCP processes.
        fd = os.open(self.directory / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield
