"""G3 Phase-1B Context Window: neighbour-segment visual context (no VLM).

Motivation
----------
The Phase-1 EvidencePack contains only frames that lie *inside* the target
Frozen G1 segment.  A single physical behaviour can straddle a frozen boundary
(e.g. "grasp then lift" split into a grasp segment and a transport segment), so
the three in-segment keyframes may not show whether the object was actually
picked up or released.

This module adds a **separate** structure, ``context_frames``, that carries a
small, fixed, deterministic budget of frames drawn from the immediately
preceding and following segments of the same episode.

Hard constraints enforced here
------------------------------
1. The target segment's own keyframes are unchanged and must remain inside
   ``[start_frame, end_frame]`` (the original in-segment assertion is preserved).
2. Neighbour frames are *never* presented as target-segment frames:
   ``is_target_segment_frame`` is derived from the frozen range, not from the
   caller.
3. A neighbour frame must belong to a genuinely adjacent segment, in the correct
   direction, within the same episode.  No episode boundary is ever crossed.
4. Missing neighbours are recorded explicitly as ``MISSING_NEIGHBOR``.
5. The neighbour budget is fixed and enforced.
6. No privileged field may appear anywhere in the emitted surface.
7. Every frame (target or neighbour) still satisfies the Clean RGB contract.

Nothing here writes to any Frozen artifact, and no model is invoked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from project2_mvp.m2 import select_keyframes
from project2_mvp.rgb_input import (
    MODEL_RGB_CONTRACT_VERSION,
    CleanRGBFrame,
    render_clean_rgb_frames,
)

from project2_mvp.m2 import FORBIDDEN_INPUT_TOKENS

from .evidence_pack import EvidencePackError

CONTEXT_WINDOW_VERSION = "P2_G3_CONTEXT_WINDOW_V1"

CONTEXT_POLICY_NAME = "PREV_END__TARGET_KEYFRAMES__NEXT_START_AND_MIDDLE"

# Fixed, deterministic budget.  Deliberately simple: no adaptive optimisation.
MAX_PREV_CONTEXT_FRAMES = 1
MAX_NEXT_CONTEXT_FRAMES = 2
MAX_CONTEXT_FRAMES_TOTAL = MAX_PREV_CONTEXT_FRAMES + MAX_NEXT_CONTEXT_FRAMES
# A next-segment MIDDLE frame is only added when the segment is long enough for
# START and MIDDLE to be distinct instants.
MIN_NEXT_FRAMES_FOR_MIDDLE = 4

ROLE_TARGET_KEYFRAME = "TARGET_KEYFRAME"
ROLE_PREV_END = "PREV_SEGMENT_END"
ROLE_NEXT_START = "NEXT_SEGMENT_START"
ROLE_NEXT_MIDDLE = "NEXT_SEGMENT_MIDDLE"

CONTEXT_ROLES = (ROLE_PREV_END, ROLE_NEXT_START, ROLE_NEXT_MIDDLE)

NEIGHBOR_PRESENT = "PRESENT"
NEIGHBOR_MISSING = "MISSING_NEIGHBOR"

# Field names this structure is allowed to expose to a future labeler.
ALLOWED_CONTEXT_FIELDS = frozenset({
    "context_frames",
    "context_frame_roles",
    "segment_identity",
    "neighbor_status",
    "context_budget",
    "target_keyframes",
})


class ContextWindowError(EvidencePackError):
    """Fail-closed error for the context-window contract."""


# ---------------------------------------------------------------------------
# Planning (pure, no rendering, no episode access)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContextFramePlan:
    """One planned context frame, before rendering."""

    frame_index: int
    evidence_role: str
    origin_segment_id: str | None
    is_target_segment_frame: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "evidence_role": self.evidence_role,
            "origin_segment_id": self.origin_segment_id,
            "is_target_segment_frame": self.is_target_segment_frame,
        }


def _get(segment: Any, key: str) -> Any:
    return getattr(segment, key) if not isinstance(segment, Mapping) else segment[key]


def plan_context_frames(
    target: Any,
    previous: Any | None,
    following: Any | None,
) -> tuple[list[ContextFramePlan], dict[str, str]]:
    """Plan the context frames for ``target``.

    Returns ``(plans, neighbor_status)``.  ``plans`` lists neighbour frames only
    (target keyframes are planned separately so the original in-segment
    assertion stays untouched).  Order is deterministic: PREV, then NEXT.
    """

    plans: list[ContextFramePlan] = []
    status: dict[str, str] = {}

    # --- previous segment: its END frame, i.e. the instant just before target
    if previous is None:
        status["PREV"] = NEIGHBOR_MISSING
    else:
        prev_end = int(_get(previous, "end_frame"))
        plans.append(
            ContextFramePlan(
                frame_index=prev_end,
                evidence_role=ROLE_PREV_END,
                origin_segment_id=str(_get(previous, "segment_id")),
                is_target_segment_frame=False,
            )
        )
        status["PREV"] = NEIGHBOR_PRESENT

    # --- next segment: its START frame, plus MIDDLE when the segment is long
    if following is None:
        status["NEXT"] = NEIGHBOR_MISSING
    else:
        next_id = str(_get(following, "segment_id"))
        next_start = int(_get(following, "start_frame"))
        next_end = int(_get(following, "end_frame"))
        plans.append(
            ContextFramePlan(
                frame_index=next_start,
                evidence_role=ROLE_NEXT_START,
                origin_segment_id=next_id,
                is_target_segment_frame=False,
            )
        )
        next_middle = (next_start + next_end) // 2
        if (
            (next_end - next_start + 1) >= MIN_NEXT_FRAMES_FOR_MIDDLE
            and next_middle != next_start
        ):
            plans.append(
                ContextFramePlan(
                    frame_index=next_middle,
                    evidence_role=ROLE_NEXT_MIDDLE,
                    origin_segment_id=next_id,
                    is_target_segment_frame=False,
                )
            )
        status["NEXT"] = NEIGHBOR_PRESENT

    return plans, status


def plan_target_keyframes(target: Any, left_boundary_type: str | None) -> list[ContextFramePlan]:
    """The target segment's own M2 keyframes, re-used verbatim (not recomputed)."""

    segment_id = str(_get(target, "segment_id"))
    keyframes = select_keyframes(target, left_boundary_type=left_boundary_type)
    seen: set[int] = set()
    plans: list[ContextFramePlan] = []
    for item in sorted(keyframes, key=lambda k: int(k.frame_index)):
        index = int(item.frame_index)
        if index in seen:
            continue
        seen.add(index)
        plans.append(
            ContextFramePlan(
                frame_index=index,
                evidence_role=ROLE_TARGET_KEYFRAME,
                origin_segment_id=segment_id,
                is_target_segment_frame=True,
            )
        )
    return plans


