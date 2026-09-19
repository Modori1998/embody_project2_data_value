"""Full Formal Signal audit plots. Shared x-axis = frame / timestep.

Boundary overlay arguments default to None so G1-P1 can still plot signals
without segmentation. G1-P2 passes Candidate / Suppressed / Final overlays.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .privileged_audit import PrivilegedAuditOverlay
from .signals import FormalSignals


def _as_frame_list(frames: Iterable[int] | None) -> list[int]:
    if frames is None:
        return []
    out: list[int] = []
    seen: set[int] = set()
    for frame in frames:
        value = int(frame)
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _draw_boundaries(
    axes: Sequence,
    *,
    candidate_boundaries: Iterable[int] | None,
    suppressed_boundaries: Iterable[int] | None,
    final_boundaries: Iterable[int] | None,
) -> None:
    specs = (
        (_as_frame_list(candidate_boundaries), "#d97706", "--", 1.15, 0.55, "candidate_boundary"),
        (_as_frame_list(suppressed_boundaries), "#6b7280", ":", 1.6, 0.9, "suppressed_boundary"),
        (_as_frame_list(final_boundaries), "#b91c1c", "-", 2.05, 0.95, "final_boundary"),
    )
    labeled: set[str] = set()
    top = axes[0]
    y_max = top.get_ylim()[1]
    for frames, color, linestyle, width, alpha, label in specs:
        if not frames:
            continue
        for ax in axes:
            use_label = label if label not in labeled else None
            first = True
            for frame in frames:
                ax.axvline(
                    int(frame),
                    color=color,
                    linestyle=linestyle,
                    linewidth=width,
                    alpha=alpha,
                    label=use_label if first else None,
                    zorder=6,
                )
                first = False
                use_label = None
            labeled.add(label)
        marker = {"candidate_boundary": "o", "suppressed_boundary": "x", "final_boundary": "v"}[label]
        top.scatter(
            frames,
            np.full(len(frames), y_max, dtype=np.float64),
            color=color,
            marker=marker,
            s=36 if label != "final_boundary" else 52,
            zorder=8,
            clip_on=False,
        )


def _annotate_finals(ax, annotations: Sequence[tuple[int, str]] | None) -> None:
    if not annotations:
        return
    y0, y1 = ax.get_ylim()
    span = y1 - y0 if y1 > y0 else 1.0
    for index, (frame, reason) in enumerate(annotations):
        offset = 0.04 + 0.08 * (index % 4)
        ax.annotate(
            f"{int(frame)} {reason}",
            xy=(int(frame), y1),
            xytext=(int(frame), y1 - offset * span),
            textcoords="data",
            fontsize=8,
            color="#7f1d1d",
            rotation=90,
            ha="right",
            va="top",
            zorder=9,
        )


def plot_episode_signals(
    signals: FormalSignals,
    output_path: str | Path,
    *,
    privileged: PrivilegedAuditOverlay | None = None,
    candidate_boundaries: Iterable[int] | None = None,
    suppressed_boundaries: Iterable[int] | None = None,
    final_boundaries: Iterable[int] | None = None,
    final_boundary_annotations: Sequence[tuple[int, str]] | None = None,
    motion_state_evidence: np.ndarray | None = None,
    title: str | None = None,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    x = signals.frame_index
    n_rows = 9 if privileged is not None else 8
    fig, axes = plt.subplots(
        n_rows,
        1,
        figsize=(18, 3.05 * n_rows),
        sharex=True,
        constrained_layout=True,
    )
    resolved_title = title or (
        f"G1 Formal Signal Audit  |  {signals.source_episode_id}  |  "
        f"T={signals.n_frames}  |  dt={signals.dt_s:.3f}s (20 Hz)"
    )
    fig.suptitle(resolved_title, fontsize=16, fontweight="bold")

    ax = axes[0]
    ax.plot(x, signals.eef_x, label="eef_x", linewidth=1.8)
    ax.plot(x, signals.eef_y, label="eef_y", linewidth=1.8)
    ax.plot(x, signals.eef_z, label="eef_z", linewidth=1.8)
    ax.set_ylabel("EEF pos (m)", fontsize=12)
    ax.set_title("1. EEF position x/y/z", fontsize=13, loc="left")
    ax.legend(fontsize=10, loc="upper right")
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    ax.plot(x, signals.translation_step_norm, color="#1d4ed8", label="translation_step_norm (m)", linewidth=1.6)
    ax.set_ylabel("step (m)", fontsize=12, color="#1d4ed8")
    ax2 = ax.twinx()
    ax2.plot(x, signals.translation_speed, color="#b45309", label="translation_speed (m/s)", linewidth=1.5)
    ax2.plot(
        x,
        signals.smoothed_translation_speed,
        color="#7c2d12",
        linestyle="--",
        label="smoothed_speed (exploratory)",
        linewidth=1.3,
    )
    ax2.set_ylabel("speed (m/s)", fontsize=12, color="#b45309")
    ax.set_title("2. translation_step_norm / translation_speed", fontsize=13, loc="left")
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc="upper right")
    ax.grid(True, alpha=0.3)

    ax = axes[2]
    motion = motion_state_evidence
    if motion is None:
        motion = signals.motion_state_candidate
    if motion is None:
        motion = np.zeros(len(x), dtype=np.float64)
    ax.step(x, np.asarray(motion, dtype=np.float64), where="post", color="#0f766e", linewidth=1.8, label="motion_state_evidence")
    ax.set_ylabel("moving=1", fontsize=12)
    ax.set_ylim(-0.15, 1.25)
    ax.set_title(
        "3. Motion state evidence (exploratory speed threshold; not Frozen Config)",
        fontsize=13,
        loc="left",
    )
    ax.legend(fontsize=10, loc="upper right")
    ax.grid(True, alpha=0.3)

    ax = axes[3]
    ax.plot(x, signals.direction_change_evidence, color="#6d28d9", linewidth=1.7, label="direction_change_evidence")
    ax.set_ylabel("rad", fontsize=12)
    ax.set_title(
        "4. Main-direction change evidence (windowed 3D heading; threshold DATA_CALIBRATION_PENDING)",
        fontsize=13,
        loc="left",
    )
    ax.legend(fontsize=10, loc="upper right")
    ax.grid(True, alpha=0.3)

    ax = axes[4]
    ax.plot(x, signals.gripper_state_raw[:, 0], label="gripper_qpos[0]", linewidth=1.6)
    ax.plot(x, signals.gripper_state_raw[:, 1], label="gripper_qpos[1]", linewidth=1.6)
    ax.plot(x, signals.gripper_aperture, label="aperture=q0-q1 (not OPEN/CLOSED)", linewidth=1.4, linestyle="--")
    ax.set_ylabel("qpos", fontsize=12)
    ax2 = ax.twinx()
    ax2.plot(x, signals.gripper_change_evidence, color="#be185d", alpha=0.75, label="gripper_change_evidence")
    ax2.set_ylabel("||Δqpos||", fontsize=12, color="#be185d")
    ax.set_title("5. gripper qpos / gripper state evidence", fontsize=13, loc="left")
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc="upper right")
    ax.grid(True, alpha=0.3)

    ax = axes[5]
    ax.plot(x, signals.gripper_command_raw, color="#0f766e", linewidth=1.7, label="gripper_command_raw")
    ax.set_ylabel("command", fontsize=12, color="#0f766e")
    ax2 = ax.twinx()
    ax2.plot(x, signals.gripper_command_change, color="#155e75", linestyle="--", label="gripper_command_change")
    ax2.set_ylabel("|Δ command|", fontsize=12, color="#155e75")
    ax.set_title("6. gripper command (ACTION_t channel 6, normalized)", fontsize=13, loc="left")
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc="upper right")
    ax.grid(True, alpha=0.3)

    ax = axes[6]
    ax.plot(x, signals.eef_rotation_delta_rad, color="#1e40af", label="eef_rotation_delta_rad", linewidth=1.6)
    ax.set_ylabel("rad", fontsize=12, color="#1e40af")
    ax2 = ax.twinx()
    ax2.plot(x, signals.eef_angular_speed_rad_s, color="#4338ca", linestyle="--", label="eef_angular_speed_rad_s")
    ax2.set_ylabel("rad/s", fontsize=12, color="#4338ca")
    ax.set_title("7. EEF rotation delta / angular speed (SUPPORTING EVIDENCE ONLY)", fontsize=13, loc="left")
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc="upper right")
    ax.grid(True, alpha=0.3)

    ax = axes[7]
    ax.plot(x, signals.action_change_magnitude, color="#374151", linewidth=1.7, label="action_change_magnitude")
    ax.set_ylabel("||Δa||", fontsize=12)
    ax.set_title(
        "8. recorded action change magnitude (SUPPORTING EVIDENCE ONLY; normalized command, not physical velocity)",
        fontsize=13,
        loc="left",
    )
    ax.legend(fontsize=10, loc="upper right")
    ax.grid(True, alpha=0.3)

    if privileged is not None:
        ax = axes[8]
        ax.plot(x, privileged.can_pos[:, 0], label="Can_pos_x")
        ax.plot(x, privileged.can_pos[:, 1], label="Can_pos_y")
        ax.plot(x, privileged.can_pos[:, 2], label="Can_pos_z")
        ax.set_ylabel("Can_pos (m)", fontsize=12)
        ax.set_title(
            "PRIVILEGED_AUDIT_ONLY / NOT_USED_BY_SEGMENTER  |  Can_pos overlay",
            fontsize=13,
            loc="left",
            color="#991b1b",
        )
        ax.legend(fontsize=10, loc="upper right")
        ax.grid(True, alpha=0.3)

    axes[-1].set_xlabel("frame / timestep  (shared x-axis; RGB_t = PROPRIO_t = ACTION_t)", fontsize=13)
    for ax in axes:
        ax.tick_params(labelsize=10)
        ax.set_xlim(0, max(int(signals.n_frames) - 1, 0))

    _draw_boundaries(
        axes,
        candidate_boundaries=candidate_boundaries,
        suppressed_boundaries=suppressed_boundaries,
        final_boundaries=final_boundaries,
    )
    _annotate_finals(axes[0], final_boundary_annotations)
    if any((candidate_boundaries, suppressed_boundaries, final_boundaries)):
        handles, labels = axes[0].get_legend_handles_labels()
        unique_handles = []
        unique_labels = []
        seen = set()
        for handle, label in zip(handles, labels):
            if label in seen:
                continue
            seen.add(label)
            unique_handles.append(handle)
            unique_labels.append(label)
        if unique_handles:
            axes[0].legend(unique_handles, unique_labels, fontsize=9, loc="upper right")

    fig.savefig(output, dpi=140)
    plt.close(fig)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"signal plot was not written: {output}")
    return output
