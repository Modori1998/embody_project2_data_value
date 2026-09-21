# Project 2 G1-P3 Motion Sufficiency Rule Shape FROZEN v1

```text
DATE = 2026-09-21
DOCUMENT_STATUS = FROZEN_RULE_SHAPE_v1
FROZEN = YES
TASK = G1-P3 POST-A0 DIRECTION CANDIDATE ACCEPTANCE RULE SHAPE
SOURCE_OF_TRUTH = GITHUB_MAIN
BASE_EVIDENCE_COMMIT = 66e4d5d81b4cfa574d551f58b5b65f4a89acfcc4

DETECTOR_MODIFIED = NO
CONFIG_GENERATED = NO
PARAMETER_SEARCH_EXECUTED = NO
NUMERIC_THRESHOLD_FROZEN = NO
ANALYSIS_WINDOW_FROZEN_AS_DETECTOR_PARAMETER = NO
STAGE_A_EXECUTED = NO
STAGE_B_EXECUTED = NO
```

本文件冻结的是 **Rule Shape｜规则形状** 和下一步工程决策边界，不冻结任何数值阈值、窗口长度或最终 Detector 配置。

---

## 1. Authority / Evidence

本决策基于 GitHub `main` 当前已提交证据：

- `0-doc/Project2_G1_P3_Baseline_Scoring_Result_20260918.md`
- `0-doc/Project2_G1_P3_Stage_A0_Direction_Discriminability_Result_20260918.md`
- `0-doc/Project2_G1_P3_RuleFamilyA_Displacement_Preparation_Result_20260918.md`
- `0-doc/10-design-review/Project2_G1_P3_RuleFamilyA_Displacement_Design_Review_20260920.md`
- `0-doc/80-audit-local/g1_p3_rule_analysis/01_stage_a0_direction_event_analysis.csv`
- `0-doc/80-audit-local/g1_p3_rule_analysis/02_direction_event_window_trace.csv`
- `0-doc/80-audit-local/g1_p3_rule_analysis/README.md`

当前 Calibration Direction cohort：

```text
VALID_DIRECTION = 17
DIRECTION_FP = 9
TOTAL = 26
```

当前 Baseline：

```text
TP = 56
FP = 10
FN = 0
```

其中 9/10 FP 为 Direction FP。

---

## 2. Frozen Negative Decisions

以下路线在当前证据下不再作为主规则继续推进：

### 2.1 Direction Threshold Only｜仅方向阈值

```text
PRIMARY_ROUTE = REJECTED
```

Stage A0 已证明 VALID / FP evidence 大量重叠，且存在 FP evidence 高于全部 VALID 的反例。

### 2.2 Persistence Only｜仅持续时间

```text
PRIMARY_ROUTE = REJECTED
```

FP run_length 与 VALID 重叠，部分 FP 反而更长。

### 2.3 Threshold × Persistence｜方向阈值 × 持续时间

```text
PRIMARY_ROUTE = REJECTED
```

9/9 Direction FP 全部落在 VALID 的 evidence × run_length 最小下界盒内。

### 2.4 Displacement Hard Gate｜位移硬门控

```text
HARD_GATE = REJECTED
ROLE = AUXILIARY_EVIDENCE
```

Rule Family A Formal Review 已冻结：

```text
DISPLACEMENT_SUPPORTED_AS_AUXILIARY_EVIDENCE
```

原因是同时存在 high-displacement FP 与 low-displacement VALID。

### 2.5 Local Speed Minimum / Relative Speed Valley｜局部最低速度 / 相对速度谷

```text
PRIMARY_ROUTE = NOT_PROMOTED
```

`local_speed_min` 和 `speed_valley_ratio_min` 在 VALID / FP 之间仍存在明显 range overlap，且已有低速 VALID 反例。不得作为单变量 hard reject 条件。

---

## 3. Frozen Positive Design Direction

当前冻结的 Candidate Acceptance 规则形状：

```text
INDEPENDENT_DIRECTION_BOUNDARY_ACCEPTANCE
=
DIRECTION_EVIDENCE_SUFFICIENT
AND
PERSISTENCE_SUFFICIENT
AND
POST_MOTION_SUFFICIENT
AND
TRAJECTORY_COHERENT
```

