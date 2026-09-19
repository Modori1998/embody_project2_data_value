"""Discover or generate the 12-Episode CALIBRATION Baseline Run. No scoring."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.baseline_calibration_run import ensure_12ep_baseline_run
from project2_g1.paths import PROJECT2_ROOT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit or materialize 12-Episode Calibration Baseline Run")
    parser.add_argument("--project-root", type=Path, default=PROJECT2_ROOT)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    result = ensure_12ep_baseline_run(
        project_root=root,
        combined_manifest_path=root / "outputs/g1_p3_canonical_gt/g1_canonical_gt_20260918_131636_c9916b89/combined_calibration_manifest.json",
        registry_path=root / "outputs/g1_audit_web/g1_audit_run_registry.json",
        runs_root=root / "outputs/g1_audit_runs",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
