from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.boundary_engine import CANDIDATE_GRIPPER, UnlabeledSegment
from project2_g1.source import FormalEpisodeArrays
from project2_mvp.m2 import assert_no_privileged_inputs, select_keyframes, summarize_motion
from project2_mvp.m2_materializer import (
    EXPECTED_FROZEN_G1_IDENTITY,
    compute_m2_sanity_checks,
    runtime_frozen_g1_identity,
    validate_frozen_g1_identity,
)


def segment(start: int, end: int) -> UnlabeledSegment:
    duration = end - start + 1
    return UnlabeledSegment(
        segment_id="demo-S0001", source_episode_id="data/demo", start_frame=start,
        end_frame=end, duration_frames=duration, duration_sec=duration * 0.05,
        left_boundary_id="B", right_boundary_id="R", left_boundary_reason="x",
        right_boundary_reason="y", segmentation_version="seg", config_version="cfg",
        short_segment_flag=False, long_segment_flag=False, review_required=False,
    )


def episode(pos: np.ndarray, actions: np.ndarray | None = None) -> FormalEpisodeArrays:
    n = len(pos)
    return FormalEpisodeArrays(
        source_episode_id="data/demo", native_episode_key="demo", frame_index=np.arange(n),
        eef_pos=np.asarray(pos, dtype=float), eef_quat=np.zeros((n, 4)),
        gripper_qpos=np.column_stack([np.linspace(.04, .02, n), np.linspace(-.04, -.02, n)]),
        joint_pos=np.zeros((n, 7)), actions=np.ones((n, 7)) if actions is None else actions,
        provenance={},
    )


