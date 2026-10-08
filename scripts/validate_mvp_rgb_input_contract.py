"""Local runtime smoke for MVP_RGB_SOURCE_AND_ALIGNMENT_CONTRACT_v1.

This script intentionally renders only a few selected frames from one episode.
It does not run SigLIP2, a VLM, or any retrieval experiment.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.config import load_g1_p1_config
from project2_g1.source import build_can_mh_adapter, load_formal_episode
from project2_mvp.rgb_input import (
    MODEL_RGB_CONTRACT_VERSION,
    render_clean_rgb_frames,
    write_clean_rgb_png,
)


def _default_indices(frame_count: int) -> list[int]:
    if frame_count <= 0:
        raise ValueError("MODEL_RGB_SOURCE_LENGTH_INVALID")
    return sorted(set([0, frame_count // 2, frame_count - 1]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate clean RGB model-input source/alignment contract"
    )
    parser.add_argument("--episode-id", default="data/demo_0")
    parser.add_argument("--frame-indices", type=int, nargs="*", default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "outputs" / "mvp_rgb_contract_smoke",
    )
    args = parser.parse_args(argv)

    config = load_g1_p1_config()
    adapter = build_can_mh_adapter(config)
    episode = load_formal_episode(adapter, args.episode_id)
    states = np.asarray(adapter.get_state_sequence(args.episode_id))

    checks = {
        "formal_vs_state_length": len(episode.frame_index) == len(states),
        "formal_vs_action_length": len(episode.frame_index) == len(episode.actions),
    }
    if not all(checks.values()):
        summary = {
            "status": "BLOCKED_TEMPORAL_ALIGNMENT",
            "contract_version": MODEL_RGB_CONTRACT_VERSION,
            "episode_id": args.episode_id,
            "formal_frames": len(episode.frame_index),
            "state_frames": len(states),
            "action_frames": len(episode.actions),
            "checks": checks,
        }
        print(json.dumps(summary, indent=2))
        return 1

    indices = (
        list(args.frame_indices)
        if args.frame_indices
        else _default_indices(len(states))
    )
    frames = render_clean_rgb_frames(adapter, args.episode_id, indices)

    episode_dir = args.output_dir / args.episode_id.replace("/", "__")
    episode_dir.mkdir(parents=True, exist_ok=True)

    exported = []
    roundtrip_ok = True
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("cv2 required for PNG roundtrip validation") from exc

    for frame in frames:
        png_path = write_clean_rgb_png(
            frame,
            episode_dir / f"frame_{frame.frame_index:06d}.png",
        )
        decoded_bgr = cv2.imread(str(png_path), cv2.IMREAD_COLOR)
        if decoded_bgr is None:
            raise RuntimeError(f"MODEL_RGB_PNG_READ_FAILED: {png_path}")
        decoded_rgb = cv2.cvtColor(decoded_bgr, cv2.COLOR_BGR2RGB)
        pixel_equal = bool(np.array_equal(decoded_rgb, frame.rgb))
        roundtrip_ok = roundtrip_ok and pixel_equal
        exported.append(
            {
                "frame_index": frame.frame_index,
                "png_path": str(png_path.resolve()),
                "png_roundtrip_pixel_equal": pixel_equal,
                "provenance": frame.provenance,
            }
        )

    renderer_shapes = {
        tuple(item["provenance"]["shape"]) for item in exported
    }
    checks.update(
        {
            "selected_indices_in_range": all(
                0 <= int(index) < len(states) for index in indices
            ),
            "clean_overlay_flag": all(
                item["provenance"]["overlay_applied"] is False for item in exported
            ),
            "no_audit_mp4": all(
                item["provenance"]["audit_mp4_used"] is False for item in exported
            ),
            "no_lossy_video_roundtrip": all(
                item["provenance"]["lossy_video_roundtrip"] is False
                for item in exported
            ),
            "rgb_uint8_hwc3": all(
                item["provenance"]["dtype"] == "uint8"
                and len(item["provenance"]["shape"]) == 3
                and item["provenance"]["shape"][2] == 3
                for item in exported
            ),
            "consistent_render_shape": len(renderer_shapes) == 1,
            "lossless_png_roundtrip": roundtrip_ok,
        }
    )

    status = "PASS" if all(checks.values()) else "BLOCKED_RGB_CONTRACT"
    summary = {
        "status": status,
        "contract_version": MODEL_RGB_CONTRACT_VERSION,
        "episode_id": args.episode_id,
        "frame_count": len(states),
        "selected_frame_indices": indices,
        "checks": checks,
        "frames": exported,
        "model_input_source": "direct P1 RoboMimicStateRenderer STATE_t render",
        "audit_mp4_used": False,
        "text_overlay_used": False,
        "siglip2_executed": False,
        "vlm_executed": False,
    }
    summary_path = episode_dir / "rgb_contract_smoke_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({**summary, "summary_path": str(summary_path.resolve())}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
