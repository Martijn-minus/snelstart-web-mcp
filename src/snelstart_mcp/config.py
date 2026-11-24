"""Private, atomic local storage shared by CLI and stdio server processes."""

import contextlib
import fcntl
import json
import os
import tempfile
import threading
from contextvars import ContextVar
from pathlib import Path

from pydantic import ValidationError

from . import vault
from .models import Settings
from .models.audit import AuditCallStart


class SnelStartError(Exception):
    """A deliberately credential-free error suitable for MCP output."""


class SnelStartHTTPError(SnelStartError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


class Store:
    def __init__(self, directory: Path | None = None):
        requested = (
            directory or Path(os.environ.get("SNELSTART_CONFIG_DIR", "~/.config/snelstart-mcp"))
        ).expanduser()
        if requested.is_symlink():
            raise SnelStartError("The configuration directory must not be a symbolic link.")
        self.directory = requested.resolve()
        if any(
            (parent / ".git").exists() or (parent / ".git").is_symlink()
            for parent in (self.directory, *self.directory.parents)
        ):
            raise SnelStartError(
                "Choose a private SnelStart profile directory outside Git worktrees."
            )
        self.audit_call: ContextVar[AuditCallStart | None] = ContextVar("audit_call", default=None)
        self._lock = threading.RLock()
        self._lock_depth = 0
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.directory.is_symlink():
            raise SnelStartError("The configuration directory must not be a symbolic link.")
        self.directory.chmod(0o700)

    def read(self, name: str) -> dict:
        if name in vault.SECRET_FILES:
            return self._read_secret(name)
        return self._read_file(name)

    def _read_file(self, name: str) -> dict:
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
        if name in vault.SECRET_FILES:
            with self.locked():
                self._write_secret(name, data)
            return
        self._write_file(name, data)

    def _read_secret(self, name: str) -> dict:
        marker = self.directory / f".keyring-{name}"
        legacy = self.directory / name
        if not (marker.exists() or legacy.exists() or legacy.is_symlink()):
            return {}
        with self.locked():
            if legacy.is_symlink() or marker.is_symlink():
                raise SnelStartError("Configuration files must not be symbolic links.")
            try:
                stored = vault.backend().get_password(
                    vault.SERVICE, vault.account(self.directory, name)
                )
                if stored is not None:
                    data = json.loads(stored)
                    if not isinstance(data, dict):
                        raise ValueError("Invalid stored credentials.")
                    if not marker.exists():
                        self._write_file(marker.name, {})
                    legacy.unlink(missing_ok=True)
                    return data
            except Exception:  # noqa: BLE001 - OS backends can raise errors containing private details.
                raise self._vault_error() from None
            if legacy.exists():
                data = self._read_file(name)
                self._write_secret(name, data)
                return data
            return {}

    def _write_secret(self, name: str, data: dict) -> None:
        marker = f".keyring-{name}"
        legacy = self.directory / name
        if legacy.is_symlink() or (self.directory / marker).is_symlink():
            raise SnelStartError("Configuration files must not be symbolic links.")
        try:
            backend = vault.backend()
            account = vault.account(self.directory, name)
            serialized = json.dumps(data)
            self._write_file(marker, {})
            backend.set_password(vault.SERVICE, account, serialized)
            if backend.get_password(vault.SERVICE, account) != serialized:
                raise ValueError("Keyring write failed validation.")
            legacy.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001 - OS backends can raise errors containing private details.
            raise self._vault_error() from None

    @staticmethod
    def _vault_error() -> SnelStartError:
        return SnelStartError(
            "Could not use the OS secret store. Unlock macOS Keychain or Linux Secret Service and try again."
        )

    def _write_file(self, name: str, data: dict):
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
        with self._lock:
            if self._lock_depth:
                yield
                return
            fd = os.open(self.directory / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "w") as stream:
                fcntl.flock(stream, fcntl.LOCK_EX)
                self._lock_depth += 1
                try:
                    yield
                finally:
                    self._lock_depth -= 1
