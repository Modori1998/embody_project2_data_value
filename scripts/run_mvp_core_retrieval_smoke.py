"""Run the minimal frozen Core Retrieval engineering preflight.

This is not a Formal Retrieval run: it uses only the first three frozen
Candidate Bank episodes, a SMOKE_ONLY_SCALER, and ephemeral exact indices.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_mvp.core_retrieval import (
    faiss_index_flat_ip_smoke,
    fit_smoke_motion_scaler,
    motion_raw_vector,
    pool_unique_frame_embeddings,
    validate_siglip2_embedding,
)
from project2_mvp.m2_materializer import materialize_m2


MODEL_ID = "google/siglip2-base-patch16-224"
EXPECTED_MODEL_REVISION = "75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2"
PROTOCOL_PATH = ROOT / "0-doc/10-design-review/Project2_MVP_Core_Retrieval_Protocol_FROZEN_v1_20261008.md"
MANIFEST_DOC_PATH = ROOT / "0-doc/10-design-review/Project2_MVP_Core_Retrieval_Manifest_FROZEN_v1_20261009.md"
MANIFEST_CSV_PATH = ROOT / "0-doc/10-design-review/Project2_MVP_Core_Retrieval_Manifest_FROZEN_v1_20261009.csv"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_frozen_identity() -> tuple[list[dict[str, str]], dict[str, str]]:
    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    manifest_doc = MANIFEST_DOC_PATH.read_text(encoding="utf-8")
    required_protocol = (
        "DOCUMENT_STATUS = FROZEN_v1",
        "MVP_CORE_RETRIEVAL_PROTOCOL_v1",
        "MVP_M4_MOTION_REP_V1",
        "MVP_M4_SIGLIP2_REP_V1",
        "CORE_V1_LATE_FUSION = DISABLED",
    )
    required_manifest = (
        "DOCUMENT_STATUS = FROZEN_v1",
        "MANIFEST_VERSION = MVP_CORE_RETRIEVAL_MANIFEST_v1",
        "CORE_RETRIEVAL_MANIFEST =",
        "FROZEN_v1",
        "TOTAL_SELECTED_UNIQUE = 63",
    )
    if any(value not in protocol for value in required_protocol):
        raise RuntimeError("STOP_FROZEN_RETRIEVAL_IDENTITY_MISMATCH: protocol")
    if any(value not in manifest_doc for value in required_manifest):
        raise RuntimeError("STOP_FROZEN_RETRIEVAL_IDENTITY_MISMATCH: manifest doc")
    rows = _read_csv(MANIFEST_CSV_PATH)
    ids = [row["episode_id"] for row in rows]
    counts = {
        cohort: sum(row["cohort"] == cohort for row in rows)
        for cohort in ("CANDIDATE_BANK", "CALIBRATION_QUERY", "FINAL_QUERY")
    }
    if (
        len(rows) != 63
        or len(set(ids)) != 63
        or counts != {"CANDIDATE_BANK": 36, "CALIBRATION_QUERY": 9, "FINAL_QUERY": 18}
        or {row["manifest_version"] for row in rows} != {"MVP_CORE_RETRIEVAL_MANIFEST_v1"}
    ):
        raise RuntimeError("STOP_FROZEN_RETRIEVAL_IDENTITY_MISMATCH: manifest csv")
    return rows, counts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model-revision", default=EXPECTED_MODEL_REVISION)
    parser.add_argument("--model-cache", type=Path, default=ROOT / "outputs/model_cache/huggingface")
    args = parser.parse_args(argv)
    if args.model_revision != EXPECTED_MODEL_REVISION:
        raise RuntimeError("SigLIP2 smoke must use the preflight-pinned exact revision")

    import faiss
    import torch
    import transformers
    from transformers import AutoModel, AutoProcessor

    manifest, counts = validate_frozen_identity()
    candidate_rows = sorted(
        (row for row in manifest if row["cohort"] == "CANDIDATE_BANK"),
        key=lambda row: int(row["selection_rank"]),
    )
    smoke_episodes = [row["episode_id"] for row in candidate_rows[:3]]
    output = ROOT / "outputs/core_retrieval_runtime_preflight" / args.run_id
    if output.exists():
        raise FileExistsError(f"immutable output run already exists: {output}")
    output.mkdir(parents=True)
    git_base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    m2_output = output / "m2_smoke"
    m2_result = materialize_m2(m2_output, smoke_episodes, git_base=git_base)

    motion_rows = _read_csv(m2_output / "robot_motion_summary.csv")
    keyframe_rows = _read_csv(m2_output / "keyframe_manifest.csv")
    # Six segments are the minimum required for one self-excluded Top-5 query.
    selected_motion = motion_rows[:6]
    if len(selected_motion) < 6:
        raise RuntimeError("candidate smoke subset has fewer than six segments")
    segment_ids = [row["segment_id"] for row in selected_motion]
    selected_id_set = set(segment_ids)
    selected_keyframes = [row for row in keyframe_rows if row["segment_id"] in selected_id_set]
    by_segment: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in selected_keyframes:
        by_segment[row["segment_id"]].append(row)

    raw_motion = [motion_raw_vector(row) for row in selected_motion]
    scaler = fit_smoke_motion_scaler(raw_motion)
    motion_vectors = [scaler.transform(row) for row in raw_motion]

    processor = AutoProcessor.from_pretrained(
        MODEL_ID, revision=args.model_revision, cache_dir=args.model_cache, use_fast=False
    )
    # The pinned official repository currently declares model_type="siglip".
    # AutoModel is the compatible loader for that repository config; forcing
    # Siglip2Model produces an invalid patch-embedding shape interpretation.
    model = AutoModel.from_pretrained(
        MODEL_ID, revision=args.model_revision, cache_dir=args.model_cache
    )
    model.eval()
    device = torch.device("cpu")
    model.to(device)

    unique_png: dict[tuple[str, int], Path] = {}
    for row in selected_keyframes:
        key = (row["source_episode_id"], int(row["frame_index"]))
        unique_png.setdefault(key, m2_output / row["png_relpath"])
    frame_embeddings: dict[tuple[str, int], np.ndarray] = {}
    ordered_keys = sorted(unique_png)
    batch_size = 4
    with torch.inference_mode():
        for start in range(0, len(ordered_keys), batch_size):
            keys = ordered_keys[start : start + batch_size]
            images = []
            for key in keys:
                with Image.open(unique_png[key]) as image:
                    images.append(image.convert("RGB").copy())
            inputs = processor(images=images, return_tensors="pt")
            inputs = {name: value.to(device) for name, value in inputs.items()}
            features = model.get_image_features(**inputs)
            for key, feature in zip(keys, features):
                frame_embeddings[key] = validate_siglip2_embedding(feature)

    first_frame_embedding = frame_embeddings[ordered_keys[0]]
    visual_vectors = []
    unique_frame_counts = {}
    for segment_id in segment_ids:
        rows = by_segment[segment_id]
        episode_id = rows[0]["source_episode_id"]
        mapping = {
            int(row["frame_index"]): frame_embeddings[(episode_id, int(row["frame_index"]))]
            for row in rows
        }
        pooled, unique_indices = pool_unique_frame_embeddings(rows, mapping)
        visual_vectors.append(pooled)
        unique_frame_counts[segment_id] = len(unique_indices)

    query_id = segment_ids[0]
    motion_top5 = faiss_index_flat_ip_smoke(
        motion_vectors, segment_ids, motion_vectors[0], top_k=5, exclude_segment_id=query_id
    )
    visual_top5 = faiss_index_flat_ip_smoke(
        visual_vectors, segment_ids, visual_vectors[0], top_k=5, exclude_segment_id=query_id
    )
    result = {
        "run_id": args.run_id,
        "git_base": git_base,
        "frozen_protocol_identity": "PASS",
        "frozen_manifest_identity": "PASS",
        "manifest_episode_count": len(manifest),
        "manifest_counts": counts,
        "model_id": MODEL_ID,
        "model_class": type(model).__name__,
        "exact_revision_sha": args.model_revision,
        "transformers_version": transformers.__version__,
        "torch_version": torch.__version__,
        "faiss_version": faiss.__version__,
        "device": str(device),
        "dtype": str(next(model.parameters()).dtype),
        "siglip2_embedding_dim": int(first_frame_embedding.shape[0]),
        "motion_vector_dim": int(motion_vectors[0].shape[0]),
        "visual_vector_dim": int(visual_vectors[0].shape[0]),
        "smoke_episodes": smoke_episodes,
        "m2_segments_materialized": m2_result["segments_processed"],
        "smoke_segments_indexed": len(segment_ids),
        "smoke_segment_ids": segment_ids,
        "unique_frame_embeddings": len(frame_embeddings),
        "unique_frame_counts_by_segment": unique_frame_counts,
        "motion_scaler_role": scaler.role,
        "motion_scaler_constant_feature_indices": list(scaler.constant_feature_indices),
        "query_segment_id": query_id,
        "top_k_smoke": 5,
        "motion_top5": motion_top5,
        "visual_top5": visual_top5,
        "checks": {
            "SIGLIP2_MODEL_LOAD": "PASS",
            "SIGLIP2_EXACT_REVISION_PINNED": "YES",
            "FORMAL_CLEAN_RGB_TO_SIGLIP2": "PASS",
            "SIGLIP2_SINGLE_FRAME_SMOKE": "PASS",
            "MOTION_REPRESENTATION_SMOKE": "PASS",
            "VISUAL_REPRESENTATION_SMOKE": "PASS",
            "FAISS_MOTION_SMOKE": "PASS",
            "FAISS_VISUAL_SMOKE": "PASS",
            "TOP5_PIPELINE_SMOKE": "PASS",
        },
        "scope": {
            "formal_63_episode_executed": False,
            "calibration_query_executed": False,
            "final_query_executed": False,
            "human_audit_executed": False,
            "p5_computed": False,
            "vlm_executed": False,
            "late_fusion_executed": False,
        },
    }
    (output / "runtime_preflight_result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
