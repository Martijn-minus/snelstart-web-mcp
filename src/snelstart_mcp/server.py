"""Assembly of the stdio MCP tool groups."""

from time import monotonic

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from .audit import AuditLog
from .client import Client
from .config import SnelStartError, Store
from .enums import AuditOutcome
from .models.audit import AuditCallResponse
from .models.requests import LimitRequest, ToolRequest
from .models.responses import DataResponse
from .purchase_upload import register_purchase_upload_tools
from .tooling import tool_registrar, validate_request
from .tools_archives import register_archive_tools
from .tools_bookkeeping import register_bookkeeping_tools
from .tools_connection import register_connection_tools
from .tools_review import register_review_tools
from .updater import UpdateChecker
from .version import installed_version


class AuditedMCP(FastMCP):
    def __init__(self, audit: AuditLog, server_version: str):
        super().__init__(
            "snelstart",
            instructions=(
                "Check the selected SnelStart administration before accessing records. "
                "Recorded balances do not prove payment. Write only on an explicit request "
                "and verify the record before and after any change. Never request or display "
                "credentials. The audit log records tool calls and their outcomes. "
                "Local year backups are available. When the user mentions backups or year-end "
                "work, point out snelstart_list_archives and snelstart_create_year_archive. "
                "Offer a backup before significant bookkeeping changes. "
                "Create an archive on request and use snelstart_verify_archive to check its files. "
                "An MCP export covers its declared scope; restoring in SnelStart 12 requires a native BACPAC. "
                "If snelstart_status reports an available update, tell the user. Updates are applied locally."
            ),
            log_level="WARNING",
        )
        # FastMCP exposes its implementation version through the underlying MCP server.
        self._mcp_server.version = server_version
        self.audit = audit
        self.registered_requests: dict[str, type[ToolRequest] | None] = {}

    async def call_tool(self, name, arguments):
        tool = (
            name if isinstance(name, str) and name in self.registered_requests else "unknown_tool"
        )
        start = monotonic()
        try:
            call = self.audit.start(tool)
        except SnelStartError as error:
            raise ToolError(str(error)) from None

        scope = self.audit.store.audit_call.set(call)
        outcome = AuditOutcome.INTERRUPTED
        try:
            request = self.registered_requests.get(tool)
            if request is not None:
                validate_request(request, arguments)
            result = await super().call_tool(name, arguments)
            outcome = AuditOutcome.OK
            return result
        except Exception:
            outcome = AuditOutcome.ERROR
            raise
        finally:
            self.audit.store.audit_call.reset(scope)
            try:
                self.audit.finish(call, tool, outcome, round((monotonic() - start) * 1000))
            except SnelStartError:
                # The start event survives. A caller must not assume a completed action was undone.
                if outcome is AuditOutcome.OK:
                    raise ToolError(
                        "Could not complete the local audit log. Check the outcome before retrying."
                    ) from None


def create_server(client: Client | None = None) -> FastMCP:
    client = client or Client(Store())
    audit = AuditLog(client.store)
    server_version = installed_version() or "unknown"
    mcp = AuditedMCP(audit, server_version)
    tool = tool_registrar(mcp, mcp.registered_requests)
    register_connection_tools(tool, client, UpdateChecker(), server_version=server_version)
    register_bookkeeping_tools(tool, client)
    register_review_tools(tool, client)
    register_purchase_upload_tools(tool, client)
    register_archive_tools(tool, client)

    @tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def snelstart_audit_log(request: LimitRequest) -> DataResponse[list[AuditCallResponse]]:
        """List recent local MCP calls for the selected administration, or profile calls when none is selected."""
        return DataResponse(data=audit.recent(request.limit))

    return mcp
