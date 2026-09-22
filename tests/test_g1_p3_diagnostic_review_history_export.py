"""G1-P3 diagnostic review-history freeze: append-only fidelity and determinism.

Covers ``scripts/export_g1_p3_diagnostic_review_history.py``, the
``POST_UNBLIND_EVIDENCE`` exporter for the 20 DESIGN_DIAGNOSTIC events.

The contract this file pins down:

* **every** revision in ``predicted_boundary_review_history`` is exported -- the
  first blinded review and the later owner unblinded adjudication are both kept,
  unlike the P2 exporter which keeps only ``max(review_id)``;
* ``review_phase`` is derived from the stored reviewer identity and never
  guessed from timestamps; an unclassified reviewer is a hard error;
* ``arm`` / ``pair_id`` / ``P12`` / ``C12`` are joined from
  ``02_selection_internal.csv``, not read out of the human review database;
* the frozen selection table and the reviewed boundary must agree on the frame;
* every event must carry at least one ``FIRST_BLINDED_REVIEW`` revision;
* output is UTF-8 without BOM, LF-terminated, frozen column order, stable sort,
  and byte-deterministic;
* the owner database is opened read-only and left untouched.
"""

from __future__ import annotations

import csv
import hashlib
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts", Path(__file__).resolve().parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import export_g1_p3_diagnostic_review_history as exporter  # noqa: E402

from project2_g1_audit_web.reviews import ReviewStore  # noqa: E402

RUN_ID = "g1_design_diagnostic_test_000000_00000000"

# Four events over two pairs, chosen to exercise every revision shape:
#   * single blind revision                          -> DIAG-001 / DIAG-002
#   * blind + intermediate same-content blind + owner -> DIAG-003
#   * blind + owner                                  -> DIAG-004
DIAG_001 = "G1P3-DIAG-001"
DIAG_002 = "G1P3-DIAG-002"
DIAG_003 = "G1P3-DIAG-003"
DIAG_004 = "G1P3-DIAG-004"

SELECTION_HEADER = (
    "diagnostic_event_id,arm,pair_id,episode_id,event_frame,boundary_id,"
    "representative_candidate_id,P12,P12_percentile,C12,C12_percentile,"
    "direction_evidence,direction_evidence_percentile,run_length,"
    "run_length_percentile,match_distance,distance_to_nearest_gripper_final,"
    "selection_reason"
)

# (diagnostic_event_id, arm, pair_id, episode_id, event_frame, boundary_id, P12, C12)
SELECTION_ROWS = [
    (DIAG_001, "A", "P01", "data/demo_1", 10, "demo_1-B0001", "0.10", "0.11"),
    (DIAG_002, "B", "P01", "data/demo_2", 20, "demo_2-B0002", "0.20", "0.90"),
    (DIAG_003, "A", "P02", "data/demo_3", 30, "demo_3-B0003", "0.30", "0.12"),
    (DIAG_004, "B", "P02", "data/demo_4", 40, "demo_4-B0004", "0.40", "0.95"),
]

# (diagnostic_event_id, decision, reason_code, reviewer, reviewed_at)
HISTORY_ROWS = [
    (DIAG_001, "VALID", None, "DESIGN_OWNER", "2026-09-22T16:00:00+08:00"),
    (DIAG_002, "REDUNDANT", "REDUNDANT_DIRECTION_JITTER", "DESIGN_OWNER",
     "2026-09-22T16:01:00+08:00"),
    # intermediate revision, same reviewer, same content as the first
    (DIAG_003, "VALID", None, "DESIGN_OWNER", "2026-09-22T16:02:00+08:00"),
    (DIAG_003, "VALID", None, "DESIGN_OWNER", "2026-09-22T20:24:00+08:00"),
    (DIAG_003, "REDUNDANT", "REDUNDANT_DIRECTION_JITTER", "DESIGN_OWNER_UNBLINDED",
     "2026-09-22T20:38:00+08:00"),
    (DIAG_004, "REDUNDANT", "REDUNDANT_DIRECTION_JITTER", "DESIGN_OWNER",
     "2026-09-22T16:03:00+08:00"),
    (DIAG_004, "VALID", None, "DESIGN_OWNER_UNBLINDED", "2026-09-22T20:38:01+08:00"),
]

