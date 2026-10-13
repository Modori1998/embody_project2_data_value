"""Contract tests for the P2-G3 candidate structured-JSON annotation pipeline.

Covers the required cases: legal JSON, illegal enum, missing field, truncated
JSON, neighbour-segment frame citation, non-existent frame, wrong source
episode, note/enum contradiction, uncertain, empty event list, raw-response
immutability and run traceability.

Everything here is a pure-python unit test over synthetic payloads and a
synthetic manifest.  No model, no GPU and no dataset are required.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from project2_g3 import semantic_prompt as P  # noqa: E402
from project2_g3 import semantic_schema as S  # noqa: E402
from project2_g3 import semantic_validation as V  # noqa: E402

EPISODE = "data/demo_47"
SEGMENT = "demo_47-S0003"
INTERVAL = (50, 90)


def make_manifest() -> list[V.FrameEntry]:
    """Two target keyframes plus one neighbour-context frame."""

    return [
        V.FrameEntry(frame_index=50, role="START", source_episode_id=EPISODE,
                     origin_segment_id=SEGMENT, target_segment_id=SEGMENT,
                     is_target_segment_frame=True, pixel_sha256="a" * 64),
        V.FrameEntry(frame_index=70, role="MIDDLE", source_episode_id=EPISODE,
                     origin_segment_id=SEGMENT, target_segment_id=SEGMENT,
                     is_target_segment_frame=True, pixel_sha256="b" * 64),
        V.FrameEntry(frame_index=91, role="NEXT_SEGMENT_START", source_episode_id=EPISODE,
                     origin_segment_id="demo_47-S0004", target_segment_id=SEGMENT,
                     is_target_segment_frame=False, pixel_sha256="c" * 64),
    ]


def make_identity() -> V.TargetSegmentIdentity:
    return V.TargetSegmentIdentity(
        source_episode_id=EPISODE, segment_id=SEGMENT,
        start_frame=INTERVAL[0], end_frame=INTERVAL[1],
    )


def validate(payload: dict, *, finish_reason: str | None = "stop"):
    return V.validate_model_output(
        json.dumps(payload, ensure_ascii=False),
        manifest=make_manifest(), identity=make_identity(),
        finish_reason=finish_reason,
    )


def legal_payload() -> dict:
    return {
        "motion_phase": "transport",
        "object_relation": ["moving_with_gripper"],
        "gripper_state": "closed",
        "events": [
            {"event_type": "object_motion", "event_outcome": "unclear",
             "evidence_frame_indices": [50, 70]}
        ],
        "evidence_frame_indices": [50, 70],
        "evidence_quality": "partial",
        "observation_note": "红色物体随夹爪移动，接触点被遮挡。",
    }


# --------------------------------------------------------------------------- #
# 1. legal JSON
# --------------------------------------------------------------------------- #
class TestLegalOutput:
    def test_legal_payload_is_valid(self):
        result = validate(legal_payload())
        assert result.parse_ok
        assert result.schema_ok
        assert result.frame_evidence_ok
        assert result.status == V.VALID, [f.to_dict() for f in result.findings]

    def test_parsed_payload_is_returned_unchanged(self):
        payload = legal_payload()
        result = validate(payload)
        assert result.parsed == payload

    def test_markdown_fence_is_tolerated_but_flagged(self):
        text = "```json\n" + json.dumps(legal_payload(), ensure_ascii=False) + "\n```"
        result = V.validate_model_output(text, manifest=make_manifest(),
                                        identity=make_identity())
        assert result.parse_ok
        assert any(f.check_id == "MARKDOWN_FENCE_WRAPPER" for f in result.findings)

    def test_empty_event_list_is_legal(self):
        """An empty event list is structurally legal and not an error.

        The relation is set to a non-motion value so this test isolates
        *structural* legality; ``events=[]`` combined with
        ``moving_with_gripper`` is separately a consistency candidate.
        """
        payload = legal_payload()
        payload["events"] = []
        payload["object_relation"] = ["object_static"]
        result = validate(payload)
        assert result.parse_ok
        assert result.schema_ok
        assert result.status in (V.VALID, V.UNRESOLVED)

    def test_empty_event_list_is_schema_valid_regardless_of_relation(self):
        payload = legal_payload()
        payload["events"] = []
        result = validate(payload)  # keeps moving_with_gripper on purpose
        assert result.parse_ok
        assert result.schema_ok, "emptiness of events is structural, not a schema error"

    def test_none_observed_event_is_legal(self):
        payload = legal_payload()
        payload["events"] = [{"event_type": "none_observed", "event_outcome": "unclear",
                              "evidence_frame_indices": [50]}]
        result = validate(payload)
        assert result.parse_ok
        assert not any(f.check_id == "EVENT_NONE_OBSERVED_MIXED_CANDIDATE"
                       for f in result.findings)


# --------------------------------------------------------------------------- #
# 2. illegal enum / extra fields / types
# --------------------------------------------------------------------------- #
class TestSchemaViolations:
    def test_illegal_motion_phase_enum(self):
        payload = legal_payload()
        payload["motion_phase"] = "flying"
        result = validate(payload)
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert any(f.check_id == "ILLEGAL_ENUM" and f.field == "motion_phase"
                   for f in result.findings)
        assert not result.schema_ok

    def test_illegal_event_type_enum(self):
        payload = legal_payload()
        payload["events"][0]["event_type"] = "teleport"
        result = validate(payload)
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert any(f.check_id == "ILLEGAL_ENUM" for f in result.findings)

    def test_forbidden_extra_field(self):
        payload = legal_payload()
        payload["task_completed"] = True
        result = validate(payload)
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert any(f.check_id == "FORBIDDEN_EXTRA_FIELD" for f in result.findings)

    def test_caller_owned_field_from_model_is_rejected(self):
        payload = legal_payload()
        payload["segment_id"] = "some-other-segment"
        result = validate(payload)
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert any(f.check_id == "CALLER_OWNED_FIELD_IN_MODEL_OUTPUT"
                   for f in result.findings)

    def test_wrong_type_for_object_relation(self):
        payload = legal_payload()
        payload["object_relation"] = "moving_with_gripper"
        result = validate(payload)
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert any(f.check_id == "WRONG_TYPE" and f.field == "object_relation"
                   for f in result.findings)

    def test_evidence_indices_must_be_integers(self):
        payload = legal_payload()
        payload["evidence_frame_indices"] = ["50"]
        result = validate(payload)
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert any(f.check_id == "WRONG_TYPE" for f in result.findings)

    def test_empty_object_relation_rejected(self):
        payload = legal_payload()
        payload["object_relation"] = []
        result = validate(payload)
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert any(f.check_id == "EMPTY_OBJECT_RELATION" for f in result.findings)

    def test_note_too_long_rejected(self):
        payload = legal_payload()
        payload["observation_note"] = "x" * (S.NOTE_MAX_CHARS + 1)
        result = validate(payload)
        assert any(f.check_id == "NOTE_TOO_LONG" for f in result.findings)


# --------------------------------------------------------------------------- #
# 3. missing field
# --------------------------------------------------------------------------- #
class TestMissingFields:
    @pytest.mark.parametrize("field", list(S.MODEL_OWNED_FIELDS))
    def test_each_required_field_is_enforced(self, field):
        payload = legal_payload()
        payload.pop(field)
        result = validate(payload)
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert any(f.check_id == "MISSING_REQUIRED_FIELD" and f.field == field
                   for f in result.findings)

    def test_missing_event_subfield(self):
        payload = legal_payload()
        payload["events"][0].pop("event_outcome")
        result = validate(payload)
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert any(f.check_id == "MISSING_REQUIRED_FIELD" and f.field == "events"
                   for f in result.findings)


# --------------------------------------------------------------------------- #
# 4. truncated JSON
# --------------------------------------------------------------------------- #
class TestTruncation:
    def test_truncated_output_is_invalid(self):
        text = json.dumps(legal_payload(), ensure_ascii=False)[:60]
        result = V.validate_model_output(text, manifest=make_manifest(),
                                        identity=make_identity(),
                                        finish_reason="length")
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert result.truncated
        assert any(f.check_id == "OUTPUT_TRUNCATED" for f in result.findings)

    def test_length_finish_reason_flags_even_when_parseable(self):
        """Owner Freeze lists truncated replies as hard-invalid / fail-closed."""
        result = validate(legal_payload(), finish_reason="length")
        assert result.truncated
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert not result.schema_ok

    def test_unparseable_reply(self):
        result = V.validate_model_output("not json at all", manifest=make_manifest(),
                                        identity=make_identity())
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert any(f.check_id == "JSON_UNPARSEABLE" for f in result.findings)

    def test_json_array_is_not_an_object(self):
        result = V.validate_model_output("[1,2,3]", manifest=make_manifest(),
                                        identity=make_identity())
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert not result.parse_ok


# --------------------------------------------------------------------------- #
# 5. neighbour-segment citation
# --------------------------------------------------------------------------- #
class TestFrameEvidence:
    def test_neighbour_frame_as_target_evidence_is_caught(self):
        payload = legal_payload()
        payload["evidence_frame_indices"] = [50, 91]
        result = validate(payload)
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert 91 in result.cross_boundary_references
        assert any(f.check_id == "TARGET_CONTEXT_CROSS_BOUNDARY" for f in result.findings)
        assert not result.frame_evidence_ok

    def test_neighbour_frame_in_event_evidence_is_caught(self):
        payload = legal_payload()
        payload["events"][0]["evidence_frame_indices"] = [91]
        result = validate(payload)
        assert 91 in result.cross_boundary_references
        assert result.status == V.INVALID_MODEL_OUTPUT

    def test_nonexistent_frame_is_caught(self):
        payload = legal_payload()
        payload["evidence_frame_indices"] = [999]
        result = validate(payload)
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert 999 in result.invalid_references
        assert any(f.check_id == "FRAME_NOT_IN_REQUEST_MANIFEST" for f in result.findings)

    def test_frame_outside_frozen_interval_is_caught(self):
        """A frame that exists in the manifest but sits outside [50,90]."""
        manifest = make_manifest() + [
            V.FrameEntry(frame_index=45, role="PREV_SEGMENT_END", source_episode_id=EPISODE,
                         origin_segment_id="demo_47-S0002", target_segment_id=SEGMENT,
                         is_target_segment_frame=False, pixel_sha256="d" * 64),
        ]
        payload = legal_payload()
        payload["evidence_frame_indices"] = [45]
        result = V.validate_model_output(json.dumps(payload), manifest=manifest,
                                        identity=make_identity())
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert 45 in result.invalid_references
        assert any(f.check_id == "FRAME_OUTSIDE_TARGET_SEGMENT" for f in result.findings)

    def test_wrong_source_episode_in_manifest_fails_closed(self):
        manifest = [
            V.FrameEntry(frame_index=50, role="START", source_episode_id="data/demo_999",
                         origin_segment_id=SEGMENT, target_segment_id=SEGMENT,
                         is_target_segment_frame=True, pixel_sha256="a" * 64),
        ]
        findings = V.check_manifest_integrity(manifest, make_identity())
        assert any(f.check_id == "FRAME_SOURCE_EPISODE_MISMATCH" for f in findings)

    def test_target_frame_outside_interval_fails_closed(self):
        manifest = [
            V.FrameEntry(frame_index=10, role="START", source_episode_id=EPISODE,
                         origin_segment_id=SEGMENT, target_segment_id=SEGMENT,
                         is_target_segment_frame=True, pixel_sha256="a" * 64),
        ]
        findings = V.check_manifest_integrity(manifest, make_identity())
        assert any(f.check_id == "TARGET_FRAME_OUTSIDE_INTERVAL" for f in findings)

    def test_invalid_pixel_sha_fails_closed(self):
        manifest = [
            V.FrameEntry(frame_index=50, role="START", source_episode_id=EPISODE,
                         origin_segment_id=SEGMENT, target_segment_id=SEGMENT,
                         is_target_segment_frame=True, pixel_sha256="not-a-sha"),
        ]
        findings = V.check_manifest_integrity(manifest, make_identity())
        assert any(f.check_id == "FRAME_PIXEL_SHA_INVALID" for f in findings)

    def test_duplicate_frame_in_manifest_fails_closed(self):
        entry = V.FrameEntry(frame_index=50, role="START", source_episode_id=EPISODE,
                             origin_segment_id=SEGMENT, target_segment_id=SEGMENT,
                             is_target_segment_frame=True, pixel_sha256="a" * 64)
        findings = V.check_manifest_integrity([entry, entry], make_identity())
        assert any(f.check_id == "DUPLICATE_FRAME_IN_MANIFEST" for f in findings)

    def test_empty_manifest_fails_closed(self):
        findings = V.check_manifest_integrity([], make_identity())
        assert any(f.check_id == "EMPTY_FRAME_MANIFEST" for f in findings)

    def test_citation_sites_are_reported(self):
        payload = legal_payload()
        cited = V.collect_cited_frames(payload)
        sites = {site for site, _ in cited}
        assert "evidence_frame_indices" in sites
        assert "events[0].evidence_frame_indices" in sites


# --------------------------------------------------------------------------- #
# 6. note / category contradictions
# --------------------------------------------------------------------------- #
class TestLabelConsistency:
    def test_note_open_vs_gripper_closed(self):
        payload = legal_payload()
        payload["gripper_state"] = "closed"
        payload["observation_note"] = "夹爪张开，尚未接触物体。"
        result = validate(payload)
        assert result.status == V.REVIEW_REQUIRED
        assert any(f.check_id == "LABEL_NOTE_CONFLICT_CANDIDATE" for f in result.findings)
        assert result.schema_ok  # contradiction does not invalidate the shape

    def test_note_closed_vs_gripper_open(self):
        payload = legal_payload()
        payload["gripper_state"] = "open"
        payload["observation_note"] = "夹爪已经闭合夹紧。"
        result = validate(payload)
        assert any(f.check_id == "LABEL_NOTE_CONFLICT_CANDIDATE" for f in result.findings)

    def test_note_holding_vs_gripper_open(self):
        payload = legal_payload()
        payload["gripper_state"] = "open"
        payload["observation_note"] = "机械臂正握住红色圆柱。"
        result = validate(payload)
        assert any(f.check_id == "LABEL_NOTE_CONFLICT_CANDIDATE" for f in result.findings)

    def test_episode_level_completion_claim_is_flagged(self):
        payload = legal_payload()
        payload["observation_note"] = "任务完成，物体已放入正确位置。"
        result = validate(payload)
        assert any(f.check_id == "EPISODE_LEVEL_CLAIM_CANDIDATE" for f in result.findings)
        assert result.status == V.REVIEW_REQUIRED

    def test_idle_phase_with_substantive_event(self):
        payload = legal_payload()
        payload["motion_phase"] = "idle"
        result = validate(payload)
        assert any(f.check_id == "PHASE_EVENT_CONFLICT_CANDIDATE" for f in result.findings)

    def test_none_observed_mixed_with_real_event(self):
        payload = legal_payload()
        payload["events"].append({"event_type": "none_observed", "event_outcome": "unclear",
                                  "evidence_frame_indices": [50]})
        result = validate(payload)
        assert any(f.check_id == "EVENT_NONE_OBSERVED_MIXED_CANDIDATE"
                   for f in result.findings)

    def test_no_event_but_relation_claims_motion(self):
        payload = legal_payload()
        payload["events"] = []
        payload["object_relation"] = ["moving_with_gripper"]
        result = validate(payload)
        assert any(f.check_id == "EVENT_RELATION_CONFLICT_CANDIDATE"
                   for f in result.findings)

    def test_lone_none_observed_with_motion_relation_is_caught(self):
        payload = legal_payload()
        payload["events"] = [{"event_type": "none_observed",
                              "event_outcome": "unclear",
                              "evidence_frame_indices": [50]}]
        payload["object_relation"] = ["moving_with_gripper"]
        result = validate(payload)
        assert any(f.check_id == "EVENT_RELATION_CONFLICT_CANDIDATE"
                   for f in result.findings)

    def test_substantive_event_with_motion_relation_is_not_flagged(self):
        payload = legal_payload()  # has object_motion + moving_with_gripper
        result = validate(payload)
        assert not any(f.check_id == "EVENT_RELATION_CONFLICT_CANDIDATE"
                       for f in result.findings)

    def test_definite_outcome_without_two_frames(self):
        payload = legal_payload()
        payload["events"][0]["event_outcome"] = "success"
        payload["events"][0]["evidence_frame_indices"] = [70]
        result = validate(payload)
        assert any(f.check_id == "EVIDENCE_SUFFICIENCY_CANDIDATE" for f in result.findings)

    def test_two_frames_satisfies_outcome_evidence_rule(self):
        payload = legal_payload()
        payload["events"][0]["event_outcome"] = "success"
        payload["events"][0]["evidence_frame_indices"] = [50, 70]
        result = validate(payload)
        assert not any(f.check_id == "EVIDENCE_SUFFICIENCY_CANDIDATE"
                       for f in result.findings)

    def test_sufficient_quality_without_citation(self):
        payload = legal_payload()
        payload["evidence_quality"] = "sufficient"
        payload["evidence_frame_indices"] = []
        result = validate(payload)
        assert any(f.check_id == "EVIDENCE_QUALITY_WITHOUT_CITATION"
                   for f in result.findings)

    def test_consistency_findings_are_candidates_not_errors(self):
        payload = legal_payload()
        payload["gripper_state"] = "closed"
        payload["observation_note"] = "夹爪张开。"
        result = validate(payload)
        assert all(f.scope == V.SCOPE_CANDIDATE for f in result.candidate_findings)
        assert result.deterministic_findings == []


# --------------------------------------------------------------------------- #
# 7. uncertain / abstention
# --------------------------------------------------------------------------- #
class TestUncertainty:
    def test_full_abstention_is_unresolved_not_invalid(self):
        payload = {
            "motion_phase": "uncertain",
            "object_relation": ["uncertain"],
            "gripper_state": "uncertain",
            "events": [],
            "evidence_frame_indices": [],
            "evidence_quality": "insufficient",
            "observation_note": "画面过暗，无法判断夹爪与物体的关系。",
        }
        result = validate(payload)
        assert result.parse_ok and result.schema_ok
        assert result.abstained
        assert result.status == V.UNRESOLVED

    def test_partial_abstention_is_valid(self):
        payload = legal_payload()
        payload["gripper_state"] = "uncertain"
        payload["evidence_quality"] = "insufficient"
        result = validate(payload)
        assert result.parse_ok
        assert result.status == V.VALID

    def test_abstention_helpers(self):
        assert S.is_abstention("motion_phase", "uncertain")
        assert S.is_abstention("event_outcome", "unclear")
        assert S.is_abstention("event_type", "none_observed")
        assert not S.is_abstention("motion_phase", "transport")
        assert not S.is_abstention("gripper_state", "open")

    def test_uncertain_is_reachable_for_every_categorical_field(self):
        for field, values in S.ABSTENTION_VALUES.items():
            assert values, field
            for value in values:
                assert value in S.ENUM_TABLE[field], (field, value)


# --------------------------------------------------------------------------- #
# 8. raw response immutability
# --------------------------------------------------------------------------- #
class TestRawImmutability:
    def test_validator_does_not_mutate_the_payload(self):
        payload = legal_payload()
        payload["gripper_state"] = "closed"
        payload["observation_note"] = "夹爪张开。"  # contradiction on purpose
        before = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        result = validate(payload)
        after = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        assert before == after
        assert result.parsed == payload  # returned copy equals the original

    def test_validator_does_not_mutate_raw_text(self):
        raw = json.dumps(legal_payload(), ensure_ascii=False)
        snapshot = str(raw)
        V.validate_model_output(raw, manifest=make_manifest(), identity=make_identity())
        assert raw == snapshot

    def test_status_decision_never_rewrites_findings(self):
        payload = legal_payload()
        payload["events"][0]["event_outcome"] = "success"
        payload["events"][0]["evidence_frame_indices"] = [70]
        result = validate(payload)
        assert result.parsed["events"][0]["event_outcome"] == "success"


# --------------------------------------------------------------------------- #
# 9. prompt / schema provenance
# --------------------------------------------------------------------------- #
class TestPromptContract:
    def test_prompt_sha_is_stable_and_hex(self):
        frames = make_manifest()
        a = P.render_prompt(source_episode_id=EPISODE, segment_id=SEGMENT,
                            start_frame=50, end_frame=90, frames=frames)
        b = P.render_prompt(source_episode_id=EPISODE, segment_id=SEGMENT,
                            start_frame=50, end_frame=90, frames=frames)
        assert a == b
        digest = P.prompt_sha256(a)
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)

    def test_prompt_changes_when_evidence_changes(self):
        frames = make_manifest()
        a = P.render_prompt(source_episode_id=EPISODE, segment_id=SEGMENT,
                            start_frame=50, end_frame=90, frames=frames)
        b = P.render_prompt(source_episode_id=EPISODE, segment_id=SEGMENT,
                            start_frame=50, end_frame=90, frames=frames[:2])
        assert P.prompt_sha256(a) != P.prompt_sha256(b)

    def test_prompt_pairs_every_image_with_frame_identity(self):
        text = P.render_prompt(source_episode_id=EPISODE, segment_id=SEGMENT,
                               start_frame=50, end_frame=90, frames=make_manifest())
        for token in ("frame_index", "role", "source_episode_id",
                      "origin_segment_id", "是否目标段帧"):
            assert token in text
        for index in ("50", "70", "91"):
            assert index in text
        assert "NEXT_SEGMENT_START" in text

    def test_prompt_states_the_core_prohibitions(self):
        text = P.render_prompt(source_episode_id=EPISODE, segment_id=SEGMENT,
                               start_frame=50, end_frame=90, frames=make_manifest())
        for token in ("相邻 Segment", "不得推断", "任务", "特权字段",
                      "重新定义 Segment 边界"):
            assert token in text

    def test_prompt_enums_match_the_schema(self):
        """The prompt must not drift from semantic_schema enums."""
        block = P.render_enum_block()
        for field in ("motion_phase", "object_relation", "gripper_state",
                      "event_type", "event_outcome", "evidence_quality"):
            for value in S.ENUM_TABLE[field]:
                assert f'"{value}"' in block, (field, value)

    def test_prompt_requires_json_only(self):
        text = P.render_prompt(source_episode_id=EPISODE, segment_id=SEGMENT,
                               start_frame=50, end_frame=90, frames=make_manifest())
        assert "一个合法 JSON 对象" in text
        assert "Markdown" in text

    def test_template_file_content_carries_version_and_sha(self):
        content = P.template_file_content()
        assert P.SEMANTIC_PROMPT_VERSION in content
        assert P.template_sha256() in content
        assert "argus" in content.lower()

    def test_default_prompt_has_no_context_frames_by_default(self):
        """v0.1 pilot default is target-keyframes-only."""
        frames = [e for e in make_manifest() if e.is_target_segment_frame]
        text = P.render_prompt(source_episode_id=EPISODE, segment_id=SEGMENT,
                               start_frame=50, end_frame=90, frames=frames)
        assert "91" not in text


class TestSchemaContract:
    def test_schema_declares_no_additional_properties(self):
        schema = S.json_schema()
        assert schema["additionalProperties"] is False
        assert schema["properties"]["events"]["items"]["additionalProperties"] is False

    def test_schema_required_matches_declared_fields(self):
        schema = S.json_schema()
        assert tuple(schema["required"]) == S.MODEL_OWNED_FIELDS
        assert set(schema["properties"]) == set(S.MODEL_OWNED_FIELDS)

    def test_candidate_taxonomy_declares_guards(self):
        tax = S.candidate_taxonomy()
        assert tax["status"] == "CANDIDATE_V0_1_NOT_OWNER_FROZEN"
        joined = " ".join(tax["semantic_guards"])
        assert "grasp" in joined and "closed" in joined and "episode-level" in joined

    def test_caller_owned_fields_are_not_model_owned(self):
        assert not set(S.CALLER_OWNED_FIELDS) & set(S.MODEL_OWNED_FIELDS)

    def test_example_payload_is_schema_valid(self):
        result = validate(S.example_payload())
        assert result.parse_ok and result.schema_ok


# --------------------------------------------------------------------------- #
# 10. run traceability
# --------------------------------------------------------------------------- #
class TestTraceability:
    def test_request_record_is_caller_owned_and_hashed(self):
        record = V.build_request_record(
            identity=make_identity(), manifest=make_manifest(),
            prompt_sha256="f" * 64, model_revision="m@rev",
            sampling={"temperature": 0.0, "seed": 1234},
        )
        assert record["source_episode_id"] == EPISODE
        assert record["segment_id"] == SEGMENT
        assert record["segment_interval_frames"] == [50, 90]
        assert len(record["request_sha256"]) == 64
        assert record["frames"][0]["pixel_sha256"] == "a" * 64

    def test_request_hash_changes_with_manifest(self):
        base = V.build_request_record(identity=make_identity(), manifest=make_manifest(),
                                      prompt_sha256="f" * 64, model_revision="m",
                                      sampling={})
        shorter = V.build_request_record(identity=make_identity(),
                                         manifest=make_manifest()[:2],
                                         prompt_sha256="f" * 64, model_revision="m",
                                         sampling={})
        assert base["request_sha256"] != shorter["request_sha256"]

    def test_processing_error_maps_to_processing_error_status(self):
        result = V.validate_model_output(
            None, manifest=make_manifest(), identity=make_identity(),
            processing_error="SERVER_UNREACHABLE: refused",
        )
        assert result.status == V.PROCESSING_ERROR
        assert any(f.check_id == "TRANSPORT_OR_SERVER_ERROR" for f in result.findings)

    def test_processing_error_is_not_a_data_quality_verdict(self):
        """A pipeline fault must never be recorded as a bad robot observation."""
        result = V.validate_model_output(None, manifest=make_manifest(),
                                        identity=make_identity(),
                                        processing_error="timeout")
        assert result.status in (V.PROCESSING_ERROR,)
        assert result.status not in (V.INVALID_MODEL_OUTPUT, V.REVIEW_REQUIRED)

    def test_status_vocabulary_is_complete(self):
        for name in ("PROCESSING_ERROR", "INVALID_INPUT", "INVALID_MODEL_OUTPUT",
                     "REVIEW_REQUIRED", "UNRESOLVED", "VALID"):
            assert isinstance(getattr(V, name), str)

    def test_every_finding_has_a_scope(self):
        payload = legal_payload()
        payload["gripper_state"] = "closed"
        payload["observation_note"] = "夹爪张开。"
        result = validate(payload)
        assert result.findings
        assert all(f.scope in (V.SCOPE_CANDIDATE, V.SCOPE_DETERMINISTIC)
                   for f in result.findings)


# --------------------------------------------------------------------------- #
# 11. baseline runner contracts
# --------------------------------------------------------------------------- #
class TestBaselineContracts:
    def test_pinned_sample_matches_phase1c_selection(self):
        from project2_g3.dev_segments import PINNED_BASELINE_SEGMENTS
        assert len(PINNED_BASELINE_SEGMENTS) == 10
        ids = [r["segment_id"] for r in PINNED_BASELINE_SEGMENTS]
        assert len(set(ids)) == 10
        episodes = [r["episode_id"] for r in PINNED_BASELINE_SEGMENTS]
        assert len(set(episodes)) == 10, "one segment per episode for diversity"
        expected = {
            "demo_120-S0005", "demo_165-S0003", "demo_196-S0002", "demo_227-S0005",
            "demo_277-S0005", "demo_292-S0002", "demo_33-S0001", "demo_47-S0003",
            "demo_74-S0003", "demo_75-S0001",
        }
        assert set(ids) == expected

    def test_pinned_sample_covers_short_and_normal_strata(self):
        from project2_g3.dev_segments import PINNED_BASELINE_SEGMENTS
        strata = " ".join(r["strata"] for r in PINNED_BASELINE_SEGMENTS)
        assert strata.count("SHORT") >= 3
        assert strata.count("NORMAL") >= 5
        assert "FIRST" in strata and "LAST" in strata
        assert "COMPLETE" in strata and "INCOMPLETE" in strata

    def test_pinned_intervals_are_self_consistent(self):
        from project2_g3.dev_segments import PINNED_BASELINE_SEGMENTS
        for row in PINNED_BASELINE_SEGMENTS:
            assert 0 <= row["start_frame"] <= row["end_frame"]

    def test_gates_are_pre_registered_and_frozen_in_code(self):
        spec = __import__("importlib").util.spec_from_file_location(
            "runner", ROOT / "scripts" / "run_g3_json_tiny_baseline.py")
        module = __import__("importlib").util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.GATES["illegal_model_inputs_max"] == 0
        assert module.GATES["truncated_outputs_max"] == 0
        assert module.GATES["json_parse_rate_min"] == 0.90
        assert module.DEFAULT_MAX_TOKENS == 512
        assert module.DEFAULT_TEMPERATURE == 0.0
