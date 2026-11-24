"""Keyboard editor for global and per-administration write permissions."""

import curses
import sys
from contextlib import suppress
from uuid import UUID

from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from .config import SnelStartError, Store
from .models.permissions import PermissionRow, WriteSelection
from .purchase_upload import SUBMIT_PURCHASE, UPLOAD_URL
from .write_access import grantable_operations, save_selection

GROUP_NAMES = {
    "Articles": "Products",
    "Attachments": "Attachments",
    "BalansBoekingen": "Ledger and journals",
    "BoekhoudingSettings": "Settings",
    "BtwAangiftes": "VAT and ICP",
    "CompanySettings": "Settings",
    "Customers": "Customers and suppliers",
    "Grootboek": "Ledger and journals",
    "IcpAangiftes": "VAT and ICP",
    "Invoices": "Sales invoices",
    "Jaarafsluiting": "Year-end",
    "KasBankBoeking": "Bank and cash",
    "MemoriaalBoekingen": "Ledger and journals",
    "Purchases": "Purchases",
    "Settings": "Settings",
    "Suppliers": "Customers and suppliers",
}

PURCHASE_PDF_OPERATIONS = {UPLOAD_URL, SUBMIT_PURCHASE}


def permission_groups(operations: set[str]) -> dict[str, frozenset[str]]:
    grouped: dict[str, set[str]] = {}
    for operation in operations:
        category = operation.split("/", 2)[1]
        name = (
            "Purchase PDF upload"
            if operation in PURCHASE_PDF_OPERATIONS
            else GROUP_NAMES.get(category, category)
        )
        grouped.setdefault(name, set()).add(operation)
    return {name: frozenset(grouped[name]) for name in sorted(grouped)}


def _rows(groups: dict[str, frozenset[str]], expanded: set[str]) -> list[PermissionRow]:
    rows = [
        PermissionRow(label="Global access (all administrations)"),
        PermissionRow(
            label="All eligible operations for this administration",
            operations=frozenset().union(*groups.values()),
        ),
    ]
    for name, operations in groups.items():
        rows.append(PermissionRow(label=name, operations=operations, group=name))
        if name in expanded:
            rows.extend(
                PermissionRow(label=operation, operations=frozenset({operation}), detail=True)
                for operation in sorted(operations)
            )
    return rows


def _toggle(selection: WriteSelection, row: PermissionRow) -> None:
    if row.operations is None:
        selection.allow_writes = not selection.allow_writes
    elif row.operations <= selection.operations:
        selection.operations.difference_update(row.operations)
    else:
        selection.operations.update(row.operations)


def _row_text(row: PermissionRow, selection: WriteSelection, expanded: set[str]) -> str:
    if row.operations is None:
        return f"[{'x' if selection.allow_writes else ' '}] {row.label}"
    selected = len(row.operations & selection.operations)
    total = len(row.operations)
    mark = "x" if selected and selected == total else "-" if selected else " "
    if row.detail:
        return f"    [{mark}] {row.label}"
    prefix = ("- " if row.group in expanded else "+ ") if row.group else ""
    return f"[{mark}] {prefix}{row.label}  ({selected}/{total})"


