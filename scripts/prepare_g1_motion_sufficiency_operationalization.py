"""Prepare G1-P3 Motion Sufficiency operationalization evidence (READ-ONLY).

Purpose
-------
Answer, *without* selecting any numeric threshold, which existing / derived
field best expresses the two FROZEN rule-shape conditions

* ``POST_MOTION_SUFFICIENCY``
* ``TRAJECTORY_COHERENCE``

for the frozen Calibration Direction cohort (17 VALID + 9 DIRECTION_FP = 26).

Inputs (GitHub-tracked, immutable, never rewritten by this script)
-----------------------------------------------------------------
* ``0-doc/80-audit-local/g1_p3_rule_analysis/01_stage_a0_direction_event_analysis.csv``
* ``0-doc/80-audit-local/g1_p3_rule_analysis/02_direction_event_window_trace.csv``

Outputs (new, LF-only, UTF-8, no BOM)
-------------------------------------
* ``.../g1_p3_rule_analysis/03_motion_sufficiency_operationalization_event.csv``
* ``.../g1_p3_rule_analysis/04_motion_sufficiency_operationalization_summary.csv``

Candidate operational definitions compared (exactly four, no sweep)
------------------------------------------------------------------
Post-motion Sufficiency
  P8  = ``post_speed_mean``  (Stage A0 existing field, W=8)
        = mean(translation_speed_mps) over relative_frame in [0, +7]
  P12 = ``right_speed_reference`` (ANALYSIS_DERIVED_FIELD)
        = median(translation_speed_mps) over relative_frame in [+4, +12]

Trajectory Coherence
  C8  = min(left_straightness_w8, right_straightness_w8), re-derived here from
        the trace (left relative_frame [-8,-1], right relative_frame [0,+7]).
  C12 = min(left_straightness, right_straightness) at the event-frame row
        (existing W=12 analysis context).

Hard constraints honoured by this script
----------------------------------------
* Does NOT modify Detector / Candidate Generation / Acceptance /
  Consolidation / Frozen Protocol / configs.
* Does NOT search parameters, select thresholds, train classifiers, build
  decision trees or perform automatic feature selection.
* Does NOT sweep additional windows (only W8 vs W12 are compared).
* Does NOT introduce acceleration / jerk / curvature / action / rotation /
  gripper / heading feature families.
* Does NOT read Web SQLite, privileged simulator state, object pose, reward,
  success, done or terminal semantics.
* Does NOT regenerate or modify the two existing evidence CSVs.
* Deterministic: fixed sort (episode_id ASC, event_frame ASC), no random
  sampling. Re-running on identical inputs yields identical CSV bytes.

The ``VALID_FLOOR`` emitted here is a *Calibration Envelope Diagnostic*
(VALID minimum), explicitly NOT a Detector threshold.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
EVIDENCE_DIR = PROJECT_ROOT / "0-doc" / "80-audit-local" / "g1_p3_rule_analysis"

EVENT_CSV_IN = EVIDENCE_DIR / "01_stage_a0_direction_event_analysis.csv"
TRACE_CSV_IN = EVIDENCE_DIR / "02_direction_event_window_trace.csv"

EVENT_CSV_OUT = EVIDENCE_DIR / "03_motion_sufficiency_operationalization_event.csv"
SUMMARY_CSV_OUT = EVIDENCE_DIR / "04_motion_sufficiency_operationalization_summary.csv"

# ---------------------------------------------------------------------------
# Frozen cohort / window constants

EXPECTED_EVENT_ROWS = 26
EXPECTED_VALID = 17
EXPECTED_FP = 9

VALID_CLASS = "VALID_DIRECTION"
FP_CLASS = "DIRECTION_FP"

# P8: frozen W=8 post window, half-open heading convention -> frames [0, +7].
P8_WINDOW = (0, 7)
# P12: existing analysis sustained post-motion reference window.
P12_WINDOW = (4, 12)
# C8: re-derived W=8 straightness windows.
C8_LEFT_WINDOW = (-8, -1)
C8_RIGHT_WINDOW = (0, 7)
# C12: existing analysis W=12 straightness windows (consistency re-check only).
C12_LEFT_WINDOW = (-12, -1)
C12_RIGHT_WINDOW = (0, 11)

# Degenerate-path guard: path_length below this -> NaN, never a huge ratio.
PATH_EPS = 1e-9

# Critical events that MUST be present (coverage gate).
CRITICAL_EVENTS: tuple[tuple[str, int], ...] = (
    ("demo_242", 41),
    ("demo_242", 60),
    ("demo_242", 78),
    ("demo_278", 83),
    ("demo_278", 105),
    ("demo_278", 125),
    ("demo_242", 136),
    ("demo_162", 211),
    ("demo_255", 116),
    ("demo_242", 224),
    ("demo_255", 14),
    ("demo_260", 75),
)

FEATURES = ("P8", "P12", "C8", "C12")

COHORTS = (
    "VALID",
    "FP",
    "ALL",
    "SEED_VALID",
    "FRESH_VALID",
    "SEED_FP",
    "FRESH_FP",
)


# ---------------------------------------------------------------------------
# Small deterministic numeric helpers (testable, stdlib only)


def norm3(dx: float, dy: float, dz: float) -> float:
    """Euclidean norm of a 3-vector."""
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def path_length(steps: Sequence[Mapping[str, Any]]) -> float:
    """Path length = sum of per-frame ``step_displacement_m`` over the window."""
    return math.fsum(float(s["step_displacement_m"]) for s in steps)


def net_displacement(steps: Sequence[Mapping[str, Any]]) -> float:
    """Net displacement = norm of the summed per-frame delta vector."""
    sx = math.fsum(float(s["step_dx"]) for s in steps)
    sy = math.fsum(float(s["step_dy"]) for s in steps)
    sz = math.fsum(float(s["step_dz"]) for s in steps)
    return norm3(sx, sy, sz)


def straightness(steps: Sequence[Mapping[str, Any]]) -> float:
    """Straightness = net_displacement / path_length, NaN if path is degenerate."""
    if not steps:
        return float("nan")
    total = path_length(steps)
    if total < PATH_EPS:
        return float("nan")
    return net_displacement(steps) / total


def quantile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolation quantile (deterministic, numpy-compatible default)."""
    if not sorted_values:
        return float("nan")
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    pos = q * (len(sorted_values) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_values[lo])
    frac = pos - lo
    return float(sorted_values[lo]) + (float(sorted_values[hi]) - float(sorted_values[lo])) * frac


