from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_mvp.m2_materializer import materialize_m2


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize the MVP-M2 small-sample runtime")
    parser.add_argument("--episode", action="append", dest="episodes")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    episodes = args.episodes or ["data/demo_0", "data/demo_1", "data/demo_2"]
    run_id = args.run_id or "mvp_m2_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    git_base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    result = materialize_m2(ROOT / "outputs" / "mvp_m2" / run_id, episodes, git_base=git_base)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
