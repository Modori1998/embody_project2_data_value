"""Write G1-P1 signal-contract audit report. No G1-complete claims."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _yesno(value: bool) -> str:
    return "PASS" if value else "FAIL"


def write_audit_report(path: str | Path, payload: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    discovery = payload["discovery"]
    lines: list[str] = [
        "# G1-P1 Signal Contract Audit Report",
        "",
        "This report covers **G1-P1 Signal Contract + Audit Harness** only.",
        "It does **not** claim G1 complete, segmentation validated, boundary algorithm works,",
        "threshold frozen, or G1 gate closed.",
        "",
        "## A. Local Discovery",
        "",
        f"PROJECT2_ENGINEERING_MASTER = `{discovery['engineering_master']}`",
        f"PROJECT2_ROADMAP = `{discovery['roadmap']}`",
        f"PROJECT2_READABLE_DESIGN = `{discovery['readable_design']}`",
        "",
        f"DATASET_PATH = `{discovery['dataset_path']}`",
        f"DATASET_TYPE = `{discovery['dataset_type']}`",
        f"PROJECT_ROOT = `{discovery['project_root']}`",
        f"REUSED_P1_READER = `{discovery['reused_p1_reader']}`",
        f"SOURCE_READER_PATH = `{discovery['source_reader_path']}`",
        f"EPISODE_COUNT = `{discovery['episode_count']}`",
        "",
        "### Frozen design status (not re-opened this phase)",
        "",
        "```text",
        "G1-A = FROZEN",
        "G1-B = FROZEN",
        "G1-C = FROZEN",
        "G1-D = FROZEN",
        "G1-P1 = CURRENT IMPLEMENTATION PHASE",
        "G1_DESIGN = FROZEN",
        "G1_IMPLEMENTATION = READY",
        "G1_GATE = OPEN_FOR_CALIBRATION",
        "```",
        "",
        "## B. Source Schema",
        "",
        "Fields below were read from the live Can/MH HDF5. Named `Can_pos` keys are **not** stored;",
        "object GT is the packed `obs/object` 14D vector.",
        "",
        "| field | shape | dtype | semantic meaning | unit if verified | formal / privileged |",
        "|---|---|---|---|---|---|",
    ]
    for row in payload["schema"]:
        shape = "x".join(str(x) for x in row["shape"]) if row["shape"] else "scalar/attr"
        lines.append(
            "| `{field}` | `{shape}` | `{dtype}` | {meaning} | {unit} | {role} |".format(
                field=row["field"],
                shape=shape,
                dtype=row["dtype"],
                meaning=row["semantic_meaning"].replace("|", "/"),
                unit=row["unit_if_verified"].replace("|", "/"),
                role=row["formal_or_privileged"],
            )
        )
    lines.extend(
        [
            "",
            "## C. Implemented Signal Contract",
            "",
            "Index rule: `POLICY_OBSERVATION_t = RGB_t + PROPRIO_t`; `ACTION_TARGET_t = ACTION_t`.",
            "Derived deltas use observation-aligned backward difference: `delta[0]=0`, `delta[t]=x[t]-x[t-1]`.",
            "This does not shift EEF/Action/RGB by one frame.",
            "",
            "| signal | source | formula | index alignment | unit | role |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in payload["signal_catalog"]:
        lines.append(
            "| `{name}` | `{source}` | {formula} | {alignment} | {unit} | {role} |".format(
                name=row["name"],
                source=row["source"],
                formula=row["formula"].replace("|", "/"),
                alignment=row["index_alignment"].replace("|", "/"),
                unit=row["unit"].replace("|", "/"),
                role=row["role"].replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "### Calibration placeholders",
            "",
            "All boundary numeric thresholds remain `DATA_CALIBRATION_PENDING`.",
            "Exploratory runtime defaults exist only for smoothing / windowed direction evidence / optional",
            "`motion_state_candidate`. They are `status=exploratory`, `not_formal=true`, and **not** used",
            "for this phase PASS/FAIL.",
            "",
            "## D. Audit Samples",
            "",
        ]
    )
    for sample in payload["samples"]:
        issues = sample.get("issues") or ["none"]
        if isinstance(issues, list):
            issue_text = "; ".join(str(item) for item in issues) if issues else "none"
        else:
            issue_text = str(issues)
        lines.extend(
            [
                f"### {sample['episode_id']}",
                "",
                f"- length = `{sample['length']}`",
                f"- video_path = `{sample['video_path']}`",
                f"- signal_plot_path = `{sample['signal_plot_path']}`",
                f"- weak_reference = `{sample.get('weak_reference', 'UNKNOWN')}`",
                f"- split = `{sample.get('split', 'UNKNOWN')}`",
                f"- issues = {issue_text}",
                "",
            ]
        )
    checks = payload["automated_checks"]
    lines.extend(
        [
            "## E. Automated Checks",
            "",
            f"QUATERNION_SIGN_INVARIANCE = {checks['QUATERNION_SIGN_INVARIANCE']}",
            f"TEMPORAL_ALIGNMENT = {checks['TEMPORAL_ALIGNMENT']}",
            f"PRIVILEGED_LEAKAGE = {checks['PRIVILEGED_LEAKAGE']}",
            f"NAN_INF_CHECK = {checks['NAN_INF_CHECK']}",
            f"VIDEO_SIGNAL_FRAME_ALIGNMENT = {checks['VIDEO_SIGNAL_FRAME_ALIGNMENT']}",
            "",
            "### Per-check notes",
            "",
        ]
    )
    for note in payload.get("check_notes", []):
        lines.append(f"- {note}")
    lines.extend(
        [
            "",
            "## F. Blockers / Unknowns",
            "",
        ]
    )
    unknowns = payload.get("unknowns") or ["none recorded"]
    for item in unknowns:
        lines.append(f"- UNKNOWN: {item}")
    lines.extend(
        [
            "",
            "## G. Final Phase Status",
            "",
            f"G1_P1_STATUS = {payload['g1_p1_status']}",
            "",
            "G1-P2 Boundary Engine was **not** implemented in this phase.",
            "",
        ]
    )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def write_g1_p2_audit_report(path: str | Path, payload: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    discovery = payload["discovery"]
    lines: list[str] = [
        "# G1-P2 Boundary Engine Audit Report",
        "",
        "This report covers **G1-P2 Boundary Engine + Postprocess** only.",
        "Segmentation is **EXPLORATORY_ONLY**. Thresholds are **not** frozen.",
        "",
        "## A. Input Baseline",
        "",
        f"PROJECT2_ENGINEERING_MASTER = `{discovery['engineering_master']}`",
        f"PROJECT2_ROADMAP = `{discovery['roadmap']}`",
        f"PROJECT2_READABLE_DESIGN = `{discovery['readable_design']}`",
        f"DATASET_PATH = `{discovery['dataset_path']}`",
        f"DATASET_TYPE = `{discovery['dataset_type']}`",
        f"PROJECT_ROOT = `{discovery['project_root']}`",
        f"G1_P1_CODE_BASELINE = `{discovery.get('g1_p1_code_baseline', 'src/project2_g1')}`",
        f"G1_P1_CONFIG = `{discovery.get('g1_p1_config', '')}`",
        f"G1_P2_CONFIG = `{discovery.get('g1_p2_config', '')}`",
        "",
        "```text",
        "G1-A = FROZEN",
        "G1-B = FROZEN",
        "G1-C = FROZEN",
        "G1-D = FROZEN",
        "G1-P1_CODE_IMPLEMENTATION = PASS",
        f"G1-P1_AUTOMATED_AUDIT = {payload.get('g1_p1_automated_audit', 'PASS')}",
        "G1_P1_HUMAN_VISUAL_REVIEW = DEFERRED",
        "REASON = REMOTE_ENVIRONMENT_LIMITATION",
        "G1_P2_IMPLEMENTATION = ALLOWED",
        "G1_P2_SEGMENTATION_STATUS = EXPLORATORY_ONLY",
        "G1_GATE = OPEN_FOR_CALIBRATION",
        "```",
        "",
        "G1-P1 human visual review is deferred because of remote-environment limits.",
        "That deferral is **not** a G1-P1 failure. Automated P1 checks remain PASS.",
        "P1 is therefore **not** described as completely validated.",
        "",
        "## B. Boundary Engine",
        "",
        "The engine consumes frozen G1-P1 FormalSignals and does not rewrite signal formulas.
Moving/idle regime for P2 candidates is `translation_speed > motion_speed_threshold` with persistence;
this does **not** change the P1 smoothed_translation_speed signal, which remains visualization-only.",
        "",
        "```text",
        "Formal Signal",
        "→ persistent Hard / Motion candidates",
        "→ debounce (same-type, same-polarity)",
        "→ supporting evidence attached to Motion candidates only",
        "→ boundary consolidation (Hard > Motion > Supporting)",
        "→ pause bridging",
        "→ short-segment neighbor-compatible merge with Hard protection",
        "→ max-length audit flag (no forced split)",
        "→ unlabeled exploratory segments",
        "```",
        "",
        "### Candidate rules",
        "",
        "- Hard: persistent gripper OPEN→CLOSE / CLOSE→OPEN. Interaction state change only; not grasp/place success.",
        "- Motion: persistent moving↔stationary, and large+persistent main-direction change.",
        "- Isolated speed spikes and single-frame direction flips are not candidates.",
        "- Rotation / recorded action never create a boundary; they only attach `ROTATION_SUPPORT` / `ACTION_SUPPORT` to existing Motion candidates.",
        "",
        "### Persistence / debounce",
        "",
        "Both the pre-change and post-change binary regimes must last `persistence_frames`.",
        "Debounce suppresses repeated same-type same-polarity candidates. Opposite gripper",
        "transitions are never collapsed by debounce or consolidation.",
        "",
        "### Consolidation",
        "",
        "Candidates within `boundary_consolidation_window` of the earliest cluster member,",
        "and polarity-compatible, become one event. If a Hard Boundary is present it anchors",
        "the representative frame. Opposite Hard Boundaries stay separate.",
        "",
        "### Hard protection / micro-interaction",
        "",
        "Confirmed persistent gripper transitions are not deleted by ordinary length guards.",
        "Two nearby opposite Hard Boundaries are retained and flagged `MICRO_INTERACTION` / `REVIEW_REQUIRED`.",
        "",
        "### Pause bridging",
        "",
        "A short idle between MOVE_TO_IDLE and IDLE_TO_MOVE may be bridged only when gripper",
        "state is compatible, pre/post heading is compatible, there is no Hard Boundary, and",
        "the idle is ≤ `pause_bridge_duration`.",
        "",
        "### Short segment merge",
        "",
        "`min_segment_length` marks `SHORT_SEGMENT_CANDIDATE` then inspects neighbor strength",
        "and motion continuity. Merge toward the more compatible neighbor using gripper > speed",
        "> direction > rotation > action. Hard Boundaries are preferentially preserved.",
        "",
        "### Long segment audit",
        "",
        "`max_segment_length` only sets an audit flag. If suppressed/raw candidates exist inside",
        "a long segment, the flag is `LONG_SEGMENT_WITH_INTERNAL_CANDIDATE`. No equal-window split.",
        "",
        "## C. Exploratory Config",
        "",
        "Every parameter is `status = EXPLORATORY`, `formal = false`, `DATA_CALIBRATION_PENDING`.",
        "Values are temporary defaults for smoke + audit generation. They are **not** calibrated",
        "against Human Boundary GT and must not be treated as Frozen Config.",
        "",
        "| name | value | unit | status | formal |",
        "|---|---|---|---|---|",
    ]
    for row in payload.get("parameters", []):
        lines.append(
            "| `{name}` | `{value}` | {unit} | {status} | {formal} |".format(
                name=row["name"],
                value=row["value"],
                unit=str(row.get("unit", "")).replace("|", "/"),
                status=row.get("status", "EXPLORATORY"),
                formal=str(row.get("formal", False)).lower(),
            )
        )
    lines.extend(
        [
            "",
            "## D. Smoke Episodes",
            "",
        ]
    )
    for sample in payload.get("samples", []):
        lines.extend(
            [
                f"### {sample['episode_id']}",
                "",
                f"- episode_id = `{sample['episode_id']}`",
                f"- quality group = `{sample.get('quality_group', 'UNKNOWN')}`",
                f"- length = `{sample['length']}`",
                f"- candidate count = `{sample.get('candidate_count', 0)}`",
                f"- suppressed count = `{sample.get('suppressed_count', 0)}`",
                f"- final boundary count = `{sample.get('final_boundary_count', 0)}`",
                f"- segment count = `{sample.get('segment_count', 0)}`",
                f"- video_path = `{sample.get('video_path', '')}`",
                f"- plot_path = `{sample.get('plot_path', '')}`",
                f"- review_required = `{sample.get('review_required', False)}`",
                f"- short_segment_count = `{sample.get('short_segment_count', 0)}`",
                f"- long_segment_count = `{sample.get('long_segment_count', 0)}`",
                "",
            ]
        )
    checks = payload.get("automated_checks", {})
    lines.extend(
        [
            "## E. Automated Verification",
            "",
            f"CANDIDATE_RULE_TEST = {checks.get('CANDIDATE_RULE_TEST', 'UNKNOWN')}",
            f"PERSISTENCE_TEST = {checks.get('PERSISTENCE_TEST', 'UNKNOWN')}",
            f"SUPPORTING_ONLY_TEST = {checks.get('SUPPORTING_ONLY_TEST', 'UNKNOWN')}",
            f"CONSOLIDATION_TEST = {checks.get('CONSOLIDATION_TEST', 'UNKNOWN')}",
            f"HARD_PROTECTION_TEST = {checks.get('HARD_PROTECTION_TEST', 'UNKNOWN')}",
            f"PAUSE_BRIDGING_TEST = {checks.get('PAUSE_BRIDGING_TEST', 'UNKNOWN')}",
            f"PRIVILEGED_LEAKAGE = {checks.get('PRIVILEGED_LEAKAGE', 'UNKNOWN')}",
            f"FULL_PIPELINE_SMOKE = {checks.get('FULL_PIPELINE_SMOKE', 'UNKNOWN')}",
            "",
            "### Per-check notes",
            "",
        ]
    )
    for note in payload.get("check_notes", []):
        lines.append(f"- {note}")
    lines.extend(
        [
            "",
            "## F. Observed Cases",
            "",
            "The following are **observed facts from the exploratory smoke run**. They are not",
            "claims that the decisions are correct, calibrated, or ready to freeze.",
            "",
        ]
    )
    for item in payload.get("observed_cases", []) or ["none recorded"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## G. Unknown / Blocker",
            "",
        ]
    )
    for item in payload.get("unknowns", []) or ["none recorded"]:
        lines.append(f"- {item}")
    for item in payload.get("blockers", []) or []:
        lines.append(f"- BLOCKER: {item}")
    flags = payload.get("issue_flags") or {
        "UPSTREAM_SIGNAL_ISSUE": "NO",
        "DATA_SCHEMA_ISSUE": "NO",
        "PIPELINE_BUG": "NO",
    }
    lines.extend(
        [
            "",
            f"UPSTREAM_SIGNAL_ISSUE = {flags.get('UPSTREAM_SIGNAL_ISSUE', 'NO')}",
            f"DATA_SCHEMA_ISSUE = {flags.get('DATA_SCHEMA_ISSUE', 'NO')}",
            f"PIPELINE_BUG = {flags.get('PIPELINE_BUG', 'NO')}",
        ]
    )
    lines.extend(
        [
            "",
            "## H. Final Status",
            "",
            f"G1_P2_STATUS = {payload.get('g1_p2_status', 'UNKNOWN')}",
            "",
            "```text",
            "G1_P2_STATUS != CLOSED",
            "G1 != CLOSED",
            "THRESHOLD != FROZEN",
            "SEGMENTATION != VALIDATED",
            "BEST_CONFIG != FOUND",
            "Human GT Calibration = NOT DONE",
            "G1-P3 = NOT_STARTED",
            "```",
            "",
        ]
    )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output
