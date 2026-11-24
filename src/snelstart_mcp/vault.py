"""OS-backed storage for account credentials and OAuth tokens."""

import sys
from hashlib import sha256
from pathlib import Path

SERVICE = "snelstart-web-mcp"
SECRET_FILES = frozenset({"tokens.json", "credentials.json"})


def backend():
    if sys.platform == "darwin":
        from keyring.backends.macOS import Keyring
    elif sys.platform == "linux":
        from keyring.backends.SecretService import Keyring
    else:
        raise RuntimeError("No supported OS secret store.")
    return Keyring()


def account(directory: Path, name: str) -> str:
    profile = sha256(str(directory.resolve()).encode()).hexdigest()
    return f"{profile}:{name}"
