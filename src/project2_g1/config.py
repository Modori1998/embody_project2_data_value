"""G1-P1 config schema. Formal numeric thresholds remain DATA_CALIBRATION_PENDING."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import CONFIG_PATH, DATASET_LOW_DIM_HDF5, DATASET_RAW_HDF5


@dataclass(frozen=True)
class CalibrationPlaceholders:
    """Frozen-design slots. Values are not formal until G1-P3/P4."""

    status: str = "DATA_CALIBRATION_PENDING"
    not_formal: bool = True
    motion_speed_threshold: float | None = None
    motion_persistence_frames: int | None = None
    direction_angle_threshold: float | None = None
    direction_persistence_frames: int | None = None
    gripper_state_threshold: float | None = None
    pause_bridge_duration: float | None = None
    boundary_consolidation_window: int | None = None
    min_segment_length: int | None = None
    max_segment_length: int | None = None
    tolerance_window: int | None = None


@dataclass(frozen=True)
class ExploratoryRuntimeDefaults:
    """Temporary numbers needed to draw / stabilize continuous evidence.

    These are NOT Frozen Config and MUST NOT be used for G1-P1 PASS/FAIL.
    """

    status: str = "exploratory"
    not_formal: bool = True
    used_for_pass_fail: bool = False
    note: str = (
        "Temporary values required for visualization / numerical stability only. "
        "Not Frozen Config."
    )
    smoothed_speed_window_frames: int = 5
    direction_window_frames: int = 8
    direction_min_window_displacement_m: float = 0.005
    heading_min_step_m: float = 0.001
    motion_speed_threshold_m_s: float = 0.02
    motion_persistence_frames: int = 3
    gripper_state_threshold: float | None = None


@dataclass(frozen=True)
class G1P1Config:
    phase: str = "G1-P1"
    control_frequency_hz: float = 20.0
    nominal_dt_s: float = 0.05
    eef_pos_unit: str = "meter"
    action_unit: str = "NORMALIZED_CONTROLLER_INPUT"
    raw_hdf5: Path = DATASET_RAW_HDF5
    low_dim_hdf5: Path = DATASET_LOW_DIM_HDF5
    smoke_episode_count: int = 4
    max_smoke_length_frames: int = 400
    calibration: CalibrationPlaceholders = field(default_factory=CalibrationPlaceholders)
    exploratory: ExploratoryRuntimeDefaults = field(default_factory=ExploratoryRuntimeDefaults)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def dt(self) -> float:
        return float(self.nominal_dt_s)


def load_g1_p1_config(path: str | Path | None = None) -> G1P1Config:
    config_path = Path(path) if path is not None else CONFIG_PATH
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    placeholders = payload.get("calibration_placeholders", {})
    exploratory = payload.get("exploratory_runtime_defaults", {})
    smoke = payload.get("smoke", {})
    return G1P1Config(
        phase=str(payload.get("phase", "G1-P1")),
        control_frequency_hz=float(payload.get("control_frequency_hz", 20.0)),
        nominal_dt_s=float(payload.get("nominal_dt_s", 0.05)),
        eef_pos_unit=str(payload.get("eef_pos_unit", "meter")),
        action_unit=str(payload.get("action_unit", "NORMALIZED_CONTROLLER_INPUT")),
        smoke_episode_count=int(smoke.get("episode_count", 4)),
        max_smoke_length_frames=int(smoke.get("max_smoke_length_frames", 400)),
        calibration=CalibrationPlaceholders(
            status=str(placeholders.get("status", "DATA_CALIBRATION_PENDING")),
            not_formal=bool(placeholders.get("not_formal", True)),
            motion_speed_threshold=placeholders.get("motion_speed_threshold"),
            motion_persistence_frames=placeholders.get("motion_persistence_frames"),
            direction_angle_threshold=placeholders.get("direction_angle_threshold"),
            direction_persistence_frames=placeholders.get("direction_persistence_frames"),
            gripper_state_threshold=placeholders.get("gripper_state_threshold"),
            pause_bridge_duration=placeholders.get("pause_bridge_duration"),
            boundary_consolidation_window=placeholders.get("boundary_consolidation_window"),
            min_segment_length=placeholders.get("min_segment_length"),
            max_segment_length=placeholders.get("max_segment_length"),
            tolerance_window=placeholders.get("tolerance_window"),
        ),
        exploratory=ExploratoryRuntimeDefaults(
            status=str(exploratory.get("status", "exploratory")),
            not_formal=bool(exploratory.get("not_formal", True)),
            used_for_pass_fail=bool(exploratory.get("used_for_pass_fail", False)),
            note=str(exploratory.get("note", "")),
            smoothed_speed_window_frames=int(exploratory.get("smoothed_speed_window_frames", 5)),
            direction_window_frames=int(exploratory.get("direction_window_frames", 8)),
            direction_min_window_displacement_m=float(
                exploratory.get("direction_min_window_displacement_m", 0.005)
            ),
            heading_min_step_m=float(exploratory.get("heading_min_step_m", 0.001)),
            motion_speed_threshold_m_s=float(exploratory.get("motion_speed_threshold_m_s", 0.02)),
            motion_persistence_frames=int(exploratory.get("motion_persistence_frames", 3)),
            gripper_state_threshold=exploratory.get("gripper_state_threshold"),
        ),
        raw=payload,
    )
