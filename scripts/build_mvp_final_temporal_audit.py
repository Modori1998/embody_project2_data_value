"""Generate full-segment temporal GIFs for the frozen Final blind Human Audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for path in (SRC, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from build_mvp_calibration_audit_ui import build_page
from build_mvp_calibration_temporal_audit import sampled_indices
from project2_g1.config import load_g1_p1_config
from project2_g1.source import build_can_mh_adapter
from project2_mvp.rgb_input import MODEL_RGB_CONTRACT_VERSION, render_clean_rgb_frames

DEFAULT_STAGE1_RUN = ROOT / "outputs/mvp_core_retrieval_formal/mvp_core_retrieval_formal_stage1_20261009"
RUBRIC = ROOT / "0-doc/10-design-review/Project2_MVP_Human_Relevance_Rubric_Clarification_FROZEN_v1_20261012.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_final_temporal_package(
    stage1: Path,
    stage2: Path,
    output: Path,
    *,
    target_fps: float = 10.0,
) -> dict:
    if not stage1.is_dir() or not stage2.is_dir():
        raise FileNotFoundError("Stage1 or Stage2 Formal run is missing")

    rubric = RUBRIC.read_text(encoding="utf-8")
    if not all(
        token in rubric
        for token in (
            "DOCUMENT_STATUS = FROZEN_v1",
            "FINAL_HUMAN_AUDIT_RUBRIC =",
            "LOCKED_TO_FROZEN_v1",
        )
    ):
        raise RuntimeError("STOP_FINAL_RUBRIC_NOT_FROZEN")

    audit_rows = read_csv(stage2 / "final_human_audit_pairs.csv")
    segment_rows = read_csv(stage1 / "m2/segment_input_manifest.csv")
    unique_pairs = {
        (row["query_segment_id"], row["candidate_segment_id"]) for row in audit_rows
    }
    pair_counts = Counter(
        (row["query_segment_id"], row["candidate_segment_id"]) for row in audit_rows
    )
    hidden_repeats = sum(count == 2 for count in pair_counts.values())
    if hidden_repeats != 12 or len(audit_rows) != len(unique_pairs) + 12:
        raise RuntimeError("STOP_FINAL_BLIND_AUDIT_REPEAT_IDENTITY_MISMATCH")

    required_ids = {segment_id for pair in unique_pairs for segment_id in pair}
    segment_by_id = {row["segment_id"]: row for row in segment_rows}
    missing = sorted(required_ids - set(segment_by_id))
    if missing:
        raise RuntimeError(f"STOP_FINAL_AUDIT_SEGMENT_MISSING: {missing}")

    protected = ("final_motion_top5.csv", "final_visual_top5.csv", "final_human_audit_pairs.csv")
    protected_before = {name: sha256_file(stage2 / name) for name in protected}

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
            int(row["start_frame"]),
            int(row["end_frame"]),
            source_fps,
            target_fps,
        )
        indices_by_segment[segment_id] = indices
        needed_by_episode[row["source_episode_id"]].update(indices)

    adapter = build_can_mh_adapter(load_g1_p1_config())
    rendered = {}
    try:
        for episode_id in sorted(needed_by_episode):
            frames = render_clean_rgb_frames(
                adapter, episode_id, sorted(needed_by_episode[episode_id])
            )
            rendered.update(
                {(episode_id, frame.frame_index): frame.rgb for frame in frames}
            )
    finally:
        close = getattr(adapter, "close", None)
        if callable(close):
            close()

    gif_paths: dict[str, str] = {}
    gif_manifest = []
    frame_duration_ms = int(round(1000.0 / target_fps))
    total_sampled_frames = 0
    for segment_id in sorted(required_ids):
        row = segment_by_id[segment_id]
        episode_id = row["source_episode_id"]
        indices = indices_by_segment[segment_id]
        images = [
            Image.fromarray(rendered[(episode_id, index)], mode="RGB")
            for index in indices
        ]
        relative = (
            Path("segment_gifs")
            / episode_id.split("/")[-1]
            / f"{segment_id}.gif"
        )
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
                raise RuntimeError(f"Final Segment GIF validation failed: {segment_id}")
        total_sampled_frames += len(indices)
        gif_paths[segment_id] = relative.as_posix()
        gif_manifest.append(
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
                "gif_sha256": sha256_file(target),
                "rgb_contract_version": MODEL_RGB_CONTRACT_VERSION,
                "overlay_applied": False,
                "retrieval_input": False,
            }
        )

    guidance = (
        "按完整局部行为判断，而不是只看绝对位置。优先看 interaction phase（交互阶段）、"
        "gripper interaction（夹爪交互状态）和 temporal motion（时序运动）。"
        "低位移本身不是 UNSURE。RELEVANT=同一局部行为；PARTIAL=部分状态相似但关键行为不同；"
        "NOT_RELEVANT=明显不同；UNSURE=看完整 GIF 后仍无法稳定判断；"
        "BAD_SEGMENT=切段本身导致无法可靠比较。"
    )
    build_page(
        stage1,
        output,
        segment_gifs=gif_paths,
        allow_existing_output=True,
        audit_rows=audit_rows,
        page_title="Final Blind Human Audit",
        storage_key_suffix=stage2.name,
        export_filename="final_human_audit_pairs_filled.csv",
        review_guidance=guidance,
    )

    protected_after = {name: sha256_file(stage2 / name) for name in protected}
    if protected_before != protected_after:
        raise RuntimeError("STOP_FINAL_RETRIEVAL_ARTIFACT_MUTATED")

    (output / "segment_gif_manifest.json").write_text(
        json.dumps(gif_manifest, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "final_temporal_audit_evidence": "PASS",
        "final_audit_items": len(audit_rows),
        "unique_pairs": len(unique_pairs),
        "hidden_repeats": hidden_repeats,
        "unique_segments_with_gif": len(required_ids),
        "source_episode_count": len(needed_by_episode),
        "total_sampled_frames": total_sampled_frames,
        "target_fps": target_fps,
        "rubric_sha256": sha256_file(RUBRIC),
        "retrieval_rerun": False,
        "gif_evidence_is_retrieval_input": False,
        "human_labels_started": False,
        "p5_computed": False,
    }
    (output / "final_temporal_evidence_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage1-run", type=Path, default=DEFAULT_STAGE1_RUN)
    parser.add_argument("--stage2-run", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target-fps", type=float, default=10.0)
    args = parser.parse_args(argv)

    output = ROOT / "outputs/mvp_core_retrieval_human_audit" / args.run_id
    result = build_final_temporal_package(
        args.stage1_run.resolve(),
        args.stage2_run.resolve(),
        output,
        target_fps=args.target_fps,
    )
    print(json.dumps({"output": str(output.resolve()), **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
