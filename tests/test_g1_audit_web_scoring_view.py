"""G1 Audit Web read-only Baseline Scoring comparison view tests."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = Path(__file__).resolve().parent
for path in (SRC, TESTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from unittest.mock import Mock

from fastapi.testclient import TestClient

from g1_audit_web_fixtures import write_synthetic_run
from project2_g1_audit_web.app import create_app
from project2_g1_audit_web.registry import auto_register
from project2_g1_audit_web.scoring_view import (
    MATCH_FN,
    MATCH_FP,
    MATCH_TP,
    ScoringUnavailable,
    build_episode_comparison,
    build_run_overview,
    discover_score,
    load_bundle,
)
from project2_g1_audit_web.service import G1AuditWebInput

RUN_ID = "g1_calibration_test_000000000000"
SNAPSHOT_ID = "g1_canonical_gt_test_000000000000"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _make_score(root: Path, score_id: str) -> Path:
    score_dir = root / "outputs" / "g1_p3_scoring" / score_id
    _write(
        score_dir / "score_meta.json",
        json.dumps(
            {
                "score_id": score_id,
                "run_id": RUN_ID,
                "canonical_gt_snapshot_id": SNAPSHOT_ID,
                "matching_rule_id": "MAX_CARDINALITY_MIN_TOTAL_DISTANCE_ONE_TO_ONE_V1",
                "tolerance_frames": 3,
                "tolerance_seconds": 0.15,
                "scored_at": "2026-09-18T15:57:14+08:00",
            }
        ),
    )
    _write(
        score_dir / "baseline_metrics.json",
        json.dumps(
            {
                "TP": 2,
                "FP": 1,
                "FN": 1,
                "Precision": 0.6666666666666666,
                "Recall": 0.6666666666666666,
                "F1": 0.6666666666666666,
                "MODE_01_REMAINING": 1,
                "MODE_02_REMAINING": 0,
                "MODE_03_REMAINING": 0,
                "UNASSIGNED_KNOWN_FP_REMAINING": 0,
                "NEW_UNANCHORED_FP_COUNT": 0,
            }
        ),
    )
    _csv(
        score_dir / "matching_pairs.csv",
        [
            "episode_id", "gt_id", "gt_frame", "pred_boundary_id", "pred_frame",
            "delta_frame", "abs_error_frames", "abs_error_seconds", "gt_source",
            "protected_class", "source_package", "pred_candidate_type",
            "pred_representative_candidate_id", "match_class",
        ],
        [
            {
                "episode_id": "data/demo_0", "gt_id": "data/demo_0-HGT0001", "gt_frame": "4",
                "pred_boundary_id": "demo_0-B0001", "pred_frame": "4", "delta_frame": "0",
                "abs_error_frames": "0", "abs_error_seconds": "0.0", "gt_source": "VALID_INHERIT",
                "protected_class": "GRIPPER_PRIMARY", "source_package": "SEED",
                "pred_candidate_type": "GRIPPER_TRANSITION",
                "pred_representative_candidate_id": "demo_0-C0001", "match_class": "EXACT",
            },
            {
                "episode_id": "data/demo_1", "gt_id": "data/demo_1-HGT0001", "gt_frame": "4",
                "pred_boundary_id": "demo_1-B0001", "pred_frame": "4", "delta_frame": "0",
                "abs_error_frames": "0", "abs_error_seconds": "0.0", "gt_source": "VALID_INHERIT",
                "protected_class": "GRIPPER_PRIMARY", "source_package": "SEED",
                "pred_candidate_type": "GRIPPER_TRANSITION",
                "pred_representative_candidate_id": "demo_1-C0001", "match_class": "EXACT",
            },
        ],
    )
    _csv(
        score_dir / "unmatched_predictions_fp.csv",
        [
            "episode_id", "pred_boundary_id", "pred_frame", "candidate_type",
            "representative_candidate_id", "member_candidate_types", "member_candidate_frames",
            "known_fp_anchor_matched", "known_fp_anchor_frame", "known_fp_error_mode",
            "reason_code", "is_new_unanchored_fp",
        ],
        [
            {
                "episode_id": "data/demo_0", "pred_boundary_id": "demo_0-B0002", "pred_frame": "41",
                "candidate_type": "DIRECTION_CHANGE", "representative_candidate_id": "demo_0-C0002",
                "member_candidate_types": "DIRECTION_CHANGE", "member_candidate_frames": "41",
                "known_fp_anchor_matched": "true", "known_fp_anchor_frame": "41",
                "known_fp_error_mode": "MODE_01", "reason_code": "REDUNDANT_DIRECTION_JITTER",
                "is_new_unanchored_fp": "false",
            },
        ],
    )
    _csv(
        score_dir / "unmatched_gt_fn.csv",
        [
            "episode_id", "gt_id", "gt_frame", "gt_source", "protected_class", "source_package",
        ],
        [
            {
                "episode_id": "data/demo_1", "gt_id": "data/demo_1-HGT0002", "gt_frame": "10",
                "gt_source": "VALID_INHERIT", "protected_class": "VALID_DIRECTION_PRIMARY",
                "source_package": "SEED",
            },
        ],
    )
    return score_dir


def _make_canonical_gt(root: Path) -> Path:
    gt_dir = root / "outputs" / "g1_p3_canonical_gt" / SNAPSHOT_ID
    _csv(
        gt_dir / "canonical_human_boundary_gt.csv",
        [
            "canonical_gt_snapshot_id", "gt_id", "episode_id", "gt_frame", "gt_source",
            "protected_class", "source_package", "source_export_id", "source_run_id",
            "source_boundary_id", "source_review_id", "human_decision", "reason_code",
            "comment", "source_run_stage", "source_set_role",
        ],
        [
            {
                "canonical_gt_snapshot_id": SNAPSHOT_ID, "gt_id": "data/demo_0-HGT0001",
                "episode_id": "data/demo_0", "gt_frame": "4", "gt_source": "VALID_INHERIT",
                "protected_class": "GRIPPER_PRIMARY", "source_package": "SEED",
                "source_export_id": "seed", "source_run_id": "seed-run", "source_boundary_id": "demo_0-B0001",
                "source_review_id": "1", "human_decision": "VALID", "reason_code": "", "comment": "",
                "source_run_stage": "EXPLORATORY_AUDIT", "source_set_role": "EXPLORATORY",
            },
            {
                "canonical_gt_snapshot_id": SNAPSHOT_ID, "gt_id": "data/demo_1-HGT0001",
                "episode_id": "data/demo_1", "gt_frame": "4", "gt_source": "VALID_INHERIT",
                "protected_class": "GRIPPER_PRIMARY", "source_package": "SEED",
                "source_export_id": "seed", "source_run_id": "seed-run", "source_boundary_id": "demo_1-B0001",
                "source_review_id": "2", "human_decision": "VALID", "reason_code": "", "comment": "",
                "source_run_stage": "EXPLORATORY_AUDIT", "source_set_role": "EXPLORATORY",
            },
            {
                "canonical_gt_snapshot_id": SNAPSHOT_ID, "gt_id": "data/demo_1-HGT0002",
                "episode_id": "data/demo_1", "gt_frame": "10", "gt_source": "VALID_INHERIT",
                "protected_class": "VALID_DIRECTION_PRIMARY", "source_package": "SEED",
                "source_export_id": "seed", "source_run_id": "seed-run", "source_boundary_id": "demo_1-B0002",
                "source_review_id": "3", "human_decision": "VALID", "reason_code": "", "comment": "",
                "source_run_stage": "EXPLORATORY_AUDIT", "source_set_role": "EXPLORATORY",
            },
        ],
    )
    _csv(
        gt_dir / "known_false_positive_anchor.csv",
        [
            "canonical_gt_snapshot_id", "episode_id", "anchor_frame", "source_package",
            "source_export_id", "source_run_id", "source_boundary_id", "source_review_id",
            "candidate_type", "representative_candidate_id", "member_candidate_ids",
            "member_candidate_types", "member_candidate_frames", "member_candidate_count",
            "reason_code", "comment", "error_mode",
        ],
        [],
    )
    return gt_dir


class ScoringViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)
        _make_score(self.root, "g1_baseline_score_test_00000001")
        _make_canonical_gt(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_discover_score_picks_latest(self) -> None:
        _make_score(self.root, "g1_baseline_score_test_00000002")
        found = discover_score(self.root, RUN_ID)
        self.assertIsNotNone(found)
        self.assertEqual(found["score_id"], "g1_baseline_score_test_00000002")

    def test_discover_score_missing_run_returns_none(self) -> None:
        self.assertIsNone(discover_score(self.root, "g1_no_such_run"))

    def test_load_bundle_groups_artifacts(self) -> None:
        bundle = load_bundle(self.root, RUN_ID)
        self.assertEqual(bundle.score_id, "g1_baseline_score_test_00000001")
        self.assertEqual(len(bundle.matching_pairs), 2)
        self.assertEqual(len(bundle.unmatched_predictions_fp), 1)
        self.assertEqual(len(bundle.unmatched_gt_fn), 1)
        self.assertEqual(len(bundle.canonical_gt), 3)
        self.assertEqual(bundle.tp_by_episode["data/demo_0"][0]["gt_id"], "data/demo_0-HGT0001")
        self.assertEqual(bundle.fn_by_episode["data/demo_1"][0]["gt_id"], "data/demo_1-HGT0002")

    def test_load_bundle_missing_score_raises(self) -> None:
        with self.assertRaises(ScoringUnavailable):
            load_bundle(self.root, "g1_no_such_run")


class ScoringOverviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)
        self.run_root = write_synthetic_run(self.root / "runs", run_id=RUN_ID, n_episodes=2)
        auto_register(self.root / "web" / "g1_audit_run_registry.json", self.run_root)
        _make_score(self.root, "g1_baseline_score_test_00000001")
        _make_canonical_gt(self.root)
        self.bundle = load_bundle(self.root, RUN_ID)
        self.service = G1AuditWebInput(
            project_root=self.root,
            registry_path=self.root / "web" / "g1_audit_run_registry.json",
            owner_db_path=self.root / "web" / "owner.sqlite3",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_run_overview_counts(self) -> None:
        loaded = self.service.load_validated_run(RUN_ID)
        overview = build_run_overview(self.bundle, loaded["episodes"])
        self.assertEqual(overview["totals"], {"tp": 2, "fp": 1, "fn": 1})
        by_id = {row["episode_id"]: row for row in overview["episodes"]}
        self.assertEqual(by_id["data/demo_0"]["tp"], 1)
        self.assertEqual(by_id["data/demo_0"]["fp"], 1)
        self.assertEqual(by_id["data/demo_0"]["fn"], 0)
        self.assertEqual(by_id["data/demo_1"]["tp"], 1)
        self.assertEqual(by_id["data/demo_1"]["fn"], 1)
        self.assertEqual(by_id["data/demo_1"]["fp"], 0)

    def test_episode_comparison_timeline(self) -> None:
        boundaries = [
            {"boundary_id": "demo_0-B0001", "frame": "4", "candidate_type": "GRIPPER_TRANSITION", "reason": "X"},
            {"boundary_id": "demo_0-B0002", "frame": "41", "candidate_type": "DIRECTION_CHANGE", "reason": "Y"},
        ]
        comparison = build_episode_comparison(
            self.bundle, episode_id="data/demo_0", boundaries=boundaries, length=50
        )
        self.assertEqual(comparison["counts"], {"n_gt": 1, "n_pred": 2, "tp": 1, "fp": 1, "fn": 0})
        statuses = {row["status"]: row for row in comparison["timeline"]}
        self.assertEqual(statuses[MATCH_TP]["pred"]["boundary_id"], "demo_0-B0001")
        self.assertEqual(statuses[MATCH_FP]["pred"]["boundary_id"], "demo_0-B0002")
        self.assertIn("MODE_01", statuses[MATCH_FP]["note"])

    def test_episode_comparison_fn_status(self) -> None:
        boundaries = [
            {"boundary_id": "demo_1-B0001", "frame": "4", "candidate_type": "GRIPPER_TRANSITION", "reason": "X"},
        ]
        comparison = build_episode_comparison(
            self.bundle, episode_id="data/demo_1", boundaries=boundaries, length=50
        )
        self.assertEqual(comparison["counts"]["fn"], 1)
        fn_rows = [row for row in comparison["timeline"] if row["status"] == MATCH_FN]
        self.assertEqual(fn_rows[0]["gt"]["gt_id"], "data/demo_1-HGT0002")


class ScoringRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)
        self.run_root = write_synthetic_run(self.root / "runs", run_id=RUN_ID, n_episodes=2)
        registry = self.root / "web" / "g1_audit_run_registry.json"
        auto_register(registry, self.run_root)
        _make_score(self.root, "g1_baseline_score_test_00000001")
        _make_canonical_gt(self.root)
        self.service = G1AuditWebInput(
            project_root=self.root,
            registry_path=registry,
            owner_db_path=self.root / "web" / "owner.sqlite3",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _client(self) -> TestClient:
        app = create_app(project_root=self.root, web_input=self.service, video_proxy=Mock())
        return TestClient(app)

    def test_overview_and_episode_render(self) -> None:
        client = self._client()
        overview = client.get(f"/audit/{RUN_ID}/scoring")
        self.assertEqual(overview.status_code, 200)
        self.assertIn("复核条例", overview.text)
        episode = client.get(f"/audit/{RUN_ID}/scoring/data--demo_0")
        self.assertEqual(episode.status_code, 200)
        self.assertIn("逐帧并排对照", episode.text)
        self.assertIn("fp-tag", episode.text)

    def test_no_scoring_fallback(self) -> None:
        other = write_synthetic_run(self.root / "runs", run_id="g1_no_score_run_000000000000", n_episodes=1)
        auto_register(self.root / "web" / "g1_audit_run_registry.json", other)
        client = self._client()
        response = client.get("/audit/g1_no_score_run_000000000000/scoring")
        self.assertEqual(response.status_code, 400)
        self.assertIn("SCORING_UNAVAILABLE", response.text)


if __name__ == "__main__":
    unittest.main()
