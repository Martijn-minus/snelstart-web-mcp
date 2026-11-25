import asyncio
import hashlib
import json
from zipfile import ZipFile

import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError

from snelstart_mcp import financial_review
from snelstart_mcp.backup import ARCHIVE_FORMAT, LEGACY_ARCHIVE
from snelstart_mcp.client import Client
from snelstart_mcp.config import Store
from snelstart_mcp.server import create_server

ADMIN = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
BANK = "33333333-3333-4333-8333-333333333333"
BANK2 = "44444444-4444-4444-8444-444444444444"
BOOKING = "55555555-5555-4555-8555-555555555555"
INVOICE = "66666666-6666-4666-8666-666666666666"


@pytest.fixture
def app(tmp_path, monkeypatch):
    store = Store(tmp_path / "profile")
    store.write("config.json", {"administration_id": ADMIN, "allow_writes": True})
    seen = []
    handlers = {
        "/Administrations/All": [{"id": 1, "identifier": ADMIN}],
        "/Administrations/Open": 0,
    }

    def reply(request):
        seen.append(request)
        item = handlers[request.url.path]
        if callable(item):
            item = item(request)
        return item if isinstance(item, httpx.Response) else httpx.Response(200, json=item)

    with httpx.Client(transport=httpx.MockTransport(reply)) as http:
        client = Client(store, http)
        monkeypatch.setattr(client.auth, "access_token", lambda *_args, **_kwargs: "fixture")
        server = create_server(client)

        def call(name, arguments=None):
            result = asyncio.run(server.call_tool(name, arguments or {}))
            return result[1] if isinstance(result, tuple) else json.loads(result[0].text)

        yield call, store, handlers, seen


def page(*rows, total=None):
    return {"resultList": list(rows), "totalMatchCount": len(rows) if total is None else total}


def test_bulk_entry_outcomes_keep_identity_and_distinguish_incomplete_reads(app, monkeypatch):
    call, _, handlers, _ = app
    monkeypatch.setattr(financial_review, "MAX_BATCH_BYTES", 100)
    handlers.update(
        {
            "/MemoriaalBoekingen/GetDetails": {"publicIdentifier": BOOKING},
            "/KasBankBoeking/GetKasBankboekingDetails": httpx.Response(404),
            "/BalansBoekingen/GetDetails": httpx.Response(503),
            "/Purchases/Get": {"description": "a" * 200},
        }
    )
    entries = [
        {"kind": kind, "entry_id": BOOKING}
        for kind in ("journal", "bank", "opening_balance", "purchase")
    ]
    result = call("snelstart_get_entries", {"entries": entries})
    assert result["administration_id"] == ADMIN and result["complete"] is False
    assert [row["status"] for row in result["entries"]] == [
        "found",
        "missing",
        "failed",
        "too_large",
    ]
    assert all(row["entry_id"] == BOOKING for row in result["entries"])
    assert result["entries"][0]["details"] == {"publicIdentifier": BOOKING}
    assert result["entries"][3]["details"] is None


@pytest.mark.parametrize("bulk", [False, True])
def test_bank_detail_http_500_exposes_verified_list_evidence_separately(app, bulk):
    call, _, handlers, seen = app
    details = "/KasBankBoeking/GetKasBankboekingDetails"
    listing = "/KasBankBoeking/GetKasBankBoekingenWithTimespan"
    context = {"journal_id": BANK, "booking_date": "2026-01-02"}
    matched = {
        "identifier": BOOKING,
        "date": "2026-01-01T23:15:00Z",
        "invoiceKoppelingen": [{"invoiceIdentifier": INVOICE}],
    }
    handlers[details] = httpx.Response(500, json={"private": "fixture"})

    def list_entries(request):
        params = request.url.params
        assert params["grootboekIdentifier"] == BANK
        assert params["vanaf"].startswith("2025-12-31T23:00")
        assert params["totEnMet"].startswith("2026-01-03T22:59")
        if params["skip"] == "0":
            return page({"identifier": OTHER, "date": "2026-01-02"}, total=2)
        assert params["skip"] == "1"
        return page(matched, total=2)

    handlers[listing] = list_entries
    ref = {"kind": "bank", "entry_id": BOOKING, "bank_list_context": context}
    if bulk:
        result = call("snelstart_get_entries", {"entries": [ref]})
        assert result["complete"] is False
        (entry,) = result["entries"]
        assert entry["status"] == "failed" and entry["details"] is None
    else:
        entry = call("snelstart_get_entry", ref)
        assert entry["data"] is None
    assert entry["failure_code"] == "bank_detail_unavailable"
    assert entry["bank_list_evidence"] == context | {"entry": matched}
    assert "HTTP 500" in entry["reason"] and "private" not in entry["reason"]
    assert [request.url.path for request in seen if request.method == "GET"][-3:] == [
        details,
        listing,
        listing,
    ]


