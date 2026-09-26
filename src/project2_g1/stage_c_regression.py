"""G1-P3 Stage C regression-only verification.

No parameter search is exposed here.  The Owner-selected Stage A acceptance
and retained parent postprocess configuration are replayed twice verbatim.
"""
from __future__ import annotations

import csv
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from project2_g1_audit_web.hashes import sha256_file, tree_fingerprint

from .baseline_scoring import (
    EXPECTED_EXPORT_IDS, EXPECTED_CONFIG_HASH, EXPECTED_RUN_ID,
    EXPECTED_SIGNAL_HASH, EXPECTED_SNAPSHOT_ID, SQLITE_SHA256,
    fragmentation_diagnostics, load_canonical_snapshot, localization_summary,
)
from .boundary_engine import DECISION_REJECT_ACCEPTANCE, EngineResult
from .boundary_matching import SAMPLE_HZ
from .paths import PROJECT2_ROOT
from .stage_a12_calibration import SNAPSHOT_RUN, TRACE_FIELDS, _load_signals, score_results
from .stage_b_calibration import (
    EVALUATION_USAGE, STAGE_A_PARENT, TAU_C12, TAU_P12, hard_guardrail,
    run_window, scoring_details,
)

BOUNDARY_CONSOLIDATION_WINDOW = 8
NEW_SEARCH_AXIS = "FORBIDDEN"
PARAMETER_TUNING = "FORBIDDEN"
THRESHOLD_SELECTION = "FORBIDDEN"

RESIDUAL_FIELDS = (
    "episode_id", "pred_frame", "candidate_type", "final_boundary_id",
    "representative_candidate_id", "member_candidate_ids", "member_candidate_types",
    "member_candidate_frames", "known_fp_anchor_matched", "known_fp_anchor_frame",
    "error_mode", "reason_code", "residual_role",
)
EDGE_FIELDS = (
    "episode_id", "candidate_id", "frame", "candidate_type", "P12",
    "P12_context_complete", "C12", "C12_context_complete", "fallback_behavior",
    "acceptance_decision", "final_status", "target_boundary_id",
)


class StageCRegressionError(ValueError):
    pass


def _write_csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def fixed_config_identity() -> dict[str, Any]:
    return {
        "stage_a_parent": STAGE_A_PARENT,
        "tau_P12": TAU_P12,
        "tau_C12": TAU_C12,
        "boundary_consolidation_window": BOUNDARY_CONSOLIDATION_WINDOW,
        "new_search_axis": NEW_SEARCH_AXIS,
        "parameter_tuning": PARAMETER_TUNING,
        "threshold_selection": THRESHOLD_SELECTION,
    }


def validate_parent(metrics: Mapping[str, Any]) -> None:
    expected = (56, 2, 0, 0.9655172413793104, 1.0, 0.9824561403508771, 1, 0, 0.0, 0.0)
    actual = (
        metrics["TP"], metrics["FP"], metrics["FN"], metrics["Precision"],
        metrics["Recall"], metrics["F1"], metrics["Direction_FP_remaining"],
        metrics["NEW_UNANCHORED_FP"], metrics["Localization_p90"],
        metrics["fragmentation_1_2_ratio"],
    )
    if actual != expected:
        raise StageCRegressionError(f"STOP_STAGE_C_PARENT_REPLAY_MISMATCH actual={actual}")


def stage_c_guardrails(metrics: Mapping[str, Any]) -> bool:
    return (
        hard_guardrail(metrics, metrics)
        and metrics["Fresh_valid_direction_recall"] == 1.0
        and metrics["FN"] == 0
        and metrics["NEW_UNANCHORED_FP"] == 0
    )


def _event_map(results: Sequence[EngineResult]) -> dict[str, Any]:
    return {f"{event.episode_id}:{event.boundary_id}": event
            for result in results for event in result.final_events}


