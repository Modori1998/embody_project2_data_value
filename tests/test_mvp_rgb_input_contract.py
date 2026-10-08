"""Unit tests for the retrieval-first MVP clean RGB contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_mvp.rgb_input import (
    MODEL_RGB_CONTRACT_VERSION,
    render_clean_rgb_frames,
    write_clean_rgb_png,
)


class _FakeAdapter:
    def __init__(self) -> None:
        self.states = np.arange(12, dtype=np.float64).reshape(3, 4)

    def get_state_sequence(self, source_episode_id: str) -> np.ndarray:
        return self.states

    def get_model_file(self, source_episode_id: str) -> str:
        return "<mujoco/>"


class _FakeRenderer:
    def __init__(self, adapter: _FakeAdapter) -> None:
        self.adapter = adapter
        self.camera_name = "fake_camera"
        self.width = 10
        self.height = 8
        self.closed = False

    def render(self, model_file: str, state: np.ndarray) -> np.ndarray:
        value = int(state[0])
        return np.full((self.height, self.width, 3), value, dtype=np.uint8)

    def close(self) -> None:
        self.closed = True


class ModelRGBContractTests(unittest.TestCase):
    def test_direct_render_preserves_pixels_and_contract_metadata(self) -> None:
        adapter = _FakeAdapter()
        frames = render_clean_rgb_frames(
            adapter,
            "data/demo_fake",
            [0, 2],
            renderer_factory=_FakeRenderer,
        )
        self.assertEqual([frame.frame_index for frame in frames], [0, 2])
        self.assertTrue(np.all(frames[0].rgb == 0))
        self.assertTrue(np.all(frames[1].rgb == 8))
        for frame in frames:
            self.assertEqual(
                frame.provenance["contract_version"],
                MODEL_RGB_CONTRACT_VERSION,
            )
            self.assertFalse(frame.provenance["overlay_applied"])
            self.assertFalse(frame.provenance["audit_mp4_used"])
            self.assertFalse(frame.provenance["lossy_video_roundtrip"])
            self.assertEqual(frame.provenance["color_space"], "RGB")
            self.assertEqual(frame.rgb.dtype, np.uint8)

    def test_out_of_range_index_fails_fast(self) -> None:
        with self.assertRaises(IndexError):
            render_clean_rgb_frames(
                _FakeAdapter(),
                "data/demo_fake",
                [3],
                renderer_factory=_FakeRenderer,
            )

    def test_png_roundtrip_is_lossless_when_cv2_available(self) -> None:
        try:
            import cv2
        except ImportError:
            self.skipTest("cv2 not available in this interpreter")

        frame = render_clean_rgb_frames(
            _FakeAdapter(),
            "data/demo_fake",
            [1],
            renderer_factory=_FakeRenderer,
        )[0]
        with TemporaryDirectory() as tmp:
            path = write_clean_rgb_png(frame, Path(tmp) / "frame_000001.png")
            decoded_bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
            self.assertIsNotNone(decoded_bgr)
            decoded_rgb = cv2.cvtColor(decoded_bgr, cv2.COLOR_BGR2RGB)
            self.assertTrue(np.array_equal(decoded_rgb, frame.rgb))


if __name__ == "__main__":
    unittest.main()
