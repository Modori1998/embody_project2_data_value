# Project 2 / G1-P3 Stage C Regression Result

Date: 2026-09-26

Status: `PASS_READY_FOR_FINAL_CALIBRATION_CONFIG_OWNER_REVIEW`

Immutable run: `g1_p3_stage_c_20260926_110515_07dd8743`

## 1. Fixed Candidate Config

Stage C executed regression checks only. It exposed no search surface and performed no parameter tuning.

```text
Stage A acceptance = A1-007-C002
tau_P12 = 0.04758563666765155
tau_C12 = 0.690169167642685
boundary_consolidation_window = 8

NEW_SEARCH_AXIS = FORBIDDEN
PARAMETER_TUNING = FORBIDDEN
THRESHOLD_SELECTION = FORBIDDEN
```

Window 8 is the retained parent postprocess value following the Stage B Owner decision `NO_SAFE_INCREMENTAL_CHANGE`; it is not described as a Stage B optimization win.

## 2. Parent Replay and Metrics

The fixed Candidate Config was run twice through the complete 12-Episode Calibration pipeline. Run A reproduced the Stage B parent exactly:

```text
TP / FP / FN = 56 / 2 / 0
Precision = 0.9655172413793104
Recall = 1.0
F1 = 0.9824561403508771
Direction FP remaining = 1
NEW_UNANCHORED_FP = 0
PARENT_REPLAY = PASS
```

## 3. HARD Guardrails

```text
CALIBRATION_GRIPPER_RECALL = 1.0
CALIBRATION_MERGED_CLUSTER_RECALL = 1.0
SEED_VALID_DIRECTION_RECALL = 1.0
FRESH_VALID_DIRECTION_RECALL = 1.0
FN = 0
NEW_UNANCHORED_FP = 0
ALL_HARD_GUARDRAILS = PASS
```

No new unmatched GT and no new unanchored prediction were produced.

## 4. Residual Inventory

The inventory was rebuilt from Stage C final predictions, frozen ±3-frame one-to-one matching, and known-FP anchor matching. It contains exactly two rows:

| Episode | Frame | Type | Final boundary | Representative | Reason | Role |
|---|---:|---|---|---|---|---|
| `data/demo_242` | 60 | `DIRECTION_CHANGE` | `demo_242-B0003` | `demo_242-C0004` | `REDUNDANT_DIRECTION_JITTER` | `ACCEPTANCE_RESIDUAL` |
| `data/demo_255` | 135 | `IDLE_TO_MOVE` | `demo_255-B0006` | `demo_255-C0008` | `REDUNDANT_SHORT_PAUSE` | `KNOWN_UNDER_CONSOLIDATION_RESIDUAL` |

Both predictions matched their existing known-FP anchors. `data/demo_242@60` remains the accepted Stage A acceptance residual. `data/demo_255@135` remains the accepted known under-consolidation residual under the retained parent postprocess. No demo-specific rule was added.

## 5. Edge-context Regression

```text
P12_CONTEXT_INCOMPLETE_COUNT = 10
C12_CONTEXT_INCOMPLETE_COUNT = 6
```

All 10 P12-incomplete candidates received `KEEP_EDGE_CONTEXT_INCOMPLETE`, implementing fail-open without a shortened substitute window. Nine remained active final members; one was subsequently handled by the unchanged postprocess as `MERGE_LEFT`. It was not rejected by Candidate Acceptance.

All 6 candidates with complete P12 and incomplete C12 received `KEEP_C12_CONTEXT_INCOMPLETE`, implementing P12-only fallback. All six remained active final members.

There was no automatic edge-context rejection, new FN, new unanchored FP, or unexpected acceptance suppression.

## 6. Fragmentation

```text
1_2_frame_segment_ratio = 0.0
segments_per_episode = 5.833333333333333
NO_MASS_1_2_FRAME_FRAGMENTATION = YES
```

The result aligns exactly with the Stage B parent at window 8. The existing implementation continues to report `short_segment_ratio` as a contract gap rather than inventing a new hard threshold.

## 7. Localization

Frozen matching tolerance remained ±3 frames, or ±0.15 seconds at 20 Hz.

| Metric | Frames | Seconds |
|---|---:|---:|
| Mean | 0.0 | 0.0 |
| Median | 0 | 0.0 |
| p90 | 0 | 0.0 |
| Max | 0 | 0.0 |

## 8. Determinism

Run A and Run B used identical signals and the identical fixed Candidate Config.

```text
FINAL_BOUNDARY_SET_IDENTICAL = YES
MATCHING_IDENTICAL = YES
METRICS_IDENTICAL = YES
RESIDUAL_INVENTORY_IDENTICAL = YES
ACCEPTANCE_TRACE_IDENTICAL = YES
EDGE_CONTEXT_COUNTS_IDENTICAL = YES
DETERMINISTIC_REPLAY_PASS = YES
```

Run IDs and timestamps were excluded from the comparison.

## 9. Protected Artifact Identity

Before/after fingerprints were identical for:

- Canonical GT snapshot;
- Seed and Fresh Human Calibration exports;
- Owner SQLite;
- Frozen Protocol v1.0, v1.1, and v1.2;
- Stage A Owner Decision;
- Stage B Owner Decision.

```text
PROTECTED_ARTIFACT_IDENTITY = PASS
PRE_EXISTING_STALE_FINGERPRINT_ASSERTION = YES
```

The Owner SQLite actual SHA256 remained `83e32b075f6d94ca117ad930a563e1152bb446174a1a84e7870a774978a39430` before and after Stage C. The existing baseline-scoring test still expects legacy SHA256 `076b3fe1504b23334cc861b32fb3145efaa92f187aa4002be1afcee7bc96c718`. Stage C did not modify SQLite or Human Review to satisfy that stale assertion.

## 10. Gate Result

```text
PARENT_REPLAY = PASS
ALL_HARD_GUARDRAILS = PASS
NO_NEW_RESIDUAL_FP = YES
NO_NEW_FN = YES
DETERMINISTIC_REPLAY = PASS
PROTECTED_ARTIFACT_IDENTITY = PASS
NO_MASS_FRAGMENTATION = YES
EVALUATION_TOUCHED = NO

READY_FOR_FINAL_CALIBRATION_CONFIG_OWNER_REVIEW = YES
CALIBRATION_CONFIG_FROZEN = NO
```

Stage C stops at the Design Owner gate. It does not freeze the final Calibration config and does not enter Independent Evaluation.
