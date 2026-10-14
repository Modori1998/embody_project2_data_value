# G3D2-R Results — 2026-10-14

Pre-registration: `G3D2_R_Reliability_Protocol.md` (frozen before the new pilot/full inference).
Base main: `689bd65150505bb6a02874c886f2009dd6fbe34c`. This is a sanitized aggregate
export; raw requests/responses stay in the gitignored `outputs/g3d2r/` tree. No personal
human CSV, RGB, HDF5 or model weights are committed.

## 0. What this run actually is

The prior G3D2 run stopped twice at call 44/60 (`demo_71-S0003`, arm G1) because a
single schema-invalid response aborted the whole run. G3D2-R adds unit-level bounded
retry, separate first-attempt/retry accounting, per-cell failure isolation and a global
breaker, then re-runs **all 60 cells** from a fresh directory.

**Critical honesty note — the declared mechanism.** The original design intended
*Schema-constrained decoding*. A compatibility probe on the deployed local
`llama-server` (0.6.0-dev, build 11577, `cbe28bb3c`) showed that
`response_format={"type":"json_schema", ...}` returns HTTP 200 with only a generic
`object` grammar (`response-format-schema ::= object`), i.e. it does **not** enforce the
v0.2 Schema's required keys. That gate failed, so the executed protocol is
`FALLBACK_JSON_OBJECT_RETRY_V1` (`response_format={"type":"json_object"}` plus bounded
retry). This run is **not** and must never be described as schema-constrained decoding.

## 1. Run identity and integrity (verified)

| Item | Value |
|---|---|
| Pilot run | `outputs/g3d2r/pilot_fallback_r1` — 20/20 valid, 0 retries, `gate_pass=true` |
| Full run | `outputs/g3d2r/full_fallback_r1` |
| Protocol | `fallback_json_object_retry_v1` (pilot and full protocol identical) |
| Constraint probe (retained) | `outputs/g3d2r/constraint_probe_v1` |
| Frozen manifest SHA-256 | `0ed8ece0f6b091a4697ce4de77bdbbf67becda56604fe654e695ceba6073ee29` |
| Prompt v0.2.1 SHA-256 | `11b874a3daba9d42398a50bef8473c01924a672f06acda09e0ac3933110e53b4` |
| Temporal instruction SHA-256 | `d7ed0e41123e08af6a6d6d1dfeef4618183804d157764843e79bbbeaaec153a4` |
| Schema v0.2 SHA-256 | `4cbec780693511c6e029a1fc005a7c523e5af7ea6a4ba127c7b9fc44253d0ad7` |
| Model revision | `Qwen/Qwen3-VL-4B-Instruct-GGUF@1cd86afb9a95c410a6038ab3b40d8b578c892266::Qwen3VL-4B-Instruct-Q4_K_M.gguf+mmproj-Qwen3VL-4B-Instruct-F16.gguf` |
| GGUF / mmproj SHA-256 | `66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a` / `256f3a43bd4205ffef48d6b92715e1e70b5b0e9aef06522584967513a9985331` |
| Sampling | temperature 0.0, seed 1234, max_tokens 512, stream false, ctx 4096, target keyframes only |
| Cohort | 12 frozen Development segments × 5 arms = 60 cells |
| Retry budget | 2 structure attempts / 3 service attempts per cell |

All five hashes above were re-verified against the current repo and the model files
after the run; each matched. The 12 `sample_order` segments and the per-segment RGB
SHA-256 triples in `run_manifest.json` match the frozen sample manifest. No input,
model or configuration drift was detected.

## 2. Completion status

**`G3D2_R_FULL_COMPLETE`** — all 60 planned cells reached a final status.

* `gate_pass=false` is expected: the frozen gate requires 60/60 valid, and one cell is a
  permanent, protocol-legal failure. It is reported, not hidden and not repaired.
* The permanent failure is `demo_71-S0003:G1` — the same segment/arm that stopped both
  original runs. Attempt 1 and the retry both returned HTTP 200 with `finish_reason=stop`
  and were `INVALID_MODEL_OUTPUT` (missing top-level `evidence_frame_indices`). The retry
  therefore did not recover it; the failure is a genuine prompt/model reliability limit
  on that cell, not a runner bug, truncation or image mismatch.
* No global breaker fired: no OOM, no repeated service unavailability, no identity drift.
* GPU was quiescent before the run (no M11/ACT or other compute process); VRAM was a
  constant 4351 MiB during inference.

## 3. Reliability (P4) — all attempts counted as real cost

