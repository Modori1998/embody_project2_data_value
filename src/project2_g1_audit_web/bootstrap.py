"""Legacy G1-P2 audit package → versioned P2_G1_AUDIT_FOLDER_V1 run."""

from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from .contract import CONTRACT_VERSION, ContractError, validate_g1_audit_folder
from .hashes import (
    SIGNAL_CONTRACT_VERSION,
    SOURCE_DATASET_ID,
    allocate_run_id,
    config_hash_from_payload,
    now_iso,
    signal_contract_hash_from_path,
)
from .registry import auto_register, default_owner_db_path, default_registry_path

REQUIRED_LEGACY_EPISODE_FILES = (
    "video.mp4",
    "signal_boundary_plot.png",
    "candidate_boundaries.csv",
    "boundary_decisions.csv",
    "final_boundaries.csv",
    "segment_manifest.csv",
)
MERGE_DECISIONS = frozenset({"MERGE_CONSOLIDATION", "MERGE_LEFT", "MERGE_RIGHT"})
SOURCE_HDF5_NAME = "demo_v15.hdf5"


def _copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _decision_counts(rows: list[dict[str, str]]) -> tuple[int, int, int]:
    counter = Counter(str(row.get("decision") or "").strip() for row in rows)
    keep = counter.get("KEEP", 0)
    retain = counter.get("RETAIN_HARD", 0)
    merge = sum(counter[name] for name in MERGE_DECISIONS)
    return keep, merge, retain


