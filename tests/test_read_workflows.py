import asyncio
import json
import stat
from datetime import date
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError

from snelstart_mcp import backup, year_data
from snelstart_mcp import client as api
from snelstart_mcp.audit import AuditLog
from snelstart_mcp.client import Client
from snelstart_mcp.config import SnelStartError, Store
from snelstart_mcp.server import create_server

ADMIN = "11111111-1111-4111-8111-111111111111"
ENTRY = "33333333-3333-4333-8333-333333333333"


@pytest.fixture
def session(tmp_path, monkeypatch):
    store = Store(tmp_path / "private")
    store.write("config.json", {"administration_id": ADMIN, "allow_writes": False})
    requests = []
    replies = {
        "/Administrations/All": [{"id": 1, "identifier": ADMIN}],
        "/Administrations/Open": 0,
    }

    def handle(request):
        assert request.url.host == "webapi.snelstart.nl"
        requests.append(request)
        reply = replies[request.url.path]
        return reply if isinstance(reply, httpx.Response) else httpx.Response(200, json=reply)

    with httpx.Client(transport=httpx.MockTransport(handle)) as http:
        client = Client(store, http)
        monkeypatch.setattr(client.auth, "access_token", lambda *a, **kw: "mock-token")
        yield client, requests, replies


def call(client, name, params):
    result = asyncio.run(create_server(client).call_tool(name, params))
    if isinstance(result, tuple):
        return result[1]
    return json.loads(result[0].text)


@pytest.mark.parametrize(
    ("day", "start", "end"),
    [
        ("2025-12-31", "2025-12-30T23:00:00.000+00:00", "2025-12-31T22:59:59.999+00:00"),
        ("2026-03-29", "2026-03-28T23:00:00.000+00:00", "2026-03-29T21:59:59.999+00:00"),
    ],
)
def test_purchase_query_preserves_local_boundaries_across_dst(session, day, start, end):
    client, requests, replies = session
    path = "/Purchases/SearchAllInkopen"
    replies[path] = {"resultList": [{"factuurdatum": day}], "totalMatchCount": 1}
    result = call(
        client,
        "snelstart_search_purchases",
        {
            "start_date": day,
            "through_date": day,
        },
    )
    assert result["data"]["totalMatchCount"] == 1
    assert requests[-1].url.params["startDate"] == start
    assert requests[-1].url.params["dateUntil"] == end


def test_sales_search_posts_only_to_read_endpoint(session):
    client, requests, replies = session
    path = "/Invoices/Search"
    replies[path] = {"totalMatchCount": 1, "resultList": [{"factuurNummerId": 123}]}
    assert call(
        client, "snelstart_search_sales", {"query": "Invoice 0309", "status": "outstanding"}
    )["data"]
    assert (requests[-1].method, requests[-1].url.path) == ("POST", path)
    assert requests[-1].url.params["statusFilter"] == "2"
    body = json.loads(requests[-1].content)
    assert [term["term"] for term in body["globalSearchTerms"]] == ["Invoice", "0309"]


def test_bank_mutations_use_working_read_route(session):
    client, requests, replies = session
    path = "/KasBankBoeking/GetKasBankBoekingenWithTimespan"
    replies[path] = {"totalMatchCount": 1, "resultList": [{"identifier": ENTRY}]}
    result = call(
        client,
        "snelstart_bank_entries",
        {
            "ledger_id": ENTRY,
            "start_date": "2025-12-31",
            "through_date": "2025-12-31",
            "marked_only": True,
        },
    )
    assert result["data"]["resultList"][0]["identifier"] == ENTRY
    assert requests[-1].url.path == path
    assert requests[-1].url.params["statusFilter"] == "1"
    assert requests[-1].url.params["totEnMet"].endswith("22:59:59.999+00:00")


def test_attachment_metadata_maps_the_web_api_fields(session):
    client, _, replies = session
    replies["/Purchases/GetAttachmentsWithIdentifier"] = [
        {
            "publicIdentifier": ENTRY,
            "id": 9,
            "name": "invoice.pdf",
            "originalSizeInBytes": 42,
            "thumbnail": "discard",
        }
    ]
    result = call(client, "snelstart_list_attachments", {"kind": "purchase", "entry_id": ENTRY})
    assert result["data"] == [
        {
            "attachmentIdentifier": ENTRY,
            "attachmentId": 9,
            "fileName": "invoice.pdf",
            "size": 42,
        }
    ]


