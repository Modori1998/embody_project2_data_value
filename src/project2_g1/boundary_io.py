"""CSV / template writers for the G1-P2 Boundary Audit Package."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from .boundary_engine import BoundaryDecision, EngineResult

HUMAN_REVIEW_VALUES = ("VALID", "REDUNDANT", "MISALIGNED", "MISSED_BOUNDARY")
REASON_CODES = (
    "REDUNDANT_SHORT_PAUSE",
    "REDUNDANT_DIRECTION_JITTER",
    "REDUNDANT_ROTATION",
    "REDUNDANT_ACTION_JITTER",
    "MISSED_GRIPPER_TRANSITION",
    "MISSED_MOVE_STOP",
    "MISSED_STOP_MOVE",
    "MISSED_DIRECTION_CHANGE",
    "MISALIGNED_GRIPPER",
    "MISALIGNED_MOTION_CHANGE",
    "OTHER",
)

REVIEW_TEMPLATE_FIELDS = (
    "episode_id",
    "predicted_boundary_id",
    "predicted_frame",
    "human_review",
    "corrected_frame",
    "human_added_frame",
    "reason_code",
    "note",
    "reviewer",
    "review_version",
)

DECISION_ORDER = (
    "KEEP",
    "RETAIN_HARD",
    "SUPPRESS_DEBOUNCE",
    "MERGE_CONSOLIDATION",
    "SUPPRESS_SHORT_PAUSE",
    "MERGE_LEFT",
    "MERGE_RIGHT",
    "REVIEW_REQUIRED",
)


def _write_csv(path: Path, fieldnames: Iterable[str], rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in writer.fieldnames})
    return path


def _decision_rows(result: EngineResult) -> list[dict[str, Any]]:
    rows = []
    for candidate in result.candidates:
        decision = result.decisions.get(
            candidate.candidate_id,
            BoundaryDecision(candidate.candidate_id, "REVIEW_REQUIRED", "missing decision"),
        )
        row = decision.to_row()
        row["episode_id"] = result.episode_id
        row["frame"] = candidate.frame
        row["candidate_type"] = candidate.candidate_type
        rows.append(row)
    return rows


def write_episode_audit_tables(episode_dir: Path, result: EngineResult) -> dict[str, str]:
    episode_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = _write_csv(
        episode_dir / "candidate_boundaries.csv",
        (
            "episode_id",
            "candidate_id",
            "frame",
            "candidate_type",
            "primary_reason",
            "supporting_reasons",
            "evidence_value",
            "persistence_status",
            "source_signal",
            "config_version",
            "polarity",
        ),
        [item.to_row() for item in result.candidates],
    )
    decision_path = _write_csv(
        episode_dir / "boundary_decisions.csv",
        (
            "episode_id",
            "candidate_id",
            "frame",
            "candidate_type",
            "decision",
            "reason",
            "target_boundary_id",
        ),
        _decision_rows(result),
    )
    final_path = _write_csv(
        episode_dir / "final_boundaries.csv",
        (
            "boundary_id",
            "episode_id",
            "frame",
            "candidate_type",
            "reason",
            "representative_candidate_id",
            "member_candidate_ids",
            "member_candidate_types",
            "member_candidate_frames",
            "member_candidate_count",
            "supporting_reasons",
            "review_flags",
            "polarity",
            "config_version",
            "segmentation_version",
        ),
        [item.to_row() for item in result.final_events],
    )
    segment_path = _write_csv(
        episode_dir / "segment_manifest.csv",
        (
            "segment_id",
            "source_episode_id",
            "start_frame",
            "end_frame",
            "duration_frames",
            "duration_sec",
            "left_boundary_id",
            "right_boundary_id",
            "left_boundary_reason",
            "right_boundary_reason",
            "segmentation_version",
            "config_version",
            "short_segment_flag",
            "long_segment_flag",
            "review_required",
            "segment_label",
            "semantic_phase",
            "review_flags",
        ),
        [item.to_row() for item in result.segments],
    )
    return {
        "candidate_boundaries": str(candidate_path.resolve()),
        "boundary_decisions": str(decision_path.resolve()),
        "final_boundaries": str(final_path.resolve()),
        "segment_manifest": str(segment_path.resolve()),
    }


def empty_review_row(episode_id: str, **overrides: Any) -> dict[str, Any]:
    row = {key: "" for key in REVIEW_TEMPLATE_FIELDS}
    row["episode_id"] = episode_id
    row.update(overrides)
    return row


def build_human_review_rows(results: list[EngineResult], extra_missed_slots: int = 3) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for event in result.final_events:
            rows.append(
                empty_review_row(
                    result.episode_id,
                    predicted_boundary_id=event.boundary_id,
                    predicted_frame=event.frame,
                )
            )
        for _ in range(int(extra_missed_slots)):
            rows.append(
                empty_review_row(
                    result.episode_id,
                    note="optional extra row for MISSED_BOUNDARY (human-added; not auto-labeled)",
                )
            )
    return rows


def write_human_review_template(path: Path, results: list[EngineResult]) -> Path:
    codebook = path.with_name("human_boundary_review_codebook.json")
    codebook.write_text(
        json.dumps(
            {
                "human_review": list(HUMAN_REVIEW_VALUES),
                "reason_code": list(REASON_CODES),
                "note": (
                    "Schema only. Do not auto-generate human labels. "
                    "MISSED_BOUNDARY may be added as a new row that does not map to a predicted boundary. "
                    "MISALIGNED requires corrected_frame. Extra empty rows are provided per episode."
                ),
                "auto_generated_human_labels": False,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return _write_csv(path, REVIEW_TEMPLATE_FIELDS, build_human_review_rows(results))
