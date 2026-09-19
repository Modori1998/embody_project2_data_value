"""Stage A0 discriminability audit: cohorts, lineage, derivation, immutability."""

from __future__ import annotations

import ast
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.baseline_scoring import EXPECTED_RUN_ID, EXPECTED_SNAPSHOT_ID, SQLITE_SHA256
from project2_g1.boundary_engine import persistent_high_runs
from project2_g1.canonical_gt import PROTECTED_DIRECTION
from project2_g1.stage_a0_analysis import (
    EVENT_FIELDS,
    EXPECTED_SCORE_ID,
    FROZEN_DIRECTION_PERSISTENCE,
    FROZEN_DIRECTION_THRESHOLD,
    KNOWN_FINGERPRINTS,
    LEGAL_ERROR_MODES,
    PRIVILEGED_TOKENS,
    attach_fp_package,
    derive_run_length,
    extract_fp_cohorts,
    extract_valid_direction_cohort,
    parse_supporting_reasons,
    peak_shape,
    quantile,
    source_fingerprints,
)
from project2_g1_audit_web.hashes import sha256_file, tree_fingerprint


def _read(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class CohortExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pairs = _read(ROOT / "outputs/g1_p3_scoring" / EXPECTED_SCORE_ID / "matching_pairs.csv")
        cls.fps = _read(ROOT / "outputs/g1_p3_scoring" / EXPECTED_SCORE_ID / "unmatched_predictions_fp.csv")
        cls.anchors = _read(ROOT / "outputs/g1_p3_scoring" / EXPECTED_SCORE_ID / "known_fp_anchor_status.csv")
        cls.valid = extract_valid_direction_cohort(cls.pairs)
        cls.direction_fp, cls.non_direction = extract_fp_cohorts(cls.fps)
        attach_fp_package(cls.direction_fp, cls.anchors)
        attach_fp_package(cls.non_direction, cls.anchors)

    def test_valid_cohort_from_matching_pairs(self) -> None:
        self.assertEqual(len(self.valid), 17)
        self.assertEqual(sum(1 for row in self.valid if row["source_package"] == "SEED"), 6)
        self.assertEqual(sum(1 for row in self.valid if row["source_package"] == "FRESH"), 11)
        self.assertTrue(all(row["protected_class"] == PROTECTED_DIRECTION for row in self.valid))
        self.assertTrue(all(row["pred_candidate_type"] == "DIRECTION_CHANGE" for row in self.valid))
        self.assertEqual(self.valid, sorted(self.valid, key=lambda row: (row["episode_id"], row["pred_frame"], row["pred_boundary_id"])))

    def test_merged_gripper_clusters_are_excluded(self) -> None:
        merged = [row for row in self.pairs if row["protected_class"] == "MERGED_GRIPPER_CLUSTER"]
        self.assertTrue(merged)
        valid_ids = {row["pred_boundary_id"] for row in self.valid}
        self.assertTrue(valid_ids.isdisjoint({row["pred_boundary_id"] for row in merged}))
        gripper = [row for row in self.pairs if row["pred_candidate_type"] == "GRIPPER_TRANSITION"]
        self.assertTrue(valid_ids.isdisjoint({row["pred_boundary_id"] for row in gripper}))

    def test_direction_fp_excludes_non_direction(self) -> None:
        self.assertEqual(len(self.fps), 10)
        self.assertEqual(len(self.direction_fp), 9)
        self.assertEqual(len(self.non_direction), 1)
        self.assertEqual(self.non_direction[0]["pred_boundary_id"], "demo_255-B0007")
        self.assertEqual(self.non_direction[0]["pred_candidate_type"], "IDLE_TO_MOVE")
        self.assertTrue(all(row["pred_candidate_type"] == "DIRECTION_CHANGE" for row in self.direction_fp))

    def test_error_modes_are_frozen_and_fresh_unassigned_stays(self) -> None:
        modes = {row["error_mode"] for row in self.direction_fp}
        self.assertTrue(modes <= set(LEGAL_ERROR_MODES))
        counts = {mode: sum(1 for row in self.direction_fp if row["error_mode"] == mode) for mode in LEGAL_ERROR_MODES}
        self.assertEqual(counts["MODE_01"], 3)
        self.assertEqual(counts["MODE_02"], 3)
        self.assertEqual(counts["MODE_03"], 1)
        self.assertEqual(counts["UNASSIGNED"], 2)
        unassigned = [row for row in self.direction_fp if row["error_mode"] == "UNASSIGNED"]
        self.assertEqual({row["pred_boundary_id"] for row in unassigned}, {"demo_162-B0005", "demo_255-B0005"})
        self.assertTrue(all(row["source_package"] == "FRESH" for row in unassigned))

    def test_seed_fresh_fp_provenance(self) -> None:
        self.assertEqual(sum(1 for row in self.direction_fp if row["source_package"] == "SEED"), 7)
        self.assertEqual(sum(1 for row in self.direction_fp if row["source_package"] == "FRESH"), 2)


class LineageAndDerivationTests(unittest.TestCase):
    def test_candidate_final_lineage_representative_exists(self) -> None:
        run = ROOT / "outputs/g1_audit_runs" / EXPECTED_RUN_ID
        pairs = _read(ROOT / "outputs/g1_p3_scoring" / EXPECTED_SCORE_ID / "matching_pairs.csv")
        valid = extract_valid_direction_cohort(pairs)
        fps = _read(ROOT / "outputs/g1_p3_scoring" / EXPECTED_SCORE_ID / "unmatched_predictions_fp.csv")
        direction_fp, _non = extract_fp_cohorts(fps)
        for item in valid + direction_fp:
            native = item["episode_id"].split("/")[-1]
            finals = _read(run / "diagnostic" / native / "final_boundaries.csv")
            cands = _read(run / "diagnostic" / native / "candidate_boundaries.csv")
            final = next(row for row in finals if row["boundary_id"] == item["pred_boundary_id"])
            self.assertEqual(final["candidate_type"], "DIRECTION_CHANGE")
            self.assertEqual(int(final["frame"]), item["pred_frame"])
            rep = next(row for row in cands if row["candidate_id"] == final["representative_candidate_id"])
            self.assertEqual(rep["candidate_type"], "DIRECTION_CHANGE")
            self.assertEqual(int(rep["frame"]), item["pred_frame"])
            self.assertGreater(float(rep["evidence_value"]), FROZEN_DIRECTION_THRESHOLD)

    def test_run_length_derivation_matches_persistent_high_runs(self) -> None:
        values = np.array([0.0, 0.5, 1.3, 1.8, 1.5, 0.4, 2.0, 2.1, 2.2, 0.0], dtype=np.float64)
        runs = persistent_high_runs(values, FROZEN_DIRECTION_THRESHOLD, FROZEN_DIRECTION_PERSISTENCE)
        self.assertEqual(runs, [(3, 1.8, 3), (8, 2.2, 3)])
        length, prov = derive_run_length(values, 3, FROZEN_DIRECTION_THRESHOLD, FROZEN_DIRECTION_PERSISTENCE)
        self.assertEqual(length, 3)
        self.assertEqual(prov, "ANALYSIS_DERIVED")
        missing, missing_prov = derive_run_length(values, 1, FROZEN_DIRECTION_THRESHOLD, FROZEN_DIRECTION_PERSISTENCE)
        self.assertIsNone(missing)
        self.assertEqual(missing_prov, "NOT_AVAILABLE")

    def test_peak_width_formula_uses_frozen_threshold(self) -> None:
        values = np.array([0.0, 1.3, 1.9, 1.4, 0.2], dtype=np.float64)
        shape = peak_shape(values, 2, FROZEN_DIRECTION_THRESHOLD, 8)
        self.assertEqual(shape["peak_width"], 3)
        self.assertEqual(shape["peak_value"], 1.9)
        expected_area = (1.3 - 1.2) + (1.9 - 1.2) + (1.4 - 1.2)
        self.assertAlmostEqual(shape["local_area_above_threshold"], expected_area)

    def test_window_bounds_clip(self) -> None:
        from project2_g1.stage_a0_analysis import _clip_window
        self.assertEqual(_clip_window(10, 0, 8), (0, 9))
        self.assertEqual(_clip_window(10, 9, 8), (1, 10))
        self.assertEqual(_clip_window(10, 4, 3), (1, 8))

    def test_support_parsing(self) -> None:
        self.assertEqual(parse_supporting_reasons(""), (False, False, "NONE"))
        self.assertEqual(parse_supporting_reasons("ROTATION_SUPPORT|ACTION_SUPPORT"), (True, True, "ROTATION_SUPPORT|ACTION_SUPPORT"))
        self.assertEqual(parse_supporting_reasons("ACTION_SUPPORT"), (False, True, "ACTION_SUPPORT"))

    def test_gripper_distance_derivation(self) -> None:
        from project2_g1.stage_a0_analysis import _min_abs_distance, _signed_next
        self.assertEqual(_min_abs_distance(136, [4, 96, 124, 146]), 10)
        self.assertEqual(_signed_next(136, [4, 96, 124, 146]), 10)
        self.assertIsNone(_signed_next(224, [4, 96, 124, 146]))
        self.assertIsNone(_min_abs_distance(10, []))

    def test_quantile_is_deterministic(self) -> None:
        self.assertEqual(quantile([1, 2, 3, 4], 0.5), 2.5)
        self.assertEqual(quantile([3], 0.25), 3)


class ContractAndImmutabilityTests(unittest.TestCase):
    def test_no_privileged_imports_or_event_fields(self) -> None:
        source = SRC / "project2_g1" / "stage_a0_analysis.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        self.assertFalse(any("privileged" in name for name in imported))
        blob = " ".join(EVENT_FIELDS).lower()
        for token in ("can_pos", "reward", "success", "object_gt"):
            self.assertNotIn(token, blob)
        self.assertTrue(PRIVILEGED_TOKENS)

    def test_source_does_not_generate_config_or_search(self) -> None:
        tree = ast.parse((SRC / "project2_g1" / "stage_a0_analysis.py").read_text(encoding="utf-8"))
        calls = [node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
        self.assertNotIn("score_baseline", calls)
        self.assertNotIn("run_boundary_engine", calls)
        assigned = {
            node.targets[0].id: node.value.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
        }
        self.assertIn("parameter_search_executed", (SRC / "project2_g1" / "stage_a0_analysis.py").read_text(encoding="utf-8"))
        self.assertFalse(assigned.get("parameter_search_executed", False))

    def test_known_source_fingerprints(self) -> None:
        fps = source_fingerprints(ROOT)
        self.assertEqual(fps["canonical_gt"], KNOWN_FINGERPRINTS["canonical_gt"])
        self.assertEqual(fps["seed_export"], KNOWN_FINGERPRINTS["seed_export"])
        self.assertEqual(fps["fresh_export"], KNOWN_FINGERPRINTS["fresh_export"])
        self.assertEqual(fps["owner_sqlite"], SQLITE_SHA256)
        self.assertEqual(fps["protocol_v1"], KNOWN_FINGERPRINTS["protocol_v1"])
        self.assertEqual(fps["protocol_v11"], KNOWN_FINGERPRINTS["protocol_v11"])
        self.assertEqual(
            sha256_file(ROOT / "outputs/g1_audit_runs" / EXPECTED_RUN_ID / "run_meta.json"),
            KNOWN_FINGERPRINTS["baseline_run_meta"],
        )
        self.assertEqual(
            tree_fingerprint(ROOT / "outputs/g1_p3_canonical_gt" / EXPECTED_SNAPSHOT_ID)["tree_fingerprint"],
            KNOWN_FINGERPRINTS["canonical_gt"],
        )

    def test_event_schema_has_provenance_fields(self) -> None:
        self.assertIn("run_length_provenance", EVENT_FIELDS)
        self.assertIn("heading_homology_note", EVENT_FIELDS)
        self.assertIn("diagnostic_window_note", EVENT_FIELDS)


class OfficialArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = ROOT / "outputs/g1_p3_stage_a0"
        if not root.is_dir():
            raise unittest.SkipTest("stage a0 artifact not materialized yet")
        analyses = [path for path in root.iterdir() if path.is_dir() and path.name.startswith("g1_stage_a0_")]
        if not analyses:
            raise unittest.SkipTest("stage a0 artifact not materialized yet")
        cls.analysis_root = sorted(analyses, key=lambda path: path.name)[-1]
        cls.meta = json.loads((cls.analysis_root / "stage_a0_meta.json").read_text(encoding="utf-8"))
        cls.events = _read(cls.analysis_root / "stage_a0_direction_event_analysis.csv")
        cls.non_dir = _read(cls.analysis_root / "stage_a0_non_direction_fp.csv")
        cls.decision = json.loads((cls.analysis_root / "stage_a0_decision.json").read_text(encoding="utf-8"))

    def test_meta_contract(self) -> None:
        self.assertEqual(self.meta["baseline_run_id"], EXPECTED_RUN_ID)
        self.assertEqual(self.meta["baseline_score_id"], EXPECTED_SCORE_ID)
        self.assertEqual(self.meta["canonical_gt_snapshot_id"], EXPECTED_SNAPSHOT_ID)
        self.assertEqual(self.meta["stage"], "A0")
        self.assertFalse(self.meta["parameter_search_executed"])
        self.assertFalse(self.meta["detector_modified"])
        self.assertFalse(self.meta["config_generated"])
        self.assertFalse(self.meta["threshold_sweep_executed"])
        self.assertEqual(self.meta["matching_rule_id"], "MAX_CARDINALITY_MIN_TOTAL_DISTANCE_ONE_TO_ONE_V1")
        self.assertEqual(int(self.meta["tolerance_frames"]), 3)

    def test_event_ordering_and_counts(self) -> None:
        self.assertEqual(len(self.events), 26)
        valid = [row for row in self.events if row["human_class"] == "VALID_DIRECTION"]
        fp = [row for row in self.events if row["human_class"] == "DIRECTION_FP"]
        self.assertEqual(len(valid), 17)
        self.assertEqual(len(fp), 9)
        self.assertEqual(self.events, sorted(self.events, key=lambda row: (row["episode_id"], int(row["pred_frame"]), row["pred_boundary_id"])))
        self.assertTrue(all(row["run_length_provenance"].startswith("ANALYSIS_DERIVED") or row["run_length_provenance"] == "NOT_AVAILABLE" for row in self.events))
        self.assertEqual(len(self.non_dir), 1)
        self.assertEqual(self.non_dir[0]["candidate_type"], "IDLE_TO_MOVE")

    def test_no_privileged_columns(self) -> None:
        header = list(self.events[0].keys())
        blob = " ".join(header).lower()
        for token in PRIVILEGED_TOKENS:
            self.assertNotIn(token, blob)

    def test_decision_is_one_of_four(self) -> None:
        self.assertIn(
            self.decision["classification"],
            {
                "THRESHOLD_PERSISTENCE_DISCRIMINABILITY",
                "DERIVED_SIGNAL_DISCRIMINABILITY",
                "NO_INTERPRETABLE_DISCRIMINABILITY",
                "MIXED_INSUFFICIENT",
            },
        )

    def test_no_tmp_leftovers(self) -> None:
        leftovers = [path for path in (ROOT / "outputs/g1_p3_stage_a0").iterdir() if path.name.startswith(".tmp-")]
        self.assertEqual(leftovers, [])

    def test_plots_materialized(self) -> None:
        for name in self.meta["plots"]:
            path = self.analysis_root / "plots" / name
            self.assertTrue(path.is_file(), name)
            self.assertGreater(path.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
