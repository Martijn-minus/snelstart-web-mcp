"""Receive the registered SnelStart Web callback in a temporary Chrome window."""

import asyncio
import base64
from urllib.parse import parse_qs, urlsplit

from .config import SnelStartError

CALLBACK_HOST = "web.snelstart.nl"
CALLBACK_PATHS = {"", "/"}
SIGN_IN_TIMEOUT = 300


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
            browser = await playwright.chromium.launch(
                channel="chrome", headless=False, chromium_sandbox=True
            )
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
