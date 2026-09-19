"""Copy a validated lineage-only G1 Audit Run and materialize Final member semantics.

Does not re-run Detector, Signal, candidate detection, or consolidation.
Candidate / Decision / Segment / media files are copied unchanged.
Only final_boundaries.csv columns and additive run_meta markers change.
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any

from project2_g1.final_semantics import (
    FINAL_BOUNDARY_SEMANTICS_V1,
    SEMANTICS_LINEAGE_ONLY,
    SEMANTICS_MATERIALIZED,
    candidate_index_from_rows,
    detect_final_schema,
    materialize_final_row,
)
from project2_g1_audit_web.contract import CONTRACT_VERSION, ContractError, validate_g1_audit_folder
from project2_g1_audit_web.hashes import allocate_run_id, now_iso
from project2_g1_audit_web.registry import auto_register, default_owner_db_path, default_registry_path

MATERIALIZATION_KIND = "FINAL_BOUNDARY_MEMBER_SEMANTICS_V1"
MATERIALIZATION_SALT = "final_boundary_semantics_materialized_v1"

FINAL_FIELDNAMES = (
    "boundary_id",
    "episode_id",
    "frame",
    "candidate_type",
    "reason",
    "representative_candidate_id",
    "member_candidate_ids",
    "member_candidate_types",
    "member_candidate_frames",
    "member_candidate_count",
    "supporting_reasons",
    "review_flags",
    "polarity",
    "config_version",
    "segmentation_version",
)


def _rewrite_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def materialize_parent_run(
    *,
    project_root: str | Path,
    parent_run_root: str | Path,
    dest_parent: str | Path | None = None,
    register: bool = True,
    salt: str = MATERIALIZATION_SALT,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    parent = Path(parent_run_root).resolve()
    dest_parent_path = Path(dest_parent or (root / "outputs" / "g1_audit_runs")).resolve()
    parent_validated = validate_g1_audit_folder(parent)
    parent_mode = str(parent_validated.get("final_member_semantics") or SEMANTICS_LINEAGE_ONLY)
    if parent_mode != SEMANTICS_LINEAGE_ONLY:
        raise ContractError(f"parent run is not LINEAGE_ONLY: {parent_mode}")
    parent_meta = dict(parent_validated["run_meta"])
    created_at = now_iso()
    run_id = allocate_run_id(
        run_stage=str(parent_meta["run_stage"]),
        config_hash=str(parent_meta["config_hash"]),
        created_at=created_at,
        salt=salt,
    )
    dest = dest_parent_path / run_id
    if dest.exists():
        raise ContractError(f"child run root already exists: {dest}")
    shutil.copytree(parent, dest)

    for episode in parent_validated["episodes"]:
        cand_path = dest / str(episode["candidates_relpath"])
        bound_path = dest / str(episode["boundaries_relpath"])
        with cand_path.open("r", encoding="utf-8", newline="") as handle:
            candidates = list(csv.DictReader(handle))
        with bound_path.open("r", encoding="utf-8", newline="") as handle:
            schema = detect_final_schema(csv.DictReader(handle).fieldnames)
        if schema != SEMANTICS_LINEAGE_ONLY:
            raise ContractError(f"{episode['episode_id']}: expected lineage-only finals in parent copy")
        with bound_path.open("r", encoding="utf-8", newline="") as handle:
            finals = list(csv.DictReader(handle))
        by_id = candidate_index_from_rows(candidates)
        rewritten = [materialize_final_row(row, by_id) for row in finals]
        _rewrite_csv(bound_path, list(FINAL_FIELDNAMES), rewritten)

    manifest_path = dest / str(parent_meta["manifest_path"])
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    for row in rows:
        row["run_id"] = run_id
    _rewrite_csv(manifest_path, fieldnames, rows)

    child_meta = dict(parent_meta)
    child_meta["contract_version"] = CONTRACT_VERSION
    child_meta["run_id"] = run_id
    child_meta["created_at"] = created_at
    child_meta["parent_run_id"] = str(parent_meta["run_id"])
    child_meta["final_boundary_semantics"] = FINAL_BOUNDARY_SEMANTICS_V1
    child_meta["schema_materialization"] = MATERIALIZATION_KIND
    child_meta["bootstrap"] = False
    child_meta["materialization_note"] = (
        "SCHEMA MATERIALIZATION CHILD RUN. Copied parent Audit Folder; "
        "denormalized member type/frame onto final_boundaries.csv from Candidate SSOT. "
        "Detector, Signal, candidate detection, and consolidation were not re-run."
    )
    (dest / "run_meta.json").write_text(
        json.dumps(child_meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    validated = validate_g1_audit_folder(dest)
    if str(validated.get("final_member_semantics")) != SEMANTICS_MATERIALIZED:
        raise ContractError("child run did not validate as MATERIALIZED")
    record = None
    if register:
        record = auto_register(
            default_registry_path(root),
            dest,
            owner_db_path=default_owner_db_path(root),
            owner_note="final boundary member semantics materialization child",
        )
    return {
        "run_id": run_id,
        "run_root": str(dest),
        "parent_run_id": str(parent_meta["run_id"]),
        "parent_run_root": str(parent),
        "validated": validated,
        "registry_record": record,
        "config_hash": str(parent_meta["config_hash"]),
        "signal_contract_hash": str(parent_meta["signal_contract_hash"]),
        "episode_count": int(parent_meta["episode_count"]),
        "final_member_semantics": SEMANTICS_MATERIALIZED,
    }
