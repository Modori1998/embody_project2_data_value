"""Run frozen Formal Core Retrieval Stage 2 for the 18 Final queries.

This runner reuses immutable Stage1 representations and FAISS indices. It performs
Final Retrieval and builds the blind Final Human Audit pair package only.
It does not compute P@5 and does not use Human labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_mvp.core_retrieval import (
    MOTION_REPRESENTATION_VERSION,
    VISUAL_REPRESENTATION_VERSION,
    build_blind_audit_items,
)

DEFAULT_STAGE1_RUN = ROOT / "outputs/mvp_core_retrieval_formal/mvp_core_retrieval_formal_stage1_20261009"
PROTOCOL = ROOT / "0-doc/10-design-review/Project2_MVP_Core_Retrieval_Protocol_FROZEN_v1_20261008.md"
ADDENDUM = ROOT / "0-doc/10-design-review/Project2_MVP_Core_Retrieval_Protocol_Addendum_FROZEN_v1_20261009.md"
RUBRIC = ROOT / "0-doc/10-design-review/Project2_MVP_Human_Relevance_Rubric_Clarification_FROZEN_v1_20261012.md"

PROTECTED_STAGE1_FILES = (
    "motion_segment_embeddings.npz",
    "motion_embedding_manifest.csv",
    "motion_scaler.json",
    "motion_feature_schema.json",
    "visual_segment_embeddings.npz",
    "visual_embedding_manifest.csv",
    "siglip_model_identity.json",
    "faiss_motion.index",
    "faiss_visual.index",
    "candidate_segment_manifest.csv",
    "calibration_query_manifest.csv",
    "final_query_manifest.csv",
    "calibration_motion_top5.csv",
    "calibration_visual_top5.csv",
    "m2/robot_motion_summary.csv",
    "m2/keyframe_manifest.csv",
    "m2/segment_input_manifest.csv",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_authority() -> None:
    protocol = PROTOCOL.read_text(encoding="utf-8")
    addendum = ADDENDUM.read_text(encoding="utf-8")
    rubric = RUBRIC.read_text(encoding="utf-8")
    if not all(
        value in protocol
        for value in ("DOCUMENT_STATUS = FROZEN_v1", "FINAL_QUERY_EPISODES = 18", "STRICT_BINARY_MACRO_PRECISION_AT_5")
    ):
        raise RuntimeError("STOP_FROZEN_RETRIEVAL_IDENTITY_MISMATCH: protocol")
    if not all(
        value in addendum
        for value in ("DOCUMENT_STATUS = FROZEN_v1", "HIDDEN_REPEAT", "BLIND_AUDIT_ORDER")
    ):
        raise RuntimeError("STOP_FROZEN_RETRIEVAL_IDENTITY_MISMATCH: addendum")
    if not all(
        value in rubric
        for value in (
            "DOCUMENT_STATUS = FROZEN_v1",
            "FINAL_RETRIEVAL_AUTHORIZED =",
            "YES",
            "FINAL_HUMAN_AUDIT_RUBRIC =",
            "LOCKED_TO_FROZEN_v1",
        )
    ):
        raise RuntimeError("STOP_HUMAN_RELEVANCE_RUBRIC_NOT_FROZEN")


def search_top5(
    index,
    candidate_ids: list[str],
    query: np.ndarray,
    query_episode: str,
    episode_by_segment: dict[str, str],
) -> list[tuple[str, float]]:
    scores, positions = index.search(
        np.ascontiguousarray(query[None, :], dtype=np.float32), 5
    )
    result = []
    for score, position in zip(scores[0], positions[0]):
        if position < 0:
            continue
        candidate_id = candidate_ids[int(position)]
        if episode_by_segment[candidate_id] == query_episode:
            raise RuntimeError("STOP_CROSS_EPISODE_FAILURE")
        if not np.isfinite(score):
            raise RuntimeError("STOP_NONFINITE_SIMILARITY")
        result.append((candidate_id, float(score)))
    if len(result) != 5:
        raise RuntimeError("STOP_FORMAL_TOP5_FAILURE")
    return result


def load_embedding_matrix(path: Path) -> tuple[list[str], np.ndarray]:
    with np.load(path, allow_pickle=False) as data:
        ids = [str(value) for value in data["segment_ids"].tolist()]
        matrix = np.asarray(data["embeddings"], dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[0] != len(ids) or not np.isfinite(matrix).all():
        raise RuntimeError(f"STOP_EMBEDDING_ARTIFACT_INVALID: {path.name}")
    return ids, matrix


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage1-run", type=Path, default=DEFAULT_STAGE1_RUN)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)

    import faiss

    validate_authority()
    stage1 = args.stage1_run.resolve()
    if not stage1.is_dir():
        raise FileNotFoundError(f"Stage1 Formal run missing: {stage1}")

    for relpath in PROTECTED_STAGE1_FILES:
        if not (stage1 / relpath).is_file():
            raise FileNotFoundError(f"Stage1 protected artifact missing: {relpath}")

    protected_before = {
        relpath: sha256_file(stage1 / relpath) for relpath in PROTECTED_STAGE1_FILES
    }

    stage1_meta = json.loads((stage1 / "run_meta.json").read_text(encoding="utf-8"))
    if not (
        stage1_meta.get("formal_63_episode_executed") is True
        and stage1_meta.get("calibration_retrieval_executed") is True
        and stage1_meta.get("final_query_segments_selected") is True
        and stage1_meta.get("final_retrieval_executed") is False
        and stage1_meta.get("p5_computed") is False
    ):
        raise RuntimeError("STOP_STAGE1_PROVENANCE_INVALID")

    final_manifest = read_csv(stage1 / "final_query_manifest.csv")
    if len(final_manifest) != 18:
        raise RuntimeError("STOP_FINAL_QUERY_COUNT_CHANGED")
    if (
        sum(row["assigned_gripper_class"] == "TRUE" for row in final_manifest) != 9
        or sum(row["assigned_gripper_class"] == "FALSE" for row in final_manifest) != 9
    ):
        raise RuntimeError("STOP_FINAL_QUERY_BALANCE_CHANGED")

    motion_ids, motion_matrix = load_embedding_matrix(stage1 / "motion_segment_embeddings.npz")
    visual_ids, visual_matrix = load_embedding_matrix(stage1 / "visual_segment_embeddings.npz")
    if motion_ids != visual_ids:
        raise RuntimeError("STOP_MOTION_VISUAL_SEGMENT_ID_MISMATCH")
    if motion_matrix.shape[1] != 17 or visual_matrix.shape[1] != 768:
        raise RuntimeError("STOP_FORMAL_REPRESENTATION_DIMENSION_MISMATCH")

    motion_index_by_id = {segment_id: index for index, segment_id in enumerate(motion_ids)}
    if len(motion_index_by_id) != len(motion_ids):
        raise RuntimeError("STOP_DUPLICATE_SEGMENT_ID")

    embedding_manifest = read_csv(stage1 / "motion_embedding_manifest.csv")
    episode_by_segment = {
        row["segment_id"]: row["episode_id"] for row in embedding_manifest
    }
    motion_summary = read_csv(stage1 / "m2/robot_motion_summary.csv")
    motion_by_id = {row["segment_id"]: row for row in motion_summary}

    candidate_manifest = read_csv(stage1 / "candidate_segment_manifest.csv")
    candidate_manifest = sorted(
        candidate_manifest, key=lambda row: int(row["candidate_index_row"])
    )
    candidate_ids = [row["segment_id"] for row in candidate_manifest]
    if len(candidate_ids) != 203 or len(set(candidate_ids)) != 203:
        raise RuntimeError("STOP_CANDIDATE_SEGMENT_COUNT_CHANGED")

    motion_index = faiss.read_index(str(stage1 / "faiss_motion.index"))
    visual_index = faiss.read_index(str(stage1 / "faiss_visual.index"))
    if (
        motion_index.d != 17
        or visual_index.d != 768
        or motion_index.ntotal != 203
        or visual_index.ntotal != 203
    ):
        raise RuntimeError("STOP_FAISS_INDEX_IDENTITY_MISMATCH")

    final_motion = []
    final_visual = []
    for query in final_manifest:
        query_id = query["segment_id"]
        query_episode = query["episode_id"]
        if query_id not in motion_index_by_id or query_id not in episode_by_segment:
            raise RuntimeError(f"STOP_FINAL_QUERY_SEGMENT_MISSING: {query_id}")

        for rank, (candidate_id, score) in enumerate(
            search_top5(
                motion_index,
                candidate_ids,
                motion_matrix[motion_index_by_id[query_id]],
                query_episode,
                episode_by_segment,
            ),
            1,
        ):
            final_motion.append(
                {
                    "query_segment_id": query_id,
                    "candidate_segment_id": candidate_id,
                    "rank": rank,
                    "similarity": score,
                    "representation_version": MOTION_REPRESENTATION_VERSION,
                }
            )
        for rank, (candidate_id, score) in enumerate(
            search_top5(
                visual_index,
                candidate_ids,
                visual_matrix[motion_index_by_id[query_id]],
                query_episode,
                episode_by_segment,
            ),
            1,
        ):
            final_visual.append(
                {
                    "query_segment_id": query_id,
                    "candidate_segment_id": candidate_id,
                    "rank": rank,
                    "similarity": score,
                    "representation_version": VISUAL_REPRESENTATION_VERSION,
                }
            )

    audit_rows, repeat_pairs, unique_pair_count = build_blind_audit_items(
        final_motion,
        final_visual,
        cohort="FINAL",
        repeat_n=12,
        item_prefix="FIN",
    )
    for row in audit_rows:
        query = motion_by_id[row["query_segment_id"]]
        candidate = motion_by_id[row["candidate_segment_id"]]
        row.update(
            {
                "query_duration_sec": query["duration_sec"],
                "query_gripper_start_state": query["gripper_start_state"],
                "query_gripper_end_state": query["gripper_end_state"],
                "query_gripper_transition_present": query["gripper_transition_present"],
                "query_eef_displacement_xyz": query["eef_displacement_xyz"],
                "query_coarse_direction_change_rad": query[
                    "coarse_direction_change_rad"
                ],
                "candidate_duration_sec": candidate["duration_sec"],
                "candidate_gripper_start_state": candidate["gripper_start_state"],
                "candidate_gripper_end_state": candidate["gripper_end_state"],
                "candidate_gripper_transition_present": candidate[
                    "gripper_transition_present"
                ],
                "candidate_eef_displacement_xyz": candidate[
                    "eef_displacement_xyz"
                ],
                "candidate_coarse_direction_change_rad": candidate[
                    "coarse_direction_change_rad"
                ],
                "review_label": "",
                "query_bad_segment": "",
            }
        )

    output = ROOT / "outputs/mvp_core_retrieval_formal" / args.run_id
    if output.exists():
        raise FileExistsError(f"immutable output run already exists: {output}")
    output.mkdir(parents=True)

    write_csv(output / "final_motion_top5.csv", final_motion)
    write_csv(output / "final_visual_top5.csv", final_visual)
    write_csv(output / "final_human_audit_pairs.csv", audit_rows)

    protected_after = {
        relpath: sha256_file(stage1 / relpath) for relpath in PROTECTED_STAGE1_FILES
    }
    if protected_before != protected_after:
        raise RuntimeError("STOP_STAGE1_ARTIFACT_MUTATED")

    if len(final_motion) != 90 or len(final_visual) != 90:
        raise RuntimeError("STOP_FINAL_TOP5_COUNT_FAILURE")
    if len(repeat_pairs) != 12 or len(audit_rows) != unique_pair_count + 12:
        raise RuntimeError("STOP_FINAL_BLIND_AUDIT_COUNT_FAILURE")
    if any(
        episode_by_segment[row["query_segment_id"]]
        == episode_by_segment[row["candidate_segment_id"]]
        for row in [*final_motion, *final_visual]
    ):
        raise RuntimeError("STOP_FINAL_CROSS_EPISODE_FAILURE")

    run_meta = {
        "run_id": args.run_id,
        "created_at": datetime.now().astimezone().isoformat(),
        "git_base": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "stage1_run": str(stage1),
        "stage1_git_base": stage1_meta.get("git_base"),
        "protocol_sha256": sha256_file(PROTOCOL),
        "addendum_sha256": sha256_file(ADDENDUM),
        "rubric_sha256": sha256_file(RUBRIC),
        "protected_stage1_sha256": protected_after,
        "final_query_count": 18,
        "final_query_balance": {"TRUE": 9, "FALSE": 9},
        "candidate_segment_count": 203,
        "motion_top5_rows": len(final_motion),
        "visual_top5_rows": len(final_visual),
        "blind_audit_unique_pairs": unique_pair_count,
        "hidden_repeat_pairs": len(repeat_pairs),
        "blind_audit_total_items": len(audit_rows),
        "final_retrieval_executed": True,
        "human_audit_executed": False,
        "human_labels_frozen": False,
        "p5_computed": False,
        "formal_gate_decision_made": False,
    }
    (output / "run_meta.json").write_text(
        json.dumps(run_meta, indent=2) + "\n", encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "output_run": str(output),
                "final_queries": 18,
                "motion_top5_rows": len(final_motion),
                "visual_top5_rows": len(final_visual),
                "blind_audit_unique_pairs": unique_pair_count,
                "hidden_repeat_pairs": 12,
                "blind_audit_total_items": len(audit_rows),
                "p5_computed": False,
                "next": "BUILD_FINAL_TEMPORAL_BLIND_HUMAN_AUDIT",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
