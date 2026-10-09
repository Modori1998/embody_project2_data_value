"""Prepare the deterministic episode-level MVP Core Retrieval manifest candidate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project2_mvp.retrieval_manifest_preparation import run_retrieval_manifest_preparation


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--historical-root", type=Path)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    result = run_retrieval_manifest_preparation(
        project_root=args.project_root,
        historical_root=args.historical_root,
        run_id=args.run_id,
    )
    print(json.dumps({
        **result["summary"],
        "selected_episode_ids": {
            name: [row["episode_id"] for row in rows]
            for name, rows in result["selected"].items()
        },
        "output_run": result["output_run"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
