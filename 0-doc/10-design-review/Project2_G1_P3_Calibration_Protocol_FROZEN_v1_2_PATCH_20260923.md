# Project 2 G1-P3 Calibration Protocol FROZEN v1.2 PATCH

```text
DATE = 2026-09-23
DOCUMENT_STATUS = FROZEN_v1.2
FROZEN = YES
PATCH_TYPE = ADDITIVE_CALIBRATION_SEARCH_PROTOCOL_UPDATE
BASE_PROTOCOL = Project2_G1_P3_Calibration_Protocol_FROZEN_v1_20260917.md
PRIOR_PATCH = Project2_G1_P3_Calibration_Protocol_FROZEN_v1_1_PATCH_20260918.md
SOURCE_OF_TRUTH = GITHUB_MAIN
EVIDENCE_AUTHORITY_HEAD = 6a1faca6169452032ae70d967def864254d2b4d4

DETECTOR_MODIFIED = NO
CONFIG_GENERATED = NO
PARAMETER_SEARCH_EXECUTED = NO
NUMERIC_THRESHOLD_FROZEN = NO
CALIBRATION_GT_CHANGED = NO
EVALUATION_TOUCHED = NO
```

本补丁冻结 **Calibration Search｜校准搜索** 的下一阶段协议，不修改 Detector，也不在本文中选择任何数值阈值。

除本文明确覆盖的 Stage A search surface、P12/C12 operationalization、lookahead / edge policy 与下一实现 Gate 外，v1.0/v1.1 的以下契约继续有效：

- Canonical Human GT；
- ±3 frames one-to-one matching；
- 12-Episode Calibration Set；
- Seed / Fresh provenance；
- HARD guardrails；
- Stage B consolidation 边界；
- Stage C regression；
- Config Selection / Stop Rule；
- Calibration / Independent Evaluation 隔离；
- v1.1 Human Calibration Export identity。

---

## 1. Evidence Basis

本补丁只使用已经冻结到 GitHub 的证据：

1. `Project2_G1_P3_Stage_A0_Direction_Discriminability_Result_20260918.md`；
2. `Project2_G1_P3_Motion_Sufficiency_Rule_Shape_FROZEN_v1_20260921.md`；
3. `Project2_G1_P3_Motion_Sufficiency_Operationalization_Preparation_Result_20260921.md`；
4. `Project2_G1_P3_Trajectory_Mechanism_Validation_Design_FROZEN_v1_20260921.md`；
5. `g1_p3_trajectory_mechanism_validation/05_owner_adjudication_result.md`；
6. `g1_p3_trajectory_mechanism_validation/05_review_history.csv`。

必须同时保留两套 diagnostic readout：

```text
FIRST_BLINDED_RESULT
LOW C12 = 1/10 REDUNDANT
HIGH C12 = 1/10 REDUNDANT
BLINDED_GATE = NOT_SUPPORTED_AS_GENERAL_ACCEPTANCE_COMPONENT

OWNER_ADJUDICATED_RESULT
LOW C12 = 4/10 REDUNDANT
HIGH C12 = 0/10 REDUNDANT
OWNER_ADJUDICATED_GATE = SUPPORTED_FOR_PROTOCOL_PATCH_REVIEW
```

因此本补丁**不允许**声称 C12 已被独立盲审验证或泛化证明。

---

## 2. Superseded Stage A Route

v1.0 的 Stage A 主搜索轴：

```text
direction_change_threshold
×
direction_persistence_frames
```

在 Stage A0 及后续分析中已显示 VALID / FP 大量重叠，不能形成稳定、可解释的 Candidate Acceptance。

因此冻结：

```text
DIRECTION_THRESHOLD_ONLY_PRIMARY_ROUTE = REJECTED
PERSISTENCE_ONLY_PRIMARY_ROUTE = REJECTED
THRESHOLD_X_PERSISTENCE_PRIMARY_ROUTE = REJECTED

V1_2_DIRECTION_GENERATION_POLICY =
KEEP_BASELINE_GENERATION_FIXED_DURING_STAGE_A1_A2
```

