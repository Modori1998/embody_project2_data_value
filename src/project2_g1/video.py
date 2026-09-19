"""Episode visual resolver for G1-P1 smoke samples.

Can/MH raw/low_dim stores no RGB. Existing episode videos were not found.
Smoke videos are rendered from P1 RoboMimicStateRenderer using states[t],
which aligns with RGB_t / PROPRIO_t. Only smoke episodes are encoded.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np

from .paths import ensure_project1_on_path


def count_video_frames(path: str | Path) -> int:
    import cv2

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video: {path}")
    try:
        length = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if length > 0:
            return length
        frames = 0
        while True:
            ok, _ = capture.read()
            if not ok:
                break
            frames += 1
        return frames
    finally:
        capture.release()


def render_episode_audit_video(
    adapter,
    source_episode_id: str,
    output_path: str | Path,
    *,
    fps: float = 20.0,
) -> dict[str, Any]:
    """Render one smoke episode. Does not materialize the full dataset."""

    ensure_project1_on_path()
    import cv2
    from project1_benchmark.robomimic_rgb_materializer import RoboMimicStateRenderer

    os.environ.setdefault("MUJOCO_GL", "wgl")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    states = np.asarray(adapter.get_state_sequence(source_episode_id))
    model_file = adapter.get_model_file(source_episode_id)
    renderer = RoboMimicStateRenderer(adapter)
    writer = None
    try:
        print(
            f"G1-P1 video render start {source_episode_id} frames={len(states)} -> {output}",
            flush=True,
        )
        for index, state in enumerate(states):
            image = renderer.render(model_file, state)
            if writer is None:
                height, width = image.shape[:2]
                writer = cv2.VideoWriter(
                    str(output),
                    cv2.VideoWriter_fourcc(*"mp4v"),
                    float(fps),
                    (int(width), int(height)),
                )
                if not writer.isOpened():
                    raise RuntimeError(f"VIDEO_WRITER_OPEN_FAILED: {output}")
            bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            cv2.putText(
                bgr,
                f"{source_episode_id}  frame {index}",
                (4, 14),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.32,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            writer.write(bgr)
            if (index + 1) % 25 == 0 or index + 1 == len(states):
                print(
                    f"G1-P1 video render {source_episode_id} {index + 1}/{len(states)}",
                    flush=True,
                )
    finally:
        if writer is not None:
            writer.release()
        renderer.close()
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"VIDEO_OUTPUT_INVALID: {output}")
    frame_count = count_video_frames(output)
    return {
        "video_path": str(output.resolve()),
        "requested_frames": int(len(states)),
        "written_frames": int(frame_count),
        "fps": float(fps),
        "source": "P1 RoboMimicStateRenderer reset_to(model_file, states[t])",
        "alignment_rule": "video_frame[t] = render(STATE_t) = RGB_t / PROPRIO_t",
    }
