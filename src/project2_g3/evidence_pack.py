"""No-VLM EvidencePack adapter for the G3 Phase-1 audit.

An EvidencePack is the *exact* set of evidence a future G3 labeler (VLM or
otherwise) would be permitted to consume for one Frozen G1 segment:

    keyframes (clean RGB)  +  robot motion summary  +  segment identity

This module is intentionally free of any model call.  It enforces four
contracts and fails closed:

1. Temporal alignment: every MODEL_RGB frame index equals the keyframe index
   and lies inside the inclusive Frozen G1 segment range.
2. RGB provenance: frames come from a direct renderer STATE_t path with
   ``overlay_applied == False`` and ``audit_mp4_used == False``.
3. Forbidden fields: no reward / done / object GT / privileged state / leakage
   token may appear in any field name offered as model input.
4. Task text: the task string is reported with an explicit provenance and a
   ``recorded_instruction`` flag; an environment id is never silently upgraded
   into a recorded natural-language instruction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from project2_g1.boundary_engine import CANDIDATE_GRIPPER, UnlabeledSegment
from project2_g1.source import FormalEpisodeArrays
from project2_mvp.m2 import (
    ALLOWED_FORMAL_INPUT_FIELDS,
    FORBIDDEN_INPUT_TOKENS,
    MOTION_FEATURE_VERSION,
    SelectedKeyframe,
    assert_no_privileged_inputs,
    select_keyframes,
    summarize_motion,
)
from project2_mvp.rgb_input import (
    MODEL_RGB_CONTRACT_VERSION,
    CleanRGBFrame,
    render_clean_rgb_frames,
)

EVIDENCE_PACK_VERSION = "P2_G3_EVIDENCE_PACK_V1"

# Field names an EvidencePack is allowed to expose to a future labeler.
ALLOWED_EVIDENCE_FIELDS = frozenset({
    "keyframe_rgb",
    "keyframe_roles",
    "segment_identity",
    "robot_motion_summary",
    "task_text",
})


class EvidencePackError(ValueError):
    pass


@dataclass(frozen=True)
class TaskTextEvidence:
    """Task text available to a labeler, with honest provenance."""

    available: bool
    value: str | None
    provenance: str
    recorded_instruction: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "value": self.value,
            "provenance": self.provenance,
            "recorded_instruction": self.recorded_instruction,
        }


@dataclass(frozen=True)
class EvidencePack:
    episode_id: str
    segment_id: str
    start_frame: int
    end_frame: int
    duration_frames: int
    duration_sec: float
    keyframes: tuple[SelectedKeyframe, ...]
    rgb_frames: tuple[CleanRGBFrame, ...]
    motion_summary: Mapping[str, Any]
    task_text: TaskTextEvidence
    forbidden_field_audit: Mapping[str, Any]
    alignment_audit: Mapping[str, Any]
    provenance: Mapping[str, Any] = field(default_factory=dict)

    @property
    def keyframe_indices(self) -> tuple[int, ...]:
        return tuple(sorted({int(item.frame_index) for item in self.keyframes}))

    @property
    def rgb_indices(self) -> tuple[int, ...]:
        return tuple(sorted(int(frame.frame_index) for frame in self.rgb_frames))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_pack_version": EVIDENCE_PACK_VERSION,
            "episode_id": self.episode_id,
            "segment_id": self.segment_id,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "duration_frames": self.duration_frames,
            "duration_sec": self.duration_sec,
            "keyframes": [
                {"frame_index": item.frame_index, "roles": list(item.roles)}
                for item in self.keyframes
            ],
            "rgb_frames": [
                {
                    "frame_index": frame.frame_index,
                    "shape": list(frame.rgb.shape),
                    "dtype": str(frame.rgb.dtype),
                    "pixel_sha256": frame.provenance.get("pixel_sha256"),
                    "overlay_applied": frame.provenance.get("overlay_applied"),
                    "audit_mp4_used": frame.provenance.get("audit_mp4_used"),
                }
                for frame in self.rgb_frames
            ],
            "motion_summary": dict(self.motion_summary),
            "task_text": self.task_text.to_dict(),
            "forbidden_field_audit": dict(self.forbidden_field_audit),
            "alignment_audit": dict(self.alignment_audit),
            "provenance": dict(self.provenance),
        }


def audit_forbidden_field_names(field_names: Iterable[str]) -> dict[str, Any]:
    """Report forbidden/unapproved names; never silently accept them."""

    normalized = {str(name).strip().lower() for name in field_names}
    forbidden = sorted(
        name for name in normalized if any(token in name for token in FORBIDDEN_INPUT_TOKENS)
    )
    unapproved = sorted(name for name in normalized if name not in ALLOWED_EVIDENCE_FIELDS)
    return {
        "checked_fields": sorted(normalized),
        "forbidden_tokens": sorted(FORBIDDEN_INPUT_TOKENS),
        "forbidden_hits": forbidden,
        "unapproved_fields": unapproved,
        "passed": not forbidden and not unapproved,
    }


def audit_emitted_surfaces(pack_dict: Mapping[str, Any]) -> dict[str, Any]:
    """Dynamically scan the *emitted* model-facing keys for forbidden tokens."""

    surfaces: list[str] = []
    surfaces.extend(str(k) for k in pack_dict.get("motion_summary", {}).keys())
    for kf in pack_dict.get("keyframes", []):
        surfaces.extend(str(role) for role in kf.get("roles", []))
    surfaces.extend(["keyframe_rgb", "task_text", "segment_identity"])
    audit = audit_forbidden_field_names(surfaces)
    # keyframe roles / motion keys are not themselves allowlisted names, so only
    # the forbidden-token scan is meaningful here.
    audit["unapproved_fields"] = []
    audit["passed"] = not audit["forbidden_hits"]
    return audit


def task_text_evidence(provenance: Mapping[str, Any]) -> TaskTextEvidence:
    """Derive task text honestly.

    Can/MH stores no per-episode natural-language instruction.  The only
    dataset-level task string is the environment id (e.g. ``PickPlaceCan``).
    It is reported as an environment/task id, never as a recorded instruction.
    """

    raw = provenance.get("task")
    if raw is None or str(raw).strip() == "":
        return TaskTextEvidence(
            available=False,
            value=None,
            provenance="NO_TASK_FIELD_IN_SOURCE",
            recorded_instruction=False,
        )
    return TaskTextEvidence(
        available=True,
        value=str(raw),
        provenance="SOURCE_PROVENANCE_ENVIRONMENT_TASK_ID",
        recorded_instruction=False,
    )


def _assert_rgb_contract(rgb_frames: Sequence[CleanRGBFrame]) -> None:
    for frame in rgb_frames:
        prov = frame.provenance
        if prov.get("contract_version") != MODEL_RGB_CONTRACT_VERSION:
            raise EvidencePackError(
                f"STOP_RGB_CONTRACT_VERSION_MISMATCH: {prov.get('contract_version')}"
            )
        if prov.get("overlay_applied") is not False:
            raise EvidencePackError("STOP_RGB_OVERLAY_PRESENT")
        if prov.get("audit_mp4_used") is not False:
            raise EvidencePackError("STOP_RGB_FROM_AUDIT_MP4")
        if prov.get("lossy_video_roundtrip") is not False:
            raise EvidencePackError("STOP_RGB_LOSSY_VIDEO_ROUNDTRIP")


def assert_evidence_alignment(pack: EvidencePack) -> None:
    """Fail closed if MODEL_RGB / keyframe / segment indices disagree."""

    keyframe_indices = pack.keyframe_indices
    rgb_indices = pack.rgb_indices
    if rgb_indices != keyframe_indices:
        raise EvidencePackError(
            "STOP_EVIDENCE_RGB_KEYFRAME_MISMATCH: "
            f"rgb={rgb_indices} keyframes={keyframe_indices}"
        )
    if not keyframe_indices:
        raise EvidencePackError("STOP_EVIDENCE_NO_KEYFRAMES")
    if len(set(rgb_indices)) != len(rgb_indices):
        raise EvidencePackError(f"STOP_EVIDENCE_DUPLICATE_RGB: {rgb_indices}")
    for index in keyframe_indices:
        if index < pack.start_frame or index > pack.end_frame:
            raise EvidencePackError(
                "STOP_EVIDENCE_KEYFRAME_OUT_OF_SEGMENT: "
                f"index={index} range=[{pack.start_frame},{pack.end_frame}]"
            )


def build_evidence_pack(
    segment: UnlabeledSegment | Mapping[str, Any],
    episode: FormalEpisodeArrays,
    adapter: Any,
    *,
    left_boundary_type: str | None,
    gripper_state: np.ndarray | None,
    render: bool = True,
    renderer_factory: Any | None = None,
    frame_cache: Mapping[int, CleanRGBFrame] | None = None,
) -> EvidencePack:
    """Assemble one EvidencePack.  No model is ever invoked.

    ``frame_cache`` lets a caller render each unique frame once per episode and
    reuse it across segments; cached frames are still contract-validated.
    """

    # Fail closed before doing any work.
    assert_no_privileged_inputs(ALLOWED_FORMAL_INPUT_FIELDS)

    get = (
        (lambda key: getattr(segment, key))
        if not isinstance(segment, Mapping)
        else segment.__getitem__
    )
    start = int(get("start_frame"))
    end = int(get("end_frame"))
    n_episode = len(episode.eef_pos)
    if start < 0 or end < start or end >= n_episode:
        raise EvidencePackError(
            f"STOP_EVIDENCE_SEGMENT_OUT_OF_EPISODE: [{start},{end}] episode_len={n_episode}"
        )
    keyframes = select_keyframes(segment, left_boundary_type=left_boundary_type)
    motion = summarize_motion(
        segment,
        episode,
        gripper_state=gripper_state,
        left_boundary_type=left_boundary_type,
    )

    n = len(episode.eef_pos)
    indices = sorted({int(item.frame_index) for item in keyframes})
    for index in indices:
        if index < 0 or index >= n:
            raise EvidencePackError(
                f"STOP_EVIDENCE_FRAME_OUT_OF_EPISODE: index={index} episode_len={n}"
            )

    if frame_cache is not None:
        missing = [index for index in indices if index not in frame_cache]
        if missing:
            raise EvidencePackError(f"STOP_EVIDENCE_FRAME_CACHE_MISS: {missing}")
        rgb_frames = tuple(frame_cache[index] for index in indices)
    elif render:
        rgb_frames = render_clean_rgb_frames(
            adapter, episode.source_episode_id, indices, renderer_factory=renderer_factory
        )
    else:
        rgb_frames = tuple(
            CleanRGBFrame(
                source_episode_id=episode.source_episode_id,
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
            for index in indices
        )
    _assert_rgb_contract(rgb_frames)

    forbidden = audit_forbidden_field_names(ALLOWED_EVIDENCE_FIELDS)
    if not forbidden["passed"]:
        raise EvidencePackError(
            f"STOP_EVIDENCE_FORBIDDEN_FIELD: {forbidden['forbidden_hits']}"
        )

    surface_audit = audit_emitted_surfaces({"motion_summary": motion, "keyframes": [
        {"frame_index": item.frame_index, "roles": list(item.roles)} for item in keyframes
    ]})
    if not surface_audit["passed"]:
        raise EvidencePackError(
            f"STOP_EVIDENCE_SURFACE_FORBIDDEN_TOKEN: {surface_audit['forbidden_hits']}"
        )
    forbidden = dict(forbidden)
    forbidden["emitted_surface_audit"] = surface_audit

    pack = EvidencePack(
        episode_id=str(episode.source_episode_id),
        segment_id=str(get("segment_id")),
        start_frame=start,
        end_frame=end,
        duration_frames=int(get("duration_frames")),
        duration_sec=float(get("duration_sec")),
        keyframes=keyframes,
        rgb_frames=rgb_frames,
        motion_summary=motion,
        task_text=task_text_evidence(episode.provenance),
        forbidden_field_audit=forbidden,
        alignment_audit={
            "model_rgb_indices": list(indices),
            "keyframe_indices": list(indices),
            "segment_range": [start, end],
            "alignment_rule": "MODEL_RGB[t] = render(STATE_t); PROPRIO[t]; ACTION[t]",
            "index_preserving": True,
        },
        provenance={
            "rgb_contract_version": MODEL_RGB_CONTRACT_VERSION,
            "motion_feature_version": MOTION_FEATURE_VERSION,
            "left_boundary_type": left_boundary_type or "EPISODE_START",
            "gripper_event_present": left_boundary_type == CANDIDATE_GRIPPER,
            "vlm_invoked": False,
            "source_episode_provenance": dict(episode.provenance),
        },
    )
    assert_evidence_alignment(pack)
    return pack
