"""Regenerate canonical Clean RGB frames for a pinned G1 episode frame set.

Purpose
-------
The P2-G3 VLM feasibility probe needs *real* robot RGB that is legal model
input.  Local A/B audit material only exists as labelled side-by-side panels,
which are explicitly **not** valid VLM input (text overlay, panel borders,
resampled cells).  This script therefore re-renders the original frames from
frozen source state using the *existing, unmodified* P1 renderer through the
frozen ``MVP_RGB_SOURCE_AND_ALIGNMENT_CONTRACT_v1`` path:

    MODEL_RGB[t] = render(STATE_t)

Nothing about the RGB contract, G1 segmentation or M2 keyframes is changed.
No frame is cropped out of a labelled panel.  ``MUJOCO_GL=wgl`` matches the
renderer setting already recorded by Phase 1/1B.

Interpreter
-----------
Requires the existing Project-1/2 renderer environment and is **read-only**
with respect to it::

    PY=C:/Users/95611/miniconda3/envs/project1_robomimic_audit/python.exe
    $PY scripts/materialize_g3_vlm_rgb_frames.py --help

Typical use::

    $PY scripts/materialize_g3_vlm_rgb_frames.py \
        --episode-id data/demo_47 \
        --frames 50 70 90 --context-frames 49 91 94 \
        --output-dir <tmp>/rgb \
        --provenance-out <tmp>/rgb_provenance.csv

``--expect-csv`` verifies the freshly rendered ``pixel_sha256`` against a
previously frozen frame manifest (e.g. the Phase-1B
``G3_Context_Window_Frame_Provenance_20261012.csv``), which proves the
regenerated pixels are byte-identical to the frozen evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _load_expected(path: Path, episode_id: str) -> dict[int, set[str]]:
    """Read frame_index -> {pixel_sha256} for every frozen row of an episode.

    The Phase-1B provenance CSV records *context* rows per target segment, so a
    frame that is a keyframe of segment X usually appears only as context of a
    neighbouring segment.  Keying on the frame index (collecting every hash
    observed for it) lets a regenerated frame be verified regardless of which
    segment's row happens to mention it.
    """
    expected: dict[int, set[str]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            src = row.get("source_episode_id") or row.get("episode_id")
            if src != episode_id:
                continue
            try:
                index = int(row["frame_index"])
            except (KeyError, TypeError, ValueError):
                continue
            digest = (row.get("pixel_sha256") or "").lower()
            if digest:
                expected.setdefault(index, set()).add(digest)
    return expected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--episode-id", required=True, help="e.g. data/demo_47")
    parser.add_argument("--frames", type=int, nargs="+", required=True,
                        help="target-segment frame indices, temporal order")
    parser.add_argument("--context-frames", type=int, nargs="*", default=[],
                        help="optional neighbour-segment frames (recorded as context)")
    parser.add_argument("--context-roles", nargs="*", default=[],
                        help="role label per --context-frames entry "
                             "(e.g. PREV_SEGMENT_END NEXT_SEGMENT_START NEXT_SEGMENT_MIDDLE)")
    parser.add_argument("--target-segment-id", default="")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--provenance-out")
    parser.add_argument("--summary-out",
                        help=("write the machine-readable summary here; the renderer "
                              "prints a banner on stdout, so parse this file, not stdout"))
    parser.add_argument("--expect-csv", help="frozen frame provenance CSV to verify against")
    args = parser.parse_args(argv)

    os.environ.setdefault("MUJOCO_GL", "wgl")

    from project2_g1.config import load_g1_p1_config
    from project2_g1.source import build_can_mh_adapter
    from project2_mvp.m2_materializer import assert_frozen_g1_identity
    from project2_mvp.rgb_input import render_clean_rgb_frames, write_clean_rgb_png

    identity = assert_frozen_g1_identity()
    config = load_g1_p1_config()
    adapter = build_can_mh_adapter(config)

    target_frames = [int(v) for v in args.frames]
    context_frames = [int(v) for v in args.context_frames]
    if args.context_roles and len(args.context_roles) != len(context_frames):
        parser.error("--context-roles count must match --context-frames count")

    all_frames = target_frames + context_frames
    if len(set(all_frames)) != len(all_frames):
        parser.error("frame indices must be unique across target and context")

    rendered = render_clean_rgb_frames(adapter, args.episode_id, all_frames)
    by_index = {frame.frame_index: frame for frame in rendered}

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    expected = _load_expected(Path(args.expect_csv), args.episode_id) if args.expect_csv else {}

    rows = []
    mismatches = []
    for role_kind, indices, roles in (
        ("TARGET_KEYFRAME", target_frames, [None] * len(target_frames)),
        ("CONTEXT", context_frames, list(args.context_roles) + [None] * len(context_frames)),
    ):
        for position, index in enumerate(indices):
            frame = by_index[index]
            role = roles[position] if position < len(roles) else None
            label = f"{args.episode_id.replace('/', '_')}_f{index:05d}.png"
            path = write_clean_rgb_png(frame, out_dir / label)
            pixel_sha = frame.provenance["pixel_sha256"]

            expect_hashes = expected.get(index)
            match = None
            if expect_hashes:
                match = pixel_sha.lower() in expect_hashes
                if not match:
                    mismatches.append({
                        "frame_index": index,
                        "expected": sorted(expect_hashes),
                        "actual": pixel_sha,
                    })

            rows.append({
                "source_episode_id": args.episode_id,
                "target_segment_id": args.target_segment_id,
                "frame_index": index,
                "kind": role_kind,
                "evidence_role": role or "",
                "is_target_segment_frame": role_kind == "TARGET_KEYFRAME",
                "png_path": str(path),
                "png_bytes": path.stat().st_size,
                "pixel_sha256": pixel_sha,
                "png_file_sha256": _file_sha256(path),
                "contract_version": frame.provenance["contract_version"],
                "overlay_applied": frame.provenance["overlay_applied"],
                "audit_mp4_used": frame.provenance["audit_mp4_used"],
                "lossy_video_roundtrip": frame.provenance["lossy_video_roundtrip"],
                "shape": "x".join(str(v) for v in frame.provenance["shape"]),
                "matches_frozen_manifest": "" if match is None else match,
            })

    if args.provenance_out:
        out = Path(args.provenance_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    summary = {
        "episode_id": args.episode_id,
        "target_segment_id": args.target_segment_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "frozen_g1_identity": identity,
        "frames": rows,
        "frozen_mismatches": mismatches,
        "contract_verified": {
            "overlay_free": all(not r["overlay_applied"] for r in rows),
            "no_audit_mp4": all(not r["audit_mp4_used"] for r in rows),
            "no_lossy_roundtrip": all(not r["lossy_video_roundtrip"] for r in rows),
        },
    }
    if args.summary_out:
        out = Path(args.summary_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str),
                       encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    if mismatches:
        print("FROZEN_MANIFEST_MISMATCH", file=sys.stderr)
        return 5
    return 0


def _file_sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