def distribution(values: Iterable[float]) -> dict[str, float]:
    """n / min / q25 / median / q75 / max for a cohort (NaN-aware)."""
    clean = sorted(float(v) for v in values if not math.isnan(float(v)))
    if not clean:
        return {
            "n": 0.0,
            "min": float("nan"),
            "q25": float("nan"),
            "median": float("nan"),
            "q75": float("nan"),
            "max": float("nan"),
        }
    return {
        "n": float(len(clean)),
        "min": clean[0],
        "q25": quantile(clean, 0.25),
        "median": quantile(clean, 0.50),
        "q75": quantile(clean, 0.75),
        "max": clean[-1],
    }


def range_overlap(a: Iterable[float], b: Iterable[float]) -> float:
    """Overlap length of two ranges; 0.0 when disjoint, NaN when either empty."""
    a_clean = [float(v) for v in a if not math.isnan(float(v))]
    b_clean = [float(v) for v in b if not math.isnan(float(v))]
    if not a_clean or not b_clean:
        return float("nan")
    lo = max(min(a_clean), min(b_clean))
    hi = min(max(a_clean), max(b_clean))
    return max(0.0, hi - lo)


def iqr_overlap(a: Iterable[float], b: Iterable[float]) -> float:
    """Overlap length of the two IQRs; 0.0 when disjoint, NaN when either empty."""
    a_clean = [float(v) for v in a if not math.isnan(float(v))]
    b_clean = [float(v) for v in b if not math.isnan(float(v))]
    if not a_clean or not b_clean:
        return float("nan")
    a_sorted = sorted(a_clean)
    b_sorted = sorted(b_clean)
    lo = max(quantile(a_sorted, 0.25), quantile(b_sorted, 0.25))
    hi = min(quantile(a_sorted, 0.75), quantile(b_sorted, 0.75))
    return max(0.0, hi - lo)


