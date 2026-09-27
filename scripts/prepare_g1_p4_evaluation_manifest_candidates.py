"""Prepare disjoint G1-P4 evaluation-manifest candidates without evaluation."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project2_g1.evaluation_manifest_preparation import run_manifest_preparation


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    result = run_manifest_preparation(project_root=args.project_root)
    print(json.dumps({**result["summary"],
                      "option_episode_ids": {name: [r["episode_id"] for r in rows]
                                             for name, rows in result["options"].items()},
                      "output_run": result["output_run"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
