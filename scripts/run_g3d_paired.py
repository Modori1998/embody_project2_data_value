"""G3D fail-closed offline preflight; model calls require a verified service."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project2_g3.g3d_paired import verified_frames  # noqa: E402

FROZEN = ROOT / "0-doc/10-design-review/evidence/P2_G3_Taxonomy_v0_2_20261013"
SMALL = ("demo_2-S0003", "demo_169-S0002", "demo_172-S0004", "demo_180-S0001")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rgb-cache", type=Path, required=True)
    p.add_argument("--human-reference", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    manifest = json.loads((FROZEN / "run_manifest.json").read_text(encoding="utf-8"))
    if manifest["versions"]["v0_2"]["prompt_variant"] != "v0_2_1":
        raise ValueError("STOP_BASELINE_PROMPT_DRIFT")
    rows = {row["segment_id"]: row for row in csv.DictReader((FROZEN / "sample_manifest.csv").open(encoding="utf-8-sig")) if row["cohort"] == "microset"}
    human = {row["segment_id"]: row for row in csv.DictReader(args.human_reference.open(encoding="utf-8-sig")) if row["cohort"] == "microset"}
    if set(rows) != set(human) or len(rows) != 12:
        raise ValueError("STOP_HUMAN_SEGMENT_SET_DRIFT")
    for key, row in rows.items():
        ref = human[key]
        for field in ("episode_id", "start_frame", "end_frame", "target_keyframes", "frame_png_sha256s"):
            if row[field] != ref[field]:
                raise ValueError(f"STOP_HUMAN_IDENTITY_DRIFT: {key} {field}")
        verified_frames(row, args.rgb_cache)
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:8080/v1/models", timeout=3) as response:
            models = json.load(response)
        service = {"status": "reachable", "models": models}
    except Exception as exc:
        service = {"status": "unreachable", "reason": type(exc).__name__}
    result = {"status": "EXPERIMENT_NOT_RUN", "reason": "MODEL_SERVICE_PREFLIGHT_ONLY",
              "frozen_run_id": manifest["run_id"], "verified_segments": len(rows),
              "verified_png": 36, "small_gate": SMALL, "service": service,
              "model_revision": manifest["model_revision"],
              "prompt_sha256": manifest["versions"]["v0_2"]["prompt_template_sha256"],
              "schema_sha256": manifest["schema_sha256"]["v0_2"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 2 if service["status"] != "reachable" else 0


if __name__ == "__main__":
    raise SystemExit(main())
