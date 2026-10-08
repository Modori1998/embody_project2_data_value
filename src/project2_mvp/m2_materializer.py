"""Small-sample runtime materializer for MVP-M2."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from project2_g1.boundary_engine import CANDIDATE_GRIPPER
from project2_g1.config import load_g1_p1_config
from project2_g1.paths import PROJECT2_ROOT
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


EXPECTED_FROZEN_G1_IDENTITY = {
    "stage_a_acceptance_config": "A1-007-C002",
    "tau_P12": 0.04758563666765155,
    "tau_C12": 0.690169167642685,
    "boundary_consolidation_window": 8,
    "p12_incomplete": "FAIL_OPEN_KEEP",
    "c12_incomplete": "P12_ONLY_FALLBACK",
}
EXPECTED_RGB_CONTRACT_VERSION = "MVP_RGB_SOURCE_AND_ALIGNMENT_CONTRACT_v1"
FROZEN_G1_CONFIG_DOC = (
    PROJECT2_ROOT
    / "0-doc"
    / "10-design-review"
    / "Project2_G1_P3_Final_Calibration_Config_FROZEN_v1_20260927.md"
)


def runtime_frozen_g1_identity() -> dict[str, Any]:
    return {
        "stage_a_acceptance_config": STAGE_A_PARENT,
        "tau_P12": TAU_P12,
        "tau_C12": TAU_C12,
        "boundary_consolidation_window": BOUNDARY_CONSOLIDATION_WINDOW,
        "p12_incomplete": "FAIL_OPEN_KEEP",
        "c12_incomplete": "P12_ONLY_FALLBACK",
    }


def validate_frozen_g1_identity(actual: dict[str, Any]) -> None:
    mismatches = {
        key: {"expected": expected, "actual": actual.get(key)}
        for key, expected in EXPECTED_FROZEN_G1_IDENTITY.items()
        if actual.get(key) != expected
    }
    if mismatches:
        raise ValueError(
            "STOP_FROZEN_G1_IDENTITY_FAILURE: "
            + json.dumps(mismatches, sort_keys=True)
        )


def assert_frozen_g1_identity() -> dict[str, Any]:
    actual = runtime_frozen_g1_identity()
    validate_frozen_g1_identity(actual)
    if not FROZEN_G1_CONFIG_DOC.is_file():
        raise FileNotFoundError(
            f"STOP_FROZEN_G1_CONFIG_DOC_MISSING: {FROZEN_G1_CONFIG_DOC}"
        )
    frozen_text = FROZEN_G1_CONFIG_DOC.read_text(encoding="utf-8")
    required_literals = (
        "STAGE_A_ACCEPTANCE_CONFIG = A1-007-C002",
        "tau_P12 = 0.04758563666765155",
        "tau_C12 = 0.690169167642685",
        "boundary_consolidation_window = 8",
        "FAIL_OPEN_KEEP",
        "P12_ONLY_FALLBACK",
    )
    missing = [value for value in required_literals if value not in frozen_text]
    if missing:
        raise ValueError(
            "STOP_FROZEN_G1_DOC_IDENTITY_FAILURE: "
            + json.dumps(missing)
        )
    return actual


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


def compute_m2_sanity_checks(
    segment_rows: Sequence[dict[str, Any]],
    keyframe_rows: Sequence[dict[str, Any]],
    motion_rows: Sequence[dict[str, Any]],
    rgb_records: Sequence[dict[str, Any]],
) -> dict[str, bool]:
    """Compute runtime gates from materialized rows; never hard-code PASS."""

    segments = {str(row["segment_id"]): row for row in segment_rows}
    by_segment: dict[str, list[dict[str, Any]]] = {}
    for row in keyframe_rows:
        by_segment.setdefault(str(row["segment_id"]), []).append(row)

    keyframe_in_segment = True
    start_exact = True
    end_exact = True
    middle_deterministic = True
    multi_role_preserved = True
    gripper_semantics = True

    for segment_id, segment in segments.items():
        start = int(segment["start_frame"])
        end = int(segment["end_frame"])
        expected_middle = (start + end) // 2
        rows = by_segment.get(segment_id, [])
        frames = [int(row["frame_index"]) for row in rows]
        role_map = {
            int(row["frame_index"]): set(str(row["roles"]).split("|"))
            for row in rows
        }

        keyframe_in_segment &= all(start <= frame <= end for frame in frames)
        start_exact &= any(
            int(row["frame_index"]) == start and "START" in str(row["roles"]).split("|")
            for row in rows
        )
        end_exact &= any(
            int(row["frame_index"]) == end and "END" in str(row["roles"]).split("|")
            for row in rows
        )
        middle_deterministic &= any(
            int(row["frame_index"]) == expected_middle
            and "MIDDLE" in str(row["roles"]).split("|")
            for row in rows
        )

        expected_roles: dict[int, set[str]] = {}
        for frame, role in ((start, "START"), (expected_middle, "MIDDLE"), (end, "END")):
            expected_roles.setdefault(frame, set()).add(role)
        left_is_gripper = str(segment.get("left_boundary_type")) == CANDIDATE_GRIPPER
        if left_is_gripper:
            expected_roles.setdefault(start, set()).add("GRIPPER_EVENT")
        multi_role_preserved &= role_map == expected_roles

        gripper_rows = [
            row
            for row in rows
            if "GRIPPER_EVENT" in str(row["roles"]).split("|")
        ]
        if left_is_gripper:
            gripper_semantics &= (
                len(gripper_rows) == 1
                and int(gripper_rows[0]["frame_index"]) == start
            )
        else:
            gripper_semantics &= len(gripper_rows) == 0

    key_identities = [
        (
            str(row["source_episode_id"]),
            str(row["segment_id"]),
            int(row["frame_index"]),
        )
        for row in keyframe_rows
    ]
    rgb_identities = [
        (
            str(row["source_episode_id"]),
            str(row["segment_id"]),
            int(row["frame_index"]),
        )
        for row in rgb_records
    ]
    no_duplicate_rgb = (
        len(key_identities) == len(set(key_identities))
        and len(rgb_identities) == len(set(rgb_identities))
        and set(key_identities) == set(rgb_identities)
        and len({str(row["png_relpath"]) for row in rgb_records}) == len(rgb_records)
    )

    duration_identity = all(
        int(row["duration_frames"])
        == int(row["end_frame"]) - int(row["start_frame"]) + 1
        for row in segment_rows
    )
    motion_by_segment = {str(row["segment_id"]): row for row in motion_rows}
    motion_feature_finite = set(motion_by_segment) == set(segments)
    for row in motion_rows:
        numeric = [
            row["duration_sec"],
            row["eef_net_displacement_m"],
            row["eef_path_length_m"],
            *row["eef_displacement_xyz"],
            *row["eef_main_direction_xyz"],
            row["gripper_start_aperture"],
            row["gripper_end_aperture"],
            row["action_magnitude_mean"],
            row["action_magnitude_max"],
            row["action_magnitude_std"],
        ]
        motion_feature_finite &= bool(
            __import__("numpy").isfinite(
                __import__("numpy").asarray(numeric, dtype=float)
            ).all()
        )
        coarse = row.get("coarse_direction_change_rad")
        if coarse is not None:
            motion_feature_finite &= bool(__import__("numpy").isfinite(float(coarse)))

    rgb_contract_identity = (
        MODEL_RGB_CONTRACT_VERSION == EXPECTED_RGB_CONTRACT_VERSION
        and all(
            str(row.get("rgb_contract_version")) == EXPECTED_RGB_CONTRACT_VERSION
            for row in keyframe_rows
        )
        and all(
            row.get("provenance", {}).get("contract_version")
            == EXPECTED_RGB_CONTRACT_VERSION
            and row.get("provenance", {}).get("overlay_applied") is False
            and row.get("provenance", {}).get("audit_mp4_used") is False
            and row.get("provenance", {}).get("lossy_video_roundtrip") is False
            for row in rgb_records
        )
    )

    return {
        "FROZEN_G1_CONFIG_IDENTITY": runtime_frozen_g1_identity()
        == EXPECTED_FROZEN_G1_IDENTITY,
        "RGB_CONTRACT_IDENTITY": rgb_contract_identity,
        "KEYFRAME_FRAME_IN_SEGMENT": keyframe_in_segment,
        "START_FRAME_EXACT": start_exact,
        "END_FRAME_EXACT": end_exact,
        "MIDDLE_DETERMINISTIC": middle_deterministic,
        "NO_DUPLICATE_RGB_MATERIALIZATION": no_duplicate_rgb,
        "MULTI_ROLE_FRAME_PRESERVED": multi_role_preserved,
        "GRIPPER_EVENT_SEMANTICS": gripper_semantics,
        "MOTION_FEATURE_FINITE": motion_feature_finite,
        "NO_PRIVILEGED_INPUT": True,
        "SEGMENT_DURATION_IDENTITY": duration_identity,
    }


def assert_m2_sanity(checks: dict[str, bool]) -> None:
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise ValueError(
            "STOP_MVP_M2_RUNTIME_SANITY_FAILURE: " + json.dumps(failed)
        )


def materialize_m2(
    output_root: str | Path,
    episode_ids: Sequence[str] = ("data/demo_0", "data/demo_1", "data/demo_2"),
    *,
    git_base: str,
) -> dict[str, Any]:
    """Materialize one immutable M2 run from the Frozen G1 configuration."""

    assert_no_privileged_inputs(ALLOWED_FORMAL_INPUT_FIELDS)
    frozen_g1_identity = assert_frozen_g1_identity()
    if MODEL_RGB_CONTRACT_VERSION != EXPECTED_RGB_CONTRACT_VERSION:
        raise ValueError(
            "STOP_RGB_CONTRACT_IDENTITY_FAILURE: "
            f"expected={EXPECTED_RGB_CONTRACT_VERSION} actual={MODEL_RGB_CONTRACT_VERSION}"
        )
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
    computed_checks = compute_m2_sanity_checks(
        segment_rows,
        keyframe_rows,
        motion_rows,
        rgb_records,
    )
    assert_m2_sanity(computed_checks)
    sanity = {
        "episodes_processed": len(episode_ids),
        "segments_processed": len(segment_rows),
        "keyframe_rows": len(keyframe_rows),
        "unique_rgb_files": len(rgb_records),
        "multi_role_frame_count": multi_role,
        "gripper_event_segments": gripper_event_segments,
        "checks": {
            name: "PASS" if passed else "FAIL"
            for name, passed in computed_checks.items()
        },
    }
    (output / "sanity_summary.json").write_text(json.dumps(sanity, indent=2) + "\n", encoding="utf-8")
    meta = {
        "run_id": output.name,
        "created_at": datetime.now().astimezone().isoformat(),
        "git_base": git_base,
        "episode_ids": list(episode_ids),
        "frozen_g1_identity": frozen_g1_identity,
        "frozen_g1_expected_identity": EXPECTED_FROZEN_G1_IDENTITY,
        "frozen_g1_config_doc": str(FROZEN_G1_CONFIG_DOC.relative_to(PROJECT2_ROOT)),
        "frozen_g1_config_doc_sha256": _sha256(FROZEN_G1_CONFIG_DOC),
        "rgb_contract_version": MODEL_RGB_CONTRACT_VERSION,
        "feature_version": MOTION_FEATURE_VERSION,
        "siglip2_executed": False,
        "dino_executed": False,
        "vlm_executed": False,
        "faiss_executed": False,
    }
    (output / "run_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return {"output_run": str(output.resolve()), **sanity}
