import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from snelstart_mcp import updater
from snelstart_mcp.config import SnelStartError
from snelstart_mcp.enums import UpdateStatus
from snelstart_mcp.version import version_label

COMMIT = "0" * 40


def install_metadata(monkeypatch, url=updater.UPSTREAM, revision=None):
    package = SimpleNamespace(
        version="0.2.0",
        read_text=lambda filename: json.dumps(
            {
                "url": url,
                "vcs_info": {"vcs": "git", "commit_id": COMMIT, "requested_revision": revision},
            }
        ),
    )
    monkeypatch.setattr(updater, "distribution", lambda name: package)


@pytest.mark.parametrize(
    ("comparison", "status"),
    [
        ("ahead", UpdateStatus.AVAILABLE),
        ("identical", UpdateStatus.CURRENT),
        ("diverged", UpdateStatus.UNAVAILABLE),
    ],
)
def test_git_update_check_uses_unauthenticated_public_comparison(monkeypatch, comparison, status):
    install_metadata(monkeypatch)
    request = httpx.Request("GET", "https://api.github.com/")
    fetch = Mock(return_value=httpx.Response(200, json={"status": comparison}, request=request))
    monkeypatch.setattr(updater.httpx, "get", fetch)
    checker = updater.UpdateChecker()
    result = checker.check()
    assert result.status is status
    assert result.installed_version == "0.2.0"
    assert checker.check() == result
    fetch.assert_called_once()
    assert fetch.call_args.args[0].endswith(f"/compare/{COMMIT}...main")
    assert "Authorization" not in fetch.call_args.kwargs["headers"]
    checker.check(refresh=True)
    assert fetch.call_count == 2


@pytest.mark.parametrize(
    ("url", "revision"), [("file:///local/example", None), (updater.UPSTREAM, "v0.2.0")]
)
def test_nonstandard_sources_are_not_sent_to_github(monkeypatch, url, revision):
    install_metadata(monkeypatch, url, revision)
    fetch = Mock()
    monkeypatch.setattr(updater.httpx, "get", fetch)
    assert updater.UpdateChecker().check().status is UpdateStatus.UNAVAILABLE
    fetch.assert_not_called()


def test_self_update_runs_only_for_active_uv_tool(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "which", lambda name: "/fixture/uv")
    run = Mock(return_value=SimpleNamespace(stdout=str(tmp_path)))
    monkeypatch.setattr(updater.subprocess, "run", run)
    monkeypatch.setattr(updater.sys, "prefix", str(tmp_path / "checkout"))
    with pytest.raises(SnelStartError, match="outside the active uv tool installation"):
        updater.update_tool()
    assert run.call_count == 1
    monkeypatch.setattr(updater.sys, "prefix", str(tmp_path / updater.PACKAGE))
    assert updater.update_tool().completed
    assert run.call_args.args == (["/fixture/uv", "tool", "upgrade", updater.PACKAGE],)


def test_same_process_detects_local_upgrade_during_cached_update_check(monkeypatch):
    running = "2026.11.24.9"
    package = SimpleNamespace(version=running, read_text=lambda _: None)
    monkeypatch.setattr(updater, "distribution", lambda _: package)
    monkeypatch.setattr(updater, "installed_version", lambda: package.version)
    request = httpx.Request("GET", "https://pypi.org/")
    fetch = Mock(
        return_value=httpx.Response(200, json={"info": {"version": running}}, request=request)
    )
    monkeypatch.setattr(updater.httpx, "get", fetch)

    checker = updater.UpdateChecker(running_version=running)
    assert checker.check().status is UpdateStatus.CURRENT
    package.version = "2026.11.24.10"
    result = checker.check()
    assert result.status is UpdateStatus.RECONNECT_REQUIRED
    assert result.running_version == running
    assert result.installed_version == package.version
    assert "Reconnect" in result.message
    assert checker.check(refresh=True) == result
    fetch.assert_called_once()


@pytest.mark.parametrize(
    ("installed", "latest", "release_date"),
    [
        ("2026.9.3", "2026.11.4.1", "4 November 2026"),
        ("2026.11.24.post2", "2026.11.24.3", "24 November 2026"),
        ("2026.11.24.1", "2026.11.24.2", "24 November 2026"),
    ],
)
def test_pypi_calendar_update_compares_using_package_versions(
    monkeypatch, installed, latest, release_date
):
    package = SimpleNamespace(version=installed, read_text=lambda _: None)
    monkeypatch.setattr(updater, "distribution", lambda name: package)
    request = httpx.Request("GET", "https://pypi.org/")
    fetch = Mock(
        return_value=httpx.Response(200, json={"info": {"version": latest}}, request=request)
    )
    monkeypatch.setattr(updater.httpx, "get", fetch)
    result = updater.UpdateChecker().check()
    assert result.status is UpdateStatus.AVAILABLE
    assert result.latest_version == latest
    assert f"{latest} ({release_date})" in result.message
    assert fetch.call_args.args == ("https://pypi.org/pypi/snelstart-web-mcp/json",)
    assert version_label("2026.11.4.post1") == "2026.11.4.post1 (4 November 2026)"
