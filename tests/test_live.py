"""Opt-in live contract test, isolated from the default administration and session."""

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from snelstart_mcp.backup import DATASETS
from snelstart_mcp.client import Client, catalog
from snelstart_mcp.config import SnelStartError, Store
from snelstart_mcp.dates import AMSTERDAM
from snelstart_mcp.server import create_server
from snelstart_mcp.version import installed_version

TEST_ADMINISTRATION = "mcp-test"


def test_stdio_handshake_reports_the_running_package_version(tmp_path):
    async def check():
        command = StdioServerParameters(
            command=sys.executable,
            args=["-m", "snelstart_mcp.cli", "--config-dir", str(tmp_path), "serve"],
        )
        async with stdio_client(command) as (reader, writer), ClientSession(reader, writer) as mcp:
            protocol = await mcp.initialize()
            assert protocol.serverInfo.version == installed_version()
            assert "snelstart_list_archives" in protocol.instructions
            assert "snelstart_create_year_archive" in protocol.instructions
            assert "snelstart_verify_archive" in protocol.instructions

    asyncio.run(check())


class IsolatedTestStore(Store):
    def __init__(self, directory: Path, source: Store):
        super().__init__(directory)
        self.source = source

    def read(self, name: str) -> dict:
        # Reuse the authorized login in memory. Tokens and the selected administration
        # belong to the temporary profile, not to the user’s regular profile.
        return self.source.read(name) if name == "credentials.json" else super().read(name)


def test_isolated_profile_does_not_borrow_the_default_refresh_token(tmp_path):
    source = Store(tmp_path / "default")
    source.write("tokens.json", {"refresh_token": "default-token"})
    source.write("credentials.json", {"username": "test@example.test", "password": "test"})
    isolated = IsolatedTestStore(tmp_path / "test-profile", source)
    assert isolated.read("credentials.json")["username"] == "test@example.test"
    assert isolated.read("tokens.json") == {}
    isolated.write("tokens.json", {"refresh_token": "test-token"})
    assert source.read("tokens.json") == {"refresh_token": "default-token"}
    assert not (isolated.directory / "credentials.json").exists()


class ReadOnlyTestClient(Client):
    test_admin_id: str | None = None

    def select_administration(self, identifier: str, persist: bool = True):
        if identifier != self.test_admin_id:
            raise SnelStartError("Live tests may only open the mcp-test administration.")
        return super().select_administration(identifier, persist)

    def _send(self, method, path, *args, **kwargs):
        operation = f"{method} {path}"
        if operation != "POST /Administrations/Open" and not catalog().get(operation, {}).get(
            "read_only"
        ):
            raise SnelStartError("Live tests may not send bookkeeping mutations.")
        return super()._send(method, path, *args, **kwargs)


def serve_test_profile(path: Path):
    client = ReadOnlyTestClient(IsolatedTestStore(path, Store()))
    try:
        eligible = [
            row
            for row in client.administrations()
            if row.get("administrationName") == TEST_ADMINISTRATION
        ]
        if len(eligible) != 1:
            raise SnelStartError("Live tests require exactly one administration named mcp-test.")
        client.test_admin_id = eligible[0]["identifier"]
        client.select_administration(client.test_admin_id)
        create_server(client).run(transport="stdio")
    finally:
        client.close()


