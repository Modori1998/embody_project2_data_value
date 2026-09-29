from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path

from project2_g1.formal_evaluation_run import (
    EXPECTED_EPISODES, MANIFEST_VERSION, TAU_C12, TAU_P12, WINDOW,
    freeze_integrity, frozen_runtime_snapshot,
)
from project2_g1.paths import PROJECT2_ROOT
from project2_g1_audit_web.app import create_app
from project2_g1_audit_web.view import run_header

class FormalEvaluationRunTests(unittest.TestCase):
    def test_frozen_identity_and_no_search_surface(self):
        self.assertEqual(len(EXPECTED_EPISODES), 24)
        self.assertEqual(len(set(EXPECTED_EPISODES)), 24)
        self.assertEqual(MANIFEST_VERSION, "G1_P4_EVAL_MANIFEST_v1")
        self.assertEqual((TAU_P12, TAU_C12, WINDOW), (0.04758563666765155, 0.690169167642685, 8))
        snapshot = frozen_runtime_snapshot(PROJECT2_ROOT)
        self.assertEqual(snapshot["boundary_consolidation_window"], 8)
        self.assertNotIn("search_space", snapshot)

    def test_freeze_gate_exact_and_disjoint(self):
        audit = freeze_integrity(PROJECT2_ROOT)
        self.assertEqual(audit["status"], "PASS")
        self.assertEqual(audit["episode_ids"], list(EXPECTED_EPISODES))
        self.assertEqual(audit["checks"]["overlap_exploratory"], 0)
        self.assertEqual(audit["checks"]["overlap_calibration"], 0)
        self.assertEqual(audit["checks"]["overlap_diagnostic"], 0)

    def test_evaluation_header_identity(self):
        loaded = {"run_meta": {"run_id": "eval", "run_stage": "EVALUATION", "created_at": "x", "config_hash": "a" * 64, "episode_count": 24, "evaluation_manifest_version": MANIFEST_VERSION, "frozen_config_identity": "G1 Final Config FROZEN_v1", "must_not_feed_back_to_calibration": True}}
        header = run_header(loaded)
        self.assertTrue(header.evaluation_no_tuning)
        self.assertTrue(header.must_not_feed_back_to_calibration)

    def test_no_scoring_or_gt_dependency_in_builder(self):
        source = (PROJECT2_ROOT / "src/project2_g1/formal_evaluation_run.py").read_text(encoding="utf-8")
        for forbidden in ("baseline_scoring", "match_by_episode", "canonical_gt", "formal_evaluation_score.json"):
            self.assertNotIn(forbidden, source.lower())

    def test_isolated_web_can_initialize(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); registry = root / "registry.json"
            registry.write_text(json.dumps({"schema_version": 1, "contract_version": "P2_G1_AUDIT_FOLDER_V1", "runs": {}}), encoding="utf-8")
            db = root / "evaluation.sqlite"
            app = create_app(project_root=PROJECT2_ROOT, registry_path=registry, owner_db_path=db, proxy_cache_root=root / "cache")
            self.assertTrue(db.is_file())
            self.assertEqual(Path(app.state.review_store.sqlite_path), db.resolve())

if __name__ == "__main__": unittest.main()
