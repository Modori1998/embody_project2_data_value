"""Stage A0 Direction Candidate Discriminability Audit.

READ-ONLY analysis of frozen Baseline Scoring + Formal Signals.
Does not modify Detector, does not search parameters, does not generate configs.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from project2_g1_audit_web.hashes import now_iso, sha256_file, tree_fingerprint

from .baseline_calibration_run import EXPECTED_CONFIG_HASH, EXPECTED_SIGNAL_HASH
from .baseline_scoring import (
    EXPECTED_EXPORT_IDS,
    EXPECTED_RUN_ID,
    EXPECTED_SNAPSHOT_ID,
    SQLITE_SHA256,
    load_canonical_snapshot,
)
from .boundary_config import load_g1_p2_config
from .boundary_engine import (
    CANDIDATE_DIRECTION,
    CANDIDATE_GRIPPER,
    CANDIDATE_IDLE_TO_MOVE,
    CANDIDATE_MOVE_TO_IDLE,
    heading_angle,
    heading_vector,
    persistent_high_runs,
)
from .boundary_matching import MATCHING_RULE_ID, TOLERANCE_FRAMES
from .canonical_gt import PROTECTED_DIRECTION
from .config import load_g1_p1_config
from .paths import CONFIG_PATH, DATASET_RAW_HDF5, G1_P2_CONFIG_PATH, PROJECT2_ENGINEERING_MASTER, PROJECT2_ROOT
from .signals import compute_formal_signals
from .source import build_can_mh_adapter, load_formal_episode

CALIBRATION_PROTOCOL_EFFECTIVE_VERSION = "FROZEN_v1.1"
STAGE = "A0_DIRECTION_CANDIDATE_DISCRIMINABILITY_AUDIT"
EXPECTED_SCORE_ID = "g1_baseline_score_20260918_155714_42295cc6"
HUMAN_VALID = "VALID_DIRECTION"
HUMAN_FP = "DIRECTION_FP"
PACKAGE_SEED = "SEED"
PACKAGE_FRESH = "FRESH"
LEGAL_ERROR_MODES = ("MODE_01", "MODE_02", "MODE_03", "UNASSIGNED")
FROZEN_DIRECTION_THRESHOLD = 1.2
FROZEN_DIRECTION_PERSISTENCE = 3
FROZEN_WINDOW_FRAMES = 8
DIAGNOSTIC_WINDOWS = (3, 5, 8)
PRIMARY_WINDOW = 8
MIN_WINDOW_DISPLACEMENT_M = 0.005
PRIVILEGED_TOKENS = (
    "can_pos", "can_quat", "object_gt", "object_pos", "reward", "success", "done",
    "privileged", "can_to_eef",
)
FORBIDDEN_SOURCE_TOKENS = PRIVILEGED_TOKENS + ("direction_change_threshold_sweep", "grid_search")

KNOWN_FINGERPRINTS = {
    "canonical_gt": "335a8d62d9871e26f34a6e887206cbb48504dfc551337c024086e7252ac399ef",
    "seed_export": "8ba31e9721ee3554b3b56b3bc46ff041c175b39865ea76c918f931b0a6d355c7",
    "fresh_export": "01a3c732ae8b193a72ede845363105d0742b2f8357685e1f61d0a1b52dc3eb1f",
    "owner_sqlite": SQLITE_SHA256,
    "protocol_v1": "d75c05d7a0cad0ba2298225745314af7a313ad70e19d331b3b49205fb7e81c1a",
    "protocol_v11": "011eab45065026d2c697daafa06826c80c873129c687bd97799a95e9af4ef175",
    "baseline_run_meta": "4a9b5e973e5c093e554488b45bcfbc1ecfa006bce04da9b1a0a3a6a18de172e8",
}

EVENT_FIELDS = (
    "episode_id", "pred_boundary_id", "pred_frame", "human_class", "source_package",
    "error_mode", "reason_code", "gt_id", "representative_candidate_id",
    "member_candidate_count", "member_candidate_types",
    "evidence_value", "evidence_value_provenance",
    "run_length", "run_length_provenance",
    "translation_speed_at_event", "smoothed_speed_at_event",
    "local_speed_min", "local_speed_mean", "pre_speed_mean", "post_speed_mean",
    "speed_drop_ratio", "speed_context_provenance",
    "local_speed_min_w3", "local_speed_min_w5", "local_speed_min_w8",
    "diagnostic_window_note",
    "pre_displacement_m", "post_displacement_m", "min_displacement_m",
    "displacement_provenance",
    "heading_angle_rad", "heading_vs_evidence_delta", "heading_homology_note",
    "heading_provenance",
    "local_speed_valley", "idle_fraction_in_window",
    "distance_to_nearest_move_to_idle", "distance_to_nearest_idle_to_move",
    "idle_context_provenance",
    "distance_to_nearest_gripper_candidate", "distance_to_nearest_gripper_final",
    "signed_distance_to_next_gripper", "gripper_distance_provenance",
    "rotation_support", "action_support", "support_combination", "support_provenance",
    "peak_value", "peak_width", "left_decay", "right_decay",
    "local_area_above_threshold", "local_secondary_peaks", "peak_shape_formula",
    "peak_shape_provenance",
    "is_independent_direction_final", "is_gripper_primary_merged",
)

NON_DIRECTION_FP_FIELDS = (
    "episode_id", "pred_boundary_id", "pred_frame", "candidate_type", "reason_code",
    "error_mode", "source_package", "representative_candidate_id",
    "distance_to_nearest_gripper_final", "distance_to_nearest_direction_final",
    "member_candidate_types",
)

NUMERIC_ANALYSIS_FIELDS = (
    "evidence_value", "run_length", "translation_speed_at_event", "smoothed_speed_at_event",
    "local_speed_min", "local_speed_mean", "pre_speed_mean", "post_speed_mean",
    "speed_drop_ratio", "pre_displacement_m", "post_displacement_m", "min_displacement_m",
    "heading_angle_rad", "heading_vs_evidence_delta", "idle_fraction_in_window",
    "distance_to_nearest_gripper_candidate", "distance_to_nearest_gripper_final",
    "signed_distance_to_next_gripper", "distance_to_nearest_move_to_idle",
    "distance_to_nearest_idle_to_move", "peak_width", "local_area_above_threshold",
    "local_secondary_peaks", "left_decay", "right_decay", "member_candidate_count",
)

FEATURE_FORMULAS = {
    "evidence_value": "representative candidate CSV evidence_value = peak of direction_change_evidence in the persistent run",
    "run_length": "ANALYSIS_DERIVED: persistent_high_runs(direction_change_evidence, T=1.2, P=3) run_length at peak_frame==pred_frame",
    "translation_speed_at_event": "translation_speed[t]",
    "smoothed_speed_at_event": "smoothed_translation_speed[t]",
    "local_speed_min": "min(translation_speed[t-W:t+W+1]) with W=8 frozen P1 direction_window_frames; clipped to episode",
    "local_speed_mean": "mean(translation_speed[t-W:t+W+1]) W=8",
    "pre_speed_mean": "mean(translation_speed[t-W:t]) W=8",
    "post_speed_mean": "mean(translation_speed[t:t+W]) W=8",
    "speed_drop_ratio": "(pre_speed_mean - local_speed_min) / pre_speed_mean if pre_speed_mean > 0 else NA",
    "pre_displacement_m": "||heading_vector(signals, t-W, t)|| W=8",
    "post_displacement_m": "||heading_vector(signals, t, t+W)|| W=8",
    "min_displacement_m": "min(pre_displacement_m, post_displacement_m)",
    "heading_angle_rad": "heading_angle(pre_vec, post_vec); homologous with direction_change_evidence when both window norms >= 0.005 m",
    "local_speed_valley": "1 if argmin(translation_speed[t-W:t+W+1]) is within 1 frame of t else 0; DIAGNOSTIC",
    "idle_fraction_in_window": "mean(motion_state_candidate[t-W:t+W+1]==0); DIAGNOSTIC only, not a split rule",
    "distance_to_nearest_gripper_candidate": "min |frame_gripper_cand - t|",
    "distance_to_nearest_gripper_final": "min |frame_gripper_final - t|",
    "signed_distance_to_next_gripper": "min(frame_gripper_final - t) among finals with frame > t; else NA",
    "peak_width": "length of maximal contiguous run of (direction_change_evidence > 1.2) containing t; uses frozen baseline threshold only to describe the current persistent run",
    "left_decay": "evidence[t] - evidence[t-1]",
    "right_decay": "evidence[t] - evidence[t+1]",
    "local_area_above_threshold": "sum(max(evidence[i]-1.2, 0) for i in the contiguous above-threshold run containing t)",
    "local_secondary_peaks": "count of local maxima of evidence in [t-W, t+W] excluding t; W=8",
}


class StageA0Error(ValueError):
    pass


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise StageA0Error(f"{path}: missing header")
        return list(reader)


def _write_csv(path: Path, fieldnames: Sequence[str], rows: list[Mapping[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if row.get(key) is None else row[key] for key in fieldnames})


def _csv_bool(value: bool) -> str:
    return "true" if value else "false"


def parse_supporting_reasons(raw: str | None) -> tuple[bool, bool, str]:
    parts = [item for item in str(raw or "").split("|") if item]
    rotation = "ROTATION_SUPPORT" in parts
    action = "ACTION_SUPPORT" in parts
    if rotation and action:
        combo = "ROTATION_SUPPORT|ACTION_SUPPORT"
    elif rotation:
        combo = "ROTATION_SUPPORT"
    elif action:
        combo = "ACTION_SUPPORT"
    elif not parts:
        combo = "NONE"
    else:
        combo = "|".join(parts)
    return rotation, action, combo


def quantile(values: Sequence[float], q: float) -> float | None:
    xs = sorted(float(v) for v in values)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    pos = float(q) * (len(xs) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def overlap_interval(a_lo: float | None, a_hi: float | None, b_lo: float | None, b_hi: float | None) -> dict[str, Any]:
    if None in (a_lo, a_hi, b_lo, b_hi):
        return {"overlap": None, "overlap_width": None, "status": "NOT_AVAILABLE"}
    left = max(a_lo, b_lo)
    right = min(a_hi, b_hi)
    if left > right:
        return {"overlap": False, "overlap_width": 0.0, "status": "NO_OVERLAP", "interval": None}
    return {
        "overlap": True,
        "overlap_width": float(right - left),
        "status": "OVERLAP",
        "interval": [float(left), float(right)],
    }


def numeric_summary(values: Sequence[float | None]) -> dict[str, Any]:
    xs = [float(v) for v in values if v is not None and v == v]
    if not xs:
        return {
            "count": 0, "mean": None, "median": None, "q25": None, "q75": None,
            "min": None, "max": None, "missing": len(values),
        }
    return {
        "count": len(xs),
        "mean": float(sum(xs) / len(xs)),
        "median": quantile(xs, 0.5),
        "q25": quantile(xs, 0.25),
        "q75": quantile(xs, 0.75),
        "min": float(min(xs)),
        "max": float(max(xs)),
        "missing": len(values) - len(xs),
    }


def _finite_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def extract_valid_direction_cohort(matching_pairs: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair in matching_pairs:
        if str(pair.get("protected_class") or "") != PROTECTED_DIRECTION:
            continue
        if str(pair.get("pred_candidate_type") or "") != CANDIDATE_DIRECTION:
            continue
        rows.append({
            "episode_id": str(pair["episode_id"]),
            "pred_boundary_id": str(pair["pred_boundary_id"]),
            "pred_frame": int(pair["pred_frame"]),
            "human_class": HUMAN_VALID,
            "source_package": str(pair.get("source_package") or ""),
            "error_mode": "",
            "reason_code": "",
            "gt_id": str(pair.get("gt_id") or ""),
            "representative_candidate_id": str(pair.get("pred_representative_candidate_id") or ""),
            "protected_class": str(pair.get("protected_class") or ""),
            "pred_candidate_type": str(pair.get("pred_candidate_type") or ""),
        })
    rows.sort(key=lambda item: (item["episode_id"], item["pred_frame"], item["pred_boundary_id"]))
    return rows


def extract_fp_cohorts(fp_rows: Sequence[Mapping[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    direction: list[dict[str, Any]] = []
    non_direction: list[dict[str, Any]] = []
    for row in fp_rows:
        payload = {
            "episode_id": str(row["episode_id"]),
            "pred_boundary_id": str(row["pred_boundary_id"]),
            "pred_frame": int(row["pred_frame"]),
            "human_class": HUMAN_FP,
            "source_package": "",
            "error_mode": str(row.get("known_fp_error_mode") or "UNASSIGNED"),
            "reason_code": str(row.get("reason_code") or ""),
            "gt_id": "",
            "representative_candidate_id": str(row.get("representative_candidate_id") or ""),
            "pred_candidate_type": str(row.get("candidate_type") or ""),
            "member_candidate_types": str(row.get("member_candidate_types") or ""),
            "known_fp_anchor_matched": str(row.get("known_fp_anchor_matched") or ""),
        }
        if payload["error_mode"] not in LEGAL_ERROR_MODES:
            raise StageA0Error(f"illegal error_mode {payload['error_mode']} on {payload['pred_boundary_id']}")
        if payload["pred_candidate_type"] == CANDIDATE_DIRECTION:
            direction.append(payload)
        else:
            non_direction.append(payload)
    direction.sort(key=lambda item: (item["episode_id"], item["pred_frame"], item["pred_boundary_id"]))
    non_direction.sort(key=lambda item: (item["episode_id"], item["pred_frame"], item["pred_boundary_id"]))
    return direction, non_direction


def attach_fp_package(fp_rows: list[dict[str, Any]], anchor_rows: Sequence[Mapping[str, str]]) -> None:
    by_pred = {
        (str(row["episode_id"]), str(row["matched_pred_boundary_id"])): row
        for row in anchor_rows
        if str(row.get("matched_pred_boundary_id") or "")
    }
    for row in fp_rows:
        key = (row["episode_id"], row["pred_boundary_id"])
        anchor = by_pred.get(key)
        if anchor is not None:
            row["source_package"] = str(anchor.get("source_package") or "")
            if str(anchor.get("error_mode") or "") and row["error_mode"] != str(anchor["error_mode"]):
                raise StageA0Error(
                    f"error_mode mismatch {row['pred_boundary_id']}: "
                    f"fp={row['error_mode']} anchor={anchor['error_mode']}"
                )


def native_key(episode_id: str) -> str:
    return episode_id.split("/", 1)[-1]


def _clip_window(n: int, frame: int, radius: int) -> tuple[int, int]:
    start = max(0, int(frame) - int(radius))
    end = min(int(n), int(frame) + int(radius) + 1)
    return start, end


def _mean_or_none(values: np.ndarray) -> float | None:
    if len(values) == 0:
        return None
    return float(np.mean(values))


def _min_abs_distance(frame: int, others: Sequence[int]) -> int | None:
    if not others:
        return None
    return int(min(abs(int(frame) - int(other)) for other in others))


def _signed_next(frame: int, others: Sequence[int]) -> int | None:
    later = [int(other) - int(frame) for other in others if int(other) > int(frame)]
    if not later:
        return None
    return int(min(later))


def derive_run_length(evidence: np.ndarray, frame: int, threshold: float, persistence: int) -> tuple[int | None, str]:
    runs = persistent_high_runs(evidence, threshold, persistence)
    matched = [item for item in runs if int(item[0]) == int(frame)]
    if len(matched) == 1:
        return int(matched[0][2]), "ANALYSIS_DERIVED"
    if not matched:
        containing = [
            item for item in runs
            if _frame_in_run(evidence, int(item[0]), threshold, int(frame))
        ]
        if len(containing) == 1:
            return int(containing[0][2]), "ANALYSIS_DERIVED_CONTAINING_RUN"
        return None, "NOT_AVAILABLE"
    return None, "NOT_AVAILABLE_AMBIGUOUS"


def _frame_in_run(evidence: np.ndarray, peak_frame: int, threshold: float, frame: int) -> bool:
    high = np.asarray(evidence, dtype=np.float64) > float(threshold)
    if not (0 <= int(frame) < len(high)) or not high[int(frame)]:
        return False
    start = int(peak_frame)
    while start > 0 and high[start - 1]:
        start -= 1
    end = int(peak_frame)
    n = len(high)
    while end + 1 < n and high[end + 1]:
        end += 1
    return start <= int(frame) <= end


def peak_shape(evidence: np.ndarray, frame: int, threshold: float, window: int) -> dict[str, Any]:
    values = np.asarray(evidence, dtype=np.float64)
    n = len(values)
    t = int(frame)
    if not (0 <= t < n):
        raise StageA0Error(f"frame {frame} out of bounds n={n}")
    high = values > float(threshold)
    start = t
    while start > 0 and high[start - 1]:
        start -= 1
    end = t
    while end + 1 < n and high[end + 1]:
        end += 1
    width = int(end - start + 1) if high[t] else 0
    area = float(np.sum(np.maximum(values[start:end + 1] - float(threshold), 0.0))) if high[t] else 0.0
    left = float(values[t] - values[t - 1]) if t > 0 else None
    right = float(values[t] - values[t + 1]) if t + 1 < n else None
    w_start, w_end = _clip_window(n, t, window)
    secondary = 0
    for index in range(w_start, w_end):
        if index == t:
            continue
        prev_ok = index == 0 or values[index] >= values[index - 1]
        next_ok = index == n - 1 or values[index] >= values[index + 1]
        if prev_ok and next_ok and values[index] > float(threshold):
            secondary += 1
    return {
        "peak_value": float(values[t]),
        "peak_width": width if high[t] else None,
        "left_decay": left,
        "right_decay": right,
        "local_area_above_threshold": area if high[t] else None,
        "local_secondary_peaks": secondary,
        "peak_shape_formula": (
            "peak_width=len(maximal contiguous evidence>T containing t); "
            "local_area=sum(max(evidence-T,0) on that run); "
            f"T={threshold} frozen baseline; W={window} for secondary peaks"
        ),
        "peak_shape_provenance": "ANALYSIS_DERIVED_FROZEN_THRESHOLD_DESCRIPTIVE",
    }


def speed_context(signals, frame: int, window: int) -> dict[str, Any]:
    t = int(frame)
    n = int(signals.n_frames)
    speed = np.asarray(signals.translation_speed, dtype=np.float64)
    smoothed = np.asarray(signals.smoothed_translation_speed, dtype=np.float64)
    start, end = _clip_window(n, t, window)
    pre = speed[max(0, t - window):t]
    post = speed[t:min(n, t + window)]
    local = speed[start:end]
    pre_mean = _mean_or_none(pre)
    local_min = float(np.min(local)) if len(local) else None
    drop = None
    if pre_mean is not None and pre_mean > 0 and local_min is not None:
        drop = float((pre_mean - local_min) / pre_mean)
    argmin = int(np.argmin(local)) + start if len(local) else None
    valley = None if argmin is None else int(abs(argmin - t) <= 1)
    idle_frac = None
    if signals.motion_state_candidate is not None:
        motion = np.asarray(signals.motion_state_candidate)
        idle_frac = float(np.mean(motion[start:end] == 0)) if end > start else None
    return {
        "translation_speed_at_event": float(speed[t]),
        "smoothed_speed_at_event": float(smoothed[t]),
        "local_speed_min": local_min,
        "local_speed_mean": _mean_or_none(local),
        "pre_speed_mean": pre_mean,
        "post_speed_mean": _mean_or_none(post),
        "speed_drop_ratio": drop,
        "local_speed_valley": valley,
        "idle_fraction_in_window": idle_frac,
        "speed_context_provenance": f"FORMAL_SIGNAL W={window} FROZEN_P1_DIRECTION_WINDOW",
    }


def displacement_context(signals, frame: int, window: int) -> dict[str, Any]:
    t = int(frame)
    pre_vec = heading_vector(signals, t - window, t)
    post_vec = heading_vector(signals, t, t + window)
    pre_n = float(np.linalg.norm(pre_vec))
    post_n = float(np.linalg.norm(post_vec))
    angle = heading_angle(pre_vec, post_vec)
    evidence = float(signals.direction_change_evidence[t])
    delta = None if angle is None else float(angle - evidence)
    if angle is None:
        homology = "NOT_AVAILABLE_ZERO_NORM"
    elif pre_n < MIN_WINDOW_DISPLACEMENT_M or post_n < MIN_WINDOW_DISPLACEMENT_M:
        homology = "DIVERGES_WHEN_DISPLACEMENT_GATE_ZEROS_EVIDENCE"
    else:
        homology = "HOMOLOGOUS_WITH_DIRECTION_CHANGE_EVIDENCE_NOT_INDEPENDENT"
    return {
        "pre_displacement_m": pre_n,
        "post_displacement_m": post_n,
        "min_displacement_m": float(min(pre_n, post_n)),
        "heading_angle_rad": angle,
        "heading_vs_evidence_delta": delta,
        "heading_homology_note": homology,
        "displacement_provenance": f"heading_vector FormalSignal W={window}",
        "heading_provenance": f"heading_angle(pre,post) W={window}; {homology}",
    }


def load_episode_tables(run_root: Path, episode_id: str) -> dict[str, Any]:
    native = native_key(episode_id)
    diagnostic = run_root / "diagnostic" / native
    candidates = _read_csv(diagnostic / "candidate_boundaries.csv")
    finals = _read_csv(diagnostic / "final_boundaries.csv")
    return {"candidates": candidates, "finals": finals}


def _frames_of_type(rows: Sequence[Mapping[str, str]], field: str, cand_type: str) -> list[int]:
    out: list[int] = []
    for row in rows:
        if str(row.get(field) or "") == cand_type:
            out.append(int(row["frame"]))
    return out


def lineage_for_final(finals: Sequence[Mapping[str, str]], candidates: Sequence[Mapping[str, str]], boundary_id: str) -> dict[str, Any]:
    matched = [row for row in finals if str(row.get("boundary_id") or "") == boundary_id]
    if len(matched) != 1:
        raise StageA0Error(f"{boundary_id}: expected 1 final row, got {len(matched)}")
    final = matched[0]
    rep_id = str(final.get("representative_candidate_id") or "")
    reps = [row for row in candidates if str(row.get("candidate_id") or "") == rep_id]
    if len(reps) != 1:
        raise StageA0Error(f"{boundary_id}: representative {rep_id} not unique in candidates")
    candidate = reps[0]
    member_types = [part for part in str(final.get("member_candidate_types") or "").split("|") if part]
    member_count = int(str(final.get("member_candidate_count") or "0") or 0)
    gripper_merged = member_count >= 2 and CANDIDATE_GRIPPER in member_types
    independent = str(final.get("candidate_type") or "") == CANDIDATE_DIRECTION and not gripper_merged
    rotation, action, combo = parse_supporting_reasons(final.get("supporting_reasons") or candidate.get("supporting_reasons"))
    return {
        "final": final,
        "candidate": candidate,
        "member_candidate_count": member_count,
        "member_candidate_types": str(final.get("member_candidate_types") or ""),
        "is_independent_direction_final": independent,
        "is_gripper_primary_merged": gripper_merged,
        "rotation_support": rotation,
        "action_support": action,
        "support_combination": combo,
        "evidence_value": float(candidate["evidence_value"]),
    }


def source_fingerprints(root: Path) -> dict[str, Any]:
    protocol_v1 = root / "0-doc/10-design-review/Project2_G1_P3_Calibration_Protocol_FROZEN_v1_20260917.md"
    protocol_v11 = root / "0-doc/10-design-review/Project2_G1_P3_Calibration_Protocol_FROZEN_v1_1_PATCH_20260918.md"
    sqlite = root / "outputs/g1_audit_web/g1_audit_web_owner.sqlite3"
    seed_export = root / "outputs/g1_audit_web/human_calibration_export" / EXPECTED_EXPORT_IDS[0]
    fresh_export = root / "outputs/g1_audit_web/human_calibration_export" / EXPECTED_EXPORT_IDS[1]
    snapshot = root / "outputs/g1_p3_canonical_gt" / EXPECTED_SNAPSHOT_ID
    run = root / "outputs/g1_audit_runs" / EXPECTED_RUN_ID
    score = root / "outputs/g1_p3_scoring" / EXPECTED_SCORE_ID
    return {
        "baseline_run": tree_fingerprint(run)["tree_fingerprint"],
        "baseline_run_meta": sha256_file(run / "run_meta.json"),
        "baseline_score": tree_fingerprint(score)["tree_fingerprint"],
        "canonical_gt": tree_fingerprint(snapshot)["tree_fingerprint"],
        "seed_export": tree_fingerprint(seed_export)["tree_fingerprint"],
        "fresh_export": tree_fingerprint(fresh_export)["tree_fingerprint"],
        "owner_sqlite": sha256_file(sqlite),
        "protocol_v1": sha256_file(protocol_v1),
        "protocol_v11": sha256_file(protocol_v11),
        "dataset": sha256_file(DATASET_RAW_HDF5) if DATASET_RAW_HDF5.is_file() else None,
        "engineering_master": sha256_file(PROJECT2_ENGINEERING_MASTER) if PROJECT2_ENGINEERING_MASTER.is_file() else None,
        "g1_p1_config": sha256_file(CONFIG_PATH),
        "g1_p2_config": sha256_file(G1_P2_CONFIG_PATH),
    }


def assert_known_fingerprints(fingerprints: Mapping[str, Any]) -> None:
    mapping = {
        "canonical_gt": KNOWN_FINGERPRINTS["canonical_gt"],
        "seed_export": KNOWN_FINGERPRINTS["seed_export"],
        "fresh_export": KNOWN_FINGERPRINTS["fresh_export"],
        "owner_sqlite": KNOWN_FINGERPRINTS["owner_sqlite"],
        "protocol_v1": KNOWN_FINGERPRINTS["protocol_v1"],
        "protocol_v11": KNOWN_FINGERPRINTS["protocol_v11"],
        "baseline_run_meta": KNOWN_FINGERPRINTS["baseline_run_meta"],
    }
    errors = [f"{key} mismatch" for key, expected in mapping.items() if fingerprints.get(key) != expected]
    if errors:
        raise StageA0Error("source identity failed: " + "; ".join(errors))


def pairwise_ordering_rate(valid: Sequence[float], fp: Sequence[float], *, higher_is_valid_like: bool = True) -> float | None:
    if not valid or not fp:
        return None
    total = 0
    wins = 0
    for left in valid:
        for right in fp:
            total += 1
            if higher_is_valid_like:
                wins += int(left > right)
            else:
                wins += int(left < right)
    return float(wins / total) if total else None


def univariate_rows(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    valid = [row for row in events if row["human_class"] == HUMAN_VALID]
    fp = [row for row in events if row["human_class"] == HUMAN_FP]
    rows: list[dict[str, Any]] = []
    for field in NUMERIC_ANALYSIS_FIELDS:
        valid_vals = [_finite_float(row.get(field)) for row in valid]
        fp_vals = [_finite_float(row.get(field)) for row in fp]
        v_sum = numeric_summary(valid_vals)
        f_sum = numeric_summary(fp_vals)
        range_ov = overlap_interval(v_sum["min"], v_sum["max"], f_sum["min"], f_sum["max"])
        iqr_ov = overlap_interval(v_sum["q25"], v_sum["q75"], f_sum["q25"], f_sum["q75"])
        if v_sum["median"] is None or f_sum["median"] is None:
            direction = "NOT_AVAILABLE"
        elif v_sum["median"] > f_sum["median"]:
            direction = "VALID_HIGHER_MEDIAN"
        elif v_sum["median"] < f_sum["median"]:
            direction = "FP_HIGHER_MEDIAN"
        else:
            direction = "TIE_MEDIAN"
        contradiction = False
        contradiction_note = ""
        if v_sum["count"] and f_sum["count"]:
            if f_sum["max"] is not None and v_sum["median"] is not None and f_sum["max"] > v_sum["median"]:
                contradiction = True
                contradiction_note = "FP_MAX_ABOVE_VALID_MEDIAN"
            if v_sum["min"] is not None and f_sum["median"] is not None and v_sum["min"] < f_sum["median"] and contradiction:
                contradiction_note = "FP_MAX_ABOVE_VALID_MEDIAN_AND_VALID_MIN_BELOW_FP_MEDIAN"
            v_clean = [item for item in valid_vals if item is not None]
            f_clean = [item for item in fp_vals if item is not None]
            if v_clean and f_clean and max(f_clean) >= min(v_clean) and min(f_clean) <= max(v_clean):
                if any(fp_v >= vd for fp_v in f_clean for vd in v_clean):
                    if "THRESHOLD" in field.upper() or field == "evidence_value":
                        contradiction = True
        seed_valid = numeric_summary([_finite_float(row.get(field)) for row in valid if row["source_package"] == PACKAGE_SEED])
        seed_fp = numeric_summary([_finite_float(row.get(field)) for row in fp if row["source_package"] == PACKAGE_SEED])
        fresh_valid = numeric_summary([_finite_float(row.get(field)) for row in valid if row["source_package"] == PACKAGE_FRESH])
        fresh_fp = numeric_summary([_finite_float(row.get(field)) for row in fp if row["source_package"] == PACKAGE_FRESH])
        seed_dir = None
        fresh_dir = None
        if seed_valid["median"] is not None and seed_fp["median"] is not None:
            seed_dir = "VALID_HIGHER" if seed_valid["median"] > seed_fp["median"] else ("FP_HIGHER" if seed_valid["median"] < seed_fp["median"] else "TIE")
        if fresh_valid["median"] is not None and fresh_fp["median"] is not None:
            fresh_dir = "VALID_HIGHER" if fresh_valid["median"] > fresh_fp["median"] else ("FP_HIGHER" if fresh_valid["median"] < fresh_fp["median"] else "TIE")
        generalization = "INSUFFICIENT"
        if seed_dir and fresh_dir:
            generalization = "CONSISTENT" if seed_dir == fresh_dir else "SEED_ONLY_OR_REVERSED"
        elif seed_dir and not fresh_dir:
            generalization = "SEED_ONLY_PATTERN"
        elif fresh_dir and not seed_dir:
            generalization = "FRESH_ONLY_PATTERN"
        v_clean = [item for item in valid_vals if item is not None]
        f_clean = [item for item in fp_vals if item is not None]
        rows.append({
            "field": field,
            "formula": FEATURE_FORMULAS.get(field, ""),
            "valid_count": v_sum["count"],
            "valid_mean": v_sum["mean"],
            "valid_median": v_sum["median"],
            "valid_q25": v_sum["q25"],
            "valid_q75": v_sum["q75"],
            "valid_min": v_sum["min"],
            "valid_max": v_sum["max"],
            "fp_count": f_sum["count"],
            "fp_mean": f_sum["mean"],
            "fp_median": f_sum["median"],
            "fp_q25": f_sum["q25"],
            "fp_q75": f_sum["q75"],
            "fp_min": f_sum["min"],
            "fp_max": f_sum["max"],
            "range_overlap": range_ov["status"],
            "range_overlap_width": range_ov.get("overlap_width"),
            "iqr_overlap": iqr_ov["status"],
            "iqr_overlap_width": iqr_ov.get("overlap_width"),
            "sort_direction": direction,
            "contradiction": _csv_bool(contradiction),
            "contradiction_note": contradiction_note,
            "pairwise_ordering_rate_valid_gt_fp": pairwise_ordering_rate(v_clean, f_clean, higher_is_valid_like=True),
            "seed_sort_direction": seed_dir or "",
            "fresh_sort_direction": fresh_dir or "",
            "generalization": generalization,
            "seed_valid_median": seed_valid["median"],
            "seed_fp_median": seed_fp["median"],
            "fresh_valid_median": fresh_valid["median"],
            "fresh_fp_median": fresh_fp["median"],
            "seed_fp_count": seed_fp["count"],
            "fresh_fp_count": fresh_fp["count"],
        })
    return rows


def mode_summary_rows(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    valid = [row for row in events if row["human_class"] == HUMAN_VALID]
    valid_e = numeric_summary([_finite_float(row.get("evidence_value")) for row in valid])
    for mode in LEGAL_ERROR_MODES:
        subset = [row for row in events if row["human_class"] == HUMAN_FP and row["error_mode"] == mode]
        if not subset:
            rows.append({
                "error_mode": mode, "count": 0, "seed_count": 0, "fresh_count": 0,
                "episodes": "", "frames": "", "note": "none in DIRECTION_FP_COHORT",
            })
            continue
        e_sum = numeric_summary([_finite_float(row.get("evidence_value")) for row in subset])
        r_sum = numeric_summary([_finite_float(row.get("run_length")) for row in subset])
        s_sum = numeric_summary([_finite_float(row.get("local_speed_min")) for row in subset])
        d_sum = numeric_summary([_finite_float(row.get("min_displacement_m")) for row in subset])
        g_sum = numeric_summary([_finite_float(row.get("distance_to_nearest_gripper_final")) for row in subset])
        supports = Counter(str(row.get("support_combination") or "NONE") for row in subset)
        rows.append({
            "error_mode": mode,
            "count": len(subset),
            "seed_count": sum(1 for row in subset if row["source_package"] == PACKAGE_SEED),
            "fresh_count": sum(1 for row in subset if row["source_package"] == PACKAGE_FRESH),
            "episodes": "|".join(sorted({row["episode_id"] for row in subset})),
            "frames": "|".join(f"{native_key(row['episode_id'])}@{row['pred_frame']}" for row in subset),
            "evidence_min": e_sum["min"],
            "evidence_median": e_sum["median"],
            "evidence_max": e_sum["max"],
            "run_length_min": r_sum["min"],
            "run_length_median": r_sum["median"],
            "run_length_max": r_sum["max"],
            "local_speed_min_median": s_sum["median"],
            "min_displacement_median": d_sum["median"],
            "distance_to_gripper_median": g_sum["median"],
            "support_combinations": json.dumps(dict(supports), ensure_ascii=False),
            "evidence_vs_valid_median": (
                None if e_sum["median"] is None or valid_e["median"] is None
                else float(e_sum["median"] - valid_e["median"])
            ),
            "note": "",
        })
    return rows


def pairwise_analysis(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    valid = [row for row in events if row["human_class"] == HUMAN_VALID]
    fp = [row for row in events if row["human_class"] == HUMAN_FP]
    pairs = [
        ("evidence_value", "run_length"),
        ("evidence_value", "local_speed_min"),
        ("run_length", "min_displacement_m"),
        ("local_speed_min", "distance_to_nearest_gripper_final"),
    ]
    out: dict[str, Any] = {"method": "interpretable_2d_box_and_ordering", "classifier": "NONE"}
    reports = []
    for x_name, y_name in pairs:
        v_x = [_finite_float(row.get(x_name)) for row in valid]
        v_y = [_finite_float(row.get(y_name)) for row in valid]
        f_x = [_finite_float(row.get(x_name)) for row in fp]
        f_y = [_finite_float(row.get(y_name)) for row in fp]
        v_xmin = min((item for item in v_x if item is not None), default=None)
        v_ymin = min((item for item in v_y if item is not None), default=None)
        below_valid_min_box = []
        inside_valid_range = []
        for row, xv, yv in zip(fp, f_x, f_y):
            if xv is None or yv is None or v_xmin is None or v_ymin is None:
                continue
            label = f"{native_key(row['episode_id'])}@{row['pred_frame']}:{row['error_mode']}"
            if xv < v_xmin or yv < v_ymin:
                below_valid_min_box.append(label)
            else:
                inside_valid_range.append(label)
        reports.append({
            "x": x_name,
            "y": y_name,
            "valid_min_x": v_xmin,
            "valid_min_y": v_ymin,
            "fp_outside_valid_min_box": below_valid_min_box,
            "fp_inside_or_above_valid_min_box": inside_valid_range,
            "note": (
                "Raising both axes as lower bounds can remove FP outside the VALID min-box "
                "without removing VALID. FP inside that box cannot be removed by monotone "
                "AND-of-lower-bounds without VALID risk. This is SEARCH_RATIONALE, not a sweep."
            ),
        })
    out["pairs"] = reports
    return out


def classify_a0(events: Sequence[Mapping[str, Any]], uni: Sequence[Mapping[str, Any]], pairwise: Mapping[str, Any]) -> dict[str, Any]:
    by_field = {row["field"]: row for row in uni}
    evidence = by_field["evidence_value"]
    run_length = by_field["run_length"]
    threshold_overlap = evidence["range_overlap"] == "OVERLAP"
    persistence_overlap = run_length["range_overlap"] == "OVERLAP"
    evidence_contradiction = str(evidence["contradiction"]) == "true"
    persistence_contradiction = str(run_length["contradiction"]) == "true"
    threshold_risk = "HIGH" if threshold_overlap and evidence_contradiction else ("MEDIUM" if threshold_overlap else "LOW")
    persistence_risk = "HIGH" if persistence_overlap and (
        run_length["valid_min"] is not None and run_length["fp_max"] is not None
        and run_length["fp_max"] >= run_length["valid_min"]
    ) else ("MEDIUM" if persistence_overlap else "LOW")
    joint = next(item for item in pairwise["pairs"] if item["x"] == "evidence_value" and item["y"] == "run_length")
    joint_outside = list(joint["fp_outside_valid_min_box"])
    joint_inside = list(joint["fp_inside_or_above_valid_min_box"])
    fresh_fp = [row for row in events if row["human_class"] == HUMAN_FP and row["source_package"] == PACKAGE_FRESH]
    seed_fp = [row for row in events if row["human_class"] == HUMAN_FP and row["source_package"] == PACKAGE_SEED]
    mode_counts = Counter(row["error_mode"] for row in events if row["human_class"] == HUMAN_FP)

    derived_fields = [
        "local_speed_min", "min_displacement_m", "idle_fraction_in_window",
        "distance_to_nearest_gripper_final", "speed_drop_ratio",
    ]
    derived_consistent = []
    derived_seed_only = []
    for name in derived_fields:
        row = by_field[name]
        if row["generalization"] == "CONSISTENT":
            derived_consistent.append(name)
        elif row["generalization"] == "SEED_ONLY_PATTERN":
            derived_seed_only.append(name)

    if threshold_risk == "LOW" and persistence_risk in {"LOW", "MEDIUM"} and not joint_inside:
        classification = "THRESHOLD_PERSISTENCE_DISCRIMINABILITY"
        stage_a = "SUPPORTED"
        design = "NONE"
        reason = "evidence/run_length separate VALID vs FP with no high-evidence FP inside the VALID cloud"
    elif threshold_risk == "HIGH" and persistence_risk == "HIGH" and joint_inside and not derived_consistent:
        classification = "NO_INTERPRETABLE_DISCRIMINABILITY"
        stage_a = "NOT_SUPPORTED"
        design = "NONE"
        reason = "VALID and Direction FP overlap on evidence and run_length; no consistent derived Formal Signal split"
    elif threshold_risk == "HIGH" and (derived_consistent or joint_outside) and (len(fresh_fp) < 3 or derived_seed_only or joint_inside):
        classification = "MIXED_INSUFFICIENT"
        stage_a = "OWNER_REVIEW_REQUIRED"
        design = (
            "Candidate acceptance / context rule may be needed for overlapping high-evidence FP; "
            "not implementable in this round"
        )
        reason = (
            "threshold-only is contradicted by high-evidence FP; persistence overlap is large; "
            "some 2-feature / context patterns exist but Fresh Direction FP n is small and/or not all modes share one mechanism"
        )
    elif threshold_risk == "HIGH" and derived_consistent and not joint_inside:
        classification = "DERIVED_SIGNAL_DISCRIMINABILITY"
        stage_a = "NOT_SUPPORTED"
        design = "Formal Signal derived acceptance rule candidate; Design Review required before any search"
        reason = "threshold/persistence insufficient, but derived Formal Signals show a consistent VALID vs FP difference"
    else:
        classification = "MIXED_INSUFFICIENT"
        stage_a = "OWNER_REVIEW_REQUIRED"
        design = "Possibly a bounded Stage A search plus a Design-level acceptance rule; Owner must choose"
        reason = (
            "evidence/run_length are not cleanly separable (HIGH threshold-only risk) while some "
            "joint/context structure exists; Fresh Direction FP count is limited"
        )

    return {
        "THRESHOLD_ONLY_RISK": threshold_risk,
        "PERSISTENCE_ONLY_RISK": persistence_risk,
        "JOINT_FP_OUTSIDE_VALID_MIN_BOX": joint_outside,
        "JOINT_FP_INSIDE_VALID_MIN_BOX": joint_inside,
        "classification": classification,
        "STAGE_A_THRESHOLD_PERSISTENCE_SEARCH": stage_a,
        "DESIGN_CHANGE_CANDIDATE": design,
        "reason": reason,
        "fresh_direction_fp_count": len(fresh_fp),
        "seed_direction_fp_count": len(seed_fp),
        "mode_counts": dict(mode_counts),
        "derived_consistent_fields": derived_consistent,
        "derived_seed_only_fields": derived_seed_only,
        "evidence_range_overlap": evidence["range_overlap"],
        "run_length_range_overlap": run_length["range_overlap"],
    }


def _fmt(value: Any, digits: int = 6) -> str:
    number = _finite_float(value)
    if number is None:
        return ""
    if float(number).is_integer() and abs(number) < 1e12 and digits >= 0:
        if isinstance(value, int) or (isinstance(value, float) and number == int(number) and abs(number) < 1e9):
            if digits == 0 or (abs(number - round(number)) < 1e-12 and abs(number) >= 1):
                pass
    return f"{number:.16g}"


def render_event_row(row: Mapping[str, Any]) -> dict[str, Any]:
    out = {}
    for key in EVENT_FIELDS:
        value = row.get(key)
        if isinstance(value, bool):
            out[key] = _csv_bool(value)
        elif isinstance(value, float):
            out[key] = "" if not math.isfinite(value) else f"{value:.16g}"
        elif value is None:
            out[key] = ""
        else:
            out[key] = value
    return out


def build_event_features(
    item: Mapping[str, Any],
    *,
    tables: Mapping[str, Any],
    signals,
    p2_threshold: float,
    p2_persistence: int,
) -> dict[str, Any]:
    lineage = lineage_for_final(tables["finals"], tables["candidates"], item["pred_boundary_id"])
    if item["human_class"] == HUMAN_VALID and not lineage["is_independent_direction_final"]:
        raise StageA0Error(f"{item['pred_boundary_id']} is not an independent DIRECTION final")
    frame = int(item["pred_frame"])
    if int(lineage["candidate"]["frame"]) != frame or int(lineage["final"]["frame"]) != frame:
        raise StageA0Error(f"{item['pred_boundary_id']} frame lineage mismatch")
    run_length, run_prov = derive_run_length(
        signals.direction_change_evidence, frame, p2_threshold, p2_persistence
    )
    speed = speed_context(signals, frame, PRIMARY_WINDOW)
    diag = {f"local_speed_min_w{w}": speed_context(signals, frame, w)["local_speed_min"] for w in DIAGNOSTIC_WINDOWS}
    disp = displacement_context(signals, frame, PRIMARY_WINDOW)
    shape = peak_shape(signals.direction_change_evidence, frame, p2_threshold, PRIMARY_WINDOW)
    cand_gripper = _frames_of_type(tables["candidates"], "candidate_type", CANDIDATE_GRIPPER)
    final_gripper = _frames_of_type(tables["finals"], "candidate_type", CANDIDATE_GRIPPER)
    move_idle = _frames_of_type(tables["candidates"], "candidate_type", CANDIDATE_MOVE_TO_IDLE)
    idle_move = _frames_of_type(tables["candidates"], "candidate_type", CANDIDATE_IDLE_TO_MOVE)
    row = {
        **item,
        "member_candidate_count": lineage["member_candidate_count"],
        "member_candidate_types": lineage["member_candidate_types"],
        "evidence_value": lineage["evidence_value"],
        "evidence_value_provenance": "CANDIDATE_CSV_REPRESENTATIVE",
        "run_length": run_length,
        "run_length_provenance": run_prov,
        **speed,
        **diag,
        "diagnostic_window_note": "local_speed_min_w3/w5/w8 DIAGNOSTIC_ONLY; not a Detector parameter and not selected as optimal",
        **disp,
        **shape,
        "distance_to_nearest_move_to_idle": _min_abs_distance(frame, move_idle),
        "distance_to_nearest_idle_to_move": _min_abs_distance(frame, idle_move),
        "idle_context_provenance": "DIAGNOSTIC motion_state_candidate + candidate-type distances; not a Formal split rule",
        "distance_to_nearest_gripper_candidate": _min_abs_distance(frame, cand_gripper),
        "distance_to_nearest_gripper_final": _min_abs_distance(frame, final_gripper),
        "signed_distance_to_next_gripper": _signed_next(frame, final_gripper),
        "gripper_distance_provenance": "ANALYSIS_DERIVED from Candidate/Final lineage; consolidation window not modified",
        "rotation_support": lineage["rotation_support"],
        "action_support": lineage["action_support"],
        "support_combination": lineage["support_combination"],
        "support_provenance": "FINAL/CANDIDATE supporting_reasons; supporting only",
        "is_independent_direction_final": lineage["is_independent_direction_final"],
        "is_gripper_primary_merged": lineage["is_gripper_primary_merged"],
    }
    return row


def assert_no_privileged_fields(rows: Sequence[Mapping[str, Any]]) -> None:
    blob = json.dumps(list(rows), ensure_ascii=False).lower()
    for token in PRIVILEGED_TOKENS:
        if token in blob:
            raise StageA0Error(f"privileged token leaked into analysis rows: {token}")


def make_plots(events: Sequence[Mapping[str, Any]], plot_dir: Path) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_dir.mkdir(parents=True, exist_ok=True)
    valid = [row for row in events if row["human_class"] == HUMAN_VALID]
    fp = [row for row in events if row["human_class"] == HUMAN_FP]
    mode_color = {
        "MODE_01": "#d62728",
        "MODE_02": "#ff7f0e",
        "MODE_03": "#9467bd",
        "UNASSIGNED": "#8c564b",
        "": "#1f77b4",
    }
    written: list[str] = []

    def _label(row: Mapping[str, Any]) -> str:
        base = f"{native_key(row['episode_id'])}@{row['pred_frame']}"
        if row["human_class"] == HUMAN_FP:
            return f"{base}:{row['error_mode']}"
        return base

    def _scatter(ax, x_name, y_name, title):
        for row in valid:
            ax.scatter(_finite_float(row.get(x_name)), _finite_float(row.get(y_name)), c="#1f77b4", marker="o", s=36)
            ax.annotate(_label(row), (_finite_float(row.get(x_name)), _finite_float(row.get(y_name))), fontsize=6)
        for row in fp:
            ax.scatter(
                _finite_float(row.get(x_name)), _finite_float(row.get(y_name)),
                c=mode_color.get(row["error_mode"], "black"), marker="x", s=50,
            )
            ax.annotate(_label(row), (_finite_float(row.get(x_name)), _finite_float(row.get(y_name))), fontsize=6)
        ax.set_xlabel(x_name)
        ax.set_ylabel(y_name)
        ax.set_title(title)
        ax.grid(True, alpha=0.3)

    def _save(fig, name: str) -> None:
        path = plot_dir / name
        fig.tight_layout()
        fig.savefig(path, dpi=140)
        plt.close(fig)
        written.append(name)

    def _boxplot(ax, data, names):
        try:
            ax.boxplot(data, tick_labels=names)
        except TypeError:
            ax.boxplot(data, labels=names)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    _boxplot(
        ax,
        [
            [_finite_float(row["evidence_value"]) for row in valid],
            [_finite_float(row["evidence_value"]) for row in fp],
        ],
        ["VALID", "FP"],
    )
    rng = np.random.default_rng(0)
    for index, group in enumerate((valid, fp), start=1):
        xs = index + (rng.random(len(group)) - 0.5) * 0.12
        ys = [_finite_float(row["evidence_value"]) for row in group]
        colors = ["#1f77b4" if row["human_class"] == HUMAN_VALID else mode_color[row["error_mode"]] for row in group]
        ax.scatter(xs, ys, c=colors, zorder=3)
        for x, y, row in zip(xs, ys, group):
            ax.annotate(_label(row), (x, y), fontsize=6)
    ax.set_ylabel("evidence_value")
    ax.set_title("evidence_value VALID vs Direction FP")
    _save(fig, "01_evidence_value_valid_vs_fp.png")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    _boxplot(
        ax,
        [
            [_finite_float(row["run_length"]) for row in valid if _finite_float(row["run_length"]) is not None],
            [_finite_float(row["run_length"]) for row in fp if _finite_float(row["run_length"]) is not None],
        ],
        ["VALID", "FP"],
    )
    for index, group in enumerate((valid, fp), start=1):
        xs = index + (rng.random(len(group)) - 0.5) * 0.12
        ys = [_finite_float(row["run_length"]) for row in group]
        colors = ["#1f77b4" if row["human_class"] == HUMAN_VALID else mode_color[row["error_mode"]] for row in group]
        ax.scatter(xs, ys, c=colors, zorder=3)
        for x, y, row in zip(xs, ys, group):
            ax.annotate(_label(row), (x, y), fontsize=6)
    ax.set_ylabel("run_length")
    ax.set_title("run_length VALID vs Direction FP (ANALYSIS_DERIVED)")
    _save(fig, "02_run_length_valid_vs_fp.png")

    fig, ax = plt.subplots(figsize=(8, 5.5))
    _scatter(ax, "evidence_value", "run_length", "evidence_value x run_length")
    _save(fig, "03_evidence_vs_run_length.png")

    fig, ax = plt.subplots(figsize=(8, 5.5))
    _scatter(ax, "local_speed_min", "evidence_value", "local_speed_min x evidence_value")
    _save(fig, "04_local_speed_min_vs_evidence.png")

    fig, ax = plt.subplots(figsize=(8, 5.5))
    _scatter(ax, "pre_displacement_m", "post_displacement_m", "pre vs post displacement")
    _save(fig, "05_pre_post_displacement.png")

    fig, ax = plt.subplots(figsize=(8, 5.5))
    _scatter(ax, "distance_to_nearest_gripper_final", "evidence_value", "distance_to_nearest_gripper_final x evidence")
    _save(fig, "06_distance_to_nearest_gripper.png")

    key_fields = [
        "evidence_value", "run_length", "local_speed_min", "min_displacement_m",
        "idle_fraction_in_window", "distance_to_nearest_gripper_final",
        "heading_angle_rad", "speed_drop_ratio",
    ]
    matrix = []
    ylabels = []
    for row in list(valid) + list(fp):
        matrix.append([_finite_float(row.get(name)) for name in key_fields])
        ylabels.append(_label(row) + (" VALID" if row["human_class"] == HUMAN_VALID else " FP"))
    arr = np.array(matrix, dtype=np.float64)
    z = np.full_like(arr, np.nan)
    for col in range(arr.shape[1]):
        sl = arr[:, col]
        mask = np.isfinite(sl)
        if not np.any(mask):
            continue
        mu = float(np.nanmean(sl))
        sd = float(np.nanstd(sl))
        if sd == 0:
            z[mask, col] = 0.0
        else:
            z[mask, col] = (sl[mask] - mu) / sd
    fig, ax = plt.subplots(figsize=(11, max(6, 0.32 * len(ylabels) + 2)))
    im = ax.imshow(z, aspect="auto", cmap="coolwarm")
    ax.set_xticks(range(len(key_fields)))
    ax.set_xticklabels(key_fields, rotation=30, ha="right")
    ax.set_yticks(range(len(ylabels)))
    ax.set_yticklabels(ylabels, fontsize=7)
    ax.set_title("z-scored key features (visualization only; not a model)")
    fig.colorbar(im, ax=ax, fraction=0.03)
    _save(fig, "07_feature_heatmap_zscore_viz_only.png")
    return written


def write_findings(
    path: Path,
    *,
    meta: Mapping[str, Any],
    cohorts: Mapping[str, Any],
    uni: Sequence[Mapping[str, Any]],
    modes: Sequence[Mapping[str, Any]],
    pairwise: Mapping[str, Any],
    decision: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    non_direction: Sequence[Mapping[str, Any]],
) -> None:
    by_field = {row["field"]: row for row in uni}
    lines = [
        "# Stage A0 Direction Candidate Discriminability Findings",
        "",
        f"analysis_id = {meta['analysis_id']}",
        f"CALIBRATION_PROTOCOL_EFFECTIVE_VERSION = {CALIBRATION_PROTOCOL_EFFECTIVE_VERSION}",
        f"STAGE = {STAGE}",
        "PARAMETER_CHANGE_ALLOWED = NO",
        "PARAMETER_SEARCH_ALLOWED = NO",
        "FORMAL_SIGNAL_ONLY = YES",
        "PRIVILEGED_SIMULATOR_STATE_ALLOWED = NO",
        "",
        "## Cohorts",
        json.dumps(cohorts, indent=2, ensure_ascii=False),
        "",
        "## Evidence value",
        json.dumps(by_field["evidence_value"], indent=2, ensure_ascii=False, default=str),
        "",
        "## Run length",
        json.dumps(by_field["run_length"], indent=2, ensure_ascii=False, default=str),
        "",
        "## MODE summary",
        json.dumps(list(modes), indent=2, ensure_ascii=False, default=str),
        "",
        "## Pairwise (interpretable, no classifier)",
        json.dumps(pairwise, indent=2, ensure_ascii=False, default=str),
        "",
        "## Decision evidence",
        json.dumps(decision, indent=2, ensure_ascii=False, default=str),
        "",
        "## Heading homology",
        "heading_angle_rad uses the same pre/post heading_vector windows as direction_change_evidence.",
        "When both window displacements >= 0.005 m it is not an independent discriminator.",
        "",
        "## Non-direction FP",
        json.dumps(list(non_direction), indent=2, ensure_ascii=False, default=str),
        "",
        "## Explicit non-scope",
        "DETECTOR_MODIFIED = NO",
        "CONFIG_GENERATED = NO",
        "PARAMETER_SEARCH_EXECUTED = NO",
        "STAGE_A_EXECUTED = NO",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_stage_a0(*, project_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(project_root or PROJECT2_ROOT).resolve()
    score_root = root / "outputs/g1_p3_scoring" / EXPECTED_SCORE_ID
    run_root = root / "outputs/g1_audit_runs" / EXPECTED_RUN_ID
    if not score_root.is_dir():
        raise StageA0Error(f"missing frozen score {score_root}")
    score_meta = json.loads((score_root / "score_meta.json").read_text(encoding="utf-8"))
    if str(score_meta.get("score_id") or "") != EXPECTED_SCORE_ID:
        raise StageA0Error("score_id mismatch")
    if str(score_meta.get("run_id") or "") != EXPECTED_RUN_ID:
        raise StageA0Error("score run_id mismatch")
    if bool(score_meta.get("parameter_search_executed")):
        raise StageA0Error("frozen score claims parameter search")
    guardrails = json.loads((score_root / "guardrail_metrics.json").read_text(encoding="utf-8"))
    baseline_metrics = json.loads((score_root / "baseline_metrics.json").read_text(encoding="utf-8"))
    matching_pairs = _read_csv(score_root / "matching_pairs.csv")
    fp_rows = _read_csv(score_root / "unmatched_predictions_fp.csv")
    anchors = _read_csv(score_root / "known_fp_anchor_status.csv")

    snapshot = load_canonical_snapshot(root / "outputs/g1_p3_canonical_gt" / EXPECTED_SNAPSHOT_ID)
    p1 = load_g1_p1_config()
    p2 = load_g1_p2_config()
    if float(p2.direction_change_threshold) != FROZEN_DIRECTION_THRESHOLD:
        raise StageA0Error("frozen threshold mismatch")
    if int(p2.direction_persistence_frames) != FROZEN_DIRECTION_PERSISTENCE:
        raise StageA0Error("frozen persistence mismatch")
    if int(p1.exploratory.direction_window_frames) != FROZEN_WINDOW_FRAMES:
        raise StageA0Error("frozen P1 window mismatch")

    before = source_fingerprints(root)
    assert_known_fingerprints(before)

    valid = extract_valid_direction_cohort(matching_pairs)
    direction_fp, non_direction_fp = extract_fp_cohorts(fp_rows)
    attach_fp_package(direction_fp, anchors)
    attach_fp_package(non_direction_fp, anchors)
    if len(fp_rows) != 10:
        raise StageA0Error(f"TOTAL_FP derived {len(fp_rows)} != 10")
    if any(row["error_mode"] not in LEGAL_ERROR_MODES for row in direction_fp):
        raise StageA0Error("illegal Direction FP error_mode")

    needed = sorted({row["episode_id"] for row in valid + direction_fp + non_direction_fp})
    tables = {episode_id: load_episode_tables(run_root, episode_id) for episode_id in needed}
    adapter = build_can_mh_adapter(p1)
    signals_by_episode = {}
    for episode_id in needed:
        episode = load_formal_episode(adapter, episode_id)
        signals_by_episode[episode_id] = compute_formal_signals(episode, p1, include_motion_state_candidate=True)

    events: list[dict[str, Any]] = []
    for item in valid + direction_fp:
        events.append(
            build_event_features(
                item,
                tables=tables[item["episode_id"]],
                signals=signals_by_episode[item["episode_id"]],
                p2_threshold=float(p2.direction_change_threshold),
                p2_persistence=int(p2.direction_persistence_frames),
            )
        )
    events.sort(key=lambda row: (row["episode_id"], row["pred_frame"], row["pred_boundary_id"]))
    assert_no_privileged_fields(events)

    non_dir_out = []
    for item in non_direction_fp:
        episode_tables = tables[item["episode_id"]]
        gripper = _frames_of_type(episode_tables["finals"], "candidate_type", CANDIDATE_GRIPPER)
        direction = _frames_of_type(episode_tables["finals"], "candidate_type", CANDIDATE_DIRECTION)
        non_dir_out.append({
            "episode_id": item["episode_id"],
            "pred_boundary_id": item["pred_boundary_id"],
            "pred_frame": item["pred_frame"],
            "candidate_type": item["pred_candidate_type"],
            "reason_code": item["reason_code"],
            "error_mode": item["error_mode"],
            "source_package": item["source_package"],
            "representative_candidate_id": item["representative_candidate_id"],
            "distance_to_nearest_gripper_final": _min_abs_distance(item["pred_frame"], gripper),
            "distance_to_nearest_direction_final": _min_abs_distance(item["pred_frame"], direction),
            "member_candidate_types": item.get("member_candidate_types") or "",
        })

    uni = univariate_rows(events)
    modes = mode_summary_rows(events)
    pairwise = pairwise_analysis(events)
    decision = classify_a0(events, uni, pairwise)

    seed_valid = [row for row in valid if row["source_package"] == PACKAGE_SEED]
    fresh_valid = [row for row in valid if row["source_package"] == PACKAGE_FRESH]
    seed_fp = [row for row in direction_fp if row["source_package"] == PACKAGE_SEED]
    fresh_fp = [row for row in direction_fp if row["source_package"] == PACKAGE_FRESH]
    mode_counts = Counter(row["error_mode"] for row in direction_fp)
    cohorts = {
        "TOTAL_VALID_DIRECTION": len(valid),
        "SEED_VALID_DIRECTION": len(seed_valid),
        "FRESH_VALID_DIRECTION": len(fresh_valid),
        "TOTAL_FP": len(fp_rows),
        "DIRECTION_FP": len(direction_fp),
        "NON_DIRECTION_FP": len(non_direction_fp),
        "MODE_01": int(mode_counts.get("MODE_01", 0)),
        "MODE_02": int(mode_counts.get("MODE_02", 0)),
        "MODE_03": int(mode_counts.get("MODE_03", 0)),
        "UNASSIGNED": int(mode_counts.get("UNASSIGNED", 0)),
        "guardrails_read": {
            "CALIBRATION_GRIPPER_RECALL": guardrails["CALIBRATION_GRIPPER_RECALL"],
            "CALIBRATION_MERGED_CLUSTER_RECALL": guardrails["CALIBRATION_MERGED_CLUSTER_RECALL"],
            "SEED_VALID_DIRECTION_RECALL": guardrails["SEED_VALID_DIRECTION_RECALL"],
            "FRESH_VALID_DIRECTION_RECALL_BASELINE": guardrails["FRESH_VALID_DIRECTION_RECALL_BASELINE"],
            "FN_BASELINE": guardrails["FN_BASELINE"],
        },
        "baseline_metrics_read": {
            "TP": baseline_metrics["TP"],
            "FP": baseline_metrics["FP"],
            "FN": baseline_metrics["FN"],
            "Precision": baseline_metrics["Precision"],
            "Recall": baseline_metrics["Recall"],
            "F1": baseline_metrics["F1"],
            "NEW_UNANCHORED_FP_COUNT": baseline_metrics["NEW_UNANCHORED_FP_COUNT"],
        },
    }

    created_at = now_iso()
    stamp = created_at.replace(":", "").replace("-", "").replace("T", "_")[:15]
    digest = hashlib.sha256(
        f"{EXPECTED_RUN_ID}|{EXPECTED_SCORE_ID}|{EXPECTED_SNAPSHOT_ID}|{created_at}|{uuid.uuid4().hex}".encode("utf-8")
    ).hexdigest()[:8]
    analysis_id = f"g1_stage_a0_{stamp}_{digest}"
    out_root = root / "outputs/g1_p3_stage_a0"
    out_root.mkdir(parents=True, exist_ok=True)
    temp_path = out_root / f".tmp-{analysis_id}-{uuid.uuid4().hex}"
    final_path = out_root / analysis_id
    temp_path.mkdir(parents=False)

    meta = {
        "analysis_id": analysis_id,
        "created_at": created_at,
        "baseline_run_id": EXPECTED_RUN_ID,
        "baseline_score_id": EXPECTED_SCORE_ID,
        "canonical_gt_snapshot_id": EXPECTED_SNAPSHOT_ID,
        "config_hash": EXPECTED_CONFIG_HASH,
        "signal_contract_hash": EXPECTED_SIGNAL_HASH,
        "matching_rule_id": MATCHING_RULE_ID,
        "tolerance_frames": TOLERANCE_FRAMES,
        "stage": "A0",
        "calibration_protocol_effective_version": CALIBRATION_PROTOCOL_EFFECTIVE_VERSION,
        "parameter_search_executed": False,
        "detector_modified": False,
        "config_generated": False,
        "stage_a_executed": False,
        "formal_signal_only": True,
        "privileged_simulator_state_allowed": False,
        "run_length_provenance_policy": "ANALYSIS_DERIVED via persistent_high_runs at frozen T=1.2 P=3; Candidate CSV has no run_length column",
        "primary_window_frames": PRIMARY_WINDOW,
        "diagnostic_windows": list(DIAGNOSTIC_WINDOWS),
        "frozen_direction_change_threshold": FROZEN_DIRECTION_THRESHOLD,
        "frozen_direction_persistence_frames": FROZEN_DIRECTION_PERSISTENCE,
        "feature_formulas": FEATURE_FORMULAS,
        "snapshot_episode_count": int(snapshot["meta"]["episode_count"]),
        "classifier_trained": False,
        "threshold_sweep_executed": False,
    }

    try:
        plots_dir = temp_path / "plots"
        plot_names = make_plots(events, plots_dir)
        _write_csv(temp_path / "stage_a0_direction_event_analysis.csv", EVENT_FIELDS, [render_event_row(row) for row in events])
        uni_fields = list(uni[0].keys()) if uni else ["field"]
        _write_csv(temp_path / "stage_a0_feature_summary.csv", uni_fields, uni)
        mode_fields = list(modes[0].keys()) if modes else ["error_mode"]
        _write_csv(temp_path / "stage_a0_mode_summary.csv", mode_fields, modes)
        _write_csv(temp_path / "stage_a0_non_direction_fp.csv", NON_DIRECTION_FP_FIELDS, non_dir_out)
        (temp_path / "stage_a0_pairwise.json").write_text(
            json.dumps(pairwise, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (temp_path / "stage_a0_decision.json").write_text(
            json.dumps(decision, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (temp_path / "stage_a0_cohorts.json").write_text(
            json.dumps(cohorts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        write_findings(
            temp_path / "stage_a0_findings.md",
            meta=meta,
            cohorts=cohorts,
            uni=uni,
            modes=modes,
            pairwise=pairwise,
            decision=decision,
            events=events,
            non_direction=non_dir_out,
        )
        meta["plots"] = plot_names
        (temp_path / "stage_a0_meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        os.rename(temp_path, final_path)
    except Exception:
        if temp_path.exists():
            shutil.rmtree(temp_path)
        raise

    after = source_fingerprints(root)
    if after != before:
        shutil.rmtree(final_path)
        raise StageA0Error("source immutability check failed after Stage A0")
    immutability = {
        "BASELINE_RUN_UNCHANGED": after["baseline_run"] == before["baseline_run"],
        "BASELINE_SCORE_UNCHANGED": after["baseline_score"] == before["baseline_score"],
        "CANONICAL_GT_UNCHANGED": after["canonical_gt"] == KNOWN_FINGERPRINTS["canonical_gt"],
        "SEED_EXPORT_UNCHANGED": after["seed_export"] == KNOWN_FINGERPRINTS["seed_export"],
        "FRESH_EXPORT_UNCHANGED": after["fresh_export"] == KNOWN_FINGERPRINTS["fresh_export"],
        "OWNER_SQLITE_UNCHANGED": after["owner_sqlite"] == KNOWN_FINGERPRINTS["owner_sqlite"],
        "FROZEN_PROTOCOL_UNCHANGED": (
            after["protocol_v1"] == KNOWN_FINGERPRINTS["protocol_v1"]
            and after["protocol_v11"] == KNOWN_FINGERPRINTS["protocol_v11"]
        ),
        "DATASET_UNCHANGED": after["dataset"] == before["dataset"] and after["dataset"] is not None,
        "fingerprints": after,
    }
    if not all(value is True for key, value in immutability.items() if key != "fingerprints"):
        shutil.rmtree(final_path)
        raise StageA0Error(f"immutability failed: {immutability}")

    return {
        "analysis_id": analysis_id,
        "analysis_root": str(final_path),
        "meta": meta,
        "cohorts": cohorts,
        "decision": decision,
        "events": events,
        "univariate": uni,
        "modes": modes,
        "pairwise": pairwise,
        "non_direction_fp": non_dir_out,
        "immutability": immutability,
        "validator": "PASS",
    }
