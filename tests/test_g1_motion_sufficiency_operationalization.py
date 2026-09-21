"""Minimal tests for the G1-P3 motion sufficiency operationalization prep script.

Scope (deliberately small, no existing test is refactored):
* W8 path length / net displacement / straightness maths
* zero-path NaN guard
* event identity + cohort integrity against the frozen evidence inputs
* VALID-floor envelope diagnostic
* determinism (byte-identical, LF-only, no BOM)
* no privileged field use
"""

from __future__ import annotations

import ast
import csv
import hashlib
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import prepare_g1_motion_sufficiency_operationalization as prep  # noqa: E402

FORBIDDEN_TOKENS = (
    "reward",
    "success",
    "terminal",
    "next_obs",
    "privileged",
    "object_pose",
    "obs/object",
    "sqlite",
)


def _code_tokens(module_path: Path) -> set[str]:
    """Collect string/name tokens from a module, excluding docstrings.

    Docstrings legitimately *name* the forbidden signals in order to declare
    that they are not used, so they must be excluded from the token scan.
    """
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    docstrings.add(id(body[0].value))

    tokens: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings:
                tokens.add(node.value.lower())
        elif isinstance(node, ast.Name):
            tokens.add(node.id.lower())
        elif isinstance(node, ast.Attribute):
            tokens.add(node.attr.lower())
    return tokens


class TestStraightnessMaths(unittest.TestCase):
    """W8 path length, net displacement and straightness."""

    def test_path_length_sums_step_displacement(self):
        steps = [
            {"step_displacement_m": "0.03"},
            {"step_displacement_m": "0.04"},
            {"step_displacement_m": "0.05"},
        ]
        self.assertAlmostEqual(prep.path_length(steps), 0.12, places=12)

    def test_path_length_of_empty_window_is_zero(self):
        self.assertEqual(prep.path_length([]), 0.0)

    def test_net_displacement_is_norm_of_summed_delta(self):
        steps = [
            {"step_dx": "0.03", "step_dy": "0.0", "step_dz": "0.0"},
            {"step_dx": "0.04", "step_dy": "0.0", "step_dz": "0.0"},
        ]
        self.assertAlmostEqual(prep.net_displacement(steps), 0.07, places=12)

    def test_net_displacement_is_zero_for_closed_loop(self):
        steps = [
            {"step_dx": "0.05", "step_dy": "0.0", "step_dz": "0.0"},
            {"step_dx": "-0.05", "step_dy": "0.0", "step_dz": "0.0"},
        ]
        self.assertAlmostEqual(prep.net_displacement(steps), 0.0, places=12)

    def test_straightness_is_one_for_collinear_path(self):
        steps = [
            {"step_dx": "0.02", "step_dy": "0.0", "step_dz": "0.0", "step_displacement_m": "0.02"},
            {"step_dx": "0.03", "step_dy": "0.0", "step_dz": "0.0", "step_displacement_m": "0.03"},
        ]
        self.assertAlmostEqual(prep.straightness(steps), 1.0, places=12)

    def test_straightness_drops_below_one_for_detour(self):
        # Out-and-back: full path length, near-zero net displacement.
        steps = [
            {"step_dx": "0.04", "step_dy": "0.0", "step_dz": "0.0", "step_displacement_m": "0.04"},
            {"step_dx": "-0.04", "step_dy": "0.0", "step_dz": "0.0", "step_displacement_m": "0.04"},
        ]
        self.assertAlmostEqual(prep.straightness(steps), 0.0, places=12)

    def test_straightness_within_unit_interval(self):
        steps = [
            {"step_dx": "0.03", "step_dy": "0.01", "step_dz": "0.0", "step_displacement_m": "0.0316"},
            {"step_dx": "-0.01", "step_dy": "0.02", "step_dz": "0.0", "step_displacement_m": "0.0224"},
        ]
        value = prep.straightness(steps)
        self.assertGreaterEqual(value, 0.0)
        self.assertLessEqual(value, 1.0)


