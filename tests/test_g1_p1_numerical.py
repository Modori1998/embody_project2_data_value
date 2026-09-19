"""Core derived signals must be finite, or source anomalies must be reported."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np

from project2_g1.config import G1P1Config
from project2_g1.signals import collect_numerical_issues, compute_formal_signals
from project2_g1.source import FormalEpisodeArrays


class NumericalQualityTests(unittest.TestCase):
    def test_numerical_quality(self) -> None:
        n = 6
        episode = FormalEpisodeArrays(
            source_episode_id="data/demo_finite",
            native_episode_key="demo_finite",
            frame_index=np.arange(n, dtype=np.int64),
            eef_pos=np.linspace(0.0, 0.1, n * 3, dtype=np.float64).reshape(n, 3),
            eef_quat=np.tile(np.array([0.0, 0.0, 0.0, 1.0]), (n, 1)),
            gripper_qpos=np.stack([np.full(n, 0.03), np.full(n, -0.03)], axis=1),
            joint_pos=np.zeros((n, 7)),
            actions=np.zeros((n, 7)),
            provenance={},
        )
        signals = compute_formal_signals(episode, G1P1Config())
        self.assertEqual(signals.numerical_issues, [])
        for name, array in signals.arrays_for_quality_check().items():
            self.assertTrue(np.isfinite(array).all(), msg=name)

    def test_source_nan_is_reported_not_silently_filled(self) -> None:
        n = 4
        pos = np.zeros((n, 3), dtype=np.float64)
        pos[2] = np.nan
        episode = FormalEpisodeArrays(
            source_episode_id="data/demo_nan",
            native_episode_key="demo_nan",
            frame_index=np.arange(n, dtype=np.int64),
            eef_pos=pos,
            eef_quat=np.tile(np.array([0.0, 0.0, 0.0, 1.0]), (n, 1)),
            gripper_qpos=np.zeros((n, 2)),
            joint_pos=np.zeros((n, 7)),
            actions=np.zeros((n, 7)),
            provenance={},
        )
        signals = compute_formal_signals(episode, G1P1Config())
        self.assertTrue(signals.numerical_issues)
        self.assertTrue(np.isnan(signals.eef_x[2]))
        reported = collect_numerical_issues(signals)
        self.assertTrue(any(item["nan"] > 0 for item in reported))


if __name__ == "__main__":
    unittest.main()