def _select(
    screen: curses.window,
    administration: UUID,
    selection: WriteSelection,
    groups: dict[str, frozenset[str]],
) -> WriteSelection | None:
    with suppress(curses.error):
        curses.curs_set(0)
    expanded: set[str] = set()
    position = 1
    start = 0
    while True:
        height, width = screen.getmaxyx()
        visible = max(1, height - 6)
        rows = _rows(groups, expanded)
        start = max(0, min(start, position, len(rows) - visible))
        start = max(start, position - visible + 1)

        screen.erase()
        if width > 1 and height >= 7:
            screen.addnstr(0, 0, "SnelStart MCP / Write permissions", width - 1, curses.A_BOLD)
            screen.addnstr(1, 0, f"Administration: {administration}", width - 1)
            state = "on (all administrations)" if selection.allow_writes else "off"
            screen.addnstr(2, 0, f"Global access: {state}", width - 1)
            for index, row in enumerate(rows[start : start + visible], start):
                row_style = curses.A_REVERSE if index == position else curses.A_NORMAL
                screen.addnstr(
                    index - start + 4, 0, _row_text(row, selection, expanded), width - 1, row_style
                )
            screen.addnstr(
                height - 2, 0, "Up/Down move  Space toggle  Tab show/hide details", width - 1
            )
            screen.addnstr(height - 1, 0, "Enter review  Esc cancel", width - 1)
        screen.refresh()

        key = screen.getch()
        row = rows[position]
        if key in (27, ord("q")):
            return None
        if height < 7 or width < 2:
            continue
        if key in (curses.KEY_ENTER, 10, 13):
            return selection
        if key == ord(" "):
            _toggle(selection, row)
        elif key == 9:
            if position == 1:
                expanded = set() if len(expanded) == len(groups) else set(groups)
            elif row.group:
                expanded.symmetric_difference_update({row.group})
        elif key == curses.KEY_UP:
            position = max(0, position - 1)
        elif key == curses.KEY_DOWN:
            position = min(len(rows) - 1, position + 1)
        elif key == curses.KEY_PPAGE:
            position = max(0, position - visible)
        elif key == curses.KEY_NPAGE:
            position = min(len(rows) - 1, position + visible)


def _review(
    console: Console,
    administration: UUID,
    before: WriteSelection,
    after: WriteSelection,
    groups: dict[str, frozenset[str]],
) -> bool:
    console.print(f"\nWrite permissions for {administration}", style="bold")
    if before.allow_writes != after.allow_writes:
        action = "Enable" if after.allow_writes else "Disable"
        console.print(f"{action} global write access for all administrations.", style="yellow")
    if before.operations != after.operations:
        additions = after.operations - before.operations
        removals = before.operations - after.operations
        table = Table(show_header=True, header_style="bold", box=None)
        table.add_column("Group")
        table.add_column("Grant", justify="right")
        table.add_column("Revoke", justify="right")
        for group, operations in groups.items():
            added = operations & additions
            removed = operations & removals
            if added or removed:
                table.add_row(group, str(len(added)), str(len(removed)))
        console.print(table)
        if len(additions) + len(removals) <= 10:
            for operation in sorted(additions):
                console.print(f"  + {operation}", markup=False)
            for operation in sorted(removals):
                console.print(f"  - {operation}", markup=False)
    if after.allow_writes and before.operations != after.operations:
        console.print("Scoped selections take effect when global write access is off.")
    return Confirm.ask("Save these changes?", default=False, console=console)


def configure_write_access(store: Store, administration_id: UUID | None) -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise SnelStartError("Run writes configure in an interactive terminal.")
    original = store.settings()
    administration = administration_id or original.administration_id
    if administration is None:
        raise SnelStartError("Select an administration or pass --administration UUID.")
    available = grantable_operations()
    groups = permission_groups(available)
    saved = original.write_permissions.get(administration, set())
    before = WriteSelection(allow_writes=original.allow_writes, operations=saved & available)
    console = Console()
    try:
        after = curses.wrapper(_select, administration, before.model_copy(deep=True), groups)
        if after is None:
            console.print("Cancelled.")
            return
        if after == before:
            console.print("No changes to save.")
            return
        if not _review(console, administration, before, after, groups):
            console.print("Cancelled.")
            return
    except KeyboardInterrupt:
        console.print("\nCancelled.")
        return
    except curses.error:
        raise SnelStartError(
            "Could not open the menu. Run writes configure in a supported terminal."
        ) from None
    after.operations.update(saved - available)
    save_selection(
        store,
        original,
        administration,
        after,
        follows_active_administration=administration_id is None,
    )
    console.print("Write permissions saved.", style="green")
