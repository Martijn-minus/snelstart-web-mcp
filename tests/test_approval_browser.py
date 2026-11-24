import asyncio
from contextlib import suppress
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
import pytest

from snelstart_mcp import approval, approval_browser
from snelstart_mcp.client import Client
from snelstart_mcp.config import SnelStartError, Store
from snelstart_mcp.enums import WriteApprovalStatus
from snelstart_mcp.models.approval import WriteIntent
from snelstart_mcp.server import create_server

ADMIN = UUID("11111111-1111-4111-8111-111111111111")
CREATE = "POST /MemoriaalBoekingen/Create"


def _prepare(store, number):
    intent = WriteIntent(
        tool="snelstart_write",
        operation=CREATE,
        administration_id=ADMIN,
        details={"number": number, "description": "Amount < review threshold"},
    )
    before = set(store.read(approval.FILE))
    with pytest.raises(SnelStartError, match="Local confirmation required"):
        approval.require_approval(store, intent, None)
    (identifier,) = set(store.read(approval.FILE)) - before
    return UUID(identifier), intent


@pytest.fixture
def profile(tmp_path, monkeypatch):
    store = Store(tmp_path)
    store.write("config.json", {"administration_id": str(ADMIN), "allow_writes": True})
    opened = []

    def fake_browser(url):
        opened.append(url)
        return True

    monkeypatch.setattr(approval_browser, "_open_local_browser", fake_browser)
    with httpx.Client(trust_env=False, timeout=2) as browser:
        try:
            yield store, browser, opened
        finally:
            for url in opened:
                with suppress(httpx.HTTPError):
                    browser.post(url, headers=_origin(url), data={"action": "cancel"})
    assert approval_browser.REVIEW_SLOT.acquire(timeout=3)
    approval_browser.REVIEW_SLOT.release()


def _origin(url):
    return {"Origin": f"http://{urlsplit(url).netloc}"}


def test_mcp_opens_exact_batch_and_local_browser_approves_only_selected_requests(profile):
    store, browser, opened = profile
    first, intent = _prepare(store, 1)
    second, _ = _prepare(store, 2)
    third, _ = _prepare(store, 3)
    args = {"approval_ids": [str(first), str(second)]}

    def fail_api(_):
        pytest.fail("Preparing, reviewing and checking approvals must stay local.")

    async def exercise():
        with httpx.Client(transport=httpx.MockTransport(fail_api)) as http:
            server = create_server(Client(store, http))
            _, review = await server.call_tool("snelstart_open_write_review", args)
            assert review["approval_ids"] == args["approval_ids"]
            (url,) = opened
            assert url not in repr(review)

            rendered = browser.get(url)
            assert rendered.status_code == 200
            assert rendered.headers["cache-control"] == "no-store"
            assert "frame-ancestors 'none'" in rendered.headers["content-security-policy"]
            assert "Amount &lt; review threshold" in rendered.text
            assert str(first) in rendered.text and str(second) in rendered.text
            assert str(third) not in rendered.text
            assert " checked" not in rendered.text

            _, initial_states = await server.call_tool("snelstart_write_approval_status", args)
            assert [item["status"] for item in initial_states["data"]] == ["pending", "pending"]
            settled = browser.post(
                url, headers=_origin(url), data={"action": "approve", "approval": str(first)}
            )
            assert settled.status_code == 200
            assert "Approved 1 of 2 requests" in settled.text
            _, states = await server.call_tool("snelstart_write_approval_status", args)
            assert [item["status"] for item in states["data"]] == ["approved", "pending"]

    asyncio.run(exercise())
    with pytest.raises(SnelStartError, match="no matching"):
        approval.require_approval(
            store, intent.model_copy(update={"details": {"number": 9}}), first
        )
    approval.require_approval(store, intent, first)
    assert (
        approval.write_approval_states(store, [first])[0].status is WriteApprovalStatus.UNAVAILABLE
    )
    with pytest.raises(SnelStartError, match="no matching"):
        approval.require_approval(store, intent, first)


def test_browser_rejects_wrong_origin_unknown_requests_and_cancellation(profile):
    store, browser, opened = profile
    identifier, _ = _prepare(store, 1)
    _, thread = approval_browser.open_write_review(store, [identifier])
    (url,) = opened
    assert browser.get(url.rsplit("/", 1)[0] + "/wrong").status_code == 404
    assert browser.get(url, headers={"Host": "unexpected.invalid"}).status_code == 404

    proposed = {"action": "approve", "approval": str(identifier)}
    assert (
        browser.post(
            url, headers={"Origin": "https://unexpected.invalid"}, data=proposed
        ).status_code
        == 403
    )
    invalid = browser.post(url, headers=_origin(url), data=proposed | {"approval": str(uuid4())})
    assert invalid.status_code == 400
    assert browser.post(url, headers=_origin(url), data={"action": "approve"}).status_code == 400
    assert browser.post(url, headers=_origin(url), data={"action": "cancel"}).status_code == 200
    thread.join(2)
    assert not thread.is_alive()
    assert (
        approval.write_approval_states(store, [identifier])[0].status is WriteApprovalStatus.PENDING
    )


def test_changed_or_expired_request_prevents_any_selection_being_approved(profile):
    store, browser, opened = profile
    first, _ = _prepare(store, 1)
    second, _ = _prepare(store, 2)
    approval_browser.open_write_review(store, [first, second])
    (url,) = opened
    records = store.read(approval.FILE)
    records[str(second)]["intent"]["details"]["number"] = 3
    store.write(approval.FILE, records)
    response = browser.post(
        url,
        headers=_origin(url),
        data={"action": "approve", "approval": [str(first), str(second)]},
    )
    assert response.status_code == 409
    assert all(
        state.status is WriteApprovalStatus.PENDING
        for state in approval.write_approval_states(store, [first, second])
    )


def test_review_tools_absent_when_server_is_read_only(tmp_path):
    server = create_server(Client(Store(tmp_path), read_only=True))
    names = {tool.name for tool in asyncio.run(server.list_tools())}
    assert "snelstart_open_write_review" not in names
    assert "snelstart_write_approval_status" not in names
