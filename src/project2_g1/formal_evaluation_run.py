"""Build the frozen G1-P4 Evaluation inference and Human Audit package.

This module intentionally has no episode-selection, tuning, GT, or scoring
surface.  It executes the frozen detector once and materializes an isolated
P2_G1_AUDIT_FOLDER_V1 run.
"""
from __future__ import annotations

import csv
import json
import shutil
import tempfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Mapping, Sequence

from project2_g1_audit_web.contract import CONTRACT_VERSION, validate_g1_audit_folder
from project2_g1_audit_web.hashes import (
    SIGNAL_CONTRACT_VERSION, allocate_run_id, config_hash_from_payload,
    now_iso, sha256_file, signal_contract_hash_from_path,
)
from project2_g1_audit_web.registry import auto_register
from project2_g1_audit_web.reviews import ReviewStore

from .alignment import audit_nan_inf, audit_temporal_alignment
from .boundary_config import load_g1_p2_config
from .boundary_engine import CANDIDATE_DIRECTION, CANDIDATE_GRIPPER, EngineResult
from .boundary_io import write_episode_audit_tables
from .config import load_g1_p1_config
from .evaluation_manifest_preparation import load_historical_sets
from .paths import CONFIG_PATH, DATASET_LOW_DIM_HDF5, DATASET_RAW_HDF5, G1_P2_CONFIG_PATH
from .plot import plot_episode_signals
from .signals import FormalSignals, compute_formal_signals
from .source import build_can_mh_adapter, enumerate_episodes, load_formal_episode
from .stage_b_calibration import STAGE_A_PARENT, TAU_C12, TAU_P12, run_window
from .stage_c_regression import build_edge_trace
from .video import count_video_frames, render_episode_audit_video

MANIFEST_VERSION = "G1_P4_EVAL_MANIFEST_v1"
FROZEN_CONFIG_NAME = "G1 Final Config FROZEN_v1"
EXPECTED_EPISODES = (
    "data/demo_129", "data/demo_176", "data/demo_91", "data/demo_18",
    "data/demo_275", "data/demo_234", "data/demo_3", "data/demo_178",
    "data/demo_94", "data/demo_10", "data/demo_224", "data/demo_58",
    "data/demo_141", "data/demo_161", "data/demo_262", "data/demo_121",
    "data/demo_253", "data/demo_284", "data/demo_20", "data/demo_207",
    "data/demo_85", "data/demo_46", "data/demo_238", "data/demo_282",
)
EXPECTED_RAW_SHA256 = "6f5a0e96fc375468ae19ccac86a6dee3b4d3862ef0fe37ca2d02e93d9046fe6b"
EXPECTED_LOW_SHA256 = "c4a34c837913446d295c6ca38f2b31888d69812198478af470ecb84a99e9f7d7"
DATASET_ID = "robomimic_v15_can_mh"
WINDOW = 8

FROZEN_MANIFEST = "0-doc/10-design-review/Project2_G1_P4_Independent_Evaluation_Manifest_FROZEN_v1_20260929.csv"
FROZEN_MANIFEST_DOC = "0-doc/10-design-review/Project2_G1_P4_Independent_Evaluation_Manifest_FROZEN_v1_20260929.md"
FROZEN_CONFIG_DOC = "0-doc/10-design-review/Project2_G1_P3_Final_Calibration_Config_FROZEN_v1_20260927.md"
CODEBOOK_SOURCE = "outputs/g1_audit_runs/g1_exploratory_audit_20260917_141541_fe251439/human_boundary_review_codebook.json"

MANIFEST_FIELDS = (
    "run_id", "episode_id", "native_episode_key", "demo_key", "source_hdf5",
    "source_dataset_id", "set_role", "config_hash", "signal_contract_version",
    "signal_contract_hash", "video_relpath", "plot_relpath", "signal_plot_relpath",
    "candidates_relpath", "boundaries_relpath", "segments_relpath", "smoke_relpath",
    "quality_group", "review_required", "length", "candidate_count",
    "suppressed_count", "final_boundary_count", "segment_count", "short_segment_count",
    "long_segment_count", "cluster_count", "deactivated_candidate_count", "keep_count",
    "merge_count", "retain_hard_count", "alignment", "nan_inf",
)

