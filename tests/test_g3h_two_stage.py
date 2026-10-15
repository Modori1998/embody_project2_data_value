"""Synthetic visual facts; never use the seven G3H Pilot segments."""
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from project2_g3.g3h_two_stage import fact_schema, map_facts, parse_fact_json, validate_facts
from project2_g3.semantic_validation import FrameEntry, TargetSegmentIdentity, validate_model_output_v0_2
from scripts.run_g3h_p1 import SEGMENTS, protocol_identity

SID = "synthetic-S0001"
INDICES = [10, 20, 30]


def facts():
    frames = [{"frame_index": idx, "can_visible": "yes", "can_region": region,
               "can_relative_to_reference": f"{region} of fixed divider",
               "gripper_visible": "yes", "gripper_aperture": "closed",
               "can_gripper_relation": "beneath_gripper"}
              for idx, region in zip(INDICES, ("left", "center", "right"))]
    blank = {"answer": "no", "evidence_frame_indices": []}
    return {"segment_id": SID, "frames": frames, "same_can": "yes",
            "fixed_reference_comparable": "yes", "reference_description": "fixed box divider",
            "can_motion": {"answer": "yes", "direction": "right", "evidence_frame_indices": [10, 30]},
            "moves_with_gripper": {"answer": "yes", "evidence_frame_indices": [10, 30]},
            "closing_near_can": deepcopy(blank), "opening_near_can": deepcopy(blank),
            "gripper_approaches_can": deepcopy(blank), "occlusion": "partial",
            "observation_note": "The same can changes position against the fixed divider."}


def mapped(value):
    assert validate_facts(value, SID, INDICES) == []
    result = map_facts(value, SID, INDICES)
    manifest = [FrameEntry(i, role, "synthetic", SID, SID, True, "0" * 64)
                for i, role in zip(INDICES, ("START", "MIDDLE", "END"))]
    qc = validate_model_output_v0_2(json.dumps(result), manifest=manifest,
           identity=TargetSegmentIdentity("synthetic", SID, 10, 30), finish_reason="stop")
    assert qc.parse_ok and qc.schema_ok and qc.frame_evidence_ok and not qc.truncated, qc.to_dict()
    return result


def events(value):
    return {e["event_type"] for e in mapped(value)["events"]}


def test_can_rightward_motion_and_transport():
    v = facts()
    assert mapped(v)["motion_phase"] == "transport"
    assert events(v) == {"object_motion"}


def test_only_gripper_moves_object_static():
    v = facts()
    v["can_motion"] = {"answer": "no", "direction": "none", "evidence_frame_indices": [10, 30]}
    v["moves_with_gripper"] = {"answer": "no", "evidence_frame_indices": []}
    v["gripper_approaches_can"] = {"answer": "yes", "evidence_frame_indices": [10, 30]}
    assert mapped(v)["motion_phase"] == "approach"
    assert events(v) == set()


def test_can_moves_without_gripper_is_still_object_motion():
    v = facts()
    v["moves_with_gripper"] = {"answer": "no", "evidence_frame_indices": [10, 30]}
    assert mapped(v)["motion_phase"] != "transport"
    assert events(v) == {"object_motion"}


def test_open_or_static_closed_gripper_does_not_trigger_grasp():
    v = facts()
    v["can_motion"] = {"answer": "no", "direction": "none", "evidence_frame_indices": [10, 30]}
    v["moves_with_gripper"] = {"answer": "no", "evidence_frame_indices": []}
    for f in v["frames"]:
        f["gripper_aperture"] = "open"
    assert "grasp_attempt" not in events(v)
    for f in v["frames"]:
        f["gripper_aperture"] = "closed"
    assert "grasp_attempt" not in events(v)


def test_visible_closing_and_multiple_events_preserved():
    v = facts()
    v["closing_near_can"] = {"answer": "yes", "evidence_frame_indices": [10, 20]}
    assert events(v) == {"grasp_attempt", "object_motion"}
    assert mapped(v)["motion_phase"] == "transport"


def test_release_requires_visible_opening():
    v = facts()
    v["can_motion"] = {"answer": "uncertain", "direction": "uncertain", "evidence_frame_indices": []}
    v["moves_with_gripper"] = {"answer": "uncertain", "evidence_frame_indices": []}
    v["opening_near_can"] = {"answer": "uncertain", "evidence_frame_indices": []}
    assert "release_attempt" not in events(v)
    v["opening_near_can"] = {"answer": "yes", "evidence_frame_indices": [20, 30]}
    assert "release_attempt" in events(v)


def test_occlusion_uncertainty_never_becomes_positive_event():
    v = facts()
    v["same_can"] = "uncertain"
    v["fixed_reference_comparable"] = "uncertain"
    v["can_motion"] = {"answer": "uncertain", "direction": "uncertain", "evidence_frame_indices": []}
    v["moves_with_gripper"] = {"answer": "uncertain", "evidence_frame_indices": []}
    v["occlusion"] = "severe"
    result = mapped(v)
    assert result["events"] == []
    assert result["event_assessment"] == "insufficient_evidence"


def test_invalid_frame_reference_and_duplicate_fields_rejected():
    v = facts()
    v["can_motion"]["evidence_frame_indices"] = [10, 99]
    assert "FACT_EVIDENCE_FRAMES:can_motion" in validate_facts(v, SID, INDICES)
    with pytest.raises(ValueError, match="DUPLICATE_JSON_KEY"):
        parse_fact_json('{"segment_id":"a","segment_id":"b"}')
    v = facts()
    v["unexpected"] = True
    assert validate_facts(v, SID, INDICES) == ["FACT_TOP_LEVEL_KEYS"]
    assert fact_schema()["additionalProperties"] is False


def test_preregistered_protocol_identity_and_seven_segments():
    assert len(SEGMENTS) == len(set(SEGMENTS)) == 7
    identity = protocol_identity()
    assert all(len(value) == 64 for key, value in identity.items() if key.endswith("sha256"))
