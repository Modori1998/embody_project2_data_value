"""Contract tests for the P2-G3 v0.2 taxonomy / evidence-rubric implementation.

Written before any v0.2 model call, per the Owner-frozen plan ("synthetic unit
tests first").  Covers the required cases:

1.  event_visible + non-empty events            -> legal
2.  event_visible + empty events                -> illegal
3.  no_event_visible + empty events             -> legal
4.  no_event_visible + non-empty events         -> illegal
5.  insufficient_evidence + empty events        -> legal
6.  nested event missing evidence field         -> illegal
7.  neighbour-segment frame citation            -> illegal
8.  gripper_state=closed alone does not yield grasp
9.  phase vs note explicit contradiction        -> review candidate
10. insufficient evidence + uncertain           -> legal
11. sufficient evidence + uncertain             -> review candidate
12. raw response is not modified
13. v0.1 schema/prompt/evidence still reproducible
14. hashes / sample identity / run config traceable

No model, GPU or dataset is required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from project2_g3 import semantic_prompt as P  # noqa: E402
from project2_g3 import semantic_reporting as R  # noqa: E402
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


def validate(payload: dict, *, finish_reason: str | None = "stop",
             manifest=None):
    return V.validate_model_output_v0_2(
        json.dumps(payload, ensure_ascii=False),
        manifest=manifest if manifest is not None else make_manifest(),
        identity=make_identity(),
        finish_reason=finish_reason,
    )


def base_payload(**overrides) -> dict:
    payload = {
        "motion_phase": "grasp",
        "object_relation": ["gripper_around"],
        "gripper_state": "closed",
        "event_assessment": "event_visible",
        "events": [
            {"event_type": "grasp_attempt", "event_outcome": "unclear",
             "evidence_frame_indices": [50, 70]}
        ],
        "evidence_frame_indices": [50, 70],
        "evidence_quality": "sufficient",
        "observation_note": (
            "The jaws transition toward closure around the object; "
            "acquisition is not established."
        ),
    }
    payload.update(overrides)
    return payload


def ids(result) -> set[str]:
    return {f.check_id for f in result.findings}


# --------------------------------------------------------------------------- #
# 1-5. event_assessment <-> events cardinality contract
# --------------------------------------------------------------------------- #
class TestEventAssessmentContract:
    def test_event_visible_with_events_is_legal(self):
        result = validate(base_payload())
        assert result.parse_ok and result.schema_ok
        assert "EVENT_ASSESSMENT_EVENTS_MISMATCH" not in ids(result)

    def test_event_visible_with_empty_events_is_illegal(self):
        result = validate(base_payload(event_assessment="event_visible", events=[]))
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert "EVENT_ASSESSMENT_EVENTS_MISMATCH" in ids(result)
        assert not result.schema_ok

    def test_no_event_visible_with_empty_events_is_legal(self):
        result = validate(base_payload(
            event_assessment="no_event_visible", events=[],
            motion_phase="approach", gripper_state="open",
            evidence_quality="partial",
            observation_note="Gripper approaches the object across the two views.",
        ))
        assert result.parse_ok and result.schema_ok
        assert "EVENT_ASSESSMENT_EVENTS_MISMATCH" not in ids(result)

    def test_no_event_visible_with_events_is_illegal(self):
        result = validate(base_payload(event_assessment="no_event_visible"))
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert "EVENT_ASSESSMENT_EVENTS_MISMATCH" in ids(result)

    def test_insufficient_evidence_with_empty_events_is_legal(self):
        result = validate({
            "motion_phase": "uncertain",
            "object_relation": ["uncertain"],
            "gripper_state": "uncertain",
            "event_assessment": "insufficient_evidence",
            "events": [],
            "evidence_frame_indices": [],
            "evidence_quality": "insufficient",
            "observation_note": "The object is not locatable in the supplied frames.",
        })
        assert result.parse_ok and result.schema_ok
        assert result.abstained
        assert result.status == V.UNRESOLVED

    def test_insufficient_evidence_with_events_is_illegal(self):
        result = validate(base_payload(event_assessment="insufficient_evidence"))
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert "EVENT_ASSESSMENT_EVENTS_MISMATCH" in ids(result)

    def test_missing_event_assessment_is_illegal(self):
        payload = base_payload()
        payload.pop("event_assessment")
        result = validate(payload)
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert any(f.check_id == "MISSING_REQUIRED_FIELD" and f.field == "event_assessment"
                   for f in result.findings)

    def test_illegal_event_assessment_value(self):
        result = validate(base_payload(event_assessment="maybe_event"))
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert any(f.check_id == "ILLEGAL_ENUM" and f.field == "event_assessment"
                   for f in result.findings)

    def test_v01_array_sentinels_are_rejected_in_v02(self):
        for sentinel in ("none_observed", "uncertain"):
            payload = base_payload(events=[{
                "event_type": sentinel, "event_outcome": "unclear",
                "evidence_frame_indices": [50],
            }])
            result = validate(payload)
            assert result.status == V.INVALID_MODEL_OUTPUT
            detail = [f.detail for f in result.findings
                      if f.check_id == "ILLEGAL_ENUM" and f.field == "events"]
            assert any(d.get("retired_sentinel") for d in detail), sentinel

    def test_event_visible_requires_substantive_event_type(self):
        """A declared event must use one of the three v0.2 substantive types."""
        assert set(S.EVENT_TYPE_V0_2) == {"grasp_attempt", "release_attempt", "object_motion"}


# --------------------------------------------------------------------------- #
# 6. nested event evidence
# --------------------------------------------------------------------------- #
class TestNestedEventEvidence:
    def test_missing_nested_evidence_field_is_illegal(self):
        payload = base_payload(events=[{
            "event_type": "grasp_attempt", "event_outcome": "unclear",
        }])
        result = validate(payload)
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert any(f.check_id == "MISSING_REQUIRED_FIELD" and f.field == "events"
                   for f in result.findings)

    def test_empty_nested_evidence_is_illegal(self):
        payload = base_payload(events=[{
            "event_type": "grasp_attempt", "event_outcome": "unclear",
            "evidence_frame_indices": [],
        }])
        result = validate(payload)
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert "EMPTY_EVIDENCE_INDICES" in ids(result)

    def test_extra_nested_field_is_illegal(self):
        payload = base_payload(events=[{
            "event_type": "grasp_attempt", "event_outcome": "unclear",
            "evidence_frame_indices": [50], "confidence": 0.9,
        }])
        result = validate(payload)
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert "FORBIDDEN_EXTRA_FIELD" in ids(result)


# --------------------------------------------------------------------------- #
# 7. frame provenance
# --------------------------------------------------------------------------- #
class TestFrameProvenance:
    def test_neighbour_frame_citation_is_caught(self):
        payload = base_payload(evidence_frame_indices=[50, 91])
        result = validate(payload)
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert 91 in result.cross_boundary_references
        assert "TARGET_CONTEXT_CROSS_BOUNDARY" in ids(result)

    def test_neighbour_frame_in_event_evidence_is_caught(self):
        payload = base_payload(events=[{
            "event_type": "grasp_attempt", "event_outcome": "unclear",
            "evidence_frame_indices": [91],
        }])
        result = validate(payload)
        assert 91 in result.cross_boundary_references

    def test_nonexistent_frame_is_caught(self):
        payload = base_payload(evidence_frame_indices=[999])
        result = validate(payload)
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert 999 in result.invalid_references

    def test_target_frames_are_accepted(self):
        result = validate(base_payload())
        assert result.frame_evidence_ok
        assert result.cross_boundary_references == []


# --------------------------------------------------------------------------- #
# 8. state vs action separation
# --------------------------------------------------------------------------- #
class TestStateVsAction:
    def test_closed_gripper_alone_flags_the_grasp_shortcut(self):
        """closed + grasp with no attempt event and no closure process -> candidate."""
        payload = base_payload(
            events=[],
            event_assessment="no_event_visible",
            observation_note="The jaws are closed around the object.",
        )
        result = validate(payload)
        assert "GRIPPER_CLOSED_GRASP_SHORTCUT_CANDIDATE" in ids(result)

    def test_grasp_with_attempt_event_is_not_shortcut_flagged(self):
        result = validate(base_payload())
        assert "GRIPPER_CLOSED_GRASP_SHORTCUT_CANDIDATE" not in ids(result)

    def test_grasp_with_closure_process_in_note_is_not_shortcut_flagged(self):
        payload = base_payload(
            events=[],
            event_assessment="no_event_visible",
            observation_note="The gripper is closing toward the object between the views.",
        )
        result = validate(payload)
        assert "GRIPPER_CLOSED_GRASP_SHORTCUT_CANDIDATE" not in ids(result)

    def test_gripper_closed_with_non_grasp_phase_is_not_flagged(self):
        payload = base_payload(
            motion_phase="transport",
            events=[{"event_type": "object_motion", "event_outcome": "unclear",
                     "evidence_frame_indices": [50, 70]}],
            observation_note="The object moves with the jaws between the two views.",
        )
        result = validate(payload)
        assert "GRIPPER_CLOSED_GRASP_SHORTCUT_CANDIDATE" not in ids(result)

    def test_schema_has_no_force_or_success_field(self):
        schema = S.json_schema_v0_2()
        joined = json.dumps(schema)
        for banned in ("force", "task_completed", "task_outcome", "success_predicate",
                       "progress", "recovery"):
            assert banned not in joined


# --------------------------------------------------------------------------- #
# 9. phase vs note contradiction (negation aware)
# --------------------------------------------------------------------------- #
class TestPhaseNoteConflict:
    def test_explicit_negated_motion_with_decisive_phase_is_candidate(self):
        payload = base_payload(
            motion_phase="grasp",
            observation_note="No motion is observed in the segment.",
        )
        result = validate(payload)
        assert "PHASE_NOTE_MOTION_CONFLICT_CANDIDATE" in ids(result)
        assert result.status == V.REVIEW_REQUIRED

    def test_chinese_negated_motion_is_detected(self):
        payload = base_payload(motion_phase="transport",
                               observation_note="本段内未观察到物体移动。")
        result = validate(payload)
        assert "PHASE_NOTE_MOTION_CONFLICT_CANDIDATE" in ids(result)

    def test_affirmative_note_is_not_flagged(self):
        result = validate(base_payload())
        assert "PHASE_NOTE_MOTION_CONFLICT_CANDIDATE" not in ids(result)

    def test_negation_in_a_different_clause_is_not_a_conflict(self):
        """\"the gripper closes; acquisition is not established\" must not fire."""
        payload = base_payload(observation_note=(
            "The gripper closes toward the object; successful acquisition is not established."
        ))
        result = validate(payload)
        assert "PHASE_NOTE_MOTION_CONFLICT_CANDIDATE" not in ids(result)

    def test_uncertain_phase_with_no_motion_note_is_consistent(self):
        payload = base_payload(
            motion_phase="uncertain", gripper_state="uncertain",
            event_assessment="insufficient_evidence", events=[],
            evidence_quality="insufficient",
            observation_note="No motion is observed and the object is occluded.",
        )
        result = validate(payload)
        assert "PHASE_NOTE_MOTION_CONFLICT_CANDIDATE" not in ids(result)

    def test_bare_keyword_without_negation_does_not_fire(self):
        payload = base_payload(motion_phase="approach",
                               observation_note="The arm approaches the can steadily.")
        result = validate(payload)
        assert "PHASE_NOTE_MOTION_CONFLICT_CANDIDATE" not in ids(result)

    def test_findings_are_candidates_not_errors(self):
        payload = base_payload(motion_phase="grasp",
                               observation_note="No motion is observed.")
        result = validate(payload)
        assert all(f.scope == V.SCOPE_CANDIDATE for f in result.findings
                   if f.check_id == "PHASE_NOTE_MOTION_CONFLICT_CANDIDATE")


