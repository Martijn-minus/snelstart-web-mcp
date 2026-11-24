import sys
from contextlib import asynccontextmanager

import pytest

from snelstart_mcp import browser_login
from snelstart_mcp.enums import BrowserStatus


def test_browser_check_reports_a_missing_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "playwright.async_api", None)
    assert browser_login.check_browser(launch=True).status is BrowserStatus.MISSING_EXTRA


@pytest.mark.parametrize("detected", [False, True])
def test_default_browser_check_only_detects_chrome(monkeypatch, detected):
    playwright = pytest.importorskip("playwright.async_api")
    monkeypatch.setattr(browser_login, "_chrome_detected", lambda: detected)
    monkeypatch.setattr(playwright, "async_playwright", lambda: pytest.fail("Chrome was launched"))
    expected = BrowserStatus.DETECTED if detected else BrowserStatus.CHROME_NOT_FOUND
    assert browser_login.check_browser(launch=False).status is expected


@pytest.mark.parametrize("launch_fails", [False, True])
def test_browser_launch_probe_uses_the_sign_in_channel_and_closes_it(monkeypatch, launch_fails):
    playwright = pytest.importorskip("playwright.async_api")
    calls = []

    class Chrome:
        async def launch(self, **options):
            calls.append(options)
            if launch_fails:
                raise playwright.Error("do not show browser driver output")
            return self

        async def close(self):
            calls.append("closed")

    @asynccontextmanager
    async def driver():
        yield type("Playwright", (), {"chromium": Chrome()})

    monkeypatch.setattr(playwright, "async_playwright", driver)
    monkeypatch.setattr(browser_login, "_chrome_detected", lambda: True)
    report = browser_login.check_browser(launch=True)
    assert calls[0] == {
        "channel": "chrome",
        "headless": False,
        "chromium_sandbox": True,
        "timeout": browser_login.LAUNCH_CHECK_TIMEOUT * 1000,
    }
    if launch_fails:
        assert report.status is BrowserStatus.LAUNCH_FAILED
        assert "driver output" not in report.message
    else:
        assert report.status is BrowserStatus.READY and calls[1:] == ["closed"]