def residual_role(candidate_type: str, reason_code: str) -> str:
    if candidate_type == "DIRECTION_CHANGE" and reason_code == "REDUNDANT_DIRECTION_JITTER":
        return "ACCEPTANCE_RESIDUAL"
    if reason_code == "REDUNDANT_SHORT_PAUSE":
        return "KNOWN_UNDER_CONSOLIDATION_RESIDUAL"
    return "KNOWN_RESIDUAL_OTHER"


def build_residual_inventory(results: Sequence[EngineResult], details: Mapping[str, Any]) -> list[dict[str, Any]]:
    events = _event_map(results)
    rows = []
    for pred in sorted(details["unmatched"], key=lambda x: (x["episode_id"], x["pred_frame"], x["pred_id"])):
        event = events[pred["pred_id"]]
        anchor = details["pred_anchors"][pred["pred_id"]]
        rows.append({
            "episode_id": event.episode_id, "pred_frame": event.frame,
            "candidate_type": event.candidate_type, "final_boundary_id": event.boundary_id,
            "representative_candidate_id": event.representative_candidate_id,
            "member_candidate_ids": "|".join(event.member_candidate_ids),
            "member_candidate_types": "|".join(event.member_candidate_types),
            "member_candidate_frames": "|".join(map(str, event.member_candidate_frames)),
            "known_fp_anchor_matched": anchor["known_fp_anchor_matched"],
            "known_fp_anchor_frame": anchor["known_fp_anchor_frame"],
            "error_mode": anchor["known_fp_error_mode"], "reason_code": anchor["reason_code"],
            "residual_role": residual_role(event.candidate_type, anchor["reason_code"]),
        })
    return rows


