import asyncio
import json
import stat
from datetime import date, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import UUID
from zipfile import ZipFile

import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError

from snelstart_mcp import backup, year_data
from snelstart_mcp import client as api
from snelstart_mcp.audit import AuditLog
from snelstart_mcp.client import Client
from snelstart_mcp.config import SnelStartError, Store
from snelstart_mcp.enums import UpdateStatus
from snelstart_mcp.models.update import UpdateCheckResponse
from snelstart_mcp.server import create_server
from snelstart_mcp.version import installed_version

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
        "/Jaarafsluiting/GetAllJaarafsluiting": fiscal_years(("2024-01-01", "2024-12-31")),
    }

    def handle(request):
        assert request.url.host == "webapi.snelstart.nl"
        requests.append(request)
        reply = replies[request.url.path]
        if callable(reply):
            reply = reply(request)
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


def fiscal_years(*periods):
    rows = [{"boekjaar": {"startDate": start, "endDate": end}} for start, end in periods]
    return {"resultList": rows, "totalMatchCount": len(rows)}


def test_ledger_export_pages_and_filters_each_account(session):
    client, requests, replies = session
    ledger_path = "/Grootboek/GetGrootboekMutaties"
    other = "22222222-2222-4222-8222-222222222222"

    def ledger(request):
        if request.url.params["grootboekIdentifier"] == other:
            return {"resultList": [], "totalMatchCount": 0}
        rows = {
            "0": [{"publicIdentifier": "current", "datum": "2024-12-31T23:00:00"}],
            "1": [{"publicIdentifier": "prior", "datum": "2023-12-31T22:59:59Z"}],
        }
        return {"resultList": rows[request.url.params["skip"]], "totalMatchCount": 2}

    replies[ledger_path] = ledger
    result = call(
        client,
        "snelstart_export_ledger_entries",
        {"ledger_ids": [ENTRY, other], "start_date": "2024-01-01", "through_date": "2024-12-31"},
    )
    assert result["administration_id"] == ADMIN
    assert result["total_exported_rows"] == 1
    assert result["ledgers"][0]["fetched_rows"] == 2
    assert result["ledgers"][1]["exported_rows"] == 0
    exported = Path(result["path"])
    assert stat.S_IMODE(exported.stat().st_mode) == 0o600
    assert sha256(exported.read_bytes()).hexdigest() == result["sha256"]
    assert json.loads(exported.read_text()) == {
        "ledger_id": ENTRY,
        "entry": {"publicIdentifier": "current", "datum": "2024-12-31T23:00:00"},
    }
    ledger_calls = [request for request in requests if request.url.path == ledger_path]
    assert [request.url.params["skip"] for request in ledger_calls] == ["0", "1", "0"]


def test_ledger_export_crosses_a_non_calendar_fiscal_year_boundary(session):
    client, _, replies = session
    replies["/Jaarafsluiting/GetAllJaarafsluiting"] = fiscal_years(
        ("2024-07-01T00:00:00", "2025-06-30T00:00:00"),
        ("2023-07-01T00:00:00", "2024-06-30T00:00:00"),
    )

    def ledger(request):
        through_date = request.url.params["dateTo"][:10]
        rows = {
            "2024-06-30": [{"publicIdentifier": "prior", "datum": "2024-06-30T23:59:59"}],
            "2024-07-01": [{"publicIdentifier": "current", "datum": "2024-07-01T00:00:00"}],
        }
        return {"resultList": rows[through_date], "totalMatchCount": 1}

    replies["/Grootboek/GetGrootboekMutaties"] = ledger
    result = call(
        client,
        "snelstart_export_ledger_entries",
        {"ledger_ids": [ENTRY], "start_date": "2024-06-30", "through_date": "2024-07-01"},
    )
    assert result["total_exported_rows"] == 2
    assert result["ledgers"][0]["fetched_rows"] == 2
    rows = [json.loads(line) for line in Path(result["path"]).read_text().splitlines()]
    assert [row["entry"]["publicIdentifier"] for row in rows] == ["current", "prior"]


def test_ledger_export_checks_all_three_years_when_the_latest_has_no_rows(session):
    client, requests, replies = session
    ledger_path = "/Grootboek/GetGrootboekMutaties"
    counts = {2025: 0, 2024: 15, 2023: 24}
    replies["/Jaarafsluiting/GetAllJaarafsluiting"] = fiscal_years(
        *((f"{year}-01-01", f"{year}-12-31") for year in counts)
    )

    def ledger(request):
        year = int(request.url.params["dateTo"][:4])
        offset = int(request.url.params["skip"])
        rows = [
            {"publicIdentifier": f"{year}-{index}", "datum": f"{year}-01-{index + 1:02d}"}
            for index in range(offset, min(offset + 10, counts[year]))
        ]
        return {"resultList": rows, "totalMatchCount": counts[year]}

    replies[ledger_path] = ledger
    result = call(
        client,
        "snelstart_export_ledger_entries",
        {"ledger_ids": [ENTRY], "start_date": "2023-01-01", "through_date": "2025-12-31"},
    )
    assert result["total_exported_rows"] == 39
    rows = [json.loads(line) for line in Path(result["path"]).read_text().splitlines()]
    assert [row["entry"]["publicIdentifier"] for row in rows] == [
        f"{year}-{index}" for year, count in counts.items() for index in range(count)
    ]
    assert [
        (request.url.params["dateTo"][:10], request.url.params["skip"])
        for request in requests
        if request.url.path == ledger_path
    ] == [
        ("2025-12-31", "0"),
        ("2024-12-31", "0"),
        ("2024-12-31", "10"),
        ("2023-12-31", "0"),
        ("2023-12-31", "10"),
        ("2023-12-31", "20"),
    ]


