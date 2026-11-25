"""Validated parts of the SnelStart Web API contract."""

from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

from ..enums import HttpMethod
from . import JsonObject

SALES_BOOKING_DETAILS = "GET /Invoices/GetVerkoopBoekingDetailsForExpandRow"
SALES_BOOKING_ID_PARAMETER = "verkoopboekingIdentifier"
SALES_BOOKING_ID_ERROR = (
    "Provide a posted sale's nonzero verkoopboekingPublicIdentifier. "
    "Draft sales invoices have no booking UUID."
)


def _posted_sales_booking_id(identifier: UUID) -> UUID:
    if identifier.int == 0:
        raise ValueError(SALES_BOOKING_ID_ERROR)
    return identifier


PostedSalesBookingId = Annotated[
    UUID, AfterValidator(_posted_sales_booking_id), Field(description=SALES_BOOKING_ID_ERROR)
]
SALES_BOOKING_ID = TypeAdapter(PostedSalesBookingId)


class OperationSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    method: HttpMethod
    path: str
    query_parameters: list[str]
    required_parameters: list[str]
    json_body: bool
    read_only: bool
    write_warning: str | None = Field(default=None, exclude_if=lambda value: value is None)


class WebApiRequest(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    operation: str
    parameters: JsonObject | None = None
    body: JsonValue = None
    download: bool = False
    expected_administration: UUID | None = None


class InvoiceSearchTerm(BaseModel):
    term: str
    match_exactly: bool = Field(default=False, serialization_alias="hasToMatchExactly")


class InvoiceSearchBody(BaseModel):
    query: str = Field(serialization_alias="rawSearchTerm")
    global_terms: list[InvoiceSearchTerm] = Field(serialization_alias="globalSearchTerms")
    column_terms: list[JsonObject] = Field(
        default_factory=list, serialization_alias="columnSearchTerms"
    )


class JournalReference(BaseModel):
    grootboekIdentifier: UUID


class GeneralJournalReference(JournalReference):
    grootboekFunctieId: int


class PurchaseDetailIdentity(BaseModel):
    publicIdentifier: UUID
    factuurNummerIdentifier: UUID


class IcpReturnListing(BaseModel):
    model_config = ConfigDict(strict=True)

    icpAangiftes: list[JsonObject]
    validationMessages: list[JsonObject]


JSON_VALUE = TypeAdapter(JsonValue)
JSON_ROWS = TypeAdapter(list[JsonObject])
