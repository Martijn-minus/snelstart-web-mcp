import os
import shutil
import subprocess
from pathlib import Path

import pytest

INSTALLER = Path(__file__).resolve().parents[1] / "install.sh"


def executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/bash\nset -eu\n" + body)
    path.chmod(0o755)


@pytest.mark.skipif(shutil.which("bash") is None, reason="requires Bash")
@pytest.mark.parametrize("platform", ["Darwin", "Linux", "MINGW64_NT"])
def test_install_script_selects_python_and_rejects_native_windows(tmp_path, platform):
    bin_dir = tmp_path / "bin"
    brew_prefix = tmp_path / "Test Homebrew"
    python = brew_prefix / "opt/python@3.13/bin/python3.13"
    log = tmp_path / "uv-commands"
    executable(bin_dir / "uname", 'printf "%s\\n" "$TEST_PLATFORM"\n')
    executable(bin_dir / "brew", 'printf "%s\\n" "$TEST_BREW_PREFIX"\n')
    executable(python, 'printf "Python 3.13.0\\n"\n')
    executable(
        bin_dir / "snelstart-mcp",
        'printf "%s\\n" "$*" >> "$TEST_UV_LOG"\nprintf "SnelStart MCP [test]\\n"\n',
    )
    executable(
        bin_dir / "uv",
        r"""printf '%s\n' "$*" >> "$TEST_UV_LOG"
case "$1 $2" in
    "python find")
        if [[ "$TEST_PLATFORM" == Darwin ]]; then
            [[ "$PATH" == *":${TEST_PYTHON%/*}:"* ]]
        else
            [[ "$*" == *" 3.13" ]] || exit 1
        fi
        printf '%s\n' "$TEST_PYTHON"
        ;;
    "python install"|"tool install") ;;
    "tool dir") printf '%s\n' "${0%/*}" ;;
    *) exit 1 ;;
esac
""",
    )
    result = subprocess.run(
        [
            "bash",
            str(INSTALLER),
            *(["--with-skills", "codex", "--with-hooks"] if platform == "Darwin" else []),
        ],
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "TEST_PLATFORM": platform,
            "TEST_BREW_PREFIX": str(brew_prefix),
            "TEST_PYTHON": str(python),
            "TEST_UV_LOG": str(log),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    if platform.startswith("MINGW"):
        assert result.returncode == 1 and "inside WSL" in result.stderr
        assert not log.exists()
        return

    assert result.returncode == 0, result.stderr
    commands = log.read_text()
    assert (
        "python find --no-project --system --no-managed-python --no-python-downloads >=3.11"
        in commands
    )
    assert ("python install 3.13" in commands) == (platform == "Linux")
    assert (
        f"tool install --quiet --python {python} --no-python-downloads "
        "--upgrade-package snelstart-web-mcp snelstart-web-mcp[browser]" in commands
    )
    assert "tool update-shell" not in commands
    assert ("install codex --skills-only --apply --text" in commands) == (platform == "Darwin")
    assert ("install codex --hooks-only --apply --text" in commands) == (platform == "Darwin")
    assert "snelstart-mcp login --method browser" in result.stdout
