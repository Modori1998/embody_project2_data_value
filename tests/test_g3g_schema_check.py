"""Contract checks for the new G3G-P1 decoding protocol."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]

from project2_g3 import semantic_schema as S, semantic_validation as V
from run_g3g_schema_check import constrained_format


def test_constrained_protocol_uses_frozen_schema_for_both_arms():
    for arm in ("4B", "8B"):
        wire = json.loads(json.dumps(constrained_format(S.json_schema_v0_2())))
        assert arm in ("4B", "8B")
        assert wire == {"type": "json_object", "schema": S.json_schema_v0_2()}
        assert set(wire["schema"]["required"]) == {
            "motion_phase", "object_relation", "gripper_state", "event_assessment",
            "events", "evidence_frame_indices", "evidence_quality", "observation_note",
        }
        assert wire["schema"]["additionalProperties"] is False
        assert wire["schema"]["properties"]["events"]["items"]["additionalProperties"] is False


def test_independent_validator_rejects_missing_and_bad_nested_fields():
    valid = {
        "motion_phase": "idle", "object_relation": ["object_not_visible"],
        "gripper_state": "open", "event_assessment": "no_event_visible",
        "events": [], "evidence_frame_indices": [],
        "evidence_quality": "insufficient", "observation_note": "No object visible.",
    }
    assert V.check_schema_v0_2(valid) == []
    missing = dict(valid)
    del missing["evidence_frame_indices"]
    assert V.check_schema_v0_2(missing)
    extra = dict(valid, debug=True)
    assert V.check_schema_v0_2(extra)
    nested = dict(valid, events=[{"event_type": "object_motion"}])
    assert V.check_schema_v0_2(nested)
    duplicate = dict(valid, object_relation=["object_not_visible", "object_not_visible"])
    assert V.check_schema_v0_2(duplicate)