@pytest.mark.parametrize("next_start", ["2024-12-31", "2025-02-01"])
def test_ledger_export_rejects_ambiguous_fiscal_year_coverage(session, next_start):
    client, requests, replies = session
    replies["/Jaarafsluiting/GetAllJaarafsluiting"] = fiscal_years(
        ("2024-01-01", "2024-12-31"),
        (next_start, "2025-12-31"),
    )
    with pytest.raises(ToolError, match="could not verify fiscal-year coverage"):
        call(
            client,
            "snelstart_export_ledger_entries",
            {"ledger_ids": [ENTRY], "start_date": "2024-01-01", "through_date": "2025-12-31"},
        )
    assert not (client.store.directory / "exports").exists()
    assert all(request.url.path != "/Grootboek/GetGrootboekMutaties" for request in requests)


@pytest.mark.parametrize(
    ("start", "settings_year", "expected_years", "total"),
    [
        ("2026-01-01", 2023, [2026], 51),
        ("2026-01-01", 2026, [2026], 51),
        ("2023-01-01", 2023, [2026, 2025, 2024, 2023], 90),
    ],
)
def test_ledger_export_includes_an_unlisted_active_fiscal_year(
    session, start, settings_year, expected_years, total
):
    client, requests, replies = session
    settings_path = "/Settings/Get"
    ledger_path = "/Grootboek/GetGrootboekMutaties"
    counts = {2023: 24, 2024: 15, 2025: 0, 2026: 51}
    replies["/Jaarafsluiting/GetAllJaarafsluiting"] = fiscal_years(
        *((f"{year}-01-01", f"{year}-12-31") for year in (2023, 2024, 2025))
    )
    replies[settings_path] = {
        "currentFinancialYearStartDate": f"{settings_year}-01-01T00:00:00",
        "currentFinancialYearEndDate": f"{settings_year}-12-31T00:00:00",
    }

    def ledger(request):
        year = int(request.url.params["dateTo"][:4])
        offset = int(request.url.params["skip"])
        rows = [
            {"publicIdentifier": f"{year}-{index}", "datum": f"{year}-01-01"}
            for index in range(offset, min(offset + 25, counts[year]))
        ]
        return {"resultList": rows, "totalMatchCount": counts[year]}

    replies[ledger_path] = ledger
    result = call(
        client,
        "snelstart_export_ledger_entries",
        {"ledger_ids": [ENTRY], "start_date": start, "through_date": "2026-11-24"},
    )
    assert result["total_exported_rows"] == total
    rows = [json.loads(line) for line in Path(result["path"]).read_text().splitlines()]
    assert [row["entry"]["publicIdentifier"] for row in rows] == [
        f"{year}-{index}" for year in expected_years for index in range(counts[year])
    ]
    (settings_request,) = [request for request in requests if request.url.path == settings_path]
    assert settings_request.method == "GET"
    assert not settings_request.url.params
    assert [
        int(request.url.params["dateTo"][:4])
        for request in requests
        if request.url.path == ledger_path and request.url.params["skip"] == "0"
    ] == expected_years


def test_ledger_export_continues_a_configured_non_calendar_fiscal_year(session):
    client, requests, replies = session
    ledger_path = "/Grootboek/GetGrootboekMutaties"
    replies["/Jaarafsluiting/GetAllJaarafsluiting"] = fiscal_years(
        ("2024-07-01", "2025-06-30"),
    )
    replies["/Settings/Get"] = {
        "currentFinancialYearStartDate": "2023-07-01T00:00:00",
        "currentFinancialYearEndDate": "2024-06-30T00:00:00",
    }
    replies[ledger_path] = {"resultList": [], "totalMatchCount": 0}
    result = call(
        client,
        "snelstart_export_ledger_entries",
        {"ledger_ids": [ENTRY], "start_date": "2025-06-30", "through_date": "2026-02-01"},
    )
    assert result["total_exported_rows"] == 0
    assert [
        request.url.params["dateTo"][:10] for request in requests if request.url.path == ledger_path
    ] == ["2026-02-01", "2025-06-30"]


@pytest.mark.parametrize(
    ("settings", "error"),
    [
        ({"currentFinancialYearStartDate": "2026-01-01"}, "from the administration settings"),
        (
            {
                "currentFinancialYearStartDate": "2024-01-01",
                "currentFinancialYearEndDate": "2026-12-31",
            },
            "settings do not establish",
        ),
        (
            {
                "currentFinancialYearStartDate": "2026-02-01",
                "currentFinancialYearEndDate": "2026-12-31",
            },
            "could not verify fiscal-year coverage",
        ),
        (
            {
                "currentFinancialYearStartDate": "2023-07-01",
                "currentFinancialYearEndDate": "2024-06-30",
            },
            "settings do not establish",
        ),
    ],
)
def test_ledger_export_rejects_unverified_coverage_with_an_active_year(session, settings, error):
    client, requests, replies = session
    replies["/Jaarafsluiting/GetAllJaarafsluiting"] = fiscal_years(
        ("2024-01-01", "2024-12-31"), ("2025-01-01", "2025-12-31")
    )
    replies["/Settings/Get"] = settings
    with pytest.raises(ToolError, match=error):
        call(
            client,
            "snelstart_export_ledger_entries",
            {"ledger_ids": [ENTRY], "start_date": "2025-01-01", "through_date": "2026-11-24"},
        )
    assert not (client.store.directory / "exports").exists()
    assert all(request.url.path != "/Grootboek/GetGrootboekMutaties" for request in requests)


