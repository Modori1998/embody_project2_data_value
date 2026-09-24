import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from project2_g1.boundary_config import load_g1_p2_config
from project2_g1.boundary_engine import (
    BoundaryCandidate, BoundaryDecision, BoundaryEvent, CANDIDATE_DIRECTION,
    CANDIDATE_GRIPPER, CANDIDATE_IDLE_TO_MOVE, DECISION_KEEP,
    DECISION_MERGE_CONSOLIDATION,
)
from project2_g1.stage_b_calibration import (
    CANDIDATE_FIELDS, CHANGED_FIELDS, DIAGNOSTIC_SET_THRESHOLD_USAGE, EVALUATION_USAGE, STAGE_A_PARENT,
    STAGE_B_WINDOWS, TAU_C12, TAU_P12, StageBCalibrationError,
    assert_single_factor, changed_cluster_lineage, demo242_trace, demo255_trace, hard_guardrail,
    runtime_config,
)


def candidate(cid, frame, kind):
    return BoundaryCandidate("data/demo_255", cid, frame, kind, "reason", [], 1.0,
                             "PERSISTENT", "signal", "v")


def event(bid, frame, kind, rep, ids, types, frames):
    return BoundaryEvent(bid, "data/demo_255", frame, kind, "reason", ids,
                         representative_candidate_id=rep,
                         member_candidate_types=types,
                         member_candidate_frames=frames,
                         member_candidate_count=len(ids))


def result_for_255(merged=True):
    c1 = candidate("C1", 125, CANDIDATE_GRIPPER)
    c2 = candidate("C2", 135, CANDIDATE_IDLE_TO_MOVE)
    if merged:
        events = [event("B1", 125, CANDIDATE_GRIPPER, "C1", ["C1", "C2"],
                        [CANDIDATE_GRIPPER, CANDIDATE_IDLE_TO_MOVE], [125, 135])]
        decisions = {"C1": BoundaryDecision("C1", DECISION_KEEP, "", "B1"),
                     "C2": BoundaryDecision("C2", DECISION_MERGE_CONSOLIDATION, "", "B1")}
    else:
        events = [event("B1", 125, CANDIDATE_GRIPPER, "C1", ["C1"], [CANDIDATE_GRIPPER], [125]),
                  event("B2", 135, CANDIDATE_IDLE_TO_MOVE, "C2", ["C2"], [CANDIDATE_IDLE_TO_MOVE], [135])]
        decisions = {"C1": BoundaryDecision("C1", DECISION_KEEP, "", "B1"),
                     "C2": BoundaryDecision("C2", DECISION_KEEP, "", "B2")}
    return SimpleNamespace(episode_id="data/demo_255", candidates=[c1, c2], decisions=decisions,
                           events=events, final_events=events)


class StageBTests(unittest.TestCase):
    def test_search_space_and_parent_are_frozen(self):
        self.assertEqual(STAGE_B_WINDOWS, (8, 10, 12))
        self.assertEqual(STAGE_A_PARENT, "A1-007-C002")
        self.assertEqual(TAU_P12, 0.04758563666765155)
        self.assertEqual(TAU_C12, 0.690169167642685)

    def test_window_override_reaches_config(self):
        self.assertEqual([runtime_config(w).boundary_consolidation_window for w in STAGE_B_WINDOWS], [8, 10, 12])
        with self.assertRaises(StageBCalibrationError):
            runtime_config(9)

    def test_configs_are_single_factor_and_deterministic(self):
        configs = [runtime_config(w) for w in STAGE_B_WINDOWS]
        assert_single_factor(configs)
        self.assertEqual(configs, [runtime_config(w) for w in STAGE_B_WINDOWS])

    def test_single_factor_rejects_other_change(self):
        from dataclasses import replace
        base = load_g1_p2_config()
        with self.assertRaises(StageBCalibrationError):
            assert_single_factor([runtime_config(8, base), replace(runtime_config(10, base), pause_bridge_duration=11)])

    def test_demo255_lineage_separate_at_control(self):
        rows = demo255_trace([result_for_255(False)], 8)
        self.assertTrue(all(r["SAME_FINAL_CLUSTER"] == "NO" for r in rows))

    def test_demo255_lineage_merged(self):
        rows = demo255_trace([result_for_255(True)], 10)
        self.assertTrue(all(r["SAME_FINAL_CLUSTER"] == "YES" for r in rows))
        self.assertEqual(rows[1]["representative_candidate_id"], "C1")

    def test_changed_cluster_preserves_representative(self):
        old = result_for_255(False)
        new = result_for_255(True)
        pairs = [SimpleNamespace(pred_id="data/demo_255:B1", gt_id="G1"),
                 SimpleNamespace(pred_id="data/demo_255:B2", gt_id="G2")]
        snapshot = {"gt_rows": [], "fp_rows": []}
        # Isolate cluster-diff semantics from frozen matching in this unit test.
        from unittest.mock import patch
        details_old = {"pair_by_pred": {p.pred_id: p for p in pairs}}
        details_new = {"pair_by_pred": {pairs[0].pred_id: pairs[0]}}
        with patch("project2_g1.stage_b_calibration.scoring_details", side_effect=[details_old, details_new]):
            rows = changed_cluster_lineage([old], [new], snapshot, 10)
        self.assertEqual(rows[0]["REPRESENTATIVE_FRAME_CHANGED"], "NO")
        self.assertEqual(rows[0]["TWO_VALID_GT_MERGED"], "YES")

    def test_demo242_status(self):
        c = candidate("D1", 60, CANDIDATE_DIRECTION)
        c.episode_id = "data/demo_242"
        e = event("B1", 60, CANDIDATE_DIRECTION, "D1", ["D1"], [CANDIDATE_DIRECTION], [60])
        e.episode_id = "data/demo_242"
        r = SimpleNamespace(episode_id="data/demo_242", candidates=[c],
                            decisions={"D1": BoundaryDecision("D1", DECISION_KEEP, "", "B1")},
                            events=[e], final_events=[e])
        self.assertEqual(demo242_trace([r], 8)["FINAL_STATUS"], "REMAINING")

    def test_guardrail_includes_unanchored_fp(self):
        base = {"Fresh_valid_direction_recall": 1.0, "FN": 0}
        metrics = {"Gripper_recall": 1.0, "Merged_cluster_recall": 1.0,
                   "Seed_valid_direction_recall": 1.0, "Fresh_valid_direction_recall": 1.0,
                   "FN": 0, "NEW_UNANCHORED_FP": 0}
        self.assertTrue(hard_guardrail(metrics, base))
        metrics["NEW_UNANCHORED_FP"] = 1
        self.assertFalse(hard_guardrail(metrics, base))

    def test_diagnostic_and_evaluation_are_forbidden(self):
        self.assertEqual(DIAGNOSTIC_SET_THRESHOLD_USAGE, "FORBIDDEN")
        self.assertEqual(EVALUATION_USAGE, "FORBIDDEN")

    def test_default_config_not_mutated(self):
        original = load_g1_p2_config()
        runtime_config(12, original)
        self.assertEqual(original.boundary_consolidation_window, 8)

    def test_artifact_schemas_cover_required_audit_fields(self):
        self.assertTrue({"TP", "FP", "FN", "Localization_p90", "STAGE_B_HARD_GUARDRAIL"}.issubset(CANDIDATE_FIELDS))
        self.assertTrue({"member_candidate_ids", "GT_MATCH_BEFORE", "GT_MATCH_AFTER",
                         "TWO_VALID_GT_MERGED"}.issubset(CHANGED_FIELDS))


if __name__ == "__main__":
    unittest.main()
