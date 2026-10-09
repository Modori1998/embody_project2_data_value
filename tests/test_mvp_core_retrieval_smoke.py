from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_mvp.core_retrieval import (
    MOTION_VECTOR_DIM,
    faiss_index_flat_ip_smoke,
    fit_smoke_motion_scaler,
    motion_raw_vector,
    pool_unique_frame_embeddings,
    validate_siglip2_embedding,
)


def motion_row() -> dict:
    return {
        "duration_sec": 1.0,
        "eef_net_displacement_m": 0.1,
        "eef_path_length_m": 0.2,
        "eef_displacement_xyz": [0.1, 0.0, 0.0],
        "eef_main_direction_xyz": [1.0, 0.0, 0.0],
        "coarse_direction_change_rad": 0.2,
        "gripper_start_state": "OPEN",
        "gripper_end_state": "CLOSED",
        "gripper_transition_present": True,
        "action_magnitude_mean": 0.4,
        "action_magnitude_max": 0.8,
        "action_magnitude_std": 0.1,
    }


class CoreRetrievalSmokeTests(unittest.TestCase):
    def test_motion_representation_dimension_and_finite(self) -> None:
        raw = [motion_raw_vector({**motion_row(), "duration_sec": 1.0 + index}) for index in range(6)]
        scaler = fit_smoke_motion_scaler(raw)
        vector = scaler.transform(raw[0])
        self.assertEqual(vector.shape, (MOTION_VECTOR_DIM,))
        self.assertTrue(np.isfinite(vector).all())
        self.assertAlmostEqual(float(np.linalg.norm(vector)), 1.0, places=6)
        self.assertEqual(scaler.role, "SMOKE_ONLY_SCALER")

    def test_visual_pooling_deduplicates_multi_role_frame(self) -> None:
        keyframes = [
            {"frame_index": 4, "roles": "START|GRIPPER_EVENT"},
            {"frame_index": 4, "roles": "START"},
            {"frame_index": 9, "roles": "END"},
        ]
        embeddings = {4: np.array([1.0, 0.0]), 9: np.array([0.0, 1.0])}
        pooled, unique = pool_unique_frame_embeddings(keyframes, embeddings)
        self.assertEqual(unique, (4, 9))
        self.assertTrue(np.allclose(pooled, np.array([1.0, 1.0]) / np.sqrt(2)))

    def test_faiss_index_flat_ip_returns_valid_top_k(self) -> None:
        try:
            import faiss  # noqa: F401
        except ImportError:
            self.skipTest("faiss-cpu is installed only in the isolated runtime environment")
        vectors = [np.eye(6, dtype=np.float32)[index] for index in range(6)]
        ids = [f"segment-{index}" for index in range(6)]
        result = faiss_index_flat_ip_smoke(vectors, ids, vectors[0], top_k=5, exclude_segment_id=ids[0])
        self.assertEqual(len(result), 5)
        self.assertTrue(all(row["segment_id"] in ids for row in result))
        self.assertNotIn(ids[0], [row["segment_id"] for row in result])

    def test_siglip2_embedding_finite(self) -> None:
        vector = validate_siglip2_embedding(np.array([[3.0, 4.0]], dtype=np.float32))
        self.assertTrue(np.isfinite(vector).all())
        self.assertAlmostEqual(float(np.linalg.norm(vector)), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