# ---------------------------------------------------------------------------
# Materialised window
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContextFrame:
    source_episode_id: str
    frame_index: int
    pixel_sha256: str | None
    target_segment_id: str
    origin_segment_id: str | None
    evidence_role: str
    is_target_segment_frame: bool
    renderer_provenance: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_episode_id": self.source_episode_id,
            "frame_index": self.frame_index,
            "pixel_sha256": self.pixel_sha256,
            "target_segment_id": self.target_segment_id,
            "origin_segment_id": self.origin_segment_id,
            "evidence_role": self.evidence_role,
            "is_target_segment_frame": self.is_target_segment_frame,
            "renderer_provenance": dict(self.renderer_provenance),
        }


@dataclass(frozen=True)
class ContextWindow:
    context_window_version: str
    episode_id: str
    target_segment_id: str
    target_start_frame: int
    target_end_frame: int
    target_keyframe_indices: tuple[int, ...]
    context_frames: tuple[ContextFrame, ...]
    neighbor_status: Mapping[str, str]
    budget_audit: Mapping[str, Any]
    provenance: Mapping[str, Any] = field(default_factory=dict)

    @property
    def context_indices(self) -> tuple[int, ...]:
        return tuple(frame.frame_index for frame in self.context_frames)

    @property
    def evidence_indices(self) -> tuple[int, ...]:
        """Target keyframes followed by neighbour frames, in display order."""

        return tuple(self.target_keyframe_indices) + self.context_indices

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_window_version": self.context_window_version,
            "episode_id": self.episode_id,
            "target_segment_id": self.target_segment_id,
            "target_start_frame": self.target_start_frame,
            "target_end_frame": self.target_end_frame,
            "target_keyframe_indices": list(self.target_keyframe_indices),
            "context_frames": [frame.to_dict() for frame in self.context_frames],
            "neighbor_status": dict(self.neighbor_status),
            "budget_audit": dict(self.budget_audit),
            "provenance": dict(self.provenance),
        }


# ---------------------------------------------------------------------------
# Validation (fail closed)
# ---------------------------------------------------------------------------


