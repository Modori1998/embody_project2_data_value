"""MVP-M2 deterministic keyframes and raw robot motion summaries.

Only policy-visible robot-side inputs are accepted here.  Retrieval scaling,
normalization, embeddings, and similarity are deliberately out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import numpy as np

from project2_g1.boundary_engine import CANDIDATE_GRIPPER, UnlabeledSegment
from project2_g1.source import FormalEpisodeArrays


MOTION_FEATURE_VERSION = "MVP_M2_MOTION_FEATURE_V1"
MOTION_DIRECTION_EPSILON_M = 1.0e-9
ALLOWED_FORMAL_INPUT_FIELDS = frozenset({"eef_pos", "gripper_qpos", "actions"})
FORBIDDEN_INPUT_TOKENS = frozenset(
    {"object", "can_pos", "can_quat", "reward", "done", "success", "next_obs", "states"}
)


@dataclass(frozen=True)
class SelectedKeyframe:
    frame_index: int
    roles: tuple[str, ...]

    @property
    def roles_text(self) -> str:
        return "|".join(self.roles)


def assert_no_privileged_inputs(field_names: Iterable[str]) -> None:
    """Fail closed if an M2 caller declares any privileged source field."""

    normalized = {str(name).strip().lower() for name in field_names}
    forbidden = sorted(
        name for name in normalized if any(token in name for token in FORBIDDEN_INPUT_TOKENS)
    )
    unexpected = sorted(name for name in normalized if name not in ALLOWED_FORMAL_INPUT_FIELDS)
    if forbidden or unexpected:
        raise ValueError(
            "MVP_M2_PRIVILEGED_OR_UNAPPROVED_INPUT: "
            f"forbidden={forbidden} unexpected={unexpected}"
        )


def select_keyframes(
    segment: UnlabeledSegment | Mapping[str, Any],
    *,
    left_boundary_type: str | None,
) -> tuple[SelectedKeyframe, ...]:
    """Select START/MIDDLE/END and optional left GRIPPER_EVENT, deduped by frame."""

    get = (lambda key: getattr(segment, key)) if not isinstance(segment, Mapping) else segment.__getitem__
    start = int(get("start_frame"))
    end = int(get("end_frame"))
    if start < 0 or end < start:
        raise ValueError(f"MVP_M2_SEGMENT_RANGE_INVALID: start={start} end={end}")
    middle = (start + end) // 2
    by_frame: dict[int, list[str]] = {}
    for frame, role in ((start, "START"), (middle, "MIDDLE"), (end, "END")):
        by_frame.setdefault(frame, []).append(role)
    if left_boundary_type == CANDIDATE_GRIPPER:
        by_frame.setdefault(start, []).append("GRIPPER_EVENT")
    return tuple(
        SelectedKeyframe(frame_index=frame, roles=tuple(roles))
        for frame, roles in sorted(by_frame.items())
    )


def gripper_aperture(gripper_qpos: np.ndarray) -> np.ndarray:
    values = np.asarray(gripper_qpos, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] < 2:
        raise ValueError(f"MVP_M2_GRIPPER_QPOS_SHAPE_INVALID: {values.shape}")
    return values[:, 0] - values[:, 1]


def _direction(displacement: np.ndarray) -> list[float]:
    norm = float(np.linalg.norm(displacement))
    if norm <= MOTION_DIRECTION_EPSILON_M:
        return [0.0, 0.0, 0.0]
    return [float(value) for value in displacement / norm]


def _coarse_direction_change(points: np.ndarray) -> tuple[float | None, bool]:
    # Deterministic non-overlapping halves. Each half needs two positions to
    # define a displacement; incomplete evidence remains NA rather than zero.
    split = len(points) // 2
    first = points[:split]
    second = points[split:]
    if len(first) < 2 or len(second) < 2:
        return None, False
    left = first[-1] - first[0]
    right = second[-1] - second[0]
    left_norm = float(np.linalg.norm(left))
    right_norm = float(np.linalg.norm(right))
    if left_norm <= MOTION_DIRECTION_EPSILON_M or right_norm <= MOTION_DIRECTION_EPSILON_M:
        return None, False
    cosine = float(np.dot(left, right) / (left_norm * right_norm))
    return float(np.arccos(np.clip(cosine, -1.0, 1.0))), True


def summarize_motion(
    segment: UnlabeledSegment | Mapping[str, Any],
    episode: FormalEpisodeArrays,
    *,
    gripper_state: np.ndarray | None,
    left_boundary_type: str | None = None,
) -> dict[str, Any]:
    """Compute raw, interpretable M2 features over an inclusive G1 segment."""

    assert_no_privileged_inputs(ALLOWED_FORMAL_INPUT_FIELDS)
    get = (lambda key: getattr(segment, key)) if not isinstance(segment, Mapping) else segment.__getitem__
    start, end = int(get("start_frame")), int(get("end_frame"))
    expected_duration = end - start + 1
    if int(get("duration_frames")) != expected_duration:
        raise ValueError("MVP_M2_SEGMENT_DURATION_IDENTITY_FAIL")
    n = len(episode.eef_pos)
    if start < 0 or end >= n or end < start:
        raise ValueError(f"MVP_M2_SEGMENT_OUT_OF_RANGE: [{start}, {end}] n={n}")

    pos = np.asarray(episode.eef_pos[start : end + 1], dtype=np.float64)
    displacement = pos[-1] - pos[0]
    steps = np.diff(pos, axis=0)
    path_length = float(np.linalg.norm(steps, axis=1).sum()) if len(steps) else 0.0
    coarse_angle, coarse_complete = _coarse_direction_change(pos)
    aperture = gripper_aperture(episode.gripper_qpos)
    actions = np.asarray(episode.actions[start : end + 1], dtype=np.float64)
    magnitudes = np.linalg.norm(actions, axis=1)

    if gripper_state is None:
        start_state = end_state = "NOT_MATERIALIZED"
        transition_present = False
    else:
        states = np.asarray(gripper_state)
        if len(states) != n:
            raise ValueError("MVP_M2_GRIPPER_STATE_ALIGNMENT_ERROR")
        start_state = "OPEN" if int(states[start]) == 1 else "CLOSED"
        end_state = "OPEN" if int(states[end]) == 1 else "CLOSED"
        transition_present = bool(
            left_boundary_type == CANDIDATE_GRIPPER
            or np.any(states[start + 1 : end + 1] != states[start:end])
        )

    row = {
        "segment_id": str(get("segment_id")),
        "source_episode_id": str(get("source_episode_id")),
        "start_frame": start,
        "end_frame": end,
        "duration_frames": expected_duration,
        "duration_sec": float(get("duration_sec")),
        "eef_net_displacement_m": float(np.linalg.norm(displacement)),
        "eef_path_length_m": path_length,
        "eef_displacement_xyz": [float(value) for value in displacement],
        "eef_main_direction_xyz": _direction(displacement),
        "coarse_direction_change_rad": coarse_angle,
        "coarse_direction_context_complete": coarse_complete,
        "gripper_start_aperture": float(aperture[start]),
        "gripper_end_aperture": float(aperture[end]),
        "gripper_start_state": start_state,
        "gripper_end_state": end_state,
        "gripper_transition_present": transition_present,
        "action_magnitude_mean": float(np.mean(magnitudes)),
        "action_magnitude_max": float(np.max(magnitudes)),
        "action_magnitude_std": float(np.std(magnitudes)),
        "action_semantic": "NORMALIZED_CONTROLLER_INPUT",
        "segmentation_version": str(get("segmentation_version")),
        "config_version": str(get("config_version")),
        "feature_version": MOTION_FEATURE_VERSION,
    }
    numeric = [
        row["duration_sec"], row["eef_net_displacement_m"], row["eef_path_length_m"],
        *row["eef_displacement_xyz"], *row["eef_main_direction_xyz"],
        row["gripper_start_aperture"], row["gripper_end_aperture"],
        row["action_magnitude_mean"], row["action_magnitude_max"], row["action_magnitude_std"],
    ]
    if not np.isfinite(np.asarray(numeric, dtype=np.float64)).all():
        raise ValueError("MVP_M2_MOTION_FEATURE_NONFINITE")
    if coarse_angle is not None and not np.isfinite(coarse_angle):
        raise ValueError("MVP_M2_COARSE_DIRECTION_NONFINITE")
    return row
