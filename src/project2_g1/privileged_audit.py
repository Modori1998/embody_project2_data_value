"""Privileged Audit Overlay.

PRIVILEGED_AUDIT_ONLY
NOT_USED_BY_SEGMENTER

This pipeline is structurally separate from Formal Signal calculation.
It may read simulator object GT to help a human see where the can moved.
It must not be imported by the Formal calculator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

# Packed Can/MH obs/object layout from P1 M07 semantic reconstruction:
# [0:3]=Can_to_robot0_eef_pos, [3:7]=Can_to_robot0_eef_quat,
# [7:10]=Can_pos, [10:14]=Can_quat
CAN_TO_EEF_POS = slice(0, 3)
CAN_TO_EEF_QUAT = slice(3, 7)
CAN_POS = slice(7, 10)
CAN_QUAT = slice(10, 14)

OVERLAY_FLAGS = {
    "visibility": "PRIVILEGED_AUDIT_ONLY",
    "used_by_segmenter": False,
    "label": "PRIVILEGED_AUDIT_ONLY / NOT_USED_BY_SEGMENTER",
}


@dataclass(frozen=True)
class PrivilegedAuditOverlay:
    source_episode_id: str
    n_frames: int
    object_packed: np.ndarray
    can_pos: np.ndarray
    can_quat: np.ndarray
    can_to_eef_pos: np.ndarray
    rewards: np.ndarray
    dones: np.ndarray
    flags: dict[str, Any]


def load_privileged_overlay(adapter, source_episode_id: str) -> PrivilegedAuditOverlay:
    reference = adapter.get_privileged_reference(source_episode_id)
    packed = np.asarray(reference["object"], dtype=np.float64)
    if packed.ndim != 2 or packed.shape[1] != 14:
        raise ValueError(f"unexpected privileged object shape: {packed.shape}")
    return PrivilegedAuditOverlay(
        source_episode_id=adapter.get_source_episode_id(source_episode_id),
        n_frames=len(packed),
        object_packed=packed,
        can_pos=packed[:, CAN_POS],
        can_quat=packed[:, CAN_QUAT],
        can_to_eef_pos=packed[:, CAN_TO_EEF_POS],
        rewards=np.asarray(reference["rewards"], dtype=np.float64),
        dones=np.asarray(reference["dones"], dtype=np.float64),
        flags=dict(OVERLAY_FLAGS),
    )