def test_bank_detail_http_500_never_returns_another_booking(app):
    call, _, handlers, _ = app
    handlers["/KasBankBoeking/GetKasBankboekingDetails"] = httpx.Response(500)
    handlers["/KasBankBoeking/GetKasBankBoekingenWithTimespan"] = page(
        {"identifier": OTHER, "date": "2026-01-02"},
        {"identifier": BOOKING, "date": "2026-01-03"},
    )
    ref = {"kind": "bank", "entry_id": BOOKING}
    with pytest.raises(ToolError, match="Provide bank_list_context"):
        call("snelstart_get_entry", ref)
    ref["bank_list_context"] = {"journal_id": BANK, "booking_date": "2026-01-02"}
    result = call("snelstart_get_entries", {"entries": [ref]})
    assert result["complete"] is False
    (entry,) = result["entries"]
    assert entry["status"] == "failed" and entry["details"] is None
    assert entry["failure_code"] == "bank_detail_unavailable"
    assert "No unique matching booking ID" in entry["reason"]
    assert "bank_list_evidence" not in entry


def test_successful_bank_detail_does_not_query_the_list(app):
    call, _, handlers, _ = app
    detail = {"identifier": BOOKING}
    handlers["/KasBankBoeking/GetKasBankboekingDetails"] = detail
    ref = {
        "kind": "bank",
        "entry_id": BOOKING,
        "bank_list_context": {"journal_id": BANK, "booking_date": "2026-01-02"},
    }
    assert call("snelstart_get_entry", ref) == {"data": detail}


def test_batch_checks_journal_attachments_even_when_detail_flag_is_false(app):
    call, _, handlers, seen = app
    journal_attachments = "/MemoriaalBoekingen/GetAttachments"
    purchase_attachments = "/Purchases/GetAttachmentsWithIdentifier"
    bank_attachments = "/KasBankBoeking/GetAttachments"
    detail = {"publicIdentifier": BOOKING, "hasBijlagen": False}
    handlers.update(
        {
            "/MemoriaalBoekingen/GetDetails": detail,
            "/Purchases/Get": {"publicIdentifier": BOOKING},
            "/KasBankBoeking/GetKasBankboekingDetails": {"identifier": BOOKING},
            "/BalansBoekingen/GetDetails": {"publicIdentifier": BOOKING},
            journal_attachments: [
                {
                    "publicIdentifier": INVOICE,
                    "name": "evidence.pdf",
                    "originalSizeInBytes": 0,
                    "createdOn": "0001-01-01T00:00:00",
                    "thumbnailUrl": "private-fixture",
                }
            ],
            purchase_attachments: [],
            bank_attachments: [],
        }
    )
    request = {
        "entries": [
            {"kind": kind, "entry_id": BOOKING}
            for kind in ("journal", "purchase", "bank", "opening_balance")
        ]
    }
    default = call("snelstart_get_entries", request)
    assert all("attachments" not in row for row in default["entries"])

    checked = call("snelstart_get_entries", request | {"include_attachments": True})
    assert checked["complete"] is True
    journal, purchase, bank, opening = checked["entries"]
    assert journal["details"] == detail
    assert journal["attachments"] == [
        {
            "attachmentIdentifier": INVOICE,
            "fileName": "evidence.pdf",
            "size": 0,
            "createdOn": "0001-01-01T00:00:00",
        }
    ]
    assert purchase["attachments"] == bank["attachments"] == []
    assert "attachments" not in opening
    assert [
        (request.url.path, dict(request.url.params))
        for request in seen
        if request.url.path in (journal_attachments, purchase_attachments, bank_attachments)
    ] == [
        (journal_attachments, {"publicIdentifier": BOOKING}),
        (purchase_attachments, {"journaalpostIdentifier": BOOKING}),
        (bank_attachments, {"journaalpostIdentifier": BOOKING}),
    ]


