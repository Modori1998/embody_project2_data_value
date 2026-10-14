# G3F-P1 Plan (pre-registered) — 2026-10-14

Base main: `2969475e8e6ff6b37a33010ad21cf1116beaf11e`. Frozen **before** the full
Development inference; the criteria are also encoded in
`scripts/run_g3f_p1_paired.py::SUCCESS_CRITERIA`.

## 1. Question

Is the *minimal* semantically-correct prompt (v0.2.3) better than (a) the old
v0.2.1 with its known defect and (b) the over-triggering v0.2.2 expansion — and
can it recover true `object_motion` without the false positives?

## 2. Matrix (all three arms freshly run, new Run ID)

| Arm | Prompt | Role |
|---|---|---|
| A | v0.2.1 (`11b874a3…`) | historical performance reference, contains the known semantic defect |
| B | v0.2.2 (`61ac6bce…`) | the executed expansion + self-check |
| C | v0.2.3 (`cb9fa472…`) | minimal correct semantics (only the one sentence) |

Identical for all three arms: Qwen3-VL-4B Q4_K_M + mmproj (same SHA), the frozen
3 RGB frames (36 image SHA verified), v0.2 Schema, seed 1234, temperature 0,
max_tokens 512, the same `llama-server` config, the frozen
`FALLBACK_JSON_OBJECT_RETRY_V1` retry protocol. No Robot State, no Can Position.

Historical A/B responses from `outputs/g3f/full_r1` are **not** spliced in.

## 3. Stages

* Pilot: 4 segments (`demo_2`, `demo_4`, `demo_169`, `demo_180`) × 3 arms = 12
  cells. Engineering only; the 4 known samples are not used to tune anything.
* Full: the 12 frozen Development segments × 3 arms = 36 cells, after the pilot
  passes.

## 4. Metrics

Event micro-F1, event-set exact match, motion-phase accuracy, `object_motion`
TP/FP/FN, `grasp_attempt` TP/FP/FN, `release_attempt` TP/FP/FN, phase-event QC
findings, per-segment A/B/C predictions, tokens, wall time, retries, failures.

Primary contrasts: **C − A** (minimal fix vs old prompt) and **C − B** (minimal
fix vs the expansion).

## 5. Pre-registered Development release criteria

C may proceed to an independent Episode-disjoint evaluation only if **all** hold:

1. C `object_motion` TP ≥ 2 of 3;
2. C `object_motion` FP ≤ 2;
3. C micro-F1 ≥ the same-run A micro-F1;
4. C event-set exact match ≥ the same-run A;
5. C phase-correct count ≥ A − 1;
6. engineering validity and input identity meet the frozen requirements.

If any criterion fails:

* the **incorrect old semantics are not restored** (the defect stays fixed);
* v0.2.3 is retained as the semantically-correct candidate implementation;
* the automatic annotation quality is marked **NOT_READY**;
* diagnosis continues through visual-evidence analysis rather than more prompt
  churn.

Even if all pass, C is only a candidate for an independent, Episode-disjoint
evaluation — never a generalisation claim. No result may retro-edit the G3F
`NO_GAIN` conclusion.

## 6. Next-step plan (triggered by error type, P6)

* C still misses real object motion → check whether the model can even describe
  can displacement in `observation_note`; if not, the bottleneck is visual
  evidence extraction.
* note says static but `object_motion` emitted → prioritise evidence/label
  consistency QC (non-destructive), not auto-editing events.
* note correctly describes can motion but no event → prioritise independent event
  judgement / structured semantic mapping.
* model cannot reliably separate can motion from EEF motion → the next phase
  (G3E) design should include **E0** raw 3 frames, **E1** 5 uniformly selected
  frames, **E2** 5 adaptively selected frames, plus optionally RGB-derived Can
  Position as a separate candidate (simulator Object GT is never mixed into the
  formal input).

Adding frames is **not** asserted as necessary from these 12 Development samples
alone; it is a pre-registered hypothesis for G3E.

## 7. Out of scope

Model training, human-label edits, Robot State, Can Position input, extra RGB
input, QC-triggered retry, and any change to historical runs.
