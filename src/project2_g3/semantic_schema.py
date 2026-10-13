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


# =========================================================================== #
# v0.2 (Owner-frozen development spec, 2026-10-13)
#
# Everything above this line is the v0.1 candidate and is kept byte-for-byte so
# the v0.1 prompt/schema/run records stay reproducible.  v0.2 is added
# alongside rather than editing v0.1 in place.
#
# Source of truth: 0-doc/10-design-review/
#   P2_G3_Taxonomy_v0_2_Design_Owner_Freeze_20261013.md
#   P2_G3_Evidence_Rubric_v0_2_Plan_Owner_Freeze_20261013.md
#   P2_G3_Semantic_JSON_v0_2_Output_Design_Owner_Freeze_20261013.md
# =========================================================================== #

SEMANTIC_SCHEMA_VERSION_V0_2 = "P2_G3_SEMANTIC_JSON_V0_2_CANDIDATE"

#: v0.2 keeps the nine v0.1 motion-phase labels; what changes is the
#: observed-evidence rule behind each label (see ``PHASE_EVIDENCE_RULES_V0_2``).
MOTION_PHASE_V0_2 = MOTION_PHASE

#: Kept separate from ``gripper_state`` this round (no merge).
OBJECT_RELATION_V0_2 = OBJECT_RELATION

#: ``gripper_state`` now explicitly means the jaw configuration of the **last
#: valid target-frame image supplied**, not any arbitrary sample.
GRIPPER_STATE_V0_2 = GRIPPER_STATE

#: v0.2 substantive event types only.  The v0.1 ``none_observed`` / ``uncertain``
#: array *sentinels* are retired; occurrence uncertainty moves to
#: ``event_assessment``.  This migration is versioned, never retrofitted onto
#: stored v0.1 JSON.
EVENT_TYPE_V0_2 = (
    "grasp_attempt",
    "release_attempt",
    "object_motion",
)

EVENT_OUTCOME_V0_2 = EVENT_OUTCOME
EVIDENCE_QUALITY_V0_2 = EVIDENCE_QUALITY

#: The single new top-level model-owned field in v0.2.
EVENT_ASSESSMENT_V0_2 = (
    "event_visible",
    "no_event_visible",
    "insufficient_evidence",
)

#: Cardinality contract between ``event_assessment`` and ``events``.
#: ``None`` means "must be a non-empty array of substantive events".
EVENT_ASSESSMENT_EVENTS_CONTRACT_V0_2: dict[str, str] = {
    "event_visible": "NON_EMPTY_SUBSTANTIVE",
    "no_event_visible": "EMPTY",
    "insufficient_evidence": "EMPTY",
}

MODEL_OWNED_FIELDS_V0_2 = (
    "motion_phase",
    "object_relation",
    "gripper_state",
    "event_assessment",
    "events",
    "evidence_frame_indices",
    "evidence_quality",
    "observation_note",
)
REQUIRED_FIELDS_V0_2 = MODEL_OWNED_FIELDS_V0_2
EVENT_FIELDS_V0_2 = EVENT_FIELDS
REQUIRED_EVENT_FIELDS_V0_2 = EVENT_FIELDS_V0_2
NOTE_MAX_CHARS_V0_2 = NOTE_MAX_CHARS

ENUM_TABLE_V0_2: dict[str, tuple[str, ...]] = {
    "motion_phase": MOTION_PHASE_V0_2,
    "object_relation": OBJECT_RELATION_V0_2,
    "gripper_state": GRIPPER_STATE_V0_2,
    "event_type": EVENT_TYPE_V0_2,
    "event_outcome": EVENT_OUTCOME_V0_2,
    "evidence_quality": EVIDENCE_QUALITY_V0_2,
    "event_assessment": EVENT_ASSESSMENT_V0_2,
}

ABSTENTION_VALUES_V0_2: dict[str, tuple[str, ...]] = {
    "motion_phase": ("uncertain",),
    "object_relation": ("uncertain",),
    "gripper_state": ("uncertain",),
    "event_outcome": ("unclear",),
    "evidence_quality": ("insufficient", "partial"),
    "event_assessment": ("insufficient_evidence",),
}

