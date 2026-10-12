"""Phase-1B structural evidence-delta analysis (deterministic, no VLM).

Question this answers
---------------------
Adding neighbour-segment frames increases the *number* of images.  Does it also
increase the **instrumented** evidence available about gripper state and end
effector motion, measured on allowed fields only (``gripper_qpos``, ``eef_pos``)?

This is a **structural proxy**, not ground truth.  It cannot tell you whether a
human can see a grasp; it only tells you whether the extra frames carry a wider
instrumented range than the in-segment keyframes alone.  Every output row is
tagged ``STRUCTURAL_PROXY_NOT_HUMAN_GT`` so it can never be mistaken for a
scored observability label.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from project2_g1.config import load_g1_p1_config
from project2_g1.paths import PROJECT2_ROOT
from project2_g1.source import build_can_mh_adapter, load_formal_episode

from .development_pool import write_json

STRUCTURAL_DELTA_VERSION = "P2_G3_PHASE1B_STRUCTURAL_DELTA_V1"

# Aperture proxy: sum of the two gripper finger joint positions (metres).
# A change of at least this much between two frames is treated as an
# instrumented gripper transition.
GRIPPER_TRANSITION_THRESHOLD = 0.005
PROXY_TAG = "STRUCTURAL_PROXY_NOT_HUMAN_GT"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _aperture(gripper_qpos: np.ndarray, index: int) -> float:
    return float(np.sum(np.abs(np.asarray(gripper_qpos[index], dtype=np.float64))))


def _path_length(eef_pos: np.ndarray, indices: Sequence[int]) -> float:
    ordered = sorted(set(int(i) for i in indices))
    if len(ordered) < 2:
        return 0.0
    pts = np.asarray(eef_pos, dtype=np.float64)[ordered]
    return float(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)))


def compute_structural_delta(
    run_dir: str | Path,
    *,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    run = Path(run_dir).resolve()
    window_rows = _read_csv(run / "context_window_manifest.csv")
    frame_rows = _read_csv(run / "evidence_frame_manifest.csv")

    by_segment: dict[str, list[dict[str, str]]] = {}
    for row in frame_rows:
        by_segment.setdefault(row["target_segment_id"], []).append(row)

    root = Path(project_root or PROJECT2_ROOT).resolve()
    config = load_g1_p1_config()
    adapter = build_can_mh_adapter(config)

    rows: list[dict[str, Any]] = []
    try:
        cache: dict[str, Any] = {}
        for window in window_rows:
            episode_id = window["episode_id"]
            if episode_id not in cache:
                cache[episode_id] = load_formal_episode(adapter, episode_id)
            episode = cache[episode_id]
            gripper = np.asarray(episode.gripper_qpos, dtype=np.float64)
            eef = np.asarray(episode.eef_pos, dtype=np.float64)

            a_indices = json.loads(window["target_keyframe_indices"])
            b_indices = sorted(
                set(int(r["frame_index"]) for r in by_segment.get(window["segment_id"], []))
                | set(int(i) for i in a_indices)
            )

            a_ap = [_aperture(gripper, i) for i in a_indices]
            b_ap = [_aperture(gripper, i) for i in b_indices]
            a_range = max(a_ap) - min(a_ap)
            b_range = max(b_ap) - min(b_ap)

            a_path = _path_length(eef, a_indices)
            b_path = _path_length(eef, b_indices)

            rows.append({
                "episode_id": episode_id,
                "segment_id": window["segment_id"],
                "start_frame": window["start_frame"],
                "end_frame": window["end_frame"],
                "prev_status": window["prev_status"],
                "next_status": window["next_status"],
                "a_frame_count": len(a_indices),
                "b_frame_count": len(b_indices),
                "added_frame_count": len(b_indices) - len(a_indices),
                "a_gripper_range": round(a_range, 6),
                "b_gripper_range": round(b_range, 6),
                "gripper_range_gain": round(b_range - a_range, 6),
                "a_gripper_transition_detectable": a_range >= GRIPPER_TRANSITION_THRESHOLD,
                "b_gripper_transition_detectable": b_range >= GRIPPER_TRANSITION_THRESHOLD,
                "gripper_transition_newly_detectable": (
                    a_range < GRIPPER_TRANSITION_THRESHOLD
                    and b_range >= GRIPPER_TRANSITION_THRESHOLD
                ),
                "gripper_transition_lost": (
                    a_range >= GRIPPER_TRANSITION_THRESHOLD
                    and b_range < GRIPPER_TRANSITION_THRESHOLD
                ),
                "a_eef_path_m": round(a_path, 6),
                "b_eef_path_m": round(b_path, 6),
                "eef_path_gain_m": round(b_path - a_path, 6),
                "frame_span_gain": (
                    max(b_indices) - min(b_indices) - (max(a_indices) - min(a_indices))
                ),
                "evidence_class": PROXY_TAG,
            })
    finally:
        close = getattr(adapter, "close", None)
        if callable(close):
            close()

    n = len(rows)
    newly = sum(bool(r["gripper_transition_newly_detectable"]) for r in rows)
    lost = sum(bool(r["gripper_transition_lost"]) for r in rows)
    gain_pos = sum(float(r["gripper_range_gain"]) > 0 for r in rows)
    path_gain_pos = sum(float(r["eef_path_gain_m"]) > 0 for r in rows)

    summary = {
        "structural_delta_version": STRUCTURAL_DELTA_VERSION,
        "evidence_class": PROXY_TAG,
        "warning": (
            "Structural proxy only. These numbers describe instrumented gripper/EEF ranges, "
            "NOT whether a human can see an object interaction. Do not report them as "
            "observability ground truth."
        ),
        "gripper_transition_threshold": GRIPPER_TRANSITION_THRESHOLD,
        "segments": n,
        "segments_with_gripper_range_gain": gain_pos,
        "segments_with_eef_path_gain": path_gain_pos,
        "segments_gripper_transition_newly_detectable": newly,
        "segments_gripper_transition_lost": lost,
        "segments_with_any_added_frame": sum(int(r["added_frame_count"]) > 0 for r in rows),
        "mean_added_frames": (
            float(np.mean([int(r["added_frame_count"]) for r in rows])) if rows else None
        ),
        "mean_gripper_range_gain": (
            float(np.mean([float(r["gripper_range_gain"]) for r in rows])) if rows else None
        ),
        "mean_eef_path_gain_m": (
            float(np.mean([float(r["eef_path_gain_m"]) for r in rows])) if rows else None
        ),
        "vlm_invoked": False,
    }

    _write_csv(run / "structural_delta.csv", rows, [
        "episode_id", "segment_id", "start_frame", "end_frame",
        "prev_status", "next_status",
        "a_frame_count", "b_frame_count", "added_frame_count",
        "a_gripper_range", "b_gripper_range", "gripper_range_gain",
        "a_gripper_transition_detectable", "b_gripper_transition_detectable",
        "gripper_transition_newly_detectable", "gripper_transition_lost",
        "a_eef_path_m", "b_eef_path_m", "eef_path_gain_m",
        "frame_span_gain", "evidence_class",
    ])
    write_json(run / "structural_delta_summary.json", {
        **summary,
        "computed_at": datetime.now().astimezone().isoformat(),
    })
    return summary


def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="P2-G3 Phase-1B structural evidence delta")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(compute_structural_delta(args.run_dir), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
