"""Install the skills bundled with this package into supported clients."""

import os
import tempfile
from importlib.resources import files
from pathlib import Path

from .config import SnelStartError
from .models.responses import SkillInstallResponse

SKILL_CLIENTS = ("codex", "claude-code")


def _bundled_skills() -> dict[str, bytes]:
    source = files("snelstart_mcp").joinpath("skills")
    # Editable installs load the Python package from the repository's src directory.
    package_parent = Path(__file__).resolve().parents[1]
    checkout_skills = package_parent.parent / ".agents" / "skills"
    if package_parent.name == "src" and checkout_skills.is_dir():
        source = checkout_skills
    if not source.is_dir():
        raise SnelStartError("The SnelStart skill bundle is missing.")
    skills = {
        folder.name: folder.joinpath("SKILL.md").read_bytes()
        for folder in source.iterdir()
        if folder.is_dir() and folder.joinpath("SKILL.md").is_file()
    }
    if not skills:
        raise SnelStartError("The SnelStart skill bundle is empty.")
    return skills


def install_skills(client: str, *, apply: bool) -> list[SkillInstallResponse]:
    if client not in SKILL_CLIENTS:
        raise SnelStartError("Bundled skills can be installed for Codex and Claude Code.")
    root = Path.home() / (".agents" if client == "codex" else ".claude") / "skills"
    plans = []
    for name, data in sorted(_bundled_skills().items()):
        path = root / name / "SKILL.md"
        if path.parent.is_symlink() or path.is_symlink():
            raise SnelStartError(f"The existing {name} skill uses a symbolic link.")
        exists = path.parent.exists()
        if exists and (not path.is_file() or path.read_bytes() != data):
            raise SnelStartError(f"A different {name} skill already exists at {path.parent}.")
        plans.append((name, path, data, exists))

    results = []
    for name, path, data, exists in plans:
        status = "already_configured" if exists else "preview"
        if apply and not exists:
            root.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=root) as temporary:
                temporary.write(data)
                temporary.flush()
                path.parent.mkdir()
                try:
                    os.link(temporary.name, path)
                except OSError:
                    path.parent.rmdir()
                    raise
            status = "installed"
        results.append(SkillInstallResponse(name=name, path=path, status=status))
    return results
