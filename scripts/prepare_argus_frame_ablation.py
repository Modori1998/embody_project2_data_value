"""CPU-only frame schedule preparation; never loads a model or renders images.

Short segments fail closed rather than silently duplicating frames. Output is a
schedule, not a verified RGB manifest. Run from any directory with --output.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "0-doc/10-design-review/evidence/P2_G3_Taxonomy_v0_2_20261013/sample_manifest.csv"


def schedule(anchors: list[int], count: int) -> list[int]:
    if len(anchors) != 3 or anchors != sorted(set(anchors)):
        raise ValueError("STOP_ANCHOR_IDENTITY")
    if count < 3 or anchors[-1] - anchors[0] + 1 < count:
        raise ValueError("STOP_INSUFFICIENT_UNIQUE_FRAMES")
    selected = set(anchors)
    while len(selected) < count:
        ordered = sorted(selected)
        # Largest gap first, ties choose earliest left endpoint; floor midpoint.
        left, right = min(zip(ordered, ordered[1:]), key=lambda p: (-(p[1] - p[0]), p[0]))
        selected.add((left + right) // 2)
    return sorted(selected)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--short-controls", action="store_true", help="Approved matrix: ten 3/6/12 triples plus two 3/4 controls")
    args = parser.parse_args()
    rows = [r for r in csv.DictReader(FROZEN.open(encoding="utf-8-sig")) if r["cohort"] == "microset"]
    if len(rows) != 12 or len({r["segment_id"] for r in rows}) != 12:
        raise ValueError("STOP_COHORT_IDENTITY")
    planned = []
    for row in rows:
        anchors = list(map(int, row["target_keyframes"].split(";")))
        counts = (3, 4) if args.short_controls and int(row["segment_length"]) < 12 else (3, 6, 12)
        for count in counts:
            try:
                indices = schedule(anchors, count)
                status = "SCHEDULE_ONLY_RGB_NOT_MATERIALIZED"
            except ValueError as error:
                indices, status = [], str(error)
            planned.append({"segment_id": row["segment_id"], "episode_id": row["episode_id"],
                "start_frame": int(row["start_frame"]), "end_frame": int(row["end_frame"]),
                "requested_image_count": count, "frame_ids": indices,
                "nominal_timestamps_s": [i / 20.0 for i in indices],
                "timestamp_basis": "G1 nominal control clock 20 Hz; not measured video PTS",
                "status": status})
    result = {"version": "ARGUS_FRAME_SCHEDULE_APPROVED_V1" if args.short_controls else "ARGUS_FRAME_SCHEDULE_DRAFT_V1", "selection": "largest_gap_floor_midpoint_earliest_tie",
        "source_manifest_sha256": hashlib.sha256(FROZEN.read_bytes()).hexdigest(),
        "inference_calls": 0, "rgb_materialized": False,
        "blocked_cells": sum(r["status"].startswith("STOP_") for r in planned), "cells": planned}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"planned_cells": len(planned), "blocked_cells": result["blocked_cells"], "inference_calls": 0}))


if __name__ == "__main__":
    main()
