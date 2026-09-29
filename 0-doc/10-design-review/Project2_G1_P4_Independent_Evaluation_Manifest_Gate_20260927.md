# Project 2 G1-P4 Independent Evaluation Manifest Gate

```text
DATE = 2026-09-27
DOCUMENT_STATUS = RESOLVED_BY_FROZEN_MANIFEST_v1
SOURCE_OF_TRUTH = GITHUB_MAIN

FINAL_CALIBRATION_CONFIG = FROZEN_v1
CALIBRATION_CONFIG_FROZEN = YES

EVALUATION_MANIFEST_FROZEN = YES
FORMAL_EVALUATION_RUN_ALLOWED = YES

NEXT_GATE =
P2_S1D_FORMAL_EVALUATION_AUDIT_RUN_AND_HUMAN_REVIEW
```

## 1. Why this Gate exists

Frozen Calibration Protocol v1 已明确：

```text
EVALUATION_SET_POLICY = DISJOINT_FROM_EXPLORATORY_AND_CALIBRATION
```

并且：

```text
本 Protocol 不冻结 Evaluation Episode 数量与具体 ID
```

同时 Independent Evaluation 只能在 Config Freeze 后首次正式运行。

因此 Final Calibration Config 已冻结后，下一步不是由 Implementation 层自行挑 episode 并直接跑 Evaluation，而是先生成一个只含 provenance / episode identity 的候选 Evaluation Manifest，交由 Design Owner 冻结。

## 2. Manifest preparation constraints

候选 episode 必须：

```text
DISJOINT_FROM_EXPLORATORY = YES
DISJOINT_FROM_CALIBRATION_SEED = YES
DISJOINT_FROM_CALIBRATION_FRESH = YES
DISJOINT_FROM_20_EVENT_DESIGN_DIAGNOSTIC = YES
```

准备 Manifest 时禁止查看或使用：

```text
Human Evaluation labels
Canonical Evaluation GT
Frozen-config Evaluation Precision/Recall/F1
FP/FN
error-mode outcome
任何基于正式 Evaluation 输出的“挑样本”
```

允许用于候选池事实检查的只能是：

- source episode ID；
- dataset provenance；
- episode 是否可读；
- frame count / duration；
- 现有非标签 metadata；
- 是否与历史已用 episode 重叠。

## 3. Owner decision required

Implementation 层可以：

```text
DISCOVER_ELIGIBLE_POOL = YES
PROPOSE_MANIFEST_CANDIDATES = YES
AUDIT_DISJOINTNESS = YES
```

Implementation 层不可以：

```text
FREEZE_EVALUATION_IDS = NO
RUN_FORMAL_EVALUATION = NO
BUILD_EVALUATION_GT = NO
START_HUMAN_REVIEW = NO
```

必须由 Design Owner 冻结：

```text
EVALUATION_EPISODE_COUNT
EVALUATION_EPISODE_IDS
MANIFEST_VERSION
PROVENANCE
```

之后才能打开：

```text
FORMAL_EVALUATION_RUN_ALLOWED = YES
```

## 4. Frozen config remains unchanged

本 Gate 不修改 Final Calibration Config：

```text
A1-007-C002

tau_P12 = 0.04758563666765155
tau_C12 = 0.690169167642685
boundary_consolidation_window = 8

P12 incomplete = FAIL_OPEN_KEEP
C12 incomplete = P12_ONLY_FALLBACK
```

任何 Evaluation Manifest 设计都不得回头改这些值。

## 5. Next step

```text
1. Pull latest GitHub main
2. Read this Gate + Final Config Freeze + Frozen Protocol
3. Discover eligible evaluation episode pool
4. Prove disjointness from all historical non-evaluation cohorts
5. Produce candidate manifest proposal + provenance only
6. STOP
7. Design Owner freezes count + IDs
8. Only then run Independent Evaluation
```


## 6. Gate Resolution — 2026-09-29

Design Owner selected the deterministic Medium proposal (24 episodes).

Authority:

```text
Project2_G1_P4_Independent_Evaluation_Manifest_FROZEN_v1_20260929.md
Project2_G1_P4_Independent_Evaluation_Manifest_FROZEN_v1_20260929.csv
```

```text
EVALUATION_EPISODE_COUNT = 24
EVALUATION_MANIFEST_FROZEN = YES
FORMAL_EVALUATION_RUN_ALLOWED = YES
```