含义：

- 当前 baseline 的 Direction evidence / persistence 继续负责 **Candidate Generation｜候选生成**；
- v1.2 Stage A1/A2 不再把 direction threshold / persistence 当作主要调参轴；
- 如未来要重新改变 Candidate Generation，必须另开 Design Change Request，不得混进本轮 Candidate Acceptance 校准。

---

## 3. Frozen Candidate Acceptance Architecture

```text
Direction Candidate Generation
  ├─ existing direction evidence
  └─ existing persistence
        ↓
Candidate Acceptance
  ├─ Stage A1: P12 Post-motion Sufficiency
  └─ Stage A2: optional Conditional C12 Tail Guard
        ↓
Event Consolidation
        ↓
Final Boundary
```

中文：

- Candidate Generation 回答“方向变化是否真实出现”；
- P12 回答“变化后是否形成持续的新运动阶段”；
- C12 只作为可选的尾部保护，检查“明显回摆 / 绕行 / jitter”是否能在 P12 之外提供增量价值；
- Consolidation 继续处理 Gripper / motion 事件邻近关系。

---

## 4. P12 Formal Calibration Component

### 4.1 Operational definition

本轮 v1.2 Calibration Search 固定：

```text
P12 =
median(translation_speed_mps)
over relative_frame [+4,+12]
```

其中 20 Hz 下：

```text
+4  = +0.20 s
+12 = +0.60 s
```

冻结：

```text
P12_ROLE = FORMAL_CALIBRATION_SEARCH_COMPONENT
P12_STATISTIC_FOR_V1_2 = MEDIAN
P12_WINDOW_FOR_V1_2 = [+4,+12]
P12_THRESHOLD = DATA_CALIBRATION_PENDING
```

这表示 operational definition 在 v1.2 搜索中固定，不表示 numeric threshold 已冻结。

P12 来自既有 Formal translation speed，不修改 P1 Base Signal Contract。

---

## 5. C12 Conditional Strategy Candidate

### 5.1 Operational definition

v1.2 允许的 C12 定义固定为：

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

冻结：

```text
C12_ROLE = CONDITIONAL_STRATEGY_CANDIDATE
C12_UNCONDITIONAL_HARD_GATE = FORBIDDEN
C12_WINDOW_SWEEP = FORBIDDEN
C12_THRESHOLD = DATA_CALIBRATION_PENDING
C12_GENERALIZATION_PROVEN = NO
BLINDED_VALIDATION_SUPPORTED = NO
```

中文：

C12 可以进入 Calibration 对照，但不能因为 Owner 解盲后的 4/10 vs 0/10 结果直接成为默认 hard reject 条件。

---

## 6. Diagnostic Set Isolation

20-event Design Diagnostic Set 永久保持：

```text
MUST_NOT_ENTER_CALIBRATION_GT = YES
MUST_NOT_ENTER_EVALUATION_GT = YES
MUST_NOT_BE_USED_FOR_THRESHOLD_SELECTION = YES
```

因此：

- `02_selection_internal.csv` 中的 P12/C12 数值不得参与 threshold 选取；
- `05_review_history.csv` 的 human labels 不得加入 12-Episode Calibration GT；
- 不允许用这 20 条反复挑选 P12/C12 阈值；
- 该集合只允许作为 mechanism / design evidence 与已冻结 provenance。

---

## 7. Stage A1 — P12-only Calibration

正式第一阶段：

```text
STAGE_A1 =
P12_ONLY_CANDIDATE_ACCEPTANCE
```

规则形状：

```text
KEEP independent Direction candidate
IF P12 >= tau_P12

REJECT
IF P12 < tau_P12
```

其中：

```text
tau_P12 = selected only from 12-Episode Calibration GT
```

### 7.1 Threshold candidate construction

禁止使用 Diagnostic Set 中的 0.045 / 0.050 或其它观察值作为正式阈值。

v1.2 使用确定、有限的 **Breakpoint Search｜断点搜索**：

