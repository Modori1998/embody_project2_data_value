"""Generate clean-RGB Segment GIFs and an interactive Calibration audit page."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for path in (SRC, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from build_mvp_calibration_audit_ui import build_page
from project2_g1.config import load_g1_p1_config
from project2_g1.source import build_can_mh_adapter
from project2_mvp.rgb_input import MODEL_RGB_CONTRACT_VERSION, render_clean_rgb_frames


DEFAULT_FORMAL_RUN = ROOT / "outputs/mvp_core_retrieval_formal/mvp_core_retrieval_formal_stage1_20261009"
PROTECTED_RETRIEVAL_FILES = (
    "calibration_motion_top5.csv",
    "calibration_visual_top5.csv",
    "calibration_query_manifest.csv",
    "final_query_manifest.csv",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sampled_indices(start: int, end: int, source_fps: float, target_fps: float) -> list[int]:
    if start > end or source_fps <= 0 or target_fps <= 0:
        raise ValueError("invalid segment timing for temporal audit evidence")
    stride = max(1, round(source_fps / target_fps))
    indices = list(range(start, end + 1, stride))
    if indices[-1] != end:
        indices.append(end)
    return indices


def build_temporal_package(formal_run: Path, output: Path, *, target_fps: float = 10.0) -> dict:
    audit_rows = read_csv(formal_run / "calibration_human_audit_pairs.csv")
    segment_rows = read_csv(formal_run / "m2/segment_input_manifest.csv")
    if len(audit_rows) != 95:
        raise ValueError(f"Calibration audit item count changed: {len(audit_rows)}")
    original_order = [row["audit_item_id"] for row in audit_rows]
    unique_pairs = {(row["query_segment_id"], row["candidate_segment_id"]) for row in audit_rows}
    repeated_groups = sum(
        count == 2
        for count in __import__("collections").Counter(
            (row["query_segment_id"], row["candidate_segment_id"]) for row in audit_rows
        ).values()
    )
    if len(unique_pairs) != 83 or repeated_groups != 12:
        raise ValueError("Frozen blind audit pair/repeat counts changed")
    required_ids = {value for pair in unique_pairs for value in pair}
    segment_by_id = {row["segment_id"]: row for row in segment_rows}
    missing = sorted(required_ids - set(segment_by_id))
    if missing:
        raise ValueError(f"Audit segments missing from Formal M2 manifest: {missing}")

    protected_before = {name: sha256(formal_run / name) for name in PROTECTED_RETRIEVAL_FILES}
    output.mkdir(parents=True, exist_ok=False)
    gif_root = output / "segment_gifs"
    gif_root.mkdir()
    needed_by_episode: dict[str, set[int]] = defaultdict(set)
    indices_by_segment: dict[str, list[int]] = {}
    for segment_id in sorted(required_ids):
        row = segment_by_id[segment_id]
        duration_frames = int(row["duration_frames"])
        duration_sec = float(row["duration_sec"])
        source_fps = duration_frames / duration_sec
        indices = sampled_indices(
            int(row["start_frame"]), int(row["end_frame"]), source_fps, target_fps
        )
        indices_by_segment[segment_id] = indices
        needed_by_episode[row["source_episode_id"]].update(indices)

    adapter = build_can_mh_adapter(load_g1_p1_config())
    rendered = {}
    try:
        for episode_id in sorted(needed_by_episode):
            frames = render_clean_rgb_frames(adapter, episode_id, sorted(needed_by_episode[episode_id]))
            rendered.update({(episode_id, frame.frame_index): frame.rgb for frame in frames})
    finally:
        close = getattr(adapter, "close", None)
        if callable(close):
            close()

    gif_paths: dict[str, str] = {}
    manifest = []
    frame_duration_ms = int(round(1000.0 / target_fps))
    for segment_id in sorted(required_ids):
        row = segment_by_id[segment_id]
        episode_id = row["source_episode_id"]
        indices = indices_by_segment[segment_id]
        images = [Image.fromarray(rendered[(episode_id, index)], mode="RGB") for index in indices]
        relative = Path("segment_gifs") / episode_id.split("/")[-1] / f"{segment_id}.gif"
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        images[0].save(
            target,
            format="GIF",
            save_all=True,
            append_images=images[1:],
            duration=frame_duration_ms,
            loop=0,
            optimize=False,
            disposal=2,
        )
        with Image.open(target) as check:
            decoded_frames = int(getattr(check, "n_frames", 1))
            if check.format != "GIF" or decoded_frames != len(indices):
                raise RuntimeError(f"Segment GIF validation failed: {segment_id}")
        gif_paths[segment_id] = relative.as_posix()
        manifest.append(
            {
                "segment_id": segment_id,
                "source_episode_id": episode_id,
                "start_frame": int(row["start_frame"]),
                "end_frame": int(row["end_frame"]),
                "sampled_frame_count": len(indices),
                "sampled_frame_indices": indices,
                "target_fps": target_fps,
                "frame_duration_ms": frame_duration_ms,
                "gif_relpath": relative.as_posix(),
                "gif_sha256": sha256(target),
                "rgb_contract_version": MODEL_RGB_CONTRACT_VERSION,
                "overlay_applied": False,
                "retrieval_input": False,
            }
        )

    build_page(
        formal_run,
        output,
        segment_gifs=gif_paths,
        allow_existing_output=True,
    )
    order_after = [item["row"]["audit_item_id"] for item in json.loads(
        (output / "index.html").read_text(encoding="utf-8").split("const items=", 1)[1].split(";\nconst labels=", 1)[0]
    )]
    protected_after = {name: sha256(formal_run / name) for name in PROTECTED_RETRIEVAL_FILES}
    if original_order != order_after or protected_before != protected_after:
        raise RuntimeError("Audit order or Retrieval artifacts changed")
    (output / "segment_gif_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "temporal_audit_evidence": "PASS",
        "calibration_audit_items": 95,
        "unique_pairs": 83,
        "hidden_repeats": 12,
        "unique_segments_with_gif": len(required_ids),
        "query_gifs": len({row["query_segment_id"] for row in audit_rows}),
        "candidate_gifs": len({row["candidate_segment_id"] for row in audit_rows}),
        "audit_order_unchanged": True,
        "retrieval_rerun": False,
        "human_labels_started": False,
        "protected_retrieval_sha256": protected_after,
    }
    (output / "temporal_evidence_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def existing_segment_gif_paths(output: Path) -> dict[str, str]:
    manifest_path = output / "segment_gif_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Temporal GIF manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    gif_paths: dict[str, str] = {}
    for row in manifest:
        segment_id = str(row["segment_id"])
        relative = str(row["gif_relpath"])
        target = output / relative
        if not target.is_file() or target.stat().st_size <= 0:
            raise FileNotFoundError(f"Temporal GIF is missing: {target}")
        gif_paths[segment_id] = relative
    if not gif_paths:
        raise ValueError("Temporal GIF manifest is empty")
    return gif_paths


def refresh_temporal_audit_ui(formal_run: Path, output: Path) -> dict:
    if not output.is_dir():
        raise FileNotFoundError(f"Temporal audit output is missing: {output}")
    gif_paths = existing_segment_gif_paths(output)
    result = build_page(
        formal_run,
        output,
        segment_gifs=gif_paths,
        allow_existing_output=True,
    )
    return {
        "refresh_ui_only": True,
        "segment_gifs_reused": len(gif_paths),
        **result,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--formal-run", type=Path, default=DEFAULT_FORMAL_RUN)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target-fps", type=float, default=10.0)
    parser.add_argument(
        "--refresh-ui-only",
        action="store_true",
        help="Reuse existing Segment GIFs and rebuild only index.html/ui_meta.json.",
    )
    args = parser.parse_args(argv)
    output = ROOT / "outputs/mvp_core_retrieval_human_audit" / args.run_id
    if args.refresh_ui_only:
        result = refresh_temporal_audit_ui(args.formal_run.resolve(), output)
    else:
        result = build_temporal_package(args.formal_run.resolve(), output, target_fps=args.target_fps)
    print(json.dumps({"output": str(output.resolve()), **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