@pytest.mark.parametrize("response", [httpx.Response(404), [{"publicIdentifier": INVOICE}]])
def test_batch_retains_details_when_attachment_lookup_is_incomplete(app, monkeypatch, response):
    call, _, handlers, _ = app
    monkeypatch.setattr(financial_review, "MAX_BATCH_BYTES", 60)
    detail = {"publicIdentifier": BOOKING}
    handlers["/MemoriaalBoekingen/GetDetails"] = detail
    handlers["/MemoriaalBoekingen/GetAttachments"] = response
    result = call(
        "snelstart_get_entries",
        {
            "entries": [{"kind": "journal", "entry_id": BOOKING}],
            "include_attachments": True,
        },
    )
    assert result["complete"] is False
    (booking,) = result["entries"]
    assert booking["status"] == "found" and booking["details"] == detail
    assert "attachments" not in booking
    expected = "HTTP 404" if isinstance(response, httpx.Response) else "snelstart_list_attachments"
    assert expected in booking["attachment_lookup_error"]


def _bank_sources(handlers, entries):
    handlers["/KasBankBoeking/GetKasEnBankDagboeken"] = [
        {"grootboekIdentifier": BANK, "numberOfGemarkeerd": 3},
        {"grootboekIdentifier": BANK2, "numberOfGemarkeerd": 0},
    ]

    def bank(request):
        params = request.url.params
        assert params["take"] == "100"
        rows = entries[params["grootboekIdentifier"]]
        skip = int(params["skip"])
        return page(*rows[skip : skip + 1], total=len(rows))

    handlers["/KasBankBoeking/GetKasBankBoekingenWithTimespan"] = bank


@pytest.mark.parametrize("tool", ["snelstart_get_entry", "snelstart_get_entries"])
def test_purchase_detail_retries_by_invoice_only_when_ids_match(app, tool):
    call, _, handlers, seen = app
    primary = "/Purchases/Get"
    alternate = "/Purchases/GetByFactuurNummerIdentifier"
    handlers[primary] = httpx.Response(400)
    detail = {
        "publicIdentifier": BOOKING,
        "factuurNummerIdentifier": INVOICE,
        "boekingsregels": [{"omschrijving": "fixture"}],
    }
    handlers[alternate] = detail
    ref = {"entry_id": BOOKING, "kind": "purchase", "purchase_invoice_id": INVOICE}
    result = call(tool, ref if tool == "snelstart_get_entry" else {"entries": [ref]})
    if tool == "snelstart_get_entry":
        assert result["data"] == detail
    else:
        assert result["complete"] is True
        assert result["entries"][0]["details"] == detail
        assert result["entries"][0]["entry_id"] == BOOKING
    reads = [request for request in seen if request.url.path in {primary, alternate}]
    assert [(request.url.path, dict(request.url.params)) for request in reads] == [
        (primary, {"journaalpostIdentifier": BOOKING}),
        (alternate, {"factuurNummerIdentifier": INVOICE}),
    ]


@pytest.mark.parametrize(
    ("invoice_id", "detail", "reason"),
    [
        (None, None, "from the same row"),
        (
            INVOICE,
            {"publicIdentifier": OTHER, "factuurNummerIdentifier": INVOICE},
            "did not verify both identifiers",
        ),
        (
            INVOICE,
            {"publicIdentifier": BOOKING, "factuurNummerIdentifier": OTHER},
            "did not verify both identifiers",
        ),
    ],
)
def test_purchase_detail_reports_a_rejection_without_exposing_unverified_details(
    app, invoice_id, detail, reason
):
    call, _, handlers, seen = app
    primary = "/Purchases/Get"
    alternate = "/Purchases/GetByFactuurNummerIdentifier"
    handlers[primary] = httpx.Response(400, json={"private": "fixture"})
    handlers[alternate] = detail
    ref = {"entry_id": BOOKING, "kind": "purchase", "purchase_invoice_id": invoice_id}
    batch = call("snelstart_get_entries", {"entries": [ref]})
    assert batch["complete"] is False
    (entry,) = batch["entries"]
    assert entry["status"] == "failed"
    assert entry["failure_code"] == "purchase_detail_rejected"
    assert entry["details"] is None
    assert "HTTP 400" in entry["reason"] and reason in entry["reason"]
    assert "private" not in entry["reason"]
    assert any(request.url.path == alternate for request in seen) == (invoice_id is not None)


