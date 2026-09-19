"""Temporal alignment: source / derived / action / EEF share the same frame index."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np

from project2_g1.alignment import audit_temporal_alignment
from project2_g1.config import G1P1Config
from project2_g1.signals import compute_formal_signals
from project2_g1.source import FormalEpisodeArrays


def _synthetic_episode(n: int = 8) -> FormalEpisodeArrays:
    t = np.arange(n, dtype=np.float64)
    pos = np.stack([0.01 * t, 0.02 * t, np.full(n, 0.9)], axis=1)
    quat = np.tile(np.array([0.0, 0.0, 0.0, 1.0]), (n, 1))
    gripper = np.stack([np.full(n, 0.04), np.full(n, -0.04)], axis=1)
    actions = np.zeros((n, 7), dtype=np.float64)
    actions[:, 2] = 0.1
    return FormalEpisodeArrays(
        source_episode_id="data/demo_synthetic",
        native_episode_key="demo_synthetic",
        frame_index=np.arange(n, dtype=np.int64),
        eef_pos=pos,
        eef_quat=quat,
        gripper_qpos=gripper,
        joint_pos=np.zeros((n, 7), dtype=np.float64),
        actions=actions,
        provenance={},
    )


class TemporalAlignmentTests(unittest.TestCase):
    def test_temporal_alignment(self) -> None:
        episode = _synthetic_episode()
        signals = compute_formal_signals(episode, G1P1Config())
        audit = audit_temporal_alignment(episode, signals, rgb_frame_count=len(episode.frame_index))
        self.assertEqual(audit.status, "PASS", audit.checks)
        self.assertTrue(np.array_equal(signals.frame_index, episode.frame_index))
        self.assertTrue(np.allclose(signals.eef_x, episode.eef_pos[:, 0]))
        self.assertTrue(np.allclose(signals.action_raw, episode.actions))
        self.assertAlmostEqual(float(signals.delta_x[0]), 0.0)
        self.assertAlmostEqual(float(signals.delta_x[1]), 0.01)
        expected_speed = float(np.linalg.norm([0.01, 0.02, 0.0]) / 0.05)
        self.assertAlmostEqual(float(signals.translation_speed[1]), expected_speed, places=10)

    def test_no_silent_plus_one_shift(self) -> None:
        episode = _synthetic_episode()
        signals = compute_formal_signals(episode, G1P1Config())
        self.assertFalse(np.allclose(signals.eef_x[:-1], episode.eef_pos[1:, 0]) and not np.allclose(signals.eef_x, episode.eef_pos[:, 0]))
        self.assertFalse(np.allclose(signals.action_raw[:-1, 2], episode.actions[1:, 2]) and not np.allclose(signals.action_raw, episode.actions))


if __name__ == "__main__":
    unittest.main()