def test_incomplete_ledger_export_does_not_leave_partial_file(session):
    client, _, replies = session
    replies["/Jaarafsluiting/GetAllJaarafsluiting"] = fiscal_years(
        ("2024-01-01", "2024-12-31"), ("2025-01-01", "2025-12-31")
    )

    def ledger(request):
        if request.url.params["dateTo"][:4] == "2025":
            return {
                "resultList": [{"publicIdentifier": "newer", "datum": "2025-01-01"}],
                "totalMatchCount": 1,
            }
        return {
            "resultList": [{"publicIdentifier": "repeated", "datum": "2024-01-01"}],
            "totalMatchCount": 2,
        }

    replies["/Grootboek/GetGrootboekMutaties"] = ledger
    with pytest.raises(ToolError, match="duplicate row ID"):
        call(
            client,
            "snelstart_export_ledger_entries",
            {"ledger_ids": [ENTRY], "start_date": "2024-01-01", "through_date": "2025-12-31"},
        )
    assert list((client.store.directory / "exports").iterdir()) == []


def test_purchase_evidence_uses_same_attachment_redaction_and_can_skip_attachments(session):
    client, requests, replies = session
    attachment_path = "/Purchases/GetAttachmentsWithIdentifier"
    replies.update(
        {
            "/Purchases/Get": {"booking": "fixture"},
            "/Purchases/GetInkoopBetalingen": [{"settlement": "fixture"}],
            attachment_path: [
                {"publicIdentifier": ENTRY, "name": "example.pdf", "thumbnailUrl": "private"}
            ],
        }
    )
    (evidence,) = call(client, "snelstart_purchase_evidence", {"purchase_ids": [ENTRY]})["data"]
    assert evidence["purchase_id"] == ENTRY
    assert evidence["purchase"] == {"booking": "fixture"}
    assert evidence["payments"] == [{"settlement": "fixture"}]
    assert evidence["attachments"] == [{"attachmentIdentifier": ENTRY, "fileName": "example.pdf"}]
    requests.clear()
    (without,) = call(
        client,
        "snelstart_purchase_evidence",
        {"purchase_ids": [ENTRY], "include_attachments": False},
    )["data"]
    assert without["attachments"] is None
    assert attachment_path not in [request.url.path for request in requests]


@pytest.mark.parametrize(
    ("tool", "ids", "path", "key"),
    [
        (
            "snelstart_sales_booking_details",
            "booking_ids",
            "/Invoices/GetVerkoopBoekingDetailsForExpandRow",
            "verkoopboekingIdentifier",
        ),
        (
            "snelstart_vat_return_details",
            "return_ids",
            "/BtwAangiftes/GetByPublicIdentifier",
            "publicIentifier",
        ),
    ],
)
def test_batch_detail_tools_keep_order_and_validate_duplicate_ids(session, tool, ids, path, key):
    client, requests, replies = session
    replies[path] = lambda request: {"id": request.url.params[key]}
    with pytest.raises(ToolError, match="only once"):
        call(client, tool, {ids: [ENTRY, ENTRY]})
    assert not requests
    expected = [ENTRY, "22222222-2222-4222-8222-222222222222"]
    assert call(client, tool, {ids: expected})["data"] == [
        {"identifier": identifier, "details": {"id": identifier}} for identifier in expected
    ]
    assert [request.url.params[key] for request in requests if request.url.path == path] == expected


def test_icp_listing_pages_and_preserves_source_validation_messages(session):
    client, requests, replies = session
    path = "/IcpAangiftes/GetIcpAangiftes"
    row = {"publicIdentifier": ENTRY, "aangifteJaar": 2026, "isPersisted": True}
    messages = [{"type": 1, "message": "fixture"}]

    def list_returns(request):
        assert request.method == "GET" and request.url.params["top"] == "1"
        return {
            "icpAangiftes": [row] if request.url.params["skip"] == "0" else [],
            "validationMessages": messages,
        }

    replies[path] = list_returns
    assert call(client, "snelstart_icp_returns", {"take": 1}) == {
        "data": [row],
        "validation_messages": messages,
        "next_skip": 1,
    }
    assert call(client, "snelstart_icp_returns", {"skip": 1, "take": 1}) == {
        "data": [],
        "validation_messages": messages,
        "next_skip": None,
    }
    replies[path] = {"icpAangiftes": [row, row], "validationMessages": []}
    with pytest.raises(ToolError, match="more ICP returns than requested"):
        call(client, "snelstart_icp_returns", {"take": 1})
    assert all(request.method == "GET" for request in requests if request.url.path == path)


