"""Discover or materialize the 12-Episode CALIBRATION Baseline Run.

Scientific identity is config_hash + signal_contract_hash + Combined 12-Episode
set.  This module does not score, match, or write Human Review.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable, Mapping

from project2_g1_audit_web.contract import CONTRACT_VERSION, validate_g1_audit_folder
from project2_g1_audit_web.hashes import (
    SIGNAL_CONTRACT_VERSION,
    allocate_run_id,
    config_hash_from_path,
    now_iso,
    signal_contract_hash_from_path,
)
from project2_g1_audit_web.registry import auto_register, load_registry

from .alignment import audit_nan_inf, audit_temporal_alignment
from .boundary_config import load_g1_p2_config
from .boundary_engine import run_boundary_engine
from .boundary_io import write_episode_audit_tables
from .config import load_g1_p1_config
from .fresh_calibration_run import (
    EXPECTED_CONFIG_HASH,
    EXPECTED_SIGNAL_HASH,
    MANIFEST_FIELDS,
    SOURCE_DATASET_ID,
    _decision_counts,
    _formal_summary,
    _read_csv,
    _render_video_worker,
    _write_csv,
)
from .paths import CONFIG_PATH, DATASET_RAW_HDF5, G1_P2_CONFIG_PATH
from .plot import plot_episode_signals
from .signals import compute_formal_signals
from .source import build_can_mh_adapter, enumerate_episodes, load_formal_episode
from .video import count_video_frames

PARENT_RUN_ID = "g1_exploratory_audit_20260917_141541_fe251439"
SEED_SOURCE_RUN_ID = "g1_exploratory_audit_20260917_141541_fe251439"
FRESH_SOURCE_RUN_ID = "g1_calibration_20260918_094455_df2ce8b2"
CANONICAL_GT_SNAPSHOT_ID = "g1_canonical_gt_20260918_131636_c9916b89"
SEARCH_STAGE = "BASELINE"


class BaselineCalibrationRunError(ValueError):
    pass


def load_combined_manifest(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    episode_ids = [str(item) for item in payload.get("episode_ids") or []]
    seed_ids = [str(item) for item in payload.get("seed_episode_ids") or []]
    fresh_ids = [str(item) for item in payload.get("fresh_episode_ids") or []]
    if payload.get("canonical_gt_snapshot_id") != CANONICAL_GT_SNAPSHOT_ID:
        raise BaselineCalibrationRunError("combined manifest snapshot_id mismatch")
    if len(episode_ids) != 12 or len(set(episode_ids)) != 12:
        raise BaselineCalibrationRunError(f"EPISODE_COUNT={len(set(episode_ids))} DUPLICATE={len(episode_ids) - len(set(episode_ids))}")
    if set(seed_ids) | set(fresh_ids) != set(episode_ids):
        raise BaselineCalibrationRunError("combined episode set is not Seed 6 + Fresh 6")
    if set(seed_ids) & set(fresh_ids):
        raise BaselineCalibrationRunError("Seed/Fresh overlap in combined manifest")
    if len(seed_ids) != 6 or len(fresh_ids) != 6:
        raise BaselineCalibrationRunError("Seed/Fresh counts are not 6/6")
    return payload


def identity_errors(
    meta: Mapping[str, Any],
    episode_ids: Iterable[str],
    set_roles: Iterable[str],
    *,
    expected_episodes: set[str],
    expected_config_hash: str,
    expected_signal_hash: str,
) -> list[str]:
    errors: list[str] = []
    actual = {str(item) for item in episode_ids}
    roles = {str(item) for item in set_roles}
    if str(meta.get("run_stage") or "") != "CALIBRATION":
        errors.append(f"run_stage={meta.get('run_stage')}")
    if roles != {"CALIBRATION"}:
        errors.append(f"set_role={sorted(roles)}")
    if int(meta.get("episode_count") or -1) != 12 or len(actual) != 12:
        errors.append(f"episode_count={meta.get('episode_count')} unique={len(actual)}")
    if str(meta.get("search_stage") or "") != SEARCH_STAGE:
        errors.append(f"search_stage={meta.get('search_stage')}")
    if str(meta.get("config_hash") or "") != expected_config_hash:
        errors.append("wrong config_hash")
    if str(meta.get("signal_contract_hash") or "") != expected_signal_hash:
        errors.append("wrong signal_contract_hash")
    if actual != expected_episodes:
        missing = sorted(expected_episodes - actual)
        extra = sorted(actual - expected_episodes)
        errors.append(f"episode exact-set failed missing={missing} extra={extra}")
    if str(meta.get("final_boundary_semantics") or "") != "MATERIALIZED_V1":
        errors.append(f"final_boundary_semantics={meta.get('final_boundary_semantics')}")
    if str(meta.get("calibration_config_role") or "") != "BASELINE_UNMODIFIED":
        errors.append(f"calibration_config_role={meta.get('calibration_config_role')}")
    if meta.get("parameter_search_executed") is not False:
        errors.append("parameter_search_executed is not false")
    try:
        diff_count = int(meta["parameter_diff_count"])
    except (KeyError, TypeError, ValueError):
        errors.append(f"parameter_diff_count={meta.get('parameter_diff_count')}")
    else:
        if diff_count != 0:
            errors.append(f"parameter_diff_count={diff_count}")
    return errors


def _safe_is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def iter_candidate_run_dirs(runs_root: str | Path, registry_path: str | Path) -> list[Path]:
    root = Path(runs_root)
    ordered: list[Path] = []
    seen: set[str] = set()
    try:
        payload = load_registry(registry_path)
    except Exception:
        payload = {"runs": {}}
    for run_id, record in (payload.get("runs") or {}).items():
        path = Path(str(record.get("audit_folder_path") or ""))
        seen.add(str(run_id))
        if _safe_is_dir(path):
            ordered.append(path)
    try:
        names = os.listdir(root)
    except OSError:
        names = []
    for name in sorted(names):
        if name in seen or name.startswith("."):
            continue
        path = root / name
        if _safe_is_dir(path):
            ordered.append(path)
    return ordered


def assess_run(run_root: str | Path, *, expected_episodes: set[str], expected_config_hash: str, expected_signal_hash: str) -> dict[str, Any]:
    root = Path(run_root)
    try:
        meta = json.loads((root / "run_meta.json").read_text(encoding="utf-8"))
        rows = _read_csv(root / str(meta.get("manifest_path") or "episode_manifest.csv"))
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        return {"qualifies": False, "run_root": str(root), "run_id": root.name, "reasons": [f"unreadable: {exc}"]}
    errors = identity_errors(
        meta,
        [row["episode_id"] for row in rows],
        [row.get("set_role") or "" for row in rows],
        expected_episodes=expected_episodes,
        expected_config_hash=expected_config_hash,
        expected_signal_hash=expected_signal_hash,
    )
    if errors:
        return {
            "qualifies": False,
            "run_id": str(meta.get("run_id") or root.name),
            "run_root": str(root),
            "run_stage": meta.get("run_stage"),
            "episode_count": meta.get("episode_count"),
            "search_stage": meta.get("search_stage"),
            "reasons": errors,
        }
    try:
        validated = validate_g1_audit_folder(root)
        validator = "PASS"
    except Exception as exc:
        return {
            "qualifies": False,
            "run_id": str(meta.get("run_id") or root.name),
            "run_root": str(root),
            "reasons": [f"validator={exc}"],
        }
    return {
        "qualifies": True,
        "run_id": str(meta["run_id"]),
        "run_root": str(root),
        "run_meta": meta,
        "episode_ids": [row["episode_id"] for row in validated["episodes"]],
        "validator": validator,
        "reasons": [],
    }


def discover_existing_baseline_run(
    *,
    runs_root: str | Path,
    registry_path: str | Path,
    combined_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    expected_episodes = {str(item) for item in combined_manifest["episode_ids"]}
    expected_config = str(combined_manifest.get("config_baseline_hash") or EXPECTED_CONFIG_HASH)
    expected_signal = str(combined_manifest.get("signal_contract_hash") or EXPECTED_SIGNAL_HASH)
    audits = []
    found = []
    for path in iter_candidate_run_dirs(runs_root, registry_path):
        result = assess_run(
            path,
            expected_episodes=expected_episodes,
            expected_config_hash=expected_config,
            expected_signal_hash=expected_signal,
        )
        audits.append({key: result[key] for key in ("run_id", "run_root", "qualifies", "reasons") if key in result} | {
            "episode_count": result.get("episode_count"),
            "run_stage": result.get("run_stage"),
            "search_stage": result.get("search_stage"),
        })
        if result.get("qualifies"):
            found.append(result)
    if len(found) > 1:
        raise BaselineCalibrationRunError(
            "multiple qualifying 12-Episode baseline runs; refusing to guess: "
            + ", ".join(item["run_id"] for item in found)
        )
    if found:
        return {"status": "FOUND", "run": found[0], "audits": audits}
    return {"status": "NOT_FOUND", "run": None, "audits": audits}


def _prediction_signature(run_root: Path, episode_id: str) -> dict[str, Any]:
    meta = json.loads((run_root / "run_meta.json").read_text(encoding="utf-8"))
    rows = [row for row in _read_csv(run_root / str(meta.get("manifest_path") or "episode_manifest.csv")) if row["episode_id"] == episode_id]
    if len(rows) != 1:
        raise BaselineCalibrationRunError(f"{run_root.name}/{episode_id}: manifest row count {len(rows)}")
    row = rows[0]
    native = row["native_episode_key"]
    finals = _read_csv(run_root / "diagnostic" / native / "final_boundaries.csv")
    candidates = _read_csv(run_root / "diagnostic" / native / "candidate_boundaries.csv")
    segments = _read_csv(run_root / "diagnostic" / native / "segment_manifest.csv")
    return {
        "episode_length": int(row["length"]),
        "candidate_count": len(candidates),
        "final_count": len(finals),
        "finals": [
            (
                str(item.get("frame") or ""),
                str(item.get("candidate_type") or ""),
                str(item.get("member_candidate_types") or ""),
                str(item.get("member_candidate_frames") or ""),
            )
            for item in finals
        ],
        "segments": [
            (str(item.get("start_frame") or ""), str(item.get("end_frame") or ""))
            for item in segments
        ],
    }


def compare_prediction_episodes(new_root: str | Path, source_root: str | Path, episode_ids: Iterable[str]) -> dict[str, Any]:
    differences: list[dict[str, Any]] = []
    for episode_id in episode_ids:
        left = _prediction_signature(Path(new_root), episode_id)
        right = _prediction_signature(Path(source_root), episode_id)
        for field in ("episode_length", "candidate_count", "final_count", "finals", "segments"):
            if left[field] != right[field]:
                differences.append({
                    "episode_id": episode_id,
                    "field": field,
                    "new": left[field],
                    "source": right[field],
                })
    return {"status": "PASS" if not differences else "FAIL", "differences": differences}


def build_12ep_baseline_calibration_run(
    *,
    project_root: str | Path,
    combined_manifest_path: str | Path,
    registry_path: str | Path,
    runs_root: str | Path,
    parent_run_id: str = PARENT_RUN_ID,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    combined = load_combined_manifest(combined_manifest_path)
    episode_ids = sorted(str(item) for item in combined["episode_ids"])
    seed_ids = [str(item) for item in combined["seed_episode_ids"]]
    fresh_ids = [str(item) for item in combined["fresh_episode_ids"]]

    p1_config = load_g1_p1_config(root / "configs" / CONFIG_PATH.name)
    p2_config = load_g1_p2_config(root / "configs" / G1_P2_CONFIG_PATH.name)
    config_path = root / "configs" / G1_P2_CONFIG_PATH.name
    signal_path = root / "configs" / CONFIG_PATH.name
    config_hash = config_hash_from_path(config_path)
    signal_hash = signal_contract_hash_from_path(signal_path)
    if config_hash != EXPECTED_CONFIG_HASH or config_hash != combined.get("config_baseline_hash"):
        raise BaselineCalibrationRunError("baseline config hash mismatch")
    if signal_hash != EXPECTED_SIGNAL_HASH or signal_hash != combined.get("signal_contract_hash"):
        raise BaselineCalibrationRunError("signal contract hash mismatch")
    if p2_config.config_version != "g1_p2_exploratory_segmentation.v0":
        raise BaselineCalibrationRunError("config_version changed")
    if p2_config.segmentation_version != "G1-P2-EXPLORATORY-v0":
        raise BaselineCalibrationRunError("segmentation_version changed")

    created_at = now_iso()
    run_id = allocate_run_id(
        run_stage="CALIBRATION", config_hash=config_hash, created_at=created_at,
        salt=str(combined["canonical_gt_snapshot_id"]),
    )
    final_root = Path(runs_root).resolve() / run_id
    if final_root.exists():
        raise BaselineCalibrationRunError(f"immutable run already exists: {final_root}")
    Path(runs_root).mkdir(parents=True, exist_ok=True)

    adapter = build_can_mh_adapter(p1_config)
    catalog = {item.source_episode_id: item for item in enumerate_episodes(adapter)}
    missing = sorted(set(episode_ids) - set(catalog))
    extra_check = []
    if missing:
        raise BaselineCalibrationRunError(f"MISSING={missing}")
    if extra_check:
        raise BaselineCalibrationRunError(f"EXTRA={extra_check}")

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
                title=f"12-Episode Calibration Baseline | {episode_id} | T={signals.n_frames}",
            )
            video_path = staging / "media" / native / "video.mp4"
            video_expected[episode_id] = (video_path, int(identity.num_steps))
            alignment = audit_temporal_alignment(episode, signals, rgb_frame_count=None)
            nan_inf = audit_nan_inf(signals)
            if alignment.status != "PASS" or nan_inf["status"] != "PASS":
                raise BaselineCalibrationRunError(
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
                    raise BaselineCalibrationRunError(
                        f"{episode_id}: video frames={observed} expected={expected_frames}"
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
            "episode_count": 12, "codebook_path": "human_boundary_review_codebook.json",
            "manifest_path": "episode_manifest.csv", "config_snapshot_path": "config_snapshot.json",
            "final_boundary_semantics": "MATERIALIZED_V1",
            "schema_materialization": "FINAL_BOUNDARY_MEMBER_SEMANTICS_V1",
            "search_stage": SEARCH_STAGE,
            "calibration_manifest_id": str(combined["canonical_gt_snapshot_id"]),
            "calibration_config_role": "BASELINE_UNMODIFIED",
            "parameter_search_executed": False, "parameter_diff_count": 0,
            "search_gate": "OPEN_FOR_BASELINE_SCORING",
            "human_review_status": "NOT_REQUIRED",
            "canonical_gt_snapshot_id": str(combined["canonical_gt_snapshot_id"]),
            "iteration_note": (
                "12-Episode Calibration Baseline · search_stage=BASELINE · "
                "Canonical GT already frozen · no Human Review rebind"
            ),
        }
        (staging / "run_meta.json").write_text(
            json.dumps(run_meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        validated = validate_g1_audit_folder(staging)
        if {row["episode_id"] for row in validated["episodes"]} != set(episode_ids):
            raise BaselineCalibrationRunError("validated run is not an exact combined episode set")
        staging.rename(final_root)

    seed_cmp = compare_prediction_episodes(final_root, root / "outputs" / "g1_audit_runs" / SEED_SOURCE_RUN_ID, seed_ids)
    fresh_cmp = compare_prediction_episodes(final_root, root / "outputs" / "g1_audit_runs" / FRESH_SOURCE_RUN_ID, fresh_ids)
    if seed_cmp["status"] != "PASS" or fresh_cmp["status"] != "PASS":
        raise BaselineCalibrationRunError(
            "REPORT_PIPELINE_DRIFT: " + json.dumps({"seed": seed_cmp, "fresh": fresh_cmp}, default=str)
        )

    record = auto_register(
        registry_path, final_root,
        owner_note="12-Episode Calibration Baseline; unmodified exploratory config; Canonical GT frozen; scoring not executed",
    )
    return {
        "existing_baseline_run": "NOT_FOUND_THEN_CREATED",
        "run_id": run_id, "run_root": str(final_root), "parent_run_id": parent_run_id,
        "episode_ids": episode_ids, "seed_episode_ids": seed_ids, "fresh_episode_ids": fresh_ids,
        "config_hash": config_hash, "signal_contract_hash": signal_hash,
        "parameter_diff_count": 0, "search_stage": SEARCH_STAGE,
        "validator": "PASS", "registry_status": record.status,
        "seed_consistency": seed_cmp, "fresh_consistency": fresh_cmp,
        "formal_summaries": formal_summaries,
    }


def ensure_12ep_baseline_run(**kwargs: Any) -> dict[str, Any]:
    combined = load_combined_manifest(kwargs["combined_manifest_path"])
    discovered = discover_existing_baseline_run(
        runs_root=kwargs["runs_root"],
        registry_path=kwargs["registry_path"],
        combined_manifest=combined,
    )
    if discovered["status"] == "FOUND":
        run = discovered["run"]
        return {
            "existing_baseline_run": "FOUND",
            "run_id": run["run_id"],
            "run_root": run["run_root"],
            "run_meta": run["run_meta"],
            "validator": run["validator"],
            "audits": discovered["audits"],
            "materialized": False,
        }
    created = build_12ep_baseline_calibration_run(**kwargs)
    created["audits"] = discovered["audits"]
    created["materialized"] = True
    return created
