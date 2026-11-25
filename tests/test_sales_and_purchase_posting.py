import asyncio
import json
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError

from snelstart_mcp import sales_attachments, tools_sales
from snelstart_mcp.client import Client
from snelstart_mcp.config import SnelStartError, Store
from snelstart_mcp.server import create_server

ADMIN = "11111111-1111-4111-8111-111111111111"
RECORD = "22222222-2222-4222-8222-222222222222"
SALE = {
    "administration_id": ADMIN,
    "kind": "invoice",
    "customer_code": 73,
    "document_date": "2026-11-25",
    "lines": [{"article_id": 2, "quantity": "2", "unit_price": "10"}],
}
MAIL = {"recipient": "example@example.test", "subject": "Synthetic test", "message": "Test body"}


@pytest.fixture
def flow(tmp_path, monkeypatch):
    store = Store(tmp_path / "profile")
    store.write(
        "config.json",
        {
            "administration_id": ADMIN,
            "allow_writes": True,
            "direct_write_administrations": [ADMIN],
            "write_permissions": {
                ADMIN: ["POST /Invoices/Send", "POST /Quotations/SaveAndSend"],
            },
        },
    )
    replies = {
        "/Administrations/All": [{"id": 1, "identifier": ADMIN}],
        "/Administrations/Open": 0,
        "/Customers/Get": {"id": 7, "relationCode": 73, "paymentTerm": 30},
        "/Articles/GetArticleForCustomer": {"articleId": 2, "name": "Services", "vat": {"id": 2}},
        "/Articles/Get": {"articleId": 2, "name": "Services", "vat": {"id": 2}},
        "/Validation/HasValidCompanySettings": True,
    }
    requests = []

    def handle(request):
        requests.append(request)
        reply = replies[request.url.path]
        return httpx.Response(200, json=reply(request) if callable(reply) else reply)

    with httpx.Client(transport=httpx.MockTransport(handle)) as http:
        client = Client(store, http)
        monkeypatch.setattr(client.auth, "access_token", lambda *_a, **_kw: "synthetic-token")
        yield client, replies, requests


def call(client, name, parameters):
    result = asyncio.run(create_server(client).call_tool(name, parameters))
    return result[1] if isinstance(result, tuple) else json.loads(result[0].text)


def calculate(request):
    payload = json.loads(request.content)
    assert payload["customerId"] == 7
    assert payload["paymentTerm"] == 30
    assert payload["invoiceLines"][0]["sellingPrice"] == 10
    return {
        **payload,
        "invoiceLines": [{**payload["invoiceLines"][0], "totalPrice": 20}],
        "totalExcludingVatBeforeDiscount": 20,
        "totalExcludingVatAfterDiscount": 20,
        "totalIncludingVat": 24.2,
        "invoiceDiscount": 0,
        "totalVat": [{"baseTotal": 20, "vatTotal": 4.2}],
    }


def test_preview_and_save_invoice_keep_totals_and_do_not_send(flow):
    client, replies, requests = flow
    replies["/Invoices/RedetermineVat"] = calculate
    replies["/Invoices/SaveOnly"] = {"status": 5, "invoiceNumber": "0004"}
    preview = call(client, "snelstart_preview_sales_document", SALE)
    assert preview["gross"] == "24.2"
    assert preview["vat_breakdown"] == [{"base": "20", "vat_amount": "4.2"}]
    with pytest.raises(ToolError, match="differs from the approved total"):
        call(client, "snelstart_save_sales_document", {**SALE, "expected_gross": "24.21"})
    result = call(client, "snelstart_save_sales_document", {**SALE, "expected_gross": "24.20"})
    assert result["invoice_number"] == "0004"
    assert all(request.url.path != "/Invoices/Send" for request in requests)
    body = json.loads(requests[-1].content)
    assert "mailAddressTo" not in body
    assert body["invoiceDate"] == "2026-11-25T00:00:00.000Z"


def test_invoice_draft_uses_order_save(flow):
    client, replies, requests = flow
    replies["/Invoices/RedetermineVat"] = calculate
    replies["/Orders/Save"] = {"orderId": 10, "orderNumber": 11}
    result = call(
        client,
        "snelstart_save_sales_document",
        {**SALE, "expected_gross": "24.20", "draft": True},
    )
    assert requests[-1].url.path == "/Orders/Save"
    assert result["draft"] and result["order_number"] == 11 and result["invoice_number"] is None


def test_quotation_email_uploads_only_approved_bytes_and_surfaces_sender_verification(
    flow, tmp_path, monkeypatch
):
    client, replies, requests = flow
    replies["/Quotations/RedetermineVat"] = calculate
    replies["/Attachments/GetAttachmentUploadUriNew"] = "mock-signed-blob"
    fixture = tmp_path / "test.txt"
    fixture.write_bytes(b"synthetic attachment")
    staged = []

    def upload(url, path, data):
        staged.append((url, path, data))
        return "https://storage.test/upload?sig=private"

    def send(request):
        payload = json.loads(request.content)
        assert payload["isConceptOfferte"] is False
        assert payload["mailAddressTo"] == MAIL["recipient"]
        assert payload["mailSubject"] == MAIL["subject"]
        assert payload["mailAddressBcc"] == ""
        assert payload["attachments"] == [
            {
                "uri": "https://storage.test/upload?sig=private",
                "originalFileName": "test.txt",
                "size": len(fixture.read_bytes()),
            }
        ]
        return {"successful": False, "orderNumber": 5, "failureCode": 10}

    monkeypatch.setattr(tools_sales, "upload_attachment", upload)
    replies["/Quotations/SaveAndSend"] = send
    request = {
        **SALE,
        **MAIL,
        "kind": "quotation",
        "expected_gross": "24.20",
        "attachment_paths": [str(fixture)],
    }
    settings = client.store.settings()
    settings.direct_write_administrations.clear()
    client.store.write("config.json", settings.model_dump(mode="json"))
    with pytest.raises(ToolError, match="approval"):
        call(client, "snelstart_email_new_sales_document", request)
    assert not staged
    assert all(r.url.path != "/Attachments/GetAttachmentUploadUriNew" for r in requests)
    pending = client.store.read("write-approvals.json")
    assert sha256(fixture.read_bytes()).hexdigest() in json.dumps(pending)
    settings.direct_write_administrations.add(UUID(ADMIN))
    client.store.write("config.json", settings.model_dump(mode="json"))
    result = call(client, "snelstart_email_new_sales_document", request)
    assert result["outcome"] == "sender_verification_required"
    assert result["order_number"] == 5
    assert "sig" not in json.dumps(result)
    assert staged == [("mock-signed-blob", fixture, fixture.read_bytes())]


