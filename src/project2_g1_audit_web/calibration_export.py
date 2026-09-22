"""Immutable Human Calibration Export for a completed G1 Audit Run.

This module is deliberately review-layer only.  It never changes the Detector,
the source Audit Run, or the Web-owned SQLite database.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from project2_g1.final_semantics import SEMANTICS_MATERIALIZED

from .contract import is_design_diagnostic
from .hashes import sha256_file, tree_fingerprint
from .input import load_csv_rows
from .reviews import (
    ADDED_TABLE,
    BOUNDARY_TABLE,
    MISALIGNED_REASONS,
    MISSED_REASONS,
    REDUNDANT_REASONS,
    SIGNAL_NAMES,
    SIGNAL_TABLE,
)

EXPORT_CONTRACT = "P2_G1_HUMAN_CALIBRATION_EXPORT_V1"
EXPORT_INTENDED_ROLE = "CALIBRATION_SEED"
EXPORT_INTENDED_ROLE_CALIBRATION = "CALIBRATION"
ALLOWED_INTENDED_ROLES = (EXPORT_INTENDED_ROLE, EXPORT_INTENDED_ROLE_CALIBRATION)
CALIBRATION_PROTOCOL_DOCUMENT = "Project2_G1_P3_Calibration_Protocol_FROZEN_v1_1_PATCH_20260918.md"
CALIBRATION_PROTOCOL_STATUS = "FROZEN_v1.1"

SIGNAL_FIELDS = (
    "export_id", "episode_id", "signal_contract_version", "signal_contract_hash",
    "signal_name", "decision", "comment", "effective_review_id", "reviewer",
    "reviewed_at", "review_origin", "review_source_run_id",
)
PREDICTED_FIELDS = (
    "export_id", "source_run_id", "episode_id", "boundary_id", "predicted_frame",
    "candidate_type", "representative_candidate_id", "member_candidate_ids",
    "member_candidate_types", "member_candidate_frames", "member_candidate_count",
    "human_decision", "reason_code", "corrected_frame", "comment",
    "effective_review_id", "reviewer", "reviewed_at",
)
ADDED_FIELDS = (
    "export_id", "source_run_id", "episode_id", "added_group_id",
    "human_added_frame", "reason_code", "comment", "review_id", "reviewer", "reviewed_at",
)
DATA_FILES = ("signal_review.csv", "predicted_boundary_review.csv", "human_added_boundary.csv")


class ExportBlocked(ValueError):
    """The current review state is not eligible for the Seed export."""

    def __init__(self, errors: Iterable[str]):
        self.errors = [str(item) for item in errors if str(item).strip()]
        super().__init__("EXPORT_BLOCKED: " + " | ".join(self.errors))


class ExportValidationError(ValueError):
    """A generated or existing export does not satisfy the frozen contract."""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _read_only_connection(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise ExportBlocked([f"owner SQLite does not exist: {path}"])
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _latest(rows: Iterable[sqlite3.Row], key_fields: tuple[str, ...]) -> dict[tuple[str, ...], sqlite3.Row]:
    out: dict[tuple[str, ...], sqlite3.Row] = {}
    for row in rows:
        key = tuple(str(row[field]) for field in key_fields)
        if key not in out:
            out[key] = row
    return out


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ExportValidationError(f"{path.name}: missing header")
        return list(reader.fieldnames), list(reader)


def _source_identity(loaded: Mapping[str, Any]) -> dict[str, str] | None:
    roles = {str(item.set_role) for item in loaded["episodes"]}
    if len(roles) != 1:
        return None
    meta = loaded["run_meta"]
    return {
        "run_stage": str(loaded["run_stage"]),
        "set_role": next(iter(roles)),
        "calibration_role": str(meta.get("calibration_role") or ""),
        "calibration_config_role": str(meta.get("calibration_config_role") or ""),
    }


def resolve_export_role(loaded: Mapping[str, Any]) -> str | None:
    """Map a source run to the frozen intended_role, or None if ineligible."""

    identity = _source_identity(loaded)
    if identity is None:
        return None
    # Design Diagnostic runs are human-reviewable but permanently barred from
    # Human Calibration Export (additive hard block; other stages unchanged).
    if is_design_diagnostic(identity["run_stage"]) or is_design_diagnostic(
        identity["set_role"]
    ):
        return None
    if identity["run_stage"] == "EXPLORATORY_AUDIT" and identity["set_role"] == "EXPLORATORY":
        return EXPORT_INTENDED_ROLE
    if (
        identity["run_stage"] == "CALIBRATION"
        and identity["set_role"] == "CALIBRATION"
        and identity["calibration_role"] == "BASELINE_HUMAN_AUDIT"
        and identity["calibration_config_role"] == "BASELINE_UNMODIFIED"
    ):
        return EXPORT_INTENDED_ROLE_CALIBRATION
    return None


def export_eligibility_errors(loaded: Mapping[str, Any], intended_role: str | None) -> list[str]:
    role = str(intended_role or "").strip()
    if role not in ALLOWED_INTENDED_ROLES:
        return [f"unsupported intended_role: {intended_role}"]
    resolved = resolve_export_role(loaded)
    if resolved is None:
        identity = _source_identity(loaded)
        stage = identity["run_stage"] if identity else str(loaded.get("run_stage") or "")
        set_role = identity["set_role"] if identity else sorted({str(item.set_role) for item in loaded["episodes"]})
        cal_role = identity["calibration_role"] if identity else str((loaded.get("run_meta") or {}).get("calibration_role") or "")
        cal_config = identity["calibration_config_role"] if identity else str((loaded.get("run_meta") or {}).get("calibration_config_role") or "")
        return [
            "source identity is not eligible for Human Calibration Export: "
            f"run_stage={stage} set_role={set_role} "
            f"calibration_role={cal_role} calibration_config_role={cal_config}"
        ]
    if role != resolved:
        return [f"intended_role {role} does not match frozen mapping for source (expected {resolved})"]
    return []


def _snapshot_identity(signal_rows: list[dict[str, Any]], boundary_rows: list[dict[str, Any]], added_rows: list[dict[str, Any]]) -> str:
    payload = {
        "signal_review_ids": [row["effective_review_id"] for row in signal_rows],
        "boundary_review_ids": [row["effective_review_id"] for row in boundary_rows],
        "added_review_ids": [row["review_id"] for row in added_rows],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class HumanCalibrationExportService:
    def __init__(self, *, project_root: str | Path, owner_db_path: str | Path, export_root: str | Path | None = None):
        self.project_root = Path(project_root).resolve()
        self.owner_db_path = Path(owner_db_path).resolve()
        self.export_root = Path(export_root or (self.project_root / "outputs" / "g1_audit_web" / "human_calibration_export")).resolve()

    def _collect_snapshot(self, loaded: Mapping[str, Any]) -> dict[str, Any]:
        run_id = str(loaded["run_id"])
        meta = loaded["run_meta"]
        episodes = list(loaded["episodes"])
        episode_ids = {item.episode_id for item in episodes}
        episode_lengths = {item.episode_id: int(item.length) for item in episodes}
        if str(loaded.get("final_member_semantics") or "") != SEMANTICS_MATERIALIZED:
            raise ExportBlocked(["source Final Boundary semantics must be MATERIALIZED_V1"])

        finals: dict[tuple[str, str], dict[str, str]] = {}
        for episode in episodes:
            for row in load_csv_rows(episode.boundaries_path):
                key = (episode.episode_id, str(row.get("boundary_id") or ""))
                if not key[1] or key in finals:
                    raise ExportBlocked([f"invalid or duplicate source boundary: {key}"])
                finals[key] = row

        connection = _read_only_connection(self.owner_db_path)
        try:
            connection.execute("BEGIN")
            review_snapshot_time = _now()
            signal_db = connection.execute(
                f"SELECT * FROM {SIGNAL_TABLE} WHERE signal_contract_hash = ? AND signal_contract_version = ? ORDER BY review_id DESC",
                (str(meta["signal_contract_hash"]), str(meta["signal_contract_version"])),
            ).fetchall()
            boundary_db = connection.execute(
                f"SELECT * FROM {BOUNDARY_TABLE} WHERE run_id = ? ORDER BY review_id DESC", (run_id,)
            ).fetchall()
            added_db = connection.execute(
                f"SELECT * FROM {ADDED_TABLE} WHERE run_id = ? ORDER BY review_id DESC", (run_id,)
            ).fetchall()
            current_signals = _latest(signal_db, ("episode_id", "signal_name"))
            current_boundaries = _latest(boundary_db, ("episode_id", "boundary_id"))
            current_added = _latest(added_db, ("episode_id", "added_group_id"))

            signal_rows: list[dict[str, Any]] = []
            errors: list[str] = []
            for episode_id in sorted(episode_ids):
                for signal_name in SIGNAL_NAMES:
                    row = current_signals.get((episode_id, signal_name))
                    if row is None:
                        errors.append(f"P1 NOT_REVIEWED: {episode_id}/{signal_name}")
                        continue
                    decision = str(row["decision"])
                    if decision != "PASS":
                        errors.append(f"P1 seed policy requires PASS: {episode_id}/{signal_name}={decision}")
                    review_source = str(row["source_run_id"])
                    signal_rows.append({
                        "export_id": "",
                        "episode_id": episode_id,
                        "signal_contract_version": str(row["signal_contract_version"]),
                        "signal_contract_hash": str(row["signal_contract_hash"]),
                        "signal_name": signal_name,
                        "decision": decision,
                        "comment": str(row["comment"] or ""),
                        "effective_review_id": int(row["review_id"]),
                        "reviewer": str(row["reviewer"]),
                        "reviewed_at": str(row["reviewed_at"]),
                        "review_origin": "DIRECT_REVIEW" if review_source == run_id else "REUSED_REVIEW",
                        "review_source_run_id": review_source,
                    })

            predicted_rows: list[dict[str, Any]] = []
            for key in sorted(finals):
                episode_id, boundary_id = key
                final = finals[key]
                row = current_boundaries.get(key)
                if row is None:
                    errors.append(f"P2 NOT_REVIEWED: {episode_id}/{boundary_id}")
                    continue
                decision = str(row["decision"])
                corrected = row["corrected_frame"]
                if decision not in {"VALID", "REDUNDANT", "MISALIGNED"}:
                    errors.append(f"P2 NOT_REVIEWED: {episode_id}/{boundary_id}={decision}")
                if decision == "MISALIGNED" and corrected is None:
                    errors.append(f"MISALIGNED requires corrected_frame: {episode_id}/{boundary_id}")
                if decision == "MISALIGNED" and str(row["reason_code"] or "") not in MISALIGNED_REASONS:
                    errors.append(f"MISALIGNED requires compatible reason_code: {episode_id}/{boundary_id}")
                if decision == "REDUNDANT" and str(row["reason_code"] or "") not in REDUNDANT_REASONS:
                    errors.append(f"REDUNDANT requires compatible reason_code: {episode_id}/{boundary_id}")
                if str(row["reason_code"] or "") == "OTHER" and not str(row["comment"] or "").strip():
                    errors.append(f"OTHER requires comment: {episode_id}/{boundary_id}")
                if int(row["predicted_frame"]) != int(final["frame"]):
                    errors.append(f"review predicted_frame disagrees with source Final: {episode_id}/{boundary_id}")
                predicted_rows.append({
                    "export_id": "", "source_run_id": run_id, "episode_id": episode_id,
                    "boundary_id": boundary_id, "predicted_frame": int(final["frame"]),
                    "candidate_type": str(final["candidate_type"]),
                    "representative_candidate_id": str(final["representative_candidate_id"]),
                    "member_candidate_ids": str(final["member_candidate_ids"]),
                    "member_candidate_types": str(final["member_candidate_types"]),
                    "member_candidate_frames": str(final["member_candidate_frames"]),
                    "member_candidate_count": int(final["member_candidate_count"]),
                    "human_decision": decision, "reason_code": str(row["reason_code"] or ""),
                    "corrected_frame": "" if corrected is None else int(corrected),
                    "comment": str(row["comment"] or ""), "effective_review_id": int(row["review_id"]),
                    "reviewer": str(row["reviewer"]), "reviewed_at": str(row["reviewed_at"]),
                })

            unexpected = sorted(set(current_boundaries) - set(finals))
            if unexpected:
                errors.append(f"boundary review not in source Final: {unexpected[0]}")

            added_rows: list[dict[str, Any]] = []
            for (episode_id, group_id), row in sorted(current_added.items()):
                if episode_id not in episode_ids:
                    errors.append(f"human-added boundary episode not in source run: {episode_id}")
                frame = int(row["human_added_frame"])
                if episode_id in episode_lengths and not (0 <= frame < episode_lengths[episode_id]):
                    errors.append(f"human-added boundary frame out of range: {episode_id}/{group_id}")
                reason = str(row["reason_code"] or "")
                if reason not in MISSED_REASONS:
                    errors.append(f"human-added boundary requires compatible reason_code: {episode_id}/{group_id}")
                if reason == "OTHER" and not str(row["comment"] or "").strip():
                    errors.append(f"human-added OTHER requires comment: {episode_id}/{group_id}")
                added_rows.append({
                    "export_id": "", "source_run_id": run_id, "episode_id": episode_id,
                    "added_group_id": group_id, "human_added_frame": frame,
                    "reason_code": str(row["reason_code"]), "comment": str(row["comment"] or ""),
                    "review_id": int(row["review_id"]), "reviewer": str(row["reviewer"]),
                    "reviewed_at": str(row["reviewed_at"]),
                })
            if errors:
                raise ExportBlocked(errors)
            return {
                "review_snapshot_time": review_snapshot_time,
                "signal_rows": signal_rows,
                "predicted_rows": predicted_rows,
                "added_rows": added_rows,
                "signal_review_ids": {int(row["review_id"]) for row in signal_db},
                "boundary_review_ids": {int(row["review_id"]) for row in boundary_db},
                "added_review_ids": {int(row["review_id"]) for row in added_db},
                "finals": finals,
            }
        finally:
            connection.rollback()
            connection.close()

    def assess(self, loaded: Mapping[str, Any], *, intended_role: str | None = None) -> dict[str, Any]:
        review_errors: list[str] = []
        signal_rows = predicted_rows = added_rows = 0
        try:
            snapshot = self._collect_snapshot(loaded)
            signal_rows = len(snapshot["signal_rows"])
            predicted_rows = len(snapshot["predicted_rows"])
            added_rows = len(snapshot["added_rows"])
            review_ready = True
        except ExportBlocked as exc:
            review_ready = False
            review_errors = list(exc.errors)
        resolved = resolve_export_role(loaded)
        if intended_role is None:
            role = resolved or ""
            eligibility = (
                export_eligibility_errors(loaded, resolved)
                if resolved is not None
                else ["source identity is not eligible for Human Calibration Export"]
            )
        else:
            role = intended_role
            eligibility = export_eligibility_errors(loaded, intended_role)
        export_eligible = not eligibility
        effective = review_ready and export_eligible
        return {
            "ready": effective,
            "review_ready": review_ready,
            "export_eligible": export_eligible,
            "effective_export_ready": effective,
            "intended_role": role,
            "errors": review_errors + eligibility,
            "signal_rows": signal_rows,
            "predicted_rows": predicted_rows,
            "added_rows": added_rows,
        }

    def create_export(self, loaded: Mapping[str, Any], *, intended_role: str = EXPORT_INTENDED_ROLE) -> dict[str, Any]:
        eligibility = export_eligibility_errors(loaded, intended_role)
        if eligibility:
            raise ExportBlocked(eligibility)
        identity = _source_identity(loaded)
        if identity is None:
            raise ExportBlocked(["source identity is not eligible for Human Calibration Export"])
        run_id = str(loaded["run_id"])

        sqlite_before = sha256_file(self.owner_db_path)
        run_before = tree_fingerprint(loaded["run_root"])["tree_fingerprint"]
        snapshot = self._collect_snapshot(loaded)
        created_at = _now()
        stamp = datetime.fromisoformat(created_at).strftime("%Y%m%d_%H%M%S")
        identity_sha = _snapshot_identity(snapshot["signal_rows"], snapshot["predicted_rows"], snapshot["added_rows"])
        salt = uuid.uuid4().hex
        short_hash = hashlib.sha256(f"{run_id}|{identity_sha}|{created_at}|{salt}".encode("utf-8")).hexdigest()[:8]
        prefix = "g1_cal_seed_export" if intended_role == EXPORT_INTENDED_ROLE else "g1_cal_export"
        export_id = f"{prefix}_{stamp}_{short_hash}"
        if export_id == run_id:
            raise ExportValidationError("export_id must differ from source_run_id")
        for row in snapshot["signal_rows"] + snapshot["predicted_rows"] + snapshot["added_rows"]:
            row["export_id"] = export_id

        self.export_root.mkdir(parents=True, exist_ok=True)
        final_path = self.export_root / export_id
        temp_path = self.export_root / f".tmp-{export_id}-{uuid.uuid4().hex}"
        if final_path.exists():
            raise ExportValidationError(f"immutable export already exists: {final_path}")
        temp_path.mkdir()
        try:
            _write_csv(temp_path / DATA_FILES[0], SIGNAL_FIELDS, snapshot["signal_rows"])
            _write_csv(temp_path / DATA_FILES[1], PREDICTED_FIELDS, snapshot["predicted_rows"])
            _write_csv(temp_path / DATA_FILES[2], ADDED_FIELDS, snapshot["added_rows"])
            reviewers = sorted({str(row["reviewer"]) for row in snapshot["signal_rows"] + snapshot["predicted_rows"] + snapshot["added_rows"]})
            decisions = Counter(str(row["human_decision"]) for row in snapshot["predicted_rows"])
            source_meta = loaded["run_meta"]
            meta = {
                "export_contract": EXPORT_CONTRACT,
                "export_id": export_id,
                "created_at": created_at,
                "review_snapshot_time": snapshot["review_snapshot_time"],
                "source_run_id": run_id,
                "source_run_stage": identity["run_stage"],
                "source_set_role": identity["set_role"],
                "calibration_role": identity["calibration_role"],
                "calibration_config_role": identity["calibration_config_role"],
                "config_version": str(source_meta["config_version"]),
                "config_hash": str(source_meta["config_hash"]),
                "signal_contract_version": str(source_meta["signal_contract_version"]),
                "signal_contract_hash": str(source_meta["signal_contract_hash"]),
                "final_boundary_semantics": str(source_meta.get("final_boundary_semantics") or "MATERIALIZED_V1"),
                "reviewer": reviewers[0] if len(reviewers) == 1 else reviewers,
                "episode_count": len(loaded["episodes"]),
                "signal_review_row_count": len(snapshot["signal_rows"]),
                "predicted_boundary_review_row_count": len(snapshot["predicted_rows"]),
                "human_added_boundary_row_count": len(snapshot["added_rows"]),
                "intended_role": intended_role,
                "must_not_feed_evaluation": True,
                "calibration_protocol_document": CALIBRATION_PROTOCOL_DOCUMENT,
                "calibration_protocol_status": CALIBRATION_PROTOCOL_STATUS,
                "validation_status": "PASS",
                "review_snapshot_identity_sha256": identity_sha,
                "decision_counts": dict(sorted(decisions.items())),
                "files_sha256": {name: sha256_file(temp_path / name) for name in DATA_FILES},
            }
            (temp_path / "export_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            self.validate_export(temp_path, loaded=loaded, snapshot=snapshot)
            os.rename(temp_path, final_path)
        except Exception:
            if temp_path.exists():
                shutil.rmtree(temp_path)
            raise

        sqlite_after = sha256_file(self.owner_db_path)
        run_after = tree_fingerprint(loaded["run_root"])["tree_fingerprint"]
        if sqlite_before != sqlite_after or run_before != run_after:
            raise ExportValidationError("source immutability check failed after export")
        return {
            "export_id": export_id, "export_path": str(final_path), "meta": meta,
            "owner_sqlite_unchanged": sqlite_before == sqlite_after,
            "source_audit_run_unchanged": run_before == run_after,
        }

    def validate_export(self, path: str | Path, *, loaded: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
        root = Path(path)
        meta = json.loads((root / "export_meta.json").read_text(encoding="utf-8"))
        signal_fields, signals = _read_csv(root / DATA_FILES[0])
        predicted_fields, predicted = _read_csv(root / DATA_FILES[1])
        added_fields, added = _read_csv(root / DATA_FILES[2])
        errors: list[str] = []
        if meta.get("export_contract") != EXPORT_CONTRACT:
            errors.append("contract mismatch")
        export_id = str(meta.get("export_id") or "")
        if not export_id or export_id == str(loaded["run_id"]):
            errors.append("invalid export_id")
        if meta.get("source_run_id") != loaded["run_id"]:
            errors.append("source_run_id mismatch")
        errors.extend(export_eligibility_errors(loaded, str(meta.get("intended_role") or "")))
        source = _source_identity(loaded)
        if (
            source is None
            or meta.get("source_run_stage") != source["run_stage"]
            or meta.get("source_set_role") != source["set_role"]
        ):
            errors.append("source identity mismatch")
        if str(meta.get("intended_role") or "") == EXPORT_INTENDED_ROLE_CALIBRATION and (
            meta.get("calibration_role") != "BASELINE_HUMAN_AUDIT"
            or meta.get("calibration_config_role") != "BASELINE_UNMODIFIED"
        ):
            errors.append("calibration provenance mismatch")
        if meta.get("must_not_feed_evaluation") is not True:
            errors.append("role/evaluation guard mismatch")
        if signal_fields != list(SIGNAL_FIELDS) or predicted_fields != list(PREDICTED_FIELDS) or added_fields != list(ADDED_FIELDS):
            errors.append("CSV schema mismatch")
        expected_episodes = {item.episode_id for item in loaded["episodes"]}
        if int(meta.get("episode_count", -1)) != len(expected_episodes):
            errors.append("episode_count mismatch")
        if len(signals) != len(expected_episodes) * len(SIGNAL_NAMES) or any(row["decision"] != "PASS" for row in signals):
            errors.append("P1 completeness/pass gate failed")
        if len(predicted) != len(snapshot["finals"]):
            errors.append("P2 completeness gate failed")
        if any(row["human_decision"] == "NOT_REVIEWED" for row in predicted):
            errors.append("P2 contains NOT_REVIEWED")
        if any(row["human_decision"] == "MISALIGNED" and row["corrected_frame"] == "" for row in predicted):
            errors.append("MISALIGNED missing corrected_frame")
        if any(row["episode_id"] not in expected_episodes for row in signals + predicted + added):
            errors.append("row episode not in source run")
        if any(row["export_id"] != export_id for row in signals + predicted + added):
            errors.append("row export_id mismatch")
        for row in predicted:
            key = (row["episode_id"], row["boundary_id"])
            source = snapshot["finals"].get(key)
            if source is None:
                errors.append(f"boundary not in source Final: {key}")
                continue
            for csv_name, source_name in (("predicted_frame", "frame"), ("candidate_type", "candidate_type"),
                                          ("representative_candidate_id", "representative_candidate_id"),
                                          ("member_candidate_ids", "member_candidate_ids"),
                                          ("member_candidate_types", "member_candidate_types"),
                                          ("member_candidate_frames", "member_candidate_frames"),
                                          ("member_candidate_count", "member_candidate_count")):
                if str(row[csv_name]) != str(source[source_name]):
                    errors.append(f"source Final mismatch: {key}/{csv_name}")
        if any(int(row["effective_review_id"]) not in snapshot["signal_review_ids"] for row in signals):
            errors.append("signal review_id missing from SQLite snapshot")
        if any(int(row["effective_review_id"]) not in snapshot["boundary_review_ids"] for row in predicted):
            errors.append("boundary review_id missing from SQLite snapshot")
        if any(int(row["review_id"]) not in snapshot["added_review_ids"] for row in added):
            errors.append("added review_id missing from SQLite snapshot")
        for name in DATA_FILES:
            if meta.get("files_sha256", {}).get(name) != sha256_file(root / name):
                errors.append(f"SHA256 mismatch: {name}")
        if len(signals) != int(meta.get("signal_review_row_count", -1)) or len(predicted) != int(meta.get("predicted_boundary_review_row_count", -1)) or len(added) != int(meta.get("human_added_boundary_row_count", -1)):
            errors.append("metadata row counts mismatch")
        if errors:
            raise ExportValidationError("EXPORT_VALIDATION_FAILED: " + " | ".join(errors))
        return {"status": "PASS", "signal_rows": len(signals), "predicted_rows": len(predicted), "added_rows": len(added)}

    def list_exports(self, *, source_run_id: str | None = None) -> list[dict[str, Any]]:
        if not self.export_root.is_dir():
            return []
        out = []
        for path in sorted((item for item in self.export_root.iterdir() if item.is_dir() and not item.name.startswith(".tmp-")), reverse=True):
            try:
                meta = json.loads((path / "export_meta.json").read_text(encoding="utf-8"))
                if source_run_id and meta.get("source_run_id") != source_run_id:
                    continue
                valid = all((path / name).is_file() and meta.get("files_sha256", {}).get(name) == sha256_file(path / name) for name in DATA_FILES)
                out.append({**meta, "validation_status": "PASS" if valid else "FAIL", "export_path": str(path)})
            except (OSError, json.JSONDecodeError):
                continue
        return out