def test_checked_bank_export_retains_markings_and_cleans_partial_file(app):
    call, store, handlers, seen = app
    linked = {
        "identifier": BOOKING,
        "date": "2025-01-31T22:59:00Z",
        "mustBeChecked": True,
        "invoiceKoppelingen": [{"invoiceIdentifier": INVOICE}],
    }
    outside = {"identifier": OTHER, "date": "2025-01-31T23:00:00Z"}
    entries = {BANK: [linked, outside], BANK2: []}
    _bank_sources(handlers, entries)
    args = {"journal_ids": [BANK, BANK2], "start_date": "2025-01-01", "through_date": "2025-01-31"}
    result = call("snelstart_export_bank_entries", args)
    assert result["complete"] and result["administration_id"] == ADMIN
    assert [row["fetched_rows"] for row in result["journals"]] == [2, 0]
    assert [row["exported_rows"] for row in result["journals"]] == [1, 0]
    (path,) = (store.directory / "exports").iterdir()
    assert result["path"] == str(path)
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == result["sha256"]
    rows = [json.loads(line) for line in data.splitlines()]
    assert rows[0]["journal"]["numberOfGemarkeerd"] == 3
    assert rows[1]["entry"] == linked
    assert [item.url.params["skip"] for item in seen if "skip" in item.url.params] == [
        "0",
        "1",
        "0",
    ]
    entries[BANK2] = [linked, linked]
    with pytest.raises(ToolError, match="duplicate row ID"):
        call("snelstart_export_bank_entries", args)
    assert list((store.directory / "exports").iterdir()) == [path]


def make_snapshot(store, letter, rows, *, administration=ADMIN, legacy=False, cutoff="2025-12-31"):
    directory = store.directory / "backups"
    directory.mkdir(exist_ok=True)
    path = directory / ("snelstart-2025-" + letter * 32 + ".zip")
    filename = "inkopen.json" if legacy else "purchases.json"
    payload = json.dumps(rows).encode()
    manifest = {
        "format": LEGACY_ARCHIVE["version"] if legacy else ARCHIVE_FORMAT,
        "year": 2025,
        "through_date": cutoff,
        "created_at": "2026-01-01T00:00:00Z",
        "mcp_administration_id": administration,
        "files": {filename: {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}},
    }
    if legacy:
        rename = {value: key for key, value in LEGACY_ARCHIVE["manifest_keys"].items()}
        manifest = {rename.get(key, key): value for key, value in manifest.items()}
    with ZipFile(path, "w") as zip_file:
        zip_file.writestr("manifest.json", json.dumps(manifest))
        zip_file.writestr(filename, payload)
    return path.name


def test_compare_snapshots_is_local_verified_and_scoped(app):
    call, store, _, seen = app
    before = make_snapshot(
        store,
        "a",
        [
            {"publicIdentifier": BOOKING, "amount": 100},
            {"publicIdentifier": OTHER, "amount": 200},
        ],
        legacy=True,
    )
    after = make_snapshot(
        store,
        "b",
        [
            {"publicIdentifier": BOOKING, "amount": 105},
            {"publicIdentifier": INVOICE, "amount": 350},
        ],
    )
    args = {"dataset": "purchases", "before": before, "after": after}
    result = call("snelstart_compare_archives", args | {"take": 2})
    assert (result["added"], result["changed"], result["removed"], result["unchanged"]) == (
        1,
        1,
        1,
        0,
    )
    assert result["next_skip"] == 2
    last = call("snelstart_compare_archives", args | {"skip": 2})
    assert any(row["fields_changed"] == ["amount"] for row in result["entries"] + last["entries"])
    mismatch = make_snapshot(store, "c", [], cutoff="2025-11-30")
    with pytest.raises(ToolError, match="same year and cutoff"):
        call("snelstart_compare_archives", args | {"after": mismatch})
    different_admin = make_snapshot(store, "d", [], administration=OTHER)
    with pytest.raises(ToolError, match="same administration"):
        call("snelstart_compare_archives", args | {"after": different_admin})
    assert not seen


def test_compare_archives_advertises_only_booking_datasets(tmp_path):
    server = create_server(Client(Store(tmp_path / "profile")))
    tool = next(
        tool
        for tool in asyncio.run(server.list_tools())
        if tool.name == "snelstart_compare_archives"
    )
    enum = tool.inputSchema["$defs"]["ArchiveComparisonDataset"]["enum"]
    assert set(enum) == {"purchases", "sales", "bank_entries", "journal_and_opening_entries"}
    with pytest.raises(ToolError, match="Invalid input for this SnelStart tool"):
        asyncio.run(
            server.call_tool(
                tool.name,
                {"before": "before", "after": "after", "dataset": "balance_and_profit_loss"},
            )
        )


def test_mcp_status_reports_reconnect_with_running_and_installed_versions(app, monkeypatch):
    call, _, _, seen = app
    monkeypatch.setattr("snelstart_mcp.updater.installed_version", lambda: "2099.1.1.1")
    status = call("snelstart_status")
    update = status["update"]
    assert update["status"] == "reconnect_required"
    assert update["running_version"] == status["server_version"]
    assert update["installed_version"] == "2099.1.1.1"
    assert call("snelstart_check_update") == update
    assert not seen


