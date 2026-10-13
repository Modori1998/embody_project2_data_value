"""P2-G3 deterministic QC for the candidate structured annotation.

Three check families, deliberately separated by *what can actually be proven*:

A. **JSON / Schema** -- parseability, required keys, types, enum membership,
   forbidden extra fields, truncation.  Provable, fail-closed.
B. **Frame evidence** -- every cited frame is looked up in the immutable
   request manifest.  Frame *existence*, ownership and scope are provable.
   Frame *existence* is NOT visual truth: citing a legal frame proves the
   citation is well-formed, never that the visual judgement is right.
C. **Label consistency** -- contradictions among the fields of one annotation.
   These are ``*_CANDIDATE`` findings: the model contradicts itself, but a
   program cannot decide which side is true.  They route to human review and
   are never auto-corrected.

Hard rule: the validator **never mutates the model answer**.  It returns
findings; the caller stores the original bytes untouched next to them.

Status vocabulary (aligned with the Owner Freeze):

``PROCESSING_ERROR``      transport/server failure, no usable reply
``INVALID_INPUT``         the *request* was malformed (pre-call, fail closed)
``INVALID_MODEL_OUTPUT``  reply is unparseable / schema-invalid / cites
                          impossible frames
``REVIEW_REQUIRED``       structurally valid but carries review candidates
``UNRESOLVED``            structurally valid, no findings, model honestly
                          abstained on the substantive fields
``VALID``                 structurally valid, no findings, no abstention
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field as dc_field
from typing import Any, Iterable, Mapping, Sequence

from . import semantic_schema as S

# --------------------------------------------------------------------------- #
# statuses / severities
# --------------------------------------------------------------------------- #
PROCESSING_ERROR = "PROCESSING_ERROR"
INVALID_INPUT = "INVALID_INPUT"
INVALID_MODEL_OUTPUT = "INVALID_MODEL_OUTPUT"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
UNRESOLVED = "UNRESOLVED"
VALID = "VALID"

#: ``DETERMINISTIC`` findings are structurally provable.  ``CANDIDATE`` findings
#: are semantic contradictions that require a human to adjudicate.
SCOPE_DETERMINISTIC = "DETERMINISTIC"
SCOPE_CANDIDATE = "CANDIDATE"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Finding:
    check_id: str
    scope: str
    message: str
    # NOTE: named ``field`` for the finding's target; ``dataclasses.field`` is
    # imported as ``dc_field`` so the dataclass attribute does not shadow it.
    field: str | None = None
    detail: dict[str, Any] = dc_field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out = {
            "check_id": self.check_id,
            "scope": self.scope,
            "message": self.message,
        }
        if self.field is not None:
            out["field"] = self.field
        if self.detail:
            out["detail"] = self.detail
        return out


@dataclass(frozen=True)
class FrameEntry:
    """One immutable, caller-owned request-frame identity."""

    frame_index: int
    role: str
    source_episode_id: str
    origin_segment_id: str
    target_segment_id: str
    is_target_segment_frame: bool
    pixel_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "role": self.role,
            "source_episode_id": self.source_episode_id,
            "origin_segment_id": self.origin_segment_id,
            "target_segment_id": self.target_segment_id,
            "is_target_segment_frame": self.is_target_segment_frame,
            "pixel_sha256": self.pixel_sha256,
        }


@dataclass(frozen=True)
class TargetSegmentIdentity:
    """Trusted segment identity. Never taken from model output."""

    source_episode_id: str
    segment_id: str
    start_frame: int
    end_frame: int

    @property
    def interval(self) -> tuple[int, int]:
        return (self.start_frame, self.end_frame)

    def contains(self, frame_index: int) -> bool:
        return self.start_frame <= frame_index <= self.end_frame


@dataclass
class ValidationResult:
    status: str
    findings: list[Finding]
    parsed: dict[str, Any] | None
    parse_ok: bool
    truncated: bool = False
    schema_ok: bool = False
    frame_evidence_ok: bool = False
    cited_frames: list[int] = dc_field(default_factory=list)
    invalid_references: list[int] = dc_field(default_factory=list)
    cross_boundary_references: list[int] = dc_field(default_factory=list)
    abstained: bool = False

    @property
    def candidate_findings(self) -> list[Finding]:
        return [f for f in self.findings if f.scope == SCOPE_CANDIDATE]

    @property
    def deterministic_findings(self) -> list[Finding]:
        return [f for f in self.findings if f.scope == SCOPE_DETERMINISTIC]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "parse_ok": self.parse_ok,
            "schema_ok": self.schema_ok,
            "frame_evidence_ok": self.frame_evidence_ok,
            "truncated": self.truncated,
            "abstained": self.abstained,
            "cited_frames": sorted(self.cited_frames),
            "invalid_references": sorted(self.invalid_references),
            "cross_boundary_references": sorted(self.cross_boundary_references),
            "findings": [f.to_dict() for f in self.findings],
        }


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json_text(raw: str) -> tuple[str, bool]:
    """Return ``(candidate_json_text, fenced)``.

    A Markdown fence is tolerated for *diagnosis* (Argus does the same) but the
    caller records that the intended interface was not honoured.
    """

    if raw is None:
        return "", False
    text = raw.strip()
    match = _FENCE_RE.search(text)
    if match:
        return match.group(1).strip(), True
    return text, False


def parse_model_json(raw: str) -> tuple[dict[str, Any] | None, bool, str | None]:
    """Parse the reply into a JSON object.  Returns ``(obj, fenced, error)``."""

    text, fenced = extract_json_text(raw)
    if not text:
        return None, fenced, "EMPTY_RESPONSE"
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        # try to salvage the outermost object, but report that we did
        start, end = text.find("{"), text.rfind("}")
        if 0 <= start < end:
            try:
                value = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return None, fenced, f"JSON_DECODE_ERROR: {exc}"
        else:
            return None, fenced, f"JSON_DECODE_ERROR: {exc}"
    if not isinstance(value, dict):
        return None, fenced, f"JSON_NOT_AN_OBJECT: {type(value).__name__}"
    return value, fenced, None


# --------------------------------------------------------------------------- #
# A. schema checks
# --------------------------------------------------------------------------- #
def check_schema(payload: Mapping[str, Any]) -> list[Finding]:
    findings: list[Finding] = []

    for key in S.REQUIRED_FIELDS:
        if key not in payload:
            findings.append(Finding(
                "MISSING_REQUIRED_FIELD", SCOPE_DETERMINISTIC,
                f"缺少必填字段 '{key}'。", field=key,
            ))

    extra = [k for k in payload if k not in S.MODEL_OWNED_FIELDS]
    for key in extra:
        if key in S.CALLER_OWNED_FIELDS:
            findings.append(Finding(
                "CALLER_OWNED_FIELD_IN_MODEL_OUTPUT", SCOPE_DETERMINISTIC,
                f"模型输出包含由调用方注入的可信字段 '{key}'，不得采信。", field=key,
            ))
        else:
            findings.append(Finding(
                "FORBIDDEN_EXTRA_FIELD", SCOPE_DETERMINISTIC,
                f"不允许的额外字段 '{key}'。", field=key,
            ))

    # -- scalar enums ------------------------------------------------------
    for name in ("motion_phase", "gripper_state", "evidence_quality"):
        if name not in payload:
            continue
        value = payload[name]
        if not isinstance(value, str):
            findings.append(Finding(
                "WRONG_TYPE", SCOPE_DETERMINISTIC,
                f"'{name}' 期望字符串，实际 {type(value).__name__}。", field=name,
            ))
        elif value not in S.ENUM_TABLE[name]:
            findings.append(Finding(
                "ILLEGAL_ENUM", SCOPE_DETERMINISTIC,
                f"'{name}' 取值 '{value}' 不在候选枚举中。", field=name,
                detail={"allowed": list(S.ENUM_TABLE[name])},
            ))

    # -- object_relation array --------------------------------------------
    if "object_relation" in payload:
        value = payload["object_relation"]
        if not isinstance(value, list):
            findings.append(Finding(
                "WRONG_TYPE", SCOPE_DETERMINISTIC,
                f"'object_relation' 期望数组，实际 {type(value).__name__}。",
                field="object_relation",
            ))
        else:
            if not value:
                findings.append(Finding(
                    "EMPTY_OBJECT_RELATION", SCOPE_DETERMINISTIC,
                    "'object_relation' 为空数组；无法判断时应使用 ['uncertain']。",
                    field="object_relation",
                ))
            for item in value:
                if not isinstance(item, str) or item not in S.OBJECT_RELATION:
                    findings.append(Finding(
                        "ILLEGAL_ENUM", SCOPE_DETERMINISTIC,
                        f"'object_relation' 含非法取值 {item!r}。",
                        field="object_relation",
                        detail={"allowed": list(S.OBJECT_RELATION)},
                    ))
            if len(set(v for v in value if isinstance(v, str))) != len(value):
                findings.append(Finding(
                    "DUPLICATE_ENUM_VALUE", SCOPE_DETERMINISTIC,
                    "'object_relation' 含重复取值。", field="object_relation",
                ))

    # -- segment-level evidence indices -----------------------------------
    _check_index_array(payload, "evidence_frame_indices", findings, required=False)

    # -- events ------------------------------------------------------------
    events = payload.get("events")
    if events is not None:
        if not isinstance(events, list):
            findings.append(Finding(
                "WRONG_TYPE", SCOPE_DETERMINISTIC,
                f"'events' 期望数组，实际 {type(events).__name__}。", field="events",
            ))
        else:
            for pos, event in enumerate(events):
                if not isinstance(event, dict):
                    findings.append(Finding(
                        "WRONG_TYPE", SCOPE_DETERMINISTIC,
                        f"events[{pos}] 期望对象，实际 {type(event).__name__}。",
                        field="events",
                    ))
                    continue
                for key in S.REQUIRED_EVENT_FIELDS:
                    if key not in event:
                        findings.append(Finding(
                            "MISSING_REQUIRED_FIELD", SCOPE_DETERMINISTIC,
                            f"events[{pos}] 缺少字段 '{key}'。", field="events",
                            detail={"event_index": pos},
                        ))
                for key in event:
                    if key not in S.REQUIRED_EVENT_FIELDS:
                        findings.append(Finding(
                            "FORBIDDEN_EXTRA_FIELD", SCOPE_DETERMINISTIC,
                            f"events[{pos}] 含不允许的额外字段 '{key}'。", field="events",
                            detail={"event_index": pos},
                        ))
                for name in ("event_type", "event_outcome"):
                    if name not in event:
                        continue
                    value = event[name]
                    if not isinstance(value, str):
                        findings.append(Finding(
                            "WRONG_TYPE", SCOPE_DETERMINISTIC,
                            f"events[{pos}].{name} 期望字符串，实际 {type(value).__name__}。",
                            field="events", detail={"event_index": pos},
                        ))
                    elif value not in S.ENUM_TABLE[name]:
                        findings.append(Finding(
                            "ILLEGAL_ENUM", SCOPE_DETERMINISTIC,
                            f"events[{pos}].{name} 取值 '{value}' 不在候选枚举中。",
                            field="events",
                            detail={"event_index": pos, "allowed": list(S.ENUM_TABLE[name])},
                        ))
                _check_index_array(event, "evidence_frame_indices", findings,
                                   required=True, where=f"events[{pos}]")

    # -- observation_note --------------------------------------------------
    note = payload.get("observation_note")
    if isinstance(note, str):
        if len(note) > S.NOTE_MAX_CHARS:
            findings.append(Finding(
                "NOTE_TOO_LONG", SCOPE_DETERMINISTIC,
                f"observation_note 长度 {len(note)} 超过上限 {S.NOTE_MAX_CHARS}。",
                field="observation_note",
            ))
        if len(note.strip()) == 0:
            findings.append(Finding(
                "EMPTY_NOTE", SCOPE_DETERMINISTIC,
                "observation_note 为空字符串。", field="observation_note",
            ))
    elif note is not None:
        findings.append(Finding(
            "WRONG_TYPE", SCOPE_DETERMINISTIC,
            f"'observation_note' 期望字符串，实际 {type(note).__name__}。",
            field="observation_note",
        ))

    return findings


def _check_index_array(
    container: Mapping[str, Any],
    key: str,
    findings: list[Finding],
    *,
    required: bool,
    where: str | None = None,
) -> None:
    label = f"{where}.{key}" if where else key
    if key not in container:
        return
    value = container[key]
    if not isinstance(value, list):
        findings.append(Finding(
            "WRONG_TYPE", SCOPE_DETERMINISTIC,
            f"{label} 期望数组，实际 {type(value).__name__}。", field=key,
        ))
        return
    if required and not value:
        findings.append(Finding(
            "EMPTY_EVIDENCE_INDICES", SCOPE_DETERMINISTIC,
            f"{label} 为空；事件证据不得为空。", field=key,
        ))
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            findings.append(Finding(
                "WRONG_TYPE", SCOPE_DETERMINISTIC,
                f"{label} 含非整数值 {item!r}。", field=key,
            ))


# --------------------------------------------------------------------------- #
# B. frame evidence checks
# --------------------------------------------------------------------------- #
def collect_cited_frames(payload: Mapping[str, Any]) -> list[tuple[str, int]]:
    """Every ``(citation_site, frame_index)`` the model asserted."""

    cited: list[tuple[str, int]] = []
    top = payload.get("evidence_frame_indices")
    if isinstance(top, list):
        cited.extend(("evidence_frame_indices", v) for v in top if isinstance(v, int)
                     and not isinstance(v, bool))
    events = payload.get("events")
    if isinstance(events, list):
        for pos, event in enumerate(events):
            if not isinstance(event, dict):
                continue
            frames = event.get("evidence_frame_indices")
            if isinstance(frames, list):
                cited.extend((f"events[{pos}].evidence_frame_indices", v)
                             for v in frames if isinstance(v, int)
                             and not isinstance(v, bool))
    return cited


def check_manifest_integrity(
    manifest: Sequence[FrameEntry],
    identity: TargetSegmentIdentity,
) -> list[Finding]:
    """Pre-call / structural integrity of the trusted request manifest."""

    findings: list[Finding] = []
    if not manifest:
        findings.append(Finding(
            "EMPTY_FRAME_MANIFEST", SCOPE_DETERMINISTIC,
            "请求帧清单为空，无法构成合法模型输入。",
        ))
        return findings

    seen: set[int] = set()
    for entry in manifest:
        if entry.frame_index in seen:
            findings.append(Finding(
                "DUPLICATE_FRAME_IN_MANIFEST", SCOPE_DETERMINISTIC,
                f"帧 {entry.frame_index} 在清单中重复。",
            ))
        seen.add(entry.frame_index)
        if entry.source_episode_id != identity.source_episode_id:
            findings.append(Finding(
                "FRAME_SOURCE_EPISODE_MISMATCH", SCOPE_DETERMINISTIC,
                f"帧 {entry.frame_index} 的 Episode '{entry.source_episode_id}' "
                f"与目标 '{identity.source_episode_id}' 不一致。",
                detail={"frame_index": entry.frame_index},
            ))
        if entry.target_segment_id != identity.segment_id:
            findings.append(Finding(
                "FRAME_TARGET_SEGMENT_MISMATCH", SCOPE_DETERMINISTIC,
                f"帧 {entry.frame_index} 标注的目标段 '{entry.target_segment_id}' "
                f"与 '{identity.segment_id}' 不一致。",
                detail={"frame_index": entry.frame_index},
            ))
        if not SHA256_RE.match(entry.pixel_sha256 or ""):
            findings.append(Finding(
                "FRAME_PIXEL_SHA_INVALID", SCOPE_DETERMINISTIC,
                f"帧 {entry.frame_index} 的 pixel_sha256 非法。",
                detail={"frame_index": entry.frame_index},
            ))
        if entry.is_target_segment_frame and not identity.contains(entry.frame_index):
            findings.append(Finding(
                "TARGET_FRAME_OUTSIDE_INTERVAL", SCOPE_DETERMINISTIC,
                f"被标为目标段帧的 {entry.frame_index} 落在冻结区间 "
                f"[{identity.start_frame},{identity.end_frame}] 之外。",
                detail={"frame_index": entry.frame_index},
            ))
    return findings


def check_frame_evidence(
    payload: Mapping[str, Any],
    manifest: Sequence[FrameEntry],
    identity: TargetSegmentIdentity,
) -> tuple[list[Finding], list[int], list[int], list[int]]:
    """Validate every citation.  Returns ``(findings, cited, invalid, cross)``."""

    by_index = {entry.frame_index: entry for entry in manifest}
    findings: list[Finding] = []
    cited: list[int] = []
    invalid: list[int] = []
    cross: list[int] = []

    for site, frame_index in collect_cited_frames(payload):
        cited.append(frame_index)
        entry = by_index.get(frame_index)
        if entry is None:
            invalid.append(frame_index)
            findings.append(Finding(
                "FRAME_NOT_IN_REQUEST_MANIFEST", SCOPE_DETERMINISTIC,
                f"{site} 引用了未随请求提供的帧 {frame_index}。",
                field=site, detail={"frame_index": frame_index},
            ))
            continue
        if not identity.contains(frame_index):
            invalid.append(frame_index)
            findings.append(Finding(
                "FRAME_OUTSIDE_TARGET_SEGMENT", SCOPE_DETERMINISTIC,
                f"{site} 引用的帧 {frame_index} 落在冻结目标区间 "
                f"[{identity.start_frame},{identity.end_frame}] 之外。",
                field=site, detail={"frame_index": frame_index},
            ))
        if not entry.is_target_segment_frame:
            cross.append(frame_index)
            findings.append(Finding(
                "TARGET_CONTEXT_CROSS_BOUNDARY", SCOPE_DETERMINISTIC,
                f"{site} 把邻居段上下文帧 {frame_index}（角色 {entry.role}，"
                f"来源段 {entry.origin_segment_id}）当作目标段事件证据引用。",
                field=site,
                detail={"frame_index": frame_index, "role": entry.role,
                        "origin_segment_id": entry.origin_segment_id},
            ))

    return findings, cited, invalid, cross


# --------------------------------------------------------------------------- #
# C. label consistency checks (candidates)
# --------------------------------------------------------------------------- #
_OPEN_WORDS = ("张开", "打开", "松开", "张开状", "opened", "is open", "open ")
_CLOSED_WORDS = ("闭合", "合拢", "夹紧", "关闭", "closed", "is closed")
_HOLD_WORDS = ("夹住", "抓住", "握住", "夹起", "已经夹", "holding", "grasped", "holding the")
_TASK_DONE_WORDS = (
    "任务完成", "完成了任务", "整个任务完成", "成功完成", "任务已成功",
    "task is complete", "task completed", "task was completed", "mission complete",
    "successfully completed the task",
)


def _note_has(note: str, words: Iterable[str]) -> str | None:
    lowered = note.lower()
    for word in words:
        if word.lower() in lowered:
            return word
    return None


def check_label_consistency(payload: Mapping[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    note = payload.get("observation_note")
    note = note if isinstance(note, str) else ""

    phase = payload.get("motion_phase")
    gripper = payload.get("gripper_state")
    relations = [r for r in (payload.get("object_relation") or []) if isinstance(r, str)]
    events = [e for e in (payload.get("events") or []) if isinstance(e, dict)]

    # -- gripper state vs note --------------------------------------------
    if note:
        open_hit = _note_has(note, _OPEN_WORDS)
        closed_hit = _note_has(note, _CLOSED_WORDS)
        if gripper == "closed" and open_hit:
            findings.append(Finding(
                "LABEL_NOTE_CONFLICT_CANDIDATE", SCOPE_CANDIDATE,
                f"gripper_state='closed'，但 observation_note 出现张开语义 '{open_hit}'。",
                field="gripper_state", detail={"note_token": open_hit},
            ))
        if gripper == "open" and closed_hit:
            findings.append(Finding(
                "LABEL_NOTE_CONFLICT_CANDIDATE", SCOPE_CANDIDATE,
                f"gripper_state='open'，但 observation_note 出现闭合语义 '{closed_hit}'。",
                field="gripper_state", detail={"note_token": closed_hit},
            ))
        hold_hit = _note_has(note, _HOLD_WORDS)
        if hold_hit and gripper == "open":
            findings.append(Finding(
                "LABEL_NOTE_CONFLICT_CANDIDATE", SCOPE_CANDIDATE,
                f"observation_note 声称握持（'{hold_hit}'），但 gripper_state='open'。",
                field="gripper_state", detail={"note_token": hold_hit},
            ))

    # -- episode-level completion claim -----------------------------------
    done_hit = _note_has(note, _TASK_DONE_WORDS) if note else None
    if done_hit:
        findings.append(Finding(
            "EPISODE_LEVEL_CLAIM_CANDIDATE", SCOPE_CANDIDATE,
            f"observation_note 断言任务级完成（'{done_hit}'）；单个 G1 段不足以支撑"
            "任务完成判断。",
            field="observation_note", detail={"note_token": done_hit},
        ))

    # -- phase vs events ---------------------------------------------------
    substantive = [e for e in events
                   if e.get("event_type") not in (None, "none_observed", "uncertain")]
    if phase == "idle" and substantive:
        findings.append(Finding(
            "PHASE_EVENT_CONFLICT_CANDIDATE", SCOPE_CANDIDATE,
            "motion_phase='idle'，但 events 中声明了实质事件。",
            field="motion_phase",
            detail={"event_types": [e.get("event_type") for e in substantive]},
        ))

    # -- none_observed mixed with other events ----------------------------
    types = [e.get("event_type") for e in events]
    if "none_observed" in types and len(events) > 1:
        findings.append(Finding(
            "EVENT_NONE_OBSERVED_MIXED_CANDIDATE", SCOPE_CANDIDATE,
            "events 同时包含 'none_observed' 与其他事件，二者互相矛盾。",
            field="events", detail={"event_types": types},
        ))

    # -- no observed event but object asserted to move with gripper -------
    # An empty ``events`` list and a lone ``none_observed`` are both claims that
    # nothing happened; asserting the object moves with the gripper in the same
    # annotation contradicts that.
    if not substantive and "moving_with_gripper" in relations:
        findings.append(Finding(
            "EVENT_RELATION_CONFLICT_CANDIDATE", SCOPE_CANDIDATE,
            "events 未声明任何实质事件，但 object_relation 声称 "
            "'moving_with_gripper'。",
            field="events", detail={"event_types": types},
        ))

    # -- definite outcome without post-event evidence ---------------------
    for pos, event in enumerate(events):
        if event.get("event_outcome") in ("success", "failure"):
            frames = event.get("evidence_frame_indices")
            if not isinstance(frames, list) or len(frames) < 2:
                findings.append(Finding(
                    "EVIDENCE_SUFFICIENCY_CANDIDATE", SCOPE_CANDIDATE,
                    f"events[{pos}] 断言确定性结果 '{event.get('event_outcome')}'，"
                    "但少于 2 个支持帧，无法体现事件前后变化。",
                    field="events", detail={"event_index": pos},
                ))

    # -- evidence_quality sufficient with no citations --------------------
    if payload.get("evidence_quality") == "sufficient":
        has_citation = bool(payload.get("evidence_frame_indices"))
        if not has_citation:
            findings.append(Finding(
                "EVIDENCE_QUALITY_WITHOUT_CITATION", SCOPE_DETERMINISTIC,
                "evidence_quality='sufficient' 但未提供任何支持帧。",
                field="evidence_quality",
            ))

    return findings


def is_abstained(payload: Mapping[str, Any]) -> bool:
    """True when the model abstained on every substantive categorical field."""

    if not isinstance(payload, Mapping):
        return False
    substantive = ("motion_phase", "gripper_state")
    for name in substantive:
        if not S.is_abstention(name, payload.get(name)):
            return False
    relations = payload.get("object_relation")
    if isinstance(relations, list) and relations:
        if not all(S.is_abstention("object_relation", r) for r in relations):
            return False
    else:
        return False
    return True


# --------------------------------------------------------------------------- #
# orchestrator
# --------------------------------------------------------------------------- #
def decide_status(findings: Sequence[Finding], *, abstained: bool) -> str:
    if any(f.scope == SCOPE_DETERMINISTIC for f in findings):
        # a structural/citation problem that is provable
        hard = {
            "MISSING_REQUIRED_FIELD", "FORBIDDEN_EXTRA_FIELD",
            "CALLER_OWNED_FIELD_IN_MODEL_OUTPUT", "WRONG_TYPE", "ILLEGAL_ENUM",
            "DUPLICATE_ENUM_VALUE", "EMPTY_OBJECT_RELATION",
            "FRAME_NOT_IN_REQUEST_MANIFEST", "FRAME_OUTSIDE_TARGET_SEGMENT",
            "TARGET_CONTEXT_CROSS_BOUNDARY",
            # The Owner Freeze lists truncated replies (especially
            # finish_reason=length) as hard-invalid / fail-closed: an incomplete
            # annotation must not be silently accepted as a short one.
            "OUTPUT_TRUNCATED",
        }
        if any(f.check_id in hard for f in findings):
            return INVALID_MODEL_OUTPUT
        return REVIEW_REQUIRED
    if any(f.scope == SCOPE_CANDIDATE for f in findings):
        return REVIEW_REQUIRED
    return UNRESOLVED if abstained else VALID


def validate_model_output(
    raw_text: str | None,
    *,
    manifest: Sequence[FrameEntry],
    identity: TargetSegmentIdentity,
    finish_reason: str | None = None,
    processing_error: str | None = None,
) -> ValidationResult:
    """Full deterministic QC of one model reply for one frozen segment."""

    if processing_error is not None:
        return ValidationResult(
            status=PROCESSING_ERROR, findings=[Finding(
                "TRANSPORT_OR_SERVER_ERROR", SCOPE_DETERMINISTIC, processing_error,
            )],
            parsed=None, parse_ok=False,
        )

    truncated = (finish_reason == "length")
    payload, fenced, error = parse_model_json(raw_text or "")

    findings: list[Finding] = []
    if truncated:
        findings.append(Finding(
            "OUTPUT_TRUNCATED", SCOPE_DETERMINISTIC,
            "输出被 token 上限截断（finish_reason=length）。",
        ))
    if fenced:
        findings.append(Finding(
            "MARKDOWN_FENCE_WRAPPER", SCOPE_DETERMINISTIC,
            "回复被 Markdown 代码围栏包裹，不符合 JSON-only 接口约定。",
        ))

    if payload is None:
        findings.append(Finding(
            "JSON_UNPARSEABLE", SCOPE_DETERMINISTIC, f"无法解析为 JSON 对象：{error}",
        ))
        return ValidationResult(
            status=INVALID_MODEL_OUTPUT, findings=findings, parsed=None,
            parse_ok=False, truncated=truncated,
        )

    findings.extend(check_schema(payload))
    frame_findings, cited, invalid, cross = check_frame_evidence(
        payload, manifest, identity
    )
    findings.extend(frame_findings)
    findings.extend(check_label_consistency(payload))

    schema_ok = not any(
        f.check_id in {
            "MISSING_REQUIRED_FIELD", "FORBIDDEN_EXTRA_FIELD", "WRONG_TYPE",
            "ILLEGAL_ENUM", "DUPLICATE_ENUM_VALUE", "EMPTY_OBJECT_RELATION",
            "CALLER_OWNED_FIELD_IN_MODEL_OUTPUT", "EMPTY_EVIDENCE_INDICES",
        } for f in findings
    ) and not truncated
    frame_ok = not invalid and not cross and not any(
        f.check_id.startswith("FRAME_") for f in findings
    )
    abstained = is_abstained(payload)
    status = decide_status(findings, abstained=abstained)

    return ValidationResult(
        status=status, findings=findings, parsed=payload, parse_ok=True,
        truncated=truncated, schema_ok=schema_ok, frame_evidence_ok=frame_ok,
        cited_frames=cited, invalid_references=invalid,
        cross_boundary_references=cross, abstained=abstained,
    )


# --------------------------------------------------------------------------- #
# provenance helpers
# --------------------------------------------------------------------------- #
def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_request_record(
    *,
    identity: TargetSegmentIdentity,
    manifest: Sequence[FrameEntry],
    prompt_sha256: str,
    model_revision: str,
    sampling: Mapping[str, Any],
) -> dict[str, Any]:
    """Caller-owned request identity.  Never taken from model output."""

    payload = {
        "source_episode_id": identity.source_episode_id,
        "segment_id": identity.segment_id,
        "segment_interval_frames": [identity.start_frame, identity.end_frame],
        "schema_version": S.SEMANTIC_SCHEMA_VERSION,
        "prompt_sha256": prompt_sha256,
        "model_revision": model_revision,
        "sampling": dict(sampling),
        "frames": [entry.to_dict() for entry in manifest],
    }
    payload["request_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return payload


# =========================================================================== #
# v0.2 validation (Owner-frozen development spec, 2026-10-13)
#
# v0.1 functions above are untouched so stored v0.1 records stay reproducible.
# v0.2 adds: the `event_assessment` field, its strict cardinality contract with
# `events`, the retirement of the v0.1 `none_observed` / `uncertain` array
# sentinels, phase-vs-note and phase-vs-quality review candidates, and a
# dedicated unsupported-outcome check.
# =========================================================================== #

#: Phases that claim observable motion.  Used by the negation-aware
#: phase/note conflict rule; ``idle`` and ``uncertain`` are deliberately
#: excluded because "no motion" is *consistent* with them.
_DECISIVE_MOTION_PHASES = (
    "approach", "grasp", "lift", "transport", "place", "retract", "other",
)

#: Generic motion vocabulary that any decisive phase implies.
_GENERIC_MOTION_WORDS = (
    "运动", "移动", "动作", "变化", "位移",
    "motion", "moved", "moves", "moving", "movement", "action", "change",
)

#: Phase-specific motion vocabulary.
_PHASE_MOTION_WORDS: dict[str, tuple[str, ...]] = {
    "approach": ("靠近", "接近", "趋近", "approach", "approaching", "advance"),
    "grasp": ("闭合", "合拢", "夹取", "夹住动作", "closing", "closes", "closure", "grasp"),
    "lift": ("提起", "抬起", "上升", "lift", "lifting", "raise", "raising"),
    "transport": ("搬运", "运送", "带过去", "carry", "carrying", "transport", "transfer"),
    "place": ("放置", "放下", "落位", "placing", "placement", "put down"),
    "retract": ("撤离", "移开", "收回", "retract", "retracting", "withdraw"),
    "other": (),
}

#: Negation cues.  Matched per clause, not across clause boundaries.
_NEGATION_CUES = (
    "未", "没有", "无", "不", "没", "未曾", "并未",
    "no ", "not ", "no-", "n't", "without", "never", "cannot", "can't",
    "unable to", "isn't", "aren't", "wasn't", "weren't",
)

#: Wording that shows a *process* (a change), not a static state.
_CLOSURE_PROCESS_WORDS = (
    "正在闭合", "逐渐闭合", "闭合过程", "过渡", "趋于闭合",
    "closing toward", "closing", "closes", "closure", "transition",
)

#: Strong event assertions used for the narrative event_assessment conflict.
_EVENT_ASSERTION_WORDS = (
    "抓取成功", "已抓住", "夹住了", "释放了", "放下动作", "滑落",
    "grasped successfully", "successfully grasped", "has grasped", "released",
    "slipped", "dropped the", "picked up the",
)

_CLAUSE_SPLIT_RE = re.compile(r"[。．.!?！？;；，,、\n]+")


class _StatusV02:
    """Status vocabulary (identical names to v0.1)."""

    PROCESSING_ERROR = PROCESSING_ERROR
    INVALID_INPUT = INVALID_INPUT
    INVALID_MODEL_OUTPUT = INVALID_MODEL_OUTPUT
    REVIEW_REQUIRED = REVIEW_REQUIRED
    UNRESOLVED = UNRESOLVED
    VALID = VALID


class _ScopeV02:
    DETERMINISTIC = SCOPE_DETERMINISTIC
    CANDIDATE = SCOPE_CANDIDATE


def _clauses(note: str) -> list[str]:
    return [c for c in _CLAUSE_SPLIT_RE.split(note) if c.strip()]


def _clause_has_negated_motion(clause: str, phase: str) -> str | None:
    """Return the matched motion word when a clause negates motion.

    Clause-scoped so that "the gripper closes; acquisition is not established"
    is not read as a contradiction.  Requires BOTH a motion word and a negation
    cue *in the same clause*, which is what stops a bare keyword match from
    producing a false positive.
    """

    lowered = clause.lower()
    has_negation = any(cue in lowered for cue in _NEGATION_CUES)
    if not has_negation:
        return None
    words = _GENERIC_MOTION_WORDS + _PHASE_MOTION_WORDS.get(phase, ())
    for word in words:
        if word.lower() in lowered:
            return word
    return None


def check_schema_v0_2(payload: Mapping[str, Any]) -> list[Finding]:
    """Structural checks for the v0.2 payload (hard-invalid where provable)."""

    findings: list[Finding] = []

    for key in S.REQUIRED_FIELDS_V0_2:
        if key not in payload:
            findings.append(Finding(
                "MISSING_REQUIRED_FIELD", SCOPE_DETERMINISTIC,
                f"缺少必填字段 '{key}'。", field=key,
            ))

    for key in payload:
        if key in S.MODEL_OWNED_FIELDS_V0_2:
            continue
        if key in S.CALLER_OWNED_FIELDS:
            findings.append(Finding(
                "CALLER_OWNED_FIELD_IN_MODEL_OUTPUT", SCOPE_DETERMINISTIC,
                f"模型输出包含由调用方注入的可信字段 '{key}'，不得采信。", field=key,
            ))
        else:
            findings.append(Finding(
                "FORBIDDEN_EXTRA_FIELD", SCOPE_DETERMINISTIC,
                f"不允许的额外字段 '{key}'。", field=key,
            ))

    # -- scalar enums (incl. the new event_assessment) --------------------
    for name in ("motion_phase", "gripper_state", "evidence_quality", "event_assessment"):
        if name not in payload:
            continue
        value = payload[name]
        if not isinstance(value, str):
            findings.append(Finding(
                "WRONG_TYPE", SCOPE_DETERMINISTIC,
                f"'{name}' 期望字符串，实际 {type(value).__name__}。", field=name,
            ))
        elif value not in S.ENUM_TABLE_V0_2[name]:
            findings.append(Finding(
                "ILLEGAL_ENUM", SCOPE_DETERMINISTIC,
                f"'{name}' 取值 '{value}' 不在 v0.2 枚举中。", field=name,
                detail={"allowed": list(S.ENUM_TABLE_V0_2[name])},
            ))

    # -- object_relation --------------------------------------------------
    if "object_relation" in payload:
        value = payload["object_relation"]
        if not isinstance(value, list):
            findings.append(Finding(
                "WRONG_TYPE", SCOPE_DETERMINISTIC,
                f"'object_relation' 期望数组，实际 {type(value).__name__}。",
                field="object_relation",
            ))
        else:
            if not value:
                findings.append(Finding(
                    "EMPTY_OBJECT_RELATION", SCOPE_DETERMINISTIC,
                    "'object_relation' 为空数组；无法判断时应使用 ['uncertain']。",
                    field="object_relation",
                ))
            for item in value:
                if not isinstance(item, str) or item not in S.OBJECT_RELATION_V0_2:
                    findings.append(Finding(
                        "ILLEGAL_ENUM", SCOPE_DETERMINISTIC,
                        f"'object_relation' 含非法取值 {item!r}。",
                        field="object_relation",
                        detail={"allowed": list(S.OBJECT_RELATION_V0_2)},
                    ))
            if len(set(v for v in value if isinstance(v, str))) != len(value):
                findings.append(Finding(
                    "DUPLICATE_ENUM_VALUE", SCOPE_DETERMINISTIC,
                    "'object_relation' 含重复取值。", field="object_relation",
                ))

    _check_index_array(payload, "evidence_frame_indices", findings, required=False)

    # -- events structure -------------------------------------------------
    events = payload.get("events")
    substantive: list[Mapping[str, Any]] = []
    if events is not None:
        if not isinstance(events, list):
            findings.append(Finding(
                "WRONG_TYPE", SCOPE_DETERMINISTIC,
                f"'events' 期望数组，实际 {type(events).__name__}。", field="events",
            ))
        else:
            for pos, event in enumerate(events):
                if not isinstance(event, dict):
                    findings.append(Finding(
                        "WRONG_TYPE", SCOPE_DETERMINISTIC,
                        f"events[{pos}] 期望对象，实际 {type(event).__name__}。",
                        field="events",
                    ))
                    continue
                substantive.append(event)
                for key in S.REQUIRED_EVENT_FIELDS_V0_2:
                    if key not in event:
                        findings.append(Finding(
                            "MISSING_REQUIRED_FIELD", SCOPE_DETERMINISTIC,
                            f"events[{pos}] 缺少字段 '{key}'。", field="events",
                            detail={"event_index": pos},
                        ))
                for key in event:
                    if key not in S.REQUIRED_EVENT_FIELDS_V0_2:
                        findings.append(Finding(
                            "FORBIDDEN_EXTRA_FIELD", SCOPE_DETERMINISTIC,
                            f"events[{pos}] 含不允许的额外字段 '{key}'。", field="events",
                            detail={"event_index": pos},
                        ))
                for name in ("event_type", "event_outcome"):
                    if name not in event:
                        continue
                    value = event[name]
                    if not isinstance(value, str):
                        findings.append(Finding(
                            "WRONG_TYPE", SCOPE_DETERMINISTIC,
                            f"events[{pos}].{name} 期望字符串，实际 {type(value).__name__}。",
                            field="events", detail={"event_index": pos},
                        ))
                    elif value not in S.ENUM_TABLE_V0_2[name]:
                        detail: dict[str, Any] = {
                            "event_index": pos, "allowed": list(S.ENUM_TABLE_V0_2[name]),
                        }
                        message = (f"events[{pos}].{name} 取值 '{value}' 不在 v0.2 枚举中。")
                        if name == "event_type" and value in ("none_observed", "uncertain"):
                            message += (
                                " v0.1 的数组哨兵值在 v0.2 已迁移到 event_assessment。"
                            )
                            detail["retired_sentinel"] = True
                        findings.append(Finding(
                            "ILLEGAL_ENUM", SCOPE_DETERMINISTIC, message,
                            field="events", detail=detail,
                        ))
                _check_index_array(event, "evidence_frame_indices", findings,
                                   required=True, where=f"events[{pos}]")

    # -- event_assessment <-> events cardinality contract -----------------
    assessment = payload.get("event_assessment")
    if isinstance(assessment, str) and assessment in S.EVENT_ASSESSMENT_V0_2 \
            and isinstance(events, list):
        rule = S.EVENT_ASSESSMENT_EVENTS_CONTRACT_V0_2[assessment]
        if rule == "NON_EMPTY_SUBSTANTIVE":
            if not substantive:
                findings.append(Finding(
                    "EVENT_ASSESSMENT_EVENTS_MISMATCH", SCOPE_DETERMINISTIC,
                    "event_assessment='event_visible' 但 events 为空；"
                    "必须至少一个带目标帧引用的实质事件。",
                    field="event_assessment",
                ))
        elif rule == "EMPTY" and substantive:
            findings.append(Finding(
                "EVENT_ASSESSMENT_EVENTS_MISMATCH", SCOPE_DETERMINISTIC,
                f"event_assessment='{assessment}' 时 events 必须为空数组，"
                f"实际有 {len(substantive)} 个事件。",
                field="event_assessment",
            ))

    # -- observation_note --------------------------------------------------
    note = payload.get("observation_note")
    if isinstance(note, str):
        if len(note) > S.NOTE_MAX_CHARS_V0_2:
            findings.append(Finding(
                "NOTE_TOO_LONG", SCOPE_DETERMINISTIC,
                f"observation_note 长度 {len(note)} 超过上限 {S.NOTE_MAX_CHARS_V0_2}。",
                field="observation_note",
            ))
        if not note.strip():
            findings.append(Finding(
                "EMPTY_NOTE", SCOPE_DETERMINISTIC,
                "observation_note 为空字符串。", field="observation_note",
            ))
    elif note is not None:
        findings.append(Finding(
            "WRONG_TYPE", SCOPE_DETERMINISTIC,
            f"'observation_note' 期望字符串，实际 {type(note).__name__}。",
            field="observation_note",
        ))

    return findings


def check_label_consistency_v0_2(payload: Mapping[str, Any]) -> list[Finding]:
    """v0.2 semantic review candidates (never auto-corrects)."""

    findings: list[Finding] = []
    note = payload.get("observation_note")
    note = note if isinstance(note, str) else ""

    phase = payload.get("motion_phase")
    gripper = payload.get("gripper_state")
    quality = payload.get("evidence_quality")
    assessment = payload.get("event_assessment")
    relations = [r for r in (payload.get("object_relation") or []) if isinstance(r, str)]
    events = [e for e in (payload.get("events") or []) if isinstance(e, dict)]

    # -- PHASE_NOTE_MOTION_CONFLICT_CANDIDATE -----------------------------
    if phase in _DECISIVE_MOTION_PHASES and note:
        for clause in _clauses(note):
            hit = _clause_has_negated_motion(clause, str(phase))
            if hit:
                findings.append(Finding(
                    "PHASE_NOTE_MOTION_CONFLICT_CANDIDATE", SCOPE_CANDIDATE,
                    f"motion_phase='{phase}'，但 observation_note 的同一分句"
                    f"否定了运动（'{hit}'）。",
                    field="motion_phase",
                    detail={"clause": clause.strip(), "motion_token": hit},
                ))
                break

    # -- EVIDENCE_PHASE_QUALITY_CONFLICT_CANDIDATE ------------------------
    if phase in _DECISIVE_MOTION_PHASES and quality in ("partial", "insufficient"):
        findings.append(Finding(
            "EVIDENCE_PHASE_QUALITY_CONFLICT_CANDIDATE", SCOPE_CANDIDATE,
            f"motion_phase='{phase}' 是明确阶段，但 evidence_quality='{quality}'；"
            "按 v0.2 Rubric 该阶段通常应为 uncertain。",
            field="evidence_quality",
            detail={"motion_phase": phase, "evidence_quality": quality},
        ))
    if phase == "uncertain" and quality == "sufficient":
        findings.append(Finding(
            "EVIDENCE_PHASE_QUALITY_CONFLICT_CANDIDATE", SCOPE_CANDIDATE,
            "motion_phase='uncertain' 但 evidence_quality='sufficient'，"
            "支持程度与结论不一致。",
            field="evidence_quality",
        ))

    # -- EVENT_OUTCOME_UNSUPPORTED_CANDIDATE ------------------------------
    for pos, event in enumerate(events):
        if event.get("event_outcome") in ("success", "failure"):
            frames = event.get("evidence_frame_indices")
            if not isinstance(frames, list) or len(frames) < 2:
                findings.append(Finding(
                    "EVENT_OUTCOME_UNSUPPORTED_CANDIDATE", SCOPE_CANDIDATE,
                    f"events[{pos}] 断言确定结果 '{event.get('event_outcome')}'，"
                    "但缺少可比较的前/后视觉支持帧（<2）。",
                    field="events", detail={"event_index": pos},
                ))

    # -- GRIPPER_CLOSED_GRASP_SHORTCUT_CANDIDATE --------------------------
    has_grasp_attempt = any(e.get("event_type") == "grasp_attempt" for e in events)
    note_shows_closure_process = bool(note) and any(
        w.lower() in note.lower() for w in _CLOSURE_PROCESS_WORDS
    )
    if phase == "grasp" and gripper == "closed" \
            and not has_grasp_attempt and not note_shows_closure_process:
        findings.append(Finding(
            "GRIPPER_CLOSED_GRASP_SHORTCUT_CANDIDATE", SCOPE_CANDIDATE,
            "motion_phase='grasp' 与 gripper_state='closed' 同时出现，"
            "但没有任何 grasp_attempt 事件或闭合过程描述；"
            "疑似由静态夹爪状态直接支撑了动作阶段。",
            field="motion_phase",
            detail={"gripper_state": gripper},
        ))

    # -- v0.1 note/enum rules retained ------------------------------------
    if note:
        open_hit = _note_has(note, _OPEN_WORDS)
        closed_hit = _note_has(note, _CLOSED_WORDS)
        if gripper == "closed" and open_hit:
            findings.append(Finding(
                "LABEL_NOTE_CONFLICT_CANDIDATE", SCOPE_CANDIDATE,
                f"gripper_state='closed'，但 observation_note 出现张开语义 '{open_hit}'。",
                field="gripper_state", detail={"note_token": open_hit},
            ))
        if gripper == "open" and closed_hit:
            findings.append(Finding(
                "LABEL_NOTE_CONFLICT_CANDIDATE", SCOPE_CANDIDATE,
                f"gripper_state='open'，但 observation_note 出现闭合语义 '{closed_hit}'。",
                field="gripper_state", detail={"note_token": closed_hit},
            ))
        hold_hit = _note_has(note, _HOLD_WORDS)
        if hold_hit and gripper == "open":
            findings.append(Finding(
                "LABEL_NOTE_CONFLICT_CANDIDATE", SCOPE_CANDIDATE,
                f"observation_note 声称握持（'{hold_hit}'），但 gripper_state='open'。",
                field="gripper_state", detail={"note_token": hold_hit},
            ))
        done_hit = _note_has(note, _TASK_DONE_WORDS)
        if done_hit:
            findings.append(Finding(
                "EPISODE_LEVEL_CLAIM_CANDIDATE", SCOPE_CANDIDATE,
                f"observation_note 断言任务级完成（'{done_hit}'）；"
                "单个 G1 段不足以支撑任务完成判断。",
                field="observation_note", detail={"note_token": done_hit},
            ))

    # -- EVENT_ASSESSMENT_CONFLICT (narrative) ----------------------------
    if assessment == "no_event_visible" and note:
        hit = _note_has(note, _EVENT_ASSERTION_WORDS)
        if hit:
            findings.append(Finding(
                "EVENT_ASSESSMENT_CONFLICT", SCOPE_CANDIDATE,
                f"event_assessment='no_event_visible'，但 observation_note "
                f"出现事件断言 '{hit}'。",
                field="event_assessment", detail={"note_token": hit},
            ))
    if assessment == "event_visible" and note and not events:
        findings.append(Finding(
            "EVENT_ASSESSMENT_CONFLICT", SCOPE_CANDIDATE,
            "event_assessment='event_visible' 但 events 为空数组。",
            field="event_assessment",
        ))

    # -- phase vs events ---------------------------------------------------
    substantive = [e for e in events if e.get("event_type") in S.EVENT_TYPE_V0_2]
    if phase == "idle" and substantive:
        findings.append(Finding(
            "PHASE_EVENT_CONFLICT_CANDIDATE", SCOPE_CANDIDATE,
            "motion_phase='idle'，但 events 中声明了实质事件。",
            field="motion_phase",
            detail={"event_types": [e.get("event_type") for e in substantive]},
        ))
    if not substantive and "moving_with_gripper" in relations \
            and assessment == "no_event_visible":
        findings.append(Finding(
            "EVENT_RELATION_CONFLICT_CANDIDATE", SCOPE_CANDIDATE,
            "event_assessment='no_event_visible' 且无实质事件，"
            "但 object_relation 声称 'moving_with_gripper'。",
            field="events",
        ))

    # -- v0.1 structural-evidence rule retained ---------------------------
    if quality == "sufficient" and not payload.get("evidence_frame_indices"):
        findings.append(Finding(
            "EVIDENCE_QUALITY_WITHOUT_CITATION", SCOPE_DETERMINISTIC,
            "evidence_quality='sufficient' 但未提供任何支持帧。",
            field="evidence_quality",
        ))

    return findings


def is_abstained_v0_2(payload: Mapping[str, Any]) -> bool:
    """Whole-annotation abstention (same definition as v0.1, per Output Design)."""

    if not isinstance(payload, Mapping):
        return False
    for name in ("motion_phase", "gripper_state"):
        if not S.is_abstention_v0_2(name, payload.get(name)):
            return False
    relations = payload.get("object_relation")
    if isinstance(relations, list) and relations:
        if not all(S.is_abstention_v0_2("object_relation", r) for r in relations):
            return False
    else:
        return False
    return True


def decide_status_v0_2(findings: Sequence[Finding], *, abstained: bool) -> str:
    hard = {
        "MISSING_REQUIRED_FIELD", "FORBIDDEN_EXTRA_FIELD",
        "CALLER_OWNED_FIELD_IN_MODEL_OUTPUT", "WRONG_TYPE", "ILLEGAL_ENUM",
        "DUPLICATE_ENUM_VALUE", "EMPTY_OBJECT_RELATION",
        "FRAME_NOT_IN_REQUEST_MANIFEST", "FRAME_OUTSIDE_TARGET_SEGMENT",
        "TARGET_CONTEXT_CROSS_BOUNDARY", "OUTPUT_TRUNCATED",
        # v0.2: the event cardinality contract is hard-invalid by Owner Freeze
        "EVENT_ASSESSMENT_EVENTS_MISMATCH",
        # v0.2: an event item is only substantive if it carries target-frame
        # citations, so a citation-less event is a contract violation rather
        # than a soft review flag.  (v0.1's decision table is left unchanged.)
        "EMPTY_EVIDENCE_INDICES",
    }
    if any(f.scope == SCOPE_DETERMINISTIC for f in findings):
        if any(f.check_id in hard for f in findings):
            return INVALID_MODEL_OUTPUT
        return REVIEW_REQUIRED
    if any(f.scope == SCOPE_CANDIDATE for f in findings):
        return REVIEW_REQUIRED
    return UNRESOLVED if abstained else VALID


def validate_model_output_v0_2(
    raw_text: str | None,
    *,
    manifest: Sequence[FrameEntry],
    identity: TargetSegmentIdentity,
    finish_reason: str | None = None,
    processing_error: str | None = None,
) -> ValidationResult:
    """Full deterministic QC of one model reply against the v0.2 contract."""

    if processing_error is not None:
        return ValidationResult(
            status=PROCESSING_ERROR, findings=[Finding(
                "TRANSPORT_OR_SERVER_ERROR", SCOPE_DETERMINISTIC, processing_error,
            )],
            parsed=None, parse_ok=False,
        )

    truncated = (finish_reason == "length")
    payload, fenced, error = parse_model_json(raw_text or "")

    findings: list[Finding] = []
    if truncated:
        findings.append(Finding(
            "OUTPUT_TRUNCATED", SCOPE_DETERMINISTIC,
            "输出被 token 上限截断（finish_reason=length）。",
        ))
    if fenced:
        findings.append(Finding(
            "MARKDOWN_FENCE_WRAPPER", SCOPE_DETERMINISTIC,
            "回复被 Markdown 代码围栏包裹，不符合 JSON-only 接口约定。",
        ))

    if payload is None:
        findings.append(Finding(
            "JSON_UNPARSEABLE", SCOPE_DETERMINISTIC, f"无法解析为 JSON 对象：{error}",
        ))
        return ValidationResult(
            status=INVALID_MODEL_OUTPUT, findings=findings, parsed=None,
            parse_ok=False, truncated=truncated,
        )

    findings.extend(check_schema_v0_2(payload))
    frame_findings, cited, invalid, cross = check_frame_evidence(
        payload, manifest, identity
    )
    findings.extend(frame_findings)
    findings.extend(check_label_consistency_v0_2(payload))

    schema_ok = not any(
        f.check_id in {
            "MISSING_REQUIRED_FIELD", "FORBIDDEN_EXTRA_FIELD", "WRONG_TYPE",
            "ILLEGAL_ENUM", "DUPLICATE_ENUM_VALUE", "EMPTY_OBJECT_RELATION",
            "CALLER_OWNED_FIELD_IN_MODEL_OUTPUT", "EMPTY_EVIDENCE_INDICES",
            "EVENT_ASSESSMENT_EVENTS_MISMATCH",
        } for f in findings
    ) and not truncated
    frame_ok = not invalid and not cross and not any(
        f.check_id.startswith("FRAME_") for f in findings
    )
    abstained = is_abstained_v0_2(payload)
    status = decide_status_v0_2(findings, abstained=abstained)

    return ValidationResult(
        status=status, findings=findings, parsed=payload, parse_ok=True,
        truncated=truncated, schema_ok=schema_ok, frame_evidence_ok=frame_ok,
        cited_frames=cited, invalid_references=invalid,
        cross_boundary_references=cross, abstained=abstained,
    )


def build_request_record_v0_2(
    *,
    identity: TargetSegmentIdentity,
    manifest: Sequence[FrameEntry],
    prompt_sha256: str,
    model_revision: str,
    sampling: Mapping[str, Any],
) -> dict[str, Any]:
    """Caller-owned request identity for a v0.2 run."""

    payload = {
        "source_episode_id": identity.source_episode_id,
        "segment_id": identity.segment_id,
        "segment_interval_frames": [identity.start_frame, identity.end_frame],
        "schema_version": S.SEMANTIC_SCHEMA_VERSION_V0_2,
        "prompt_sha256": prompt_sha256,
        "model_revision": model_revision,
        "sampling": dict(sampling),
        "frames": [entry.to_dict() for entry in manifest],
    }
    payload["request_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return payload
