import argparse
import getpass
import json
import sys
from pathlib import Path
from uuid import UUID

import httpx
from rich.console import Console

from .audit import AuditLog
from .backup import list_archives
from .browser_login import check_browser
from .cli_output import (
    show_audit,
    show_har_import,
    show_install,
    show_status,
    show_update,
    show_update_check,
    show_writes,
)
from .client import Client
from .config import SnelStartError, Store
from .enums import LoginMethod, WriteMode
from .har import import_har
from .installer import CLIENTS, install
from .models.audit import AuditSummary
from .models.responses import ConnectionStatus, DoctorResponse, HarImportResponse
from .updater import UpdateChecker, update_tool
from .version import installed_version, version_label
from .write_access import set_write_access


def _doctor(client: Client, *, launch_browser: bool) -> DoctorResponse:
    connection_error = None
    administrations = []
    try:
        administrations = [
            {"identifier": row.get("identifier"), "name": row.get("administrationName")}
            for row in client.administrations()
        ]
    except SnelStartError as error:
        connection_error = str(error)
    except httpx.HTTPError:
        connection_error = "SnelStart is unavailable. Try again later."

    status = client.status()
    selected_id = status["administration_id"]
    selected_name = next(
        (
            row["name"]
            for row in administrations
            if selected_id and row["identifier"] == selected_id
        ),
        None,
    )
    audit_id = UUID(selected_id) if selected_id else None
    audit_log = AuditLog(client.store)
    try:
        summary = audit_log.report(audit_id, 1).summary
    except SnelStartError as error:
        path = audit_log.path(audit_id)
        summary = AuditSummary(database=path, exists=path.is_file(), error=str(error))
    return DoctorResponse.model_validate(
        {
            **status,
            "server_version": installed_version() or "unknown",
            "connected": connection_error is None,
            "connection_error": connection_error,
            "administration_name": selected_name,
            "administration_count": len(administrations),
            "administrations": administrations,
            "audit": summary,
            "browser": check_browser(launch=launch_browser),
            "backups": list_archives(client.store),
            "update": UpdateChecker().check(),
        }
    )


