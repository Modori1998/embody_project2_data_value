# Project 2 G1 Human Audit Web Design FROZEN v1.1 PATCH

```text
DATE = 2026-09-18
DOCUMENT_STATUS = FROZEN_v1.1
FROZEN = YES
PATCH_TYPE = ADDITIVE_EXPORT_GATE_CLARIFICATION
BASE_DESIGN = Project2_G1_Human_Audit_Web_Design_FROZEN_v1_20260916.md
BASE_DESIGN_STATUS = FROZEN_v1.0
OWNER_REVIEW = PASS
SCOPE = P2_G1_HUMAN_CALIBRATION_EXPORT_V1 SOURCE ELIGIBILITY + READINESS
DRIVE_FILE_ID = 1UNriIfJXOIVsmfK5AyNpMk5MRIz1VROu
```

本补丁只覆盖 Human Calibration Export 的 source eligibility、intended_role 与 readiness 语义。其余 Web Design v1.0 全部继承。

## 1. Legal Export Mapping

```text
Package A:
EXPLORATORY_AUDIT + EXPLORATORY
→ intended_role = CALIBRATION_SEED

Package B:
CALIBRATION + CALIBRATION
+ calibration_role = BASELINE_HUMAN_AUDIT
+ calibration_config_role = BASELINE_UNMODIFIED
→ intended_role = CALIBRATION
```

两类均：

```text
export_contract = P2_G1_HUMAN_CALIBRATION_EXPORT_V1
must_not_feed_evaluation = true
```

禁止实现新增 `CALIBRATION_FRESH` 等 role。

## 2. Readiness Contract

```text
review_ready
export_eligible
effective_export_ready = review_ready && export_eligible
```

用户可见 “Ready / Create Export” 只能由 `effective_export_ready` 驱动。

不允许出现 review_ready=true，但 create_export 必然因 source role 失败的 UI/API 不一致。

## 3. Export Service

`assess / create_export / validate_export` 必须共享同一份 frozen eligibility mapping。

Package A 现有行为必须保持。

Package B 必须合法接受：

```text
run_stage = CALIBRATION
set_role = CALIBRATION
calibration_role = BASELINE_HUMAN_AUDIT
calibration_config_role = BASELINE_UNMODIFIED
intended_role = CALIBRATION
```

## 4. CLI / Web

CLI 合法 intended_role 至少包含：

```text
CALIBRATION_SEED
CALIBRATION
```

但 source identity validator 仍必须拒绝非法组合。

Web POST 不得继续写死 `CALIBRATION_SEED`；必须根据 frozen source identity mapping 自动选出 role，且不允许用户自由输入未冻结 role。

## 5. Current Formal Fresh Source

```text
run_id = g1_calibration_20260918_094455_df2ce8b2
P1 = 36 / 36 PASS
P2 = 35 / 35 REVIEWED
VALID = 32
REDUNDANT = 3
MISALIGNED = 0
HUMAN_ADDED = 0
```

`g1_calibration_20260917_222604_d4425fc3` 不是 Human Review Source；不得复制、迁移或 rebind review。

## 6. No Scope Expansion

本 patch 不允许修改 SQLite schema、review key、append-only history、Detector、Final semantics；不生成 Canonical GT、不启动 matching、参数搜索或 Evaluation。

## 7. Authority

```text
G1_HUMAN_AUDIT_WEB_DESIGN_EFFECTIVE_VERSION = FROZEN_v1.1
```

若 v1.0 与本 v1.1 在 Export eligibility/readiness 上冲突，v1.1 覆盖；其余条款仍以 v1.0。

```text
G1_HUMAN_AUDIT_WEB_DESIGN =
FROZEN_v1.1_READY_FOR_FRESH_EXPORT_PATCH
```
