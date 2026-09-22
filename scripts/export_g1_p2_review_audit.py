"""Export every human P2 (predicted-boundary) review into one audit table.

Scope
-----
The G1 Audit Web keeps human review in an append-only SQLite store split
across two tabs:

* ``P1`` = per-signal review (``signal_review_history``)
* ``P2`` = per-boundary review (``predicted_boundary_review_history``)

Only the P2 side carries discriminating information, so this exporter
consolidates **P2 only** across every registered run into a single table that
follows the frozen ``predicted_boundary_review.csv`` export schema
(``P2_G1_HUMAN_CALIBRATION_EXPORT_V1``) plus the run provenance columns needed
to keep the runs apart.

The append-only store may hold several revisions of the same
``(run_id, episode_id, boundary_id)`` key; only the row with the highest
``review_id`` (the current value) is exported, and ``effective_review_id``
records which revision that was.

Nothing here unblinds or analyses the review outcome: the table carries no
arm / P12 / C12 / coherence / matching column, and no REDUNDANT-rate or gate
verdict is computed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

OWNER_DB_RELPATH = "outputs/g1_audit_web/g1_audit_web_owner.sqlite3"
REGISTRY_RELPATH = "outputs/g1_audit_web/g1_audit_run_registry.json"
OUTPUT_DIR_RELPATH = "outputs/g1_audit_web/p2_review_audit"

TABLE_NAME = "p2_review_audit.csv"
META_NAME = "p2_review_audit_meta.json"

# Stage order is chronological by construction, so sorting by it reads as a
# review history rather than an arbitrary alphabetical list.
STAGE_ORDER = ("EXPLORATORY_AUDIT", "CALIBRATION", "DESIGN_DIAGNOSTIC")

FIELDS = (
    "run_stage",
    "source_run_id",
    "diagnostic_set_id",
    "episode_id",
    "boundary_id",
    "predicted_frame",
    "candidate_type",
    "representative_candidate_id",
    "member_candidate_ids",
    "member_candidate_types",
    "member_candidate_frames",
    "member_candidate_count",
    "human_decision",
    "reason_code",
    "corrected_frame",
    "comment",
    "effective_review_id",
    "reviewer",
    "reviewed_at",
)

# ``source_run_id`` / ``episode_id`` / ``boundary_id`` / ``predicted_frame`` /
# ``human_decision`` / ... mirror the frozen export schema
# (P2_G1_HUMAN_CALIBRATION_EXPORT_V1) so downstream tooling reads either file
# the same way. ``run_stage`` and ``diagnostic_set_id`` are added here because
# this table spans several runs at once, and the frozen schema only ever
# described a single-source export.

BOUNDARY_CONTEXT_FIELDS = (
    "candidate_type",
    "representative_candidate_id",
    "member_candidate_ids",
    "member_candidate_types",
    "member_candidate_frames",
    "member_candidate_count",
)


class ReviewAuditError(RuntimeError):
    """Raised when the audit table cannot be built safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    """Write the audit table as UTF-8 **with BOM**.

    The table exists to be opened in a spreadsheet by a human auditor and it
    carries Chinese review comments. Without a BOM, spreadsheet apps routinely
    mis-decode those cells, so the BOM is deliberate here. Line endings stay
    ``\\n`` and quoting stays RFC-4180, matching the rest of the repo.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def load_registry(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        raise ReviewAuditError(f"registry not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return dict(payload.get("runs") or {})


def current_p2_reviews(db_path: Path) -> list[dict[str, Any]]:
    """Current (highest review_id) P2 review row per review key."""

    if not db_path.is_file():
        raise ReviewAuditError(f"owner review store not found: {db_path}")
    uri = f"file:{db_path.as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT h.*
            FROM predicted_boundary_review_history h
            JOIN (
                SELECT run_id, episode_id, boundary_id, MAX(review_id) AS review_id
                FROM predicted_boundary_review_history
                GROUP BY run_id, episode_id, boundary_id
            ) latest
              ON latest.review_id = h.review_id
            ORDER BY h.run_id, h.episode_id, h.predicted_frame, h.boundary_id
            """
        ).fetchall()
    finally:
        con.close()
    return [dict(row) for row in rows]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def boundary_context(run_root: Path) -> tuple[dict[str, dict[str, str]], tuple[str, ...]]:
    """``(boundary_id -> frozen Detector context, columns)`` for one run folder.

    Older runs predate the frozen ``MATERIALIZED_V1`` schema, so the column set
    is reported rather than assumed: a legacy run legitimately has no
    ``representative_candidate_id`` / ``member_candidate_*`` columns, and the
    audit table shows those cells empty.
    """

    manifest = run_root / "episode_manifest.csv"
    if not manifest.is_file():
        raise ReviewAuditError(f"episode_manifest.csv not found under {run_root}")
    context: dict[str, dict[str, str]] = {}
    columns: tuple[str, ...] = ()
    for row in _read_csv(manifest):
        relpath = str(row.get("boundaries_relpath") or "")
        if not relpath:
            continue
        path = run_root / relpath
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not columns:
                columns = tuple(reader.fieldnames or ())
            for boundary in reader:
                boundary_id = str(boundary.get("boundary_id") or "")
                if boundary_id:
                    context[boundary_id] = boundary
    return context, columns


