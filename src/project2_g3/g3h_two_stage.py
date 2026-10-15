"""Frozen G3H-P1 visual facts and deterministic event mapping.

The mapper has no image, human-reference, or prior-prediction inputs.
"""
from __future__ import annotations

import copy
import json
from typing import Any

from project2_g3 import semantic_schema as S

ANSWERS = ("yes", "no", "uncertain")
REGIONS = ("left", "center", "right", "not_observable", "uncertain")
APERTURES = ("open", "closed", "partially_open", "not_observable", "uncertain")
RELATIONS = ("beneath_gripper", "left_of_gripper", "right_of_gripper", "separate", "not_observable", "uncertain")
DIRECTIONS = ("left", "right", "up", "down", "mixed", "none", "uncertain")
JUDGMENTS = ("moves_with_gripper", "closing_near_can", "opening_near_can", "gripper_approaches_can")


def _judgment() -> dict:
    return {"type": "object", "additionalProperties": False,
            "required": ["answer", "evidence_frame_indices"],
            "properties": {"answer": {"type": "string", "enum": list(ANSWERS)},
                           "evidence_frame_indices": {"type": "array", "items": {"type": "integer"}}}}


_FACT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["segment_id", "frames", "same_can", "fixed_reference_comparable",
                 "reference_description", "can_motion", *JUDGMENTS, "occlusion", "observation_note"],
    "properties": {
        "segment_id": {"type": "string"},
        "frames": {"type": "array", "minItems": 3, "maxItems": 3, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["frame_index", "can_visible", "can_region", "can_relative_to_reference", "gripper_visible", "gripper_aperture", "can_gripper_relation"],
            "properties": {
                "frame_index": {"type": "integer"},
                "can_visible": {"type": "string", "enum": list(ANSWERS)},
                "can_region": {"type": "string", "enum": list(REGIONS)},
                "can_relative_to_reference": {"type": "string", "minLength": 1, "maxLength": 80},
                "gripper_visible": {"type": "string", "enum": list(ANSWERS)},
                "gripper_aperture": {"type": "string", "enum": list(APERTURES)},
                "can_gripper_relation": {"type": "string", "enum": list(RELATIONS)},
            }}},
        "same_can": {"type": "string", "enum": list(ANSWERS)},
        "fixed_reference_comparable": {"type": "string", "enum": list(ANSWERS)},
        "reference_description": {"type": "string", "minLength": 1},
        "can_motion": {"type": "object", "additionalProperties": False,
                       "required": ["answer", "direction", "evidence_frame_indices"],
                       "properties": {"answer": {"type": "string", "enum": list(ANSWERS)},
                                      "direction": {"type": "string", "enum": list(DIRECTIONS)},
                                      "evidence_frame_indices": {"type": "array", "items": {"type": "integer"}}}},
        **{key: _judgment() for key in JUDGMENTS},
        "occlusion": {"type": "string", "enum": ["none", "partial", "severe", "uncertain"]},
        "observation_note": {"type": "string", "minLength": 1, "maxLength": 250},
    },
}

FACT_PROMPT = (
    "Inspect the same red Can across three chronological 128x128 RGB frames. Report only directly visible facts in one JSON object. "
    "Use exactly the keys segment_id, frames, same_can, fixed_reference_comparable, reference_description, can_motion, "
    "moves_with_gripper, closing_near_can, opening_near_can, gripper_approaches_can, occlusion, observation_note. "
    "For each frame, frames[] has frame_index, can_visible, can_region (left/center/right/not_observable/uncertain relative to a fixed table or box), "
    "can_relative_to_reference (brief position relative to the SAME fixed landmark), "
    "gripper_visible, gripper_aperture (open/closed/partially_open/not_observable/uncertain), and can_gripper_relation "
    "(beneath_gripper/left_of_gripper/right_of_gripper/separate/not_observable/uncertain). "
    "For can_motion output answer yes/no/uncertain, direction left/right/up/down/mixed/none/uncertain, and evidence_frame_indices. "
    "For the other four judgments output answer yes/no/uncertain and evidence_frame_indices. "
    "Compare the SAME Can against a fixed table or box reference; arm or gripper motion alone is not Can motion. "
    "Use yes for closing_near_can only if an actual transition toward closed near the Can is visible, and yes for opening_near_can only for a visible opening transition. "
    "Use uncertain or not_observable when occlusion or low resolution prevents a judgment. Cite at least two supplied frames for a visible transition. "
    "Describe visible evidence briefly in observation_note. Do not give action phases, event labels, success claims, or task outcomes."
)


