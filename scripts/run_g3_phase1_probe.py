"""Read-only CLI: P2-G3 Phase-1 Development-pool observability probe.

No VLM call, no Formal retrieval, no mutation of Frozen artifacts.
Requires the renderer interpreter (robosuite/mujoco/robomimic/h5py).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g3.probe import run_phase1_probe  # noqa: E402


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="P2-G3 Phase-1 read-only probe")
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--output-root")
    parser.add_argument(
        "--project-root",
        help="Root holding read-only outputs/ manifests (defaults to this worktree)",
    )
    args = parser.parse_args()
    output_root = Path(args.output_root) if args.output_root else ROOT / "outputs" / "g3_phase1_probe"
    project_root = Path(args.project_root) if args.project_root else ROOT
    result = run_phase1_probe(
        output_root, render=not args.no_render, run_id=args.run_id, project_root=project_root
    )
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
