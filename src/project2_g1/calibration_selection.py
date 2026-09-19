"""Leakage-safe Fresh Calibration episode screening and coverage selection.

Inputs are limited to dataset metadata, Formal G1 signals, and one fixed
baseline Detector config.  No video, Human Review, GT, reward, success, done,
or simulator object state is read here.
"""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from .boundary_engine import (
    CANDIDATE_DIRECTION,
    CANDIDATE_GRIPPER,
    CANDIDATE_IDLE_TO_MOVE,
    CANDIDATE_MOVE_TO_IDLE,
    run_boundary_engine,
)
from .signals import compute_formal_signals
from .source import enumerate_episodes, load_formal_episode

SELECTION_VERSION = "P2_G1_FRESH_CALIBRATION_SELECTION_V1"
PROTOCOL_DOCUMENT = "Project2_G1_P3_Calibration_Protocol_FROZEN_v1_20260917.md"
SOURCE_DATASET_ID = "robomimic_v15_can_mh"
CONTROL_HZ = 20.0

SCREENING_FEATURES = (
    "episode_id", "episode_length_frames", "duration_seconds",
    "baseline_candidate_count", "baseline_final_boundary_count",
    "gripper_primary_count", "direction_primary_count",
    "move_to_idle_primary_count", "idle_to_move_primary_count",
    "merged_boundary_count", "gripper_direction_merged_count",
    "short_segment_count", "min_segment_length", "mean_segment_length",
    "max_segment_length", "direction_primary_ratio", "gripper_primary_ratio",
    "quality_group", "selection_screening_status",
)
FORBIDDEN_SELECTION_FIELDS = frozenset({
    "object", "object_gt", "can_pos", "can_to_eef", "reward", "done", "success",
    "human_review", "human_gt", "human_decision", "reviewer", "review_id",
})

SELECTION_FIELDS = (
    "selection_version", "episode_id", "source_dataset_id",
    "episode_length_frames", "duration_seconds", "baseline_candidate_count",
    "baseline_final_boundary_count", "gripper_primary_count",
    "direction_primary_count", "move_to_idle_primary_count",
    "idle_to_move_primary_count", "merged_boundary_count",
    "gripper_direction_merged_count", "short_segment_count",
    "length_bucket", "boundary_count_bucket", "selection_bucket",
    "selection_reason", "is_existing_seed", "is_selected_fresh",
    "evaluation_role", "screening_config_hash", "signal_contract_hash",
)


class SelectionError(ValueError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _nearest_rank(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise SelectionError("cannot derive bucket threshold from empty values")
    index = max(0, min(len(ordered) - 1, int(np.ceil(quantile * len(ordered))) - 1))
    return ordered[index]


def derive_thresholds(rows: list[dict[str, Any]]) -> dict[str, float]:
    if not rows:
        raise SelectionError("eligible screening pool is empty")
    positive_direction = [float(row["direction_primary_ratio"]) for row in rows if float(row["direction_primary_ratio"]) > 0]
    return {
        "length_q33": _nearest_rank((row["episode_length_frames"] for row in rows), 1 / 3),
        "length_q67": _nearest_rank((row["episode_length_frames"] for row in rows), 2 / 3),
        "boundary_q33": _nearest_rank((row["baseline_final_boundary_count"] for row in rows), 1 / 3),
        "boundary_q67": _nearest_rank((row["baseline_final_boundary_count"] for row in rows), 2 / 3),
        "direction_positive_median": _nearest_rank(positive_direction or [0.0], 0.5),
        "short_segment_median": _nearest_rank((row["short_segment_count"] for row in rows), 0.5),
    }


def _bucket(value: float, low: float, high: float, names: tuple[str, str, str]) -> str:
    if value <= low:
        return names[0]
    if value <= high:
        return names[1]
    return names[2]


def annotate_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, float]]:
    thresholds = derive_thresholds(rows)
    out = []
    for raw in rows:
        row = dict(raw)
        row["length_bucket"] = _bucket(
            float(row["episode_length_frames"]), thresholds["length_q33"], thresholds["length_q67"],
            ("SHORT", "MEDIUM", "LONG"),
        )
        row["boundary_count_bucket"] = _bucket(
            float(row["baseline_final_boundary_count"]), thresholds["boundary_q33"], thresholds["boundary_q67"],
            ("LOW", "MEDIUM", "HIGH"),
        )
        ratio = float(row["direction_primary_ratio"])
        if ratio == 0:
            row["direction_bucket"] = "DIRECTION_LIGHT"
        elif ratio <= thresholds["direction_positive_median"]:
            row["direction_bucket"] = "DIRECTION_MEDIUM"
        else:
            row["direction_bucket"] = "DIRECTION_HEAVY"
        labels = []
        preservation = (
            int(row["gripper_primary_count"]) > 0
            and row["boundary_count_bucket"] in {"LOW", "MEDIUM"}
            and int(row["short_segment_count"]) <= thresholds["short_segment_median"]
            and row["direction_bucket"] != "DIRECTION_HEAVY"
        )
        if preservation:
            labels.append("PRESERVATION_CANDIDATE")
        if int(row["direction_primary_count"]) > 0:
            labels.append("DIRECTION_COVERAGE")
        if row["length_bucket"] == "LONG" or row["boundary_count_bucket"] == "HIGH":
            labels.append("COMPLEXITY_CANDIDATE")
        row["selection_labels"] = labels
        row["selection_bucket"] = "|".join(labels) if labels else "STRUCTURAL_DIVERSITY"
        out.append(row)
    return out, thresholds