def test_backup_filters_rows_using_local_dates():
    early = {"date": "2024-12-31T23:00:00Z"}
    last = {"date": "2025-12-31T23:59:59.999"}
    outside = {"date": "2025-12-31T23:00:00Z"}
    assert year_data._in_period(
        [early, outside, last],
        date(2025, 1, 1),
        date(2025, 12, 31),
        "date",
    ) == [early, last]


def test_backup_stops_before_using_another_administration(session):
    client, requests, _ = session
    client.store.write("config.json", {"administration_id": ENTRY, "allow_writes": False})
    with pytest.raises(SnelStartError, match="selected administration does not match"):
        client.request("GET /Grootboek/GetAllMinimal", expected_administration=ADMIN)
    assert not requests


def test_only_invoice_search_is_a_catalog_post_read():
    assert (
        {
            key
            for key, entry in api.catalog().items()
            if entry["method"] != "GET" and entry["read_only"]
        }
        == api.READ_POST_OPERATIONS
        == {"POST /Invoices/Search"}
    )


def test_download_does_not_return_content_or_use_remote_name_as_path(session):
    client, requests, replies = session
    data = b"%PDF-1.7\nopaque invoice"
    download = "/Attachments/GetContentByIdentifier"
    replies[download] = httpx.Response(
        200,
        content=data,
        headers={
            "content-type": "application/pdf",
            "content-disposition": 'attachment; filename="../../invoice.pdf"',
        },
    )
    result = call(client, "snelstart_download_document", {"attachment_id": ENTRY})
    path = Path(result["path"])
    assert path.parent == client.store.directory / "downloads"
    assert path.read_bytes() == data
    assert result["original_filename"] == "invoice.pdf"
    assert result["sha256"] == sha256(data).hexdigest()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert "opaque invoice" not in json.dumps(result)
    assert requests[-1].url.path == download


@pytest.mark.parametrize(
    ("status", "mime", "body"),
    [
        (206, "application/pdf", b"%PDF-1.7 partial"),
        (200, "text/html", b"<html>login"),
        (200, "application/pdf", b""),
        (200, "application/pdf", b"X" * 51),
    ],
)
def test_failed_download_leaves_no_file(session, monkeypatch, status, mime, body):
    client, _, replies = session
    monkeypatch.setattr(api, "MAX_DOWNLOAD_BYTES", 50)
    operation = "GET /Invoices/GetPdfByFactuurNummerId"
    replies[operation.split()[1]] = httpx.Response(
        status, content=body, headers={"Content-Type": mime}
    )
    with pytest.raises(SnelStartError):
        client.request(operation, {"factuurNummerId": 12}, download=True)
    assert not list((client.store.directory / "downloads").glob("*"))


def test_download_does_not_follow_cross_origin_redirect(session):
    client, requests, replies = session
    path = "/Invoices/GetPdfByFactuurNummerId"
    replies[path] = httpx.Response(302, headers={"Location": "https://example.test/file.pdf"})
    with pytest.raises(SnelStartError, match="HTTP 302"):
        client.request(f"GET {path}", {"factuurNummerId": 1}, download=True)
    assert requests[-1].url.host == "webapi.snelstart.nl"


def test_backup_checks_duplicate_pages_and_does_not_publish_incomplete_zip(session, monkeypatch):
    client, _, replies = session
    path = "/Invoices/Search"
    replies[path] = {"totalMatchCount": 2, "resultList": [{"id": ENTRY}]}
    with pytest.raises(SnelStartError, match="duplicate row ID"):
        year_data.pages(
            client.request,
            f"POST {path}",
            {
                "statusFilter": 0,
                "sortDataFieldName": "invoiceDate",
            },
            ("id",),
            {},
        )

    def fail(*args):
        raise SnelStartError("The export is incomplete.")

    monkeypatch.setattr(backup, "collect", fail)
    with pytest.raises(SnelStartError, match="incomplete"):
        backup.create_archive(client.store, 2020, date(2020, 12, 31), client=client)
    assert not list((client.store.directory / "backups").iterdir())