中文解释：

一个独立 Direction Boundary 不能只证明“方向真的变了”，还需要证明：

1. **Post-motion Sufficiency｜后段运动充分性**  
   切点之后确实形成了一个持续的新运动阶段，而不是方向变化后迅速衰减、停顿或微调。

2. **Trajectory Coherence｜轨迹一致性**  
   切点两侧的运动轨迹具有足够一致性，不是明显的回摆、绕动、jitter 或 detour。

本文件冻结这两个语义条件进入后续正式设计。

---

## 4. Post-motion Sufficiency Evidence

当前分析导出中：

`right_speed_reference`

定义为：

```text
median(translation_speed_mps)
over relative_frame = [+4, +12]
```

即候选切点后约 +0.2 s 到 +0.6 s 的持续速度参考。

在当前 26 个 Calibration Direction events 上：

- VALID 的 `right_speed_reference` 最低约为 0.0535 m/s；
- 以 VALID 最低值作为只读诊断边界，可覆盖 7/9 Direction FP 且不触碰 17 个 VALID；
- 典型新增解释事件包括 `demo_242@41`：切点前速度参考高，但切点后持续速度明显衰减。

因此冻结：

```text
POST_MOTION_SUFFICIENCY = SUPPORTED_AS_FORMAL_RULE_COMPONENT
```

但以下内容 **未冻结**：

```text
right_speed_reference 是否为最终 operational field = NOT_FROZEN
统计量 median / mean = NOT_FROZEN
窗口 [+4,+12] = NOT_FROZEN
numeric threshold = NOT_FROZEN
```

---

## 5. Trajectory Coherence Evidence

当前分析导出中：

`Straightness Ratio｜直线性比值`

定义：

```text
straightness = net_displacement / path_length
```

并使用：

```text
min(left_straightness, right_straightness)
```

代表左右两侧较差的一侧轨迹一致性。

当前 evidence 显示：

- VALID 的 min-straightness 最低约为 0.770；
- `demo_162@211` 的 min-straightness 约 0.553；
- `demo_242@60` 的 min-straightness 约 0.748；
- 这些事件正是单纯 displacement / local speed 难以解释的高价值反例。

因此冻结：

```text
TRAJECTORY_COHERENCE = SUPPORTED_AS_FORMAL_RULE_COMPONENT
```

但以下内容 **未冻结**：

```text
straightness 是否最终采用 min(left,right) = NOT_FROZEN
path window = NOT_FROZEN
numeric threshold = NOT_FROZEN
```

---

## 6. Current Combined Diagnostic Observation

在当前 Calibration 26-event evidence 上，一个只读诊断示例：

```text
REJECT IF

right_speed_reference < 0.045 m/s

OR

min(left_straightness, right_straightness) < 0.75
```

可得到：

```text
Direction FP covered = 9 / 9
VALID rejected = 0 / 17
```

并且邻近诊断点：

```text
speed 0.045~0.050
straightness 0.75~0.76
```

也出现相同的 Calibration outcome。

**重要：这只是 Rule Discovery Diagnostic｜规则发现诊断。**

因此：

```text
0.045 = NOT_FROZEN
0.050 = NOT_FROZEN
0.75 = NOT_FROZEN
0.76 = NOT_FROZEN

9/9 + 0/17 = CALIBRATION_OBSERVATION
NOT GENERALIZATION_PROOF
```

不得直接写入 Detector config。

---

## 7. Counterexample Interpretation

### 7.1 demo_242@41

```text
FP
high displacement
local_speed_min not very low
left_speed_reference ≈ 0.184
right_speed_reference ≈ 0.0386
```

解释：

方向变化后没有形成同等级的持续新运动阶段。

Primary explanatory axis：

```text
POST_MOTION_SUFFICIENCY
```

### 7.2 demo_162@211

```text
FP
high displacement
run_length = 17
left_straightness ≈ 0.553
right_straightness ≈ 0.890
```

解释：

运动量与持续性都不弱，但一侧轨迹显著不一致，存在回摆 / detour / jitter 特征。

Primary explanatory axis：

```text
TRAJECTORY_COHERENCE
```

### 7.3 demo_255@14

```text
VALID
very low local_speed_min
but trajectory coherence is high
and post-motion continues
```