def valid_floor(values: Iterable[float]) -> float:
    """Calibration Envelope Diagnostic: minimum over the 17 VALID events.

    This is explicitly NOT a Detector threshold.
    """
    clean = [float(v) for v in values if not math.isnan(float(v))]
    return min(clean) if clean else float("nan")


def below_floor(value: float, floor: float) -> bool:
    """True when a value sits strictly below the VALID envelope floor."""
    if math.isnan(value) or math.isnan(floor):
        return False
    return value < floor


def pair_explained(
    p_below: bool,
    c_below: bool,
) -> bool:
    """Joint rule-shape diagnostic: FP explained if either axis is below floor."""
    return bool(p_below or c_below)


def fmt(value: Any) -> str:
    """Deterministic CSV scalar formatting (shortest round-trip float repr)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        if value == int(value) and abs(value) < 1e15:
            return str(int(value))
        return repr(value)
    return str(value)


# ---------------------------------------------------------------------------
# Loading


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_inputs() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Load the two immutable evidence CSVs (read-only)."""
    if not EVENT_CSV_IN.exists():
        raise FileNotFoundError(EVENT_CSV_IN)
    if not TRACE_CSV_IN.exists():
        raise FileNotFoundError(TRACE_CSV_IN)
    return _read_csv(EVENT_CSV_IN), _read_csv(TRACE_CSV_IN)


def group_trace(trace: list[dict[str, str]]) -> dict[tuple[str, int], dict[int, dict[str, str]]]:
    """Index the trace by (episode_key, event_frame) -> relative_frame -> row."""
    grouped: dict[tuple[str, int], dict[int, dict[str, str]]] = {}
    for row in trace:
        key = (row["episode_key"], int(row["event_frame"]))
        grouped.setdefault(key, {})[int(row["relative_frame"])] = row
    return grouped


def slice_window(
    frames: Mapping[int, Mapping[str, str]], window: tuple[int, int]
) -> list[Mapping[str, str]]:
    """Return the frames inside an inclusive [lo, hi] window, ordered by frame."""
    lo, hi = window
    return [frames[k] for k in range(lo, hi + 1) if k in frames]


def window_mean(frames: Mapping[int, Mapping[str, str]], window: tuple[int, int], field: str) -> float:
    lo, hi = window
    values = [float(frames[k][field]) for k in range(lo, hi + 1) if k in frames]
    if not values:
        return float("nan")
    return math.fsum(values) / len(values)


def window_median(frames: Mapping[int, Mapping[str, str]], window: tuple[int, int], field: str) -> float:
    lo, hi = window
    values = sorted(float(frames[k][field]) for k in range(lo, hi + 1) if k in frames)
    if not values:
        return float("nan")
    mid = len(values) // 2
    if len(values) % 2 == 1:
        return values[mid]
    return math.fsum(values[mid - 1 : mid + 1]) / 2.0


# ---------------------------------------------------------------------------
# Build