def test_backup_verifies_hashes_and_is_not_a_native_backup(tmp_path):
    store = Store(tmp_path / "private")
    source = tmp_path / "audit.xaf"
    source.write_text("<auditfile><header><fiscalYear>2020</fiscalYear></header></auditfile>")
    output = backup.create_archive(store, 2020, date(2020, 12, 31), audit_file=str(source))
    verified = backup.verify_archive(store, output["archive"])
    assert verified["verified"]
    assert not verified["bacpac_included"]
    path = Path(output["path"])
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with ZipFile(path, "w") as archive:
        archive.writestr("audit_file.xaf", b"changed")
        archive.writestr("manifest.json", json.dumps(output))
    with pytest.raises(SnelStartError, match="Checksum mismatch"):
        backup.verify_archive(store, output["archive"])


def test_archive_tools_package_verify_and_list_local_sources(session, tmp_path):
    client, requests, _ = session
    source = tmp_path / "audit.xaf"
    source.write_text("<auditfile><header><fiscalYear>2020</fiscalYear></header></auditfile>")
    created = call(
        client,
        "snelstart_create_year_archive",
        {
            "year": 2020,
            "through_date": "2020-12-31",
            "live_export": False,
            "auditfile_path": str(source),
        },
    )
    args = {"archive": created["archive"]}
    assert call(client, "snelstart_verify_archive", args)["files"] == created["files"]
    assert call(client, "snelstart_list_archives", {})["data"] == [
        {**args, "path": created["path"]}
    ]
    assert not requests


@pytest.mark.parametrize(
    ("content", "error"),
    [
        (b"", "member is empty"),
        (b"<!DOCTYPE auditfile><auditfile/>", "unexpected DTD"),
        (b"<auditfile", "No readable XAF"),
    ],
)
def test_invalid_audit_sources_leave_no_archive(tmp_path, content, error):
    store = Store(tmp_path / "private")
    source = tmp_path / "audit.xaf"
    source.write_bytes(content)
    with pytest.raises(SnelStartError, match=error):
        backup.create_archive(store, 2020, date(2020, 12, 31), audit_file=str(source))
    assert not list((store.directory / "backups").iterdir())


@pytest.mark.parametrize(
    ("source_type", "member", "error"),
    [
        ("administration_backup", "file.txt", "no database model"),
        ("official_export", "file.txt", "exactly one audit file"),
        ("attachments", None, "invalid or too large"),
        ("attachments", "not-a-zip", "corrupt or unreadable"),
    ],
)
def test_invalid_archive_sources_are_not_published(tmp_path, source_type, member, error):
    store = Store(tmp_path / "private")
    source = tmp_path / (
        "source.bacpac" if source_type == "administration_backup" else "source.zip"
    )
    if member == "not-a-zip":
        source.write_text("corrupt source")
    else:
        with ZipFile(source, "w") as container:
            if member:
                container.writestr(member, b"fixture")
    with pytest.raises(SnelStartError, match=error):
        backup.create_archive(store, 2020, date(2020, 12, 31), **{source_type: str(source)})
    assert not list((store.directory / "backups").iterdir())


@pytest.mark.parametrize(
    ("member", "through", "extra", "error"),
    [
        ("../audit_file.xaf", "2020-12-31", None, "contents do not match"),
        ("audit_file.xaf", "2021-01-01", None, "contents do not match"),
        ("audit_file.xaf", "2020-12-31", "unexpected.txt", "contents do not match"),
        ("audit_file.xaf", "2020-02-30", None, "unknown format"),
    ],
)
def test_archive_verification_rejects_unsafe_or_inconsistent_manifests(
    tmp_path, member, through, extra, error
):
    store = Store(tmp_path / "private")
    name = f"snelstart-2020-{'a' * 32}.zip"
    path = Store(store.directory / "backups").directory / name
    content = b"fixture"
    manifest = {
        "format": backup.ARCHIVE_FORMAT,
        "year": 2020,
        "through_date": through,
        "files": {member: {"bytes": len(content), "sha256": sha256(content).hexdigest()}},
    }
    with ZipFile(path, "w") as archive:
        archive.writestr(member, content)
        archive.writestr("manifest.json", json.dumps(manifest))
        if extra:
            archive.writestr(extra, b"extra")
    with pytest.raises(SnelStartError, match=error):
        backup.verify_archive(store, name)


