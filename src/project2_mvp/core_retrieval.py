"""Frozen Core v1 representation helpers used by runtime preflight.

The functions here implement the frozen 17D motion representation, unique-frame
visual pooling, and exact inner-product smoke search. Formal batch orchestration
and Human evaluation are intentionally out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np


MOTION_REPRESENTATION_VERSION = "MVP_M4_MOTION_REP_V1"
VISUAL_REPRESENTATION_VERSION = "MVP_M4_SIGLIP2_REP_V1"
MOTION_VECTOR_DIM = 17
CONTINUOUS_INDICES = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 14, 15, 16)
KINEMATICS_INDICES = tuple(range(0, 11))
GRIPPER_INDICES = (11, 12, 13)
ACTION_INDICES = (14, 15, 16)


class CoreRetrievalRuntimeError(ValueError):
    pass


def _vector3(value: Any, field: str) -> list[float]:
    if isinstance(value, str):
        import json

        value = json.loads(value)
    values = [float(item) for item in value]
    if len(values) != 3:
        raise CoreRetrievalRuntimeError(f"{field} must have exactly three values")
    return values


def motion_raw_vector(row: Mapping[str, Any]) -> np.ndarray:
    """Map one MVP_M2_MOTION_FEATURE_V1 row to the frozen 17D raw vector."""

    start_state = str(row["gripper_start_state"])
    end_state = str(row["gripper_end_state"])
    if start_state not in {"OPEN", "CLOSED"} or end_state not in {"OPEN", "CLOSED"}:
        raise CoreRetrievalRuntimeError("Frozen semantic gripper state is required")
    coarse_raw = row.get("coarse_direction_change_rad")
    coarse_missing = coarse_raw in (None, "", "null", "None")
    coarse = np.nan if coarse_missing else float(coarse_raw)
    displacement = _vector3(row["eef_displacement_xyz"], "eef_displacement_xyz")
    direction = _vector3(row["eef_main_direction_xyz"], "eef_main_direction_xyz")
    vector = np.asarray(
        [
            np.log1p(float(row["duration_sec"])),
            np.log1p(float(row["eef_net_displacement_m"])),
            np.log1p(float(row["eef_path_length_m"])),
            *displacement,
            *direction,
            coarse,
            1.0 if coarse_missing else 0.0,
            1.0 if start_state == "OPEN" else 0.0,
            1.0 if end_state == "OPEN" else 0.0,
            1.0 if str(row["gripper_transition_present"]).lower() in {"true", "1", "yes"} else 0.0,
            float(row["action_magnitude_mean"]),
            float(row["action_magnitude_max"]),
            float(row["action_magnitude_std"]),
        ],
        dtype=np.float64,
    )
    if vector.shape != (MOTION_VECTOR_DIM,):
        raise CoreRetrievalRuntimeError(f"motion raw dimension mismatch: {vector.shape}")
    finite_except_coarse = np.delete(vector, 9)
    if not np.isfinite(finite_except_coarse).all():
        raise CoreRetrievalRuntimeError("motion raw vector contains non-finite values")
    return vector


@dataclass(frozen=True)
class SmokeRobustScaler:
    """SMOKE_ONLY_SCALER; never a Formal Candidate Bank scaler."""

    median: np.ndarray
    denominator: np.ndarray
    constant_feature_indices: tuple[int, ...]
    coarse_valid_median: float
    role: str = "SMOKE_ONLY_SCALER"

    def transform(self, raw: np.ndarray) -> np.ndarray:
        values = np.asarray(raw, dtype=np.float64).copy()
        if values.shape != (MOTION_VECTOR_DIM,):
            raise CoreRetrievalRuntimeError("motion transform expects 17D input")
        if np.isnan(values[9]):
            values[9] = self.coarse_valid_median
        if not np.isfinite(values).all():
            raise CoreRetrievalRuntimeError("motion input remains non-finite after frozen missing rule")
        values[list(CONTINUOUS_INDICES)] = (
            values[list(CONTINUOUS_INDICES)] - self.median
        ) / self.denominator
        return _equal_group_weight_and_normalize(values)


def fit_smoke_motion_scaler(raw_vectors: Sequence[np.ndarray]) -> SmokeRobustScaler:
    matrix = np.asarray(raw_vectors, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[1] != MOTION_VECTOR_DIM or len(matrix) < 1:
        raise CoreRetrievalRuntimeError("SMOKE_ONLY_SCALER requires non-empty Nx17 input")
    valid_coarse = matrix[np.isfinite(matrix[:, 9]), 9]
    if len(valid_coarse) == 0:
        raise CoreRetrievalRuntimeError("no valid coarse direction value for frozen median imputation")
    coarse_median = float(np.median(valid_coarse))
    fitted = matrix.copy()
    fitted[~np.isfinite(fitted[:, 9]), 9] = coarse_median
    continuous = fitted[:, list(CONTINUOUS_INDICES)]
    median = np.median(continuous, axis=0)
    q25 = np.percentile(continuous, 25, axis=0)
    q75 = np.percentile(continuous, 75, axis=0)
    iqr = q75 - q25
    constant_local = np.flatnonzero(iqr == 0.0)
    denominator = iqr.copy()
    denominator[constant_local] = 1.0
    constant_global = tuple(CONTINUOUS_INDICES[index] for index in constant_local)
    return SmokeRobustScaler(
        median=median,
        denominator=denominator,
        constant_feature_indices=constant_global,
        coarse_valid_median=coarse_median,
    )


def _normalize(vector: np.ndarray, *, label: str) -> np.ndarray:
    values = np.asarray(vector, dtype=np.float32)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise CoreRetrievalRuntimeError(f"{label} vector invalid")
    norm = float(np.linalg.norm(values))
    if norm <= 0.0 or not np.isfinite(norm):
        raise CoreRetrievalRuntimeError(f"{label} vector has zero/invalid norm")
    return np.ascontiguousarray(values / norm, dtype=np.float32)


def _equal_group_weight_and_normalize(vector: np.ndarray) -> np.ndarray:
    values = np.asarray(vector, dtype=np.float64)
    weighted = np.zeros(MOTION_VECTOR_DIM, dtype=np.float64)
    group_weight = np.sqrt(3.0)
    for indices in (KINEMATICS_INDICES, GRIPPER_INDICES, ACTION_INDICES):
        group = values[list(indices)]
        norm = float(np.linalg.norm(group))
        if norm > 0.0:
            weighted[list(indices)] = group / norm / group_weight
    return _normalize(weighted, label="motion")


def validate_siglip2_embedding(embedding: Any) -> np.ndarray:
    if hasattr(embedding, "detach"):
        embedding = embedding.detach().cpu().numpy()
    values = np.asarray(embedding)
    if values.ndim == 2 and values.shape[0] == 1:
        values = values[0]
    if values.ndim != 1:
        raise CoreRetrievalRuntimeError(f"SigLIP2 embedding ndim invalid: {values.shape}")
    return _normalize(values, label="SigLIP2 frame")


def pool_unique_frame_embeddings(
    keyframes: Sequence[Mapping[str, Any]],
    frame_embeddings: Mapping[int, Any],
) -> tuple[np.ndarray, tuple[int, ...]]:
    """Unweighted unique-frame mean; roles never duplicate a frame embedding."""

    unique_indices = tuple(sorted({int(row["frame_index"]) for row in keyframes}))
    if not unique_indices:
        raise CoreRetrievalRuntimeError("segment has no keyframes")
    missing = [index for index in unique_indices if index not in frame_embeddings]
    if missing:
        raise CoreRetrievalRuntimeError(f"missing frame embeddings: {missing}")
    normalized = [validate_siglip2_embedding(frame_embeddings[index]) for index in unique_indices]
    dimensions = {len(item) for item in normalized}
    if len(dimensions) != 1:
        raise CoreRetrievalRuntimeError("visual frame embedding dimension mismatch")
    return _normalize(np.mean(np.stack(normalized), axis=0), label="visual segment"), unique_indices


def faiss_index_flat_ip_smoke(
    vectors: Sequence[np.ndarray],
    segment_ids: Sequence[str],
    query: np.ndarray,
    *,
    top_k: int = 5,
    exclude_segment_id: str | None = None,
) -> list[dict[str, Any]]:
    import faiss

    matrix = np.ascontiguousarray(np.stack(vectors).astype(np.float32))
    if matrix.ndim != 2 or len(matrix) != len(segment_ids) or not np.isfinite(matrix).all():
        raise CoreRetrievalRuntimeError("FAISS input matrix invalid")
    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)
    request_k = min(len(segment_ids), top_k + (1 if exclude_segment_id else 0))
    scores, indices = index.search(np.ascontiguousarray(query[None, :], dtype=np.float32), request_k)
    results = []
    for score, index_value in zip(scores[0], indices[0]):
        if index_value < 0:
            continue
        segment_id = str(segment_ids[int(index_value)])
        if segment_id == exclude_segment_id:
            continue
        if not np.isfinite(score):
            raise CoreRetrievalRuntimeError("FAISS returned non-finite score")
        results.append({"segment_id": segment_id, "score": float(score)})
        if len(results) == min(top_k, len(segment_ids) - (1 if exclude_segment_id in segment_ids else 0)):
            break
    if not results or any(row["segment_id"] not in set(segment_ids) for row in results):
        raise CoreRetrievalRuntimeError("FAISS returned invalid segment IDs")
    return results
