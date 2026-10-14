"""G3F Phase–Event semantic-consistency QC (versioned, NON-DESTRUCTIVE).

This is an *additive* review layer for the G3 semantic annotation.  It never
edits a prediction, a human label or a phase; it never adds ``object_motion``;
it never turns a candidate conflict into ``INVALID_MODEL_OUTPUT``.  It only
returns review-candidate findings so a later human/QC step can inspect them.

The frozen v0.2.1 validator (``semantic_validation``) is untouched.  This module
is what ``G3F_Phase_Event_Output_Design.md`` describes and is opt-in.

Rules (all CANDIDATE scope)
---------------------------
A. ``PHASE_OBJECT_MOTION_MISSING_CANDIDATE``
   ``motion_phase in {transport, lift}`` but no ``object_motion`` event.  The
   phase claims object displacement; the event set omits it.
B. ``RELATION_OBJECT_MOTION_MISSING_CANDIDATE``
   ``object_relation`` contains ``moving_with_gripper`` but no ``object_motion``.
C. ``OBJECT_MOTION_NOTE_CONFLICT_CANDIDATE``
   ``observation_note`` *explicitly* denies object motion/displacement while
   ``events`` contains ``object_motion``.  A mere absence of a motion mention is
   NOT a conflict; an explicit denial is required.
D. ``GRASP_EVENT_NOTE_CONFLICT_CANDIDATE``
   ``events`` contains ``grasp_attempt`` while the note *explicitly* denies an
   observed grasp process / states the gripper stayed in one configuration
   throughout.  A closed gripper state alone is NOT enough.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

PHASE_EVENT_QC_VERSION = "P2_G3_PHASE_EVENT_QC_V0_2_2_CANDIDATE"

#: Rule-A phases: the frozen schema says these entail object displacement.
DISPLACEMENT_PHASES = ("transport", "lift")

SCOPE_CANDIDATE = "CANDIDATE"

_CLAUSE_SPLIT_RE = re.compile(r"[。．.!?！？;；，,、\n]+")

#: Static / motion-denial tokens; used clause-scoped with an object reference so
#: a static *gripper* alone never fires rule C.
_STATIC_TOKENS = (
    "静止", "保持不动", "保持原位", "位置不变", "没动", "未移动", "没有移动",
    "无位移", "没有位移", "未发生位移", "无明显位移", "未见明显位移",
    "no motion", "no movement", "no displacement", "no change in position",
    "stationary", "static", "remains in place", "stays in place", "unchanged",
)

#: Object references for the clause-scoped static check.
_OBJECT_TOKENS = (
    "物体", "罐", "杯", "可乐", "瓶子", "盒子", "托盘",
    "can", "object", "bottle", "cup", "box", "container",
)

#: Explicit object-static / no-displacement assertions (must be a denial).
_STATIC_PATTERNS = (
    "物体静止", "物体保持静止", "物体保持不动", "物体没有移动", "物体未移动",
    "物体无位移", "物体没有位移", "物体位置不变", "物体保持原位", "物体未发生位移",
    "物体没有发生位移", "物体未见移动", "物体没动", "物体保持静止不动",
    "静止不动", "保持静止", "保持不动", "位置不变", "未见明显位移", "没有明显位移",
    "object is static", "object remains static", "object is stationary",
    "object remains stationary", "object stays static", "object stays stationary",
    "can is stationary", "can remains stationary", "can stays stationary",
    "can is static", "can remains static", "can stays static",
    "no object motion", "no visible object motion", "no object movement",
    "no visible object movement", "no observable object motion",
    "object does not move", "object did not move", "object doesn't move",
    "object shows no motion", "no discernible displacement", "no visible displacement",
    "no object displacement", "object remains in place", "object position unchanged",
    "remains in place", "no movement of the can", "no motion of the can",
    "no visible motion", "no clear motion", "no significant motion",
    "no motion observed", "no movement observed", "no displacement observed",
)

#: Curated explicit denials of an observed grasp *process*.  A generic
#: negation plus a grasp word is NOT enough: "not sure whether the grasp
#: succeeded" negates the outcome, not the process.  Rule D therefore only fires
#: on these explicit process-denial phrases, or on a configuration-static phrase
#: combined with an explicit "nothing visible happened" denial.
_NO_GRASP_PROCESS_PATTERNS = (
    "no visible grasp", "no grasp attempt", "no visible grasp attempt",
    "no observed grasp", "no discernible grasp", "no clear grasp",
    "no grasp process", "no visible grasping", "no gripper closure",
    "no visible closure", "no visible gripping", "did not observe a grasp",
    "未观察到抓取", "没有观察到抓取", "未见到抓取", "未见抓取", "无抓取过程",
    "未观察到抓取过程", "没有观察到抓取过程", "未见抓取过程", "未见抓取动作",
    "没有抓取动作", "未观察到夹爪闭合", "未见夹爪闭合", "没有观察到闭合过程",
    "未观察到任何抓取", "无可见抓取",
)

#: "Gripper did not change configuration" style phrases.
_CONFIG_STATIC_PATTERNS = (
    "夹爪始终闭合", "夹爪始终保持闭合", "夹爪一直闭合", "夹爪保持闭合",
    "夹爪始终静止", "夹爪保持不变", "夹爪构型不变", "夹爪状态不变",
    "gripper remains closed throughout", "gripper stayed closed throughout",
    "gripper remains open throughout", "gripper is stationary throughout",
    "gripper does not change", "gripper did not change", "gripper unchanged",
    "no change in gripper", "gripper remains unchanged",
)

#: Explicit "nothing observable happened" denials used only with the config check.
_NO_EVENT_DENIAL_PATTERNS = (
    "no visible motion", "no motion observed", "no visible event",
    "no event observed", "no visible change", "未观察到任何变化", "未见任何变化",
    "无可见变化", "未观察到运动", "未见运动", "无可观察变化",
)


@dataclass(frozen=True)
class Finding:
    check_id: str
    scope: str
    message: str
    field: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "scope": self.scope, "message": self.message,
                "field": self.field, "detail": self.detail}


def _clauses(note: str) -> list[str]:
    return [c.strip() for c in _CLAUSE_SPLIT_RE.split(note) if c.strip()]


def _event_types(payload: Mapping[str, Any]) -> list[str]:
    return [e.get("event_type") for e in (payload.get("events") or [])
            if isinstance(e, dict) and isinstance(e.get("event_type"), str)]


def _has_explicit_static_denial(note: str) -> str | None:
    lowered = note.lower()
    for pattern in _STATIC_PATTERNS:
        if pattern.lower() in lowered:
            return pattern
    # clause-scoped: a static token next to an object reference is an explicit
    # denial of object motion.
    for clause in _clauses(note):
        low = clause.lower()
        if any(t in clause or t in low for t in _STATIC_TOKENS) \
                and any(o in clause or o in low for o in _OBJECT_TOKENS):
            return clause.strip()
    return None


def _has_explicit_no_grasp(note: str) -> str | None:
    """An explicit denial of an observed grasp process (never a mere negation)."""

    lowered = note.lower()
    for pattern in _NO_GRASP_PROCESS_PATTERNS:
        if pattern.lower() in lowered:
            return pattern
    has_static = _has_pattern(note, _CONFIG_STATIC_PATTERNS)
    has_denial = _has_pattern(note, _NO_EVENT_DENIAL_PATTERNS)
    if has_static and has_denial:
        return f"{has_static} + {has_denial}"
    return None


def _has_pattern(note: str, patterns: Sequence[str]) -> str | None:
    lowered = note.lower()
    for pattern in patterns:
        if pattern.lower() in lowered:
            return pattern
    return None


def check_phase_event_consistency(payload: Mapping[str, Any]) -> list[Finding]:
    """Return review candidates.  Never mutates ``payload``."""

    if not isinstance(payload, Mapping):
        return []
    phase = payload.get("motion_phase")
    relations = [r for r in (payload.get("object_relation") or []) if isinstance(r, str)]
    types = _event_types(payload)
    note = payload.get("observation_note")
    note = note if isinstance(note, str) else ""

    findings: list[Finding] = []

    # -- Rule A: displacement phase without object_motion ------------------
    if phase in DISPLACEMENT_PHASES and "object_motion" not in types:
        findings.append(Finding(
            "PHASE_OBJECT_MOTION_MISSING_CANDIDATE", SCOPE_CANDIDATE,
            f"motion_phase='{phase}' 声称物体位移，但 events 未声明 object_motion。"
            "需人工复核是 Phase 误判还是 Event 漏报。",
            field="events", detail={"motion_phase": phase, "event_types": types},
        ))

    # -- Rule B: moving_with_gripper relation without object_motion --------
    if "moving_with_gripper" in relations and "object_motion" not in types:
        findings.append(Finding(
            "RELATION_OBJECT_MOTION_MISSING_CANDIDATE", SCOPE_CANDIDATE,
            "object_relation 声称 'moving_with_gripper'，但 events 未声明 "
            "object_motion。需人工复核两者是否一致。",
            field="events", detail={"event_types": types, "object_relation": relations},
        ))

    # -- Rule C: explicit "object is static" note with object_motion event --
    if "object_motion" in types and note:
        hit = _has_explicit_static_denial(note)
        if hit:
            findings.append(Finding(
                "OBJECT_MOTION_NOTE_CONFLICT_CANDIDATE", SCOPE_CANDIDATE,
                f"observation_note 明确否定物体位移（'{hit}'），但 events 声明了 "
                "object_motion。",
                field="events", detail={"note_token": hit, "event_types": types},
            ))

    # -- Rule D: grasp_attempt with an explicit "no grasp process" note ----
    if "grasp_attempt" in types and note:
        hit = _has_explicit_no_grasp(note)
        if hit:
            findings.append(Finding(
                "GRASP_EVENT_NOTE_CONFLICT_CANDIDATE", SCOPE_CANDIDATE,
                "events 声明 grasp_attempt，但 observation_note 明确否定抓取过程："
                f"'{hit}'。",
                field="events", detail={"note_token": hit, "event_types": types},
            ))

    return findings


def review_annotation(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Non-destructive review envelope for one already-validated annotation."""

    findings = check_phase_event_consistency(payload)
    return {
        "phase_event_qc_version": PHASE_EVENT_QC_VERSION,
        "review_status": "REVIEW_CANDIDATE" if findings else "NO_FINDING",
        "findings": [f.to_dict() for f in findings],
    }


def summarize(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for finding in findings:
        key = finding["check_id"]
        out[key] = out.get(key, 0) + 1
    return out
