# Project 2 G1-P3 Fresh Calibration Export Patch Result

```text
DATE = 2026-09-18
TASK = HUMAN CALIBRATION EXPORT MINIMAL PATCH + FRESH PACKAGE-B EXPORT
EXPORT_CONTRACT = P2_G1_HUMAN_CALIBRATION_EXPORT_V1
CALIBRATION_PROTOCOL_EFFECTIVE_VERSION = FROZEN_v1.1
G1_HUMAN_AUDIT_WEB_DESIGN_EFFECTIVE_VERSION = FROZEN_v1.1
G1_FRESH_CALIBRATION_EXPORT = PASS_READY_FOR_COMBINED_CANONICAL_GT
MANDATORY_STOP = YES
SEARCH_GATE = CLOSED
```

本轮只完成 Frozen v1.1 要求的最小 Export eligibility patch，并对正式 Fresh source 执行一次 Package B Export。未生成 Canonical GT，未做 matching、Baseline Scoring、Stage A0 或任何参数搜索。

---

## 1. Authority Readback

真实读取 Google Drive：

| 文档 | Drive fileId | DOCUMENT_STATUS |
|---|---|---|
| `Project2_G1_P3_Calibration_Protocol_FROZEN_v1_1_PATCH_20260918.md` | `1Irqgq6gsN4SegnAgZfDx_Apg32oUjv-b` | `FROZEN_v1.1` |
| `Project2_G1_Human_Audit_Web_Design_FROZEN_v1_1_PATCH_20260918.md` | `1UNriIfJXOIVsmfK5AyNpMk5MRIz1VROu` | `FROZEN_v1.1` |
| `Project2_G1_P3_Calibration_Protocol_FROZEN_v1_20260917.md` | `160L0a9BDvOcankT1gZJQsxEErZ6YWWAb` | `FROZEN_v1.0` |
| `Project2_G1_Human_Audit_Web_Design_FROZEN_v1_20260916.md` | `1v6ZtopYFfCIWG9kjCOmwJe2C-XWB4xRR` | `FROZEN_v1.0` |

本地继承 base：

```text
0-doc/10-design-review/Project2_G1_P3_Calibration_Protocol_FROZEN_v1_20260917.md
0-doc/10-design-review/Project2_G1_P3_Calibration_Protocol_FROZEN_v1_1_PATCH_20260918.md
0-doc/10-design-review/Project2_G1_Human_Audit_Web_Design_FROZEN_v1_1_PATCH_20260918.md
```

Drive 两个 v1.1 Patch 均存在，且 `OWNER_REVIEW = PASS`。未使用旧 v1.0 自行猜设计。

```text
CALIBRATION_PROTOCOL_EFFECTIVE_VERSION = FROZEN_v1.1
G1_HUMAN_AUDIT_WEB_DESIGN_EFFECTIVE_VERSION = FROZEN_v1.1
EXPORT_CONTRACT = P2_G1_HUMAN_CALIBRATION_EXPORT_V1
PACKAGE_A_MAPPING = EXPLORATORY_AUDIT + EXPLORATORY → CALIBRATION_SEED
PACKAGE_B_MAPPING = CALIBRATION + CALIBRATION + BASELINE_HUMAN_AUDIT + BASELINE_UNMODIFIED → CALIBRATION
FRESH_PACKAGE_B_INTENDED_ROLE = CALIBRATION
```

---

## 2. Patch Files

MINIMAL_TARGETED_CHANGE。未做 architecture refactor，未新增 `CALIBRATION_FRESH` / `PACKAGE_B` 枚举。

修改：

- `src/project2_g1_audit_web/calibration_export.py`
- `scripts/export_g1_human_calibration.py`
- `src/project2_g1_audit_web/app.py`
- `src/project2_g1_audit_web/templates/audit.html`
- `tests/test_g1_audit_web_calibration_export.py`

实现要点：

- 共享 helper：`_source_identity` / `resolve_export_role` / `export_eligibility_errors`
- `assess` / `create_export` / `validate_export` 使用同一份 Frozen eligibility mapping
- Package A 继续支持 Exploratory Seed Export
- Package B 合法接受 Fresh CALIBRATION baseline，`intended_role = CALIBRATION`
- CLI `--intended-role` choices = `CALIBRATION_SEED` + `CALIBRATION`；choice 不等于合法，仍校验 mapping
- Web POST 不再写死 `CALIBRATION_SEED`；按 Frozen mapping 自动解析 role，用户不可自由输入
- UI Ready / Create Export 由 `assess.ready` 驱动，而 `ready = effective_export_ready`