def test_combined_export_checks_year_and_preserves_original_zip(tmp_path):
    source = tmp_path / "official.zip"
    with ZipFile(source, "w") as archive:
        archive.writestr(
            "official.xaf", "<auditfile><header><fiscalYear>2020</fiscalYear></header></auditfile>"
        )
        archive.writestr("bijlagen/factuur.pdf", b"%PDF-1.7")
    store = Store(tmp_path / "private")
    with pytest.raises(SnelStartError, match="year"):
        backup.create_archive(store, 2019, date(2019, 12, 31), official_export=str(source))
    saved = backup.create_archive(store, 2020, date(2020, 12, 31), official_export=str(source))
    assert saved["source_files"]["official_export"]["attachment_count"] == 1
    with ZipFile(saved["path"]) as archive:
        assert archive.read("official_export.zip") == source.read_bytes()


def test_backup_inspects_the_same_bytes_that_are_archived(session, tmp_path, monkeypatch):
    client, _, _ = session
    source = tmp_path / "audit.xaf"
    original = b"<auditfile><header><fiscalYear>2020</fiscalYear></header></auditfile>"
    source.write_bytes(original)

    def collect(*args):
        source.write_bytes(b"<a-different-file/>")
        return {"bank_entries": [], "journal_and_opening_entries": []}

    monkeypatch.setattr(backup, "collect", collect)
    saved = backup.create_archive(
        client.store,
        2020,
        date(2020, 12, 31),
        client=client,
        audit_file=str(source),
    )
    with ZipFile(saved["path"]) as archive:
        assert archive.read("audit_file.xaf") == original
    assert saved["source_files"]["audit_file"]["fiscalYear"] == "2020"


def test_backup_total_limit_allows_multiple_large_members(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "MAX_MEMBER", 512)
    audit = tmp_path / "audit.xaf"
    audit.write_bytes(
        b"<auditfile><header><fiscalYear>2020</fiscalYear></header>" + b" " * 340 + b"</auditfile>"
    )
    attachments = tmp_path / "attachments.zip"
    with ZipFile(attachments, "w") as archive:
        archive.writestr("file.pdf", b"x" * 285)
    assert audit.stat().st_size + attachments.stat().st_size > 512
    store = Store(tmp_path / "private")
    saved = backup.create_archive(
        store,
        2020,
        date(2020, 12, 31),
        audit_file=str(audit),
        attachments=str(attachments),
    )
    assert backup.verify_archive(store, saved["archive"])["verified"]


def test_legacy_archive_remains_readable_with_english_manifest_keys(tmp_path):
    store = Store(tmp_path / "private")
    directory = Store(store.directory / "backups").directory
    legacy = backup.LEGACY_ARCHIVE
    keys = {english: previous for previous, english in legacy["manifest_keys"].items()}
    member = legacy["files"][0]
    content = b"{}"
    archive_name = "snelstart-2020-" + "a" * 32 + ".zip"
    with ZipFile(directory / archive_name, "w") as archive:
        archive.writestr(member, content)
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "format": legacy["version"],
                    keys["year"]: 2020,
                    keys["through_date"]: "2020-12-31",
                    keys["files"]: {
                        member: {"bytes": len(content), "sha256": sha256(content).hexdigest()}
                    },
                    keys["mcp_counts"]: {"inkopen": 3},
                    keys["source_files"]: {"officiele_export": {"overige_bestanden": 2}},
                    keys["mcp_scope"]: {"inbegrepen": ["inkopen"]},
                }
            ),
        )
    manifest = backup.verify_archive(store, archive_name)
    assert manifest["verified"] and manifest["year"] == 2020
    assert manifest["stored_format"] == legacy["version"]
    assert member in manifest["files"]
    assert manifest["mcp_counts"] == {"purchases": 3}
    assert manifest["source_files"] == {"official_export": {"attachment_count": 2}}
    assert manifest["mcp_scope"] == {"included": ["purchases"]}


def test_purchase_review_filter_and_vat_details_use_read_routes(session):
    client, requests, replies = session
    replies["/Purchases/SearchAllInkopen"] = {"totalMatchCount": 0, "resultList": []}
    reviews = call(
        client,
        "snelstart_search_purchases",
        {"start_date": "2025-01-01", "through_date": "2025-12-31", "review_only": True},
    )
    assert reviews["data"]["resultList"] == []
    assert requests[-1].method == "GET"
    assert requests[-1].url.params["onlyTeControlerenInkopen"] == "true"

    replies["/BtwAangiftes/GetAll"] = [{"id": 42}]
    replies["/BtwAangiftes/Get"] = {"id": 42, "fixture": True}
    listed = call(client, "snelstart_vat_returns", {})
    assert listed["data"] == [{"id": 42}]
    result = call(
        client,
        "snelstart_read",
        {"operation": "GET /BtwAangiftes/Get", "parameters": {"id": listed["data"][0]["id"]}},
    )
    assert result["data"] == {"id": 42, "fixture": True}
    assert requests[-1].method == "GET" and requests[-1].url.params["id"] == "42"


