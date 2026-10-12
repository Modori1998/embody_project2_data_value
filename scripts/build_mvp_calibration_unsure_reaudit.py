"""Build a focused Calibration re-audit page from first-pass UNSURE items only."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_mvp_calibration_audit_ui import build_page, read_csv
from build_mvp_calibration_temporal_audit import existing_segment_gif_paths

DEFAULT_FORMAL_RUN = ROOT / "outputs/mvp_core_retrieval_formal/mvp_core_retrieval_formal_stage1_20261009"
DEFAULT_FIRST_PASS = ROOT / "0-doc/80-audit-local/mvp_core_retrieval_calibration/01_calibration_human_audit_pairs_filled_20261011.csv"
DEFAULT_SOURCE_PACKAGE = ROOT / "outputs/mvp_core_retrieval_human_audit/calibration_blind_audit_temporal_v1_20261010"
DEFAULT_RUN_ID = "calibration_unsure_reaudit_v1_20261012"
EXPECTED_FIRST_PASS_ITEMS = 95
EXPECTED_UNSURE_ITEMS = 31


def select_unsure_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    if len(rows) != EXPECTED_FIRST_PASS_ITEMS:
        raise ValueError(f"First-pass audit item count changed: {len(rows)}")
    selected = [dict(row) for row in rows if row.get("review_label") == "UNSURE"]
    if len(selected) != EXPECTED_UNSURE_ITEMS:
        raise ValueError(f"First-pass UNSURE count changed: {len(selected)}")
    for row in selected:
        row["review_label"] = ""
        row["query_bad_segment"] = ""
    return selected


def build_unsure_reaudit(
    formal_run: Path,
    first_pass: Path,
    source_package: Path,
    output: Path,
) -> dict:
    selected = select_unsure_rows(read_csv(first_pass))
    source_gifs = existing_segment_gif_paths(source_package)
    required_segments = {
        segment_id
        for row in selected
        for segment_id in (row["query_segment_id"], row["candidate_segment_id"])
    }
    missing = sorted(required_segments - set(source_gifs))
    if missing:
        raise FileNotFoundError(f"Existing temporal GIF package is missing required segments: {missing}")

    output.mkdir(parents=True, exist_ok=True)
    gif_paths = {
        segment_id: Path(
            os.path.relpath(source_package / source_gifs[segment_id], output)
        ).as_posix()
        for segment_id in required_segments
    }

    result = build_page(
        formal_run,
        output,
        segment_gifs=gif_paths,
        allow_existing_output=True,
        audit_rows=selected,
        page_title="Calibration UNSURE Re-audit",
        storage_key_suffix="unsure-reaudit-v1-20261012",
        export_filename="calibration_unsure_reaudit_filled.csv",
    )
    summary = {
        "mode": "CALIBRATION_UNSURE_REAUDIT",
        "source_first_pass": str(first_pass.resolve()),
        "source_temporal_package": str(source_package.resolve()),
        "source_audit_items": EXPECTED_FIRST_PASS_ITEMS,
        "reaudit_items": len(selected),
        "source_label": "UNSURE",
        "prior_labels_preloaded": False,
        "segment_gifs_reused": len(required_segments),
        "gif_rerendered": False,
        "retrieval_rerun": False,
        "formal_result": False,
        "purpose": "Calibration rubric clarification before Final freeze",
    }
    (output / "unsure_reaudit_meta.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return {**result, **summary}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--formal-run", type=Path, default=DEFAULT_FORMAL_RUN)
    parser.add_argument("--first-pass", type=Path, default=DEFAULT_FIRST_PASS)
    parser.add_argument("--source-package", type=Path, default=DEFAULT_SOURCE_PACKAGE)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    args = parser.parse_args(argv)

    output = ROOT / "outputs/mvp_core_retrieval_human_audit" / args.run_id
    result = build_unsure_reaudit(
        args.formal_run.resolve(),
        args.first_pass.resolve(),
        args.source_package.resolve(),
        output,
    )
    print(json.dumps({"output": str(output.resolve()), **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
