"""Formal G1 signal calculator.

This module computes robot-side Formal Base Signals only.
It must not read simulator object GT, reward, done, success, or future obs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .config import ExploratoryRuntimeDefaults, G1P1Config
from .source import ACTION_DIMENSION_NAMES, FormalEpisodeArrays


FORMAL_SIGNAL_ROLE = {
    "eef_x": "Layer1 kinematics / primary translation evidence",
    "eef_y": "Layer1 kinematics / primary translation evidence",
    "eef_z": "Layer1 kinematics / primary translation evidence",
    "delta_x": "Layer1 realized translation step",
    "delta_y": "Layer1 realized translation step",
    "delta_z": "Layer1 realized translation step",
    "translation_step_norm": "Layer1 realized translation magnitude",
    "translation_speed": "Layer1 realized translation speed",
    "smoothed_translation_speed": "Layer1 evidence (smoothing exploratory only)",
    "direction_change_evidence": "Layer1 main-direction change continuous evidence",
    "gripper_state_raw": "Layer2 realized gripper state",
    "gripper_aperture": "Layer2 derived aperture (not OPEN/CLOSED)",
    "gripper_change_evidence": "Layer2 gripper transition evidence",
    "gripper_command_raw": "Layer3 command intent gripper channel",
    "gripper_command_change": "Layer3 command-change evidence",
    "eef_rotation_delta_rad": "Supporting evidence only: EEF orientation geodesic delta",
    "eef_angular_speed_rad_s": "Supporting evidence only: EEF angular speed",
    "action_raw": "Layer3 source-native recorded action",
    "action_delta": "Layer3 command delta",
    "action_change_magnitude": "Layer3 command-change magnitude; supporting only",
}


@dataclass
class FormalSignals:
    source_episode_id: str
    native_episode_key: str
    n_frames: int
    dt_s: float
    frame_index: np.ndarray
    eef_x: np.ndarray
    eef_y: np.ndarray
    eef_z: np.ndarray
    delta_x: np.ndarray
    delta_y: np.ndarray
    delta_z: np.ndarray
    translation_step_norm: np.ndarray
    translation_speed: np.ndarray
    smoothed_translation_speed: np.ndarray
    direction_change_evidence: np.ndarray
    gripper_state_raw: np.ndarray
    gripper_aperture: np.ndarray
    gripper_change_evidence: np.ndarray
    gripper_command_raw: np.ndarray
    gripper_command_change: np.ndarray
    eef_rotation_delta_rad: np.ndarray
    eef_angular_speed_rad_s: np.ndarray
    action_raw: np.ndarray
    action_delta: np.ndarray
    action_change_magnitude: np.ndarray
    action_dimension_names: tuple[str, ...] = ACTION_DIMENSION_NAMES
    motion_state_candidate: np.ndarray | None = None
    motion_state_candidate_meta: dict[str, Any] = field(default_factory=dict)
    numerical_issues: list[dict[str, Any]] = field(default_factory=list)
    catalog: list[dict[str, str]] = field(default_factory=list)

    def arrays_for_quality_check(self) -> dict[str, np.ndarray]:
        payload = {
            "eef_x": self.eef_x,
            "eef_y": self.eef_y,
            "eef_z": self.eef_z,
            "delta_x": self.delta_x,
            "delta_y": self.delta_y,
            "delta_z": self.delta_z,
            "translation_step_norm": self.translation_step_norm,
            "translation_speed": self.translation_speed,
            "smoothed_translation_speed": self.smoothed_translation_speed,
            "direction_change_evidence": self.direction_change_evidence,
            "gripper_state_raw": self.gripper_state_raw,
            "gripper_aperture": self.gripper_aperture,
            "gripper_change_evidence": self.gripper_change_evidence,
            "gripper_command_raw": self.gripper_command_raw,
            "gripper_command_change": self.gripper_command_change,
            "eef_rotation_delta_rad": self.eef_rotation_delta_rad,
            "eef_angular_speed_rad_s": self.eef_angular_speed_rad_s,
            "action_raw": self.action_raw,
            "action_delta": self.action_delta,
            "action_change_magnitude": self.action_change_magnitude,
        }
        if self.motion_state_candidate is not None:
            payload["motion_state_candidate"] = self.motion_state_candidate
        return payload


def moving_average(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 1:
        return np.asarray(values, dtype=np.float64)
    kernel = np.ones(int(window), dtype=np.float64) / float(window)
    padded = np.pad(np.asarray(values, dtype=np.float64), (window - 1, 0), mode="edge")
    return np.convolve(padded, kernel, mode="valid")[: len(values)]


def unit_quaternions(quaternions: np.ndarray) -> np.ndarray:
    quaternions = np.asarray(quaternions, dtype=np.float64)
    if quaternions.ndim == 1:
        quaternions = quaternions[None, :]
    norms = np.linalg.norm(quaternions, axis=1, keepdims=True)
    out = np.full_like(quaternions, np.nan, dtype=np.float64)
    valid = np.isfinite(quaternions).all(axis=1) & np.isfinite(norms[:, 0]) & (norms[:, 0] > 0)
    out[valid] = quaternions[valid] / norms[valid]
    return out


def quaternion_geodesic_angle(q_a: np.ndarray, q_b: np.ndarray) -> np.ndarray:
    """Sign-invariant geodesic angle in radians.

    q and -q represent the same orientation, so |dot| is used.
    rotation(q, q) = 0 and rotation(q, -q) = 0.
    """

    a = unit_quaternions(q_a)
    b = unit_quaternions(q_b)
    dots = np.sum(a * b, axis=1)
    abs_dots = np.clip(np.abs(dots), 0.0, 1.0)
    return 2.0 * np.arccos(abs_dots)


def consecutive_quaternion_delta(quaternions: np.ndarray) -> np.ndarray:
    quaternions = np.asarray(quaternions, dtype=np.float64)
    n = len(quaternions)
    out = np.zeros(n, dtype=np.float64)
    if n < 2:
        return out
    out[1:] = quaternion_geodesic_angle(quaternions[:-1], quaternions[1:])
    return out


def pad_backward_diff(values: np.ndarray) -> np.ndarray:
    """Observation-aligned backward difference.

    delta[0] = 0
    delta[t] = x[t] - x[t-1]  for t >= 1

    This does not shift EEF[t] / Action[t] themselves. It answers "how did
    the observed quantity change in arriving at frame t".
    """

    values = np.asarray(values, dtype=np.float64)
    out = np.zeros_like(values, dtype=np.float64)
    if len(values) < 2:
        return out
    out[1:] = values[1:] - values[:-1]
    return out


def window_direction_change_evidence(
    delta_xyz: np.ndarray,
    *,
    window_frames: int,
    min_window_displacement_m: float,
) -> np.ndarray:
    """Continuous 3D heading-change evidence for later window-based comparison.

    Uses vector-summed translation over left/right windows, not single-axis
    sign flips. Thresholding this score is DATA_CALIBRATION_PENDING.
    """

    delta_xyz = np.asarray(delta_xyz, dtype=np.float64)
    n = len(delta_xyz)
    evidence = np.zeros(n, dtype=np.float64)
    if n == 0 or window_frames <= 0:
        return evidence
    for t in range(n):
        left = delta_xyz[max(0, t - window_frames) : t]
        right = delta_xyz[t : min(n, t + window_frames)]
        if len(left) == 0 or len(right) == 0:
            continue
        v_left = np.sum(left, axis=0)
        v_right = np.sum(right, axis=0)
        n_left = float(np.linalg.norm(v_left))
        n_right = float(np.linalg.norm(v_right))
        if n_left < min_window_displacement_m or n_right < min_window_displacement_m:
            continue
        cosine = float(np.dot(v_left, v_right) / (n_left * n_right))
        evidence[t] = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    return evidence


def _catalog_row(name: str, source: str, formula: str, alignment: str, unit: str, role: str) -> dict[str, str]:
    return {
        "name": name,
        "source": source,
        "formula": formula,
        "index_alignment": alignment,
        "unit": unit,
        "role": role,
    }


def compute_formal_signals(
    episode: FormalEpisodeArrays,
    config: G1P1Config,
    *,
    include_motion_state_candidate: bool = True,
) -> FormalSignals:
    dt = float(config.dt)
    pos = np.asarray(episode.eef_pos, dtype=np.float64)
    quat = np.asarray(episode.eef_quat, dtype=np.float64)
    gripper = np.asarray(episode.gripper_qpos, dtype=np.float64)
    actions = np.asarray(episode.actions, dtype=np.float64)
    n = len(pos)
    delta = pad_backward_diff(pos)
    step = np.linalg.norm(delta, axis=1)
    speed = step / dt
    exploratory: ExploratoryRuntimeDefaults = config.exploratory
    smoothed = moving_average(speed, exploratory.smoothed_speed_window_frames)
    direction = window_direction_change_evidence(
        delta,
        window_frames=exploratory.direction_window_frames,
        min_window_displacement_m=exploratory.direction_min_window_displacement_m,
    )
    gripper_delta = pad_backward_diff(gripper)
    gripper_change = np.linalg.norm(gripper_delta.reshape(n, -1), axis=1)
    aperture = gripper[:, 0] - gripper[:, 1]
    gripper_command = actions[:, 6]
    gripper_command_change = np.abs(pad_backward_diff(gripper_command))
    rotation_delta = consecutive_quaternion_delta(quat)
    angular_speed = rotation_delta / dt
    action_delta = pad_backward_diff(actions)
    action_change = np.linalg.norm(action_delta, axis=1)

    motion_candidate = None
    motion_meta: dict[str, Any] = {
        "status": "EXPERIMENTAL / CALIBRATION_PENDING",
        "not_formal": True,
        "used_for_pass_fail": False,
    }
    if include_motion_state_candidate:
        motion_candidate = (
            smoothed > float(exploratory.motion_speed_threshold_m_s)
        ).astype(np.int8)
        motion_meta.update(
            {
                "threshold_m_s": exploratory.motion_speed_threshold_m_s,
                "threshold_status": "exploratory",
                "definition": "1 if smoothed_translation_speed > exploratory threshold else 0",
            }
        )

    catalog = [
        _catalog_row(
            "eef_x/y/z",
            "obs/robot0_eef_pos",
            "eef_pos[t, i]",
            "t aligned with RGB_t / ACTION_t / PROPRIO_t",
            "meter",
            FORMAL_SIGNAL_ROLE["eef_x"],
        ),
        _catalog_row(
            "delta_x/y/z",
            "obs/robot0_eef_pos",
            "delta[0]=0; delta[t]=pos[t]-pos[t-1]",
            "same t; no action/eef/rgb shift",
            "meter",
            FORMAL_SIGNAL_ROLE["delta_x"],
        ),
        _catalog_row(
            "translation_step_norm",
            "obs/robot0_eef_pos",
            "norm(delta_xyz[t])",
            "same t",
            "meter",
            FORMAL_SIGNAL_ROLE["translation_step_norm"],
        ),
        _catalog_row(
            "translation_speed",
            "obs/robot0_eef_pos + dt=0.05s",
            "step_norm[t] / 0.05",
            "same t",
            "meter / second",
            FORMAL_SIGNAL_ROLE["translation_speed"],
        ),
        _catalog_row(
            "smoothed_translation_speed",
            "translation_speed",
            "causal moving average, exploratory window",
            "same t",
            "meter / second",
            FORMAL_SIGNAL_ROLE["smoothed_translation_speed"],
        ),
        _catalog_row(
            "direction_change_evidence",
            "3D translation delta windows",
            "angle(sum(delta[t-W:t]), sum(delta[t:t+W])); not single-axis sign flip",
            "same t; window edges padded by available frames",
            "radian",
            FORMAL_SIGNAL_ROLE["direction_change_evidence"],
        ),
        _catalog_row(
            "gripper_state_raw",
            "obs/robot0_gripper_qpos",
            "qpos[t]",
            "same t",
            "source-native finger joints",
            FORMAL_SIGNAL_ROLE["gripper_state_raw"],
        ),
        _catalog_row(
            "gripper_aperture",
            "obs/robot0_gripper_qpos",
            "qpos[t,0] - qpos[t,1]",
            "same t",
            "source-native (not frozen OPEN/CLOSED)",
            FORMAL_SIGNAL_ROLE["gripper_aperture"],
        ),
        _catalog_row(
            "gripper_change_evidence",
            "obs/robot0_gripper_qpos",
            "norm(qpos[t]-qpos[t-1])",
            "same t",
            "source-native",
            FORMAL_SIGNAL_ROLE["gripper_change_evidence"],
        ),
        _catalog_row(
            "gripper_command_raw",
            "actions[:,6]",
            "recorded OSC_POSE gripper command channel",
            "ACTION_t",
            "NORMALIZED_CONTROLLER_INPUT",
            FORMAL_SIGNAL_ROLE["gripper_command_raw"],
        ),
        _catalog_row(
            "gripper_command_change",
            "actions[:,6]",
            "abs(cmd[t]-cmd[t-1])",
            "ACTION_t",
            "NORMALIZED_CONTROLLER_INPUT",
            FORMAL_SIGNAL_ROLE["gripper_command_change"],
        ),
        _catalog_row(
            "eef_rotation_delta_rad",
            "obs/robot0_eef_quat",
            "2*arccos(abs(dot(q[t-1], q[t]))) after unit-normalize; q and -q equivalent",
            "same t",
            "radian",
            FORMAL_SIGNAL_ROLE["eef_rotation_delta_rad"],
        ),
        _catalog_row(
            "eef_angular_speed_rad_s",
            "eef_rotation_delta_rad / dt",
            "rotation_delta[t] / 0.05",
            "same t",
            "radian / second",
            FORMAL_SIGNAL_ROLE["eef_angular_speed_rad_s"],
        ),
        _catalog_row(
            "action_raw",
            "source-native actions",
            "actions[t] 7D OSC_POSE",
            "ACTION_t",
            "NORMALIZED_CONTROLLER_INPUT; translation output scale 0.05 m, rotation 0.5 rad are controller maps, not claimed physical velocity of this recorded stream",
            FORMAL_SIGNAL_ROLE["action_raw"],
        ),
        _catalog_row(
            "action_delta",
            "actions",
            "action[0]=0-pad; action[t]-action[t-1]",
            "ACTION_t",
            "NORMALIZED_CONTROLLER_INPUT",
            FORMAL_SIGNAL_ROLE["action_delta"],
        ),
        _catalog_row(
            "action_change_magnitude",
            "actions",
            "L2_norm(action_delta[t])",
            "ACTION_t",
            "NORMALIZED_CONTROLLER_INPUT magnitude",
            FORMAL_SIGNAL_ROLE["action_change_magnitude"],
        ),
    ]

    signals = FormalSignals(
        source_episode_id=episode.source_episode_id,
        native_episode_key=episode.native_episode_key,
        n_frames=n,
        dt_s=dt,
        frame_index=np.asarray(episode.frame_index, dtype=np.int64),
        eef_x=pos[:, 0],
        eef_y=pos[:, 1],
        eef_z=pos[:, 2],
        delta_x=delta[:, 0],
        delta_y=delta[:, 1],
        delta_z=delta[:, 2],
        translation_step_norm=step,
        translation_speed=speed,
        smoothed_translation_speed=smoothed,
        direction_change_evidence=direction,
        gripper_state_raw=gripper,
        gripper_aperture=aperture,
        gripper_change_evidence=gripper_change,
        gripper_command_raw=gripper_command,
        gripper_command_change=gripper_command_change,
        eef_rotation_delta_rad=rotation_delta,
        eef_angular_speed_rad_s=angular_speed,
        action_raw=actions,
        action_delta=action_delta,
        action_change_magnitude=action_change,
        motion_state_candidate=motion_candidate,
        motion_state_candidate_meta=motion_meta,
        catalog=catalog,
    )
    signals.numerical_issues = collect_numerical_issues(signals)
    return signals


def collect_numerical_issues(signals: FormalSignals) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for name, array in signals.arrays_for_quality_check().items():
        finite = np.isfinite(array)
        n_nan = int(np.isnan(array).sum())
        n_inf = int(np.isinf(array).sum())
        if n_nan or n_inf:
            issues.append(
                {
                    "signal": name,
                    "nan": n_nan,
                    "inf": n_inf,
                    "length": int(array.size),
                    "finite_fraction": float(finite.mean()) if array.size else 1.0,
                    "policy": "reported; not silently replaced with 0",
                }
            )
    return issues
