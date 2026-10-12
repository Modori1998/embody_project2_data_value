"""Deterministic Development-pool construction for the G3 Phase-1 probe.

The Development pool is every readable dataset episode that is **not** reserved
by any frozen Formal artifact:

    Development pool =
        readable dataset episodes
        - HISTORICAL_G1 episodes (exploratory + calibration + design diagnostic)
        - FROZEN_G1_EVALUATION episodes (24, deferred independent evaluation)
        - FROZEN_CORE_RETRIEVAL episodes (63 = 36 candidate bank + 9 calibration + 18 final)

No query, candidate, human label, embedding, or retrieval score is consulted.
Selection is a pure function of the dataset identity and a fixed salt.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from project2_g1.evaluation_manifest_preparation import (
    DATASET_ID,
    historical_usage_rows,
    load_historical_sets,
    scan_dataset,
)
from project2_g1.paths import PROJECT2_ROOT
from project2_mvp.retrieval_manifest_preparation import load_frozen_g1_evaluation

PROBE_SALT = "P2_G3_PHASE1_PROBE_20261012"
PROBE_MANIFEST_VERSION = "P2_G3_PHASE1_DEV_PROBE_MANIFEST_v1"
STRATA = ("SHORT", "MEDIUM", "LONG")
DEFAULT_PER_STRATUM = 4

FROZEN_CORE_RETRIEVAL_RELATIVE_PATH = Path(
    "0-doc/10-design-review/"
    "Project2_MVP_Core_Retrieval_Manifest_FROZEN_v1_20261009.csv"
)


class DevelopmentPoolError(ValueError):
    pass


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_frozen_core_retrieval_ids(root: Path) -> tuple[set[str], dict[str, Any]]:
    """Load the 63 reserved Formal Core Retrieval episodes (read-only)."""

    path = root / FROZEN_CORE_RETRIEVAL_RELATIVE_PATH
    rows = _read_csv(path)
    ids = [str(row["episode_id"]) for row in rows]
    cohorts = Counter(str(row["cohort"]) for row in rows)
    expected = {"CANDIDATE_BANK": 36, "CALIBRATION_QUERY": 9, "FINAL_QUERY": 18}
    if dict(cohorts) != expected:
        raise DevelopmentPoolError(
            f"STOP_FROZEN_CORE_RETRIEVAL_COHORT_MISMATCH: {dict(cohorts)}"
        )
    if len(set(ids)) != 63:
        raise DevelopmentPoolError(
            f"STOP_FROZEN_CORE_RETRIEVAL_COUNT_MISMATCH: unique={len(set(ids))}"
        )
    provenance = {
        "source_artifact": FROZEN_CORE_RETRIEVAL_RELATIVE_PATH.as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "count": len(ids),
        "cohorts": dict(cohorts),
    }
    return set(ids), provenance


def probe_digest(episode_id: str) -> str:
    return hashlib.sha256(f"{PROBE_SALT}|{episode_id}".encode("utf-8")).hexdigest()


def build_development_pool(root: str | Path | None = None) -> dict[str, Any]:
    """Build the Development pool with explicit exclusion provenance."""

    project_root = Path(root or PROJECT2_ROOT).resolve()
    historical, _source_sets = load_historical_sets(project_root)
    historical_rows = historical_usage_rows(historical, _source_sets)
    historical_ids = {str(row["episode_id"]) for row in historical_rows}

    _frozen_rows, frozen_eval_ids, frozen_eval_provenance = load_frozen_g1_evaluation(project_root)
    frozen_retrieval_ids, frozen_retrieval_provenance = load_frozen_core_retrieval_ids(project_root)

    pool, dataset = scan_dataset(project_root, historical)

    dev_rows: list[dict[str, Any]] = []
    for row in pool:
        episode_id = str(row["episode_id"])
        readable = row["readability_status"] == "READABLE"
        reasons: list[str] = []
        if not readable:
            reasons.append(str(row.get("exclusion_reason") or row["readability_status"]))
        if episode_id in historical_ids:
            reasons.append("HISTORICAL_G1_USAGE")
        if episode_id in frozen_eval_ids:
            reasons.append("FROZEN_G1_EVALUATION")
        if episode_id in frozen_retrieval_ids:
            reasons.append("FROZEN_CORE_RETRIEVAL")
        in_dev_pool = not reasons
        dev_rows.append({
            "episode_id": episode_id,
            "frame_count": int(row["frame_count"]),
            "duration_seconds": float(row["duration_seconds_if_available"]),
            "source_identity": str(row["source_identity"]),
            "readability_status": str(row["readability_status"]),
            "development_pool_member": "YES" if in_dev_pool else "NO",
            "exclusion_reasons": "|".join(reasons),
        })

    members = [row for row in dev_rows if row["development_pool_member"] == "YES"]
    if not members:
        raise DevelopmentPoolError("STOP_DEVELOPMENT_POOL_EMPTY")

    summary = {
        "dataset_id": DATASET_ID,
        "dataset_identity": dataset,
        "total_dataset_episodes": len(dev_rows),
        "historical_g1_unique": len(historical_ids),
        "frozen_g1_evaluation": len(frozen_eval_ids),
        "frozen_core_retrieval": len(frozen_retrieval_ids),
        "development_pool_size": len(members),
        "unreadable_or_schema_invalid": sum(
            row["readability_status"] != "READABLE" for row in dev_rows
        ),
        "frozen_g1_evaluation_provenance": frozen_eval_provenance,
        "frozen_core_retrieval_provenance": frozen_retrieval_provenance,
        "overlap_historical_vs_frozen_eval": sorted(historical_ids & frozen_eval_ids),
        "overlap_historical_vs_frozen_retrieval": sorted(historical_ids & frozen_retrieval_ids),
        "overlap_frozen_eval_vs_frozen_retrieval": sorted(frozen_eval_ids & frozen_retrieval_ids),
    }
    return {"rows": dev_rows, "members": members, "summary": summary}


def assign_probe_strata(members: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Duration terciles computed over the Development pool only."""

    ordered = sorted(members, key=lambda row: (int(row["frame_count"]), str(row["episode_id"])))
    n = len(ordered)
    if n < 3 * DEFAULT_PER_STRATUM:
        raise DevelopmentPoolError(f"STOP_DEVELOPMENT_POOL_TOO_SMALL: {n}")
    first_cut = n // 3
    second_cut = (2 * n) // 3
    enriched: list[dict[str, Any]] = []
    for index, original in enumerate(ordered):
        row = dict(original)
        row["duration_stratum"] = (
            "SHORT" if index < first_cut else "MEDIUM" if index < second_cut else "LONG"
        )
        row["duration_rank"] = index + 1
        row["probe_digest"] = probe_digest(str(row["episode_id"]))
        enriched.append(row)
    return enriched


