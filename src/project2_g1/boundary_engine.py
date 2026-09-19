"""G1-P2 Boundary Engine + Event-aware Postprocess.

Formal inputs are G1-P1 FormalSignals only. This module must not read
simulator object GT, reward, done, success, next_obs, or future privileged state.

All numeric thresholds come from G1P2Config and remain EXPLORATORY /
DATA_CALIBRATION_PENDING. Outputs are Unlabeled Behavior Segments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np

from .boundary_config import G1P2Config
from .final_semantics import build_materialized_fields
from .signals import FormalSignals

EPISODE_START = "EPISODE_START"
EPISODE_END = "EPISODE_END"

CANDIDATE_GRIPPER = "GRIPPER_TRANSITION"
CANDIDATE_MOVE_TO_IDLE = "MOVE_TO_IDLE"
CANDIDATE_IDLE_TO_MOVE = "IDLE_TO_MOVE"
CANDIDATE_DIRECTION = "DIRECTION_CHANGE"

SUPPORT_ROTATION = "ROTATION_SUPPORT"
SUPPORT_ACTION = "ACTION_SUPPORT"

DECISION_KEEP = "KEEP"
DECISION_SUPPRESS_DEBOUNCE = "SUPPRESS_DEBOUNCE"
DECISION_MERGE_CONSOLIDATION = "MERGE_CONSOLIDATION"
DECISION_SUPPRESS_SHORT_PAUSE = "SUPPRESS_SHORT_PAUSE"
DECISION_MERGE_LEFT = "MERGE_LEFT"
DECISION_MERGE_RIGHT = "MERGE_RIGHT"
DECISION_RETAIN_HARD = "RETAIN_HARD"
DECISION_REVIEW_REQUIRED = "REVIEW_REQUIRED"

FLAG_MICRO_INTERACTION = "MICRO_INTERACTION"
FLAG_REVIEW_REQUIRED = "REVIEW_REQUIRED"
FLAG_SHORT_SEGMENT = "SHORT_SEGMENT_CANDIDATE"
FLAG_LONG_SEGMENT = "LONG_SEGMENT_AUDIT"
FLAG_LONG_INTERNAL = "LONG_SEGMENT_WITH_INTERNAL_CANDIDATE"

TYPE_PRIORITY = {
    CANDIDATE_GRIPPER: 0,
    CANDIDATE_MOVE_TO_IDLE: 1,
    CANDIDATE_IDLE_TO_MOVE: 1,
    CANDIDATE_DIRECTION: 2,
}

MOTION_TYPES = {CANDIDATE_MOVE_TO_IDLE, CANDIDATE_IDLE_TO_MOVE, CANDIDATE_DIRECTION}


@dataclass
class BoundaryCandidate:
    episode_id: str
    candidate_id: str
    frame: int
    candidate_type: str
    primary_reason: str
    supporting_reasons: list[str]
    evidence_value: float
    persistence_status: str
    source_signal: str
    config_version: str
    polarity: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "candidate_id": self.candidate_id,
            "frame": int(self.frame),
            "candidate_type": self.candidate_type,
            "primary_reason": self.primary_reason,
            "supporting_reasons": "|".join(self.supporting_reasons) if self.supporting_reasons else "",
            "evidence_value": float(self.evidence_value),
            "persistence_status": self.persistence_status,
            "source_signal": self.source_signal,
            "config_version": self.config_version,
            "polarity": self.polarity,
        }


@dataclass
class BoundaryDecision:
    candidate_id: str
    decision: str
    reason: str
    target_boundary_id: str | None = None

    def to_row(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "decision": self.decision,
            "reason": self.reason,
            "target_boundary_id": self.target_boundary_id or "",
        }


@dataclass
class BoundaryEvent:
    boundary_id: str
    episode_id: str
    frame: int
    candidate_type: str
    reason: str
    member_candidate_ids: list[str]
    supporting_reasons: list[str] = field(default_factory=list)
    review_flags: list[str] = field(default_factory=list)
    polarity: str = ""
    config_version: str = ""
    segmentation_version: str = ""
    active: bool = True
    representative_candidate_id: str = ""
    member_candidate_types: list[str] = field(default_factory=list)
    member_candidate_frames: list[int] = field(default_factory=list)
    member_candidate_count: int = 0

    def to_row(self) -> dict[str, Any]:
        return {
            "boundary_id": self.boundary_id,
            "episode_id": self.episode_id,
            "frame": int(self.frame),
            "candidate_type": self.candidate_type,
            "reason": self.reason,
            "member_candidate_ids": "|".join(self.member_candidate_ids),
            "representative_candidate_id": self.representative_candidate_id,
            "member_candidate_types": "|".join(self.member_candidate_types),
            "member_candidate_frames": "|".join(str(int(frame)) for frame in self.member_candidate_frames),
            "member_candidate_count": int(self.member_candidate_count),
            "supporting_reasons": "|".join(self.supporting_reasons) if self.supporting_reasons else "",
            "review_flags": "|".join(self.review_flags) if self.review_flags else "",
            "polarity": self.polarity,
            "config_version": self.config_version,
            "segmentation_version": self.segmentation_version,
        }


@dataclass
class UnlabeledSegment:
    segment_id: str
    source_episode_id: str
    start_frame: int
    end_frame: int
    duration_frames: int
    duration_sec: float
    left_boundary_id: str
    right_boundary_id: str
    left_boundary_reason: str
    right_boundary_reason: str
    segmentation_version: str
    config_version: str
    short_segment_flag: bool
    long_segment_flag: bool
    review_required: bool
    segment_label: str = "NONE"
    semantic_phase: str = "NONE"
    review_flags: list[str] = field(default_factory=list)

    def to_row(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "source_episode_id": self.source_episode_id,
            "start_frame": int(self.start_frame),
            "end_frame": int(self.end_frame),
            "duration_frames": int(self.duration_frames),
            "duration_sec": float(self.duration_sec),
            "left_boundary_id": self.left_boundary_id,
            "right_boundary_id": self.right_boundary_id,
            "left_boundary_reason": self.left_boundary_reason,
            "right_boundary_reason": self.right_boundary_reason,
            "segmentation_version": self.segmentation_version,
            "config_version": self.config_version,
            "short_segment_flag": bool(self.short_segment_flag),
            "long_segment_flag": bool(self.long_segment_flag),
            "review_required": bool(self.review_required),
            "segment_label": self.segment_label,
            "semantic_phase": self.semantic_phase,
            "review_flags": "|".join(self.review_flags) if self.review_flags else "",
        }


@dataclass
class EngineResult:
    episode_id: str
    native_episode_key: str
    n_frames: int
    dt_s: float
    motion_state: np.ndarray
    gripper_state: np.ndarray
    candidates: list[BoundaryCandidate]
    decisions: dict[str, BoundaryDecision]
    events: list[BoundaryEvent]
    segments: list[UnlabeledSegment]
    config_metadata: dict[str, Any]
    review_required: bool

    @property
    def final_events(self) -> list[BoundaryEvent]:
        return sorted(
            [event for event in self.events if event.active],
            key=lambda item: item.frame,
        )

    @property
    def candidate_frames(self) -> list[int]:
        return [int(item.frame) for item in self.candidates]

    @property
    def suppressed_frames(self) -> list[int]:
        final_frames = {int(event.frame) for event in self.final_events}
        frames: list[int] = []
        for cand in self.candidates:
            if int(cand.frame) in final_frames:
                continue
            frames.append(int(cand.frame))
        return frames

    @property
    def final_frames(self) -> list[int]:
        return [int(event.frame) for event in self.final_events]

    @property
    def final_annotations(self) -> list[tuple[int, str]]:
        return [(int(event.frame), _short_reason(event)) for event in self.final_events]


def _short_reason(event: BoundaryEvent) -> str:
    mapping = {
        CANDIDATE_GRIPPER: "GRIPPER",
        CANDIDATE_MOVE_TO_IDLE: "MOVE_IDLE",
        CANDIDATE_IDLE_TO_MOVE: "IDLE_MOVE",
        CANDIDATE_DIRECTION: "DIR",
    }
    label = mapping.get(event.candidate_type, event.candidate_type)
    flags = ",".join(event.review_flags) if event.review_flags else ""
    return f"{label}|{flags}" if flags else label


def binarize_motion_state(speed: np.ndarray, threshold: float) -> np.ndarray:
    return (np.asarray(speed, dtype=np.float64) > float(threshold)).astype(np.int8)


def binarize_gripper_state(aperture: np.ndarray, threshold: float) -> np.ndarray:
    """Exploratory OPEN=1 / CLOSED=0 from aperture. Not a frozen grasp definition."""

    return (np.asarray(aperture, dtype=np.float64) > float(threshold)).astype(np.int8)


def persistent_binary_transitions(
    state: np.ndarray,
    persistence_frames: int,
) -> list[tuple[int, int, int]]:
    """Return (frame, from_state, to_state) for regime changes that persist on both sides.

    Looking forward inside the same series to confirm the new regime is persistence,
    not privileged next_obs / future GT.
    """

    state = np.asarray(state, dtype=np.int8)
    n = len(state)
    persistence = int(persistence_frames)
    if persistence < 1 or n < (2 * persistence + 1):
        return []
    out: list[tuple[int, int, int]] = []
    for t in range(1, n):
        if state[t] == state[t - 1]:
            continue
        left_start = t - persistence
        right_end = t + persistence
        if left_start < 0 or right_end > n:
            continue
        if np.all(state[left_start:t] == state[t - 1]) and np.all(state[t:right_end] == state[t]):
            out.append((int(t), int(state[t - 1]), int(state[t])))
    return out


def persistent_high_runs(
    values: np.ndarray,
    threshold: float,
    persistence_frames: int,
) -> list[tuple[int, float, int]]:
    """Persistent threshold crossings. Returns (peak_frame, peak_value, run_length)."""

    values = np.asarray(values, dtype=np.float64)
    high = values > float(threshold)
    persistence = int(persistence_frames)
    if persistence < 1 or len(values) == 0:
        return []
    out: list[tuple[int, float, int]] = []
    t = 0
    n = len(high)
    while t < n:
        if not high[t]:
            t += 1
            continue
        start = t
        while t < n and high[t]:
            t += 1
        run = t - start
        if run < persistence:
            continue
        peak_offset = int(np.argmax(values[start:t]))
        peak = start + peak_offset
        out.append((int(peak), float(values[peak]), int(run)))
    return out


def heading_vector(signals: FormalSignals, start: int, end: int) -> np.ndarray:
    start = max(0, int(start))
    end = min(int(signals.n_frames), int(end))
    if end <= start:
        return np.zeros(3, dtype=np.float64)
    return np.array(
        [
            float(np.sum(signals.delta_x[start:end])),
            float(np.sum(signals.delta_y[start:end])),
            float(np.sum(signals.delta_z[start:end])),
        ],
        dtype=np.float64,
    )


def heading_angle(vec_a: np.ndarray, vec_b: np.ndarray) -> float | None:
    n_a = float(np.linalg.norm(vec_a))
    n_b = float(np.linalg.norm(vec_b))
    if n_a <= 0.0 or n_b <= 0.0:
        return None
    cosine = float(np.dot(vec_a, vec_b) / (n_a * n_b))
    return float(np.arccos(np.clip(cosine, -1.0, 1.0)))


def _assign_ids(
    episode_id: str,
    config_version: str,
    items: list[BoundaryCandidate],
) -> list[BoundaryCandidate]:
    items = sorted(items, key=lambda item: (item.frame, TYPE_PRIORITY.get(item.candidate_type, 9)))
    for index, item in enumerate(items, start=1):
        item.episode_id = episode_id
        item.candidate_id = f"{episode_id.split('/')[-1]}-C{index:04d}"
        item.config_version = config_version
        item.persistence_status = "PERSISTENT"
    return items


def _generate_gripper_candidates(
    signals: FormalSignals,
    gripper_state: np.ndarray,
    config: G1P2Config,
) -> list[BoundaryCandidate]:
    out: list[BoundaryCandidate] = []
    for frame, from_state, to_state in persistent_binary_transitions(
        gripper_state, config.gripper_persistence_frames
    ):
        if from_state == 1 and to_state == 0:
            polarity = "OPEN_TO_CLOSE"
            reason = "PERSISTENT_GRIPPER_OPEN_TO_CLOSE"
        elif from_state == 0 and to_state == 1:
            polarity = "CLOSE_TO_OPEN"
            reason = "PERSISTENT_GRIPPER_CLOSE_TO_OPEN"
        else:
            continue
        out.append(
            BoundaryCandidate(
                episode_id=signals.source_episode_id,
                candidate_id="",
                frame=frame,
                candidate_type=CANDIDATE_GRIPPER,
                primary_reason=reason,
                supporting_reasons=[],
                evidence_value=float(abs(signals.gripper_aperture[frame] - signals.gripper_aperture[frame - 1])),
                persistence_status="PERSISTENT",
                source_signal="gripper_aperture",
                config_version=config.config_version,
                polarity=polarity,
            )
        )
    return out


def _generate_motion_candidates(
    signals: FormalSignals,
    motion_state: np.ndarray,
    config: G1P2Config,
) -> list[BoundaryCandidate]:
    out: list[BoundaryCandidate] = []
    for frame, from_state, to_state in persistent_binary_transitions(
        motion_state, config.motion_persistence_frames
    ):
        if from_state == 1 and to_state == 0:
            cand_type = CANDIDATE_MOVE_TO_IDLE
            polarity = "MOVE_TO_IDLE"
            reason = "PERSISTENT_MOVE_TO_IDLE"
        elif from_state == 0 and to_state == 1:
            cand_type = CANDIDATE_IDLE_TO_MOVE
            polarity = "IDLE_TO_MOVE"
            reason = "PERSISTENT_IDLE_TO_MOVE"
        else:
            continue
        out.append(
            BoundaryCandidate(
                episode_id=signals.source_episode_id,
                candidate_id="",
                frame=frame,
                candidate_type=cand_type,
                primary_reason=reason,
                supporting_reasons=[],
                evidence_value=float(signals.translation_speed[frame]),
                persistence_status="PERSISTENT",
                source_signal="translation_speed",
                config_version=config.config_version,
                polarity=polarity,
            )
        )
    return out


def _generate_direction_candidates(
    signals: FormalSignals,
    config: G1P2Config,
) -> list[BoundaryCandidate]:
    out: list[BoundaryCandidate] = []
    for frame, value, run_length in persistent_high_runs(
        signals.direction_change_evidence,
        config.direction_change_threshold,
        config.direction_persistence_frames,
    ):
        out.append(
            BoundaryCandidate(
                episode_id=signals.source_episode_id,
                candidate_id="",
                frame=frame,
                candidate_type=CANDIDATE_DIRECTION,
                primary_reason="PERSISTENT_DIRECTION_CHANGE",
                supporting_reasons=[],
                evidence_value=float(value),
                persistence_status="PERSISTENT",
                source_signal="direction_change_evidence",
                config_version=config.config_version,
                polarity="DIRECTION_CHANGE",
                extra={"run_length": int(run_length)},
            )
        )
    return out


def generate_raw_candidates(
    signals: FormalSignals,
    motion_state: np.ndarray,
    gripper_state: np.ndarray,
    config: G1P2Config,
) -> list[BoundaryCandidate]:
    items: list[BoundaryCandidate] = []
    items.extend(_generate_gripper_candidates(signals, gripper_state, config))
    items.extend(_generate_motion_candidates(signals, motion_state, config))
    items.extend(_generate_direction_candidates(signals, config))
    return _assign_ids(signals.source_episode_id, config.config_version, items)


def _window_max(values: np.ndarray, frame: int, window: int) -> float:
    lo = max(0, int(frame) - int(window))
    hi = min(len(values), int(frame) + int(window) + 1)
    if hi <= lo:
        return 0.0
    return float(np.max(values[lo:hi]))


def attach_supporting_evidence(
    candidates: list[BoundaryCandidate],
    signals: FormalSignals,
    config: G1P2Config,
) -> None:
    """Rotation / action may reinforce Motion candidates. They never create boundaries."""

    window = int(config.support_window_frames)
    for cand in candidates:
        if cand.candidate_type not in MOTION_TYPES:
            continue
        rot_peak = _window_max(signals.eef_rotation_delta_rad, cand.frame, window)
        act_peak = _window_max(signals.action_change_magnitude, cand.frame, window)
        if rot_peak >= float(config.rotation_support_threshold):
            if SUPPORT_ROTATION not in cand.supporting_reasons:
                cand.supporting_reasons.append(SUPPORT_ROTATION)
        if act_peak >= float(config.action_support_threshold):
            if SUPPORT_ACTION not in cand.supporting_reasons:
                cand.supporting_reasons.append(SUPPORT_ACTION)


def debounce_candidates(
    candidates: list[BoundaryCandidate],
    config: G1P2Config,
) -> dict[str, BoundaryDecision]:
    decisions: dict[str, BoundaryDecision] = {}
    kept: list[BoundaryCandidate] = []
    window = int(config.debounce_frames)
    for cand in sorted(candidates, key=lambda item: (item.frame, TYPE_PRIORITY.get(item.candidate_type, 9))):
        suppressed_by = None
        for prev in reversed(kept):
            if cand.frame - prev.frame > window:
                break
            same_family = cand.candidate_type == prev.candidate_type and cand.polarity == prev.polarity
            if same_family:
                suppressed_by = prev
                break
        if suppressed_by is not None:
            decisions[cand.candidate_id] = BoundaryDecision(
                candidate_id=cand.candidate_id,
                decision=DECISION_SUPPRESS_DEBOUNCE,
                reason=(
                    f"same-type same-polarity candidate within debounce_frames={window} "
                    f"of {suppressed_by.candidate_id}"
                ),
                target_boundary_id=suppressed_by.candidate_id,
            )
        else:
            kept.append(cand)
            decisions[cand.candidate_id] = BoundaryDecision(
                candidate_id=cand.candidate_id,
                decision=DECISION_KEEP,
                reason="passed persistence and debounce",
                target_boundary_id=None,
            )
    return decisions


def _compatible_for_cluster(cluster: list[BoundaryCandidate], cand: BoundaryCandidate) -> bool:
    for member in cluster:
        if member.candidate_type == CANDIDATE_GRIPPER and cand.candidate_type == CANDIDATE_GRIPPER:
            if member.polarity and cand.polarity and member.polarity != cand.polarity:
                return False
        opposite_motion = {
            (CANDIDATE_MOVE_TO_IDLE, CANDIDATE_IDLE_TO_MOVE),
            (CANDIDATE_IDLE_TO_MOVE, CANDIDATE_MOVE_TO_IDLE),
        }
        if (member.candidate_type, cand.candidate_type) in opposite_motion:
            return False
    return True


def _cluster_candidates(
    candidates: list[BoundaryCandidate],
    window: int,
) -> list[list[BoundaryCandidate]]:
    ordered = sorted(candidates, key=lambda item: item.frame)
    clusters: list[list[BoundaryCandidate]] = []
    current: list[BoundaryCandidate] = []
    for cand in ordered:
        if not current:
            current = [cand]
            continue
        near = (cand.frame - current[0].frame) <= window
        if near and _compatible_for_cluster(current, cand):
            current.append(cand)
        else:
            clusters.append(current)
            current = [cand]
    if current:
        clusters.append(current)
    return clusters


def _pick_representative(cluster: list[BoundaryCandidate]) -> BoundaryCandidate:
    return sorted(
        cluster,
        key=lambda item: (TYPE_PRIORITY.get(item.candidate_type, 9), item.frame),
    )[0]


def consolidate_candidates(
    candidates: list[BoundaryCandidate],
    decisions: dict[str, BoundaryDecision],
    config: G1P2Config,
) -> list[BoundaryEvent]:
    active = [
        cand
        for cand in candidates
        if decisions.get(cand.candidate_id, BoundaryDecision(cand.candidate_id, DECISION_KEEP, "")).decision
        == DECISION_KEEP
    ]
    clusters = _cluster_candidates(active, int(config.boundary_consolidation_window))
    events: list[BoundaryEvent] = []
    native = candidates[0].episode_id.split("/")[-1] if candidates else "episode"
    episode_id = candidates[0].episode_id if candidates else ""
    for index, cluster in enumerate(clusters, start=1):
        representative = _pick_representative(cluster)
        boundary_id = f"{native}-B{index:04d}"
        supporting: list[str] = []
        for member in cluster:
            for reason in member.supporting_reasons:
                if reason not in supporting:
                    supporting.append(reason)
        # Member pipes are denormalized Candidate fields. Representative
        # identity comes from _pick_representative(), not sorted-list[0].
        materialized = build_materialized_fields(
            representative_candidate_id=representative.candidate_id,
            members=[
                {
                    "candidate_id": member.candidate_id,
                    "candidate_type": member.candidate_type,
                    "frame": int(member.frame),
                }
                for member in cluster
            ],
        )
        ordered_members = list(materialized["members"])
        event = BoundaryEvent(
            boundary_id=boundary_id,
            episode_id=episode_id,
            frame=int(representative.frame),
            candidate_type=representative.candidate_type,
            reason=representative.primary_reason,
            member_candidate_ids=[item["candidate_id"] for item in ordered_members],
            supporting_reasons=supporting,
            polarity=representative.polarity,
            config_version=config.config_version,
            segmentation_version=config.segmentation_version,
            active=True,
            representative_candidate_id=str(materialized["representative_candidate_id"]),
            member_candidate_types=[item["candidate_type"] for item in ordered_members],
            member_candidate_frames=[int(item["frame"]) for item in ordered_members],
            member_candidate_count=int(materialized["member_candidate_count"]),
        )
        events.append(event)
        for member in cluster:
            if member.candidate_id == representative.candidate_id:
                reason = (
                    "hard boundary anchored as cluster representative"
                    if member.candidate_type == CANDIDATE_GRIPPER
                    else "cluster representative"
                )
                decisions[member.candidate_id] = BoundaryDecision(
                    candidate_id=member.candidate_id,
                    decision=DECISION_KEEP,
                    reason=reason,
                    target_boundary_id=boundary_id,
                )
            else:
                decisions[member.candidate_id] = BoundaryDecision(
                    candidate_id=member.candidate_id,
                    decision=DECISION_MERGE_CONSOLIDATION,
                    reason=(
                        f"consolidated into {boundary_id} anchored at "
                        f"{representative.candidate_type}@{representative.frame}"
                    ),
                    target_boundary_id=boundary_id,
                )
    return events


def _active_events(events: Iterable[BoundaryEvent]) -> list[BoundaryEvent]:
    return sorted([event for event in events if event.active], key=lambda item: item.frame)


def _event_by_id(events: list[BoundaryEvent], boundary_id: str) -> BoundaryEvent | None:
    for event in events:
        if event.boundary_id == boundary_id:
            return event
    return None


def _mark_candidates(
    decisions: dict[str, BoundaryDecision],
    event: BoundaryEvent,
    decision: str,
    reason: str,
) -> None:
    for candidate_id in event.member_candidate_ids:
        current = decisions.get(candidate_id)
        if current is not None and current.decision == DECISION_MERGE_CONSOLIDATION:
            continue
        decisions[candidate_id] = BoundaryDecision(
            candidate_id=candidate_id,
            decision=decision,
            reason=reason,
            target_boundary_id=event.boundary_id,
        )


def _mean_state(values: np.ndarray, start: int, end: int) -> float:
    start = max(0, int(start))
    end = min(len(values), int(end) + 1)
    if end <= start:
        return 0.0
    return float(np.mean(values[start:end]))


def _pause_pair_eligible(
    left: BoundaryEvent,
    right: BoundaryEvent,
    signals: FormalSignals,
    gripper_state: np.ndarray,
    config: G1P2Config,
) -> bool:
    if left.candidate_type != CANDIDATE_MOVE_TO_IDLE:
        return False
    if right.candidate_type != CANDIDATE_IDLE_TO_MOVE:
        return False
    if left.candidate_type == CANDIDATE_GRIPPER or right.candidate_type == CANDIDATE_GRIPPER:
        return False
    duration = int(right.frame) - int(left.frame)
    if duration <= 0 or duration > int(config.pause_bridge_duration):
        return False
    n = signals.n_frames
    window = int(config.direction_window_frames)
    pre = heading_vector(signals, left.frame - window, left.frame)
    post = heading_vector(signals, right.frame, right.frame + window)
    if float(np.linalg.norm(pre)) < float(config.direction_min_window_displacement_m):
        return False
    if float(np.linalg.norm(post)) < float(config.direction_min_window_displacement_m):
        return False
    angle = heading_angle(pre, post)
    if angle is None or angle > float(config.direction_compatibility_threshold):
        return False
    pause_grip = _mean_state(gripper_state, left.frame, min(n - 1, right.frame - 1))
    pre_grip = _mean_state(gripper_state, max(0, left.frame - window), max(0, left.frame - 1))
    post_grip = _mean_state(gripper_state, right.frame, min(n - 1, right.frame + window - 1))
    binarized = [
        int(pre_grip >= 0.5),
        int(pause_grip >= 0.5),
        int(post_grip >= 0.5),
    ]
    if len(set(binarized)) != 1:
        return False
    return True


def pause_bridge_events(
    events: list[BoundaryEvent],
    decisions: dict[str, BoundaryDecision],
    signals: FormalSignals,
    gripper_state: np.ndarray,
    config: G1P2Config,
) -> list[BoundaryEvent]:
    active = _active_events(events)
    skip: set[str] = set()
    for left, right in zip(active, active[1:]):
        if left.boundary_id in skip or right.boundary_id in skip:
            continue
        if not _pause_pair_eligible(left, right, signals, gripper_state, config):
            continue
        left.active = False
        right.active = False
        skip.add(left.boundary_id)
        skip.add(right.boundary_id)
        reason = (
            f"short pause {right.frame - left.frame} frames with compatible gripper/heading "
            f"and no hard interaction event"
        )
        _mark_candidates(decisions, left, DECISION_SUPPRESS_SHORT_PAUSE, reason)
        _mark_candidates(decisions, right, DECISION_SUPPRESS_SHORT_PAUSE, reason)
    return events


def _neighbor_compatibility(
    signals: FormalSignals,
    gripper_state: np.ndarray,
    motion_state: np.ndarray,
    left_start: int,
    left_end: int,
    right_start: int,
    right_end: int,
    config: G1P2Config,
) -> float:
    """Interpretable weighted score. Not a learned classifier.

    Priority: gripper > translation/speed > direction > rotation > action.
    """

    score = 0.0
    left_grip = int(_mean_state(gripper_state, left_start, left_end) >= 0.5)
    right_grip = int(_mean_state(gripper_state, right_start, right_end) >= 0.5)
    if left_grip == right_grip:
        score += 100.0
    left_move = int(_mean_state(motion_state, left_start, left_end) >= 0.5)
    right_move = int(_mean_state(motion_state, right_start, right_end) >= 0.5)
    if left_move == right_move:
        score += 50.0
    else:
        speed_l = _mean_state(signals.translation_speed, left_start, left_end)
        speed_r = _mean_state(signals.translation_speed, right_start, right_end)
        score += 50.0 * max(0.0, 1.0 - abs(speed_l - speed_r) / 0.2)
    vec_l = heading_vector(signals, left_start, left_end + 1)
    vec_r = heading_vector(signals, right_start, right_end + 1)
    angle = heading_angle(vec_l, vec_r)
    if angle is None:
        score += 5.0
    else:
        score += 25.0 * max(0.0, 1.0 - angle / max(float(config.direction_compatibility_threshold), 1e-6))
    rot_l = _mean_state(signals.eef_angular_speed_rad_s, left_start, left_end)
    rot_r = _mean_state(signals.eef_angular_speed_rad_s, right_start, right_end)
    score += 10.0 * max(0.0, 1.0 - abs(rot_l - rot_r) / 0.5)
    act_l = _mean_state(signals.action_change_magnitude, left_start, left_end)
    act_r = _mean_state(signals.action_change_magnitude, right_start, right_end)
    score += 5.0 * max(0.0, 1.0 - abs(act_l - act_r) / 1.0)
    return float(score)


def _is_hard_event(event: BoundaryEvent | None) -> bool:
    return event is not None and event.candidate_type == CANDIDATE_GRIPPER


def build_segments_from_events(
    events: list[BoundaryEvent],
    signals: FormalSignals,
    config: G1P2Config,
    *,
    extra_flags: dict[tuple[int, int], list[str]] | None = None,
) -> list[UnlabeledSegment]:
    n = int(signals.n_frames)
    dt = float(signals.dt_s)
    bounds = _active_events(events)
    cuts = [0] + [int(event.frame) for event in bounds if 0 < int(event.frame) < n] + [n]
    # unique ordered cut points as segment starts; last is exclusive end sentinel
    unique: list[int] = []
    for frame in cuts:
        if not unique or frame != unique[-1]:
            unique.append(frame)
    if unique[-1] != n:
        unique.append(n)
    segments: list[UnlabeledSegment] = []
    native = signals.native_episode_key
    extra_flags = extra_flags or {}
    for index, (start, end_exclusive) in enumerate(zip(unique, unique[1:]), start=1):
        end = int(end_exclusive) - 1
        duration = end - start + 1
        left_event = None if start == 0 else next((item for item in bounds if item.frame == start), None)
        right_event = None if end_exclusive == n else next((item for item in bounds if item.frame == end_exclusive), None)
        left_id = EPISODE_START if left_event is None else left_event.boundary_id
        right_id = EPISODE_END if right_event is None else right_event.boundary_id
        left_reason = EPISODE_START if left_event is None else left_event.reason
        right_reason = EPISODE_END if right_event is None else right_event.reason
        flags = list(extra_flags.get((start, end), []))
        short = duration < int(config.min_segment_length)
        long = duration > int(config.max_segment_length)
        if short:
            flags.append(FLAG_SHORT_SEGMENT)
        if long:
            flags.append(FLAG_LONG_SEGMENT)
        review = any(
            flag in flags
            for flag in (FLAG_SHORT_SEGMENT, FLAG_MICRO_INTERACTION, FLAG_LONG_INTERNAL, FLAG_REVIEW_REQUIRED)
        )
        segments.append(
            UnlabeledSegment(
                segment_id=f"{native}-S{index:04d}",
                source_episode_id=signals.source_episode_id,
                start_frame=int(start),
                end_frame=int(end),
                duration_frames=int(duration),
                duration_sec=float(duration) * dt,
                left_boundary_id=left_id,
                right_boundary_id=right_id,
                left_boundary_reason=left_reason,
                right_boundary_reason=right_reason,
                segmentation_version=config.segmentation_version,
                config_version=config.config_version,
                short_segment_flag=short,
                long_segment_flag=long,
                review_required=review,
                review_flags=flags,
            )
        )
    return segments


def apply_hard_micro_flags(
    events: list[BoundaryEvent],
    decisions: dict[str, BoundaryDecision],
    config: G1P2Config,
) -> dict[tuple[int, int], list[str]]:
    """Opposite nearby Hard Boundaries stay separate and are flagged for review."""

    extra: dict[tuple[int, int], list[str]] = {}
    active = _active_events(events)
    window = int(config.min_segment_length)
    for left, right in zip(active, active[1:]):
        if not (_is_hard_event(left) and _is_hard_event(right)):
            continue
        if left.polarity == right.polarity:
            continue
        gap = int(right.frame) - int(left.frame)
        if gap >= window:
            continue
        for event in (left, right):
            if FLAG_MICRO_INTERACTION not in event.review_flags:
                event.review_flags.append(FLAG_MICRO_INTERACTION)
            if FLAG_REVIEW_REQUIRED not in event.review_flags:
                event.review_flags.append(FLAG_REVIEW_REQUIRED)
            _mark_candidates(
                decisions,
                event,
                DECISION_RETAIN_HARD,
                "nearby opposite hard gripper transitions retained; MICRO_INTERACTION / REVIEW_REQUIRED",
            )
        extra[(int(left.frame), int(right.frame) - 1)] = [FLAG_MICRO_INTERACTION, FLAG_REVIEW_REQUIRED]
    return extra


def apply_short_segment_merges(
    events: list[BoundaryEvent],
    decisions: dict[str, BoundaryDecision],
    signals: FormalSignals,
    motion_state: np.ndarray,
    gripper_state: np.ndarray,
    config: G1P2Config,
) -> None:
    min_len = int(config.min_segment_length)
    n = int(signals.n_frames)
    safety = 0
    while safety < n + 2:
        safety += 1
        extra = apply_hard_micro_flags(events, decisions, config)
        segments = build_segments_from_events(events, signals, config, extra_flags=extra)
        merged = False
        for seg in sorted(segments, key=lambda item: item.duration_frames):
            if seg.duration_frames >= min_len:
                continue
            if seg.left_boundary_id == EPISODE_START and seg.right_boundary_id == EPISODE_END:
                continue
            left_event = _event_by_id(events, seg.left_boundary_id)
            right_event = _event_by_id(events, seg.right_boundary_id)
            left_hard = _is_hard_event(left_event)
            right_hard = _is_hard_event(right_event)
            if left_hard and right_hard:
                continue
            options: list[tuple[str, float, BoundaryEvent]] = []
            if left_event is not None and not left_hard:
                prev_start = 0
                active = _active_events(events)
                idx = next((i for i, item in enumerate(active) if item.boundary_id == left_event.boundary_id), None)
                if idx is not None and idx > 0:
                    prev_start = int(active[idx - 1].frame)
                score = _neighbor_compatibility(
                    signals,
                    gripper_state,
                    motion_state,
                    prev_start,
                    seg.start_frame - 1 if seg.start_frame > 0 else 0,
                    seg.start_frame,
                    seg.end_frame,
                    config,
                )
                options.append(("left", score, left_event))
            if right_event is not None and not right_hard:
                active = _active_events(events)
                idx = next((i for i, item in enumerate(active) if item.boundary_id == right_event.boundary_id), None)
                next_end = n - 1
                if idx is not None and idx + 1 < len(active):
                    next_end = int(active[idx + 1].frame) - 1
                score = _neighbor_compatibility(
                    signals,
                    gripper_state,
                    motion_state,
                    seg.start_frame,
                    seg.end_frame,
                    min(n - 1, seg.end_frame + 1),
                    next_end,
                    config,
                )
                options.append(("right", score, right_event))
            if not options:
                if left_hard or right_hard:
                    target = left_event if left_hard else right_event
                    if target is not None:
                        _mark_candidates(
                            decisions,
                            target,
                            DECISION_RETAIN_HARD,
                            "hard boundary protected from ordinary length-guard deletion",
                        )
                        if FLAG_REVIEW_REQUIRED not in target.review_flags:
                            target.review_flags.append(FLAG_REVIEW_REQUIRED)
                continue
            options.sort(key=lambda item: (-item[1], item[0]))
            side, _, target = options[0]
            target.active = False
            decision = DECISION_MERGE_LEFT if side == "left" else DECISION_MERGE_RIGHT
            _mark_candidates(
                decisions,
                target,
                decision,
                f"short segment {seg.segment_id} merged toward more compatible {side} neighbor",
            )
            merged = True
            break
        if not merged:
            break


def apply_max_length_audit(
    segments: list[UnlabeledSegment],
    candidates: list[BoundaryCandidate],
    config: G1P2Config,
) -> None:
    max_len = int(config.max_segment_length)
    for seg in segments:
        if seg.duration_frames <= max_len:
            continue
        seg.long_segment_flag = True
        if FLAG_LONG_SEGMENT not in seg.review_flags:
            seg.review_flags.append(FLAG_LONG_SEGMENT)
        internal = [
            cand
            for cand in candidates
            if seg.start_frame < int(cand.frame) < seg.end_frame
        ]
        if internal:
            if FLAG_LONG_INTERNAL not in seg.review_flags:
                seg.review_flags.append(FLAG_LONG_INTERNAL)
            seg.review_required = True
        # Audit only: no forced split.


def run_boundary_engine(signals: FormalSignals, config: G1P2Config) -> EngineResult:
    motion_state = binarize_motion_state(
        signals.translation_speed, config.motion_speed_threshold
    )
    gripper_state = binarize_gripper_state(signals.gripper_aperture, config.gripper_state_threshold)
    candidates = generate_raw_candidates(signals, motion_state, gripper_state, config)
    if not candidates:
        decisions: dict[str, BoundaryDecision] = {}
        events: list[BoundaryEvent] = []
        segments = build_segments_from_events(events, signals, config)
        apply_max_length_audit(segments, candidates, config)
        review = any(seg.review_required for seg in segments)
        return EngineResult(
            episode_id=signals.source_episode_id,
            native_episode_key=signals.native_episode_key,
            n_frames=int(signals.n_frames),
            dt_s=float(signals.dt_s),
            motion_state=motion_state,
            gripper_state=gripper_state,
            candidates=candidates,
            decisions=decisions,
            events=events,
            segments=segments,
            config_metadata=config.metadata(),
            review_required=review,
        )

    decisions = debounce_candidates(candidates, config)
    attach_supporting_evidence(candidates, signals, config)
    events = consolidate_candidates(candidates, decisions, config)
    pause_bridge_events(events, decisions, signals, gripper_state, config)
    apply_short_segment_merges(events, decisions, signals, motion_state, gripper_state, config)
    extra = apply_hard_micro_flags(events, decisions, config)
    segments = build_segments_from_events(events, signals, config, extra_flags=extra)
    apply_max_length_audit(segments, candidates, config)
    # Recompute short/long flags after merges (already encoded in latest segments).
    review = any(seg.review_required for seg in segments) or any(
        FLAG_REVIEW_REQUIRED in event.review_flags for event in events if event.active
    )
    return EngineResult(
        episode_id=signals.source_episode_id,
        native_episode_key=signals.native_episode_key,
        n_frames=int(signals.n_frames),
        dt_s=float(signals.dt_s),
        motion_state=motion_state,
        gripper_state=gripper_state,
        candidates=candidates,
        decisions=decisions,
        events=events,
        segments=segments,
        config_metadata=config.metadata(),
        review_required=review,
    )
