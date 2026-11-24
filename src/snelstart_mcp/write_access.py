"""Local write permission inspection and updates."""

from argparse import Namespace
from uuid import UUID

from .client import catalog
from .config import SnelStartError, Store
from .enums import WriteMode
from .models import Settings
from .models.permissions import WriteSelection
from .write_policy import needs_scoped_grant


def grantable_operations() -> set[str]:
    return {
        name
        for name, entry in catalog().items()
        if not entry["read_only"] and not entry["path"].startswith("/Administrations/")
    }


def _write_permissions(settings: Settings) -> dict[str, list[str]]:
    return {str(key): sorted(operations) for key, operations in settings.write_permissions.items()}


def set_write_access(store: Store, args: Namespace) -> dict:
    if args.mode == WriteMode.LIST:
        if args.available:
            return {"operations": sorted(grantable_operations())}
        settings = store.settings()
        return {
            "allow_writes": settings.allow_writes,
            "write_permissions": _write_permissions(settings),
        }
    with store.locked():
        settings = store.settings()
        if args.mode in {WriteMode.ON, WriteMode.OFF}:
            settings.allow_writes = args.mode == WriteMode.ON
            if not settings.allow_writes:
                settings.write_permissions.clear()
            result = {"allow_writes": settings.allow_writes}
        else:
            if settings.allow_writes and not needs_scoped_grant(args.operation):
                raise SnelStartError("Turn off global writing before managing scoped permissions.")
            if args.operation not in grantable_operations():
                raise SnelStartError("Choose an allowlisted bookkeeping write operation.")
            operations = settings.write_permissions.get(args.administration_id, set())
            if args.mode == WriteMode.GRANT:
                operations.add(args.operation)
            else:
                operations.discard(args.operation)
            if operations:
                settings.write_permissions[args.administration_id] = operations
            else:
                settings.write_permissions.pop(args.administration_id, None)
            result = {
                "administration_id": str(args.administration_id),
                "approved_write_operations": sorted(operations),
            }
        _save_settings(store, settings)
    return result


def _save_settings(store: Store, settings: Settings) -> None:
    config = settings.model_dump(mode="json", exclude_none=True)
    config["write_permissions"] = _write_permissions(settings)
    store.write("config.json", config)


def save_selection(
    store: Store,
    original: Settings,
    administration: UUID,
    selection: WriteSelection,
    *,
    follows_active_administration: bool,
) -> None:
    with store.locked():
        settings = store.settings()
        original_grants = original.write_permissions.get(administration, set())
        if (
            settings.allow_writes != original.allow_writes
            or settings.write_permissions.get(administration, set()) != original_grants
            or (follows_active_administration and settings.administration_id != administration)
        ):
            raise SnelStartError(
                "Write permissions or the active administration changed. Reopen the menu."
            )
        if selection.operations - original_grants - grantable_operations():
            raise SnelStartError("Choose only allowlisted bookkeeping write operations.")
        settings.allow_writes = selection.allow_writes
        if selection.operations:
            settings.write_permissions[administration] = selection.operations
        else:
            settings.write_permissions.pop(administration, None)
        _save_settings(store, settings)
