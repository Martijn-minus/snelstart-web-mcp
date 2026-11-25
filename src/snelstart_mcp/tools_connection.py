from mcp.types import ToolAnnotations

from .approval import require_approval
from .client import Client, catalog
from .config import SnelStartError
from .models.approval import WriteIntent
from .models.requests import (
    AdministrationRequest,
    OperationListRequest,
    ReadOperationRequest,
    WriteOperationRequest,
)
from .models.responses import (
    AdministrationResponse,
    ConnectionStatus,
    JsonResponse,
    OperationListResponse,
    SelectedAdministration,
)
from .models.update import UpdateCheckResponse
from .tooling import READ, WRITE, Register
from .tools_bookkeeping import ATTACHMENT_OPERATIONS, attachment_metadata
from .updater import UpdateChecker


def register_connection_tools(
    tool: Register, client: Client, updates: UpdateChecker, *, server_version: str
) -> None:
    @tool(annotations=READ)
    def snelstart_status() -> ConnectionStatus:
        """Show the running MCP version, connection, write access and available updates."""
        return ConnectionStatus.model_validate(
            {**client.status(), "server_version": server_version, "update": updates.check()}
        )

    @tool(annotations=READ)
    def snelstart_check_update() -> UpdateCheckResponse:
        """Check whether to reconnect or update the MCP. Report the result to the user."""
        return updates.check(refresh=True)

    @tool(annotations=READ)
    def snelstart_list_administrations() -> list[AdministrationResponse]:
        """List available administrations and refresh the login if needed."""
        return [AdministrationResponse.model_validate(row) for row in client.administrations()]

    @tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def snelstart_select_administration(request: AdministrationRequest) -> SelectedAdministration:
        """Select an administration by UUID and remember it locally."""
        return SelectedAdministration.model_validate(
            client.select_administration(str(request.administration_id))
        )

    @tool(annotations=READ)
    def snelstart_list_operations(request: OperationListRequest) -> OperationListResponse:
        """Find allowlisted API operations and their exact parameters."""
        found = [
            dict(operation=key, **value)
            for key, value in catalog().items()
            if request.query.lower() in key.lower()
            and (value["read_only"] or not (request.read_only or client.read_only))
        ]
        return OperationListResponse.model_validate(
            {"total": len(found), "operations": found[: request.limit]}
        )

    @tool(annotations=READ)
    def snelstart_read(request: ReadOperationRequest) -> JsonResponse:
        """Call an allowlisted read operation. Pass filters for a POST search."""
        entry = catalog().get(request.operation)
        if not entry or not entry["read_only"]:
            raise SnelStartError("Unknown read operation. Use snelstart_list_operations.")
        result = client.request(request.operation, request.parameters, request.filters)
        if request.operation in ATTACHMENT_OPERATIONS:
            result = attachment_metadata(result)
        elif request.operation in {
            "GET /InvoiceSettings/GetDefaultAttachments",
            "GET /QuotationSettings/GetDefaultAttachments",
        }:
            result = attachment_metadata(result if result is not None else [])
        elif request.operation == "GET /Quotations/Get" and isinstance(result, dict):
            attachments = result.get("attachments")
            result["attachments"] = attachment_metadata(
                attachments if attachments is not None else []
            )
        return JsonResponse(data=result)

    @tool(annotations=WRITE)
    def snelstart_write(request: WriteOperationRequest) -> JsonResponse:
        """Call a catalog mutation when writes are locally enabled and explicitly requested. Verify the accounting record after the call."""
        if request.operation == "GET /Attachments/GetAttachmentUploadUriNew":
            raise SnelStartError(
                "Use snelstart_attach_bank_pdf for a bank booking or "
                "snelstart_upload_purchase_pdf for a new purchase."
            )
        entry = catalog().get(request.operation)
        if not entry or entry["read_only"] or entry["path"].startswith("/Administrations/"):
            raise SnelStartError("Unknown write operation. Use snelstart_list_operations.")
        client.check_write_access(request.operation, request.administration_id)
        require_approval(
            client.store,
            WriteIntent(
                tool="snelstart_write",
                operation=request.operation,
                administration_id=request.administration_id,
                details={"parameters": request.parameters, "payload": request.payload},
            ),
            request.approval_id,
        )
        return JsonResponse(
            data=client.request(
                request.operation,
                request.parameters,
                request.payload,
                expected_administration=str(request.administration_id),
            )
        )