def main():
    output_options = argparse.ArgumentParser(add_help=False)
    output = output_options.add_mutually_exclusive_group()
    output.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Print JSON (default when output is piped or redirected)",
    )
    output.add_argument(
        "--text",
        dest="json_output",
        action="store_false",
        default=argparse.SUPPRESS,
        help="Print a readable summary (default in an interactive terminal)",
    )
    parser = argparse.ArgumentParser(
        description="Connect local MCP clients to your SnelStart Web administration",
        parents=[output_options],
    )
    parser.add_argument("--config-dir", type=Path, help="Use a separate local profile")
    parser.add_argument(
        "--version", action="version", version=f"SnelStart MCP {version_label(installed_version())}"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve", help="Start the MCP server over stdio")
    commands.add_parser("codex-hook", help="Handle a Codex hook event over stdio")
    commands.add_parser("status", parents=[output_options], help="Show the local sign-in profile")
    doctor = commands.add_parser(
        "doctor", parents=[output_options], help="Check the connection, Chrome and local backups"
    )
    doctor.add_argument(
        "--check-browser",
        action="store_true",
        help="Briefly open and close a blank Chrome window to test browser sign-in readiness",
    )
    audit = commands.add_parser(
        "audit", parents=[output_options], help="Show local MCP audit history without signing in"
    )
    audit_scope = audit.add_mutually_exclusive_group()
    audit_scope.add_argument(
        "--administration",
        type=UUID,
        metavar="UUID",
        help="Inspect a specific administration instead of the selected one",
    )
    audit_scope.add_argument(
        "--profile", action="store_true", help="Inspect calls made with no administration selected"
    )
    audit.add_argument(
        "--limit", type=int, default=30, help="Number of recent calls to show (1–100)"
    )
    update = commands.add_parser(
        "update",
        aliases=["self-update"],
        parents=[output_options],
        help="Upgrade the current uv tool installation",
    )
    update.add_argument(
        "--check", action="store_true", help="Check for updates without installing anything"
    )
    commands.add_parser(
        "setup", parents=[output_options], help="Set up sign-in with saved credentials"
    )
    login = commands.add_parser(
        "login", parents=[output_options], help="Sign in with saved credentials or a browser window"
    )
    login.add_argument(
        "--method",
        type=LoginMethod,
        choices=list(LoginMethod),
        default=LoginMethod.CREDENTIALS,
        help="Choose browser OAuth or use saved credentials (default)",
    )
    har = commands.add_parser(
        "import-har", parents=[output_options], help="Import a SnelStart session from a HAR file"
    )
    har.add_argument("path", type=Path)
    har.add_argument(
        "--save-password",
        action="store_true",
        help="Save the sign-in password from the HAR to private local storage",
    )
    installer = commands.add_parser(
        "install", parents=[output_options], help="Register the MCP server with local clients"
    )
    installer.add_argument("clients", nargs="+", choices=[*CLIENTS, "all", "stdio"])
    installer.add_argument("--apply", action="store_true", help="Apply the previewed registration")
    skill_options = installer.add_mutually_exclusive_group()
    skill_options.add_argument(
        "--with-skills",
        action="store_true",
        help="Also install the bundled skills for Codex or Claude Code",
    )
    skill_options.add_argument(
        "--skills-only",
        action="store_true",
        help="Install skills without changing the MCP registration",
    )
    hook_options = installer.add_mutually_exclusive_group()
    hook_options.add_argument(
        "--with-hooks", action="store_true", help="Also install the optional Codex hooks"
    )
    hook_options.add_argument(
        "--hooks-only",
        action="store_true",
        help="Install Codex hooks without changing MCP registration",
    )
    installer.add_argument("--client-config", type=Path, help="Override one client config file")
    writes = commands.add_parser(
        "writes", parents=[output_options], help="Inspect or manage bookkeeping write permissions"
    )
    write_modes = writes.add_subparsers(dest="mode", required=True)
    write_modes.add_parser(
        "on",
        parents=[output_options],
        help="Enable global access to allowlisted bookkeeping writes",
    )
    write_modes.add_parser(
        "off",
        parents=[output_options],
        help="Disable all bookkeeping writes and clear scoped permissions",
    )
    write_list = write_modes.add_parser(
        "list", parents=[output_options], help="Show grants and the global switch"
    )
    write_list.add_argument(
        "--available", action="store_true", help="Show every catalog operation eligible for a grant"
    )
    configure = write_modes.add_parser(
        WriteMode.CONFIGURE, help="Select write permissions interactively"
    )
    configure.add_argument(
        "--administration", type=UUID, metavar="UUID", help="Edit a specific administration"
    )
    for mode in (WriteMode.GRANT, WriteMode.REVOKE):
        scoped = write_modes.add_parser(
            mode, parents=[output_options], help="Manage one operation for one administration"
        )
        scoped.add_argument("administration_id", type=UUID)
        scoped.add_argument("operation", help="Exact catalog operation, including HTTP method")
    args = parser.parse_args()
    if args.command == "codex-hook":
        from .codex_hook import main as run_hook

        run_hook()
        return
    json_output = getattr(args, "json_output", not sys.stdout.isatty())
    if args.command == "install":
        try:
            result = install(
                args.clients,
                apply=args.apply,
                profile=args.config_dir,
                config_path=args.client_config,
                with_skills=args.with_skills,
                skills_only=args.skills_only,
                with_hooks=args.with_hooks,
                hooks_only=args.hooks_only,
            )
        except SnelStartError as error:
            parser.error(str(error))
        if json_output:
            print(json.dumps(result, indent=2))
        else:
            show_install(
                Console(),
                result,
                apply=args.apply,
                skills_only=args.skills_only,
                hooks_only=args.hooks_only,
            )
        if any(item["status"] == "error" for item in result):
            sys.exit(1)
        return
    client: Client | None = None
    try:
        if args.command in ("update", "self-update"):
            if args.check:
                checked = UpdateChecker().check()
                if json_output:
                    print(checked.model_dump_json(indent=2))
                else:
                    show_update_check(Console(), checked)
                return
            updated = update_tool()
            if json_output:
                print(updated.model_dump_json(indent=2))
            else:
                show_update(Console(), updated)
            return
        store = Store(args.config_dir)
        if args.command == "writes":
            if args.mode == WriteMode.CONFIGURE:
                if json_output:
                    raise SnelStartError(
                        "Run writes configure in an interactive terminal without --json."
                    )
                try:
                    from .permission_editor import configure_write_access
                except ImportError as error:
                    if error.name not in {"curses", "_curses"}:
                        raise
                    raise SnelStartError(
                        "The interactive editor requires Python curses support."
                    ) from None
                configure_write_access(store, args.administration)
            else:
                permissions = set_write_access(store, args)
                if json_output:
                    print(json.dumps(permissions, indent=2))
                else:
                    show_writes(Console(), WriteMode(args.mode), permissions)
            return
        if args.command == "audit":
            administration_id = args.administration
            if administration_id is None and not args.profile:
                administration_id = store.settings().administration_id
            report = AuditLog(store).report(administration_id, args.limit)
            if json_output:
                print(report.model_dump_json(indent=2))
            else:
                show_audit(Console(), report)
            return
        client = Client(store)
        if args.command == "serve":
            from .server import create_server

            create_server(client).run(transport="stdio")
            return
        if args.command == "setup":
            print("SnelStart email address: ", end="", file=sys.stderr, flush=True)
            username = input("").strip()
            password = getpass.getpass("SnelStart password (stored privately under ~/.config): ")
            if not username or not password:
                raise SnelStartError("Email address and password are required.")
            with store.locked():
                store.write("credentials.json", {"username": username, "password": password})
            client.auth.login()
            result = client.status()
        elif args.command == "login":
            if not json_output and args.method is LoginMethod.BROWSER:
                Console(stderr=True).print("Opening Chrome for SnelStart sign-in…", style="cyan")
            client.auth.login(args.method)
            result = client.status()
        elif args.command == "import-har":
            result = import_har(args.path, store, client.auth, args.save_password)
        elif args.command == "doctor":
            report = _doctor(client, launch_browser=args.check_browser)
            if json_output:
                print(report.model_dump_json(indent=2))
            else:
                show_status(Console(), "Doctor", report)
            if report.connection_error is not None:
                print(report.connection_error, file=sys.stderr)
                sys.exit(1)
            return
        else:
            result = client.status()
        if json_output:
            print(json.dumps(result, indent=2))
        elif args.command == "import-har":
            show_har_import(Console(), HarImportResponse.model_validate(result))
        else:
            title = "Status" if args.command == "status" else "Signed in"
            show_status(Console(), title, ConnectionStatus.model_validate(result))
    except SnelStartError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPError:
        print("SnelStart is unavailable. Try again later.", file=sys.stderr)
        sys.exit(1)
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
