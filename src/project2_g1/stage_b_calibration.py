"""G1-P3 Stage B limited consolidation calibration.

The Stage A owner-selected acceptance rule is fixed.  This module varies only
the in-memory boundary consolidation window over the frozen set {8, 10, 12}.
"""
from __future__ import annotations

import csv
import json
import os
import uuid
from collections import defaultdict
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .baseline_scoring import (
    EXPECTED_CONFIG_HASH, EXPECTED_RUN_ID, EXPECTED_SIGNAL_HASH,
    EXPECTED_SNAPSHOT_ID, load_canonical_snapshot, match_known_fp_anchors,
)
from .boundary_config import G1P2Config, load_g1_p2_config
from .boundary_engine import (
    CANDIDATE_DIRECTION, CANDIDATE_GRIPPER, CANDIDATE_IDLE_TO_MOVE,
    BoundaryEvent, EngineResult, run_boundary_engine,
)
from .boundary_matching import match_by_episode
from .paths import PROJECT2_ROOT
from .stage_a12_calibration import (
    SNAPSHOT_RUN, TRACE_FIELDS, _load_signals, acceptance_callback, score_results,
)

STAGE_A_PARENT = "A1-007-C002"
TAU_P12 = 0.04758563666765155
TAU_C12 = 0.690169167642685
STAGE_B_WINDOWS = (8, 10, 12)
DIAGNOSTIC_SET_THRESHOLD_USAGE = "FORBIDDEN"
EVALUATION_USAGE = "FORBIDDEN"

CANDIDATE_FIELDS = (
    "candidate_id", "parent_candidate_id", "variant", "boundary_consolidation_window",
    "tau_P12", "tau_C12", "TP", "FP", "FN", "Precision", "Recall", "F1",
    "Direction_FP_remaining", "Seed_Direction_FP_remaining", "Fresh_Direction_FP_remaining",
    "MODE_01_remaining", "MODE_02_remaining", "MODE_03_remaining", "UNASSIGNED_remaining",
    "NEW_UNANCHORED_FP", "Gripper_recall", "Merged_cluster_recall",
    "Seed_valid_direction_recall", "Fresh_valid_direction_recall", "Localization_mean",
    "Localization_median", "Localization_p90", "Localization_max",
    "fragmentation_1_2_ratio", "segments_per_episode", "STAGE_B_HARD_GUARDRAIL",
    "DEMO_255_125_135_SAME_CLUSTER", "DEMO_242_60_STATUS", "selection_status",
)

CHANGED_FIELDS = (
    "episode_id", "window_from", "window_to", "old_final_boundaries", "new_final_boundary",
    "member_candidate_ids", "member_candidate_types", "member_candidate_frames",
    "representative_before", "representative_after", "GT_MATCH_BEFORE", "GT_MATCH_AFTER",
    "TP_TO_FN", "TWO_VALID_GT_MERGED", "REPRESENTATIVE_FRAME_CHANGED",
    "INDEPENDENT_EVENT_MERGED",
)


class StageBCalibrationError(ValueError):
    pass


def _write_csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def runtime_config(window: int, base: G1P2Config | None = None) -> G1P2Config:
    if int(window) not in STAGE_B_WINDOWS:
        raise StageBCalibrationError(f"Stage B window outside frozen search space: {window}")
    return replace(base or load_g1_p2_config(), boundary_consolidation_window=int(window))


def assert_single_factor(configs: Sequence[G1P2Config]) -> None:
    rows = []
    for config in configs:
        row = asdict(config)
        row.pop("boundary_consolidation_window")
        rows.append(row)
    if not rows or any(row != rows[0] for row in rows[1:]):
        raise StageBCalibrationError("Stage B configs differ beyond boundary_consolidation_window")


def run_window(signals: Mapping[str, Any], window: int) -> tuple[list[EngineResult], list[dict[str, Any]]]:
    config = runtime_config(window)
    trace: list[dict[str, Any]] = []
    callback = acceptance_callback("P12_C12", TAU_P12, TAU_C12, trace)
    return [run_boundary_engine(signals[ep], config, callback) for ep in sorted(signals)], trace


