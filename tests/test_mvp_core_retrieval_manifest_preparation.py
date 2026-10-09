from __future__ import annotations

import ast
import csv
import random
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_mvp import retrieval_manifest_preparation as module
from project2_mvp.retrieval_manifest_preparation import (
    EXPECTED_LOW_DIM_SHA256,
    EXPECTED_RAW_SHA256,
    FROZEN_G1_EVAL_COUNT,
    FROZEN_G1_EVAL_RELATIVE_PATH,
    FROZEN_G1_EVAL_VERSION,
    LEAKAGE_FIELDS,
    RetrievalManifestPreparationError,
    assign_duration_terciles,
    build_disjointness_audit,
    leakage_audit,
    load_frozen_g1_evaluation,
    prepare_immutable_temp,
    select_episode_cohorts,
    stable_digest,
    validate_dataset_identity,
    validate_exclusion_sets,
)


def rows(count: int = 90):
    return [
        {
            "episode_id": f"data/demo_{index}",
            "frame_count": 50 + index,
            "duration_seconds_if_available": (50 + index) / 20.0,
            "source_identity": "dataset-identity",
        }
        for index in range(count)
    ]


class CoreRetrievalManifestPreparationTests(unittest.TestCase):
    def test_historical_union_exclusion(self) -> None:
        selected_rows, selected = select_episode_cohorts(rows())
        historical = {selected_rows[0]["episode_id"]}
        with self.assertRaises(RetrievalManifestPreparationError):
            build_disjointness_audit(selected, historical, set())

    def test_frozen_g1_evaluation_24_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / FROZEN_G1_EVAL_RELATIVE_PATH
            path.parent.mkdir(parents=True)
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=("manifest_version", "selection_rank", "episode_id"))
                writer.writeheader()
                for rank in range(1, FROZEN_G1_EVAL_COUNT + 1):
                    writer.writerow({"manifest_version": FROZEN_G1_EVAL_VERSION, "selection_rank": rank, "episode_id": f"data/eval_{rank}"})
            output, ids, provenance = load_frozen_g1_evaluation(root)
            self.assertEqual(len(output), 24)
            self.assertEqual(len(ids), 24)
            self.assertEqual(provenance["manifest_version"], FROZEN_G1_EVAL_VERSION)

    def test_historical_vs_eval_overlap_detection(self) -> None:
        with self.assertRaises(RetrievalManifestPreparationError):
            validate_exclusion_sets({"data/demo_1"}, {"data/demo_1"})
        self.assertEqual(validate_exclusion_sets({"data/demo_1"}, {"data/demo_2"}), [])

    def test_duration_tercile_assignment_is_deterministic(self) -> None:
        forward, definition = assign_duration_terciles(rows(91))
        backward, second = assign_duration_terciles(list(reversed(rows(91))))
        self.assertEqual([(r["episode_id"], r["duration_stratum"]) for r in forward], [(r["episode_id"], r["duration_stratum"]) for r in backward])
        self.assertEqual(definition, second)
        self.assertEqual(definition["counts"], {"SHORT": 30, "MEDIUM": 30, "LONG": 31})

    def test_sha256_ranking_is_explicit_and_deterministic(self) -> None:
        self.assertEqual(stable_digest("data/demo_1"), stable_digest("data/demo_1"))
        self.assertNotEqual(stable_digest("data/demo_1"), stable_digest("data/demo_2"))

    def test_cohort_counts_are_36_9_18(self) -> None:
        _all, selected = select_episode_cohorts(rows())
        audit = build_disjointness_audit(selected, set(), set())
        self.assertEqual(audit["CANDIDATE_COUNT"], 36)
        self.assertEqual(audit["CALIBRATION_QUERY_COUNT"], 9)
        self.assertEqual(audit["FINAL_QUERY_COUNT"], 18)
        self.assertEqual(audit["TOTAL_SELECTED_UNIQUE"], 63)

    def test_three_cohorts_are_disjoint(self) -> None:
        _all, selected = select_episode_cohorts(rows())
        audit = build_disjointness_audit(selected, set(), set())
        self.assertEqual(audit["CANDIDATE_CALIBRATION_OVERLAP"], [])
        self.assertEqual(audit["CANDIDATE_FINAL_OVERLAP"], [])
        self.assertEqual(audit["CALIBRATION_FINAL_OVERLAP"], [])
        self.assertEqual(audit["RETRIEVAL_MANIFEST_DISJOINTNESS"], "PASS")

    def test_per_stratum_counts_are_12_3_6(self) -> None:
        _all, selected = select_episode_cohorts(rows())
        audit = build_disjointness_audit(selected, set(), set())
        self.assertEqual(audit["STRATUM_BALANCE"], "PASS")
        self.assertEqual(audit["stratum_counts"]["CANDIDATE_BANK"], {"SHORT": 12, "MEDIUM": 12, "LONG": 12})
        self.assertEqual(audit["stratum_counts"]["CALIBRATION_QUERY"], {"SHORT": 3, "MEDIUM": 3, "LONG": 3})
        self.assertEqual(audit["stratum_counts"]["FINAL_QUERY"], {"SHORT": 6, "MEDIUM": 6, "LONG": 6})

    def test_stratum_rank_preserves_frozen_allocation_ranges(self) -> None:
        _all, selected = select_episode_cohorts(rows())
        for stratum in ("SHORT", "MEDIUM", "LONG"):
            self.assertEqual(
                [r["stratum_rank"] for r in selected["CANDIDATE_BANK"] if r["duration_stratum"] == stratum],
                list(range(1, 13)),
            )
            self.assertEqual(
                [r["stratum_rank"] for r in selected["CALIBRATION_QUERY"] if r["duration_stratum"] == stratum],
                list(range(13, 16)),
            )
            self.assertEqual(
                [r["stratum_rank"] for r in selected["FINAL_QUERY"] if r["duration_stratum"] == stratum],
                list(range(16, 22)),
            )

    def test_selection_is_independent_from_input_order(self) -> None:
        fixture = rows()
        reversed_rows = list(reversed(fixture))
        shuffled = list(fixture)
        random.Random(20261008).shuffle(shuffled)
        outputs = []
        for candidate in (fixture, reversed_rows, shuffled):
            all_rows, _selected = select_episode_cohorts(candidate)
            outputs.append([(r["cohort"], r["cohort_rank"], r["episode_id"], r["selection_digest"]) for r in all_rows])
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])

    def test_no_model_retrieval_or_scoring_imports(self) -> None:
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name.lower() for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append((node.module or "").lower())
        forbidden = ("faiss", "siglip", "transformers", "boundary_engine", "stage_c", "scoring")
        self.assertFalse(any(token in name for name in imported for token in forbidden), imported)

    def test_immutable_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            temp = prepare_immutable_temp(output)
            self.assertTrue(temp.is_dir())
            with self.assertRaises(RetrievalManifestPreparationError):
                prepare_immutable_temp(output)

    def test_leakage_audit_fields(self) -> None:
        audit = leakage_audit()
        for name in LEAKAGE_FIELDS:
            self.assertIs(audit[name], False)
        self.assertEqual(audit["LEAKAGE_AUDIT"], "PASS")

    def test_dataset_identity_mismatch_fails_fast(self) -> None:
        valid = {"dataset_id": "robomimic_v15_can_mh", "raw_hdf5_sha256": EXPECTED_RAW_SHA256, "low_dim_hdf5_sha256": EXPECTED_LOW_DIM_SHA256}
        validate_dataset_identity(valid)
        invalid = dict(valid)
        invalid["raw_hdf5_sha256"] = "bad"
        with self.assertRaises(RetrievalManifestPreparationError):
            validate_dataset_identity(invalid)

    def test_insufficient_eligible_pool_fails_fast(self) -> None:
        with self.assertRaises(RetrievalManifestPreparationError):
            assign_duration_terciles(rows(62))


if __name__ == "__main__":
    unittest.main()
