# Development and releases

[Back to the quick start](../README.md)

See [quick start from a source checkout](installation.md#quick-start-from-a-source-checkout) for local setup.

## Code and tests

The server registers separate groups for connection, bookkeeping and archive tools. The client owns administration context and API requests. Pydantic contracts live in `src/snelstart_mcp/models/` and fixed string enums in `src/snelstart_mcp/enums/`. The MCP advertises flat tool arguments for client compatibility. Year collection and archive storage are separate modules.

```sh
uv run ruff check src tests
uv run ruff format --check src tests
uv run --frozen --extra browser basedpyright
uv run pytest --cov=snelstart_mcp --cov-branch --cov-report=term-missing tests
SNELSTART_RUN_LIVE=1 uv run pytest -q tests/test_live.py
```

The live test requires exactly one administration named `mcp-test`. It signs in using a separate temporary profile, stores test tokens only in that profile and opens only the test administration. It uses read routes and verifies that bookkeeping writes are blocked.

### Pre-commit and distribution builds

From the repository root, install or run the hooks.

```sh
uv run --frozen --extra browser pre-commit install
uv run --frozen --extra browser pre-commit run --all-files
```

The hooks run BasedPyright on the package and Ruff linting and formatting on the package and tests. They also check JSON, YAML and TOML, trailing whitespace, final newlines, merge markers, large files and private keys.

The SnelStart MCP GitHub Actions workflow runs the hooks and offline tests on Python 3.11 and 3.13. It builds a wheel and source distribution, validates the metadata with Twine, and saves both files in the run's `snelstart-mcp-distributions` artifact. From the repository root, run `uv build --no-sources` to build the same formats locally. [PyPI publishing documentation](https://docs.pypi.org/publishing/publishing-to-pypi/)

### Publishing a calendar release

Set the version in `pyproject.toml` to `YYYY.M.D.N` and update `uv.lock` with `uv lock`. Use the release date and count releases from `1` each day. For example, `2026.11.24.1` is followed by `2026.11.24.2` on the same day. The first release on the next day starts at `2026.11.25.1`. Write month, day, and release number without leading zeroes. Tag the reviewed commit as `v<VERSION>`. The PyPI workflow validates the version and tag, builds the package, and publishes via the repository's `pypi` environment.

```sh
gh workflow run workflow.yml --ref "v$(uv run --frozen python -c 'from importlib.metadata import version; print(version("snelstart-web-mcp"))')"
```

The PyPI Trusted Publisher must match this repository and `workflow.yml`. [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
