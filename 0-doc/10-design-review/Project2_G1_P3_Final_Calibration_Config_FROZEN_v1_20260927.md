# Project 2 G1-P3 Final Calibration Config FROZEN v1

```text
DATE = 2026-09-27
DOCUMENT_STATUS = FROZEN_v1
FROZEN = YES
SOURCE_OF_TRUTH = GITHUB_MAIN

CALIBRATION_PROTOCOL = FROZEN_v1.2
STAGE_C_RESULT = Project2_G1_P3_Stage_C_Regression_Result_20260926.md
STAGE_C_RUN = g1_p3_stage_c_20260926_110515_07dd8743

DESIGN_OWNER_FREEZE_DECISION = CONFIRMED

CALIBRATION_CONFIG_FROZEN = YES
G1_FINAL_CONFIG = FROZEN_FOR_INDEPENDENT_EVALUATION
NEXT_GATE = P2_S1D_INDEPENDENT_EVALUATION

EVALUATION_TOUCHED_AT_FREEZE = NO
```

## 1. Final Frozen Config

Design Owner 明确确认冻结以下 G1 Calibration Config：

```text
STAGE_A_ACCEPTANCE_CONFIG = A1-007-C002

tau_P12 = 0.04758563666765155
tau_C12 = 0.690169167642685

boundary_consolidation_window = 8
```

其中 `boundary_consolidation_window=8` 的身份是：

```text
RETAINED_PARENT_VALUE_AFTER_STAGE_B_NO_SAFE_INCREMENTAL_CHANGE
```

不是 Stage B 搜索产生的优化胜者。

## 2. Frozen Acceptance Semantics

正常 context 完整的独立 Direction candidate：

```text
KEEP
IF
P12 >= 0.04758563666765155
AND
C12 >= 0.690169167642685
```

P12：

```text
P12 =
median(translation_speed_mps)
over relative_frame [+4,+12]
```

C12：

```text
left_straightness =
net_displacement / path_length
over relative_frame [-12,-1]

right_straightness =
net_displacement / path_length
over relative_frame [0,+11]

C12 =
min(left_straightness, right_straightness)
```

Edge policy 继续冻结为：

```text
IF P12 context incomplete:
    FAIL_OPEN_KEEP

IF P12 complete AND C12 context incomplete:
    APPLY_P12_ONLY_FALLBACK

SHORTENED_WINDOW_SUBSTITUTION = FORBIDDEN
```

Direction Candidate Generation、Formal Signals、debounce、pause bridge、short-segment handling 及其它未明确改变的 baseline 行为全部保持不变。

## 3. Freeze Evidence

Stage C 对同一 fixed config 做 deterministic replay，结果：

```text
TP / FP / FN = 56 / 2 / 0

Precision = 0.9655172413793104
Recall = 1.0
F1 = 0.9824561403508771

CALIBRATION_GRIPPER_RECALL = 1.0
CALIBRATION_MERGED_CLUSTER_RECALL = 1.0
SEED_VALID_DIRECTION_RECALL = 1.0
FRESH_VALID_DIRECTION_RECALL = 1.0

NEW_UNANCHORED_FP = 0

LOCALIZATION_MEAN_FRAMES = 0.0
LOCALIZATION_MEDIAN_FRAMES = 0
LOCALIZATION_P90_FRAMES = 0
LOCALIZATION_MAX_FRAMES = 0

FRAGMENTATION_1_2_RATIO = 0.0

P12_CONTEXT_INCOMPLETE_COUNT = 10
C12_CONTEXT_INCOMPLETE_COUNT = 6

PARENT_REPLAY = PASS
ALL_HARD_GUARDRAILS = PASS
DETERMINISTIC_REPLAY = PASS
PROTECTED_ARTIFACT_IDENTITY = PASS
NO_MASS_FRAGMENTATION = YES
EVALUATION_TOUCHED = NO
```

因此满足 Final Calibration Config Freeze 的 Owner Gate。

## 4. Known Residuals Accepted at Freeze

### data/demo_242 @60

```text
candidate_type = DIRECTION_CHANGE
human_reason = REDUNDANT_DIRECTION_JITTER
residual_role = ACCEPTANCE_RESIDUAL
```

冻结决定：

```text
KNOWN_RESIDUAL = ACCEPTED
NO_FURTHER_CALIBRATION_TUNING_FOR_THIS_CASE = YES
```

### data/demo_255 @135

```text
candidate_type = IDLE_TO_MOVE
human_reason = REDUNDANT_SHORT_PAUSE
residual_role = KNOWN_UNDER_CONSOLIDATION_RESIDUAL
```

Stage B 已证明 global consolidation window=10/12 虽能合并目标事件，但会引入不可接受的 over-consolidation 与 FN。

冻结决定：

```text
KNOWN_RESIDUAL = ACCEPTED
NO_PAIR_SPECIFIC_RULE = YES
NO_TYPE_SPECIFIC_PATCH = YES
NO_GLOBAL_WINDOW_EXPANSION = YES
```

## 5. Calibration Is Now Closed

从本 Freeze 生效起：

```text
CALIBRATION_SEARCH_CLOSED = YES
CALIBRATION_SET_MUST_NOT_BE_USED_FOR_FURTHER_TUNING = YES
```

禁止基于 Calibration Set 再修改：

```text
tau_P12
tau_C12
boundary_consolidation_window
direction threshold
direction persistence
pause bridge
debounce
motion threshold
gripper threshold
min segment length
matching tolerance
review taxonomy
其它 segmentation heuristic / special case
```

任何未来改变上述配置都必须：

```text
NEW_DESIGN_CHANGE_REQUEST
→ new protocol / version
→ new provenance
```

不得静默覆盖 FROZEN_v1。

## 6. Independent Evaluation Contract

下一阶段只允许：

```text
P2-S1D Independent Evaluation
```

要求：

- Evaluation Set 必须与 Calibration Set 隔离；
- Frozen Config 在看到 Evaluation 结果前保持不变；
- 正式 Evaluation 运行不得反向参与 parameter selection；
- Evaluation 暴露的 failure 只能记录为 evaluation evidence / future Design Change Request；
- 禁止在同一 Evaluation Set 上“看结果 → 调参 → 重跑并当正式结果”。

正式主 matching 继续沿用 Frozen Protocol：

```text
MAX_CARDINALITY_MIN_TOTAL_DISTANCE_ONE_TO_ONE
TOLERANCE_FRAMES = 3
TOLERANCE_SECONDS = 0.15
```

## 7. Gate Status

```text
G1_P3_CALIBRATION = CLOSED
CALIBRATION_CONFIG_FROZEN = YES
G1_FINAL_CONFIG = FROZEN_FOR_INDEPENDENT_EVALUATION

P2_S1D_GATE = OPEN
NEXT_GATE = P2_S1D_INDEPENDENT_EVALUATION

G1 = NOT_CLOSED
```

G1 只有在 Independent Evaluation 完成并通过 Design Owner review 后才允许关闭。