| Arm | Planned | First-attempt valid | Retry attempts | Retry recovered | Final valid | Final failed | First-valid rate | Final-valid rate | Avg attempts/cell | Prompt tok | Completion tok | Wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| G0 | 12 | 12 | 0 | 0 | 12 | 0 | 1.000 | 1.000 | 1.000 | 27,800 | 1,763 | 30.1 |
| G1 | 12 | 11 | 1 | 0 | 11 | 1 | 0.917 | 0.917 | 1.083 | 36,809 | 2,018 | 36.5 |
| T0 | 12 | 12 | 0 | 0 | 12 | 0 | 1.000 | 1.000 | 1.000 | 30,686 | 1,876 | 32.4 |
| T1 | 12 | 12 | 0 | 0 | 12 | 0 | 1.000 | 1.000 | 1.000 | 36,850 | 1,993 | 35.0 |
| T2 | 12 | 12 | 0 | 0 | 12 | 0 | 1.000 | 1.000 | 1.000 | 44,467 | 2,032 | 39.8 |
| **Total** | **60** | **59** | **1** | **0** | **59** | **1** | **0.983** | **0.983** | **1.017** | **176,612** | **9,682** | **173.75** |

Error types: the only error is `INVALID_MODEL_OUTPUT`, twice, both on `demo_71-S0003:G1`.
Retry never changed a verdict: `retry_recovered=0` in every arm. Group errors are shown
explicitly rather than collapsed into a retried success rate.

## 4. Semantic results (P5) — frozen G3C 12-segment multi-event reference

`motion_phase` is single-choice; events are the multi-label set
(`grasp_attempt`, `object_motion`, `release_attempt`). Micro P/R/F1 is over event types.

### 4a. Each arm on its own valid segments

| Arm | n | Phase correct | Event-set exact | Micro P | Micro R | Micro F1 | Presence P | Presence R | Presence F1 |
|---|---|---|---|---|---|---|---|---|---|
| G0 | 12 | 7 | 5 | 0.636 | 0.636 | 0.636 | 0.727 | 1.000 | 0.842 |
| G1 | 11 | 7 | 3 | 0.545 | 0.600 | 0.571 | 0.636 | 1.000 | 0.778 |
| T0 | 12 | 3 | 4 | 0.385 | 0.455 | 0.417 | 0.667 | 1.000 | 0.800 |
| T1 | 12 | 7 | 2 | 0.467 | 0.636 | 0.538 | 0.667 | 1.000 | 0.800 |
| T2 | 12 | 6 | 0 | 0.353 | 0.545 | 0.429 | 0.667 | 1.000 | 0.800 |

Per event type (TP/FP/FN), own-valid:

| Arm | grasp_attempt | object_motion | release_attempt |
|---|---|---|---|
| G0 | 7/4/0 | 0/0/3 | 0/0/1 |
| G1 | 6/4/0 | 0/1/3 | 0/0/1 |
| T0 | 5/4/2 | 0/2/3 | 0/2/1 |
| T1 | 7/4/0 | 0/4/3 | 0/0/1 |
| T2 | 6/4/1 | 0/7/3 | 0/0/1 |

### 4b. Paired metrics on the 11 segments valid for all five arms

`demo_71-S0003` is excluded here because G1 is permanently invalid on it. Excluding it
biases the comparison (it is a segment where G0/T0/T1/T2 do have valid outputs), so the
common-valid table below is reported alongside 4a and never instead of it.

| Arm | n | Phase correct | Event-set exact | Micro P | Micro R | Micro F1 | Presence P | Presence R | Presence F1 |
|---|---|---|---|---|---|---|---|---|---|
| G0 | 11 | 7 | 4 | 0.600 | 0.600 | 0.600 | 0.700 | 1.000 | 0.824 |
| G1 | 11 | 7 | 3 | 0.545 | 0.600 | 0.571 | 0.636 | 1.000 | 0.778 |
| T0 | 11 | 3 | 3 | 0.333 | 0.400 | 0.364 | 0.636 | 1.000 | 0.778 |
| T1 | 11 | 6 | 2 | 0.462 | 0.600 | 0.522 | 0.636 | 1.000 | 0.778 |
| T2 | 11 | 5 | 0 | 0.333 | 0.500 | 0.400 | 0.636 | 1.000 | 0.778 |

### 4c. End-to-end over all 12 planned segments (invalid cell counts as not-correct)

| Arm | Planned | Valid | Event-set exact match | Phase correct | End-to-end exact rate |
|---|---|---|---|---|---|
| G0 | 12 | 12 | 5 | 7 | 0.417 |
| G1 | 12 | 11 | 3 | 7 | 0.250 |
| T0 | 12 | 12 | 4 | 3 | 0.333 |
| T1 | 12 | 12 | 2 | 7 | 0.167 |
| T2 | 12 | 12 | 0 | 6 | 0.000 |

### 4d. Pre-registered contrasts (event micro-F1)

| Contrast | Own-valid Δ | Common-valid Δ | Threshold | Verdict |
|---|---|---|---|---|
| T0 vs G0 | −0.219 | −0.236 | ≥ +0.10 | not met (regression) |
| G1 vs G0 | −0.065 | −0.029 | — | negative gain |
| T1 vs T0 | +0.121 | +0.158 | — | recovers part of T0's loss, still below G0 |
| T2 vs T1 | −0.109 | −0.122 | — | regression |
| T2 vs T0 | +0.012 | +0.036 | ≥ +0.10 | not met |

