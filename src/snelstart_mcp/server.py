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
from .models.snapshot import SnapshotInfo, SnapshotPage, SnapshotReadRequest
from .purchase_upload import register_purchase_upload_tools
from .snapshot import Snapshot
from .tooling import tool_registrar, validate_request
from .tools_approval import register_approval_tools
from .tools_archives import register_archive_tools
from .tools_bookkeeping import register_bookkeeping_tools
from .tools_connection import register_connection_tools
from .tools_mutation import register_mutation_tools
from .tools_review import register_review_tools
from .updater import UpdateChecker
from .version import installed_version

LIVE_INSTRUCTIONS = (
    "Recommend making and verifying a backup before starting bookkeeping work. Present live "
    "read-only and offline archive access as options and let the user choose. Do not create "
    "a backup, switch modes, or change permissions without the user's request. "
    "Check the selected SnelStart administration before accessing records. "
    "Recorded balances do not prove payment. Write only on an explicit request "
    "and verify the record before and after any change. If a write returns an approval ID, "
    "use snelstart_open_write_review for the pending IDs from the user's requested changes. "
    "Only the user may confirm "
    "in their local browser or terminal. When the user returns, check which IDs were approved "
    "with snelstart_write_approval_status and retry only those exact requests. Never request or display "
    "credentials. The audit log records tool calls and their outcomes. "
    "After a write, inspect snelstart_mutation_receipts and use snelstart_verify_mutation "
    "for supported read-back checks. Resolve uncertain outcomes before considering a retry. "
    "Use snelstart_list_archives to find backups, snelstart_create_year_archive to create one "
    "on request, and snelstart_verify_archive to check files. "
    "An MCP export covers its declared scope; restoring in SnelStart 12 requires a native BACPAC. "
    "If snelstart_status reports an available update or asks to reconnect, tell the user. "
    "Updates are applied locally."
)
OFFLINE_INSTRUCTIONS = (
    "This server reads one local SnelStart year archive. Call snelstart_snapshot_info first "
    "to confirm the administration, the date covered through, and the available datasets. "
    "Use snelstart_snapshot_read to page saved records. Explain the archive's scope and dates "
    "when reporting results. For missing or newer data, let the user decide whether to refresh "
    "the snapshot in a live read-only session. This server makes no network requests. The user "
    "should decide which archive data to share with their MCP client."
)
LOCAL_READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)


class AuditedMCP(FastMCP):
    def __init__(self, audit: AuditLog, server_version: str, *, name: str, instructions: str):
        super().__init__(
            name,
            instructions=instructions,
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
    running_version = installed_version()
    server_version = running_version or "unknown"
    instructions = (
        "This server is running in live read-only mode. " + LIVE_INSTRUCTIONS
        if client.read_only
        else LIVE_INSTRUCTIONS
    )
    mcp = AuditedMCP(audit, server_version, name="snelstart", instructions=instructions)
    tool = tool_registrar(mcp, mcp.registered_requests, read_only=client.read_only)
    register_connection_tools(
        tool, client, UpdateChecker(running_version=running_version), server_version=server_version
    )
    register_bookkeeping_tools(tool, client)
    register_review_tools(tool, client)
    register_purchase_upload_tools(tool, client)
    register_archive_tools(tool, client)
    register_mutation_tools(tool, client, audit)
    if not client.read_only:
        register_approval_tools(tool, client.store)

    @tool(annotations=LOCAL_READ)
    def snelstart_audit_log(request: LimitRequest) -> DataResponse[list[AuditCallResponse]]:
        """List recent local MCP calls for the selected administration, or profile calls when none is selected."""
        return DataResponse(data=audit.recent(request.limit))

    return mcp


def create_snapshot_server(store: Store, snapshot: Snapshot) -> FastMCP:
    audit = AuditLog(store, scope=lambda: snapshot.info.mcp_administration_id)
    mcp = AuditedMCP(
        audit,
        installed_version() or "unknown",
        name="snelstart-offline",
        instructions=OFFLINE_INSTRUCTIONS,
    )
    tool = tool_registrar(mcp, mcp.registered_requests)

    @tool(annotations=LOCAL_READ)
    def snelstart_snapshot_info() -> SnapshotInfo:
        """Show the mounted archive, its dates and which saved datasets can be queried."""
        return snapshot.info

    @tool(annotations=LOCAL_READ)
    def snelstart_snapshot_read(request: SnapshotReadRequest) -> SnapshotPage:
        """Page a saved dataset. Use section for an object key or group_index for journal entries."""
        return snapshot.read(request)

    return mcp
