"""Freeze six Fresh Calibration episode identities from fixed baseline screening."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.boundary_config import load_g1_p2_config
from project2_g1.calibration_selection import (
    PROTOCOL_DOCUMENT,
    SCREENING_FEATURES,
    SELECTION_FIELDS,
    SELECTION_VERSION,
    SOURCE_DATASET_ID,
    annotate_rows,
    build_shortlist,
    deterministic_manifest_id,
    now_iso,
    screen_dataset,
    select_final,
    selection_reason,
    validate_manifest_round_trip,
    validate_selection,
    write_csv_exclusive,
)
from project2_g1.config import load_g1_p1_config
from project2_g1.paths import DATASET_LOW_DIM_HDF5, DATASET_RAW_HDF5, G1_P2_CONFIG_PATH, PROJECT2_ROOT
from project2_g1.source import build_can_mh_adapter, enumerate_episodes
from project2_g1_audit_web.hashes import config_hash_from_path, signal_contract_hash_from_path

SEED_EXPORT_ID = "g1_cal_seed_export_20260917_214637_2f8d8802"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select and freeze six Fresh G1 Calibration Episodes")
    parser.add_argument("--project-root", type=Path, default=PROJECT2_ROOT)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--seed-export-id", default=SEED_EXPORT_ID)
    return parser.parse_args()


def _seed_ids(seed_path: Path) -> tuple[dict, list[str]]:
    meta = json.loads((seed_path / "export_meta.json").read_text(encoding="utf-8"))
    with (seed_path / "signal_review.csv").open(encoding="utf-8", newline="") as handle:
        ids = sorted({row["episode_id"] for row in csv.DictReader(handle)})
    if len(ids) != 6 or int(meta["episode_count"]) != 6:
        raise ValueError("formal Seed Export does not contain exactly 6 episodes")
    return meta, ids


def _manifest_rows(shortlist, selected_ids, config_hash, signal_hash):
    rows = []
    for item in shortlist:
        row = dict(item)
        row.update({
            "selection_version": SELECTION_VERSION,
            "source_dataset_id": SOURCE_DATASET_ID,
            "selection_reason": selection_reason(row),
            "is_existing_seed": False,
            "is_selected_fresh": row["episode_id"] in selected_ids,
            "evaluation_role": "UNASSIGNED",
            "screening_config_hash": config_hash,
            "signal_contract_hash": signal_hash,
        })
        rows.append(row)
    return rows


def _report(
    *, total: int, seed_ids: list[str], screening, failures, thresholds, shortlist_rows,
    selected, csv_path: Path, manifest_path: Path, screening_path: Path,
    source_paths: str, config_hash: str, signal_hash: str,
) -> str:
    label_counts = Counter(label for row in selected for label in row["selection_labels"])
    selected_ids = [row["episode_id"] for row in selected]
    lines = [
        "# Project 2 G1-P3 Fresh Calibration Episode Selection Result",
        "",
        "```text",
        "DATE = 2026-09-17",
        "TASK = FRESH_CALIBRATION_EPISODE_SELECTION",
        "SELECTION_METHOD = COVERAGE_BASED / NO_WEIGHTED_SCORE",
        "HUMAN_VIDEO_USED_FOR_SELECTION = NO",
        "HUMAN_GT_USED_FOR_SELECTION = NO",
        "PRIVILEGED_GT_USED = NO",
        "EVALUATION_SELECTED = NO",
        "PARAMETER_SEARCH_EXECUTED = NO",
        "AUDIT_RUN_GENERATED = NO",
        "```",
        "",
        "## 1. Authority",
        "",
        "```text",
        "CALIBRATION_PROTOCOL = FROZEN_v1.0",
        "CALIBRATION_TARGET_N = 12",
        "CALIBRATION_SEED_N = 6",
        "CALIBRATION_FRESH_N = 6",
        "SEARCH_GATE = CLOSED",
        "```",
        "",
        "Local Frozen Protocol and Google Drive Frozen Protocol are identical after newline normalization.",
        "",
        "## 2. Dataset",
        "",
        f"- `SOURCE_DATASET_ID = {SOURCE_DATASET_ID}`",
        f"- `SOURCE_HDF5_PATH = {source_paths}`",
        f"- `TOTAL_EPISODE_COUNT = {total}`",
        f"- `screening_config_hash = {config_hash}`",
        f"- `signal_contract_hash = {signal_hash}`",
        "",
        "Dataset HDF5 files were opened read-only through the existing Project 1 adapter.",
        "",
        "## 3. Candidate Pool QA",
        "",
        "```text",
        f"TOTAL_DATASET_EPISODES = {total}",
        f"EXCLUDED_SEED = {len(seed_ids)}",
        "EXCLUDED_EXISTING_EVALUATION_HOLD = 0",
        f"SCREENING_SUCCESS = {len(screening)}",
        f"SCREENING_FAILED = {len(failures)}",
        f"ELIGIBLE_FRESH_POOL = {len(screening)}",
        "SEED_OVERLAP = 0",
        "```",
        "",
        "Selection-only tertile thresholds were derived from the eligible pool:",
        "",
        f"- Length q33/q67: `{thresholds['length_q33']:.0f}` / `{thresholds['length_q67']:.0f}` frames",
        f"- Final-count q33/q67: `{thresholds['boundary_q33']:.0f}` / `{thresholds['boundary_q67']:.0f}`",
        "",
        "## 4. Shortlist",
        "",
        "| Episode | Length | Final | Gripper | Direction | Merged | G+D Merged | Short | Bucket | Reason |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in shortlist_rows:
        lines.append(
            f"| `{row['episode_id']}` | {row['episode_length_frames']} | {row['baseline_final_boundary_count']} | "
            f"{row['gripper_primary_count']} | {row['direction_primary_count']} | {row['merged_boundary_count']} | "
            f"{row['gripper_direction_merged_count']} | {row['short_segment_count']} | {row['selection_bucket']} | "
            f"{row['selection_reason']} |"
        )
    lines.extend(["", "## 5. Final Fresh 6", ""])
    for row in selected:
        lines.extend([
            f"### `{row['episode_id']}`", "",
            f"`selection_bucket = {row['selection_bucket']}`", "",
            row["selection_reason"], "",
        ])
    lines.extend([
        "## 6. Coverage Check", "", "```text",
        f"PRESERVATION_CANDIDATE = {label_counts['PRESERVATION_CANDIDATE']}",
        f"DIRECTION_COVERAGE = {label_counts['DIRECTION_COVERAGE']}",
        f"COMPLEXITY_CANDIDATE = {label_counts['COMPLEXITY_CANDIDATE']}",
        f"length buckets covered = {sorted({row['length_bucket'] for row in selected})}",
        f"boundary-count buckets covered = {sorted({row['boundary_count_bucket'] for row in selected})}",
        f"quality buckets covered = {sorted({row['quality_group'] for row in selected})}",
        f"gripper coverage = {sum(int(row['gripper_primary_count']) > 0 for row in selected)} episodes",
        f"merged coverage = {sum(int(row['gripper_direction_merged_count']) > 0 for row in selected)} episodes with Gripper+Direction merged",
        "```", "",
        "## 7. Manifest", "",
        f"- Full screening: `{screening_path}`",
        f"- Shortlist/selection CSV: `{csv_path}`",
        f"- Frozen identity manifest: `{manifest_path}`",
        "", "## 8. Leakage / Scope Check", "", "```text",
        "HUMAN_VIDEO_USED_FOR_SELECTION = NO",
        "HUMAN_GT_USED_FOR_SELECTION = NO",
        "PRIVILEGED_GT_USED = NO",
        "EVALUATION_SELECTED = NO",
        "PARAMETER_SEARCH_EXECUTED = NO",
        "HUMAN_REVIEW_STARTED = NO",
        "CANONICAL_GT_GENERATED = NO",
        "AUDIT_RUN_GENERATED = NO",
        "```", "", "## 9. Search Gate", "", "```text",
        f"CALIBRATION_EPISODE_IDS = {seed_ids + selected_ids}",
        "12 selected total = YES",
        "6 reviewed seed = YES",
        "6 fresh unreviewed = YES",
        "COMBINED_CANONICAL_GT = NOT_READY",
        "SEARCH_GATE = CLOSED",
        "```", "", "## 10. Final Status", "", "```text",
        "G1_FRESH_CALIBRATION_EPISODE_SELECTION =",
        "PASS_READY_FOR_BASELINE_AUDIT_RUN",
        "MANDATORY_STOP = YES",
        "```", "",
    ])
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = args.project_root.resolve()
    output = (args.output_dir or (root / "outputs" / "g1_p3_calibration_selection")).resolve()
    seed_path = root / "outputs" / "g1_audit_web" / "human_calibration_export" / args.seed_export_id
    seed_meta, seed_ids = _seed_ids(seed_path)
    p1 = load_g1_p1_config()
    p2 = load_g1_p2_config()
    config_hash = config_hash_from_path(G1_P2_CONFIG_PATH)
    signal_hash = signal_contract_hash_from_path(root / "configs" / "g1_p1_signal_contract.json")
    if config_hash != seed_meta["config_hash"] or signal_hash != seed_meta["signal_contract_hash"]:
        raise ValueError("current fixed baseline identity differs from formal Seed Export")

    adapter = build_can_mh_adapter(p1)
    identities = enumerate_episodes(adapter)
    screened, failures = screen_dataset(adapter, p1, p2, exclude_episode_ids=set(seed_ids))
    annotated, thresholds = annotate_rows(screened)
    shortlist = build_shortlist(annotated, n=12)
    selected = select_final(shortlist, n=6)
    selected_ids = {row["episode_id"] for row in selected}
    shortlist_rows = _manifest_rows(shortlist, selected_ids, config_hash, signal_hash)
    for row in selected:
        row.update({"evaluation_role": "UNASSIGNED", "selection_reason": selection_reason(row)})
    validate_selection(
        shortlist=shortlist_rows, selected=selected, seed_ids=set(seed_ids),
        config_hash=config_hash, expected_config_hash=seed_meta["config_hash"],
        signal_hash=signal_hash, expected_signal_hash=seed_meta["signal_contract_hash"],
    )

    screening_path = output / "fresh_calibration_screening_v1_20260917.csv"
    selection_path = output / "fresh_calibration_selection_v1_20260917.csv"
    manifest_path = output / "fresh_calibration_manifest_v1.json"
    failure_path = output / "fresh_calibration_screening_failures_v1_20260917.csv"
    write_csv_exclusive(screening_path, (*SCREENING_FEATURES, "length_bucket", "boundary_count_bucket", "direction_bucket"), annotated)
    write_csv_exclusive(selection_path, SELECTION_FIELDS, shortlist_rows)
    write_csv_exclusive(failure_path, ("episode_id", "failure_reason"), failures)
    manifest = {
        "created_at": now_iso(),
        "protocol_document": PROTOCOL_DOCUMENT,
        "selection_version": SELECTION_VERSION,
        "source_dataset_id": SOURCE_DATASET_ID,
        "source_hdf5_paths": [str(DATASET_RAW_HDF5), str(DATASET_LOW_DIM_HDF5)],
        "existing_seed_export_id": args.seed_export_id,
        "existing_seed_episode_ids": seed_ids,
        "fresh_episode_ids": sorted(selected_ids),
        "target_calibration_count": 12,
        "fresh_count": 6,
        "evaluation_usage": "FORBIDDEN_UNTIL_SEPARATE_EVALUATION_SELECTION",
        "parameter_search_allowed": False,
        "human_review_status": "NOT_STARTED",
        "screening_config_hash": config_hash,
        "signal_contract_hash": signal_hash,
        "selection_thresholds": thresholds,
    }
    manifest["manifest_id"] = deterministic_manifest_id(manifest)
    with manifest_path.open("x", encoding="utf-8", errors="strict") as handle:
        handle.write(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    validate_manifest_round_trip(manifest_path)

    report_path = root / "0-doc" / "Project2_G1_P3_Fresh_Calibration_Episode_Selection_Result_20260917.md"
    with report_path.open("x", encoding="utf-8") as handle:
        handle.write(_report(
            total=len(identities), seed_ids=seed_ids, screening=screened, failures=failures,
            thresholds=thresholds, shortlist_rows=shortlist_rows, selected=selected,
            csv_path=selection_path, manifest_path=manifest_path, screening_path=screening_path,
            source_paths=f"raw={DATASET_RAW_HDF5}; low_dim={DATASET_LOW_DIM_HDF5}",
            config_hash=config_hash, signal_hash=signal_hash,
        ))
    print(json.dumps({
        "source_dataset_id": SOURCE_DATASET_ID, "total_episode_count": len(identities),
        "excluded_seed": len(seed_ids), "screening_success": len(screened),
        "screening_failed": len(failures), "eligible_fresh_pool": len(screened),
        "shortlist": [row["episode_id"] for row in shortlist],
        "fresh_episode_ids": sorted(selected_ids), "manifest_id": manifest["manifest_id"],
        "selection_csv": str(selection_path), "manifest_json": str(manifest_path),
        "report": str(report_path),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