未修改：Detector、threshold、SQLite schema、Human Review、source Audit Run、Seed Export、Frozen v1.0、Frozen v1.1 Patch 正文。

---

## 3. Eligibility Mapping

```text
Package A:
  run_stage = EXPLORATORY_AUDIT
  set_role = EXPLORATORY
  intended_role = CALIBRATION_SEED
  must_not_feed_evaluation = true

Package B:
  run_stage = CALIBRATION
  set_role = CALIBRATION
  calibration_role = BASELINE_HUMAN_AUDIT
  calibration_config_role = BASELINE_UNMODIFIED
  intended_role = CALIBRATION
  must_not_feed_evaluation = true
```

禁止组合（已测）：

```text
CALIBRATION source + intended_role = CALIBRATION_SEED     → blocked
EXPLORATORY source + intended_role = CALIBRATION          → blocked
CALIBRATION + calibration_role != BASELINE_HUMAN_AUDIT    → blocked
CALIBRATION + calibration_config_role != BASELINE_UNMODIFIED → blocked
```

---

## 4. Readiness Alignment

```text
review_ready = Human Review completeness + schema validity
export_eligible = source identity + intended_role 符合 Frozen v1.1 mapping
effective_export_ready = review_ready AND export_eligible
assess.ready = effective_export_ready
```

正式 Fresh source 当前回读：

```text
run_id = g1_calibration_20260918_094455_df2ce8b2
review_ready = true
export_eligible = true
effective_export_ready = true
intended_role = CALIBRATION
```

不再出现：`assess ready=true` 但 `create_export` 必然因 source identity 400。

未使用 `g1_calibration_20260917_222604_d4425fc3` 作为 Human Review Source；未 copy / rebind / 迁移 / 重写 review。

---

## 5. Regression Tests

```text
Package A = PASS
Package B = PASS
```

Package B 覆盖：

```text
A 合法 reviewed CALIBRATION baseline → Export allowed
B CALIBRATION 但 P1 incomplete → blocked
C CALIBRATION 但 P2 incomplete → blocked
D calibration_role != BASELINE_HUMAN_AUDIT → blocked
E calibration_config_role != BASELINE_UNMODIFIED → blocked
F CALIBRATION source + CALIBRATION_SEED → blocked
G EXPLORATORY source + CALIBRATION → blocked
H existing Exploratory Seed Export → still PASS
I assess / create_export / validate_export eligibility 判断一致
J SQLite unchanged
K source run unchanged
```

测试结果：

```text
test_g1_audit_web_calibration_export.py = 14 PASS / 0 FAIL
test_g1_audit_web*                      = 59 PASS / 0 FAIL
test_g1_fresh_calibration_run.py        = 5 PASS / 0 FAIL

total tests = 64
pass        = 64
fail        = 0
```

说明：`test_g1_audit_web*` 已包含 14 个 Export 专项测试；合计 64 = 59 + 5，不重复计数 14。

Package A 现有 Seed Export 身份保持：

```text
export_id = g1_cal_seed_export_20260917_214637_2f8d8802
source_run_id = g1_exploratory_audit_20260917_141541_fe251439
intended_role = CALIBRATION_SEED
signal_review = 36
predicted_boundary_review = 31
VALID = 24
REDUNDANT = 7
HUMAN_ADDED = 0
```

---

## 6. Fresh Export

正式 source 验证 PASS，且 `effective_export_ready = true` 后，执行一次：

```text
source_run_id = g1_calibration_20260918_094455_df2ce8b2
intended_role = CALIBRATION
```

```text
export_id = g1_cal_export_20260918_120335_81c068bf
export_path = outputs/g1_audit_web/human_calibration_export/g1_cal_export_20260918_120335_81c068bf
```

磁盘回读：

```text
signal_review.csv
  rows = 36
  PASS = 36

predicted_boundary_review.csv
  rows = 35
  VALID = 32
  REDUNDANT = 3
  MISALIGNED = 0
  NOT_REVIEWED = 0

human_added_boundary.csv
  rows = 0
  header exists = YES
```

