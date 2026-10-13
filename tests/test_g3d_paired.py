import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from project2_g3.g3d_paired import verified_frames, score_pairs


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
