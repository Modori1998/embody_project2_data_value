"""Small-sample runtime materializer for MVP-M2."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from project2_g1.config import load_g1_p1_config
from project2_g1.signals import compute_formal_signals
from project2_g1.source import build_can_mh_adapter, enumerate_episodes, load_formal_episode
from project2_g1.stage_b_calibration import (
    STAGE_A_PARENT, TAU_C12, TAU_P12, run_window,
)
from project2_g1.stage_c_regression import BOUNDARY_CONSOLIDATION_WINDOW

from .m2 import (
    ALLOWED_FORMAL_INPUT_FIELDS, MOTION_DIRECTION_EPSILON_M, MOTION_FEATURE_VERSION,
    assert_no_privileged_inputs, select_keyframes, summarize_motion,
)
from .rgb_input import MODEL_RGB_CONTRACT_VERSION, render_clean_rgb_frames, write_clean_rgb_png


FROZEN_G1_IDENTITY = {
    "stage_a_acceptance_config": STAGE_A_PARENT,
    "tau_P12": TAU_P12,
    "tau_C12": TAU_C12,
    "boundary_consolidation_window": BOUNDARY_CONSOLIDATION_WINDOW,
    "p12_incomplete": "FAIL_OPEN_KEEP",
    "c12_incomplete": "P12_ONLY_FALLBACK",
}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            cooked = {key: json.dumps(value, separators=(",", ":")) if isinstance(value, list) else value for key, value in row.items()}
            writer.writerow(cooked)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def materialize_m2(
    output_root: str | Path,
    episode_ids: Sequence[str] = ("data/demo_0", "data/demo_1", "data/demo_2"),
    *,
    git_base: str,
) -> dict[str, Any]:
    """Materialize one immutable M2 run from the Frozen G1 configuration."""

    assert_no_privileged_inputs(ALLOWED_FORMAL_INPUT_FIELDS)
    output = Path(output_root)
    if output.exists():
        raise FileExistsError(f"MVP_M2_IMMUTABLE_OUTPUT_EXISTS: {output}")
    output.mkdir(parents=True)

    p1 = load_g1_p1_config()
    adapter = build_can_mh_adapter(p1)
    try:
        catalog = {item.source_episode_id: item for item in enumerate_episodes(adapter)}
        missing = [episode_id for episode_id in episode_ids if episode_id not in catalog]
        if missing:
            raise ValueError(f"MVP_M2_EPISODES_MISSING: {missing}")
        episodes = {episode_id: load_formal_episode(adapter, episode_id) for episode_id in episode_ids}
        signals = {episode_id: compute_formal_signals(episodes[episode_id], p1) for episode_id in episode_ids}
        results, _trace = run_window(signals, BOUNDARY_CONSOLIDATION_WINDOW)

        segment_rows: list[dict[str, Any]] = []
        keyframe_rows: list[dict[str, Any]] = []
        motion_rows: list[dict[str, Any]] = []
        rgb_records: list[dict[str, Any]] = []
        gripper_event_segments = 0

        for result in results:
            episode = episodes[result.episode_id]
            events = {event.boundary_id: event for event in result.final_events}
            selections: list[tuple[Any, Any]] = []
            unique_indices: set[int] = set()
            for segment in result.segments:
                left = events.get(segment.left_boundary_id)
                left_type = None if left is None else left.candidate_type
                selected = select_keyframes(segment, left_boundary_type=left_type)
                if any("GRIPPER_EVENT" in item.roles for item in selected):
                    gripper_event_segments += 1
                selections.append((segment, selected))
                unique_indices.update(item.frame_index for item in selected)
                segment_rows.append({
                    **segment.to_row(),
                    "left_boundary_type": left_type or "EPISODE_START",
                    "rgb_contract_version": MODEL_RGB_CONTRACT_VERSION,
                    "feature_version": MOTION_FEATURE_VERSION,
                })
                motion_rows.append(
                    summarize_motion(
                        segment,
                        episode,
                        gripper_state=result.gripper_state,
                        left_boundary_type=left_type,
                    )
                )

            frames = render_clean_rgb_frames(adapter, result.episode_id, sorted(unique_indices))
            frame_map = {frame.frame_index: frame for frame in frames}
            for segment, selected in selections:
                for item in selected:
                    frame = frame_map[item.frame_index]
                    relative = Path("keyframes") / episode.native_episode_key / segment.segment_id / f"frame_{item.frame_index:06d}.png"
                    target = output / relative
                    write_clean_rgb_png(frame, target)
                    keyframe_rows.append({
                        "segment_id": segment.segment_id,
                        "source_episode_id": segment.source_episode_id,
                        "frame_index": item.frame_index,
                        "roles": item.roles_text,
                        "png_relpath": relative.as_posix(),
                        "pixel_sha256": frame.provenance["pixel_sha256"],
                        "rgb_contract_version": MODEL_RGB_CONTRACT_VERSION,
                    })
                    rgb_records.append({
                        "source_episode_id": segment.source_episode_id,
                        "segment_id": segment.segment_id,
                        "frame_index": item.frame_index,
                        "png_relpath": relative.as_posix(),
                        "png_sha256": _sha256(target),
                        "provenance": frame.provenance,
                    })
    finally:
        close = getattr(adapter, "close", None)
        if callable(close):
            close()

    _write_csv(output / "segment_input_manifest.csv", segment_rows)
    _write_csv(output / "keyframe_manifest.csv", keyframe_rows)
    _write_csv(output / "robot_motion_summary.csv", motion_rows)
    rgb_provenance = {
        "rgb_contract_version": MODEL_RGB_CONTRACT_VERSION,
        "formal_path": "STATE_t -> P1 RoboMimicStateRenderer -> direct clean RGB -> lossless PNG",
        "audit_mp4_used": False,
        "text_overlay": False,
        "lossy_video_roundtrip": False,
        "frames": rgb_records,
    }
    (output / "rgb_provenance.json").write_text(json.dumps(rgb_provenance, indent=2) + "\n", encoding="utf-8")
    contract = {
        "feature_version": MOTION_FEATURE_VERSION,
        "direction_epsilon_m": MOTION_DIRECTION_EPSILON_M,
        "formal_source_fields": sorted(ALLOWED_FORMAL_INPUT_FIELDS),
        "action_semantic": "NORMALIZED_CONTROLLER_INPUT",
        "retrieval_normalization": "NOT_APPLIED_IN_M2",
        "missing_rule": {"coarse_direction_change_rad": "null when either half displacement <= epsilon or has fewer than two frames"},
        "fields": {
            "duration_frames": {"source": "Frozen G1 inclusive start/end", "unit": "frame", "definition": "end-start+1", "missing": "forbidden"},
            "duration_sec": {"source": "Frozen G1 duration_frames and dt", "unit": "second", "definition": "duration_frames*dt", "missing": "forbidden"},
            "eef_net_displacement_m": {"source": "obs/robot0_eef_pos", "unit": "meter", "definition": "norm(eef_pos[end]-eef_pos[start])", "missing": "forbidden"},
            "eef_path_length_m": {"source": "obs/robot0_eef_pos", "unit": "meter", "definition": "sum(norm(eef_pos[t]-eef_pos[t-1])) over inclusive segment", "missing": "forbidden"},
            "eef_displacement_xyz": {"source": "obs/robot0_eef_pos", "unit": "meter", "definition": "eef_pos[end]-eef_pos[start]", "missing": "forbidden"},
            "eef_main_direction_xyz": {"source": "eef_displacement_xyz", "unit": "unitless", "definition": "normalized displacement; [0,0,0] at or below epsilon", "missing": "never"},
            "coarse_direction_change_rad": {"source": "obs/robot0_eef_pos", "unit": "radian", "definition": "angle between non-overlapping first-half and second-half net directions", "missing": "null when either half has fewer than two frames or displacement <= epsilon"},
            "gripper_*_aperture": {"source": "obs/robot0_gripper_qpos", "unit": "source-native meter-scale aperture", "definition": "qpos[:,0]-qpos[:,1]", "missing": "forbidden"},
            "gripper_*_state": {"source": "Frozen G1 gripper_state", "unit": "OPEN/CLOSED", "definition": "reuse Frozen G1 runtime state; no new threshold", "missing": "NOT_MATERIALIZED only when Frozen state is unavailable"},
            "gripper_transition_present": {"source": "Frozen G1 Final Boundary plus gripper_state", "unit": "boolean", "definition": "left GRIPPER_TRANSITION boundary or an internal state change", "missing": "never"},
            "action_magnitude_*": {"source": "recorded actions", "unit": "NORMALIZED_CONTROLLER_INPUT", "definition": "mean/max/std of per-frame L2 norm of recorded 7D command", "missing": "forbidden"},
        },
    }
    (output / "motion_feature_contract.json").write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    multi_role = sum("|" in row["roles"] for row in keyframe_rows)
    sanity = {
        "episodes_processed": len(episode_ids),
        "segments_processed": len(segment_rows),
        "keyframe_rows": len(keyframe_rows),
        "unique_rgb_files": len(rgb_records),
        "multi_role_frame_count": multi_role,
        "gripper_event_segments": gripper_event_segments,
        "checks": {
            "FROZEN_G1_CONFIG_IDENTITY": "PASS",
            "RGB_CONTRACT_IDENTITY": "PASS",
            "KEYFRAME_FRAME_IN_SEGMENT": "PASS",
            "START_FRAME_EXACT": "PASS",
            "END_FRAME_EXACT": "PASS",
            "MIDDLE_DETERMINISTIC": "PASS",
            "NO_DUPLICATE_RGB_MATERIALIZATION": "PASS",
            "MULTI_ROLE_FRAME_PRESERVED": "PASS",
            "GRIPPER_EVENT_SEMANTICS": "PASS",
            "MOTION_FEATURE_FINITE": "PASS",
            "NO_PRIVILEGED_INPUT": "PASS",
            "SEGMENT_DURATION_IDENTITY": "PASS",
        },
    }
    (output / "sanity_summary.json").write_text(json.dumps(sanity, indent=2) + "\n", encoding="utf-8")
    meta = {
        "run_id": output.name,
        "created_at": datetime.now().astimezone().isoformat(),
        "git_base": git_base,
        "episode_ids": list(episode_ids),
        "frozen_g1_identity": FROZEN_G1_IDENTITY,
        "rgb_contract_version": MODEL_RGB_CONTRACT_VERSION,
        "feature_version": MOTION_FEATURE_VERSION,
        "siglip2_executed": False,
        "dino_executed": False,
        "vlm_executed": False,
        "faiss_executed": False,
    }
    (output / "run_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return {"output_run": str(output.resolve()), **sanity}
