"""Focused checks for G3G Pilot request identity and Task A QC."""

import hashlib
import json

from scripts import run_g3g_pilot as G
from project2_g3 import semantic_schema as S


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


def test_schema_protocol_changes_only_task_b_and_is_arm_independent():
    for arm in ("4B", "8B"):
        assert arm in G.EXPECTED
        assert G.response_format("A", True) == {"type": "json_object"}
        assert G.response_format("B", True) == {
            "type": "json_object", "schema": S.json_schema_v0_2()}
        assert G.response_format("B", False) == {"type": "json_object"}


def test_development_uses_frozen_twelve_segment_order():
    frozen = json.loads((G.FROZEN / "run_manifest.json").read_text(encoding="utf-8"))
    assert G.selected_segments(frozen, False) == G.SEGMENTS
    selected = G.selected_segments(frozen, True)
    assert len(selected) == len(set(selected)) == 12
    assert set(G.SEGMENTS) <= set(selected)
    frozen["cohorts"]["microset"]["segments"] = selected[:11]
    try:
        G.selected_segments(frozen, True)
    except ValueError as exc:
        assert "STOP_FROZEN_DEVELOPMENT_COHORT_DRIFT" in str(exc)
    else:
        raise AssertionError("Expected frozen cohort drift stop")