def screen_dataset(
    adapter, p1_config, p2_config, *, exclude_episode_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    excluded = set(exclude_episode_ids or set())
    for identity in enumerate_episodes(adapter):
        if identity.source_episode_id in excluded:
            continue
        try:
            episode = load_formal_episode(adapter, identity.source_episode_id)
            signals = compute_formal_signals(episode, p1_config)
            result = run_boundary_engine(signals, p2_config)
            finals = result.final_events
            primary = Counter(event.candidate_type for event in finals)
            merged = [event for event in finals if int(event.member_candidate_count) > 1]
            grip_dir = [
                event for event in merged
                if CANDIDATE_GRIPPER in event.member_candidate_types
                and CANDIDATE_DIRECTION in event.member_candidate_types
            ]
            segments = [int(segment.duration_frames) for segment in result.segments]
            total_final = len(finals)
            weak = adapter.get_weak_reference(identity.source_episode_id)
            rows.append({
                "episode_id": identity.source_episode_id,
                "episode_length_frames": int(identity.num_steps),
                "duration_seconds": round(float(identity.num_steps) / CONTROL_HZ, 6),
                "baseline_candidate_count": len(result.candidates),
                "baseline_final_boundary_count": total_final,
                "gripper_primary_count": primary[CANDIDATE_GRIPPER],
                "direction_primary_count": primary[CANDIDATE_DIRECTION],
                "move_to_idle_primary_count": primary[CANDIDATE_MOVE_TO_IDLE],
                "idle_to_move_primary_count": primary[CANDIDATE_IDLE_TO_MOVE],
                "merged_boundary_count": len(merged),
                "gripper_direction_merged_count": len(grip_dir),
                "short_segment_count": sum(bool(segment.short_segment_flag) for segment in result.segments),
                "min_segment_length": min(segments),
                "mean_segment_length": round(float(sum(segments)) / len(segments), 6),
                "max_segment_length": max(segments),
                "direction_primary_ratio": round(primary[CANDIDATE_DIRECTION] / total_final, 6) if total_final else 0.0,
                "gripper_primary_ratio": round(primary[CANDIDATE_GRIPPER] / total_final, 6) if total_final else 0.0,
                "quality_group": str(weak.get("quality_bucket") or "UNASSIGNED"),
                "selection_screening_status": "PASS",
            })
        except Exception as exc:  # fail is reported, never silently omitted
            failures.append({"episode_id": identity.source_episode_id, "failure_reason": f"{type(exc).__name__}: {exc}"})
    rows.sort(key=lambda item: item["episode_id"])
    failures.sort(key=lambda item: item["episode_id"])
    return rows, failures


def _signature(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row["length_bucket"]), str(row["boundary_count_bucket"]),
        str(row["direction_bucket"]), str(row["quality_group"]),
    )


