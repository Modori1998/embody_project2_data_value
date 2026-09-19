"""Create an immutable child G1 Audit Run with materialized Final member semantics."""

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
from project2_g1_audit_web.hashes import tree_fingerprint
from project2_g1_audit_web.materialize_final_semantics import materialize_parent_run

DEFAULT_PARENT = (
    PROJECT2_ROOT / "outputs" / "g1_audit_runs" / "g1_exploratory_audit_20260916_214523_1ba11d9d"
)
LEGACY_ROOT = PROJECT2_ROOT / "outputs" / "g1_p2_boundary_audit"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize Final Boundary member semantics as a child run.")
    parser.add_argument("--project-root", type=Path, default=PROJECT2_ROOT)
    parser.add_argument("--parent-run", type=Path, default=DEFAULT_PARENT)
    parser.add_argument("--no-register", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    parent = Path(args.parent_run).resolve()
    legacy_before = tree_fingerprint(LEGACY_ROOT) if LEGACY_ROOT.is_dir() else None
    parent_before = tree_fingerprint(parent)
    result = materialize_parent_run(
        project_root=args.project_root,
        parent_run_root=parent,
        register=not args.no_register,
    )
    parent_after = tree_fingerprint(parent)
    legacy_after = tree_fingerprint(LEGACY_ROOT) if LEGACY_ROOT.is_dir() else None
    payload = {
        "run_id": result["run_id"],
        "run_root": result["run_root"],
        "parent_run_id": result["parent_run_id"],
        "config_hash": result["config_hash"],
        "signal_contract_hash": result["signal_contract_hash"],
        "final_member_semantics": result["final_member_semantics"],
        "parent_before": parent_before["tree_fingerprint"],
        "parent_after": parent_after["tree_fingerprint"],
        "parent_unchanged": parent_before["tree_fingerprint"] == parent_after["tree_fingerprint"],
        "legacy_before": None if legacy_before is None else legacy_before["tree_fingerprint"],
        "legacy_after": None if legacy_after is None else legacy_after["tree_fingerprint"],
        "legacy_unchanged": True
        if legacy_before is None or legacy_after is None
        else legacy_before["tree_fingerprint"] == legacy_after["tree_fingerprint"],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not payload["parent_unchanged"] or not payload["legacy_unchanged"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
