"""Receive the registered SnelStart Web callback in a temporary Chrome window."""

import asyncio
import base64
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

from .config import SnelStartError
from .enums import BrowserStatus
from .models.responses import BrowserCheck

if TYPE_CHECKING:
    from playwright.async_api import Browser, Playwright

CALLBACK_HOST = "web.snelstart.nl"
CALLBACK_PATHS = {"", "/"}
SIGN_IN_TIMEOUT = 300
LAUNCH_CHECK_TIMEOUT = 8


async def _launch_chrome(playwright: "Playwright", *, timeout: int | None = None) -> "Browser":
    return await playwright.chromium.launch(
        channel="chrome", headless=False, chromium_sandbox=True, timeout=timeout
    )


def _chrome_detected() -> bool:
    # Playwright looks for the stable Chrome channel at these standard locations.
    if sys.platform == "darwin":
        chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    elif sys.platform == "linux":
        chrome = Path("/opt/google/chrome/chrome")
    else:
        return False
    return chrome.is_file() and os.access(chrome, os.X_OK)


def check_browser(*, launch: bool) -> BrowserCheck:
    try:
        from playwright.async_api import Error, async_playwright
    except ImportError:
        return BrowserCheck(
            status=BrowserStatus.MISSING_EXTRA,
            message="Install the browser extra to enable Chrome sign-in.",
        )

    if not launch:
        if _chrome_detected():
            return BrowserCheck(
                status=BrowserStatus.DETECTED,
                message="Google Chrome detected. Run doctor --check-browser to test launch.",
            )
        return BrowserCheck(
            status=BrowserStatus.CHROME_NOT_FOUND,
            message="Google Chrome was not found in the standard location.",
        )

    async def probe() -> None:
        async with asyncio.timeout(LAUNCH_CHECK_TIMEOUT):
            async with async_playwright() as playwright:
                browser = await _launch_chrome(playwright, timeout=LAUNCH_CHECK_TIMEOUT * 1000)
                await browser.close()

    try:
        asyncio.run(probe())
    except (Error, OSError, TimeoutError):
        if not _chrome_detected():
            return BrowserCheck(
                status=BrowserStatus.CHROME_NOT_FOUND,
                message="Chrome could not launch. Install Google Chrome in the standard location.",
            )
        return BrowserCheck(
            status=BrowserStatus.LAUNCH_FAILED,
            message="Chrome could not launch. Run this command from a graphical desktop session.",
        )
    return BrowserCheck(status=BrowserStatus.READY, message="Google Chrome opened and closed.")


def is_web_callback(url: str) -> bool:
    target = urlsplit(url)
    return (
        target.scheme == "https"
        and target.netloc == CALLBACK_HOST
        and target.path in CALLBACK_PATHS
        and not target.fragment
    )


def open_browser_callback(authorization_url: str) -> str:
    try:
        from playwright.async_api import Error, async_playwright
    except ImportError:
        raise SnelStartError(
            "Browser sign-in requires the browser extra. Run 'uv sync --frozen --extra browser'."
        ) from None

    async def authorize() -> str:
        async with async_playwright() as playwright:
            browser = await _launch_chrome(playwright)
            try:
                page = await browser.new_page()
                session = await page.context.new_cdp_session(page)
                frame = (await session.send("Page.getFrameTree"))["frameTree"]["frame"]["id"]
                callback = asyncio.get_running_loop().create_future()

                async def receive(event):
                    url = event["request"]["url"]
                    command = {"requestId": event["requestId"]}
                    query = parse_qs(urlsplit(url).query, keep_blank_values=True)
                    if (
                        event["frameId"] == frame
                        and event["request"]["method"] == "GET"
                        and is_web_callback(url)
                        and {"code", "error"} & query.keys()
                    ):
                        # Finish the navigation locally before the web app can consume the code.
                        await session.send(
                            "Fetch.fulfillRequest",
                            {
                                **command,
                                "responseCode": 200,
                                "responseHeaders": [
                                    {"name": "Content-Type", "value": "text/plain; charset=utf-8"},
                                    {"name": "Cache-Control", "value": "no-store"},
                                ],
                                "body": base64.b64encode(
                                    b"Return to the SnelStart MCP terminal."
                                ).decode(),
                            },
                        )
                        if not callback.done():
                            callback.set_result(url)
                    else:
                        await session.send("Fetch.continueRequest", command)

                def window_closed(_page):
                    if not callback.done():
                        callback.set_result(None)

                page.on("close", window_closed)
                session.on("Fetch.requestPaused", receive)
                await session.send(
                    "Fetch.enable",
                    {
                        "patterns": [
                            {"urlPattern": f"https://{CALLBACK_HOST}/*", "resourceType": "Document"}
                        ]
                    },
                )
                async with asyncio.timeout(SIGN_IN_TIMEOUT):
                    await page.goto(authorization_url, wait_until="commit")
                    result = await callback
                if result is None:
                    raise SnelStartError("The browser window closed before sign-in completed.")
                return result
            finally:
                await browser.close()

    try:
        return asyncio.run(authorize())
    except TimeoutError:
        raise SnelStartError("The browser sign-in timed out.") from None
    except Error:
        raise SnelStartError(
            "Could not finish browser sign-in. Make sure Google Chrome is installed."
        ) from None
