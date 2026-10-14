import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from project2_g3 import semantic_prompt as P  # noqa: E402
from project2_g3 import semantic_schema as S  # noqa: E402
from project2_g3.phase_event_qc import (  # noqa: E402
    PHASE_EVENT_QC_VERSION, check_phase_event_consistency, review_annotation,
)

FROZEN_V021_SHA = "11b874a3daba9d42398a50bef8473c01924a672f06acda09e0ac3933110e53b4"


def payload(**over):
    base = {"motion_phase": "approach", "object_relation": ["gripper_around"],
            "gripper_state": "open", "event_assessment": "event_visible",
            "events": [{"event_type": "grasp_attempt", "event_outcome": "unclear",
                        "evidence_frame_indices": [1, 2]}],
            "evidence_frame_indices": [1, 2], "evidence_quality": "sufficient",
            "observation_note": "Robot approaches the can."}
    base.update(over)
    return base


def ids(findings):
    return sorted(f.check_id for f in findings)


# --- prompt versioning ----------------------------------------------------- #
def test_v0_2_1_prompt_is_byte_identical_to_frozen():
    assert P.template_sha256_v0_2_1() == FROZEN_V021_SHA
    assert "长距离的连续搬运可能确实" in P.PROMPT_TEMPLATE_V0_2_1


def test_v0_2_2_removes_conflict_and_adds_self_check_but_keeps_contract():
    assert "长距离的连续搬运可能确实" not in P.PROMPT_TEMPLATE_V0_2_2
    assert "输出前一致性自检" in P.PROMPT_TEMPLATE_V0_2_2
    assert P.template_sha256_v0_2_2() != P.template_sha256_v0_2_1()
    # contract must not drift: every required key and every v0.2 enum value stays
    # (both blocks are rendered from the frozen schema at render time)
    assert "{required_fields}" in P.PROMPT_TEMPLATE_V0_2_2
    assert "{enums}" in P.PROMPT_TEMPLATE_V0_2_2
    rendered_fields = P.render_required_fields_v0_2()
    for key in S.MODEL_OWNED_FIELDS_V0_2:
        assert key in rendered_fields
    rendered_enums = P.render_enum_block_v0_2()
    for values in S.ENUM_TABLE_V0_2.values():
        for value in values:
            assert value in rendered_enums
    # exactly the two anchored changes, no other line touched
    diff = P.template_diff_v0_2_1_v0_2_2()
    assert diff.count("\n-") == 1 and diff.count("- 长距离") == 1


def test_prompt_version_registry_fails_closed():
    assert P.prompt_version_info("v0_2_1")["prompt_template_sha256"] == FROZEN_V021_SHA
    assert P.prompt_version_info("v0_2_2")["prompt_version"].endswith("V0_2_2_CANDIDATE")
    with pytest.raises(ValueError, match="STOP_UNKNOWN_PROMPT_VERSION"):
        P.prompt_version_info("v9")


# --- QC rules -------------------------------------------------------------- #
def test_rule_a_transport_without_object_motion():
    found = check_phase_event_consistency(payload(motion_phase="transport",
        events=[{"event_type": "grasp_attempt", "event_outcome": "unclear",
                 "evidence_frame_indices": [1, 2]}]))
    assert ids(found) == ["PHASE_OBJECT_MOTION_MISSING_CANDIDATE"]
    assert found[0].scope == "CANDIDATE"
    assert not check_phase_event_consistency(payload(motion_phase="transport",
        events=[{"event_type": "object_motion"}]))


def test_rule_b_moving_with_gripper_without_object_motion():
    found = check_phase_event_consistency(payload(object_relation=["moving_with_gripper"],
        events=[]))
    assert "RELATION_OBJECT_MOTION_MISSING_CANDIDATE" in ids(found)


def test_rule_c_requires_explicit_static_denial():
    # explicit denial + object_motion -> conflict
    found = check_phase_event_consistency(payload(observation_note="The can remains static during approach.",
        events=[{"event_type": "object_motion"}]))
    assert "OBJECT_MOTION_NOTE_CONFLICT_CANDIDATE" in ids(found)
    # mere absence of a motion mention -> no conflict
    assert "OBJECT_MOTION_NOTE_CONFLICT_CANDIDATE" not in ids(check_phase_event_consistency(
        payload(observation_note="Robot approaches the can with open gripper.",
                events=[{"event_type": "object_motion"}])))


def test_rule_d_does_not_fire_on_closed_state_alone():
    # closed gripper with grasp_attempt but no denial -> no conflict
    assert ids(check_phase_event_consistency(payload(gripper_state="closed",
        observation_note="Gripper closes around the can."))) == []
    # explicit denial of the grasp process -> conflict
    assert "GRASP_EVENT_NOTE_CONFLICT_CANDIDATE" in ids(check_phase_event_consistency(
        payload(observation_note="No visible grasp or object motion occurs within the segment.")))
    # outcome uncertainty is NOT a process denial (regression: pilot false alert)
    assert ids(check_phase_event_consistency(payload(
        observation_note="夹爪闭合并接触物体，但尚未明确是否被成功抓取。"))) == []
    # configuration-static + explicit no-event denial -> conflict
    assert "GRASP_EVENT_NOTE_CONFLICT_CANDIDATE" in ids(check_phase_event_consistency(
        payload(observation_note="Gripper remains closed throughout; no visible motion observed.")))


def test_qc_is_non_destructive_and_versioned():
    original = payload(motion_phase="transport", observation_note="The object remains stationary.")
    snapshot = copy.deepcopy(original)
    review = review_annotation(original)
    assert original == snapshot
    assert review["phase_event_qc_version"] == PHASE_EVENT_QC_VERSION
    assert review["review_status"] == "REVIEW_CANDIDATE"
    assert review_annotation(payload())["review_status"] == "NO_FINDING"
