# Project 2 / G1-P3 Stage B Limited Consolidation Result

Date: 2026-09-24

Status: `READY_FOR_DESIGN_OWNER_STAGE_B_REVIEW`

Immutable run: `g1_p3_stage_b_20260924_173040_5be5fa47`

## Scope and fixed parent

Stage B was executed as a single-factor Calibration experiment on the frozen 12-episode set. The fixed parent was `A1-007-C002` with `tau_P12 = 0.04758563666765155` and `tau_C12 = 0.690169167642685`. Only the runtime, in-memory `boundary_consolidation_window` changed, over the frozen search space `{8, 10, 12}`. No production default was changed, no Diagnostic Set value entered parameter selection, and no Evaluation data was read or run.

## Parent replay gate

Window 8 reproduced the selected Stage A parent exactly:

- TP / FP / FN: `56 / 2 / 0`
- Precision / Recall / F1: `0.9655172413793104 / 1.0 / 0.9824561403508771`
- Direction FP remaining: `1`
- Residuals: `data/demo_242@60 DIRECTION_CHANGE` and `data/demo_255@135 IDLE_TO_MOVE`
- Parent replay: `PASS`

## Window comparison

| Window | TP | FP | FN | Precision | Recall | F1 | Fresh valid Direction recall | New unanchored FP | Hard guardrail |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 8 | 56 | 2 | 0 | 0.9655172413793104 | 1.0 | 0.9824561403508771 | 1.0 | 0 | PASS |
| 10 | 52 | 2 | 4 | 0.9629629629629629 | 0.9285714285714286 | 0.9454545454545454 | 0.7272727272727273 | 1 | FAIL |
| 12 | 50 | 2 | 6 | 0.9615384615384616 | 0.8928571428571429 | 0.9259259259259259 | 0.5454545454545454 | 1 | FAIL |

Gripper recall, merged-cluster recall, and Seed valid Direction recall remained `1.0` for all three windows. Window 10 and 12 nevertheless fail the frozen hard guardrails because FN increases, Fresh valid Direction recall regresses, and a new unanchored FP appears.

Localization mean, median, p90, and max were all `0.0` frames for every matched boundary under every window. The 1–2 frame fragmentation ratio was `0.0` throughout. Segments per episode changed from `5.833333333333333` at window 8 to `5.416666666666667` at window 10 and `5.25` at window 12.

## Trigger lineage: data/demo_255 @125/@135

| Window | @125 GRIPPER_TRANSITION | @135 IDLE_TO_MOVE | Same final cluster | Final representative | Members |
|---:|---|---|---|---|---|
| 8 | `KEEP -> demo_255-B0005` | `KEEP -> demo_255-B0006` | NO | separate | `125`; `135` |
| 10 | `KEEP -> demo_255-B0004` | `MERGE_CONSOLIDATION -> demo_255-B0004` | YES | `GRIPPER_TRANSITION@125`, `demo_255-C0006` | `125|135` |
| 12 | `KEEP -> demo_255-B0003` | `MERGE_CONSOLIDATION -> demo_255-B0003` | YES | `GRIPPER_TRANSITION@125`, `demo_255-C0006` | `125|135` |

Thus the intended under-consolidation mechanism is fixed by windows 10 and 12 in the real pipeline. That intended effect is not guardrail-safe because both larger windows also merge independent valid events elsewhere.

## Non-target trace: data/demo_242 @60

For windows 8, 10, and 12, `demo_242-C0004 DIRECTION_CHANGE@60` remains an independent final at frame 60. It is not merged or suppressed. Therefore:

`ACCEPTANCE_RESIDUAL_CHANGED_BY_STAGE_B = NO`

Its persistence is not counted as a Stage B mechanism benefit or failure; it remains the known Stage A acceptance residual.

## Changed cluster audit

Relative to window 8, window 10 produced 6 changed-cluster lineage rows and window 12 produced 9. The complete member IDs, types, frames, representatives, and before/after GT matches are in `changed_cluster_lineage.csv`.

### Window 8 to 10

- `demo_255`: `4 GRIPPER_TRANSITION + 14 DIRECTION_CHANGE` merged; two valid GT became one match (`TP_TO_FN=YES`).
- `demo_255`: intended `125 GRIPPER_TRANSITION + 135 IDLE_TO_MOVE` merged; the valid GT at 125 remained matched and the redundant 135 boundary was removed.
- `demo_260`: `66 + 75 DIRECTION_CHANGE` merged; two valid GT became one match (`TP_TO_FN=YES`).
- `demo_260`: `137 MOVE_TO_IDLE + 146 GRIPPER_TRANSITION` merged; its new representative at 146 was unmatched, with the same-frame `146 IDLE_TO_MOVE` redistributed into a separate final. This changed region loses valid matching and creates the new unanchored FP.
- `demo_270`: `4 GRIPPER_TRANSITION + 13 DIRECTION_CHANGE` merged; two valid GT became one match (`TP_TO_FN=YES`).

The audit records 4 over-consolidation rows for window 10.

### Window 8 to 12

Window 12 includes all material unsafe mergers above and additionally:

- `demo_230`: an extra Direction member at 119 joins the final represented at 108 without loss of its GT match.
- `demo_255`: `63 + 75 DIRECTION_CHANGE` merged; two valid GT became one match (`TP_TO_FN=YES`).
- `demo_260`: `91 DIRECTION_CHANGE + 103 MOVE_TO_IDLE` merged; two valid GT became one match (`TP_TO_FN=YES`).

The audit records 6 over-consolidation rows for window 12.

## Stage B decision surface

- Window 8 is the control and passes hard guardrails, but does not fix the confirmed `demo_255@125/@135` under-consolidation.
- Windows 10 and 12 fix the intended trigger, but both fail hard guardrails and are not Owner-review-safe Stage B candidates.
- `STAGE_B_SAFE_CANDIDATES = []`
- `MINIMAL_SAFE_WINDOW_CANDIDATE = NONE`

No final window is selected or frozen by this run. The result is returned to the Design Owner because the allowed search space contains no config that both fixes the intended mechanism and preserves the frozen guardrails.

## Required status

`STAGE_B_EXECUTED = YES`

`STAGE_B_OWNER_SELECTION_PENDING = YES`

`STAGE_C_EXECUTED = NO`

`CALIBRATION_CONFIG_FROZEN = NO`

`EVALUATION_TOUCHED = NO`

`CANONICAL_GT_MODIFIED = NO`

`HUMAN_REVIEW_MODIFIED = NO`