def audit_context_field_names(field_names: Iterable[str]) -> dict[str, Any]:
    """Forbidden-token and allowlist audit against the *context* allowlist.

    Deliberately separate from the EvidencePack allowlist: the context window
    legitimately exposes names (``context_frames``, ``neighbor_status``, ...)
    that the in-segment EvidencePack does not.
    """

    normalized = {str(name).strip().lower() for name in field_names}
    forbidden = sorted(
        name for name in normalized if any(token in name for token in FORBIDDEN_INPUT_TOKENS)
    )
    unapproved = sorted(name for name in normalized if name not in ALLOWED_CONTEXT_FIELDS)
    return {
        "checked_fields": sorted(normalized),
        "forbidden_tokens": sorted(FORBIDDEN_INPUT_TOKENS),
        "forbidden_hits": forbidden,
        "unapproved_fields": unapproved,
        "passed": not forbidden and not unapproved,
    }


def _assert_clean_rgb(frame: ContextFrame) -> None:
    prov = frame.renderer_provenance
    if prov.get("contract_version") != MODEL_RGB_CONTRACT_VERSION:
        raise ContextWindowError(
            f"STOP_CONTEXT_RGB_CONTRACT_VERSION_MISMATCH: {prov.get('contract_version')}"
        )
    if prov.get("overlay_applied") is not False:
        raise ContextWindowError("STOP_CONTEXT_RGB_OVERLAY_PRESENT")
    if prov.get("audit_mp4_used") is not False:
        raise ContextWindowError("STOP_CONTEXT_RGB_FROM_AUDIT_MP4")
    if prov.get("lossy_video_roundtrip") is not False:
        raise ContextWindowError("STOP_CONTEXT_RGB_LOSSY_VIDEO_ROUNDTRIP")


