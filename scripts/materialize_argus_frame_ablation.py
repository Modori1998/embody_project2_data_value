"""Render approved schedules with the frozen read-only renderer; no inference."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("STOP_OUTPUT_EXISTS")
    schedule = json.loads(args.schedule.read_text(encoding="utf-8"))
    if len(schedule["cells"]) != 34 or schedule["blocked_cells"]:
        raise ValueError("STOP_APPROVED_MATRIX_REQUIRED")
    from project2_g1.config import load_g1_p1_config
    from project2_g1.source import build_can_mh_adapter
    from project2_mvp.m2_materializer import assert_frozen_g1_identity
    from project2_mvp.rgb_input import render_clean_rgb_frames, write_clean_rgb_png
    identity = assert_frozen_g1_identity()
    frozen_path = ROOT / "0-doc/10-design-review/evidence/P2_G3_Taxonomy_v0_2_20261013/sample_manifest.csv"
    frozen = {r["segment_id"]: r for r in csv.DictReader(frozen_path.open(encoding="utf-8-sig")) if r["cohort"] == "microset"}
    if hashlib.sha256(frozen_path.read_bytes()).hexdigest() != schedule["source_manifest_sha256"]:
        raise ValueError("STOP_SOURCE_MANIFEST_DRIFT")
    os.environ.setdefault("MUJOCO_GL", "wgl")
    adapter = build_can_mh_adapter(load_g1_p1_config())
    args.output.mkdir(parents=True)
    manifest = {"schedule_sha256": hashlib.sha256(args.schedule.read_bytes()).hexdigest(),
                "frozen_g1_identity": identity, "cells": [], "frames": {}, "inference_calls": 0}
    try:
        for sid, row in frozen.items():
            cells = [c for c in schedule["cells"] if c["segment_id"] == sid]
            indices = sorted({i for c in cells for i in c["frame_ids"]})
            rendered = render_clean_rgb_frames(adapter, row["episode_id"], indices)
            expected = dict(zip(map(int, row["target_keyframes"].split(";")),
                                zip(row["frame_png_sha256s"].split(";"), row["frame_pixel_sha256s"].split(";"))))
            for frame in rendered:
                if frame.provenance["shape"] != [128, 128, 3]:
                    raise ValueError("STOP_PREPROCESSING_DRIFT")
                path = write_clean_rgb_png(frame, args.output / "rgb" / f"{sid}_f{frame.frame_index:05d}.png")
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if frame.frame_index in expected and (digest, frame.provenance["pixel_sha256"]) != expected[frame.frame_index]:
                    raise ValueError(f"STOP_ORIGINAL_RGB_DRIFT:{sid}:{frame.frame_index}")
                manifest["frames"][f"{sid}:{frame.frame_index}"] = {
                    "path": str(path.resolve()), "png_sha256": digest, "frame_index": frame.frame_index,
                    "nominal_timestamp_s": frame.frame_index / 20.0, "actual_timestamp_s": None,
                    "timestamp_basis": "nominal control clock 20 Hz; actual PTS unavailable",
                    "provenance": frame.provenance}
            manifest["cells"].extend(cells)
            print(sid, "rendered", len(indices), "anchors verified", len(expected), flush=True)
    finally:
        close = getattr(adapter, "close", None)
        if callable(close):
            close()
    (args.output / "input_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("COMPLETE", len(manifest["frames"]), "unique frames", len(manifest["cells"]), "cells", flush=True)


if __name__ == "__main__":
    main()