def test_read_only_reconciliation_reports_evidence_and_competing_payments(app):
    call, _, handlers, seen = app

    def bank(identifier, amount, description, links=None):
        return {
            "identifier": identifier,
            "date": "2025-02-12",
            "amount": amount,
            "description": description,
            "invoiceKoppelingen": links or [],
        }

    _bank_sources(
        handlers,
        {
            BANK: [
                bank("one", -20, "Fixture vendor REF-99001"),
                bank("two", -20, "Fixture vendor REF-99001"),
                bank("three", 50, "Fixture client INV-6611"),
                bank(
                    "four",
                    -77,
                    "Recorded purchase",
                    [{"invoiceIdentifier": INVOICE, "isPurchase": True}],
                ),
                bank("five", -100, "Unknown transfer"),
            ]
        },
    )
    handlers["/Invoices/Search"] = page(
        {
            "factuurNummerPublicIdentifier": OTHER,
            "invoiceNumber": "INV-6611",
            "invoiceDate": "2025-01-31",
            "customerName": "Fixture client",
            "invoiceTotal": 50,
            "hasBijlage": True,
        }
    )
    handlers["/Purchases/SearchAllInkopen"] = page(
        {
            "publicIdentifier": INVOICE,
            "factuurnummer": "REF-99001",
            "factuurdatum": "2024-12-31",
            "leverancierNaam": "Fixture vendor",
            "factuurbedrag": 20,
            "hasBijlagen": False,
        }
    )
    result = call(
        "snelstart_reconcile_bank",
        {
            "journal_ids": [BANK],
            "start_date": "2025-02-01",
            "through_date": "2025-02-28",
            "take": 5,
        },
    )
    rows = {row["identifier"]: row for row in result["entries"]}
    assert rows["one"]["status"] == rows["two"]["status"] == "ambiguous"
    assert rows["one"]["possible_duplicate"] and rows["two"]["competing_bank_entries"]
    assert rows["one"]["candidates"][0]["documents"] == "missing"
    assert rows["three"]["status"] == "suggested"
    assert rows["three"]["candidates"][0]["reference_matches"] is True
    assert rows["four"]["status"] == "recorded_link" and rows["four"]["recorded_link_ids"] == [
        INVOICE
    ]
    assert rows["five"]["status"] == "unmatched"
    assert {request.url.path for request in seen if request.method != "GET"} == {
        "/Administrations/Open",
        "/Invoices/Search",
    }


def test_mutation_receipt_verification_and_unresolved_timeout(app, monkeypatch):
    call, store, handlers, seen = app
    handlers["/MemoriaalBoekingen/Create"] = {"publicIdentifier": BOOKING}
    handlers["/MemoriaalBoekingen/GetDetails"] = {"publicIdentifier": BOOKING}
    args = {
        "operation": "POST /MemoriaalBoekingen/Create",
        "administration_id": ADMIN,
        "payload": {"description": "private-payload-fixture"},
    }
    with pytest.raises(ToolError, match="Local confirmation required"):
        call("snelstart_write", args)
    assert call("snelstart_mutation_receipts")["data"] == []
    assert not seen
    monkeypatch.setattr("snelstart_mcp.tools_connection.require_approval", lambda *_: None)
    call("snelstart_write", args)
    (receipt,) = call("snelstart_mutation_receipts")["data"]
    assert receipt["status"] == "accepted" and receipt["operation"] == args["operation"]
    assert (
        receipt["record_id"] == BOOKING and receipt["request_sha256"] and receipt["response_sha256"]
    )
    verified = call("snelstart_verify_mutation", {"receipt_id": receipt["receipt_id"]})
    assert (
        verified["status"] == "verified" and verified["verification"] == "returned_record_present"
    )

    def timeout(request):
        raise httpx.ReadTimeout("private-transport-fixture", request=request)

    handlers["/MemoriaalBoekingen/Create"] = timeout
    with pytest.raises(ToolError, match="unavailable"):
        call("snelstart_write", args)
    unresolved = call("snelstart_mutation_receipts")["data"][0]
    assert unresolved["status"] == "unresolved" and unresolved["response_sha256"] is None
    call("snelstart_verify_mutation", {"receipt_id": unresolved["receipt_id"]})
    assert sum(request.url.path == "/MemoriaalBoekingen/Create" for request in seen) == 2
    database = store.directory / "audit" / f"{ADMIN}.sqlite3"
    assert b"private-payload-fixture" not in database.read_bytes()
