"""Emit advisory context for the bundled Codex hooks."""

import sys

from pydantic import ValidationError

from .enums import CodexHookEvent, UpdateStatus
from .models.hooks import CodexHookContext, CodexHookInput, CodexHookOutput

WRITE_TOOLS = ("snelstart_write", "snelstart_upload_purchase_pdf")
UPDATE_TOOLS = ("snelstart_status", "snelstart_check_update")
TOOL_PREFIX = "mcp__snelstart__"
MAX_INPUT = 1_048_576


def _output(event: CodexHookInput, context: str, *, notice: str | None = None) -> CodexHookOutput:
    return CodexHookOutput(
        hookSpecificOutput=CodexHookContext(
            hookEventName=event.hook_event_name, additionalContext=context
        ),
        systemMessage=notice,
    )


def hook_output(event: CodexHookInput) -> CodexHookOutput | None:
    if not event.tool_name.startswith(TOOL_PREFIX):
        return None
    tool = event.tool_name.removeprefix(TOOL_PREFIX)
    if tool in WRITE_TOOLS:
        if event.hook_event_name is CodexHookEvent.PRE_TOOL_USE:
            return _output(
                event,
                "This SnelStart tool can change bookkeeping. Check the selected administration "
                "and the user's authorization for this specific change.",
            )
        return _output(
            event,
            "Verify the SnelStart result with a read-only follow-up. For purchase uploads, "
            "check the processing status. If the outcome is uncertain, inspect the record and "
            "the audit log before trying again.",
        )
    if event.hook_event_name is not CodexHookEvent.POST_TOOL_USE or tool not in UPDATE_TOOLS:
        return None
    response = event.tool_response
    if not isinstance(response, dict) or response.get("isError"):
        return None
    result = response.get("structuredContent", response)
    if not isinstance(result, dict):
        return None
    update = result.get("update") if tool == "snelstart_status" else result
    if not isinstance(update, dict) or update.get("status") != UpdateStatus.AVAILABLE:
        return None
    notice = "SnelStart MCP update available. Run 'snelstart-mcp update' locally and reconnect."
    return _output(event, "Tell the user about the available SnelStart MCP update.", notice=notice)


def main() -> None:
    payload = sys.stdin.buffer.read(MAX_INPUT + 1)
    if len(payload) > MAX_INPUT:
        return
    try:
        event = CodexHookInput.model_validate_json(payload)
    except ValidationError:
        return
    result = hook_output(event)
    if result is not None:
        print(result.model_dump_json(exclude_none=True))


if __name__ == "__main__":
    main()
