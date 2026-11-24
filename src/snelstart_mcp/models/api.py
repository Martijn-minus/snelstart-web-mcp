"""Validated parts of the SnelStart Web API contract."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

from ..enums import HttpMethod
from . import JsonObject


class OperationSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    method: HttpMethod
    path: str
    query_parameters: list[str]
    required_parameters: list[str]
    json_body: bool
    read_only: bool


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


JSON_VALUE = TypeAdapter(JsonValue)
JSON_ROWS = TypeAdapter(list[JsonObject])