def test_invoice_readiness_uses_the_portal_gate_without_returning_company_values(session):
    client, _, replies = session
    replies["/Validation/HasValidCompanySettings"] = False
    replies["/CompanySettings/GetCompanySettings"] = {
        "name": "Example BV",
        "address": "Example 1",
        "zipCode": "1234 AB",
        "city": "Example",
        "email": "",
        "iban": None,
        "vatNumber": "TEST",
        "kvkNumber": "TEST",
    }
    result = call(client, "snelstart_sales_invoice_readiness", {})
    assert result == {"company_settings_valid": False, "blank_company_fields": ["email", "iban"]}


def test_purchase_review_preserves_recognized_values_and_checks_booking_identity(session):
    client, requests, replies = session
    replies["/Purchases/GetGemarkeerdeInkopenOfVraagpostenCount"] = {"aantal": 3}
    assert call(client, "snelstart_purchase_review_count", {}) == {"marked_or_question_items": 3}
    review = "/Purchases/GetTeControlerenInkoop"
    record = {"publicIdentifier": ENTRY, "factuurnummer": "00016", "factuurbedrag": 12.35}
    replies[review] = record
    replies["/Purchases/GetAttachmentsWithIdentifier"] = [{"publicIdentifier": ENTRY}]
    result = call(client, "snelstart_purchase_review_item", {"entry_id": ENTRY})
    assert result == {
        "entry_id": ENTRY,
        "recognition": record,
        "attachments": [{"attachmentIdentifier": ENTRY}],
    }
    assert [dict(request.url.params) for request in requests if request.url.path == review] == [
        {"identifier": ENTRY}
    ]
    assert (
        call(
            client,
            "snelstart_purchase_review_item",
            {"entry_id": ENTRY, "include_attachments": False},
        )["attachments"]
        is None
    )
    replies[review] = {"publicIdentifier": ADMIN}
    with pytest.raises(ToolError, match="requested purchase review item"):
        call(client, "snelstart_purchase_review_item", {"entry_id": ENTRY})


def test_stripe_report_pages_payouts_and_rejects_duplicate_transactions(session, tmp_path):
    client, requests, _ = session
    path = tmp_path / "stripe.csv"
    header = "automatic_payout_id,balance_transaction_id,currency,net\n"
    path.write_text(header + "po_a,txn_1,eur,21.31\npo_a,txn_2,EUR,-2.31\npo_b,txn_3,USD,6\n")
    args = {"provider": "stripe", "file_path": str(path), "take": 1}
    page = call(client, "snelstart_read_payment_report", args)
    assert page["payout_count"] == 2 and page["next_skip"] == 1
    assert page["sha256"] == sha256(path.read_bytes()).hexdigest()
    assert page["payouts"][0]["calculated_net"] == "19.00"
    assert call(client, "snelstart_read_payment_report", args | {"skip": 1})["next_skip"] is None
    path.write_text(header + "po_a,txn_1,EUR,21.31\npo_b,txn_1,EUR,6\n")
    with pytest.raises(ToolError, match="duplicate Stripe balance transaction ID"):
        call(client, "snelstart_read_payment_report", args)
    assert not requests


def test_mollie_report_accepts_localized_headings_and_decimal_commas(session, tmp_path):
    client, _, _ = session
    report = tmp_path / "mollie.csv"
    report.write_text(
        '"Referentie";"Valuta";"Bedrag"\n"REF-001";"EUR";"12,35"\nREF-001;EUR;-1,10\n'
    )
    result = call(
        client,
        "snelstart_read_payment_report",
        {
            "provider": "mollie",
            "file_path": str(report),
            "mollie_columns": {
                "settlement_reference": "Referentie",
                "settlement_currency": "Valuta",
                "settlement_amount": "Bedrag",
            },
        },
    )
    assert result["payouts"][0]["calculated_net"] == "11.25"


def test_adyen_report_keeps_arithmetic_difference_separate_from_bank_evidence(session, tmp_path):
    client, _, replies = session
    report = tmp_path / "adyen.csv"
    report.write_text(
        "Merchant Account,Batch Number,Type,Net Currency,Net Debit (NC),Net Credit (NC),Modification Reference\n"
        "example,1,Settled,EUR,,21.31,\nexample,1,Fee,EUR,2.31,,\n"
        "example,1,MerchantPayout,EUR,19.01,,TXABC123XT batch 1\n"
        "example,2,Settled,EUR,,19.01,\nexample,3,Settled,USD,,19.01,\n"
    )
    replies["/KasBankBoeking/GetKasEnBankDagboeken"] = [{"grootboekIdentifier": ENTRY}]
    replies["/KasBankBoeking/GetKasBankBoekingenWithTimespan"] = {
        "totalMatchCount": 2,
        "resultList": [
            {
                "identifier": ENTRY,
                "date": "2026-01-02",
                "amount": 19.01,
                "description": "TXABC123XT",
            },
            {
                "identifier": ADMIN,
                "date": "2026-01-03",
                "amount": 19.01,
                "description": "unrelated",
            },
        ],
    }
    args = {
        "provider": "adyen",
        "file_path": str(report),
        "bank_journal_id": ENTRY,
        "bank_currency": "EUR",
        "start_date": "2026-01-01",
        "through_date": "2026-01-31",
    }
    result = call(client, "snelstart_compare_payment_report", args)
    exact, ambiguous, other = result["payouts"]
    assert exact["status"] == "reference_and_amount"
    assert exact["payout"]["calculated_net"] == "19.00"
    assert exact["payout"]["declared_payout"] == "19.01"
    assert exact["payout"]["difference"] == "-0.01"
    assert exact["candidates"] == [{"entry_id": ENTRY, "booking_date": "2026-01-02"}]
    assert ambiguous["status"] == "ambiguous" and ambiguous["candidate_count"] == 2
    assert other["status"] == "other_currency" and other["candidates"] == []


