"""CLI: wrap the current G1-P2 legacy audit package as a versioned G1 Audit Run."""

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
from project2_g1_audit_web.bootstrap import bootstrap_legacy_run
from project2_g1_audit_web.hashes import tree_fingerprint


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap a versioned G1 audit run from the legacy P2 package.")
    parser.add_argument("--from-legacy", type=Path, default=ROOT / "outputs" / "g1_p2_boundary_audit")
    parser.add_argument("--project-root", type=Path, default=PROJECT2_ROOT)
    parser.add_argument("--no-register", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    before = tree_fingerprint(args.from_legacy)
    result = bootstrap_legacy_run(
        project_root=args.project_root,
        legacy_root=args.from_legacy,
        register=not args.no_register,
    )
    after = tree_fingerprint(args.from_legacy)
    payload = {
        "run_id": result["run_id"],
        "run_root": result["run_root"],
        "episode_count": result["episode_count"],
        "config_hash": result["config_hash"],
        "signal_contract_hash": result["signal_contract_hash"],
        "legacy_before": before["tree_fingerprint"],
        "legacy_after": after["tree_fingerprint"],
        "legacy_unchanged": before["tree_fingerprint"] == after["tree_fingerprint"],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