def test_client_locale_does_not_change_the_english_tool_contract(session, monkeypatch):
    client, _, _ = session
    monkeypatch.setenv("LANG", "nl_NL.UTF-8")
    dutch_locale = asyncio.run(create_server(client).list_tools())
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")
    french_locale = asyncio.run(create_server(client).list_tools())
    assert dutch_locale == french_locale
    sales = next(tool for tool in french_locale if tool.name == "snelstart_search_sales")
    assert sales.description.startswith("Search sales invoices")
    status_schema = sales.inputSchema["properties"]["status"]
    if "$ref" in status_schema:
        status_schema = sales.inputSchema["$defs"][status_schema["$ref"].rsplit("/", 1)[-1]]
    assert set(status_schema["enum"]) == {
        "all",
        "overdue",
        "outstanding",
        "paid",
        "draft",
    }


def test_english_errors_and_query_are_independent_of_client_language(session):
    client, requests, replies = session
    path = "/Customers/Search"
    replies[path] = {"totalMatchCount": 0, "resultList": []}
    first = call(client, "snelstart_search_relations", {"kind": "customers"})
    first_url = requests[-1].url
    second = call(client, "snelstart_search_relations", {"kind": "customers"})
    assert second == first and requests[-1].url == first_url
    with pytest.raises(ToolError, match="start date must be"):
        call(
            client,
            "snelstart_search_purchases",
            {
                "start_date": "2025-12-31",
                "through_date": "2025-01-01",
            },
        )


def test_audit_records_outcomes_without_tool_arguments_or_response_payload(session):
    client, _, replies = session
    replies["/Customers/Search"] = {
        "totalMatchCount": 1,
        "resultList": [{"name": "PRIVATE-RESPONSE"}],
    }
    call(client, "snelstart_search_relations", {"kind": "customers", "query": "PRIVATE-QUERY"})
    with pytest.raises(ToolError, match="Writing is disabled"):
        call(
            client,
            "snelstart_write",
            {
                "operation": "POST /MemoriaalBoekingen/Create",
                "payload": {"password": "PRIVATE-PASSWORD"},
            },
        )
    events = call(client, "snelstart_audit_log", {"limit": 10})["data"]
    outcomes = {event["tool"]: event["outcome"] for event in events}
    assert outcomes["snelstart_search_relations"] == "ok"
    assert outcomes["snelstart_write"] == "error"
    audit_file = client.store.directory / "audit.sqlite3"
    assert stat.S_IMODE(audit_file.stat().st_mode) == 0o600
    assert b"PRIVATE-" not in audit_file.read_bytes()


def test_tool_is_blocked_if_audit_intent_cannot_be_saved(session, monkeypatch):
    client, requests, _ = session
    server = create_server(client)

    def fail(tool):
        raise SnelStartError("Could not write the local audit log.")

    monkeypatch.setattr(server.audit, "start", fail)
    with pytest.raises(ToolError, match="Could not write the local audit log"):
        asyncio.run(server.call_tool("snelstart_chart_of_accounts", {}))
    assert not requests


def test_corrupt_audit_database_blocks_reads_and_tool_execution(session):
    client, requests, _ = session
    audit = AuditLog(client.store)
    audit.path.write_bytes(b"not a database")
    with pytest.raises(ToolError, match="Could not write the local audit log"):
        call(client, "snelstart_list_administrations", {})
    with pytest.raises(SnelStartError, match="Could not read the local audit log"):
        audit.recent(10)
    assert not requests
    assert audit.path.read_bytes() == b"not a database"


