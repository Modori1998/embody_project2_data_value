"""Score a completed, paired G3G Development run against frozen G3C reference.

Writes private local evaluation.json only; the public report is reviewed separately.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project2_g3.g3d_paired import score_pairs
from project2_g3.g3d2r_reliability import truth

FROZEN = ROOT / "0-doc/10-design-review/evidence/P2_G3_Taxonomy_v0_2_20261013"
ARMS = ("4B", "8B")
TASKS = ("A", "B")
QUESTIONS = ("can_visible", "can_position_change", "can_moves_with_gripper", "gripper_open_close_change")


def development_gates(a: dict, b: dict, engineering: dict) -> dict[str, bool]:
    """Apply only the six criteria frozen in G3G_Plan.md."""
    return {
        "event_micro_f1_gain_ge_0_10": b["event_type_micro_f1"] - a["event_type_micro_f1"] >= 0.10 - 1e-12,
        "object_motion_tp_ge_2": b["by_type"]["object_motion"]["tp"] >= 2,
        "object_motion_fp_le_1": b["by_type"]["object_motion"]["fp"] <= 1,
        "event_exact_gain_ge_1": b["exact_match"] >= a["exact_match"] + 1,
        "phase_correct_drop_le_1": b["phase_correct"] >= a["phase_correct"] - 1,
        "engineering_valid": all(engineering[arm]["final_valid"] == 24 for arm in ARMS),
    }


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def evaluate(run: Path, human_path: Path) -> dict:
    frozen = json.loads((FROZEN / "run_manifest.json").read_text(encoding="utf-8"))
    ids = tuple(frozen["cohorts"]["microset"]["segments"])
    if len(ids) != len(set(ids)) != 12:
        raise ValueError("STOP_FROZEN_COHORT_DRIFT")
    sample = {r["segment_id"]: r for r in csv.DictReader((FROZEN / "sample_manifest.csv").open(encoding="utf-8-sig"))}
    human_rows = {r["segment_id"]: r for r in csv.DictReader(human_path.open(encoding="utf-8-sig"))}
    for sid in ids:
        if any(sample[sid][k] != human_rows[sid][k] for k in
               ("episode_id", "start_frame", "end_frame", "target_keyframes", "frame_png_sha256s")):
            raise ValueError("STOP_HUMAN_IDENTITY_DRIFT:" + sid)
    inputs = {arm: read_jsonl(run / f"{arm}_inputs.jsonl") for arm in ARMS}
    responses = {arm: read_jsonl(run / f"{arm}_responses.jsonl") for arm in ARMS}
    manifests = {arm: json.loads((run / f"{arm}_run_manifest.json").read_text(encoding="utf-8")) for arm in ARMS}
    planned = [(sid, task) for sid in ids for task in TASKS]
    for arm in ARMS:
        if manifests[arm].get("run_scope") != "G3G_DEVELOPMENT_12_SEGMENTS" or manifests[arm].get("frozen_cohort") != list(ids):
            raise ValueError("STOP_RUN_SCOPE_DRIFT:" + arm)
        if [(r["segment_id"], r["task"]) for r in inputs[arm]] != planned:
            raise ValueError("STOP_INPUT_ORDER_DRIFT:" + arm)
        grouped = {}
        for r in responses[arm]:
            grouped.setdefault((r["segment_id"], r["task"]), []).append(r)
        if set(grouped) != set(planned):
            raise ValueError("STOP_MISSING_OR_EXTRA_CELLS:" + arm)
        for key in planned:
            attempts = grouped[key]
            if len(attempts) > 2 or [r["attempt"] for r in attempts] != list(range(1, len(attempts) + 1)):
                raise ValueError("STOP_ATTEMPT_PROTOCOL:" + str(key))
            if len(attempts) > 1 and attempts[0]["valid"]:
                raise ValueError("STOP_RETRY_AFTER_VALID:" + str(key))
    for left, right in zip(inputs["4B"], inputs["8B"]):
        if any(left[k] != right[k] for k in ("segment_id", "task", "content_sha256", "prompt_sha256", "png_sha256", "frame_indices")):
            raise ValueError("STOP_PAIRED_INPUT_DRIFT")
        if left["request"]["response_format"] != right["request"]["response_format"]:
            raise ValueError("STOP_PAIRED_PROTOCOL_DRIFT")
    finals = {}
    engineering = {}
    for arm in ARMS:
        group = {}
        for r in responses[arm]:
            group.setdefault((r["segment_id"], r["task"]), []).append(r)
        finals[arm] = {key: next((r for r in attempts if r["valid"]), None) for key, attempts in group.items()}
        rr = responses[arm]
        engineering[arm] = {
            "planned_cells": 24, "actual_attempts": len(rr),
            "first_valid": sum(attempts[0]["valid"] for attempts in group.values()),
            "final_valid": sum(r is not None for r in finals[arm].values()),
            "retry_attempts": sum(len(attempts) - 1 for attempts in group.values()),
            "failed_cells": [list(key) for key, r in finals[arm].items() if r is None],
            "prompt_tokens": sum((r.get("usage") or {}).get("prompt_tokens", 0) for r in rr),
            "completion_tokens": sum((r.get("usage") or {}).get("completion_tokens", 0) for r in rr),
            "wall_seconds": sum(r["wall_seconds"] for r in rr),
            "peak_vram_mib": max(r["peak_used_vram_mib"] for r in rr),
            "minimum_free_ram_mib": min(r["min_free_ram_mib"] for r in rr),
            "phase_event_qc": dict(Counter(r["phase_event_qc"]["review_status"] for r in rr if r["task"] == "B")),
        }
    complete = all(engineering[arm]["final_valid"] == 24 for arm in ARMS)
    result = {"human_reference_sha256": hashlib.sha256(human_path.read_bytes()).hexdigest(),
              "segments": list(ids), "engineering": engineering, "complete": complete}
    if not complete:
        result["decision"] = "INCOMPLETE_UNSCORABLE"
        return result
    rows = [{"segment_id": sid, "human": truth(human_rows[sid]),
             "A": finals["4B"][(sid, "B")]["parsed"], "B": finals["8B"][(sid, "B")]["parsed"]} for sid in ids]
    scored = score_pairs(rows)
    result["semantic_metrics"] = {"4B": scored["A"], "8B": scored["B"]}
    result["per_segment"] = [{"segment_id": sid, "human": truth(human_rows[sid]),
                              "4B": {task: finals["4B"][(sid, task)]["parsed"] for task in TASKS},
                              "8B": {task: finals["8B"][(sid, task)]["parsed"] for task in TASKS}}
                             for sid in ids]
    result["task_a_counts"] = {arm: {key: dict(Counter(finals[arm][(sid, "A")]["parsed"][key]["answer"] for sid in ids))
                                     for key in QUESTIONS} for arm in ARMS}
    a, b = scored["A"], scored["B"]
    checks = development_gates(a, b, engineering)
    result["gates"] = checks
    result["decision"] = "8B_DEVELOPMENT_CANDIDATE" if all(checks.values()) else "8B_NO_CONFIRMED_GAIN"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--human-reference", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.run_dir, args.human_reference)
    path = args.run_dir / "evaluation.json"
    if path.exists():
        raise FileExistsError("STOP_EVALUATION_EXISTS")
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(result["decision"], result["gates"] if result["complete"] else result["engineering"])


if __name__ == "__main__":
    main()