def build_shortlist(rows: list[dict[str, Any]], *, n: int = 12) -> list[dict[str, Any]]:
    """Greedy set coverage over explicit structural atoms; no weighted score."""
    if len(rows) < n:
        raise SelectionError(f"eligible pool has {len(rows)} rows, cannot build shortlist of {n}")
    chosen: list[dict[str, Any]] = []
    remaining = list(rows)
    covered: set[tuple[str, str]] = set()

    def atoms(row: Mapping[str, Any]) -> set[tuple[str, str]]:
        values = {
            ("length", str(row["length_bucket"])),
            ("boundary", str(row["boundary_count_bucket"])),
            ("direction", str(row["direction_bucket"])),
            ("quality", str(row["quality_group"])),
            ("merged", "YES" if int(row["merged_boundary_count"]) > 0 else "NO"),
            ("grip_dir_merged", "YES" if int(row["gripper_direction_merged_count"]) > 0 else "NO"),
        }
        values.update(("selection", label) for label in row["selection_labels"])
        return values

    def pick_one(predicate) -> None:
        eligible = [row for row in remaining if predicate(row)]
        if not eligible:
            raise SelectionError("candidate pool cannot satisfy shortlist coverage seed")
        picked = min(
            eligible,
            key=lambda row: (-len(atoms(row) - covered), _signature(row), str(row["episode_id"])),
        )
        chosen.append(picked)
        covered.update(atoms(picked))
        remaining.remove(picked)

    def ensure_count(wanted: int, predicate) -> None:
        while sum(bool(predicate(row)) for row in chosen) < wanted:
            pick_one(predicate)

    ensure_count(3, lambda row: "PRESERVATION_CANDIDATE" in row["selection_labels"])
    ensure_count(2, lambda row: "DIRECTION_COVERAGE" in row["selection_labels"])
    ensure_count(1, lambda row: "COMPLEXITY_CANDIDATE" in row["selection_labels"])
    if sum(int(row["gripper_direction_merged_count"]) > 0 for row in rows) >= 2:
        ensure_count(2, lambda row: int(row["gripper_direction_merged_count"]) > 0)

    while len(chosen) < n:
        ranked = sorted(
            remaining,
            key=lambda row: (
                -len(atoms(row) - covered),
                _signature(row),
                str(row["episode_id"]),
            ),
        )
        picked = ranked[0]
        chosen.append(picked)
        covered.update(atoms(picked))
        remaining.remove(picked)
    return sorted(chosen, key=lambda item: item["episode_id"])


def _feasible(combo: tuple[dict[str, Any], ...], *, require_grip_dir_merged: bool) -> bool:
    label_counts = Counter(label for row in combo for label in row["selection_labels"])
    return (
        label_counts["PRESERVATION_CANDIDATE"] >= 3
        and label_counts["DIRECTION_COVERAGE"] >= 2
        and label_counts["COMPLEXITY_CANDIDATE"] >= 1
        and len({row["length_bucket"] for row in combo}) >= 2
        and len({row["boundary_count_bucket"] for row in combo}) >= 2
        and sum(int(row["gripper_primary_count"]) > 0 for row in combo) >= 2
        and (not require_grip_dir_merged or sum(int(row["gripper_direction_merged_count"]) > 0 for row in combo) >= 2)
        and len({row["quality_group"] for row in combo}) >= 2
    )


def select_final(shortlist: list[dict[str, Any]], *, n: int = 6) -> list[dict[str, Any]]:
    require_merged = sum(int(row["gripper_direction_merged_count"]) > 0 for row in shortlist) >= 2
    feasible = [combo for combo in itertools.combinations(shortlist, n) if _feasible(combo, require_grip_dir_merged=require_merged)]
    if not feasible:
        raise SelectionError("shortlist has no Final 6 combination satisfying coverage constraints")

    def coverage_key(combo: tuple[dict[str, Any], ...]) -> tuple[Any, ...]:
        structural = len({(row["length_bucket"], row["boundary_count_bucket"]) for row in combo})
        direction = len({row["direction_bucket"] for row in combo})
        quality = len({row["quality_group"] for row in combo})
        merged = len({"MERGED" if int(row["merged_boundary_count"]) > 0 else "UNMERGED" for row in combo})
        ids = tuple(sorted(str(row["episode_id"]) for row in combo))
        return (-structural, -direction, -quality, -merged, ids)

    selected = min(feasible, key=coverage_key)
    return sorted((dict(row) for row in selected), key=lambda item: item["episode_id"])