class TestDegeneratePathGuard(unittest.TestCase):
    """path_length < 1e-9 -> NaN, never a fabricated large ratio."""

    def test_zero_path_returns_nan(self):
        steps = [{"step_dx": "0.0", "step_dy": "0.0", "step_dz": "0.0", "step_displacement_m": "0.0"}]
        self.assertTrue(math.isnan(prep.straightness(steps)))

    def test_sub_epsilon_path_returns_nan(self):
        steps = [
            {"step_dx": "1e-12", "step_dy": "0.0", "step_dz": "0.0", "step_displacement_m": "1e-12"}
        ]
        self.assertTrue(math.isnan(prep.straightness(steps)))

    def test_empty_window_returns_nan(self):
        self.assertTrue(math.isnan(prep.straightness([])))

    def test_nan_never_produces_inf(self):
        steps = [{"step_dx": "0.0", "step_dy": "0.0", "step_dz": "0.0", "step_displacement_m": "0.0"}]
        self.assertFalse(math.isinf(prep.straightness(steps)))


class TestQuantileAndDistribution(unittest.TestCase):
    def test_quantile_matches_linear_interpolation(self):
        values = [0.0, 1.0, 2.0, 3.0, 4.0]
        self.assertAlmostEqual(prep.quantile(values, 0.5), 2.0, places=12)
        self.assertAlmostEqual(prep.quantile(values, 0.25), 1.0, places=12)
        self.assertAlmostEqual(prep.quantile(values, 0.75), 3.0, places=12)

    def test_quantile_single_value(self):
        self.assertAlmostEqual(prep.quantile([0.7], 0.75), 0.7, places=12)

    def test_distribution_reports_expected_shape(self):
        stats = prep.distribution([3.0, 1.0, 2.0])
        self.assertEqual(stats["n"], 3.0)
        self.assertAlmostEqual(stats["min"], 1.0, places=12)
        self.assertAlmostEqual(stats["median"], 2.0, places=12)
        self.assertAlmostEqual(stats["max"], 3.0, places=12)

    def test_overlap_helpers(self):
        self.assertAlmostEqual(prep.range_overlap([0.0, 1.0], [0.5, 2.0]), 0.5, places=12)
        self.assertAlmostEqual(prep.range_overlap([0.0, 1.0], [2.0, 3.0]), 0.0, places=12)
        self.assertAlmostEqual(
            prep.iqr_overlap([0.0, 1.0, 2.0, 3.0, 4.0], [0.5, 1.0, 1.5, 2.0, 2.5]), 1.0, places=12
        )


class TestEnvelopeDiagnostic(unittest.TestCase):
    """VALID_FLOOR is a read-only calibration envelope diagnostic."""

    def test_valid_floor_is_minimum(self):
        self.assertAlmostEqual(prep.valid_floor([0.4, 0.1, 0.9]), 0.1, places=12)

    def test_below_floor_is_strict(self):
        self.assertTrue(prep.below_floor(0.09, 0.1))
        self.assertFalse(prep.below_floor(0.1, 0.1))
        self.assertFalse(prep.below_floor(0.11, 0.1))

    def test_below_floor_false_when_nan_involved(self):
        self.assertFalse(prep.below_floor(float("nan"), 0.1))
        self.assertFalse(prep.below_floor(0.05, float("nan")))

    def test_no_valid_event_can_fall_below_its_own_floor(self):
        valid = [0.4, 0.1, 0.9, 0.25]
        floor = prep.valid_floor(valid)
        self.assertFalse(any(prep.below_floor(v, floor) for v in valid))

    def test_pair_explained_is_or_semantics(self):
        self.assertTrue(prep.pair_explained(True, False))
        self.assertTrue(prep.pair_explained(False, True))
        self.assertTrue(prep.pair_explained(True, True))
        self.assertFalse(prep.pair_explained(False, False))