1. 在 12-Episode Calibration GT 对应的 eligible independent Direction cohort 上计算 P12；
2. 对排序后的 unique P12 值，只在相邻值中点以及 no-gate baseline 处形成候选；
3. 每个候选完整重跑 scoring + guardrail；
4. 不做任意 dense sweep，不使用 optimizer。

这等价于搜索所有可能改变该有限 Calibration cohort 分类结果的有效断点，同时避免人为拍摄连续网格。

---

## 8. Stage A2 — P12 + Conditional C12 Tail Guard

只有 Stage A1 已得到至少一个 HARD guardrail 全通过的 P12 候选后，才允许进入：

```text
STAGE_A2 =
P12_PLUS_CONDITIONAL_C12
```

规则形状：

```text
KEEP
IF P12 >= tau_P12
AND C12 >= tau_C12
```

但 C12 必须满足 **Incremental Promotion Gate｜增量晋级门禁**。

### 8.1 C12 threshold candidates

`tau_C12` 只能从同一 12-Episode Calibration cohort 的 C12 unique-value breakpoints 构造。

禁止：

- 从 20-event Diagnostic Set 取 0.75 / 0.76 等阈值；
- 大量 window sweep；
- P12 × C12 × direction threshold × persistence 全组合网格。

### 8.2 C12 promotion gate

P12+C12 只有同时满足以下条件，C12 才能进入最终 Config 候选：

```text
1. ALL_HARD_GUARDRAILS = PASS

2. NEW_FN <= P12_ONLY_NEW_FN

3. DIRECTION_FP_REMAINING
   < selected P12-only candidate

4. improvement is not SEED_ONLY
   Fresh Calibration must show non-regression
   and the gain may not be explained only by Seed memorization

5. If P12-only and P12+C12 are equivalent
   → choose P12-only
```

即：

```text
SIMPLICITY_TIE_BREAK = P12_ONLY
```

C12 必须证明“在 P12 之外有增量价值”，不能因为机制看起来合理就自动进入 Detector。

---

## 9. Guardrails

继续继承 v1.0：

```text
CALIBRATION_GRIPPER_RECALL HARD = 1.0
CALIBRATION_MERGED_CLUSTER_RECALL HARD = 1.0
SEED_VALID_DIRECTION_RECALL HARD = 1.0
FRESH_VALID_DIRECTION_RECALL HARD = NON_REGRESSION_VS_BASELINE
FN_new <= FN_baseline HARD
```

所有 Stage A1/A2 config 先过 guardrail，再比较 FP / F1。

Config selection 在 HARD guardrail 通过后按：

```text
L1 minimize known Direction FP remaining
L2 minimize total FP
L3 higher Boundary F1
L4 lower localization p90
L5 simpler rule / fewer acceptance components
```

其中 L5 明确保证：

若 P12-only 与 P12+C12 实质等价，选择 P12-only。

---

## 10. Bounded Lookahead

Project 2 当前 G1 是离线 dataset segmentation，因此允许有限未来上下文。

冻结：

```text
OFFLINE_BOUNDED_LOOKAHEAD = ALLOWED
MAX_ACCEPTANCE_LOOKAHEAD_FRAMES = 12
MAX_ACCEPTANCE_LOOKAHEAD_SECONDS = 0.60 @ 20Hz

P12_RIGHT_LOOKAHEAD = +12
C12_RIGHT_LOOKAHEAD = +11
BOUNDARY_FRAME_SHIFT_DUE_TO_LOOKAHEAD = FORBIDDEN
```

lookahead 只用于决定 candidate 是否保留，Final Boundary frame 仍保持原 candidate / representative frame。

若未来把 G1 迁移为 online / causal segmentation，本协议不自动适用，必须另开设计。

---

## 11. Episode Edge Policy

禁止用缩短窗口伪装成完整 P12/C12。

冻结为 **Fail-open Edge Policy｜边缘缺上下文时保守保留**：

