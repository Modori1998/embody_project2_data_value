"""Build the G1-P3 Trajectory Mechanism Diagnostic Set (READ-ONLY).

Purpose
-------
Materialize a **Design Diagnostic Set** of independent Direction Final
Boundaries drawn only from episodes that never participated in the existing
Calibration / Rule Discovery work, then select a rank-based, blinded,
matched 10 + 10 sample.

The set answers exactly one question (Frozen Validation Design §2):

    Among new independent Direction candidates with sufficient post-motion,
    does low trajectory coherence enrich human-reviewed REDUNDANT boundaries?

Hard constraints honoured by this script
----------------------------------------
* Does NOT modify Detector / segmentation / Candidate Generation /
  Candidate Acceptance / Event Consolidation / config / Frozen Protocol.
* Does NOT select or use any numeric threshold; no calibration VALID_FLOOR,
  0.045 / 0.050 / 0.75 / 0.76 values are consumed anywhere.
* Does NOT read Web SQLite, privileged simulator state, object pose, reward,
  success, done or terminal semantics.
* Does NOT use any human label: the candidate pool and both audit CSVs are
  label-free by construction.
* Does NOT create human review rows, does NOT write any review result.
* Deterministic: identical inputs produce byte-identical selection artifacts.

Selection pipeline (Frozen Validation Design §7 - §11)
-----------------------------------------------------
1. Candidate pool = independent Direction Final Boundary from non-calibration
   episodes, minus near-gripper consolidation context (<= 12 frames), minus
   incomplete ±12 window context, minus degenerate (zero-length) trajectories.
2. P12 = median(translation_speed) over relative_frame [+4, +12].
3. C12 = min(left_straightness, right_straightness) with
   left over [-12, -1] and right over [0, +11].
4. P12_ELIGIBLE_POOL = top 50 % of P12 rank (percentile selection, NOT a
   physical threshold).
5. Arm A (low coherence target) = bottom 25 % of C12 rank inside the pool.
   Arm B (high coherence control) = top 25 % of C12 rank inside the pool.
6. One event per episode, no episode shared between arms.
7. Arm B is matched to Arm A by minimum
   MATCH_DISTANCE = |dP12 pct| + |d evidence pct| + |d run_length pct|.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from project2_g1.boundary_config import load_g1_p2_config  # noqa: E402
from project2_g1.boundary_engine import run_boundary_engine  # noqa: E402
from project2_g1.config import load_g1_p1_config  # noqa: E402
from project2_g1.signals import compute_formal_signals  # noqa: E402
from project2_g1.source import (  # noqa: E402
    build_can_mh_adapter,
    enumerate_episodes,
    load_formal_episode,
)
from project2_g1.stage_a0_analysis import (  # noqa: E402
    _min_abs_distance,
    derive_run_length,
    lineage_for_final,
)
from project2_g1_audit_web.hashes import (  # noqa: E402
    config_hash_from_path,
    signal_contract_hash_from_path,
)

# ---------------------------------------------------------------------------
# Frozen identity / constants

DESIGN_VERSION = "FROZEN_TARGETED_MATCHED_DIAGNOSTIC_V1"
DATASET_ROLE = "DESIGN_DIAGNOSTIC_SET"
PRIMARY_HYPOTHESIS = "LOW_C12_ENRICHES_REDUNDANT_GIVEN_HIGH_P12"
SELECTION_RULE = "RANK_BASED_BLINDED_MATCHED"

SOURCE_OF_TRUTH = "GITHUB_MAIN"
FROZEN_DESIGN_DOC = (
    "0-doc/10-design-review/"
    "Project2_G1_P3_Trajectory_Mechanism_Validation_Design_FROZEN_v1_20260921.md"
)
FROZEN_DESIGN_COMMIT = "ff2a33cf4b956eb57d11dd608d3b3fbd67d602d0"

CONFIG_PATH = PROJECT_ROOT / "configs" / "g1_p2_exploratory_segmentation.json"
SIGNAL_CONTRACT_PATH = PROJECT_ROOT / "configs" / "g1_p1_signal_contract.json"

EXPECTED_CONFIG_HASH = "dde590e759a31cb8c865369e18256ebecbbd01bc94a58e1d3ca695bb50f2a630"
EXPECTED_SIGNAL_HASH = "24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d"
EXPECTED_SEGMENTATION_VERSION = "G1-P2-EXPLORATORY-v0"
EXPECTED_CONFIG_VERSION = "g1_p2_exploratory_segmentation.v0"

# Frozen Calibration episode set (authoritative source:
# outputs/g1_p3_canonical_gt/g1_canonical_gt_20260918_131636_c9916b89/
# combined_calibration_manifest.json). Verified against SSOT at build time.
CALIBRATION_EPISODE_IDS: tuple[str, ...] = (
    "data/demo_0",
    "data/demo_32",
    "data/demo_179",
    "data/demo_230",
    "data/demo_242",
    "data/demo_278",
    "data/demo_150",
    "data/demo_162",
    "data/demo_213",
    "data/demo_255",
    "data/demo_260",
    "data/demo_270",
)
CALIBRATION_MANIFEST_PATH = (
    PROJECT_ROOT
    / "outputs/g1_p3_canonical_gt/g1_canonical_gt_20260918_131636_c9916b89"
    / "combined_calibration_manifest.json"
)
BASELINE_RUN_ROOT = (
    PROJECT_ROOT / "outputs/g1_audit_runs/g1_calibration_20260918_141032_781e5d8b"
)

OUT_DIR = (
    PROJECT_ROOT / "0-doc/80-audit-local/g1_p3_trajectory_mechanism_validation"
)
POOL_CSV = OUT_DIR / "01_candidate_pool.csv"
INTERNAL_CSV = OUT_DIR / "02_selection_internal.csv"
BLINDED_CSV = OUT_DIR / "03_selection_blinded.csv"

# Candidate semantics (reused from the frozen Stage A0 derivation).
CANDIDATE_DIRECTION = "DIRECTION_CHANGE"
CANDIDATE_GRIPPER = "GRIPPER_TRANSITION"

# Window definitions (Frozen Validation Design §6). Diagnostic only.
P12_WINDOW = (4, 12)          # relative_frame, inclusive
C12_LEFT_WINDOW = (-12, -1)   # relative_frame, inclusive
C12_RIGHT_WINDOW = (0, 11)    # relative_frame, inclusive

MIN_CONTEXT_FRAMES = 12       # both sides must have >= 12 frames of context
NEAR_GRIPPER_FRAMES = 12      # distance_to_nearest_gripper_final <= 12 excluded

PATH_EPS = 1e-9

# Selection parameters (percentile selection, NOT thresholds).
P12_ELIGIBLE_PERCENTILE = 0.50
ARM_LOW_QUANTILE = 0.25
ARM_HIGH_QUANTILE = 0.75

TARGET_PER_ARM = 10
MIN_PER_ARM = 8
MAX_SELECTED_EVENTS_PER_EPISODE = 1

# Deterministic default timestamp for diagnostic_set_id. Overridable via CLI so
# that the default artifacts are byte-reproducible.
DEFAULT_SET_TIMESTAMP = "20260921_000000"

# Blinding contract tokens. Must never appear in 03_selection_blinded.csv.
FORBIDDEN_BLINDING_TOKENS: tuple[str, ...] = (
    "arm",
    "p12",
    "c12",
    "coherence",
    "target",
    "control",
    "match_distance",
    "low",
    "high",
    "expected",
    "redundant",
    "valid",
)

# Exclusion reason codes (deterministic precedence order).
R_CALIBRATION = "CALIBRATION_EPISODE"
R_GRIPPER_PRIMARY_MERGED = "GRIPPER_PRIMARY_MERGED_FINAL"
R_EDGE_CONTEXT = "EDGE_CONTEXT_INCOMPLETE"
R_NEAR_GRIPPER = "NEAR_GRIPPER_CONSOLIDATION_CONTEXT"
R_DEGENERATE = "DEGENERATE_TRAJECTORY_CONTEXT"
R_RUN_LENGTH = "RUN_LENGTH_NOT_AVAILABLE"

POOL_COLUMNS = (
    "episode_id",
    "boundary_id",
    "event_frame",
    "candidate_type",
    "representative_candidate_id",
    "member_candidate_ids",
    "member_candidate_count",
    "member_candidate_types",
    "is_independent_direction_final",
    "is_gripper_primary_merged",
    "n_frames",
    "left_context_frames",
    "right_context_frames",
    "config_hash",
    "signal_contract_hash",
    "segmentation_version",
    "direction_evidence",
    "run_length",
    "P12",
    "left_path_length_m",
    "right_path_length_m",
    "left_net_displacement_m",
    "right_net_displacement_m",
    "left_straightness",
    "right_straightness",
    "C12",
    "distance_to_nearest_gripper_final",
    "edge_context_incomplete",
    "eligible_after_all_exclusions",
    "ineligibility_reason",
)

INTERNAL_COLUMNS = (
    "diagnostic_event_id",
    "arm",
    "pair_id",
    "episode_id",
    "event_frame",
    "boundary_id",
    "representative_candidate_id",
    "P12",
    "P12_percentile",
    "C12",
    "C12_percentile",
    "direction_evidence",
    "direction_evidence_percentile",
    "run_length",
    "run_length_percentile",
    "match_distance",
    "distance_to_nearest_gripper_final",
    "selection_reason",
)

BLINDED_COLUMNS = (
    "diagnostic_event_id",
    "episode_id",
    "boundary_id",
    "event_frame",
    "event_type",
    "representative_candidate_id",
    "member_candidate_ids",
    "diagnostic_set_id",
)


class DiagnosticBuildError(ValueError):
    """Fail-fast on identity / integrity violations."""


# ---------------------------------------------------------------------------
# Deterministic helpers


def norm3(dx: float, dy: float, dz: float) -> float:
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def path_length(values: Iterable[float]) -> float:
    """Path length = sum of per-frame translation step norms."""
    return math.fsum(float(v) for v in values)


def net_displacement(dxs: Iterable[float], dys: Iterable[float], dzs: Iterable[float]) -> float:
    """Net displacement = norm of the summed per-frame delta vector."""
    return norm3(math.fsum(dxs), math.fsum(dys), math.fsum(dzs))


def straightness(path: float, net: float) -> float:
    """Straightness = net / path; NaN when the path is degenerate."""
    if path < PATH_EPS:
        return float("nan")
    return net / path


def median(values: Sequence[float]) -> float:
    clean = sorted(float(v) for v in values)
    if not clean:
        return float("nan")
    mid = len(clean) // 2
    if len(clean) % 2 == 1:
        return clean[mid]
    return (clean[mid - 1] + clean[mid]) / 2.0


def quantile(values: Sequence[float], q: float) -> float:
    clean = sorted(float(v) for v in values)
    if not clean:
        return float("nan")
    if len(clean) == 1:
        return clean[0]
    pos = q * (len(clean) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return clean[lo]
    return clean[lo] + (clean[hi] - clean[lo]) * (pos - lo)


def percentile_map(
    rows: Sequence[Mapping[str, Any]], key: str
) -> dict[str, float]:
    """Ascending rank percentile: lowest value -> 0.0, highest -> 1.0.

    Ties are broken deterministically by (episode_id, event_frame, boundary_id)
    so the mapping is stable across runs.
    """
    ordered = sorted(
        rows,
        key=lambda r: (float(r[key]), str(r["episode_id"]), int(r["event_frame"]), str(r["boundary_id"])),
    )
    n = len(ordered)
    out: dict[str, float] = {}
    for index, row in enumerate(ordered):
        out[str(row["boundary_id"])] = (index / (n - 1)) if n > 1 else 0.0
    return out


def fmt(value: Any) -> str:
    """Deterministic CSV scalar formatting."""
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


def render_csv(columns: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> str:
    """Canonical LF-only, UTF-8, no-BOM CSV text."""
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


def write_csv_lf(path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> bytes:
    """Explicit LF line terminator; never relies on csv.writer defaults."""
    payload = render_csv(columns, rows).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


# ---------------------------------------------------------------------------
# Calibration set recovery from SSOT artifacts


def load_calibration_episode_ids() -> tuple[str, ...]:
    """Recover the frozen calibration episode set from the canonical manifest."""
    if not CALIBRATION_MANIFEST_PATH.is_file():
        raise DiagnosticBuildError(f"calibration manifest missing: {CALIBRATION_MANIFEST_PATH}")
    payload = json.loads(CALIBRATION_MANIFEST_PATH.read_text(encoding="utf-8"))
    ids = tuple(str(item) for item in payload.get("episode_ids", ()))
    if not ids:
        raise DiagnosticBuildError("calibration manifest has no episode_ids")
    return ids


def count_calibration_direction_finals() -> int:
    """Count DIRECTION finals inside the frozen 12-episode baseline run.

    Used only for the exclusion audit so the "Calibration excluded" number is
    an actually observed count rather than an assumption. The expected value is
    26, i.e. exactly the frozen Calibration Direction cohort
    (17 VALID_DIRECTION + 9 DIRECTION_FP) — this doubles as a check that the
    pool-construction semantics reproduce the frozen cohort.
    """
    total = 0
    for episode_id in load_calibration_episode_ids():
        path = BASELINE_RUN_ROOT / "diagnostic" / episode_id.split("/")[-1] / "final_boundaries.csv"
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if str(row.get("candidate_type") or "") == CANDIDATE_DIRECTION:
                    total += 1
    return total


EXPECTED_CALIBRATION_DIRECTION_FINALS = 26

RUN_REGISTRY_PATH = PROJECT_ROOT / "outputs/g1_audit_web/g1_audit_run_registry.json"


def audit_reviewed_episode_coverage() -> dict[str, Any]:
    """Verify that every episode ever opened in an audit run is calibration.

    The design requires excluding events already human-reviewed for Rule
    Discovery. Every registered audit run is inspected; if any covered episode
    falls outside the frozen calibration set, the build must stop because that
    episode's events may already carry human labels.

    Only run folders / the JSON registry are read here — never the review
    database, and never as a candidate source.
    """
    if not RUN_REGISTRY_PATH.is_file():
        return {"registry_available": False, "covered_episodes": [], "outside_calibration": []}
    payload = json.loads(RUN_REGISTRY_PATH.read_text(encoding="utf-8"))
    covered: set[str] = set()
    unreadable: list[str] = []
    for run_id, meta in payload.get("runs", {}).items():
        diagnostic = Path(str(meta.get("audit_folder_path") or "")) / "diagnostic"
        try:
            if not diagnostic.is_dir():
                continue
            names = sorted(p.name for p in diagnostic.iterdir() if p.is_dir())
        except (PermissionError, OSError):
            unreadable.append(str(run_id))
            continue
        covered.update(f"data/{name}" for name in names)
    calibration = set(load_calibration_episode_ids())
    return {
        "registry_available": True,
        "covered_episodes": sorted(covered),
        "outside_calibration": sorted(covered - calibration),
        "unreadable_runs": unreadable,
    }


# ---------------------------------------------------------------------------
# Candidate materialization (read-only detector reuse)


def window_slice(values: Sequence[float], frame: int, window: tuple[int, int]) -> list[float]:
    """Frames relative_frame in [lo, hi] mapped to absolute indices."""
    lo, hi = window
    return [float(values[frame + offset]) for offset in range(lo, hi + 1)]


def context_available(n_frames: int, frame: int) -> tuple[int, int]:
    """(left_context_frames, right_context_frames) around an event frame."""
    return int(frame), int(n_frames - frame)


def compute_p12(translation_speed: Sequence[float], frame: int) -> float:
    """P12 = median(translation_speed_mps) over relative_frame [+4, +12]."""
    return median(window_slice(translation_speed, frame, P12_WINDOW))


def compute_c12(
    step_norm: Sequence[float],
    delta_x: Sequence[float],
    delta_y: Sequence[float],
    delta_z: Sequence[float],
    frame: int,
) -> dict[str, float]:
    """C12 = min(left_straightness, right_straightness) over ±12 windows."""
    left_path = path_length(window_slice(step_norm, frame, C12_LEFT_WINDOW))
    right_path = path_length(window_slice(step_norm, frame, C12_RIGHT_WINDOW))
    left_net = net_displacement(
        window_slice(delta_x, frame, C12_LEFT_WINDOW),
        window_slice(delta_y, frame, C12_LEFT_WINDOW),
        window_slice(delta_z, frame, C12_LEFT_WINDOW),
    )
    right_net = net_displacement(
        window_slice(delta_x, frame, C12_RIGHT_WINDOW),
        window_slice(delta_y, frame, C12_RIGHT_WINDOW),
        window_slice(delta_z, frame, C12_RIGHT_WINDOW),
    )
    left_straight = straightness(left_path, left_net)
    right_straight = straightness(right_path, right_net)
    if math.isnan(left_straight) or math.isnan(right_straight):
        combined = float("nan")
    else:
        combined = min(left_straight, right_straight)
    return {
        "left_path_length_m": left_path,
        "right_path_length_m": right_path,
        "left_net_displacement_m": left_net,
        "right_net_displacement_m": right_net,
        "left_straightness": left_straight,
        "right_straightness": right_straight,
        "C12": combined,
    }


def materialize_pool(
    *,
    adapter,
    p1_config,
    p2_config,
    excluded_episodes: set[str],
    limit_episodes: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Run the frozen detector read-only and collect Direction Final Boundaries."""
    counters = {"episodes_scanned": 0, "episodes_skipped_calibration": 0, "non_direction_final_excluded": 0}
    rows: list[dict[str, Any]] = []

    episodes = enumerate_episodes(adapter)
    for identity in episodes:
        episode_id = identity.source_episode_id
        if episode_id in excluded_episodes:
            counters["episodes_skipped_calibration"] += 1
            continue
        if limit_episodes is not None and counters["episodes_scanned"] >= limit_episodes:
            break
        counters["episodes_scanned"] += 1

        episode = load_formal_episode(adapter, episode_id)
        signals = compute_formal_signals(episode, p1_config)
        result = run_boundary_engine(signals, p2_config)

        finals = [event.to_row() for event in result.final_events]
        candidates = [candidate.to_row() for candidate in result.candidates]
        final_gripper_frames = [
            int(row["frame"]) for row in finals if str(row["candidate_type"]) == CANDIDATE_GRIPPER
        ]

        for final in finals:
            if str(final.get("candidate_type") or "") != CANDIDATE_DIRECTION:
                counters["non_direction_final_excluded"] += 1
                continue
            frame = int(final["frame"])
            lineage = lineage_for_final(finals, candidates, str(final["boundary_id"]))
            run_length, run_provenance = derive_run_length(
                signals.direction_change_evidence,
                frame,
                p2_config.direction_change_threshold,
                p2_config.direction_persistence_frames,
            )
            left_ctx, right_ctx = context_available(signals.n_frames, frame)
            edge_incomplete = left_ctx < MIN_CONTEXT_FRAMES or right_ctx < MIN_CONTEXT_FRAMES

            row: dict[str, Any] = {
                "episode_id": episode_id,
                "boundary_id": str(final["boundary_id"]),
                "event_frame": frame,
                "candidate_type": CANDIDATE_DIRECTION,
                "representative_candidate_id": str(final.get("representative_candidate_id") or ""),
                "member_candidate_ids": str(final.get("member_candidate_ids") or ""),
                "member_candidate_count": int(final.get("member_candidate_count") or 0),
                "member_candidate_types": str(final.get("member_candidate_types") or ""),
                "is_independent_direction_final": bool(lineage["is_independent_direction_final"]),
                "is_gripper_primary_merged": bool(lineage["is_gripper_primary_merged"]),
                "n_frames": int(signals.n_frames),
                "left_context_frames": left_ctx,
                "right_context_frames": right_ctx,
                "config_hash": EXPECTED_CONFIG_HASH,
                "signal_contract_hash": EXPECTED_SIGNAL_HASH,
                "segmentation_version": EXPECTED_SEGMENTATION_VERSION,
                "direction_evidence": float(lineage["evidence_value"]),
                "run_length": run_length,
                "run_length_provenance": run_provenance,
                "distance_to_nearest_gripper_final": _min_abs_distance(frame, final_gripper_frames),
                "edge_context_incomplete": edge_incomplete,
            }

            # P12 / C12 are only meaningful with complete ±12 context. When the
            # context is incomplete the windows would be shorter than declared,
            # so no value is emitted (NaN with an explicit reason).
            if edge_incomplete:
                row.update(
                    {
                        "P12": float("nan"),
                        "left_path_length_m": float("nan"),
                        "right_path_length_m": float("nan"),
                        "left_net_displacement_m": float("nan"),
                        "right_net_displacement_m": float("nan"),
                        "left_straightness": float("nan"),
                        "right_straightness": float("nan"),
                        "C12": float("nan"),
                    }
                )
            else:
                row["P12"] = compute_p12(signals.translation_speed, frame)
                row.update(
                    compute_c12(
                        signals.translation_step_norm,
                        signals.delta_x,
                        signals.delta_y,
                        signals.delta_z,
                        frame,
                    )
                )

            rows.append(row)

    rows.sort(key=lambda r: (str(r["episode_id"]), int(r["event_frame"]), str(r["boundary_id"])))
    return rows, counters


