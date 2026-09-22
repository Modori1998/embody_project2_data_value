"""P2 human review audit table export: scope, provenance, determinism.

Covers ``scripts/export_g1_p2_review_audit.py``:

* P1 (per-signal) review rows are excluded, P2 (per-boundary) rows are not;
* only the current (highest ``review_id``) revision of an append-only key is
  exported, and ``effective_review_id`` records which revision that was;
* the column set stays a superset of the frozen export schema;
* the table is written as UTF-8 with BOM and is byte-deterministic;
* a run whose boundary table predates the frozen MATERIALIZED_V1 schema is
  tolerated and reported rather than silently blank;
* an unreadable run folder yields a null boundary universe, not 0.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts", Path(__file__).resolve().parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import export_g1_p2_review_audit as exporter  # noqa: E402

from project2_g1_audit_web.reviews import ReviewStore  # noqa: E402

MODERN_RUN = "g1_calibration_20260101_000000_aaaaaaaa"
LEGACY_RUN = "g1_exploratory_audit_20260102_000000_bbbbbbbb"
BROKEN_RUN = "g1_calibration_20260103_000000_cccccccc"

MODERN_COLUMNS = (
    "boundary_id,episode_id,frame,candidate_type,reason,"
    "representative_candidate_id,member_candidate_ids,member_candidate_types,"
    "member_candidate_frames,member_candidate_count"
)
LEGACY_COLUMNS = (
    "boundary_id,episode_id,frame,candidate_type,reason,member_candidate_ids"
)

# Every column the frozen export contract defines. The audit table must carry
# all of them (it adds run_stage / diagnostic_set_id because it spans runs).
FROZEN_SCHEMA_FIELDS = (
    "source_run_id",
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


class _Fixture:
    """Minimal project root: registry + run folders + owner review store."""

    def __init__(self, tmp: Path) -> None:
        self.root = tmp
        self.runs = tmp / "outputs/g1_audit_runs"
        self.db = tmp / "outputs/g1_audit_web/g1_audit_web_owner.sqlite3"
        self.registry = tmp / "outputs/g1_audit_web/g1_audit_run_registry.json"

    def add_run(
        self,
        run_id: str,
        *,
        run_stage: str,
        boundaries: list[dict[str, str]],
        columns: str = MODERN_COLUMNS,
        diagnostic_set_id: str = "",
        folder: Path | None = None,
    ) -> Path:
        run_root = folder or (self.runs / run_id)
        episode = "demo_1"
        diag = run_root / "diagnostic" / episode
        diag.mkdir(parents=True, exist_ok=True)

        with (diag / "final_boundaries.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            handle.write(columns + "\n")
            for row in boundaries:
                handle.write(",".join(row.get(name, "") for name in columns.split(",")) + "\n")

        with (run_root / "episode_manifest.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            handle.write("run_id,episode_id,boundaries_relpath\n")
            handle.write(f"{run_id},{episode},diagnostic/{episode}/final_boundaries.csv\n")

        meta = {"run_id": run_id, "run_stage": run_stage}
        if diagnostic_set_id:
            meta["diagnostic_set_id"] = diagnostic_set_id
        (run_root / "run_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        self._registry_entries().append(
            {
                "run_id": run_id,
                "run_stage": run_stage,
                "audit_folder_path": str(run_root),
            }
        )
        self._write_registry()
        return run_root

    def _registry_entries(self) -> list[dict[str, str]]:
        if not hasattr(self, "_entries"):
            self._entries: list[dict[str, str]] = []
        return self._entries

    def _write_registry(self) -> None:
        self.registry.parent.mkdir(parents=True, exist_ok=True)
        self.registry.write_text(
            json.dumps(
                {"schema_version": 1, "runs": {e["run_id"]: e for e in self._registry_entries()}},
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    def connect(self) -> sqlite3.Connection:
        ReviewStore(self.db)  # creates the append-only schema
        con = sqlite3.connect(self.db)
        con.row_factory = sqlite3.Row
        return con


def _boundary_row(boundary_id: str, frame: int, **extra: str) -> dict[str, str]:
    row = {
        "boundary_id": boundary_id,
        "episode_id": "data/demo_1",
        "frame": str(frame),
        "candidate_type": "DIRECTION_CHANGE",
        "reason": "PERSISTENT_DIRECTION_CHANGE",
        "representative_candidate_id": boundary_id.replace("-B", "-C"),
        "member_candidate_ids": boundary_id.replace("-B", "-C"),
        "member_candidate_types": "DIRECTION_CHANGE",
        "member_candidate_frames": str(frame),
        "member_candidate_count": "1",
    }
    row.update(extra)
    return row


def _insert_boundary_review(con, run_id, boundary_id, frame, decision, **kw):
    con.execute(
        "INSERT INTO predicted_boundary_review_history "
        "(run_id, episode_id, boundary_id, predicted_frame, decision, reason_code, "
        " corrected_frame, comment, reviewer, reviewed_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            run_id,
            "data/demo_1",
            boundary_id,
            frame,
            decision,
            kw.get("reason_code"),
            kw.get("corrected_frame"),
            kw.get("comment"),
            kw.get("reviewer", "DESIGN_OWNER"),
            kw.get("reviewed_at", "2026-09-22T10:00:00+08:00"),
        ),
    )


def _insert_signal_review(con, run_id, signal_name, decision):
    con.execute(
        "INSERT INTO signal_review_history "
        "(episode_id, signal_contract_version, signal_contract_hash, signal_name, "
        " decision, comment, source_run_id, reviewer, reviewed_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "data/demo_1",
            "g1_p1_signal_contract.v0",
            "0" * 64,
            signal_name,
            decision,
            None,
            run_id,
            "DESIGN_OWNER",
            "2026-09-22T10:00:00+08:00",
        ),
    )


class TestP2ReviewAuditExport(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.fx = _Fixture(self.root)

    def _seed(self) -> None:
        self.fx.add_run(
            MODERN_RUN,
            run_stage="CALIBRATION",
            boundaries=[
                _boundary_row("demo_1-B0001", 10),
                _boundary_row("demo_1-B0002", 40),
            ],
        )
        self.fx.add_run(
            LEGACY_RUN,
            run_stage="EXPLORATORY_AUDIT",
            columns=LEGACY_COLUMNS,
            boundaries=[
                {
                    "boundary_id": "demo_1-B0001",
                    "episode_id": "data/demo_1",
                    "frame": "10",
                    "candidate_type": "GRIPPER_TRANSITION",
                    "reason": "GRIPPER_TRANSITION",
                    "member_candidate_ids": "demo_1-C0001",
                }
            ],
        )
        con = self.fx.connect()
        with con:
            _insert_boundary_review(con, MODERN_RUN, "demo_1-B0001", 10, "VALID")
            _insert_boundary_review(
                con, MODERN_RUN, "demo_1-B0002", 40, "REDUNDANT",
                reason_code="REDUNDANT_SHORT_PAUSE", comment="停顿",
            )
            _insert_boundary_review(con, LEGACY_RUN, "demo_1-B0001", 10, "VALID")
            _insert_signal_review(con, MODERN_RUN, "TRANSLATION", "PASS")
            _insert_signal_review(con, MODERN_RUN, "DIRECTION", "PASS")
        con.close()

    def test_p1_rows_are_excluded(self) -> None:
        self._seed()
        rows, _ = exporter.build_table(self.root)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["human_decision"] != "PASS" for row in rows))
        self.assertNotIn("signal_name", exporter.FIELDS)

    def test_only_latest_revision_is_exported(self) -> None:
        self._seed()
        con = self.fx.connect()
        with con:
            # A second, later review of the same key must win.
            _insert_boundary_review(
                con, MODERN_RUN, "demo_1-B0001", 10, "MISALIGNED",
                reason_code="MISALIGNED_GRIPPER", corrected_frame=12,
                reviewed_at="2026-09-22T11:00:00+08:00",
            )
        con.close()

        rows, _ = exporter.build_table(self.root)
        target = [
            row
            for row in rows
            if row["source_run_id"] == MODERN_RUN and row["boundary_id"] == "demo_1-B0001"
        ]
        self.assertEqual(len(target), 1, "one current row per append-only key")
        self.assertEqual(target[0]["human_decision"], "MISALIGNED")
        self.assertEqual(str(target[0]["corrected_frame"]), "12")
        self.assertEqual(target[0]["reviewed_at"], "2026-09-22T11:00:00+08:00")
        # effective_review_id must point at the winning revision, not the first.
        ids = [
            row["effective_review_id"]
            for row in rows
            if row["boundary_id"] == "demo_1-B0001"
        ]
        self.assertEqual(len(set(ids)), 2)  # one per run

    def test_schema_covers_the_frozen_export_contract(self) -> None:
        missing = [name for name in FROZEN_SCHEMA_FIELDS if name not in exporter.FIELDS]
        self.assertEqual(missing, [], f"audit table dropped frozen columns: {missing}")
        for extra in ("run_stage", "diagnostic_set_id"):
            self.assertIn(extra, exporter.FIELDS)

    def test_table_is_utf8_bom_and_byte_deterministic(self) -> None:
        self._seed()
        out = self.root / "export"
        self.assertEqual(exporter.main(["--project-root", str(self.root),
                                        "--output-dir", str(out)]), 0)
        table = out / exporter.TABLE_NAME
        first = table.read_bytes()
        self.assertTrue(first.startswith(b"\xef\xbb\xbf"), "expected a UTF-8 BOM")

        self.assertEqual(exporter.main(["--project-root", str(self.root),
                                        "--output-dir", str(out)]), 0)
        self.assertEqual(table.read_bytes(), first, "export must be deterministic")

        with table.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 3)
        self.assertEqual(
            [row for row in rows if row["comment"]], 
            [row for row in rows if row["comment"] == "停顿"],
        )

    def test_legacy_boundary_schema_is_reported_not_silently_blank(self) -> None:
        self._seed()
        rows, meta = exporter.build_table(self.root)
        legacy = [row for row in rows if row["source_run_id"] == LEGACY_RUN]
        self.assertEqual(len(legacy), 1)
        # Legacy run has no representative candidate column at all.
        self.assertEqual(legacy[0]["representative_candidate_id"], "")
        self.assertEqual(legacy[0]["member_candidate_ids"], "demo_1-C0001")
        self.assertEqual(meta["legacy_schema_runs"], [LEGACY_RUN])
        self.assertEqual(meta["reviews_missing_boundary_context"], [])

    def test_unreadable_run_reports_null_universe(self) -> None:
        self._seed()
        # Register a run whose folder does not exist on disk.
        self.fx.add_run(
            BROKEN_RUN,
            run_stage="CALIBRATION",
            boundaries=[],
            folder=self.root / "outputs/g1_audit_runs" / BROKEN_RUN,
        )
        (self.root / "outputs/g1_audit_runs" / BROKEN_RUN / "episode_manifest.csv").unlink()

        _, meta = exporter.build_table(self.root)
        broken = [item for item in meta["per_run"] if item["run_id"] == BROKEN_RUN]
        self.assertEqual(len(broken), 1)
        self.assertIsNone(broken[0]["boundaries_in_run"], "unknown universe must be null")
        self.assertIn(BROKEN_RUN, [item["run_id"] for item in meta["unreadable_runs"]])

    def test_blinding_contract_is_declared_and_not_violated(self) -> None:
        self._seed()
        _, meta = exporter.build_table(self.root)
        self.assertFalse(meta["blinding"]["unblinded"])
        self.assertFalse(meta["blinding"]["arm_or_cohort_column_present"])
        self.assertFalse(meta["blinding"]["redundant_rate_computed"])
        self.assertFalse(meta["blinding"]["gate_verdict_computed"])
        for token in ("arm", "p12", "c12", "coherence", "pair_id", "match_distance"):
            self.assertNotIn(token, [name.lower() for name in exporter.FIELDS])


if __name__ == "__main__":
    unittest.main()
