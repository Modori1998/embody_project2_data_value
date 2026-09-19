"""Run Stage A0 Direction Candidate Discriminability Audit. No parameter search."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.paths import PROJECT2_ROOT
from project2_g1.stage_a0_analysis import run_stage_a0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="G1 Stage A0 Direction Discriminability Audit")
    parser.add_argument("--project-root", type=Path, default=PROJECT2_ROOT)
    args = parser.parse_args(argv)
    result = run_stage_a0(project_root=args.project_root.resolve())
    decision = result["decision"]
    cohorts = result["cohorts"]
    print(json.dumps({
        "CALIBRATION_PROTOCOL_EFFECTIVE_VERSION": "FROZEN_v1.1",
        "STAGE": "A0_DIRECTION_CANDIDATE_DISCRIMINABILITY_AUDIT",
        "PARAMETER_SEARCH_EXECUTED": False,
        "analysis_id": result["analysis_id"],
        "analysis_root": result["analysis_root"],
        "cohorts": cohorts,
        "THRESHOLD_ONLY_RISK": decision["THRESHOLD_ONLY_RISK"],
        "PERSISTENCE_ONLY_RISK": decision["PERSISTENCE_ONLY_RISK"],
        "classification": decision["classification"],
        "STAGE_A_THRESHOLD_PERSISTENCE_SEARCH": decision["STAGE_A_THRESHOLD_PERSISTENCE_SEARCH"],
        "DESIGN_CHANGE_CANDIDATE": decision["DESIGN_CHANGE_CANDIDATE"],
        "immutability": {key: value for key, value in result["immutability"].items() if key != "fingerprints"},
        "DETECTOR_MODIFIED": False,
        "CONFIG_GENERATED": False,
        "STAGE_A_EXECUTED": False,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
