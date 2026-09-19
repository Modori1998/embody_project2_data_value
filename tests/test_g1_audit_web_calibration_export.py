from __future__ import annotations

import csv
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = Path(__file__).resolve().parent
for path in (SRC, TESTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from g1_audit_web_fixtures import write_merge_semantics_run
from project2_g1_audit_web.calibration_export import (
    EXPORT_INTENDED_ROLE_CALIBRATION,
    ExportBlocked,
    HumanCalibrationExportService,
    resolve_export_role,
)
from project2_g1_audit_web.app import create_app
from project2_g1_audit_web.hashes import sha256_file, tree_fingerprint
from project2_g1_audit_web.input import load_csv_rows, load_run
from project2_g1_audit_web.reviews import SIGNAL_NAMES, ReviewStore
from project2_g1_audit_web.registry import auto_register
from project2_g1_audit_web.view import encode_episode_id


class CalibrationExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run_root = write_merge_semantics_run(self.root / "runs", materialized=True)
        self.loaded = load_run(self.run_root)
        self.db = self.root / "owner.sqlite3"
        self.store = ReviewStore(self.db, reviewer="DESIGN_OWNER")
        self.exports = self.root / "exports"
        self.service = HumanCalibrationExportService(
            project_root=self.root, owner_db_path=self.db, export_root=self.exports
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _complete(self, *, redundant_first: bool = True) -> None:
        meta = self.loaded["run_meta"]
        for episode in self.loaded["episodes"]:
            finals = load_csv_rows(episode.boundaries_path)
            predicted = {row["boundary_id"]: int(row["frame"]) for row in finals}
            boundaries = {}
            for index, boundary_id in enumerate(predicted):
                if redundant_first and episode.episode_id == "data/demo_0" and index == 0:
                    boundaries[boundary_id] = {
                        "decision": "REDUNDANT", "reason_code": "REDUNDANT_SHORT_PAUSE", "comment": "",
                    }
                else:
                    boundaries[boundary_id] = {"decision": "VALID", "reason_code": "", "comment": ""}
            self.store.save_episode(
                run_id=self.loaded["run_id"], episode_id=episode.episode_id,
                signal_contract_version=meta["signal_contract_version"],
                signal_contract_hash=meta["signal_contract_hash"],
                episode_length=episode.length, predicted=predicted,
                signals={name: {"decision": "PASS", "comment": ""} for name in SIGNAL_NAMES},
                boundaries=boundaries, added=[], episode_note="not exported",
            )

    def _insert_signal(self, *, episode_id: str, signal_name: str, decision: str, source_run_id: str) -> None:
        meta = self.loaded["run_meta"]
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                "INSERT INTO signal_review_history (episode_id, signal_contract_version, signal_contract_hash, signal_name, decision, comment, source_run_id, reviewer, reviewed_at) VALUES (?, ?, ?, ?, ?, '', ?, 'DESIGN_OWNER', '2026-09-17T00:00:00+08:00')",
                (episode_id, meta["signal_contract_version"], meta["signal_contract_hash"], signal_name, decision, source_run_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _reload(self) -> None:
        self.loaded = load_run(self.run_root)

    def _rewrite_identity(
        self,
        *,
        run_stage: str,
        calibration_role: str = "",
        calibration_config_role: str = "",
    ) -> None:
        meta_path = self.run_root / "run_meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["run_stage"] = run_stage
        if calibration_role:
            meta["calibration_role"] = calibration_role
        else:
            meta.pop("calibration_role", None)
        if calibration_config_role:
            meta["calibration_config_role"] = calibration_config_role
        else:
            meta.pop("calibration_config_role", None)
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        set_role = {
            "EXPLORATORY_AUDIT": "EXPLORATORY",
            "CALIBRATION": "CALIBRATION",
            "EVALUATION": "EVALUATION",
        }[run_stage]
        manifest = self.run_root / "episode_manifest.csv"
        with manifest.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = list(reader.fieldnames or [])
            rows = list(reader)
        for row in rows:
            row["set_role"] = set_role
        with manifest.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        self._reload()

    def _as_calibration_baseline(
        self,
        *,
        calibration_role: str = "BASELINE_HUMAN_AUDIT",
        calibration_config_role: str = "BASELINE_UNMODIFIED",
    ) -> None:
        self._rewrite_identity(
            run_stage="CALIBRATION",
            calibration_role=calibration_role,
            calibration_config_role=calibration_config_role,
        )

    def test_complete_export_reuse_redundant_empty_added_and_immutability(self) -> None:
        self._complete()
        for name in SIGNAL_NAMES:
            self._insert_signal(episode_id="data/demo_0", signal_name=name, decision="PASS", source_run_id="parent_run")
        sqlite_before = sha256_file(self.db)
        run_before = tree_fingerprint(self.run_root)["tree_fingerprint"]

        result = self.service.create_export(self.loaded)
        path = Path(result["export_path"])
        meta = json.loads((path / "export_meta.json").read_text(encoding="utf-8"))
        with (path / "signal_review.csv").open(encoding="utf-8", newline="") as handle:
            signals = list(csv.DictReader(handle))
        with (path / "predicted_boundary_review.csv").open(encoding="utf-8", newline="") as handle:
            predicted = list(csv.DictReader(handle))
        with (path / "human_added_boundary.csv").open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            self.assertEqual(reader.fieldnames, [
                "export_id", "source_run_id", "episode_id", "added_group_id", "human_added_frame",
                "reason_code", "comment", "review_id", "reviewer", "reviewed_at",
            ])
            self.assertEqual(list(reader), [])

        self.assertEqual(len(signals), 12)
        self.assertTrue(all(row["decision"] == "PASS" for row in signals))
        reused = [row for row in signals if row["episode_id"] == "data/demo_0"]
        self.assertTrue(all(row["review_origin"] == "REUSED_REVIEW" and row["review_source_run_id"] == "parent_run" for row in reused))
        self.assertEqual(len(predicted), 4)
        self.assertEqual(sum(row["human_decision"] == "REDUNDANT" for row in predicted), 1)
        self.assertTrue(all(row["representative_candidate_id"] for row in predicted))
        self.assertEqual(meta["source_run_stage"], "EXPLORATORY_AUDIT")
        self.assertEqual(meta["source_set_role"], "EXPLORATORY")
        self.assertEqual(meta["intended_role"], "CALIBRATION_SEED")
        self.assertTrue(meta["must_not_feed_evaluation"])
        self.assertNotIn("episode_note", json.dumps(meta))
        self.assertEqual(sqlite_before, sha256_file(self.db))
        self.assertEqual(run_before, tree_fingerprint(self.run_root)["tree_fingerprint"])

        first_bytes = (path / "export_meta.json").read_bytes()
        second = self.service.create_export(self.loaded)
        self.assertNotEqual(result["export_id"], second["export_id"])
        self.assertEqual(first_bytes, (path / "export_meta.json").read_bytes())

    def test_p1_not_reviewed_and_fail_block(self) -> None:
        with self.assertRaisesRegex(ExportBlocked, "P1 NOT_REVIEWED"):
            self.service.create_export(self.loaded)
        self._complete()
        self._insert_signal(episode_id="data/demo_0", signal_name="DIRECTION", decision="FAIL", source_run_id=self.loaded["run_id"])
        with self.assertRaisesRegex(ExportBlocked, "requires PASS"):
            self.service.create_export(self.loaded)

    def test_p2_not_reviewed_blocks(self) -> None:
        meta = self.loaded["run_meta"]
        for episode in self.loaded["episodes"]:
            self.store.save_episode(
                run_id=self.loaded["run_id"], episode_id=episode.episode_id,
                signal_contract_version=meta["signal_contract_version"], signal_contract_hash=meta["signal_contract_hash"],
                episode_length=episode.length, predicted={},
                signals={name: {"decision": "PASS", "comment": ""} for name in SIGNAL_NAMES},
                boundaries={}, added=[], episode_note="",
            )
        with self.assertRaisesRegex(ExportBlocked, "P2 NOT_REVIEWED"):
            self.service.create_export(self.loaded)

    def test_invalid_misaligned_and_boundary_not_in_run_block(self) -> None:
        self._complete(redundant_first=False)
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                "INSERT INTO predicted_boundary_review_history (run_id, episode_id, boundary_id, predicted_frame, decision, reason_code, corrected_frame, comment, reviewer, reviewed_at) VALUES (?, 'data/demo_0', 'demo_0-B0001', 4, 'MISALIGNED', 'MISALIGNED_GRIPPER', NULL, '', 'DESIGN_OWNER', '2026-09-17T00:00:00+08:00')",
                (self.loaded["run_id"],),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaisesRegex(ExportBlocked, "MISALIGNED requires corrected_frame"):
            self.service.create_export(self.loaded)

        self._complete(redundant_first=False)
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                "INSERT INTO predicted_boundary_review_history (run_id, episode_id, boundary_id, predicted_frame, decision, reason_code, corrected_frame, comment, reviewer, reviewed_at) VALUES (?, 'data/demo_0', 'NOT-IN-RUN', 1, 'VALID', '', NULL, '', 'DESIGN_OWNER', '2026-09-17T00:00:01+08:00')",
                (self.loaded["run_id"],),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaisesRegex(ExportBlocked, "boundary review not in source Final"):
            self.service.create_export(self.loaded)

    def test_web_trigger_creates_export_and_history_is_visible(self) -> None:
        self._complete()
        registry = self.root / "registry.json"
        auto_register(registry, self.run_root)
        app = create_app(
            project_root=self.root, registry_path=registry, owner_db_path=self.db,
            review_store=self.store,
        )
        client = TestClient(app)
        encoded = encode_episode_id("data/demo_0")
        url = f"/audit/{self.loaded['run_id']}/episode/{encoded}/export"
        response = client.post(url, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn("exported=g1_cal_seed_export_", response.headers["location"])
        history = app.state.calibration_exporter.list_exports(source_run_id=self.loaded["run_id"])
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["intended_role"], "CALIBRATION_SEED")
        self.assertEqual(history[0]["validation_status"], "PASS")

    def test_calibration_baseline_export_allowed(self) -> None:
        self._complete()
        self._as_calibration_baseline()
        sqlite_before = sha256_file(self.db)
        run_before = tree_fingerprint(self.run_root)["tree_fingerprint"]
        assess = self.service.assess(self.loaded)
        self.assertTrue(assess["review_ready"])
        self.assertTrue(assess["export_eligible"])
        self.assertTrue(assess["effective_export_ready"])
        self.assertTrue(assess["ready"])
        self.assertEqual(assess["intended_role"], EXPORT_INTENDED_ROLE_CALIBRATION)
        self.assertEqual(resolve_export_role(self.loaded), EXPORT_INTENDED_ROLE_CALIBRATION)

        result = self.service.create_export(self.loaded, intended_role=EXPORT_INTENDED_ROLE_CALIBRATION)
        path = Path(result["export_path"])
        meta = json.loads((path / "export_meta.json").read_text(encoding="utf-8"))
        with (path / "signal_review.csv").open(encoding="utf-8", newline="") as handle:
            signals = list(csv.DictReader(handle))
        with (path / "predicted_boundary_review.csv").open(encoding="utf-8", newline="") as handle:
            predicted = list(csv.DictReader(handle))
        with (path / "human_added_boundary.csv").open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            self.assertTrue(reader.fieldnames)
            self.assertEqual(list(reader), [])
        self.assertTrue(str(result["export_id"]).startswith("g1_cal_export_"))
        self.assertEqual(len(signals), 12)
        self.assertEqual(len(predicted), 4)
        self.assertEqual(meta["source_run_stage"], "CALIBRATION")
        self.assertEqual(meta["source_set_role"], "CALIBRATION")
        self.assertEqual(meta["calibration_role"], "BASELINE_HUMAN_AUDIT")
        self.assertEqual(meta["calibration_config_role"], "BASELINE_UNMODIFIED")
        self.assertEqual(meta["intended_role"], "CALIBRATION")
        self.assertTrue(meta["must_not_feed_evaluation"])
        self.assertEqual(sqlite_before, sha256_file(self.db))
        self.assertEqual(run_before, tree_fingerprint(self.run_root)["tree_fingerprint"])

    def test_calibration_p1_incomplete_blocked(self) -> None:
        self._as_calibration_baseline()
        assess = self.service.assess(self.loaded)
        self.assertFalse(assess["review_ready"])
        self.assertTrue(assess["export_eligible"])
        self.assertFalse(assess["effective_export_ready"])
        with self.assertRaisesRegex(ExportBlocked, "P1 NOT_REVIEWED"):
            self.service.create_export(self.loaded, intended_role=EXPORT_INTENDED_ROLE_CALIBRATION)

    def test_calibration_p2_incomplete_blocked(self) -> None:
        meta = self.loaded["run_meta"]
        for episode in self.loaded["episodes"]:
            self.store.save_episode(
                run_id=self.loaded["run_id"], episode_id=episode.episode_id,
                signal_contract_version=meta["signal_contract_version"],
                signal_contract_hash=meta["signal_contract_hash"],
                episode_length=episode.length, predicted={},
                signals={name: {"decision": "PASS", "comment": ""} for name in SIGNAL_NAMES},
                boundaries={}, added=[], episode_note="",
            )
        self._as_calibration_baseline()
        with self.assertRaisesRegex(ExportBlocked, "P2 NOT_REVIEWED"):
            self.service.create_export(self.loaded, intended_role=EXPORT_INTENDED_ROLE_CALIBRATION)

    def test_calibration_wrong_calibration_role_blocked(self) -> None:
        self._complete()
        self._as_calibration_baseline(calibration_role="SEARCH_CANDIDATE")
        assess = self.service.assess(self.loaded)
        self.assertTrue(assess["review_ready"])
        self.assertFalse(assess["export_eligible"])
        self.assertFalse(assess["ready"])
        with self.assertRaisesRegex(ExportBlocked, "source identity is not eligible"):
            self.service.create_export(self.loaded, intended_role=EXPORT_INTENDED_ROLE_CALIBRATION)

    def test_calibration_wrong_config_role_blocked(self) -> None:
        self._complete()
        self._as_calibration_baseline(calibration_config_role="SEARCHED")
        with self.assertRaisesRegex(ExportBlocked, "source identity is not eligible"):
            self.service.create_export(self.loaded, intended_role=EXPORT_INTENDED_ROLE_CALIBRATION)

    def test_calibration_source_rejects_seed_role(self) -> None:
        self._complete()
        self._as_calibration_baseline()
        assess = self.service.assess(self.loaded, intended_role="CALIBRATION_SEED")
        self.assertFalse(assess["export_eligible"])
        with self.assertRaisesRegex(ExportBlocked, "does not match frozen mapping"):
            self.service.create_export(self.loaded, intended_role="CALIBRATION_SEED")

    def test_exploratory_source_rejects_calibration_role(self) -> None:
        self._complete()
        assess = self.service.assess(self.loaded, intended_role=EXPORT_INTENDED_ROLE_CALIBRATION)
        self.assertFalse(assess["export_eligible"])
        self.assertFalse(assess["ready"])
        with self.assertRaisesRegex(ExportBlocked, "does not match frozen mapping"):
            self.service.create_export(self.loaded, intended_role=EXPORT_INTENDED_ROLE_CALIBRATION)

    def test_assess_create_validate_share_eligibility(self) -> None:
        self._complete()
        seed_assess = self.service.assess(self.loaded)
        self.assertEqual(seed_assess["ready"], seed_assess["review_ready"] and seed_assess["export_eligible"])
        self.assertEqual(seed_assess["intended_role"], "CALIBRATION_SEED")
        result = self.service.create_export(self.loaded, intended_role="CALIBRATION_SEED")
        meta = json.loads((Path(result["export_path"]) / "export_meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["intended_role"], seed_assess["intended_role"])
        self._as_calibration_baseline()
        cal_assess = self.service.assess(self.loaded)
        self.assertTrue(cal_assess["effective_export_ready"])
        self.assertEqual(cal_assess["intended_role"], "CALIBRATION")
        cal = self.service.create_export(self.loaded, intended_role=EXPORT_INTENDED_ROLE_CALIBRATION)
        cal_meta = json.loads((Path(cal["export_path"]) / "export_meta.json").read_text(encoding="utf-8"))
        self.assertEqual(cal_meta["intended_role"], cal_assess["intended_role"])
        self.assertEqual(resolve_export_role(self.loaded), cal_assess["intended_role"])

    def test_web_calibration_baseline_uses_resolved_role(self) -> None:
        self._complete()
        self._as_calibration_baseline()
        registry = self.root / "registry.json"
        auto_register(registry, self.run_root)
        app = create_app(
            project_root=self.root, registry_path=registry, owner_db_path=self.db,
            review_store=self.store,
        )
        client = TestClient(app)
        encoded = encode_episode_id("data/demo_0")
        response = client.post(f"/audit/{self.loaded['run_id']}/episode/{encoded}/export", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn("exported=g1_cal_export_", response.headers["location"])
        history = app.state.calibration_exporter.list_exports(source_run_id=self.loaded["run_id"])
        self.assertEqual(history[0]["intended_role"], "CALIBRATION")
        self.assertEqual(history[0]["source_run_stage"], "CALIBRATION")


if __name__ == "__main__":
    unittest.main()
