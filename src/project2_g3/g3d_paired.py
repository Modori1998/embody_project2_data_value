"""G3D frozen input checks and multi-event paired scoring (no model calls)."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from project2_mvp.m2 import summarize_motion

ALLOWED_MOTION_KEYS = (
    "eef_displacement_xyz", "eef_net_displacement_m", "eef_path_length_m",
    "gripper_start_aperture", "gripper_end_aperture",
    "gripper_start_state", "gripper_end_state", "gripper_transition_present",
    "action_magnitude_mean", "action_magnitude_max", "action_magnitude_std",
    "action_semantic",
)
EVENTS = ("grasp_attempt", "object_motion", "release_attempt")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_frames(row: dict, rgb_dir: Path) -> list[Path]:
    indices = [int(v) for v in row["target_keyframes"].split(";")]
    hashes = row["frame_png_sha256s"].split(";")
    if len(indices) != 3 or len(hashes) != 3 or len(set(indices)) != 3:
        raise ValueError("STOP_FRAME_MANIFEST_SHAPE")
    if indices[0] < int(row["start_frame"]) or indices[-1] > int(row["end_frame"]):
        raise ValueError("STOP_CROSS_BOUNDARY_FRAME")
    paths = [rgb_dir / f'{row["segment_id"]}_f{i:05d}.png' for i in indices]
    if any(not p.is_file() or sha256(p) != h for p, h in zip(paths, hashes)):
        raise ValueError("STOP_RGB_SHA_MISMATCH")
    return paths


def motion_block(segment, episode, *, gripper_state=None, left_boundary_type=None) -> str:
    """Only policy-visible, same-episode, same-interval M2 features may enter B."""
    get = lambda key: segment[key] if isinstance(segment, dict) else getattr(segment, key)
    if get("source_episode_id") != episode.source_episode_id:
        raise ValueError("STOP_EPISODE_IDENTITY")
    n = len(episode.eef_pos)
    if any(len(getattr(episode, field)) != n for field in ("gripper_qpos", "actions")):
        raise ValueError("STOP_TEMPORAL_ALIGNMENT")
    result = summarize_motion(segment, episode, gripper_state=gripper_state,
                              left_boundary_type=left_boundary_type)
    if (result["segment_id"], result["start_frame"], result["end_frame"]) != (
        get("segment_id"), get("start_frame"), get("end_frame")
    ):
        raise ValueError("STOP_SEGMENT_IDENTITY")
    selected = {key: result[key] for key in ALLOWED_MOTION_KEYS}
    def finite(v):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return math.isfinite(v)
        if isinstance(v, list):
            return all(finite(x) for x in v)
        return True
    if not all(finite(v) for v in selected.values()):
        raise ValueError("STOP_NONFINITE_MOTION")
    return ("\n\n# Robot state within this segment (B only)\n"
            "EEF positions/displacements/path are metres; gripper aperture uses source qpos units. "
            "Actions are normalized controller inputs, not observed object motion. "
            "EEF movement does not prove object_motion; gripper closure does not prove grasp success. "
            "Apply the same visual event and frame evidence rules.\n"
            + json.dumps(selected, ensure_ascii=False, sort_keys=True, allow_nan=False))


def score_pairs(rows: list[dict]) -> dict:
    """Each row holds human, A and B parsed v0.2 JSON, joined by segment ID."""
    if len({r["segment_id"] for r in rows}) != len(rows):
        raise ValueError("STOP_DUPLICATE_SEGMENT")
    out = {}
    for arm in ("A", "B"):
        tp = fp = fn = phase_ok = exact = 0
        by_type = {event: {"tp": 0, "fp": 0, "fn": 0} for event in EVENTS}
        for row in rows:
            truth = set(row["human"]["events"])
            pred = {e["event_type"] for e in row[arm]["events"]}
            phase_ok += row[arm]["motion_phase"] == row["human"]["motion_phase"]
            exact += pred == truth
            tp += len(pred & truth); fp += len(pred - truth); fn += len(truth - pred)
            for event in EVENTS:
                by_type[event]["tp"] += event in pred and event in truth
                by_type[event]["fp"] += event in pred and event not in truth
                by_type[event]["fn"] += event not in pred and event in truth
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        out[arm] = {"motion_phase_accuracy": phase_ok / len(rows) if rows else 0.0,
                    "phase_correct": phase_ok, "exact_match": exact,
                    "event_type_micro_precision": precision,
                    "event_type_micro_recall": recall,
                    "event_type_micro_f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
                    "event_presence_precision": sum(bool(r[arm]["events"]) and bool(r["human"]["events"]) for r in rows) /
                    max(1, sum(bool(r[arm]["events"]) for r in rows)),
                    "event_presence_recall": sum(bool(r[arm]["events"]) and bool(r["human"]["events"]) for r in rows) /
                    max(1, sum(bool(r["human"]["events"]) for r in rows)),
                    "by_type": by_type}
        p, q = out[arm]["event_presence_precision"], out[arm]["event_presence_recall"]
        out[arm]["event_presence_f1"] = 2*p*q/(p+q) if p+q else 0.0
    out["segments"] = [{"segment_id": r["segment_id"], "human": r["human"],
                        "A": r["A"], "B": r["B"],
                        "event_comparison": ("both_correct" if set(e["event_type"] for e in r["A"]["events"]) == set(r["human"]["events"]) and set(e["event_type"] for e in r["B"]["events"]) == set(r["human"]["events"]) else
                                             "A_only" if set(e["event_type"] for e in r["A"]["events"]) == set(r["human"]["events"]) else
                                             "B_only" if set(e["event_type"] for e in r["B"]["events"]) == set(r["human"]["events"]) else "both_wrong")}
                       for r in rows]
    return out
