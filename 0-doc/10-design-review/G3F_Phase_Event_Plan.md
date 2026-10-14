# G3F Phase–Event Plan (pre-registered) — 2026-10-14

Base main: `05228ce2dfe5cb8a759b1b3d7431359ad296c5da`.

This plan is frozen **before** the full Development inference. The success
criteria below are also encoded in `scripts/run_g3f_paired.py` as
`SUCCESS_CRITERIA` and are evaluated only after all 24 cells exist. They are not
adjusted after seeing results.

## 1. Question

Does removing the Phase–Event conflict in the prompt (v0.2.2) reduce the
`object_motion` under-reporting seen in G3D2-R, **without** adding false
`object_motion`, and does it improve overall event recognition?

This is a targeted semantic fix, not a new round of prompt engineering.

## 2. Matrix

| Arm | RGB | Prompt | Robot State | Can Position |
|---|---|---|---|---|
| A | frozen 3 frames | v0.2.1 (`11b874a3…`) | none | none |
| B | identical 3 frames | v0.2.2 (`61ac6bce…`) | none | none |

Same for BOTH arms: Qwen3-VL-4B Q4_K_M GGUF + mmproj (identical SHA), the frozen
v0.2 Schema, segment identity, seed 1234, temperature 0, max_tokens 512, the same
`llama-server` config, and the frozen `FALLBACK_JSON_OBJECT_RETRY_V1` retry
protocol (2 structure / 3 service attempts). No retry or parameter differs per
arm. B − A therefore isolates the prompt change (including the added self-check,
which is a bundle and cannot be attributed to one sentence without a later
ablation).

## 3. Stages

| Stage | Segments | Cells | Notes |
|---|---|---|---|
| Pilot | `demo_2-S0003`, `demo_4-S0003`, `demo_169-S0002`, `demo_180-S0001` | 4 × 2 = 8 | plumbing/validity/cost only; these are known Development samples, so an improving pilot proves nothing about generalization |
| Full | the 12 frozen Development segments | 12 × 2 = 24 | new Run ID; A and B both re-run from scratch |

* The full run must use a **new run directory**. Historical G3D2-R G0 outputs are
  never spliced in as the baseline.
* The full run starts only if the pilot is 8/8 valid and the pilot records the
  same two prompt SHAs.
* RGB pixel SHA-256 is verified for all 36 images before any call; model/mmproj
  identity and the frozen prompt/schema SHAs are verified before any call;
  competing GPU processes abort the run.

## 4. Metrics

Primary: multi-event micro-F1, event-set exact match, motion-phase accuracy.
Key events: `object_motion` TP/FP/FN, `grasp_attempt` TP/FP/FN,
`release_attempt` TP/FP/FN. Also reported: reliability (first-attempt valid,
retries, failures), tokens, wall time, GPU memory.

## 5. Pre-registered success criteria

B may proceed as a Development **candidate** only if **all** hold:

1. micro-F1(B) − micro-F1(A) **≥ +0.10**;
2. at least **2 of the 3** `object_motion` true positives recovered;
3. `object_motion` false positives increase by **at most 1**;
4. motion-phase correct count drops by **at most 1**;
5. event-set exact-match count is **not lower** than A;
6. JSON/Schema/frame-evidence engineering requirements are met equally by A and B.

If any criterion fails → **NO_GAIN**, and prompt expansion stops. Even if all
pass, B is only a `CANDIDATE`, requiring a later **Episode-disjoint** held-out
evaluation before any performance claim.

## 6. Diagnosis plan (P5)

For every segment classify A→B as `PHASE_CORRECTED`, `EVENT_RECOVERED`,
`EVENT_FALSE_POSITIVE_ADDED`, `PHASE_EVENT_CONSISTENCY_IMPROVED`,
`CONSISTENT_BUT_WRONG`, or `NO_CHANGE`, and print both `observation_note`s.
Report failures as well as successes. Specifically watch: `demo_2`/`demo_4`/
`demo_159` (recover `object_motion`?), `demo_169`/`demo_232`/`demo_72` (new
false positives?), `demo_180` (CLOSED-as-grasp?), `demo_172` (spurious object
motion?).

## 7. Out of scope this round

Robot State, Can Position, extra frames, QC-triggered retry, two-stage
annotation, and any change to the frozen v0.2.1 prompt or the G3D2-R results.
