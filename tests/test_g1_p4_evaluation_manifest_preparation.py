import inspect
import tempfile
import unittest
from pathlib import Path

from project2_g1.paths import PROJECT2_ROOT
from project2_g1.evaluation_manifest_preparation import (
    FORMAL_EVALUATION_RUN_ALLOWED, HISTORICAL_FIELDS, MANIFEST_FIELDS, POOL_FIELDS,
    EvaluationManifestPreparationError, audit_disjointness, deterministic_rankings,
    load_historical_sets, manifest_rows, prepare_immutable_temp,
)
import project2_g1.evaluation_manifest_preparation as module


class EvaluationManifestPreparationTests(unittest.TestCase):
    def synthetic(self, count=60):
        return [{"episode_id": f"data/demo_{i}", "frame_count": 50 + i,
                 "duration_seconds_if_available": (50 + i) / 20,
                 "source_identity": "dataset"} for i in range(count)]

    def test_historical_episode_union_and_provenance(self):
        sets, _sources = load_historical_sets(PROJECT2_ROOT)
        self.assertEqual(len(sets["exploratory"]), 6)
        self.assertEqual(len(sets["calibration_seed"]), 6)
        self.assertEqual(len(sets["calibration_fresh"]), 6)
        self.assertEqual(len(sets["calibration_combined"]), 12)
        self.assertEqual(len(sets["design_diagnostic"]), 20)
        self.assertEqual(len(set().union(*sets.values())), 32)

    def test_eligibility_exclusion_audit(self):
        historical = {"exploratory": {"data/demo_1"}, "calibration_seed": set(),
                      "calibration_fresh": set(), "calibration_combined": set(),
                      "design_diagnostic": {"data/demo_2"}}
        options = {"valid": [{"episode_id": "data/demo_3"}]}
        self.assertEqual(audit_disjointness(options, historical)["DISJOINTNESS_AUDIT"], "PASS")
        options = {"invalid": [{"episode_id": "data/demo_2"}]}
        self.assertEqual(audit_disjointness(options, historical)["DISJOINTNESS_AUDIT"], "FAIL")

    def test_deterministic_selection_reproducible(self):
        first, first_hash, _ = deterministic_rankings(self.synthetic())
        second, second_hash, _ = deterministic_rankings(list(reversed(self.synthetic())))
        self.assertEqual([x["episode_id"] for x in first], [x["episode_id"] for x in second])
        self.assertEqual([x["episode_id"] for x in first_hash], [x["episode_id"] for x in second_hash])

    def test_nested_options(self):
        ranking, _hash, _strata = deterministic_rankings(self.synthetic())
        small = manifest_rows(ranking, 12, "method")
        medium = manifest_rows(ranking, 24, "method")
        large = manifest_rows(ranking, 36, "method")
        self.assertLess({r["episode_id"] for r in small}, {r["episode_id"] for r in medium})
        self.assertLess({r["episode_id"] for r in medium}, {r["episode_id"] for r in large})

    def test_duration_strata_balanced(self):
        ranking, _hash, _strata = deterministic_rankings(self.synthetic())
        first_twelve = [r["duration_stratum"] for r in ranking[:12]]
        self.assertEqual(first_twelve.count("SHORT"), 4)
        self.assertEqual(first_twelve.count("MEDIUM"), 4)
        self.assertEqual(first_twelve.count("LONG"), 4)

    def test_no_evaluation_scoring_or_pipeline_import(self):
        source = inspect.getsource(module)
        self.assertNotIn("boundary_engine", source)
        self.assertNotIn("score_results", source)
        self.assertNotIn("run_stage_c", source)
        self.assertFalse(FORMAL_EVALUATION_RUN_ALLOWED)

    def test_no_evaluation_gt_or_human_review_api(self):
        source = inspect.getsource(module)
        self.assertNotIn("load_canonical_snapshot", source)
        self.assertNotIn("owner.sqlite", source.lower())
        self.assertNotIn("audit_web.app", source.lower())

    def test_output_schema(self):
        self.assertTrue({"source_artifact", "eligible_for_evaluation"}.issubset(HISTORICAL_FIELDS))
        self.assertTrue({"readability_status", "eligibility_status", "exclusion_reason"}.issubset(POOL_FIELDS))
        self.assertTrue({"selection_method", "selection_rank", "duration_seconds"}.issubset(MANIFEST_FIELDS))

    def test_immutable_output_run(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            temp = prepare_immutable_temp(output)
            self.assertTrue(temp.exists())
            with self.assertRaises(EvaluationManifestPreparationError):
                prepare_immutable_temp(output)


if __name__ == "__main__":
    unittest.main()