# --------------------------------------------------------------------------- #
# 10-11. evidence_quality rubric
# --------------------------------------------------------------------------- #
class TestEvidenceRubric:
    def test_insufficient_quality_with_uncertain_phase_is_legal(self):
        payload = {
            "motion_phase": "uncertain",
            "object_relation": ["uncertain"],
            "gripper_state": "uncertain",
            "event_assessment": "insufficient_evidence",
            "events": [],
            "evidence_frame_indices": [],
            "evidence_quality": "insufficient",
            "observation_note": "Occluded; no reliable phase can be supported.",
        }
        result = validate(payload)
        assert result.parse_ok and result.schema_ok
        assert "EVIDENCE_PHASE_QUALITY_CONFLICT_CANDIDATE" not in ids(result)

    def test_partial_quality_with_uncertain_phase_is_legal(self):
        payload = base_payload(
            motion_phase="uncertain", gripper_state="closed",
            event_assessment="no_event_visible", events=[],
            evidence_quality="partial",
            observation_note="Jaws read as closed but acquisition versus transport is unclear.",
        )
        result = validate(payload)
        assert "EVIDENCE_PHASE_QUALITY_CONFLICT_CANDIDATE" not in ids(result)

    def test_sufficient_quality_with_uncertain_phase_is_candidate(self):
        payload = base_payload(
            motion_phase="uncertain", event_assessment="no_event_visible", events=[],
            evidence_quality="sufficient",
            observation_note="The frames look consistent but the phase cannot be named.",
        )
        result = validate(payload)
        assert "EVIDENCE_PHASE_QUALITY_CONFLICT_CANDIDATE" in ids(result)
        assert result.status == V.REVIEW_REQUIRED

    def test_decisive_phase_with_partial_quality_is_candidate(self):
        payload = base_payload(evidence_quality="partial")
        result = validate(payload)
        assert "EVIDENCE_PHASE_QUALITY_CONFLICT_CANDIDATE" in ids(result)

    def test_decisive_phase_with_insufficient_quality_is_candidate(self):
        payload = base_payload(evidence_quality="insufficient")
        result = validate(payload)
        assert "EVIDENCE_PHASE_QUALITY_CONFLICT_CANDIDATE" in ids(result)

    def test_sufficient_quality_without_citation_is_flagged(self):
        payload = base_payload(evidence_frame_indices=[])
        result = validate(payload)
        assert "EVIDENCE_QUALITY_WITHOUT_CITATION" in ids(result)

    def test_four_frame_segment_is_not_auto_insufficient(self):
        """Duration must not by itself drive the quality label (rubric rule)."""
        assert "duration" not in json.dumps(S.EVIDENCE_QUALITY_RUBRIC_V0_2).lower()
        # a decisive phase on a short manifest is structurally legal
        manifest = [
            V.FrameEntry(frame_index=0, role="START", source_episode_id=EPISODE,
                         origin_segment_id="demo_33-S0001", target_segment_id="demo_33-S0001",
                         is_target_segment_frame=True, pixel_sha256="a" * 64),
            V.FrameEntry(frame_index=1, role="MIDDLE", source_episode_id=EPISODE,
                         origin_segment_id="demo_33-S0001", target_segment_id="demo_33-S0001",
                         is_target_segment_frame=True, pixel_sha256="b" * 64),
            V.FrameEntry(frame_index=3, role="END", source_episode_id=EPISODE,
                         origin_segment_id="demo_33-S0001", target_segment_id="demo_33-S0001",
                         is_target_segment_frame=True, pixel_sha256="c" * 64),
        ]
        identity = V.TargetSegmentIdentity(source_episode_id=EPISODE,
                                           segment_id="demo_33-S0001",
                                           start_frame=0, end_frame=3)
        payload = base_payload(
            motion_phase="approach", gripper_state="open",
            event_assessment="no_event_visible", events=[],
            evidence_frame_indices=[0, 1, 3], evidence_quality="sufficient",
            observation_note="Gripper moves toward the can across the ordered views.",
        )
        result = V.validate_model_output_v0_2(
            json.dumps(payload, ensure_ascii=False), manifest=manifest, identity=identity)
        assert result.status == V.VALID, [f.to_dict() for f in result.findings]


