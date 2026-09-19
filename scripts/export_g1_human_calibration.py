"""Create one immutable P2_G1_HUMAN_CALIBRATION_EXPORT_V1 package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.paths import PROJECT2_ROOT
from project2_g1_audit_web.calibration_export import (
    ALLOWED_INTENDED_ROLES,
    EXPORT_INTENDED_ROLE,
    HumanCalibrationExportService,
)
from project2_g1_audit_web.registry import default_owner_db_path, default_registry_path
from project2_g1_audit_web.service import G1AuditWebInput


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export completed G1 Human Reviews as an immutable Human Calibration package")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--intended-role", default=EXPORT_INTENDED_ROLE, choices=list(ALLOWED_INTENDED_ROLES))
    parser.add_argument("--project-root", type=Path, default=PROJECT2_ROOT)
    parser.add_argument("--registry-path", type=Path, default=None)
    parser.add_argument("--sqlite-path", type=Path, default=None)
    parser.add_argument("--export-root", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    registry = args.registry_path or default_registry_path(args.project_root)
    sqlite_path = args.sqlite_path or default_owner_db_path(args.project_root)
    web_input = G1AuditWebInput(project_root=args.project_root, registry_path=registry, owner_db_path=sqlite_path)
    loaded = web_input.load_validated_run(args.run_id)
    exporter = HumanCalibrationExportService(
        project_root=args.project_root,
        owner_db_path=sqlite_path,
        export_root=args.export_root,
    )
    result = exporter.create_export(loaded, intended_role=args.intended_role)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
