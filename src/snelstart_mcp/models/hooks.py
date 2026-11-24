"""Contracts for SnelStart's local Codex command hooks."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue

from ..enums import CodexHookEvent


class CodexHookInput(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    hook_event_name: CodexHookEvent
    tool_name: str
    tool_response: JsonValue = None


class CodexHookContext(BaseModel):
    hookEventName: CodexHookEvent
    additionalContext: str


class CodexHookOutput(BaseModel):
    hookSpecificOutput: CodexHookContext
    systemMessage: str | None = None


class CodexHookCommand(BaseModel):
    type: Literal["command"] = "command"
    command: str
    timeout: int = 5
    statusMessage: str


class CodexHookGroup(BaseModel):
    matcher: str
    hooks: list[CodexHookCommand]


class CodexHooksInstallResponse(BaseModel):
    path: Path
    status: Literal["preview", "installed", "already_configured"]
    entries: dict[CodexHookEvent, list[CodexHookGroup]]
