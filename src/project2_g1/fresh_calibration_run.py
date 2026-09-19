"""Build one immutable Fresh Calibration baseline Human Audit Run.

This module intentionally has no calibration search surface.  It consumes the
frozen Fresh manifest, the existing P1 signal config, and the one baseline P2
config, then materializes a normal P2_G1_AUDIT_FOLDER_V1 run.
"""

from __future__ import annotations

import csv
import json
import shutil
import tempfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Mapping

from project2_g1_audit_web.contract import CONTRACT_VERSION, validate_g1_audit_folder
from project2_g1_audit_web.hashes import (
    SIGNAL_CONTRACT_VERSION,
    allocate_run_id,
    config_hash_from_path,
    now_iso,
    signal_contract_hash_from_path,
)
from project2_g1_audit_web.registry import auto_register

from .alignment import audit_nan_inf, audit_temporal_alignment
from .boundary_config import load_g1_p2_config
from .boundary_engine import (
    CANDIDATE_DIRECTION,
    CANDIDATE_GRIPPER,
    run_boundary_engine,
)
from .boundary_io import write_episode_audit_tables
from .config import load_g1_p1_config
from .paths import (
    CONFIG_PATH,
    DATASET_RAW_HDF5,
    G1_P2_CONFIG_PATH,
)
from .plot import plot_episode_signals
from .signals import compute_formal_signals
from .source import build_can_mh_adapter, enumerate_episodes, load_formal_episode
from .video import count_video_frames, render_episode_audit_video


EXPECTED_MANIFEST_ID = "g1_fresh_calibration_manifest_2aa5cfe05295"
EXPECTED_CONFIG_HASH = "dde590e759a31cb8c865369e18256ebecbbd01bc94a58e1d3ca695bb50f2a630"
EXPECTED_SIGNAL_HASH = "24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d"
PARENT_RUN_ID = "g1_exploratory_audit_20260917_141541_fe251439"
SOURCE_DATASET_ID = "robomimic_v15_can_mh"

MANIFEST_FIELDS = (
    "run_id", "episode_id", "native_episode_key", "demo_key", "source_hdf5",
    "source_dataset_id", "set_role", "config_hash", "signal_contract_version",
    "signal_contract_hash", "video_relpath", "plot_relpath", "signal_plot_relpath",
    "candidates_relpath", "boundaries_relpath", "segments_relpath", "smoke_relpath",
    "quality_group", "review_required", "length", "candidate_count",
    "suppressed_count", "final_boundary_count", "segment_count",
    "short_segment_count", "long_segment_count", "cluster_count",
    "deactivated_candidate_count", "keep_count", "merge_count",
    "retain_hard_count", "alignment", "nan_inf",
)


class FreshCalibrationRunError(ValueError):
    pass


