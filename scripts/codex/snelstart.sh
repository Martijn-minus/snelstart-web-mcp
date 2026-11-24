#!/bin/bash
set -euo pipefail

export PATH="${UV_TOOL_BIN_DIR:-$HOME/.local/bin}:$HOME/.local/bin:$PATH:/opt/homebrew/bin:/usr/local/bin"

if ! command -v snelstart-mcp >/dev/null && command -v uv >/dev/null; then
    bin_dir=$(uv tool dir --bin)
    export PATH="$bin_dir:$PATH"
fi

if ! command -v snelstart-mcp >/dev/null; then
    printf '%s\n' 'Install the local runtime: uv tool install "snelstart-web-mcp[browser]"' >&2
    exit 127
fi

case "${1:-}" in
    serve|codex-hook) exec snelstart-mcp "$1" ;;
    *) exit 2 ;;
esac
