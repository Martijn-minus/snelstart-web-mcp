"""Read-only checks for special purchase and ledger-account workflows."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ..enums import CostCentreRequirement, PurchasePostingKind, PurchaseVatBand
from . import JsonObject
from .requests import AdministrationRequest


class PurchasePostingCheckRequest(AdministrationRequest):
    kind: PurchasePostingKind = PurchasePostingKind.STANDARD
    account_number: int = Field(ge=0)
    vat_band: PurchaseVatBand | None = None
    cost_centre_id: UUID | None = None
    invoice_total: Decimal | None = Field(default=None, gt=0, decimal_places=2, max_digits=14)
    paid_amount: Decimal | None = Field(default=None, gt=0, decimal_places=2, max_digits=14)
    purchase_id: UUID | None = None
    purchase_invoice_id: UUID | None = None

    @model_validator(mode="after")
    def check_workflow_inputs(self):
        foreign = self.kind in {PurchasePostingKind.INTRA_EU, PurchasePostingKind.OUTSIDE_EU}
        if foreign != (self.vat_band is not None):
            raise ValueError("Choose the Dutch VAT band for a foreign purchase only.")
        if self.cost_centre_id is not None and self.cost_centre_id.int == 0:
            raise ValueError("Provide a nonzero cost-centre identifier.")
        if (self.purchase_id is not None and self.purchase_id.int == 0) or (
            self.purchase_invoice_id is not None
            and (self.purchase_id is None or self.purchase_invoice_id.int == 0)
        ):
            raise ValueError("Provide nonzero purchase identifiers from the same search row.")
        if self.kind is PurchasePostingKind.PAYMENT_DISCOUNT:
            if (
                self.invoice_total is None
                or self.paid_amount is None
                or self.paid_amount >= self.invoice_total
            ):
                raise ValueError(
                    "Provide the gross invoice total and a smaller positive settled payment."
                )
        elif self.invoice_total is not None or self.paid_amount is not None:
            raise ValueError(
                "Invoice total and settled payment apply to the payment discount check."
            )
        return self


class PurchasePostingEvidence(BaseModel):
    purchase_id: UUID
    matching_lines: list[JsonObject]
    vat_lines: list[JsonObject] | None
    selected_cost_centre_recorded: bool | None = None


class PurchasePostingCheck(BaseModel):
    administration_id: UUID
    kind: PurchasePostingKind
    account_number: int
    account_name: str
    account_id: UUID | None
    account_function: int
    expected_function: int | None
    account_matches_workflow: bool
    cost_centre_requirement: CostCentreRequirement
    cost_centre_id: UUID | None
    cost_centre_input_matches_account: bool
    expected_vat_box: str | None
    payment_discount: Decimal | None
    purchase_evidence: PurchasePostingEvidence | None = None
    steps: list[str]
