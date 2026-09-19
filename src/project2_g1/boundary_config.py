"""G1-P2 exploratory segmentation config.

All numeric values are EXPLORATORY / DATA_CALIBRATION_PENDING / NOT_FORMAL.
This is not Frozen Config and must not be described as FINAL / OPTIMAL / BEST.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import G1_P2_CONFIG_PATH

PARAM_STATUS = "EXPLORATORY"
DATA_CALIBRATION_STATUS = "DATA_CALIBRATION_PENDING"


def _param(payload: dict[str, Any], key: str, default: float | int) -> float | int:
    block = payload.get(key, default)
    if isinstance(block, dict):
        return block.get("value", default)
    return block


@dataclass(frozen=True)
class G1P2Config:
    phase: str = "G1-P2"
    status: str = PARAM_STATUS
    formal: bool = False
    not_formal: bool = True
    data_calibration_status: str = DATA_CALIBRATION_STATUS
    segmentation_status: str = "EXPLORATORY_ONLY"
    config_version: str = "g1_p2_exploratory_segmentation.v0"
    segmentation_version: str = "G1-P2-EXPLORATORY-v0"
    motion_speed_threshold: float = 0.02
    motion_persistence_frames: int = 4
    direction_change_threshold: float = 1.2
    direction_persistence_frames: int = 3
    gripper_state_threshold: float = 0.06
    gripper_persistence_frames: int = 4
    debounce_frames: int = 4
    boundary_consolidation_window: int = 8
    pause_bridge_duration: int = 10
    min_segment_length: int = 8
    max_segment_length: int = 80
    boundary_tolerance_window: int = 5
    rotation_support_threshold: float = 0.015
    action_support_threshold: float = 0.5
    support_window_frames: int = 8
    direction_compatibility_threshold: float = 0.8
    direction_window_frames: int = 8
    direction_min_window_displacement_m: float = 0.005
    smoke_episode_count: int = 6
    max_smoke_length_frames: int = 400
    must_include_p1_demos: tuple[str, ...] = ("demo_0", "demo_32", "demo_179", "demo_278")
    must_include_worse: bool = True
    preferred_worse_demo: str = "demo_242"
    raw: dict[str, Any] = field(default_factory=dict)

    def marked_parameters(self) -> list[dict[str, Any]]:
        rows = [
            ("motion_speed_threshold", self.motion_speed_threshold, "m/s"),
            ("motion_persistence_frames", self.motion_persistence_frames, "frame"),
            ("direction_change_threshold", self.direction_change_threshold, "radian"),
            ("direction_persistence_frames", self.direction_persistence_frames, "frame"),
            ("gripper_state_threshold", self.gripper_state_threshold, "source-native aperture"),
            ("gripper_persistence_frames", self.gripper_persistence_frames, "frame"),
            ("debounce_frames", self.debounce_frames, "frame"),
            ("boundary_consolidation_window", self.boundary_consolidation_window, "frame"),
            ("pause_bridge_duration", self.pause_bridge_duration, "frame"),
            ("min_segment_length", self.min_segment_length, "frame"),
            ("max_segment_length", self.max_segment_length, "frame"),
            ("boundary_tolerance_window", self.boundary_tolerance_window, "frame"),
            ("rotation_support_threshold", self.rotation_support_threshold, "radian"),
            ("action_support_threshold", self.action_support_threshold, "normalized command magnitude"),
            ("support_window_frames", self.support_window_frames, "frame"),
            ("direction_compatibility_threshold", self.direction_compatibility_threshold, "radian"),
            ("direction_window_frames", self.direction_window_frames, "frame"),
            ("direction_min_window_displacement_m", self.direction_min_window_displacement_m, "meter"),
        ]
        return [
            {
                "name": name,
                "value": value,
                "unit": unit,
                "status": PARAM_STATUS,
                "formal": False,
                "not_formal": True,
                "data_calibration_status": DATA_CALIBRATION_STATUS,
            }
            for name, value, unit in rows
        ]

    def metadata(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "status": self.status,
            "formal": self.formal,
            "not_formal": self.not_formal,
            "data_calibration_status": self.data_calibration_status,
            "segmentation_status": self.segmentation_status,
            "config_version": self.config_version,
            "segmentation_version": self.segmentation_version,
            "boundary_tolerance_window_used_by_segmenter": False,
        }


def load_g1_p2_config(path: str | Path | None = None) -> G1P2Config:
    config_path = Path(path) if path is not None else G1_P2_CONFIG_PATH
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    params = payload.get("parameters", {})
    smoke = payload.get("smoke", {})
    return G1P2Config(
        phase=str(payload.get("phase", "G1-P2")),
        status=str(payload.get("status", PARAM_STATUS)),
        formal=bool(payload.get("formal", False)),
        not_formal=bool(payload.get("not_formal", True)),
        data_calibration_status=str(
            payload.get("data_calibration_status", DATA_CALIBRATION_STATUS)
        ),
        segmentation_status=str(payload.get("segmentation_status", "EXPLORATORY_ONLY")),
        config_version=str(payload.get("config_version", "g1_p2_exploratory_segmentation.v0")),
        segmentation_version=str(payload.get("segmentation_version", "G1-P2-EXPLORATORY-v0")),
        motion_speed_threshold=float(_param(params, "motion_speed_threshold", 0.02)),
        motion_persistence_frames=int(_param(params, "motion_persistence_frames", 4)),
        direction_change_threshold=float(_param(params, "direction_change_threshold", 1.2)),
        direction_persistence_frames=int(_param(params, "direction_persistence_frames", 3)),
        gripper_state_threshold=float(_param(params, "gripper_state_threshold", 0.06)),
        gripper_persistence_frames=int(_param(params, "gripper_persistence_frames", 4)),
        debounce_frames=int(_param(params, "debounce_frames", 4)),
        boundary_consolidation_window=int(_param(params, "boundary_consolidation_window", 8)),
        pause_bridge_duration=int(_param(params, "pause_bridge_duration", 10)),
        min_segment_length=int(_param(params, "min_segment_length", 8)),
        max_segment_length=int(_param(params, "max_segment_length", 80)),
        boundary_tolerance_window=int(_param(params, "boundary_tolerance_window", 5)),
        rotation_support_threshold=float(_param(params, "rotation_support_threshold", 0.015)),
        action_support_threshold=float(_param(params, "action_support_threshold", 0.5)),
        support_window_frames=int(_param(params, "support_window_frames", 8)),
        direction_compatibility_threshold=float(
            _param(params, "direction_compatibility_threshold", 0.8)
        ),
        direction_window_frames=int(_param(params, "direction_window_frames", 8)),
        direction_min_window_displacement_m=float(
            _param(params, "direction_min_window_displacement_m", 0.005)
        ),
        smoke_episode_count=int(smoke.get("episode_count", 6)),
        max_smoke_length_frames=int(smoke.get("max_smoke_length_frames", 400)),
        must_include_p1_demos=tuple(smoke.get("must_include_p1_demos", ["demo_0"])),
        must_include_worse=bool(smoke.get("must_include_worse", True)),
        preferred_worse_demo=str(smoke.get("preferred_worse_demo", "demo_242")),
        raw=payload,
    )
