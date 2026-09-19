"""Baseline scoring identity, metrics, artifacts, and immutability tests."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.baseline_scoring import (
    EXPECTED_RUN_ID,
    EXPECTED_SNAPSHOT_ID,
    FN_FIELDS,
    FP_FIELDS,
    METRIC_VERSION,
    SQLITE_SHA256,
    fragmentation_diagnostics,
    gt_spacing_diagnostics,
    load_baseline_run,
    load_canonical_snapshot,
    match_known_fp_anchors,
    ratio,
    validate_score_dir,
)
from project2_g1.boundary_matching import TOLERANCE_FRAMES
from project2_g1_audit_web.hashes import sha256_file, tree_fingerprint
from project2_g1.baseline_scoring import MetricZeroDenominatorError


class ScoringPrimitiveTests(unittest.TestCase):
    def test_tolerance_is_fixed_three(self) -> None:
        self.assertEqual(TOLERANCE_FRAMES, 3)

    def test_zero_denominator_is_contract_gap(self) -> None:
        with self.assertRaises(MetricZeroDenominatorError):
            ratio(0, 0, name="precision")

    def test_gt_spacing_warn_uses_two_t(self) -> None:
        rows = [
            {"episode_id": "e", "gt_frame": "0"},
            {"episode_id": "e", "gt_frame": "9"},
        ]
        diag = gt_spacing_diagnostics(rows)
        self.assertFalse(diag["gt_spacing_warn"])
        self.assertEqual(diag["min_gt_spacing_frames"], 9)
        close = gt_spacing_diagnostics([
            {"episode_id": "e", "gt_frame": "0"},
            {"episode_id": "e", "gt_frame": "6"},
        ])
        self.assertTrue(close["gt_spacing_warn"])

    def test_short_segment_ratio_is_contract_gap(self) -> None:
        frag = fragmentation_diagnostics([
            {"episode_id": "e", "duration_frames": "1"},
            {"episode_id": "e", "duration_frames": "8"},
        ])
        self.assertEqual(frag["1_2_frame_segment_ratio"], 0.5)
        self.assertTrue(frag["FRAGMENTATION_SHORT_RATIO_CONTRACT_GAP"])
        self.assertIsNone(frag["short_segment_ratio"])
        self.assertEqual(frag["short_segment_ratio_status"], "NOT_COMPUTED_CONTRACT_GAP")

    def test_unassigned_anchors_are_known_fp_not_new(self) -> None:
        preds = [
            {"episode_id": "e", "pred_id": "P1", "pred_frame": 10, "pred_boundary_id": "P1"},
            {"episode_id": "e", "pred_id": "P2", "pred_frame": 40, "pred_boundary_id": "P2"},
        ]
        anchors = [
            {"episode_id": "e", "anchor_frame": "10", "error_mode": "UNASSIGNED", "reason_code": "REDUNDANT_SHORT_PAUSE", "source_package": "FRESH", "source_boundary_id": "B1"},
            {"episode_id": "e", "anchor_frame": "40", "error_mode": "MODE_01", "reason_code": "REDUNDANT_DIRECTION_JITTER", "source_package": "SEED", "source_boundary_id": "B2"},
        ]
        _anchor_status, pred_status = match_known_fp_anchors(preds, anchors)
        self.assertFalse(pred_status["P1"]["is_new_unanchored_fp"])
        self.assertEqual(pred_status["P1"]["known_fp_error_mode"], "UNASSIGNED")
        self.assertFalse(pred_status["P2"]["is_new_unanchored_fp"])

    def test_new_unanchored_fp_outside_all_anchors(self) -> None:
        preds = [
            {"episode_id": "e", "pred_id": "Pnew", "pred_frame": 80, "pred_boundary_id": "Pnew"},
        ]
        anchors = [
            {"episode_id": "e", "anchor_frame": "10", "error_mode": "UNASSIGNED", "reason_code": "X", "source_package": "FRESH", "source_boundary_id": "B1"},
        ]
        _anchor_status, pred_status = match_known_fp_anchors(preds, anchors)
        self.assertTrue(pred_status["Pnew"]["is_new_unanchored_fp"])
        self.assertEqual(pred_status["Pnew"]["reason_code"], "NEW_UNANCHORED_FP")

    def test_empty_fn_and_fp_schema_round_trip(self) -> None:
        temp = tempfile.TemporaryDirectory()
        try:
            fn_path = Path(temp.name) / "unmatched_gt_fn.csv"
            fp_path = Path(temp.name) / "unmatched_predictions_fp.csv"
            with fn_path.open("w", encoding="utf-8", newline="") as handle:
                csv.DictWriter(handle, fieldnames=FN_FIELDS).writeheader()
            with fp_path.open("w", encoding="utf-8", newline="") as handle:
                csv.DictWriter(handle, fieldnames=FP_FIELDS).writeheader()
            with fn_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(list(reader.fieldnames), list(FN_FIELDS))
                self.assertEqual(list(reader), [])
            with fp_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(list(reader.fieldnames), list(FP_FIELDS))
                self.assertEqual(list(reader), [])
        finally:
            temp.cleanup()


class OfficialInputIdentityTests(unittest.TestCase):
    def test_canonical_snapshot_exact_identity(self) -> None:
        loaded = load_canonical_snapshot(
            ROOT / "outputs/g1_p3_canonical_gt" / EXPECTED_SNAPSHOT_ID
        )
        self.assertEqual(loaded["meta"]["canonical_gt_snapshot_id"], EXPECTED_SNAPSHOT_ID)
        self.assertEqual(int(loaded["meta"]["episode_count"]), 12)
        self.assertEqual(len(loaded["gt_rows"]), 56)
        self.assertEqual(len(loaded["fp_rows"]), 10)
        self.assertEqual(int(loaded["meta"]["conflict_count"]), 0)
        self.assertEqual(len(set(loaded["manifest"]["episode_ids"])), 12)

    def test_baseline_run_exact_identity(self) -> None:
        snapshot = load_canonical_snapshot(
            ROOT / "outputs/g1_p3_canonical_gt" / EXPECTED_SNAPSHOT_ID
        )
        run = load_baseline_run(
            ROOT / "outputs/g1_audit_runs" / EXPECTED_RUN_ID,
            expected_episodes={str(item) for item in snapshot["manifest"]["episode_ids"]},
        )
        self.assertEqual(run["meta"]["run_id"], EXPECTED_RUN_ID)
        self.assertEqual(run["meta"]["run_stage"], "CALIBRATION")
        self.assertEqual(run["meta"]["search_stage"], "BASELINE")
        self.assertEqual(int(run["meta"]["episode_count"]), 12)
        self.assertEqual(run["validator"], "PASS")
        self.assertEqual(run["loaded"]["final_member_semantics"], "MATERIALIZED")
        self.assertEqual(run["meta"]["config_hash"], snapshot["manifest"]["config_baseline_hash"])
        self.assertEqual(run["meta"]["signal_contract_hash"], snapshot["manifest"]["signal_contract_hash"])


class OfficialScoreArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        scoring_root = ROOT / "outputs/g1_p3_scoring"
        if not scoring_root.is_dir():
            raise unittest.SkipTest("scoring artifact not materialized yet")
        scores = [path for path in scoring_root.iterdir() if path.is_dir() and path.name.startswith("g1_baseline_score_")]
        if not scores:
            raise unittest.SkipTest("scoring artifact not materialized yet")
        latest = max(scores, key=lambda path: path.name)
        cls.loaded = validate_score_dir(latest)
        cls.score_root = latest

    def test_core_metrics_and_pairs(self) -> None:
        metrics = self.loaded["metrics"]
        self.assertEqual(metrics["TP"], 56)
        self.assertEqual(metrics["FP"], 10)
        self.assertEqual(metrics["FN"], 0)
        self.assertEqual(metrics["EXACT_TP"], 56)
        self.assertEqual(metrics["NEAR_TP"], 0)
        self.assertEqual(metrics["FN_BASELINE"], 0)
        self.assertAlmostEqual(metrics["Precision"], 56 / 66)
        self.assertEqual(metrics["Recall"], 1.0)
        self.assertAlmostEqual(metrics["F1"], 112 / 122)
        self.assertEqual(self.loaded["meta"]["metric_version"], METRIC_VERSION)
        self.assertEqual(int(self.loaded["meta"]["tolerance_frames"]), 3)

    def test_guardrails_and_known_fp(self) -> None:
        metrics = self.loaded["metrics"]
        guard = json.loads((self.score_root / "guardrail_metrics.json").read_text(encoding="utf-8"))
        self.assertEqual(guard["CALIBRATION_GRIPPER_RECALL"], 1.0)
        self.assertEqual(guard["CALIBRATION_MERGED_CLUSTER_RECALL"], 1.0)
        self.assertEqual(guard["SEED_VALID_DIRECTION_RECALL"], 1.0)
        self.assertEqual(guard["FRESH_VALID_DIRECTION_RECALL_BASELINE"], 1.0)
        self.assertEqual(metrics["MODE_01_REMAINING"], 3)
        self.assertEqual(metrics["MODE_02_REMAINING"], 3)
        self.assertEqual(metrics["MODE_03_REMAINING"], 1)
        self.assertEqual(metrics["UNASSIGNED_KNOWN_FP_REMAINING"], 3)
        self.assertEqual(metrics["NEW_UNANCHORED_FP_COUNT"], 0)
        self.assertEqual(metrics["KNOWN_FP_ANCHOR_TOTAL"], 10)

    def test_empty_fn_file_keeps_header(self) -> None:
        with (self.score_root / "unmatched_gt_fn.csv").open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            self.assertEqual(list(reader.fieldnames), list(FN_FIELDS))
            self.assertEqual(list(reader), [])

    def test_oversegmentation_and_episode_set(self) -> None:
        metrics = self.loaded["metrics"]
        self.assertEqual(metrics["episode_oversegmented_count"], 4)
        self.assertEqual(metrics["total_oversegmentation"], 10)
        self.assertEqual(metrics["mean_predicted_boundaries_per_episode"], 5.5)
        self.assertAlmostEqual(metrics["mean_gt_boundaries_per_episode"], 56 / 12)
        self.assertEqual(
            set(metrics["oversegmented_episodes"]),
            {"data/demo_162", "data/demo_242", "data/demo_255", "data/demo_278"},
        )
        with (self.score_root / "episode_metrics.csv").open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 12)
        by_id = {row["episode_id"]: int(row["over_segmentation"]) for row in rows}
        self.assertEqual(by_id["data/demo_162"], 1)
        self.assertEqual(by_id["data/demo_242"], 4)
        self.assertEqual(by_id["data/demo_255"], 2)
        self.assertEqual(by_id["data/demo_278"], 3)

    def test_atomic_artifact_not_mutated_by_validation(self) -> None:
        before = {name: sha256_file(self.score_root / name) for name in (
            "score_meta.json", "baseline_metrics.json", "matching_pairs.csv", "unmatched_gt_fn.csv"
        )}
        validate_score_dir(self.score_root)
        after = {name: sha256_file(self.score_root / name) for name in before}
        self.assertEqual(before, after)

    def test_immutability_fingerprints(self) -> None:
        self.assertEqual(
            sha256_file(ROOT / "outputs/g1_audit_web/g1_audit_web_owner.sqlite3"),
            SQLITE_SHA256,
        )
        self.assertEqual(
            tree_fingerprint(ROOT / "outputs/g1_p3_canonical_gt" / EXPECTED_SNAPSHOT_ID)["tree_fingerprint"],
            "335a8d62d9871e26f34a6e887206cbb48504dfc551337c024086e7252ac399ef",
        )


if __name__ == "__main__":
    unittest.main()
