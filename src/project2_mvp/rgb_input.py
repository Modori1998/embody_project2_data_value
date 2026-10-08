"""Clean RGB model-input contract for the Project 2 retrieval-first MVP.

The existing G1 audit videos are human-review artifacts. They contain text
overlays and pass through lossy MP4 encoding, so they are not valid Formal
model inputs for SigLIP2 or a VLM.

Formal model RGB is rendered directly from source STATE_t by the existing P1
RoboMimicStateRenderer and is consumed in-memory or exported losslessly as PNG.
No text overlay, audit annotation, or video decode roundtrip is permitted here.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np

from project2_g1.paths import ensure_project1_on_path


MODEL_RGB_CONTRACT_VERSION = "MVP_RGB_SOURCE_AND_ALIGNMENT_CONTRACT_v1"

RendererFactory = Callable[[Any], Any]


@dataclass(frozen=True)
class CleanRGBFrame:
    """One source-aligned, overlay-free RGB frame."""

    source_episode_id: str
    frame_index: int
    rgb: np.ndarray
    provenance: dict[str, Any]


def _default_renderer_factory(adapter: Any) -> Any:
    ensure_project1_on_path()
    from project1_benchmark.robomimic_rgb_materializer import RoboMimicStateRenderer

    return RoboMimicStateRenderer(adapter)


def _validate_rgb(image: np.ndarray) -> np.ndarray:
    rgb = np.asarray(image)
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError(f"MODEL_RGB_SHAPE_INVALID: expected HxWx3, got {rgb.shape}")
    if rgb.dtype != np.uint8:
        raise ValueError(f"MODEL_RGB_DTYPE_INVALID: expected uint8, got {rgb.dtype}")
    if rgb.size == 0:
        raise ValueError("MODEL_RGB_EMPTY")
    return np.ascontiguousarray(rgb).copy()


def _renderer_runtime_metadata(renderer: Any) -> dict[str, Any]:
    """Record stable scalar renderer settings when the implementation exposes them."""

    metadata: dict[str, Any] = {
        "renderer_class": f"{type(renderer).__module__}.{type(renderer).__name__}",
        "mujoco_gl": os.environ.get("MUJOCO_GL"),
    }
    for name in (
        "camera_name",
        "camera",
        "width",
        "height",
        "render_width",
        "render_height",
    ):
        if not hasattr(renderer, name):
            continue
        value = getattr(renderer, name)
        if isinstance(value, (str, int, float, bool)) or value is None:
            metadata[name] = value
    return metadata


def render_clean_rgb_frames(
    adapter: Any,
    source_episode_id: str,
    frame_indices: Iterable[int],
    *,
    renderer_factory: RendererFactory | None = None,
) -> tuple[CleanRGBFrame, ...]:
    """Render selected Formal model-input frames directly from source states.

    Alignment is index-preserving:
        MODEL_RGB[t] = render(STATE_t)

    The same canonical timestep index t is used by the existing P1/P2 source
    contract for proprio and recorded action. The action remains a source-native
    command; this function does not reinterpret it as a physical outcome.
    """

    indices = tuple(int(index) for index in frame_indices)
    if not indices:
        raise ValueError("MODEL_RGB_FRAME_INDICES_EMPTY")

    states = np.asarray(adapter.get_state_sequence(source_episode_id))
    if len(states) == 0:
        raise ValueError(f"MODEL_RGB_SOURCE_STATES_EMPTY: {source_episode_id}")

    for index in indices:
        if index < 0 or index >= len(states):
            raise IndexError(
                f"MODEL_RGB_FRAME_INDEX_OUT_OF_RANGE: episode={source_episode_id} "
                f"index={index} state_count={len(states)}"
            )

    os.environ.setdefault("MUJOCO_GL", "wgl")
    factory = renderer_factory or _default_renderer_factory
    renderer = factory(adapter)
    model_file = adapter.get_model_file(source_episode_id)

    frames: list[CleanRGBFrame] = []
    try:
        renderer_meta = _renderer_runtime_metadata(renderer)
        for index in indices:
            rgb = _validate_rgb(renderer.render(model_file, states[index]))
            pixel_sha256 = hashlib.sha256(rgb.tobytes(order="C")).hexdigest()
            frames.append(
                CleanRGBFrame(
                    source_episode_id=source_episode_id,
                    frame_index=index,
                    rgb=rgb,
                    provenance={
                        "contract_version": MODEL_RGB_CONTRACT_VERSION,
                        "source": "P1 RoboMimicStateRenderer direct STATE_t render",
                        "alignment_rule": (
                            "MODEL_RGB[t] = render(STATE_t); same canonical index t "
                            "as PROPRIO[t] / recorded ACTION[t]"
                        ),
                        "color_space": "RGB",
                        "dtype": str(rgb.dtype),
                        "shape": [int(value) for value in rgb.shape],
                        "overlay_applied": False,
                        "audit_mp4_used": False,
                        "lossy_video_roundtrip": False,
                        "pixel_sha256": pixel_sha256,
                        "renderer_runtime": renderer_meta,
                    },
                )
            )
    finally:
        close = getattr(renderer, "close", None)
        if callable(close):
            close()

    return tuple(frames)


def write_clean_rgb_png(frame: CleanRGBFrame, output_path: str | Path) -> Path:
    """Losslessly export one clean RGB frame without annotations or resizing."""

    import cv2

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    bgr = cv2.cvtColor(frame.rgb, cv2.COLOR_RGB2BGR)
    ok = cv2.imwrite(
        str(output),
        bgr,
        [cv2.IMWRITE_PNG_COMPRESSION, 3],
    )
    if not ok or not output.is_file() or output.stat().st_size <= 0:
        raise RuntimeError(f"MODEL_RGB_PNG_WRITE_FAILED: {output}")
    return output