def test_icp_details_validate_persisted_ids_and_match_the_response(session):
    client, requests, replies = session
    path = "/IcpAangiftes/GetByPublicIdentifier"
    ids = [ENTRY, "22222222-2222-4222-8222-222222222222"]

    def detail(request):
        assert request.method == "GET"
        return {"publicIdentifier": request.url.params["publicIdentifier"], "totaal": 10}

    replies[path] = detail
    with pytest.raises(ToolError, match="nonzero public identifiers"):
        call(client, "snelstart_icp_return_details", {"return_ids": [str(UUID(int=0))]})
    assert not requests
    records = call(client, "snelstart_icp_return_details", {"return_ids": ids})["data"]
    assert [record["identifier"] for record in records] == ids
    assert [record["details"]["totaal"] for record in records] == [10, 10]
    replies[path] = {"publicIdentifier": ids[1]}
    with pytest.raises(ToolError, match="requested ICP return ID"):
        call(client, "snelstart_icp_return_details", {"return_ids": [ids[0]]})


def test_article_search_uses_source_code_order_and_links_to_details(session):
    client, requests, replies = session
    article = {"articleId": 17, "code": "ABC", "sellingPriceExcludingVat": 20}
    replies["/Articles/Search"] = {"totalMatchCount": 5, "resultList": [article]}
    replies["/Articles/Get"] = article
    result = call(client, "snelstart_search_articles", {"query": "ABC", "skip": 2, "take": 1})
    assert result["data"]["resultList"] == [article]
    assert dict(requests[-1].url.params) == {
        "searchTerm": "ABC",
        "skip": "2",
        "take": "1",
        "sortDataFieldName": "code",
        "sortDescending": "false",
    }
    assert call(client, "snelstart_article_details", {"article_id": 17}) == {"data": article}
    assert dict(requests[-1].url.params) == {"id": "17"}
    with pytest.raises(ToolError, match="requested article ID"):
        call(client, "snelstart_article_details", {"article_id": 18})


def test_ledger_account_details_verify_the_number_and_return_source_settings(session):
    client, requests, replies = session
    account = {"grootboekNumber": 1200, "btw": [], "kostenplaatsInstelling": 1}
    replies["/Grootboek/GetGrootboekByNumber"] = account
    result = call(client, "snelstart_ledger_account_details", {"account_number": 1200})
    assert result == {"data": account}
    assert dict(requests[-1].url.params) == {"number": "1200"}
    with pytest.raises(ToolError, match="requested ledger account number"):
        call(client, "snelstart_ledger_account_details", {"account_number": 1201})


def test_sales_draft_uuid_rejects_a_mixed_batch_before_reading_any_record(session):
    client, requests, _ = session
    with pytest.raises(ToolError, match="Draft sales invoices have no booking UUID"):
        call(
            client,
            "snelstart_sales_booking_details",
            {"booking_ids": [ENTRY, "00000000-0000-0000-0000-000000000000"]},
        )
    assert requests == []


@pytest.mark.parametrize("value", ["00000000-0000-0000-0000-000000000000", "", None])
def test_generic_read_rejects_missing_sales_booking_identifiers_before_contacting_snelstart(
    session, value
):
    client, requests, _ = session
    with pytest.raises(ToolError, match="nonzero verkoopboekingPublicIdentifier"):
        call(
            client,
            "snelstart_read",
            {
                "operation": "GET /Invoices/GetVerkoopBoekingDetailsForExpandRow",
                "parameters": {"verkoopboekingIdentifier": value},
            },
        )
    assert requests == []


@pytest.mark.parametrize(
    ("day", "start", "end"),
    [
        ("2025-12-31", "2025-12-29T23:00:00.000+00:00", "2026-01-01T22:59:59.999+00:00"),
        ("2026-03-29", "2026-03-27T23:00:00.000+00:00", "2026-03-30T21:59:59.999+00:00"),
    ],
)
def test_purchase_query_preserves_local_boundaries_across_dst(session, day, start, end):
    client, requests, replies = session
    path = "/Purchases/SearchAllInkopen"
    replies[path] = {
        "totalMatchCount": 2,
        "resultList": [
            {"publicIdentifier": "wanted", "factuurdatum": day},
            {
                "publicIdentifier": "outside",
                "factuurdatum": (date.fromisoformat(day) - timedelta(days=1)).isoformat(),
            },
        ],
    }
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