Other pre-registered items: T2 `object_motion` recall 0/3 (needs ≥ 2/3) — not met;
T2 grasp FP not increased vs G0 (4 vs 4) — met, but T2 raises `object_motion` FP from
0 to 7 (own) / 0 to 6 (common); T2 phase-correct down 1 vs G0 — met; T0 phase-correct
down 4 vs G0 — not met; schema/evidence gate 59/60 — not fully met.

## 5. Segment-level diagnosis (the pre-flagged cases)

Full per-segment predictions, all five arms, are in
`outputs/g3d2r/full_fallback_r1/per_segment_evaluation.jsonl` (local).

* **`object_motion` misses (`demo_2`, `demo_4`, `demo_159`)** — every arm predicts only
  `grasp_attempt`; the human set also contains `object_motion`. Recall stays 0/3 in all
  five arms. Neither the temporal prompt nor either state summary recovers a single one.
* **`grasp_attempt` false positives on no-event approaches (`demo_169`, `demo_232`, `demo_72`)**
  — all humans are `no_event_visible`; G0/G1/T0/T1 all assert `grasp_attempt`; T2 also
  asserts `grasp_attempt` (and adds `object_motion`). No arm fixes these.
* **Old robot-state false positives (`demo_172`, and the `demo_180` A-right/B-wrong case)**
  — on `demo_172` (human `place` + `release_attempt`) the state arms G1/T1/T2 all predict
  `idle` + `object_motion`, i.e. the summary actively pulls the answer away from the
  release. On the idle `demo_180` no-event segment, G0 is the only arm that is fully
  correct (`idle`, no events); G1/T1 predict `grasp_attempt` and T0 predicts
  `object_motion`. The old v0.2.1 + no-state arm remains the safest on these two.
* **`demo_71-S0003`** — G0/T0 predict the correct event set but the wrong phase; G1 is
  the permanent invalid cell; T1/T2 predict `approach` with an extra `object_motion`.
* **Only arm with zero wins** — T2 has 0/12 exact event sets end-to-end.

## 6. Decision

**`NO_GAIN`.**

* The chronological three-frame temporal prompt (T0) **hurts**: micro-F1 drops by 0.22
  against G0 and phase correctness collapses from 7 to 3.
* The old whole-segment Robot State summary (G1) is a small negative vs G0, consistent
  with the earlier negative-gain finding.
* Interval-aligned Robot State (T2) does not beat whole-segment state (T2 vs T1 negative)
  and adds `object_motion` false positives; its small edge over T0 only brings it back
  toward G0, not past it.
* No arm meets the pre-registered +0.10 threshold, and no arm fixes the two systematic
  error classes (`object_motion` recall, `grasp_attempt` FP on approaches).
* The binding constraint looks like **which frames are shown**, not how the prompt or the
  state summary is worded: three fixed keyframes cannot support `object_motion` for the
  transport segments and invite `grasp_attempt` on empty approaches equally in every arm.
  Therefore **G3E Adaptive Keyframes is a justified next hypothesis**, but it must be
  pre-registered as a fresh experiment; stacking more prompt/state variants on this input
  is not supported by the data. G3E remains an unexecuted design option, not a result.

Development cohort only — these are not held-out test results, and no arm may be
described as validated for independence.

## 7. Cost

* Total model calls: **61** (60 first attempts + 1 retry); all are counted.
* Tokens: **176,612 prompt + 9,682 completion**. Wall time: **173.75 s** of summed call
  latency. Sampled GPU VRAM constant at **4351 MiB** of 8188 MiB (RTX 4060 Laptop).
* Per-arm token totals (P+C): G0 29,563 · G1 38,827 · T0 32,562 · T1 38,843 · T2 46,499.
  T2 costs ~57% more tokens than G0 for a lower F1.

## 8. Artifacts and reproduction

* Implementation: `scripts/run_g3d2_five_arm.py` (retry protocol),
  `scripts/evaluate_g3d2r_reliability.py` + `src/project2_g3/g3d2r_reliability.py`
  (post-hoc analysis), tests in `tests/test_g3d2r_reliability.py`.
* Reproduction: start the frozen local `llama-server` with the GGUF + mmproj above, then
  `python scripts/run_g3d2_five_arm.py --stage full --protocol fallback_json_object_retry_v1 ...`
  into a new directory, then
  `python scripts/evaluate_g3d2r_reliability.py --run-dir <dir> --human-reference <local filled G3C v2 CSV>`.
* The human multi-event reference stays local and is intentionally not committed.
* The earlier 44-cell prefix and the old `outputs/g3d2/full_main_r2` run are **not** mixed
  into any number in this document.