def build_edge_trace(results: Sequence[EngineResult], trace: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    results_by_episode = {result.episode_id: result for result in results}
    rows = []
    for item in trace:
        p_incomplete = not bool(item["P12_context_complete"])
        c_fallback = bool(item["P12_context_complete"]) and not bool(item["C12_context_complete"])
        if not p_incomplete and not c_fallback:
            continue
        result = results_by_episode[str(item["episode_id"])]
        decision = result.decisions[str(item["candidate_id"])]
        event = next((event for event in result.events if item["candidate_id"] in event.member_candidate_ids), None)
        if p_incomplete:
            fallback = "P12_INCOMPLETE_FAIL_OPEN_KEEP"
        else:
            fallback = "C12_INCOMPLETE_FALLBACK_P12_ONLY"
        if event and event.active:
            final_status = "ACTIVE_FINAL_MEMBER"
        elif decision.decision == DECISION_REJECT_ACCEPTANCE:
            final_status = "REJECTED_BY_ACCEPTANCE"
        else:
            final_status = decision.decision
        rows.append({
            "episode_id": item["episode_id"], "candidate_id": item["candidate_id"],
            "frame": item["frame"], "candidate_type": item["candidate_type"],
            "P12": item["P12"], "P12_context_complete": item["P12_context_complete"],
            "C12": item["C12"], "C12_context_complete": item["C12_context_complete"],
            "fallback_behavior": fallback, "acceptance_decision": item["acceptance_decision"],
            "final_status": final_status, "target_boundary_id": decision.target_boundary_id or "",
        })
    return rows


def _final_boundary_signature(results: Sequence[EngineResult]) -> list[dict[str, Any]]:
    return [{
        "episode_id": event.episode_id, "boundary_id": event.boundary_id, "frame": event.frame,
        "candidate_type": event.candidate_type,
        "representative_candidate_id": event.representative_candidate_id,
        "member_candidate_ids": list(event.member_candidate_ids),
        "member_candidate_types": list(event.member_candidate_types),
        "member_candidate_frames": list(event.member_candidate_frames),
    } for result in results for event in result.final_events]


def _pair_signature(details: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [{
        "episode_id": pair.episode_id, "gt_id": pair.gt_id, "gt_frame": pair.gt_frame,
        "pred_id": pair.pred_id, "pred_frame": pair.pred_frame,
        "delta_frame": pair.delta_frame, "abs_error_frames": pair.abs_error_frames,
    } for pair in sorted(details["pairs"], key=lambda p: (p.episode_id, p.gt_frame, p.pred_frame, p.gt_id))]


def compare_replays(run_a: Mapping[str, Any], run_b: Mapping[str, Any]) -> dict[str, str]:
    checks = {
        "FINAL_BOUNDARY_SET_IDENTICAL": run_a["final_boundaries"] == run_b["final_boundaries"],
        "MATCHING_IDENTICAL": run_a["matching"] == run_b["matching"],
        "METRICS_IDENTICAL": run_a["metrics"] == run_b["metrics"],
        "RESIDUAL_INVENTORY_IDENTICAL": run_a["residuals"] == run_b["residuals"],
        "ACCEPTANCE_TRACE_IDENTICAL": run_a["acceptance_trace"] == run_b["acceptance_trace"],
        "EDGE_CONTEXT_COUNTS_IDENTICAL": run_a["edge_counts"] == run_b["edge_counts"],
    }
    checks["DETERMINISTIC_REPLAY_PASS"] = all(checks.values())
    return {key: "YES" if value else "NO" for key, value in checks.items()}


def _protected_paths(root: Path) -> dict[str, tuple[str, Path]]:
    return {
        "canonical_gt_snapshot": ("tree", root / SNAPSHOT_RUN),
        "human_export_seed": ("tree", root / "outputs/g1_audit_web/human_calibration_export" / EXPECTED_EXPORT_IDS[0]),
        "human_export_fresh": ("tree", root / "outputs/g1_audit_web/human_calibration_export" / EXPECTED_EXPORT_IDS[1]),
        "owner_sqlite": ("file", root / "outputs/g1_audit_web/g1_audit_web_owner.sqlite3"),
        "protocol_v1": ("file", root / "0-doc/10-design-review/Project2_G1_P3_Calibration_Protocol_FROZEN_v1_20260917.md"),
        "protocol_v1_1": ("file", root / "0-doc/10-design-review/Project2_G1_P3_Calibration_Protocol_FROZEN_v1_1_PATCH_20260918.md"),
        "protocol_v1_2": ("file", root / "0-doc/10-design-review/Project2_G1_P3_Calibration_Protocol_FROZEN_v1_2_PATCH_20260923.md"),
        "stage_a_owner_decision": ("file", root / "0-doc/10-design-review/Project2_G1_P3_Stage_A_Selection_and_Stage_B_Gate_20260924.md"),
        "stage_b_owner_decision": ("file", root / "0-doc/10-design-review/Project2_G1_P3_Stage_B_Owner_Decision_and_Stage_C_Gate_20260926.md"),
    }


def protected_fingerprints(root: Path) -> dict[str, str]:
    values = {}
    for name, (kind, path) in _protected_paths(root).items():
        if not path.exists():
            raise StageCRegressionError(f"protected artifact missing: {path}")
        values[name] = tree_fingerprint(path)["tree_fingerprint"] if kind == "tree" else sha256_file(path)
    return values


def prepare_immutable_temp(output: Path) -> Path:
    temp = output.parent / (".tmp-" + output.name)
    if output.exists() or temp.exists():
        raise StageCRegressionError("immutable output run already exists")
    temp.mkdir(parents=True, exist_ok=False)
    return temp


def _replay(signals: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    results, trace = run_window(signals, BOUNDARY_CONSOLIDATION_WINDOW)
    metrics = score_results(results, snapshot)
    details = scoring_details(results, snapshot)
    residuals = build_residual_inventory(results, details)
    edge = build_edge_trace(results, trace)
    counts = {
        "P12_context_incomplete_count": sum(not bool(x["P12_context_complete"]) for x in trace),
        "C12_context_incomplete_count": sum(bool(x["P12_context_complete"]) and not bool(x["C12_context_complete"]) for x in trace),
    }
    return {
        "results": results, "acceptance_trace": trace, "metrics": metrics, "details": details,
        "residuals": residuals, "edge": edge, "edge_counts": counts,
        "final_boundaries": _final_boundary_signature(results), "matching": _pair_signature(details),
    }


def run_stage_c(*, project_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(project_root or PROJECT2_ROOT).resolve()
    before = protected_fingerprints(root)
    snapshot = load_canonical_snapshot(root / SNAPSHOT_RUN)
    episodes = list(snapshot["manifest"]["episode_ids"])
    signals = _load_signals(root, episodes)

    run_a = _replay(signals, snapshot)
    validate_parent(run_a["metrics"])
    if not stage_c_guardrails(run_a["metrics"]):
        raise StageCRegressionError("STAGE_C_HARD_GUARDRAIL_FAIL")
    run_b = _replay(signals, snapshot)
    validate_parent(run_b["metrics"])
    determinism = compare_replays(run_a, run_b)
    if determinism["DETERMINISTIC_REPLAY_PASS"] != "YES":
        raise StageCRegressionError(f"STAGE_C_DETERMINISM_FAIL {determinism}")

    after = protected_fingerprints(root)
    protected_pass = before == after
    stale_sqlite = after["owner_sqlite"] != SQLITE_SHA256
    protected_check = {
        "before": before, "after": after, "identical_before_after": protected_pass,
        "protected_artifact_identity_pass": protected_pass,
        "PRE_EXISTING_STALE_FINGERPRINT_ASSERTION": stale_sqlite,
        "expected_legacy_owner_sqlite_sha256": SQLITE_SHA256,
        "actual_owner_sqlite_sha256": after["owner_sqlite"],
    }
    if not protected_pass:
        raise StageCRegressionError("PROTECTED_ARTIFACT_IDENTITY_FAIL")

    metrics = run_a["metrics"]
    details = run_a["details"]
    residuals = run_a["residuals"]
    expected_roles = {"ACCEPTANCE_RESIDUAL", "KNOWN_UNDER_CONSOLIDATION_RESIDUAL"}
    no_new_residual = (len(residuals) == 2 and all(r["known_fp_anchor_matched"] for r in residuals)
                       and {r["residual_role"] for r in residuals} == expected_roles)
    if not no_new_residual or metrics["FN"] != 0:
        raise StageCRegressionError("STAGE_C_RESIDUAL_OR_FN_REGRESSION")

    errors = [pair.abs_error_frames for pair in details["pairs"]]
    localization = localization_summary(errors)
    segments = [{"episode_id": r.episode_id, "duration_frames": s.duration_frames}
                for r in run_a["results"] for s in r.segments]
    fragmentation = fragmentation_diagnostics(segments)
    no_mass_fragmentation = fragmentation["1_2_frame_segment_ratio"] == 0.0
    if not no_mass_fragmentation:
        raise StageCRegressionError("STAGE_C_FRAGMENTATION_REGRESSION")

    matched_gt = {pair.gt_id for pair in details["pairs"]}
    unmatched_gt = [row for row in snapshot["gt_rows"] if row["gt_id"] not in matched_gt]
    matching_rows = run_a["matching"]
    unmatched_pred_rows = [{**pred, **details["pred_anchors"][pred["pred_id"]]}
                           for pred in details["unmatched"]]
    guardrails = {
        "Gripper_recall": metrics["Gripper_recall"],
        "Merged_cluster_recall": metrics["Merged_cluster_recall"],
        "Seed_valid_direction_recall": metrics["Seed_valid_direction_recall"],
        "Fresh_valid_direction_recall": metrics["Fresh_valid_direction_recall"],
        "FN": metrics["FN"], "NEW_UNANCHORED_FP": metrics["NEW_UNANCHORED_FP"],
        "ALL_HARD_GUARDRAILS": "PASS",
    }

    now = datetime.now().astimezone()
    run_id = "g1_p3_stage_c_" + now.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    output = root / "outputs/g1_p3_stage_c_regression" / run_id
    temp = prepare_immutable_temp(output)

    config_identity = fixed_config_identity()
    summary = {
        "run_id": run_id, "config_identity": config_identity,
        "tau_P12": TAU_P12, "tau_C12": TAU_C12,
        "boundary_consolidation_window": BOUNDARY_CONSOLIDATION_WINDOW,
        **{k: metrics[k] for k in ("TP", "FP", "FN", "Precision", "Recall", "F1",
            "Gripper_recall", "Merged_cluster_recall", "Seed_valid_direction_recall",
            "Fresh_valid_direction_recall", "NEW_UNANCHORED_FP")},
        "residual_fp_count": len(residuals),
        "fragmentation_1_2_ratio": fragmentation["1_2_frame_segment_ratio"],
        "segments_per_episode": fragmentation["segments_per_episode"],
        "localization_mean": localization["mean_frames"],
        "localization_median": localization["median_frames"],
        "localization_p90": localization["p90_frames"],
        "localization_max": localization["max_frames"],
        **run_a["edge_counts"], "deterministic_replay_pass": True,
        "protected_artifact_identity_pass": True, "all_hard_guardrails_pass": True,
        "no_new_residual_fp": True, "no_new_fn": True,
        "no_mass_1_2_frame_fragmentation": True, "evaluation_touched": False,
        "STAGE_C_RESULT": "PASS_READY_FOR_FINAL_CALIBRATION_CONFIG_OWNER_REVIEW",
        "CALIBRATION_CONFIG_FROZEN": False,
    }
    meta = {
        "run_id": run_id, "created_at": now.isoformat(), "protocol": "FROZEN_v1.2_STAGE_C_REGRESSION_ONLY",
        "config_hash": EXPECTED_CONFIG_HASH, "signal_contract_hash": EXPECTED_SIGNAL_HASH,
        "canonical_gt_snapshot_id": EXPECTED_SNAPSHOT_ID, "baseline_run_id": EXPECTED_RUN_ID,
        "config_identity": config_identity, "replay_count": 2,
        "EVALUATION_USAGE": EVALUATION_USAGE, "EVALUATION_TOUCHED": False,
        "CALIBRATION_CONFIG_FROZEN": False,
    }
    (temp / "run_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (temp / "stage_c_regression_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    _write_csv(temp / "matching_pairs.csv", list(matching_rows[0]), matching_rows)
    _write_csv(temp / "unmatched_predictions_fp.csv", list(unmatched_pred_rows[0]), unmatched_pred_rows)
    gt_fields = list(snapshot["gt_rows"][0])
    _write_csv(temp / "unmatched_gt_fn.csv", gt_fields, unmatched_gt)
    (temp / "guardrail_metrics.json").write_text(json.dumps(guardrails, indent=2) + "\n", encoding="utf-8")
    _write_csv(temp / "residual_fp_inventory.csv", RESIDUAL_FIELDS, residuals)
    _write_csv(temp / "edge_context_trace.csv", EDGE_FIELDS, run_a["edge"])
    _write_csv(temp / "candidate_acceptance_trace.csv", TRACE_FIELDS, run_a["acceptance_trace"])
    (temp / "fragmentation_metrics.json").write_text(json.dumps({**fragmentation,
        "NO_MASS_1_2_FRAME_FRAGMENTATION": True}, indent=2) + "\n", encoding="utf-8")
    (temp / "localization_metrics.json").write_text(json.dumps({**localization,
        "tolerance_frames": 3, "tolerance_seconds": 3 / SAMPLE_HZ}, indent=2) + "\n", encoding="utf-8")
    (temp / "determinism_comparison.json").write_text(json.dumps(determinism, indent=2) + "\n", encoding="utf-8")
    (temp / "protected_artifact_check.json").write_text(json.dumps(protected_check, indent=2) + "\n", encoding="utf-8")
    os.rename(temp, output)
    return {"summary": summary, "output_run": str(output), "residuals": residuals,
            "edge": run_a["edge"], "determinism": determinism,
            "protected": protected_check, "localization": localization,
            "fragmentation": fragmentation}
