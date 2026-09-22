"""Export the full append-only review history of the G1-P3 DESIGN_DIAGNOSTIC set.

Scope
-----
This is the ``POST_UNBLIND_EVIDENCE`` freeze for the 20 diagnostic events
selected by ``02_selection_internal.csv``.

Unlike ``export_g1_p2_review_audit.py`` -- which exports only the *current*
(highest ``review_id``) value of every reviewed boundary -- this exporter keeps
**every** revision in ``predicted_boundary_review_history``, so the first
blinded review and the later owner unblinded adjudication are both preserved
side by side.

``review_phase`` is derived from the stored provenance only, never guessed
from timestamps:

```text
reviewer = DESIGN_OWNER            -> FIRST_BLINDED_REVIEW
reviewer = DESIGN_OWNER_UNBLINDED  -> OWNER_UNBLINDED_ADJUDICATION
```

An unknown reviewer is a hard error: this file is an evidence freeze, so a
provenance value nobody has classified must not be silently exported.

Guarantees
----------
* read-only: the SQLite file is opened with ``mode=ro`` and never written;
* no label is computed, no detector / protocol / threshold is touched;
* deterministic output: fixed column order, fixed sort order, UTF-8 (no BOM),
  LF line endings, so the file can be rebuilt byte-for-byte from the
  production SQLite plus ``02_selection_internal.csv``.

``arm`` / ``pair_id`` / ``P12`` / ``C12`` are joined from
``02_selection_internal.csv`` -- they are *not* read from the human review
database.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sqlite3
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RUN_ID = "g1_design_diagnostic_20260922_135647_69bf2a94"

SET_RELPATH = "0-doc/80-audit-local/g1_p3_trajectory_mechanism_validation"
SELECTION_RELPATH = f"{SET_RELPATH}/02_selection_internal.csv"
OUTPUT_RELPATH = f"{SET_RELPATH}/05_review_history.csv"
OWNER_DB_RELPATH = "outputs/g1_audit_web/g1_audit_web_owner.sqlite3"

# ``review_phase`` is a pure function of the stored reviewer identity.
PHASE_BY_REVIEWER = {
    "DESIGN_OWNER": "FIRST_BLINDED_REVIEW",
    "DESIGN_OWNER_UNBLINDED": "OWNER_UNBLINDED_ADJUDICATION",
}

EXPECTED_EVENT_COUNT = 20
EXPECTED_DISTINCT_EPISODE_COUNT = 20
EXPECTED_PAIR_COUNT = 10
EXPECTED_ARM_COUNTS = {"A": 10, "B": 10}

FIELDS = (
    "diagnostic_event_id",
    "episode_id",
    "boundary_id",
    "event_frame",
    "arm",
    "pair_id",
    "P12",
    "C12",
    "review_id",
    "reviewer",
    "reviewed_at",
    "human_decision",
    "reason_code",
    "corrected_frame",
    "comment",
    "review_phase",
)

#: Sort order, stated once so the file is reproducible.
SORT_KEY = ("diagnostic_event_id", "review_id")

SELECTION_FIELDS = (
    "diagnostic_event_id",
    "arm",
    "pair_id",
    "episode_id",
    "event_frame",
    "boundary_id",
    "P12",
    "C12",
)


class ReviewHistoryError(RuntimeError):
    """Raised when the evidence freeze cannot be produced safely."""


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def load_selection(path: Path) -> list[dict[str, str]]:
    """Read the authoritative 20-event universe and validate its shape."""

    if not path.is_file():
        raise ReviewHistoryError(f"selection file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [name for name in SELECTION_FIELDS if name not in (reader.fieldnames or [])]
        if missing:
            raise ReviewHistoryError(f"selection file lacks columns: {missing}")
        rows = [{name: _text(row.get(name)) for name in SELECTION_FIELDS} for row in reader]

    if len(rows) != EXPECTED_EVENT_COUNT:
        raise ReviewHistoryError(
            f"EVENT_COUNT = {len(rows)}, expected {EXPECTED_EVENT_COUNT}"
        )
    episodes = {row["episode_id"] for row in rows}
    if len(episodes) != EXPECTED_DISTINCT_EPISODE_COUNT:
        raise ReviewHistoryError(
            f"DISTINCT_EPISODE_COUNT = {len(episodes)}, "
            f"expected {EXPECTED_DISTINCT_EPISODE_COUNT}"
        )
    pairs = {row["pair_id"] for row in rows}
    if len(pairs) != EXPECTED_PAIR_COUNT:
        raise ReviewHistoryError(
            f"PAIR_COUNT = {len(pairs)}, expected {EXPECTED_PAIR_COUNT}"
        )
    arm_counts = {arm: sum(1 for row in rows if row["arm"] == arm) for arm in ("A", "B")}
    if arm_counts != EXPECTED_ARM_COUNTS:
        raise ReviewHistoryError(f"arm counts = {arm_counts}, expected {EXPECTED_ARM_COUNTS}")

    keys = [(row["episode_id"], row["boundary_id"]) for row in rows]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise ReviewHistoryError(f"duplicate join keys: {duplicates}")
    if any(not row["diagnostic_event_id"] for row in rows):
        raise ReviewHistoryError("selection file has an empty diagnostic_event_id")
    return rows


def load_history(db_path: Path, selection: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Read every revision for the 20 selected boundaries (read-only)."""

    if not db_path.is_file():
        raise ReviewHistoryError(f"owner review database not found: {db_path}")
    wanted = {(row["episode_id"], row["boundary_id"]) for row in selection}
    uri = f"file:{db_path.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT review_id, run_id, episode_id, boundary_id, predicted_frame, "
            "decision, reason_code, corrected_frame, comment, reviewer, reviewed_at "
            "FROM predicted_boundary_review_history WHERE run_id = ? ORDER BY review_id",
            (RUN_ID,),
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows if (row["episode_id"], row["boundary_id"]) in wanted]