def fact_schema() -> dict:
    return copy.deepcopy(_FACT_SCHEMA)


def render_fact_prompt(segment_id: str, indices: list[int]) -> str:
    return FACT_PROMPT + f"\nsegment_id: {segment_id}\nframe_indices: {', '.join(map(str, indices))} (START, MIDDLE, END)"


def parse_fact_json(raw: str) -> dict:
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY:" + key)
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=reject_duplicates)
    if not isinstance(value, dict):
        raise ValueError("FACT_NOT_OBJECT")
    return value


def validate_facts(facts: dict, segment_id: str, indices: list[int]) -> list[str]:
    """Independent shape, enum, identity, frame and answer coherence checks."""
    errors = []
    schema = fact_schema()
    if set(facts) != set(schema["required"]):
        return ["FACT_TOP_LEVEL_KEYS"]
    if facts["segment_id"] != segment_id:
        errors.append("FACT_SEGMENT_ID")
    frames = facts["frames"]
    if not isinstance(frames, list) or len(frames) != 3:
        return errors + ["FACT_FRAMES_COUNT"]
    expected_frame_keys = set(schema["properties"]["frames"]["items"]["required"])
    if [f.get("frame_index") for f in frames if isinstance(f, dict)] != indices:
        errors.append("FACT_FRAME_ORDER")
    for frame in frames:
        if not isinstance(frame, dict) or set(frame) != expected_frame_keys:
            errors.append("FACT_FRAME_KEYS")
            continue
        for key, allowed in (("can_visible", ANSWERS), ("can_region", REGIONS),
                             ("gripper_visible", ANSWERS), ("gripper_aperture", APERTURES),
                             ("can_gripper_relation", RELATIONS)):
            if frame[key] not in allowed:
                errors.append("FACT_FRAME_ENUM:" + key)
        if not isinstance(frame["can_relative_to_reference"], str) or not frame["can_relative_to_reference"].strip() or len(frame["can_relative_to_reference"]) > 80:
            errors.append("FACT_FRAME_REFERENCE_TEXT")
        if type(frame["frame_index"]) is not int:
            errors.append("FACT_FRAME_INDEX_TYPE")
    for key in ("same_can", "fixed_reference_comparable"):
        if facts[key] not in ANSWERS:
            errors.append("FACT_ENUM:" + key)
    for key in ("reference_description", "observation_note"):
        if not isinstance(facts[key], str) or not facts[key].strip():
            errors.append("FACT_TEXT:" + key)
    if isinstance(facts["observation_note"], str) and len(facts["observation_note"]) > 250:
        errors.append("FACT_NOTE_TOO_LONG")
    if facts["occlusion"] not in ("none", "partial", "severe", "uncertain"):
        errors.append("FACT_OCCLUSION")
    for key in ("can_motion", *JUDGMENTS):
        item = facts[key]
        keys = {"answer", "direction", "evidence_frame_indices"} if key == "can_motion" else {"answer", "evidence_frame_indices"}
        if not isinstance(item, dict) or set(item) != keys:
            errors.append("FACT_JUDGMENT_KEYS:" + key)
            continue
        if item["answer"] not in ANSWERS:
            errors.append("FACT_ANSWER:" + key)
        cited = item["evidence_frame_indices"]
        if not isinstance(cited, list) or any(type(i) is not int or i not in indices for i in cited) or len(cited) != len(set(cited)):
            errors.append("FACT_EVIDENCE_FRAMES:" + key)
        elif item["answer"] == "yes" and len(cited) < 2:
            errors.append("FACT_YES_NEEDS_TWO_FRAMES:" + key)
        if key == "can_motion":
            if item["direction"] not in DIRECTIONS:
                errors.append("FACT_DIRECTION")
            if item["answer"] == "yes" and item["direction"] in ("none", "uncertain"):
                errors.append("FACT_MOTION_DIRECTION_MISSING")
            if item["answer"] == "no" and item["direction"] != "none":
                errors.append("FACT_NO_MOTION_DIRECTION")
            if item["answer"] == "uncertain" and item["direction"] != "uncertain":
                errors.append("FACT_UNCERTAIN_DIRECTION")
    return errors