def test_numeric_purchase_query_filters_checked_pages_before_applying_skip_and_take(session):
    client, requests, replies = session
    route = "/Purchases/SearchAllInkopen"

    def search(request):
        params = request.url.params
        assert params["onlyTeControlerenInkopen"] == "false"
        if params["searchTerm"] == "001234":
            return {"resultList": [], "totalMatchCount": 0, "searchTerm": ""}
        assert params["searchTerm"] == ""
        rows = {
            "0": [
                {
                    "publicIdentifier": "first",
                    "factuurnummer": "001234",
                    "factuurdatum": "2024-02-29",
                    "isTeControlerenInkoop": True,
                },
                {
                    "publicIdentifier": "different",
                    "factuurnummer": 1234,
                    "factuurdatum": "2024-02-15",
                    "isTeControlerenInkoop": True,
                },
            ],
            "2": [
                {
                    "publicIdentifier": "second",
                    "factuurnummer": "001234",
                    "factuurdatum": "2024-02-01",
                    "isTeControlerenInkoop": True,
                },
                {
                    "publicIdentifier": "outside",
                    "factuurnummer": "001234",
                    "factuurdatum": "2024-01-31",
                    "isTeControlerenInkoop": True,
                },
            ],
        }
        return {"resultList": rows[params["skip"]], "totalMatchCount": 4}

    replies[route] = search
    result = call(
        client,
        "snelstart_search_purchases",
        {
            "query": "001234",
            "start_date": "2024-02-01",
            "through_date": "2024-02-29",
            "review_only": True,
            "skip": 1,
            "take": 1,
        },
    )["data"]
    assert result == {
        "totalMatchCount": 2,
        "resultList": [
            {
                "publicIdentifier": "second",
                "factuurnummer": "001234",
                "factuurdatum": "2024-02-01",
                "isTeControlerenInkoop": True,
            }
        ],
        "searchTerm": "001234",
    }
    assert [
        (request.url.params["searchTerm"], request.url.params["skip"])
        for request in requests
        if request.url.path == route
    ] == [("001234", "0"), ("", "0"), ("", "2")]


@pytest.mark.parametrize("query", ["", "Supplier"])
def test_purchase_review_filter_counts_only_marked_rows_across_checked_pages(session, query):
    client, requests, replies = session
    route = "/Purchases/SearchAllInkopen"
    drafts = [
        {"publicIdentifier": "other-signal", "isBasisControleNodig": True},
        {"publicIdentifier": "unmarked", "isTeControlerenInkoop": False},
        {"publicIdentifier": "first-marked", "isTeControlerenInkoop": True},
        {"publicIdentifier": "second-marked", "isTeControlerenInkoop": True},
        {"publicIdentifier": "no-marker"},
    ]
    rows = [draft | {"factuurdatum": "2024-02-28"} for draft in drafts]

    def search(request):
        params = request.url.params
        assert params["onlyTeControlerenInkopen"] == "false" and params["searchTerm"] == query
        skip = int(params["skip"])
        return {"resultList": rows[skip : skip + 2], "totalMatchCount": len(rows)}

    replies[route] = search
    result = call(
        client,
        "snelstart_search_purchases",
        {
            "query": query,
            "start_date": "2024-02-01",
            "through_date": "2024-02-29",
            "review_only": True,
            "skip": 1,
            "take": 1,
        },
    )["data"]
    assert result["totalMatchCount"] == 2 and result["resultList"] == [rows[3]]
    assert [request.url.params["skip"] for request in requests if request.url.path == route] == [
        "0",
        "2",
        "4",
    ]


def test_exact_purchase_search_accepts_formatted_reference_and_rejects_dual_filters(session):
    client, requests, replies = session
    route = "/Purchases/SearchAllInkopen"
    row = {"publicIdentifier": "exact", "factuurnummer": "INV-001", "factuurdatum": "2024-03-31"}
    replies[route] = {
        "resultList": [row, row | {"publicIdentifier": "prefix", "factuurnummer": "INV-001-A"}],
        "totalMatchCount": 2,
    }
    params = {
        "start_date": "2024-03-01",
        "through_date": "2024-03-31",
        "invoice_number": " INV-001 ",
    }
    result = call(client, "snelstart_search_purchases", params)["data"]
    assert result["totalMatchCount"] == 1 and result["resultList"] == [row]
    assert [
        request.url.params["searchTerm"] for request in requests if request.url.path == route
    ] == [""]
    with pytest.raises(ToolError, match="either invoice_number"):
        call(client, "snelstart_search_purchases", params | {"query": "Supplier"})


@pytest.mark.parametrize(("query", "count"), [("Supplier", 0), ("1234", 1)])
def test_purchase_text_search_keeps_native_matches_without_a_local_fallback(session, query, count):
    client, requests, replies = session
    route = "/Purchases/SearchAllInkopen"
    rows = [{"publicIdentifier": "purchase", "factuurdatum": "2024-01-02"}] if count else []
    replies[route] = {"resultList": rows, "totalMatchCount": count}
    result = call(
        client,
        "snelstart_search_purchases",
        {"query": query, "start_date": "2024-01-01", "through_date": "2024-02-01", "skip": 1},
    )["data"]
    assert result["totalMatchCount"] == count
    assert result["resultList"] == []
    assert [
        request.url.params["searchTerm"] for request in requests if request.url.path == route
    ] == [query]


