"""P2-G3 candidate semantic annotation schema v0.1 (structured JSON + enums).

**STATUS: CANDIDATE, NOT OWNER-FROZEN.**

The Owner Freeze (2026-10-13) fixed the *output architecture*: one JSON object,
controlled finite enums with an explicit uncertainty state, a short grounded
``observation_note``, frame-level evidence citations, deterministic QC, and
trusted caller-owned provenance.  It explicitly did **not** freeze the exact
enumeration set, the JSON Schema v1 implementation or the prompt bytes.  This
module is the v0.1 candidate that the tiny baseline is meant to falsify.

Design constraints carried over from the freeze (non-negotiable)
---------------------------------------------------------------
1. The model annotates exactly one **frozen G1 Segment**; it may never
   redefine segment boundaries.
2. ``grasp`` as a motion phase does **not** mean a successful grasp.
3. ``gripper_state=closed`` must **never** be read as ``holding``/task success.
4. Observing no object motion is **not** evidence that a grasp failed.
5. A segment alone cannot support any episode-level task-completion claim.
6. ``uncertain`` must always be reachable, and ``events`` may legitimately be
   empty (``none_observed`` / ``[]``).
7. Any affirmative categorical claim must be backed by cited frames from the
   target segment; fields that cannot be determined may say so explicitly.
8. ``observation_note`` is a short grounded observation, **not** a second
   competing classification channel.

Why this is deliberately smaller than Argus
-------------------------------------------
Argus labels a whole episode from a full video with timestamps and asks for
timelines, per-step progress (0..1), ``completion``/``success_predicate``,
state changes, scene graphs, recovery pairing, instruction variants and
performance review.  P2 has a frozen *segment*, a handful of keyframes, no
timestamps given to the model, and no episode-level evidence, so all
episode-level and progress constructs are removed rather than approximated.
See ``0-doc/90-implementation-local/G3_JSON_Prompt_Design_v0_1.md`` for the
field-by-field disposition.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

SEMANTIC_SCHEMA_VERSION = "P2_G3_SEMANTIC_JSON_V0_1_CANDIDATE"

# --------------------------------------------------------------------------- #
# Controlled vocabularies (CANDIDATE v0.1)
# --------------------------------------------------------------------------- #
#: Dominant visible motion phase of the frozen segment.
#: ``grasp`` is the *chosen behavior class*, never a verified successful grasp.
MOTION_PHASE = (
    "approach",
    "grasp",
    "lift",
    "transport",
    "place",
    "retract",
    "idle",
    "other",
    "uncertain",
)

#: Visible relation between the gripper and the task object.
#: ``gripper_around`` means the jaws visually surround the object; it does NOT
#: assert contact, force or a successful hold.
OBJECT_RELATION = (
    "gripper_around",
    "gripper_contact_visible",
    "moving_with_gripper",
    "object_static",
    "object_not_visible",
    "uncertain",
)

#: Visible gripper configuration only.  Never an object-state assertion.
GRIPPER_STATE = (
    "open",
    "closed",
    "partially_open",
    "uncertain",
)

#: Candidate events inside the frozen target segment.
EVENT_TYPE = (
    "grasp_attempt",
    "release_attempt",
    "object_motion",
    "none_observed",
    "uncertain",
)

#: Local outcome of one candidate event.  ``unclear`` is the abstention value.
#: A local ``success`` never promotes to episode-level task success.
EVENT_OUTCOME = (
    "success",
    "failure",
    "unclear",
)

#: Whether the supplied frames can support the asserted fields at all.
EVIDENCE_QUALITY = (
    "sufficient",
    "partial",
    "insufficient",
)

#: Which enum an event's outcome belongs to, for reuse by the validator.
ENUM_TABLE: dict[str, tuple[str, ...]] = {
    "motion_phase": MOTION_PHASE,
    "object_relation": OBJECT_RELATION,
    "gripper_state": GRIPPER_STATE,
    "event_type": EVENT_TYPE,
    "event_outcome": EVENT_OUTCOME,
    "evidence_quality": EVIDENCE_QUALITY,
}

#: How the model may legitimately abstain, per field.
ABSTENTION_VALUES: dict[str, tuple[str, ...]] = {
    "motion_phase": ("uncertain",),
    "object_relation": ("uncertain",),
    "gripper_state": ("uncertain",),
    "event_type": ("uncertain", "none_observed"),
    "event_outcome": ("unclear",),
    "evidence_quality": ("insufficient", "partial"),
}

# --------------------------------------------------------------------------- #
# Structural contract
# --------------------------------------------------------------------------- #
MODEL_OWNED_FIELDS = (
    "motion_phase",
    "object_relation",
    "gripper_state",
    "events",
    "evidence_frame_indices",
    "evidence_quality",
    "observation_note",
)
REQUIRED_FIELDS = MODEL_OWNED_FIELDS
EVENT_FIELDS = ("event_type", "event_outcome", "evidence_frame_indices")
REQUIRED_EVENT_FIELDS = EVENT_FIELDS
NOTE_MAX_CHARS = 400

#: Trusted, caller-owned identities.  The model is never allowed to supply these
#: as truth; if it emits them they are treated as forbidden extra fields.
CALLER_OWNED_FIELDS = (
    "schema_version",
    "run_id",
    "source_episode_id",
    "segment_id",
    "segment_interval_frames",
    "prompt_sha256",
    "model_revision",
    "evidence_pack_sha256",
)

#: ``additionalProperties: false`` at every level.
STRICT_ADDITIONAL_PROPERTIES = True

_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": SEMANTIC_SCHEMA_VERSION,
    "type": "object",
    "additionalProperties": False,
    "required": list(REQUIRED_FIELDS),
    "properties": {
        "motion_phase": {"type": "string", "enum": list(MOTION_PHASE)},
        "object_relation": {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {"type": "string", "enum": list(OBJECT_RELATION)},
        },
        "gripper_state": {"type": "string", "enum": list(GRIPPER_STATE)},
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": list(REQUIRED_EVENT_FIELDS),
                "properties": {
                    "event_type": {"type": "string", "enum": list(EVENT_TYPE)},
                    "event_outcome": {"type": "string", "enum": list(EVENT_OUTCOME)},
                    "evidence_frame_indices": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "integer"},
                    },
                },
            },
        },
        "evidence_frame_indices": {
            "type": "array",
            "items": {"type": "integer"},
        },
        "evidence_quality": {"type": "string", "enum": list(EVIDENCE_QUALITY)},
        "observation_note": {"type": "string", "minLength": 1, "maxLength": NOTE_MAX_CHARS},
    },
}


def json_schema() -> dict[str, Any]:
    """Return a deep-ish copy of the candidate JSON Schema."""

    import copy

    return copy.deepcopy(_SCHEMA)


def enum_for(field: str) -> tuple[str, ...]:
    if field not in ENUM_TABLE:
        raise KeyError(f"UNKNOWN_ENUM_FIELD: {field}")
    return ENUM_TABLE[field]


def is_abstention(field: str, value: Any) -> bool:
    """True when *value* is one of the field's legitimate abstention values."""

    allowed = ABSTENTION_VALUES.get(field)
    if allowed is None:
        return False
    return isinstance(value, str) and value in allowed


