import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from project2_g3.g3d2_temporal import build_content, interval_state
from project2_g3.semantic_validation import FrameEntry, TargetSegmentIdentity


def fixture():
    segment = SimpleNamespace(segment_id="demo_1-S0001", source_episode_id="data/demo_1",
        start_frame=0, end_frame=4, duration_frames=5, duration_sec=.25,
        segmentation_version="frozen", config_version="frozen")
    episode = SimpleNamespace(source_episode_id="data/demo_1",
        eef_pos=np.array([[i*.1, 0, 0] for i in range(5)]),
        gripper_qpos=np.array([[.04, -.04]]*3 + [[.01, -.01]]*2),
        actions=np.zeros((5, 7)))
    frames = [FrameEntry(i, role, "data/demo_1", "demo_1-S0001", "demo_1-S0001", True, "0"*64)
              for i, role in zip((0, 2, 4), ("START", "MIDDLE", "END"))]
    identity = TargetSegmentIdentity("data/demo_1", "demo_1-S0001", 0, 4)
    return segment, episode, frames, identity


def test_interval_alignment_and_real_change():
    segment, episode, _, _ = fixture()
    items = interval_state(segment=segment, episode=episode,
        gripper_state=np.array([1, 1, 1, 0, 0]), frame_indices=[0, 2, 4], dt_s=.05)
    assert [x["gripper_actual_change_frames"] for x in items] == [[], [3]]
    assert items[0]["eef_end_xyz_m"] == items[1]["eef_start_xyz_m"]
    assert items[0]["start_frame"] == 0 and items[1]["end_frame"] == 4
    with pytest.raises(ValueError, match="STOP_INTERVAL_FRAME_ALIGNMENT"):
        interval_state(segment=segment, episode=episode,
            gripper_state=np.ones(5), frame_indices=[0, 4, 5], dt_s=.05)


def test_actual_interleaving_and_state_matrix():
    segment, episode, frames, identity = fixture()
    args = dict(identity=identity, frames=frames, paths=[Path("0"), Path("2"), Path("4")],
        task_text="pick up the can and place it into the correct box", segment=segment,
        episode=episode, gripper_state=np.array([1, 1, 1, 0, 0]),
        left_boundary_type=None, dt_s=.05,
        image_data_uri=lambda path: "data:image/png;base64,"+path.name)
    old, _ = build_content(group="G0", **args)
    t0, _ = build_content(group="T0", **args)
    g1, state1 = build_content(group="G1", **args)
    t1, state2 = build_content(group="T1", **args)
    t2, state3 = build_content(group="T2", **args)
    assert [x["type"] for x in old] == ["text", "image_url", "image_url", "image_url"]
    assert [x["type"] for x in t0] == ["text", "text", "image_url", "text", "image_url", "text", "image_url"]
    assert [x["image_url"] for x in old if x["type"] == "image_url"] == [x["image_url"] for x in t2 if x["type"] == "image_url"]
    assert state1 == state2 and state1 and state3
    assert t0[0]["text"] == t1[0]["text"][:len(t0[0]["text"])] == t2[0]["text"]
    assert "Interval 1" in t2[3]["text"] and "Interval 2" in t2[5]["text"]
    assert "eef_xyz_m" in t2[1]["text"] and "gripper_aperture_qpos" in t2[1]["text"]