def _render_video_worker(
    project_root: str, episode_id: str, output_path: str, fps: float
) -> dict[str, Any]:
    """Isolated renderer process; avoids sharing MuJoCo/OpenGL contexts."""

    root = Path(project_root)
    config = load_g1_p1_config(root / "configs" / CONFIG_PATH.name)
    adapter = build_can_mh_adapter(config)
    return render_episode_audit_video(adapter, episode_id, output_path, fps=fps)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FreshCalibrationRunError(f"expected JSON object: {path}")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[Mapping[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _decision_counts(result: Any) -> Counter[str]:
    return Counter(item.decision for item in result.decisions.values())


def _formal_summary(result: Any, length: int) -> dict[str, int]:
    primary = Counter(event.candidate_type for event in result.final_events)
    return {
        "episode_length": int(length),
        "candidate_count": len(result.candidates),
        "final_boundary_count": len(result.final_events),
        "gripper_primary_count": primary[CANDIDATE_GRIPPER],
        "direction_primary_count": primary[CANDIDATE_DIRECTION],
        "merged_boundary_count": sum(event.member_candidate_count > 1 for event in result.final_events),
        "short_segment_count": sum(bool(item.short_segment_flag) for item in result.segments),
    }


def compare_screening(
    formal: Mapping[str, Mapping[str, int]], screening_csv: Path
) -> dict[str, Any]:
    screening = {row["episode_id"]: row for row in _read_csv(screening_csv)}
    mapping = {
        "episode_length": "episode_length_frames",
        "candidate_count": "baseline_candidate_count",
        "final_boundary_count": "baseline_final_boundary_count",
        "gripper_primary_count": "gripper_primary_count",
        "direction_primary_count": "direction_primary_count",
        "merged_boundary_count": "merged_boundary_count",
        "short_segment_count": "short_segment_count",
    }
    differences: list[dict[str, Any]] = []
    for episode_id, actual in formal.items():
        old = screening.get(episode_id)
        if old is None:
            differences.append({"episode_id": episode_id, "field": "row", "screening": "MISSING", "formal": "PRESENT"})
            continue
        for current_key, old_key in mapping.items():
            expected = int(float(old[old_key]))
            observed = int(actual[current_key])
            if expected != observed:
                differences.append({
                    "episode_id": episode_id, "field": current_key,
                    "screening": expected, "formal": observed,
                })
    return {"status": "PASS" if not differences else "FAIL", "differences": differences}


def build_fresh_calibration_run(
    *,
    project_root: str | Path,
    manifest_path: str | Path,
    screening_csv: str | Path,
    registry_path: str | Path,
    runs_root: str | Path,
    parent_run_id: str = PARENT_RUN_ID,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    frozen = _load_json(Path(manifest_path))
    if frozen.get("manifest_id") != EXPECTED_MANIFEST_ID:
        raise FreshCalibrationRunError("Fresh manifest identity mismatch")
    episode_ids = [str(item) for item in frozen.get("fresh_episode_ids", [])]
    if len(episode_ids) != 6 or len(set(episode_ids)) != 6:
        raise FreshCalibrationRunError("Fresh manifest must contain exactly six unique episodes")
    seed_ids = {str(item) for item in frozen.get("existing_seed_episode_ids", [])}
    if set(episode_ids) & seed_ids:
        raise FreshCalibrationRunError("Fresh manifest overlaps Seed episodes")
    if frozen.get("parameter_search_allowed") is not False:
        raise FreshCalibrationRunError("Fresh manifest does not keep parameter search closed")

    p1_config = load_g1_p1_config(root / "configs" / CONFIG_PATH.name)
    p2_config = load_g1_p2_config(root / "configs" / G1_P2_CONFIG_PATH.name)
    config_path = root / "configs" / G1_P2_CONFIG_PATH.name
    signal_path = root / "configs" / CONFIG_PATH.name
    config_hash = config_hash_from_path(config_path)
    signal_hash = signal_contract_hash_from_path(signal_path)
    if config_hash != EXPECTED_CONFIG_HASH or config_hash != frozen.get("screening_config_hash"):
        raise FreshCalibrationRunError("baseline config hash mismatch")
    if signal_hash != EXPECTED_SIGNAL_HASH or signal_hash != frozen.get("signal_contract_hash"):
        raise FreshCalibrationRunError("signal contract hash mismatch")

    created_at = now_iso()
    run_id = allocate_run_id(
        run_stage="CALIBRATION", config_hash=config_hash, created_at=created_at,
        salt=str(frozen["manifest_id"]),
    )
    final_root = Path(runs_root).resolve() / run_id
    if final_root.exists():
        raise FreshCalibrationRunError(f"immutable run already exists: {final_root}")
    Path(runs_root).mkdir(parents=True, exist_ok=True)

    adapter = build_can_mh_adapter(p1_config)
    catalog = {item.source_episode_id: item for item in enumerate_episodes(adapter)}
    missing = sorted(set(episode_ids) - set(catalog))
    if missing:
        raise FreshCalibrationRunError(f"Fresh manifest episodes missing from dataset: {missing}")

    formal_summaries: dict[str, dict[str, int]] = {}
    manifest_rows: list[dict[str, Any]] = []
    video_expected: dict[str, tuple[Path, int]] = {}
    with tempfile.TemporaryDirectory(prefix=f".{run_id}.staging-", dir=Path(runs_root)) as temp_name:
        staging = Path(temp_name)
        shutil.copyfile(config_path, staging / "config_snapshot.json")
        parent_codebook = root / "outputs" / "g1_audit_runs" / parent_run_id / "human_boundary_review_codebook.json"
        shutil.copyfile(parent_codebook, staging / "human_boundary_review_codebook.json")

        for episode_id in episode_ids:
            identity = catalog[episode_id]
            native = identity.native_episode_key
            episode = load_formal_episode(adapter, episode_id)
            signals = compute_formal_signals(episode, p1_config)
            result = run_boundary_engine(signals, p2_config)
            formal_summaries[episode_id] = _formal_summary(result, identity.num_steps)
            diagnostic = staging / "diagnostic" / native
            tables = write_episode_audit_tables(diagnostic, result)

            # Formal plots contain only Formal Signals and machine Detector output.
            plot_episode_signals(
                signals, diagnostic / "signal_plot.png", privileged=None,
                candidate_boundaries=None, suppressed_boundaries=None, final_boundaries=None,
                title=f"G1-P1 Formal Signals | {episode_id} | T={signals.n_frames}",
            )
            plot_episode_signals(
                signals, diagnostic / "signal_boundary_plot.png", privileged=None,
                candidate_boundaries=result.candidate_frames,
                suppressed_boundaries=result.suppressed_frames,
                final_boundaries=result.final_frames,
                final_boundary_annotations=result.final_annotations,
                motion_state_evidence=result.motion_state,
                title=f"Fresh Calibration Baseline Human Audit | {episode_id} | T={signals.n_frames}",
            )
            video_path = staging / "media" / native / "video.mp4"
            video_expected[episode_id] = (video_path, int(identity.num_steps))
            alignment = audit_temporal_alignment(episode, signals, rgb_frame_count=None)
            nan_inf = audit_nan_inf(signals)
            if alignment.status != "PASS" or nan_inf["status"] != "PASS":
                raise FreshCalibrationRunError(
                    f"{episode_id}: alignment={alignment.status} nan_inf={nan_inf['status']}"
                )
            decisions = _decision_counts(result)
            suppressed = sum(
                decisions[name] for name in (
                    "SUPPRESS_DEBOUNCE", "SUPPRESS_SHORT_PAUSE",
                    "MERGE_CONSOLIDATION", "MERGE_LEFT", "MERGE_RIGHT",
                )
            )
            weak = adapter.get_weak_reference(episode_id)
            rel = lambda value: Path(value).relative_to(staging).as_posix()
            manifest_rows.append({
                "run_id": run_id, "episode_id": episode_id,
                "native_episode_key": native, "demo_key": native,
                "source_hdf5": DATASET_RAW_HDF5.name,
                "source_dataset_id": SOURCE_DATASET_ID, "set_role": "CALIBRATION",
                "config_hash": config_hash,
                "signal_contract_version": SIGNAL_CONTRACT_VERSION,
                "signal_contract_hash": signal_hash,
                "video_relpath": rel(video_path),
                "plot_relpath": rel(diagnostic / "signal_boundary_plot.png"),
                "signal_plot_relpath": rel(diagnostic / "signal_plot.png"),
                "candidates_relpath": rel(Path(tables["candidate_boundaries"])),
                "boundaries_relpath": rel(Path(tables["final_boundaries"])),
                "segments_relpath": rel(Path(tables["segment_manifest"])),
                "smoke_relpath": rel(Path(tables["boundary_decisions"])),
                "quality_group": str(weak.get("quality_bucket") or "UNASSIGNED"),
                "review_required": bool(result.review_required),
                "length": identity.num_steps, "candidate_count": len(result.candidates),
                "suppressed_count": suppressed,
                "final_boundary_count": len(result.final_events),
                "segment_count": len(result.segments),
                "short_segment_count": sum(bool(item.short_segment_flag) for item in result.segments),
                "long_segment_count": sum(bool(item.long_segment_flag) for item in result.segments),
                "cluster_count": len(result.final_events),
                "deactivated_candidate_count": suppressed,
                "keep_count": decisions["KEEP"], "merge_count": decisions["MERGE_CONSOLIDATION"],
                "retain_hard_count": decisions["RETAIN_HARD"],
                "alignment": alignment.status, "nan_inf": nan_inf["status"],
            })

        # Rendering is deterministic per Episode and independent of Detector
        # computation. Separate processes keep MuJoCo/OpenGL contexts isolated.
        with ProcessPoolExecutor(max_workers=3) as pool:
            futures = {
                pool.submit(
                    _render_video_worker, str(root), episode_id, str(video_path),
                    float(p1_config.control_frequency_hz),
                ): episode_id
                for episode_id, (video_path, _) in video_expected.items()
            }
            for future in as_completed(futures):
                episode_id = futures[future]
                info = future.result()
                video_path, expected_frames = video_expected[episode_id]
                observed = count_video_frames(video_path)
                if int(info["written_frames"]) != expected_frames or observed != expected_frames:
                    raise FreshCalibrationRunError(
                        f"{episode_id}: video frames={observed} expected={expected_frames}"
                    )

        consistency = compare_screening(formal_summaries, Path(screening_csv))
        if consistency["status"] != "PASS":
            raise FreshCalibrationRunError(
                "SCREENING_FORMAL_RUN_CONSISTENCY_FAILED: " + json.dumps(consistency["differences"])
            )
        _write_csv(staging / "episode_manifest.csv", MANIFEST_FIELDS, manifest_rows)
        run_meta = {
            "contract_version": CONTRACT_VERSION, "run_id": run_id,
            "run_stage": "CALIBRATION", "created_at": created_at,
            "parent_run_id": parent_run_id,
            "config_version": p2_config.config_version, "config_hash": config_hash,
            "segmentation_version": p2_config.segmentation_version,
            "signal_contract_version": SIGNAL_CONTRACT_VERSION,
            "signal_contract_hash": signal_hash, "source_dataset_id": SOURCE_DATASET_ID,
            "episode_count": 6, "codebook_path": "human_boundary_review_codebook.json",
            "manifest_path": "episode_manifest.csv", "config_snapshot_path": "config_snapshot.json",
            "final_boundary_semantics": "MATERIALIZED_V1",
            "schema_materialization": "FINAL_BOUNDARY_MEMBER_SEMANTICS_V1",
            "calibration_role": "BASELINE_HUMAN_AUDIT",
            "calibration_manifest_id": frozen["manifest_id"],
            "calibration_config_role": "BASELINE_UNMODIFIED",
            "parameter_search_executed": False, "parameter_diff_count": 0,
            "search_gate": "CLOSED", "human_review_status": "NOT_STARTED",
            "iteration_note": "Fresh Calibration · Baseline Human Audit · Search Gate Closed",
        }
        (staging / "run_meta.json").write_text(
            json.dumps(run_meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        validated = validate_g1_audit_folder(staging)
        if {row["episode_id"] for row in validated["episodes"]} != set(episode_ids):
            raise FreshCalibrationRunError("validated run is not an exact manifest episode set")
        staging.rename(final_root)

    try:
        record = auto_register(
            registry_path, final_root,
            owner_note="Fresh Calibration baseline Human Audit; baseline unmodified; Search Gate closed",
        )
    except Exception:
        # The run remains immutable and valid but unregistered; caller must report BLOCKED.
        raise
    return {
        "run_id": run_id, "run_root": str(final_root), "parent_run_id": parent_run_id,
        "episode_ids": episode_ids, "formal_summaries": formal_summaries,
        "screening_consistency": consistency, "config_hash": config_hash,
        "signal_contract_hash": signal_hash, "parameter_diff_count": 0,
        "registry_status": record.status,
    }
