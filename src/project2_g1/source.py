"""Read-only reuse of Project 1 RoboMimic HDF5 Source Adapter.

This module does not define a competing schema. All temporal / action / proprio
semantics come from the frozen P1 contract and adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .config import G1P1Config
from .paths import ensure_project1_on_path


FORMAL_PROPRIO_KEYS = (
    "robot0_eef_pos",
    "robot0_eef_quat",
    "robot0_gripper_qpos",
    "robot0_joint_pos",
)
OPTIONAL_PROPRIO_KEYS = (
    "robot0_joint_vel",
    "robot0_gripper_qvel",
)
ACTION_DIMENSION_NAMES = (
    "translation_delta_x",
    "translation_delta_y",
    "translation_delta_z",
    "rotation_delta_x",
    "rotation_delta_y",
    "rotation_delta_z",
    "gripper_command",
)


@dataclass(frozen=True)
class EpisodeIdentity:
    source_episode_id: str
    native_episode_key: str
    episode_index: int
    num_steps: int


@dataclass(frozen=True)
class FormalEpisodeArrays:
    """Policy-visible arrays only. Privileged GT is never stored here."""

    source_episode_id: str
    native_episode_key: str
    frame_index: np.ndarray
    eef_pos: np.ndarray
    eef_quat: np.ndarray
    gripper_qpos: np.ndarray
    joint_pos: np.ndarray
    actions: np.ndarray
    provenance: dict[str, Any]


def build_can_mh_adapter(config: G1P1Config):
    ensure_project1_on_path()
    from project1_benchmark.robomimic_adapter import (
        RoboMimicCollectionType,
        RoboMimicHDF5SourceAdapter,
    )

    raw = Path(config.raw_hdf5)
    low = Path(config.low_dim_hdf5)
    if not raw.is_file():
        raise FileNotFoundError(f"READ_ONLY raw HDF5 missing: {raw}")
    if not low.is_file():
        raise FileNotFoundError(f"READ_ONLY low_dim HDF5 missing: {low}")
    return RoboMimicHDF5SourceAdapter(
        raw,
        low,
        source_profile=RoboMimicCollectionType.CAN_MH,
        rgb_hdf5=None,
    )


def enumerate_episodes(adapter) -> tuple[EpisodeIdentity, ...]:
    return tuple(
        EpisodeIdentity(
            source_episode_id=item.source_episode_id,
            native_episode_key=item.native_episode_key,
            episode_index=item.episode_index,
            num_steps=item.num_steps,
        )
        for item in adapter.enumerate_episodes()
    )


def load_formal_episode(adapter, source_episode_id: str) -> FormalEpisodeArrays:
    """Load Formal G1 inputs only: proprio + recorded action.

    RGB is not stored in Can/MH low_dim. Video uses P1 state renderer separately.
    Privileged object/reward/done/next_obs/states are not loaded here.
    """

    proprio = adapter.get_robot_proprio(source_episode_id)
    actions = np.asarray(adapter.get_action_sequence(source_episode_id), dtype=np.float64)
    eef_pos = np.asarray(proprio["robot0_eef_pos"], dtype=np.float64)
    eef_quat = np.asarray(proprio["robot0_eef_quat"], dtype=np.float64)
    gripper = np.asarray(proprio["robot0_gripper_qpos"], dtype=np.float64)
    joint_pos = np.asarray(proprio["robot0_joint_pos"], dtype=np.float64)
    lengths = {
        "eef_pos": len(eef_pos),
        "eef_quat": len(eef_quat),
        "gripper_qpos": len(gripper),
        "joint_pos": len(joint_pos),
        "actions": len(actions),
    }
    if len(set(lengths.values())) != 1:
        raise ValueError(f"TEMPORAL_ALIGNMENT_ERROR: length mismatch {lengths}")
    count = int(lengths["actions"])
    native_key = source_episode_id.split("/")[-1]
    return FormalEpisodeArrays(
        source_episode_id=adapter.get_source_episode_id(source_episode_id),
        native_episode_key=native_key,
        frame_index=np.arange(count, dtype=np.int64),
        eef_pos=eef_pos,
        eef_quat=eef_quat,
        gripper_qpos=gripper,
        joint_pos=joint_pos,
        actions=actions,
        provenance=adapter.get_provenance(source_episode_id),
    )


def inspect_source_schema(adapter, source_episode_id: str = "demo_0") -> list[dict[str, Any]]:
    """Read-only schema listing of fields that actually exist."""

    h5py = _require_h5py()
    native = source_episode_id.split("/")[-1]
    rows: list[dict[str, Any]] = []
    with h5py.File(adapter.raw_hdf5, "r") as raw, h5py.File(adapter.low_dim_hdf5, "r") as low:
        raw_ep = raw["data"][native]
        low_ep = low["data"][native]
        for key, dataset in raw_ep.items():
            rows.append(_schema_row(f"raw/{key}", dataset, _raw_semantic(key)))
        for key, dataset in low_ep.items():
            if key in ("obs", "next_obs"):
                continue
            rows.append(_schema_row(f"low_dim/{key}", dataset, _low_semantic(key)))
        for key, dataset in low_ep["obs"].items():
            rows.append(_schema_row(f"low_dim/obs/{key}", dataset, _obs_semantic(key)))
        for key, dataset in low_ep["next_obs"].items():
            rows.append(
                _schema_row(
                    f"low_dim/next_obs/{key}",
                    dataset,
                    "TRANSITION_RESULT obs[t+1]; forbidden Formal G1 input",
                    role="privileged",
                )
            )
    return rows


def _schema_row(field: str, dataset: Any, meaning: str, role: str | None = None) -> dict[str, Any]:
    array = dataset
    shape = tuple(int(x) for x in getattr(array, "shape", ()))
    dtype = str(getattr(array, "dtype", "unknown"))
    if role is None:
        role = "privileged" if _is_privileged_field(field) else "formal_or_supporting"
    return {
        "field": field,
        "shape": shape,
        "dtype": dtype,
        "semantic_meaning": meaning,
        "unit_if_verified": _unit_for_field(field),
        "formal_or_privileged": role,
    }


def _is_privileged_field(field: str) -> bool:
    name = field.lower()
    return any(
        token in name
        for token in (
            "/object",
            "next_obs",
            "reward",
            "done",
            "states",
            "success",
        )
    )


def _unit_for_field(field: str) -> str:
    if field.endswith("robot0_eef_pos"):
        return "meter (P1 freeze)"
    if field.endswith("robot0_eef_quat"):
        return "unit quaternion XYZW (P1/M07 provenance)"
    if "gripper_qpos" in field:
        return "Panda finger joint position (source-native, meter-scale aperture joints)"
    if field.endswith("actions") or field.endswith("/actions"):
        return "NORMALIZED_CONTROLLER_INPUT (not claimed as meter/rad physical velocity)"
    if "joint_pos" in field and "cos" not in field and "sin" not in field:
        return "radian (Panda joint position)"
    return "UNVERIFIED / source-native"


def _raw_semantic(key: str) -> str:
    return {
        "actions": "source-native recorded 7D OSC_POSE command",
        "states": "raw MuJoCo 71D state; privileged",
        "interventions": "teleop intervention flag if present",
        "policy_acting": "teleop metadata if present",
        "user_acting": "teleop metadata if present",
    }.get(key, "raw HDF5 field")


def _low_semantic(key: str) -> str:
    return {
        "actions": "same recorded 7D action as raw (lineage-checked by P1 adapter)",
        "states": "raw MuJoCo 71D state copy; privileged",
        "rewards": "simulator reward; privileged",
        "dones": "simulator done; privileged",
    }.get(key, "low_dim HDF5 field")


def _obs_semantic(key: str) -> str:
    return {
        "robot0_eef_pos": "EEF Cartesian position; Formal G1 kinematics",
        "robot0_eef_quat": "EEF orientation quaternion; Formal supporting rotation evidence",
        "robot0_gripper_qpos": "realized gripper finger state; Formal interaction evidence",
        "robot0_joint_pos": "Panda 7-DoF joint position; Formal proprio, not joint-as-rotation-boundary",
        "robot0_joint_vel": "optional proprio",
        "robot0_gripper_qvel": "optional proprio",
        "robot0_eef_quat_site": "site quaternion; not required Formal G1 input",
        "robot0_joint_pos_cos": "derived joint encoding; not required Formal G1 input",
        "robot0_joint_pos_sin": "derived joint encoding; not required Formal G1 input",
        "object": "packed object GT 14D; PRIVILEGED_AUDIT_ONLY",
    }.get(key, "observation field")


def _require_h5py():
    import h5py

    return h5py