def map_facts(facts: dict, segment_id: str, indices: list[int]) -> dict:
    """Map validated visual facts; never read RGB or a reference label."""
    errors = validate_facts(facts, segment_id, indices)
    if errors:
        raise ValueError("FACT_INVALID:" + ",".join(errors))
    motion = facts["can_motion"]
    motion_ok = (facts["same_can"] == "yes" and facts["fixed_reference_comparable"] == "yes"
                 and motion["answer"] == "yes")
    sync_ok = motion_ok and facts["moves_with_gripper"]["answer"] == "yes"
    closing = facts["closing_near_can"]["answer"] == "yes"
    opening = facts["opening_near_can"]["answer"] == "yes"
    approach = facts["gripper_approaches_can"]["answer"] == "yes"
    triggered = []
    for event_type, active, key in (("grasp_attempt", closing, "closing_near_can"),
                                    ("release_attempt", opening, "opening_near_can"),
                                    ("object_motion", motion_ok, "can_motion")):
        if active:
            triggered.append({"event_type": event_type, "event_outcome": "unclear",
                              "evidence_frame_indices": facts[key]["evidence_frame_indices"]})
    if opening:
        phase, phase_frames = "place", facts["opening_near_can"]["evidence_frame_indices"]
    elif sync_ok:
        phase, phase_frames = "transport", sorted(set(motion["evidence_frame_indices"] + facts["moves_with_gripper"]["evidence_frame_indices"]))
    elif closing:
        phase, phase_frames = "grasp", facts["closing_near_can"]["evidence_frame_indices"]
    elif approach:
        phase, phase_frames = "approach", facts["gripper_approaches_can"]["evidence_frame_indices"]
    elif motion_ok:
        phase, phase_frames = "other", motion["evidence_frame_indices"]
    elif (motion["answer"] == "no" and all(facts[k]["answer"] == "no" for k in JUDGMENTS)
          and facts["fixed_reference_comparable"] == "yes"):
        phase, phase_frames = "idle", indices
    else:
        phase, phase_frames = "uncertain", []
    last = facts["frames"][-1]
    if all(f["can_visible"] == "no" for f in facts["frames"]):
        relation = ["object_not_visible"]
    elif sync_ok:
        relation = ["moving_with_gripper"]
    elif motion["answer"] == "no" and facts["fixed_reference_comparable"] == "yes":
        relation = ["object_static"]
    elif last["can_gripper_relation"] == "beneath_gripper":
        relation = ["gripper_around"]
    else:
        relation = ["uncertain"]
    uncertain = (motion["answer"] == "uncertain" or any(facts[k]["answer"] == "uncertain" for k in JUDGMENTS)
                 or facts["same_can"] == "uncertain" or facts["fixed_reference_comparable"] == "uncertain")
    event_assessment = "event_visible" if triggered else ("insufficient_evidence" if uncertain else "no_event_visible")
    evidence = sorted(set(phase_frames + [i for event in triggered for i in event["evidence_frame_indices"]]))
    quality = "sufficient" if phase != "uncertain" and evidence else ("partial" if evidence else "insufficient")
    note = (f"Visual facts: same_can={facts['same_can']}; fixed_reference={facts['fixed_reference_comparable']}; "
            f"can_motion={motion['answer']}({motion['direction']}); moves_with_gripper={facts['moves_with_gripper']['answer']}; "
            f"closing_near_can={facts['closing_near_can']['answer']}; opening_near_can={facts['opening_near_can']['answer']}; "
            f"occlusion={facts['occlusion']}.")
    result = {"motion_phase": phase, "object_relation": relation,
              "gripper_state": last["gripper_aperture"] if last["gripper_aperture"] in S.GRIPPER_STATE_V0_2 else "uncertain",
              "event_assessment": event_assessment, "events": triggered,
              "evidence_frame_indices": evidence, "evidence_quality": quality,
              "observation_note": note}
    if len(note) > S.NOTE_MAX_CHARS_V0_2:
        raise ValueError("MAPPED_NOTE_TOO_LONG")
    return result