class FormalEvaluationRunError(ValueError):
    pass

def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))

def _write_csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)

def _render_worker(root: str, episode_id: str, output: str, fps: float) -> dict[str, Any]:
    project_root = Path(root)
    config = load_g1_p1_config(project_root / "configs" / CONFIG_PATH.name)
    adapter = build_can_mh_adapter(config)
    try:
        return render_episode_audit_video(adapter, episode_id, output, fps=fps)
    finally:
        close = getattr(adapter, "close", None)
        if close: close()

def _formal_signal_rows(signals: FormalSignals) -> list[dict[str, Any]]:
    arrays = signals.arrays_for_quality_check()
    rows = []
    for i, frame in enumerate(signals.frame_index):
        row: dict[str, Any] = {"episode_id": signals.source_episode_id, "frame": int(frame)}
        for name, values in arrays.items():
            value = values[i]
            if getattr(value, "ndim", 0) == 0:
                row[name] = float(value)
            else:
                row[name] = json.dumps([float(x) for x in value])
        rows.append(row)
    return rows

def frozen_runtime_snapshot(root: Path) -> dict[str, Any]:
    return {
        "identity": FROZEN_CONFIG_NAME,
        "stage_a_acceptance_config": STAGE_A_PARENT,
        "tau_P12": TAU_P12, "tau_C12": TAU_C12,
        "boundary_consolidation_window": WINDOW,
        "P12_definition": "median(translation_speed_mps), relative frames [+4,+12]",
        "C12_definition": "min(straightness[-12,-1], straightness[0,+11])",
        "P12_incomplete": "FAIL_OPEN_KEEP",
        "C12_incomplete": "P12_ONLY_FALLBACK",
        "baseline_boundary_config": json.loads((root / "configs" / G1_P2_CONFIG_PATH.name).read_text(encoding="utf-8")),
    }

def freeze_integrity(root: Path) -> dict[str, Any]:
    rows = _read_csv(root / FROZEN_MANIFEST)
    ids = tuple(row["episode_id"] for row in rows)
    versions = {row["manifest_version"] for row in rows}
    historical, _ = load_historical_sets(root)
    overlaps = {name: sorted(set(ids) & values) for name, values in historical.items()}
    raw_hash, low_hash = sha256_file(DATASET_RAW_HDF5), sha256_file(DATASET_LOW_DIM_HDF5)
    checks = {
        "manifest_version_exact": versions == {MANIFEST_VERSION},
        "episode_ids_exact_order": ids == EXPECTED_EPISODES,
        "episode_count_exact": len(ids) == 24 and len(set(ids)) == 24,
        "dataset_raw_identity": raw_hash == EXPECTED_RAW_SHA256,
        "dataset_low_dim_identity": low_hash == EXPECTED_LOW_SHA256,
        "overlap_exploratory": len(overlaps["exploratory"]),
        "overlap_calibration": len(overlaps["calibration_combined"]),
        "overlap_diagnostic": len(overlaps["design_diagnostic"]),
    }
    passed = all(v is True or v == 0 for v in checks.values())
    return {
        "status": "PASS" if passed else "FAIL", "checks": checks, "overlaps": overlaps,
        "manifest_sha256": sha256_file(root / FROZEN_MANIFEST),
        "manifest_doc_sha256": sha256_file(root / FROZEN_MANIFEST_DOC),
        "frozen_config_doc_sha256": sha256_file(root / FROZEN_CONFIG_DOC),
        "raw_hdf5_sha256": raw_hash, "low_dim_hdf5_sha256": low_hash,
        "episode_ids": list(ids),
    }

