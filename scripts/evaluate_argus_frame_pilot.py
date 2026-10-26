"""Summarize actual engineering Pilot only; never invent formal 34-cell results."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project2_g3.g3d_paired import score_pairs


def read_jsonl(path):
    return [json.loads(line) for line in path.open(encoding="utf-8")]


def costs(rows):
    times = sorted(r["wall_seconds"] for r in rows)
    return {"attempts": len(rows), "wall_seconds": sum(times), "median_s": statistics.median(times) if times else None,
            "p95_s_nearest_rank": times[math.ceil(.95 * len(times)) - 1] if times else None,
            "prompt_tokens": sum(r["usage"].get("prompt_tokens", 0) for r in rows),
            "completion_tokens": sum(r["usage"].get("completion_tokens", 0) for r in rows),
            "sampled_peak_vram_mib": max((r["sampled_peak_vram_mib"] for r in rows if r["sampled_peak_vram_mib"] is not None), default=None),
            "newly_encoded_visual_tokens": sum(r.get("newly_encoded_visual_tokens", sum(r["visual_embedding_tokens_per_image"])) for r in rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--human-reference", type=Path, required=True)
    parser.add_argument("--prior-incident-run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    expected_human = "ecc716860eaf7617e00c1b23812fb1394a2719851346580a24e057a7e1ac938c"
    if hashlib.sha256(args.human_reference.read_bytes()).hexdigest() != expected_human:
        raise ValueError("STOP_REFERENCE_DRIFT")
    refs = {r["segment_id"]: r for r in csv.DictReader(args.human_reference.open(encoding="utf-8-sig"))}
    rows = read_jsonl(args.run_dir / "pilot/responses.jsonl")
    terminal = json.loads((args.run_dir / "pilot/terminal.json").read_text(encoding="utf-8"))
    gate = json.loads((args.run_dir / "pilot/summary.json").read_text(encoding="utf-8"))
    expected_cells = {(sid, arm) for sid in ("demo_2-S0003", "demo_169-S0002") for arm in (3, 6, 12)}
    if len(terminal) != 6 or {(r["segment_id"], r["arm"]) for r in terminal} != expected_cells:
        raise ValueError("STOP_PILOT_INCOMPLETE_OR_COHORT_DRIFT")
    if gate["gate_pass"] or all(r["valid"] for r in terminal):
        raise ValueError("STOP_USE_PASSED_PILOT_EVALUATOR")
    first = [r for r in rows if r["attempt"] == 1]
    identity = json.loads((args.run_dir / "run_identity.json").read_text(encoding="utf-8"))
    result = {"decision": "INCONCLUSIVE_ENGINEERING", "pilot_gate_pass": False, "formal_status": "NOT_RUN",
              "formal_planned_cells": 34, "formal_executed_cells": 0, "identity": identity, "per_arm": {}, "per_segment": []}
    if (args.run_dir / "full").exists():
        raise ValueError("STOP_FORMAL_EXISTS_USE_FORMAL_EVALUATOR")
    common_ids = set.intersection(*[{r["segment_id"] for r in terminal if r["arm"] == arm and r["valid"]} for arm in (3, 6, 12)])
    def score(selected):
        pairs = []
        for r in selected:
            ref = refs[r["segment_id"]]
            pairs.append({"segment_id": r["segment_id"], "human": {"motion_phase": ref["phase_ref"],
                "events": list(filter(None, ref["event_types_ref"].split(";")))}, "A": r["parsed"], "B": r["parsed"]})
        return score_pairs(pairs)["A"]
    def legal(selected):
        return {"n": len(selected), "parse_ok": sum(r["qc"]["parse_ok"] for r in selected),
                "schema_ok": sum(r["qc"]["schema_ok"] for r in selected), "evidence_ok": sum(r["qc"]["frame_evidence_ok"] for r in selected),
                "schema_valid_denominator": sum(r["qc"]["schema_ok"] for r in selected),
                "evidence_ok_given_schema": sum(r["qc"]["schema_ok"] and r["qc"]["frame_evidence_ok"] for r in selected)}
    for arm in (3, 6, 12):
        selected = [r for r in terminal if r["arm"] == arm]
        valid = [r for r in selected if r["valid"]]
        own = score(valid)
        counts = own["by_type"]["object_motion"]
        tp, fp, fn = (counts[k] for k in ("tp", "fp", "fn"))
        own["object_motion"] = {**counts, "precision": tp/(tp+fp) if tp+fp else 0,
            "recall": tp/(tp+fn) if tp+fn else 0, "f1": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,
            "positive_truth_n": tp+fn, "caution": "own-valid cohort only; zero-positive denominator is not a recall estimate"}
        result["per_arm"][str(arm)] = {"planned": 2, "final_valid": len(valid), "final_failed": 2-len(valid),
            "first_legality": legal([r for r in first if r["arm"] == arm]), "final_legality": legal(selected),
            "all_attempt_legality": legal([r for r in rows if r["arm"] == arm]), "own_valid_scores": own,
            "common_valid_ids": sorted(common_ids), "common_valid_scores": score([r for r in valid if r["segment_id"] in common_ids]),
            "end_to_end_exact": own["exact_match"], "end_to_end_exact_denominator": 2,
            "all_attempt_cost": costs([r for r in rows if r["arm"] == arm]), "first_attempt_cost": costs([r for r in first if r["arm"] == arm])}
    for r in terminal:
        ref = refs[r["segment_id"]]
        result["per_segment"].append({k:r[k] for k in ("segment_id", "arm", "frame_ids", "valid", "parsed", "qc", "visual_embedding_tokens", "visual_embedding_tokens_per_image", "sampled_peak_vram_mib", "wall_seconds", "attempt")}
        )
        result["per_segment"][-1]["human"] = {"phase": ref["phase_ref"], "events": list(filter(None,ref["event_types_ref"].split(";")))}
    result["pilot_first_legality"], result["pilot_final_legality"] = legal(first), legal(terminal)
    result["pilot_all_attempt_legality"] = legal(rows)
    result["pilot_cost"] = costs(rows)
    all_cost_rows = list(rows)
    if args.prior_incident_run:
        prior = read_jsonl(args.prior_incident_run / "pilot/responses.jsonl")
        result["prior_incident_cost"] = costs(prior)
        all_cost_rows += prior
    result["all_runs_cost_including_incident"] = costs(all_cost_rows)
    samples = read_jsonl(args.run_dir / "gpu_samples.jsonl")
    gaps = [b["unix_s"]-a["unix_s"] for a,b in zip(samples,samples[1:])]
    result["telemetry"] = {"samples": len(samples), "median_interval_s": statistics.median(gaps), "max_interval_s": max(gaps),
        "baseline_sample_mib": samples[0]["used_vram_mib"], "whole_gpu_includes_desktop": True}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(result,out,ensure_ascii=False,indent=2)
    print(json.dumps({k:result[k] for k in ("decision","pilot_first_legality","pilot_final_legality","pilot_cost","all_runs_cost_including_incident","telemetry")},ensure_ascii=False))


if __name__ == "__main__":
    main()
