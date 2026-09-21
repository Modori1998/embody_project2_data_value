# Project 2 G1-P3 Trajectory Mechanism Validation Design FROZEN v1

```text
DATE = 2026-09-21
DOCUMENT_STATUS = FROZEN_VALIDATION_DESIGN_v1
FROZEN = YES
TASK = TARGETED_TRAJECTORY_MECHANISM_VALIDATION
SOURCE_OF_TRUTH = GITHUB_MAIN
BASELINE_AUTHORITY_HEAD = 7d2fbd79bc24309301abf602bd3c768fcffadf16

DETECTOR_MODIFIED = NO
CONFIG_GENERATED = NO
NUMERIC_THRESHOLD_FROZEN = NO
PROTOCOL_PATCH_CREATED = NO
CALIBRATION_SET_EXPANDED = NO
EVALUATION_SET_TOUCHED = NO
```

本文件冻结的是 **Trajectory Mechanism Validation｜轨迹机制验证** 的实验设计。

目标不是继续搜索 feature，也不是把 C12 直接写进 Detector，而是只回答：

> 在未参与既有 Rule Discovery / Calibration 的新 episode 中，  
> 当 **Post-motion Sufficiency｜后段运动充分性** 已经较高时，  
> **较低 Trajectory Coherence｜轨迹一致性** 是否确实更容易对应人工判定的冗余 Direction Boundary？

---

## 1. Why This Validation Is Required

当前已冻结：

```text
G1_P3_DIRECTION_RULE_SHAPE =
POST_MOTION_SUFFICIENCY
+
TRAJECTORY_COHERENCE
```

Operationalization preparation 已得到：

```text
P12 = preferred post-motion candidate
C12 = promising but not yet frozen
Pair12 on current calibration cohort =
9 / 9 Direction FP explained
0 / 17 VALID rejected
```

但仍存在三项关键限制：

1. Pair12 的全部 W12 增量来自同一 episode：`demo_242`；
2. Fresh Direction FP 只有 2 条；
3. C8 / C12 在 SEED 的 median 层面出现方向反转，说明 trajectory coherence 不是“所有 FP 普遍更低”的主分离轴，而更像少数错误机制的 tail condition。

因此：

```text
C12_OPERATIONALIZATION = NOT_FROZEN
CALIBRATION_PROTOCOL_PATCH = NOT_READY
```

---

## 2. Validation Question

本轮唯一主问题：

```text
CONDITIONAL_TRAJECTORY_QUESTION
=
Among new independent Direction candidates with sufficient post-motion,
does low trajectory coherence enrich human-reviewed REDUNDANT boundaries?
```

中文：

> 在后续运动已经足够持续的前提下，轨迹一致性差，是否真的更容易代表“回摆 / 绕动 / jitter / detour 导致的不应独立切段”？

本轮不验证：

- P12 numeric threshold；
- C12 numeric threshold；
- 最终 Detector F1；
- 最终 calibration threshold；
- Event Consolidation；
- Gripper proximity rule。

---

## 3. Dataset Role

新样本必须单独定义为：

```text
DATASET_ROLE = DESIGN_DIAGNOSTIC_SET
```

**Design Diagnostic Set｜设计诊断集**

中文解释：

只用于验证一个设计机制是否值得继续，不允许用于最终 threshold calibration，也不允许充当 Independent Evaluation。

必须满足：

```text
MUST_NOT_ENTER_CALIBRATION_GT = YES
MUST_NOT_ENTER_EVALUATION_GT = YES
MUST_NOT_BE_USED_FOR_THRESHOLD_SELECTION = YES
```

既有 12 个 Calibration episode 必须全部排除。

不得重新使用：

Seed calibration episodes

```text
demo_0
demo_32
demo_179
demo_230
demo_242
demo_278
```

Fresh calibration episodes

```text
demo_150
demo_162
demo_213
demo_255
demo_260
demo_270
```

若 GitHub SSOT 中 episode naming / set membership 有更新，以最新 authoritative artifact 为准；不得硬覆盖 SSOT。

---

## 4. Candidate Pool

候选池只允许来自：

```text
independent Direction Final Boundary
```

必须：

- 来自未参与现有 Calibration 的 episode；
- 使用当前 baseline segmentation / candidate lineage；
- 不读 Web SQLite 作为 candidate source；
- 不使用 privileged simulator state；
- 不修改 baseline detector。

排除：

- Gripper-primary merged Final Boundary；
- 非 Direction boundary；
- 已进入现有 Calibration 的 event；
- 已人工审核并用于 Rule Discovery 的 event。

