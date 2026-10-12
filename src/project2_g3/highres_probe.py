"""Phase-1B high-resolution feasibility probe (experimental, non-invasive).

Why this file exists
--------------------
The Phase-1B brief asks, read-only first, whether the renderer can be asked for a
different output width/height.  Answer from source inspection:

* ``RoboMimicStateRenderer.__init__(self, adapter)`` takes no resolution argument;
* ``RoboMimicStateRenderer.render(self, model_file, state)`` takes none either;
* the size comes from the module constant ``FORMAL_RGB_RESOLUTION = (128, 128)``
  in ``project1_benchmark/robomimic_adapter.py``;
* ``canonicalize_raw_mujoco_rgb`` **raises** ``RGBContractError`` whenever the
  native render shape is not exactly ``(128, 128, 3)``, with the message
  "resize is forbidden".

So the P1 public API does **not** support a custom resolution, and the frozen RGB
contract actively forbids a different native shape.

This module therefore does **not** modify P1.  It only asks the *underlying*
robosuite simulator, through an unmodified ``RoboMimicStateRenderer`` instance,
whether a larger native render is physically possible at all.  That answer is
what a change proposal needs.  Nothing produced here is fed into any formal
pipeline, and no frozen output is touched.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from project2_g1.config import load_g1_p1_config
from project2_g1.paths import PROJECT2_ROOT
from project2_g1.source import build_can_mh_adapter, load_formal_episode

from .development_pool import write_json

HIGHRES_PROBE_VERSION = "P2_G3_PHASE1B_HIGHRES_FEASIBILITY_V1"
FORMAL_RESOLUTION = (128, 128)
CANDIDATE_RESOLUTIONS: tuple[tuple[int, int], ...] = ((128, 128), (256, 256), (512, 512))

# Representative frames chosen because Phase 1 flagged them as occlusion / small
# object cases.  (episode_id, frame_index, why)
DEFAULT_SAMPLE_FRAMES: tuple[tuple[str, int, str], ...] = (
    ("data/demo_33", 69, "grasp-segment END; can partly out of view"),
    ("data/demo_75", 48, "MIDDLE of a DIRECTION_CHANGE segment; can occluded"),
    ("data/demo_75", 97, "MIDDLE of a DIRECTION_CHANGE segment; can occluded"),
)


def _sha256(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes(order="C")).hexdigest()


def probe_highres(
    output_root: str | Path,
    *,
    run_id: str | None = None,
    project_root: str | Path | None = None,
    samples: Sequence[tuple[str, int, str]] | None = None,
    resolutions: Sequence[tuple[int, int]] = CANDIDATE_RESOLUTIONS,
    save_png: bool = True,
) -> dict[str, Any]:
    """Render the same source states at several native sizes, without P1 changes."""

    from project2_mvp.rgb_input import _default_renderer_factory  # noqa: PLC2701

    root = Path(project_root or PROJECT2_ROOT).resolve()
    run_id = run_id or "g3_phase1b_highres_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    output = Path(output_root) / run_id
    output.mkdir(parents=True, exist_ok=True)

    config = load_g1_p1_config()
    adapter = build_can_mh_adapter(config)
    samples = tuple(samples or DEFAULT_SAMPLE_FRAMES)

    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    renderer = None
    try:
        renderer = _default_renderer_factory(adapter)
        for episode_id, frame_index, why in samples:
            episode = load_formal_episode(adapter, episode_id)
            states = np.asarray(adapter.get_state_sequence(episode_id))
            if frame_index < 0 or frame_index >= len(states):
                errors.append(f"{episode_id}: frame {frame_index} out of range")
                continue
            state = states[frame_index]
            model_file = adapter.get_model_file(episode_id)
            for height, width in resolutions:
                try:
                    # reset_to through the *unmodified* P1 renderer, then ask the
                    # underlying simulator directly for a different native size.
                    renderer.environment.reset_to(
                        {"model": model_file, "states": np.asarray(state)}
                    )
                    raw = renderer.environment.env.sim.render(
                        height=height, width=width, camera_name="agentview"
                    )
                    rgb = np.ascontiguousarray(np.asarray(raw)[::-1])
                    if rgb.shape != (height, width, 3) or rgb.dtype != np.uint8:
                        errors.append(
                            f"{episode_id}:f{frame_index}@{height}x{width} "
                            f"unexpected shape/dtype {rgb.shape}/{rgb.dtype}"
                        )
                        continue
                    png = None
                    if save_png:
                        from PIL import Image

                        png = output / f"{episode_id.replace('/', '__')}__f{frame_index}__{height}x{width}.png"
                        Image.fromarray(rgb).save(png)
                    rows.append({
                        "episode_id": episode_id,
                        "frame_index": frame_index,
                        "why_sampled": why,
                        "height": height,
                        "width": width,
                        "shape": list(rgb.shape),
                        "dtype": str(rgb.dtype),
                        "pixel_sha256": _sha256(rgb),
                        "unique_colours": int(len(np.unique(rgb.reshape(-1, 3), axis=0))),
                        "png_path": None if png is None else str(png.relative_to(output)),
                        "native_render": True,
                        "resized_from_formal": False,
                    })
                except Exception as exc:  # noqa: BLE001 - report, never mask
                    errors.append(f"{episode_id}:f{frame_index}@{height}x{width} "
                                  f"{type(exc).__name__}: {exc}")
    finally:
        close = getattr(renderer, "close", None)
        if callable(close):
            close()
        close_adapter = getattr(adapter, "close", None)
        if callable(close_adapter):
            close_adapter()

    by_resolution: dict[str, Any] = {}
    for height, width in resolutions:
        subset = [r for r in rows if (r["height"], r["width"]) == (height, width)]
        by_resolution[f"{height}x{width}"] = {
            "frames_rendered": len(subset),
            "mean_unique_colours": (
                float(np.mean([r["unique_colours"] for r in subset])) if subset else None
            ),
        }

    summary = {
        "highres_probe_version": HIGHRES_PROBE_VERSION,
        "p1_renderer_modified": False,
        "formal_rgb_contract_modified": False,
        "formal_outputs_touched": False,
        "fed_into_formal_pipeline": False,
        "p1_renderer_supports_custom_resolution": False,
        "p1_renderer_api_evidence": [
            "RoboMimicStateRenderer.__init__(self, adapter) has no width/height argument",
            "RoboMimicStateRenderer.render(self, model_file, state) has no width/height argument",
            "FORMAL_RGB_RESOLUTION = (128, 128) is a module constant in robomimic_adapter.py",
            "canonicalize_raw_mujoco_rgb raises RGBContractError on any other native shape "
            "('resize is forbidden')",
        ],
        "underlying_simulator_accepts_other_sizes": bool(rows),
        "formal_resolution": list(FORMAL_RESOLUTION),
        "candidate_resolutions": [list(r) for r in resolutions],
        "frames": rows,
        "by_resolution": by_resolution,
        "errors": errors,
        "interpretation": (
            "The frozen P1 API cannot be asked for a custom size and the frozen RGB "
            "contract rejects any non-128x128 native shape. A higher-resolution "
            "variant would therefore require an explicit Owner-approved contract "
            "change, not a local edit."
        ),
    }
    write_json(output / "highres_feasibility.json", summary)
    write_json(output / "run_meta.json", {
        "run_id": run_id,
        "created_at": datetime.now().astimezone().isoformat(),
        "highres_probe_version": HIGHRES_PROBE_VERSION,
        "output_scope": "DEVELOPMENT_ONLY_EXPERIMENTAL_NOT_FORMAL",
    })
    return {"output_run": str(output.resolve()), **summary}


def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="P2-G3 Phase-1B high-res feasibility probe")
    parser.add_argument("--run-id")
    parser.add_argument("--output-root")
    args = parser.parse_args()
    root = (
        Path(args.output_root) if args.output_root
        else PROJECT2_ROOT / "outputs" / "g3_phase1b_highres"
    )
    result = probe_highres(root, run_id=args.run_id)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
