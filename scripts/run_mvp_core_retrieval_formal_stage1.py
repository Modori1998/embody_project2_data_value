"""Run frozen Formal Core Retrieval Stage 1 through blind Calibration packaging."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_mvp.core_retrieval import (
    ACTION_INDICES,
    CONTINUOUS_INDICES,
    GRIPPER_INDICES,
    KINEMATICS_INDICES,
    MOTION_REPRESENTATION_VERSION,
    MOTION_VECTOR_DIM,
    VISUAL_REPRESENTATION_VERSION,
    build_blind_audit_items,
    candidate_segment_rows,
    fit_motion_scaler,
    motion_raw_vector,
    pool_unique_frame_embeddings,
    select_query_segments,
    validate_siglip2_embedding,
)
from project2_mvp.m2_materializer import materialize_m2


MODEL_ID = "google/siglip2-base-patch16-224"
MODEL_REVISION = "75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2"
PROTOCOL = ROOT / "0-doc/10-design-review/Project2_MVP_Core_Retrieval_Protocol_FROZEN_v1_20261008.md"
ADDENDUM = ROOT / "0-doc/10-design-review/Project2_MVP_Core_Retrieval_Protocol_Addendum_FROZEN_v1_20261009.md"
MANIFEST_DOC = ROOT / "0-doc/10-design-review/Project2_MVP_Core_Retrieval_Manifest_FROZEN_v1_20261009.md"
MANIFEST_CSV = ROOT / "0-doc/10-design-review/Project2_MVP_Core_Retrieval_Manifest_FROZEN_v1_20261009.csv"


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


def validate_authority() -> tuple[list[dict[str, str]], dict[str, list[str]]]:
    protocol = PROTOCOL.read_text(encoding="utf-8")
    addendum = ADDENDUM.read_text(encoding="utf-8")
    manifest_doc = MANIFEST_DOC.read_text(encoding="utf-8")
    if not all(value in protocol for value in ("DOCUMENT_STATUS = FROZEN_v1", "MVP_M4_MOTION_REP_V1", "MVP_M4_SIGLIP2_REP_V1")):
        raise RuntimeError("STOP_FROZEN_RETRIEVAL_IDENTITY_MISMATCH: protocol")
    if not all(value in addendum for value in ("DOCUMENT_STATUS = FROZEN_v1", "QUERY_EPISODE_ASSIGN", "HIDDEN_REPEAT", "BLIND_AUDIT_ORDER")):
        raise RuntimeError("STOP_FROZEN_RETRIEVAL_IDENTITY_MISMATCH: addendum")
    if not all(value in manifest_doc for value in ("DOCUMENT_STATUS = FROZEN_v1", "TOTAL_SELECTED_UNIQUE = 63")):
        raise RuntimeError("STOP_FROZEN_RETRIEVAL_IDENTITY_MISMATCH: manifest")
    rows = read_csv(MANIFEST_CSV)
    cohorts = {
        name: [row["episode_id"] for row in sorted(rows, key=lambda row: int(row["selection_rank"])) if row["cohort"] == name]
        for name in ("CANDIDATE_BANK", "CALIBRATION_QUERY", "FINAL_QUERY")
    }
    if len(rows) != 63 or len({row["episode_id"] for row in rows}) != 63:
        raise RuntimeError("STOP_FROZEN_RETRIEVAL_IDENTITY_MISMATCH: manifest count")
    if {name: len(ids) for name, ids in cohorts.items()} != {"CANDIDATE_BANK": 36, "CALIBRATION_QUERY": 9, "FINAL_QUERY": 18}:
        raise RuntimeError("STOP_FROZEN_RETRIEVAL_IDENTITY_MISMATCH: cohort count")
    return rows, cohorts


def search_top5(index, candidate_ids: list[str], query: np.ndarray, query_episode: str, episode_by_segment: dict[str, str]) -> list[tuple[str, float]]:
    scores, positions = index.search(np.ascontiguousarray(query[None, :], dtype=np.float32), 5)
    result = []
    for score, position in zip(scores[0], positions[0]):
        if position < 0:
            continue
        candidate_id = candidate_ids[int(position)]
        if episode_by_segment[candidate_id] == query_episode:
            raise RuntimeError("STOP_CROSS_EPISODE_FAILURE")
        result.append((candidate_id, float(score)))
    if len(result) != 5 or not np.isfinite([score for _, score in result]).all():
        raise RuntimeError("STOP_FORMAL_TOP5_FAILURE")
    return result


def create_audit_html(
    output: Path,
    audit_rows: list[dict],
    keyframes: dict[str, list[dict[str, str]]],
    motion_by_id: dict[str, dict[str, str]],
) -> None:
    assets = output / "human_audit_assets"
    assets.mkdir()

    def strip(segment_id: str) -> str:
        images = []
        for row in sorted(keyframes[segment_id], key=lambda item: int(item["frame_index"])):
            source = "../m2/" + row["png_relpath"]
            images.append(
                f'<figure><img src="{html.escape(source)}" alt="keyframe"><figcaption>{html.escape(row["roles"])}</figcaption></figure>'
            )
        return "".join(images)

    cards = []
    for row in audit_rows:
        query_id = row["query_segment_id"]
        candidate_id = row["candidate_segment_id"]
        query = motion_by_id[query_id]
        candidate = motion_by_id[candidate_id]
        cards.append(f"""
