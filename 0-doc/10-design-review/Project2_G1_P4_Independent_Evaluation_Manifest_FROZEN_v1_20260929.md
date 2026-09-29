# Project 2 G1-P4 Independent Evaluation Manifest FROZEN v1

```text
DATE = 2026-09-29
DOCUMENT_STATUS = FROZEN_v1
FROZEN = YES
SOURCE_OF_TRUTH = GITHUB_MAIN

PARENT_PREPARATION_RESULT =
Project2_G1_P4_Evaluation_Manifest_Preparation_Result_20260927.md

PARENT_PREPARATION_COMMIT =
ab400fe8c769f1aa3afdec314675d460c5cf5944

FINAL_CALIBRATION_CONFIG =
Project2_G1_P3_Final_Calibration_Config_FROZEN_v1_20260927.md

EVALUATION_MANIFEST_VERSION = G1_P4_EVAL_MANIFEST_v1
EVALUATION_EPISODE_COUNT = 24

EVALUATION_MANIFEST_FROZEN = YES
FORMAL_EVALUATION_RUN_ALLOWED = YES

DISJOINTNESS_AUDIT = PASS
LEAKAGE_AUDIT = PASS

HUMAN_LABEL_USED_FOR_SELECTION = NO
EVALUATION_GT_USED_FOR_SELECTION = NO
FROZEN_CONFIG_SCORE_USED_FOR_SELECTION = NO
FORMAL_EVALUATION_EXECUTED_BEFORE_FREEZE = NO
HUMAN_AUDIT_STARTED_BEFORE_FREEZE = NO
```

## 1. Dataset Identity

```text
dataset_id = robomimic_v15_can_mh

demo_v15.hdf5 SHA256 =
6f5a0e96fc375468ae19ccac86a6dee3b4d3862ef0fe37ca2d02e93d9046fe6b

low_dim_v15.hdf5 SHA256 =
c4a34c837913446d295c6ca38f2b31888d69812198478af470ecb84a99e9f7d7

total_dataset_episodes = 300
eligible_evaluation_pool = 268
historical_unique_excluded = 32
unreadable_or_schema_invalid = 0
```

## 2. Frozen Selection Rule

本 Evaluation Manifest 来自 Preparation Result 中的 Medium proposal。

确定性抽样算法：

```text
DURATION_TERCILE_ROUND_ROBIN_WITHIN_STRATUM_SHA256
```

其规则为：

1. 排除所有 Exploratory / Calibration / Design Diagnostic 已使用 episode；
2. 排除技术上不可读或 schema invalid episode；
3. 按 frame_count 排序并划分 SHORT / MEDIUM / LONG terciles；
4. 每个 tercile 内按稳定 SHA256 规则排序；
5. 以 SHORT → MEDIUM → LONG round-robin 形成 nested deterministic ranking；
6. Design Owner 明确选择前 24 条 Medium proposal 作为 Independent Evaluation Set。

该选择未使用任何 Evaluation outcome。

## 3. Frozen Evaluation Episode IDs

```text
data/demo_129
data/demo_176
data/demo_91
data/demo_18
data/demo_275
data/demo_234
data/demo_3
data/demo_178
data/demo_94
data/demo_10
data/demo_224
data/demo_58
data/demo_141
data/demo_161
data/demo_262
data/demo_121
data/demo_253
data/demo_284
data/demo_20
data/demo_207
data/demo_85
data/demo_46
data/demo_238
data/demo_282
```

Summary：

```text
episode_count = 24
total_frames = 4432
total_duration_seconds = 221.6
estimated_manual_audit_workload_minutes = 55.3867
```

## 4. Disjointness Contract

Frozen manifest 已通过：

```text
OVERLAP_WITH_EXPLORATORY = 0
OVERLAP_WITH_CALIBRATION_SEED = 0
OVERLAP_WITH_CALIBRATION_FRESH = 0
OVERLAP_WITH_CALIBRATION_COMBINED = 0
OVERLAP_WITH_DESIGN_DIAGNOSTIC = 0

DISJOINTNESS_AUDIT = PASS
```

从本 Freeze 生效后，禁止把上述历史 cohort 中任何 episode 加入 Evaluation Set。

## 5. Leakage Contract

Manifest preparation 已确认：

```text
human_label_used = false
evaluation_gt_used = false
frozen_config_score_used = false
fp_fn_used = false
error_mode_used = false
result_based_cherry_pick_used = false
formal_evaluation_executed = false
human_audit_started = false

LEAKAGE_AUDIT = PASS
```

因此本 manifest 可作为 held-out evaluation｜留出独立评估集合。

## 6. Formal Evaluation Permission

Design Owner 已明确选择 Medium 24 条，因此：

```text
EVALUATION_MANIFEST_FROZEN = YES
FORMAL_EVALUATION_RUN_ALLOWED = YES
```

下一步允许：

```text
Frozen Config
→ 24 frozen Evaluation episodes
→ Formal EVALUATION run
→ Audit Package / Web
→ Human Evaluation Audit
→ Canonical Evaluation GT
→ Formal scoring
→ Design Owner G1 Evaluation Review
```

## 7. Prohibited After Freeze

禁止：

```text
change evaluation episode IDs
replace a difficult episode
drop a failed episode
add an easy episode
change frozen G1 config
change matching tolerance
use evaluation outcome for tuning
reuse calibration GT
silently redefine error taxonomy
```

如果 Evaluation 暴露失败，只允许记录：

```text
EVALUATION_FAILURE_CASE
→ future Design Change Request
```

不得在本 v1 Evaluation Set 上调参后重跑并继续声称为第一次独立评估。

## 8. Gate Status

```text
G1_CALIBRATION_CONFIG = FROZEN_v1
G1_P4_EVALUATION_MANIFEST = FROZEN_v1
FORMAL_EVALUATION_RUN_ALLOWED = YES

NEXT_GATE =
P2_S1D_FORMAL_EVALUATION_AUDIT_RUN_AND_HUMAN_REVIEW
```
