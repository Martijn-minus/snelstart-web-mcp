#!/usr/bin/env bash
# Install the published SnelStart MCP in an isolated uv tool environment.
set -euo pipefail

fail() {
    printf 'SnelStart MCP: %s\n' "$*" >&2
    exit 1
}

install_uv() (
    command -v curl >/dev/null || fail 'Install curl or uv, then run this installer again.'
    local download
    download=$(mktemp)
    trap 'rm -f -- "$download"' EXIT
    printf 'Installing uv for your user account…\n'
    curl --fail --silent --show-error --location --proto '=https' \
        --output "$download" https://astral.sh/uv/0.12.5/install.sh
    UV_INSTALL_DIR="$HOME/.local/bin" UV_NO_MODIFY_PATH=1 sh "$download"
)

add_homebrew_python_to_path() {
    local brew_prefix bin_dir
    PATH="$PATH:/opt/homebrew/bin:/usr/local/bin:/usr/bin"
    if command -v brew >/dev/null && brew_prefix=$(brew --prefix); then
        for bin_dir in "$brew_prefix/bin" "$brew_prefix"/opt/python*/bin; do
            if [[ -d "$bin_dir" ]]; then
                PATH="$PATH:$bin_dir"
            fi
        done
    fi
}

main() {
    local skills_client=""
    if [[ "${1:-}" == --help && $# == 1 ]]; then
        printf 'Usage: bash install.sh [--with-skills codex|claude-code]\n'
        printf 'Install SnelStart MCP on macOS or Linux.\n'
        return
    fi
    if [[ $# == 2 && "$1" == --with-skills && ( "$2" == codex || "$2" == claude-code ) ]]; then
        skills_client=$2
    elif [[ $# != 0 ]]; then
        fail 'Run bash install.sh --help for installer options.'
    fi

    case "$(uname -s)" in
        Darwin) add_homebrew_python_to_path ;;
        Linux) ;;
        MINGW*|MSYS*|CYGWIN*|Windows*)
            fail 'Native Windows is unsupported. Run this installer in a Linux shell inside WSL.'
            ;;
        *) fail 'This installer supports macOS and Linux.' ;;
    esac
    export PATH="$PATH:$HOME/.local/bin:$HOME/.cargo/bin"
    if ! command -v uv >/dev/null; then
        install_uv
    fi
    local uv_path python bin_dir
    uv_path=$(command -v uv) || fail 'uv is missing. See https://docs.astral.sh/uv/getting-started/installation/.'

    if ! python=$("$uv_path" python find --no-project --system --no-managed-python \
        --no-python-downloads '>=3.11' 2>/dev/null) &&
        ! python=$("$uv_path" python find --no-project --managed-python \
        --no-python-downloads '>=3.11' 2>/dev/null); then
        printf 'No compatible Python found. Installing Python 3.13 with uv…\n'
        "$uv_path" python install 3.13
        python=$("$uv_path" python find --no-project --managed-python --no-python-downloads 3.13)
    fi

    printf 'Using %s (%s)\n' "$("$python" --version)" "$python"
    printf 'Installing SnelStart MCP from PyPI…\n'
    "$uv_path" tool install --quiet --python "$python" --no-python-downloads \
        --upgrade-package snelstart-web-mcp 'snelstart-web-mcp[browser]'
    bin_dir=$("$uv_path" tool dir --bin)
    "$bin_dir/snelstart-mcp" --version
    if [[ -n "$skills_client" ]]; then
        "$bin_dir/snelstart-mcp" install "$skills_client" --skills-only --apply --text
    fi

    case ":$PATH:" in
        *":$bin_dir:"*) ;;
        *)
            if "$uv_path" tool update-shell; then
                printf 'Open a new terminal to pick up the PATH update.\n'
            else
                printf 'Add %s to your PATH, or use the executable there directly.\n' "$bin_dir"
            fi
            ;;
    esac

    printf '\nWith Google Chrome installed, run:\n'
    printf '  snelstart-mcp login --method browser\n'
    printf '  snelstart-mcp doctor\n'
    printf '\nFor Codex, run snelstart-mcp install codex --apply and reconnect the client.\n'
}

main "$@"