说明：

“切点瞬间速度低”本身不能作为 reject 依据。

### 7.4 demo_242@224

```text
VALID
low W=8 displacement
but post-motion persists
and trajectory remains coherent
```

说明：

“窗口净位移低”本身不能作为 hard gate。

---

## 8. Consolidation Separation

以下信息继续保持职责分离：

```text
NEAR_NEXT_GRIPPER
=
EVENT_CONSOLIDATION_CONTEXT
NOT
DIRECTION_CANDIDATE_ACCEPTANCE_HARD_GATE
```

例如：

`demo_242@136 Direction @136 → Gripper @146`

更接近同一物理事件的 Candidate Consolidation 问题。

因此：

- gripper proximity 不并入本 Rule Shape 的全局 Direction Acceptance；
- MODE_03 继续保留到 Consolidation 设计层处理。

---

## 9. Frozen Architecture After This Decision

```text
Candidate Generation
  ├─ Direction evidence
  └─ Persistence
        ↓
Candidate Acceptance
  ├─ Post-motion Sufficiency
  └─ Trajectory Coherence
        ↓
Event Consolidation
  └─ Gripper / motion event proximity
        ↓
Final Boundary
```

其中：

- Direction Evidence / Persistence 回答“几何变化是否真实存在”；
- Post-motion Sufficiency / Trajectory Coherence 回答“是否值得形成独立行为段”；
- Consolidation 回答“多个真实 candidate 是否属于同一个物理事件”。

---

## 10. Mandatory Next Step

下一步不是直接修改 Detector。

必须先执行：

```text
MOTION_SUFFICIENCY_OPERATIONALIZATION_PREPARATION
```

目标：

在不进行数值 threshold optimization 的前提下，比较一组有限、可解释的 operational definition，确认：

1. Post-motion Sufficiency 最终应该由哪个字段表达；
2. Trajectory Coherence 最终应该由哪个字段表达；
3. 固定窗口应该如何定义；
4. 是否需要修改 P1 Signal Contract；
5. 哪些定义对 Seed / Fresh / 关键 VALID counterexample 都保持一致。

完成后才能决定是否生成新的 Calibration Protocol Patch。

---

## 11. Operationalization Search Boundary

下一步允许比较的字段族必须有限：

### Post-motion Sufficiency candidates

- `post_speed_mean`（现有 Stage A0 W=8 派生字段）
- `right_speed_reference`（当前 analysis W=12 持续速度）
- 如需其它统计量，只允许来自相同 Formal translation speed，不得引入新 privileged signal。

### Trajectory Coherence candidates

- `left_straightness`
- `right_straightness`
- `min(left_straightness, right_straightness)`

允许基于已有 EEF translation 导出。

禁止：

- classifier；
- decision tree；
- 自动 feature search；
- 任意大量窗口 sweep；
- privileged simulator state；
- object pose / reward / success。

---

## 12. Frozen Non-Scope

```text
DETECTOR_MODIFIED = NO
CONFIG_GENERATED = NO
PARAMETER_SEARCH_EXECUTED = NO
NUMERIC_THRESHOLD_FROZEN = NO
WINDOW_FROZEN = NO
P1_SIGNAL_CONTRACT_MODIFIED = NO
STAGE_A_EXECUTED = NO
STAGE_B_EXECUTED = NO
INDEPENDENT_EVALUATION_EXECUTED = NO
```

---

## 13. Final Decision

```text
G1_P3_DIRECTION_RULE_SHAPE =
FROZEN_POST_MOTION_SUFFICIENCY_AND_TRAJECTORY_COHERENCE

DISPLACEMENT_ROLE =
AUXILIARY_EVIDENCE

LOCAL_SPEED_MIN_ROLE =
DIAGNOSTIC_ONLY

RELATIVE_SPEED_VALLEY_ROLE =
DIAGNOSTIC_ONLY

GRIPPER_PROXIMITY_ROLE =
CONSOLIDATION_CONTEXT

NEXT_GATE =
MOTION_SUFFICIENCY_OPERATIONALIZATION_PREPARATION
```

本文件冻结“下一步应该围绕什么物理规则设计”，而不是冻结“最终 Detector 用什么数值”。
