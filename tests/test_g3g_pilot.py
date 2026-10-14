"""Focused checks for G3G Pilot request identity and Task A QC."""

import hashlib

from scripts import run_g3g_pilot as G


def test_frozen_smoke_prompt_identity():
    prompt = G.task_a_prompt("demo_2-S0003", [63, 84, 106])
    assert hashlib.sha256(prompt.encode()).hexdigest() == G.SMOKE_A_SHA


def test_task_a_rejects_missing_or_wrong_frame_evidence():
    value = {"segment_id": "demo_2-S0003"}
    for key in ("can_visible", "can_position_change", "can_moves_with_gripper",
                "gripper_open_close_change"):
        value[key] = {"answer": "uncertain", "evidence_frame_indices": [], "observation": "unclear"}
    assert G.valid_a(value, "demo_2-S0003", [63, 84, 106])
    value["can_visible"]["evidence_frame_indices"] = [107]
    assert not G.valid_a(value, "demo_2-S0003", [63, 84, 106])
    value["can_visible"]["evidence_frame_indices"] = [63]
    del value["gripper_open_close_change"]
    assert not G.valid_a(value, "demo_2-S0003", [63, 84, 106])
