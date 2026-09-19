"""12-Episode Baseline Scoring. Matching is type-unaware; Detector/GT are read-only."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from project2_g1_audit_web.contract import validate_g1_audit_folder
from project2_g1_audit_web.hashes import now_iso, sha256_file, tree_fingerprint

from .baseline_calibration_run import EXPECTED_CONFIG_HASH, EXPECTED_SIGNAL_HASH, identity_errors
from .boundary_matching import (
    MATCHING_RULE_ID,
    SAMPLE_HZ,
    TOLERANCE_FRAMES,
    TOLERANCE_SECONDS,
    match_by_episode,
)
from .canonical_gt import (
    CANONICAL_GT_CONTRACT_VERSION,
    CANONICAL_GT_FIELDS,
    KNOWN_FP_FIELDS,
    PACKAGE_FRESH,
    PACKAGE_SEED,
    PROTECTED_DIRECTION,
    PROTECTED_GRIPPER,
    PROTECTED_MERGED,
    TOLERANCE_FRAMES as GT_TOLERANCE_FRAMES,
)
from .paths import (
    DATASET_RAW_HDF5,
    PROJECT2_ROOT,
    PROJECT2_ENGINEERING_MASTER,
)

METRIC_VERSION = "P2_G1_CALIBRATION_SCORING_V1"
CALIBRATION_PROTOCOL_EFFECTIVE_VERSION = "FROZEN_v1.1"
CONFIG_SELECTION_RULE = "LEXICOGRAPHIC_CONSTRAINED"
EXPECTED_RUN_ID = "g1_calibration_20260918_141032_781e5d8b"
EXPECTED_SNAPSHOT_ID = "g1_canonical_gt_20260918_131636_c9916b89"
EXPECTED_EXPORT_IDS = (
    "g1_cal_seed_export_20260917_214637_2f8d8802",
    "g1_cal_export_20260918_120335_81c068bf",
)
SQLITE_SHA256 = "076b3fe1504b23334cc861b32fb3145efaa92f187aa4002be1afcee7bc96c718"

SCORE_FILES = (
    "score_meta.json",
    "matching_pairs.csv",
    "unmatched_predictions_fp.csv",
    "unmatched_gt_fn.csv",
    "episode_metrics.csv",
    "guardrail_metrics.json",
    "known_fp_anchor_status.csv",
    "baseline_metrics.json",
)

MATCHING_PAIR_FIELDS = (
    "episode_id", "gt_id", "gt_frame", "pred_boundary_id", "pred_frame",
    "delta_frame", "abs_error_frames", "abs_error_seconds", "gt_source",
    "protected_class", "source_package", "pred_candidate_type",
    "pred_representative_candidate_id", "match_class",
)
FP_FIELDS = (
    "episode_id", "pred_boundary_id", "pred_frame", "candidate_type",
    "representative_candidate_id", "member_candidate_types", "member_candidate_frames",
    "known_fp_anchor_matched", "known_fp_anchor_frame", "known_fp_error_mode",
    "reason_code", "is_new_unanchored_fp",
)
FN_FIELDS = (
    "episode_id", "gt_id", "gt_frame", "gt_source", "protected_class", "source_package",
)
EPISODE_METRIC_FIELDS = (
    "episode_id", "n_gt", "n_pred", "TP", "FP", "FN", "Precision", "Recall", "F1",
    "over_segmentation", "under_segmentation", "mean_localization_error_frames",
)
ANCHOR_STATUS_FIELDS = (
    "episode_id", "anchor_frame", "error_mode", "source_package", "source_boundary_id",
    "status", "matched_pred_boundary_id", "matched_pred_frame", "abs_error_frames",
)


class ScoringError(ValueError):
    pass


class MetricZeroDenominatorError(ScoringError):
    pass


class ScoringSanityError(ScoringError):
    pass


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ScoringError(f"{path.name}: missing header")
        return list(reader.fieldnames), list(reader)


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _csv_bool(value: bool) -> str:
    return "true" if value else "false"


def nearest_rank(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(float(item) for item in values)
    if not ordered:
        raise ScoringError("nearest-rank on empty values")
    index = max(0, min(len(ordered) - 1, int(math.ceil(quantile * len(ordered))) - 1))
    return ordered[index]


def ratio(numerator: int, denominator: int, *, name: str) -> float:
    if denominator == 0:
        raise MetricZeroDenominatorError(
            f"REPORT_METRIC_ZERO_DENOMINATOR_CONTRACT_GAP name={name} numerator={numerator}"
        )
    return numerator / denominator


def f1_score(precision: float, recall: float) -> float:
    if precision + recall == 0:
        raise MetricZeroDenominatorError(
            "REPORT_METRIC_ZERO_DENOMINATOR_CONTRACT_GAP name=f1 precision+recall=0"
        )
    return 2.0 * precision * recall / (precision + recall)


def localization_summary(abs_errors: list[int]) -> dict[str, Any]:
    if not abs_errors:
        return {
            "count": 0,
            "mean_frames": None,
            "median_frames": None,
            "p90_frames": None,
            "max_frames": None,
            "mean_seconds": None,
            "median_seconds": None,
            "p90_seconds": None,
            "max_seconds": None,
        }
    mean = sum(abs_errors) / len(abs_errors)
    median = nearest_rank(abs_errors, 0.5)
    p90 = nearest_rank(abs_errors, 0.9)
    maximum = max(abs_errors)
    return {
        "count": len(abs_errors),
        "mean_frames": mean,
        "median_frames": median,
        "p90_frames": p90,
        "max_frames": maximum,
        "mean_seconds": mean / SAMPLE_HZ,
        "median_seconds": median / SAMPLE_HZ,
        "p90_seconds": p90 / SAMPLE_HZ,
        "max_seconds": maximum / SAMPLE_HZ,
    }


def native_key(episode_id: str) -> str:
    return episode_id.split("/", 1)[-1]


def load_canonical_snapshot(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    meta = json.loads((root / "canonical_gt_meta.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "combined_calibration_manifest.json").read_text(encoding="utf-8"))
    gt_fields, gt_rows = _read_csv(root / "canonical_human_boundary_gt.csv")
    fp_fields, fp_rows = _read_csv(root / "known_false_positive_anchor.csv")
    errors: list[str] = []
    if str(meta.get("canonical_gt_snapshot_id") or "") != EXPECTED_SNAPSHOT_ID:
        errors.append("canonical_gt_snapshot_id mismatch")
    if str(meta.get("canonical_gt_contract_version") or "") != CANONICAL_GT_CONTRACT_VERSION:
        errors.append("canonical_gt_contract_version mismatch")
    if int(meta.get("episode_count") or -1) != 12:
        errors.append("episode_count != 12")
    if int(meta.get("canonical_gt_count") or -1) != 56 or len(gt_rows) != 56:
        errors.append(f"canonical_gt_count={meta.get('canonical_gt_count')} rows={len(gt_rows)}")
    if int(meta.get("known_fp_anchor_count") or -1) != 10 or len(fp_rows) != 10:
        errors.append(f"known_fp_anchor_count={meta.get('known_fp_anchor_count')} rows={len(fp_rows)}")
    try:
        conflict_count = int(meta["conflict_count"])
    except (KeyError, TypeError, ValueError):
        errors.append("conflicts missing")
    else:
        if conflict_count != 0:
            errors.append("conflicts != 0")
    if gt_fields != list(CANONICAL_GT_FIELDS):
        errors.append("GT schema mismatch")
    if fp_fields != list(KNOWN_FP_FIELDS):
        errors.append("known-FP schema mismatch")
    declared = meta.get("files_sha256") or {}
    if declared.get("canonical_human_boundary_gt.csv") != sha256_file(root / "canonical_human_boundary_gt.csv"):
        errors.append("GT SHA256 mismatch")
    if declared.get("known_false_positive_anchor.csv") != sha256_file(root / "known_false_positive_anchor.csv"):
        errors.append("known-FP SHA256 mismatch")
    if GT_TOLERANCE_FRAMES != TOLERANCE_FRAMES:
        errors.append("snapshot T contract mismatch")
    if errors:
        raise ScoringError("; ".join(errors))
    return {
        "root": root,
        "meta": meta,
        "manifest": manifest,
        "gt_rows": gt_rows,
        "fp_rows": fp_rows,
    }


def load_baseline_run(path: str | Path, *, expected_episodes: set[str]) -> dict[str, Any]:
    root = Path(path)
    loaded = validate_g1_audit_folder(root)
    meta = loaded["run_meta"]
    identity = identity_errors(
        meta,
        [row["episode_id"] for row in loaded["episodes"]],
        [row.get("set_role") or "" for row in loaded["episodes"]],
        expected_episodes=expected_episodes,
        expected_config_hash=EXPECTED_CONFIG_HASH,
        expected_signal_hash=EXPECTED_SIGNAL_HASH,
    )
    if identity:
        raise ScoringError("baseline run identity failed: " + "; ".join(identity))
    if str(meta.get("run_id") or "") != EXPECTED_RUN_ID:
        raise ScoringError(f"run_id mismatch: {meta.get('run_id')}")
    if loaded.get("final_member_semantics") not in {"MATERIALIZED", "MATERIALIZED_V1"} and str(meta.get("final_boundary_semantics") or "") != "MATERIALIZED_V1":
        raise ScoringError("Final semantics is not MATERIALIZED_V1")
    predictions: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, str]] = {}
    for episode in loaded["episodes"]:
        episode_id = str(episode["episode_id"])
        boundaries_rel = str(episode["boundaries_relpath"])
        segments_rel = str(episode["segments_relpath"])
        _fields, finals = _read_csv(root / boundaries_rel)
        _seg_fields, segs = _read_csv(root / segments_rel)
        for row in finals:
            pred = {
                "episode_id": episode_id,
                "pred_id": str(row["boundary_id"]),
                "pred_boundary_id": str(row["boundary_id"]),
                "pred_frame": int(row["frame"]),
                "candidate_type": str(row.get("candidate_type") or ""),
                "representative_candidate_id": str(row.get("representative_candidate_id") or ""),
                "member_candidate_types": str(row.get("member_candidate_types") or ""),
                "member_candidate_frames": str(row.get("member_candidate_frames") or ""),
            }
            predictions.append(pred)
            by_id[pred["pred_id"]] = pred
        for row in segs:
            segments.append({"episode_id": episode_id, **row})
    return {
        "root": root,
        "loaded": loaded,
        "meta": meta,
        "predictions": predictions,
        "prediction_by_id": by_id,
        "segments": segments,
        "validator": "PASS",
    }


def gt_spacing_diagnostics(gt_rows: list[Mapping[str, str]]) -> dict[str, Any]:
    by_episode: dict[str, list[int]] = defaultdict(list)
    for row in gt_rows:
        by_episode[str(row["episode_id"])].append(int(row["gt_frame"]))
    min_spacing: int | None = None
    warn = False
    for frames in by_episode.values():
        ordered = sorted(frames)
        for left, right in zip(ordered, ordered[1:]):
            gap = right - left
            min_spacing = gap if min_spacing is None else min(min_spacing, gap)
            if gap <= 2 * TOLERANCE_FRAMES:
                warn = True
    return {"gt_spacing_warn": warn, "min_gt_spacing_frames": min_spacing}


def _guardrail_recall(gt_rows: list[Mapping[str, str]], matched: set[str], predicate) -> dict[str, Any]:
    selected = [row for row in gt_rows if predicate(row)]
    recalled = [row for row in selected if str(row["gt_id"]) in matched]
    return {
        "n_gt": len(selected),
        "n_recalled": len(recalled),
        "recall": ratio(len(recalled), len(selected), name="guardrail_recall") if selected else _empty_guardrail(),
        "gt_ids": [str(row["gt_id"]) for row in selected],
        "missed_gt_ids": [str(row["gt_id"]) for row in selected if str(row["gt_id"]) not in matched],
    }


def _empty_guardrail() -> float:
    raise MetricZeroDenominatorError(
        "REPORT_METRIC_ZERO_DENOMINATOR_CONTRACT_GAP name=guardrail_recall n_gt=0"
    )


def match_known_fp_anchors(
    unmatched_preds: list[dict[str, Any]],
    anchors: list[Mapping[str, str]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """One-to-one FP↔anchor matching with the frozen rule. UNASSIGNED is in scope."""
    pred_by_id = {str(item["pred_id"]): item for item in unmatched_preds}
    anchor_points = []
    for index, row in enumerate(anchors):
        anchor_points.append({
            "episode_id": str(row["episode_id"]),
            "gt_id": f"anchor:{row['episode_id']}:{row['anchor_frame']}:{index}",
            "gt_frame": int(row["anchor_frame"]),
            "row": row,
        })
    pred_points = [
        {
            "episode_id": str(item["episode_id"]),
            "pred_id": str(item["pred_id"]),
            "pred_frame": int(item["pred_frame"]),
        }
        for item in unmatched_preds
    ]
    matched_by_episode = match_by_episode(anchor_points, pred_points)
    anchor_status: dict[str, dict[str, Any]] = {}
    pred_status: dict[str, dict[str, Any]] = {}
    matched_anchor_ids: set[str] = set()
    matched_pred_ids: set[str] = set()
    for episode_id, result in matched_by_episode.items():
        for pair in result.pairs:
            matched_anchor_ids.add(pair.gt_id)
            matched_pred_ids.add(pair.pred_id)
            anchor_row = next(item["row"] for item in anchor_points if item["gt_id"] == pair.gt_id)
            payload = {
                "status": "REMAINING",
                "matched_pred_boundary_id": pair.pred_id,
                "matched_pred_frame": pair.pred_frame,
                "abs_error_frames": pair.abs_error_frames,
                "error_mode": str(anchor_row["error_mode"]),
                "anchor_frame": int(anchor_row["anchor_frame"]),
                "reason_code": str(anchor_row.get("reason_code") or ""),
                "episode_id": episode_id,
                "source_package": str(anchor_row.get("source_package") or ""),
                "source_boundary_id": str(anchor_row.get("source_boundary_id") or ""),
            }
            anchor_status[pair.gt_id] = payload
            pred_status[pair.pred_id] = {
                "known_fp_anchor_matched": True,
                "known_fp_anchor_frame": int(anchor_row["anchor_frame"]),
                "known_fp_error_mode": str(anchor_row["error_mode"]),
                "reason_code": str(anchor_row.get("reason_code") or ""),
                "is_new_unanchored_fp": False,
            }
    for item in anchor_points:
        if item["gt_id"] in matched_anchor_ids:
            continue
        row = item["row"]
        anchor_status[item["gt_id"]] = {
            "status": "FIXED",
            "matched_pred_boundary_id": "",
            "matched_pred_frame": "",
            "abs_error_frames": "",
            "error_mode": str(row["error_mode"]),
            "anchor_frame": int(row["anchor_frame"]),
            "reason_code": str(row.get("reason_code") or ""),
            "episode_id": str(row["episode_id"]),
            "source_package": str(row.get("source_package") or ""),
            "source_boundary_id": str(row.get("source_boundary_id") or ""),
        }
    for pred_id in pred_by_id:
        if pred_id in pred_status:
            continue
        pred_status[pred_id] = {
            "known_fp_anchor_matched": False,
            "known_fp_anchor_frame": "",
            "known_fp_error_mode": "",
            "reason_code": "NEW_UNANCHORED_FP",
            "is_new_unanchored_fp": True,
        }
    return anchor_status, pred_status


def fragmentation_diagnostics(segments: list[Mapping[str, Any]]) -> dict[str, Any]:
    durations = [int(item["duration_frames"]) for item in segments]
    n_seg = len(durations)
    n_12 = sum(1 for item in durations if item in (1, 2))
    by_episode: dict[str, int] = defaultdict(int)
    for item in segments:
        by_episode[str(item["episode_id"])] += 1
    return {
        "1_2_frame_segment_ratio": (n_12 / n_seg) if n_seg else None,
        "1_2_frame_segment_count": n_12,
        "segment_count": n_seg,
        "segments_per_episode": (sum(by_episode.values()) / len(by_episode)) if by_episode else None,
        "short_segment_ratio": None,
        "short_segment_ratio_status": "NOT_COMPUTED_CONTRACT_GAP",
        "FRAGMENTATION_SHORT_RATIO_CONTRACT_GAP": True,
        "note": "short_segment_ratio threshold is not frozen; min_segment_length remains EXPLORATORY",
    }


def _source_fingerprints(root: Path) -> dict[str, Any]:
    protocol_v1 = root / "0-doc/10-design-review/Project2_G1_P3_Calibration_Protocol_FROZEN_v1_20260917.md"
    protocol_v11 = root / "0-doc/10-design-review/Project2_G1_P3_Calibration_Protocol_FROZEN_v1_1_PATCH_20260918.md"
    sqlite = root / "outputs/g1_audit_web/g1_audit_web_owner.sqlite3"
    seed_export = root / "outputs/g1_audit_web/human_calibration_export" / EXPECTED_EXPORT_IDS[0]
    fresh_export = root / "outputs/g1_audit_web/human_calibration_export" / EXPECTED_EXPORT_IDS[1]
    snapshot = root / "outputs/g1_p3_canonical_gt" / EXPECTED_SNAPSHOT_ID
    run = root / "outputs/g1_audit_runs" / EXPECTED_RUN_ID
    return {
        "baseline_run": tree_fingerprint(run)["tree_fingerprint"],
        "canonical_gt": tree_fingerprint(snapshot)["tree_fingerprint"],
        "seed_export": tree_fingerprint(seed_export)["tree_fingerprint"],
        "fresh_export": tree_fingerprint(fresh_export)["tree_fingerprint"],
        "owner_sqlite": sha256_file(sqlite),
        "protocol_v1": sha256_file(protocol_v1),
        "protocol_v11": sha256_file(protocol_v11),
        "dataset": sha256_file(DATASET_RAW_HDF5) if DATASET_RAW_HDF5.is_file() else None,
        "engineering_master": sha256_file(PROJECT2_ENGINEERING_MASTER) if PROJECT2_ENGINEERING_MASTER.is_file() else None,
    }


def sanity_discrepancies(metrics: Mapping[str, Any], episode_rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    expected = {
        "TP": 56,
        "FP": 10,
        "FN": 0,
        "EXACT_TP": 56,
        "NEAR_TP": 0,
        "episode_oversegmented_count": 4,
        "total_oversegmentation": 10,
        "NEW_UNANCHORED_FP_COUNT": 0,
        "MODE_01_REMAINING": 3,
        "MODE_02_REMAINING": 3,
        "MODE_03_REMAINING": 1,
        "UNASSIGNED_KNOWN_FP_REMAINING": 3,
        "KNOWN_FP_REMAINING_TOTAL": 10,
        "KNOWN_FP_FIXED_TOTAL": 0,
    }
    out: list[dict[str, Any]] = []
    for key, value in expected.items():
        actual = metrics.get(key)
        if actual != value:
            out.append({"field": key, "expected": value, "actual": actual, "reason": "SANITY_MISMATCH"})
    expected_over = {
        "data/demo_278": 3,
        "data/demo_242": 4,
        "data/demo_162": 1,
        "data/demo_255": 2,
    }
    by_episode = {row["episode_id"]: int(row["over_segmentation"]) for row in episode_rows}
    for episode_id, expected_value in expected_over.items():
        actual = by_episode.get(episode_id)
        if actual != expected_value:
            out.append({
                "field": "over_segmentation",
                "episode": episode_id,
                "expected": expected_value,
                "actual": actual,
                "reason": "SANITY_OVERSEGMENTATION_MISMATCH",
            })
    for episode_id, actual in by_episode.items():
        if episode_id not in expected_over and actual != 0:
            out.append({
                "field": "over_segmentation",
                "episode": episode_id,
                "expected": 0,
                "actual": actual,
                "reason": "UNEXPECTED_OVERSEGMENTED_EPISODE",
            })
    return out


def validate_score_dir(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    errors: list[str] = []
    for name in SCORE_FILES:
        if not (root / name).is_file():
            errors.append(f"missing {name}")
    if errors:
        raise ScoringError("; ".join(errors))
    meta = json.loads((root / "score_meta.json").read_text(encoding="utf-8"))
    pair_fields, pairs = _read_csv(root / "matching_pairs.csv")
    fp_fields, fps = _read_csv(root / "unmatched_predictions_fp.csv")
    fn_fields, fns = _read_csv(root / "unmatched_gt_fn.csv")
    if pair_fields != list(MATCHING_PAIR_FIELDS):
        errors.append("matching_pairs.csv schema mismatch")
    if fp_fields != list(FP_FIELDS):
        errors.append("unmatched_predictions_fp.csv schema mismatch")
    if fn_fields != list(FN_FIELDS):
        errors.append("unmatched_gt_fn.csv schema mismatch")
    metrics = json.loads((root / "baseline_metrics.json").read_text(encoding="utf-8"))
    if int(metrics["TP"]) != len(pairs):
        errors.append("TP != matching_pairs rows")
    if int(metrics["FP"]) != len(fps):
        errors.append("FP != unmatched prediction rows")
    if int(metrics["FN"]) != len(fns):
        errors.append("FN != unmatched GT rows")
    if meta.get("matching_rule_id") != MATCHING_RULE_ID:
        errors.append("matching_rule_id mismatch")
    if int(meta.get("tolerance_frames") or -1) != TOLERANCE_FRAMES:
        errors.append("tolerance_frames mismatch")
    if meta.get("parameter_search_executed") is not False:
        errors.append("parameter_search_executed must be false")
    if errors:
        raise ScoringError("; ".join(errors))
    return {"status": "PASS", "score_id": meta["score_id"], "meta": meta, "metrics": metrics}


def score_baseline(
    *,
    project_root: str | Path | None = None,
    run_root: str | Path | None = None,
    snapshot_root: str | Path | None = None,
    scoring_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(project_root or PROJECT2_ROOT).resolve()
    snapshot = load_canonical_snapshot(snapshot_root or root / "outputs/g1_p3_canonical_gt" / EXPECTED_SNAPSHOT_ID)
    expected_episodes = {str(item) for item in snapshot["manifest"]["episode_ids"]}
    if len(expected_episodes) != 12:
        raise ScoringError("Combined manifest episode_count != 12")
    run = load_baseline_run(run_root or root / "outputs/g1_audit_runs" / EXPECTED_RUN_ID, expected_episodes=expected_episodes)
    before = _source_fingerprints(root)

    gt_rows = snapshot["gt_rows"]
    gt_by_id = {str(row["gt_id"]): row for row in gt_rows}
    pred_points = run["predictions"]
    gt_points = [
        {
            "episode_id": str(row["episode_id"]),
            "gt_id": str(row["gt_id"]),
            "gt_frame": int(row["gt_frame"]),
        }
        for row in gt_rows
    ]
    matching = match_by_episode(gt_points, pred_points)
    matched_gt_ids: set[str] = set()
    matched_pred_ids: set[str] = set()
    pairs: list[dict[str, Any]] = []
    exact = 0
    near = 0
    abs_errors: list[int] = []
    for episode_id in sorted(matching):
        result = matching[episode_id]
        for pair in result.pairs:
            gt = gt_by_id[pair.gt_id]
            pred = run["prediction_by_id"][pair.pred_id]
            matched_gt_ids.add(pair.gt_id)
            matched_pred_ids.add(pair.pred_id)
            if pair.match_class == "EXACT":
                exact += 1
            else:
                near += 1
            abs_errors.append(pair.abs_error_frames)
            pairs.append({
                "episode_id": pair.episode_id,
                "gt_id": pair.gt_id,
                "gt_frame": pair.gt_frame,
                "pred_boundary_id": pair.pred_id,
                "pred_frame": pair.pred_frame,
                "delta_frame": pair.delta_frame,
                "abs_error_frames": pair.abs_error_frames,
                "abs_error_seconds": pair.abs_error_seconds,
                "gt_source": gt["gt_source"],
                "protected_class": gt["protected_class"],
                "source_package": gt["source_package"],
                "pred_candidate_type": pred["candidate_type"],
                "pred_representative_candidate_id": pred["representative_candidate_id"],
                "match_class": pair.match_class,
            })

    unmatched_preds = [item for item in pred_points if item["pred_id"] not in matched_pred_ids]
    unmatched_gts = [row for row in gt_rows if str(row["gt_id"]) not in matched_gt_ids]
    anchor_status, pred_anchor_status = match_known_fp_anchors(unmatched_preds, snapshot["fp_rows"])

    tp = len(pairs)
    fp = len(unmatched_preds)
    fn = len(unmatched_gts)
    precision = ratio(tp, tp + fp, name="precision")
    recall = ratio(tp, tp + fn, name="recall")
    f1 = f1_score(precision, recall)
    loc = localization_summary(abs_errors)

    episode_rows: list[dict[str, Any]] = []
    over_count = 0
    total_over = 0
    for episode_id in sorted(expected_episodes):
        result = matching.get(episode_id)
        n_gt = sum(1 for row in gt_rows if row["episode_id"] == episode_id)
        n_pred = sum(1 for item in pred_points if item["episode_id"] == episode_id)
        ep_tp = result.tp if result else 0
        ep_fp = result.fp if result else n_pred
        ep_fn = result.fn if result else n_gt
        ep_prec = ratio(ep_tp, ep_tp + ep_fp, name=f"precision:{episode_id}")
        ep_rec = ratio(ep_tp, ep_tp + ep_fn, name=f"recall:{episode_id}")
        ep_f1 = f1_score(ep_prec, ep_rec)
        over = max(0, n_pred - n_gt)
        under = max(0, n_gt - n_pred)
        if over > 0:
            over_count += 1
            total_over += over
        ep_errors = [pair.abs_error_frames for pair in (result.pairs if result else ())]
        episode_rows.append({
            "episode_id": episode_id,
            "n_gt": n_gt,
            "n_pred": n_pred,
            "TP": ep_tp,
            "FP": ep_fp,
            "FN": ep_fn,
            "Precision": ep_prec,
            "Recall": ep_rec,
            "F1": ep_f1,
            "over_segmentation": over,
            "under_segmentation": under,
            "mean_localization_error_frames": (sum(ep_errors) / len(ep_errors)) if ep_errors else "",
        })

    gripper = _guardrail_recall(
        gt_rows, matched_gt_ids,
        lambda row: str(row["protected_class"]) == PROTECTED_GRIPPER,
    )
    merged = _guardrail_recall(
        gt_rows, matched_gt_ids,
        lambda row: str(row["protected_class"]) == PROTECTED_MERGED,
    )
    seed_dir = _guardrail_recall(
        gt_rows, matched_gt_ids,
        lambda row: str(row["protected_class"]) == PROTECTED_DIRECTION and str(row["source_package"]) == PACKAGE_SEED,
    )
    fresh_dir = _guardrail_recall(
        gt_rows, matched_gt_ids,
        lambda row: str(row["protected_class"]) == PROTECTED_DIRECTION and str(row["source_package"]) == PACKAGE_FRESH,
    )

    mode_counts = defaultdict(lambda: {"REMAINING": 0, "FIXED": 0})
    for payload in anchor_status.values():
        mode_counts[str(payload["error_mode"])][payload["status"]] += 1
    new_unanchored = [item for item in unmatched_preds if pred_anchor_status[item["pred_id"]]["is_new_unanchored_fp"]]
    remaining_total = sum(1 for payload in anchor_status.values() if payload["status"] == "REMAINING")
    fixed_total = sum(1 for payload in anchor_status.values() if payload["status"] == "FIXED")

    frag = fragmentation_diagnostics(run["segments"])
    spacing = gt_spacing_diagnostics(gt_rows)

    fp_rows = []
    for item in sorted(unmatched_preds, key=lambda row: (row["episode_id"], row["pred_frame"], row["pred_id"])):
        status = pred_anchor_status[item["pred_id"]]
        fp_rows.append({
            "episode_id": item["episode_id"],
            "pred_boundary_id": item["pred_boundary_id"],
            "pred_frame": item["pred_frame"],
            "candidate_type": item["candidate_type"],
            "representative_candidate_id": item["representative_candidate_id"],
            "member_candidate_types": item["member_candidate_types"],
            "member_candidate_frames": item["member_candidate_frames"],
            "known_fp_anchor_matched": _csv_bool(bool(status["known_fp_anchor_matched"])),
            "known_fp_anchor_frame": status["known_fp_anchor_frame"],
            "known_fp_error_mode": status["known_fp_error_mode"],
            "reason_code": status["reason_code"],
            "is_new_unanchored_fp": _csv_bool(bool(status["is_new_unanchored_fp"])),
        })
    fn_rows = [
        {
            "episode_id": row["episode_id"],
            "gt_id": row["gt_id"],
            "gt_frame": row["gt_frame"],
            "gt_source": row["gt_source"],
            "protected_class": row["protected_class"],
            "source_package": row["source_package"],
        }
        for row in sorted(unmatched_gts, key=lambda item: (item["episode_id"], int(item["gt_frame"]), item["gt_id"]))
    ]
    anchor_rows = [
        {
            "episode_id": payload["episode_id"],
            "anchor_frame": payload["anchor_frame"],
            "error_mode": payload["error_mode"],
            "source_package": payload["source_package"],
            "source_boundary_id": payload["source_boundary_id"],
            "status": payload["status"],
            "matched_pred_boundary_id": payload["matched_pred_boundary_id"],
            "matched_pred_frame": payload["matched_pred_frame"],
            "abs_error_frames": payload["abs_error_frames"],
        }
        for payload in sorted(anchor_status.values(), key=lambda item: (item["episode_id"], int(item["anchor_frame"])))
    ]

    metrics = {
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "FN_BASELINE": fn,
        "Precision": precision,
        "Recall": recall,
        "F1": f1,
        "EXACT_TP": exact,
        "NEAR_TP": near,
        "localization": loc,
        "episode_oversegmented_count": over_count,
        "total_oversegmentation": total_over,
        "mean_predicted_boundaries_per_episode": len(pred_points) / 12,
        "mean_gt_boundaries_per_episode": len(gt_rows) / 12,
        "oversegmented_episodes": [row["episode_id"] for row in episode_rows if int(row["over_segmentation"]) > 0],
        "MODE_01_REMAINING": mode_counts["MODE_01"]["REMAINING"],
        "MODE_01_FIXED": mode_counts["MODE_01"]["FIXED"],
        "MODE_02_REMAINING": mode_counts["MODE_02"]["REMAINING"],
        "MODE_02_FIXED": mode_counts["MODE_02"]["FIXED"],
        "MODE_03_REMAINING": mode_counts["MODE_03"]["REMAINING"],
        "MODE_03_FIXED": mode_counts["MODE_03"]["FIXED"],
        "UNASSIGNED_KNOWN_FP_REMAINING": mode_counts["UNASSIGNED"]["REMAINING"],
        "UNASSIGNED_KNOWN_FP_FIXED": mode_counts["UNASSIGNED"]["FIXED"],
        "KNOWN_FP_ANCHOR_TOTAL": len(snapshot["fp_rows"]),
        "KNOWN_FP_REMAINING_TOTAL": remaining_total,
        "KNOWN_FP_FIXED_TOTAL": fixed_total,
        "NEW_UNANCHORED_FP_COUNT": len(new_unanchored),
        "NEW_UNANCHORED_FP": [
            {
                "episode_id": item["episode_id"],
                "pred_frame": item["pred_frame"],
                "boundary_id": item["pred_id"],
                "representative_type": item["candidate_type"],
            }
            for item in new_unanchored
        ],
        "fragmentation": frag,
        "gt_spacing": spacing,
        "anchor_scope": "ALL_KNOWN_FP_ANCHORS_INCLUDING_UNASSIGNED",
        "REPORT_ANCHOR_SCOPE_CONTRACT_CONFLICT": False,
    }
    discrepancies = sanity_discrepancies(metrics, episode_rows)
    if discrepancies:
        raise ScoringSanityError("STOP SCORING FINALIZATION: " + json.dumps(discrepancies, ensure_ascii=False))

    guardrails = {
        "CALIBRATION_GRIPPER_RECALL": gripper["recall"],
        "CALIBRATION_MERGED_CLUSTER_RECALL": merged["recall"],
        "SEED_VALID_DIRECTION_RECALL": seed_dir["recall"],
        "FRESH_VALID_DIRECTION_RECALL_BASELINE": fresh_dir["recall"],
        "FN_BASELINE": fn,
        "slices": {
            "gripper": gripper,
            "merged": merged,
            "seed_valid_direction": seed_dir,
            "fresh_valid_direction": fresh_dir,
        },
    }

    created_at = now_iso()
    stamp = datetime.fromisoformat(created_at).strftime("%Y%m%d_%H%M%S")
    identity = hashlib.sha256(
        f"{EXPECTED_RUN_ID}|{EXPECTED_SNAPSHOT_ID}|{created_at}|{uuid.uuid4().hex}".encode("utf-8")
    ).hexdigest()[:8]
    score_id = f"g1_baseline_score_{stamp}_{identity}"
    out_root = Path(scoring_root or root / "outputs/g1_p3_scoring")
    out_root.mkdir(parents=True, exist_ok=True)
    final_path = out_root / score_id
    if final_path.exists():
        raise ScoringError(f"immutable score already exists: {final_path}")
    temp_path = out_root / f".tmp-{score_id}-{uuid.uuid4().hex}"
    temp_path.mkdir()

    meta = {
        "score_id": score_id,
        "metric_version": METRIC_VERSION,
        "scored_at": created_at,
        "run_id": EXPECTED_RUN_ID,
        "canonical_gt_snapshot_id": EXPECTED_SNAPSHOT_ID,
        "human_export_ids": list(EXPECTED_EXPORT_IDS),
        "matching_rule_id": MATCHING_RULE_ID,
        "tolerance_frames": TOLERANCE_FRAMES,
        "tolerance_seconds": TOLERANCE_SECONDS,
        "tolerance_is_search_axis": False,
        "config_hash": EXPECTED_CONFIG_HASH,
        "signal_contract_hash": EXPECTED_SIGNAL_HASH,
        "search_stage": "BASELINE",
        "parameter_search_executed": False,
        "stage_a0_executed": False,
        "detector_modified": False,
        "canonical_gt_modified": False,
        "evaluation_executed": False,
        "calibration_protocol_effective_version": CALIBRATION_PROTOCOL_EFFECTIVE_VERSION,
        "config_selection_rule": CONFIG_SELECTION_RULE,
        "FN_BASELINE": fn,
        "BASELINE_SCORING": "FROZEN",
        "NEXT_GATE": "STAGE_A0_DIRECTION_CANDIDATE_DISCRIMINABILITY_AUDIT",
        "FRAGMENTATION_SHORT_RATIO_CONTRACT_GAP": True,
        "anchor_scope": "ALL_KNOWN_FP_ANCHORS_INCLUDING_UNASSIGNED",
    }
    try:
        (temp_path / "score_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _write_csv(temp_path / "matching_pairs.csv", MATCHING_PAIR_FIELDS, pairs)
        _write_csv(temp_path / "unmatched_predictions_fp.csv", FP_FIELDS, fp_rows)
        _write_csv(temp_path / "unmatched_gt_fn.csv", FN_FIELDS, fn_rows)
        _write_csv(
            temp_path / "episode_metrics.csv",
            EPISODE_METRIC_FIELDS,
            [
                {
                    **row,
                    "Precision": f"{row['Precision']:.16g}",
                    "Recall": f"{row['Recall']:.16g}",
                    "F1": f"{row['F1']:.16g}",
                }
                for row in episode_rows
            ],
        )
        (temp_path / "guardrail_metrics.json").write_text(
            json.dumps(guardrails, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        _write_csv(temp_path / "known_fp_anchor_status.csv", ANCHOR_STATUS_FIELDS, anchor_rows)
        (temp_path / "baseline_metrics.json").write_text(
            json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        validate_score_dir(temp_path)
        os.rename(temp_path, final_path)
    except Exception:
        if temp_path.exists():
            shutil.rmtree(temp_path)
        raise

    after = _source_fingerprints(root)
    if before != after:
        shutil.rmtree(final_path)
        raise ScoringError("source immutability check failed after scoring")
    if after["owner_sqlite"] != SQLITE_SHA256:
        raise ScoringError("OWNER_SQLITE_UNCHANGED failed")

    return {
        "score_id": score_id,
        "score_root": str(final_path),
        "meta": meta,
        "metrics": metrics,
        "guardrails": guardrails,
        "episode_metrics": episode_rows,
        "validator": "PASS",
        "immutability": {
            "BASELINE_RUN_UNCHANGED": True,
            "CANONICAL_GT_SNAPSHOT_UNCHANGED": True,
            "SEED_EXPORT_UNCHANGED": True,
            "FRESH_EXPORT_UNCHANGED": True,
            "OWNER_SQLITE_UNCHANGED": True,
            "FROZEN_PROTOCOL_UNCHANGED": True,
            "DATASET_UNCHANGED": after["dataset"] is not None,
            "fingerprints": after,
        },
    }
