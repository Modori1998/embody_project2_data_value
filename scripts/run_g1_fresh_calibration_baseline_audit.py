"""CLI for the frozen Fresh Calibration baseline Human Audit Run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.fresh_calibration_run import build_fresh_calibration_run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate immutable Fresh Calibration baseline Audit Run")
    parser.add_argument("--project-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    result = build_fresh_calibration_run(
        project_root=root,
        manifest_path=root / "outputs/g1_p3_calibration_selection/fresh_calibration_manifest_v1.json",
        screening_csv=root / "outputs/g1_p3_calibration_selection/fresh_calibration_screening_v1_20260917.csv",
        registry_path=root / "outputs/g1_audit_web/g1_audit_run_registry.json",
        runs_root=root / "outputs/g1_audit_runs",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