<section>
<h2>{html.escape(row['audit_item_id'])}</h2>
<h3>Query</h3><div class="strip">{strip(query_id)}</div>
<p>{html.escape(query_id)} | duration={html.escape(query['duration_sec'])}s | gripper={html.escape(query['gripper_start_state'])}→{html.escape(query['gripper_end_state'])} | transition={html.escape(query['gripper_transition_present'])} | displacement={html.escape(query['eef_displacement_xyz'])} | direction-change={html.escape(query['coarse_direction_change_rad'])}</p>
<h3>Candidate</h3><div class="strip">{strip(candidate_id)}</div>
<p>{html.escape(candidate_id)} | duration={html.escape(candidate['duration_sec'])}s | gripper={html.escape(candidate['gripper_start_state'])}→{html.escape(candidate['gripper_end_state'])} | transition={html.escape(candidate['gripper_transition_present'])} | displacement={html.escape(candidate['eef_displacement_xyz'])} | direction-change={html.escape(candidate['coarse_direction_change_rad'])}</p>
<p>Label: RELEVANT / PARTIAL / NOT_RELEVANT / BAD_SEGMENT / UNSURE</p>
</section>""")
    page = """<!doctype html><meta charset="utf-8"><title>Calibration Blind Human Audit</title>
<style>body{font-family:Arial,sans-serif;max-width:1200px;margin:auto}section{border:1px solid #aaa;padding:16px;margin:20px 0}.strip{display:flex;gap:8px;flex-wrap:wrap}figure{margin:0}img{width:160px;height:160px;object-fit:contain;border:1px solid #ddd}figcaption{text-align:center}</style>
<h1>Calibration Blind Human Audit</h1><p>Review in audit order. Retrieval method, scores, ranks, and repeat status are intentionally hidden.</p>""" + "\n".join(cards)
    (assets / "index.html").write_text(page, encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model-cache", type=Path, default=ROOT / "outputs/model_cache/huggingface")
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args(argv)

    import faiss
    import torch
    import transformers
    from transformers import AutoModel, AutoProcessor

    manifest_rows, cohorts = validate_authority()
    output = ROOT / "outputs/mvp_core_retrieval_formal" / args.run_id
    if output.exists():
        raise FileExistsError(f"immutable output run already exists: {output}")
    output.mkdir(parents=True)
    git_base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    episode_ids = [row["episode_id"] for row in sorted(manifest_rows, key=lambda row: (row["cohort"], int(row["selection_rank"])))]
    m2_output = output / "m2"
    m2_result = materialize_m2(m2_output, episode_ids, git_base=git_base)
    if m2_result["episodes_processed"] != 63:
        raise RuntimeError("STOP_FORMAL_M2_MATERIALIZATION_FAILURE")

    motion_rows = read_csv(m2_output / "robot_motion_summary.csv")
    keyframe_rows = read_csv(m2_output / "keyframe_manifest.csv")
    cohort_by_episode = {row["episode_id"]: row["cohort"] for row in manifest_rows}
    episode_by_segment = {row["segment_id"]: row["source_episode_id"] for row in motion_rows}
    motion_by_id = {row["segment_id"]: row for row in motion_rows}
    keyframes_by_segment: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in keyframe_rows:
        keyframes_by_segment[row["segment_id"]].append(row)

    candidate_rows = candidate_segment_rows(motion_rows, cohorts["CANDIDATE_BANK"])
    raw_by_id = {row["segment_id"]: motion_raw_vector(row) for row in motion_rows}
    scaler = fit_motion_scaler([raw_by_id[row["segment_id"]] for row in candidate_rows])
    motion_ids = [row["segment_id"] for row in motion_rows]
    motion_matrix = np.stack([scaler.transform(raw_by_id[segment_id]) for segment_id in motion_ids]).astype(np.float32)
    np.savez_compressed(output / "motion_segment_embeddings.npz", segment_ids=np.asarray(motion_ids), embeddings=motion_matrix)
    write_csv(output / "motion_embedding_manifest.csv", [
        {"embedding_row": i, "segment_id": sid, "episode_id": episode_by_segment[sid], "cohort": cohort_by_episode[episode_by_segment[sid]], "representation_version": MOTION_REPRESENTATION_VERSION}
        for i, sid in enumerate(motion_ids)
    ])
    (output / "motion_feature_schema.json").write_text(json.dumps({
        "version": MOTION_REPRESENTATION_VERSION, "dimension": MOTION_VECTOR_DIM,
        "continuous_indices_zero_based": list(CONTINUOUS_INDICES), "kinematics_indices_zero_based": list(KINEMATICS_INDICES),
        "gripper_indices_zero_based": list(GRIPPER_INDICES), "action_indices_zero_based": list(ACTION_INDICES),
        "scaling": "Candidate-Bank Robust median/IQR", "group_weighting": "equal 1/3 then final L2",
    }, indent=2) + "\n", encoding="utf-8")
    (output / "motion_scaler.json").write_text(json.dumps({
        "role": scaler.role, "fit_cohort": "CANDIDATE_BANK", "fit_episode_count": 36,
        "fit_segment_count": len(candidate_rows), "fit_episode_ids": cohorts["CANDIDATE_BANK"],
        "continuous_indices_zero_based": list(CONTINUOUS_INDICES), "median": scaler.median.tolist(),
        "denominator": scaler.denominator.tolist(), "coarse_valid_median": scaler.coarse_valid_median,
        "constant_feature_indices_zero_based": list(scaler.constant_feature_indices),
    }, indent=2) + "\n", encoding="utf-8")

    processor = AutoProcessor.from_pretrained(MODEL_ID, revision=MODEL_REVISION, cache_dir=args.model_cache, use_fast=False)
    model = AutoModel.from_pretrained(MODEL_ID, revision=MODEL_REVISION, cache_dir=args.model_cache)
    device = torch.device("cpu")
    model.eval().to(device)
    ordered_frames = sorted(
        {(row["source_episode_id"], int(row["frame_index"]), row["png_relpath"]) for row in keyframe_rows},
        key=lambda item: (item[0], item[1]),
    )
    frame_vectors: dict[tuple[str, int], np.ndarray] = {}
    with torch.inference_mode():
        for start in range(0, len(ordered_frames), args.batch_size):
            batch = ordered_frames[start:start + args.batch_size]
            images = []
            for _, _, relpath in batch:
                with Image.open(m2_output / relpath) as image:
                    images.append(image.convert("RGB").copy())
            inputs = {name: value.to(device) for name, value in processor(images=images, return_tensors="pt").items()}
            features = model.get_image_features(**inputs)
            for (episode, frame, _), feature in zip(batch, features):
                frame_vectors[(episode, frame)] = validate_siglip2_embedding(feature)
    frame_keys = list(frame_vectors)
    frame_matrix = np.stack([frame_vectors[key] for key in frame_keys]).astype(np.float32)
    np.savez_compressed(
        output / "visual_frame_embeddings.npz",
        episode_ids=np.asarray([key[0] for key in frame_keys]), frame_indices=np.asarray([key[1] for key in frame_keys]), embeddings=frame_matrix,
    )
    visual_vectors = {}
    visual_manifest = []
    for segment_id in motion_ids:
        rows = keyframes_by_segment[segment_id]
        episode = episode_by_segment[segment_id]
        mapping = {int(row["frame_index"]): frame_vectors[(episode, int(row["frame_index"]))] for row in rows}
        vector, indices = pool_unique_frame_embeddings(rows, mapping)
        visual_vectors[segment_id] = vector
        visual_manifest.append({
            "embedding_row": len(visual_manifest), "segment_id": segment_id, "episode_id": episode,
            "cohort": cohort_by_episode[episode], "unique_frame_count": len(indices), "representation_version": VISUAL_REPRESENTATION_VERSION,
        })
    visual_matrix = np.stack([visual_vectors[sid] for sid in motion_ids]).astype(np.float32)
    if visual_matrix.shape[1] != 768:
        raise RuntimeError(f"STOP_VISUAL_DIMENSION_FAILURE: {visual_matrix.shape}")
    np.savez_compressed(output / "visual_segment_embeddings.npz", segment_ids=np.asarray(motion_ids), embeddings=visual_matrix)
    write_csv(output / "visual_embedding_manifest.csv", visual_manifest)
    (output / "siglip_model_identity.json").write_text(json.dumps({
        "model_id": MODEL_ID, "exact_revision": MODEL_REVISION, "loader": "AutoModel config-driven",
        "model_class": type(model).__name__, "processor": type(processor).__name__, "use_fast": False,
        "transformers_version": transformers.__version__, "torch_version": torch.__version__,
        "device": str(device), "dtype": str(next(model.parameters()).dtype), "visual_dimension": 768,
    }, indent=2) + "\n", encoding="utf-8")

    candidate_ids = [row["segment_id"] for row in candidate_rows]
    motion_index_by_id = {sid: i for i, sid in enumerate(motion_ids)}
    candidate_motion = np.stack([motion_matrix[motion_index_by_id[sid]] for sid in candidate_ids]).astype(np.float32)
    candidate_visual = np.stack([visual_vectors[sid] for sid in candidate_ids]).astype(np.float32)
    motion_index = faiss.IndexFlatIP(17)
    visual_index = faiss.IndexFlatIP(768)
    motion_index.add(candidate_motion)
    visual_index.add(candidate_visual)
    faiss.write_index(motion_index, str(output / "faiss_motion.index"))
    faiss.write_index(visual_index, str(output / "faiss_visual.index"))
    write_csv(output / "candidate_segment_manifest.csv", [
        {"candidate_index_row": i, "segment_id": sid, "episode_id": episode_by_segment[sid]}
        for i, sid in enumerate(candidate_ids)
    ])

    calibration_manifest, calibration_balance = select_query_segments(
        motion_rows, cohorts["CALIBRATION_QUERY"], cohort="CALIBRATION_QUERY", target_true=4
    )
    final_manifest, final_balance = select_query_segments(
        motion_rows, cohorts["FINAL_QUERY"], cohort="FINAL_QUERY", target_true=9
    )
    write_csv(output / "calibration_query_manifest.csv", calibration_manifest)
    write_csv(output / "final_query_manifest.csv", final_manifest)

    calibration_motion = []
    calibration_visual = []
    for query in calibration_manifest:
        query_id = query["segment_id"]
        query_episode = query["episode_id"]
        for rank, (candidate_id, score) in enumerate(search_top5(motion_index, candidate_ids, motion_matrix[motion_index_by_id[query_id]], query_episode, episode_by_segment), 1):
            calibration_motion.append({"query_segment_id": query_id, "candidate_segment_id": candidate_id, "rank": rank, "similarity": score, "representation_version": MOTION_REPRESENTATION_VERSION})
        for rank, (candidate_id, score) in enumerate(search_top5(visual_index, candidate_ids, visual_vectors[query_id], query_episode, episode_by_segment), 1):
            calibration_visual.append({"query_segment_id": query_id, "candidate_segment_id": candidate_id, "rank": rank, "similarity": score, "representation_version": VISUAL_REPRESENTATION_VERSION})
    write_csv(output / "calibration_motion_top5.csv", calibration_motion)
    write_csv(output / "calibration_visual_top5.csv", calibration_visual)

    audit_rows, repeat_pairs, unique_pair_count = build_blind_audit_items(calibration_motion, calibration_visual)
    for row in audit_rows:
        query = motion_by_id[row["query_segment_id"]]
        candidate = motion_by_id[row["candidate_segment_id"]]
        row.update({
            "query_duration_sec": query["duration_sec"], "query_gripper_start_state": query["gripper_start_state"],
            "query_gripper_end_state": query["gripper_end_state"], "query_gripper_transition_present": query["gripper_transition_present"],
            "query_eef_displacement_xyz": query["eef_displacement_xyz"], "query_coarse_direction_change_rad": query["coarse_direction_change_rad"],
            "candidate_duration_sec": candidate["duration_sec"], "candidate_gripper_start_state": candidate["gripper_start_state"],
            "candidate_gripper_end_state": candidate["gripper_end_state"], "candidate_gripper_transition_present": candidate["gripper_transition_present"],
            "candidate_eef_displacement_xyz": candidate["eef_displacement_xyz"], "candidate_coarse_direction_change_rad": candidate["coarse_direction_change_rad"],
            "review_label": "", "query_bad_segment": "",
        })
    write_csv(output / "calibration_human_audit_pairs.csv", audit_rows)
    create_audit_html(output, audit_rows, keyframes_by_segment, motion_by_id)

    candidate_episode_set = set(cohorts["CANDIDATE_BANK"])
    sanity_checks = {
        "FORMAL_EPISODES_63": m2_result["episodes_processed"] == 63,
        "CANDIDATE_EPISODES_36": len(candidate_episode_set) == 36,
        "CALIBRATION_QUERY_EPISODES_9": len(cohorts["CALIBRATION_QUERY"]) == 9,
        "FINAL_QUERY_EPISODES_18": len(cohorts["FINAL_QUERY"]) == 18,
        "FORMAL_SCALER_CANDIDATE_ONLY": scaler.role == "FORMAL_CANDIDATE_BANK_SCALER" and {row["source_episode_id"] for row in candidate_rows} <= candidate_episode_set,
        "CANDIDATE_IDS_ALIGNED": candidate_motion.shape[0] == candidate_visual.shape[0] == len(candidate_ids),
        "QUERY_NOT_IN_CANDIDATE_INDEX": not ({row["episode_id"] for row in calibration_manifest + final_manifest} & candidate_episode_set),
        "MOTION_VECTORS_FINITE": bool(np.isfinite(motion_matrix).all()),
        "VISUAL_VECTORS_FINITE": bool(np.isfinite(visual_matrix).all()),
        "CALIBRATION_QUERY_SEGMENTS_9": len(calibration_manifest) == 9,
        "FINAL_QUERY_SEGMENTS_18": len(final_manifest) == 18,
        "CALIBRATION_MOTION_TOP5_9_OF_9": len(calibration_motion) == 45,
        "CALIBRATION_VISUAL_TOP5_9_OF_9": len(calibration_visual) == 45,
        "CROSS_EPISODE": all(episode_by_segment[r["query_segment_id"]] != episode_by_segment[r["candidate_segment_id"]] for r in calibration_motion + calibration_visual),
        "BLIND_PAIR_DEDUP": unique_pair_count == len({(r["query_segment_id"], r["candidate_segment_id"]) for r in calibration_motion + calibration_visual}),
        "HIDDEN_REPEATS_12": len(repeat_pairs) == 12,
        "FINAL_RETRIEVAL_EXECUTED_NO": True,
        "HUMAN_SCORING_EXECUTED_NO": True,
        "P5_COMPUTED_NO": True,
    }
    if not all(sanity_checks.values()):
        raise RuntimeError("STOP_FORMAL_STAGE1_SANITY_FAILURE: " + json.dumps([key for key, value in sanity_checks.items() if not value]))
    sanity = {
        "checks": {key: "PASS" for key in sanity_checks},
        "total_segments_materialized": len(motion_rows), "candidate_segment_count": len(candidate_ids),
        "formal_motion_scaler_fit_segments": len(candidate_rows), "calibration_query_balance": calibration_balance,
        "final_query_balance": final_balance, "blind_audit_unique_pairs": unique_pair_count,
        "hidden_repeat_pairs": 12, "blind_audit_total_items": len(audit_rows),
    }
    (output / "sanity_summary.json").write_text(json.dumps(sanity, indent=2) + "\n", encoding="utf-8")
    (output / "run_meta.json").write_text(json.dumps({
        "run_id": args.run_id, "created_at": datetime.now().astimezone().isoformat(), "git_base": git_base,
        "protocol_sha256": sha256_file(PROTOCOL), "addendum_sha256": sha256_file(ADDENDUM),
        "manifest_doc_sha256": sha256_file(MANIFEST_DOC), "manifest_csv_sha256": sha256_file(MANIFEST_CSV),
        "model_id": MODEL_ID, "exact_revision": MODEL_REVISION,
        "formal_63_episode_executed": True, "calibration_retrieval_executed": True,
        "final_query_segments_selected": True, "final_retrieval_executed": False,
        "human_audit_executed": False, "p5_computed": False, "vlm_executed": False,
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_run": str(output), **sanity}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
