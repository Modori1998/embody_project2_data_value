"""CLI: materialize the blinded G1-P3 trajectory diagnostic set as a
DESIGN_DIAGNOSTIC G1 Human Audit Web run.

The 20 events come only from 03_selection_blinded.csv. No re-selection, no
re-ranking, no re-matching, no labels, no Detector change.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.trajectory_diagnostic_run import (  # noqa: E402
    BLINDED_MANIFEST_RELPATH,
    TrajectoryDiagnosticRunError,
    build_trajectory_diagnostic_run,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Materialize the blinded G1-P3 trajectory diagnostic Audit Web run"
    )
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument(
        "--blinded-manifest",
        type=Path,
        default=None,
        help=f"defaults to <project-root>/{BLINDED_MANIFEST_RELPATH}",
    )
    parser.add_argument("--created-at", default=None, help="ISO timestamp override (tests only)")
    args = parser.parse_args(argv)

    root = args.project_root.resolve()
    try:
        result = build_trajectory_diagnostic_run(
            project_root=root,
            blinded_manifest_path=args.blinded_manifest,
            registry_path=root / "outputs" / "g1_audit_web" / "g1_audit_run_registry.json",
            runs_root=root / "outputs" / "g1_audit_runs",
            owner_db_path=root / "outputs" / "g1_audit_web" / "g1_audit_web_owner.sqlite3",
            created_at=args.created_at,
        )
    except TrajectoryDiagnosticRunError as exc:
        print("BLOCKED: " + str(exc))
        return 2

    print("=" * 74)
    print("G1-P3 TRAJECTORY MECHANISM DIAGNOSTIC AUDIT RUN")
    print("=" * 74)
    print(f"run_id                  = {result['run_id']}")
    print(f"run_root                = {result['run_root']}")
    print(f"run_stage               = {result['run_stage']}")
    print(f"set_role                = {result['set_role']}")
    print(f"diagnostic_set_id       = {result['diagnostic_set_id']}")
    print(f"event_count             = {result['event_count']}")
    print(f"distinct_episodes       = {result['distinct_episodes']}")
    print(f"config_hash             = {result['config_hash']}")
    print(f"signal_contract_hash    = {result['signal_contract_hash']}")
    print(f"blocked_downstreams     = {', '.join(result['blocked_downstreams'])}")
    print(f"blinding_contract       = {result['blinding_contract']}")
    print(f"registry_status         = {result['registry_status']}")
    print("=" * 74)
    print("open = /audit/" + str(result["run_id"]))
    print(json.dumps({"run_id": result["run_id"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
