"""Human-readable terminal output; JSON output retains the CLI's existing contracts."""

from datetime import datetime
from pathlib import Path
from shlex import join

from rich.console import Console
from rich.filesize import decimal
from rich.table import Table
from rich.text import Text

from .enums import BrowserStatus, UpdateStatus, WriteMode
from .models.audit import AuditReport, AuditSummary
from .models.responses import (
    ArchiveInventory,
    ConnectionStatus,
    DoctorResponse,
    HarImportResponse,
    ToolUpdateResponse,
)
from .models.update import UpdateCheckResponse
from .version import version_label


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


def _audit_time(timestamp: str) -> str:
    try:
        return datetime.fromisoformat(timestamp).astimezone().strftime("%d %b %Y, %H:%M:%S %Z")
    except (OverflowError, OSError, ValueError):
        return "Unavailable"


def _audit_summary(console: Console, summary: AuditSummary) -> None:
    fields = _fields()
    fields.add_row("Database", _literal(summary.database))
    if summary.error:
        fields.add_row("Status", _literal(summary.error, "bold red"))
    elif summary.total_calls:
        fields.add_row(
            "MCP calls",
            f"{summary.total_calls} total · {summary.succeeded} OK · {summary.failed} failed · "
            f"{summary.pending} pending · {summary.interrupted} interrupted",
        )
        if summary.latest_call:
            latest = summary.latest_call
            fields.add_row("Latest call", _literal(f"{latest.tool} · {latest.outcome}"))
            fields.add_row("Recorded at", _audit_time(latest.started_at))
    else:
        fields.add_row("MCP calls", "No calls recorded for this scope.")
    console.print(fields)


def _backup_summary(console: Console, backups: ArchiveInventory) -> None:
    console.print(f"\nLocal backups ({len(backups.archives)})", style="bold")
    console.print(_literal(backups.directory, "dim"))
    if backups.error:
        console.print(_literal(backups.error, "yellow"))
        return
    if not backups.archives:
        console.print("No year backups in this profile.", style="dim")
        return

    table = Table(box=None, padding=(0, 1))
    table.add_column("Year", no_wrap=True)
    table.add_column("Through", no_wrap=True)
    table.add_column("Created", no_wrap=True)
    table.add_column("ZIP size", justify="right", no_wrap=True)
    table.add_column("Contents")
    for archive in backups.archives:
        contents = (
            "Unreadable manifest"
            if not archive.manifest_readable
            else "Native BACPAC included"
            if archive.bacpac_included
            else "Year archive"
        )
        table.add_row(
            str(archive.year),
            str(archive.through_date or "—"),
            _audit_time(archive.created_at.isoformat()) if archive.created_at else "Unavailable",
            decimal(archive.size_bytes),
            contents,
        )
    console.print(table)
    console.print(
        'To check for missing or changed files, ask Codex "Verify my latest SnelStart backup."',
        style="dim",
    )


def show_audit(console: Console, report: AuditReport) -> None:
    _heading(console, "Audit history")
    console.print(_literal(report.administration_id or "Profile · no administration selected"))
    console.print()
    _audit_summary(console, report.summary)
    if report.calls:
        history = Table(box=None, padding=(0, 1, 0, 0))
        history.add_column("Time", style="dim")
        history.add_column("Outcome")
        history.add_column("Tool", overflow="fold")
        history.add_column("Duration", justify="right")
        for call in report.calls:
            duration = f"{call.elapsed_ms} ms" if call.elapsed_ms is not None else "—"
            history.add_row(
                _audit_time(call.started_at), call.outcome, _literal(call.tool), duration
            )
        console.print()
        console.print(history)


def show_update_check(console: Console, result: UpdateCheckResponse) -> None:
    _heading(console, "Update check")
    fields = _fields()
    fields.add_row("Installed version", _literal(version_label(result.installed_version)))
    if result.latest_version:
        fields.add_row("Latest release", _literal(version_label(result.latest_version)))
    if result.installed_commit:
        fields.add_row("Git revision", _literal(result.installed_commit[:12]))
    fields.add_row(
        "Status",
        _literal(result.message, "yellow" if result.status is UpdateStatus.AVAILABLE else ""),
    )
    console.print(fields)


def show_update(console: Console, update: ToolUpdateResponse) -> None:
    _heading(console, "Update")
    console.print(_literal(f"Update check completed for {update.package}.", "green"))
    console.print("Reconnect MCP clients to load the installed version.", style="dim")


def _write_scope(global_access: bool, scoped_access: bool) -> Text:
    if global_access:
        return Text("Global · standard operations", style="bold yellow")
    if scoped_access:
        return Text("Scoped · approved operations only", style="yellow")
    return Text("Read-only", style="green")


def show_status(console: Console, title: str, status: ConnectionStatus) -> None:
    _heading(console, title)
    if isinstance(status, DoctorResponse):
        if status.connected:
            console.print("Connected to SnelStart", style="bold green")
        else:
            console.print("Could not connect to SnelStart", style="bold yellow")
    elif not status.configured:
        console.print("Sign-in required", style="bold yellow")
    console.print()

    fields = _fields()
    name = status.administration_name if isinstance(status, DoctorResponse) else None
    if status.server_version is not None:
        fields.add_row("SnelStart MCP version", _literal(version_label(status.server_version)))
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
    if isinstance(status, DoctorResponse):
        browser_style = (
            "green"
            if status.browser.status is BrowserStatus.READY
            else ""
            if status.browser.status is BrowserStatus.DETECTED
            else "yellow"
        )
        fields.add_row("Chrome sign-in", _literal(status.browser.message, browser_style))
    if status.update is not None:
        update_style = "bold yellow" if status.update.status is UpdateStatus.AVAILABLE else ""
        fields.add_row("Updates", _literal(status.update.message, update_style))
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

        console.print("\nAudit log", style="bold")
        _audit_summary(console, status.audit)
        console.print("Recent calls: snelstart-mcp audit", style="dim")
        _backup_summary(console, status.backups)

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


def show_install(
    console: Console,
    results: list[dict],
    *,
    apply: bool,
    skills_only: bool = False,
    hooks_only: bool = False,
) -> None:
    title = "Add-on installation" if skills_only or hooks_only else "Client registration"
    _heading(console, title if apply else title + " preview")
    labels = {
        "preview": ("Ready to register", "cyan"),
        "installed": ("Registered", "green"),
        "updated": ("Updated", "green"),
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
        for skill in item.get("skills", []):
            label, style = labels[skill["status"]]
            console.print(
                Text("  Skill ")
                + _literal(skill["name"], "bold")
                + Text(f"  · {label}", style=style)
            )
            console.print(Text("    ") + _literal(skill["path"], "dim"))
        if (hooks := item.get("hooks")) is not None:
            label, style = labels[hooks["status"]]
            console.print(Text(f"  Codex hooks  · {label}", style=style))
            console.print(Text("    ") + _literal(hooks["path"], "dim"))
            if apply:
                console.print("    Open /hooks in Codex to review and trust the definitions.")
            else:
                console.print_json(data={"hooks": hooks["entries"]}, indent=2)
        if len(results) == 1 and not apply:
            if "command" in item:
                console.print(_literal(join(item["command"])))
            if "snippet" in item:
                console.print_json(data=item["snippet"], indent=2)
    if not apply and any(item["status"] == "preview" for item in results):
        if skills_only or hooks_only:
            console.print("\nAdd --apply to install the selected add-ons.", style="dim")
        elif len(results) == 1 and results[0]["client"] == "stdio" and "config" not in results[0]:
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
