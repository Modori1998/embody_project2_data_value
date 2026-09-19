"""Owner-controlled G1 audit run registry. Separate from generator/M07 registries."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .contract import CONTRACT_VERSION, ContractError, validate_g1_audit_folder

RegistryStatus = Literal["AUTO_REGISTERED", "MANUAL_ADDED", "MANUAL_OVERRIDE", "DISABLED_BY_OWNER"]
ALLOWED_STATUS = {"AUTO_REGISTERED", "MANUAL_ADDED", "MANUAL_OVERRIDE", "DISABLED_BY_OWNER"}
REGISTRY_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class RegistryRecord:
    run_id: str
    run_stage: str
    config_version: str
    config_hash: str
    parent_run_id: str | None
    audit_folder_path: str
    created_at: str
    registered_at: str
    signal_contract_version: str
    signal_contract_hash: str
    episode_count: int
    source_dataset_id: str
    status: str
    owner_note: str
    updated_at: str
    override_reason: str
    last_event: str

    @property
    def run_root(self) -> str:
        return self.audit_folder_path

    @property
    def enabled(self) -> bool:
        return self.status != "DISABLED_BY_OWNER"

    @property
    def path_source(self) -> str:
        return self.status


def default_registry_path(project_root: str | Path) -> Path:
    return Path(project_root).resolve() / "outputs" / "g1_audit_web" / "g1_audit_run_registry.json"


def default_owner_db_path(project_root: str | Path) -> Path:
    return Path(project_root).resolve() / "outputs" / "g1_audit_web" / "g1_audit_web_owner.sqlite3"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _empty_payload() -> dict[str, Any]:
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "updated_at": _now(),
        "runs": {},
    }


def load_registry(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return _empty_payload()
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "runs" not in payload:
        raise ContractError(f"invalid G1 registry payload: {target}")
    payload.setdefault("schema_version", REGISTRY_SCHEMA_VERSION)
    payload.setdefault("contract_version", CONTRACT_VERSION)
    payload.setdefault("runs", {})
    return payload


def save_registry(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(payload)
    payload["updated_at"] = _now()
    payload["schema_version"] = REGISTRY_SCHEMA_VERSION
    payload["contract_version"] = CONTRACT_VERSION
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(target)


def _as_parent(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _record_from_mapping(run_id: str, raw: dict[str, Any]) -> RegistryRecord:
    folder = str(raw.get("audit_folder_path") or raw.get("run_root") or "")
    return RegistryRecord(
        run_id=run_id,
        run_stage=str(raw.get("run_stage") or ""),
        config_version=str(raw.get("config_version") or ""),
        config_hash=str(raw.get("config_hash") or ""),
        parent_run_id=_as_parent(raw.get("parent_run_id")),
        audit_folder_path=folder,
        created_at=str(raw.get("created_at") or ""),
        registered_at=str(raw.get("registered_at") or ""),
        signal_contract_version=str(raw.get("signal_contract_version") or ""),
        signal_contract_hash=str(raw.get("signal_contract_hash") or ""),
        episode_count=int(raw.get("episode_count") or 0),
        source_dataset_id=str(raw.get("source_dataset_id") or ""),
        status=str(raw.get("status") or "AUTO_REGISTERED"),
        owner_note=str(raw.get("owner_note") or raw.get("note") or ""),
        updated_at=str(raw.get("updated_at") or ""),
        override_reason=str(raw.get("override_reason") or ""),
        last_event=str(raw.get("last_event") or ""),
    )


def list_records(payload: dict[str, Any]) -> list[RegistryRecord]:
    rows = [_record_from_mapping(run_id, raw) for run_id, raw in payload.get("runs", {}).items()]
    rows.sort(key=lambda item: (item.created_at, item.run_id), reverse=True)
    return rows


def record_to_mapping(record: RegistryRecord) -> dict[str, Any]:
    return {
        "run_id": record.run_id,
        "run_stage": record.run_stage,
        "config_version": record.config_version,
        "config_hash": record.config_hash,
        "parent_run_id": record.parent_run_id,
        "audit_folder_path": record.audit_folder_path,
        "created_at": record.created_at,
        "registered_at": record.registered_at,
        "signal_contract_version": record.signal_contract_version,
        "signal_contract_hash": record.signal_contract_hash,
        "episode_count": record.episode_count,
        "source_dataset_id": record.source_dataset_id,
        "status": record.status,
        "owner_note": record.owner_note,
        "updated_at": record.updated_at,
        "override_reason": record.override_reason,
        "last_event": record.last_event,
        "enabled": record.enabled,
    }


def append_owner_event(
    db_path: str | Path,
    *,
    run_id: str,
    event_type: str,
    from_status: str,
    to_status: str,
    reason: str,
) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS owner_override_event (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                from_status TEXT NOT NULL,
                to_status TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO owner_override_event (
                run_id, event_type, from_status, to_status, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, event_type, from_status, to_status, reason, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def _validated_record(run_root: str | Path, *, status: str, owner_note: str, reason: str) -> RegistryRecord:
    validated = validate_g1_audit_folder(run_root)
    meta = validated["run_meta"]
    now = _now()
    return RegistryRecord(
        run_id=str(meta["run_id"]),
        run_stage=str(meta["run_stage"]),
        config_version=str(meta.get("config_version") or ""),
        config_hash=str(meta["config_hash"]),
        parent_run_id=_as_parent(meta.get("parent_run_id")),
        audit_folder_path=str(Path(run_root).resolve()),
        created_at=str(meta["created_at"]),
        registered_at=now,
        signal_contract_version=str(meta["signal_contract_version"]),
        signal_contract_hash=str(meta["signal_contract_hash"]),
        episode_count=int(meta["episode_count"]),
        source_dataset_id=str(meta["source_dataset_id"]),
        status=status,
        owner_note=owner_note,
        updated_at=now,
        override_reason=reason,
        last_event="REGISTER",
    )


def auto_register(
    registry_path: str | Path,
    run_root: str | Path,
    *,
    owner_db_path: str | Path | None = None,
    owner_note: str = "",
) -> RegistryRecord:
    record = _validated_record(run_root, status="AUTO_REGISTERED", owner_note=owner_note, reason="")
    payload = load_registry(registry_path)
    if record.run_id in payload["runs"]:
        raise ContractError(f"duplicate run_id already registered: {record.run_id}")
    payload["runs"][record.run_id] = record_to_mapping(record)
    save_registry(registry_path, payload)
    if owner_db_path is not None:
        append_owner_event(
            owner_db_path,
            run_id=record.run_id,
            event_type="AUTO_REGISTER",
            from_status="",
            to_status=record.status,
            reason=owner_note or "auto-register",
        )
    return record


def owner_override(
    registry_path: str | Path,
    *,
    run_id: str,
    status: RegistryStatus,
    reason: str,
    owner_db_path: str | Path,
    run_root: str | Path | None = None,
    owner_note: str = "",
) -> RegistryRecord:
    if status not in ALLOWED_STATUS:
        raise ContractError(f"unsupported registry status: {status}")
    if not str(reason).strip():
        raise ContractError("owner override requires a non-empty reason")
    payload = load_registry(registry_path)
    existing = payload["runs"].get(run_id)
    if existing is None:
        if run_root is None:
            raise ContractError(f"{run_id} is not in the registry; pass run_root to add it")
        record = _validated_record(
            run_root,
            status=status,
            owner_note=owner_note,
            reason=reason,
        )
        from_status = ""
        record = RegistryRecord(**{**record.__dict__, "last_event": "MANUAL_ADD_OR_OVERRIDE"})
    else:
        prev = _record_from_mapping(run_id, existing)
        from_status = prev.status
        root = Path(run_root).resolve() if run_root is not None else Path(prev.audit_folder_path)
        validated = validate_g1_audit_folder(root)
        meta = validated["run_meta"]
        if str(meta["run_id"]) != run_id:
            raise ContractError(f"run_root run_id={meta['run_id']} does not match {run_id}")
        now = _now()
        record = RegistryRecord(
            run_id=run_id,
            run_stage=str(meta["run_stage"]),
            config_version=str(meta.get("config_version") or prev.config_version),
            config_hash=str(meta["config_hash"]),
            parent_run_id=_as_parent(meta.get("parent_run_id")),
            audit_folder_path=str(root),
            created_at=str(meta["created_at"]),
            registered_at=prev.registered_at,
            signal_contract_version=str(meta["signal_contract_version"]),
            signal_contract_hash=str(meta["signal_contract_hash"]),
            episode_count=int(meta["episode_count"]),
            source_dataset_id=str(meta["source_dataset_id"]),
            status=status,
            owner_note=owner_note or prev.owner_note,
            updated_at=now,
            override_reason=reason,
            last_event="OWNER_OVERRIDE",
        )
    payload["runs"][record.run_id] = record_to_mapping(record)
    save_registry(registry_path, payload)
    append_owner_event(
        owner_db_path,
        run_id=record.run_id,
        event_type=record.last_event,
        from_status=from_status,
        to_status=record.status,
        reason=reason,
    )
    return record


def restore_run(
    registry_path: str | Path,
    *,
    run_id: str,
    reason: str,
    owner_db_path: str | Path,
) -> RegistryRecord:
    return owner_override(
        registry_path,
        run_id=run_id,
        status="AUTO_REGISTERED",
        reason=reason,
        owner_db_path=owner_db_path,
        owner_note="RESTORE",
    )


def active_records(payload: dict[str, Any]) -> list[RegistryRecord]:
    return [row for row in list_records(payload) if row.status != "DISABLED_BY_OWNER"]
