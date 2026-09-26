import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from project2_g1.stage_c_regression import (
    BOUNDARY_CONSOLIDATION_WINDOW, EDGE_FIELDS, EVALUATION_USAGE,
    NEW_SEARCH_AXIS, PARAMETER_TUNING, RESIDUAL_FIELDS, STAGE_A_PARENT,
    TAU_C12, TAU_P12, THRESHOLD_SELECTION, StageCRegressionError,
    build_edge_trace, build_residual_inventory, compare_replays,
    fixed_config_identity, prepare_immutable_temp, residual_role, stage_c_guardrails, validate_parent,
)


class StageCRegressionTests(unittest.TestCase):
    def metrics(self):
        return {
            "TP": 56, "FP": 2, "FN": 0,
            "Precision": 0.9655172413793104, "Recall": 1.0,
            "F1": 0.9824561403508771, "Direction_FP_remaining": 1,
            "NEW_UNANCHORED_FP": 0, "Localization_p90": 0.0,
            "fragmentation_1_2_ratio": 0.0, "Gripper_recall": 1.0,
            "Merged_cluster_recall": 1.0, "Seed_valid_direction_recall": 1.0,
            "Fresh_valid_direction_recall": 1.0,
        }

    def test_fixed_config(self):
        identity = fixed_config_identity()
        self.assertEqual(STAGE_A_PARENT, "A1-007-C002")
        self.assertEqual(TAU_P12, 0.04758563666765155)
        self.assertEqual(TAU_C12, 0.690169167642685)
        self.assertEqual(BOUNDARY_CONSOLIDATION_WINDOW, 8)
        self.assertEqual(identity["boundary_consolidation_window"], 8)

    def test_search_surface_forbidden(self):
        self.assertEqual((NEW_SEARCH_AXIS, PARAMETER_TUNING, THRESHOLD_SELECTION),
                         ("FORBIDDEN", "FORBIDDEN", "FORBIDDEN"))

    def test_parent_replay_exact(self):
        validate_parent(self.metrics())
        bad = self.metrics(); bad["FN"] = 1
        with self.assertRaises(StageCRegressionError):
            validate_parent(bad)

    def test_guardrails(self):
        self.assertTrue(stage_c_guardrails(self.metrics()))
        bad = self.metrics(); bad["Fresh_valid_direction_recall"] = 0.9
        self.assertFalse(stage_c_guardrails(bad))

    def test_residual_roles_derive_from_reason(self):
        self.assertEqual(residual_role("DIRECTION_CHANGE", "REDUNDANT_DIRECTION_JITTER"),
                         "ACCEPTANCE_RESIDUAL")
        self.assertEqual(residual_role("IDLE_TO_MOVE", "REDUNDANT_SHORT_PAUSE"),
                         "KNOWN_UNDER_CONSOLIDATION_RESIDUAL")

    def test_residual_inventory(self):
        event = SimpleNamespace(
            episode_id="data/demo_x", boundary_id="B1", frame=60,
            candidate_type="DIRECTION_CHANGE", representative_candidate_id="C1",
            member_candidate_ids=["C1"], member_candidate_types=["DIRECTION_CHANGE"],
            member_candidate_frames=[60], active=True,
        )
        result = SimpleNamespace(final_events=[event])
        pred = {"episode_id": "data/demo_x", "pred_id": "data/demo_x:B1", "pred_frame": 60}
        details = {"unmatched": [pred], "pred_anchors": {"data/demo_x:B1": {
            "known_fp_anchor_matched": True, "known_fp_anchor_frame": 60,
            "known_fp_error_mode": "MODE_01", "reason_code": "REDUNDANT_DIRECTION_JITTER"}}}
        rows = build_residual_inventory([result], details)
        self.assertEqual(rows[0]["residual_role"], "ACCEPTANCE_RESIDUAL")

    def _edge_result(self, decision="KEEP"):
        event = SimpleNamespace(member_candidate_ids=["C1"], active=True)
        return SimpleNamespace(
            episode_id="data/demo_x", events=[event],
            decisions={"C1": SimpleNamespace(decision=decision, target_boundary_id="B1")})

    def test_edge_p12_fail_open(self):
        trace = [{"episode_id": "data/demo_x", "candidate_id": "C1", "frame": 2,
                  "candidate_type": "DIRECTION_CHANGE", "P12": None,
                  "P12_context_complete": False, "C12": None,
                  "C12_context_complete": False,
                  "acceptance_decision": "KEEP_EDGE_CONTEXT_INCOMPLETE"}]
        rows = build_edge_trace([self._edge_result()], trace)
        self.assertEqual(rows[0]["fallback_behavior"], "P12_INCOMPLETE_FAIL_OPEN_KEEP")
        self.assertNotEqual(rows[0]["final_status"], "REJECTED_BY_ACCEPTANCE")

    def test_edge_c12_fallback(self):
        trace = [{"episode_id": "data/demo_x", "candidate_id": "C1", "frame": 15,
                  "candidate_type": "DIRECTION_CHANGE", "P12": 0.1,
                  "P12_context_complete": True, "C12": None,
                  "C12_context_complete": False,
                  "acceptance_decision": "KEEP_C12_CONTEXT_INCOMPLETE"}]
        rows = build_edge_trace([self._edge_result()], trace)
        self.assertEqual(rows[0]["fallback_behavior"], "C12_INCOMPLETE_FALLBACK_P12_ONLY")

    def test_determinism_comparison(self):
        replay = {"final_boundaries": [1], "matching": [2], "metrics": {"TP": 1},
                  "residuals": [3], "acceptance_trace": [4], "edge_counts": {"P12": 0}}
        comparison = compare_replays(replay, dict(replay))
        self.assertTrue(all(value == "YES" for value in comparison.values()))

    def test_no_evaluation_access(self):
        self.assertEqual(EVALUATION_USAGE, "FORBIDDEN")

    def test_output_schemas(self):
        self.assertTrue({"residual_role", "known_fp_anchor_matched", "member_candidate_ids"}.issubset(RESIDUAL_FIELDS))
        self.assertTrue({"fallback_behavior", "final_status", "P12_context_complete"}.issubset(EDGE_FIELDS))

    def test_immutable_output_run(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run-1"
            temp = prepare_immutable_temp(output)
            self.assertTrue(temp.is_dir())
            with self.assertRaises(StageCRegressionError):
                prepare_immutable_temp(output)


if __name__ == "__main__":
    unittest.main()
