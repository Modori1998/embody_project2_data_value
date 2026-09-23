# Project 2 G1-P3 Stage A1/A2 Calibration Result

```text
DATE = 2026-09-23
PROTOCOL = FROZEN_v1.2
RUN_ID = g1_p3_stage_a12_20260923_170635_d0c0e0cb
CALIBRATION_CONFIG_FROZEN = NO
STAGE_B_EXECUTED = NO
EVALUATION_TOUCHED = NO
NEXT_GATE = DESIGN_OWNER_STAGE_A1_A2_CONFIG_REVIEW
```

## 1. Baseline replay gate

The current Formal Signals, unchanged baseline generation/config, full boundary
engine, frozen one-to-one matching, and frozen 12-episode Canonical GT reproduce
the baseline exactly:

```text
TP = 56, FP = 10, FN = 0
Precision = 0.8484848484848485
Recall = 1.0
F1 = 0.9180327868852458
Gripper recall = 1.0
Merged-cluster recall = 1.0
Seed valid-Direction recall = 1.0
Fresh valid-Direction recall = 1.0
NEW_UNANCHORED_FP = 0
```

Identity remained `config_hash=dde590e759a31cb8c865369e18256ebecbbd01bc94a58e1d3ca695bb50f2a630`,
`signal_contract_hash=24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d`,
snapshot `g1_canonical_gt_20260918_131636_c9916b89`, and the exact frozen 12 episodes.

## 2. Direction cohort and breakpoints

The baseline eligible independent-Direction cohort contains 26 events (17
VALID, 9 known Direction FP). Twenty-five have complete P12 context and yield
24 adjacent-value midpoints; the no-gate baseline is also recorded, for 25 A1
config rows. Complete P12 values span 0.02175541491690641 to
0.177182199961986. One edge event, `data/demo_242@224`, lacks P12 and C12
right context and is retained fail-open.

Twenty-four events have valid C12 context, yielding 23 adjacent-value C12
midpoints for every surviving P12 threshold. Valid C12 values span
0.619112575080552 to 0.976625176822308. No shortened-window substitute was
used.

Threshold construction reads only values recomputed from Formal Signals for
the frozen Calibration episodes. The 20-event diagnostic CSV/history/adjudication
is not a threshold input.

## 3. Stage A1 — P12 only

Twenty-four P12 midpoint configs were fully rerun through generation, debounce,
acceptance, consolidation, pause/segment postprocess, matching and scoring.
Seven pass every HARD guardrail.

The strongest metrics-only A1 review candidate (not a selected/final config) is:

```text
candidate = A1-007
tau_P12 = midpoint(0.041690904318396275, 0.05348036901690683)
        = 0.04758563666765155
TP/FP/FN = 56/3/0
Precision/Recall/F1 = 0.9491525423728814 / 1.0 / 0.9739130434782608
Direction FP remaining = 2
Seed/Fresh Direction FP remaining = 1/1
```

It removes known Direction FP at `demo_242@41`, `demo_242@78`,
`demo_242@136`, `demo_255@116`, and `demo_278@83/@105/@125`.
The remaining known Direction FP are `demo_162@211` and `demo_242@60`.
The first threshold above this survivor region rejects a legal Direction, so
legal Direction is demonstrably threatened by more aggressive P12 thresholds;
those configs are marked `HARD_GUARDRAIL_FAIL` and cannot enter A2.

## 4. Stage A2 — conditional C12

Seven A1 survivors times 23 C12 midpoints produced 161 complete pipeline
reruns. Fourteen satisfy all absolute HARD guardrails. Seven additionally pass
the incremental gate, including a strict decrease in Fresh Direction FP versus
their own P12-only parent; therefore the gain is not Seed-only.

All seven promotable rows use the same naturally generated Calibration
breakpoint:

```text
tau_C12 = midpoint(0.6313066374425232, 0.7490316978428467)
        = 0.690169167642685
```

For parent `A1-007`, candidate `A1-007-C002` changes TP/FP/FN from 56/3/0 to
56/2/0, Direction FP from 2 to 1, and Fresh Direction FP from 1 to 0 while all
four recall guardrails remain 1.0. The residual Direction FP is Seed. This is
an incremental-promotion candidate, not a final selection.

## 5. Edge and audit interpretation

Across all debounced Direction candidates in a run, 10 lack complete P12
lookahead and are retained fail-open. For P12-pass candidates entering the C12
variant, incomplete C12 falls back to P12-only; the candidate tables record the
per-config counts. Candidate-level decisions and reasons are in
`candidate_acceptance_trace.csv`.

The Design Owner should review the seven A1 survivors and seven A2 promotable
candidates, especially the simplicity/extra-Fresh-FP tradeoff between
`A1-007` and `A1-007-C002`. This report intentionally does not choose between
them.

```text
DIAGNOSTIC_SET_USED_FOR_THRESHOLD_SELECTION = NO
HUMAN_LABEL_ADDED = NO
CANONICAL_GT_MODIFIED = NO
CALIBRATION_CONFIG_FROZEN = NO
STAGE_B_EXECUTED = NO
EVALUATION_TOUCHED = NO
NEXT_GATE = DESIGN_OWNER_STAGE_A1_A2_CONFIG_REVIEW
```