async def run_live_contract(path: Path):
    command = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).resolve()), "--serve", str(path)],
    )
    async with stdio_client(command) as (reader, writer), ClientSession(reader, writer) as mcp:
        protocol = await mcp.initialize()
        assert "Check the selected SnelStart administration" in protocol.instructions
        tools = {entry.name: entry for entry in (await mcp.list_tools()).tools}
        assert "Search sales invoices" in tools["snelstart_search_sales"].description
        assert tools["snelstart_upload_purchase_pdf"].annotations.readOnlyHint is False
        assert tools["snelstart_purchase_upload_status"].annotations.readOnlyHint is True

        async def call(tool, arguments=None, *, expect_error=False, missing_route=None):
            response = await mcp.call_tool(tool, arguments or {})
            if response.isError and missing_route:
                message = response.content[0].text
                if f"HTTP 404 for GET {missing_route}." in message:
                    return None
            assert bool(response.isError) is expect_error, f"{tool}: {response.content[0].text}"
            if expect_error:
                return response.content[0].text
            if response.structuredContent is not None:
                return response.structuredContent
            return json.loads(response.content[0].text)

        status = await call("snelstart_status")
        administrations = (await call("snelstart_list_administrations"))["result"]
        match = [
            row for row in administrations if row.get("administrationName") == TEST_ADMINISTRATION
        ]
        assert len(match) == 1 and status["administration_id"] == match[0]["identifier"]
        assert status["configured"] and status["allow_writes"] is False
        assert status["approved_write_operations"] == []
        readiness = await call("snelstart_sales_invoice_readiness")
        assert isinstance(readiness["company_settings_valid"], bool)
        queue = await call("snelstart_purchase_review_count")
        assert queue["marked_or_question_items"] >= 0

        today = datetime.now(AMSTERDAM).date()
        period = {"start_date": f"{today.year}-01-01", "through_date": today.isoformat()}
        assert (await call("snelstart_list_operations", {"query": "Invoices/Search"}))["total"] == 1
        accounts = (await call("snelstart_chart_of_accounts"))["data"]
        assert isinstance(accounts, list)
        ledger_ids = []
        for row in accounts[:3]:
            number = row["grootboekNumber"]
            account = await call("snelstart_ledger_account_details", {"account_number": number})
            assert account["data"]["grootboekNumber"] == number
            identifier = UUID(account["data"]["publicIdentifier"])
            assert identifier.int and identifier == UUID(row["grootboekId"])
            ledger_ids.append(str(identifier))
        if ledger_ids:
            exported = await call(
                "snelstart_export_ledger_entries", {**period, "ledger_ids": ledger_ids}
            )
            assert [ledger["ledger_id"] for ledger in exported["ledgers"]] == ledger_ids
        assert (
            "balans"
            in (await call("snelstart_balance_sheet", {"through_date": today.isoformat()}))["data"]
        )
        result = (await call("snelstart_financial_result", period))["data"]
        assert {"financialResult", "startDateBoekjaar", "endDateBoekjaar"} <= result.keys()
        for tool, args in [
            ("snelstart_search_purchases", {**period, "take": 1}),
            ("snelstart_search_purchases", {**period, "take": 1, "review_only": True}),
            ("snelstart_search_sales", {"status": "all", "take": 1}),
            ("snelstart_search_relations", {"kind": "customers", "take": 1}),
            ("snelstart_search_relations", {"kind": "suppliers", "take": 1}),
        ]:
            assert isinstance((await call(tool, args))["data"]["resultList"], list)
        assert isinstance((await call("snelstart_vat_returns"))["data"], list)
        icp = await call("snelstart_icp_returns", {"take": 10})
        assert isinstance(icp["data"], list) and isinstance(icp["validation_messages"], list)
        for row in icp["data"]:
            if row.get("isPersisted") and row.get("publicIdentifier"):
                ref = str(UUID(row["publicIdentifier"]))
                detail = await call("snelstart_icp_return_details", {"return_ids": [ref]})
                assert detail["data"][0]["identifier"] == ref
                break
        articles = await call("snelstart_search_articles", {"take": 1})
        assert isinstance(articles["data"]["resultList"], list)
        if articles["data"]["resultList"]:
            article_id = articles["data"]["resultList"][0]["articleId"]
            article = await call("snelstart_article_details", {"article_id": article_id})
            assert article["data"]["articleId"] == article_id
        assert isinstance((await call("snelstart_supplemental_vat_years"))["data"], list)
        banks = (await call("snelstart_bank_journals"))["data"]
        assert isinstance(banks, list)
        if banks:
            bank = await call(
                "snelstart_bank_entries",
                {
                    **period,
                    "ledger_id": banks[0]["grootboekIdentifier"],
                    "take": 1,
                },
            )
            assert isinstance(bank["data"]["resultList"], list)
        closed = await call(
            "snelstart_year_end_review",
            {
                "year": today.year,
                "section": "open_purchases",
            },
            missing_route="/Jaarafsluiting/GetOpenstaandeInkoopfacturen",
        )
        # A new administration can lack this year-end route data. The MCP must
        # preserve the HTTP 404 instead of returning a misleading empty list.
        if closed is not None:
            assert isinstance(closed["data"], list)

        denial = await call(
            "snelstart_write",
            {
                "operation": "POST /MemoriaalBoekingen/Create",
                "administration_id": status["administration_id"],
                "payload": {},
            },
            expect_error=True,
        )
        assert "Writing is disabled" in denial
        await call(
            "snelstart_read",
            {
                "operation": "POST /MemoriaalBoekingen/Create",
            },
            expect_error=True,
        )
        events = (await call("snelstart_audit_log"))["data"]
        assert any(e["tool"] == "snelstart_write" and e["outcome"] == "error" for e in events)
        assert any(e["tool"] == "snelstart_search_sales" and e["outcome"] == "ok" for e in events)

        archive = await call(
            "snelstart_create_year_archive",
            {
                "year": today.year,
                "through_date": today.isoformat(),
            },
        )
        checked = await call("snelstart_verify_archive", {"archive": archive["archive"]})
        assert checked["verified"]
        assert checked["mcp_administration_id"] == status["administration_id"]
        assert set(checked["files"]) == {f"{name}.json" for name in DATASETS}
        listed = await call("snelstart_list_archives")
        assert listed["data"][0]["archive"] == archive["archive"]


@pytest.mark.skipif(os.getenv("SNELSTART_RUN_LIVE") != "1", reason="opt-in live test on mcp-test")
def test_live_contract():
    source = Store()
    previous = source.settings().administration_id
    with tempfile.TemporaryDirectory(prefix="test-profiel-", dir=source.directory) as tmp:
        asyncio.run(run_live_contract(Path(tmp)))
    assert source.settings().administration_id == previous


if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--serve":
    serve_test_profile(Path(sys.argv[2]))