def validate_context_window(window: ContextWindow, episode: Any) -> None:
    """Every structural guarantee the Context Window promises, checked."""

    n_episode = len(episode.eef_pos)
    start, end = window.target_start_frame, window.target_end_frame

    # (a) frozen identity sanity
    if start < 0 or end < start or end >= n_episode:
        raise ContextWindowError(
            f"STOP_CONTEXT_TARGET_RANGE_INVALID: [{start},{end}] episode_len={n_episode}"
        )

    # (b) the original in-segment assertion is preserved for target keyframes
    if not window.target_keyframe_indices:
        raise ContextWindowError("STOP_CONTEXT_NO_TARGET_KEYFRAMES")
    for index in window.target_keyframe_indices:
        if index < start or index > end:
            raise ContextWindowError(
                "STOP_CONTEXT_KEYFRAME_OUT_OF_SEGMENT: "
                f"index={index} range=[{start},{end}]"
            )

    # (c) context frames: role, origin, episode, and the target-flag truth
    seen_pairs: set[tuple[int, str]] = set()
    roles_seen: list[str] = []
    for frame in window.context_frames:
        if frame.evidence_role not in CONTEXT_ROLES:
            raise ContextWindowError(
                f"STOP_CONTEXT_UNKNOWN_ROLE: {frame.evidence_role}"
            )
        if frame.evidence_role == ROLE_TARGET_KEYFRAME:
            raise ContextWindowError("STOP_CONTEXT_TARGET_ROLE_IN_CONTEXT_FRAMES")
        if frame.source_episode_id != window.episode_id:
            raise ContextWindowError(
                "STOP_CONTEXT_CROSS_EPISODE_FRAME: "
                f"frame_episode={frame.source_episode_id} target_episode={window.episode_id}"
            )
        if frame.target_segment_id != window.target_segment_id:
            raise ContextWindowError("STOP_CONTEXT_TARGET_ID_MISMATCH")
        # the target flag must be *derived*, never asserted by the caller
        actually_inside = start <= frame.frame_index <= end
        if frame.is_target_segment_frame != actually_inside:
            raise ContextWindowError(
                "STOP_CONTEXT_TARGET_FLAG_FALSE: "
                f"index={frame.frame_index} flagged={frame.is_target_segment_frame} "
                f"inside={actually_inside}"
            )
        if actually_inside:
            raise ContextWindowError(
                "STOP_CONTEXT_NEIGHBOR_INSIDE_TARGET_SEGMENT: "
                f"index={frame.frame_index} range=[{start},{end}]"
            )
        if not frame.origin_segment_id or frame.origin_segment_id == window.target_segment_id:
            raise ContextWindowError(
                "STOP_CONTEXT_ORIGIN_NOT_A_NEIGHBOR: "
                f"origin={frame.origin_segment_id} target={window.target_segment_id}"
            )
        # direction: PREV must lie strictly before the target, NEXT strictly after
        if frame.evidence_role == ROLE_PREV_END and frame.frame_index >= start:
            raise ContextWindowError(
                f"STOP_CONTEXT_PREV_NOT_BEFORE_TARGET: index={frame.frame_index} start={start}"
            )
        if frame.evidence_role in (ROLE_NEXT_START, ROLE_NEXT_MIDDLE) and frame.frame_index <= end:
            raise ContextWindowError(
                f"STOP_CONTEXT_NEXT_NOT_AFTER_TARGET: index={frame.frame_index} end={end}"
            )
        if frame.frame_index < 0 or frame.frame_index >= n_episode:
            raise ContextWindowError(
                f"STOP_CONTEXT_FRAME_OUT_OF_EPISODE: index={frame.frame_index} n={n_episode}"
            )
        pair = (frame.frame_index, frame.evidence_role)
        if pair in seen_pairs:
            raise ContextWindowError(f"STOP_CONTEXT_DUPLICATE_ROLE_PAIR: {pair}")
        seen_pairs.add(pair)
        roles_seen.append(frame.evidence_role)
        _assert_clean_rgb(frame)

    # (d) budget
    n_prev = sum(1 for role in roles_seen if role == ROLE_PREV_END)
    n_next = sum(1 for role in roles_seen if role in (ROLE_NEXT_START, ROLE_NEXT_MIDDLE))
    if n_prev > MAX_PREV_CONTEXT_FRAMES:
        raise ContextWindowError(f"STOP_CONTEXT_PREV_BUDGET_EXCEEDED: {n_prev}")
    if n_next > MAX_NEXT_CONTEXT_FRAMES:
        raise ContextWindowError(f"STOP_CONTEXT_NEXT_BUDGET_EXCEEDED: {n_next}")
    if len(window.context_frames) > MAX_CONTEXT_FRAMES_TOTAL:
        raise ContextWindowError(
            f"STOP_CONTEXT_TOTAL_BUDGET_EXCEEDED: {len(window.context_frames)}"
        )

    # (e) neighbor_status must agree with what was actually materialised
    for side, role_prefix in (("PREV", (ROLE_PREV_END,)), ("NEXT", (ROLE_NEXT_START, ROLE_NEXT_MIDDLE))):
        declared = window.neighbor_status.get(side)
        present = any(role in role_prefix for role in roles_seen)
        expected = NEIGHBOR_PRESENT if present else NEIGHBOR_MISSING
        if declared != expected:
            raise ContextWindowError(
                f"STOP_CONTEXT_NEIGHBOR_STATUS_MISMATCH: side={side} "
                f"declared={declared} expected={expected}"
            )

    # (f) forbidden fields, static and dynamic
    static = audit_context_field_names(ALLOWED_CONTEXT_FIELDS)
    if not static["passed"]:
        raise ContextWindowError(
            f"STOP_CONTEXT_FORBIDDEN_FIELD: {static['forbidden_hits']}"
        )
    surface = audit_context_surfaces(window)
    if not surface["passed"]:
        raise ContextWindowError(
            f"STOP_CONTEXT_SURFACE_FORBIDDEN_TOKEN: {surface['forbidden_hits']}"
        )


def audit_context_surfaces(window: ContextWindow) -> dict[str, Any]:
    """Dynamic scan of the *emitted* model-facing keys for forbidden tokens."""

    surfaces: list[str] = []
    for frame in window.context_frames:
        surfaces.append(str(frame.evidence_role))
        surfaces.extend(str(k) for k in frame.renderer_provenance.keys())
    surfaces.extend(ALLOWED_CONTEXT_FIELDS)
    audit = audit_context_field_names(surfaces)
    audit["unapproved_fields"] = []
    audit["passed"] = not audit["forbidden_hits"]
    return audit


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def _neighbors(
    segments: Sequence[Any], target_index: int
) -> tuple[Any | None, Any | None]:
    previous = segments[target_index - 1] if target_index > 0 else None
    following = segments[target_index + 1] if target_index + 1 < len(segments) else None
    return previous, following


