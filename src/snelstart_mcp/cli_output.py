"""Human-readable terminal output; JSON output retains the CLI's existing contracts."""

from datetime import datetime
from pathlib import Path
from shlex import join

from rich.console import Console
from rich.table import Table
from rich.text import Text

from .enums import WriteMode
from .models.responses import ConnectionStatus, DoctorResponse, HarImportResponse


def _heading(console: Console, title: str) -> None:
    console.print(Text.assemble(("SnelStart MCP", "bold cyan"), (" / ", "dim"), (title, "bold")))


def _literal(value: object, style: str = "") -> Text:
    return Text("".join(char if char.isprintable() else " " for char in str(value)), style=style)


def _fields() -> Table:
    table = Table.grid(padding=(0, 2, 0, 0))
    table.add_column(style="dim")
    table.add_column(overflow="fold")
    return table


def _expiry(timestamp: float | None) -> str:
    if timestamp is None:
        return "Unavailable"
    try:
        return datetime.fromtimestamp(timestamp).astimezone().strftime("%d %b %Y, %H:%M %Z")
    except (OverflowError, OSError, ValueError):
        return "Unavailable"


def _write_scope(global_access: bool, scoped_access: bool) -> Text:
    if global_access:
        return Text("Global · all eligible operations", style="bold yellow")
    if scoped_access:
        return Text("Scoped · approved operations only", style="yellow")
    return Text("Read-only", style="green")


def show_status(console: Console, title: str, status: ConnectionStatus) -> None:
    _heading(console, title)
    if isinstance(status, DoctorResponse) and status.connected:
        console.print("Connected to SnelStart", style="bold green")
    elif not status.configured:
        console.print("Sign-in required", style="bold yellow")
    console.print()

    fields = _fields()
    name = status.administration_name if isinstance(status, DoctorResponse) else None
    fields.add_row("Selected administration", _literal(name or status.administration_id or "None"))
    fields.add_row(
        "Write access", _write_scope(status.allow_writes, bool(status.approved_write_operations))
    )
    fields.add_row("Saved credentials", "Available" if status.automatic_login else "None")
    fields.add_row("Automatic refresh", "Enabled" if status.automatic_refresh else "Unavailable")
    fields.add_row("Access token expires", _expiry(status.access_token_expires_at))
    profile = status.config_directory
    if profile.is_relative_to(Path.home()):
        profile = Path("~") / profile.relative_to(Path.home())
    fields.add_row("Profile", _literal(profile))
    console.print(fields)

    if isinstance(status, DoctorResponse):
        console.print(f"\nAdministrations ({status.administration_count})", style="bold")
        for entry in status.administrations:
            label = _literal(entry.name or "Unnamed administration")
            if entry.identifier is not None and entry.identifier == status.administration_id:
                label.append("  · Selected", style="bold cyan")
            console.print(Text("  ") + label)
            if entry.identifier is not None:
                console.print(Text(f"    {entry.identifier}", style="dim", overflow="fold"))
        if not status.administrations:
            console.print("  No administrations available.", style="dim")

    if not status.configured:
        console.print("\nSign in with: snelstart-mcp login --method browser", style="dim")
    elif title == "Status":
        console.print("\nTo check the connection and list administrations: snelstart-mcp doctor")


def show_writes(console: Console, mode: WriteMode, result: dict) -> None:
    _heading(console, "Write permissions")
    if "operations" in result:
        console.print("Operations eligible for a grant", style="bold")
        for operation in result["operations"]:
            console.print(_literal(operation))
        return
    if "administration_id" in result:
        console.print(f"Permission {'granted' if mode is WriteMode.GRANT else 'revoked'}.")
        permissions = {result["administration_id"]: result["approved_write_operations"]}
    else:
        permissions = result.get("write_permissions", {})
        console.print(_write_scope(result["allow_writes"], bool(permissions)))
    for administration, operations in permissions.items():
        console.print(_literal(administration, "bold"))
        for operation in operations:
            console.print(Text("  ") + _literal(operation))
        if not operations:
            console.print("  No approved operations.", style="dim")


def show_install(console: Console, results: list[dict], *, apply: bool) -> None:
    _heading(console, "Client registration" if apply else "Client registration preview")
    labels = {
        "preview": ("Ready to register", "cyan"),
        "installed": ("Registered", "green"),
        "already_configured": ("Already configured", "green"),
        "error": ("Error", "red"),
    }
    for item in results:
        label, style = labels.get(item["status"], (item["status"], ""))
        console.print(_literal(item["client"], "bold") + Text(f"  · {label}", style=style))
        if "config" in item:
            console.print(Text("  ") + _literal(item["config"], "dim"))
        if "message" in item:
            console.print(Text("  ") + _literal(item["message"]))
        if len(results) == 1 and not apply:
            if "command" in item:
                console.print(_literal(join(item["command"])))
            if "snippet" in item:
                console.print_json(data=item["snippet"], indent=2)
    if not apply and any(item["status"] == "preview" for item in results):
        if len(results) == 1 and results[0]["client"] == "stdio" and "config" not in results[0]:
            console.print("\nAdd --client-config PATH --apply to save the snippet.", style="dim")
        else:
            console.print("\nAdd --apply to register the selected clients.", style="dim")


def show_har_import(console: Console, result: HarImportResponse) -> None:
    _heading(console, "Session imported")
    fields = _fields()
    fields.add_row("Saved password", "Yes" if result.password_saved else "No")
    fields.add_row("Observed API operations", str(result.observed_operations))
    console.print(fields)
    console.print("\nTo check the connection: snelstart-mcp doctor", style="dim")