为了隔离 Candidate Acceptance 与 Event Consolidation，额外排除明显 near-gripper consolidation context：

```text
distance_to_nearest_gripper_final <= 12 frames
```

该排除只用于本次 trajectory mechanism isolation，不冻结为 Detector rule。

---

## 5. Allowed Signals

只允许：

- EEF translation；
- translation speed；
- existing Direction evidence；
- existing run_length / persistence；
- P12；
- C12；
- baseline lineage metadata。

禁止：

- object pose；
- reward；
- success；
- done；
- privileged contact；
- task completion；
- new acceleration / jerk / curvature family；
- new action / rotation feature family；
- classifier embedding。

---

## 6. Frozen Operational Definitions For This Diagnostic Only

本次 diagnostic 暂时固定使用：

### P12 — Sustained Post-motion Context｜持续后段运动上下文

```text
P12 =
median(translation_speed_mps)
over relative_frame [+4,+12]
```

用途：

仅用于控制“后续运动已经足够持续”这一前提。

### C12 — Trajectory Coherence｜轨迹一致性

```text
left_straightness =
left_net_displacement / left_path_length
over relative_frame [-12,-1]

right_straightness =
right_net_displacement / right_path_length
over relative_frame [0,+11]

C12 =
min(left_straightness, right_straightness)
```

用途：

只验证 trajectory mechanism。

重要：

```text
P12_DETECTOR_DEFINITION_FROZEN = NO
C12_DETECTOR_DEFINITION_FROZEN = NO
WINDOW_FROZEN_AS_FINAL_CONFIG = NO
```

本轮只是为了让新样本选择规则固定、可复现。

---

## 7. Rank-based Selection — No Calibration Threshold

本轮禁止使用现有 Calibration 中的：

```text
0.045
0.050
0.75
0.76
VALID_FLOOR
```

来筛选新样本。

新样本必须使用**无标签的 rank-based selection｜基于排序的选样**，避免把 Calibration threshold 偷渡进新诊断集。

---

## 8. P12 Eligibility

在全部 eligible candidate pool 中：

按 P12 从高到低排序。

定义：

```text
P12_ELIGIBLE_POOL =
top 50% by P12 rank
```

中文解释：

只保留后段运动相对充足的一半 candidate。

这是 selection percentile，不是 Detector threshold。

---

## 9. Two Diagnostic Arms

在 P12_ELIGIBLE_POOL 内：

### Arm A — Low Coherence Target｜低轨迹一致性目标组

按 C12 从低到高排序。

候选来自：

```text
bottom 25% of C12 rank
```

目标：

找“后段运动持续，但轨迹明显不连贯”的候选。

### Arm B — High Coherence Control｜高轨迹一致性对照组

候选来自：

```text
top 25% of C12 rank
```

目标：

找“后段运动持续，且轨迹也连贯”的 Direction candidates 作为对照。

---

## 10. Matching

Arm B 不是随便挑高 C12。

每个 Arm A event 必须匹配一个 Arm B event。

Matching variables：

```text
P12 rank percentile
Direction evidence rank percentile
run_length rank percentile
```

匹配距离：

```text
MATCH_DISTANCE =
|Δ P12 percentile|
+
|Δ evidence percentile|
+
|Δ run_length percentile|
```

对每个 Arm A event：

选择当前未使用的 Arm B candidate 中 MATCH_DISTANCE 最小者。

tie-break：

```text
episode_id ASC
event_frame ASC
```

禁止使用 human label 参与匹配。

---

## 11. Episode Diversity

目标样本量：

```text
TARGET_PER_ARM = 10
TARGET_TOTAL = 20
```

允许范围：

```text
8 <= N_PER_ARM <= 12
```

Hard diversity rules：

```text
MAX_SELECTED_EVENTS_PER_EPISODE = 1
NO_EPISODE_SHARED_BETWEEN_ARMS = YES
```

因此目标 20 个 event 应尽量来自 20 个不同 episode。

若无法满足至少：

```text
MIN_PER_ARM = 8
```

则：

```text
VALIDATION_SET_BUILD = INSUFFICIENT_DIVERSITY
```

并 STOP。

---

## 12. Review Blinding

人工审核时必须隐藏：

- Arm A / Arm B；
- P12；
- C12；
- selection rank；
- expected hypothesis。

Reviewer 只看到正常 G1 Human Audit 所需内容。

允许 label：

```text
VALID
REDUNDANT
MISALIGNED
```

如果 REDUNDANT：

继续使用既有 reason taxonomy。

