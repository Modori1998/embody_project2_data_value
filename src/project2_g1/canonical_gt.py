"""Build an immutable Combined Canonical Human Boundary GT snapshot from Exports.

P3 reads only P2_G1_HUMAN_CALIBRATION_EXPORT_V1 packages.  It never opens the
Web-owned SQLite Human Review SSOT, never matches pred↔GT, and never scores.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from project2_g1_audit_web.calibration_export import (
    ADDED_FIELDS,
    DATA_FILES,
    EXPORT_CONTRACT,
    PREDICTED_FIELDS,
    SIGNAL_FIELDS,
)
from project2_g1_audit_web.hashes import SOURCE_DATASET_ID, sha256_file, tree_fingerprint

from .boundary_engine import CANDIDATE_DIRECTION, CANDIDATE_GRIPPER

SIGNAL_NAMES = (
    "TRANSLATION",
    "DIRECTION",
    "GRIPPER",
    "ROTATION",
    "ACTION",
    "VIDEO_ALIGNMENT",
)

CANONICAL_GT_CONTRACT_VERSION = "P2_G1_CANONICAL_HUMAN_BOUNDARY_GT_V1"
CALIBRATION_PROTOCOL_EFFECTIVE_VERSION = "FROZEN_v1.1"
MATCHING_RULE_ID = "MAX_CARDINALITY_MIN_TOTAL_DISTANCE_ONE_TO_ONE_V1"
TOLERANCE_FRAMES = 3
CONFIG_BASELINE_HASH = "dde590e759a31cb8c865369e18256ebecbbd01bc94a58e1d3ca695bb50f2a630"
SIGNAL_CONTRACT_HASH = "24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d"

GT_SOURCE_VALID = "VALID_INHERIT"
GT_SOURCE_MISALIGNED = "MISALIGNED_CORRECTED"
GT_SOURCE_ADDED = "HUMAN_ADDED"
GT_SOURCE_RANK = {GT_SOURCE_MISALIGNED: 0, GT_SOURCE_ADDED: 1, GT_SOURCE_VALID: 2}

PROTECTED_GRIPPER = "GRIPPER_PRIMARY"
PROTECTED_DIRECTION = "VALID_DIRECTION_PRIMARY"
PROTECTED_MERGED = "MERGED_GRIPPER_CLUSTER"
PROTECTED_OTHER = "OTHER"

PACKAGE_SEED = "SEED"
PACKAGE_FRESH = "FRESH"

CANONICAL_GT_FIELDS = (
    "canonical_gt_snapshot_id", "gt_id", "episode_id", "gt_frame", "gt_source",
    "protected_class", "source_package", "source_export_id", "source_run_id",
    "source_boundary_id", "source_review_id", "human_decision", "reason_code",
    "comment", "source_run_stage", "source_set_role",
)
KNOWN_FP_FIELDS = (
    "canonical_gt_snapshot_id", "episode_id", "anchor_frame", "source_package",
    "source_export_id", "source_run_id", "source_boundary_id", "source_review_id",
    "candidate_type", "representative_candidate_id", "member_candidate_ids",
    "member_candidate_types", "member_candidate_frames", "member_candidate_count",
    "reason_code", "comment", "error_mode",
)
SNAPSHOT_FILES = (
    "canonical_gt_meta.json",
    "combined_calibration_manifest.json",
    "canonical_human_boundary_gt.csv",
    "known_false_positive_anchor.csv",
)

SEED_ROLE = {
    "source_package": PACKAGE_SEED,
    "intended_role": "CALIBRATION_SEED",
    "source_run_stage": "EXPLORATORY_AUDIT",
    "source_set_role": "EXPLORATORY",
}
FRESH_ROLE = {
    "source_package": PACKAGE_FRESH,
    "intended_role": "CALIBRATION",
    "source_run_stage": "CALIBRATION",
    "source_set_role": "CALIBRATION",
    "calibration_role": "BASELINE_HUMAN_AUDIT",
    "calibration_config_role": "BASELINE_UNMODIFIED",
}


class CanonicalGTBlocked(ValueError):
    def __init__(self, errors: Iterable[str]):
        self.errors = [str(item) for item in errors if str(item).strip()]
        super().__init__("CANONICAL_GT_BLOCKED: " + " | ".join(self.errors))


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise CanonicalGTBlocked([f"{path.name}: missing header"])
        return list(reader.fieldnames), list(reader)


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _parse_int(value: Any, *, field: str) -> int:
    text = str(value or "").strip()
    if text == "":
        raise CanonicalGTBlocked([f"{field} is required"])
    try:
        return int(text)
    except ValueError as exc:
        raise CanonicalGTBlocked([f"{field} is not an integer: {value}"]) from exc


def _split_members(value: str) -> list[str]:
    return [part for part in str(value or "").split("|") if part]


def classify_protected_class(row: Mapping[str, str], *, gt_source: str) -> str:
    if gt_source == GT_SOURCE_ADDED:
        return PROTECTED_OTHER
    member_types = _split_members(row.get("member_candidate_types") or "")
    try:
        member_count = int(str(row.get("member_candidate_count") or "0").strip() or "0")
    except ValueError:
        member_count = len(member_types)
    if member_count >= 2 and CANDIDATE_GRIPPER in member_types:
        return PROTECTED_MERGED
    candidate_type = str(row.get("candidate_type") or "")
    if candidate_type == CANDIDATE_GRIPPER:
        return PROTECTED_GRIPPER
    if candidate_type == CANDIDATE_DIRECTION:
        return PROTECTED_DIRECTION
    return PROTECTED_OTHER


def load_error_mode_map(path: str | Path | None) -> dict[tuple[str, str, str], str]:
    if path is None:
        return {}
    mapping_path = Path(path)
    if not mapping_path.is_file():
        return {}
    _, rows = _read_csv(mapping_path)
    mapping: dict[tuple[str, str, str], str] = {}
    conflicts: list[str] = []
    for row in rows:
        if str(row.get("human_decision") or "") != "REDUNDANT":
            continue
        key = (
            str(row.get("run_id") or ""),
            str(row.get("episode_id") or ""),
            str(row.get("boundary_id") or ""),
        )
        mode = str(row.get("error_mode") or "").strip() or "UNASSIGNED"
        if key in mapping and mapping[key] != mode:
            conflicts.append(f"conflicting error_mode for {key}")
        mapping[key] = mode
    if conflicts:
        raise CanonicalGTBlocked(conflicts)
    return mapping


def validate_export_disk(
    path: str | Path,
    *,
    expected_role: Mapping[str, str],
    require_source_run_dir: Path | None = None,
) -> dict[str, Any]:
    root = Path(path)
    errors: list[str] = []
    if not root.is_dir():
        raise CanonicalGTBlocked([f"export directory missing: {root}"])
    meta_path = root / "export_meta.json"
    if not meta_path.is_file():
        raise CanonicalGTBlocked([f"export_meta.json missing: {root}"])
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("export_contract") != EXPORT_CONTRACT:
        errors.append(f"{root.name}: export_contract mismatch")
    export_id = str(meta.get("export_id") or "")
    if not export_id or export_id != root.name:
        errors.append(f"{root.name}: export_id / directory mismatch")
    if meta.get("intended_role") != expected_role["intended_role"]:
        errors.append(f"{root.name}: intended_role {meta.get('intended_role')} != {expected_role['intended_role']}")
    if meta.get("source_run_stage") != expected_role["source_run_stage"]:
        errors.append(f"{root.name}: source_run_stage mismatch")
    if meta.get("source_set_role") != expected_role["source_set_role"]:
        errors.append(f"{root.name}: source_set_role mismatch")
    if expected_role.get("calibration_role"):
        if meta.get("calibration_role") != expected_role["calibration_role"]:
            errors.append(f"{root.name}: calibration_role mismatch")
        if meta.get("calibration_config_role") != expected_role["calibration_config_role"]:
            errors.append(f"{root.name}: calibration_config_role mismatch")
    if meta.get("must_not_feed_evaluation") is not True:
        errors.append(f"{root.name}: must_not_feed_evaluation must be true")
    source_run_id = str(meta.get("source_run_id") or "")
    if not source_run_id:
        errors.append(f"{root.name}: source_run_id missing")
    if require_source_run_dir is not None:
        run_dir = Path(require_source_run_dir) / source_run_id
        if not (run_dir / "run_meta.json").is_file():
            errors.append(f"{root.name}: source run missing or unreadable: {source_run_id}")

    for name in DATA_FILES:
        file_path = root / name
        if not file_path.is_file():
            errors.append(f"{root.name}: missing {name}")
            continue
        declared = (meta.get("files_sha256") or {}).get(name)
        actual = sha256_file(file_path)
        if declared != actual:
            errors.append(f"{root.name}: SHA256 mismatch {name}")

    if errors:
        raise CanonicalGTBlocked(errors)

    signal_fields, signals = _read_csv(root / DATA_FILES[0])
    predicted_fields, predicted = _read_csv(root / DATA_FILES[1])
    added_fields, added = _read_csv(root / DATA_FILES[2])
    if signal_fields != list(SIGNAL_FIELDS):
        errors.append(f"{root.name}: signal_review.csv schema mismatch")
    if predicted_fields != list(PREDICTED_FIELDS):
        errors.append(f"{root.name}: predicted_boundary_review.csv schema mismatch")
    if added_fields != list(ADDED_FIELDS):
        errors.append(f"{root.name}: human_added_boundary.csv schema mismatch")

    episodes = sorted({str(row["episode_id"]) for row in signals} | {str(row["episode_id"]) for row in predicted} | {str(row["episode_id"]) for row in added})
    if int(meta.get("episode_count", -1)) != len(episodes):
        errors.append(f"{root.name}: episode_count mismatch")
    if any(row.get("export_id") != export_id for row in signals + predicted + added):
        errors.append(f"{root.name}: row export_id mismatch")
    if any(str(row.get("source_run_id") or "") != source_run_id for row in predicted + added):
        errors.append(f"{root.name}: predicted/added source_run_id mismatch")

    expected_signals = len(episodes) * len(SIGNAL_NAMES)
    if len(signals) != expected_signals:
        errors.append(f"{root.name}: P1 completeness failed ({len(signals)} != {expected_signals})")
    p1_counts = Counter(str(row.get("decision") or "") for row in signals)
    if p1_counts.get("PASS", 0) != len(signals) or any(decision != "PASS" for decision in p1_counts):
        errors.append(
            f"{root.name}: P1 gate failed PASS={p1_counts.get('PASS', 0)} "
            f"FAIL={p1_counts.get('FAIL', 0)} UNCERTAIN={p1_counts.get('UNCERTAIN', 0)} "
            f"NOT_REVIEWED={p1_counts.get('NOT_REVIEWED', 0)}"
        )
    if any(str(row.get("human_decision") or "") == "NOT_REVIEWED" for row in predicted):
        errors.append(f"{root.name}: P2 contains NOT_REVIEWED")
    if any(str(row.get("human_decision") or "") not in {"VALID", "REDUNDANT", "MISALIGNED"} for row in predicted):
        errors.append(f"{root.name}: P2 contains unreviewed or unknown human_decision")
    if any(str(row.get("human_decision") or "") == "MISALIGNED" and str(row.get("corrected_frame") or "").strip() == "" for row in predicted):
        errors.append(f"{root.name}: MISALIGNED missing corrected_frame")
    if int(meta.get("signal_review_row_count", -1)) != len(signals):
        errors.append(f"{root.name}: signal_review_row_count mismatch")
    if int(meta.get("predicted_boundary_review_row_count", -1)) != len(predicted):
        errors.append(f"{root.name}: predicted_boundary_review_row_count mismatch")
    if int(meta.get("human_added_boundary_row_count", -1)) != len(added):
        errors.append(f"{root.name}: human_added_boundary_row_count mismatch")
    if errors:
        raise CanonicalGTBlocked(errors)

    decisions = Counter(str(row["human_decision"]) for row in predicted)
    return {
        "path": root,
        "meta": meta,
        "signals": signals,
        "predicted": predicted,
        "added": added,
        "episode_ids": episodes,
        "source_package": expected_role["source_package"],
        "p1_counts": dict(p1_counts),
        "decision_counts": dict(decisions),
        "validation": "PASS",
    }


def _collect_candidates(
    package: Mapping[str, Any],
    *,
    error_modes: Mapping[tuple[str, str, str], str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    meta = package["meta"]
    source_package = package["source_package"]
    candidates: list[dict[str, Any]] = []
    anchors: list[dict[str, Any]] = []
    for row in package["predicted"]:
        decision = str(row["human_decision"])
        shared = {
            "episode_id": str(row["episode_id"]),
            "source_package": source_package,
            "source_export_id": str(meta["export_id"]),
            "source_run_id": str(meta["source_run_id"]),
            "source_boundary_id": str(row["boundary_id"]),
            "source_review_id": str(row.get("effective_review_id") or ""),
            "human_decision": decision,
            "reason_code": str(row.get("reason_code") or ""),
            "comment": str(row.get("comment") or ""),
            "source_run_stage": str(meta["source_run_stage"]),
            "source_set_role": str(meta["source_set_role"]),
            "predicted_row": row,
        }
        if decision == "VALID":
            candidates.append({
                **shared,
                "gt_frame": _parse_int(row["predicted_frame"], field="predicted_frame"),
                "gt_source": GT_SOURCE_VALID,
                "protected_class": classify_protected_class(row, gt_source=GT_SOURCE_VALID),
            })
        elif decision == "MISALIGNED":
            candidates.append({
                **shared,
                "gt_frame": _parse_int(row["corrected_frame"], field="corrected_frame"),
                "gt_source": GT_SOURCE_MISALIGNED,
                "protected_class": classify_protected_class(row, gt_source=GT_SOURCE_MISALIGNED),
            })
        elif decision == "REDUNDANT":
            key = (str(meta["source_run_id"]), str(row["episode_id"]), str(row["boundary_id"]))
            anchors.append({
                "episode_id": str(row["episode_id"]),
                "anchor_frame": _parse_int(row["predicted_frame"], field="predicted_frame"),
                "source_package": source_package,
                "source_export_id": str(meta["export_id"]),
                "source_run_id": str(meta["source_run_id"]),
                "source_boundary_id": str(row["boundary_id"]),
                "source_review_id": str(row.get("effective_review_id") or ""),
                "candidate_type": str(row.get("candidate_type") or ""),
                "representative_candidate_id": str(row.get("representative_candidate_id") or ""),
                "member_candidate_ids": str(row.get("member_candidate_ids") or ""),
                "member_candidate_types": str(row.get("member_candidate_types") or ""),
                "member_candidate_frames": str(row.get("member_candidate_frames") or ""),
                "member_candidate_count": str(row.get("member_candidate_count") or ""),
                "reason_code": str(row.get("reason_code") or ""),
                "comment": str(row.get("comment") or ""),
                "error_mode": error_modes.get(key, "UNASSIGNED"),
            })
        else:
            raise CanonicalGTBlocked([f"unsupported human_decision: {decision}"])

    for row in package["added"]:
        candidates.append({
            "episode_id": str(row["episode_id"]),
            "gt_frame": _parse_int(row["human_added_frame"], field="human_added_frame"),
            "gt_source": GT_SOURCE_ADDED,
            "protected_class": PROTECTED_OTHER,
            "source_package": source_package,
            "source_export_id": str(meta["export_id"]),
            "source_run_id": str(meta["source_run_id"]),
            "source_boundary_id": "",
            "source_review_id": str(row.get("review_id") or ""),
            "human_decision": GT_SOURCE_ADDED,
            "reason_code": str(row.get("reason_code") or ""),
            "comment": str(row.get("comment") or ""),
            "source_run_stage": str(meta["source_run_stage"]),
            "source_set_role": str(meta["source_set_role"]),
            "predicted_row": row,
        })
    return candidates, anchors


def _dedupe_candidates(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        grouped[(row["episode_id"], int(row["gt_frame"]))].append(row)
    kept: list[dict[str, Any]] = []
    deduped: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for key, rows in grouped.items():
        ranked = sorted(
            rows,
            key=lambda item: (
                GT_SOURCE_RANK[item["gt_source"]],
                item["source_export_id"],
                item.get("source_boundary_id") or "",
                item.get("source_review_id") or "",
            ),
        )
        best_rank = GT_SOURCE_RANK[ranked[0]["gt_source"]]
        top = [item for item in ranked if GT_SOURCE_RANK[item["gt_source"]] == best_rank]
        if len(top) > 1:
            conflicts.append({
                "episode_id": key[0],
                "gt_frame": key[1],
                "sources": [
                    {
                        "gt_source": item["gt_source"],
                        "source_package": item["source_package"],
                        "source_export_id": item["source_export_id"],
                        "source_boundary_id": item.get("source_boundary_id") or "",
                    }
                    for item in top
                ],
            })
            continue
        winner = dict(ranked[0])
        winner.pop("predicted_row", None)
        kept.append(winner)
        for loser in ranked[1:]:
            deduped.append({
                "episode_id": key[0],
                "gt_frame": key[1],
                "kept_gt_source": winner["gt_source"],
                "dropped_gt_source": loser["gt_source"],
                "dropped_source_boundary_id": loser.get("source_boundary_id") or "",
                "dropped_source_export_id": loser["source_export_id"],
            })
    if conflicts:
        raise CanonicalGTBlocked([
            "CANONICAL_GT_CONFLICT = YES: " + json.dumps(conflicts, ensure_ascii=False, sort_keys=True)
        ])
    kept.sort(key=lambda item: (item["episode_id"], int(item["gt_frame"]), GT_SOURCE_RANK[item["gt_source"]]))
    return kept, deduped, conflicts


def _assign_gt_ids(rows: list[dict[str, Any]], *, snapshot_id: str) -> list[dict[str, Any]]:
    counters: dict[str, int] = defaultdict(int)
    out = []
    for row in rows:
        counters[row["episode_id"]] += 1
        assigned = {
            "canonical_gt_snapshot_id": snapshot_id,
            "gt_id": f"{row['episode_id']}-HGT{counters[row['episode_id']]:04d}",
            "episode_id": row["episode_id"],
            "gt_frame": int(row["gt_frame"]),
            "gt_source": row["gt_source"],
            "protected_class": row["protected_class"],
            "source_package": row["source_package"],
            "source_export_id": row["source_export_id"],
            "source_run_id": row["source_run_id"],
            "source_boundary_id": row.get("source_boundary_id") or "",
            "source_review_id": row.get("source_review_id") or "",
            "human_decision": row["human_decision"],
            "reason_code": row.get("reason_code") or "",
            "comment": row.get("comment") or "",
            "source_run_stage": row["source_run_stage"],
            "source_set_role": row["source_set_role"],
        }
        out.append(assigned)
    return out


def _spacing_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_episode: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        by_episode[row["episode_id"]].append(int(row["gt_frame"]))
    min_spacing: int | None = None
    warn = False
    for frames in by_episode.values():
        ordered = sorted(frames)
        for left, right in zip(ordered, ordered[1:]):
            gap = right - left
            min_spacing = gap if min_spacing is None else min(min_spacing, gap)
            if gap <= 2 * TOLERANCE_FRAMES:
                warn = True
    return {
        "gt_spacing_warn": warn,
        "min_gt_spacing_frames": min_spacing,
    }


def _fingerprint_optional(path: Path | None) -> str | None:
    if path is None or not Path(path).exists():
        return None
    target = Path(path)
    if target.is_dir():
        return tree_fingerprint(target)["tree_fingerprint"]
    return sha256_file(target)


def validate_snapshot_dir(path: str | Path, *, seed: Mapping[str, Any], fresh: Mapping[str, Any]) -> dict[str, Any]:
    root = Path(path)
    errors: list[str] = []
    for name in SNAPSHOT_FILES:
        if not (root / name).is_file():
            errors.append(f"missing {name}")
    if errors:
        raise CanonicalGTBlocked(errors)
    meta = json.loads((root / "canonical_gt_meta.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "combined_calibration_manifest.json").read_text(encoding="utf-8"))
    gt_fields, gt_rows = _read_csv(root / "canonical_human_boundary_gt.csv")
    fp_fields, fp_rows = _read_csv(root / "known_false_positive_anchor.csv")
    if gt_fields != list(CANONICAL_GT_FIELDS):
        errors.append("canonical_human_boundary_gt.csv schema mismatch")
    if fp_fields != list(KNOWN_FP_FIELDS):
        errors.append("known_false_positive_anchor.csv schema mismatch")
    snapshot_id = str(meta.get("canonical_gt_snapshot_id") or "")
    if snapshot_id != root.name and not root.name.startswith(f".tmp-{snapshot_id}"):
        errors.append("snapshot_id / directory mismatch")
    if meta.get("canonical_gt_contract_version") != CANONICAL_GT_CONTRACT_VERSION:
        errors.append("canonical_gt_contract_version mismatch")
    if meta.get("calibration_protocol_effective_version") != CALIBRATION_PROTOCOL_EFFECTIVE_VERSION:
        errors.append("protocol version mismatch")
    if meta.get("matching_executed") is not False or meta.get("tolerance_applied") is not False:
        errors.append("matching/tolerance must not have been executed")
    if manifest.get("evaluation_eligible") is not False or manifest.get("must_not_feed_evaluation") is not True:
        errors.append("evaluation leakage guard failed")
    seed_ids = list(seed["episode_ids"])
    fresh_ids = list(fresh["episode_ids"])
    combined = seed_ids + fresh_ids
    if set(seed_ids) & set(fresh_ids):
        errors.append("seed/fresh overlap")
    if len(set(combined)) != len(seed_ids) + len(fresh_ids):
        errors.append("duplicate episode_id")
    if int(meta.get("episode_count", -1)) != len(set(combined)):
        errors.append("episode_count mismatch")
    if int(meta.get("seed_episode_count", -1)) != len(seed_ids):
        errors.append("seed_episode_count mismatch")
    if int(meta.get("fresh_episode_count", -1)) != len(fresh_ids):
        errors.append("fresh_episode_count mismatch")
    if sorted(manifest.get("episode_ids") or []) != sorted(set(combined)):
        errors.append("manifest episode_ids mismatch")
    gt_pairs = [(row["episode_id"], int(row["gt_frame"])) for row in gt_rows]
    if len(gt_pairs) != len(set(gt_pairs)):
        errors.append("duplicate Canonical GT (episode_id, gt_frame)")
    if any(row["canonical_gt_snapshot_id"] != snapshot_id for row in gt_rows + fp_rows):
        errors.append("row snapshot_id mismatch")
    if any(row["gt_id"] == row.get("source_boundary_id") and row.get("source_boundary_id") for row in gt_rows):
        errors.append("gt_id must not reuse source_boundary_id")
    declared = meta.get("files_sha256") or {}
    for name in ("canonical_human_boundary_gt.csv", "known_false_positive_anchor.csv"):
        if declared.get(name) != sha256_file(root / name):
            errors.append(f"SHA256 mismatch {name}")
    if int(meta.get("canonical_gt_count", -1)) != len(gt_rows):
        errors.append("canonical_gt_count mismatch")
    if int(meta.get("known_fp_anchor_count", -1)) != len(fp_rows):
        errors.append("known_fp_anchor_count mismatch")
    if errors:
        raise CanonicalGTBlocked(errors)
    return {"status": "PASS", "canonical_gt_count": len(gt_rows), "known_fp_anchor_count": len(fp_rows)}


def build_combined_canonical_gt(
    *,
    seed_export_path: str | Path,
    fresh_export_path: str | Path,
    snapshot_root: str | Path,
    error_mode_map_path: str | Path | None = None,
    expected_seed_episode_ids: Iterable[str] | None = None,
    expected_fresh_episode_ids: Iterable[str] | None = None,
    required_seed_count: int = 6,
    required_fresh_count: int = 6,
    source_run_root: str | Path | None = None,
    owner_sqlite_path: str | Path | None = None,
    dataset_paths: Iterable[str | Path] | None = None,
) -> dict[str, Any]:
    seed_path = Path(seed_export_path)
    fresh_path = Path(fresh_export_path)
    out_root = Path(snapshot_root)
    run_root = Path(source_run_root) if source_run_root is not None else None

    before = {
        "seed_export": tree_fingerprint(seed_path)["tree_fingerprint"],
        "fresh_export": tree_fingerprint(fresh_path)["tree_fingerprint"],
        "owner_sqlite": _fingerprint_optional(Path(owner_sqlite_path) if owner_sqlite_path else None),
        "dataset": {
            str(path): _fingerprint_optional(Path(path))
            for path in (dataset_paths or [])
        },
    }
    if run_root is not None:
        before["source_runs"] = {}

    seed = validate_export_disk(seed_path, expected_role=SEED_ROLE, require_source_run_dir=run_root)
    fresh = validate_export_disk(fresh_path, expected_role=FRESH_ROLE, require_source_run_dir=run_root)
    if run_root is not None:
        before["source_runs"][seed["meta"]["source_run_id"]] = tree_fingerprint(run_root / seed["meta"]["source_run_id"])["tree_fingerprint"]
        before["source_runs"][fresh["meta"]["source_run_id"]] = tree_fingerprint(run_root / fresh["meta"]["source_run_id"])["tree_fingerprint"]

    seed_ids = list(seed["episode_ids"])
    fresh_ids = list(fresh["episode_ids"])
    overlap = sorted(set(seed_ids) & set(fresh_ids))
    combined = seed_ids + fresh_ids
    expected_total = required_seed_count + required_fresh_count
    errors: list[str] = []
    if len(seed_ids) != required_seed_count:
        errors.append(f"SEED_EPISODES = {len(seed_ids)} (expected {required_seed_count})")
    if len(fresh_ids) != required_fresh_count:
        errors.append(f"FRESH_EPISODES = {len(fresh_ids)} (expected {required_fresh_count})")
    if len(set(combined)) != expected_total:
        errors.append(f"TOTAL_UNIQUE_EPISODES = {len(set(combined))} (expected {expected_total})")
    if overlap:
        errors.append(f"EPISODE_OVERLAP = {overlap}")
    if expected_seed_episode_ids is not None and set(seed_ids) != set(expected_seed_episode_ids):
        errors.append("seed episode exact-set mismatch vs frozen expected ids")
    if expected_fresh_episode_ids is not None and set(fresh_ids) != set(expected_fresh_episode_ids):
        errors.append("fresh episode exact-set mismatch vs frozen expected ids")
    if errors:
        raise CanonicalGTBlocked(errors)

    error_modes = load_error_mode_map(error_mode_map_path)
    seed_gt, seed_fp = _collect_candidates(seed, error_modes=error_modes)
    fresh_gt, fresh_fp = _collect_candidates(fresh, error_modes=error_modes)
    kept, deduped, _conflicts = _dedupe_candidates(seed_gt + fresh_gt)
    anchors = sorted(seed_fp + fresh_fp, key=lambda row: (row["episode_id"], int(row["anchor_frame"]), row["source_boundary_id"]))

    created_at = _now()
    stamp = datetime.fromisoformat(created_at).strftime("%Y%m%d_%H%M%S")
    salt = uuid.uuid4().hex
    identity = hashlib.sha256(
        f"{seed['meta']['export_id']}|{fresh['meta']['export_id']}|{created_at}|{salt}".encode("utf-8")
    ).hexdigest()[:8]
    snapshot_id = f"g1_canonical_gt_{stamp}_{identity}"
    gt_rows = _assign_gt_ids(kept, snapshot_id=snapshot_id)
    fp_rows = [{"canonical_gt_snapshot_id": snapshot_id, **row} for row in anchors]
    spacing = _spacing_diagnostics(gt_rows)
    source_counts = Counter(row["gt_source"] for row in gt_rows)
    p1_all = seed["signals"] + fresh["signals"]
    p1_counts = Counter(str(row["decision"]) for row in p1_all)

    meta = {
        "canonical_gt_contract_version": CANONICAL_GT_CONTRACT_VERSION,
        "canonical_gt_snapshot_id": snapshot_id,
        "created_at": created_at,
        "calibration_protocol_effective_version": CALIBRATION_PROTOCOL_EFFECTIVE_VERSION,
        "source_export_ids": [seed["meta"]["export_id"], fresh["meta"]["export_id"]],
        "source_export_count": 2,
        "episode_count": len(set(combined)),
        "seed_episode_count": len(seed_ids),
        "fresh_episode_count": len(fresh_ids),
        "canonical_gt_count": len(gt_rows),
        "known_fp_anchor_count": len(fp_rows),
        "human_added_gt_count": source_counts.get(GT_SOURCE_ADDED, 0),
        "misaligned_gt_count": source_counts.get(GT_SOURCE_MISALIGNED, 0),
        "valid_inherit_gt_count": source_counts.get(GT_SOURCE_VALID, 0),
        "deduped_count": len(deduped),
        "conflict_count": 0,
        "dedupe_events": deduped,
        "matching_rule_id": MATCHING_RULE_ID,
        "tolerance_frames": TOLERANCE_FRAMES,
        "matching_executed": False,
        "tolerance_applied": False,
        "baseline_scoring_executed": False,
        "stage_a0_executed": False,
        "parameter_search_executed": False,
        "combined_canonical_gt": "FROZEN",
        "search_gate": "OPEN_FOR_BASELINE_SCORING",
        "must_not_feed_evaluation": True,
        "p1_pass_count": p1_counts.get("PASS", 0),
        "p1_fail_count": p1_counts.get("FAIL", 0),
        "p1_uncertain_count": p1_counts.get("UNCERTAIN", 0),
        "p1_not_reviewed_count": p1_counts.get("NOT_REVIEWED", 0),
        "predicted_reviewed_count": len(seed["predicted"]) + len(fresh["predicted"]),
        "valid_count": Counter(row["human_decision"] for row in seed["predicted"] + fresh["predicted"]).get("VALID", 0),
        "redundant_count": len(fp_rows),
        "human_added_input_count": len(seed["added"]) + len(fresh["added"]),
        **spacing,
        "files_sha256": {},
    }
    manifest = {
        "canonical_gt_snapshot_id": snapshot_id,
        "canonical_gt_contract_version": CANONICAL_GT_CONTRACT_VERSION,
        "calibration_protocol_effective_version": CALIBRATION_PROTOCOL_EFFECTIVE_VERSION,
        "episode_ids": sorted(set(combined)),
        "seed_episode_ids": sorted(seed_ids),
        "fresh_episode_ids": sorted(fresh_ids),
        "source_export_ids": [seed["meta"]["export_id"], fresh["meta"]["export_id"]],
        "source_run_ids": [seed["meta"]["source_run_id"], fresh["meta"]["source_run_id"]],
        "source_dataset_id": SOURCE_DATASET_ID,
        "config_baseline_hash": CONFIG_BASELINE_HASH,
        "signal_contract_hash": SIGNAL_CONTRACT_HASH,
        "evaluation_eligible": False,
        "must_not_feed_evaluation": True,
        "search_gate": "OPEN_FOR_BASELINE_SCORING",
        "matching_executed": False,
        "parameter_search_allowed": False,
    }

    out_root.mkdir(parents=True, exist_ok=True)
    final_path = out_root / snapshot_id
    temp_path = out_root / f".tmp-{snapshot_id}-{uuid.uuid4().hex}"
    if final_path.exists():
        raise CanonicalGTBlocked([f"immutable snapshot already exists: {final_path}"])
    temp_path.mkdir()
    try:
        _write_csv(temp_path / "canonical_human_boundary_gt.csv", CANONICAL_GT_FIELDS, gt_rows)
        _write_csv(temp_path / "known_false_positive_anchor.csv", KNOWN_FP_FIELDS, fp_rows)
        meta["files_sha256"] = {
            "canonical_human_boundary_gt.csv": sha256_file(temp_path / "canonical_human_boundary_gt.csv"),
            "known_false_positive_anchor.csv": sha256_file(temp_path / "known_false_positive_anchor.csv"),
        }
        (temp_path / "canonical_gt_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (temp_path / "combined_calibration_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        validate_snapshot_dir(temp_path, seed=seed, fresh=fresh)
        os.rename(temp_path, final_path)
    except Exception:
        if temp_path.exists():
            shutil.rmtree(temp_path)
        raise

    after = {
        "seed_export": tree_fingerprint(seed_path)["tree_fingerprint"],
        "fresh_export": tree_fingerprint(fresh_path)["tree_fingerprint"],
        "owner_sqlite": _fingerprint_optional(Path(owner_sqlite_path) if owner_sqlite_path else None),
        "dataset": {
            str(path): _fingerprint_optional(Path(path))
            for path in (dataset_paths or [])
        },
    }
    if run_root is not None:
        after["source_runs"] = {
            seed["meta"]["source_run_id"]: tree_fingerprint(run_root / seed["meta"]["source_run_id"])["tree_fingerprint"],
            fresh["meta"]["source_run_id"]: tree_fingerprint(run_root / fresh["meta"]["source_run_id"])["tree_fingerprint"],
        }
    if before != after:
        raise CanonicalGTBlocked(["source immutability check failed after snapshot build"])

    return {
        "snapshot_id": snapshot_id,
        "snapshot_path": str(final_path),
        "meta": meta,
        "manifest": manifest,
        "seed_validation": "PASS",
        "fresh_validation": "PASS",
        "immutability": {
            "seed_export_unchanged": True,
            "fresh_export_unchanged": True,
            "owner_sqlite_unchanged": True,
            "source_runs_unchanged": True,
            "dataset_unchanged": True,
            "fingerprints": after,
        },
    }