def test_purchase_search_recovers_missing_row_and_stabilizes_ties_across_calls(session):
    client, _, replies = session
    route = "/Purchases/SearchAllInkopen"
    dates = ["2023-10-01"] * 99 + ["2023-08-15"] * 2 + ["2023-02-01"] * 163
    rows = [
        {"publicIdentifier": f"purchase-{i:03}", "factuurdatum": day} for i, day in enumerate(dates)
    ]
    full_reads = 0

    def search(request):
        nonlocal full_reads
        params = request.url.params
        first = year_data.booking_date(params["startDate"])
        last = year_data.booking_date(params["dateUntil"])
        skip = int(params["skip"])
        take = int(params["take"])
        matches = [row for row in rows if first <= date.fromisoformat(row["factuurdatum"]) <= last]
        if len(matches) == len(rows):
            if not skip:
                full_reads += 1
            if full_reads % 2 == 0 or skip:
                # Two invoices dated August 15 swap places between upstream pages.
                matches[99], matches[100] = matches[100], matches[99]
        elif len(matches) == 101:
            matches[-2], matches[-1] = matches[-1], matches[-2]
        return {"totalMatchCount": len(matches), "resultList": matches[skip : skip + take]}

    replies[route] = search
    params = {"start_date": "2023-01-01", "through_date": "2023-12-31", "take": 100}
    pages = [
        call(client, "snelstart_search_purchases", params | {"skip": skip})["data"]
        for skip in (0, 100, 200)
    ]
    assert full_reads == 3
    assert [page["totalMatchCount"] for page in pages] == [264, 264, 264]
    assert [row for page in pages for row in page["resultList"]] == rows


def test_purchase_search_fails_when_a_single_day_remains_incomplete(session):
    client, _, replies = session
    route = "/Purchases/SearchAllInkopen"
    day = date(2024, 2, 29)
    row = {"publicIdentifier": "duplicated", "factuurdatum": day.isoformat()}

    def search(request):
        params = request.url.params
        if (
            year_data.booking_date(params["startDate"])
            <= day
            <= year_data.booking_date(params["dateUntil"])
        ):
            return {"totalMatchCount": 2, "resultList": [row]}
        return {"totalMatchCount": 0, "resultList": []}

    replies[route] = search
    with pytest.raises(ToolError, match="returned duplicate purchases on 2024-02-29"):
        call(
            client,
            "snelstart_search_purchases",
            {"start_date": day.isoformat(), "through_date": day.isoformat()},
        )


def test_exact_purchase_search_fails_when_complete_coverage_exceeds_the_bound(session):
    client, _, replies = session
    replies["/Purchases/SearchAllInkopen"] = {"resultList": [], "totalMatchCount": 5_001}
    with pytest.raises(ToolError, match="Narrow the date range"):
        call(
            client,
            "snelstart_search_purchases",
            {"invoice_number": "1234", "start_date": "2024-01-01", "through_date": "2024-12-31"},
        )


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
    assert year_data.entries_in_period(
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


def test_only_search_and_vat_calculation_are_catalog_post_reads():
    assert (
        {
            key
            for key, entry in api.catalog().items()
            if entry["method"] != "GET" and entry["read_only"]
        }
        == api.READ_POST_OPERATIONS
        == {
            "POST /Invoices/RedetermineVat",
            "POST /Invoices/Search",
            "POST /Quotations/RedetermineVat",
        }
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
    (listed,) = call(client, "snelstart_list_archives", {})["data"]
    assert listed["archive"] == created["archive"] and listed["path"] == created["path"]
    assert listed["year"] == 2020 and listed["through_date"] == "2020-12-31"
    assert listed["size_bytes"] == Path(created["path"]).stat().st_size
    assert datetime.fromisoformat(listed["created_at"]) == datetime.fromisoformat(
        created["created_at"]
    )
    assert listed["manifest_readable"] and not listed["bacpac_included"]
    assert not requests


def test_archive_inventory_uses_manifest_dates_and_skips_payload_checks(tmp_path):
    store = Store(tmp_path / "profile")
    directory = store.directory / "backups"
    assert backup.list_archives(store).archives == []
    assert not directory.exists()
    directory.mkdir()
    newer = directory / ("snelstart-2021-" + "a" * 32 + ".zip")
    older = directory / ("snelstart-2020-" + "b" * 32 + ".zip")
    corrupt = directory / ("snelstart-2022-" + "c" * 32 + ".zip")
    link = directory / ("snelstart-2023-" + "d" * 32 + ".zip")
    legacy = {
        "format": backup.LEGACY_ARCHIVE["version"],
        "boekjaar": 2021,
        "tot_en_met": "2021-10-31",
        "gemaakt_op": "2026-06-01T12:00:00+00:00",
        "administratie_id_mcp_export": ADMIN,
        "bestanden": {"administratie.bacpac": {"bytes": 1, "sha256": "0" * 64}},
    }
    with ZipFile(newer, "w") as archive:
        archive.writestr("manifest.json", json.dumps(legacy))
        archive.writestr("administratie.bacpac", "wrong checksum")
    with ZipFile(older, "w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "format": backup.ARCHIVE_FORMAT,
                    "year": 2020,
                    "through_date": "2020-12-31",
                    "created_at": "2026-05-01T12:00:00+00:00",
                    "files": {"audit_file.xaf": {"bytes": 1, "sha256": "0" * 64}},
                }
            ),
        )
        archive.writestr("audit_file.xaf", "archive payload")
    corrupt.write_text("incomplete archive")
    link.symlink_to(newer)
    entries = backup.list_archives(store).archives
    assert [entry.path for entry in entries] == [newer, older, corrupt]
    assert entries[0].bacpac_included and entries[0].mcp_administration_id == UUID(ADMIN)
    assert entries[0].through_date == date(2021, 10, 31)
    assert not entries[1].bacpac_included
    assert not entries[2].manifest_readable and entries[2].created_at is None
    with pytest.raises(SnelStartError, match="Checksum mismatch"):
        backup.verify_archive(store, newer.name)


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
    assert requests[-1].url.params["onlyTeControlerenInkopen"] == "false"

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
                "administration_id": ADMIN,
                "payload": {"password": "PRIVATE-PASSWORD"},
            },
        )
    events = call(client, "snelstart_audit_log", {"limit": 10})["data"]
    outcomes = {event["tool"]: event["outcome"] for event in events}
    assert outcomes["snelstart_search_relations"] == "ok"
    assert outcomes["snelstart_write"] == "error"
    audit_file = AuditLog(client.store).path(UUID(ADMIN))
    assert stat.S_IMODE(audit_file.stat().st_mode) == 0o600
    assert b"PRIVATE-" not in audit_file.read_bytes()