@pytest.mark.parametrize("success", [True, False])
def test_missing_audit_outcome_is_visible_and_does_not_retry(session, monkeypatch, success):
    client, requests, replies = session
    if not success:
        replies["/Administrations/All"] = httpx.Response(503)
    server = create_server(client)

    def fail(*args):
        raise SnelStartError("Could not write the local audit log.")

    monkeypatch.setattr(server.audit, "finish", fail)
    message = "Check the outcome before retrying" if success else "HTTP 503"
    with pytest.raises(ToolError, match=message):
        asyncio.run(server.call_tool("snelstart_list_administrations", {}))
    assert [request.url.path for request in requests] == ["/Administrations/All"]
    assert [event["outcome"] for event in server.audit.recent(1)] == ["pending"]


def test_unknown_tool_name_is_redacted_in_audit_even_with_invalid_config(session):
    client, requests, _ = session
    client.store.write("config.json", {"allow_writes": "false"})
    with pytest.raises(ToolError):
        call(client, "PRIVATE-INVALID-TOOL", {})
    (event,) = AuditLog(client.store).recent(1)
    assert event["tool"] == "unknown_tool"
    assert event["outcome"] == "error"
    assert event["administration_id"] is None
    assert not requests


def test_connection_tools_select_only_an_accessible_administration(session):
    client, requests, replies = session
    other = "22222222-2222-4222-8222-222222222222"
    assert call(client, "snelstart_status", {})["administration_id"] == ADMIN
    assert call(client, "snelstart_read", {"operation": "GET /Administrations/All"})["data"] == [
        {"id": 1, "identifier": ADMIN}
    ]
    replies["/Administrations/All"].append({"id": 2, "identifier": other})
    replies["/Administrations/Open"] = 5
    with pytest.raises(ToolError, match="could not open"):
        call(client, "snelstart_select_administration", {"administration_id": other})
    assert client.status()["administration_id"] == ADMIN
    replies["/Administrations/Open"] = 0
    assert call(client, "snelstart_select_administration", {"administration_id": other}) == {
        "opened": True,
        "identifier": other,
    }
    assert json.loads(requests[-1].content) == {
        "administrationId": 2,
        "administrationIdentifier": other,
    }
    assert client.status()["administration_id"] == other


@pytest.mark.parametrize(
    ("tool", "args", "message"),
    [
        ("audit_log", {"limit": 101}, "limit must be"),
        ("list_operations", {"limit": 0}, "limit must be"),
        ("read", {"operation": "POST /MemoriaalBoekingen/Create"}, "Unknown read operation"),
        (
            "write",
            {"operation": "GET /Administrations/All", "payload": {}},
            "Unknown write operation",
        ),
        ("download_document", {}, "exactly one"),
        (
            "download_document",
            {"attachment_id": ENTRY, "invoice_number": "INV-1"},
            "only to a sales invoice",
        ),
        ("download_document", {"invoice_number_id": 0}, "must be positive"),
        ("find_payment_matches", {"query": " ", "direction": "incoming"}, "specific search term"),
        (
            "financial_result",
            {"start_date": "2026-02-01", "through_date": "2026-01-01"},
            "start date",
        ),
        ("search_relations", {"kind": "customers", "query": "example", "take": 201}, "Page size"),
        ("purchase_payments", {"entry_id": "not-a-uuid"}, "Invalid input"),
    ],
)
def test_invalid_mcp_arguments_fail_before_network(session, tool, args, message):
    client, requests, _ = session
    with pytest.raises(ToolError, match=message):
        call(client, f"snelstart_{tool}", args)
    assert not requests


@pytest.mark.parametrize("invoice_number", [None, "INV-1"])
def test_download_sales_invoice_uses_the_pdf_route(session, invoice_number):
    client, requests, replies = session
    route = "/Invoices/GetPdfByFactuurNummerId"
    content = b"%PDF-1.7 test file"
    replies[route] = httpx.Response(
        200, headers={"Content-Type": "application/pdf"}, content=content
    )
    result = call(
        client,
        "snelstart_download_document",
        {"invoice_number_id": 5, "invoice_number": invoice_number},
    )
    assert requests[-1].url.path == route
    assert requests[-1].url.params["factuurNummerId"] == "5"
    assert requests[-1].url.params.get("invoiceNumber") == invoice_number
    assert Path(result["path"]).read_bytes() == content


def test_financial_result_reads_the_report_for_the_requested_period(session):
    client, requests, replies = session
    route = "/Reporting/FinancieelResultaat"
    replies[route] = {"financialResult": 12.5}
    result = call(
        client,
        "snelstart_financial_result",
        {"start_date": "2025-01-01", "through_date": "2025-12-31"},
    )
    assert result == {"data": {"financialResult": 12.5}}
    assert requests[-1].method == "GET" and requests[-1].url.path == route
    assert dict(requests[-1].url.params) == {"startDate": "2025-01-01", "endDate": "2025-12-31"}


