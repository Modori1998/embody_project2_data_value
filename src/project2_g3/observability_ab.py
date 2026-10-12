"""Phase-1B A/B visual-observability material builder (no VLM).

For every Frozen G1 segment of the Phase-1 sample this produces:

* an **analyst** sheet showing panel A (target keyframes only) and panel B
  (target keyframes + neighbour-segment context), with every cell labelled by
  its origin segment and role, so it is unambiguous which evidence belongs to
  the target segment and which comes from a neighbour;
* two **blinded** panel images per segment (raw frames, no headers, no role
  labels) whose A/B assignment is randomised deterministically and recorded
  only in a sealed key file.

The human review sheet is emitted **unscored**: every observability column is
left ``UNSCORED``.  No heuristic is allowed to masquerade as ground truth.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from project2_g1.boundary_engine import CANDIDATE_GRIPPER
from project2_g1.config import load_g1_p1_config
from project2_g1.paths import PROJECT2_ROOT
from project2_g1.signals import compute_formal_signals
from project2_g1.source import build_can_mh_adapter, load_formal_episode
from project2_g1.stage_b_calibration import run_window
from project2_g1.stage_c_regression import BOUNDARY_CONSOLIDATION_WINDOW
from project2_mvp.m2_materializer import assert_frozen_g1_identity
from project2_mvp.rgb_input import CleanRGBFrame, render_clean_rgb_frames

from .context_window import (
    CONTEXT_POLICY_NAME,
    CONTEXT_WINDOW_VERSION,
    ROLE_NEXT_MIDDLE,
    ROLE_NEXT_START,
    ROLE_PREV_END,
    ROLE_TARGET_KEYFRAME,
    ContextWindow,
    build_context_window,
)
from .development_pool import build_probe_selection, write_json

AB_RUN_VERSION = "P2_G3_PHASE1B_AB_OBSERVABILITY_V1"
BLINDING_SALT = "P2_G3_PHASE1B_BLIND_20261012"

# Observability dimensions.  All are left for a human to fill in.
REVIEW_DIMENSIONS = (
    "object_visible",
    "motion_phase_decidable",
    "gripper_transition_visible",
    "object_following_decidable",
    "release_decidable",
)
REVIEW_LEVELS = ("SUFFICIENT", "PARTIAL", "INSUFFICIENT")
FAILURE_REASONS = ("NONE", "OCCLUSION", "OUT_OF_FRAME", "TEMPORAL_GAP", "OTHER")
UNSCORED = "UNSCORED"


def build_panel_cells(
    window: ContextWindow,
    segment: Any,
    left_boundary_type: str | None,
    frame_cache: Mapping[int, CleanRGBFrame],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Panel A = target keyframes only.  Panel B = A plus neighbour context.

    Kept as a pure function so the "panel A must not contain neighbour frames"
    property is directly testable.
    """

    from project2_mvp.m2 import select_keyframes

    keyframe_roles = {
        int(k.frame_index): tuple(str(r) for r in k.roles)
        for k in select_keyframes(segment, left_boundary_type=left_boundary_type)
    }

    cells_a: list[dict[str, Any]] = []
    for index in window.target_keyframe_indices:
        roles = keyframe_roles.get(index, ())
        name = "START" if index == window.target_start_frame else (
            "END" if index == window.target_end_frame else "MIDDLE"
        )
        extra = " +GRIPPER" if "GRIPPER_EVENT" in roles else ""
        cells_a.append({
            "rgb": frame_cache[index].rgb,
            "is_target_segment_frame": True,
            "label": f"{name} f{index}{extra}",
        })

    prev_cells: list[dict[str, Any]] = []
    next_cells: list[dict[str, Any]] = []
    for frame in window.context_frames:
        if frame.evidence_role == ROLE_PREV_END:
            label = f"<PREV END f{frame.frame_index}"
        elif frame.evidence_role == ROLE_NEXT_START:
            label = f"NEXT START f{frame.frame_index}>"
        elif frame.evidence_role == ROLE_NEXT_MIDDLE:
            label = f"NEXT MID f{frame.frame_index}>"
        else:  # pragma: no cover - guarded by validate_context_window
            continue
        cell = {
            "rgb": frame_cache[frame.frame_index].rgb,
            "is_target_segment_frame": False,
            "label": label,
        }
        (prev_cells if frame.evidence_role == ROLE_PREV_END else next_cells).append(cell)

    return cells_a, prev_cells + cells_a + next_cells


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: json.dumps(value, separators=(",", ":"))
                if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            })


