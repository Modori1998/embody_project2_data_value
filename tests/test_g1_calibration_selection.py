from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.calibration_selection import (
    FORBIDDEN_SELECTION_FIELDS,
    SCREENING_FEATURES,
    annotate_rows,
    build_shortlist,
    deterministic_manifest_id,
    select_final,
    validate_manifest_round_trip,
    validate_selection,
)


def row(index: int) -> dict:
    final = 2 + (index % 7)
    direction = index % 4
    gripper = max(1, final - direction)
    return {
        "episode_id": f"data/demo_{1000 + index}",
        "episode_length_frames": 70 + index * 13,
        "duration_seconds": (70 + index * 13) / 20,
        "baseline_candidate_count": final + 3 + (index % 3),
        "baseline_final_boundary_count": final,
        "gripper_primary_count": gripper,
        "direction_primary_count": direction,
        "move_to_idle_primary_count": 0,
        "idle_to_move_primary_count": 0,
        "merged_boundary_count": 1 + (index % 3),
        "gripper_direction_merged_count": 1 if index % 2 == 0 else 0,
        "short_segment_count": index % 3,
        "min_segment_length": 5 + index % 4,
        "mean_segment_length": 20.0,
        "max_segment_length": 50 + index,
        "direction_primary_ratio": direction / final,
        "gripper_primary_ratio": gripper / final,
        "quality_group": ("BETTER", "OKAY", "WORSE")[index % 3],
        "selection_screening_status": "PASS",
    }


class CalibrationSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        annotated, self.thresholds = annotate_rows([row(i) for i in range(24)])
        self.pool = annotated

    def test_seed_exclusion_fresh_count_unique_and_coverage(self) -> None:
        seed = {"data/demo_0", "data/demo_32", "data/demo_179", "data/demo_230", "data/demo_242", "data/demo_278"}
        shortlist = build_shortlist(self.pool, n=12)
        selected = select_final(shortlist, n=6)
        for item in shortlist:
            item["evaluation_role"] = "UNASSIGNED"
        for item in selected:
            item["evaluation_role"] = "UNASSIGNED"
        result = validate_selection(
            shortlist=shortlist, selected=selected, seed_ids=seed,
            config_hash="c" * 64, expected_config_hash="c" * 64,
            signal_hash="s" * 64, expected_signal_hash="s" * 64,
        )
        self.assertEqual(result, {"status": "PASS", "fresh_count": 6, "seed_overlap": 0})
        self.assertEqual(len({item["episode_id"] for item in selected}), 6)

    def test_selection_is_deterministic_for_same_screening_input(self) -> None:
        first = [item["episode_id"] for item in select_final(build_shortlist(self.pool, n=12), n=6)]
        second = [item["episode_id"] for item in select_final(build_shortlist(list(reversed(self.pool)), n=12), n=6)]
        self.assertEqual(first, second)

    def test_no_privileged_human_or_evaluation_fields(self) -> None:
        self.assertFalse(set(SCREENING_FEATURES) & FORBIDDEN_SELECTION_FIELDS)
        for item in self.pool:
            self.assertFalse(set(item) & FORBIDDEN_SELECTION_FIELDS)
            item["evaluation_role"] = "UNASSIGNED"
            self.assertEqual(item["evaluation_role"], "UNASSIGNED")

    def test_fixed_config_hash_mismatch_blocks(self) -> None:
        shortlist = build_shortlist(self.pool, n=12)
        selected = select_final(shortlist, n=6)
        for item in shortlist + selected:
            item["evaluation_role"] = "UNASSIGNED"
        with self.assertRaisesRegex(ValueError, "config hash"):
            validate_selection(
                shortlist=shortlist, selected=selected, seed_ids=set(),
                config_hash="a", expected_config_hash="b",
                signal_hash="s", expected_signal_hash="s",
            )

    def test_manifest_round_trip_and_stable_identity(self) -> None:
        payload = {
            "created_at": "2026-09-17T00:00:00+08:00",
            "protocol_document": "Project2_G1_P3_Calibration_Protocol_FROZEN_v1_20260917.md",
            "selection_version": "P2_G1_FRESH_CALIBRATION_SELECTION_V1",
            "source_dataset_id": "robomimic_v15_can_mh",
            "existing_seed_export_id": "seed",
            "existing_seed_episode_ids": [f"data/demo_{i}" for i in range(6)],
            "fresh_episode_ids": [f"data/demo_{i}" for i in range(10, 16)],
            "target_calibration_count": 12,
            "fresh_count": 6,
            "evaluation_usage": "FORBIDDEN_UNTIL_SEPARATE_EVALUATION_SELECTION",
            "parameter_search_allowed": False,
            "human_review_status": "NOT_STARTED",
        }
        payload["manifest_id"] = deterministic_manifest_id(payload)
        changed_time = dict(payload, created_at="2026-09-17T01:00:00+08:00")
        self.assertEqual(deterministic_manifest_id(payload), deterministic_manifest_id(changed_time))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(validate_manifest_round_trip(path)["fresh_count"], 6)


if __name__ == "__main__":
    unittest.main()
