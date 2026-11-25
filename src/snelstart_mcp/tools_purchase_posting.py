"""Check the live chart of accounts before specialised purchase posting."""

from uuid import UUID

from .client import Client
from .config import SnelStartError
from .enums import CostCentreRequirement, EntryKind, PurchasePostingKind, PurchaseVatBand
from .models import JsonObject
from .models.api import JSON_ROWS
from .models.purchase_posting import (
    PurchasePostingCheck,
    PurchasePostingCheckRequest,
    PurchasePostingEvidence,
)
from .models.requests import EntryDetailRequest
from .tooling import READ, Register
from .tools_bookkeeping import read_booking_entry

COST_CENTRE_MODES = {
    0: CostCentreRequirement.FORBIDDEN,
    1: CostCentreRequirement.OPTIONAL,
    2: CostCentreRequirement.REQUIRED,
}
VAT_BAND_OFFSET = {
    PurchaseVatBand.LOW: 1,
    PurchaseVatBand.HIGH: 2,
    PurchaseVatBand.OTHER: 3,
}


def read_purchase_evidence(
    client: Client, request: PurchasePostingCheckRequest, ledger_id: int
) -> PurchasePostingEvidence | None:
    if request.purchase_id is None:
        return None
    detail = read_booking_entry(
        lambda operation, params: client.request(
            operation, params, expected_administration=str(request.administration_id)
        ),
        EntryDetailRequest(
            kind=EntryKind.PURCHASE,
            entry_id=request.purchase_id,
            purchase_invoice_id=request.purchase_invoice_id,
        ),
    ).data
    if not isinstance(detail, dict) or detail.get("publicIdentifier") != str(request.purchase_id):
        raise SnelStartError("SnelStart did not return the requested purchase for review.")
    lines = JSON_ROWS.validate_python(detail.get("boekingsregels"))
    matches: list[JsonObject] = [
        {
            key: row[key]
            for key in ("bedrag", "grootboekIdentifier", "kostenplaatsIdentifier", "btwSoort")
            if key in row
        }
        for row in lines
        if row.get("grootboekId") == ledger_id
    ]
    vat = detail.get("btw")
    return PurchasePostingEvidence(
        purchase_id=request.purchase_id,
        matching_lines=matches,
        vat_lines=JSON_ROWS.validate_python(vat) if vat is not None else None,
        selected_cost_centre_recorded=(
            any(row.get("kostenplaatsIdentifier") == str(request.cost_centre_id) for row in matches)
            if request.cost_centre_id is not None
            else None
        ),
    )


def register_purchase_posting_tools(tool: Register, client: Client) -> None:
    @tool(annotations=READ)
    def snelstart_check_purchase_posting(
        request: PurchasePostingCheckRequest,
    ) -> PurchasePostingCheck:
        """Check a live ledger account for reverse charge, foreign purchases, cost centres or settled payment discounts."""
        account = client.request(
            "GET /Grootboek/GetGrootboekByNumber",
            {"number": request.account_number},
            expected_administration=str(request.administration_id),
        )
        if (
            not isinstance(account, dict)
            or account.get("grootboekNumber") != request.account_number
            or type(function := account.get("grootboekfunctieId")) is not int
            or not isinstance(name := account.get("grootboekDescription"), str)
            or type(ledger_id := account.get("grootboekId")) is not int
            or type(cost_setting := account.get("kostenplaatsInstelling")) is not int
            or cost_setting not in COST_CENTRE_MODES
        ):
            raise SnelStartError(
                "SnelStart did not return the requested account and posting settings."
            )
        identifier = account.get("publicIdentifier")
        account_id = UUID(identifier) if isinstance(identifier, str) else None
        requirement = COST_CENTRE_MODES[cost_setting]
        allowed = requirement is CostCentreRequirement.OPTIONAL or (
            requirement is CostCentreRequirement.REQUIRED
        ) == (request.cost_centre_id is not None)
        expected = None
        vat_box = None
        discount = None
        steps: list[str] = []
        if request.kind is PurchasePostingKind.DOMESTIC_REVERSE_CHARGE:
            expected = 32
            vat_box = "2a"
            steps = [
                "Verify the supplier invoice qualifies for domestic reverse charge.",
                "Save and reopen the purchase on the function 32 cost account, then apply the reverse-charge setting.",
                "Read the posted booking and the VAT evidence after saving.",
            ]
        elif (
            request.kind in {PurchasePostingKind.INTRA_EU, PurchasePostingKind.OUTSIDE_EU}
            and request.vat_band is not None
        ):
            within_eu = request.kind is PurchasePostingKind.INTRA_EU
            expected = (60 if within_eu else 70) + VAT_BAND_OFFSET[request.vat_band]
            vat_box = "4b" if within_eu else "4a"
            steps = [
                "Confirm the foreign purchase type and applicable Dutch VAT band from the source invoice.",
                "Select the account with the indicated function and verify the generated VAT entries and applicable return boxes.",
            ]
        elif request.kind is PurchasePostingKind.PAYMENT_DISCOUNT:
            expected = 102
            if request.invoice_total is not None and request.paid_amount is not None:
                discount = request.invoice_total - request.paid_amount
            steps = [
                "Match the actual bank payment against the purchase before applying the difference.",
                "Record the remaining settlement difference on the function 102 account and review the separate VAT correction.",
            ]
        if requirement is CostCentreRequirement.REQUIRED:
            steps.append("Select and verify an active cost centre before posting.")
        elif request.cost_centre_id is not None and requirement is CostCentreRequirement.FORBIDDEN:
            steps.append("Remove the cost centre or choose an account that allows one.")
        return PurchasePostingCheck(
            administration_id=request.administration_id,
            kind=request.kind,
            account_number=request.account_number,
            account_name=name,
            account_id=account_id if account_id is not None and account_id.int else None,
            account_function=function,
            expected_function=expected,
            account_matches_workflow=expected is None or function == expected,
            cost_centre_requirement=requirement,
            cost_centre_id=request.cost_centre_id,
            cost_centre_input_matches_account=allowed,
            expected_vat_box=vat_box,
            payment_discount=discount,
            purchase_evidence=read_purchase_evidence(client, request, ledger_id),
            steps=steps,
        )