def blinded_order(segment_id: str) -> tuple[str, str]:
    """Deterministic, reproducible, non-obvious A/B presentation order."""

    digest = hashlib.sha256(f"{BLINDING_SALT}|{segment_id}".encode("utf-8")).digest()
    return ("A", "B") if digest[0] % 2 == 0 else ("B", "A")


# ---------------------------------------------------------------------------
# Image composition
# ---------------------------------------------------------------------------

_CELL = 192          # displayed cell size (nearest-neighbour upscale of 128px)
_PAD = 10
_HEADER = 34         # title band
_FOOTER = 24         # per-cell role/frame-index label band (must not clip the text)
_ROW_LABEL_W = 150
_BG = (250, 250, 252)
_INK = (28, 28, 32)
_MUTED = (120, 120, 130)
_TARGET = (28, 120, 60)      # green: belongs to the target segment
_NEIGHBOR = (200, 110, 20)   # orange: borrowed from a neighbour segment


def _load_cell(rgb) -> Any:
    from PIL import Image

    image = Image.fromarray(rgb)
    if image.size != (_CELL, _CELL):
        image = image.resize((_CELL, _CELL), Image.NEAREST)
    return image


def _font(size: int):
    from PIL import ImageFont

    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _render_strip(
    cells: Sequence[dict[str, Any]],
    *,
    title: str,
    annotate: bool,
) -> Any:
    """One horizontal strip of frames. ``cells`` are pre-ordered dicts."""

    from PIL import Image, ImageDraw

    width = _ROW_LABEL_W + len(cells) * (_CELL + _PAD) + _PAD
    height = _HEADER + _CELL + 2 * _PAD + _FOOTER
    canvas = Image.new("RGB", (width, height), _BG)
    draw = ImageDraw.Draw(canvas)

    if annotate:
        draw.text((_PAD, 8), title, fill=_INK, font=_font(20))

    x = _ROW_LABEL_W
    for cell in cells:
        border = _TARGET if cell["is_target_segment_frame"] else _NEIGHBOR
        box = (x - 2, _HEADER + _PAD - 2, x + _CELL + 2, _HEADER + _PAD + _CELL + 2)
        draw.rectangle(box, outline=border, width=3)
        canvas.paste(_load_cell(cell["rgb"]), (x, _HEADER + _PAD))
        if annotate:
            label = cell["label"]
            colour = _TARGET if cell["is_target_segment_frame"] else _NEIGHBOR
            draw.text((x, _HEADER + _PAD + _CELL + 4), label, fill=colour, font=_font(14))
        x += _CELL + _PAD
    return canvas


def _compose_analyst_sheet(panels: Sequence[Any]) -> Any:
    from PIL import Image

    width = max(panel.width for panel in panels)
    height = sum(panel.height for panel in panels)
    canvas = Image.new("RGB", (width, height), _BG)
    y = 0
    for panel in panels:
        canvas.paste(panel, (0, y))
        y += panel.height
    return canvas