def candidate_taxonomy() -> dict[str, Any]:
    """Machine-readable description of the candidate taxonomy (not frozen)."""

    return {
        "status": "CANDIDATE_V0_1_NOT_OWNER_FROZEN",
        "schema_version": SEMANTIC_SCHEMA_VERSION,
        "model_owned_fields": list(MODEL_OWNED_FIELDS),
        "caller_owned_fields_not_accepted_from_model": list(CALLER_OWNED_FIELDS),
        "enums": {name: list(values) for name, values in ENUM_TABLE.items()},
        "abstention_values": {k: list(v) for k, v in ABSTENTION_VALUES.items()},
        "semantic_guards": [
            "motion_phase=grasp is a behavior class, NOT a verified successful grasp",
            "gripper_state=closed must never be equated with holding or task success",
            "absence of visible object motion is not evidence of a failed grasp",
            "a single G1 segment cannot support any episode-level completion claim",
            "events may legitimately be empty; none_observed is a valid observation",
            "every affirmative claim must cite target-segment frames",
            "observation_note is a grounded note, not a second classification",
        ],
        "note_max_chars": NOTE_MAX_CHARS,
    }


def example_payload() -> dict[str, Any]:
    """A shape illustration only. Not a model result and not a frozen example."""

    return {
        "motion_phase": "transport",
        "object_relation": ["moving_with_gripper"],
        "gripper_state": "uncertain",
        "events": [
            {
                "event_type": "object_motion",
                "event_outcome": "unclear",
                "evidence_frame_indices": [70, 90],
            }
        ],
        "evidence_frame_indices": [50, 70, 90],
        "evidence_quality": "partial",
        "observation_note": "物体似乎随夹爪移动，接触点被遮挡，无法确认是否已夹住。",
    }


def required_keys() -> Sequence[str]:
    return REQUIRED_FIELDS


def iter_enum_names() -> Iterable[str]:
    return tuple(ENUM_TABLE)
