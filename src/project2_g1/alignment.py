"""Temporal alignment and numerical audits for Formal signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .signals import FormalSignals
from .source import FormalEpisodeArrays


@dataclass
class AlignmentAudit:
    status: str
    checks: list[dict[str, Any]]

    @property
    def passed(self) -> bool:
        return self.status == "PASS" and all(item["status"] == "PASS" for item in self.checks)


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "status": "PASS" if ok else "FAIL", "detail": detail}


def audit_temporal_alignment(
    episode: FormalEpisodeArrays,
    signals: FormalSignals,
    *,
    rgb_frame_count: int | None = None,
) -> AlignmentAudit:
    n = int(episode.eef_pos.shape[0])
    checks = [
        _check(
            "source_length_consistency",
            len(episode.eef_pos)
            == len(episode.eef_quat)
            == len(episode.gripper_qpos)
            == len(episode.actions)
            == len(episode.frame_index),
            f"T={n}",
        ),
        _check(
            "signal_length_matches_source",
            signals.n_frames == n
            and len(signals.frame_index) == n
            and len(signals.eef_x) == n
            and len(signals.translation_speed) == n
            and len(signals.action_change_magnitude) == n
            and len(signals.gripper_command_raw) == n,
            f"signals.n_frames={signals.n_frames}",
        ),
        _check(
            "frame_index_is_0_to_T_minus_1",
            np.array_equal(signals.frame_index, np.arange(n)),
            f"frame_index[:3]={signals.frame_index[:3].tolist()} last={int(signals.frame_index[-1]) if n else 'NA'}",
        ),
        _check(
            "eef_not_shifted",
            np.allclose(signals.eef_x, episode.eef_pos[:, 0])
            and np.allclose(signals.eef_y, episode.eef_pos[:, 1])
            and np.allclose(signals.eef_z, episode.eef_pos[:, 2]),
            "eef_* copies obs/robot0_eef_pos[t] without t+1 shift",
        ),
        _check(
            "action_not_shifted",
            np.allclose(signals.action_raw, episode.actions),
            "action_raw copies actions[t] without t+1 shift",
        ),
        _check(
            "backward_diff_definition",
            n < 2
            or (
                np.allclose(signals.delta_x[0], 0.0)
                and np.allclose(signals.delta_x[1], episode.eef_pos[1, 0] - episode.eef_pos[0, 0])
            ),
            "delta[0]=0; delta[t]=pos[t]-pos[t-1]",
        ),
        _check(
            "action_dim_7",
            episode.actions.shape == (n, 7),
            f"actions.shape={episode.actions.shape}",
        ),
    ]
    if rgb_frame_count is not None:
        checks.append(
            _check(
                "rgb_or_video_frame_count",
                int(rgb_frame_count) == n,
                f"video_frames={rgb_frame_count} vs T={n}",
            )
        )
    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    return AlignmentAudit(status=status, checks=checks)


def audit_nan_inf(signals: FormalSignals) -> dict[str, Any]:
    if signals.numerical_issues:
        return {
            "status": "FAIL",
            "policy": "issues reported, not silently zero-filled",
            "issues": signals.numerical_issues,
        }
    return {
        "status": "PASS",
        "policy": "NaN=0 and Inf=0 required for core derived signals; source anomalies would be reported",
        "issues": [],
    }