def select_probe_episodes(
    stratified: Sequence[Mapping[str, Any]],
    *,
    per_stratum: int = DEFAULT_PER_STRATUM,
) -> list[dict[str, Any]]:
    """Pick ``per_stratum`` episodes from each duration tercile by digest order."""

    selected: list[dict[str, Any]] = []
    for stratum in STRATA:
        ranked = sorted(
            (row for row in stratified if row["duration_stratum"] == stratum),
            key=lambda row: (str(row["probe_digest"]), str(row["episode_id"])),
        )
        if len(ranked) < per_stratum:
            raise DevelopmentPoolError(
                f"STOP_INSUFFICIENT_STRATUM: stratum={stratum} count={len(ranked)}"
            )
        for rank, source in enumerate(ranked[:per_stratum], 1):
            selected.append({
                "probe_manifest_version": PROBE_MANIFEST_VERSION,
                "selection_salt": PROBE_SALT,
                "duration_stratum": stratum,
                "stratum_rank": rank,
                "episode_id": str(source["episode_id"]),
                "frame_count": int(source["frame_count"]),
                "duration_seconds": float(source["duration_seconds"]),
                "probe_digest": str(source["probe_digest"]),
            })
    return selected


def build_probe_selection(root: str | Path | None = None) -> dict[str, Any]:
    pool = build_development_pool(root)
    stratified = assign_probe_strata(pool["members"])
    selected = select_probe_episodes(stratified)
    ids = [row["episode_id"] for row in selected]
    if len(set(ids)) != len(ids):
        raise DevelopmentPoolError("STOP_PROBE_SELECTION_NOT_UNIQUE")
    return {
        "summary": pool["summary"],
        "pool_rows": pool["rows"],
        "selected": selected,
        "selection_salt": PROBE_SALT,
        "selection_rule": (
            "duration terciles over Development pool (frame_count ASC, episode_id ASC); "
            f"within each stratum rank by SHA256('{PROBE_SALT}|' + episode_id); "
            f"take first {DEFAULT_PER_STRATUM} per stratum"
        ),
        "selected_count": len(selected),
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
