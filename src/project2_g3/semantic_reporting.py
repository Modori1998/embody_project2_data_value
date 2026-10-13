"""P2-G3 versioned annotation reporting.

The v0.2 Output Design requires uncertainty to be reported **field by field**
rather than as one aggregate abstention number, and it forbids comparing
``event_assessment`` against v0.1 (which had no such field) as if the metric
were identical.

This module therefore reports:

* version-agnostic engineering metrics (JSON/Schema validity, frame-reference
  validity, latency, VRAM, truncation, status counts);
* **field-level** uncertainty rates;
* ``event_assessment``-specific rates that are emitted as ``NOT_APPLICABLE``
  for a v0.1 record set instead of being silently zeroed.

Nothing here computes semantic accuracy.  Without independent human reference
the semantic metrics are ``NOT_ESTIMABLE``, and that string is what the report
carries.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping, Sequence

NOT_APPLICABLE = "NOT_APPLICABLE"
NOT_ESTIMABLE = "NOT_ESTIMABLE"

#: Decisive (non-abstaining) motion phases.
_DECISIVE_PHASES = (
    "approach", "grasp", "lift", "transport", "place", "retract", "other",
)


def _payload(record: Mapping[str, Any]) -> Mapping[str, Any]:
    return record.get("model_payload") or record.get("parsed") or {}


def _guard_statuses(record: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    validation = record.get("validation") or {}
    return list(validation.get("findings") or record.get("findings") or [])


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def compute_rates(
    records: Sequence[Mapping[str, Any]],
    *,
    version: str,
    has_event_assessment: bool | None = None,
) -> dict[str, Any]:
    """Compute the reporting metric set for one version's records.

    ``records`` items must expose (at least):
    ``parse_ok``, ``schema_ok``, ``frame_evidence_ok``, ``status``,
    ``model_payload``, ``wall_seconds``, ``vram_used_after_mib``,
    ``finish_reason`` and ``validation`` (with ``findings``).
    """

    attempted = len(records)
    if has_event_assessment is None:
        has_event_assessment = version.endswith("V0_2_CANDIDATE")

    parse_ok = sum(1 for r in records if r.get("parse_ok"))
    schema_ok = sum(1 for r in records if r.get("schema_ok"))
    frame_ok = sum(1 for r in records if r.get("frame_evidence_ok"))
    truncated = sum(1 for r in records if r.get("finish_reason") == "length")

    status_counts: Counter[str] = Counter()
    for r in records:
        status_counts[str(r.get("status"))] += 1

    check_counts: Counter[str] = Counter()
    scope_counts: Counter[str] = Counter()
    for r in records:
        for f in _guard_statuses(r):
            check_counts[str(f.get("check_id"))] += 1
            scope_counts[str(f.get("scope"))] += 1

    illegal_refs = 0
    cross_refs = 0
    for r in records:
        validation = r.get("validation") or {}
        illegal_refs += len(validation.get("invalid_references") or [])
        cross_refs += len(validation.get("cross_boundary_references") or [])

    # ---- field-level uncertainty ---------------------------------------
    phase_uncertain = 0
    quality_low = 0
    whole_abstained = 0
    event_visible = 0
    events_nonempty = 0
    assess_insufficient = 0
    decisive_phase = 0

    phase_dist: Counter[str] = Counter()
    gripper_dist: Counter[str] = Counter()
    quality_dist: Counter[str] = Counter()
    assessment_dist: Counter[str] = Counter()
    relation_dist: Counter[str] = Counter()
    event_type_dist: Counter[str] = Counter()
    outcome_dist: Counter[str] = Counter()
    contingency: Counter[tuple[str, str]] = Counter()

    for r in records:
        p = _payload(r)
        if not p:
            continue
        phase = p.get("motion_phase")
        gripper = p.get("gripper_state")
        quality = p.get("evidence_quality")
        assessment = p.get("event_assessment")
        events = p.get("events") if isinstance(p.get("events"), list) else []

        if isinstance(phase, str):
            phase_dist[phase] += 1
            if phase == "uncertain":
                phase_uncertain += 1
            if phase in _DECISIVE_PHASES:
                decisive_phase += 1
        if isinstance(gripper, str):
            gripper_dist[gripper] += 1
        if isinstance(phase, str) and isinstance(gripper, str):
            contingency[(phase, gripper)] += 1
        if isinstance(quality, str):
            quality_dist[quality] += 1
            if quality in ("partial", "insufficient"):
                quality_low += 1
        if isinstance(assessment, str):
            assessment_dist[assessment] += 1
            if assessment == "event_visible":
                event_visible += 1
            if assessment == "insufficient_evidence":
                assess_insufficient += 1
        for rel in (p.get("object_relation") or []):
            if isinstance(rel, str):
                relation_dist[rel] += 1
        if events:
            events_nonempty += 1
        for event in events:
            if isinstance(event, dict):
                if isinstance(event.get("event_type"), str):
                    event_type_dist[event["event_type"]] += 1
                if isinstance(event.get("event_outcome"), str):
                    outcome_dist[event["event_outcome"]] += 1

        relations = p.get("object_relation")
        relations_abstain = bool(relations) and all(
            rel == "uncertain" for rel in relations if isinstance(rel, str)
        ) and len(relations) == sum(1 for rel in relations if rel == "uncertain")
        if phase == "uncertain" and gripper == "uncertain" and relations_abstain:
            whole_abstained += 1

    wall = [r.get("wall_seconds") for r in records if isinstance(r.get("wall_seconds"), (int, float))]
    vram = [r.get("vram_used_after_mib") for r in records
            if isinstance(r.get("vram_used_after_mib"), (int, float))]

    closed_gripper = gripper_dist.get("closed", 0)
    grasp_phase = phase_dist.get("grasp", 0)
    grasp_and_closed = contingency.get(("grasp", "closed"), 0)

    rates: dict[str, Any] = {
        "version": version,
        "denominator": attempted,
        "model_requests_attempted": attempted,
        # -- engineering ---------------------------------------------------
        "json_parse_rate": _rate(parse_ok, attempted),
        "schema_valid_rate": _rate(schema_ok, attempted),
        "frame_reference_valid_rate": _rate(frame_ok, attempted),
        "review_required_rate": _rate(status_counts.get("REVIEW_REQUIRED", 0), attempted),
        "truncated_output_count": truncated,
        "illegal_frame_reference_count": illegal_refs,
        "cross_boundary_reference_count": cross_refs,
        "mean_wall_seconds": round(sum(wall) / len(wall), 3) if wall else None,
        "peak_vram_used_mib": max(vram) if vram else None,
        "qc_status_counts": dict(status_counts),
        "finding_counts_by_check": dict(check_counts),
        "finding_counts_by_scope": dict(scope_counts),
        # -- field-level uncertainty ---------------------------------------
        "motion_phase_uncertain_rate": _rate(phase_uncertain, attempted),
        "evidence_quality_partial_or_insufficient_rate": _rate(quality_low, attempted),
        "whole_annotation_abstained_rate": _rate(whole_abstained, attempted),
        "events_nonempty_rate": _rate(events_nonempty, attempted),
        "decisive_motion_phase_rate": _rate(decisive_phase, attempted),
        # -- distributions -------------------------------------------------
        "motion_phase_distribution": dict(phase_dist),
        "gripper_state_distribution": dict(gripper_dist),
        "evidence_quality_distribution": dict(quality_dist),
        "object_relation_distribution": dict(relation_dist),
        "event_type_distribution": dict(event_type_dist),
        "event_outcome_distribution": dict(outcome_dist),
        # -- phase/gripper co-variation ------------------------------------
        "grasp_phase_count": grasp_phase,
        "closed_gripper_count": closed_gripper,
        "grasp_phase_with_closed_gripper_count": grasp_and_closed,
        "closed_gripper_to_grasp_rate": _rate(grasp_and_closed, closed_gripper),
        "phase_gripper_contingency": {
            f"{phase}|{gripper}": count for (phase, gripper), count in contingency.items()
        },
        # -- semantic ------------------------------------------------------
        "semantic_accuracy": NOT_ESTIMABLE,
        "semantic_accuracy_note": (
            "No independent human semantic reference was collected; accuracy / "
            "precision / recall / F1 are NOT_ESTIMABLE. Do not fabricate them."
        ),
    }

    if has_event_assessment:
        rates.update({
            "event_assessment_distribution": dict(assessment_dist),
            "event_assessment_insufficient_evidence_rate": _rate(assess_insufficient, attempted),
            "event_visible_rate": _rate(event_visible, attempted),
        })
    else:
        rates.update({
            "event_assessment_distribution": NOT_APPLICABLE,
            "event_assessment_insufficient_evidence_rate": NOT_APPLICABLE,
            "event_visible_rate": NOT_APPLICABLE,
            "event_assessment_note": (
                "v0.1 had no event_assessment field; this metric is NOT_APPLICABLE "
                "and must not be compared across versions as if identical."
            ),
        })
    return rates


def paired_comparison(
    v01: Mapping[str, Any], v02: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """The Owner-required paired comparison table (v0.1 vs v0.2)."""

    def row(metric: str, key: str, note: str = "") -> dict[str, Any]:
        return {
            "metric": metric,
            "v0_1": v01.get(key, NOT_APPLICABLE),
            "v0_2": v02.get(key, NOT_APPLICABLE),
            "note": note,
        }

    rows = [
        row("JSON 可解析率", "json_parse_rate"),
        row("Schema 合法率", "schema_valid_rate",
            "各自按对应版本的 Schema 判定；v0.1 无 event_assessment 要求"),
        row("帧引用合法率", "frame_reference_valid_rate"),
        row("非法帧引用数", "illegal_frame_reference_count"),
        row("跨段引用数", "cross_boundary_reference_count"),
        row("主要动作类别分布", "motion_phase_distribution"),
        row("声明式动作阶段比例", "decisive_motion_phase_rate"),
        row("grasp 阶段数", "grasp_phase_count"),
        row("closed 夹爪数", "closed_gripper_count"),
        row("grasp 与 closed 同时出现数", "grasp_phase_with_closed_gripper_count"),
        row("closed→grasp 共变率", "closed_gripper_to_grasp_rate"),
        row("非空事件比例", "events_nonempty_rate"),
        row("evidence_quality 分布", "evidence_quality_distribution"),
        row("motion_phase uncertain 率", "motion_phase_uncertain_rate"),
        row("evidence_quality partial/insufficient 比例",
            "evidence_quality_partial_or_insufficient_rate"),
        row("整条标注完全弃权率", "whole_annotation_abstained_rate"),
        row("event_assessment 分布", "event_assessment_distribution",
            "v0.1 无此字段 → NOT_APPLICABLE，不得跨版本当作同一指标比较"),
        row("event_visible 比例", "event_visible_rate"),
        row("REVIEW_REQUIRED 比例", "review_required_rate"),
        row("冲突候选总数", "finding_counts_by_scope"),
        row("截断次数", "truncated_output_count"),
        row("平均耗时 (s)", "mean_wall_seconds"),
        row("显存峰值 (MiB)", "peak_vram_used_mib"),
        row("人工参考符合情况", "semantic_accuracy",
            "无独立人工金标 → NOT_ESTIMABLE"),
    ]
    return rows


def render_paired_markdown(rows: Iterable[Mapping[str, Any]]) -> str:
    """Render the paired comparison table as Markdown."""

    def fmt(value: Any) -> str:
        if isinstance(value, dict):
            if not value:
                return "{}"
            return ", ".join(f"{k}={v}" for k, v in sorted(value.items()))
        return str(value)

    lines = ["| 指标 | v0.1 | v0.2 | 说明 |", "| --- | --- | --- | --- |"]
    for r in rows:
        lines.append(
            f"| {r['metric']} | {fmt(r['v0_1'])} | {fmt(r['v0_2'])} | {r.get('note', '')} |"
        )
    return "\n".join(lines)


def evaluate_gates(rates: Mapping[str, Any], gates: Mapping[str, Any]) -> dict[str, Any]:
    """Apply pre-registered engineering gates to one version's rates."""

    def get(key: str, default: float = 0.0) -> float:
        value = rates.get(key)
        return float(value) if isinstance(value, (int, float)) else default

    out: dict[str, Any] = {
        "truncated_outputs": {
            "observed": rates.get("truncated_output_count"),
            "max": gates["truncated_outputs_max"],
            "pass": get("truncated_output_count") <= gates["truncated_outputs_max"],
        },
        "illegal_frame_references": {
            "observed": rates.get("illegal_frame_reference_count"),
            "max": gates["illegal_frame_references_max"],
            "pass": get("illegal_frame_reference_count") <= gates["illegal_frame_references_max"],
        },
        "cross_boundary_references": {
            "observed": rates.get("cross_boundary_reference_count"),
            "max": gates["cross_boundary_references_max"],
            "pass": get("cross_boundary_reference_count") <= gates["cross_boundary_references_max"],
        },
        "json_parse_rate": {
            "observed": rates.get("json_parse_rate"),
            "min": gates["json_parse_rate_min"],
            "pass": get("json_parse_rate") >= gates["json_parse_rate_min"],
        },
        "schema_valid_rate": {
            "observed": rates.get("schema_valid_rate"),
            "min": gates["schema_valid_rate_min"],
            "pass": get("schema_valid_rate") >= gates["schema_valid_rate_min"],
        },
        "frame_reference_valid_rate": {
            "observed": rates.get("frame_reference_valid_rate"),
            "min": gates["frame_reference_valid_rate_min"],
            "pass": get("frame_reference_valid_rate") >= gates["frame_reference_valid_rate_min"],
        },
        "no_invalid_output_classified_valid": {
            "note": (
                "Enforced structurally: INVALID_MODEL_OUTPUT is decided before "
                "VALID, and a schema-invalid label can never be reported VALID."
            ),
            "pass": True,
        },
    }
    out["all_gates_pass"] = all(v.get("pass") for v in out.values() if "pass" in v)
    return out