class TestEventIdentityAndCohort(unittest.TestCase):
    """Cohort freeze and identity integrity against the immutable inputs."""

    @classmethod
    def setUpClass(cls):
        cls.events, cls.trace = prep.load_inputs()
        cls.grouped = prep.group_trace(cls.trace)
        cls.rows = prep.build_event_rows(cls.events, cls.grouped)
        cls.floors = prep.attach_floors(cls.rows)
        cls.summary = prep.build_summary_rows(cls.rows)

    def test_event_rows_equal_26(self):
        self.assertEqual(len(self.rows), prep.EXPECTED_EVENT_ROWS)

    def test_cohort_split_is_17_valid_and_9_fp(self):
        valid = [r for r in self.rows if r["human_class"] == prep.VALID_CLASS]
        fp = [r for r in self.rows if r["human_class"] == prep.FP_CLASS]
        self.assertEqual(len(valid), prep.EXPECTED_VALID)
        self.assertEqual(len(fp), prep.EXPECTED_FP)

    def test_no_duplicate_event_key(self):
        keys = [(r["episode_id"], r["event_frame"]) for r in self.rows]
        self.assertEqual(len(keys), len(set(keys)))

    def test_rows_are_sorted_deterministically(self):
        keys = [(r["episode_id"], r["event_frame"]) for r in self.rows]
        self.assertEqual(keys, sorted(keys))

    def test_only_direction_classes_present(self):
        classes = {r["human_class"] for r in self.rows}
        self.assertEqual(classes, {prep.VALID_CLASS, prep.FP_CLASS})

    def test_critical_event_coverage_is_complete(self):
        present = {(r["episode_key"], r["event_frame"]) for r in self.rows}
        for episode_key, frame in prep.CRITICAL_EVENTS:
            self.assertIn((episode_key, frame), present)

    def test_no_non_direction_fp_leaked_into_cohort(self):
        for row in self.rows:
            self.assertNotIn("NON_DIRECTION_FP", row["human_class"])
            self.assertNotIn("IDLE_TO_MOVE", row["error_mode"])

    def test_package_partition_is_seed_13_fresh_13(self):
        seed = [r for r in self.rows if r["source_package"] == "SEED"]
        fresh = [r for r in self.rows if r["source_package"] == "FRESH"]
        self.assertEqual(len(seed), 13)
        self.assertEqual(len(fresh), 13)


class TestSourceConsistency(unittest.TestCase):
    """Each operational field must be reproducible from its declared source."""

    @classmethod
    def setUpClass(cls):
        cls.events, cls.trace = prep.load_inputs()
        cls.grouped = prep.group_trace(cls.trace)
        cls.rows = prep.build_event_rows(cls.events, cls.grouped)

    def test_p8_reproduces_from_w8_post_window(self):
        for row in self.rows:
            frames = self.grouped[(row["episode_key"], row["event_frame"])]
            recomputed = prep.window_mean(frames, prep.P8_WINDOW, "translation_speed_mps")
            self.assertAlmostEqual(recomputed, row["P8_post_speed_mean"], places=12)

    def test_p12_reproduces_from_sustained_window(self):
        for row in self.rows:
            frames = self.grouped[(row["episode_key"], row["event_frame"])]
            recomputed = prep.window_median(frames, prep.P12_WINDOW, "translation_speed_mps")
            self.assertAlmostEqual(recomputed, row["P12_right_speed_reference"], places=12)

    def test_c12_reproduces_from_w12_windows(self):
        for row in self.rows:
            self.assertAlmostEqual(
                row["C12_recomputed_left_straightness"], row["C12_left_straightness"], places=12
            )
            self.assertAlmostEqual(
                row["C12_recomputed_right_straightness"], row["C12_right_straightness"], places=12
            )

    def test_c8_min_is_min_of_sides(self):
        for row in self.rows:
            self.assertAlmostEqual(
                row["C8_min_straightness"],
                min(row["C8_left_straightness"], row["C8_right_straightness"]),
                places=12,
            )

    def test_no_inf_and_no_unexplained_nan(self):
        for row in self.rows:
            for field in (
                "P8_post_speed_mean",
                "P12_right_speed_reference",
                "C8_min_straightness",
                "C12_min_straightness",
            ):
                value = float(row[field])
                self.assertFalse(math.isinf(value))
                self.assertFalse(math.isnan(value), f"unexpected NaN in {field}")


