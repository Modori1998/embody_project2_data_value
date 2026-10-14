import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from project2_g3.g3d_paired import verified_frames, score_pairs
from project2_g3.g3d_paired import motion_block
from types import SimpleNamespace
import numpy as np


def test_rgb_hash_fail_closed(tmp_path):
    row = {"segment_id": "demo_2-S0003", "start_frame": "63", "end_frame": "106",
           "target_keyframes": "63;84;106", "frame_png_sha256s": ";".join(["0" * 64] * 3)}
    with pytest.raises(ValueError, match="STOP_RGB_SHA_MISMATCH"):
        verified_frames(row, tmp_path)


def test_multievent_scoring_counts_events_separately():
    row = {"segment_id": "s", "human": {"motion_phase": "transport", "events": ["grasp_attempt", "object_motion"]},
           "A": {"motion_phase": "grasp", "events": [{"event_type": "grasp_attempt"}]},
           "B": {"motion_phase": "transport", "events": [{"event_type": "grasp_attempt"}, {"event_type": "object_motion"}]}}
    score = score_pairs([row])
    assert score["A"]["by_type"]["object_motion"]["fn"] == 1
    assert score["B"]["by_type"]["object_motion"]["tp"] == 1
    assert score["segments"][0]["event_comparison"] == "B_only"


def test_motion_block_has_endpoints_and_actual_transition():
    segment = {"segment_id": "demo_1-S0001", "source_episode_id": "data/demo_1",
               "start_frame": 0, "end_frame": 2, "duration_frames": 3, "duration_sec": 0.15,
               "segmentation_version": "frozen", "config_version": "frozen"}
    episode = SimpleNamespace(source_episode_id="data/demo_1",
        eef_pos=np.array([[0., 0., 0.], [0.1, 0., 0.], [0.2, 0., 0.]]),
        gripper_qpos=np.array([[0.04, -0.04], [0.04, -0.04], [0.01, -0.01]]),
        actions=np.zeros((3, 7)))
    block = motion_block(segment, episode, gripper_state=np.array([1, 1, 0]))
    assert '"eef_start_xyz_m": [0.0, 0.0, 0.0]' in block
    assert '"eef_end_xyz_m": [0.2, 0.0, 0.0]' in block
    assert '"gripper_state_change_within_segment": true' in block
    with pytest.raises(ValueError, match="STOP_EPISODE_IDENTITY"):
        motion_block({**segment, "source_episode_id": "data/demo_2"}, episode,
                     gripper_state=np.array([1, 1, 0]))