def build_context_window(
    segments: Sequence[Any],
    target_index: int,
    episode: Any,
    adapter: Any,
    *,
    left_boundary_type: str | None,
    render: bool = True,
    renderer_factory: Any | None = None,
    frame_cache: Mapping[int, CleanRGBFrame] | None = None,
) -> ContextWindow:
    """Assemble one Context Window for ``segments[target_index]``."""

    if target_index < 0 or target_index >= len(segments):
        raise ContextWindowError(f"STOP_CONTEXT_TARGET_INDEX_OUT_OF_RANGE: {target_index}")

    target = segments[target_index]
    previous, following = _neighbors(segments, target_index)
    plans, status = plan_context_frames(target, previous, following)

    target_plans = plan_target_keyframes(target, left_boundary_type)
    target_indices = tuple(plan.frame_index for plan in target_plans)
    context_indices = tuple(plan.frame_index for plan in plans)
    all_indices = sorted(set(target_indices) | set(context_indices))

    # Render every unique frame exactly once (target and neighbour alike).
    if frame_cache is not None:
        missing = [i for i in all_indices if i not in frame_cache]
        if missing:
            raise ContextWindowError(f"STOP_CONTEXT_FRAME_CACHE_MISS: {missing}")
        cache = {i: frame_cache[i] for i in all_indices}
    elif render:
        rendered = render_clean_rgb_frames(
            adapter, str(episode.source_episode_id), all_indices,
            renderer_factory=renderer_factory,
        )
        cache = {frame.frame_index: frame for frame in rendered}
    else:
        cache = {
            index: CleanRGBFrame(
                source_episode_id=str(episode.source_episode_id),
                frame_index=index,
                rgb=np.zeros((1, 1, 3), dtype=np.uint8),
                provenance={
                    "contract_version": MODEL_RGB_CONTRACT_VERSION,
                    "source": "SKIPPED_NO_RENDER",
                    "overlay_applied": False,
                    "audit_mp4_used": False,
                    "lossy_video_roundtrip": False,
                    "pixel_sha256": None,
                },
            )
            for index in all_indices
        }

    context_frames = tuple(
        ContextFrame(
            source_episode_id=str(episode.source_episode_id),
            frame_index=plan.frame_index,
            pixel_sha256=cache[plan.frame_index].provenance.get("pixel_sha256"),
            target_segment_id=str(_get(target, "segment_id")),
            origin_segment_id=plan.origin_segment_id,
            evidence_role=plan.evidence_role,
            is_target_segment_frame=plan.is_target_segment_frame,
            renderer_provenance=dict(cache[plan.frame_index].provenance),
        )
        for plan in plans
    )

    n_prev = sum(1 for frame in context_frames if frame.evidence_role == ROLE_PREV_END)
    n_next = sum(
        1 for frame in context_frames
        if frame.evidence_role in (ROLE_NEXT_START, ROLE_NEXT_MIDDLE)
    )
    budget_audit = {
        "policy": CONTEXT_POLICY_NAME,
        "max_prev": MAX_PREV_CONTEXT_FRAMES,
        "max_next": MAX_NEXT_CONTEXT_FRAMES,
        "max_total": MAX_CONTEXT_FRAMES_TOTAL,
        "used_prev": n_prev,
        "used_next": n_next,
        "used_total": len(context_frames),
        "within_budget": (
            n_prev <= MAX_PREV_CONTEXT_FRAMES
            and n_next <= MAX_NEXT_CONTEXT_FRAMES
            and len(context_frames) <= MAX_CONTEXT_FRAMES_TOTAL
        ),
    }

    window = ContextWindow(
        context_window_version=CONTEXT_WINDOW_VERSION,
        episode_id=str(episode.source_episode_id),
        target_segment_id=str(_get(target, "segment_id")),
        target_start_frame=int(_get(target, "start_frame")),
        target_end_frame=int(_get(target, "end_frame")),
        target_keyframe_indices=target_indices,
        context_frames=context_frames,
        neighbor_status=status,
        budget_audit=budget_audit,
        provenance={
            "rgb_contract_version": MODEL_RGB_CONTRACT_VERSION,
            "left_boundary_type": left_boundary_type or "EPISODE_START",
            "segments_in_episode": len(segments),
            "target_index": target_index,
            "prev_segment_id": None if previous is None else str(_get(previous, "segment_id")),
            "next_segment_id": None if following is None else str(_get(following, "segment_id")),
            "vlm_invoked": False,
            "frozen_g1_boundaries_modified": False,
            "target_keyframes_reused_not_recomputed": True,
        },
    )
    validate_context_window(window, episode)
    return window


def context_rgb_lookup(
    window: ContextWindow,
    frame_cache: Mapping[int, CleanRGBFrame],
) -> dict[int, CleanRGBFrame]:
    """Fetch the rendered RGB for every evidence index of a window."""

    out: dict[int, CleanRGBFrame] = {}
    for index in window.evidence_indices:
        if index not in frame_cache:
            raise ContextWindowError(f"STOP_CONTEXT_RGB_MISSING: index={index}")
        out[index] = frame_cache[index]
    return out
