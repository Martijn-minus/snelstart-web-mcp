"""Typed requests and results for sales documents and outgoing email."""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated
from uuid import UUID

from pydantic import AliasChoices, BaseModel, Field, StringConstraints

from ..enums import (
    MailHistoryStatus,
    QuotationStatus,
    SalesDocumentKind,
    SalesEmailOutcome,
    SalesPricing,
)
from . import JsonObject
from .requests import AdministrationRequest, PageRequest, ToolRequest

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=250)]


class QuotationSearchRequest(PageRequest):
    status: QuotationStatus = QuotationStatus.ALL


class QuotationDetailsRequest(ToolRequest):
    quotation_id: UUID


class MailHistoryRequest(PageRequest):
    status: MailHistoryStatus = MailHistoryStatus.ALL


class MailHistoryAttachment(BaseModel):
    name: str
    extension: str | None = None
    size_bytes: int | None = Field(
        default=None, validation_alias=AliasChoices("size_bytes", "originalSizeInBytes")
    )


class MailHistoryEntry(BaseModel):
    sent_at: datetime | None = Field(
        default=None, validation_alias=AliasChoices("sent_at", "sendDate")
    )
    sender: str | None = Field(default=None, validation_alias=AliasChoices("sender", "addressFrom"))
    recipient: str | None = Field(
        default=None, validation_alias=AliasChoices("recipient", "addressTo")
    )
    subject: str | None = None
    status_code: int | str | None = Field(
        default=None, validation_alias=AliasChoices("status_code", "mailStatusCode")
    )
    object_type: int | None = Field(
        default=None, validation_alias=AliasChoices("object_type", "objectType")
    )
    document_type: int | None = Field(
        default=None, validation_alias=AliasChoices("document_type", "documentType")
    )
    attachments: list[MailHistoryAttachment] = Field(default_factory=list)


class MailHistory(BaseModel):
    total: int = Field(ge=0)
    skip: int
    take: int
    messages: list[MailHistoryEntry]


class MailTemplateRequest(ToolRequest):
    kind: SalesDocumentKind


class MailTemplate(BaseModel):
    kind: SalesDocumentKind
    subject: str
    message: str
    attachments: list[JsonObject]


class SalesLine(BaseModel):
    article_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    description: ShortText | None = None
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=4)


class SalesDocumentRequest(AdministrationRequest):
    kind: SalesDocumentKind
    customer_code: int = Field(gt=0)
    document_date: date
    order_date: date | None = None
    payment_term_days: int | None = Field(default=None, ge=0, le=365)
    reference: ShortText | None = None
    pricing: SalesPricing = SalesPricing.EXCLUSIVE
    discount_percent: Decimal = Field(default=Decimal(0), ge=0, le=100, decimal_places=4)
    lines: list[SalesLine] = Field(min_length=1, max_length=50)


class SalesVatTotal(BaseModel):
    base: Decimal = Field(validation_alias=AliasChoices("base", "baseTotal"))
    vat_amount: Decimal = Field(validation_alias=AliasChoices("vat_amount", "vatTotal"))


class SalesDocumentPreview(BaseModel):
    administration_id: UUID
    kind: SalesDocumentKind
    customer_code: int
    document_date: date
    currency: str = "EUR"
    net: Decimal
    gross: Decimal
    discount: Decimal
    vat_breakdown: list[SalesVatTotal]
    reference: str | None


class SalesSaveRequest(SalesDocumentRequest):
    expected_gross: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    draft: bool = False
    approval_id: UUID | None = None


class SalesSaveResult(BaseModel):
    preview: SalesDocumentPreview
    draft: bool
    order_number: int | None = None
    invoice_number: str | int | None = None


SingleEmailAddress = Annotated[
    str,
    StringConstraints(
        max_length=254,
        pattern=r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$",
    ),
]


class SalesEmailRequest(SalesDocumentRequest):
    expected_gross: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    recipient: SingleEmailAddress
    subject: ShortText
    message: str = Field(min_length=1, max_length=20000)
    attachment_paths: list[Path] | None = Field(default=None, max_length=10)
    approval_id: UUID | None = None


class SalesEmailResult(BaseModel):
    preview: SalesDocumentPreview
    outcome: SalesEmailOutcome
    order_number: int | None = None
    invoice_number: str | int | None = None
    upstream_status: int | None = None