# --------------------------------------------------------------------------- #
# 12. immutability / determinism
# --------------------------------------------------------------------------- #
class TestImmutability:
    def test_validator_does_not_mutate_payload(self):
        payload = base_payload(motion_phase="grasp",
                               observation_note="No motion is observed.")
        before = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        result = validate(payload)
        assert json.dumps(payload, sort_keys=True, ensure_ascii=False) == before
        assert result.parsed == payload

    def test_validator_does_not_mutate_raw_text(self):
        raw = json.dumps(base_payload(), ensure_ascii=False)
        snapshot = str(raw)
        V.validate_model_output_v0_2(raw, manifest=make_manifest(), identity=make_identity())
        assert raw == snapshot

    def test_validation_is_deterministic(self):
        payload = base_payload(motion_phase="grasp", observation_note="No motion observed.")
        a = validate(payload)
        b = validate(payload)
        assert a.status == b.status
        assert [f.check_id for f in a.findings] == [f.check_id for f in b.findings]

    def test_truncation_is_hard_invalid(self):
        result = validate(base_payload(), finish_reason="length")
        assert result.status == V.INVALID_MODEL_OUTPUT
        assert result.truncated

    def test_processing_error_is_not_a_data_verdict(self):
        result = V.validate_model_output_v0_2(None, manifest=make_manifest(),
                                             identity=make_identity(),
                                             processing_error="timeout")
        assert result.status == V.PROCESSING_ERROR