def _predictions(results: Sequence[EngineResult]) -> list[dict[str, Any]]:
    return [{
        "episode_id": event.episode_id,
        "pred_id": f"{event.episode_id}:{event.boundary_id}",
        "pred_boundary_id": event.boundary_id,
        "pred_frame": event.frame,
        "candidate_type": event.candidate_type,
    } for result in results for event in result.final_events]


def scoring_details(results: Sequence[EngineResult], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    preds = _predictions(results)
    gts = [{"episode_id": r["episode_id"], "gt_id": r["gt_id"], "gt_frame": int(r["gt_frame"])}
           for r in snapshot["gt_rows"]]
    matching = match_by_episode(gts, preds)
    pairs = [pair for value in matching.values() for pair in value.pairs]
    matched_preds = {p.pred_id for p in pairs}
    unmatched = [p for p in preds if p["pred_id"] not in matched_preds]
    anchors, pred_anchors = match_known_fp_anchors(unmatched, snapshot["fp_rows"])
    return {
        "pairs": pairs,
        "pair_by_pred": {p.pred_id: p for p in pairs},
        "unmatched": unmatched,
        "anchors": anchors,
        "pred_anchors": pred_anchors,
    }


def hard_guardrail(metrics: Mapping[str, Any], parent: Mapping[str, Any]) -> bool:
    return (
        metrics["Gripper_recall"] == 1.0
        and metrics["Merged_cluster_recall"] == 1.0
        and metrics["Seed_valid_direction_recall"] == 1.0
        and metrics["Fresh_valid_direction_recall"] >= parent["Fresh_valid_direction_recall"]
        and metrics["FN"] <= parent["FN"]
        and metrics["NEW_UNANCHORED_FP"] == 0
    )


def _find_result(results: Sequence[EngineResult], episode_id: str) -> EngineResult:
    return next(result for result in results if result.episode_id == episode_id)


def demo255_trace(results: Sequence[EngineResult], window: int) -> list[dict[str, Any]]:
    result = _find_result(results, "data/demo_255")
    wanted = [c for c in result.candidates if (c.frame, c.candidate_type) in {
        (125, CANDIDATE_GRIPPER), (135, CANDIDATE_IDLE_TO_MOVE)}]
    if len(wanted) != 2:
        raise StageBCalibrationError(f"demo_255 target candidates missing at window={window}")
    events = {e.boundary_id: e for e in result.events}
    target_ids = [result.decisions[c.candidate_id].target_boundary_id for c in wanted]
    same = bool(target_ids[0] and target_ids[0] == target_ids[1])
    rows = []
    for cand in wanted:
        decision = result.decisions[cand.candidate_id]
        event = events.get(decision.target_boundary_id or "")
        rows.append({
            "episode_id": result.episode_id, "window": window, "candidate_id": cand.candidate_id,
            "candidate_type": cand.candidate_type, "candidate_frame": cand.frame,
            "decision": decision.decision, "target_boundary_id": decision.target_boundary_id or "",
            "final_boundary_id": event.boundary_id if event and event.active else "",
            "final_boundary_frame": event.frame if event and event.active else "",
            "representative_candidate_id": event.representative_candidate_id if event else "",
            "member_candidate_ids": "|".join(event.member_candidate_ids) if event else "",
            "member_candidate_types": "|".join(event.member_candidate_types) if event else "",
            "member_candidate_frames": "|".join(map(str, event.member_candidate_frames)) if event else "",
            "SAME_FINAL_CLUSTER": "YES" if same else "NO",
            "FINAL_REPRESENTATIVE_TYPE": event.candidate_type if same and event else "",
            "FINAL_REPRESENTATIVE_FRAME": event.frame if same and event else "",
        })
    return rows


def demo242_trace(results: Sequence[EngineResult], window: int) -> dict[str, Any]:
    result = _find_result(results, "data/demo_242")
    candidate = next((c for c in result.candidates if c.frame == 60 and c.candidate_type == CANDIDATE_DIRECTION), None)
    if candidate is None:
        raise StageBCalibrationError("demo_242@60 direction candidate missing")
    decision = result.decisions[candidate.candidate_id]
    event = next((e for e in result.events if candidate.candidate_id in e.member_candidate_ids), None)
    if event and event.active and len(event.member_candidate_ids) == 1:
        status = "REMAINING"
    elif event and event.active:
        status = "MERGED"
    elif decision.decision.startswith("REJECT") or decision.decision.startswith("SUPPRESS"):
        status = "SUPPRESSED"
    else:
        status = "OTHER"
    nearest = sorted(result.final_events, key=lambda e: (abs(e.frame - 60), e.frame))[:3]
    return {
        "episode_id": result.episode_id, "window": window, "candidate_id": candidate.candidate_id,
        "candidate_type": candidate.candidate_type, "candidate_frame": candidate.frame,
        "decision": decision.decision, "target_boundary_id": decision.target_boundary_id or "",
        "FINAL_STATUS": status,
        "final_boundary_id": event.boundary_id if event and event.active else "",
        "final_boundary_frame": event.frame if event and event.active else "",
        "representative_candidate_id": event.representative_candidate_id if event else "",
        "member_candidate_ids": "|".join(event.member_candidate_ids) if event else "",
        "member_candidate_types": "|".join(event.member_candidate_types) if event else "",
        "member_candidate_frames": "|".join(map(str, event.member_candidate_frames)) if event else "",
        "NEAREST_ACTIVE_FINALS": "|".join(f"{e.frame}:{e.candidate_type}" for e in nearest),
        "ACCEPTANCE_RESIDUAL_CHANGED_BY_STAGE_B": "YES" if window != 8 and status != "REMAINING" else "NO",
    }


def residual_fp_rows(results: Sequence[EngineResult], snapshot: Mapping[str, Any], window: int) -> list[dict[str, Any]]:
    details = scoring_details(results, snapshot)
    event_by_pred = {f"{e.episode_id}:{e.boundary_id}": e for r in results for e in r.final_events}
    rows = []
    for pred in details["unmatched"]:
        event = event_by_pred[pred["pred_id"]]
        anchor = details["pred_anchors"][pred["pred_id"]]
        rows.append({
            "window": window, "episode_id": event.episode_id, "final_boundary_id": event.boundary_id,
            "final_frame": event.frame, "candidate_type": event.candidate_type,
            "representative_candidate_id": event.representative_candidate_id,
            "member_candidate_ids": "|".join(event.member_candidate_ids),
            "member_candidate_types": "|".join(event.member_candidate_types),
            "member_candidate_frames": "|".join(map(str, event.member_candidate_frames)),
            **anchor,
        })
    return rows


def _event_signature(event: BoundaryEvent) -> frozenset[str]:
    return frozenset(event.member_candidate_ids)


def changed_cluster_lineage(base: Sequence[EngineResult], other: Sequence[EngineResult],
                            snapshot: Mapping[str, Any], window_to: int) -> list[dict[str, Any]]:
    before_details = scoring_details(base, snapshot)
    after_details = scoring_details(other, snapshot)
    before_pair = before_details["pair_by_pred"]
    after_pair = after_details["pair_by_pred"]
    base_by_ep = {r.episode_id: r for r in base}
    rows = []
    for new_result in other:
        old_result = base_by_ep[new_result.episode_id]
        old_events = old_result.final_events
        for new in new_result.final_events:
            overlapping = [old for old in old_events if _event_signature(old) & _event_signature(new)]
            if len(overlapping) == 1 and _event_signature(overlapping[0]) == _event_signature(new):
                continue
            old_ids = [f"{old.episode_id}:{old.boundary_id}" for old in overlapping]
            new_id = f"{new.episode_id}:{new.boundary_id}"
            old_gt = [before_pair[x].gt_id for x in old_ids if x in before_pair]
            new_gt = [after_pair[new_id].gt_id] if new_id in after_pair else []
            old_repr = "|".join(f"{e.representative_candidate_id}@{e.frame}" for e in overlapping)
            rows.append({
                "episode_id": new.episode_id, "window_from": 8, "window_to": window_to,
                "old_final_boundaries": "|".join(f"{e.boundary_id}@{e.frame}:{e.candidate_type}" for e in overlapping),
                "new_final_boundary": f"{new.boundary_id}@{new.frame}:{new.candidate_type}",
                "member_candidate_ids": "|".join(new.member_candidate_ids),
                "member_candidate_types": "|".join(new.member_candidate_types),
                "member_candidate_frames": "|".join(map(str, new.member_candidate_frames)),
                "representative_before": old_repr,
                "representative_after": f"{new.representative_candidate_id}@{new.frame}",
                "GT_MATCH_BEFORE": "|".join(old_gt) or "UNMATCHED",
                "GT_MATCH_AFTER": "|".join(new_gt) or "UNMATCHED",
                "TP_TO_FN": "YES" if len(old_gt) > len(new_gt) else "NO",
                "TWO_VALID_GT_MERGED": "YES" if len(set(old_gt)) >= 2 and len(new_gt) < len(set(old_gt)) else "NO",
                "REPRESENTATIVE_FRAME_CHANGED": "YES" if not any(
                    e.representative_candidate_id == new.representative_candidate_id and e.frame == new.frame
                    for e in overlapping
                ) else "NO",
                "INDEPENDENT_EVENT_MERGED": "YES" if len(overlapping) >= 2 and len(set(old_gt)) >= 2 else "NO",
            })
    return rows


def _parent_gate(metrics: Mapping[str, Any], residuals: Sequence[Mapping[str, Any]]) -> None:
    frames = {(r["episode_id"], r["final_frame"], r["candidate_type"]) for r in residuals}
    required = {("data/demo_242", 60, CANDIDATE_DIRECTION),
                ("data/demo_255", 135, CANDIDATE_IDLE_TO_MOVE)}
    if (metrics["TP"], metrics["FP"], metrics["FN"], metrics["Direction_FP_remaining"]) != (56, 2, 0, 1) or frames != required:
        raise StageBCalibrationError(f"STOP_STAGE_B_PARENT_REPLAY_MISMATCH metrics={metrics} residuals={frames}")


def run_stage_b(*, project_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(project_root or PROJECT2_ROOT).resolve()
    snapshot = load_canonical_snapshot(root / SNAPSHOT_RUN)
    episodes = list(snapshot["manifest"]["episode_ids"])
    signals = _load_signals(root, episodes)
    configs = [runtime_config(w) for w in STAGE_B_WINDOWS]
    assert_single_factor(configs)

    by_window: dict[int, list[EngineResult]] = {}
    traces: list[dict[str, Any]] = []
    metrics: dict[int, dict[str, Any]] = {}
    details: dict[int, dict[str, Any]] = {}
    demo255: list[dict[str, Any]] = []
    demo242: list[dict[str, Any]] = []
    residuals: list[dict[str, Any]] = []
    for window in STAGE_B_WINDOWS:
        results, trace = run_window(signals, window)
        by_window[window] = results
        traces.extend({**row, "boundary_consolidation_window": window} for row in trace)
        metrics[window] = score_results(results, snapshot)
        details[window] = scoring_details(results, snapshot)
        demo255.extend(demo255_trace(results, window))
        demo242.append(demo242_trace(results, window))
        residuals.extend(residual_fp_rows(results, snapshot, window))
        if window == 8:
            _parent_gate(metrics[window], [r for r in residuals if r["window"] == 8])

    parent = metrics[8]
    candidate_rows = []
    for window in STAGE_B_WINDOWS:
        same = next(r["SAME_FINAL_CLUSTER"] for r in demo255 if r["window"] == window)
        d242 = next(r["FINAL_STATUS"] for r in demo242 if r["window"] == window)
        safe = hard_guardrail(metrics[window], parent)
        candidate_rows.append({
            "candidate_id": f"STAGE-B-W{window:02d}", "parent_candidate_id": STAGE_A_PARENT,
            "variant": "LIMITED_CONSOLIDATION", "boundary_consolidation_window": window,
            "tau_P12": TAU_P12, "tau_C12": TAU_C12, **metrics[window],
            "STAGE_B_HARD_GUARDRAIL": "PASS" if safe else "FAIL",
            "DEMO_255_125_135_SAME_CLUSTER": same, "DEMO_242_60_STATUS": d242,
            "selection_status": "STAGE_B_SAFE_CANDIDATE" if safe and same == "YES" else ("CONTROL" if window == 8 else "NOT_STAGE_B_SAFE"),
        })

    changed = changed_cluster_lineage(by_window[8], by_window[10], snapshot, 10)
    changed += changed_cluster_lineage(by_window[8], by_window[12], snapshot, 12)
    safe_windows = [r["boundary_consolidation_window"] for r in candidate_rows
                    if r["selection_status"] == "STAGE_B_SAFE_CANDIDATE"]
    minimal = min(safe_windows) if safe_windows else None
    over = {w: [r for r in changed if r["window_to"] == w and
                (r["TP_TO_FN"] == "YES" or r["TWO_VALID_GT_MERGED"] == "YES" or r["INDEPENDENT_EVENT_MERGED"] == "YES")]
            for w in (10, 12)}

    now = datetime.now().astimezone()
    run_id = "g1_p3_stage_b_" + now.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    output = root / "outputs/g1_p3_stage_b_consolidation" / run_id
    temp = output.parent / (".tmp-" + run_id)
    if output.exists() or temp.exists():
        raise StageBCalibrationError("immutable output run already exists")
    temp.mkdir(parents=True, exist_ok=False)
    _write_csv(temp / "stage_b_candidates.csv", CANDIDATE_FIELDS, candidate_rows)
    _write_csv(temp / "residual_fp_trace.csv", list(residuals[0]), residuals)
    _write_csv(temp / "demo_255_consolidation_trace.csv", list(demo255[0]), demo255)
    _write_csv(temp / "demo_242_acceptance_residual_trace.csv", list(demo242[0]), demo242)
    _write_csv(temp / "changed_cluster_lineage.csv", CHANGED_FIELDS, changed)
    trace_fields = list(TRACE_FIELDS) + ["boundary_consolidation_window"]
    _write_csv(temp / "candidate_acceptance_trace.csv", trace_fields, traces)
    summary = {
        "run_id": run_id, "created_at": now.isoformat(), "stage_a_parent": STAGE_A_PARENT,
        "tau_P12": TAU_P12, "tau_C12": TAU_C12, "search_space": list(STAGE_B_WINDOWS),
        "parent_replay": "PASS", "windows": {str(r["boundary_consolidation_window"]): r for r in candidate_rows},
        "changed_cluster_count_8_to_10": sum(r["window_to"] == 10 for r in changed),
        "changed_cluster_count_8_to_12": sum(r["window_to"] == 12 for r in changed),
        "over_consolidation_cases_window_10": len(over[10]),
        "over_consolidation_cases_window_12": len(over[12]),
        "demo_255_under_consolidation_fixed_by": [w for w in STAGE_B_WINDOWS if next(r["SAME_FINAL_CLUSTER"] for r in demo255 if r["window"] == w) == "YES"],
        "demo_242_acceptance_residual_accidentally_changed_by": [r["window"] for r in demo242 if r["ACCEPTANCE_RESIDUAL_CHANGED_BY_STAGE_B"] == "YES"],
        "stage_b_safe_candidates": safe_windows, "minimal_safe_window_candidate": minimal,
        "STAGE_B_EXECUTED": True, "STAGE_B_OWNER_SELECTION_PENDING": True,
        "STAGE_C_EXECUTED": False, "CALIBRATION_CONFIG_FROZEN": False,
        "EVALUATION_TOUCHED": False, "CANONICAL_GT_MODIFIED": False,
        "HUMAN_REVIEW_MODIFIED": False,
    }
    meta = {
        "run_id": run_id, "created_at": now.isoformat(), "protocol": "FROZEN_v1.2_STAGE_B_LIMITED",
        "config_hash": EXPECTED_CONFIG_HASH, "signal_contract_hash": EXPECTED_SIGNAL_HASH,
        "canonical_gt_snapshot_id": EXPECTED_SNAPSHOT_ID, "baseline_run_id": EXPECTED_RUN_ID,
        "stage_a_parent": STAGE_A_PARENT, "DIAGNOSTIC_SET_THRESHOLD_USAGE": DIAGNOSTIC_SET_THRESHOLD_USAGE,
        "EVALUATION_USAGE": EVALUATION_USAGE, "runtime_override_only": True,
    }
    (temp / "stage_b_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (temp / "run_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    os.rename(temp, output)
    return {"summary": summary, "output_run": str(output), "candidate_rows": candidate_rows,
            "changed": changed, "demo255": demo255, "demo242": demo242}
