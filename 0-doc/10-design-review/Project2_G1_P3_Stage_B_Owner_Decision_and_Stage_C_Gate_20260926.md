# Project 2 G1-P3 Stage B Owner Decision and Stage C Gate

```text
DATE = 2026-09-26
DOCUMENT_STATUS = OWNER_DECISION_RECORDED
SOURCE_OF_TRUTH = GITHUB_MAIN
PARENT_STAGE_B_RESULT = Project2_G1_P3_Stage_B_Limited_Consolidation_Result_20260924.md
CALIBRATION_PROTOCOL = FROZEN_v1.2

STAGE_A_PARENT = A1-007-C002
tau_P12 = 0.04758563666765155
tau_C12 = 0.690169167642685

STAGE_B_EXECUTED = YES
STAGE_B_OWNER_DECISION = NO_SAFE_INCREMENTAL_CHANGE
STAGE_B_WINDOW_10 = REJECT_HARD_GUARDRAIL
STAGE_B_WINDOW_12 = REJECT_HARD_GUARDRAIL
STAGE_B_EFFECTIVE_WINDOW_FOR_STAGE_C = RETAIN_PARENT_8

STAGE_C_GATE = OPEN
NEXT_GATE = STAGE_C_REGRESSION_IMPLEMENTATION

CALIBRATION_CONFIG_FROZEN = NO
G1_FINAL_CONFIG = NOT_FROZEN
CANONICAL_GT_MODIFIED = NO
HUMAN_REVIEW_MODIFIED = NO
EVALUATION_TOUCHED = NO
```

## 1. Stage B Result Basis

Stage B 固定 Stage A parent：

```text
A1-007-C002
tau_P12 = 0.04758563666765155
tau_C12 = 0.690169167642685
```

只对以下单一轴做正式比较：

```text
boundary_consolidation_window ∈ {8,10,12}
```

Immutable Stage B run：

```text
g1_p3_stage_b_20260924_173040_5be5fa47
```

Parent replay at window=8：

```text
TP/FP/FN = 56/2/0
Precision = 0.9655172413793104
Recall = 1.0
F1 = 0.9824561403508771
HARD_GUARDRAIL = PASS
NEW_UNANCHORED_FP = 0
```

## 2. Intended Consolidation Trigger

已确认的 Stage B trigger：

```text
data/demo_255
frame 125 = GRIPPER_TRANSITION
frame 135 = IDLE_TO_MOVE
distance = 10 frames = 0.50 s @20Hz

Owner semantics:
GRIPPER_TRANSITION@125
+
IDLE_TO_MOVE@135
=
SAME_PHYSICAL_EVENT
```

因此：

```text
ERROR_ATTRIBUTION = UNDER_CONSOLIDATION
```

真实 pipeline 结果：

```text
window=8  → SAME_FINAL_CLUSTER = NO
window=10 → SAME_FINAL_CLUSTER = YES
window=12 → SAME_FINAL_CLUSTER = YES
```

这证明 under-consolidation 的机制归因成立，但不代表扩大全局 consolidation window 是安全方案。

## 3. Global Window Expansion Fails Guardrails

### window = 10

```text
TP/FP/FN = 52/2/4
Recall = 0.9285714285714286
F1 = 0.9454545454545454
Fresh valid Direction recall = 0.7272727272727273
NEW_UNANCHORED_FP = 1
HARD_GUARDRAIL = FAIL
```

相对 window=8：

```text
CHANGED_CLUSTER_COUNT = 6
OVER_CONSOLIDATION_CASE_COUNT = 4
```

主要错误合并包括：

```text
data/demo_255 @4/@14
data/demo_260 @66/@75
data/demo_260 @137/@146
data/demo_270 @4/@13
```

### window = 12

```text
TP/FP/FN = 50/2/6
Recall = 0.8928571428571429
F1 = 0.9259259259259259
Fresh valid Direction recall = 0.5454545454545454
NEW_UNANCHORED_FP = 1
HARD_GUARDRAIL = FAIL
```

