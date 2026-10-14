"""G3D2 five-arm request construction; v0.2.1 prompt remains immutable."""
from __future__ import annotations

import hashlib
import json

import numpy as np

from project2_g3.g3d_paired import motion_block
from project2_g3.semantic_prompt import render_prompt_v0_2_1
from project2_mvp.m2 import summarize_motion

VERSION = "G3_TEMPORAL_PROMPT_V0_3_CANDIDATE"
GROUPS = ("G0", "G1", "T0", "T1", "T2")
TEMPORAL_INSTRUCTION = """

# Temporal observation task (same frozen JSON schema)
The three RGB frames are chronological. Compare consecutive observations before assigning segment-level labels.
Interval 1 (START to MIDDLE): compare visible gripper configuration, end-effector position, object position and object-gripper relation.
Interval 2 (MIDDLE to END): make the same visual comparison.
Only after both comparisons, choose one dominant motion_phase for the whole frozen Segment, report every visibly supported event, and cite target frame indices. Use uncertain/insufficient when evidence is ambiguous under the frozen schema. Do not output interval fields or hidden reasoning.
A moving end-effector does not prove object_motion. A closed gripper does not prove grasp success. An open gripper approaching an object alone does not prove grasp_attempt. Do not infer an unobserved event merely from a later state. Recorded actions are commands, not observed physical outcomes.
"""


def temporal_base(*, identity, frames, task_text):
    if len(frames) != 3 or not (frames[0].frame_index < frames[1].frame_index < frames[2].frame_index):
        raise ValueError("STOP_TEMPORAL_FRAME_ORDER")
    old = render_prompt_v0_2_1(source_episode_id=identity.source_episode_id,
        segment_id=identity.segment_id, start_frame=identity.start_frame,
        end_frame=identity.end_frame, frames=frames, task_text=task_text)
    return old + TEMPORAL_INSTRUCTION


def interval_state(*, segment, episode, gripper_state, frame_indices, dt_s):
    """M2 formulas on two inclusive RGB intervals; action[t] is unshifted."""
    if episode.source_episode_id != segment.source_episode_id:
        raise ValueError("STOP_EPISODE_IDENTITY")
    if gripper_state is None or len(gripper_state) != len(episode.eef_pos):
        raise ValueError("STOP_GRIPPER_STATE_ALIGNMENT")
    if len(frame_indices) != 3 or not (segment.start_frame <= frame_indices[0] < frame_indices[1] < frame_indices[2] <= segment.end_frame):
        raise ValueError("STOP_INTERVAL_FRAME_ALIGNMENT")
    if not np.isfinite(dt_s) or dt_s <= 0:
        raise ValueError("STOP_TIME_UNIT")
    out = []
    for ordinal, (start, end) in enumerate(zip(frame_indices[:-1], frame_indices[1:]), 1):
        sub = {"segment_id": segment.segment_id, "source_episode_id": segment.source_episode_id,
               "start_frame": start, "end_frame": end, "duration_frames": end-start+1,
               "duration_sec": (end-start+1)*dt_s,
               "segmentation_version": segment.segmentation_version,
               "config_version": segment.config_version}
        features = summarize_motion(sub, episode, gripper_state=gripper_state,
                                    left_boundary_type=None)
        changes = [i for i in range(start+1, end+1) if gripper_state[i] != gripper_state[i-1]]
        item = {"interval": ordinal, "start_frame": start, "end_frame": end,
                "eef_start_xyz_m": [float(v) for v in episode.eef_pos[start]],
                "eef_end_xyz_m": [float(v) for v in episode.eef_pos[end]],
                "eef_displacement_xyz_m": features["eef_displacement_xyz"],
                "eef_net_displacement_m": features["eef_net_displacement_m"],
                "eef_path_length_m": features["eef_path_length_m"],
                "gripper_start_aperture_qpos": features["gripper_start_aperture"],
                "gripper_end_aperture_qpos": features["gripper_end_aperture"],
                "gripper_start_state": features["gripper_start_state"],
                "gripper_end_state": features["gripper_end_state"],
                "gripper_actual_change_frames": changes,
                "action_magnitude_mean": features["action_magnitude_mean"],
                "action_magnitude_max": features["action_magnitude_max"],
                "action_magnitude_std": features["action_magnitude_std"],
                "action_semantic": "NORMALIZED_CONTROLLER_INPUT_UNSHIFTED_ACTION_T"}
        json.dumps(item, allow_nan=False)
        out.append(item)
    return out


def build_content(*, group, identity, frames, paths, task_text, segment, episode,
                  gripper_state, left_boundary_type, dt_s, image_data_uri):
    """Return exact ordered multimodal content plus robot-state text for audit."""
    if group not in GROUPS or len(paths) != 3 or len(frames) != 3:
        raise ValueError("STOP_REQUEST_MATRIX")
    old = render_prompt_v0_2_1(source_episode_id=identity.source_episode_id,
        segment_id=identity.segment_id, start_frame=identity.start_frame,
        end_frame=identity.end_frame, frames=frames, task_text=task_text)
    segment_text = motion_block(segment, episode, gripper_state=gripper_state,
                                left_boundary_type=left_boundary_type) if group in ("G1", "T1") else ""
    intervals = interval_state(segment=segment, episode=episode, gripper_state=gripper_state,
        frame_indices=[f.frame_index for f in frames], dt_s=dt_s) if group == "T2" else []
    if group in ("G0", "G1"):
        content = [{"type": "text", "text": old + segment_text}]
        content.extend({"type": "image_url", "image_url": {"url": image_data_uri(p)}} for p in paths)
    else:
        content = [{"type": "text", "text": temporal_base(identity=identity, frames=frames, task_text=task_text) + segment_text}]
        for i, (frame, path) in enumerate(zip(frames, paths)):
            role = ("START", "MIDDLE", "END")[i]
            label = f"Frame {frame.frame_index} — {role}; target Segment {identity.segment_id}."
            if group == "T2":
                if i == 0:
                    label += " Robot state at this frame is the first endpoint in interval 1."
                else:
                    label += (f"\nInterval {i}: frame {frames[i-1].frame_index} → frame {frame.frame_index}: "
                              + json.dumps(intervals[i-1], sort_keys=True, allow_nan=False)
                              + "\nThis frame is the interval end state."
                              + (" It is also interval 2's start state." if i == 1 else ""))
            content.extend(({"type": "text", "text": label},
                            {"type": "image_url", "image_url": {"url": image_data_uri(path)}}))
    state_text = segment_text if group in ("G1", "T1") else json.dumps(intervals, sort_keys=True, allow_nan=False) if group == "T2" else ""
    return content, state_text


def request_sha(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