#: v0.2 observed-evidence rules, one per motion-phase label.
#: ``requires`` states what must be visible; ``forbidden`` is the shortcut that
#: must never justify the label.  These are the frozen development definitions.
PHASE_EVIDENCE_RULES_V0_2: dict[str, dict[str, str]] = {
    "approach": {
        "zh": "靠近",
        "requires": "两个或以上有序目标帧显示夹爪/末端相对可比的参照物向目标物体靠近",
        "forbidden": "仅因夹爪是 open、或物体就在附近就判 approach",
    },
    "grasp": {
        "zh": "抓取尝试阶段",
        "requires": "可见的闭合/就位“变化过程”指向获取物体；是局部尝试阶段",
        "forbidden": "单张静止的 closed 夹爪；不得由此推断 success",
    },
    "lift": {
        "zh": "提起",
        "requires": "在可比视角下，物体与夹爪一同向上位移",
        "forbidden": "视角变化，或仅夹爪闭合",
    },
    "transport": {
        "zh": "搬运",
        "requires": "物体随时间与夹爪保持一致移动；不推断接触/力",
        "forbidden": "物体静止只是正好在夹爪旁边",
    },
    "place": {
        "zh": "放置",
        "requires": "可见向支撑面/目标位置移动，或释放动作序列；结果另行判断",
        "forbidden": "凭目标文字假定放置成功",
    },
    "retract": {
        "zh": "撤离",
        "requires": "夹爪/手臂可见地从先前的交互区域移开",
        "forbidden": "夹爪只是 open",
    },
    "idle": {
        "zh": "观察范围内静止",
        "requires": "可比时间采样支持“在观察窗口内”没有显著运动",
        "forbidden": "推断未采样整个 Segment 期间都没动",
    },
    "other": {
        "zh": "其他可见动作",
        "requires": "确实存在可见运动/过程，但不属于上述任何一类",
        "forbidden": "用 other 藏起证据不足",
    },
    "uncertain": {
        "zh": "主要动作无法确认",
        "requires": "运动方向/阶段无法由时序证据、可见性或参照可比性支持",
        "forbidden": "仅因夹爪可见就强行给一个非 uncertain 标签",
    },
}

#: v0.2 event trigger rules (frozen).
EVENT_TRIGGER_RULES_V0_2: dict[str, str] = {
    "grasp_attempt": (
        "可见的、指向获取物体的行为（例如夹爪在物体附近向闭合过渡），"
        "无论是否证明确实获取到"
    ),
    "release_attempt": (
        "在放置位置可见的放手动作；不得自动声称放置成功"
    ),
    "object_motion": (
        "在可比目标帧之间物体有可分辨的位移，无论是否由夹爪造成"
    ),
}

#: v0.2 evidence-quality rubric, scoped to ``motion_phase``.
EVIDENCE_QUALITY_RUBRIC_V0_2: dict[str, str] = {
    "sufficient": (
        "有序且可比的目标帧足以支持所选的 motion_phase（当该阶段要求运动时，"
        "需可见相应的方向/变化）。若断言确定的 event outcome，还需该事件自身的"
        "前/后支持帧。"
    ),
    "partial": (
        "能读出部分属性/状态，但因时序覆盖不全、遮挡或视觉几何含混，"
        "主要动作阶段不可靠；对应 motion_phase 通常应为 uncertain。"
    ),
    "insufficient": (
        "关键物体/夹爪或时间参照缺失或遮挡，采样连一个可靠的粗阶段都无法支持；"
        "应使用 motion_phase=uncertain 并说明缺什么。"
    ),
}