相对 window=8：

```text
CHANGED_CLUSTER_COUNT = 9
OVER_CONSOLIDATION_CASE_COUNT = 6
```

除 window=10 已出现的 unsafe merge 外，还包括：

```text
data/demo_255 @63/@75
data/demo_260 @91/@103
```

因此：

```text
STAGE_B_SAFE_CANDIDATES = []
MINIMAL_SAFE_WINDOW_CANDIDATE = NONE
```

## 4. Owner Decision

Design Owner 决定：

```text
window=10 = REJECT
window=12 = REJECT
```

原因不是它们无法修复目标案例，而是：

```text
LOCAL_TARGET_FIXED = YES
SYSTEM_LEVEL_REGRESSION = UNACCEPTABLE
```

即：为了修复一个已知 under-consolidation case，引入多个 FN、Fresh valid-Direction recall 下降及新 unanchored FP，不符合 Frozen HARD guardrails。

因此 Stage B 的正式结论是：

```text
STAGE_B_OWNER_DECISION = NO_SAFE_INCREMENTAL_CHANGE
```

而不是：

```text
STAGE_B_SELECTED_WINDOW = 8
```

window=8 只是保留 Stage A parent 原有 postprocess 配置，作为 Stage C 的输入：

```text
STAGE_B_EFFECTIVE_WINDOW_FOR_STAGE_C = RETAIN_PARENT_8
```

## 5. Residual Policy

### data/demo_242 @60

继续维持：

```text
HUMAN_GT = REDUNDANT_DIRECTION_JITTER
ROLE = ACCEPTANCE_RESIDUAL
STAGE_B_TARGET = NO
```

Stage B 8/10/12 均未改变该 residual。

### data/demo_255 @135

继续维持：

```text
HUMAN_GT = REDUNDANT_SHORT_PAUSE
ERROR_ATTRIBUTION = UNDER_CONSOLIDATION
```

由于没有任何允许的全局 consolidation window 能在修复该 case 的同时保持 HARD guardrails：

```text
RESIDUAL_DISPOSITION =
ACCEPT_KNOWN_CALIBRATION_RESIDUAL_FOR_NOW
```

含义：

- 不修改 Human GT；
- 不修改 Canonical GT；
- 不扩大 Stage B search space；
- 不新增 pair-specific / type-specific consolidation rule；
- 不为了一个 case 发起新的全局规则搜索；
- 在 Stage C 中继续作为 residual inventory 被追踪；
- 若 Independent Evaluation 以后证明该类错误具有系统性，再走新的 Design Change Request。

## 6. Stage C Gate

Stage C 现在打开。

固定 pre-freeze candidate：

```text
Stage A Acceptance =
A1-007-C002

tau_P12 =
0.04758563666765155

tau_C12 =
0.690169167642685

boundary_consolidation_window =
8  # retained parent value, not a Stage B optimization win
```

Stage C：

```text
REGRESSION_ONLY = YES
NEW_SEARCH_AXIS = FORBIDDEN
PARAMETER_TUNING = FORBIDDEN
```

至少复核：

```text
Seed guardrails
Fresh non-regression
FN
NEW_UNANCHORED_FP
known residual inventory
fragmentation
Localization
edge-context fallback / flags
deterministic replay
protected artifact identity
```

Stage C 不得：

```text
re-search P12/C12
re-search consolidation
change pause bridge
change Direction generation
change Canonical GT
change Human Review
touch Evaluation Set
freeze Final Config silently
```

## 7. Next Gate

```text
STAGE_B = CLOSED_NO_SAFE_INCREMENTAL_CHANGE
STAGE_C_GATE = OPEN
NEXT_GATE = STAGE_C_REGRESSION_IMPLEMENTATION
```

Stage C 通过后必须 STOP，返回 Design Owner 做 Final Calibration Config Review。

只有 Design Owner 明确确认后，才允许：

```text
CALIBRATION_CONFIG_FROZEN = YES
```

然后才可进入 Independent Evaluation。