不得新增“LOW_C12”之类会泄露假设的人工标签。

---

## 13. Review SSOT

新 Diagnostic review 必须：

- 建独立 run_id；
- 明确 `run_stage = DESIGN_DIAGNOSTIC` 或等价不可混淆 stage；
- review 仍走 append-only Web review；
- 最终导出 immutable diagnostic export；
- 不允许把 diagnostic review 写回现有 Calibration GT。

---

## 14. Primary Readout

人工审核完成后只比较：

```text
REDUNDANT_RATE_ARM_A
vs
REDUNDANT_RATE_ARM_B
```

其中：

```text
REDUNDANT_RATE =
REDUNDANT / reviewed events
```

MISALIGNED 单独报告，不偷偷算成 REDUNDANT。

同时报告：

- distinct episode count；
- redundant event episode count；
- reason-code distribution；
- Seed/Fresh 不适用，新集统一记 `DESIGN_DIAGNOSTIC`。

---

## 15. Frozen Diagnostic Gate

本轮预先冻结以下判定，避免审核后再改口径。

### SUPPORTED

必须同时满足：

```text
N_ARM_A >= 8
N_ARM_B >= 8

REDUNDANT_RATE_ARM_A
>= 2.0 * REDUNDANT_RATE_ARM_B

AND

REDUNDANT_RATE_ARM_A - REDUNDANT_RATE_ARM_B
>= 0.25

AND

ARM_A_REDUNDANT_DISTINCT_EPISODES >= 3
```

则：

```text
TRAJECTORY_MECHANISM_VALIDATION =
SUPPORTED_FOR_PROTOCOL_PATCH_REVIEW
```

注意：

这仍然不是最终 generalization proof。

### MIXED

存在 Arm A enrichment，但未满足全部 SUPPORTED 条件：

```text
TRAJECTORY_MECHANISM_VALIDATION =
MIXED_NEEDS_OWNER_REVIEW
```

### NOT_SUPPORTED

若：

```text
REDUNDANT_RATE_ARM_A <= REDUNDANT_RATE_ARM_B
```

则：

```text
TRAJECTORY_MECHANISM_VALIDATION =
NOT_SUPPORTED_AS_GENERAL_ACCEPTANCE_COMPONENT
```

### INSUFFICIENT

样本量 / episode diversity / review completeness 不满足要求：

```text
TRAJECTORY_MECHANISM_VALIDATION =
INSUFFICIENT_DIAGNOSTIC_EVIDENCE
```

---

## 16. Interpretation Boundary

即使 SUPPORTED，也只能说明：

> 低 C12 在“P12 较高的新 Direction candidates”中能富集人工 REDUNDANT。

不得声称：

- C12 threshold 已确定；
- C12 是所有 Direction FP 的主特征；
- Pair12 已泛化；
- 最终 Detector 已验证；
- Independent Evaluation 已通过。

---

## 17. Expected Next Gate

若结果：

```text
SUPPORTED_FOR_PROTOCOL_PATCH_REVIEW
```

下一步才允许讨论：

```text
Calibration Protocol v1.2 Patch
```

并在 patch 中决定：

- P12 是否作为正式 post-motion context；
- C12 是否作为 conditional tail guard；
- threshold calibration search surface；
- bounded lookahead；
- episode edge clipping。

若：

```text
NOT_SUPPORTED_AS_GENERAL_ACCEPTANCE_COMPONENT
```

则：

- C12 降级为 diagnostic/supporting evidence；
- 不进入通用 Candidate Acceptance；
- P12 仍可单独继续后续 Design Review。

---

## 18. Non-scope

本轮禁止：

```text
NO DETECTOR MODIFICATION
NO CONFIG GENERATION
NO NUMERIC THRESHOLD SEARCH
NO CALIBRATION SET EXPANSION
NO EVALUATION SET USE
NO CLASSIFIER
NO AUTO FEATURE SEARCH
NO PROTOCOL PATCH CREATION
NO MASTER / ROADMAP UPDATE
```

---

## 19. Final Frozen State

```text
TRAJECTORY_VALIDATION_DESIGN =
FROZEN_TARGETED_MATCHED_DIAGNOSTIC_V1

DATASET_ROLE =
DESIGN_DIAGNOSTIC_SET

PRIMARY_HYPOTHESIS =
LOW_C12_ENRICHES_REDUNDANT_GIVEN_HIGH_P12

SELECTION =
RANK_BASED_BLINDED_MATCHED

TARGET =
10 + 10 EVENTS

NEXT =
BUILD_DIAGNOSTIC_SET_ONLY
```
