# Project 2 / G1-P4 Formal Evaluation Audit Run Preparation Result

Date: 2026-09-29

## Outcome

The frozen G1 Final Config was executed once on the exact frozen 24-Episode
Independent Evaluation Manifest. The resulting immutable inference package is
ready for blind Owner Human Evaluation Audit. No Evaluation GT was created and
no formal Evaluation scoring was run.

## Frozen identities

- Git base: `90d9bb1b389d51477ab46a24ee4dc07bdf068219`
- Manifest: `G1_P4_EVAL_MANIFEST_v1`
- Manifest CSV SHA256: `d2cd12f1555b4d98e731eedab353471b2b892d1033d57db3c0b8a12a23efc471`
- Frozen Config: `G1 Final Config FROZEN_v1`
- Stage A acceptance: `A1-007-C002`
- `tau_P12 = 0.04758563666765155`
- `tau_C12 = 0.690169167642685`
- `boundary_consolidation_window = 8`
- Dataset: `robomimic_v15_can_mh`
- Raw SHA256: `6f5a0e96fc375468ae19ccac86a6dee3b4d3862ef0fe37ca2d02e93d9046fe6b`
- Low-dim SHA256: `c4a34c837913446d295c6ca38f2b31888d69812198478af470ecb84a99e9f7d7`

The 24 episode IDs and order exactly match the frozen CSV. Read-only
disjointness recheck found zero overlap with Exploratory, Calibration, and the
Design Diagnostic set.

## Run

- Run ID: `g1_evaluation_20260929_091650_b130c820`
- `run_stage = EVALUATION`
- `set_role = EVALUATION`
- Episodes attempted/completed/failed: `24 / 24 / 0`
- Predicted Final Boundaries: `99`
- Segments: `123`
- Candidates: `194`

These counts are prediction-side runtime diagnostics only. They make no quality
claim and were not used to change the configuration or Evaluation Manifest.

The package contains the frozen snapshots, dataset/freeze/disjointness checks,
Formal Signals, candidate tables, P12/C12 acceptance trace, consolidation
lineage, Final Boundaries, segment manifests, signal plots, and videos for all
24 episodes.

## Human audit isolation

The run owns a separate `evaluation_human_review.sqlite` and a run-local Audit
Web registry. The Calibration registry, Calibration Owner SQLite, Calibration
GT, and historical Human Review were not written. The existing review schema
supports `VALID`, `REDUNDANT`, `MISALIGNED + corrected_frame`, and human-added
`MISSED_BOUNDARY + human_frame`, including reason and optional note.

The Evaluation UI displays:

- `RUN_STAGE = EVALUATION`
- `SET_ROLE = EVALUATION`
- `MANIFEST = G1_P4_EVAL_MANIFEST_v1`
- `FROZEN_CONFIG = G1 Final Config FROZEN_v1`
- `MUST_NOT_FEED_BACK_TO_CALIBRATION`

It does not display Evaluation Precision, Recall, F1, FP/FN, or any automatic
Evaluation GT.

## Gate status

```text
FORMAL_EVALUATION_INFERENCE_RUN_CREATED = YES
HUMAN_EVALUATION_AUDIT_READY = YES
HUMAN_EVALUATION_AUDIT_COMPLETE = NO
CANONICAL_EVALUATION_GT_CREATED = NO
FORMAL_EVALUATION_SCORING_EXECUTED = NO
FROZEN_CONFIG_MODIFIED = NO
READY_FOR_OWNER_EVALUATION_HUMAN_AUDIT = YES
```

The next action is the Owner's blind Human Evaluation Audit across all 24
episodes. This document does not score Evaluation and does not close G1.