def selection_reason(row: Mapping[str, Any]) -> str:
    labels = set(row["selection_labels"])
    facts = (
        f"{row['length_bucket']} length ({row['episode_length_frames']} frames), "
        f"{row['boundary_count_bucket']} Final count ({row['baseline_final_boundary_count']}), "
        f"Gripper Primary={row['gripper_primary_count']}, Direction Primary={row['direction_primary_count']}, "
        f"Gripper+Direction merged={row['gripper_direction_merged_count']}, short segments={row['short_segment_count']}"
    )
    purposes = []
    if "PRESERVATION_CANDIDATE" in labels:
        purposes.append("preserve stable hard/merged behavior")
    if "DIRECTION_COVERAGE" in labels:
        purposes.append("cover independent Direction behavior for later blind Human Review")
    if "COMPLEXITY_CANDIDATE" in labels:
        purposes.append("cover long/high-boundary structural complexity")
    if not purposes:
        purposes.append("add structural diversity")
    return facts + "; selected to " + ", and ".join(purposes) + "."


def validate_selection(
    *, shortlist: list[dict[str, Any]], selected: list[dict[str, Any]], seed_ids: set[str],
    config_hash: str, expected_config_hash: str, signal_hash: str, expected_signal_hash: str,
) -> dict[str, Any]:
    errors = []
    ids = [str(row["episode_id"]) for row in selected]
    if len(ids) != 6 or len(set(ids)) != 6:
        errors.append("fresh count must be exactly 6 with no duplicates")
    if set(ids) & seed_ids:
        errors.append("fresh IDs overlap Seed IDs")
    if config_hash != expected_config_hash:
        errors.append("screening config hash differs from Seed baseline")
    if signal_hash != expected_signal_hash:
        errors.append("signal contract hash differs from Seed baseline")
    if not _feasible(tuple(selected), require_grip_dir_merged=sum(int(row["gripper_direction_merged_count"]) > 0 for row in shortlist) >= 2):
        errors.append("Final 6 coverage constraints failed")
    if any(str(row.get("evaluation_role")) != "UNASSIGNED" for row in selected):
        errors.append("Evaluation role was assigned")
    fields = set().union(*(row.keys() for row in shortlist)) if shortlist else set()
    if fields & FORBIDDEN_SELECTION_FIELDS:
        errors.append(f"forbidden fields present: {sorted(fields & FORBIDDEN_SELECTION_FIELDS)}")
    if errors:
        raise SelectionError("SELECTION_VALIDATION_FAILED: " + " | ".join(errors))
    return {"status": "PASS", "fresh_count": 6, "seed_overlap": 0}


def deterministic_manifest_id(payload: Mapping[str, Any]) -> str:
    stable = dict(payload)
    stable.pop("created_at", None)
    stable.pop("manifest_id", None)
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "g1_fresh_calibration_manifest_" + hashlib.sha256(encoded).hexdigest()[:12]


def write_csv_exclusive(path: Path, fieldnames: Iterable[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def validate_manifest_round_trip(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "manifest_id", "created_at", "protocol_document", "selection_version",
        "source_dataset_id", "existing_seed_export_id", "existing_seed_episode_ids",
        "fresh_episode_ids", "target_calibration_count", "fresh_count", "evaluation_usage",
        "parameter_search_allowed", "human_review_status",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise SelectionError(f"manifest missing fields: {missing}")
    if len(payload["fresh_episode_ids"]) != 6 or len(set(payload["fresh_episode_ids"])) != 6:
        raise SelectionError("manifest fresh_episode_ids invalid")
    if set(payload["fresh_episode_ids"]) & set(payload["existing_seed_episode_ids"]):
        raise SelectionError("manifest Seed/Fresh overlap")
    if payload["parameter_search_allowed"] is not False or payload["human_review_status"] != "NOT_STARTED":
        raise SelectionError("manifest gate fields invalid")
    expected_id = deterministic_manifest_id(payload)
    if payload["manifest_id"] != expected_id:
        raise SelectionError("manifest_id mismatch")
    return payload