def test_update_notice_is_visible_in_mcp_status_and_update_tool(session, monkeypatch):
    client, requests, _ = session
    notice = UpdateCheckResponse(
        status=UpdateStatus.AVAILABLE,
        installed_version="2026.1.1",
        latest_version="2026.1.2",
        message="An update is available.",
    )
    monkeypatch.setattr("snelstart_mcp.updater._check_update", lambda: notice)
    status = call(client, "snelstart_status", {})
    assert status["update"]["status"] == "available"
    assert status["server_version"] == installed_version()
    assert call(client, "snelstart_check_update", {})["latest_version"] == "2026.1.2"
    assert not requests


def test_tool_is_blocked_if_audit_intent_cannot_be_saved(session, monkeypatch):
    client, requests, _ = session
    server = create_server(client)

    def fail(tool):
        raise SnelStartError("Could not write the local audit log.")

    monkeypatch.setattr(server.audit, "start", fail)
    with pytest.raises(ToolError, match="Could not write the local audit log"):
        asyncio.run(server.call_tool("snelstart_chart_of_accounts", {}))
    assert not requests


def test_tool_does_not_use_a_different_administration_than_its_audit_database(session, monkeypatch):
    client, requests, _ = session
    server = create_server(client)
    start = server.audit.start
    other = "22222222-2222-4222-8222-222222222222"

    def switch_after_start(tool):
        event = start(tool)
        client.store.write("config.json", {"administration_id": other})
        return event

    monkeypatch.setattr(server.audit, "start", switch_after_start)
    with pytest.raises(ToolError, match="selected administration changed"):
        asyncio.run(server.call_tool("snelstart_chart_of_accounts", {}))
    assert not requests
    assert server.audit.report(UUID(ADMIN), 1).summary.failed == 1
    assert server.audit.report(UUID(other), 1).summary.total_calls == 0


def test_corrupt_audit_database_blocks_reads_and_tool_execution(session):
    client, requests, _ = session
    audit = AuditLog(client.store)
    path = audit.path(UUID(ADMIN))
    path.parent.mkdir()
    path.write_bytes(b"not a database")
    with pytest.raises(ToolError, match="Could not write the local audit log"):
        call(client, "snelstart_list_administrations", {})
    with pytest.raises(SnelStartError, match="Could not read the local audit log"):
        audit.recent(10)
    assert not requests
    assert path.read_bytes() == b"not a database"


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
    assert [event.outcome for event in server.audit.recent(1)] == ["pending"]


def test_unknown_tool_name_is_redacted_in_audit_even_with_invalid_config(session):
    client, requests, _ = session
    client.store.write("config.json", {"allow_writes": "false"})
    with pytest.raises(ToolError):
        call(client, "PRIVATE-INVALID-TOOL", {})
    (event,) = AuditLog(client.store).recent(1)
    assert event.tool == "unknown_tool"
    assert event.outcome == "error"
    assert event.administration_id is None
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
            {"operation": "GET /Administrations/All", "payload": {}, "administration_id": ADMIN},
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
        year_data.entries_in_period([row], date(2020, 1, 1), date(2020, 12, 31), "date")


def test_invalid_config_flag_cannot_enable_writes(session):
    client, requests, _ = session
    client.store.write("config.json", {"administration_id": ADMIN, "allow_writes": "false"})
    with pytest.raises(SnelStartError, match="Invalid MCP configuration"):
        client.request("POST /MemoriaalBoekingen/Create", body={})
    assert not requests


def test_local_write_permission_is_limited_to_one_operation_and_administration(
    session, monkeypatch
):
    client, requests, replies = session
    operation = "POST /MemoriaalBoekingen/Create"
    client.store.write(
        "config.json", {"administration_id": ADMIN, "write_permissions": {ADMIN: [operation]}}
    )
    replies["/MemoriaalBoekingen/Create"] = {"fixture": True}
    payload = {"description": "synthetic request"}
    args = {"operation": operation, "payload": payload, "administration_id": ADMIN}
    monkeypatch.setattr("snelstart_mcp.tools_connection.require_approval", lambda *_: None)
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
    with pytest.raises(ToolError, match="differs from the write request"):
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
            {
                "operation": "POST /MemoriaalBoekingen/Create",
                "payload": {},
                "administration_id": ADMIN,
            },
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