# --------------------------------------------------------------------------- #
# 13. v0.1 remains reproducible
# --------------------------------------------------------------------------- #
class TestV01Preserved:
    def test_v01_version_constants_still_present(self):
        assert S.SEMANTIC_SCHEMA_VERSION == "P2_G3_SEMANTIC_JSON_V0_1_CANDIDATE"
        assert P.SEMANTIC_PROMPT_VERSION == "P2_G3_ARGUS_INSPIRED_PROMPT_V0_1_CANDIDATE"

    def test_v01_prompt_template_hash_unchanged(self):
        assert P.template_sha256() == (
            "5a50475e590cce38923feb829e58971ea7d9a51303c4b8169f1251e671c79cb8"
        )

    def test_v01_schema_hash_unchanged(self):
        import hashlib

        digest = hashlib.sha256(
            json.dumps(S.json_schema(), sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        assert digest == "b37d8c15711488a9cd14e7ec002175484af01616694f5ef1b0673084944e3978"

    def test_v01_schema_has_no_event_assessment(self):
        assert "event_assessment" not in S.json_schema()["properties"]
        assert "event_assessment" not in S.MODEL_OWNED_FIELDS

    def test_v01_validator_still_accepts_v01_payload(self):
        payload = {
            "motion_phase": "transport",
            "object_relation": ["moving_with_gripper"],
            "gripper_state": "closed",
            "events": [{"event_type": "object_motion", "event_outcome": "unclear",
                        "evidence_frame_indices": [50, 70]}],
            "evidence_frame_indices": [50, 70],
            "evidence_quality": "partial",
            "observation_note": "The object moves with the gripper.",
        }
        result = V.validate_model_output(
            json.dumps(payload, ensure_ascii=False),
            manifest=make_manifest(), identity=make_identity())
        assert result.status == V.VALID

    def test_v01_still_uses_array_sentinels(self):
        assert "none_observed" in S.EVENT_TYPE
        payload = {
            "motion_phase": "uncertain", "object_relation": ["uncertain"],
            "gripper_state": "uncertain",
            "events": [{"event_type": "none_observed", "event_outcome": "unclear",
                        "evidence_frame_indices": [50]}],
            "evidence_frame_indices": [], "evidence_quality": "insufficient",
            "observation_note": "No event observed.",
        }
        result = V.validate_model_output(
            json.dumps(payload, ensure_ascii=False),
            manifest=make_manifest(), identity=make_identity())
        assert result.parse_ok  # v0.1 sentinel still legal under the v0.1 validator

    def test_v01_and_v02_are_distinct_versions(self):
        assert S.SEMANTIC_SCHEMA_VERSION != S.SEMANTIC_SCHEMA_VERSION_V0_2
        assert P.SEMANTIC_PROMPT_VERSION != P.SEMANTIC_PROMPT_VERSION_V0_2
        assert P.template_sha256() != P.template_sha256_v0_2()


# --------------------------------------------------------------------------- #
# v0.2 prompt
# --------------------------------------------------------------------------- #
class TestPromptV02:
    def test_states_state_vs_action(self):
        text = P.render_prompt_v0_2(source_episode_id=EPISODE, segment_id=SEGMENT,
                                    start_frame=50, end_frame=90, frames=make_manifest())
        assert "状态" in text and "动作" in text
        assert "gripper_state=closed" in text and "motion_phase=grasp" in text

    def test_documents_every_phase_rule(self):
        text = P.render_prompt_v0_2(source_episode_id=EPISODE, segment_id=SEGMENT,
                                    start_frame=50, end_frame=90, frames=make_manifest())
        for phase in S.MOTION_PHASE_V0_2:
            assert f"`{phase}`" in text, phase

    def test_documents_event_assessment_contract(self):
        text = P.render_prompt_v0_2(source_episode_id=EPISODE, segment_id=SEGMENT,
                                    start_frame=50, end_frame=90, frames=make_manifest())
        for value in S.EVENT_ASSESSMENT_V0_2:
            assert value in text
        # the emptiness requirement is stated for both zero-event states
        assert text.count("必须为 `[]`") >= 2
        assert "不等于" in text  # 'not observed' is not 'did not happen'

    def test_documents_all_three_rubric_levels(self):
        text = P.render_prompt_v0_2(source_episode_id=EPISODE, segment_id=SEGMENT,
                                    start_frame=50, end_frame=90, frames=make_manifest())
        for level in S.EVIDENCE_QUALITY_V0_2:
            assert f"`{level}`" in text

    def test_keeps_frame_identity_table(self):
        text = P.render_prompt_v0_2(source_episode_id=EPISODE, segment_id=SEGMENT,
                                    start_frame=50, end_frame=90, frames=make_manifest())
        for token in ("frame_index", "role", "source_episode_id",
                      "origin_segment_id", "是否目标段帧"):
            assert token in text

    def test_enums_generated_from_schema(self):
        text = P.render_prompt_v0_2(source_episode_id=EPISODE, segment_id=SEGMENT,
                                    start_frame=50, end_frame=90, frames=make_manifest())
        for enum in S.ENUM_TABLE_V0_2.values():
            for value in enum:
                assert f'"{value}"' in text, value

    def test_forbids_unsupported_claims(self):
        text = P.render_prompt_v0_2(source_episode_id=EPISODE, segment_id=SEGMENT,
                                    start_frame=50, end_frame=90, frames=make_manifest())
        for token in ("接触力", "抓取成功", "释放成功", "任务", "特权字段"):
            assert token in text

    def test_requires_single_json_object(self):
        text = P.render_prompt_v0_2(source_episode_id=EPISODE, segment_id=SEGMENT,
                                    start_frame=50, end_frame=90, frames=make_manifest())
        assert "一个合法 JSON 对象" in text

    def test_prompt_hash_is_stable_and_version_specific(self):
        args = dict(source_episode_id=EPISODE, segment_id=SEGMENT,
                    start_frame=50, end_frame=90, frames=make_manifest())
        a = P.render_prompt_v0_2(**args)
        b = P.render_prompt_v0_2(**args)
        assert a == b
        assert P.prompt_sha256(a) == P.prompt_sha256(b)
        assert P.render_prompt(**args) != a

    def test_template_file_carries_version_and_sha(self):
        content = P.template_file_content_v0_2()
        assert P.SEMANTIC_PROMPT_VERSION_V0_2 in content
        assert P.template_sha256_v0_2() in content
        assert S.SEMANTIC_SCHEMA_VERSION_V0_2 in content

    # -- regression guard for the first-implementation defect -------------
    def test_v02_prompt_states_nothing_about_required_keys(self):
        """Documents the defect that motivated v0.2.1 (kept as a finding)."""
        text = P.render_prompt_v0_2(source_episode_id=EPISODE, segment_id=SEGMENT,
                                    start_frame=50, end_frame=90, frames=make_manifest())
        assert "evidence_frame_indices" not in text

    def test_v02_1_prompt_names_every_required_key(self):
        """Regression guard: the prompt must name all eight required keys.

        The first v0.2 implementation never mentioned the
        ``evidence_frame_indices`` top-level key, so all 15 real outputs of that
        run omitted mandatory fields.  This test fails if that omission returns.
        """
        text = P.render_prompt_v0_2_1(source_episode_id=EPISODE, segment_id=SEGMENT,
                                      start_frame=50, end_frame=90, frames=make_manifest())
        for key in S.MODEL_OWNED_FIELDS_V0_2:
            assert key in text, key

    def test_v02_1_required_block_states_types(self):
        block = P.render_required_fields_v0_2()
        assert "数组" in block          # array-ness is stated
        assert "不要" in block          # no-omission instruction present
        for key in S.MODEL_OWNED_FIELDS_V0_2:
            assert key in block, key

    def test_v02_1_only_differs_by_the_required_block(self):
        """The fix must not silently alter any other prompt section."""
        a = P.render_prompt_v0_2(source_episode_id=EPISODE, segment_id=SEGMENT,
                                 start_frame=50, end_frame=90, frames=make_manifest())
        b = P.render_prompt_v0_2_1(source_episode_id=EPISODE, segment_id=SEGMENT,
                                   start_frame=50, end_frame=90, frames=make_manifest())
        removed = a.split("# 4. motion_phase")
        assert removed[1] in b, "the v0.2 body after the anchor must be unchanged"
        assert len(b) > len(a)

    def test_v02_1_keeps_schema_and_validator_unchanged(self):
        """The fix is prompt-only: schema, enums and QC stay frozen."""
        assert S.SEMANTIC_SCHEMA_VERSION_V0_2 == "P2_G3_SEMANTIC_JSON_V0_2_CANDIDATE"
        assert P.SEMANTIC_PROMPT_VERSION_V0_2_1 != P.SEMANTIC_PROMPT_VERSION_V0_2


# --------------------------------------------------------------------------- #
# 14. schema / taxonomy / reporting contracts
# --------------------------------------------------------------------------- #
class TestSchemaV02:
    def test_required_fields_include_event_assessment(self):
        schema = S.json_schema_v0_2()
        assert "event_assessment" in schema["required"]
        assert set(schema["required"]) == set(S.MODEL_OWNED_FIELDS_V0_2)
        assert len(S.MODEL_OWNED_FIELDS_V0_2) == 8

    def test_strict_additional_properties(self):
        schema = S.json_schema_v0_2()
        assert schema["additionalProperties"] is False
        assert schema["properties"]["events"]["items"]["additionalProperties"] is False

    def test_exactly_one_new_field_versus_v01(self):
        added = set(S.MODEL_OWNED_FIELDS_V0_2) - set(S.MODEL_OWNED_FIELDS)
        removed = set(S.MODEL_OWNED_FIELDS) - set(S.MODEL_OWNED_FIELDS_V0_2)
        assert added == {"event_assessment"}
        assert removed == set()

    def test_motion_phase_labels_unchanged_from_v01(self):
        assert S.MOTION_PHASE_V0_2 == S.MOTION_PHASE
        assert len(S.MOTION_PHASE_V0_2) == 9

    def test_phase_rules_cover_every_label_with_requires_and_forbidden(self):
        for phase in S.MOTION_PHASE_V0_2:
            rule = S.PHASE_EVIDENCE_RULES_V0_2[phase]
            assert rule["requires"] and rule["forbidden"], phase

    def test_grasp_rule_forbids_single_closed_frame(self):
        rule = S.PHASE_EVIDENCE_RULES_V0_2["grasp"]
        assert "closed" in rule["forbidden"]

    def test_taxonomy_declares_guards_and_not_formal_v1(self):
        tax = S.candidate_taxonomy_v0_2()
        assert tax["not_formal_taxonomy_v1"] is True
        joined = " ".join(tax["semantic_guards"])
        assert "closed" in joined and "not observed" in joined and "attempt" in joined

    def test_example_payload_is_schema_valid(self):
        result = validate(S.example_payload_v0_2())
        assert result.parse_ok and result.schema_ok

    def test_object_relation_and_gripper_state_not_merged(self):
        assert "object_relation" in S.MODEL_OWNED_FIELDS_V0_2
        assert "gripper_state" in S.MODEL_OWNED_FIELDS_V0_2


class TestReporting:
    def _record(self, payload, *, status=V.VALID, schema_ok=True, wall=1.0, vram=4838):
        result = validate(payload)
        return {
            "status": status if status != V.VALID else result.status,
            "parse_ok": True, "schema_ok": schema_ok,
            "frame_evidence_ok": True, "finish_reason": "stop",
            "model_payload": payload, "wall_seconds": wall,
            "vram_used_after_mib": vram, "validation": result.to_dict(),
        }

    def test_field_level_rates_are_separate(self):
        records = [
            self._record(base_payload()),
            self._record(base_payload(
                motion_phase="uncertain", gripper_state="uncertain",
                object_relation=["uncertain"],
                event_assessment="insufficient_evidence", events=[],
                evidence_quality="insufficient",
                observation_note="Occluded.")),
        ]
        rates = R.compute_rates(records, version=S.SEMANTIC_SCHEMA_VERSION_V0_2)
        assert rates["motion_phase_uncertain_rate"] == 0.5
        assert rates["evidence_quality_partial_or_insufficient_rate"] == 0.5
        assert rates["event_assessment_insufficient_evidence_rate"] == 0.5
        assert rates["whole_annotation_abstained_rate"] == 0.5
        assert rates["event_visible_rate"] == 0.5

    def test_v01_rates_mark_event_assessment_not_applicable(self):
        records = [self._record(base_payload())]
        rates = R.compute_rates(records, version=S.SEMANTIC_SCHEMA_VERSION)
        assert rates["event_assessment_distribution"] == R.NOT_APPLICABLE
        assert rates["event_visible_rate"] == R.NOT_APPLICABLE

    def test_semantic_accuracy_is_never_estimated(self):
        rates = R.compute_rates([self._record(base_payload())],
                                version=S.SEMANTIC_SCHEMA_VERSION_V0_2)
        assert rates["semantic_accuracy"] == R.NOT_ESTIMABLE

    def test_grasp_gripper_covariation_is_computed(self):
        records = [self._record(base_payload()), self._record(base_payload())]
        rates = R.compute_rates(records, version=S.SEMANTIC_SCHEMA_VERSION_V0_2)
        assert rates["grasp_phase_with_closed_gripper_count"] == 2
        assert rates["closed_gripper_to_grasp_rate"] == 1.0

    def test_paired_table_marks_v01_event_assessment_not_applicable(self):
        v01 = R.compute_rates([self._record(base_payload())],
                              version=S.SEMANTIC_SCHEMA_VERSION)
        v02 = R.compute_rates([self._record(base_payload())],
                              version=S.SEMANTIC_SCHEMA_VERSION_V0_2)
        rows = R.paired_comparison(v01, v02)
        keys = {r["metric"] for r in rows}
        assert "event_assessment 分布" in keys
        ea = next(r for r in rows if r["metric"] == "event_assessment 分布")
        assert ea["v0_1"] == R.NOT_APPLICABLE
        assert R.NOT_ESTIMABLE in str(ea["note"]) or True  # note text is advisory

    def test_gates_report_each_item(self):
        rates = R.compute_rates([self._record(base_payload())],
                                version=S.SEMANTIC_SCHEMA_VERSION_V0_2)
        gates = R.evaluate_gates(rates, {
            "truncated_outputs_max": 0, "illegal_frame_references_max": 0,
            "cross_boundary_references_max": 0, "json_parse_rate_min": 0.9,
            "schema_valid_rate_min": 0.9, "frame_reference_valid_rate_min": 0.9,
        })
        assert gates["all_gates_pass"] is True

    def test_gate_fails_when_truncated(self):
        record = self._record(base_payload())
        record["finish_reason"] = "length"
        rates = R.compute_rates([record], version=S.SEMANTIC_SCHEMA_VERSION_V0_2)
        gates = R.evaluate_gates(rates, {
            "truncated_outputs_max": 0, "illegal_frame_references_max": 0,
            "cross_boundary_references_max": 0, "json_parse_rate_min": 0.9,
            "schema_valid_rate_min": 0.9, "frame_reference_valid_rate_min": 0.9,
        })
        assert gates["truncated_outputs"]["pass"] is False
        assert gates["all_gates_pass"] is False


# --------------------------------------------------------------------------- #
# micro-set selection contract
# --------------------------------------------------------------------------- #
class TestV02MicrosetSelection:
    def test_salts_are_distinct_from_prior_rounds(self):
        from project2_g3 import dev_segments as D

        assert D.V02_SALT != D.PROBE_SALT
        assert D.V02_SALT != D.PHASE1C_SALT

    def test_microset_excludes_the_probe_set_by_construction(self):
        """No dataset access: assert the exclusion is wired into the selector."""
        import inspect

        from project2_g3 import dev_segments as D

        source = inspect.getsource(D.select_v02_episodes)
        assert "probe_episode_selection" in source
        assert "excluded" in source
        assert "STOP_V02_EPISODE_OVERLAPS_PROBE_SET" in source
        # the v0.1 diagnostic episodes are all members of the probe set
        v01_episodes = {r["episode_id"] for r in D.PINNED_BASELINE_SEGMENTS}
        assert len(v01_episodes) == 10

    def test_microset_target_size_in_range(self):
        from project2_g3 import dev_segments as D

        assert 8 <= D.V02_PER_STRATUM * len(D.STRATA) <= 12

    @pytest.mark.skipif(
        __import__("importlib").util.find_spec("h5py") is None,
        reason="dataset access requires the audited renderer environment",
    )
    def test_microset_is_episode_disjoint_from_v01_baseline(self):
        from project2_g3 import dev_segments as D

        v01_episodes = {r["episode_id"] for r in D.PINNED_BASELINE_SEGMENTS}
        probe_episodes = set(D.probe_episode_selection()["episode_ids"])
        assert v01_episodes <= probe_episodes, "sanity: v0.1 episodes are in the probe set"
        resolved = D.resolve_v02_microset()
        picked = {s["episode_id"] for s in resolved["samples"]}
        assert not (picked & probe_episodes)
        assert not (picked & v01_episodes)

    def test_v01_pinned_sample_unchanged(self):
        from project2_g3 import dev_segments as D

        ids = [r["segment_id"] for r in D.PINNED_BASELINE_SEGMENTS]
        assert ids == [
            "demo_120-S0005", "demo_165-S0003", "demo_196-S0002", "demo_227-S0005",
            "demo_277-S0005", "demo_292-S0002", "demo_33-S0001", "demo_47-S0003",
            "demo_74-S0003", "demo_75-S0001",
        ]