def run_diagnostic_set_id(run_root: Path) -> str:
    meta = run_root / "run_meta.json"
    if not meta.is_file():
        return ""
    try:
        payload = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return str(payload.get("diagnostic_set_id") or "")


def build_table(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registry = load_registry(root / REGISTRY_RELPATH)
    reviews = current_p2_reviews(root / OWNER_DB_RELPATH)

    context_cache: dict[str, dict[str, dict[str, str]]] = {}
    schema_cache: dict[str, tuple[str, ...]] = {}
    set_id_cache: dict[str, str] = {}
    unreadable: list[dict[str, str]] = []

    def context_for(run_id: str) -> dict[str, dict[str, str]]:
        if run_id in context_cache:
            return context_cache[run_id]
        info = registry.get(run_id)
        if info is None:
            context_cache[run_id] = {}
            schema_cache[run_id] = ()
            return context_cache[run_id]
        run_root = Path(str(info.get("audit_folder_path") or ""))
        try:
            context_cache[run_id], schema_cache[run_id] = boundary_context(run_root)
        except (ReviewAuditError, OSError) as exc:
            unreadable.append({"run_id": run_id, "reason": str(exc)})
            context_cache[run_id] = {}
            schema_cache[run_id] = ()
        return context_cache[run_id]

    rows: list[dict[str, Any]] = []
    missing_context: list[str] = []
    for review in reviews:
        run_id = str(review["run_id"])
        boundary_id = str(review["boundary_id"])
        info = registry.get(run_id) or {}
        if run_id not in set_id_cache:
            run_root = Path(str(info.get("audit_folder_path") or ""))
            try:
                set_id_cache[run_id] = run_diagnostic_set_id(run_root)
            except OSError:
                set_id_cache[run_id] = ""
        context = context_for(run_id).get(boundary_id)
        if context is None and run_id not in {item["run_id"] for item in unreadable}:
            missing_context.append(f"{run_id}:{boundary_id}")

        row: dict[str, Any] = {
            "run_stage": str(info.get("run_stage") or ""),
            "source_run_id": run_id,
            "diagnostic_set_id": set_id_cache.get(run_id, ""),
            "episode_id": str(review["episode_id"]),
            "boundary_id": boundary_id,
            "predicted_frame": review["predicted_frame"],
            "human_decision": str(review["decision"]),
            "reason_code": str(review.get("reason_code") or ""),
            "corrected_frame": (
                "" if review.get("corrected_frame") is None else review["corrected_frame"]
            ),
            "comment": str(review.get("comment") or ""),
            "effective_review_id": review["review_id"],
            "reviewer": str(review["reviewer"]),
            "reviewed_at": str(review["reviewed_at"]),
        }
        for name in BOUNDARY_CONTEXT_FIELDS:
            row[name] = "" if context is None else str(context.get(name) or "")
        rows.append(row)

    rows.sort(
        key=lambda item: (
            STAGE_ORDER.index(item["run_stage"])
            if item["run_stage"] in STAGE_ORDER
            else len(STAGE_ORDER),
            item["run_stage"],
            item["source_run_id"],
            item["episode_id"],
            int(item["predicted_frame"]),
            item["boundary_id"],
        )
    )

    # ---- completeness: reviewed vs the run's own boundary universe ----------
    per_run: list[dict[str, Any]] = []
    for run_id, info in registry.items():
        reviewed = [row for row in rows if row["source_run_id"] == run_id]
        run_root = Path(str(info.get("audit_folder_path") or ""))
        universe = None
        try:
            universe = len(context_for(run_id))
        except (ReviewAuditError, OSError) as exc:
            if not any(item["run_id"] == run_id for item in unreadable):
                unreadable.append({"run_id": run_id, "reason": str(exc)})
        if any(item["run_id"] == run_id for item in unreadable):
            # The run folder could not be read, so its boundary universe is
            # unknown -- report null rather than a misleading 0.
            universe = None
        counts: dict[str, int] = {}
        for row in reviewed:
            counts[row["human_decision"]] = counts.get(row["human_decision"], 0) + 1
        per_run.append(
            {
                "run_id": run_id,
                "run_stage": str(info.get("run_stage") or ""),
                "boundaries_in_run": universe,
                "reviewed_rows": len(reviewed),
                "episodes_reviewed": len({row["episode_id"] for row in reviewed}),
                "decision_counts": dict(sorted(counts.items())),
                "boundary_table_columns": list(schema_cache.get(run_id, ())),
            }
        )
    per_run.sort(key=lambda item: (item["run_stage"], item["run_id"]))

    totals: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for row in rows:
        totals[row["human_decision"]] = totals.get(row["human_decision"], 0) + 1
        if row["reason_code"]:
            reasons[row["reason_code"]] = reasons.get(row["reason_code"], 0) + 1

    meta = {
        "export_contract": "P2_G1_REVIEW_AUDIT_TABLE_V1",
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "scope": {
            "tabs_included": ["P2"],
            "tabs_excluded": ["P1"],
            "note": (
                "P2 = per-boundary human review. P1 (per-signal) rows are "
                "excluded by request; they are uniformly PASS and carry no "
                "discriminating information."
            ),
            "runs": "all runs registered in the G1 Audit Web registry",
        },
        "blinding": {
            "unblinded": False,
            "arm_or_cohort_column_present": False,
            "redundant_rate_computed": False,
            "gate_verdict_computed": False,
        },
        "source_owner_db": OWNER_DB_RELPATH,
        "source_owner_db_sha256": _sha256(root / OWNER_DB_RELPATH),
        "source_registry": REGISTRY_RELPATH,
        "source_registry_sha256": _sha256(root / REGISTRY_RELPATH),
        "table_encoding": "utf-8-sig",
        "table_encoding_note": (
            "UTF-8 with BOM so spreadsheet apps decode the Chinese review "
            "comments correctly; rows and quoting are otherwise plain CSV."
        ),
        "row_count": len(rows),
        "episode_count": len({(row["source_run_id"], row["episode_id"]) for row in rows}),
        "run_count": len({row["source_run_id"] for row in rows}),
        "decision_counts": dict(sorted(totals.items())),
        "reason_code_counts": dict(sorted(reasons.items())),
        "per_run": per_run,
        "legacy_schema_runs": [
            item["run_id"]
            for item in per_run
            if item["boundary_table_columns"]
            and "representative_candidate_id" not in item["boundary_table_columns"]
        ],
        "unreadable_runs": unreadable,
        "reviews_missing_boundary_context": sorted(set(missing_context)),
    }
    return rows, meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)

    root = Path(args.project_root).resolve()
    out_dir = Path(args.output_dir) if args.output_dir else root / OUTPUT_DIR_RELPATH

    try:
        rows, meta = build_table(root)
    except ReviewAuditError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    table_path = out_dir / TABLE_NAME
    _write_csv(table_path, FIELDS, rows)
    meta["files_sha256"] = {TABLE_NAME: _sha256(table_path)}
    (out_dir / META_NAME).write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print("=" * 74)
    print("G1 HUMAN REVIEW AUDIT TABLE (P2 only)")
    print("=" * 74)
    print(f"table           = {table_path}")
    print(f"rows            = {len(rows)}")
    print(f"runs            = {meta['run_count']}")
    print(f"episodes        = {meta['episode_count']}")
    print(f"decisions       = {meta['decision_counts']}")
    print(f"reason_codes    = {meta['reason_code_counts']}")
    if meta["unreadable_runs"]:
        print(f"unreadable_runs = {[item['run_id'] for item in meta['unreadable_runs']]}")
    if meta["reviews_missing_boundary_context"]:
        print(f"missing_context = {len(meta['reviews_missing_boundary_context'])}")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
