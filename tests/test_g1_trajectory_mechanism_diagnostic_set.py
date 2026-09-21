"""Tests for the G1-P3 trajectory mechanism diagnostic set builder.

Covers the frozen validation design contract:
* calibration episodes excluded
* near-gripper (<= 12 frames) consolidation context excluded
* incomplete ±12 context excluded
* P12 / C12 formulas
* P12 top-50 % eligibility
* C12 bottom/top quartile arm construction
* one event per episode, no episode shared across arms
* matching without reuse, match-distance formula
* blinded manifest forbidden-column / forbidden-string audit
* determinism
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
for extra in (str(SCRIPTS), str(SRC)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import build_g1_trajectory_mechanism_diagnostic_set as builder  # noqa: E402


def make_row(
    episode_id: str,
    event_frame: int,
    *,
    p12: float = 0.10,
    c12: float = 0.90,
    evidence: float = 1.5,
    run_length: int | None = 5,
    distance_to_gripper: int = 50,
    independent: bool = True,
    edge_incomplete: bool = False,
) -> dict:
    """Build a synthetic candidate-pool row."""
    return {
        "episode_id": episode_id,
        "boundary_id": f"{episode_id.split('/')[-1]}-B{event_frame:04d}",
        "event_frame": event_frame,
        "candidate_type": builder.CANDIDATE_DIRECTION,
        "representative_candidate_id": f"{episode_id.split('/')[-1]}-C{event_frame:04d}",
        "member_candidate_ids": f"{episode_id.split('/')[-1]}-C{event_frame:04d}",
        "member_candidate_count": 1,
        "member_candidate_types": builder.CANDIDATE_DIRECTION,
        "is_independent_direction_final": independent,
        "is_gripper_primary_merged": not independent,
        "n_frames": 200,
        "left_context_frames": 12 if not edge_incomplete else 5,
        "right_context_frames": 12 if not edge_incomplete else 5,
        "config_hash": builder.EXPECTED_CONFIG_HASH,
        "signal_contract_hash": builder.EXPECTED_SIGNAL_HASH,
        "segmentation_version": builder.EXPECTED_SEGMENTATION_VERSION,
        "direction_evidence": evidence,
        "run_length": run_length,
        "P12": p12,
        "left_path_length_m": 0.05,
        "right_path_length_m": 0.05,
        "left_net_displacement_m": 0.045,
        "right_net_displacement_m": 0.045,
        "left_straightness": c12,
        "right_straightness": c12,
        "C12": c12,
        "distance_to_nearest_gripper_final": distance_to_gripper,
        "edge_context_incomplete": edge_incomplete,
        "eligible_after_all_exclusions": False,
        "ineligibility_reason": "",
    }


def make_eligible_pool(count: int = 80) -> list[dict]:
    """Pool where P12, C12, evidence and run_length all rise with the index."""
    return [
        make_row(
            f"data/demo_{index}",
            100 + index,
            p12=0.01 * index,
            c12=0.80 + 0.002 * index,
            evidence=1.0 + 0.01 * index,
            run_length=index,
        )
        for index in range(1, count + 1)
    ]


class TestWindowMaths(unittest.TestCase):
    def test_path_length_sums_step_norms(self):
        self.assertAlmostEqual(builder.path_length([0.01, 0.02, 0.03]), 0.06, places=12)

    def test_net_displacement_is_vector_norm(self):
        self.assertAlmostEqual(
            builder.net_displacement([0.03, 0.04], [0.0, 0.0], [0.0, 0.0]), 0.07, places=12
        )

    def test_net_displacement_zero_for_closed_loop(self):
        self.assertAlmostEqual(
            builder.net_displacement([0.05, -0.05], [0.0, 0.0], [0.0, 0.0]), 0.0, places=12
        )

    def test_straightness_is_one_for_collinear(self):
        self.assertAlmostEqual(builder.straightness(0.06, 0.06), 1.0, places=12)

    def test_straightness_nan_for_degenerate_path(self):
        self.assertTrue(math.isnan(builder.straightness(0.0, 0.0)))
        self.assertTrue(math.isnan(builder.straightness(1e-12, 1e-12)))
        self.assertFalse(math.isinf(builder.straightness(0.0, 0.0)))

    def test_median_and_quantile(self):
        self.assertAlmostEqual(builder.median([3.0, 1.0, 2.0]), 2.0, places=12)
        self.assertAlmostEqual(builder.median([1.0, 2.0, 3.0, 4.0]), 2.5, places=12)
        self.assertAlmostEqual(builder.quantile([0.0, 1.0, 2.0, 3.0, 4.0], 0.25), 1.0, places=12)


class TestP12Formula(unittest.TestCase):
    """P12 = median(translation_speed_mps) over relative_frame [+4, +12]."""

    def test_uses_exactly_the_declared_window(self):
        speed = [float(i) for i in range(60)]
        frame = 20
        expected = builder.median([speed[frame + offset] for offset in range(4, 13)])
        self.assertAlmostEqual(builder.compute_p12(speed, frame), expected, places=12)

    def test_window_is_nine_frames_from_plus_4_to_plus_12(self):
        self.assertEqual(builder.P12_WINDOW, (4, 12))
        self.assertEqual(len(builder.window_slice([0.0] * 60, 20, builder.P12_WINDOW)), 9)

    def test_sensitive_to_decay_after_plus_8(self):
        speed = [0.1] * 60
        frame = 20
        for offset in range(8, 13):
            speed[frame + offset] = 0.01
        value = builder.compute_p12(speed, frame)
        self.assertLess(value, 0.1)

    def test_is_median_not_mean(self):
        speed = [0.05] * 60
        frame = 10
        speed[frame + 12] = 100.0
        self.assertAlmostEqual(builder.compute_p12(speed, frame), 0.05, places=12)


class TestC12Formula(unittest.TestCase):
    """C12 = min(left_straightness over [-12,-1], right over [0,+11])."""

    def test_straight_trajectory_gives_one(self):
        n = 80
        step = [0.01] * n
        dx = [0.01] * n
        zero = [0.0] * n
        result = builder.compute_c12(step, dx, zero, zero, 30)
        self.assertAlmostEqual(result["left_straightness"], 1.0, places=9)
        self.assertAlmostEqual(result["right_straightness"], 1.0, places=9)
        self.assertAlmostEqual(result["C12"], 1.0, places=9)

    def test_out_and_back_gives_zero_straightness(self):
        n = 80
        dx = [0.01 if i % 2 == 0 else -0.01 for i in range(n)]
        step = [0.01] * n
        zero = [0.0] * n
        result = builder.compute_c12(step, dx, zero, zero, 30)
        self.assertLess(result["C12"], 0.05)

    def test_c12_is_the_minimum_of_the_two_sides(self):
        n = 80
        step = [0.01] * n
        zero = [0.0] * n
        # left half straight, right half alternating
        dx = [0.01 if i < 30 else (0.01 if i % 2 == 0 else -0.01) for i in range(n)]
        result = builder.compute_c12(step, dx, zero, zero, 30)
        self.assertAlmostEqual(
            result["C12"], min(result["left_straightness"], result["right_straightness"]), places=12
        )

    def test_degenerate_path_is_nan_not_inf(self):
        n = 80
        zero = [0.0] * n
        result = builder.compute_c12(zero, zero, zero, zero, 30)
        self.assertTrue(math.isnan(result["C12"]))
        self.assertFalse(math.isinf(result["C12"]))

    def test_windows_are_the_declared_ones(self):
        self.assertEqual(builder.C12_LEFT_WINDOW, (-12, -1))
        self.assertEqual(builder.C12_RIGHT_WINDOW, (0, 11))


class TestExclusions(unittest.TestCase):
    def test_near_gripper_within_12_frames_is_excluded(self):
        rows = [make_row("data/demo_1", 100, distance_to_gripper=12)]
        builder.evaluate_exclusions(rows)
        self.assertFalse(rows[0]["eligible_after_all_exclusions"])
        self.assertEqual(rows[0]["ineligibility_reason"], builder.R_NEAR_GRIPPER)

    def test_distance_13_frames_is_kept(self):
        rows = [make_row("data/demo_1", 100, distance_to_gripper=13)]
        builder.evaluate_exclusions(rows)
        self.assertTrue(rows[0]["eligible_after_all_exclusions"])

    def test_edge_incomplete_is_excluded(self):
        rows = [make_row("data/demo_1", 5, edge_incomplete=True)]
        builder.evaluate_exclusions(rows)
        self.assertFalse(rows[0]["eligible_after_all_exclusions"])
        self.assertEqual(rows[0]["ineligibility_reason"], builder.R_EDGE_CONTEXT)

    def test_gripper_primary_merged_is_excluded(self):
        rows = [make_row("data/demo_1", 100, independent=False)]
        builder.evaluate_exclusions(rows)
        self.assertFalse(rows[0]["eligible_after_all_exclusions"])
        self.assertEqual(rows[0]["ineligibility_reason"], builder.R_GRIPPER_PRIMARY_MERGED)

    def test_degenerate_trajectory_is_excluded(self):
        row = make_row("data/demo_1", 100)
        row["C12"] = float("nan")
        builder.evaluate_exclusions([row])
        self.assertEqual(row["ineligibility_reason"], builder.R_DEGENERATE)

    def test_missing_run_length_is_excluded(self):
        rows = [make_row("data/demo_1", 100, run_length=None)]
        builder.evaluate_exclusions(rows)
        self.assertEqual(rows[0]["ineligibility_reason"], builder.R_RUN_LENGTH)

    def test_exclusion_counts_match_flags(self):
        rows = [
            make_row("data/demo_1", 100),
            make_row("data/demo_2", 100, distance_to_gripper=3),
            make_row("data/demo_3", 100, edge_incomplete=True),
            make_row("data/demo_4", 100, independent=False),
        ]
        counts = builder.evaluate_exclusions(rows)
        self.assertEqual(counts["initial_direction_candidates"], 4)
        self.assertEqual(counts[builder.R_NEAR_GRIPPER], 1)
        self.assertEqual(counts[builder.R_EDGE_CONTEXT], 1)
        self.assertEqual(counts[builder.R_GRIPPER_PRIMARY_MERGED], 1)
        eligible = [r for r in rows if r["eligible_after_all_exclusions"]]
        self.assertEqual(len(eligible), 1)


class TestPercentileRanking(unittest.TestCase):
    def test_percentile_is_ascending_and_bounded(self):
        rows = make_eligible_pool(10)
        pct = builder.percentile_map(rows, "P12")
        values = sorted(rows, key=lambda r: float(r["P12"]))
        self.assertAlmostEqual(pct[str(values[0]["boundary_id"])], 0.0, places=12)
        self.assertAlmostEqual(pct[str(values[-1]["boundary_id"])], 1.0, places=12)

    def test_p12_eligible_pool_is_top_half(self):
        rows = make_eligible_pool(80)
        selection = builder.build_selection(rows)
        self.assertEqual(len(selection["p12_eligible"]), 40)
        lowest_kept = min(float(r["P12"]) for r in selection["p12_eligible"])
        highest_dropped = max(
            float(r["P12"]) for r in rows if r not in selection["p12_eligible"]
        )
        self.assertGreaterEqual(lowest_kept, highest_dropped)

    def test_no_calibration_threshold_values_are_used(self):
        """The design forbids consuming the calibration envelope cut values.

        The scan is AST-based so that the module docstring (which *names*
        these values in order to declare they are not used) and comments are
        excluded; only real numeric constants in executable code count.

        ``0.75`` is deliberately absent from this list: it legitimately
        appears as ``ARM_HIGH_QUANTILE`` (a rank quantile), never as a C12
        feature threshold. The next test pins that distinction.
        """
        import ast

        tree = ast.parse(Path(builder.__file__).read_text(encoding="utf-8"))
        numbers = {
            float(node.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)
        }
        for forbidden in (0.045, 0.050, 0.76):
            self.assertNotIn(forbidden, numbers, f"calibration cut value used in code: {forbidden}")

    def test_arm_quantiles_are_rank_quantiles_not_feature_thresholds(self):
        self.assertEqual(builder.ARM_LOW_QUANTILE, 0.25)
        self.assertEqual(builder.ARM_HIGH_QUANTILE, 0.75)
        self.assertEqual(builder.P12_ELIGIBLE_PERCENTILE, 0.50)
        # Arm membership is decided on percentiles, never on raw feature values.
        selection = builder.build_selection(make_eligible_pool(80))
        for row in selection["arm_a_pool"]:
            self.assertLessEqual(row["C12_percentile"], builder.ARM_LOW_QUANTILE)
        for row in selection["arm_b_pool"]:
            self.assertGreaterEqual(row["C12_percentile"], builder.ARM_HIGH_QUANTILE)


class TestArmConstruction(unittest.TestCase):
    def test_low_and_high_quartiles_within_p12_eligible_pool(self):
        rows = make_eligible_pool(80)
        selection = builder.build_selection(rows)
        for row in selection["arm_a_pool"]:
            self.assertLessEqual(row["C12_percentile"], builder.ARM_LOW_QUANTILE)
        for row in selection["arm_b_pool"]:
            self.assertGreaterEqual(row["C12_percentile"], builder.ARM_HIGH_QUANTILE)
        # Arm A must be strictly lower C12 than Arm B.
        self.assertLess(
            max(float(r["C12"]) for r in selection["arm_a_pool"]),
            min(float(r["C12"]) for r in selection["arm_b_pool"]),
        )

    def test_arm_pools_are_ten_each_on_the_fixture(self):
        selection = builder.build_selection(make_eligible_pool(80))
        self.assertEqual(len(selection["arm_a_pool"]), 10)
        self.assertEqual(len(selection["arm_b_pool"]), 10)

    def test_target_arm_size_is_ten(self):
        selection = builder.build_selection(make_eligible_pool(80))
        self.assertEqual(len(selection["arm_a"]), builder.TARGET_PER_ARM)
        self.assertEqual(len(selection["pairs"]), builder.TARGET_PER_ARM)


class TestEpisodeDiversity(unittest.TestCase):
    def test_one_event_per_episode_in_arm_a(self):
        rows = make_eligible_pool(40)
        # duplicate the lowest-C12 episode into the arm A pool
        duplicate = dict(rows[0])
        duplicate["boundary_id"] = "dup-B0001"
        duplicate["event_frame"] = 999
        pool = rows + [duplicate]
        selection = builder.build_selection(pool)
        episodes = [str(r["episode_id"]) for r in selection["arm_a"]]
        self.assertEqual(len(episodes), len(set(episodes)))

    def test_select_arm_a_dedupes_episodes(self):
        arm_a_pool = [
            make_row("data/demo_1", 10, c12=0.10),
            make_row("data/demo_1", 20, c12=0.11),
            make_row("data/demo_2", 30, c12=0.12),
        ]
        chosen = builder.select_arm_a(arm_a_pool, 10)
        self.assertEqual(len(chosen), 2)
        self.assertEqual({str(r["episode_id"]) for r in chosen}, {"data/demo_1", "data/demo_2"})

    def test_no_episode_shared_between_arms(self):
        selection = builder.build_selection(make_eligible_pool(80))
        arm_a_episodes = {str(r["episode_id"]) for r in selection["arm_a"]}
        arm_b_episodes = {str(pair[1]["episode_id"]) for pair in selection["pairs"]}
        self.assertEqual(arm_a_episodes & arm_b_episodes, set())

    def test_control_never_reuses_the_target_episode(self):
        def with_percentiles(row, p12_pct, ev_pct, run_pct):
            row.update(
                {
                    "P12_percentile": p12_pct,
                    "direction_evidence_percentile": ev_pct,
                    "run_length_percentile": run_pct,
                }
            )
            return row

        target = with_percentiles(make_row("data/demo_1", 100, c12=0.10), 0.5, 0.5, 0.5)
        arm_b_pool = [
            with_percentiles(make_row("data/demo_1", 200, c12=0.99), 0.5, 0.5, 0.5),  # same episode
            with_percentiles(make_row("data/demo_2", 200, c12=0.98), 0.5, 0.5, 0.5),
        ]
        pairs, unmatched = builder.select_arm_b([target], arm_b_pool)
        self.assertEqual(unmatched, 0)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(str(pairs[0][1]["episode_id"]), "data/demo_2")

    def test_each_arm_b_candidate_is_used_at_most_once(self):
        selection = builder.build_selection(make_eligible_pool(80))
        controls = [str(pair[1]["boundary_id"]) for pair in selection["pairs"]]
        self.assertEqual(len(controls), len(set(controls)))

    def test_all_selected_events_are_distinct(self):
        selection = builder.build_selection(make_eligible_pool(80))
        members = [str(r["boundary_id"]) for r in selection["arm_a"]]
        members += [str(pair[1]["boundary_id"]) for pair in selection["pairs"]]
        self.assertEqual(len(members), len(set(members)))


class TestMatchingDistance(unittest.TestCase):
    def test_match_distance_formula(self):
        a = {"P12_percentile": 0.2, "direction_evidence_percentile": 0.5, "run_length_percentile": 0.1}
        b = {"P12_percentile": 0.3, "direction_evidence_percentile": 0.4, "run_length_percentile": 0.4}
        expected = abs(0.2 - 0.3) + abs(0.5 - 0.4) + abs(0.1 - 0.4)
        self.assertAlmostEqual(builder.match_distance(a, b), expected, places=12)

    def test_zero_distance_for_identical_percentiles(self):
        a = {"P12_percentile": 0.5, "direction_evidence_percentile": 0.5, "run_length_percentile": 0.5}
        self.assertAlmostEqual(builder.match_distance(a, a), 0.0, places=12)

    def test_greedy_choice_minimises_distance(self):
        target = {
            "boundary_id": "t", "episode_id": "data/demo_1", "event_frame": 1,
            "C12": 0.1,
            "P12_percentile": 0.90, "direction_evidence_percentile": 0.90, "run_length_percentile": 0.90,
        }
        near = dict(target, boundary_id="n", episode_id="data/demo_2",
                    P12_percentile=0.91, direction_evidence_percentile=0.89, run_length_percentile=0.90)
        far = dict(target, boundary_id="f", episode_id="data/demo_3",
                   P12_percentile=0.10, direction_evidence_percentile=0.10, run_length_percentile=0.10)
        pairs, _ = builder.select_arm_b([target], [far, near])
        self.assertEqual(str(pairs[0][1]["boundary_id"]), "n")


class TestPairIdentityIntegrity(unittest.TestCase):
    """Arm A and its matched Arm B must share one pair_id and one distance."""

    def _internal_rows(self):
        selection = builder.build_selection(make_eligible_pool(80))
        event_ids = builder.assign_diagnostic_ids(selection["arm_a"], selection["pairs"])
        return builder.build_internal_rows(selection["arm_a"], selection["pairs"], event_ids)

    def test_every_pair_id_groups_exactly_one_a_and_one_b(self):
        rows = self._internal_rows()
        groups: dict[str, list[dict]] = {}
        for row in rows:
            groups.setdefault(str(row["pair_id"]), []).append(row)
        self.assertEqual(len(groups), builder.TARGET_PER_ARM)
        for pair_id, members in groups.items():
            self.assertEqual(len(members), 2, pair_id)
            self.assertEqual({m["arm"] for m in members}, {"A", "B"}, pair_id)

    def test_match_distance_is_consistent_across_a_pair(self):
        for pair_id, members in self._grouped(self._internal_rows()).items():
            distances = {float(m["match_distance"]) for m in members}
            self.assertEqual(len(distances), 1, pair_id)

    def test_match_distance_equals_recomputed_distance(self):
        for pair_id, members in self._grouped(self._internal_rows()).items():
            a = next(m for m in members if m["arm"] == "A")
            b = next(m for m in members if m["arm"] == "B")
            expected = (
                abs(float(a["P12_percentile"]) - float(b["P12_percentile"]))
                + abs(float(a["direction_evidence_percentile"]) - float(b["direction_evidence_percentile"]))
                + abs(float(a["run_length_percentile"]) - float(b["run_length_percentile"]))
            )
            self.assertAlmostEqual(float(a["match_distance"]), expected, places=12, msg=pair_id)

    def test_paired_rows_never_share_an_episode(self):
        for pair_id, members in self._grouped(self._internal_rows()).items():
            self.assertEqual(len({m["episode_id"] for m in members}), 2, pair_id)

    @staticmethod
    def _grouped(rows):
        groups: dict[str, list[dict]] = {}
        for row in rows:
            groups.setdefault(str(row["pair_id"]), []).append(row)
        return groups


class TestBlindingContract(unittest.TestCase):
    def test_forbidden_token_detection(self):
        payload = b"diagnostic_event_id,arm\nX,A\n"
        self.assertIn("arm", builder.audit_blinding(payload))

    def test_hypothesis_string_is_detected(self):
        payload = json.dumps({"note": builder.DESIGN_VERSION}).encode("utf-8")
        found = builder.audit_blinding(payload)
        self.assertIn("target", found)

    def test_clean_payload_passes(self):
        payload = b"diagnostic_event_id,episode_id\nG1P3-DIAG-001,data/demo_5\n"
        self.assertEqual(builder.audit_blinding(payload), [])

    def test_blinded_columns_contain_no_forbidden_token(self):
        header = ",".join(builder.BLINDED_COLUMNS).lower()
        for token in builder.FORBIDDEN_BLINDING_TOKENS:
            self.assertNotIn(token, header, token)

    def test_blinded_rows_contain_no_forbidden_token(self):
        pool = make_eligible_pool(80)
        selection = builder.build_selection(pool)
        event_ids = builder.assign_diagnostic_ids(selection["arm_a"], selection["pairs"])
        selected = list(selection["arm_a"]) + [pair[1] for pair in selection["pairs"]]
        set_id = builder.compute_set_id(selected, "20260921_000000", event_ids)
        rows = builder.build_blinded_rows(selection["arm_a"], selection["pairs"], event_ids, set_id)
        payload = builder.render_csv(builder.BLINDED_COLUMNS, rows).encode("utf-8")
        self.assertEqual(builder.audit_blinding(payload), [])

    def test_blinded_manifest_has_exactly_the_expected_columns(self):
        self.assertEqual(
            set(builder.BLINDED_COLUMNS),
            {
                "diagnostic_event_id",
                "episode_id",
                "boundary_id",
                "event_frame",
                "event_type",
                "representative_candidate_id",
                "member_candidate_ids",
                "diagnostic_set_id",
            },
        )


class TestCsvSerialization(unittest.TestCase):
    def test_render_is_lf_only_without_bom(self):
        payload = builder.render_csv(["a", "b"], [{"a": 1, "b": 2.5}])
        self.assertNotIn("\r", payload)
        self.assertTrue(payload.endswith("\n"))
        self.assertFalse(payload.encode("utf-8").startswith(b"\xef\xbb\xbf"))

    def test_nan_and_bool_formatting(self):
        self.assertEqual(builder.fmt(float("nan")), "nan")
        self.assertEqual(builder.fmt(float("inf")), "inf")
        self.assertEqual(builder.fmt(True), "true")
        self.assertEqual(builder.fmt(False), "false")
        self.assertEqual(builder.fmt(None), "")


class TestDeterminism(unittest.TestCase):
    def test_selection_is_reproducible(self):
        first = builder.build_selection(make_eligible_pool(80))
        second = builder.build_selection(make_eligible_pool(80))
        self.assertEqual(
            [str(r["boundary_id"]) for r in first["arm_a"]],
            [str(r["boundary_id"]) for r in second["arm_a"]],
        )
        self.assertEqual(
            [str(pair[1]["boundary_id"]) for pair in first["pairs"]],
            [str(pair[1]["boundary_id"]) for pair in second["pairs"]],
        )

    def test_set_id_is_stable_for_identical_selection(self):
        rows = make_eligible_pool(80)
        first = builder.build_selection(rows)
        ids_a = builder.assign_diagnostic_ids(first["arm_a"], first["pairs"])
        selected_a = list(first["arm_a"]) + [p[1] for p in first["pairs"]]
        set_a = builder.compute_set_id(selected_a, "20260921_000000", ids_a)

        second = builder.build_selection(make_eligible_pool(80))
        ids_b = builder.assign_diagnostic_ids(second["arm_a"], second["pairs"])
        selected_b = list(second["arm_a"]) + [p[1] for p in second["pairs"]]
        set_b = builder.compute_set_id(selected_b, "20260921_000000", ids_b)
        self.assertEqual(set_a, set_b)

    def test_diagnostic_ids_carry_no_arm_information(self):
        rows = make_eligible_pool(80)
        selection = builder.build_selection(rows)
        event_ids = builder.assign_diagnostic_ids(selection["arm_a"], selection["pairs"])
        ordered = sorted(event_ids.values())
        self.assertEqual(ordered, [f"G1P3-DIAG-{i:03d}" for i in range(1, 21)])


class TestCalibrationExclusion(unittest.TestCase):
    EXPECTED = {
        "data/demo_0", "data/demo_32", "data/demo_179", "data/demo_230",
        "data/demo_242", "data/demo_278", "data/demo_150", "data/demo_162",
        "data/demo_213", "data/demo_255", "data/demo_260", "data/demo_270",
    }

    def test_ssot_manifest_matches_the_frozen_calibration_set(self):
        ids = builder.load_calibration_episode_ids()
        self.assertEqual(len(ids), 12)
        self.assertEqual(set(ids), self.EXPECTED)

    def test_constant_matches_ssot_manifest(self):
        self.assertEqual(set(builder.CALIBRATION_EPISODE_IDS), self.EXPECTED)

    def test_no_calibration_episode_is_selected(self):
        selection = builder.build_selection(make_eligible_pool(80))
        selected = [str(r["episode_id"]) for r in selection["arm_a"]]
        selected += [str(pair[1]["episode_id"]) for pair in selection["pairs"]]
        self.assertEqual(set(selected) & self.EXPECTED, set())


class TestBuiltArtifacts(unittest.TestCase):
    """Checks against the real committed artifacts, skipped when absent."""

    def test_blinded_manifest_is_clean_when_present(self):
        if not builder.BLINDED_CSV.is_file():
            self.skipTest("blinded manifest not built yet")
        payload = builder.BLINDED_CSV.read_bytes()
        self.assertEqual(builder.audit_blinding(payload), [])
        self.assertNotIn(b"\r", payload)

    def test_pool_csv_is_lf_only_when_present(self):
        if not builder.POOL_CSV.is_file():
            self.skipTest("candidate pool not built yet")
        payload = builder.POOL_CSV.read_bytes()
        self.assertNotIn(b"\r", payload)
        self.assertFalse(payload.startswith(b"\xef\xbb\xbf"))

    def test_selected_events_respect_hard_rules(self):
        if not builder.INTERNAL_CSV.is_file():
            self.skipTest("selection not built yet")
        import csv as _csv

        with builder.INTERNAL_CSV.open("r", encoding="utf-8", newline="") as handle:
            rows = list(_csv.DictReader(handle))
        arm_a = [r for r in rows if r["arm"] == "A"]
        arm_b = [r for r in rows if r["arm"] == "B"]
        self.assertGreaterEqual(len(arm_a), builder.MIN_PER_ARM)
        self.assertEqual(len(arm_a), len(arm_b))
        episodes = [r["episode_id"] for r in rows]
        self.assertEqual(len(episodes), len(set(episodes)))
        self.assertEqual(set(episodes) & TestCalibrationExclusion.EXPECTED, set())
        for row in rows:
            self.assertGreater(int(row["distance_to_nearest_gripper_final"]), 12)
            self.assertNotEqual(row["C12"].lower(), "nan")

    def test_built_pairs_have_consistent_identity(self):
        if not builder.INTERNAL_CSV.is_file():
            self.skipTest("selection not built yet")
        import csv as _csv

        with builder.INTERNAL_CSV.open("r", encoding="utf-8", newline="") as handle:
            rows = list(_csv.DictReader(handle))
        groups: dict[str, list[dict]] = {}
        for row in rows:
            groups.setdefault(row["pair_id"], []).append(row)
        self.assertEqual(len(groups), len([r for r in rows if r["arm"] == "A"]))
        for pair_id, members in groups.items():
            self.assertEqual(len(members), 2, pair_id)
            self.assertEqual({m["arm"] for m in members}, {"A", "B"}, pair_id)
            self.assertEqual(len({m["episode_id"] for m in members}), 2, pair_id)
            a = next(m for m in members if m["arm"] == "A")
            b = next(m for m in members if m["arm"] == "B")
            expected = (
                abs(float(a["P12_percentile"]) - float(b["P12_percentile"]))
                + abs(float(a["direction_evidence_percentile"]) - float(b["direction_evidence_percentile"]))
                + abs(float(a["run_length_percentile"]) - float(b["run_length_percentile"]))
            )
            self.assertAlmostEqual(float(a["match_distance"]), expected, places=12, msg=pair_id)

    def test_built_blinded_manifest_matches_the_internal_selection(self):
        if not builder.BLINDED_CSV.is_file() or not builder.INTERNAL_CSV.is_file():
            self.skipTest("artifacts not built yet")
        import csv as _csv

        with builder.BLINDED_CSV.open("r", encoding="utf-8", newline="") as handle:
            blinded = list(_csv.DictReader(handle))
        with builder.INTERNAL_CSV.open("r", encoding="utf-8", newline="") as handle:
            internal = list(_csv.DictReader(handle))
        self.assertEqual(len(blinded), len(internal))
        self.assertEqual(
            {r["diagnostic_event_id"] for r in blinded},
            {r["diagnostic_event_id"] for r in internal},
        )


if __name__ == "__main__":
    unittest.main()
