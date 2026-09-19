"""Shared helpers for G1 Audit Web Batch 1 tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from project2_g1_audit_web.contract import CONTRACT_VERSION
from project2_g1_audit_web.hashes import SIGNAL_CONTRACT_VERSION, config_hash_from_payload

MIN_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _write(path: Path, text: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")


def _csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_synthetic_run(
    root: Path,
    *,
    run_id: str = "g1_exploratory_audit_test_00000000",
    n_episodes: int = 2,
    contract_version: str = CONTRACT_VERSION,
    config_payload: dict[str, Any] | None = None,
    mutate_hash: bool = False,
    duplicate_episode: bool = False,
    missing_plot: bool = False,
    escape_path: bool = False,
    extra_episode_path: str | None = None,
    signal_hash: str | None = None,
    signal_contract_version: str = SIGNAL_CONTRACT_VERSION,
) -> Path:
    snapshot = config_payload or {"config_version": "g1_p2_exploratory_segmentation.v0", "parameters": {"motion_speed_threshold": {"value": 0.02}}}
    config_hash = config_hash_from_payload(snapshot)
    if mutate_hash:
        declared_hash = "0" * 64
    else:
        declared_hash = config_hash
    signal_hash = str(signal_hash or "a" * 64)
    signal_version = str(signal_contract_version or SIGNAL_CONTRACT_VERSION)
    run_root = root / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    _write(run_root / "human_boundary_review_codebook.json", json.dumps({"human_review": ["VALID"]}))
    _write(run_root / "config_snapshot.json", json.dumps(snapshot, indent=2))
    rows = []
    names = [f"demo_{i}" for i in range(n_episodes)]
    if duplicate_episode:
        names.append("demo_0")
    for index, native in enumerate(names):
        episode_id = f"data/{native}" if not (duplicate_episode and index == len(names) - 1) else "data/demo_0"
        if duplicate_episode and index == len(names) - 1:
            native = f"demo_dup_{index}"
        video_rel = f"media/{native}/video.mp4"
        plot_rel = "../secret.png" if escape_path and index == 0 else f"diagnostic/{native}/signal_boundary_plot.png"
        p1_plot_rel = f"diagnostic/{native}/signal_plot.png"
        cand_rel = f"diagnostic/{native}/candidate_boundaries.csv"
        bound_rel = f"diagnostic/{native}/final_boundaries.csv"
        seg_rel = f"diagnostic/{native}/segment_manifest.csv"
        smoke_rel = f"diagnostic/{native}/boundary_decisions.csv"
        _write(run_root / video_rel, b"fake-mp4-bytes-" + native.encode("ascii") + b"-0123456789")
        if not (missing_plot and index == 0):
            _write(run_root / (plot_rel if not escape_path else f"diagnostic/{native}/signal_boundary_plot.png"), MIN_PNG)
        _write(run_root / p1_plot_rel, MIN_PNG)
        if extra_episode_path:
            _write(Path(extra_episode_path), b"secret")
        _csv(
            run_root / cand_rel,
            ["episode_id", "candidate_id", "frame", "candidate_type", "primary_reason", "supporting_reasons", "evidence_value", "persistence_status", "source_signal", "polarity"],
            [{"episode_id": episode_id, "candidate_id": f"{native}-C0001", "frame": "4", "candidate_type": "GRIPPER_TRANSITION", "primary_reason": "X", "supporting_reasons": "", "evidence_value": "0.1", "persistence_status": "PERSISTENT", "source_signal": "gripper_aperture", "polarity": "CLOSE_TO_OPEN"}],
        )
        _csv(
            run_root / bound_rel,
            ["boundary_id", "episode_id", "frame", "candidate_type", "reason", "member_candidate_ids", "supporting_reasons", "review_flags"],
            [{"boundary_id": f"{native}-B0001", "episode_id": episode_id, "frame": "4", "candidate_type": "GRIPPER_TRANSITION", "reason": "X", "member_candidate_ids": f"{native}-C0001", "supporting_reasons": "", "review_flags": "REVIEW_REQUIRED"}],
        )
        _csv(
            run_root / smoke_rel,
            ["episode_id", "candidate_id", "frame", "candidate_type", "decision", "reason", "target_boundary_id"],
            [{"episode_id": episode_id, "candidate_id": f"{native}-C0001", "frame": "4", "candidate_type": "GRIPPER_TRANSITION", "decision": "KEEP", "reason": "keep", "target_boundary_id": f"{native}-B0001"}],
        )
        _csv(
            run_root / seg_rel,
            ["segment_id", "start_frame", "end_frame", "duration_frames", "left_boundary_id", "right_boundary_id", "short_segment_flag", "long_segment_flag", "review_required", "review_flags"],
            [{"segment_id": f"{native}-S0001", "start_frame": "0", "end_frame": "3", "duration_frames": "4", "left_boundary_id": "EPISODE_START", "right_boundary_id": f"{native}-B0001", "short_segment_flag": "True", "long_segment_flag": "False", "review_required": "True", "review_flags": "SHORT_SEGMENT_CANDIDATE"}],
        )
        rows.append(
            {
                "run_id": run_id,
                "episode_id": "data/demo_0" if duplicate_episode and index == len(names) - 1 else episode_id,
                "native_episode_key": native,
                "demo_key": native,
                "source_hdf5": "demo_v15.hdf5",
                "source_dataset_id": "robomimic_v15_can_mh",
                "set_role": "EXPLORATORY",
                "config_hash": declared_hash,
                "signal_contract_version": signal_version,
                "signal_contract_hash": signal_hash,
                "video_relpath": video_rel,
                "plot_relpath": plot_rel,
                "signal_plot_relpath": p1_plot_rel,
                "candidates_relpath": cand_rel,
                "boundaries_relpath": bound_rel,
                "segments_relpath": seg_rel,
                "smoke_relpath": smoke_rel,
                "quality_group": "BETTER" if index % 2 == 0 else "WORSE",
                "review_required": "true",
                "length": "10",
                "candidate_count": "1",
                "suppressed_count": "0",
                "final_boundary_count": "1",
                "segment_count": "1",
                "short_segment_count": "1",
                "long_segment_count": "0",
                "cluster_count": "1",
                "deactivated_candidate_count": "0",
                "keep_count": "1",
                "merge_count": "0",
                "retain_hard_count": "0",
                "alignment": "PASS",
                "nan_inf": "PASS",
            }
        )
    _csv(run_root / "episode_manifest.csv", list(rows[0].keys()), rows)
    meta = {
        "contract_version": contract_version,
        "run_id": run_id,
        "run_stage": "EXPLORATORY_AUDIT",
        "created_at": "2026-09-16T00:00:00+08:00",
        "parent_run_id": None,
        "config_version": snapshot.get("config_version"),
        "config_hash": declared_hash,
        "segmentation_version": "G1-P2-EXPLORATORY-v0",
        "signal_contract_version": signal_version,
        "signal_contract_hash": signal_hash,
        "source_dataset_id": "robomimic_v15_can_mh",
        "episode_count": len(rows),
        "codebook_path": "human_boundary_review_codebook.json",
        "manifest_path": "episode_manifest.csv",
        "config_snapshot_path": "config_snapshot.json",
    }
    _write(run_root / "run_meta.json", json.dumps(meta, indent=2))
    return run_root


def write_merge_semantics_run(
    root: Path,
    *,
    materialized: bool,
    unknown_member: bool = False,
    run_id: str = "g1_exploratory_audit_merge_00000000",
) -> Path:
    """Synthetic run with 1/2/3-member Final Boundaries on demo_0."""

    from project2_g1.final_semantics import (
        FINAL_BOUNDARY_SEMANTICS_V1,
        candidate_index_from_rows,
        materialize_final_row,
    )

    run_root = write_synthetic_run(root, run_id=run_id, n_episodes=2)
    native = "demo_0"
    episode_id = "data/demo_0"
    weird = "WEIRD_UNREGISTERED_TYPE"
    direction_type = weird if unknown_member else "DIRECTION_CHANGE"
    candidates = [
        {
            "episode_id": episode_id,
            "candidate_id": f"{native}-C0001",
            "frame": "4",
            "candidate_type": "GRIPPER_TRANSITION",
            "primary_reason": "X",
            "supporting_reasons": "",
            "evidence_value": "0.1",
            "persistence_status": "PERSISTENT",
            "source_signal": "gripper_aperture",
            "polarity": "CLOSE_TO_OPEN",
        },
        {
            "episode_id": episode_id,
            "candidate_id": f"{native}-C0002",
            "frame": "56",
            "candidate_type": "GRIPPER_TRANSITION",
            "primary_reason": "X",
            "supporting_reasons": "",
            "evidence_value": "0.1",
            "persistence_status": "PERSISTENT",
            "source_signal": "gripper_aperture",
            "polarity": "OPEN_TO_CLOSE",
        },
        {
            "episode_id": episode_id,
            "candidate_id": f"{native}-C0003",
            "frame": "57",
            "candidate_type": direction_type,
            "primary_reason": "X",
            "supporting_reasons": "ACTION_SUPPORT",
            "evidence_value": "0.1",
            "persistence_status": "PERSISTENT",
            "source_signal": "direction_change_evidence",
            "polarity": "DIRECTION_CHANGE",
        },
        {
            "episode_id": episode_id,
            "candidate_id": f"{native}-C0004",
            "frame": "112",
            "candidate_type": "GRIPPER_TRANSITION",
            "primary_reason": "X",
            "supporting_reasons": "",
            "evidence_value": "0.1",
            "persistence_status": "PERSISTENT",
            "source_signal": "gripper_aperture",
            "polarity": "CLOSE_TO_OPEN",
        },
        {
            "episode_id": episode_id,
            "candidate_id": f"{native}-C0005",
            "frame": "113",
            "candidate_type": "MOVE_TO_IDLE",
            "primary_reason": "X",
            "supporting_reasons": "",
            "evidence_value": "0.1",
            "persistence_status": "PERSISTENT",
            "source_signal": "translation_speed",
            "polarity": "MOVE_TO_IDLE",
        },
        {
            "episode_id": episode_id,
            "candidate_id": f"{native}-C0006",
            "frame": "114",
            "candidate_type": "DIRECTION_CHANGE",
            "primary_reason": "X",
            "supporting_reasons": "",
            "evidence_value": "0.1",
            "persistence_status": "PERSISTENT",
            "source_signal": "direction_change_evidence",
            "polarity": "DIRECTION_CHANGE",
        },
    ]
    finals = [
        {
            "boundary_id": f"{native}-B0001",
            "episode_id": episode_id,
            "frame": "4",
            "candidate_type": "GRIPPER_TRANSITION",
            "reason": "X",
            "member_candidate_ids": f"{native}-C0001",
            "supporting_reasons": "",
            "review_flags": "REVIEW_REQUIRED",
            "polarity": "CLOSE_TO_OPEN",
            "config_version": "g1_p2_exploratory_segmentation.v0",
            "segmentation_version": "G1-P2-EXPLORATORY-v0",
        },
        {
            "boundary_id": f"{native}-B0002",
            "episode_id": episode_id,
            "frame": "56",
            "candidate_type": "GRIPPER_TRANSITION",
            "reason": "X",
            "member_candidate_ids": f"{native}-C0002|{native}-C0003",
            "supporting_reasons": "ACTION_SUPPORT",
            "review_flags": "",
            "polarity": "OPEN_TO_CLOSE",
            "config_version": "g1_p2_exploratory_segmentation.v0",
            "segmentation_version": "G1-P2-EXPLORATORY-v0",
        },
        {
            "boundary_id": f"{native}-B0003",
            "episode_id": episode_id,
            "frame": "112",
            "candidate_type": "GRIPPER_TRANSITION",
            "reason": "X",
            "member_candidate_ids": f"{native}-C0004|{native}-C0005|{native}-C0006",
            "supporting_reasons": "",
            "review_flags": "",
            "polarity": "CLOSE_TO_OPEN",
            "config_version": "g1_p2_exploratory_segmentation.v0",
            "segmentation_version": "G1-P2-EXPLORATORY-v0",
        },
    ]
    cand_fields = [
        "episode_id",
        "candidate_id",
        "frame",
        "candidate_type",
        "primary_reason",
        "supporting_reasons",
        "evidence_value",
        "persistence_status",
        "source_signal",
        "polarity",
    ]
    lineage_fields = [
        "boundary_id",
        "episode_id",
        "frame",
        "candidate_type",
        "reason",
        "member_candidate_ids",
        "supporting_reasons",
        "review_flags",
        "polarity",
        "config_version",
        "segmentation_version",
    ]
    _csv(run_root / "diagnostic" / native / "candidate_boundaries.csv", cand_fields, candidates)
    _csv(run_root / "diagnostic" / native / "final_boundaries.csv", lineage_fields, finals)
    if not materialized:
        return run_root
    materialized_fields = [
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
    ]
    for bound in sorted((run_root / "diagnostic").glob("*/final_boundaries.csv")):
        cand = bound.parent / "candidate_boundaries.csv"
        with cand.open("r", encoding="utf-8", newline="") as handle:
            by_id = candidate_index_from_rows(list(csv.DictReader(handle)))
        with bound.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rewritten = [materialize_final_row(row, by_id) for row in rows]
        for item in rewritten:
            item.pop("members", None)
        _csv(bound, materialized_fields, rewritten)
    meta_path = run_root / "run_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["final_boundary_semantics"] = FINAL_BOUNDARY_SEMANTICS_V1
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return run_root
