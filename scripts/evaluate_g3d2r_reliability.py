"""Evaluate a completed G3D2-R run: reliability (P4) and five-arm semantics (P5).

Read-only post-hoc evaluator. It never calls the model, never rewrites the frozen
runner, never repairs a schema-invalid response and never drops a failed cell.
It writes ``evaluation.json`` and ``per_segment_evaluation.jsonl`` next to the
raw run (under the gitignored ``outputs/`` tree); the sanitized aggregate numbers
are exported to ``0-doc/10-design-review/G3D2_R_Results.md``.

The analysis is implemented and unit-tested in
``project2_g3.g3d2r_reliability``; this module only performs run identity checks
and I/O.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project2_g3.g3d2_temporal import GROUPS  # noqa: E402
from project2_g3.g3d2r_reliability import evaluate, load_cells, per_segment  # noqa: E402

FROZEN = ROOT / "0-doc/10-design-review/evidence/P2_G3_Taxonomy_v0_2_20261013"
PROTOCOL = "fallback_json_object_retry_v1"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def human_reference(path: Path, sample_rows: list[dict]) -> dict:
    human = {r["segment_id"]: r for r in csv.DictReader(path.open(encoding="utf-8-sig"))
             if r["cohort"] == "microset"}
    manifest = {r["segment_id"]: r for r in sample_rows}
    if set(human) != set(manifest) or len(human) != 12:
        raise ValueError("STOP_HUMAN_COHORT_DRIFT")
    for sid, row in manifest.items():
        ref = human[sid]
        for field in ("episode_id", "start_frame", "end_frame", "target_keyframes", "frame_png_sha256s"):
            if row[field] != ref[field]:
                raise ValueError(f"STOP_HUMAN_IDENTITY_DRIFT {sid} {field}")
    return human


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--human-reference", type=Path, required=True)
    args = parser.parse_args()

    run = json.loads((args.run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    if run.get("protocol") != PROTOCOL or run.get("expected_calls") != 60 or list(run.get("groups", [])) != list(GROUPS):
        raise ValueError("STOP_PROTOCOL_IDENTITY")
    sample_rows = [r for r in csv.DictReader((FROZEN / "sample_manifest.csv").open(encoding="utf-8-sig"))
                   if r["cohort"] == "microset"]
    if len(sample_rows) != 12 or [r["segment_id"] for r in sample_rows] != run["sample_order"]:
        raise ValueError("STOP_SAMPLE_MANIFEST_DRIFT")
    human = human_reference(args.human_reference, sample_rows)

    responses = load_jsonl(args.run_dir / "responses.jsonl")
    expected = [(sid, group) for sid in run["sample_order"] for group in GROUPS]
    cells = load_cells(responses, expected)
    if len(cells) != 60:
        raise ValueError("STOP_CELL_COUNT")

    report = {
        "run_manifest_protocol": run["protocol"],
        "frozen_manifest_sha256": run["frozen_manifest_sha256"],
        "schema_sha256": run["schema_sha256"],
        "model_revision": run["model_revision"],
        "model_gguf_sha256": run["model_gguf_sha256"],
        "mmproj_sha256": run["mmproj_sha256"],
        "sample_order": run["sample_order"],
        **evaluate(cells, human, list(GROUPS)),
    }
    (args.run_dir / "evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.run_dir / "per_segment_evaluation.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in per_segment(cells, human, list(GROUPS))) + "\n",
        encoding="utf-8")
    print(json.dumps({"reliability": report["reliability"]["overall"],
                      "own_valid_segments": report["own_valid_segments"],
                      "common_valid_segments": report["common_valid_segments"],
                      "end_to_end": report["end_to_end"],
                      "contrasts_common": report["contrasts_common"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