_FRAME_BY_EVENT = {row[0]: row[4] for row in SELECTION_ROWS}
_KEY_BY_EVENT = {row[0]: (row[3], row[5]) for row in SELECTION_ROWS}


class _Fixture:
    """Minimal project root: frozen selection table + owner review database."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.set_dir = root / exporter.SET_RELPATH
        self.set_dir.mkdir(parents=True, exist_ok=True)
        self.selection = self.set_dir / "02_selection_internal.csv"
        self.db = root / exporter.OWNER_DB_RELPATH
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self.output = self.set_dir / "05_review_history.csv"
        self._write_selection()

    def _write_selection(self, rows=None, *, frame_override=None) -> None:
        rows = SELECTION_ROWS if rows is None else rows
        frame_override = frame_override or {}
        with self.selection.open("w", encoding="utf-8", newline="") as handle:
            handle.write(SELECTION_HEADER + "\n")
            for eid, arm, pair, episode, frame, boundary, p12, c12 in rows:
                frame = frame_override.get(eid, frame)
                cells = {
                    "diagnostic_event_id": eid,
                    "arm": arm,
                    "pair_id": pair,
                    "episode_id": episode,
                    "event_frame": str(frame),
                    "boundary_id": boundary,
                    "representative_candidate_id": boundary.replace("-B", "-C"),
                    "P12": p12,
                    "C12": c12,
                }
                handle.write(
                    ",".join(cells.get(name, "") for name in SELECTION_HEADER.split(","))
                    + "\n"
                )

    def rewrite_selection(self, rows=None, *, frame_override=None) -> None:
        self._write_selection(rows, frame_override=frame_override)

    def seed_history(self, rows=None) -> None:
        ReviewStore(self.db)  # creates the append-only schema
        rows = HISTORY_ROWS if rows is None else rows
        con = sqlite3.connect(self.db)
        try:
            with con:
                for eid, decision, reason, reviewer, reviewed_at in rows:
                    episode, boundary = _KEY_BY_EVENT[eid]
                    con.execute(
                        "INSERT INTO predicted_boundary_review_history "
                        "(run_id, episode_id, boundary_id, predicted_frame, decision, "
                        " reason_code, corrected_frame, comment, reviewer, reviewed_at) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (
                            RUN_ID,
                            episode,
                            boundary,
                            _FRAME_BY_EVENT[eid],
                            decision,
                            reason,
                            None,
                            None,
                            reviewer,
                            reviewed_at,
                        ),
                    )
        finally:
            con.close()

    def export_rows(self):
        selection = exporter.load_selection(self.selection)
        history = exporter.load_history(self.db, selection)
        return exporter.build_rows(selection, history)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class TestDiagnosticReviewHistoryExport(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.fx = _Fixture(self.root)

        # The module constants describe the production 20-event set; pin them to
        # the fixture for the duration of each test.
        patched = {
            "RUN_ID": RUN_ID,
            "EXPECTED_EVENT_COUNT": len(SELECTION_ROWS),
            "EXPECTED_DISTINCT_EPISODE_COUNT": len(SELECTION_ROWS),
            "EXPECTED_PAIR_COUNT": 2,
            "EXPECTED_ARM_COUNTS": {"A": 2, "B": 2},
        }
        for name, value in patched.items():
            original = getattr(exporter, name)
            self.addCleanup(setattr, exporter, name, original)
            setattr(exporter, name, value)

    # -- append-only fidelity ------------------------------------------------

    def test_every_revision_is_kept_not_just_the_latest(self) -> None:
        self.fx.seed_history()
        rows = self.fx.export_rows()

        self.assertEqual(len(rows), len(HISTORY_ROWS))
        by_event: dict[str, list[dict[str, str]]] = {}
        for row in rows:
            by_event.setdefault(row["diagnostic_event_id"], []).append(row)

        # DIAG-003 carries three revisions; a max(review_id) exporter would
        # have kept only the last one.
        self.assertEqual(len(by_event[DIAG_003]), 3)
        self.assertEqual(
            [row["human_decision"] for row in by_event[DIAG_003]],
            ["VALID", "VALID", "REDUNDANT"],
        )
        # The intermediate same-content revision is preserved verbatim.
        self.assertEqual(
            [row["reviewer"] for row in by_event[DIAG_003]],
            ["DESIGN_OWNER", "DESIGN_OWNER", "DESIGN_OWNER_UNBLINDED"],
        )

    def test_review_phase_is_mapped_from_reviewer_identity(self) -> None:
        self.fx.seed_history()
        rows = self.fx.export_rows()

        mapping = {
            row["reviewer"]: row["review_phase"] for row in rows
        }
        self.assertEqual(mapping["DESIGN_OWNER"], "FIRST_BLINDED_REVIEW")
        self.assertEqual(
            mapping["DESIGN_OWNER_UNBLINDED"], "OWNER_UNBLINDED_ADJUDICATION"
        )
        # Phase must never be inferred from the timestamp ordering alone.
        for row in rows:
            self.assertEqual(
                row["review_phase"], exporter.PHASE_BY_REVIEWER[row["reviewer"]]
            )

    def test_unknown_reviewer_is_a_hard_error(self) -> None:
        self.fx.seed_history(
            HISTORY_ROWS + [
                (DIAG_001, "VALID", None, "SOME_NEW_REVIEWER",
                 "2026-09-22T21:00:00+08:00"),
            ]
        )
        with self.assertRaises(exporter.ReviewHistoryError) as ctx:
            self.fx.export_rows()
        message = str(ctx.exception)
        self.assertIn("SOME_NEW_REVIEWER", message)
        self.assertIn("refusing to guess", message)

    # -- provenance of the joined metadata -----------------------------------

    def test_selection_metadata_is_joined_not_read_from_the_review_db(self) -> None:
        self.fx.seed_history()
        rows = self.fx.export_rows()

        by_event = {row["diagnostic_event_id"]: row for row in rows}
        self.assertEqual(by_event[DIAG_001]["arm"], "A")
        self.assertEqual(by_event[DIAG_001]["pair_id"], "P01")
        self.assertEqual(by_event[DIAG_001]["P12"], "0.10")
        self.assertEqual(by_event[DIAG_001]["C12"], "0.11")
        self.assertEqual(by_event[DIAG_002]["arm"], "B")
        self.assertEqual(by_event[DIAG_002]["C12"], "0.90")
        # The review database has no arm/cohort column at all.
        con = sqlite3.connect(self.fx.db)
        try:
            columns = {
                row[1]
                for row in con.execute(
                    "PRAGMA table_info(predicted_boundary_review_history)"
                )
            }
        finally:
            con.close()
        for leaked in ("arm", "pair_id", "P12", "C12"):
            self.assertNotIn(leaked, columns)

    def test_frame_mismatch_between_db_and_selection_is_a_hard_error(self) -> None:
        self.fx.seed_history()
        # Rewrite the frozen selection table so its frame disagrees with the
        # already-reviewed boundary.
        self.fx.rewrite_selection(frame_override={DIAG_001: 999})
        with self.assertRaises(exporter.ReviewHistoryError) as ctx:
            self.fx.export_rows()
        self.assertIn("frame mismatch", str(ctx.exception))

    # -- completeness gate ---------------------------------------------------

    def test_missing_first_blinded_review_fails_the_completeness_gate(self) -> None:
        # DIAG-004 has no DESIGN_OWNER revision at all.
        self.fx.seed_history([row for row in HISTORY_ROWS if row[0] != DIAG_004])
        selection = exporter.load_selection(self.fx.selection)
        history = exporter.load_history(self.fx.db, selection)
        rows = exporter.build_rows(selection, history)
        with self.assertRaises(exporter.ReviewHistoryError) as ctx:
            exporter.summarise(rows, selection)
        self.assertIn(DIAG_004, str(ctx.exception))

    def test_summary_counts_match_the_kept_history(self) -> None:
        self.fx.seed_history()
        selection = exporter.load_selection(self.fx.selection)
        history = exporter.load_history(self.fx.db, selection)
        rows = exporter.build_rows(selection, history)
        metrics = exporter.summarise(rows, selection)

        self.assertEqual(metrics["EVENT_COUNT"], 4)
        self.assertEqual(metrics["TOTAL_HISTORY_ROWS"], len(HISTORY_ROWS))
        self.assertEqual(metrics["FIRST_BLINDED_EVENT_COUNT"], 4)
        self.assertEqual(metrics["FIRST_BLINDED_REVISION_COUNT"], 5)
        self.assertEqual(metrics["OWNER_UNBLINDED_REVISION_COUNT"], 2)
        self.assertTrue(metrics["NO_HISTORY_ROW_DROPPED"])

    # -- determinism and schema ---------------------------------------------

    def test_output_is_utf8_without_bom_lf_and_deterministic(self) -> None:
        self.fx.seed_history()
        rows = self.fx.export_rows()

        exporter.write_csv(self.fx.output, rows)
        first = self.fx.output.read_bytes()
        self.assertFalse(first.startswith(b"\xef\xbb\xbf"), "expected no BOM")
        self.assertNotIn(b"\r\n", first, "expected LF line endings")

        exporter.write_csv(self.fx.output, rows)
        self.assertEqual(self.fx.output.read_bytes(), first, "export must be deterministic")

        with self.fx.output.open(newline="", encoding="utf-8") as handle:
            parsed = list(csv.DictReader(handle))
        self.assertEqual(len(parsed), len(HISTORY_ROWS))

    def test_sort_order_is_diagnostic_event_then_review_id(self) -> None:
        self.fx.seed_history()
        rows = self.fx.export_rows()
        keys = [(row["diagnostic_event_id"], int(row["review_id"])) for row in rows]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(exporter.SORT_KEY, ("diagnostic_event_id", "review_id"))

    def test_column_order_is_frozen(self) -> None:
        expected = (
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
        self.assertEqual(tuple(exporter.FIELDS), expected)
        self.fx.seed_history()
        exporter.write_csv(self.fx.output, self.fx.export_rows())
        header = self.fx.output.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(tuple(header.split(",")), expected)

    # -- safety --------------------------------------------------------------

    def test_export_is_read_only_over_the_owner_database(self) -> None:
        self.fx.seed_history()
        before = _sha256(self.fx.db)
        rows = self.fx.export_rows()
        exporter.write_csv(self.fx.output, rows)
        self.assertEqual(_sha256(self.fx.db), before, "the owner DB must not change")

    def test_main_writes_the_frozen_output_path(self) -> None:
        self.fx.seed_history()
        self.assertEqual(exporter.main(["--project-root", str(self.root)]), 0)
        self.assertTrue(self.fx.output.is_file())
        self.assertEqual(
            len(self.fx.output.read_text(encoding="utf-8").strip().splitlines()),
            len(HISTORY_ROWS) + 1,
        )

    def test_check_mode_writes_nothing(self) -> None:
        self.fx.seed_history()
        self.assertEqual(
            exporter.main(["--project-root", str(self.root), "--check"]), 0
        )
        self.assertFalse(self.fx.output.exists())


if __name__ == "__main__":
    unittest.main()
