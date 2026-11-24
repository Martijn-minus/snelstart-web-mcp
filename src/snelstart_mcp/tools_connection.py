from mcp.types import ToolAnnotations

from .client import Client, catalog
from .config import SnelStartError
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
from .tooling import READ, WRITE, Register


def register_connection_tools(tool: Register, client: Client) -> None:
    @tool(annotations=READ)
    def snelstart_status() -> ConnectionStatus:
        """Show local connection and write status without credentials."""
        return ConnectionStatus.model_validate(client.status())

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
            and (not request.read_only or value["read_only"])
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
        return JsonResponse(
            data=client.request(request.operation, request.parameters, request.filters)
        )

    @tool(annotations=WRITE)
    def snelstart_write(request: WriteOperationRequest) -> JsonResponse:
        """Call a catalog mutation when writes are locally enabled and explicitly requested. Verify the accounting record after the call."""
        entry = catalog().get(request.operation)
        if not entry or entry["read_only"]:
            raise SnelStartError("Unknown write operation. Use snelstart_list_operations.")
        return JsonResponse(
            data=client.request(request.operation, request.parameters, request.payload)
        )
