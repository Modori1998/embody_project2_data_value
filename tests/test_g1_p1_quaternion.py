"""Quaternion geodesic tests: identity, sign invariance, small-angle sanity."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np

from project2_g1.signals import quaternion_geodesic_angle


class QuaternionTests(unittest.TestCase):
    def test_quaternion_sign_invariance(self) -> None:
        q = np.array([0.1, -0.2, 0.3, 0.9], dtype=np.float64)
        q = q / np.linalg.norm(q)
        zero = quaternion_geodesic_angle(q, q)
        flipped = quaternion_geodesic_angle(q, -q)
        self.assertEqual(zero.shape, (1,))
        self.assertTrue(np.allclose(zero, 0.0, atol=1e-10))
        self.assertTrue(np.allclose(flipped, 0.0, atol=1e-10))

    def test_small_angle_z_rotation(self) -> None:
        theta = math.radians(10.0)
        identity = np.array([0.0, 0.0, 0.0, 1.0])
        rotated = np.array([0.0, 0.0, math.sin(theta / 2.0), math.cos(theta / 2.0)])
        angle = float(quaternion_geodesic_angle(identity, rotated)[0])
        self.assertAlmostEqual(angle, theta, places=6)

    def test_does_not_use_raw_quat_subtraction(self) -> None:
        q = np.array([0.0, 0.0, 0.0, 1.0])
        minus = -q
        naive = float(np.linalg.norm(q - minus))
        geodesic = float(quaternion_geodesic_angle(q, minus)[0])
        self.assertGreater(naive, 1.0)
        self.assertAlmostEqual(geodesic, 0.0, places=10)


if __name__ == "__main__":
    unittest.main()
