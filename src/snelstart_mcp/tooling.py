"""Shared tool registration, error presentation and pagination guards."""

from collections.abc import Callable
from functools import wraps
from inspect import Parameter, signature
from typing import Any, Protocol

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import ValidationError

from .config import SnelStartError
from .models.requests import ToolRequest

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True)


class Register(Protocol):
    def __call__(self, *, annotations: ToolAnnotations) -> Callable[..., Any]: ...


def validate_request(request: type[ToolRequest], arguments: dict) -> ToolRequest:
    try:
        return request.model_validate(arguments)
    except ValidationError as error:
        for detail in error.errors(include_input=False, include_context=False, include_url=False):
            if detail["type"] == "value_error":
                raise ToolError(detail["msg"].removeprefix("Value error, ")) from None
        raise ToolError("Invalid input for this SnelStart tool.") from None


def tool_registrar(
    mcp: FastMCP,
    registered_requests: dict[str, type[ToolRequest] | None],
    *,
    read_only: bool = False,
) -> Register:
    def tool(*, annotations: ToolAnnotations):
        def register(function):
            if read_only and annotations.destructiveHint:
                return function
            contract = signature(function)
            request_parameter = contract.parameters.get("request")
            request = request_parameter.annotation if request_parameter else None

            @wraps(function)
            def call(*args, **kwargs):
                try:
                    if request is None:
                        return function(*args, **kwargs)
                    return function(request.model_construct(**kwargs))
                except SnelStartError as error:
                    raise ToolError(str(error)) from None
                except httpx.HTTPError:
                    raise ToolError("SnelStart is unavailable. Try again later.") from None
                except (ValueError, TypeError, KeyError):
                    raise ToolError("Invalid input or an unexpected SnelStart response.") from None
                except OSError:
                    raise ToolError("A local file could not be read or saved.") from None

            if request is not None:
                # FastMCP advertises flat arguments for existing clients.
                flat_signature = contract.replace(
                    parameters=[
                        Parameter(
                            name,
                            Parameter.KEYWORD_ONLY,
                            default=Parameter.empty if field.is_required() else field.default,
                            annotation=field.rebuild_annotation(),
                        )
                        for name, field in request.model_fields.items()
                    ]
                )
                call.__dict__["__signature__"] = flat_signature
            registered = mcp.tool(annotations=annotations)(call)
            registered_requests[function.__name__] = request
            return registered

        return register

    return tool