```text
IF P12 context [+4,+12] incomplete:
    do not reject by P12
    keep baseline candidate
    flag P12_CONTEXT_INCOMPLETE

IF P12 complete but C12 left/right context incomplete:
    apply P12 decision only
    do not reject by C12
    flag C12_CONTEXT_INCOMPLETE
```

因此：

```text
EDGE_CONTEXT_INCOMPLETE != AUTOMATIC_REJECT
SHORTENED_WINDOW_SUBSTITUTION = FORBIDDEN
```

这优先保护 Recall，并让 edge case 在 Stage C / Evaluation 中可单独审计。

---

## 12. Stage B / Stage C

v1.0 的 Stage B/C 继续有效，仅调整前置输入为通过 Stage A1/A2 的候选 acceptance config。

### Stage B — Limited Consolidation

只有当：

- Stage A acceptance 已稳定；
- HARD guardrail 全绿；
- MODE_03 / consolidation error 仍值得处理；

才比较：

```text
boundary_consolidation_window ∈ {8,10,12}
```

不与 P12/C12 组成大网格。

### Stage C — Regression Only

不新增搜索轴，只复核：

```text
Seed guardrails
Fresh non-regression
NEW_FN
NEW_UNANCHORED_FP
fragmentation
Localization
edge-context flags
```

---

## 13. Required Implementation Trace

下一实现必须对每个 independent Direction candidate 可追溯输出：

```text
candidate_id / boundary lineage
P12
P12_context_complete
C12
C12_context_complete
acceptance_variant
tau_P12
tau_C12 (nullable for P12-only)
acceptance_decision
acceptance_reason
config_hash
```

要求：

- P12/C12 都由已有 Formal translation signals 派生；
- 不读取 object pose / reward / done / success；
- 不读取 20-event Diagnostic human labels；
- 不修改 Canonical GT。

---

## 14. Next Implementation Gate

本协议冻结后，下一步只允许：

```text
STAGE_A1_A2_CALIBRATION_IMPLEMENTATION
```

严格顺序：

```text
1. 实现 P12/C12 derived acceptance context + trace
2. 锁定 baseline Direction Candidate Generation
3. 在 12-Episode Calibration GT 上生成 P12 breakpoint candidates
4. 跑 Stage A1 P12-only
5. 保留 HARD guardrail 全通过的候选
6. 对 surviving P12 candidates 做 Stage A2 conditional C12 breakpoint comparison
7. 执行 C12 Incremental Promotion Gate
8. 输出候选 config comparison
9. STOP / Design Owner 选最终 config
```

本轮实现结束时仍然：

```text
CALIBRATION_CONFIG_FROZEN = NO
```

直到 Design Owner 明确选定。

---

## 15. Prohibited in Next Implementation

```text
NO EVALUATION SET USE
NO DIAGNOSTIC_SET_THRESHOLD_SELECTION
NO CANONICAL_GT CHANGE
NO HUMAN_REVIEW REWRITE
NO DIRECTION_THRESHOLD_X_PERSISTENCE RESWEEP
NO P1 SIGNAL WINDOW CHANGE
NO C12 WINDOW SWEEP
NO CLASSIFIER
NO AUTO FEATURE SEARCH
NO PRIVILEGED SIMULATOR STATE
NO SILENT CONFIG FREEZE
```

---

## 16. Effective Authority

```text
CALIBRATION_PROTOCOL_EFFECTIVE_VERSION = FROZEN_v1.2

STAGE_A =
A1 P12_ONLY
→ A2 P12_PLUS_CONDITIONAL_C12

P12_ROLE =
FORMAL_CALIBRATION_SEARCH_COMPONENT

C12_ROLE =
CONDITIONAL_STRATEGY_CANDIDATE

DIAGNOSTIC_SET_ROLE =
MECHANISM_EVIDENCE_ONLY

NEXT_GATE =
STAGE_A1_A2_CALIBRATION_IMPLEMENTATION
```

若 v1.0/v1.1 与本文在 Stage A Search Surface 上冲突，以 v1.2 为准；其它未覆盖条款继续沿用原协议。
