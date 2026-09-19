"""Build the Combined 12-Episode Canonical Human Boundary GT snapshot from two Exports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.canonical_gt import build_combined_canonical_gt
from project2_g1.paths import DATASET_LOW_DIM_HDF5, DATASET_RAW_HDF5, PROJECT2_ROOT

DEFAULT_SEED_EXPORT_ID = "g1_cal_seed_export_20260917_214637_2f8d8802"
DEFAULT_FRESH_EXPORT_ID = "g1_cal_export_20260918_120335_81c068bf"
DEFAULT_ERROR_MODE_MAP = (
    PROJECT2_ROOT / "outputs" / "g1_human_review_analysis" / "20260917_error_attribution" / "boundary_error_attribution.csv"
)
DEFAULT_SELECTION_MANIFEST = PROJECT2_ROOT / "outputs" / "g1_p3_calibration_selection" / "fresh_calibration_manifest_v1.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Combined Canonical Human Boundary GT from two Human Calibration Exports")
    parser.add_argument("--seed-export-id", default=DEFAULT_SEED_EXPORT_ID)
    parser.add_argument("--fresh-export-id", default=DEFAULT_FRESH_EXPORT_ID)
    parser.add_argument("--project-root", type=Path, default=PROJECT2_ROOT)
    parser.add_argument("--export-root", type=Path, default=None)
    parser.add_argument("--snapshot-root", type=Path, default=None)
    parser.add_argument("--error-mode-map", type=Path, default=DEFAULT_ERROR_MODE_MAP)
    parser.add_argument("--selection-manifest", type=Path, default=DEFAULT_SELECTION_MANIFEST)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = args.project_root
    export_root = args.export_root or (project_root / "outputs" / "g1_audit_web" / "human_calibration_export")
    snapshot_root = args.snapshot_root or (project_root / "outputs" / "g1_p3_canonical_gt")
    manifest = json.loads(Path(args.selection_manifest).read_text(encoding="utf-8"))
    result = build_combined_canonical_gt(
        seed_export_path=export_root / args.seed_export_id,
        fresh_export_path=export_root / args.fresh_export_id,
        snapshot_root=snapshot_root,
        error_mode_map_path=args.error_mode_map,
        expected_seed_episode_ids=manifest["existing_seed_episode_ids"],
        expected_fresh_episode_ids=manifest["fresh_episode_ids"],
        source_run_root=project_root / "outputs" / "g1_audit_runs",
        owner_sqlite_path=project_root / "outputs" / "g1_audit_web" / "g1_audit_web_owner.sqlite3",
        dataset_paths=(DATASET_RAW_HDF5, DATASET_LOW_DIM_HDF5),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