@pytest.mark.parametrize(
    ("page", "error"),
    [
        ({"totalMatchCount": "1", "resultList": [{"id": "a"}]}, "Unexpected response"),
        ({"totalMatchCount": 100_001, "resultList": []}, "Too many rows"),
        ({"totalMatchCount": 1, "resultList": []}, "Incomplete pagination"),
    ],
)
def test_pagination_rejects_inconsistent_or_oversized_pages(page, error):
    with pytest.raises(SnelStartError, match=error):
        year_data.pages(lambda *_: page, "fixture", {}, ("id",))


@pytest.mark.parametrize(
    ("row", "message"),
    [({}, "without a readable date"), ({"date": "2020-02-30"}, "with an invalid date")],
)
def test_export_rejects_entries_with_unusable_dates(row, message):
    with pytest.raises(SnelStartError, match=message):
        year_data._in_period([row], date(2020, 1, 1), date(2020, 12, 31), "date")


def test_invalid_config_flag_cannot_enable_writes(session):
    client, requests, _ = session
    client.store.write("config.json", {"administration_id": ADMIN, "allow_writes": "false"})
    with pytest.raises(SnelStartError, match="Invalid MCP configuration"):
        client.request("POST /MemoriaalBoekingen/Create", body={})
    assert not requests


def test_local_write_permission_is_limited_to_one_operation_and_administration(session):
    client, requests, replies = session
    operation = "POST /MemoriaalBoekingen/Create"
    client.store.write(
        "config.json", {"administration_id": ADMIN, "write_permissions": {ADMIN: [operation]}}
    )
    replies["/MemoriaalBoekingen/Create"] = {"fixture": True}
    payload = {"description": "synthetic request"}
    args = {"operation": operation, "payload": payload}
    assert call(client, "snelstart_write", args) == {"data": {"fixture": True}}
    assert json.loads(requests[-1].content) == payload
    assert [request.url.path for request in requests] == [
        "/Administrations/All",
        "/Administrations/Open",
        "/MemoriaalBoekingen/Create",
    ]
    requests.clear()
    with pytest.raises(ToolError, match="Writing is disabled"):
        call(client, "snelstart_write", {**args, "operation": "POST /MemoriaalBoekingen/Update"})
    other = "22222222-2222-4222-8222-222222222222"
    client.store.write(
        "config.json", {"administration_id": other, "write_permissions": {ADMIN: [operation]}}
    )
    assert call(client, "snelstart_status", {})["approved_write_operations"] == []
    with pytest.raises(ToolError, match="Writing is disabled"):
        call(client, "snelstart_write", args)
    assert not requests


@pytest.mark.parametrize("permissions", [{ADMIN: "POST /MemoriaalBoekingen/Create"}, {"*": []}])
def test_malformed_write_permissions_cannot_enable_writes(session, permissions):
    client, requests, _ = session
    client.store.write(
        "config.json", {"administration_id": ADMIN, "write_permissions": permissions}
    )
    with pytest.raises(ToolError, match="Invalid MCP configuration"):
        call(
            client,
            "snelstart_write",
            {"operation": "POST /MemoriaalBoekingen/Create", "payload": {}},
        )
    assert not requests


def test_archival_pagination_fails_on_count_drift():
    responses = iter(
        [
            {"totalMatchCount": 2, "resultList": [{"id": "first"}]},
            {"totalMatchCount": 3, "resultList": [{"id": "second"}]},
        ]
    )
    with pytest.raises(SnelStartError, match="count changed"):
        year_data.pages(lambda *a: next(responses), "test", {}, ("id",))


