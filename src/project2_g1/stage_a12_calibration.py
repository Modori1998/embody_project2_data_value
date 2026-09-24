"""Frozen G1-P3 Stage A1/A2 calibration (Protocol v1.2).

Only FormalSignals feed candidate acceptance.  Diagnostic-set artifacts are
named below solely so threshold construction can explicitly reject them.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import statistics
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .baseline_scoring import (
    EXPECTED_CONFIG_HASH, EXPECTED_RUN_ID, EXPECTED_SIGNAL_HASH,
    EXPECTED_SNAPSHOT_ID, fragmentation_diagnostics, load_canonical_snapshot,
    match_known_fp_anchors,
)
from .boundary_config import load_g1_p2_config
from .boundary_engine import (
    CANDIDATE_DIRECTION, DECISION_KEEP, DECISION_REJECT_ACCEPTANCE,
    BoundaryCandidate, BoundaryDecision, run_boundary_engine,
)
from .boundary_matching import match_by_episode
from .config import load_g1_p1_config
from .paths import CONFIG_PATH, DATASET_RAW_HDF5, G1_P2_CONFIG_PATH, PROJECT2_ROOT
from .signals import FormalSignals, compute_formal_signals
from .source import build_can_mh_adapter, load_formal_episode

DIAGNOSTIC_THRESHOLD_INPUTS = frozenset({
    "02_selection_internal.csv", "05_review_history.csv", "05_owner_adjudication_result.md"
})
BASELINE_RUN = "outputs/g1_audit_runs/" + EXPECTED_RUN_ID
SNAPSHOT_RUN = "outputs/g1_p3_canonical_gt/" + EXPECTED_SNAPSHOT_ID
TRACE_FIELDS = (
    "episode_id", "candidate_id", "frame", "candidate_type", "direction_evidence",
    "run_length", "P12", "P12_context_complete", "C12", "C12_context_complete",
    "acceptance_variant", "tau_P12", "tau_C12", "acceptance_decision",
    "acceptance_reason", "config_hash", "signal_contract_hash",
)


class StageA12Error(ValueError): pass


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _write_csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def straightness(signals: FormalSignals, start: int, end: int) -> float | None:
    if start < 0 or end >= signals.n_frames or end < start:
        return None
    xyz = np.column_stack((signals.eef_x, signals.eef_y, signals.eef_z))[start:end + 1]
    if len(xyz) < 2: return None
    path = float(np.linalg.norm(np.diff(xyz, axis=0), axis=1).sum())
    if path < 1e-9: return None
    return float(np.linalg.norm(xyz[-1] - xyz[0]) / path)


def derive_context(signals: FormalSignals, frame: int) -> dict[str, Any]:
    p_complete = frame + 12 < signals.n_frames
    p12 = float(statistics.median(map(float, signals.translation_speed[frame + 4:frame + 13]))) if p_complete else None
    c_complete = frame - 12 >= 0 and frame + 11 < signals.n_frames
    left = straightness(signals, frame - 12, frame - 1) if c_complete else None
    right = straightness(signals, frame, frame + 11) if c_complete else None
    if left is None or right is None: c_complete, c12 = False, None
    else: c12 = min(left, right)
    return {"P12": p12, "P12_context_complete": p_complete,
            "C12": c12, "C12_context_complete": c_complete}


def breakpoint_candidates(values: Sequence[float], *, sources: Sequence[str] = ()) -> list[dict[str, Any]]:
    if any(Path(p).name in DIAGNOSTIC_THRESHOLD_INPUTS for p in sources):
        raise StageA12Error("DIAGNOSTIC_SET_THRESHOLD_USAGE = FORBIDDEN")
    unique = sorted(set(float(v) for v in values if math.isfinite(float(v))))
    return [{"threshold": (a+b)/2.0, "lower": a, "upper": b} for a, b in zip(unique, unique[1:])]


def acceptance_callback(variant: str, tau_p12: float | None, tau_c12: float | None,
                        trace: list[dict[str, Any]]):
    def apply(candidates: list[BoundaryCandidate], decisions: dict[str, BoundaryDecision], signals: FormalSignals) -> None:
        for cand in candidates:
            if cand.candidate_type != CANDIDATE_DIRECTION or decisions[cand.candidate_id].decision != DECISION_KEEP:
                continue
            ctx = derive_context(signals, cand.frame); decision = "KEEP_P12_PASS"; reason = "P12 >= tau_P12"
            reject = False
            if tau_p12 is None: decision, reason = "KEEP_NO_GATE", "baseline no acceptance gate"
            elif not ctx["P12_context_complete"]: decision, reason = "KEEP_EDGE_CONTEXT_INCOMPLETE", "P12 context incomplete; fail-open"
            elif ctx["P12"] < tau_p12: decision, reason, reject = "REJECT_P12_INSUFFICIENT", "P12 < tau_P12", True
            elif variant == "P12_C12" and tau_c12 is not None:
                if not ctx["C12_context_complete"]: decision, reason = "KEEP_C12_CONTEXT_INCOMPLETE", "C12 incomplete; fallback P12-only"
                elif ctx["C12"] < tau_c12: decision, reason, reject = "REJECT_C12_TAIL", "C12 < tau_C12", True
                else: decision, reason = "KEEP_C12_PASS", "P12 and C12 pass"
            if reject:
                decisions[cand.candidate_id] = BoundaryDecision(cand.candidate_id, DECISION_REJECT_ACCEPTANCE, reason)
            trace.append({
                "episode_id": cand.episode_id, "candidate_id": cand.candidate_id, "frame": cand.frame,
                "candidate_type": cand.candidate_type, "direction_evidence": cand.evidence_value,
                "run_length": cand.extra.get("run_length", ""), **ctx, "acceptance_variant": variant,
                "tau_P12": "" if tau_p12 is None else tau_p12, "tau_C12": "" if tau_c12 is None else tau_c12,
                "acceptance_decision": decision, "acceptance_reason": reason,
                "config_hash": EXPECTED_CONFIG_HASH, "signal_contract_hash": EXPECTED_SIGNAL_HASH,
            })
    return apply


def _ratio(n: int, d: int) -> float: return n / d if d else 0.0


def score_results(results: Sequence[Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    gt_rows = snapshot["gt_rows"]; gt_by_id = {r["gt_id"]: r for r in gt_rows}
    preds=[]; segments=[]
    for result in results:
        for e in result.final_events:
            pid=f"{e.episode_id}:{e.boundary_id}"
            preds.append({"episode_id":e.episode_id,"pred_id":pid,"pred_boundary_id":e.boundary_id,
                          "pred_frame":e.frame,"candidate_type":e.candidate_type,
                          "representative_candidate_id":e.representative_candidate_id,
                          "member_candidate_types":"|".join(e.member_candidate_types),
                          "member_candidate_frames":"|".join(map(str,e.member_candidate_frames))})
        segments.extend({"episode_id":result.episode_id,"duration_frames":s.duration_frames} for s in result.segments)
    gt_points=[{"episode_id":r["episode_id"],"gt_id":r["gt_id"],"gt_frame":int(r["gt_frame"])} for r in gt_rows]
    matching=match_by_episode(gt_points,preds); matched_gt=set(); matched_pred=set(); errors=[]
    for m in matching.values():
        for p in m.pairs: matched_gt.add(p.gt_id); matched_pred.add(p.pred_id); errors.append(p.abs_error_frames)
    unmatched=[p for p in preds if p["pred_id"] not in matched_pred]
    anchors,pred_anchor=match_known_fp_anchors(unmatched,snapshot["fp_rows"])
    tp=len(matched_gt); fp=len(unmatched); fn=len(gt_rows)-tp; precision=_ratio(tp,tp+fp); recall=_ratio(tp,tp+fn)
    modes=Counter((a["error_mode"],a["status"]) for a in anchors.values())
    direction_anchor_keys={(str(r["episode_id"]),int(r["anchor_frame"])) for r in snapshot["fp_rows"] if r["candidate_type"]==CANDIDATE_DIRECTION}
    package_direction_remaining=Counter(
        a["source_package"] for a in anchors.values()
        if a["status"]=="REMAINING" and (a["episode_id"],a["anchor_frame"]) in direction_anchor_keys
    )
    def rec(cls,pkg=None):
        cohort=[r for r in gt_rows if r["protected_class"]==cls and (pkg is None or r["source_package"]==pkg)]
        return _ratio(sum(r["gt_id"] in matched_gt for r in cohort),len(cohort))
    frag=fragmentation_diagnostics(segments)
    return {"TP":tp,"FP":fp,"FN":fn,"Precision":precision,"Recall":recall,"F1":_ratio(2*precision*recall,precision+recall),
            "Direction_FP_remaining":sum(1 for p in unmatched if p["candidate_type"]==CANDIDATE_DIRECTION),
            "Seed_Direction_FP_remaining":package_direction_remaining["SEED"],
            "Fresh_Direction_FP_remaining":package_direction_remaining["FRESH"],
            "MODE_01_remaining":modes[("MODE_01","REMAINING")],"MODE_02_remaining":modes[("MODE_02","REMAINING")],
            "MODE_03_remaining":modes[("MODE_03","REMAINING")],"UNASSIGNED_remaining":modes[("UNASSIGNED","REMAINING")],
            "NEW_UNANCHORED_FP":sum(pred_anchor[p["pred_id"]]["is_new_unanchored_fp"] for p in unmatched),
            "Gripper_recall":rec("GRIPPER_PRIMARY"),"Merged_cluster_recall":rec("MERGED_GRIPPER_CLUSTER"),
            "Seed_valid_direction_recall":rec("VALID_DIRECTION_PRIMARY","SEED"),
            "Fresh_valid_direction_recall":rec("VALID_DIRECTION_PRIMARY","FRESH"),
            "Localization_mean":float(np.mean(errors)) if errors else None,
            "Localization_median":float(np.median(errors)) if errors else None,
            "Localization_p90":float(np.percentile(errors,90,method="inverted_cdf")) if errors else None,
            "Localization_max":max(errors) if errors else None,
            "fragmentation_1_2_ratio":frag["1_2_frame_segment_ratio"],"segments_per_episode":frag["segments_per_episode"]}


def _load_signals(root: Path, episodes: Sequence[str]) -> dict[str, FormalSignals]:
    p1=load_g1_p1_config(root/CONFIG_PATH.relative_to(PROJECT2_ROOT)); adapter=build_can_mh_adapter(p1)
    try: return {ep:compute_formal_signals(load_formal_episode(adapter,ep),p1) for ep in episodes}
    finally:
        close=getattr(adapter,"close",None)
        if close: close()


def _run(signals: Mapping[str,FormalSignals], variant: str, p: float|None, c: float|None):
    config=load_g1_p2_config(); trace=[]
    cb=None if variant=="BASELINE" else acceptance_callback(variant,p,c,trace)
    results=[run_boundary_engine(signals[ep],config,cb) for ep in sorted(signals)]
    return results,trace


def _guardrail(row: Mapping[str,Any], baseline: Mapping[str,Any]) -> bool:
    return row["Gripper_recall"]==1.0 and row["Merged_cluster_recall"]==1.0 and row["Seed_valid_direction_recall"]==1.0 and row["Fresh_valid_direction_recall"]>=baseline["Fresh_valid_direction_recall"] and row["FN"]<=baseline["FN"]


def run_stage_a12(*, project_root: str|Path|None=None) -> dict[str,Any]:
    root=Path(project_root or PROJECT2_ROOT).resolve(); snap=load_canonical_snapshot(root/SNAPSHOT_RUN)
    meta=json.loads((root/BASELINE_RUN/"run_meta.json").read_text(encoding="utf-8"))
    if meta["config_hash"]!=EXPECTED_CONFIG_HASH or meta["signal_contract_hash"]!=EXPECTED_SIGNAL_HASH: raise StageA12Error("baseline identity mismatch")
    episodes=list(snap["manifest"]["episode_ids"]); signals=_load_signals(root,episodes)
    base_results,_=_run(signals,"BASELINE",None,None); baseline=score_results(base_results,snap)
    expected=(56,10,0,0.8484848484848485,1.0,0.9180327868852458)
    actual=(baseline["TP"],baseline["FP"],baseline["FN"],baseline["Precision"],baseline["Recall"],baseline["F1"])
    if actual!=expected or not _guardrail(baseline,baseline) or baseline["NEW_UNANCHORED_FP"]!=0: raise StageA12Error(f"STOP_BASELINE_REPLAY_MISMATCH {actual}")
    # Eligible cohort: baseline independent Direction finals only.
    context=[]
    for result in base_results:
        by_id={c.candidate_id:c for c in result.candidates}
        for e in result.final_events:
            if e.candidate_type==CANDIDATE_DIRECTION and set(e.member_candidate_types)=={CANDIDATE_DIRECTION}:
                cand=by_id[e.representative_candidate_id]; context.append({"episode_id":e.episode_id,"candidate_id":cand.candidate_id,"frame":cand.frame,"direction_evidence":cand.evidence_value,"run_length":cand.extra.get("run_length",""),**derive_context(signals[e.episode_id],cand.frame)})
    pbreak=breakpoint_candidates([r["P12"] for r in context if r["P12_context_complete"]])
    a1=[]; all_trace=[]
    for i,b in enumerate(pbreak,1):
        cid=f"A1-{i:03d}"; results,tr=_run(signals,"P12_ONLY",b["threshold"],None); all_trace+=tr
        row={"candidate_id":cid,"parent_candidate_id":"BASELINE","variant":"P12_ONLY","tau_P12":b["threshold"],"tau_C12":"","breakpoint_lower":b["lower"],"breakpoint_upper":b["upper"],**score_results(results,snap)}
        row["P12_edge_incomplete_count"]=sum(not x["P12_context_complete"] for x in tr); row["C12_edge_incomplete_count"]=0
        row["ALL_HARD_GUARDRAILS"]="PASS" if _guardrail(row,baseline) else "FAIL"; row["selection_status"]="A1_SURVIVOR" if row["ALL_HARD_GUARDRAILS"]=="PASS" else "HARD_GUARDRAIL_FAIL"; row["C12_INCREMENTAL_PROMOTION_PASS"]=""; a1.append(row)
    survivors=[r for r in a1 if r["ALL_HARD_GUARDRAILS"]=="PASS"]
    a2=[]
    for parent in survivors:
        cbreak=breakpoint_candidates([r["C12"] for r in context if r["C12_context_complete"]])
        for j,b in enumerate(cbreak,1):
            cid=f"{parent['candidate_id']}-C{j:03d}"; results,tr=_run(signals,"P12_C12",parent["tau_P12"],b["threshold"]); all_trace+=tr
            row={"candidate_id":cid,"parent_candidate_id":parent["candidate_id"],"variant":"P12_C12","tau_P12":parent["tau_P12"],"tau_C12":b["threshold"],"breakpoint_lower":b["lower"],"breakpoint_upper":b["upper"],**score_results(results,snap)}
            row["P12_edge_incomplete_count"]=sum(not x["P12_context_complete"] for x in tr); row["C12_edge_incomplete_count"]=sum(x["P12_context_complete"] and not x["C12_context_complete"] for x in tr)
            safe=_guardrail(row,baseline); incremental=safe and row["FN"]<=parent["FN"] and row["Direction_FP_remaining"]<parent["Direction_FP_remaining"] and row["Fresh_Direction_FP_remaining"]<parent["Fresh_Direction_FP_remaining"] and row["Fresh_valid_direction_recall"]>=parent["Fresh_valid_direction_recall"]
            row["ALL_HARD_GUARDRAILS"]="PASS" if safe else "FAIL"; row["C12_INCREMENTAL_PROMOTION_PASS"]="YES" if incremental else "NO"
            row["selection_status"]="A2_PROMOTABLE_CANDIDATE" if incremental else ("A2_NO_INCREMENTAL_VALUE" if safe else "HARD_GUARDRAIL_FAIL"); a2.append(row)
    created=datetime.now().astimezone().isoformat(); run_id="g1_p3_stage_a12_"+datetime.now().strftime("%Y%m%d_%H%M%S_")+uuid.uuid4().hex[:8]
    out=root/"outputs/g1_p3_stage_a12_calibration"/run_id; tmp=out.parent/(".tmp-"+run_id); tmp.mkdir(parents=True,exist_ok=False)
    comparison=[{"candidate_id":"BASELINE","parent_candidate_id":"","variant":"BASELINE","tau_P12":"","tau_C12":"",**baseline,"P12_edge_incomplete_count":0,"C12_edge_incomplete_count":0,"ALL_HARD_GUARDRAILS":"PASS","C12_INCREMENTAL_PROMOTION_PASS":"","selection_status":"BASELINE"}]+[r for r in a1+a2 if r["ALL_HARD_GUARDRAILS"]=="PASS"]
    fields=list(comparison[0])
    for row in comparison:
        for key in row:
            if key not in fields:
                fields.append(key)
    baseline_a1={"candidate_id":"BASELINE","parent_candidate_id":"","variant":"NO_GATE","tau_P12":"","tau_C12":"","breakpoint_lower":"","breakpoint_upper":"",**baseline,"P12_edge_incomplete_count":0,"C12_edge_incomplete_count":0,"ALL_HARD_GUARDRAILS":"PASS","C12_INCREMENTAL_PROMOTION_PASS":"","selection_status":"BASELINE"}
    _write_csv(tmp/"direction_candidate_context.csv",list(context[0]),context); _write_csv(tmp/"stage_a1_candidates.csv",list(a1[0]),[baseline_a1]+a1)
    _write_csv(tmp/"stage_a2_candidates.csv",list(a2[0]) if a2 else fields,a2); _write_csv(tmp/"config_comparison.csv",fields,comparison); _write_csv(tmp/"candidate_acceptance_trace.csv",TRACE_FIELDS,all_trace)
    summary={"run_id":run_id,"created_at":created,"baseline":baseline,"calibration_episodes":12,"canonical_gt_count":len(snap["gt_rows"]),"direction_cohort_count":len(context),"stage_a1_breakpoint_count":len(pbreak),"stage_a1_config_count":len(a1)+1,"stage_a1_guardrail_safe_count":len(survivors),"stage_a2_config_count":len(a2),"stage_a2_guardrail_safe_count":sum(r["ALL_HARD_GUARDRAILS"]=="PASS" for r in a2),"stage_a2_promotable_count":sum(r["C12_INCREMENTAL_PROMOTION_PASS"]=="YES" for r in a2),"diagnostic_set_used_for_threshold_selection":False,"human_label_added":False,"canonical_gt_modified":False,"final_config_frozen":False,"stage_b_executed":False,"evaluation_touched":False}
    (tmp/"stage_a12_summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8"); (tmp/"run_meta.json").write_text(json.dumps({"run_id":run_id,"created_at":created,"protocol":"FROZEN_v1.2","config_hash":EXPECTED_CONFIG_HASH,"signal_contract_hash":EXPECTED_SIGNAL_HASH,"canonical_gt_snapshot_id":EXPECTED_SNAPSHOT_ID,"baseline_run_id":EXPECTED_RUN_ID,"DIAGNOSTIC_SET_THRESHOLD_USAGE":"FORBIDDEN","CALIBRATION_CONFIG_FROZEN":False,"STAGE_B_EXECUTED":False,"EVALUATION_TOUCHED":False},indent=2)+"\n",encoding="utf-8")
    os.rename(tmp,out); return {"summary":summary,"output_run":str(out),"a1":a1,"a2":a2,"comparison":comparison}