class TestJointRuleShapeDiagnostic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events, cls.trace = prep.load_inputs()
        cls.rows = prep.build_event_rows(cls.events, prep.group_trace(cls.trace))
        cls.floors = prep.attach_floors(cls.rows)
        cls.summary = prep.build_summary_rows(cls.rows)

    def test_valid_rejected_is_zero_by_envelope_construction(self):
        valid = [r for r in self.rows if r["human_class"] == prep.VALID_CLASS]
        self.assertEqual(sum(1 for r in valid if r["Pair8_explained"]), 0)
        self.assertEqual(sum(1 for r in valid if r["Pair12_explained"]), 0)

    def test_fp_coverage_is_reported_consistently(self):
        fp = [r for r in self.rows if r["human_class"] == prep.FP_CLASS]
        covered8 = sum(1 for r in fp if r["Pair8_explained"])
        covered12 = sum(1 for r in fp if r["Pair12_explained"])
        self.assertLessEqual(covered8, len(fp))
        self.assertLessEqual(covered12, len(fp))
        # W12 sustained context must not cover fewer FP than W8 in this cohort.
        self.assertGreaterEqual(covered12, covered8)

    def test_pair_flags_are_booleans(self):
        for row in self.rows:
            self.assertIsInstance(row["Pair8_explained"], bool)
            self.assertIsInstance(row["Pair12_explained"], bool)

    def test_summary_covers_every_feature_and_cohort(self):
        seen = {(r["feature"], r["cohort"]) for r in self.summary}
        for feature in prep.FEATURES:
            for cohort in prep.COHORTS:
                self.assertIn((feature, cohort), seen)

    def test_summary_valid_and_fp_counts(self):
        by_key = {(r["feature"], r["cohort"]): r for r in self.summary}
        for feature in prep.FEATURES:
            self.assertEqual(by_key[(feature, "VALID")]["n"], 17.0)
            self.assertEqual(by_key[(feature, "FP")]["n"], 9.0)


class TestCsvSerialization(unittest.TestCase):
    """CSV line-ending contract: LF only, UTF-8, no BOM."""

    def test_render_csv_uses_lf_only(self):
        payload = prep.render_csv(["a", "b"], [{"a": 1, "b": 2.5}])
        self.assertNotIn("\r", payload)
        self.assertTrue(payload.endswith("\n"))

    def test_rendered_bytes_have_no_bom(self):
        payload = prep.render_csv(["a"], [{"a": "x"}]).encode("utf-8")
        self.assertFalse(payload.startswith(b"\xef\xbb\xbf"))

    def test_values_needing_quoting_are_quoted(self):
        payload = prep.render_csv(["a"], [{"a": "x,y"}])
        self.assertIn('"x,y"', payload)

    def test_nan_serializes_as_literal_nan(self):
        self.assertEqual(prep.fmt(float("nan")), "nan")
        self.assertEqual(prep.fmt(float("inf")), "inf")

    def test_booleans_serialize_lowercase(self):
        self.assertEqual(prep.fmt(True), "true")
        self.assertEqual(prep.fmt(False), "false")