class M2Tests(unittest.TestCase):
    def test_single_frame_dedups_rgb_and_preserves_all_roles(self) -> None:
        frames = select_keyframes(segment(3, 3), left_boundary_type=CANDIDATE_GRIPPER)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].roles, ("START", "MIDDLE", "END", "GRIPPER_EVENT"))

    def test_two_odd_even_middle_and_right_boundary_exclusion(self) -> None:
        self.assertEqual([x.frame_index for x in select_keyframes(segment(4, 5), left_boundary_type=None)], [4, 5])
        self.assertEqual([x.frame_index for x in select_keyframes(segment(4, 6), left_boundary_type=None)], [4, 5, 6])
        self.assertEqual([x.frame_index for x in select_keyframes(segment(4, 7), left_boundary_type=None)], [4, 5, 7])
        self.assertNotIn(8, [x.frame_index for x in select_keyframes(segment(4, 7), left_boundary_type=None)])

    def test_left_gripper_is_start_and_replay_is_deterministic(self) -> None:
        one = select_keyframes(segment(4, 8), left_boundary_type=CANDIDATE_GRIPPER)
        two = select_keyframes(segment(4, 8), left_boundary_type=CANDIDATE_GRIPPER)
        self.assertEqual(one, two)
        self.assertIn("GRIPPER_EVENT", one[0].roles)
        self.assertEqual(one[0].frame_index, 4)
        motion = summarize_motion(
            segment(0, 1), episode(np.zeros((2, 3))),
            gripper_state=np.array([0, 0]), left_boundary_type=CANDIDATE_GRIPPER,
        )
        self.assertTrue(motion["gripper_transition_present"])

    def test_motion_net_path_zero_direction_coarse_and_action(self) -> None:
        pos = np.array([[0, 0, 0], [1, 0, 0], [0, 0, 0], [0, 1, 0]], dtype=float)
        actions = np.array([[3, 4, 0, 0, 0, 0, 0]] * 4, dtype=float)
        row = summarize_motion(segment(0, 3), episode(pos, actions), gripper_state=np.array([1, 1, 0, 0]))
        self.assertAlmostEqual(row["eef_net_displacement_m"], 1.0)
        self.assertAlmostEqual(row["eef_path_length_m"], 3.0)
        self.assertEqual(row["eef_main_direction_xyz"], [0.0, 1.0, 0.0])
        self.assertTrue(row["coarse_direction_context_complete"])
        self.assertAlmostEqual(row["coarse_direction_change_rad"], np.pi / 2)
        self.assertEqual(row["action_magnitude_mean"], 5.0)
        self.assertTrue(row["gripper_transition_present"])

    def test_zero_direction_and_incomplete_coarse_are_not_false_zero(self) -> None:
        row = summarize_motion(segment(0, 1), episode(np.zeros((2, 3))), gripper_state=np.array([1, 1]))
        self.assertEqual(row["eef_main_direction_xyz"], [0.0, 0.0, 0.0])
        self.assertIsNone(row["coarse_direction_change_rad"])
        self.assertFalse(row["coarse_direction_context_complete"])

    def test_duration_identity_and_privileged_rejection(self) -> None:
        with self.assertRaises(ValueError):
            summarize_motion(replace(segment(0, 1), duration_frames=9), episode(np.zeros((2, 3))), gripper_state=None)
        for field in ("object", "Can_pos", "reward", "done", "success", "next_obs", "states"):
            with self.assertRaises(ValueError, msg=field):
                assert_no_privileged_inputs([field])

    def test_frozen_g1_identity_is_explicit_and_detects_drift(self) -> None:
        actual = runtime_frozen_g1_identity()
        self.assertEqual(actual, EXPECTED_FROZEN_G1_IDENTITY)
        validate_frozen_g1_identity(actual)
        drifted = dict(actual)
        drifted["tau_C12"] = float(actual["tau_C12"]) + 0.01
        with self.assertRaises(ValueError):
            validate_frozen_g1_identity(drifted)

    def test_runtime_sanity_is_computed_and_detects_corruption(self) -> None:
        segments = [{
            "segment_id": "demo-S0001",
            "source_episode_id": "data/demo",
            "start_frame": 4,
            "end_frame": 6,
            "duration_frames": 3,
            "left_boundary_type": CANDIDATE_GRIPPER,
        }]
        keyframes = [
            {"segment_id": "demo-S0001", "source_episode_id": "data/demo", "frame_index": 4,
             "roles": "START|GRIPPER_EVENT", "png_relpath": "a.png",
             "rgb_contract_version": "MVP_RGB_SOURCE_AND_ALIGNMENT_CONTRACT_v1"},
            {"segment_id": "demo-S0001", "source_episode_id": "data/demo", "frame_index": 5,
             "roles": "MIDDLE", "png_relpath": "b.png",
             "rgb_contract_version": "MVP_RGB_SOURCE_AND_ALIGNMENT_CONTRACT_v1"},
            {"segment_id": "demo-S0001", "source_episode_id": "data/demo", "frame_index": 6,
             "roles": "END", "png_relpath": "c.png",
             "rgb_contract_version": "MVP_RGB_SOURCE_AND_ALIGNMENT_CONTRACT_v1"},
        ]
        motion = [{
            "segment_id": "demo-S0001",
            "duration_sec": 0.15,
            "eef_net_displacement_m": 0.01,
            "eef_path_length_m": 0.02,
            "eef_displacement_xyz": [0.01, 0.0, 0.0],
            "eef_main_direction_xyz": [1.0, 0.0, 0.0],
            "gripper_start_aperture": 0.08,
            "gripper_end_aperture": 0.04,
            "action_magnitude_mean": 0.1,
            "action_magnitude_max": 0.2,
            "action_magnitude_std": 0.01,
            "coarse_direction_change_rad": None,
        }]
        provenance = {
            "contract_version": "MVP_RGB_SOURCE_AND_ALIGNMENT_CONTRACT_v1",
            "overlay_applied": False,
            "audit_mp4_used": False,
            "lossy_video_roundtrip": False,
        }
        rgb = [
            {"source_episode_id": "data/demo", "segment_id": "demo-S0001",
             "frame_index": frame, "png_relpath": path, "provenance": dict(provenance)}
            for frame, path in ((4, "a.png"), (5, "b.png"), (6, "c.png"))
        ]
        checks = compute_m2_sanity_checks(segments, keyframes, motion, rgb)
        self.assertTrue(all(checks.values()))

        corrupted = [dict(row) for row in keyframes]
        corrupted[1]["frame_index"] = 99
        bad = compute_m2_sanity_checks(segments, corrupted, motion, rgb)
        self.assertFalse(bad["KEYFRAME_FRAME_IN_SEGMENT"])
        self.assertFalse(bad["MIDDLE_DETERMINISTIC"])


if __name__ == "__main__":
    unittest.main()