def build_event_rows(
    events: list[dict[str, str]],
    grouped: Mapping[tuple[str, int], Mapping[int, Mapping[str, str]]],
) -> list[dict[str, Any]]:
    """Build one operationalization row per Calibration Direction event."""
    rows: list[dict[str, Any]] = []
    for event in events:
        episode_id = event["episode_id"]
        episode_key = episode_id.split("/")[-1]
        event_frame = int(event["pred_frame"])
        frames = grouped.get((episode_key, event_frame), {})

        # --- P8: existing Stage A0 W=8 post speed (source field, verbatim).
        p8 = float(event["post_speed_mean"])

        # --- P12: existing analysis W=12 sustained post-motion reference.
        event_frame_row = frames.get(0, {})
        p12 = float(event_frame_row["right_speed_reference"])

        # --- C8: re-derived from the trace only (no new raw data).
        left8 = slice_window(frames, C8_LEFT_WINDOW)
        right8 = slice_window(frames, C8_RIGHT_WINDOW)
        c8_left = straightness(left8)
        c8_right = straightness(right8)
        c8_min = min(c8_left, c8_right) if not (
            math.isnan(c8_left) or math.isnan(c8_right)
        ) else float("nan")

        # --- C12: existing analysis W=12 straightness (event-frame row).
        c12_left = float(event_frame_row["left_straightness"])
        c12_right = float(event_frame_row["right_straightness"])
        c12_min = min(c12_left, c12_right)

        rows.append(
            {
                "episode_id": episode_id,
                "episode_key": episode_key,
                "event_frame": event_frame,
                "human_class": event["human_class"],
                "source_package": event["source_package"],
                "error_mode": event["error_mode"] or "VALID",
                "P8_post_speed_mean": p8,
                "P12_right_speed_reference": p12,
                "C8_left_straightness": c8_left,
                "C8_right_straightness": c8_right,
                "C8_min_straightness": c8_min,
                "C8_left_path_length_m": path_length(left8),
                "C8_right_path_length_m": path_length(right8),
                "C8_left_net_displacement_m": net_displacement(left8),
                "C8_right_net_displacement_m": net_displacement(right8),
                "C12_left_straightness": c12_left,
                "C12_right_straightness": c12_right,
                "C12_min_straightness": c12_min,
                # C12 consistency re-derivation from the same trace windows.
                "C12_recomputed_left_straightness": straightness(
                    slice_window(frames, C12_LEFT_WINDOW)
                ),
                "C12_recomputed_right_straightness": straightness(
                    slice_window(frames, C12_RIGHT_WINDOW)
                ),
                "P8_window": "relative_frame[0,+7]",
                "P12_window": "relative_frame[+4,+12]",
                "C8_window": "left[-8,-1]/right[0,+7]",
                "C12_window": "left[-12,-1]/right[0,+11]",
            }
        )

    rows.sort(key=lambda r: (r["episode_id"], r["event_frame"]))
    return rows


