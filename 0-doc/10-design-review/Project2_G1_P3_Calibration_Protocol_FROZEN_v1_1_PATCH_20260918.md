# Project 2 G1-P3 Calibration Protocol FROZEN v1.1 PATCH

```text
DATE = 2026-09-18
DOCUMENT_STATUS = FROZEN_v1.1
FROZEN = YES
PATCH_TYPE = ADDITIVE_CONTRACT_CLARIFICATION
BASE_PROTOCOL = Project2_G1_P3_Calibration_Protocol_FROZEN_v1_20260917.md
BASE_PROTOCOL_STATUS = FROZEN_v1.0
OWNER_REVIEW = PASS
SCOPE = P2_G1_HUMAN_CALIBRATION_EXPORT_V1 PACKAGE-B EXPORT IDENTITY ONLY
DRIVE_FILE_ID = 1Irqgq6gsN4SegnAgZfDx_Apg32oUjv-b
```

本文件是 v1.0 的最小冻结补丁。除本文明确覆盖的 Human Calibration Export 身份契约外，v1.0 的 matching、tolerance、Canonical GT、Calibration Set、guardrail、Search Gate、Stage A0/A/B/C、Evaluation 隔离等全部继续有效。

## 1. Owner Decision

Package B 的正式 Export role 冻结为：

```text
FRESH_PACKAGE_B_INTENDED_ROLE = CALIBRATION
```

不新增 `CALIBRATION_FRESH`、`FRESH_CALIBRATION`、`PACKAGE_B` 等新枚举。Fresh 身份由 source provenance 表达。

## 2. Export Contract

```text
EXPORT_CONTRACT = P2_G1_HUMAN_CALIBRATION_EXPORT_V1
```

P3 只读取 versioned immutable Export，禁止直接读取 Web SQLite。

## 3. Legal Source → intended_role Mapping

### Package A — Exploratory Seed

```text
source_run_stage = EXPLORATORY_AUDIT
source_set_role = EXPLORATORY
intended_role = CALIBRATION_SEED
must_not_feed_evaluation = true
```

### Package B — Fresh Calibration

```text
source_run_stage = CALIBRATION
source_set_role = CALIBRATION
calibration_role = BASELINE_HUMAN_AUDIT
calibration_config_role = BASELINE_UNMODIFIED
intended_role = CALIBRATION
must_not_feed_evaluation = true
```

只有 Human Review 完整、schema 合法、source run validator PASS 时允许 Export。

Implementation 不得把 CALIBRATION source 伪装成 EXPLORATORY_AUDIT，也不得把 Fresh Calibration 伪装成 CALIBRATION_SEED。

## 4. Current Formal Package-B Source

```text
source_run_id = g1_calibration_20260918_094455_df2ce8b2
run_stage = CALIBRATION
set_role = CALIBRATION
calibration_role = BASELINE_HUMAN_AUDIT
calibration_config_role = BASELINE_UNMODIFIED
config_hash = dde590e759a31cb8c865369e18256ebecbbd01bc94a58e1d3ca695bb50f2a630
signal_contract_hash = 24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d

P1 = 36 / 36 PASS
P2 = 35 / 35 REVIEWED
VALID = 32
REDUNDANT = 3
MISALIGNED = 0
HUMAN_ADDED = 0
```

该 run 是本轮 Fresh Package B Export 的正式 source。

`g1_calibration_20260917_222604_d4425fc3` 保留作为 lineage，但不是 Human Review Source；不得迁移、复制或 rebind review。

## 5. Readiness Contract

```text
review_ready = Human Review completeness + schema validity
export_eligible = source identity + intended_role 符合本 v1.1 Contract
effective_export_ready = review_ready AND export_eligible
```

用户可见 Export Ready 必须等价于 `effective_export_ready`。

## 6. Fresh Export Expected Readback

```text
signal_review rows = 36
PASS = 36

predicted_boundary_review rows = 35
VALID = 32
REDUNDANT = 3
MISALIGNED = 0

human_added_boundary rows = 0
```

Export meta 必须保留真实 provenance，至少：

```text
source_run_id = g1_calibration_20260918_094455_df2ce8b2
source_run_stage = CALIBRATION
source_set_role = CALIBRATION
calibration_role = BASELINE_HUMAN_AUDIT
calibration_config_role = BASELINE_UNMODIFIED
intended_role = CALIBRATION
must_not_feed_evaluation = true
```

## 7. Search Gate

```text
Seed Export 6
+
Fresh Export 6
→ Combined Canonical Human GT Snapshot (12)
→ Baseline Scoring
→ Stage A0
```

只有 12-Episode Combined Canonical GT Snapshot 完成并冻结后才允许：

```text
SEARCH_GATE = OPEN
```

在此之前：

```text
SEARCH_GATE = CLOSED
PARAMETER_SEARCH = FORBIDDEN
```

## 8. Next Implementation Gate

下一实现步骤只允许：

```text
1. 读取本 FROZEN v1.1 PATCH
2. 对 exporter 做最小 eligibility patch
3. Package A Seed Export 回归测试 PASS
4. Package B CALIBRATION → intended_role=CALIBRATION
5. 对齐 assess / create_export / validate_export / CLI / Web gate
6. 测试 PASS 后导出 df2ce8b2 一次
7. disk readback + immutability check
8. STOP
```

禁止 Detector 修改、参数搜索、Canonical GT、matching、Stage A0、Evaluation、review 迁移。

## 9. Authority

```text
CALIBRATION_PROTOCOL_EFFECTIVE_VERSION = FROZEN_v1.1
```

若 v1.0 与本 v1.1 在 Package-B Export 身份上冲突，v1.1 覆盖；其余条款仍以 v1.0。

```text
G1_P3_CALIBRATION_PROTOCOL =
FROZEN_v1.1_READY_FOR_FRESH_EXPORT_PATCH
```
