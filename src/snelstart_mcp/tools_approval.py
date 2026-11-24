"""MCP tool entry points for reviewing and checking local approvals."""

from mcp.types import ToolAnnotations

from .approval import write_approval_states
from .approval_browser import open_write_review
from .config import Store
from .models.approval import (
    WriteApprovalReviewRequest,
    WriteApprovalReviewResponse,
    WriteApprovalState,
)
from .models.responses import DataResponse
from .tooling import Register


def register_approval_tools(tool: Register, store: Store) -> None:
    @tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
    )
    def snelstart_open_write_review(
        request: WriteApprovalReviewRequest,
    ) -> WriteApprovalReviewResponse:
        """Open one local browser window for pending approval IDs. The user must approve selected requests personally."""
        response, _ = open_write_review(store, request.approval_ids)
        return response

    @tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def snelstart_write_approval_status(
        request: WriteApprovalReviewRequest,
    ) -> DataResponse[list[WriteApprovalState]]:
        """Check whether each local approval ID is pending, approved or unavailable. An unavailable approval does not establish whether a write ran."""
        return DataResponse(data=write_approval_states(store, request.approval_ids))
