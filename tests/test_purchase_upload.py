import asyncio
import json
from hashlib import sha256

import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError

from snelstart_mcp import purchase_upload
from snelstart_mcp.client import Client
from snelstart_mcp.config import Store
from snelstart_mcp.server import create_server

ADMIN = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
PDF = b"%PDF-1.5\nsynthetic invoice\n%%EOF\n"
INSTANCE = "fixture-processing-id"
URI_PATH = "/bestanden-20260115-123-456/document.pdf"
DESTINATION = f"https://{purchase_upload.STORAGE_HOST}{URI_PATH}"
SIGNED_QUERY = "sp=w&sr=b&sig=private-fixture-signature"
OPERATIONS = [purchase_upload.UPLOAD_URL, purchase_upload.SUBMIT_PURCHASE]
UPLOAD_PATH = purchase_upload.UPLOAD_URL.split(" ", 1)[1]
SUBMISSION_PATH = purchase_upload.SUBMIT_PURCHASE.split(" ", 1)[1]
STATUS_PATH = purchase_upload.UPLOAD_STATUS.split(" ", 1)[1]


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    profile = Store(tmp_path / "profile")
    profile.write(
        "config.json", {"administration_id": ADMIN, "write_permissions": {ADMIN: OPERATIONS}}
    )
    file = tmp_path / "purchase invoice.pdf"
    file.write_bytes(PDF)
    api_calls = []
    storage_calls = []
    replies = {
        UPLOAD_PATH: f"{DESTINATION}?{SIGNED_QUERY}",
        SUBMISSION_PATH: {"instanceId": INSTANCE},
        STATUS_PATH: {"status": "Completed"},
    }

    def handle(request):
        assert request.url.host == "webapi.snelstart.nl"
        if request.url.path == "/Administrations/All":
            return httpx.Response(200, json=[{"id": 1, "identifier": ADMIN}])
        if request.url.path == "/Administrations/Open":
            return httpx.Response(200, json=0)
        api_calls.append(request)
        reply = replies[request.url.path]
        if isinstance(reply, httpx.Response):
            return reply
        return httpx.Response(200, json=reply)

    class StorageResponse:
        status = 201

        def close(self):
            pass

    class Storage:
        def __init__(self, host, *, timeout):
            assert host == purchase_upload.STORAGE_HOST

        def request(self, method, url, *, body, headers):
            storage_calls.append((method, url, body, headers))

        def getresponse(self):
            return StorageResponse()

        def close(self):
            pass

    monkeypatch.setattr(purchase_upload, "HTTPSConnection", Storage)
    with httpx.Client(transport=httpx.MockTransport(handle)) as http:
        client = Client(profile, http)
        monkeypatch.setattr(client.auth, "access_token", lambda *a, **kw: "api-fixture-token")
        server = create_server(client)

        def call(tool="snelstart_upload_purchase_pdf", **arguments):
            defaults = {"administration_id": ADMIN}
            if tool == "snelstart_upload_purchase_pdf":
                defaults["file_path"] = str(file)
            result = asyncio.run(server.call_tool(tool, defaults | arguments))
            return result[1] if isinstance(result, tuple) else json.loads(result[0].text)

        yield call, profile, file, api_calls, storage_calls, replies, StorageResponse


