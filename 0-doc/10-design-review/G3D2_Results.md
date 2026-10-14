# G3D2 Results — 2026-10-14

Design freeze: `bee4ed2826ed24347ad9fce66a68bb8e3ccead3a`. Runtime implementation and results recorded after that commit. All raw requests/responses remain in immutable local `outputs/g3d2` run directories and are not GitHub export artifacts.

## Gate result

Pilot: 20/20 HTTP, JSON, schema and target-frame evidence valid; no source or SHA mismatch. All five actual request layouts matched the frozen matrix. Total 54.69 seconds, 57,407 prompt and 3,070 completion tokens; sampled GPU memory 4,351 MiB. Maximum prompt tokens 3,597 under the 4,096 context.

Full Development: **`G3D2_FULL_INCOMPLETE`**. The runner stopped immediately at call 44/60 (`demo_71-S0003`, G1). HTTP 200 and JSON parse succeeded, finish reason was `stop`, completion used 125 of 512 budgeted tokens. The model omitted the required **top-level** `evidence_frame_indices` key while retaining the per-event key, so v0.2 schema validation failed. This is not output truncation, a cross-boundary citation, OOM or an HTTP error. The response also asserted `object_motion` while its own note described a static object; QC flagged that contradiction. The frozen protocol prohibits accepting a schema-invalid response, repairing the JSON, or filling the remaining cells with historical predictions. No five-arm Development scores or success claims are computed.

The 44 attempted calls took 120.26 seconds, 126,532 prompt and 6,903 completion tokens; sampled GPU memory remained 4,351 MiB. Valid structural responses by group among attempted calls: G0 9/9, G1 8/9, T0 8/8, T1 9/9, T2 9/9. Denominators are incomplete and must **not** be compared as semantic performance. The G3D2-owned model service was stopped after the hold; no other process was terminated.

## What this establishes

Request construction and short-run feasibility passed. The old v0.2.1 prompt already carried chronological frame identity. Temporal v0.3 changed actual multimodal content order and added two-interval visual comparison; T2 added interval state rather than a complete per-frame sequence. The full experiment cannot establish whether any of the five groups improves event recognition. In particular, Pilot outputs and the partial 44 calls are not a replacement for a 60-call paired score.

The schema omission in G1 demonstrates a frozen-run reliability limit. A fresh full run, if authorized under a new pre-registered stability protocol, must rerun **all 60 cells** with the same parameters and report this failed run alongside it. It may not retry only `demo_71` or increase `max_tokens` for G1. Until then, the G3D2 decision is `HOLD`, and G3E remains a design option rather than an executed conclusion from this experiment.
