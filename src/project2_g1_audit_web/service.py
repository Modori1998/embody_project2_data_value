"""Registry-backed G1 Audit Web input. Web never scans outputs/ by mtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .contract import ContractError
from .input import load_run
from .registry import (
    RegistryRecord,
    active_records,
    default_owner_db_path,
    default_registry_path,
    list_records,
    load_registry,
)


class OwnerPathError(RuntimeError):
    pass


class InvalidAuditRunError(RuntimeError):
    def __init__(self, run_id: str, errors: list[str]):
        self.run_id = run_id
        self.errors = errors
        super().__init__("; ".join(errors))


class G1AuditWebInput:
    def __init__(
        self,
        *,
        project_root: str | Path,
        registry_path: str | Path | None = None,
        owner_db_path: str | Path | None = None,
    ):
        self.project_root = Path(project_root).resolve()
        self.registry_path = Path(registry_path or default_registry_path(self.project_root))
        self.owner_db_path = Path(owner_db_path or default_owner_db_path(self.project_root))

    def list_effective_runs(self, *, include_disabled: bool = False) -> list[RegistryRecord]:
        payload = load_registry(self.registry_path)
        if include_disabled:
            return list_records(payload)
        return active_records(payload)

    def load_validated_run(self, run_id: str) -> dict[str, Any]:
        wanted = str(run_id or "").strip()
        payload = load_registry(self.registry_path)
        raw = payload.get("runs", {}).get(wanted)
        if raw is None:
            raise OwnerPathError(f"run_id not in G1 registry: {wanted}")
        record = next(item for item in list_records(payload) if item.run_id == wanted)
        if record.status == "DISABLED_BY_OWNER":
            raise OwnerPathError(f"DISABLED_BY_OWNER: {wanted}")
        try:
            loaded = load_run(record.audit_folder_path)
        except ContractError as exc:
            raise InvalidAuditRunError(wanted, [str(exc)]) from exc
        except OSError as exc:
            raise InvalidAuditRunError(
                wanted, [f"audit folder unreadable: {record.audit_folder_path} ({exc})"]
            ) from exc
        loaded["path_source"] = record.status
        loaded["registry_record"] = record
        return loaded
