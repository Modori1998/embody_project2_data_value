"""Run Frozen Baseline Scoring. Does not execute Stage A0 or parameter search."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.baseline_scoring import score_baseline
from project2_g1.paths import PROJECT2_ROOT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="G1 12-Episode Baseline Scoring")
    parser.add_argument("--project-root", type=Path, default=PROJECT2_ROOT)
    args = parser.parse_args(argv)
    result = score_baseline(project_root=args.project_root.resolve())
    print(json.dumps({
        "score_id": result["score_id"],
        "score_root": result["score_root"],
        "TP": result["metrics"]["TP"],
        "FP": result["metrics"]["FP"],
        "FN": result["metrics"]["FN"],
        "Precision": result["metrics"]["Precision"],
        "Recall": result["metrics"]["Recall"],
        "F1": result["metrics"]["F1"],
        "EXACT_TP": result["metrics"]["EXACT_TP"],
        "NEAR_TP": result["metrics"]["NEAR_TP"],
        "FN_BASELINE": result["metrics"]["FN_BASELINE"],
        "NEW_UNANCHORED_FP_COUNT": result["metrics"]["NEW_UNANCHORED_FP_COUNT"],
        "validator": result["validator"],
        "BASELINE_SCORING": result["meta"]["BASELINE_SCORING"],
        "NEXT_GATE": result["meta"]["NEXT_GATE"],
        "immutability": {key: value for key, value in result["immutability"].items() if key != "fingerprints"},
        "guardrails": {
            "CALIBRATION_GRIPPER_RECALL": result["guardrails"]["CALIBRATION_GRIPPER_RECALL"],
            "CALIBRATION_MERGED_CLUSTER_RECALL": result["guardrails"]["CALIBRATION_MERGED_CLUSTER_RECALL"],
            "SEED_VALID_DIRECTION_RECALL": result["guardrails"]["SEED_VALID_DIRECTION_RECALL"],
            "FRESH_VALID_DIRECTION_RECALL_BASELINE": result["guardrails"]["FRESH_VALID_DIRECTION_RECALL_BASELINE"],
        },
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
