"""Deterministic development sampling for the P2-G3 tiny JSON baseline.

Everything here is a pure function of frozen artifacts and structure-only
information.  No model output, no human score and no image appearance is ever
consulted when choosing samples, so the baseline denominator cannot be
manipulated after seeing predictions.

Two provenance layers are kept separate and must not be confused:

1. **Development pool** -- every readable dataset episode minus the episodes
   reserved by frozen Formal artifacts (historical G1 usage, the 24-episode
   frozen G1 evaluation manifest, the 63-episode frozen Core Retrieval
   manifest).  Reproduced with ``main``-only code.
2. **Pinned baseline sample** -- the 10 segments previously selected for the
   Phase-1C lightweight review with the fixed salt
   ``P2_G3_PHASE1C_SIMPLE10_20261013_V1`` over the 59 segments of the 12
   Phase-1 probe episodes.  That selection used only structural fields and a
   SHA-256 ordering; it did **not** use image appearance or model output.

The Phase-1C human answers recorded on those same 10 segments are
**observability self-reports** ("can a human understand the action?").  They are
**not** semantic ground truth and are **never** used here to compute accuracy.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

PROBE_SALT = "P2_G3_PHASE1_PROBE_20261012"
PHASE1C_SALT = "P2_G3_PHASE1C_SIMPLE10_20261013_V1"
STRATUM_PER_EPISODE = 4
STRATA = ("SHORT", "MEDIUM", "LONG")

FROZEN_CORE_RETRIEVAL_RELATIVE_PATH = (
    "0-doc/10-design-review/Project2_MVP_Core_Retrieval_Manifest_FROZEN_v1_20261009.csv"
)

#: The pinned 10-segment baseline sample.
#: ``segment_id``/``start_frame``/``end_frame`` are the **frozen G1** identity and
#: are re-derived and re-verified from ``main`` code at run time; if the
#: recomputation disagrees the run fails closed instead of silently using a
#: different segment.
PINNED_BASELINE_SEGMENTS: tuple[dict[str, Any], ...] = (
    {"episode_id": "data/demo_120", "segment_id": "demo_120-S0005", "start_frame": 174,
     "end_frame": 177, "strata": "SHORT|LAST|INCOMPLETE"},
    {"episode_id": "data/demo_165", "segment_id": "demo_165-S0003", "start_frame": 82,
     "end_frame": 164, "strata": "NORMAL|INTERIOR|COMPLETE"},
    {"episode_id": "data/demo_196", "segment_id": "demo_196-S0002", "start_frame": 4,
     "end_frame": 39, "strata": "NORMAL|INTERIOR|COMPLETE"},
    {"episode_id": "data/demo_227", "segment_id": "demo_227-S0005", "start_frame": 77,
     "end_frame": 145, "strata": "NORMAL|INTERIOR|COMPLETE"},
    {"episode_id": "data/demo_277", "segment_id": "demo_277-S0005", "start_frame": 219,
     "end_frame": 223, "strata": "SHORT|LAST|INCOMPLETE"},
    {"episode_id": "data/demo_292", "segment_id": "demo_292-S0002", "start_frame": 4,
     "end_frame": 74, "strata": "NORMAL|INTERIOR|COMPLETE"},
    {"episode_id": "data/demo_33", "segment_id": "demo_33-S0001", "start_frame": 0,
     "end_frame": 3, "strata": "SHORT|FIRST|INCOMPLETE"},
    {"episode_id": "data/demo_47", "segment_id": "demo_47-S0003", "start_frame": 50,
     "end_frame": 90, "strata": "NORMAL|INTERIOR|COMPLETE"},
    {"episode_id": "data/demo_74", "segment_id": "demo_74-S0003", "start_frame": 113,
     "end_frame": 129, "strata": "NORMAL|INTERIOR|COMPLETE"},
    {"episode_id": "data/demo_75", "segment_id": "demo_75-S0001", "start_frame": 0,
     "end_frame": 3, "strata": "SHORT|FIRST|INCOMPLETE"},
)


class SamplingError(RuntimeError):
    """Raised when the frozen sampling preconditions are not met (fail closed)."""


# --------------------------------------------------------------------------- #
# provenance
# --------------------------------------------------------------------------- #
def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def probe_digest(episode_id: str) -> str:
    return hashlib.sha256(f"{PROBE_SALT}|{episode_id}".encode("utf-8")).hexdigest()


def load_frozen_core_retrieval_ids(root: Path) -> tuple[set[str], dict[str, Any]]:
    """Read the 63 reserved Core Retrieval episodes (read-only)."""

    path = root / FROZEN_CORE_RETRIEVAL_RELATIVE_PATH
    if not path.is_file():
        raise SamplingError(f"STOP_FROZEN_CORE_RETRIEVAL_MANIFEST_MISSING: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    ids = [str(row["episode_id"]) for row in rows]
    cohorts = Counter(str(row["cohort"]) for row in rows)
    expected = {"CANDIDATE_BANK": 36, "CALIBRATION_QUERY": 9, "FINAL_QUERY": 18}
    if dict(cohorts) != expected:
        raise SamplingError(f"STOP_FROZEN_CORE_RETRIEVAL_COHORT_MISMATCH: {dict(cohorts)}")
    if len(set(ids)) != 63:
        raise SamplingError(f"STOP_FROZEN_CORE_RETRIEVAL_COUNT_MISMATCH: {len(set(ids))}")
    return set(ids), {
        "source_artifact": FROZEN_CORE_RETRIEVAL_RELATIVE_PATH,
        "sha256": _sha256_file(path),
        "count": len(ids),
        "cohorts": dict(cohorts),
    }


def build_development_pool(root: str | Path | None = None) -> dict[str, Any]:
    """Development pool with explicit exclusion provenance (main-only code)."""

    from project2_g1.evaluation_manifest_preparation import (
        DATASET_ID,
        historical_usage_rows,
        load_historical_sets,
        scan_dataset,
    )
    from project2_g1.paths import PROJECT2_ROOT
    from project2_mvp.retrieval_manifest_preparation import load_frozen_g1_evaluation

    project_root = Path(root or PROJECT2_ROOT).resolve()
    historical, source_sets = load_historical_sets(project_root)
    historical_rows = historical_usage_rows(historical, source_sets)
    historical_ids = {str(row["episode_id"]) for row in historical_rows}

    _rows, frozen_eval_ids, frozen_eval_prov = load_frozen_g1_evaluation(project_root)
    frozen_retrieval_ids, frozen_retrieval_prov = load_frozen_core_retrieval_ids(project_root)

    pool, dataset = scan_dataset(project_root, historical)

    rows: list[dict[str, Any]] = []
    for row in pool:
        episode_id = str(row["episode_id"])
        reasons: list[str] = []
        if row["readability_status"] != "READABLE":
            reasons.append(str(row.get("exclusion_reason") or row["readability_status"]))
        if episode_id in historical_ids:
            reasons.append("HISTORICAL_G1_USAGE")
        if episode_id in frozen_eval_ids:
            reasons.append("FROZEN_G1_EVALUATION")
        if episode_id in frozen_retrieval_ids:
            reasons.append("FROZEN_CORE_RETRIEVAL")
        rows.append({
            "episode_id": episode_id,
            "frame_count": int(row["frame_count"]),
            "development_pool_member": "YES" if not reasons else "NO",
            "exclusion_reasons": "|".join(reasons),
        })

    members = [r for r in rows if r["development_pool_member"] == "YES"]
    if not members:
        raise SamplingError("STOP_DEVELOPMENT_POOL_EMPTY")
    return {
        "rows": rows,
        "members": members,
        "summary": {
            "dataset_id": DATASET_ID,
            "dataset_identity": dataset,
            "total_dataset_episodes": len(rows),
            "development_pool_size": len(members),
            "frozen_g1_evaluation_provenance": frozen_eval_prov,
            "frozen_core_retrieval_provenance": frozen_retrieval_prov,
        },
    }


def probe_episode_selection(root: str | Path | None = None) -> dict[str, Any]:
    """Reproduce the 12 Phase-1 probe episodes (structure-only, fixed salt)."""

    pool = build_development_pool(root)
    ordered = sorted(pool["members"], key=lambda r: (int(r["frame_count"]), str(r["episode_id"])))
    n = len(ordered)
    if n < 3 * STRATUM_PER_EPISODE:
        raise SamplingError(f"STOP_DEVELOPMENT_POOL_TOO_SMALL: {n}")
    first_cut, second_cut = n // 3, (2 * n) // 3
    enriched = []
    for index, original in enumerate(ordered):
        row = dict(original)
        row["duration_stratum"] = (
            "SHORT" if index < first_cut else "MEDIUM" if index < second_cut else "LONG"
        )
        row["probe_digest"] = probe_digest(str(row["episode_id"]))
        enriched.append(row)

    selected: list[dict[str, Any]] = []
    for stratum in STRATA:
        ranked = sorted((r for r in enriched if r["duration_stratum"] == stratum),
                        key=lambda r: (r["probe_digest"], str(r["episode_id"])))
        if len(ranked) < STRATUM_PER_EPISODE:
            raise SamplingError(f"STOP_INSUFFICIENT_STRATUM: {stratum}")
        selected.extend(ranked[:STRATUM_PER_EPISODE])

    ids = [str(r["episode_id"]) for r in selected]
    if len(set(ids)) != len(ids):
        raise SamplingError("STOP_PROBE_SELECTION_NOT_UNIQUE")
    return {
        "episode_ids": ids,
        "selection_salt": PROBE_SALT,
        "selection_rule": (
            "duration terciles over the Development pool (frame_count ASC, episode_id ASC); "
            f"within each stratum rank by SHA256('{PROBE_SALT}|' + episode_id); "
            f"take the first {STRATUM_PER_EPISODE} per stratum"
        ),
        "summary": pool["summary"],
    }


# --------------------------------------------------------------------------- #
# frozen G1 segments
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FrozenSegment:
    source_episode_id: str
    segment_id: str
    start_frame: int
    end_frame: int
    ordinal: int

    @property
    def length(self) -> int:
        return self.end_frame - self.start_frame + 1


def frozen_segments_for_episode(adapter: Any, episode_id: str) -> list[FrozenSegment]:
    """Recompute the frozen G1 segments with the frozen engine and config."""

    from project2_g1.signals import compute_formal_signals
    from project2_g1.source import load_formal_episode
    from project2_g1.stage_b_calibration import run_window
    from project2_g1.stage_c_regression import BOUNDARY_CONSOLIDATION_WINDOW

    config = _load_config()
    episode = load_formal_episode(adapter, episode_id)
    signals = {episode_id: compute_formal_signals(episode, config)}
    results, _trace = run_window(signals, BOUNDARY_CONSOLIDATION_WINDOW)
    segments = list(results[0].segments)
    out: list[FrozenSegment] = []
    for ordinal, segment in enumerate(segments, 1):
        out.append(FrozenSegment(
            source_episode_id=episode_id,
            segment_id=f"{episode_id.split('/')[-1]}-S{ordinal:04d}",
            start_frame=int(segment.start_frame),
            end_frame=int(segment.end_frame),
            ordinal=ordinal,
        ))
    return out


def left_boundary_types(adapter: Any, episode_id: str) -> dict[str, str | None]:
    """Left-boundary candidate type per frozen segment (needed by M2 keyframes)."""

    from project2_g1.signals import compute_formal_signals
    from project2_g1.source import load_formal_episode
    from project2_g1.stage_b_calibration import run_window
    from project2_g1.stage_c_regression import BOUNDARY_CONSOLIDATION_WINDOW

    config = _load_config()
    episode = load_formal_episode(adapter, episode_id)
    signals = {episode_id: compute_formal_signals(episode, config)}
    results, _trace = run_window(signals, BOUNDARY_CONSOLIDATION_WINDOW)
    result = results[0]
    events = {event.boundary_id: event for event in result.final_events}
    out: dict[str, str | None] = {}
    for ordinal, segment in enumerate(result.segments, 1):
        left = events.get(segment.left_boundary_id)
        out[f"{episode_id.split('/')[-1]}-S{ordinal:04d}"] = (
            None if left is None else left.candidate_type
        )
    return out


def _load_config() -> Any:
    from project2_g1.config import load_g1_p1_config

    return load_g1_p1_config()


def target_keyframes(adapter: Any, episode_id: str, segment: FrozenSegment,
                     left_type: str | None) -> list[int]:
    """M2 START/MIDDLE/END/GRIPPER_EVENT keyframes, deduped, target-segment only."""

    from project2_mvp.m2 import select_keyframes

    mapping = {
        "start_frame": segment.start_frame,
        "end_frame": segment.end_frame,
    }
    keyframes = select_keyframes(mapping, left_boundary_type=left_type)
    indices = sorted({int(k.frame_index) for k in keyframes})
    for index in indices:
        if not (segment.start_frame <= index <= segment.end_frame):
            raise SamplingError(
                f"STOP_KEYFRAME_OUTSIDE_SEGMENT: {segment.segment_id} frame={index}"
            )
    return indices


def resolve_baseline_samples(root: str | Path | None = None) -> dict[str, Any]:
    """Verify the pinned sample against recomputed frozen segments (fail closed)."""

    from project2_g1.source import build_can_mh_adapter

    selection = probe_episode_selection(root)
    probe_ids = set(selection["episode_ids"])
    adapter = build_can_mh_adapter(_load_config())

    needed_episodes = sorted({row["episode_id"] for row in PINNED_BASELINE_SEGMENTS})
    missing = [e for e in needed_episodes if e not in probe_ids]
    if missing:
        raise SamplingError(f"STOP_PINNED_EPISODE_NOT_IN_PROBE_SELECTION: {missing}")

    cache: dict[str, dict[str, FrozenSegment]] = {}
    boundaries: dict[str, dict[str, str | None]] = {}
    samples: list[dict[str, Any]] = []
    verified: list[dict[str, Any]] = []

    for row in PINNED_BASELINE_SEGMENTS:
        episode_id = row["episode_id"]
        if episode_id not in cache:
            cache[episode_id] = {s.segment_id: s for s in frozen_segments_for_episode(adapter, episode_id)}
            boundaries[episode_id] = left_boundary_types(adapter, episode_id)
        segment = cache[episode_id].get(row["segment_id"])
        if segment is None:
            raise SamplingError(
                f"STOP_PINNED_SEGMENT_NOT_FOUND: {row['segment_id']} in {episode_id}"
            )
        if (segment.start_frame, segment.end_frame) != (row["start_frame"], row["end_frame"]):
            raise SamplingError(
                "STOP_PINNED_SEGMENT_INTERVAL_CHANGED: "
                f"{row['segment_id']} pinned=[{row['start_frame']},{row['end_frame']}] "
                f"recomputed=[{segment.start_frame},{segment.end_frame}]"
            )
        keyframes = target_keyframes(adapter, episode_id, segment,
                                     boundaries[episode_id].get(segment.segment_id))
        samples.append({
            "sample_order": len(samples) + 1,
            "episode_id": episode_id,
            "segment_id": segment.segment_id,
            "start_frame": segment.start_frame,
            "end_frame": segment.end_frame,
            "segment_length": segment.length,
            "strata": row["strata"],
            "selection_salt": PHASE1C_SALT,
            "target_keyframes": keyframes,
            "keyframe_count": len(keyframes),
        })
        verified.append({
            "segment_id": segment.segment_id,
            "pinned_interval": [row["start_frame"], row["end_frame"]],
            "recomputed_interval": [segment.start_frame, segment.end_frame],
            "match": True,
        })

    if len(samples) != len(PINNED_BASELINE_SEGMENTS):
        raise SamplingError("STOP_SAMPLE_COUNT_MISMATCH")

    return {
        "samples": samples,
        "segment_identity_verification": verified,
        "probe_selection": selection,
        "selection_salt": PHASE1C_SALT,
        "pin_provenance": {
            "source": "p2-g3-phase1c-human-observability-20261013 :: 0-doc/90-implementation-local/review_selection.csv",
            "source_sha256": "9db2ca90b6f508f5ca6a79881cd498327ec6d65858c2245f32f1489c4586942f",
            "selection_rule": (
                "structure-only selection over the 59 segments of the 12 Phase-1 probe "
                "episodes with fixed salt; strata SHORT/NORMAL, FIRST/INTERIOR/LAST, "
                "neighbour COMPLETE/INCOMPLETE; no image appearance or model output used"
            ),
            "human_scores_are_observability_not_ground_truth": True,
        },
    }


def neighbour_context_frames(
    segments: Sequence[FrozenSegment], index: int
) -> list[tuple[int, str, str]]:
    """Context frames for segment ``index`` as ``(frame_index, role, origin_segment_id)``.

    Structural rule, aligned with the frozen Phase-1B context-window budget that
    the Owner kept as *optional* (``CONTEXT_POLICY_DECISION=KEEP_CONTEXT_OPTIONAL``):

    * ``PREV_SEGMENT_END``  -- the previous segment's last frame (at most 1)
    * ``NEXT_SEGMENT_START`` -- the next segment's first frame (at most 1)
    * ``NEXT_SEGMENT_MIDDLE`` -- the next segment's middle frame, only when that
      segment is at least 4 frames long (at most 1)

    Never crosses an episode boundary.  Context frames are only ever *context*:
    they are marked ``is_target_segment_frame=False`` and must never be cited as
    target-segment evidence.
    """

    out: list[tuple[int, str, str]] = []
    if index > 0:
        previous = segments[index - 1]
        if previous.source_episode_id == segments[index].source_episode_id:
            out.append((previous.end_frame, "PREV_SEGMENT_END", previous.segment_id))
    if index + 1 < len(segments):
        following = segments[index + 1]
        if following.source_episode_id == segments[index].source_episode_id:
            out.append((following.start_frame, "NEXT_SEGMENT_START", following.segment_id))
            if following.length >= 4:
                middle = (following.start_frame + following.end_frame) // 2
                out.append((middle, "NEXT_SEGMENT_MIDDLE", following.segment_id))
    return out[:3]


def write_json(path: str | Path, payload: Any) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
                   encoding="utf-8")
    return out
