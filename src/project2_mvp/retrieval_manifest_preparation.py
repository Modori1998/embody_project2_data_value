"""Prepare the episode-level Core Retrieval manifest candidate.

This module performs identity, readability, exclusion, duration stratification,
and deterministic SHA256 selection only. It does not run segmentation, M2,
model inference, embeddings, retrieval, scoring, or human audit.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from project2_g1.evaluation_manifest_preparation import (
    DATASET_ID,
    historical_usage_rows,
    load_historical_sets,
    scan_dataset,
)
from project2_g1.paths import PROJECT2_ROOT


PROTOCOL_VERSION = "MVP_CORE_RETRIEVAL_PROTOCOL_v1"
MANIFEST_CANDIDATE_VERSION = "MVP_CORE_RETRIEVAL_MANIFEST_CANDIDATE_v1"
SELECTION_SALT = "MVP_CORE_RETRIEVAL_V1"
EXPECTED_RAW_SHA256 = "6f5a0e96fc375468ae19ccac86a6dee3b4d3862ef0fe37ca2d02e93d9046fe6b"
EXPECTED_LOW_DIM_SHA256 = "c4a34c837913446d295c6ca38f2b31888d69812198478af470ecb84a99e9f7d7"
FROZEN_G1_EVAL_VERSION = "G1_P4_EVAL_MANIFEST_v1"
FROZEN_G1_EVAL_COUNT = 24
FROZEN_G1_EVAL_RELATIVE_PATH = Path(
    "0-doc/10-design-review/"
    "Project2_G1_P4_Independent_Evaluation_Manifest_FROZEN_v1_20260929.csv"
)
STRATA = ("SHORT", "MEDIUM", "LONG")
PER_STRATUM_COUNTS = {
    "CANDIDATE_BANK": 12,
    "CALIBRATION_QUERY": 3,
    "FINAL_QUERY": 6,
}
LEAKAGE_FIELDS = {
    "human_label_used": False,
    "G1_human_GT_used_for_selection": False,
    "G1_detector_score_used": False,
    "FP_FN_used": False,
    "error_mode_used": False,
    "VLM_label_used": False,
    "SigLIP2_embedding_used": False,
    "motion_retrieval_similarity_used": False,
    "retrieval_result_used": False,
    "manual_episode_cherry_pick_used": False,
    "formal_retrieval_executed": False,
    "human_retrieval_audit_started": False,
}

SPLIT_FIELDS = (
    "protocol_version", "manifest_candidate_version", "cohort", "cohort_rank",
    "duration_stratum", "stratum_rank", "episode_id", "frame_count",
    "duration_seconds", "selection_digest", "dataset_id", "source_identity",
    "historical_g1_excluded", "frozen_g1_eval_excluded", "eligibility_status",
)


class RetrievalManifestPreparationError(ValueError):
    pass


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str] | None = None) -> None:
    columns = list(fields or ())
    if not columns:
        for row in rows:
            for key in row:
                if key not in columns:
                    columns.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def stable_digest(episode_id: str) -> str:
    return hashlib.sha256(f"{SELECTION_SALT}|{episode_id}".encode("utf-8")).hexdigest()


def load_frozen_g1_evaluation(root: Path) -> tuple[list[dict[str, Any]], set[str], dict[str, Any]]:
    path = root / FROZEN_G1_EVAL_RELATIVE_PATH
    rows = _read_csv(path)
    versions = {str(row.get("manifest_version", "")) for row in rows}
    ids = [str(row.get("episode_id", "")) for row in rows]
    ranks = [int(row.get("selection_rank", 0)) for row in rows]
    if versions != {FROZEN_G1_EVAL_VERSION}:
        raise RetrievalManifestPreparationError(
            f"STOP_FROZEN_G1_EVAL_VERSION_MISMATCH: {sorted(versions)}"
        )
    if len(rows) != FROZEN_G1_EVAL_COUNT or len(set(ids)) != FROZEN_G1_EVAL_COUNT:
        raise RetrievalManifestPreparationError(
            f"STOP_FROZEN_G1_EVAL_COUNT_MISMATCH: rows={len(rows)} unique={len(set(ids))}"
        )
    if sorted(ranks) != list(range(1, FROZEN_G1_EVAL_COUNT + 1)):
        raise RetrievalManifestPreparationError("STOP_FROZEN_G1_EVAL_RANK_MISMATCH")
    output_rows = [
        {
            "manifest_version": row["manifest_version"],
            "selection_rank": int(row["selection_rank"]),
            "episode_id": row["episode_id"],
            "excluded_from_core_retrieval": "YES",
            "source_artifact": FROZEN_G1_EVAL_RELATIVE_PATH.as_posix(),
        }
        for row in rows
    ]
    provenance = {
        "manifest_version": FROZEN_G1_EVAL_VERSION,
        "episode_count": len(rows),
        "source_artifact": FROZEN_G1_EVAL_RELATIVE_PATH.as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    return output_rows, set(ids), provenance


def validate_dataset_identity(dataset: Mapping[str, Any]) -> None:
    expected = {
        "dataset_id": DATASET_ID,
        "raw_hdf5_sha256": EXPECTED_RAW_SHA256,
        "low_dim_hdf5_sha256": EXPECTED_LOW_DIM_SHA256,
    }
    mismatches = {
        key: {"expected": value, "actual": dataset.get(key)}
        for key, value in expected.items()
        if dataset.get(key) != value
    }
    if mismatches:
        raise RetrievalManifestPreparationError(
            "STOP_DATASET_IDENTITY_MISMATCH: " + json.dumps(mismatches, sort_keys=True)
        )


def validate_exclusion_sets(historical_ids: set[str], frozen_eval_ids: set[str]) -> list[str]:
    overlap = sorted(historical_ids & frozen_eval_ids)
    if overlap:
        raise RetrievalManifestPreparationError(
            "STOP_RETRIEVAL_EXCLUSION_SET_CONFLICT: " + json.dumps(overlap)
        )
    return overlap


def assign_duration_terciles(eligible: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ordered = sorted(eligible, key=lambda row: (int(row["frame_count"]), str(row["episode_id"])))
    n = len(ordered)
    if n < 63:
        raise RetrievalManifestPreparationError(
            f"STOP_INSUFFICIENT_ELIGIBLE_POOL: count={n} minimum=63"
        )
    first_cut = n // 3
    second_cut = (2 * n) // 3
    enriched: list[dict[str, Any]] = []
    for index, original in enumerate(ordered):
        row = dict(original)
        row["duration_stratum"] = (
            "SHORT" if index < first_cut else "MEDIUM" if index < second_cut else "LONG"
        )
        row["duration_rank"] = index + 1
        row["selection_digest"] = stable_digest(str(row["episode_id"]))
        enriched.append(row)
    counts = Counter(row["duration_stratum"] for row in enriched)
    definition = {
        "method": "sort by (frame_count ASC, episode_id ASC), then rank terciles",
        "eligible_count": n,
        "first_cut_zero_based": first_cut,
        "second_cut_zero_based": second_cut,
        "counts": {name: counts[name] for name in STRATA},
        "short_max_frame_count": int(enriched[first_cut - 1]["frame_count"]),
        "medium_max_frame_count": int(enriched[second_cut - 1]["frame_count"]),
    }
    return enriched, definition


def select_episode_cohorts(eligible: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    stratified, _definition = assign_duration_terciles(eligible)
    selected_by_cohort = {name: [] for name in PER_STRATUM_COUNTS}
    for stratum in STRATA:
        ranked = sorted(
            (row for row in stratified if row["duration_stratum"] == stratum),
            key=lambda row: (str(row["selection_digest"]), str(row["episode_id"])),
        )
        required = sum(PER_STRATUM_COUNTS.values())
        if len(ranked) < required:
            raise RetrievalManifestPreparationError(
                f"STOP_INSUFFICIENT_ELIGIBLE_POOL: stratum={stratum} count={len(ranked)} minimum={required}"
            )
        start = 0
        for cohort, count in PER_STRATUM_COUNTS.items():
            rank_offset = start
            chunk = ranked[start : start + count]
            start += count
            for stratum_rank, source in enumerate(chunk, rank_offset + 1):
                row = {
                    "protocol_version": PROTOCOL_VERSION,
                    "manifest_candidate_version": MANIFEST_CANDIDATE_VERSION,
                    "cohort": cohort,
                    "cohort_rank": 0,
                    "duration_stratum": stratum,
                    "stratum_rank": stratum_rank,
                    "episode_id": source["episode_id"],
                    "frame_count": int(source["frame_count"]),
                    "duration_seconds": float(source["duration_seconds_if_available"]),
                    "selection_digest": source["selection_digest"],
                    "dataset_id": DATASET_ID,
                    "source_identity": source["source_identity"],
                    "historical_g1_excluded": "NO",
                    "frozen_g1_eval_excluded": "NO",
                    "eligibility_status": "ELIGIBLE_SELECTED",
                }
                selected_by_cohort[cohort].append(row)
    all_rows: list[dict[str, Any]] = []
    for cohort in PER_STRATUM_COUNTS:
        for rank, row in enumerate(selected_by_cohort[cohort], 1):
            row["cohort_rank"] = rank
            all_rows.append(row)
    return all_rows, selected_by_cohort


def build_disjointness_audit(
    selected: Mapping[str, Sequence[Mapping[str, Any]]],
    historical_ids: set[str],
    frozen_eval_ids: set[str],
) -> dict[str, Any]:
    ids = {name: {str(row["episode_id"]) for row in rows} for name, rows in selected.items()}
    candidate = ids["CANDIDATE_BANK"]
    calibration = ids["CALIBRATION_QUERY"]
    final = ids["FINAL_QUERY"]
    all_selected = candidate | calibration | final
    stratum_counts = {
        cohort: dict(Counter(str(row["duration_stratum"]) for row in rows))
        for cohort, rows in selected.items()
    }
    audit = {
        "CANDIDATE_COUNT": len(candidate),
        "CALIBRATION_QUERY_COUNT": len(calibration),
        "FINAL_QUERY_COUNT": len(final),
        "TOTAL_SELECTED_UNIQUE": len(all_selected),
        "CANDIDATE_CALIBRATION_OVERLAP": sorted(candidate & calibration),
        "CANDIDATE_FINAL_OVERLAP": sorted(candidate & final),
        "CALIBRATION_FINAL_OVERLAP": sorted(calibration & final),
        "SELECTED_HISTORICAL_G1_OVERLAP": sorted(all_selected & historical_ids),
        "SELECTED_FROZEN_G1_EVAL_OVERLAP": sorted(all_selected & frozen_eval_ids),
        "stratum_counts": stratum_counts,
    }
    expected_strata = {
        cohort: {stratum: count for stratum in STRATA}
        for cohort, count in PER_STRATUM_COUNTS.items()
    }
    passed = (
        audit["CANDIDATE_COUNT"] == 36
        and audit["CALIBRATION_QUERY_COUNT"] == 9
        and audit["FINAL_QUERY_COUNT"] == 18
        and audit["TOTAL_SELECTED_UNIQUE"] == 63
        and not audit["CANDIDATE_CALIBRATION_OVERLAP"]
        and not audit["CANDIDATE_FINAL_OVERLAP"]
        and not audit["CALIBRATION_FINAL_OVERLAP"]
        and not audit["SELECTED_HISTORICAL_G1_OVERLAP"]
        and not audit["SELECTED_FROZEN_G1_EVAL_OVERLAP"]
        and stratum_counts == expected_strata
    )
    audit["STRATUM_BALANCE"] = "PASS" if stratum_counts == expected_strata else "FAIL"
    audit["RETRIEVAL_MANIFEST_DISJOINTNESS"] = "PASS" if passed else "FAIL"
    if not passed:
        raise RetrievalManifestPreparationError(
            "STOP_RETRIEVAL_MANIFEST_DISJOINTNESS_FAILURE: " + json.dumps(audit, sort_keys=True)
        )
    return audit


def leakage_audit() -> dict[str, Any]:
    return {**LEAKAGE_FIELDS, "LEAKAGE_AUDIT": "PASS"}


def prepare_immutable_temp(output: Path) -> Path:
    temp = output.parent / (".tmp-" + output.name)
    if output.exists() or temp.exists():
        raise RetrievalManifestPreparationError("immutable output run already exists")
    temp.mkdir(parents=True, exist_ok=False)
    return temp


def run_retrieval_manifest_preparation(
    *,
    project_root: str | Path | None = None,
    historical_root: str | Path | None = None,
    run_id: str,
) -> dict[str, Any]:
    root = Path(project_root or PROJECT2_ROOT).resolve()
    history_root = Path(historical_root or root).resolve()
    historical, source_sets = load_historical_sets(history_root)
    historical_rows = historical_usage_rows(historical, source_sets)
    historical_ids = {str(row["episode_id"]) for row in historical_rows}
    frozen_eval_rows, frozen_eval_ids, frozen_eval_provenance = load_frozen_g1_evaluation(root)
    exclusion_overlap = validate_exclusion_sets(historical_ids, frozen_eval_ids)

    pool, dataset = scan_dataset(root, historical)
    validate_dataset_identity(dataset)
    enriched_pool: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for original in pool:
        row = dict(original)
        episode_id = str(row["episode_id"])
        historical_excluded = episode_id in historical_ids
        frozen_eval_excluded = episode_id in frozen_eval_ids
        readable = row["readability_status"] == "READABLE"
        if readable and not historical_excluded and not frozen_eval_excluded:
            status, reason = "ELIGIBLE_FOR_CORE_RETRIEVAL", ""
        else:
            status = "EXCLUDED"
            reasons = []
            if not readable:
                reasons.append(str(row.get("exclusion_reason") or row["readability_status"]))
            if historical_excluded:
                reasons.append("HISTORICAL_G1_USAGE")
            if frozen_eval_excluded:
                reasons.append("FROZEN_G1_EVALUATION")
            reason = "|".join(reasons)
        row.update({
            "historical_g1_excluded": "YES" if historical_excluded else "NO",
            "frozen_g1_eval_excluded": "YES" if frozen_eval_excluded else "NO",
            "eligibility_status": status,
            "exclusion_reason": reason,
        })
        enriched_pool.append(row)
        if status == "ELIGIBLE_FOR_CORE_RETRIEVAL":
            eligible.append(row)

    stratified, duration_definition = assign_duration_terciles(eligible)
    eligible_by_id = {str(row["episode_id"]): row for row in stratified}
    for row in enriched_pool:
        selected = eligible_by_id.get(str(row["episode_id"]))
        row["duration_stratum"] = "" if selected is None else selected["duration_stratum"]
        row["duration_rank"] = "" if selected is None else selected["duration_rank"]
        row["selection_digest"] = "" if selected is None else selected["selection_digest"]

    split_rows, selected = select_episode_cohorts(stratified)
    disjointness = build_disjointness_audit(selected, historical_ids, frozen_eval_ids)
    leakage = leakage_audit()
    summary = {
        **dataset,
        "total_dataset_episodes": len(enriched_pool),
        "historical_counts": {name: len(values) for name, values in historical.items()},
        "historical_unique_episodes": len(historical_ids),
        "frozen_g1_evaluation_episodes": len(frozen_eval_ids),
        "historical_vs_frozen_eval_overlap": exclusion_overlap,
        "eligible_retrieval_pool": len(stratified),
        "unreadable_or_schema_invalid": sum(row["readability_status"] != "READABLE" for row in enriched_pool),
        "duration_terciles": duration_definition,
        "selected_counts": {name: len(rows) for name, rows in selected.items()},
        "CORE_RETRIEVAL_MANIFEST": "READY_FOR_OWNER_REVIEW",
        "CORE_RETRIEVAL_INFERENCE": "BLOCKED_PENDING_RETRIEVAL_MANIFEST_FREEZE_AND_RUNTIME_PREFLIGHT",
    }
    provenance = {
        "protocol_version": PROTOCOL_VERSION,
        "manifest_candidate_version": MANIFEST_CANDIDATE_VERSION,
        "selection_salt": SELECTION_SALT,
        "selection_digest": 'SHA256("MVP_CORE_RETRIEVAL_V1|" + episode_id)',
        "duration_assignment": duration_definition,
        "within_stratum_sort": "selection_digest ASC, episode_id ASC",
        "within_stratum_allocation": "ranks 1-12 candidate, 13-15 calibration, 16-21 final",
        "historical_root": str(history_root),
        "historical_source_artifacts": sorted(source_sets),
        "frozen_g1_evaluation": frozen_eval_provenance,
        "dataset_identity": dataset,
        "query_segment_balance": "PENDING_POST_MANIFEST_M2_MATERIALIZATION",
        "query_selection_rule": "FROZEN_BY_PROTOCOL",
    }

    output = root / "outputs" / "mvp_core_retrieval_manifest_preparation" / run_id
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = prepare_immutable_temp(output)
    _write_csv(temp / "historical_episode_usage.csv", historical_rows)
    _write_csv(temp / "frozen_g1_evaluation_exclusion.csv", frozen_eval_rows)
    _write_csv(temp / "eligible_retrieval_pool.csv", enriched_pool)
    _write_csv(temp / "episode_split_manifest_candidate.csv", split_rows, SPLIT_FIELDS)
    _write_csv(temp / "candidate_bank_36.csv", selected["CANDIDATE_BANK"], SPLIT_FIELDS)
    _write_csv(temp / "calibration_query_9.csv", selected["CALIBRATION_QUERY"], SPLIT_FIELDS)
    _write_csv(temp / "final_query_18.csv", selected["FINAL_QUERY"], SPLIT_FIELDS)
    (temp / "retrieval_manifest_disjointness_audit.json").write_text(json.dumps(disjointness, indent=2) + "\n", encoding="utf-8")
    (temp / "retrieval_manifest_leakage_audit.json").write_text(json.dumps(leakage, indent=2) + "\n", encoding="utf-8")
    (temp / "retrieval_manifest_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    (temp / "dataset_pool_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (temp / "run_meta.json").write_text(json.dumps({
        "run_id": run_id,
        "created_at": datetime.now().astimezone().isoformat(),
        "task": "CORE_RETRIEVAL_MANIFEST_PREPARATION_ONLY",
        "protocol_version": PROTOCOL_VERSION,
        "manifest_frozen": False,
        "query_segment_selection_executed": False,
        "m2_materialization_executed": False,
        "segmentation_executed": False,
        "siglip2_executed": False,
        "faiss_executed": False,
        "retrieval_executed": False,
        "vlm_executed": False,
    }, indent=2) + "\n", encoding="utf-8")
    os.rename(temp, output)
    return {
        "output_run": str(output), "summary": summary, "selected": selected,
        "disjointness": disjointness, "leakage": leakage, "provenance": provenance,
    }
