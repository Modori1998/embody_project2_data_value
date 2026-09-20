"""Read-only Baseline Scoring comparison view for the G1 Audit Web.

Loads a run's latest scoring artifact (TP / FP / FN) and the frozen Canonical
Human Boundary GT, then builds side-by-side "detector vs gold standard" models.

This module NEVER writes review data, never re-runs matching, never modifies
the Detector, and never selects a threshold.  It only reads the immutable
runtime scoring artifact referenced by run_id (and the GT snapshot referenced
by that artifact).
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from project2_g1.paths import PROJECT2_ROOT


class ScoringUnavailable(ValueError):
    pass


SCORING_DIR_NAME = "g1_p3_scoring"
CANONICAL_GT_DIR_NAME = "g1_p3_canonical_gt"

MATCH_TP = "TP"
MATCH_FP = "FP"
MATCH_FN = "FN"


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


@dataclass
class ScoringBundle:
    score_id: str
    score_dir: Path
    meta: dict[str, Any]
    metrics: dict[str, Any]
    matching_pairs: list[dict[str, str]]
    unmatched_predictions_fp: list[dict[str, str]]
    unmatched_gt_fn: list[dict[str, str]]
    canonical_gt_dir: Path
    canonical_gt: list[dict[str, str]]
    known_fp_anchors: list[dict[str, str]]
    gt_by_episode: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    tp_by_episode: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    fp_by_episode: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    fn_by_episode: dict[str, list[dict[str, str]]] = field(default_factory=dict)


def discover_score(project_root: str | Path, run_id: str) -> dict[str, Any] | None:
    """Return {score_id, score_dir, meta} of the newest score for run_id, or None."""

    root = Path(project_root) / "outputs" / SCORING_DIR_NAME
    if not root.is_dir():
        return None
    candidates: list[tuple[Path, dict[str, Any]]] = []
    for meta_path in sorted(root.glob("*/score_meta.json")):
        try:
            meta = _read_json(meta_path)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if str(meta.get("run_id") or "") == run_id:
            candidates.append((meta_path.parent, meta))
    if not candidates:
        return None
    # score_id embeds a timestamp; newest first.
    candidates.sort(key=lambda item: str(item[1].get("score_id") or ""), reverse=True)
    score_dir, meta = candidates[0]
    return {
        "score_id": str(meta.get("score_id") or score_dir.name),
        "score_dir": score_dir,
        "meta": meta,
    }


def load_bundle(project_root: str | Path, run_id: str) -> ScoringBundle:
    discovered = discover_score(project_root, run_id)
    if discovered is None:
        raise ScoringUnavailable(f"no scoring artifact found for run_id: {run_id}")
    root = Path(project_root)
    score_dir = discovered["score_dir"]
    meta = discovered["meta"]
    metrics_path = score_dir / "baseline_metrics.json"
    metrics = _read_json(metrics_path) if metrics_path.is_file() else {}
    matching_pairs = _read_csv_rows(score_dir / "matching_pairs.csv")
    fp_rows = _read_csv_rows(score_dir / "unmatched_predictions_fp.csv")
    fn_rows = _read_csv_rows(score_dir / "unmatched_gt_fn.csv")

    snapshot_id = str(meta.get("canonical_gt_snapshot_id") or "")
    gt_dir = root / "outputs" / CANONICAL_GT_DIR_NAME / snapshot_id if snapshot_id else None
    canonical_gt: list[dict[str, str]] = []
    known_fp_anchors: list[dict[str, str]] = []
    if gt_dir is not None and gt_dir.is_dir():
        canonical_gt = _read_csv_rows(gt_dir / "canonical_human_boundary_gt.csv")
        anchors_path = gt_dir / "known_false_positive_anchor.csv"
        if anchors_path.is_file():
            known_fp_anchors = _read_csv_rows(anchors_path)

    bundle = ScoringBundle(
        score_id=discovered["score_id"],
        score_dir=score_dir,
        meta=meta,
        metrics=metrics,
        matching_pairs=matching_pairs,
        unmatched_predictions_fp=fp_rows,
        unmatched_gt_fn=fn_rows,
        canonical_gt_dir=gt_dir if gt_dir is not None else Path(),
        canonical_gt=canonical_gt,
        known_fp_anchors=known_fp_anchors,
    )
    bundle.gt_by_episode = _group_by(canonical_gt, "episode_id")
    bundle.tp_by_episode = _group_by(matching_pairs, "episode_id")
    bundle.fp_by_episode = _group_by(fp_rows, "episode_id")
    bundle.fn_by_episode = _group_by(fn_rows, "episode_id")
    return bundle


def _group_by(rows: list[dict[str, str]], key: str) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        out.setdefault(str(row.get(key) or ""), []).append(row)
    return out


def _int(value: Any) -> int | None:
    text = str(value or "").strip()
    if text == "":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _as_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes"}


def build_run_overview(bundle: ScoringBundle, episodes: list[Any]) -> dict[str, Any]:
    """Run-level scoring summary, with one row per episode."""

    totals = {"tp": len(bundle.matching_pairs), "fp": len(bundle.unmatched_predictions_fp), "fn": len(bundle.unmatched_gt_fn)}
    episode_rows: list[dict[str, Any]] = []
    episode_ids = [ep.episode_id for ep in episodes]
    for ep in episodes:
        episode_id = str(ep.episode_id)
        tp = len(bundle.tp_by_episode.get(episode_id, []))
        fp = len(bundle.fp_by_episode.get(episode_id, []))
        fn = len(bundle.fn_by_episode.get(episode_id, []))
        new_unanchored = sum(1 for row in bundle.fp_by_episode.get(episode_id, []) if _as_bool(row.get("is_new_unanchored_fp")))
        episode_rows.append(
            {
                "episode_id": episode_id,
                "quality_group": str(getattr(ep, "quality_group", "") or ""),
                "n_gt": len(bundle.gt_by_episode.get(episode_id, [])),
                "n_pred": int(getattr(ep, "final_boundary_count", 0) or 0),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "new_unanchored_fp": new_unanchored,
            }
        )
    return {
        "score_id": bundle.score_id,
        "meta": bundle.meta,
        "metrics": bundle.metrics,
        "totals": totals,
        "episodes": episode_rows,
        "episode_ids": episode_ids,
        "canonical_gt_snapshot_id": str(bundle.meta.get("canonical_gt_snapshot_id") or ""),
        "canonical_gt_count": len(bundle.canonical_gt),
        "known_fp_anchor_count": len(bundle.known_fp_anchors),
    }


def _matched_pred_ids(tp_rows: list[dict[str, str]]) -> set[str]:
    return {str(row.get("pred_boundary_id") or "") for row in tp_rows}


def _matched_gt_ids(tp_rows: list[dict[str, str]]) -> set[str]:
    return {str(row.get("gt_id") or "") for row in tp_rows}


def build_episode_comparison(
    bundle: ScoringBundle,
    *,
    episode_id: str,
    boundaries: list[dict[str, str]],
    length: int,
) -> dict[str, Any]:
    """Side-by-side detector-vs-GT model for one episode."""

    gt_rows = bundle.gt_by_episode.get(episode_id, [])
    tp_rows = bundle.tp_by_episode.get(episode_id, [])
    fp_rows = bundle.fp_by_episode.get(episode_id, [])
    fn_rows = bundle.fn_by_episode.get(episode_id, [])

    matched_gt = _matched_gt_ids(tp_rows)
    matched_pred = _matched_pred_ids(tp_rows)

    tp_by_gt: dict[str, dict[str, str]] = {str(row.get("gt_id") or ""): row for row in tp_rows}
    tp_by_pred: dict[str, dict[str, str]] = {str(row.get("pred_boundary_id") or ""): row for row in tp_rows}

    timeline: list[dict[str, Any]] = []
    for row in tp_rows:
        timeline.append(
            {
                "frame": _int(row.get("pred_frame")),
                "status": MATCH_TP,
                "gt": {
                    "gt_id": str(row.get("gt_id") or ""),
                    "gt_frame": _int(row.get("gt_frame")),
                    "protected_class": str(row.get("protected_class") or ""),
                    "gt_source": str(row.get("gt_source") or ""),
                    "source_package": str(row.get("source_package") or ""),
                },
                "pred": {
                    "boundary_id": str(row.get("pred_boundary_id") or ""),
                    "pred_frame": _int(row.get("pred_frame")),
                    "candidate_type": str(row.get("pred_candidate_type") or ""),
                },
                "delta": _int(row.get("delta_frame")),
                "note": "",
            }
        )
    for row in fp_rows:
        is_new = _as_bool(row.get("is_new_unanchored_fp"))
        note_parts = []
        if is_new:
            note_parts.append("NEW_UNANCHORED_FP")
        else:
            mode = str(row.get("known_fp_error_mode") or "").strip()
            reason = str(row.get("reason_code") or "").strip()
            note_parts.append("known FP anchor")
            if mode:
                note_parts.append(mode)
            if reason:
                note_parts.append(reason)
        timeline.append(
            {
                "frame": _int(row.get("pred_frame")),
                "status": MATCH_FP,
                "gt": None,
                "pred": {
                    "boundary_id": str(row.get("pred_boundary_id") or ""),
                    "pred_frame": _int(row.get("pred_frame")),
                    "candidate_type": str(row.get("candidate_type") or ""),
                },
                "delta": None,
                "note": " · ".join(note_parts),
                "is_new_unanchored": is_new,
            }
        )
    for row in fn_rows:
        timeline.append(
            {
                "frame": _int(row.get("gt_frame")),
                "status": MATCH_FN,
                "gt": {
                    "gt_id": str(row.get("gt_id") or ""),
                    "gt_frame": _int(row.get("gt_frame")),
                    "protected_class": str(row.get("protected_class") or ""),
                    "gt_source": str(row.get("gt_source") or ""),
                    "source_package": str(row.get("source_package") or ""),
                },
                "pred": None,
                "delta": None,
                "note": "",
            }
        )
    timeline.sort(key=lambda item: (item["frame"] if item["frame"] is not None else -1))

    # Detector side: full predicted final boundaries with match status.
    pred_list: list[dict[str, Any]] = []
    for row in boundaries:
        boundary_id = str(row.get("boundary_id") or "")
        matched = tp_by_pred.get(boundary_id)
        if matched is not None:
            status = MATCH_TP
            gt_id = str(matched.get("gt_id") or "")
            delta = _int(matched.get("delta_frame"))
        else:
            status = MATCH_FP
            gt_id = ""
            delta = None
        pred_list.append(
            {
                "boundary_id": boundary_id,
                "frame": _int(row.get("frame")),
                "candidate_type": str(row.get("candidate_type") or ""),
                "reason": str(row.get("reason") or ""),
                "status": status,
                "matched_gt_id": gt_id,
                "delta": delta,
            }
        )
    pred_list.sort(key=lambda item: (item["frame"] if item["frame"] is not None else -1))

    # Gold-standard side: full GT with match status.
    gt_list: list[dict[str, Any]] = []
    for row in gt_rows:
        gt_id = str(row.get("gt_id") or "")
        matched = tp_by_gt.get(gt_id)
        if matched is not None:
            status = MATCH_TP
            pred_id = str(matched.get("pred_boundary_id") or "")
            delta = _int(matched.get("delta_frame"))
        else:
            status = MATCH_FN
            pred_id = ""
            delta = None
        gt_list.append(
            {
                "gt_id": gt_id,
                "gt_frame": _int(row.get("gt_frame")),
                "protected_class": str(row.get("protected_class") or ""),
                "gt_source": str(row.get("gt_source") or ""),
                "source_package": str(row.get("source_package") or ""),
                "human_decision": str(row.get("human_decision") or ""),
                "reason_code": str(row.get("reason_code") or ""),
                "comment": str(row.get("comment") or ""),
                "status": status,
                "matched_pred_id": pred_id,
                "delta": delta,
            }
        )
    gt_list.sort(key=lambda item: (item["gt_frame"] if item["gt_frame"] is not None else -1))

    return {
        "episode_id": episode_id,
        "length": length,
        "timeline": timeline,
        "pred_list": pred_list,
        "gt_list": gt_list,
        "counts": {
            "n_gt": len(gt_rows),
            "n_pred": len(boundaries),
            "tp": len(tp_rows),
            "fp": len(fp_rows),
            "fn": len(fn_rows),
        },
    }