def bootstrap_legacy_run(
    *,
    project_root: str | Path,
    legacy_root: str | Path | None = None,
    p1_root: str | Path | None = None,
    p1_config_path: str | Path | None = None,
    dest_parent: str | Path | None = None,
    register: bool = True,
    salt: str = "",
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    legacy = Path(legacy_root or (root / "outputs" / "g1_p2_boundary_audit")).resolve()
    p1 = Path(p1_root or (root / "outputs" / "g1_p1_signal_audit")).resolve()
    p1_config = Path(p1_config_path or (root / "configs" / "g1_p1_signal_contract.json"))
    dest_parent_path = Path(dest_parent or (root / "outputs" / "g1_audit_runs")).resolve()

    if not legacy.is_dir():
        raise ContractError(f"legacy G1-P2 package missing: {legacy}")
    snapshot_src = legacy / "exploratory_config.json"
    codebook_src = legacy / "human_boundary_review_codebook.json"
    legacy_manifest = legacy / "episode_manifest.csv"
    for required in (snapshot_src, codebook_src, legacy_manifest):
        if not required.is_file():
            raise ContractError(f"legacy package missing {required.name}")
    if not p1_config.is_file():
        raise ContractError(f"P1 signal contract config missing: {p1_config}")

    snapshot = json.loads(snapshot_src.read_text(encoding="utf-8"))
    config_hash = config_hash_from_payload(snapshot)
    signal_hash = signal_contract_hash_from_path(p1_config)
    created_at = now_iso()
    run_id = allocate_run_id(
        run_stage="EXPLORATORY_AUDIT",
        config_hash=config_hash,
        created_at=created_at,
        salt=salt,
    )
    run_root = dest_parent_path / run_id
    if run_root.exists():
        raise ContractError(f"versioned run root already exists: {run_root}")

    rows = _read_csv(legacy_manifest)
    if not rows:
        raise ContractError("legacy episode_manifest.csv is empty")

    materialized: list[dict[str, Any]] = []
    for row in rows:
        episode_id = str(row.get("episode_id") or "").strip()
        native = str(row.get("native_episode_key") or "").strip()
        if not episode_id or not native:
            raise ContractError("legacy manifest row missing episode_id / native_episode_key")
        src_dir = legacy / native
        for name in REQUIRED_LEGACY_EPISODE_FILES:
            if not (src_dir / name).is_file():
                raise ContractError(f"{episode_id}: legacy missing {name}")
        video_rel = f"media/{native}/video.mp4"
        plot_rel = f"diagnostic/{native}/signal_boundary_plot.png"
        cand_rel = f"diagnostic/{native}/candidate_boundaries.csv"
        bound_rel = f"diagnostic/{native}/final_boundaries.csv"
        seg_rel = f"diagnostic/{native}/segment_manifest.csv"
        smoke_rel = f"diagnostic/{native}/boundary_decisions.csv"
        _copy_file(src_dir / "video.mp4", run_root / video_rel)
        _copy_file(src_dir / "signal_boundary_plot.png", run_root / plot_rel)
        _copy_file(src_dir / "candidate_boundaries.csv", run_root / cand_rel)
        _copy_file(src_dir / "final_boundaries.csv", run_root / bound_rel)
        _copy_file(src_dir / "segment_manifest.csv", run_root / seg_rel)
        _copy_file(src_dir / "boundary_decisions.csv", run_root / smoke_rel)
        p1_plot = p1 / native / "signal_plot.png"
        signal_plot_rel = ""
        if p1_plot.is_file():
            signal_plot_rel = f"diagnostic/{native}/signal_plot.png"
            _copy_file(p1_plot, run_root / signal_plot_rel)
        keep, merge, retain = _decision_counts(_read_csv(src_dir / "boundary_decisions.csv"))
        materialized.append(
            {
                "run_id": run_id,
                "episode_id": episode_id,
                "native_episode_key": native,
                "demo_key": native,
                "source_hdf5": SOURCE_HDF5_NAME,
                "source_dataset_id": SOURCE_DATASET_ID,
                "set_role": "EXPLORATORY",
                "config_hash": config_hash,
                "signal_contract_version": SIGNAL_CONTRACT_VERSION,
                "signal_contract_hash": signal_hash,
                "video_relpath": video_rel,
                "plot_relpath": plot_rel,
                "signal_plot_relpath": signal_plot_rel,
                "candidates_relpath": cand_rel,
                "boundaries_relpath": bound_rel,
                "segments_relpath": seg_rel,
                "smoke_relpath": smoke_rel,
                "quality_group": str(row.get("quality_group") or ""),
                "review_required": str(row.get("review_required") or "true"),
                "length": str(row.get("length") or "0"),
                "candidate_count": str(row.get("candidate_count") or "0"),
                "suppressed_count": str(row.get("suppressed_count") or "0"),
                "final_boundary_count": str(row.get("final_boundary_count") or "0"),
                "segment_count": str(row.get("segment_count") or "0"),
                "short_segment_count": str(row.get("short_segment_count") or "0"),
                "long_segment_count": str(row.get("long_segment_count") or "0"),
                "cluster_count": str(row.get("final_boundary_count") or "0"),
                "deactivated_candidate_count": str(row.get("suppressed_count") or "0"),
                "keep_count": str(keep),
                "merge_count": str(merge),
                "retain_hard_count": str(retain),
                "alignment": str(row.get("alignment") or ""),
                "nan_inf": str(row.get("nan_inf") or ""),
            }
        )

    _copy_file(codebook_src, run_root / "human_boundary_review_codebook.json")
    _write_json(run_root / "config_snapshot.json", snapshot)
    fieldnames = list(materialized[0].keys())
    manifest_path = run_root / "episode_manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(materialized)

    run_meta = {
        "contract_version": CONTRACT_VERSION,
        "run_id": run_id,
        "run_stage": "EXPLORATORY_AUDIT",
        "created_at": created_at,
        "parent_run_id": None,
        "config_version": str(snapshot.get("config_version") or ""),
        "config_hash": config_hash,
        "segmentation_version": str(snapshot.get("segmentation_version") or ""),
        "signal_contract_version": SIGNAL_CONTRACT_VERSION,
        "signal_contract_hash": signal_hash,
        "source_dataset_id": SOURCE_DATASET_ID,
        "episode_count": len(materialized),
        "codebook_path": "human_boundary_review_codebook.json",
        "manifest_path": "episode_manifest.csv",
        "config_snapshot_path": "config_snapshot.json",
        "legacy_source": str(legacy),
        "bootstrap": True,
        "g1_p2_status": "EXPLORATORY_ONLY",
    }
    _write_json(run_root / "run_meta.json", run_meta)
    validated = validate_g1_audit_folder(run_root)
    record = None
    if register:
        record = auto_register(
            default_registry_path(root),
            run_root,
            owner_db_path=default_owner_db_path(root),
            owner_note="legacy G1-P2 bootstrap",
        )
    return {
        "run_id": run_id,
        "run_root": str(run_root),
        "validated": validated,
        "registry_record": record,
        "episode_count": len(materialized),
        "config_hash": config_hash,
        "signal_contract_hash": signal_hash,
    }
