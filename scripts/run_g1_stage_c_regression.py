"""Run G1-P3 Stage C regression-only verification."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project2_g1.stage_c_regression import run_stage_c


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    result = run_stage_c(project_root=args.project_root)
    print(json.dumps({**result["summary"], "residuals": result["residuals"],
                      "determinism": result["determinism"],
                      "output_run": result["output_run"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