def _lineage_rows(result: EngineResult) -> list[dict[str, Any]]:
    return [{
        "episode_id": e.episode_id, "final_boundary_id": e.boundary_id, "final_frame": e.frame,
        "representative_candidate_id": e.representative_candidate_id,
        "member_candidate_ids": "|".join(e.member_candidate_ids),
        "member_candidate_types": "|".join(e.member_candidate_types),
        "member_candidate_frames": "|".join(map(str, e.member_candidate_frames)),
        "member_candidate_count": e.member_candidate_count,
    } for e in result.final_events]

def build_formal_evaluation_run(*, project_root: str | Path, runs_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(project_root).resolve()
    integrity = freeze_integrity(root)
    if integrity["status"] != "PASS":
        raise FormalEvaluationRunError("STOP_EVALUATION_FREEZE_INTEGRITY_FAILURE: " + json.dumps(integrity))
    snapshot = frozen_runtime_snapshot(root)
    config_hash = config_hash_from_payload(snapshot)
    p1_config = load_g1_p1_config(root / "configs" / CONFIG_PATH.name)
    p2_config = load_g1_p2_config(root / "configs" / G1_P2_CONFIG_PATH.name)
    if p2_config.boundary_consolidation_window != WINDOW:
        raise FormalEvaluationRunError("Frozen parent consolidation window is not 8")
    signal_hash = signal_contract_hash_from_path(root / "configs" / CONFIG_PATH.name)
    created_at = now_iso()
    run_id = allocate_run_id(run_stage="EVALUATION", config_hash=config_hash, created_at=created_at, salt=integrity["manifest_sha256"])
    output_parent = Path(runs_root or root / "outputs/g1_p4_evaluation_runs").resolve()
    final_root = output_parent / run_id
    if final_root.exists(): raise FormalEvaluationRunError(f"immutable run exists: {final_root}")
    output_parent.mkdir(parents=True, exist_ok=True)

    adapter = build_can_mh_adapter(p1_config)
    catalog = {item.source_episode_id: item for item in enumerate_episodes(adapter)}
    if set(EXPECTED_EPISODES) - set(catalog):
        raise FormalEvaluationRunError("Frozen episodes missing from dataset")
    signals: dict[str, FormalSignals] = {}
    episodes = {}
    try:
        for episode_id in EXPECTED_EPISODES:
            episode = load_formal_episode(adapter, episode_id)
            episodes[episode_id] = episode
            signals[episode_id] = compute_formal_signals(episode, p1_config)
    finally:
        close = getattr(adapter, "close", None)
        if close: close()
    results, acceptance_trace = run_window(signals, WINDOW)
    result_map = {r.episode_id: r for r in results}
    if set(result_map) != set(EXPECTED_EPISODES):
        raise FormalEvaluationRunError("ALL_24_ATTEMPTED gate failed")
    edge_trace = build_edge_trace(results, acceptance_trace)

    manifest_rows = []; all_candidates = []; all_finals = []; all_segments = []; lineage = []
    video_expected: dict[str, tuple[Path, int]] = {}
    with tempfile.TemporaryDirectory(prefix=f".{run_id}.staging-", dir=output_parent) as temp_name:
        staging = Path(temp_name)
        (staging / "config_snapshot.json").write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        shutil.copyfile(root / CODEBOOK_SOURCE, staging / "human_boundary_review_codebook.json")
        shutil.copyfile(root / FROZEN_MANIFEST, staging / "frozen_manifest_snapshot.csv")
        (staging / "frozen_config_snapshot.json").write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (staging / "freeze_integrity_check.json").write_text(json.dumps(integrity, indent=2) + "\n", encoding="utf-8")
        dataset_identity = {"dataset_id": DATASET_ID, "raw_hdf5_sha256": integrity["raw_hdf5_sha256"], "low_dim_hdf5_sha256": integrity["low_dim_hdf5_sha256"]}
        (staging / "dataset_identity.json").write_text(json.dumps(dataset_identity, indent=2) + "\n", encoding="utf-8")
        disjoint = {"status": "PASS", "overlap_exploratory": 0, "overlap_calibration": 0, "overlap_diagnostic": 0}
        (staging / "disjointness_recheck.json").write_text(json.dumps(disjoint, indent=2) + "\n", encoding="utf-8")

        for episode_id in EXPECTED_EPISODES:
            identity, sig, result = catalog[episode_id], signals[episode_id], result_map[episode_id]
            native = identity.native_episode_key; diagnostic = staging / "diagnostic" / native
            tables = write_episode_audit_tables(diagnostic, result)
            formal_rows = _formal_signal_rows(sig)
            _write_csv(diagnostic / "formal_signals.csv", tuple(formal_rows[0]), formal_rows)
            plot_episode_signals(sig, diagnostic / "signal_plot.png", privileged=None, candidate_boundaries=None, suppressed_boundaries=None, final_boundaries=None, title=f"G1 Formal Signals | EVALUATION | {episode_id}")
            plot_episode_signals(sig, diagnostic / "signal_boundary_plot.png", privileged=None, candidate_boundaries=result.candidate_frames, suppressed_boundaries=result.suppressed_frames, final_boundaries=result.final_frames, final_boundary_annotations=result.final_annotations, motion_state_evidence=result.motion_state, title=f"G1 Final Config FROZEN_v1 | EVALUATION | {episode_id}")
            video_path = staging / "media" / native / "video.mp4"
            video_expected[episode_id] = (video_path, int(identity.num_steps))
            alignment = audit_temporal_alignment(episodes[episode_id], sig, rgb_frame_count=None)
            nan_inf = audit_nan_inf(sig)
            if alignment.status != "PASS" or nan_inf["status"] != "PASS":
                raise FormalEvaluationRunError(f"{episode_id}: signal integrity failed")
            decisions = Counter(d.decision for d in result.decisions.values())
            suppressed = sum(decisions[x] for x in ("SUPPRESS_DEBOUNCE", "SUPPRESS_SHORT_PAUSE", "MERGE_CONSOLIDATION", "MERGE_LEFT", "MERGE_RIGHT"))
            rel = lambda p: Path(p).relative_to(staging).as_posix()
            manifest_rows.append({
                "run_id": run_id, "episode_id": episode_id, "native_episode_key": native, "demo_key": native,
                "source_hdf5": DATASET_RAW_HDF5.name, "source_dataset_id": DATASET_ID, "set_role": "EVALUATION",
                "config_hash": config_hash, "signal_contract_version": SIGNAL_CONTRACT_VERSION, "signal_contract_hash": signal_hash,
                "video_relpath": rel(video_path), "plot_relpath": rel(diagnostic / "signal_boundary_plot.png"), "signal_plot_relpath": rel(diagnostic / "signal_plot.png"),
                "candidates_relpath": rel(Path(tables["candidate_boundaries"])), "boundaries_relpath": rel(Path(tables["final_boundaries"])),
                "segments_relpath": rel(Path(tables["segment_manifest"])), "smoke_relpath": rel(Path(tables["boundary_decisions"])),
                "quality_group": "EVALUATION_BLIND", "review_required": bool(result.review_required), "length": identity.num_steps,
                "candidate_count": len(result.candidates), "suppressed_count": suppressed, "final_boundary_count": len(result.final_events),
                "segment_count": len(result.segments), "short_segment_count": sum(bool(s.short_segment_flag) for s in result.segments),
                "long_segment_count": sum(bool(s.long_segment_flag) for s in result.segments), "cluster_count": len(result.final_events),
                "deactivated_candidate_count": suppressed, "keep_count": decisions["KEEP"], "merge_count": decisions["MERGE_CONSOLIDATION"],
                "retain_hard_count": decisions["RETAIN_HARD"], "alignment": alignment.status, "nan_inf": nan_inf["status"],
            })
            all_candidates += [c.to_row() for c in result.candidates]
            all_finals += [e.to_row() for e in result.final_events]
            all_segments += [s.to_row() for s in result.segments]
            lineage += _lineage_rows(result)

        with ProcessPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(_render_worker, str(root), ep, str(path), float(p1_config.control_frequency_hz)): ep for ep, (path, _) in video_expected.items()}
            for future in as_completed(futures):
                ep = futures[future]; info = future.result(); path, expected = video_expected[ep]
                if int(info["written_frames"]) != expected or count_video_frames(path) != expected:
                    raise FormalEvaluationRunError(f"{ep}: video frame mismatch")

        _write_csv(staging / "episode_manifest.csv", MANIFEST_FIELDS, manifest_rows)
        for name, rows in (("candidate_boundaries.csv", all_candidates), ("final_boundaries.csv", all_finals), ("segment_manifest.csv", all_segments), ("consolidation_lineage.csv", lineage), ("candidate_acceptance_trace.csv", acceptance_trace), ("edge_context_trace.csv", edge_trace)):
            fields = tuple(rows[0]) if rows else ("episode_id",)
            _write_csv(staging / name, fields, rows)
        diagnostics = {
            "predicted_final_boundary_count": len(all_finals), "segment_count": len(all_segments),
            "candidate_count": len(all_candidates), "candidate_type_distribution": dict(Counter(r["candidate_type"] for r in all_candidates)),
            "acceptance_reason_distribution": dict(Counter(r["acceptance_reason"] for r in acceptance_trace)),
            "P12_context_incomplete_count": sum(not bool(r["P12_context_complete"]) for r in acceptance_trace),
            "C12_context_incomplete_count": sum(bool(r["P12_context_complete"]) and not bool(r["C12_context_complete"]) for r in acceptance_trace),
            "quality_claim": "NONE; prediction-side runtime diagnostics only",
        }
        (staging / "prediction_diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
        progress = {"run_id": run_id, "status": "NOT_STARTED", "episode_count": 24, "episodes_reviewed": 0, "human_audit_started": False, "human_audit_complete": False}
        (staging / "human_review_progress.json").write_text(json.dumps(progress, indent=2) + "\n", encoding="utf-8")
        run_meta = {
            "contract_version": CONTRACT_VERSION, "run_id": run_id, "run_stage": "EVALUATION", "created_at": created_at,
            "parent_run_id": None, "config_version": FROZEN_CONFIG_NAME, "config_hash": config_hash,
            "segmentation_version": "G1-FINAL-FROZEN-v1", "signal_contract_version": SIGNAL_CONTRACT_VERSION,
            "signal_contract_hash": signal_hash, "source_dataset_id": DATASET_ID, "episode_count": 24,
            "codebook_path": "human_boundary_review_codebook.json", "manifest_path": "episode_manifest.csv", "config_snapshot_path": "config_snapshot.json",
            "final_boundary_semantics": "MATERIALIZED_V1", "schema_materialization": "FINAL_BOUNDARY_MEMBER_SEMANTICS_V1",
            "set_role": "EVALUATION", "evaluation_manifest_version": MANIFEST_VERSION, "frozen_config_identity": FROZEN_CONFIG_NAME,
            "must_not_feed_back_to_calibration": True, "human_review_status": "NOT_STARTED", "search_gate": "CLOSED",
            "parameter_search_executed": False, "formal_evaluation_scoring_executed": False, "evaluation_gt_created": False,
            "iteration_note": "EVALUATION · G1_P4_EVAL_MANIFEST_v1 · G1 Final Config FROZEN_v1 · MUST NOT FEED BACK TO CALIBRATION",
        }
        (staging / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        validated = validate_g1_audit_folder(staging)
        if [r["episode_id"] for r in validated["episodes"]] != list(EXPECTED_EPISODES):
            raise FormalEvaluationRunError("validated manifest order mismatch")
        staging.rename(final_root)

    registry = final_root / "evaluation_audit_registry.json"
    auto_register(registry, final_root, owner_note="Frozen G1-P4 Evaluation Human Audit; isolated review storage")
    sqlite_path = final_root / "evaluation_human_review.sqlite"
    ReviewStore(sqlite_path)
    return {"run_id": run_id, "run_root": str(final_root), "registry_path": str(registry), "sqlite_path": str(sqlite_path), "diagnostics": diagnostics, "freeze_integrity": integrity, "episode_count": 24}