def attach_floors(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Compute VALID floors and attach below-floor / pair diagnostics to rows."""
    valid_rows = [r for r in rows if r["human_class"] == VALID_CLASS]
    floors = {
        "P8": valid_floor(r["P8_post_speed_mean"] for r in valid_rows),
        "P12": valid_floor(r["P12_right_speed_reference"] for r in valid_rows),
        "C8": valid_floor(r["C8_min_straightness"] for r in valid_rows),
        "C12": valid_floor(r["C12_min_straightness"] for r in valid_rows),
    }
    field_map = {
        "P8": "P8_post_speed_mean",
        "P12": "P12_right_speed_reference",
        "C8": "C8_min_straightness",
        "C12": "C12_min_straightness",
    }
    for row in rows:
        for feature, field in field_map.items():
            row[f"{feature}_below_valid_floor"] = below_floor(float(row[field]), floors[feature])
        row["Pair8_explained"] = pair_explained(
            row["P8_below_valid_floor"], row["C8_below_valid_floor"]
        )
        row["Pair12_explained"] = pair_explained(
            row["P12_below_valid_floor"], row["C12_below_valid_floor"]
        )
    return floors


EVENT_COLUMNS = (
    "episode_id",
    "episode_key",
    "event_frame",
    "human_class",
    "source_package",
    "error_mode",
    "P8_post_speed_mean",
    "P12_right_speed_reference",
    "C8_left_straightness",
    "C8_right_straightness",
    "C8_min_straightness",
    "C8_left_path_length_m",
    "C8_right_path_length_m",
    "C8_left_net_displacement_m",
    "C8_right_net_displacement_m",
    "C12_left_straightness",
    "C12_right_straightness",
    "C12_min_straightness",
    "C12_recomputed_left_straightness",
    "C12_recomputed_right_straightness",
    "P8_below_valid_floor",
    "P12_below_valid_floor",
    "C8_below_valid_floor",
    "C12_below_valid_floor",
    "Pair8_explained",
    "Pair12_explained",
    "P8_window",
    "P12_window",
    "C8_window",
    "C12_window",
)

SUMMARY_COLUMNS = (
    "feature",
    "cohort",
    "n",
    "min",
    "q25",
    "median",
    "q75",
    "max",
    "range_overlap",
    "iqr_overlap",
    "fp_below_valid_floor_count",
)


def cohort_values(rows: list[dict[str, Any]], feature: str, cohort: str) -> list[float]:
    field = {
        "P8": "P8_post_speed_mean",
        "P12": "P12_right_speed_reference",
        "C8": "C8_min_straightness",
        "C12": "C12_min_straightness",
    }[feature]
    if cohort == "VALID":
        selected = [r for r in rows if r["human_class"] == VALID_CLASS]
    elif cohort == "FP":
        selected = [r for r in rows if r["human_class"] == FP_CLASS]
    elif cohort == "ALL":
        selected = list(rows)
    elif cohort == "SEED_VALID":
        selected = [r for r in rows if r["human_class"] == VALID_CLASS and r["source_package"] == "SEED"]
    elif cohort == "FRESH_VALID":
        selected = [r for r in rows if r["human_class"] == VALID_CLASS and r["source_package"] == "FRESH"]
    elif cohort == "SEED_FP":
        selected = [r for r in rows if r["human_class"] == FP_CLASS and r["source_package"] == "SEED"]
    elif cohort == "FRESH_FP":
        selected = [r for r in rows if r["human_class"] == FP_CLASS and r["source_package"] == "FRESH"]
    else:
        raise ValueError(f"unknown cohort: {cohort}")
    return [float(r[field]) for r in selected]


def build_summary_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Feature x cohort summary table with overlap + envelope diagnostics."""
    summary: list[dict[str, Any]] = []
    for feature in FEATURES:
        valid_values = cohort_values(rows, feature, "VALID")
        fp_values = cohort_values(rows, feature, "FP")
        r_overlap = range_overlap(valid_values, fp_values)
        i_overlap = iqr_overlap(valid_values, fp_values)
        floor = valid_floor(valid_values)
        fp_below = sum(1 for v in fp_values if below_floor(v, floor))

        for cohort in COHORTS:
            values = cohort_values(rows, feature, cohort)
            stats = distribution(values)
            row = {
                "feature": feature,
                "cohort": cohort,
                "n": stats["n"],
                "min": stats["min"],
                "q25": stats["q25"],
                "median": stats["median"],
                "q75": stats["q75"],
                "max": stats["max"],
                "range_overlap": "",
                "iqr_overlap": "",
                "fp_below_valid_floor_count": "",
            }
            if cohort in ("VALID", "FP"):
                row["range_overlap"] = r_overlap
                row["iqr_overlap"] = i_overlap
            if cohort == "FP":
                row["fp_below_valid_floor_count"] = fp_below
            summary.append(row)
    return summary


# ---------------------------------------------------------------------------
# Writing (explicit LF + UTF-8, no BOM)


def render_csv(columns: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> str:
    """Render a CSV as a canonical LF-only UTF-8 string (no CR, no BOM)."""
    lines = [",".join(columns)]
    for row in rows:
        cells = []
        for column in columns:
            value = fmt(row.get(column, ""))
            if any(ch in value for ch in (",", '"', "\n", "\r")):
                value = '"' + value.replace('"', '""') + '"'
            cells.append(value)
        lines.append(",".join(cells))
    return "\n".join(lines) + "\n"


def write_csv(path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> bytes:
    """Write CSV bytes with explicit LF line terminator and no BOM."""
    payload = render_csv(columns, rows).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(payload)
    return payload


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# Validation


def validate(
    rows: list[dict[str, Any]],
    summary: list[dict[str, Any]],
    floors: Mapping[str, float],
) -> dict[str, Any]:
    """Run the mandatory validation gates and return a machine-readable report."""
    valid_rows = [r for r in rows if r["human_class"] == VALID_CLASS]
    fp_rows = [r for r in rows if r["human_class"] == FP_CLASS]

    keys = [(r["episode_id"], r["event_frame"]) for r in rows]
    duplicates = len(keys) - len(set(keys))

    numeric_fields = (
        "P8_post_speed_mean",
        "P12_right_speed_reference",
        "C8_left_straightness",
        "C8_right_straightness",
        "C8_min_straightness",
        "C12_left_straightness",
        "C12_right_straightness",
        "C12_min_straightness",
    )
    inf_count = 0
    nan_count = 0
    for row in rows:
        for field in numeric_fields:
            value = float(row[field])
            if math.isinf(value):
                inf_count += 1
            elif math.isnan(value):
                nan_count += 1

    # P8 source consistency: post_speed_mean == mean(speed, relative_frame [0,+7]).
    events, trace = load_inputs()
    grouped = group_trace(trace)
    p8_max_delta = 0.0
    for row in rows:
        frames = grouped[(row["episode_key"], row["event_frame"])]
        recomputed = window_mean(frames, P8_WINDOW, "translation_speed_mps")
        p8_max_delta = max(p8_max_delta, abs(recomputed - float(row["P8_post_speed_mean"])))

    # P12 source consistency: right_speed_reference == median(speed, [+4,+12]).
    p12_max_delta = 0.0
    for row in rows:
        frames = grouped[(row["episode_key"], row["event_frame"])]
        recomputed = window_median(frames, P12_WINDOW, "translation_speed_mps")
        p12_max_delta = max(p12_max_delta, abs(recomputed - float(row["P12_right_speed_reference"])))

    # C12 source consistency: existing columns reproduce from the same trace.
    c12_max_delta = 0.0
    for row in rows:
        c12_max_delta = max(
            c12_max_delta,
            abs(float(row["C12_recomputed_left_straightness"]) - float(row["C12_left_straightness"])),
            abs(float(row["C12_recomputed_right_straightness"]) - float(row["C12_right_straightness"])),
        )

    # C8 determinism: recompute independently and compare.
    c8_max_delta = 0.0
    for row in rows:
        frames = grouped[(row["episode_key"], row["event_frame"])]
        left = straightness(slice_window(frames, C8_LEFT_WINDOW))
        right = straightness(slice_window(frames, C8_RIGHT_WINDOW))
        expected_min = min(left, right) if not (
            math.isnan(left) or math.isnan(right)
        ) else float("nan")
        c8_max_delta = max(
            c8_max_delta,
            abs(left - float(row["C8_left_straightness"])),
            abs(right - float(row["C8_right_straightness"])),
            abs(expected_min - float(row["C8_min_straightness"])),
        )

    critical_present = sum(
        1 for ep, fr in CRITICAL_EVENTS if (f"data/{ep}", fr) in set(keys)
    )

    pair8_covered = sum(1 for r in fp_rows if r["Pair8_explained"])
    pair12_covered = sum(1 for r in fp_rows if r["Pair12_explained"])
    pair8_valid_rejected = sum(1 for r in valid_rows if r["Pair8_explained"])
    pair12_valid_rejected = sum(1 for r in valid_rows if r["Pair12_explained"])

    return {
        "event_rows": len(rows),
        "valid_count": len(valid_rows),
        "fp_count": len(fp_rows),
        "duplicate_event_key": duplicates,
        "inf_count": inf_count,
        "nan_count": nan_count,
        "p8_max_delta": p8_max_delta,
        "p12_max_delta": p12_max_delta,
        "c12_max_delta": c12_max_delta,
        "c8_max_delta": c8_max_delta,
        "critical_event_coverage": f"{critical_present}/{len(CRITICAL_EVENTS)}",
        "floors": dict(floors),
        "fp_below_valid_floor": {
            feature: sum(1 for r in fp_rows if r[f"{feature}_below_valid_floor"])
            for feature in FEATURES
        },
        "pair8_fp_covered": pair8_covered,
        "pair8_valid_rejected": pair8_valid_rejected,
        "pair12_fp_covered": pair12_covered,
        "pair12_valid_rejected": pair12_valid_rejected,
        "summary_rows": len(summary),
    }


def print_report(report: Mapping[str, Any], event_sha: str, summary_sha: str) -> None:
    print("=" * 72)
    print("G1-P3 MOTION SUFFICIENCY OPERATIONALIZATION PREPARATION")
    print("=" * 72)
    print(f"event_rows                 = {report['event_rows']}")
    print(f"VALID_DIRECTION            = {report['valid_count']}")
    print(f"DIRECTION_FP               = {report['fp_count']}")
    print(f"duplicate_event_key        = {report['duplicate_event_key']}")
    print(f"inf_count                  = {report['inf_count']}")
    print(f"nan_count                  = {report['nan_count']}")
    print(f"P8  source consistency     = {'PASS' if report['p8_max_delta'] < 1e-12 else 'FAIL'}"
          f" (max abs delta = {report['p8_max_delta']:.3e})")
    print(f"P12 source consistency     = {'PASS' if report['p12_max_delta'] < 1e-12 else 'FAIL'}"
          f" (max abs delta = {report['p12_max_delta']:.3e})")
    print(f"C12 source consistency     = {'PASS' if report['c12_max_delta'] < 1e-12 else 'FAIL'}"
          f" (max abs delta = {report['c12_max_delta']:.3e})")
    print(f"C8  deterministic recompute= {'PASS' if report['c8_max_delta'] < 1e-12 else 'FAIL'}"
          f" (max abs delta = {report['c8_max_delta']:.3e})")
    print(f"critical_event_coverage    = {report['critical_event_coverage']}")
    print(f"summary_rows               = {report['summary_rows']}")
    print("-" * 72)
    for feature in FEATURES:
        print(f"VALID_FLOOR({feature})          = {report['floors'][feature]!r}"
              f"   FP below floor = {report['fp_below_valid_floor'][feature]}/9")
    print("-" * 72)
    print(f"Pair8  FP covered = {report['pair8_fp_covered']}/9"
          f"   VALID rejected = {report['pair8_valid_rejected']}/17")
    print(f"Pair12 FP covered = {report['pair12_fp_covered']}/9"
          f"   VALID rejected = {report['pair12_valid_rejected']}/17")
    print("-" * 72)
    print(f"EVENT_CSV   canonical LF SHA256 = {event_sha}")
    print(f"SUMMARY_CSV canonical LF SHA256 = {summary_sha}")
    print("=" * 72)


# ---------------------------------------------------------------------------
# Entry point


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="determinism gate: fail if on-disk CSVs differ from a fresh render",
    )
    parser.add_argument(
        "--print-sha256",
        action="store_true",
        help="print canonical LF SHA256 of both output CSVs (also printed always)",
    )
    args = parser.parse_args(argv)

    events, trace = load_inputs()
    grouped = group_trace(trace)
    rows = build_event_rows(events, grouped)
    floors = attach_floors(rows)
    summary = build_summary_rows(rows)

    event_payload = render_csv(EVENT_COLUMNS, rows).encode("utf-8")
    summary_payload = render_csv(SUMMARY_COLUMNS, summary).encode("utf-8")
    event_sha = sha256_bytes(event_payload)
    summary_sha = sha256_bytes(summary_payload)

    if args.check:
        mismatches = []
        for path, payload in (
            (EVENT_CSV_OUT, event_payload),
            (SUMMARY_CSV_OUT, summary_payload),
        ):
            if not path.exists():
                mismatches.append(f"MISSING: {path}")
            elif path.read_bytes() != payload:
                mismatches.append(f"DIFFERS: {path}")
        report = validate(rows, summary, floors)
        print_report(report, event_sha, summary_sha)
        if mismatches:
            print("DETERMINISM = FAIL")
            for item in mismatches:
                print(f"  {item}")
            return 1
        print("DETERMINISM = PASS (byte-identical, LF preserved)")
        return 0

    write_csv(EVENT_CSV_OUT, EVENT_COLUMNS, rows)
    write_csv(SUMMARY_CSV_OUT, SUMMARY_COLUMNS, summary)

    report = validate(rows, summary, floors)
    print_report(report, event_sha, summary_sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
