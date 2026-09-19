"""Video frame count must match Formal signal length when a clip exists."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np


class VideoSignalAlignmentTests(unittest.TestCase):
    def test_video_signal_frame_alignment_helper(self) -> None:
        try:
            import cv2
        except ImportError:
            self.skipTest("cv2 not available in this interpreter")
        n = 5
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "clip.mp4"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 20.0, (64, 64))
            self.assertTrue(writer.isOpened())
            for index in range(n):
                frame = np.full((64, 64, 3), index, dtype=np.uint8)
                writer.write(frame)
            writer.release()
            from project2_g1.video import count_video_frames

            counted = count_video_frames(path)
            self.assertEqual(counted, n)


if __name__ == "__main__":
    unittest.main()
