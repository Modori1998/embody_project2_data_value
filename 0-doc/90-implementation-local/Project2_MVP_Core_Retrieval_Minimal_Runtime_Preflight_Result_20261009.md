# Project 2 MVP Core Retrieval Minimal Runtime Preflight Result

Date: 2026-10-09
Task: `MINIMAL_CORE_RETRIEVAL_RUNTIME_PREFLIGHT`
Result: `PASS_READY_FOR_FORMAL_CORE_RETRIEVAL`

## Git and frozen identity

- Git base after pull: `7e26dd96e3d67d194efa13f0b20ea785687257bc`
- Core Retrieval Protocol: `FROZEN_v1` — PASS
- Frozen Retrieval Manifest: `FROZEN_v1` — PASS
- Frozen manifest episode count: 63 unique episodes
- Cohorts: Candidate Bank 36, Calibration Query 9, Final Query 18
- Frozen protocol SHA256: `442d1504578849f2e4b4a97423b14caa52dca723539f96472f739e5d531d06e8`
- Frozen manifest doc SHA256: `c46e12344c8fec6304ed7a837573f2c0cf449054607d854199e84d0b2b2a6a69`
- Frozen manifest CSV SHA256: `3b7e0f3b0de13417fbfa662156bdca082efb473bda086bc882301607981dd7fd`

No Frozen Protocol, Frozen Manifest, Frozen G1, M2 feature-contract, or RGB-contract artifact was modified.

## Runtime environment

- Model ID: `google/siglip2-base-patch16-224`
- Exact repository revision SHA: `75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2`
- Loader selected from pinned repository config: `AutoModel` -> `SiglipModel`
- Processor: `AutoProcessor`, pinned repository revision, `use_fast=False`
- Transformers: `4.56.2`
- Torch: `2.14.0+cpu`
- FAISS: `1.12.0`
- SentencePiece: `0.2.2`
- Device: `cpu`
- Dtype: `torch.float32`

The pinned repository currently declares `model_type="siglip"`. Directly forcing `Siglip2Model` produced an incompatible patch-embedding shape; using the official config-driven `AutoModel` loader resolved this without changing the model ID, revision, processor, or Frozen Visual Representation protocol.

## Formal Clean RGB and SigLIP2 smoke

Input remained on `MVP_RGB_SOURCE_AND_ALIGNMENT_CONTRACT_v1`:

`STATE_t -> RoboMimicStateRenderer -> direct clean RGB -> lossless PNG -> official processor`

- Audit MP4 used: NO
- Overlay used: NO
- Lossy roundtrip used: NO
- Model load: PASS
- Exact revision pinned: YES
- Formal Clean RGB to model: PASS
- Single-frame embedding exists, finite, and non-zero: PASS
- Frame embedding dimension: 768
- Frame embedding L2 normalization: PASS

## Minimal end-to-end smoke

- Passing runtime run ID: `mvp_core_retrieval_minimal_preflight_20261009_retry4`
- Output: `outputs/core_retrieval_runtime_preflight/mvp_core_retrieval_minimal_preflight_20261009_retry4`
- Candidate Bank episodes only:
  - `data/demo_15`
  - `data/demo_157`
  - `data/demo_36`
- M2 segments materialized: 12
- Smoke segments indexed: 6
- Unique frame embeddings: 18
- Query segment: `demo_15-S0001`
- Top-K smoke: 5

Motion representation:

- Version: `MVP_M4_MOTION_REP_V1`
- Dimension: 17
- Robust scaling fit role: `SMOKE_ONLY_SCALER`
- Kinematics / Gripper / Action equal group weighting: PASS
- Final L2 normalization and finite-vector check: PASS
- FAISS `IndexFlatIP` Top-5: PASS

Visual segment representation:

- Version: `MVP_M4_SIGLIP2_REP_V1`
- Dimension: 768
- Unique M2 frames embedded once: PASS
- Frame L2 normalize -> arithmetic mean -> segment L2 normalize: PASS
- FAISS `IndexFlatIP` Top-5: PASS

The returned IDs were valid indexed segment IDs and the query segment was excluded. Scores are engineering smoke evidence only and were not interpreted as retrieval quality.

## Tests

Command:

`python -m unittest discover -s tests -p "test_mvp_core_retrieval_smoke.py" -v`

Result: 4/4 PASS

Covered:

1. 17D Motion representation dimension, finiteness, and normalized output.
2. Multi-role duplicate frame is embedded/pool-counted once.
3. FAISS `IndexFlatIP` returns five valid self-excluded neighbors.
4. SigLIP2-shaped valid embedding produces a finite normalized vector.

Targeted regressions also passed: M2 8/8 and RGB input contract 3/3.

The real runtime additionally proved pinned model load, Formal Clean RGB inference, 768D frame/segment embeddings, and both Motion and Visual Top-5 execution.

## Resolved runtime findings

Initial immutable attempts were retained. Two attempts were interrupted by the model CDN during the approximately 1.4 GB fixed-revision weight download and resumed from cache. A later attempt exposed the forced-class mismatch described above, followed by the missing `sentencepiece` dependency required by `AutoProcessor`. The dependency was installed only in the ignored project-local isolated venv; the passing retry used the same pinned revision.

## Scope isolation

- Formal 63-Episode batch executed: NO
- Formal scaler generated: NO
- Formal embedding bank generated: NO
- Formal FAISS index generated: NO
- Calibration Query executed: NO
- Final Query executed: NO
- Human Audit executed: NO
- P@5 computed: NO
- VLM executed: NO
- DINOv2 executed: NO
- Late Fusion executed: NO
- Frozen Retrieval Protocol modified: NO
- Frozen Retrieval Manifest modified: NO

## Gate result

- `GIT_SYNC = PASS`
- `FROZEN_PROTOCOL_IDENTITY = PASS`
- `FROZEN_MANIFEST_IDENTITY = PASS`
- `SIGLIP2_MODEL_LOAD = PASS`
- `SIGLIP2_EXACT_REVISION_PINNED = YES`
- `FORMAL_CLEAN_RGB_TO_SIGLIP2 = PASS`
- `MOTION_REPRESENTATION_SMOKE = PASS`
- `VISUAL_REPRESENTATION_SMOKE = PASS`
- `FAISS_MOTION_SMOKE = PASS`
- `FAISS_VISUAL_SMOKE = PASS`
- `TOP5_PIPELINE_SMOKE = PASS`
- `CORE_RETRIEVAL_RUNTIME_PREFLIGHT = PASS`
- `CORE_RETRIEVAL_INFERENCE = READY_FOR_FORMAL_CORE_RETRIEVAL_EXECUTION`
- `NEXT = FORMAL_63_EPISODE_MATERIALIZATION_AND_CORE_RETRIEVAL`

This READY state authorizes the next frozen-protocol execution stage; it does not claim that Formal Retrieval, Human Audit, P@5, or a GO / CONDITIONAL / STOP decision has been completed.
