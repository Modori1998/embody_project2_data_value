"""Export G1-P3 Rule Discovery Review evidence package (READ-ONLY).

Purpose
-------
Export the minimum event-level evidence that the web-side
``Rule Discovery Review`` needs, from the *existing immutable* G1-P3
artifacts, into ``0-doc/80-audit-local/g1_p3_rule_analysis/``:

* ``01_stage_a0_direction_event_analysis.csv`` — normalized copy of the
  frozen Stage A0 Direction event table (26 events).
* ``02_direction_event_window_trace.csv`` — NEW: event-centered ±12 frame
  per-frame trace with read-only analysis-derived context fields.

Hard constraints honoured by this script
----------------------------------------
* Does NOT modify Detector / Candidate Generation / Acceptance /
  Consolidation / Frozen Protocol / configs.
* Does NOT search parameters, select thresholds, train classifiers or
  emit any final rule.
* Does NOT read simulator object GT / reward / success / done / terminal
  semantics. Only Formal Signals (EEF position, Formal speed, Formal
  direction evidence, gripper, recorded action / rotation supporting
  info) plus the frozen Human calibration lineage are consumed.
* Deterministic: fixed sort (episode_id ASC, event_frame ASC, frame ASC),
  no random sampling. Re-running on identical inputs yields identical
  CSV bytes.

Window definition
-----------------
``ANALYSIS_EXPORT_WINDOW``: WINDOW_LEFT = 12 frames, WINDOW_RIGHT = 12
frames, i.e. relative_frame in [-12, +12] at 20 Hz => ±0.6 s.
This is an *analysis export window*, NOT a Detector parameter and it must
never be written into the Formal Detector Contract.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from project2_g1.config import load_g1_p1_config  # noqa: E402
from project2_g1.signals import compute_formal_signals  # noqa: E402
from project2_g1.source import build_can_mh_adapter, load_formal_episode  # noqa: E402

# --------------------------------------------------------------------------
# Frozen source identity (read-only inputs)
# --------------------------------------------------------------------------
STAGE_A0_ANALYSIS_ID = "g1_stage_a0_20260918_162418_7cbf826e"
BASELINE_RUN_ID = "g1_calibration_20260918_141032_781e5d8b"
BASELINE_SCORE_ID = "g1_baseline_score_20260918_155714_42295cc6"
CANONICAL_GT_SNAPSHOT_ID = "g1_canonical_gt_20260918_131636_c9916b89"
RULE_FAMILY_A_PREP_ID = "g1_rule_family_a_prep_20260918_173501"

STAGE_A0_ROOT = PROJECT_ROOT / "outputs" / "g1_p3_stage_a0" / STAGE_A0_ANALYSIS_ID
SOURCE_EVENT_CSV = STAGE_A0_ROOT / "stage_a0_direction_event_analysis.csv"

OUTPUT_DIR = PROJECT_ROOT / "0-doc" / "80-audit-local" / "g1_p3_rule_analysis"
ARTIFACT_1 = OUTPUT_DIR / "01_stage_a0_direction_event_analysis.csv"
ARTIFACT_2 = OUTPUT_DIR / "02_direction_event_window_trace.csv"

HUMAN_VALID = "VALID_DIRECTION"
HUMAN_FP = "DIRECTION_FP"
EVENT_TYPE = "DIRECTION_CHANGE"

WINDOW_LEFT = 12
WINDOW_RIGHT = 12
DT_S = 0.05  # 20 Hz frozen control frequency
CONTROL_HZ = 20.0
FROZEN_W8 = 8  # frozen P1 direction_window_frames (for the consistency check)
EPS = 1e-9

# Alias columns appended to artifact 1 so the web side can parse the
# required semantic names without renaming any frozen source column.
ARTIFACT_1_ALIAS_COLUMNS = ("event_frame", "event_type", "support")

TRACE_COLUMNS = (
    # identity
    "episode_id", "episode_key", "event_frame", "frame", "relative_frame",
    "time_relative_s", "human_class", "source_package", "error_mode", "event_type",
    # motion (Formal Signals, per frame)
    "eef_x", "eef_y", "eef_z",
    "step_dx", "step_dy", "step_dz",
    "step_displacement_m", "translation_speed_mps", "smoothed_speed_mps",
    # direction
    "direction_evidence", "heading_angle_rad_event",
    # derived context (event-level, repeated on every trace row)
    "left_speed_reference", "right_speed_reference", "event_speed_reference",
    "speed_valley_ratio_left", "speed_valley_ratio_right", "speed_valley_ratio_min",
    "left_path_length_m", "right_path_length_m",
    "left_net_displacement_m", "right_net_displacement_m",
    "left_straightness", "right_straightness",
    "left_to_right_cosine", "turn_angle_rad",
    "window_left_frames", "window_right_frames", "edge_clipped",
    "episode_n_frames",
    # gripper (Formal Signals, per frame)
    "gripper_value", "gripper_change_evidence",
    # supporting context (event-level, repeated; supporting only)
    "rotation_support_flag", "action_support_flag",
)

# Required critical counterexamples that must be directly filterable.
REQUIRED_FP_EVENTS = (
    ("demo_242", 41), ("demo_242", 60), ("demo_242", 78),
    ("demo_278", 83), ("demo_278", 105), ("demo_278", 125),
    ("demo_242", 136), ("demo_162", 211), ("demo_255", 116),
)
REQUIRED_VALID_EVENTS = (
    ("demo_242", 224), ("demo_255", 14), ("demo_260", 75),
)


class ExportError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ExportError(f"{path}: missing header")
        fields = list(reader.fieldnames)
        return fields, [dict(row) for row in reader]


def write_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
    *,
    format_values: bool = False,
) -> None:
    """Write a CSV.

    ``format_values=False`` keeps source strings byte-faithful (artifact 1 is a
    normalization of a frozen artifact and must not be re-rounded).
    ``format_values=True`` renders numbers through :func:`fmt` (artifact 2).

    ``lineterminator="\\n"`` is set explicitly so the written bytes are the
    canonical LF form. Python's ``csv`` module defaults to ``\\r\\n``, which this
    repository's ``core.autocrlf=true`` would silently rewrite to LF on commit —
    making the committed GitHub blob differ from the hashed working-tree file.
    Writing LF keeps the working tree, the git blob and the GitHub SSOT artifact
    byte-identical, so the SHA256 recorded in README.md is verifiable.
    """
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fieldnames),
            extrasaction="raise",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            if format_values:
                writer.writerow({key: fmt(row.get(key)) for key in fieldnames})
            else:
                writer.writerow({key: "" if row.get(key) is None else row[key] for key in fieldnames})


def fmt(value: Any) -> str:
    """Deterministic float rendering; NaN/inf collapse to empty (NA)."""
    if value is None or value == "":
        return ""
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return ""
    return f"{number:.16g}"


def finite(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def safe_median(values: np.ndarray) -> float | None:
    if len(values) == 0:
        return None
    return float(np.median(values))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def native_key(episode_id: str) -> str:
    return episode_id.split("/", 1)[-1]


# --------------------------------------------------------------------------
# artifact 1
# --------------------------------------------------------------------------
def build_artifact_1() -> tuple[list[str], list[dict[str, str]], list[dict[str, str]]]:
    fields, rows = read_csv_rows(SOURCE_EVENT_CSV)
    cohort = [row for row in rows if row.get("human_class") in (HUMAN_VALID, HUMAN_FP)]
    cohort.sort(key=lambda row: (row["episode_id"], int(row["pred_frame"])))

    valid_n = sum(1 for row in cohort if row["human_class"] == HUMAN_VALID)
    fp_n = sum(1 for row in cohort if row["human_class"] == HUMAN_FP)
    if len(cohort) != 26 or valid_n != 17 or fp_n != 9:
        raise ExportError(
            f"unexpected Stage A0 cohort: total={len(cohort)} valid={valid_n} fp={fp_n}"
        )

    out_fields = list(fields) + [name for name in ARTIFACT_1_ALIAS_COLUMNS if name not in fields]
    out_rows: list[dict[str, str]] = []
    for row in cohort:
        payload = dict(row)
        payload["event_frame"] = str(int(row["pred_frame"]))
        payload["event_type"] = EVENT_TYPE
        payload["support"] = str(row.get("support_combination") or "NONE")
        out_rows.append(payload)
    return out_fields, out_rows, cohort


# --------------------------------------------------------------------------
# derived analysis fields
# --------------------------------------------------------------------------
def compute_event_context(signals, frame: int) -> dict[str, Any]:
    """Read-only ANALYSIS_DERIVED_FIELD context for one Direction event.

    Window convention follows the frozen W=8 definition
    (``heading_vector(signals, a, b) == sum(delta[a:b])``) widened to the
    ±12 frame ANALYSIS_EXPORT_WINDOW, so the new fields are directly
    comparable in functional form to ``pre_/post_displacement_m``.
    """

    n = int(signals.n_frames)
    t = int(frame)
    delta = np.stack([signals.delta_x, signals.delta_y, signals.delta_z], axis=1)
    step = np.asarray(signals.translation_step_norm, dtype=np.float64)
    speed = np.asarray(signals.translation_speed, dtype=np.float64)

    left_lo = max(0, t - WINDOW_LEFT)
    right_hi = min(n, t + WINDOW_RIGHT)

    left_vec = np.sum(delta[left_lo:t], axis=0) if t > left_lo else np.zeros(3)
    right_vec = np.sum(delta[t:right_hi], axis=0) if right_hi > t else np.zeros(3)
    left_net = float(np.linalg.norm(left_vec))
    right_net = float(np.linalg.norm(right_vec))
    left_path = float(np.sum(step[left_lo:t])) if t > left_lo else 0.0
    right_path = float(np.sum(step[t:right_hi])) if right_hi > t else 0.0

    left_straightness = left_net / left_path if left_path > EPS else None
    right_straightness = right_net / right_path if right_path > EPS else None

    if left_net > EPS and right_net > EPS:
        cosine = float(np.dot(left_vec, right_vec) / (left_net * right_net))
        cosine = float(np.clip(cosine, -1.0, 1.0))
        turn_angle: float | None = float(np.arccos(cosine))
    else:
        cosine = None
        turn_angle = None

    # relative-frame based speed references (event-level analysis fields)
    def rel_slice(lo: int, hi: int) -> np.ndarray:
        a = max(0, t + lo)
        b = min(n, t + hi + 1)
        return speed[a:b] if b > a else np.array([], dtype=np.float64)

    left_ref = safe_median(rel_slice(-WINDOW_LEFT, -4))
    right_ref = safe_median(rel_slice(4, WINDOW_RIGHT))
    event_window = rel_slice(-2, 2)
    event_ref = float(np.min(event_window)) if len(event_window) else None

    def ratio(numerator: float | None, denominator: float | None) -> float | None:
        if numerator is None or denominator is None:
            return None
        if abs(denominator) < EPS:
            return None  # near-zero denominator -> NaN, never hard-divide
        return float(numerator / denominator)

    ratio_left = ratio(event_ref, left_ref)
    ratio_right = ratio(event_ref, right_ref)
    ratio_min = None
    if ratio_left is not None and ratio_right is not None:
        ratio_min = float(min(ratio_left, ratio_right))
    elif ratio_left is not None or ratio_right is not None:
        ratio_min = ratio_left if ratio_left is not None else ratio_right

    left_frames = int(t - left_lo)
    right_frames = int(right_hi - t)
    clipped = bool(left_frames < WINDOW_LEFT or right_frames < WINDOW_RIGHT)

    # frozen W=8 consistency check vs Stage A0 pre_/post_displacement_m
    w8_lo = max(0, t - FROZEN_W8)
    w8_hi = min(n, t + FROZEN_W8)
    pre_w8 = float(np.linalg.norm(np.sum(delta[w8_lo:t], axis=0))) if t > w8_lo else 0.0
    post_w8 = float(np.linalg.norm(np.sum(delta[t:w8_hi], axis=0))) if w8_hi > t else 0.0

    return {
        "left_speed_reference": left_ref,
        "right_speed_reference": right_ref,
        "event_speed_reference": event_ref,
        "speed_valley_ratio_left": ratio_left,
        "speed_valley_ratio_right": ratio_right,
        "speed_valley_ratio_min": ratio_min,
        "left_path_length_m": left_path,
        "right_path_length_m": right_path,
        "left_net_displacement_m": left_net,
        "right_net_displacement_m": right_net,
        "left_straightness": left_straightness,
        "right_straightness": right_straightness,
        "left_to_right_cosine": cosine,
        "turn_angle_rad": turn_angle,
        "window_left_frames": left_frames,
        "window_right_frames": right_frames,
        "edge_clipped": clipped,
        "episode_n_frames": n,
        "_pre_w8": pre_w8,
        "_post_w8": post_w8,
    }


# --------------------------------------------------------------------------
# artifact 2
# --------------------------------------------------------------------------
def build_artifact_2(
    cohort: Sequence[Mapping[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    config = load_g1_p1_config()
    adapter = build_can_mh_adapter(config)

    episode_ids = sorted({str(row["episode_id"]) for row in cohort})
    signals_by_episode = {}
    for episode_id in episode_ids:
        episode = load_formal_episode(adapter, episode_id)
        signals_by_episode[episode_id] = compute_formal_signals(
            episode, config, include_motion_state_candidate=True
        )

    events = sorted(cohort, key=lambda row: (row["episode_id"], int(row["pred_frame"])))
    trace_rows: list[dict[str, Any]] = []
    event_contexts: list[dict[str, Any]] = []

    for row in events:
        episode_id = str(row["episode_id"])
        key = native_key(episode_id)
        event_frame = int(row["pred_frame"])
        signals = signals_by_episode[episode_id]
        n = int(signals.n_frames)
        ctx = compute_event_context(signals, event_frame)

        evidence_at_event = float(signals.direction_change_evidence[event_frame])
        heading_event = finite(row.get("heading_angle_rad"))
        rotation_flag = str(row.get("rotation_support") or "").lower() == "true"
        action_flag = str(row.get("action_support") or "").lower() == "true"

        context_identity = {
            "episode_id": episode_id,
            "episode_key": key,
            "event_frame": event_frame,
            "human_class": row["human_class"],
            "source_package": row.get("source_package", ""),
            "error_mode": row.get("error_mode", ""),
            "event_type": EVENT_TYPE,
        }
        context_derived = {
            name: ctx[name]
            for name in (
                "left_speed_reference", "right_speed_reference", "event_speed_reference",
                "speed_valley_ratio_left", "speed_valley_ratio_right", "speed_valley_ratio_min",
                "left_path_length_m", "right_path_length_m",
                "left_net_displacement_m", "right_net_displacement_m",
                "left_straightness", "right_straightness",
                "left_to_right_cosine", "turn_angle_rad",
                "window_left_frames", "window_right_frames", "edge_clipped",
                "episode_n_frames",
            )
        }
        context_support = {
            "heading_angle_rad_event": heading_event,
            "rotation_support_flag": rotation_flag,
            "action_support_flag": action_flag,
        }

        event_contexts.append({
            **context_identity,
            **context_derived,
            "direction_evidence_at_event": evidence_at_event,
            "stage_a0_evidence_value": finite(row.get("evidence_value")),
            "stage_a0_pre_displacement_m": finite(row.get("pre_displacement_m")),
            "stage_a0_post_displacement_m": finite(row.get("post_displacement_m")),
            "recomputed_pre_w8_m": ctx["_pre_w8"],
            "recomputed_post_w8_m": ctx["_post_w8"],
        })

        lo = max(0, event_frame - WINDOW_LEFT)
        hi = min(n, event_frame + WINDOW_RIGHT + 1)
        for frame in range(lo, hi):
            rel = frame - event_frame
            trace_rows.append({
                **context_identity,
                "frame": frame,
                "relative_frame": rel,
                "time_relative_s": rel / CONTROL_HZ,
                "eef_x": float(signals.eef_x[frame]),
                "eef_y": float(signals.eef_y[frame]),
                "eef_z": float(signals.eef_z[frame]),
                "step_dx": float(signals.delta_x[frame]),
                "step_dy": float(signals.delta_y[frame]),
                "step_dz": float(signals.delta_z[frame]),
                "step_displacement_m": float(signals.translation_step_norm[frame]),
                "translation_speed_mps": float(signals.translation_speed[frame]),
                "smoothed_speed_mps": float(signals.smoothed_translation_speed[frame]),
                "direction_evidence": float(signals.direction_change_evidence[frame]),
                "gripper_value": float(signals.gripper_aperture[frame]),
                "gripper_change_evidence": float(signals.gripper_change_evidence[frame]),
                **context_derived,
                **context_support,
            })

    trace_rows.sort(
        key=lambda item: (item["episode_id"], item["event_frame"], item["frame"])
    )
    event_contexts.sort(key=lambda item: (item["episode_id"], item["event_frame"]))
    return trace_rows, event_contexts, {"signals": signals_by_episode}


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------
def validate(
    *,
    artifact_1_rows: Sequence[Mapping[str, str]],
    trace_rows: Sequence[Mapping[str, Any]],
    event_contexts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    report: dict[str, Any] = {}

    report["event_count"] = len(artifact_1_rows)
    report["valid_direction_count"] = sum(
        1 for row in artifact_1_rows if row["human_class"] == HUMAN_VALID
    )
    report["direction_fp_count"] = sum(
        1 for row in artifact_1_rows if row["human_class"] == HUMAN_FP
    )

    trace_keys = {(row["episode_id"], row["event_frame"]) for row in trace_rows}
    report["trace_event_count"] = len(trace_keys)
    report["trace_rows"] = len(trace_rows)

    # duplicate key (episode_id, event_frame, frame)
    dup = Counter((row["episode_id"], row["event_frame"], row["frame"]) for row in trace_rows)
    report["duplicate_keys"] = sum(1 for _, count in dup.items() if count > 1)

    # relative_frame range
    rel_values = sorted({int(row["relative_frame"]) for row in trace_rows})
    report["relative_frame_min"] = rel_values[0]
    report["relative_frame_max"] = rel_values[-1]
    report["relative_frame_full_span"] = rel_values == list(range(-WINDOW_LEFT, WINDOW_RIGHT + 1))

    # inf / NaN audit
    inf_fields: Counter = Counter()
    nan_fields: Counter = Counter()
    for row in trace_rows:
        for key, value in row.items():
            if isinstance(value, bool):
                continue
            if isinstance(value, float):
                if math.isinf(value):
                    inf_fields[key] += 1
                elif math.isnan(value):
                    nan_fields[key] += 1
    report["inf_count"] = int(sum(inf_fields.values()))
    report["inf_fields"] = dict(inf_fields)
    report["nan_fields"] = dict(nan_fields)

    # event-level tables must agree
    trace_meta = {
        (row["episode_id"], row["event_frame"]): (
            row["human_class"], row["error_mode"], row["source_package"]
        )
        for row in trace_rows
    }
    a1_meta = {
        (row["episode_id"], int(row["pred_frame"])): (
            row["human_class"], row.get("error_mode", ""), row.get("source_package", "")
        )
        for row in artifact_1_rows
    }
    report["identity_consistent"] = trace_meta == a1_meta

    # critical coverage
    coverage: dict[str, bool] = {}
    for key, frame in REQUIRED_FP_EVENTS + REQUIRED_VALID_EVENTS:
        label = f"{key}@{frame}"
        coverage[label] = any(
            native_key(row["episode_id"]) == key and int(row["event_frame"]) == frame
            for row in trace_rows
        )
    report["critical_coverage"] = coverage

    # direction evidence alignment at the event frame
    evidence_deltas = []
    for ctx in event_contexts:
        if ctx["stage_a0_evidence_value"] is None:
            continue
        evidence_deltas.append(abs(ctx["direction_evidence_at_event"] - ctx["stage_a0_evidence_value"]))
    report["evidence_max_abs_delta"] = max(evidence_deltas) if evidence_deltas else None

    # W=8 displacement consistency vs Stage A0
    pre_deltas = []
    post_deltas = []
    for ctx in event_contexts:
        if ctx["stage_a0_pre_displacement_m"] is not None:
            pre_deltas.append(abs(ctx["recomputed_pre_w8_m"] - ctx["stage_a0_pre_displacement_m"]))
        if ctx["stage_a0_post_displacement_m"] is not None:
            post_deltas.append(abs(ctx["recomputed_post_w8_m"] - ctx["stage_a0_post_displacement_m"]))
    report["pre_displacement_max_abs_delta"] = max(pre_deltas) if pre_deltas else None
    report["post_displacement_max_abs_delta"] = max(post_deltas) if post_deltas else None

    return report


def audit_written_csv(path: Path) -> dict[str, Any]:
    """Read the written artifact back and audit literal inf / nan tokens."""
    fields, rows = read_csv_rows(path)
    inf_cells: Counter = Counter()
    nan_cells: Counter = Counter()
    for row in rows:
        for key in fields:
            raw = (row.get(key) or "").strip().lower()
            if raw in ("inf", "-inf", "+inf", "infinity", "-infinity"):
                inf_cells[key] += 1
            elif raw in ("nan", "-nan"):
                nan_cells[key] += 1
    return {
        "rows": len(rows),
        "columns": len(fields),
        "inf_cells": dict(inf_cells),
        "nan_cells": dict(nan_cells),
    }


def render_report(report: Mapping[str, Any], sizes: Mapping[str, int], hashes: Mapping[str, str]) -> str:
    lines = ["", "=" * 74, "G1-P3 RULE ANALYSIS EVIDENCE EXPORT — VALIDATION", "=" * 74]
    lines.append(f"event_count                 = {report['event_count']}")
    lines.append(
        f"cohort                      = VALID_DIRECTION {report['valid_direction_count']}"
        f" + DIRECTION_FP {report['direction_fp_count']}"
    )
    lines.append(f"trace_rows                  = {report['trace_rows']}")
    lines.append(f"trace_unique_events         = {report['trace_event_count']}")
    lines.append(
        f"relative_frame_range        = {report['relative_frame_min']} .. {report['relative_frame_max']}"
        f"  (full -12..+12 span = {report['relative_frame_full_span']})"
    )
    lines.append(f"duplicate_keys              = {report['duplicate_keys']}")
    lines.append(f"inf_count                   = {report['inf_count']}  fields={report['inf_fields']}")
    lines.append(f"nan_fields                  = {report['nan_fields']}")
    lines.append(f"identity_consistent         = {report['identity_consistent']}")
    lines.append(f"written_trace_inf_cells     = {report['written_trace_audit']['inf_cells']}")
    lines.append(f"written_trace_nan_cells     = {report['written_trace_audit']['nan_cells']}")
    lines.append(f"evidence_max_abs_delta      = {report['evidence_max_abs_delta']}")
    lines.append(f"pre_displacement_max_delta  = {report['pre_displacement_max_abs_delta']}")
    lines.append(f"post_displacement_max_delta = {report['post_displacement_max_abs_delta']}")
    lines.append("")
    lines.append("critical event coverage:")
    for label, ok in report["critical_coverage"].items():
        lines.append(f"  {label:<18} = {'PRESENT' if ok else 'MISSING'}")
    lines.append("")
    for name in (ARTIFACT_1.name, ARTIFACT_2.name, "README.md"):
        lines.append(f"{name:<44} size={sizes.get(name, 0):>9}  sha256={hashes.get(name, '')}")
    lines.append("=" * 74)
    return "\n".join(lines)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="recompute and compare against the committed CSV bytes (determinism check)",
    )
    args = parser.parse_args(argv)

    if not SOURCE_EVENT_CSV.is_file():
        raise ExportError(f"missing frozen Stage A0 event table: {SOURCE_EVENT_CSV}")

    a1_fields, a1_rows, cohort = build_artifact_1()
    trace_rows, event_contexts, _ = build_artifact_2(cohort)

    if args.check:
        a1_before = ARTIFACT_1.read_bytes()
        a2_before = ARTIFACT_2.read_bytes()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(ARTIFACT_1, a1_fields, a1_rows)
    write_csv(ARTIFACT_2, TRACE_COLUMNS, trace_rows, format_values=True)

    if args.check:
        if a1_before != ARTIFACT_1.read_bytes() or a2_before != ARTIFACT_2.read_bytes():
            raise ExportError("DETERMINISM_FAILURE: re-run produced different bytes")
        print("determinism check: PASS (byte-identical re-run)")

    report = validate(
        artifact_1_rows=a1_rows, trace_rows=trace_rows, event_contexts=event_contexts
    )
    report["written_trace_audit"] = audit_written_csv(ARTIFACT_2)
    report["written_event_audit"] = audit_written_csv(ARTIFACT_1)

    sizes = {
        ARTIFACT_1.name: ARTIFACT_1.stat().st_size,
        ARTIFACT_2.name: ARTIFACT_2.stat().st_size,
        "README.md": (OUTPUT_DIR / "README.md").stat().st_size
        if (OUTPUT_DIR / "README.md").is_file()
        else 0,
    }
    hashes = {
        ARTIFACT_1.name: sha256_file(ARTIFACT_1),
        ARTIFACT_2.name: sha256_file(ARTIFACT_2),
        "README.md": sha256_file(OUTPUT_DIR / "README.md")
        if (OUTPUT_DIR / "README.md").is_file()
        else "",
    }

    print(render_report(report, sizes, hashes))

    # File size gate
    if sizes[ARTIFACT_1.name] >= 1_000_000:
        raise ExportError("TRACE_EXPORT_TOO_LARGE: artifact 1 >= 1 MB")
    if sizes[ARTIFACT_2.name] >= 5_000_000:
        raise ExportError("TRACE_EXPORT_TOO_LARGE: trace >= 5 MB")
    if report["inf_count"] != 0:
        raise ExportError("INF_FOUND_IN_TRACE")
    if report["written_trace_audit"]["inf_cells"]:
        raise ExportError("INF_TOKEN_IN_WRITTEN_TRACE")
    if report["duplicate_keys"] != 0:
        raise ExportError("DUPLICATE_TRACE_KEYS")
    if not all(report["critical_coverage"].values()):
        raise ExportError("CRITICAL_EVENT_MISSING")
    if not report["identity_consistent"]:
        raise ExportError("EVENT_IDENTITY_INCONSISTENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
