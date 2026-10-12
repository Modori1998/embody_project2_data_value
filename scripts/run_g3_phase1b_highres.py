"""Read-only CLI: P2-G3 Phase-1B high-resolution feasibility probe.

Experimental and non-invasive: it does not modify the P1 renderer, the frozen
RGB contract, or any formal output. Requires the renderer interpreter.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g3.highres_probe import probe_highres  # noqa: E402


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="P2-G3 Phase-1B high-resolution feasibility probe (experimental)"
    )
    parser.add_argument("--run-id")
    parser.add_argument("--output-root")
    args = parser.parse_args()
    output_root = (
        Path(args.output_root) if args.output_root else ROOT / "outputs" / "g3_phase1b_highres"
    )
    result = probe_highres(output_root, run_id=args.run_id, project_root=ROOT)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