_SCHEMA_V0_2: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": SEMANTIC_SCHEMA_VERSION_V0_2,
    "type": "object",
    "additionalProperties": False,
    "required": list(REQUIRED_FIELDS_V0_2),
    "properties": {
        "motion_phase": {"type": "string", "enum": list(MOTION_PHASE_V0_2)},
        "object_relation": {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {"type": "string", "enum": list(OBJECT_RELATION_V0_2)},
        },
        "gripper_state": {"type": "string", "enum": list(GRIPPER_STATE_V0_2)},
        "event_assessment": {"type": "string", "enum": list(EVENT_ASSESSMENT_V0_2)},
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": list(REQUIRED_EVENT_FIELDS_V0_2),
                "properties": {
                    "event_type": {"type": "string", "enum": list(EVENT_TYPE_V0_2)},
                    "event_outcome": {"type": "string", "enum": list(EVENT_OUTCOME_V0_2)},
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
        "evidence_quality": {"type": "string", "enum": list(EVIDENCE_QUALITY_V0_2)},
        "observation_note": {
            "type": "string", "minLength": 1, "maxLength": NOTE_MAX_CHARS_V0_2,
        },
    },
}


def json_schema_v0_2() -> dict[str, Any]:
    """Return a copy of the v0.2 candidate JSON Schema."""

    import copy

    return copy.deepcopy(_SCHEMA_V0_2)


def enum_for_v0_2(field: str) -> tuple[str, ...]:
    if field not in ENUM_TABLE_V0_2:
        raise KeyError(f"UNKNOWN_ENUM_FIELD_V0_2: {field}")
    return ENUM_TABLE_V0_2[field]


def is_abstention_v0_2(field: str, value: Any) -> bool:
    allowed = ABSTENTION_VALUES_V0_2.get(field)
    if allowed is None:
        return False
    return isinstance(value, str) and value in allowed


def candidate_taxonomy_v0_2() -> dict[str, Any]:
    """Machine-readable v0.2 taxonomy (development spec, not formal v1)."""

    return {
        "status": "V0_2_DEV_SPEC_OWNER_APPROVED_FROZEN_FOR_IMPLEMENTATION",
        "not_formal_taxonomy_v1": True,
        "schema_version": SEMANTIC_SCHEMA_VERSION_V0_2,
        "model_owned_fields": list(MODEL_OWNED_FIELDS_V0_2),
        "caller_owned_fields_not_accepted_from_model": list(CALLER_OWNED_FIELDS),
        "enums": {name: list(values) for name, values in ENUM_TABLE_V0_2.items()},
        "abstention_values": {k: list(v) for k, v in ABSTENTION_VALUES_V0_2.items()},
        "phase_evidence_rules": PHASE_EVIDENCE_RULES_V0_2,
        "event_trigger_rules": EVENT_TRIGGER_RULES_V0_2,
        "evidence_quality_rubric": EVIDENCE_QUALITY_RUBRIC_V0_2,
        "event_assessment_events_contract": EVENT_ASSESSMENT_EVENTS_CONTRACT_V0_2,
        "semantic_guards": [
            "state is one sampled instant; action is a change across ordered samples",
            "gripper_state=closed must never establish motion_phase=grasp",
            "grasp is an attempt phase, never proof of successful acquisition",
            "gripper_state describes the LAST valid target-frame jaw configuration only",
            "no_event_visible means 'not observed in sampled frames', NOT 'did not happen'",
            "occurrence uncertainty (event_assessment) is separate from outcome uncertainty (event_outcome)",
            "object_motion must not be read as task success",
            "a 4-frame segment is not automatically insufficient; judge visible change, not duration",
            "clear gripper visibility does not by itself make phase evidence sufficient",
            "no episode-level task outcome exists in this response",
        ],
        "note_max_chars": NOTE_MAX_CHARS_V0_2,
    }


def example_payload_v0_2() -> dict[str, Any]:
    """Shape illustration only (mirrors the Owner Freeze schematic)."""

    return {
        "motion_phase": "grasp",
        "object_relation": ["gripper_around"],
        "gripper_state": "closed",
        "event_assessment": "event_visible",
        "events": [
            {
                "event_type": "grasp_attempt",
                "event_outcome": "unclear",
                "evidence_frame_indices": [40, 45],
            }
        ],
        "evidence_frame_indices": [40, 45],
        "evidence_quality": "sufficient",
        "observation_note": (
            "The gripper closes toward an object; successful acquisition is not established."
        ),
    }