def _blinded_strip(cells: Sequence[dict[str, Any]]) -> Any:
    """Raw frames only: no title, no role labels, no frame indices."""

    from PIL import Image

    width = len(cells) * (_CELL + _PAD) + _PAD
    height = _CELL + 2 * _PAD
    canvas = Image.new("RGB", (width, height), _BG)
    x = _PAD
    for cell in cells:
        canvas.paste(_load_cell(cell["rgb"]), (x, _PAD))
        x += _CELL + _PAD
    return canvas


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def build_ab_assets(
    output_root: str | Path,
    *,
    render: bool = True,
    run_id: str | None = None,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(project_root or PROJECT2_ROOT).resolve()
    assert_frozen_g1_identity()

    selection = build_probe_selection(root)
    selected = selection["selected"]

    run_id = run_id or "g3_phase1b_ab_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    output = Path(output_root) / run_id
    if output.exists():
        raise FileExistsError(f"AB_OUTPUT_EXISTS: {output}")
    (output / "_visual" / "analyst").mkdir(parents=True)
    (output / "_visual" / "blinded").mkdir(parents=True)

    config = load_g1_p1_config()
    adapter = build_can_mh_adapter(config)

    window_rows: list[dict[str, Any]] = []
    frame_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    blind_rows: list[dict[str, Any]] = []
    episode_rows: list[dict[str, Any]] = []
    render_errors: list[str] = []

    try:
        for item in selected:
            episode_id = item["episode_id"]
            episode = load_formal_episode(adapter, episode_id)
            n = len(episode.eef_pos)
            signals = {episode_id: compute_formal_signals(episode, config)}
            results, _trace = run_window(signals, BOUNDARY_CONSOLIDATION_WINDOW)
            result = results[0]
            events = {event.boundary_id: event for event in result.final_events}
            segments = list(result.segments)

            left_types: list[str | None] = []
            for segment in segments:
                left = events.get(segment.left_boundary_id)
                left_types.append(None if left is None else left.candidate_type)

            # Every unique frame this episode needs, rendered exactly once.
            needed: set[int] = set()
            for index, segment in enumerate(segments):
                left_type = left_types[index]
                from project2_mvp.m2 import select_keyframes

                for keyframe in select_keyframes(segment, left_boundary_type=left_type):
                    needed.add(int(keyframe.frame_index))
                previous = segments[index - 1] if index > 0 else None
                following = segments[index + 1] if index + 1 < len(segments) else None
                if previous is not None:
                    needed.add(int(previous.end_frame))
                if following is not None:
                    needed.add(int(following.start_frame))
                    if (int(following.end_frame) - int(following.start_frame) + 1) >= 4:
                        needed.add((int(following.start_frame) + int(following.end_frame)) // 2)

            frame_cache: dict[int, CleanRGBFrame] = {}
            render_error: str | None = None
            if render and needed:
                try:
                    rendered = render_clean_rgb_frames(adapter, episode_id, sorted(needed))
                    frame_cache = {frame.frame_index: frame for frame in rendered}
                except Exception as exc:  # renderer stack unavailable
                    render_error = f"{type(exc).__name__}: {exc}"
                    render_errors.append(f"{episode_id}: {render_error}")

            windows: list[ContextWindow] = []
            for index, segment in enumerate(segments):
                window = build_context_window(
                    segments,
                    index,
                    episode,
                    adapter,
                    left_boundary_type=left_types[index],
                    render=render and not render_error,
                    frame_cache=frame_cache if frame_cache else None,
                )
                windows.append(window)

                # --- frame-level manifest (all eight required fields) ---
                for role_index, frame in enumerate(window.context_frames):
                    frame_rows.append({
                        "episode_id": episode_id,
                        "target_segment_id": window.target_segment_id,
                        "source_episode_id": frame.source_episode_id,
                        "frame_index": frame.frame_index,
                        "pixel_sha256": frame.pixel_sha256,
                        "origin_segment_id": frame.origin_segment_id,
                        "evidence_role": frame.evidence_role,
                        "is_target_segment_frame": frame.is_target_segment_frame,
                        "renderer_contract_version": frame.renderer_provenance.get("contract_version"),
                        "overlay_applied": frame.renderer_provenance.get("overlay_applied"),
                        "audit_mp4_used": frame.renderer_provenance.get("audit_mp4_used"),
                        "lossy_video_roundtrip": frame.renderer_provenance.get("lossy_video_roundtrip"),
                        "role_order": role_index,
                    })

                window_rows.append({
                    "episode_id": episode_id,
                    "segment_id": window.target_segment_id,
                    "start_frame": window.target_start_frame,
                    "end_frame": window.target_end_frame,
                    "target_keyframe_count": len(window.target_keyframe_indices),
                    "target_keyframe_indices": list(window.target_keyframe_indices),
                    "context_frame_count": len(window.context_frames),
                    "context_frame_indices": list(window.context_indices),
                    "prev_status": window.neighbor_status["PREV"],
                    "next_status": window.neighbor_status["NEXT"],
                    "prev_segment_id": window.provenance["prev_segment_id"],
                    "next_segment_id": window.provenance["next_segment_id"],
                    "budget_used_total": window.budget_audit["used_total"],
                    "budget_within_limit": window.budget_audit["within_budget"],
                    "context_policy": CONTEXT_POLICY_NAME,
                })

                # --- A/B panels ---
                # Panel A: the target segment's own keyframes (the Phase-1 view).
                # Panel B: the same frames plus neighbour-segment context.
                cells_a, ordered_b = build_panel_cells(
                    window, segment, left_types[index], frame_cache
                )

                slug = window.target_segment_id.replace("/", "__")
                if frame_cache:
                    panel_a = _render_strip(
                        cells_a,
                        title=f"A  |  {window.target_segment_id} "
                              f"[{window.target_start_frame}-{window.target_end_frame}]  "
                              f"target keyframes only",
                        annotate=True,
                    )
                    panel_b = _render_strip(
                        ordered_b,
                        title=f"B  |  {window.target_segment_id} "
                              f"[{window.target_start_frame}-{window.target_end_frame}]  "
                              f"+ neighbour context (orange = neighbour segment)",
                        annotate=True,
                    )
                    _compose_analyst_sheet([panel_a, panel_b]).save(
                        output / "_visual" / "analyst" / f"{slug}_AB.png"
                    )

                    order = blinded_order(window.target_segment_id)
                    strips = {"A": cells_a, "B": ordered_b}
                    for panel_number, which in enumerate(order, start=1):
                        _blinded_strip(strips[which]).save(
                            output / "_visual" / "blinded"
                            / f"{slug}__panel{panel_number}.png"
                        )
                    blind_rows.append({
                        "segment_id": window.target_segment_id,
                        "episode_id": episode_id,
                        "panel1_is": order[0],
                        "panel2_is": order[1],
                    })

                # --- unscored human review sheet ---
                review: dict[str, Any] = {
                    "episode_id": episode_id,
                    "segment_id": window.target_segment_id,
                    "start_frame": window.target_start_frame,
                    "end_frame": window.target_end_frame,
                    "duration_frames": int(segment.duration_frames),
                    "prev_status": window.neighbor_status["PREV"],
                    "next_status": window.neighbor_status["NEXT"],
                    "analyst_sheet": f"_visual/analyst/{slug}_AB.png",
                    "blinded_panel1": f"_visual/blinded/{slug}__panel1.png",
                    "blinded_panel2": f"_visual/blinded/{slug}__panel2.png",
                }
                for panel in ("A", "B"):
                    for dimension in REVIEW_DIMENSIONS:
                        review[f"{panel}_{dimension}"] = UNSCORED
                    review[f"{panel}_failure_reason"] = UNSCORED
                    review[f"{panel}_notes"] = ""
                review["reviewer_id"] = ""
                review["reviewed_at"] = ""
                review_rows.append(review)

            episode_rows.append({
                "episode_id": episode_id,
                "frame_count": n,
                "segment_count": len(segments),
                "context_frames_total": sum(len(w.context_frames) for w in windows),
                "segments_missing_prev": sum(
                    w.neighbor_status["PREV"] == "MISSING_NEIGHBOR" for w in windows
                ),
                "segments_missing_next": sum(
                    w.neighbor_status["NEXT"] == "MISSING_NEIGHBOR" for w in windows
                ),
                "budget_within_limit_all": all(
                    bool(w.budget_audit["within_budget"]) for w in windows
                ),
                "render_error": render_error or "",
                "unique_frames_rendered": len(frame_cache),
            })
    finally:
        close = getattr(adapter, "close", None)
        if callable(close):
            close()

    review_fields = [
        "episode_id", "segment_id", "start_frame", "end_frame", "duration_frames",
        "prev_status", "next_status", "analyst_sheet", "blinded_panel1", "blinded_panel2",
    ]
    for panel in ("A", "B"):
        review_fields.extend(f"{panel}_{d}" for d in REVIEW_DIMENSIONS)
        review_fields.extend([f"{panel}_failure_reason", f"{panel}_notes"])
    review_fields.extend(["reviewer_id", "reviewed_at"])

    _write_csv(output / "context_window_manifest.csv", window_rows, [
        "episode_id", "segment_id", "start_frame", "end_frame",
        "target_keyframe_count", "target_keyframe_indices",
        "context_frame_count", "context_frame_indices",
        "prev_status", "next_status", "prev_segment_id", "next_segment_id",
        "budget_used_total", "budget_within_limit", "context_policy",
    ])
    _write_csv(output / "evidence_frame_manifest.csv", frame_rows, [
        "episode_id", "target_segment_id", "source_episode_id", "frame_index",
        "pixel_sha256", "origin_segment_id", "evidence_role",
        "is_target_segment_frame", "renderer_contract_version",
        "overlay_applied", "audit_mp4_used", "lossy_video_roundtrip", "role_order",
    ])
    _write_csv(output / "ab_review_sheet_UNSCORED.csv", review_rows, review_fields)
    _write_csv(output / "ab_blinding_key_SEALED.csv", blind_rows, [
        "segment_id", "episode_id", "panel1_is", "panel2_is",
    ])
    _write_csv(output / "episode_context_summary.csv", episode_rows, [
        "episode_id", "frame_count", "segment_count", "context_frames_total",
        "segments_missing_prev", "segments_missing_next",
        "budget_within_limit_all", "render_error", "unique_frames_rendered",
    ])

    summary = {
        "ab_run_version": AB_RUN_VERSION,
        "context_window_version": CONTEXT_WINDOW_VERSION,
        "context_policy": CONTEXT_POLICY_NAME,
        "vlm_invoked": False,
        "frozen_g1_boundaries_modified": False,
        "episodes": len(episode_rows),
        "segments": len(window_rows),
        "context_frames_total": len(frame_rows),
        "target_keyframes_total": sum(
            int(row["target_keyframe_count"]) for row in window_rows
        ),
        "segments_missing_prev": sum(
            row["prev_status"] == "MISSING_NEIGHBOR" for row in window_rows
        ),
        "segments_missing_next": sum(
            row["next_status"] == "MISSING_NEIGHBOR" for row in window_rows
        ),
        "segments_with_both_neighbors": sum(
            row["prev_status"] == "PRESENT" and row["next_status"] == "PRESENT"
            for row in window_rows
        ),
        "context_frame_role_counts": _role_counts(frame_rows),
        "budget_within_limit_all": all(
            bool(row["budget_within_limit"]) for row in window_rows
        ),
        "cross_episode_frames": sum(
            row["source_episode_id"] != row["episode_id"] for row in frame_rows
        ),
        "neighbor_frames_flagged_as_target": sum(
            bool(row["is_target_segment_frame"]) and row["evidence_role"] != ROLE_TARGET_KEYFRAME
            for row in frame_rows
        ),
        "target_frames_flagged_as_neighbor": sum(
            (not bool(row["is_target_segment_frame"])) and row["evidence_role"] == ROLE_TARGET_KEYFRAME
            for row in frame_rows
        ),
        "clean_rgb_contract_violations": sum(
            row["overlay_applied"] is not False
            or row["audit_mp4_used"] is not False
            or row["lossy_video_roundtrip"] is not False
            for row in frame_rows
        ),
        "episodes_with_render_error": len(render_errors),
        "review_sheet_scored_columns": 0,
        "review_sheet_status": "UNSCORED_PENDING_HUMAN",
        "blinding": "deterministic per-segment A/B order, key sealed separately",
    }
    write_json(output / "phase1b_ab_summary.json", summary)
    write_json(output / "run_meta.json", {
        "run_id": run_id,
        "created_at": datetime.now().astimezone().isoformat(),
        "ab_run_version": AB_RUN_VERSION,
        "boundary_consolidation_window": BOUNDARY_CONSOLIDATION_WINDOW,
        "frozen_g1_identity": "VALIDATED",
        "render_enabled": render,
        "output_scope": "DEVELOPMENT_ONLY_NOT_FORMAL",
    })
    return {"output_run": str(output.resolve()), **summary}


def _role_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row["evidence_role"])
        counts[key] = counts.get(key, 0) + 1
    return counts


def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="P2-G3 Phase-1B A/B observability builder")
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--output-root")
    args = parser.parse_args()
    root = Path(args.output_root) if args.output_root else PROJECT2_ROOT / "outputs" / "g3_phase1b_ab"
    result = build_ab_assets(root, render=not args.no_render, run_id=args.run_id)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