# ---------------------------------------------------------------------------
# Exclusion evaluation


def evaluate_exclusions(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Apply the diagnostic exclusions in a fixed precedence order."""
    counts = {
        "initial_direction_candidates": len(rows),
        R_GRIPPER_PRIMARY_MERGED: 0,
        R_EDGE_CONTEXT: 0,
        R_NEAR_GRIPPER: 0,
        R_DEGENERATE: 0,
        R_RUN_LENGTH: 0,
    }
    for row in rows:
        reason = ""
        if not bool(row["is_independent_direction_final"]):
            reason = R_GRIPPER_PRIMARY_MERGED
        elif bool(row["edge_context_incomplete"]):
            reason = R_EDGE_CONTEXT
        elif row["distance_to_nearest_gripper_final"] is None:
            reason = R_NEAR_GRIPPER
        elif int(row["distance_to_nearest_gripper_final"]) <= NEAR_GRIPPER_FRAMES:
            reason = R_NEAR_GRIPPER
        elif math.isnan(float(row["C12"])):
            reason = R_DEGENERATE
        elif row["run_length"] is None:
            reason = R_RUN_LENGTH
        if reason:
            counts[reason] += 1
        row["ineligibility_reason"] = reason
        row["eligible_after_all_exclusions"] = reason == ""
    return counts


# ---------------------------------------------------------------------------
# Rank-based selection


def _sort_key_c12(row: Mapping[str, Any]) -> tuple[float, str, int]:
    return (float(row["C12"]), str(row["episode_id"]), int(row["event_frame"]))


def select_arm_a(
    arm_a_pool: Sequence[Mapping[str, Any]], target: int
) -> list[Mapping[str, Any]]:
    """Low-coherence target arm: C12 ASC, one event per episode."""
    chosen: list[Mapping[str, Any]] = []
    used_episodes: set[str] = set()
    for row in sorted(arm_a_pool, key=_sort_key_c12):
        episode_id = str(row["episode_id"])
        if episode_id in used_episodes:
            continue
        used_episodes.add(episode_id)
        chosen.append(row)
        if len(chosen) >= target:
            break
    return chosen


def match_distance(a: Mapping[str, Any], b: Mapping[str, Any]) -> float:
    """MATCH_DISTANCE = sum of absolute percentile deltas."""
    return (
        abs(float(a["P12_percentile"]) - float(b["P12_percentile"]))
        + abs(float(a["direction_evidence_percentile"]) - float(b["direction_evidence_percentile"]))
        + abs(float(a["run_length_percentile"]) - float(b["run_length_percentile"]))
    )


def select_arm_b(
    arm_a: Sequence[Mapping[str, Any]],
    arm_b_pool: Sequence[Mapping[str, Any]],
) -> tuple[list[tuple[Mapping[str, Any], Mapping[str, Any], float]], int]:
    """Greedy minimum-distance matching with no reuse and no episode sharing."""
    reserved_episodes = {str(row["episode_id"]) for row in arm_a}
    available = sorted(
        arm_b_pool,
        key=lambda r: (str(r["episode_id"]), int(r["event_frame"]), str(r["boundary_id"])),
    )
    used_episodes = set(reserved_episodes)
    pairs: list[tuple[Mapping[str, Any], Mapping[str, Any], float]] = []
    unmatched = 0

    for target in sorted(arm_a, key=_sort_key_c12):
        best: Mapping[str, Any] | None = None
        best_distance = math.inf
        for candidate in available:
            if str(candidate["boundary_id"]) in {str(p[1]["boundary_id"]) for p in pairs}:
                continue
            if str(candidate["episode_id"]) in used_episodes:
                continue
            distance = match_distance(target, candidate)
            if distance < best_distance - 1e-15:
                best = candidate
                best_distance = distance
            elif abs(distance - best_distance) <= 1e-15 and best is not None:
                current_key = (str(candidate["episode_id"]), int(candidate["event_frame"]))
                best_key = (str(best["episode_id"]), int(best["event_frame"]))
                if current_key < best_key:
                    best = candidate
        if best is None:
            unmatched += 1
            continue
        used_episodes.add(str(best["episode_id"]))
        pairs.append((target, best, best_distance))

    return pairs, unmatched


def build_selection(
    eligible: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Full rank-based selection pipeline over the eligible candidate pool."""
    p12_percentile_full = percentile_map(eligible, "P12")
    for row in eligible:
        row["P12_eligible_percentile"] = p12_percentile_full[str(row["boundary_id"])]

    p12_eligible = [
        row for row in eligible if row["P12_eligible_percentile"] >= P12_ELIGIBLE_PERCENTILE
    ]
    p12_eligible.sort(key=lambda r: (str(r["episode_id"]), int(r["event_frame"]), str(r["boundary_id"])))

    c12_percentile = percentile_map(p12_eligible, "C12")
    p12_pct = percentile_map(p12_eligible, "P12")
    evidence_pct = percentile_map(p12_eligible, "direction_evidence")
    run_pct = percentile_map(p12_eligible, "run_length")
    for row in p12_eligible:
        key = str(row["boundary_id"])
        row["C12_percentile"] = c12_percentile[key]
        row["P12_percentile"] = p12_pct[key]
        row["direction_evidence_percentile"] = evidence_pct[key]
        row["run_length_percentile"] = run_pct[key]

    arm_a_pool = [row for row in p12_eligible if row["C12_percentile"] <= ARM_LOW_QUANTILE]
    arm_b_pool = [row for row in p12_eligible if row["C12_percentile"] >= ARM_HIGH_QUANTILE]

    arm_a = select_arm_a(arm_a_pool, TARGET_PER_ARM)
    pairs, unmatched = select_arm_b(arm_a, arm_b_pool)

    return {
        "eligible": eligible,
        "p12_eligible": p12_eligible,
        "arm_a_pool": arm_a_pool,
        "arm_b_pool": arm_b_pool,
        "arm_a": arm_a,
        "pairs": pairs,
        "unmatched_arm_a": unmatched,
    }


def assign_diagnostic_ids(
    arm_a: Sequence[Mapping[str, Any]], pairs: Sequence[tuple[Any, Any, float]]
) -> dict[str, str]:
    """Stable blinded ids, ordered by episode_id then event_frame (no arm info)."""
    members: list[Mapping[str, Any]] = list(arm_a) + [pair[1] for pair in pairs]
    ordered = sorted(members, key=lambda r: (str(r["episode_id"]), int(r["event_frame"])))
    return {
        str(row["boundary_id"]): f"G1P3-DIAG-{index:03d}"
        for index, row in enumerate(ordered, start=1)
    }


def compute_set_id(
    selected: Sequence[Mapping[str, Any]], timestamp: str, event_ids: Mapping[str, str]
) -> str:
    """Content hash over selected episode/event/lineage identity + design version."""
    payload = {
        "design_version": DESIGN_VERSION,
        "events": [
            {
                "diagnostic_event_id": event_ids[str(row["boundary_id"])],
                "episode_id": str(row["episode_id"]),
                "event_frame": int(row["event_frame"]),
                "boundary_id": str(row["boundary_id"]),
                "representative_candidate_id": str(row["representative_candidate_id"]),
            }
            for row in sorted(selected, key=lambda r: event_ids[str(r["boundary_id"])])
        ],
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"g1_trajectory_mechanism_diag_{timestamp}_{hashlib.sha256(blob).hexdigest()[:8]}"


# ---------------------------------------------------------------------------
# Blinding audit


def audit_blinding(payload: bytes) -> list[str]:
    """Return the list of forbidden tokens found in the blinded manifest."""
    text = payload.decode("utf-8").lower()
    return [token for token in FORBIDDEN_BLINDING_TOKENS if token in text]


# ---------------------------------------------------------------------------
# Integrity checks


def check_identity(p1_config, p2_config) -> dict[str, str]:
    config_hash = config_hash_from_path(CONFIG_PATH)
    signal_hash = signal_contract_hash_from_path(SIGNAL_CONTRACT_PATH)
    if config_hash != EXPECTED_CONFIG_HASH:
        raise DiagnosticBuildError(f"config_hash mismatch: {config_hash}")
    if signal_hash != EXPECTED_SIGNAL_HASH:
        raise DiagnosticBuildError(f"signal_contract_hash mismatch: {signal_hash}")
    if p2_config.segmentation_version != EXPECTED_SEGMENTATION_VERSION:
        raise DiagnosticBuildError(f"segmentation_version mismatch: {p2_config.segmentation_version}")
    if p2_config.config_version != EXPECTED_CONFIG_VERSION:
        raise DiagnosticBuildError(f"config_version mismatch: {p2_config.config_version}")
    return {
        "config_hash": config_hash,
        "signal_contract_hash": signal_hash,
        "segmentation_version": p2_config.segmentation_version,
        "config_version": p2_config.config_version,
        "source_dataset_id": "robomimic_v15_can_mh",
    }


def integrity_report(
    pool: Sequence[Mapping[str, Any]],
    selection: Mapping[str, Any],
    blinded_payload: bytes,
    event_ids: Mapping[str, str],
    calibration_ids: tuple[str, ...],
) -> dict[str, Any]:
    pairs = selection["pairs"]
    arm_a = selection["arm_a"]
    arm_b = [pair[1] for pair in pairs]
    selected = list(arm_a) + arm_b

    keys = [(str(r["episode_id"]), int(r["event_frame"])) for r in selected]
    episodes = [str(r["episode_id"]) for r in selected]

    forbidden = audit_blinding(blinded_payload)

    return {
        "pool_duplicate_key": len(pool) - len({(str(r["episode_id"]), int(r["event_frame"]), str(r["boundary_id"])) for r in pool}),
        "pool_inf_count": sum(
            1
            for row in pool
            for key in ("P12", "C12", "left_straightness", "right_straightness")
            if isinstance(row[key], float) and math.isinf(row[key])
        ),
        "pool_nan_count": sum(
            1
            for row in pool
            for key in ("P12", "C12", "left_straightness", "right_straightness")
            if isinstance(row[key], float) and math.isnan(row[key])
        ),
        "selected_count": len(selected),
        "arm_a_count": len(arm_a),
        "arm_b_count": len(arm_b),
        "distinct_episodes": len(set(episodes)),
        "episode_reuse": len(episodes) - len(set(episodes)),
        "selected_duplicate_key": len(keys) - len(set(keys)),
        "calibration_leakage": sum(1 for episode in episodes if episode in set(calibration_ids)),
        "selected_non_independent": sum(
            1 for row in selected if not bool(row["is_independent_direction_final"])
        ),
        "selected_near_gripper": sum(
            1 for row in selected if int(row["distance_to_nearest_gripper_final"]) <= NEAR_GRIPPER_FRAMES
        ),
        "selected_edge_incomplete": sum(1 for row in selected if bool(row["edge_context_incomplete"])),
        "selected_nan": sum(
            1
            for row in selected
            for key in ("P12", "C12")
            if isinstance(row[key], float) and math.isnan(row[key])
        ),
        "event_id_count": len(event_ids),
        "forbidden_tokens_found": forbidden,
    }


# ---------------------------------------------------------------------------
# Artifact builders


def build_pool_rows(pool: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{column: row.get(column, "") for column in POOL_COLUMNS} for row in pool]


def build_internal_rows(
    arm_a: Sequence[Mapping[str, Any]],
    pairs: Sequence[tuple[Mapping[str, Any], Mapping[str, Any], float]],
    event_ids: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Engineering audit table. Arm A and its matched Arm B share one pair_id.

    ``match_distance`` is a pair-level property and is therefore written on both
    rows of a pair (identical value), never only on one side.
    """
    pair_by_target: dict[str, tuple[str, Mapping[str, Any], float]] = {}
    for index, (target, control, distance) in enumerate(
        sorted(pairs, key=lambda item: _sort_key_c12(item[0])), start=1
    ):
        pair_by_target[str(target["boundary_id"])] = (f"P{index:02d}", control, distance)

    rows: list[dict[str, Any]] = []
    for target in sorted(arm_a, key=_sort_key_c12):
        key = str(target["boundary_id"])
        entry = pair_by_target.get(key)
        pair_id = entry[0] if entry else ""
        distance: Any = entry[2] if entry else ""
        rows.append(
            {
                "diagnostic_event_id": event_ids[key],
                "arm": "A",
                "pair_id": pair_id,
                "episode_id": target["episode_id"],
                "event_frame": target["event_frame"],
                "boundary_id": target["boundary_id"],
                "representative_candidate_id": target["representative_candidate_id"],
                "P12": target["P12"],
                "P12_percentile": target["P12_percentile"],
                "C12": target["C12"],
                "C12_percentile": target["C12_percentile"],
                "direction_evidence": target["direction_evidence"],
                "direction_evidence_percentile": target["direction_evidence_percentile"],
                "run_length": target["run_length"],
                "run_length_percentile": target["run_length_percentile"],
                "match_distance": distance,
                "distance_to_nearest_gripper_final": target["distance_to_nearest_gripper_final"],
                "selection_reason": "LOW_C12_QUARTILE_EPISODE_DIVERSE_TARGET",
            }
        )
        if entry is None:
            continue
        _, control, _ = entry
        control_key = str(control["boundary_id"])
        rows.append(
            {
                "diagnostic_event_id": event_ids[control_key],
                "arm": "B",
                "pair_id": pair_id,
                "episode_id": control["episode_id"],
                "event_frame": control["event_frame"],
                "boundary_id": control["boundary_id"],
                "representative_candidate_id": control["representative_candidate_id"],
                "P12": control["P12"],
                "P12_percentile": control["P12_percentile"],
                "C12": control["C12"],
                "C12_percentile": control["C12_percentile"],
                "direction_evidence": control["direction_evidence"],
                "direction_evidence_percentile": control["direction_evidence_percentile"],
                "run_length": control["run_length"],
                "run_length_percentile": control["run_length_percentile"],
                "match_distance": distance,
                "distance_to_nearest_gripper_final": control["distance_to_nearest_gripper_final"],
                "selection_reason": "HIGH_C12_QUARTILE_MIN_MATCH_DISTANCE_CONTROL",
            }
        )
    return rows


def build_blinded_rows(
    arm_a: Sequence[Mapping[str, Any]],
    pairs: Sequence[tuple[Mapping[str, Any], Mapping[str, Any], float]],
    event_ids: Mapping[str, str],
    diagnostic_set_id: str,
) -> list[dict[str, Any]]:
    members: list[Mapping[str, Any]] = list(arm_a) + [pair[1] for pair in pairs]
    rows = [
        {
            "diagnostic_event_id": event_ids[str(row["boundary_id"])],
            "episode_id": row["episode_id"],
            "boundary_id": row["boundary_id"],
            "event_frame": row["event_frame"],
            "event_type": CANDIDATE_DIRECTION,
            "representative_candidate_id": row["representative_candidate_id"],
            "member_candidate_ids": row.get("member_candidate_ids", row["representative_candidate_id"]),
            "diagnostic_set_id": diagnostic_set_id,
        }
        for row in members
    ]
    rows.sort(key=lambda r: str(r["diagnostic_event_id"]))
    return rows


# ---------------------------------------------------------------------------
# Entry point


def run(
    *,
    limit_episodes: int | None = None,
    timestamp: str = DEFAULT_SET_TIMESTAMP,
    quiet: bool = False,
) -> dict[str, Any]:
    p1_config = load_g1_p1_config()
    p2_config = load_g1_p2_config()
    identity = check_identity(p1_config, p2_config)

    calibration_ids = load_calibration_episode_ids()
    if len(calibration_ids) != 12:
        raise DiagnosticBuildError(
            f"expected 12 calibration episodes, SSOT manifest has {len(calibration_ids)}"
        )
    calibration_excluded_finals = count_calibration_direction_finals()
    if calibration_excluded_finals != EXPECTED_CALIBRATION_DIRECTION_FINALS:
        raise DiagnosticBuildError(
            "calibration Direction final count mismatch: "
            f"{calibration_excluded_finals} != {EXPECTED_CALIBRATION_DIRECTION_FINALS}"
        )
    review_coverage = audit_reviewed_episode_coverage()
    if review_coverage["outside_calibration"]:
        raise DiagnosticBuildError(
            "human-reviewed episodes exist outside the calibration set: "
            + ", ".join(review_coverage["outside_calibration"])
        )

    adapter = build_can_mh_adapter(p1_config)
    pool, materialize_counters = materialize_pool(
        adapter=adapter,
        p1_config=p1_config,
        p2_config=p2_config,
        excluded_episodes=set(calibration_ids),
        limit_episodes=limit_episodes,
    )
    exclusion_counts = evaluate_exclusions(pool)
    eligible = [row for row in pool if bool(row["eligible_after_all_exclusions"])]

    selection = build_selection(eligible)
    arm_a = selection["arm_a"]
    pairs = selection["pairs"]
    event_ids = assign_diagnostic_ids(arm_a, pairs)
    selected = list(arm_a) + [pair[1] for pair in pairs]
    diagnostic_set_id = compute_set_id(selected, timestamp, event_ids)

    pool_rows = build_pool_rows(pool)
    internal_rows = build_internal_rows(arm_a, pairs, event_ids)
    blinded_rows = build_blinded_rows(arm_a, pairs, event_ids, diagnostic_set_id)

    pool_payload = render_csv(POOL_COLUMNS, pool_rows).encode("utf-8")
    internal_payload = render_csv(INTERNAL_COLUMNS, internal_rows).encode("utf-8")
    blinded_payload = render_csv(BLINDED_COLUMNS, blinded_rows).encode("utf-8")

    integrity = integrity_report(pool, selection, blinded_payload, event_ids, calibration_ids)
    if integrity["forbidden_tokens_found"]:
        raise DiagnosticBuildError(
            "BLINDING_CONTRACT_VIOLATION: " + ", ".join(integrity["forbidden_tokens_found"])
        )

    distances = [float(distance) for _, _, distance in pairs]
    summary = {
        "identity": identity,
        "design_version": DESIGN_VERSION,
        "dataset_role": DATASET_ROLE,
        "primary_hypothesis": PRIMARY_HYPOTHESIS,
        "selection_rule": SELECTION_RULE,
        "diagnostic_set_id": diagnostic_set_id,
        "calibration_episodes_excluded": len(calibration_ids),
        "calibration_episode_ids": list(calibration_ids),
        "calibration_direction_finals_excluded": calibration_excluded_finals,
        "review_coverage": review_coverage,
        "materialize_counters": materialize_counters,
        "exclusion_counts": exclusion_counts,
        "candidate_pool_count": len(pool),
        "eligible_count": len(eligible),
        "p12_eligible_count": len(selection["p12_eligible"]),
        "arm_a_pool_count": len(selection["arm_a_pool"]),
        "arm_b_pool_count": len(selection["arm_b_pool"]),
        "pairs": len(pairs),
        "arm_a_count": len(arm_a),
        "arm_b_count": len(pairs),
        "unmatched_arm_a": selection["unmatched_arm_a"],
        "match_distance_min": min(distances) if distances else float("nan"),
        "match_distance_median": median(distances) if distances else float("nan"),
        "match_distance_max": max(distances) if distances else float("nan"),
        "match_distance_q25": quantile(distances, 0.25) if distances else float("nan"),
        "match_distance_q75": quantile(distances, 0.75) if distances else float("nan"),
        "integrity": integrity,
        "payloads": {
            "pool": pool_payload,
            "internal": internal_payload,
            "blinded": blinded_payload,
        },
        "sha256": {
            "pool": hashlib.sha256(pool_payload).hexdigest(),
            "internal": hashlib.sha256(internal_payload).hexdigest(),
            "blinded": hashlib.sha256(blinded_payload).hexdigest(),
        },
    }

    if not quiet:
        write_csv_lf(POOL_CSV, POOL_COLUMNS, pool_rows)
        write_csv_lf(INTERNAL_CSV, INTERNAL_COLUMNS, internal_rows)
        write_csv_lf(BLINDED_CSV, BLINDED_COLUMNS, blinded_rows)

    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit-episodes", type=int, default=None, help="debug: cap scanned episodes")
    parser.add_argument("--timestamp", default=DEFAULT_SET_TIMESTAMP)
    parser.add_argument("--check", action="store_true", help="determinism gate against on-disk CSVs")
    args = parser.parse_args(argv)

    summary = run(limit_episodes=args.limit_episodes, timestamp=args.timestamp)

    print("=" * 74)
    print("G1-P3 TRAJECTORY MECHANISM DIAGNOSTIC SET BUILD")
    print("=" * 74)
    print(f"design_version            = {summary['design_version']}")
    print(f"dataset_role              = {summary['dataset_role']}")
    print(f"diagnostic_set_id         = {summary['diagnostic_set_id']}")
    print(f"config_hash               = {summary['identity']['config_hash']}")
    print(f"signal_contract_hash      = {summary['identity']['signal_contract_hash']}")
    print(f"segmentation_version      = {summary['identity']['segmentation_version']}")
    print("-" * 74)
    print(f"episodes scanned          = {summary['materialize_counters']['episodes_scanned']}")
    print(f"calibration eps skipped   = {summary['materialize_counters']['episodes_skipped_calibration']}")
    print(f"non-direction finals excl = {summary['materialize_counters']['non_direction_final_excluded']}")
    print(f"initial Direction finals  = {summary['exclusion_counts']['initial_direction_candidates']}")
    print(f"calibration finals excluded = {summary['calibration_direction_finals_excluded']}")
    print(f"reviewed eps outside calib  = {len(summary['review_coverage']['outside_calibration'])}")
    for key in (R_GRIPPER_PRIMARY_MERGED, R_EDGE_CONTEXT, R_NEAR_GRIPPER, R_DEGENERATE, R_RUN_LENGTH):
        print(f"  {key:<34} = {summary['exclusion_counts'][key]}")
    print(f"final eligible            = {summary['eligible_count']}")
    print("-" * 74)
    print(f"P12 eligible (top 50%)    = {summary['p12_eligible_count']}")
    print(f"low-C12 pool  (bottom 25%)= {summary['arm_a_pool_count']}")
    print(f"high-C12 pool (top 25%)   = {summary['arm_b_pool_count']}")
    print(f"matched pairs             = {summary['pairs']}")
    print(f"Arm A / Arm B             = {summary['arm_a_count']} / {summary['arm_b_count']}")
    print(f"distinct episodes         = {summary['integrity']['distinct_episodes']}")
    print(f"match distance min/med/max= {summary['match_distance_min']:.6f} / "
          f"{summary['match_distance_median']:.6f} / {summary['match_distance_max']:.6f}")
    print("-" * 74)
    print(f"BLINDING_CONTRACT         = {'PASS' if not summary['integrity']['forbidden_tokens_found'] else 'FAIL'}")
    print(f"calibration leakage       = {summary['integrity']['calibration_leakage']}")
    print(f"episode reuse             = {summary['integrity']['episode_reuse']}")
    print("-" * 74)
    for name in ("pool", "internal", "blinded"):
        print(f"{name.upper():<8} LF SHA256 = {summary['sha256'][name]}")
    print("=" * 74)

    if args.check:
        mismatches = []
        for path, key in ((POOL_CSV, "pool"), (INTERNAL_CSV, "internal"), (BLINDED_CSV, "blinded")):
            if not path.is_file():
                mismatches.append(f"MISSING: {path}")
            elif path.read_bytes() != summary["payloads"][key]:
                mismatches.append(f"DIFFERS: {path}")
        if mismatches:
            print("DETERMINISM = FAIL")
            for item in mismatches:
                print(f"  {item}")
            return 1
        print("DETERMINISM = PASS (byte-identical, LF preserved)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
