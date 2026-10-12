"""Phase-1 read-only data observability probe (no VLM, no Formal retrieval).

Runs the Frozen G1 segmentation + MVP-M2 evidence path over a deterministically
sampled Development-pool subset and records, for every segment:

- episode -> segment -> frame identity and inclusive range;
- MODEL_RGB[t] / PROPRIO[t] / ACTION[t] index alignment;
- clean-RGB provenance (direct renderer, no overlay, no audit MP4);
- repeated-render determinism (same index rendered twice must hash equal);
- forbidden-field and task-text-source audit.

Nothing is written into any Frozen artifact.  All output goes to a
development-only directory.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from project2_g1.boundary_engine import CANDIDATE_GRIPPER
from project2_g1.config import load_g1_p1_config
from project2_g1.paths import PROJECT2_ROOT
from project2_g1.signals import compute_formal_signals
from project2_g1.source import build_can_mh_adapter, load_formal_episode
from project2_g1.stage_b_calibration import run_window
from project2_g1.stage_c_regression import BOUNDARY_CONSOLIDATION_WINDOW
from project2_mvp.m2_materializer import assert_frozen_g1_identity
from project2_mvp.rgb_input import render_clean_rgb_frames

from .development_pool import build_probe_selection, write_json
from .evidence_pack import (
    ALLOWED_EVIDENCE_FIELDS,
    EVIDENCE_PACK_VERSION,
    EvidencePackError,
    audit_forbidden_field_names,
    build_evidence_pack,
)


PROBE_VERSION = "P2_G3_PHASE1_PROBE_V1"


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str] | None = None) -> None:
    columns = list(fields or ())
    if not columns:
        for row in rows:
            for key in row:
                if key not in columns:
                    columns.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            cooked = {
                key: json.dumps(value, separators=(",", ":")) if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            }
            writer.writerow(cooked)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_phase1_probe(
    output_root: str | Path,
    *,
    render: bool = True,
    run_id: str | None = None,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    """Execute the read-only probe and materialize immutable outputs."""

    root = Path(project_root or PROJECT2_ROOT).resolve()
    assert_frozen_g1_identity()
    if not audit_forbidden_field_names(ALLOWED_EVIDENCE_FIELDS)["passed"]:
        raise EvidencePackError("STOP_EVIDENCE_ALLOWLIST_INVALID")

    selection = build_probe_selection(root)
    selected = selection["selected"]

    run_id = run_id or "g3_phase1_probe_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    output = Path(output_root) / run_id
    if output.exists():
        raise FileExistsError(f"PROBE_OUTPUT_EXISTS: {output}")
    output.mkdir(parents=True)

    config = load_g1_p1_config()
    adapter = build_can_mh_adapter(config)

    episode_rows: list[dict[str, Any]] = []
    segment_rows: list[dict[str, Any]] = []
    pack_dir = output / "evidence_packs"

    try:
        for item in selected:
            episode_id = item["episode_id"]
            episode = load_formal_episode(adapter, episode_id)
            n = len(episode.eef_pos)
            signals = {episode_id: compute_formal_signals(episode, config)}
            results, _trace = run_window(signals, BOUNDARY_CONSOLIDATION_WINDOW)
            result = results[0]
            events = {event.boundary_id: event for event in result.final_events}

            # Pass 1: collect every unique keyframe index for this episode.
            segment_specs: list[tuple[Any, str | None, tuple[int, ...]]] = []
            unique_indices: set[int] = set()
            for segment in result.segments:
                left = events.get(segment.left_boundary_id)
                left_type = None if left is None else left.candidate_type
                from project2_mvp.m2 import select_keyframes

                kf = select_keyframes(segment, left_boundary_type=left_type)
                indices = tuple(sorted({int(k.frame_index) for k in kf}))
                unique_indices.update(indices)
                segment_specs.append((segment, left_type, indices))

            # Pass 2: render each unique frame exactly once, then re-render one
            # frame to prove repeated-render determinism.
            frame_cache: dict[int, Any] = {}
            render_error: str | None = None
            duplicate_hash_stable: bool | None = None
            if render and unique_indices:
                try:
                    first_pass = render_clean_rgb_frames(
                        adapter, episode_id, sorted(unique_indices)
                    )
                    frame_cache = {f.frame_index: f for f in first_pass}
                    probe_index = sorted(unique_indices)[0]
                    second_pass = render_clean_rgb_frames(adapter, episode_id, [probe_index])
                    duplicate_hash_stable = (
                        second_pass[0].provenance["pixel_sha256"]
                        == frame_cache[probe_index].provenance["pixel_sha256"]
                    )
                except Exception as exc:  # renderer stack may be unavailable
                    render_error = f"{type(exc).__name__}: {exc}"
                    frame_cache = {}

            packs: list[dict[str, Any]] = []
            gripper_event_segments = 0
            for segment, left_type, indices in segment_specs:
                if left_type == CANDIDATE_GRIPPER:
                    gripper_event_segments += 1
                pack = build_evidence_pack(
                    segment,
                    episode,
                    adapter,
                    left_boundary_type=left_type,
                    gripper_state=result.gripper_state,
                    render=render and not render_error,
                    frame_cache=frame_cache if frame_cache else None,
                )
                packs.append(pack.to_dict())
                segment_rows.append({
                    "episode_id": episode_id,
                    "segment_id": pack.segment_id,
                    "start_frame": pack.start_frame,
                    "end_frame": pack.end_frame,
                    "duration_frames": pack.duration_frames,
                    "left_boundary_type": left_type or "EPISODE_START",
                    "gripper_event_present": pack.provenance["gripper_event_present"],
                    "keyframe_indices": "|".join(str(i) for i in pack.keyframe_indices),
                    "keyframe_count": len(pack.keyframe_indices),
                    "multi_role_frames": sum(len(k.roles) > 1 for k in pack.keyframes),
                    "rgb_frame_count": len(pack.rgb_frames),
                    "rgb_index_match": pack.rgb_indices == pack.keyframe_indices,
                    "keyframes_in_segment": all(
                        pack.start_frame <= i <= pack.end_frame for i in pack.keyframe_indices
                    ),
                    "action_semantic": pack.motion_summary["action_semantic"],
                    "task_text_value": pack.task_text.value,
                    "task_text_recorded_instruction": pack.task_text.recorded_instruction,
                    "forbidden_audit_passed": pack.forbidden_field_audit["passed"],
                })

            write_json(pack_dir / f"{episode_id.replace('/', '__')}.json", {
                "evidence_pack_version": EVIDENCE_PACK_VERSION,
                "episode_id": episode_id,
                "frame_count": n,
                "segments": packs,
            })

            episode_rows.append({
                "episode_id": episode_id,
                "duration_stratum": item["duration_stratum"],
                "stratum_rank": item["stratum_rank"],
                "frame_count": n,
                "final_boundary_count": len(result.final_events),
                "boundary_types": "|".join(sorted({e.candidate_type for e in result.final_events})),
                "segment_count": len(result.segments),
                "gripper_event_segments": gripper_event_segments,
                "unique_keyframes_rendered": len(frame_cache),
                "render_error": render_error or "",
                "duplicate_render_hash_stable": duplicate_hash_stable,
                "propio_action_length_equal": len(episode.eef_pos) == len(episode.actions),
                "propio_gripper_length_equal": len(episode.eef_pos) == len(episode.gripper_qpos),
            })
    finally:
        close = getattr(adapter, "close", None)
        if callable(close):
            close()

    _write_csv(output / "probe_selection_manifest.csv", selected)
    _write_csv(output / "development_pool.csv", selection["pool_rows"])
    _write_csv(output / "episode_audit_summary.csv", episode_rows)
    _write_csv(output / "segment_audit_summary.csv", segment_rows)

    render_ok = [row for row in episode_rows if row["duplicate_render_hash_stable"] is True]
    summary = {
        "probe_version": PROBE_VERSION,
        "evidence_pack_version": EVIDENCE_PACK_VERSION,
        "vlm_invoked": False,
        "formal_retrieval_executed": False,
        "faiss_executed": False,
        "siglip2_executed": False,
        "development_pool": selection["summary"],
        "selection_salt": selection["selection_salt"],
        "selection_rule": selection["selection_rule"],
        "episodes_probed": len(episode_rows),
        "segments_probed": len(segment_rows),
        "stratum_counts": dict(Counter(row["duration_stratum"] for row in episode_rows)),
        "boundary_type_counts": dict(
            Counter(t for row in episode_rows for t in str(row["boundary_types"]).split("|") if t)
        ),
        "segments_with_gripper_event": sum(bool(r["gripper_event_present"]) for r in segment_rows),
        "segments_without_gripper_event": sum(not bool(r["gripper_event_present"]) for r in segment_rows),
        "rgb_index_match_all": all(bool(r["rgb_index_match"]) for r in segment_rows),
        "keyframes_in_segment_all": all(bool(r["keyframes_in_segment"]) for r in segment_rows),
        "forbidden_audit_passed_all": all(bool(r["forbidden_audit_passed"]) for r in segment_rows),
        "duplicate_render_stable_episodes": len(render_ok),
        "episodes_with_render_error": sum(bool(r["render_error"]) for r in episode_rows),
        "task_text_distinct": sorted({str(r["task_text_value"]) for r in segment_rows}),
        "task_text_recorded_instruction_any": any(
            bool(r["task_text_recorded_instruction"]) for r in segment_rows
        ),
        "action_semantic_values": sorted({str(r["action_semantic"]) for r in segment_rows}),
    }
    write_json(output / "phase1_probe_summary.json", summary)
    write_json(output / "run_meta.json", {
        "run_id": run_id,
        "created_at": datetime.now().astimezone().isoformat(),
        "probe_version": PROBE_VERSION,
        "boundary_consolidation_window": BOUNDARY_CONSOLIDATION_WINDOW,
        "frozen_g1_identity": "VALIDATED",
        "render_enabled": render,
        "output_scope": "DEVELOPMENT_ONLY_NOT_FORMAL",
    })
    return {"output_run": str(output.resolve()), **summary}


def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="P2-G3 Phase-1 read-only probe (no VLM)")
    parser.add_argument("--no-render", action="store_true", help="skip RGB rendering")
    parser.add_argument("--run-id")
    parser.add_argument("--output-root")
    args = parser.parse_args()
    root = Path(args.output_root) if args.output_root else PROJECT2_ROOT / "outputs" / "g3_phase1_probe"
    result = run_phase1_probe(root, render=not args.no_render, run_id=args.run_id)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
