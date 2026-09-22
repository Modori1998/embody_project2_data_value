"""P2_G1_AUDIT_FOLDER_V1 fail-fast validator. No silent repair."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .hashes import config_hash_from_payload, load_json
from project2_g1.final_semantics import (
    FINAL_BOUNDARY_SEMANTICS_V1,
    FinalSemanticsError,
    SEMANTICS_LINEAGE_ONLY,
    SEMANTICS_MATERIALIZED,
    candidate_index_from_rows,
    detect_final_schema,
    validate_materialized_final_row,
)

CONTRACT_VERSION = "P2_G1_AUDIT_FOLDER_V1"

ALLOWED_RUN_STAGES = frozenset(
    {"EXPLORATORY_AUDIT", "CALIBRATION", "EVALUATION", "DESIGN_DIAGNOSTIC"}
)
ALLOWED_SET_ROLES = frozenset(
    {"EXPLORATORY", "CALIBRATION", "EVALUATION", "DESIGN_DIAGNOSTIC"}
)
STAGE_TO_SET_ROLE = {
    "EXPLORATORY_AUDIT": "EXPLORATORY",
    "CALIBRATION": "CALIBRATION",
    "EVALUATION": "EVALUATION",
    "DESIGN_DIAGNOSTIC": "DESIGN_DIAGNOSTIC",
}

# --- Design Diagnostic (additive, frozen) ---------------------------------
# A DESIGN_DIAGNOSTIC run is human-reviewable exactly like the other stages but
# is permanently barred from every downstream consumption path. This block is
# additive only: it does not change EXPLORATORY_AUDIT / CALIBRATION / EVALUATION
# behaviour in any way.
DESIGN_DIAGNOSTIC_RUN_STAGE = "DESIGN_DIAGNOSTIC"
DESIGN_DIAGNOSTIC_SET_ROLE = "DESIGN_DIAGNOSTIC"
DESIGN_DIAGNOSTIC_BLOCKED_DOWNSTREAMS = (
    "CALIBRATION_EXPORT_ELIGIBLE",
    "CANONICAL_GT_ELIGIBLE",
    "EVALUATION_ELIGIBLE",
)


def is_design_diagnostic(stage_or_role: str | None) -> bool:
    """True for the DESIGN_DIAGNOSTIC run_stage or set_role."""

    return str(stage_or_role or "").strip() == DESIGN_DIAGNOSTIC_RUN_STAGE


def blocked_downstreams(run_stage: str | None) -> tuple[str, ...]:
    """Downstream paths that are hard-blocked for a given run_stage."""

    return (
        DESIGN_DIAGNOSTIC_BLOCKED_DOWNSTREAMS
        if is_design_diagnostic(run_stage)
        else ()
    )

REQUIRED_RUN_META_FIELDS = (
    "contract_version",
    "run_id",
    "run_stage",
    "created_at",
    "parent_run_id",
    "config_version",
    "config_hash",
    "segmentation_version",
    "signal_contract_version",
    "signal_contract_hash",
    "source_dataset_id",
    "episode_count",
    "codebook_path",
    "manifest_path",
    "config_snapshot_path",
)

REQUIRED_MANIFEST_FIELDS = (
    "run_id",
    "episode_id",
    "native_episode_key",
    "demo_key",
    "source_hdf5",
    "source_dataset_id",
    "set_role",
    "config_hash",
    "signal_contract_version",
    "signal_contract_hash",
    "video_relpath",
    "plot_relpath",
    "candidates_relpath",
    "boundaries_relpath",
    "segments_relpath",
    "smoke_relpath",
    "quality_group",
    "review_required",
    "length",
    "candidate_count",
    "suppressed_count",
    "final_boundary_count",
    "segment_count",
    "short_segment_count",
    "long_segment_count",
    "cluster_count",
    "deactivated_candidate_count",
    "keep_count",
    "merge_count",
    "retain_hard_count",
    "alignment",
    "nan_inf",
)

REQUIRED_EPISODE_FILES = (
    "video_relpath",
    "plot_relpath",
    "candidates_relpath",
    "boundaries_relpath",
    "segments_relpath",
    "smoke_relpath",
)

MEDIA_KEYS = ("video", "signal_boundary_plot", "signal_plot")
MEDIA_FIELD_BY_KEY = {
    "video": "video_relpath",
    "signal_boundary_plot": "plot_relpath",
    "signal_plot": "signal_plot_relpath",
}


class ContractError(ValueError):
    pass


def _fail(message: str) -> None:
    raise ContractError(message)


def _as_posix_rel(value: Any, *, field: str, episode_id: str) -> str:
    text = str(value or "").strip()
    if not text:
        _fail(f"{episode_id}: {field} is empty")
    if Path(text).is_absolute() or text.startswith("/") or text.startswith("\\"):
        _fail(f"{episode_id}: {field} must be relative, got {text!r}")
    if "\\" in text:
        _fail(f"{episode_id}: {field} must use posix separators, got {text!r}")
    parts = Path(text).parts
    if ".." in parts:
        _fail(f"{episode_id}: {field} must not contain '..'")
    return text


def _parse_bool(value: Any, *, field: str, episode_id: str) -> bool:
    text = str(value).strip().lower()
    if text in {"1", "true", "yes"}:
        return True
    if text in {"0", "false", "no"}:
        return False
    _fail(f"{episode_id}: {field} is not a boolean: {value!r}")
    return False


def _parse_int(value: Any, *, field: str, episode_id: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        _fail(f"{episode_id}: {field} is not an integer: {value!r}")
        return 0


def validate_g1_audit_folder(run_root: str | Path) -> dict[str, Any]:
    root = Path(run_root).resolve()
    if not root.is_dir():
        _fail(f"run folder does not exist: {root}")

    meta_path = root / "run_meta.json"
    if not meta_path.is_file():
        _fail("missing run_meta.json")
    try:
        meta = load_json(meta_path)
    except json.JSONDecodeError as exc:
        _fail(f"run_meta.json is not valid JSON: {exc}")
    if not isinstance(meta, dict):
        _fail("run_meta.json must be an object")

    missing = [key for key in REQUIRED_RUN_META_FIELDS if key not in meta]
    if missing:
        _fail(f"run_meta.json missing fields: {', '.join(missing)}")
    if str(meta["contract_version"]) != CONTRACT_VERSION:
        _fail(
            f"contract_version mismatch: expected {CONTRACT_VERSION}, got {meta['contract_version']!r}"
        )
    run_stage = str(meta["run_stage"])
    if run_stage not in ALLOWED_RUN_STAGES:
        _fail(f"unsupported run_stage: {run_stage!r}")
    run_id = str(meta["run_id"]).strip()
    if not run_id:
        _fail("run_id is empty")

    expected_set_role = STAGE_TO_SET_ROLE[run_stage]
    codebook_rel = _as_posix_rel(meta["codebook_path"], field="codebook_path", episode_id="run_meta")
    manifest_rel = _as_posix_rel(meta["manifest_path"], field="manifest_path", episode_id="run_meta")
    snapshot_rel = _as_posix_rel(
        meta["config_snapshot_path"], field="config_snapshot_path", episode_id="run_meta"
    )
    codebook_path = root / codebook_rel
    manifest_path = root / manifest_rel
    snapshot_path = root / snapshot_rel
    if not codebook_path.is_file():
        _fail(f"missing codebook: {codebook_rel}")
    if not snapshot_path.is_file():
        _fail(f"missing config snapshot: {snapshot_rel}")
    if not manifest_path.is_file():
        _fail(f"missing episode_manifest.csv: {manifest_rel}")

    try:
        snapshot = load_json(snapshot_path)
    except json.JSONDecodeError as exc:
        _fail(f"config_snapshot.json is not valid JSON: {exc}")
    actual_config_hash = config_hash_from_payload(snapshot)
    declared_config_hash = str(meta["config_hash"]).strip().lower()
    if actual_config_hash != declared_config_hash:
        _fail(
            "config_hash mismatch: run_meta declares "
            f"{declared_config_hash} but snapshot hashes to {actual_config_hash}"
        )

    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            _fail("episode_manifest.csv has no header")
        missing_cols = [key for key in REQUIRED_MANIFEST_FIELDS if key not in reader.fieldnames]
        if missing_cols:
            _fail(f"episode_manifest.csv missing columns: {', '.join(missing_cols)}")
        rows = list(reader)

    expected_count = int(meta["episode_count"])
    if len(rows) != expected_count:
        _fail(f"episode_count={expected_count} but manifest has {len(rows)} rows")

    seen: set[str] = set()
    episodes: list[dict[str, Any]] = []
    for row in rows:
        episode_id = str(row.get("episode_id") or "").strip()
        if not episode_id:
            _fail("episode_manifest.csv contains an empty episode_id")
        if episode_id in seen:
            _fail(f"duplicate episode_id: {episode_id}")
        seen.add(episode_id)
        if str(row.get("run_id") or "").strip() != run_id:
            _fail(f"{episode_id}: manifest run_id does not match run_meta")
        if str(row.get("config_hash") or "").strip().lower() != declared_config_hash:
            _fail(f"{episode_id}: manifest config_hash does not match run_meta")
        if str(row.get("signal_contract_version") or "") != str(meta["signal_contract_version"]):
            _fail(f"{episode_id}: signal_contract_version does not match run_meta")
        if str(row.get("signal_contract_hash") or "").strip().lower() != str(meta["signal_contract_hash"]).strip().lower():
            _fail(f"{episode_id}: signal_contract_hash does not match run_meta")
        set_role = str(row.get("set_role") or "").strip()
        if set_role not in ALLOWED_SET_ROLES:
            _fail(f"{episode_id}: unsupported set_role {set_role!r}")
        if set_role != expected_set_role:
            _fail(
                f"{episode_id}: set_role={set_role} is inconsistent with run_stage={run_stage}"
            )
        resolved: dict[str, Any] = dict(row)
        resolved["review_required"] = _parse_bool(
            row.get("review_required"), field="review_required", episode_id=episode_id
        )
        for int_field in (
            "length",
            "candidate_count",
            "suppressed_count",
            "final_boundary_count",
            "segment_count",
            "short_segment_count",
            "long_segment_count",
            "cluster_count",
            "deactivated_candidate_count",
            "keep_count",
            "merge_count",
            "retain_hard_count",
        ):
            resolved[int_field] = _parse_int(row.get(int_field), field=int_field, episode_id=episode_id)
        for field in REQUIRED_EPISODE_FILES:
            rel = _as_posix_rel(row.get(field), field=field, episode_id=episode_id)
            resolved[field] = rel
            if not (root / rel).is_file():
                _fail(f"{episode_id}: missing {field} file {rel}")
        plot_rel = str(row.get("signal_plot_relpath") or "").strip()
        if plot_rel:
            plot_rel = _as_posix_rel(plot_rel, field="signal_plot_relpath", episode_id=episode_id)
            if not (root / plot_rel).is_file():
                _fail(f"{episode_id}: missing signal_plot_relpath file {plot_rel}")
            resolved["signal_plot_relpath"] = plot_rel
        else:
            resolved["signal_plot_relpath"] = ""
        resolved["final_member_semantics"] = _validate_episode_final_semantics(
            root,
            episode_id=episode_id,
            candidates_rel=resolved["candidates_relpath"],
            boundaries_rel=resolved["boundaries_relpath"],
            declared_semantics=str(meta.get("final_boundary_semantics") or "").strip(),
        )
        episodes.append(resolved)

    modes = {str(item.get("final_member_semantics") or "") for item in episodes}
    if len(modes) > 1:
        _fail(f"mixed Final member semantics in one run: {sorted(modes)}")
    run_semantics = next(iter(modes)) if modes else SEMANTICS_LINEAGE_ONLY
    declared = str(meta.get("final_boundary_semantics") or "").strip()
    if declared == FINAL_BOUNDARY_SEMANTICS_V1 and run_semantics != SEMANTICS_MATERIALIZED:
        _fail("run_meta.final_boundary_semantics=MATERIALIZED_V1 but final_boundaries.csv is LINEAGE_ONLY")

    return {
        "run_root": str(root),
        "run_meta": meta,
        "run_id": run_id,
        "run_stage": run_stage,
        "config_hash": declared_config_hash,
        "signal_contract_version": str(meta["signal_contract_version"]),
        "signal_contract_hash": str(meta["signal_contract_hash"]),
        "episodes": episodes,
        "codebook_path": str(codebook_path),
        "manifest_path": str(manifest_path),
        "config_snapshot_path": str(snapshot_path),
        "media_keys": list(MEDIA_KEYS),
        "final_member_semantics": run_semantics,
    }


def _validate_episode_final_semantics(
    root: Path,
    *,
    episode_id: str,
    candidates_rel: str,
    boundaries_rel: str,
    declared_semantics: str,
) -> str:
    cand_path = root / candidates_rel
    bound_path = root / boundaries_rel
    with bound_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        try:
            schema = detect_final_schema(reader.fieldnames)
        except FinalSemanticsError as exc:
            _fail(f"{episode_id}: {exc}")
        finals = list(reader)
    if declared_semantics == FINAL_BOUNDARY_SEMANTICS_V1 and schema != SEMANTICS_MATERIALIZED:
        _fail(f"{episode_id}: MATERIALIZED_V1 declared but final_boundaries.csv is lineage-only")
    if schema != SEMANTICS_MATERIALIZED:
        return SEMANTICS_LINEAGE_ONLY
    with cand_path.open("r", encoding="utf-8", newline="") as handle:
        candidates = list(csv.DictReader(handle))
    by_id = candidate_index_from_rows(candidates)
    for row in finals:
        try:
            validate_materialized_final_row(row, by_id)
        except FinalSemanticsError as exc:
            _fail(f"{episode_id}: {exc}")
    return SEMANTICS_MATERIALIZED
