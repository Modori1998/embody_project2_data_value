# Project 2 G1-P3 Stage A Selection and Stage B Gate

```text
DATE = 2026-09-24
DOCUMENT_STATUS = OWNER_DECISION_RECORDED
SOURCE_OF_TRUTH = GITHUB_MAIN
PARENT_STAGE_A_RESULT = Project2_G1_P3_Stage_A1_A2_Calibration_Result_20260923.md
CALIBRATION_PROTOCOL = FROZEN_v1.2

STAGE_A_OWNER_SELECTION = A1-007-C002
STAGE_A_OWNER_SELECTION_STATUS = SELECTED_FOR_DOWNSTREAM_CALIBRATION
CALIBRATION_CONFIG_FROZEN = NO
G1_FINAL_CONFIG = NOT_FROZEN

STAGE_B_GATE = OPEN
NEXT_GATE = STAGE_B_LIMITED_CONSOLIDATION_IMPLEMENTATION

CANONICAL_GT_MODIFIED = NO
HUMAN_REVIEW_MODIFIED = NO
EVALUATION_TOUCHED = NO
```

## 1. Owner Stage A Selection

Design Owner 选择：

```text
A1-007-C002

tau_P12 = 0.04758563666765155
tau_C12 = 0.690169167642685
```

正常 context 完整时，Direction Candidate Acceptance 为：

```text
KEEP Direction candidate
IF
P12 >= 0.04758563666765155
AND
C12 >= 0.690169167642685
```

Edge policy、P12/C12 operational definition、Candidate Generation 固定规则继续完全继承 Calibration Protocol FROZEN v1.2。

本次选择只表示：

```text
STAGE_A_ACCEPTANCE_SELECTED = YES
```

不表示：

```text
CALIBRATION_CONFIG_FROZEN = YES
FINAL_CONFIG_FROZEN = YES
```

Stage B / Stage C 尚未完成，因此整个 G1 Calibration Config 仍未冻结。

## 2. Evidence from Stage A1/A2

Stage A1/A2 正式 Calibration run：

```text
RUN_ID = g1_p3_stage_a12_20260923_170635_d0c0e0cb
BASELINE = TP/FP/FN 56/10/0
A1-007 = TP/FP/FN 56/3/0
A1-007-C002 = TP/FP/FN 56/2/0
```

A1-007-C002 保持：

```text
Recall = 1.0
FN = 0
Seed valid-Direction recall = 1.0
Fresh valid-Direction recall = 1.0
Gripper recall = 1.0
Merged-cluster recall = 1.0
```

因此 Design Owner 接受 A1-007-C002 作为后续 Stage B 的固定 Stage A 输入。

## 3. Residual FP Owner Audit

### 3.1 data/demo_242 @60

历史 Human GT：

```text
candidate_type = DIRECTION_CHANGE
human_decision = REDUNDANT
reason_code = REDUNDANT_DIRECTION_JITTER
```

Owner 复核后维持原判断：

```text
OWNER_REVIEW = KEEP_EXISTING_HUMAN_GT
RESIDUAL_ROLE = ACCEPTANCE_RESIDUAL
STAGE_B_OPTIMIZATION_TARGET = NO
```

该处虽存在抓取尝试过程中的明显方向调整，但仍不应形成独立 behavior-segment boundary。它不是“两个应合为同一 physical event 的 surviving boundary”问题，因此不得用扩大 consolidation window 来掩盖该 residual Acceptance error。

### 3.2 data/demo_255 @135

现有相邻 Final Boundary / Candidate 语义：

```text
frame 125 = GRIPPER_TRANSITION
frame 135 = IDLE_TO_MOVE
distance = 10 frames = 0.50 s @20Hz
```

历史 Human GT：

```text
frame 125 = VALID
frame 135 = REDUNDANT
reason_code = REDUNDANT_SHORT_PAUSE
owner note = 确实有一点停顿，但是应该合并到125夹爪
```

Owner 复核后维持原判断：

```text
OWNER_REVIEW = KEEP_EXISTING_HUMAN_GT
PHYSICAL_EVENT_JUDGMENT =
GRIPPER_TRANSITION@125 + IDLE_TO_MOVE@135
BELONG_TO_THE_SAME_PHYSICAL_EVENT

ERROR_ATTRIBUTION = UNDER_CONSOLIDATION
STAGE_B_TRIGGER = CONFIRMED
```

因此该案例构成 Stage B 的有效启动证据。

## 4. Stage B Gate

Calibration Protocol v1.2 已冻结 Stage B 为 Limited Consolidation，只有 Stage A 稳定、HARD guardrail 全绿且仍存在 consolidation error 时才执行。

上述条件现在满足，因此冻结执行 Gate：

```text
STAGE_B_GATE = OPEN

STAGE_B_FIXED_PARENT =
A1-007-C002

STAGE_B_ONLY_SEARCH_AXIS =
boundary_consolidation_window

STAGE_B_CANDIDATES =
8
10
12
```

Stage B 必须保持：

```text
tau_P12 = 0.04758563666765155
tau_C12 = 0.690169167642685

Direction Candidate Generation = unchanged baseline
P12/C12 definitions = unchanged
Canonical GT = unchanged
Human Review = unchanged
Matching = frozen ±3 frame one-to-one
Evaluation = untouched
```

禁止把 Stage B 与 P12/C12、Direction threshold、persistence、pause bridge duration 或其它轴组成新网格。

## 5. Stage B Success Question

Stage B 只回答：

> 在固定 A1-007-C002 后，8 / 10 / 12 frame 的 Boundary Consolidation window 中，是否存在一个配置能正确处理 `demo_255@135` 的 under-consolidation，同时不损害真实独立 boundary、HARD guardrails、Recall、Localization 与 fragmentation。

特别要求：

```text
demo_242@60 =
NOT_A_STAGE_B_TARGET
```

如果某个更大的 consolidation window 只是“顺带吞掉” Acceptance residual 或其它真实独立事件，这不能计为 Stage B 的有效收益。

## 6. Next Gate

执行顺序：

```text
A1-007-C002 fixed
        ↓
Stage B
window = 8 / 10 / 12
each candidate full-pipeline rerun
        ↓
HARD guardrail + FP/FN + fragmentation + localization comparison
        ↓
Design Owner Stage B Selection
        ↓
Stage C Regression Only
        ↓
Final Calibration Config Freeze
        ↓
Independent Evaluation
```

当前冻结状态：

```text
STAGE_A_OWNER_SELECTION = A1-007-C002
STAGE_B_GATE = OPEN
NEXT_GATE = STAGE_B_LIMITED_CONSOLIDATION_IMPLEMENTATION
CALIBRATION_CONFIG_FROZEN = NO
EVALUATION_TOUCHED = NO
```