def test_submit_and_track_a_pdf_without_exposing_the_signed_url(workflow):
    call, profile, file, api, storage, _, _ = workflow
    result = call()
    assert result == {
        "instance_id": INSTANCE,
        "sha256": sha256(PDF).hexdigest(),
        "already_submitted": False,
    }
    assert [(req.method, req.url.path) for req in api] == [
        ("GET", UPLOAD_PATH),
        ("POST", SUBMISSION_PATH),
    ]
    assert api[0].url.params["filename"] == file.name
    assert api[1].url.params["pathUrl"] == DESTINATION
    assert not api[1].content
    assert storage == [
        (
            "PUT",
            f"{URI_PATH}?{SIGNED_QUERY}",
            PDF,
            {
                "Content-Type": "application/pdf",
                "If-None-Match": "*",
                "x-ms-blob-type": "BlockBlob",
            },
        )
    ]
    assert call() == {**result, "already_submitted": True}
    assert len(api) == 2 and len(storage) == 1
    receipts = (profile.directory / purchase_upload.RECEIPTS).read_text()
    assert "private-fixture-signature" not in receipts
    assert "api-fixture-token" not in receipts

    profile.write("config.json", {"administration_id": ADMIN, "allow_writes": False})
    assert call("snelstart_purchase_upload_status", instance_id=INSTANCE) == {
        "instance_id": INSTANCE,
        "status": "Completed",
    }
    assert api[-1].method == "GET" and api[-1].url.params["instanceId"] == INSTANCE


def test_upload_requires_the_selected_administration_and_both_permissions(workflow):
    call, profile, _, api, storage, _, _ = workflow
    with pytest.raises(ToolError, match="Select the specified administration"):
        call(administration_id=OTHER)
    profile.write(
        "config.json", {"administration_id": ADMIN, "write_permissions": {ADMIN: OPERATIONS[:1]}}
    )
    with pytest.raises(ToolError, match="Writing is disabled"):
        call()
    assert api == storage == []


def test_non_pdf_is_rejected_before_network(workflow):
    call, _, file, api, storage, _, _ = workflow
    file.write_bytes(b"HTML page")
    with pytest.raises(ToolError, match="no PDF header"):
        call()
    assert api == storage == []


def test_a_permission_change_during_storage_stops_purchase_submission(workflow, monkeypatch):
    call, profile, _, api, storage, _, response = workflow
    original_close = response.close

    def revoke(self):
        original_close(self)
        profile.write("config.json", {"administration_id": ADMIN, "allow_writes": False})

    monkeypatch.setattr(response, "close", revoke)
    with pytest.raises(ToolError, match="Writing is disabled"):
        call()
    assert [req.url.path for req in api] == [UPLOAD_PATH]
    assert len(storage) == 1
    assert profile.read(purchase_upload.RECEIPTS) == {}


@pytest.mark.parametrize(
    "url",
    [
        f"http://{purchase_upload.STORAGE_HOST}{URI_PATH}?{SIGNED_QUERY}",
        f"https://{purchase_upload.STORAGE_HOST}.example.test{URI_PATH}?{SIGNED_QUERY}",
        f"https://{purchase_upload.STORAGE_HOST}@example.test{URI_PATH}?{SIGNED_QUERY}",
        f"{DESTINATION}?sp=w",
    ],
)
def test_untrusted_storage_target_is_never_used(workflow, url):
    call, _, _, api, storage, replies, _ = workflow
    replies[UPLOAD_PATH] = url
    with pytest.raises(ToolError, match="unexpected PDF upload destination"):
        call()
    assert [req.url.path for req in api] == [UPLOAD_PATH]
    assert storage == []


def test_blob_redirect_stops_before_creating_a_purchase_and_can_be_retried(workflow):
    call, _, _, api, storage, _, response = workflow
    response.status = 307
    with pytest.raises(ToolError, match="HTTP 307"):
        call()
    assert [req.url.path for req in api] == [UPLOAD_PATH]
    assert len(storage) == 1
    response.status = 201
    assert call()["instance_id"] == INSTANCE


@pytest.mark.parametrize("reply", [httpx.Response(503), {}])
def test_an_unconfirmed_submission_cannot_be_repeated(workflow, reply):
    call, _, _, api, storage, replies, _ = workflow
    replies[SUBMISSION_PATH] = reply
    with pytest.raises(ToolError, match="Could not confirm the purchase submission"):
        call()
    with pytest.raises(ToolError, match="unresolved submission"):
        call()
    assert [req.url.path for req in api] == [UPLOAD_PATH, SUBMISSION_PATH]
    assert len(storage) == 1