def build_rows(
    selection: list[dict[str, str]], history: list[dict[str, Any]]
) -> list[dict[str, str]]:
    """Join the selection metadata onto each history revision."""

    meta = {(row["episode_id"], row["boundary_id"]): row for row in selection}
    rows: list[dict[str, str]] = []
    for record in history:
        key = (record["episode_id"], record["boundary_id"])
        event = meta.get(key)
        if event is None:  # pragma: no cover - load_history already filtered
            raise ReviewHistoryError(f"history row outside the selection: {key}")

        # The frame must agree between the frozen selection table and the
        # reviewed boundary; a disagreement means the freeze would be wrong.
        if int(record["predicted_frame"]) != int(event["event_frame"]):
            raise ReviewHistoryError(
                f"frame mismatch for {key}: db={record['predicted_frame']} "
                f"selection={event['event_frame']}"
            )

        reviewer = _text(record["reviewer"])
        phase = PHASE_BY_REVIEWER.get(reviewer)
        if phase is None:
            raise ReviewHistoryError(
                f"unclassified reviewer provenance {reviewer!r} on review_id "
                f"{record['review_id']}; refusing to guess a review_phase"
            )

        rows.append(
            {
                "diagnostic_event_id": event["diagnostic_event_id"],
                "episode_id": event["episode_id"],
                "boundary_id": event["boundary_id"],
                "event_frame": event["event_frame"],
                "arm": event["arm"],
                "pair_id": event["pair_id"],
                "P12": event["P12"],
                "C12": event["C12"],
                "review_id": str(record["review_id"]),
                "reviewer": reviewer,
                "reviewed_at": _text(record["reviewed_at"]),
                "human_decision": _text(record["decision"]),
                "reason_code": _text(record["reason_code"]),
                "corrected_frame": _text(record["corrected_frame"]),
                "comment": _text(record["comment"]),
                "review_phase": phase,
            }
        )
    rows.sort(key=lambda row: (row[SORT_KEY[0]], int(row[SORT_KEY[1]])))
    return rows


def summarise(rows: list[dict[str, str]], selection: list[dict[str, str]]) -> dict[str, Any]:
    """Completeness gate for the freeze (read-only over the built rows)."""

    per_event: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = per_event.setdefault(row["diagnostic_event_id"], {})
        bucket[row["review_phase"]] = bucket.get(row["review_phase"], 0) + 1

    missing_blind = sorted(
        row["diagnostic_event_id"]
        for row in selection
        if per_event.get(row["diagnostic_event_id"], {}).get("FIRST_BLINDED_REVIEW", 0) < 1
    )
    if missing_blind:
        raise ReviewHistoryError(
            f"{len(missing_blind)} event(s) lack a FIRST_BLINDED_REVIEW: {missing_blind}"
        )

    return {
        "EVENT_COUNT": len(selection),
        "TOTAL_HISTORY_ROWS": len(rows),
        "FIRST_BLINDED_EVENT_COUNT": sum(
            1
            for row in selection
            if per_event.get(row["diagnostic_event_id"], {}).get("FIRST_BLINDED_REVIEW", 0) >= 1
        ),
        "FIRST_BLINDED_REVISION_COUNT": sum(
            1 for row in rows if row["review_phase"] == "FIRST_BLINDED_REVIEW"
        ),
        "OWNER_UNBLINDED_REVISION_COUNT": sum(
            1 for row in rows if row["review_phase"] == "OWNER_UNBLINDED_ADJUDICATION"
        ),
        "NO_HISTORY_ROW_DROPPED": True,
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in FIELDS})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--output", default=None)
    parser.add_argument("--check", action="store_true", help="verify only; do not write")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.project_root)
    selection_path = root / SELECTION_RELPATH
    db_path = root / OWNER_DB_RELPATH
    output_path = Path(args.output) if args.output else root / OUTPUT_RELPATH

    selection = load_selection(selection_path)
    history = load_history(db_path, selection)
    rows = build_rows(selection, history)
    metrics = summarise(rows, selection)

    print("=" * 66)
    print("G1-P3 DESIGN_DIAGNOSTIC REVIEW HISTORY (append-only freeze)")
    print("=" * 66)
    print("run_id                =", RUN_ID)
    print("selection             =", selection_path)
    print("owner_db              =", db_path)
    for name, value in metrics.items():
        print(f"{name:<30}= {value}")

    if args.check:
        print("check-only: no file written")
        return 0

    write_csv(output_path, rows)
    print("output                =", output_path)
    print("sha256                =", sha256(output_path))
    print("sort order            =", " ASC, ".join(SORT_KEY) + " ASC")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReviewHistoryError as exc:
        print(f"REVIEW_HISTORY_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