文件 SHA256：

```text
signal_review.csv = ab53c9e5522d318b748b50c033f89fb46583080e8c01862cdcecf6f6cb227492
predicted_boundary_review.csv = bc8e21f7963c01449b635e9b0d010a5179427a4e3a5548321279eee78a16c3d2
human_added_boundary.csv = 122696ec48737d6fd1558e638a5708a4cbbf2895e055db7024a88bc63afa8b87
```

```text
Signal = 36 / 36 PASS
Predicted = 35 REVIEWED (32 VALID + 3 REDUNDANT)
Human Added = 0
```

---

## 7. Export Meta

```text
export_contract = P2_G1_HUMAN_CALIBRATION_EXPORT_V1
export_id = g1_cal_export_20260918_120335_81c068bf
source_run_id = g1_calibration_20260918_094455_df2ce8b2
source_run_stage = CALIBRATION
source_set_role = CALIBRATION
calibration_role = BASELINE_HUMAN_AUDIT
calibration_config_role = BASELINE_UNMODIFIED
config_hash = dde590e759a31cb8c865369e18256ebecbbd01bc94a58e1d3ca695bb50f2a630
signal_contract_hash = 24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d
intended_role = CALIBRATION
must_not_feed_evaluation = true
calibration_protocol_document = Project2_G1_P3_Calibration_Protocol_FROZEN_v1_1_PATCH_20260918.md
calibration_protocol_status = FROZEN_v1.1
validation_status = PASS
```

未把 CALIBRATION source 伪装成 `EXPLORATORY_AUDIT`，未把 Fresh Export 标成 `CALIBRATION_SEED`。

---

## 8. Immutability

项目 `tree_fingerprint` / `sha256_file` 回读：

```text
OWNER_SQLITE = 076b3fe1504b23334cc861b32fb3145efaa92f187aa4002be1afcee7bc96c718
OWNER_SQLITE_UNCHANGED = PASS

SOURCE_RUN = 20b7255b93567b753cac2b2c63f41eb7569c9a10fa701a5a4ab42f94d7f22297
SOURCE_RUN_UNCHANGED = PASS

SEED_EXPORT = 8ba31e9721ee3554b3b56b3bc46ff041c175b39865ea76c918f931b0a6d355c7
SEED_EXPORT_UNCHANGED = PASS

FROZEN_V1_0 Protocol = d75c05d7a0cad0ba2298225745314af7a313ad70e19d331b3b49205fb7e81c1a
FROZEN_V1_0_UNCHANGED = PASS

FROZEN_V1_1 Protocol Patch = 011eab45065026d2c697daafa06826c80c873129c687bd97799a95e9af4ef175
FROZEN_V1_1 Web Design Patch = 5fab901254d5b49f5cc760b66e212c1c8cd41b44631d04953e537afe907ada80
FROZEN_V1_1_PATCH_UNCHANGED = PASS
```

```text
HUMAN_REVIEW_COPY = NO
HUMAN_REVIEW_REBIND = NO
HUMAN_REVIEW_MIGRATION = NO
HUMAN_REVIEW_REWRITE = NO
DETECTOR_MODIFIED = NO
THRESHOLD_MODIFIED = NO
CANONICAL_GT_GENERATED = NO
MATCHING_EXECUTED = NO
BASELINE_SCORING_EXECUTED = NO
STAGE_A0_EXECUTED = NO
PARAMETER_SEARCH_EXECUTED = NO
```

---

## 9. Search Gate

```text
SEARCH_GATE = CLOSED
PARAMETER_SEARCH = FORBIDDEN
```

原因：仍缺

```text
Seed Export 6
+
Fresh Export 6
→ Combined 12-Episode Canonical GT Snapshot Freeze
```

在 Combined Canonical GT Snapshot 冻结之前，不允许 Baseline Scoring / Stage A0 / 任何参数搜索。

---

## 10. Final Status

```text
G1_FRESH_CALIBRATION_EXPORT =
PASS_READY_FOR_COMBINED_CANONICAL_GT
```

```text
MANDATORY_STOP = YES
NEXT_ALLOWED = Combined 12-Episode Canonical GT Snapshot Freeze
NEXT_FORBIDDEN = matching / ±3 scoring / TP-FP-FN / Baseline Scoring / Stage A0 / Detector 修改 / Evaluation selection
```
