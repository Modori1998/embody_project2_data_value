from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path: sys.path.insert(0, str(ROOT / "src"))
from project2_g1.formal_evaluation_run import build_formal_evaluation_run
if __name__ == "__main__":
    print(json.dumps(build_formal_evaluation_run(project_root=ROOT), indent=2))
