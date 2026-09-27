"""G1-P4 independent-evaluation manifest candidate preparation.

This module reads episode identity, source schema, length, and historical-use
provenance only.  It must not run segmentation, scoring, GT construction, or
human review.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from project2_g1_audit_web.hashes import sha256_file

from .config import load_g1_p1_config
from .paths import CONFIG_PATH, PROJECT2_ROOT
from .source import build_can_mh_adapter, enumerate_episodes, load_formal_episode

DATASET_ID = "robomimic_v15_can_mh"
SAMPLE_HZ = 20.0
SELECTION_SALT = "G1P4_EVAL_MANIFEST_CANDIDATE_V1"
OPTION_COUNTS = {"small": 12, "medium": 24, "large": 36}
MANIFEST_CANDIDATE_VERSION = "G1P4_EVAL_MANIFEST_CANDIDATE_V1"
EVALUATION_MANIFEST_FROZEN = False
FORMAL_EVALUATION_RUN_ALLOWED = False

EXPLORATORY_MANIFEST = "outputs/g1_audit_runs/g1_exploratory_audit_20260917_141541_fe251439/episode_manifest.csv"
FRESH_SELECTION = "outputs/g1_p3_calibration_selection/fresh_calibration_manifest_v1.json"
FRESH_AUDIT_MANIFEST = "outputs/g1_audit_runs/g1_calibration_20260918_094455_df2ce8b2/episode_manifest.csv"
COMBINED_MANIFEST = "outputs/g1_p3_canonical_gt/g1_canonical_gt_20260918_131636_c9916b89/combined_calibration_manifest.json"
SEED_EXPORT = "outputs/g1_audit_web/human_calibration_export/g1_cal_seed_export_20260917_214637_2f8d8802/signal_review.csv"
FRESH_EXPORT = "outputs/g1_audit_web/human_calibration_export/g1_cal_export_20260918_120335_81c068bf/signal_review.csv"
DIAGNOSTIC_MANIFEST = "outputs/g1_audit_runs/g1_design_diagnostic_20260922_135647_69bf2a94/episode_manifest.csv"
DIAGNOSTIC_SELECTION = "0-doc/80-audit-local/g1_p3_trajectory_mechanism_validation/02_selection_internal.csv"
DIAGNOSTIC_HISTORY = "0-doc/80-audit-local/g1_p3_trajectory_mechanism_validation/05_review_history.csv"

HISTORICAL_FIELDS = (
    "episode_id", "used_in_exploratory", "used_in_calibration_seed",
    "used_in_calibration_fresh", "used_in_calibration_combined",
    "used_in_design_diagnostic", "source_artifact", "eligible_for_evaluation",
)
POOL_FIELDS = (
    "episode_id", "frame_count", "duration_seconds_if_available", "source_identity",
    "readability_status", "used_in_exploratory", "used_in_calibration",
    "used_in_diagnostic", "disjoint_from_exploratory", "disjoint_from_calibration_seed",
    "disjoint_from_calibration_fresh", "disjoint_from_design_diagnostic",
    "eligibility_status", "exclusion_reason", "duration_stratum", "stable_hash_rank",
    "duration_stratified_rank",
)
MANIFEST_FIELDS = (
    "manifest_candidate_version", "episode_id", "selection_method", "selection_rank",
    "frame_count", "duration_seconds", "source_identity", "duration_stratum",
)


class EvaluationManifestPreparationError(ValueError):
    pass


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _write_csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _episode_set(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    return {str(row["episode_id"]) for row in rows}


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_historical_sets(root: Path) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    combined = _json(root / COMBINED_MANIFEST)
    fresh_selection = _json(root / FRESH_SELECTION)
    sources = {
        EXPLORATORY_MANIFEST: _episode_set(_read_csv(root / EXPLORATORY_MANIFEST)),
        SEED_EXPORT: _episode_set(_read_csv(root / SEED_EXPORT)),
        FRESH_SELECTION: set(map(str, fresh_selection["fresh_episode_ids"])),
        FRESH_AUDIT_MANIFEST: _episode_set(_read_csv(root / FRESH_AUDIT_MANIFEST)),
        FRESH_EXPORT: _episode_set(_read_csv(root / FRESH_EXPORT)),
        COMBINED_MANIFEST + "#seed": set(map(str, combined["seed_episode_ids"])),
        COMBINED_MANIFEST + "#fresh": set(map(str, combined["fresh_episode_ids"])),
        COMBINED_MANIFEST + "#combined": set(map(str, combined["episode_ids"])),
        DIAGNOSTIC_MANIFEST: _episode_set(_read_csv(root / DIAGNOSTIC_MANIFEST)),
        DIAGNOSTIC_SELECTION: _episode_set(_read_csv(root / DIAGNOSTIC_SELECTION)),
        DIAGNOSTIC_HISTORY: _episode_set(_read_csv(root / DIAGNOSTIC_HISTORY)),
    }
    exploratory = sources[EXPLORATORY_MANIFEST]
    seed = sources[SEED_EXPORT]
    fresh = sources[FRESH_SELECTION]
    diagnostic = sources[DIAGNOSTIC_MANIFEST]
    conflicts = []
    if not (exploratory == seed == sources[COMBINED_MANIFEST + "#seed"] == set(map(str, fresh_selection["existing_seed_episode_ids"]))):
        conflicts.append("exploratory/seed sources disagree")
    if not (fresh == sources[FRESH_AUDIT_MANIFEST] == sources[FRESH_EXPORT] == sources[COMBINED_MANIFEST + "#fresh"]):
        conflicts.append("fresh calibration sources disagree")
    if sources[COMBINED_MANIFEST + "#combined"] != seed | fresh:
        conflicts.append("combined calibration is not seed union fresh")
    if not (diagnostic == sources[DIAGNOSTIC_SELECTION] == sources[DIAGNOSTIC_HISTORY]):
        conflicts.append("design diagnostic sources disagree")
    if conflicts:
        raise EvaluationManifestPreparationError("STOP_HISTORICAL_PROVENANCE_CONFLICT: " + "; ".join(conflicts))
    return {
        "exploratory": exploratory, "calibration_seed": seed, "calibration_fresh": fresh,
        "calibration_combined": seed | fresh, "design_diagnostic": diagnostic,
    }, sources


def historical_usage_rows(sets: Mapping[str, set[str]], sources: Mapping[str, set[str]]) -> list[dict[str, Any]]:
    union = set().union(*sets.values())
    rows = []
    for episode_id in sorted(union):
        provenance = sorted(name for name, episodes in sources.items() if episode_id in episodes)
        flags = {name: episode_id in episodes for name, episodes in sets.items()}
        eligible = not any(flags.values())
        rows.append({
            "episode_id": episode_id,
            "used_in_exploratory": "YES" if flags["exploratory"] else "NO",
            "used_in_calibration_seed": "YES" if flags["calibration_seed"] else "NO",
            "used_in_calibration_fresh": "YES" if flags["calibration_fresh"] else "NO",
            "used_in_calibration_combined": "YES" if flags["calibration_combined"] else "NO",
            "used_in_design_diagnostic": "YES" if flags["design_diagnostic"] else "NO",
            "source_artifact": "|".join(provenance),
            "eligible_for_evaluation": "YES" if eligible else "NO",
        })
    return rows


def scan_dataset(root: Path, historical: Mapping[str, set[str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    config = load_g1_p1_config(root / CONFIG_PATH.relative_to(PROJECT2_ROOT))
    adapter = build_can_mh_adapter(config)
    raw_hash = sha256_file(Path(config.raw_hdf5))
    low_hash = sha256_file(Path(config.low_dim_hdf5))
    source_identity = f"{DATASET_ID}:raw={raw_hash}:low_dim={low_hash}"
    rows = []
    try:
        identities = enumerate_episodes(adapter)
        for identity in identities:
            status = "READABLE"
            exclusion = ""
            frame_count = int(identity.num_steps)
            try:
                episode = load_formal_episode(adapter, identity.source_episode_id)
                shapes = {
                    "eef_pos": episode.eef_pos.shape, "eef_quat": episode.eef_quat.shape,
                    "gripper_qpos": episode.gripper_qpos.shape, "joint_pos": episode.joint_pos.shape,
                    "actions": episode.actions.shape,
                }
                valid = (
                    frame_count > 1 and len(episode.frame_index) == frame_count
                    and len(shapes["eef_pos"]) == 2 and shapes["eef_pos"][1] == 3
                    and len(shapes["eef_quat"]) == 2 and shapes["eef_quat"][1] == 4
                    and len(shapes["gripper_qpos"]) == 2 and shapes["gripper_qpos"][1] >= 1
                    and len(shapes["joint_pos"]) == 2 and shapes["joint_pos"][1] >= 7
                    and len(shapes["actions"]) == 2 and shapes["actions"][1] == 7
                )
                if not valid:
                    status, exclusion = "SCHEMA_INVALID", "SCHEMA_INVALID"
            except KeyError:
                status, exclusion = "MISSING_REQUIRED_SOURCE_FIELD", "MISSING_REQUIRED_SOURCE_FIELD"
            except Exception as exc:  # Technical readability only; preserve blocker class.
                status, exclusion = "UNREADABLE", f"UNREADABLE:{type(exc).__name__}"
            used_exploratory = identity.source_episode_id in historical["exploratory"]
            used_calibration = identity.source_episode_id in historical["calibration_combined"]
            used_diagnostic = identity.source_episode_id in historical["design_diagnostic"]
            historical_overlap = used_exploratory or used_calibration or used_diagnostic
            if status == "READABLE" and historical_overlap:
                eligibility, exclusion = "EXCLUDED", "HISTORICAL_EPISODE_USAGE"
            elif status == "READABLE":
                eligibility = "ELIGIBLE"
            else:
                eligibility = "EXCLUDED"
            rows.append({
                "episode_id": identity.source_episode_id, "frame_count": frame_count,
                "duration_seconds_if_available": frame_count / SAMPLE_HZ,
                "source_identity": source_identity, "readability_status": status,
                "used_in_exploratory": "YES" if used_exploratory else "NO",
                "used_in_calibration": "YES" if used_calibration else "NO",
                "used_in_diagnostic": "YES" if used_diagnostic else "NO",
                "disjoint_from_exploratory": "NO" if used_exploratory else "YES",
                "disjoint_from_calibration_seed": "NO" if identity.source_episode_id in historical["calibration_seed"] else "YES",
                "disjoint_from_calibration_fresh": "NO" if identity.source_episode_id in historical["calibration_fresh"] else "YES",
                "disjoint_from_design_diagnostic": "NO" if used_diagnostic else "YES",
                "eligibility_status": eligibility, "exclusion_reason": exclusion,
            })
    finally:
        close = getattr(adapter, "close", None)
        if close:
            close()
    dataset = {
        "dataset_id": DATASET_ID, "raw_hdf5_sha256": raw_hash,
        "low_dim_hdf5_sha256": low_hash, "source_identity": source_identity,
        "sample_hz": SAMPLE_HZ,
    }
    return rows, dataset


def stable_digest(episode_id: str) -> str:
    return hashlib.sha256(f"{SELECTION_SALT}|{episode_id}".encode("utf-8")).hexdigest()


def assign_duration_strata(eligible: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ordered = sorted(eligible, key=lambda r: (int(r["frame_count"]), str(r["episode_id"])))
    n = len(ordered)
    if n < 3:
        raise EvaluationManifestPreparationError("eligible pool too small for duration stratification")
    first_cut = n // 3
    second_cut = 2 * n // 3
    enriched = []
    for index, original in enumerate(ordered):
        row = dict(original)
        row["duration_stratum"] = "SHORT" if index < first_cut else ("MEDIUM" if index < second_cut else "LONG")
        enriched.append(row)
    definition = {
        "method": "rank terciles over (frame_count ASC, episode_id ASC)",
        "short_rank_range": [1, first_cut], "medium_rank_range": [first_cut + 1, second_cut],
        "long_rank_range": [second_cut + 1, n],
        "short_max_frames": enriched[first_cut - 1]["frame_count"],
        "medium_max_frames": enriched[second_cut - 1]["frame_count"],
    }
    return enriched, definition


def deterministic_rankings(eligible: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    enriched, strata_definition = assign_duration_strata(eligible)
    pure_hash = sorted(enriched, key=lambda r: (stable_digest(str(r["episode_id"])), str(r["episode_id"])))
    buckets = {
        name: sorted((r for r in enriched if r["duration_stratum"] == name),
                     key=lambda r: (stable_digest(str(r["episode_id"])), str(r["episode_id"])))
        for name in ("SHORT", "MEDIUM", "LONG")
    }
    stratified = []
    position = 0
    while any(position < len(bucket) for bucket in buckets.values()):
        for name in ("SHORT", "MEDIUM", "LONG"):
            if position < len(buckets[name]):
                stratified.append(buckets[name][position])
        position += 1
    return stratified, pure_hash, strata_definition


def manifest_rows(ranking: Sequence[Mapping[str, Any]], count: int, method: str) -> list[dict[str, Any]]:
    if len(ranking) < count:
        raise EvaluationManifestPreparationError(f"eligible pool {len(ranking)} smaller than option {count}")
    return [{
        "manifest_candidate_version": MANIFEST_CANDIDATE_VERSION,
        "episode_id": row["episode_id"], "selection_method": method,
        "selection_rank": index, "frame_count": row["frame_count"],
        "duration_seconds": row["duration_seconds_if_available"],
        "source_identity": row["source_identity"], "duration_stratum": row["duration_stratum"],
    } for index, row in enumerate(ranking[:count], 1)]


def audit_disjointness(options: Mapping[str, Sequence[Mapping[str, Any]]], historical: Mapping[str, set[str]]) -> dict[str, Any]:
    audit = {"proposals": {}}
    all_valid = True
    for name, rows in options.items():
        ids = {str(row["episode_id"]) for row in rows}
        counts = {
            "OVERLAP_WITH_EXPLORATORY": len(ids & historical["exploratory"]),
            "OVERLAP_WITH_CALIBRATION_SEED": len(ids & historical["calibration_seed"]),
            "OVERLAP_WITH_CALIBRATION_FRESH": len(ids & historical["calibration_fresh"]),
            "OVERLAP_WITH_CALIBRATION_COMBINED": len(ids & historical["calibration_combined"]),
            "OVERLAP_WITH_DESIGN_DIAGNOSTIC": len(ids & historical["design_diagnostic"]),
        }
        valid = all(value == 0 for value in counts.values())
        audit["proposals"][name] = {**counts, "status": "VALID" if valid else "INVALID"}
        all_valid = all_valid and valid
    audit["DISJOINTNESS_AUDIT"] = "PASS" if all_valid else "FAIL"
    return audit


def _hash_rows(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    payload = "\n".join("|".join(str(row.get(field, "")) for field in fields) for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def prepare_immutable_temp(output: Path) -> Path:
    temp = output.parent / (".tmp-" + output.name)
    if output.exists() or temp.exists():
        raise EvaluationManifestPreparationError("immutable output run already exists")
    temp.mkdir(parents=True, exist_ok=False)
    return temp


def workload(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    frames = sum(int(row["frame_count"]) for row in rows)
    seconds = sum(float(row["duration_seconds"]) for row in rows)
    minutes = seconds / 60.0
    estimated = minutes * 2.0 + len(rows) * 2.0
    return {
        "episode_count": len(rows), "total_frames": frames, "total_duration_seconds": seconds,
        "total_duration_minutes": minutes,
        "estimated_manual_audit_workload_minutes": estimated,
        "workload_formula": "2x video duration + 2 minutes navigation/setup per episode; no detector outcomes used",
    }


def run_manifest_preparation(*, project_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(project_root or PROJECT2_ROOT).resolve()
    historical, source_sets = load_historical_sets(root)
    historical_rows = historical_usage_rows(historical, source_sets)
    pool, dataset = scan_dataset(root, historical)
    eligible = [row for row in pool if row["eligibility_status"] == "ELIGIBLE"]
    stratified, pure_hash, strata = deterministic_rankings(eligible)
    hash_rank = {row["episode_id"]: i for i, row in enumerate(pure_hash, 1)}
    strat_rank = {row["episode_id"]: i for i, row in enumerate(stratified, 1)}
    stratum = {row["episode_id"]: row["duration_stratum"] for row in stratified}
    for row in pool:
        row["duration_stratum"] = stratum.get(row["episode_id"], "")
        row["stable_hash_rank"] = hash_rank.get(row["episode_id"], "")
        row["duration_stratified_rank"] = strat_rank.get(row["episode_id"], "")
    method = "DURATION_TERCILE_ROUND_ROBIN_WITHIN_STRATUM_SHA256"
    options = {name: manifest_rows(stratified, count, method) for name, count in OPTION_COUNTS.items()}
    hash_proposal = manifest_rows(pure_hash, OPTION_COUNTS["large"], "GLOBAL_EPISODE_ID_SHA256")
    stratified_proposal = manifest_rows(stratified, OPTION_COUNTS["large"], method)
    audit = audit_disjointness(options, historical)
    if audit["DISJOINTNESS_AUDIT"] != "PASS":
        raise EvaluationManifestPreparationError("manifest candidate disjointness failed")
    if not (set(r["episode_id"] for r in options["small"]) < set(r["episode_id"] for r in options["medium"]) < set(r["episode_id"] for r in options["large"])):
        raise EvaluationManifestPreparationError("nested option contract failed")
    leakage = {
        "human_label_used": False, "evaluation_gt_used": False,
        "frozen_config_score_used": False, "fp_fn_used": False,
        "error_mode_used": False, "result_based_cherry_pick_used": False,
        "formal_evaluation_executed": False, "human_audit_started": False,
        "LEAKAGE_AUDIT": "PASS",
    }
    option_workloads = {name: workload(rows) for name, rows in options.items()}
    summary = {
        **dataset, "total_dataset_episodes": len(pool),
        "historical_unique_episodes": len(historical_rows),
        "exploratory_episodes": len(historical["exploratory"]),
        "calibration_seed_episodes": len(historical["calibration_seed"]),
        "calibration_fresh_episodes": len(historical["calibration_fresh"]),
        "calibration_combined_episodes": len(historical["calibration_combined"]),
        "design_diagnostic_episodes": len(historical["design_diagnostic"]),
        "eligible_evaluation_pool": len(eligible),
        "unreadable_or_schema_invalid": sum(row["readability_status"] != "READABLE" for row in pool),
        "options": option_workloads, "disjointness_audit": "PASS", "leakage_audit": "PASS",
        "EVALUATION_EPISODE_COUNT": "OWNER_DECISION_PENDING",
        "EVALUATION_MANIFEST_FROZEN": False, "FORMAL_EVALUATION_RUN_ALLOWED": False,
        "READY_FOR_DESIGN_OWNER_EVALUATION_MANIFEST_REVIEW": True,
    }
    provenance = {
        "manifest_candidate_version": MANIFEST_CANDIDATE_VERSION,
        "eligible_pool_hash": _hash_rows(sorted(eligible, key=lambda r: r["episode_id"]),
                                          ("episode_id", "frame_count", "source_identity")),
        "historical_exclusion_set_hash": hashlib.sha256("\n".join(sorted(r["episode_id"] for r in historical_rows)).encode()).hexdigest(),
        "selection_algorithm": method, "hash_algorithm": "SHA256",
        "hash_input": f"{SELECTION_SALT}|<episode_id>",
        "sorting_rule": "within each duration rank-tercile: digest ASC, episode_id ASC; interleave SHORT,MEDIUM,LONG",
        "duration_strata_definition": strata, "dataset_identity": dataset,
        "option_counts_are_proposals_not_frozen": OPTION_COUNTS,
        "historical_source_artifacts": sorted(source_sets),
        "skipped_for_historical_overlap": sorted(set().union(*historical.values())),
    }
    now = datetime.now().astimezone()
    run_id = "g1_p4_eval_manifest_prep_" + now.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    output = root / "outputs/g1_p4_evaluation_manifest_preparation" / run_id
    temp = prepare_immutable_temp(output)
    _write_csv(temp / "historical_episode_usage.csv", HISTORICAL_FIELDS, historical_rows)
    _write_csv(temp / "eligible_evaluation_pool.csv", POOL_FIELDS, pool)
    for name, rows in options.items():
        _write_csv(temp / f"evaluation_manifest_option_{name}.csv", MANIFEST_FIELDS, rows)
    _write_csv(temp / "duration_stratified_proposal.csv", MANIFEST_FIELDS, stratified_proposal)
    _write_csv(temp / "hash_deterministic_proposal.csv", MANIFEST_FIELDS, hash_proposal)
    (temp / "manifest_candidate_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    (temp / "evaluation_manifest_disjointness_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    (temp / "evaluation_manifest_leakage_audit.json").write_text(json.dumps(leakage, indent=2) + "\n", encoding="utf-8")
    (temp / "dataset_pool_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (temp / "run_meta.json").write_text(json.dumps({
        "run_id": run_id, "created_at": now.isoformat(), "task": "EVALUATION_MANIFEST_PREPARATION_ONLY",
        "dataset_identity": dataset, "selection_algorithm": method,
        "segmentation_executed": False, "scoring_executed": False,
        "evaluation_gt_accessed": False, "human_review_started": False,
        "EVALUATION_MANIFEST_FROZEN": False, "FORMAL_EVALUATION_RUN_ALLOWED": False,
    }, indent=2) + "\n", encoding="utf-8")
    os.rename(temp, output)
    return {"summary": summary, "output_run": str(output), "options": options,
            "audit": audit, "leakage": leakage, "provenance": provenance}