def test_read_quotation_search_and_email_history(flow):
    client, replies, requests = flow
    replies["/Quotations/Search"] = {"totalMatchCount": 1, "resultList": [{"identifier": RECORD}]}
    replies["/Mail/Search"] = {
        "totalMatchCount": 1,
        "resultList": [
            {
                "addressTo": MAIL["recipient"],
                "subject": MAIL["subject"],
                "text": "private",
                "mailStatusCode": 4,
                "attachments": [{"name": "test.txt", "originalSizeInBytes": 20}],
            }
        ],
    }
    assert (
        call(client, "snelstart_search_quotations", {"status": "draft"})["data"]["totalMatchCount"]
        == 1
    )
    assert requests[-1].url.params["statusFilter"] == "3"
    entry = call(client, "snelstart_sent_email_history", {"status": "delivered"})["messages"][0]
    assert requests[-1].url.params["mailStatusSearchType"] == "4"
    assert entry["status_code"] == 4
    assert entry["attachments"][0]["size_bytes"] == 20
    assert "private" not in json.dumps(entry)
    assert "status_code" in entry


@pytest.mark.parametrize(
    ("kind", "band", "function", "vat_box"),
    [
        ("domestic_reverse_charge", None, 32, "2a"),
        ("intra_eu", "high", 62, "4b"),
        ("outside_eu", "low", 71, "4a"),
        ("payment_discount", None, 102, None),
    ],
)
def test_purchase_check_validates_account_function_and_cost_centre(
    flow, kind, band, function, vat_box
):
    client, replies, requests = flow
    row = {
        "grootboekId": 7,
        "grootboekNumber": 7000,
        "grootboekDescription": "Fixture",
        "grootboekfunctieId": function,
        "publicIdentifier": RECORD,
        "kostenplaatsInstelling": 2,
    }
    replies["/Grootboek/GetGrootboekByNumber"] = row
    request = {"administration_id": ADMIN, "kind": kind, "account_number": 7000, "vat_band": band}
    if kind == "payment_discount":
        request.update({"invoice_total": "121", "paid_amount": "117.37"})
    result = call(client, "snelstart_check_purchase_posting", request)
    assert result["account_matches_workflow"]
    assert result["expected_vat_box"] == vat_box
    assert result["cost_centre_requirement"] == "required"
    assert not result["cost_centre_input_matches_account"]
    assert result["payment_discount"] == ("3.63" if kind == "payment_discount" else None)
    assert requests[-1].method == "GET"


def test_sales_storage_rejects_wrong_destination_and_symlink(tmp_path):
    fixture = tmp_path / "test.txt"
    fixture.write_bytes(b"test")
    for url in (
        "https://unrelated.test/bestanden-20261125-1-2/id_test.txt?sig=1&sp=w",
        f"https://{sales_attachments.STORAGE_HOST}/other/id_test.txt?sig=1&sp=w",
        f"https://{sales_attachments.STORAGE_HOST}/bestanden-20261125-1-2/id_other.txt?sig=1&sp=w",
    ):
        with pytest.raises(SnelStartError, match="unexpected .* upload destination"):
            sales_attachments.upload_attachment(url, fixture, fixture.read_bytes())
    link = Path(tmp_path / "link.txt")
    link.symlink_to(fixture)
    with pytest.raises(OSError):
        sales_attachments.read_attachment(link, 100)


def test_purchase_evidence_matches_ledger_when_chart_omits_its_uuid(flow):
    client, replies, _ = flow
    replies["/Grootboek/GetGrootboekByNumber"] = {
        "grootboekId": 7,
        "grootboekNumber": 7011,
        "grootboekDescription": "EU high",
        "grootboekfunctieId": 62,
        "publicIdentifier": str(UUID(int=0)),
        "kostenplaatsInstelling": 0,
    }
    replies["/Purchases/Get"] = {
        "publicIdentifier": RECORD,
        "boekingsregels": [
            {"grootboekId": 7, "grootboekIdentifier": ADMIN, "bedrag": 10},
            {"grootboekId": 8, "bedrag": 5},
        ],
        "btw": [],
    }
    result = call(
        client,
        "snelstart_check_purchase_posting",
        {
            "administration_id": ADMIN,
            "kind": "intra_eu",
            "vat_band": "high",
            "account_number": 7011,
            "purchase_id": RECORD,
        },
    )
    assert result["account_id"] is None
    assert result["purchase_evidence"]["matching_lines"] == [
        {"grootboekIdentifier": ADMIN, "bedrag": 10},
    ]
    assert result["purchase_evidence"]["vat_lines"] == []
