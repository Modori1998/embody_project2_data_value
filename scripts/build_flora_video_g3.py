"""CPU-only Flora MP4 evidence preparation.

Exit codes: 0 success, 2 fail-closed source/video/PTS/manifest error.
Nothing here starts a VLM, changes original Flora JSON or creates G1 labels.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.project2_g3.flora_video_evidence import VideoEvidenceError, build_video_evidence


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--flora-zip", required=True, help="Flora export ZIP with raw_json/demo_N.json members")
    ap.add_argument("--video-dir", required=True, help="Directory containing videos/ or demo_N_agentview_20fps.mp4")
    ap.add_argument("--output-dir", required=True, help="Must not already contain files")
    ap.add_argument("--episode", action="append", dest="episodes", help="Repeat for smoke; omit for all 15")
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--ffprobe", default="ffprobe")
    args = ap.parse_args()
    try:
        summary = build_video_evidence(
            args.flora_zip, args.video_dir, args.output_dir,
            episodes=args.episodes, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe,
        )
    except (VideoEvidenceError, ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print("FLORA_VIDEO_G3_BLOCKED:", exc, file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