def test_complete_year_collection_pins_admin_and_checks_every_date():
    bank, journal, opening = ("bank-id", "journal-id", "opening-id")
    identifiers = [f"11111111-1111-4111-8111-{i:012d}" for i in (1, 2, 3)]
    bank_id, journal_id, opening_id = identifiers
    called = []

    def page(*rows):
        return {"resultList": list(rows), "totalMatchCount": len(rows)}

    replies = {
        "GET /KasBankBoeking/GetKasEnBankDagboeken": [{"grootboekIdentifier": bank_id}],
        "GET /Grootboek/GetMemoriaalAndBeginBalansDagboekenWithSaldo": [
            {"grootboekIdentifier": journal_id, "grootboekFunctieId": 7},
            {"grootboekIdentifier": opening_id, "grootboekFunctieId": 8},
        ],
        "POST /Invoices/Search": page(
            {"verkoopOrderId": 12, "invoiceDate": "2025-12-31"},
            {"factuurNummerId": 12, "date": "2024-12-31"},
        ),
        "GET /Purchases/SearchAllInkopen": page(
            {"publicIdentifier": "in", "factuurdatum": "2025-01-01"},
            {"publicIdentifier": "out", "factuurdatum": "2026-01-01"},
        ),
        "GET /KasBankBoeking/GetKasBankBoekingenWithTimespan": page(
            {"identifier": bank, "date": "2025-07-15"}
        ),
        "GET /MemoriaalBoekingen/Search": page(
            {"publicIdentifier": journal, "datum": "2025-01-01"}
        ),
        "GET /BalansBoekingen/Search": page({"publicIdentifier": opening, "datum": "2025-01-01"}),
        "GET /Grootboek/GetBalansResultaatAndRubrieken": {"balans": []},
        "GET /Grootboek/GetAllMinimal": [],
        "GET /BtwAangiftes/GetAll": [],
    }

    class MockReadClient:
        def request(self, operation, params=None, body=None, *, expected_administration):
            assert expected_administration == ADMIN
            called.append(operation)
            if operation.endswith("/Search") and "Boekingen/" in operation:
                assert params["top"] == 100
            return replies[operation]

    result = year_data.collect(MockReadClient(), 2025, date(2025, 12, 31), ADMIN)
    assert set(result) == year_data.DATASETS
    assert set(called) == replies.keys()
    assert [row["publicIdentifier"] for row in result["purchases"]] == ["in"]
    assert len(result["sales"]) == 1
    assert len(result["bank_entries"][0]["entries"]) == 1
    assert sum(len(row["entries"]) for row in result["journal_and_opening_entries"]) == 2


@pytest.mark.parametrize(
    ("name", "arguments", "path", "reply"),
    [
        ("snelstart_chart_of_accounts", {}, "/Grootboek/GetAllMinimal", []),
        (
            "snelstart_balance_sheet",
            {"through_date": "2025-12-31"},
            "/Grootboek/GetBalansResultaatAndRubrieken",
            {},
        ),
        (
            "snelstart_ledger_entries",
            {"ledger_id": ENTRY, "through_date": "2025-12-31"},
            "/Grootboek/GetGrootboekMutaties",
            {},
        ),
        (
            "snelstart_get_entry",
            {"kind": "journal", "entry_id": ENTRY},
            "/MemoriaalBoekingen/GetDetails",
            {},
        ),
        (
            "snelstart_get_entry",
            {"kind": "bank", "entry_id": ENTRY},
            "/KasBankBoeking/GetKasBankboekingDetails",
            {},
        ),
        ("snelstart_bank_journals", {}, "/KasBankBoeking/GetKasEnBankDagboeken", []),
        (
            "snelstart_find_payment_matches",
            {"query": "test", "direction": "outgoing"},
            "/KasBankBoeking/SearchInvoices",
            {},
        ),
        ("snelstart_purchase_payments", {"entry_id": ENTRY}, "/Purchases/GetInkoopBetalingen", []),
        ("snelstart_supplemental_vat_years", {}, "/BtwAangiftes/GetJarenVoorJaarSuppletie", []),
        ("snelstart_vat_returns", {}, "/BtwAangiftes/GetAll", []),
        (
            "snelstart_year_end_review",
            {"year": 2025, "section": "open_purchases"},
            "/Jaarafsluiting/GetOpenstaandeInkoopfacturen",
            [],
        ),
        (
            "snelstart_read",
            {"operation": "GET /Grootboek/GetAllMinimal"},
            "/Grootboek/GetAllMinimal",
            [],
        ),
    ],
)
def test_tool_routes_and_response_data(session, name, arguments, path, reply):
    client, requests, replies = session
    replies[path] = reply
    assert call(client, name, arguments)["data"] == reply
    assert requests[-1].url.path == path
    assert all(req.method == "GET" or req.url.path == "/Administrations/Open" for req in requests)