class TestDeterminism(unittest.TestCase):
    """Re-running on identical inputs must yield identical bytes."""

    def test_two_builds_are_byte_identical(self):
        events, trace = prep.load_inputs()
        grouped = prep.group_trace(trace)

        first_rows = prep.build_event_rows(events, grouped)
        prep.attach_floors(first_rows)
        first = prep.render_csv(prep.EVENT_COLUMNS, first_rows).encode("utf-8")

        second_rows = prep.build_event_rows(events, grouped)
        prep.attach_floors(second_rows)
        second = prep.render_csv(prep.EVENT_COLUMNS, second_rows).encode("utf-8")

        self.assertEqual(first, second)
        self.assertEqual(hashlib.sha256(first).hexdigest(), hashlib.sha256(second).hexdigest())

    def test_summary_render_is_deterministic(self):
        events, trace = prep.load_inputs()
        grouped = prep.group_trace(trace)
        rows_a = prep.build_event_rows(events, grouped)
        prep.attach_floors(rows_a)
        rows_b = prep.build_event_rows(events, grouped)
        prep.attach_floors(rows_b)
        self.assertEqual(
            prep.render_csv(prep.SUMMARY_COLUMNS, prep.build_summary_rows(rows_a)),
            prep.render_csv(prep.SUMMARY_COLUMNS, prep.build_summary_rows(rows_b)),
        )

    def test_inputs_are_not_modified_by_building(self):
        before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (prep.EVENT_CSV_IN, prep.TRACE_CSV_IN)
        }
        events, trace = prep.load_inputs()
        rows = prep.build_event_rows(events, prep.group_trace(trace))
        prep.attach_floors(rows)
        prep.build_summary_rows(rows)
        after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in before}
        self.assertEqual(before, after)


class TestNoPrivilegedFieldUse(unittest.TestCase):
    """The preparation script must stay inside the Formal Signal boundary."""

    def test_module_tokens_contain_no_privileged_signal(self):
        tokens = _code_tokens(Path(prep.__file__))
        blob = " ".join(sorted(tokens))
        for token in FORBIDDEN_TOKENS:
            self.assertNotIn(token, blob, f"forbidden token present in code: {token}")

    def test_module_declares_no_detector_or_config_writes(self):
        tokens = _code_tokens(Path(prep.__file__))
        for token in ("configs", "detector", "threshold_selected", "grid_search"):
            self.assertNotIn(token, tokens)

    def test_outputs_are_confined_to_the_audit_evidence_dir(self):
        for path in (prep.EVENT_CSV_OUT, prep.SUMMARY_CSV_OUT):
            self.assertEqual(path.parent, prep.EVIDENCE_DIR)

    def test_inputs_are_the_two_tracked_evidence_csvs(self):
        self.assertEqual(prep.EVENT_CSV_IN.name, "01_stage_a0_direction_event_analysis.csv")
        self.assertEqual(prep.TRACE_CSV_IN.name, "02_direction_event_window_trace.csv")

    def test_only_declared_windows_are_used(self):
        # Guard against accidental window sweeps creeping into the prep step.
        self.assertEqual(prep.P8_WINDOW, (0, 7))
        self.assertEqual(prep.P12_WINDOW, (4, 12))
        self.assertEqual(prep.C8_LEFT_WINDOW, (-8, -1))
        self.assertEqual(prep.C8_RIGHT_WINDOW, (0, 7))
        self.assertEqual(prep.C12_LEFT_WINDOW, (-12, -1))
        self.assertEqual(prep.C12_RIGHT_WINDOW, (0, 11))


class TestInputEvidenceImmutability(unittest.TestCase):
    """The two upstream evidence CSVs keep their published SHA256."""

    PUBLISHED = {
        "01_stage_a0_direction_event_analysis.csv": (
            "db6060e80ae0353e9d74d41ffca990d2d177027458ef65cca479e0cd239d760e"
        ),
        "02_direction_event_window_trace.csv": (
            "f4c081df2f83f3a3650361f5f5afb7cb3936569540571255305e13c5ce457fb6"
        ),
    }

    def test_published_lf_sha256_matches_repo_blob(self):
        """Compare against the repo blob (LF canonical form), not the CRLF checkout."""
        import subprocess

        for name, expected in self.PUBLISHED.items():
            blob = subprocess.run(
                ["git", "cat-file", "blob", f"HEAD:0-doc/80-audit-local/g1_p3_rule_analysis/{name}"],
                cwd=str(ROOT),
                capture_output=True,
                check=True,
            ).stdout
            self.assertEqual(hashlib.sha256(blob).hexdigest(), expected, name)


if __name__ == "__main__":
    unittest.main()
