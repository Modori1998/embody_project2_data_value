# Project 2 G1 Audit Web Batch 3 — Human Calibration Export Result

```text
DATE = 2026-09-17
PHASE = 6 HUMAN CALIBRATION EXPORT ONLY
EXPORT_CONTRACT = P2_G1_HUMAN_CALIBRATION_EXPORT_V1
G1_AUDIT_WEB_BATCH3_EXPORT = PASS_SEED_EXPORT_READY
MANDATORY_STOP = YES
SEARCH_GATE = CLOSED
```

## 1. Authority Readback

真实读取 Google Drive：

- `Project2_G1_P3_Calibration_Protocol_FROZEN_v1_20260917.md`
- `Project2_G1_Human_Audit_Web_Design_FROZEN_v1_20260916.md`
- `Project_2_Engineering_Design_Master_v1_20260914.md`
- `Project2_Development_Roadmap_and_Design_Gate_Plan_v1_20260914.md`

真实读取本地：

- `0-doc/10-design-review/Project2_G1_P3_Calibration_Protocol_FROZEN_v1_20260917.md`
- `0-doc/80-audit-local/Project2_G1_Human_Review_Error_Attribution_Audit_20260917.md`
- `0-doc/90-implementation-local/Project2_G1_Audit_Web_Implementation_Batch2_Result_20260916.md`

本地 Frozen Protocol 与 Drive Frozen Protocol 换行归一化后全文一致。

```text
CALIBRATION_PROTOCOL = FROZEN_v1.0
P3_CONSUMES_EXPORT = YES
P3_DIRECT_SQLITE_CONSUMPTION = FORBIDDEN
```

## 2. Source Run

```text
run_id = g1_exploratory_audit_20260917_141541_fe251439
run_stage = EXPLORATORY_AUDIT
set_role = EXPLORATORY
final_boundary_semantics = MATERIALIZED_V1
episode_count = 6
```

源 Run 身份未修改。Calibration Seed 身份仅写入 Export 的 `intended_role`。

## 3. Implementation

新增：

- `src/project2_g1_audit_web/calibration_export.py`
- `scripts/export_g1_human_calibration.py`
- `tests/test_g1_audit_web_calibration_export.py`

修改：

- `src/project2_g1_audit_web/app.py`
- `src/project2_g1_audit_web/templates/audit.html`
- `src/project2_g1_audit_web/__init__.py`
- `scripts/run_g1_audit_web.py`

实现行为：

- SQLite `mode=ro` + `PRAGMA query_only=ON` + 单一 read transaction；
- current state 采用 append-only history 的最高 `review_id`；
- P1 Seed gate 只允许全 PASS；
- P2 gate 要求每个 source Final 恰有当前有效审核；
- 保留全部 REDUNDANT 行；
- MISALIGNED 要求 `corrected_frame`；
- Final materialized member fields 与 source Final 回读逐字段校验；
- 临时目录写入、完整回读验证、通过后同盘原子 rename；
- 已有 Export 不覆盖；重复触发生成新 `export_id`；
- CSV SHA256 写入 `export_meta.json`；
- UI 只在 gate PASS 时启用，包含二次确认与 Existing Exports；
- 未导出 `episode_note_history`。

CLI：

```text
python scripts/export_g1_human_calibration.py \
  --run-id g1_exploratory_audit_20260917_141541_fe251439 \
  --intended-role CALIBRATION_SEED
```

## 4. Real Export

```text
export_id = g1_cal_seed_export_20260917_214637_2f8d8802
export_path = outputs/g1_audit_web/human_calibration_export/g1_cal_seed_export_20260917_214637_2f8d8802
```

文件：

```text
export_meta.json
signal_review.csv
predicted_boundary_review.csv
human_added_boundary.csv
```

磁盘回读：

```text
SOURCE_EPISODES = 6
SIGNAL_REVIEW_ROWS = 36
SIGNAL_PASS = 36
PREDICTED_BOUNDARY_ROWS = 31
VALID = 24
REDUNDANT = 7
MISALIGNED = 0
HUMAN_ADDED_ROWS = 0
NOT_REVIEWED = 0
EXPORT_ROLE = CALIBRATION_SEED
MUST_NOT_FEED_EVALUATION = YES
```

`human_added_boundary.csv` 存在，包含完整 header，数据行为 0。

## 5. Provenance

```text
source_run_stage = EXPLORATORY_AUDIT
source_set_role = EXPLORATORY
intended_role = CALIBRATION_SEED
must_not_feed_evaluation = true
```

`data/demo_0` 的 6 条 Signal Review：

```text
review_origin = REUSED_REVIEW
review_source_run_id = g1_exploratory_audit_20260916_214523_1ba11d9d
```

未伪造 child direct review。

## 6. Validation

```text
contract = PASS
export_id consistency = PASS
source identity = PASS
episode completeness = PASS
P1 completeness / PASS gate = PASS
P2 completeness = PASS
REDUNDANT retention = PASS
empty human-added file = PASS
source Final linkage = PASS
predicted_frame linkage = PASS
materialized member semantics = PASS
SQLite review ID linkage = PASS
file SHA256 = PASS
disk readback = PASS
```

文件 SHA256：

```text
signal_review.csv = b68b8d4346e95138bf5305003b0ddd79c9bc7789a4c374eed9c6a91c2965585b
predicted_boundary_review.csv = d4ab6f0f488169e9408479d93aa99262144c03acb8b31a626ef43d04fab0eb08
human_added_boundary.csv = 122696ec48737d6fd1558e638a5708a4cbbf2895e055db7024a88bc63afa8b87
```

## 7. Tests

```text
test_g1_audit_web* = 49 PASS
test_g1_final_semantics* = 13 PASS
test_g1_p2* = 16 PASS
TOTAL = 78 PASS / 0 FAIL
```

专项覆盖：completeness、P1 reuse provenance、REDUNDANT retention、empty human-added、P1 NOT_REVIEWED、P1 FAIL、P2 NOT_REVIEWED、MISALIGNED missing corrected frame、boundary not in run、immutability、Web trigger/history、SQLite/Audit Run unchanged。

唯一测试提示为 FastAPI TestClient 的 `httpx` future deprecation warning，不影响结果。

## 8. Source Immutability

```text
Owner SQLite before = 2b262a201fedba71d37366aa58f228a3d98903f29cf3cd1adc3870f7c9b51502
Owner SQLite after  = 2b262a201fedba71d37366aa58f228a3d98903f29cf3cd1adc3870f7c9b51502
OWNER_SQLITE_UNCHANGED = PASS

Source Audit Run before = 4ec155960e70187a89948e1fa9193d0dc4837eb6c1d36dc96016be54df3db4fe
Source Audit Run after  = 4ec155960e70187a89948e1fa9193d0dc4837eb6c1d36dc96016be54df3db4fe
SOURCE_AUDIT_RUN_UNCHANGED = PASS
```

## 9. Explicit Non-Scope Confirmation

```text
DETECTOR_MODIFIED = NO
THRESHOLD_MODIFIED = NO
DETECTOR_RERUN = NO
CALIBRATION_RUN_GENERATED = NO
EVALUATION_RUN_GENERATED = NO
CANONICAL_GT_GENERATED = NO
MATCHING_EXECUTED = NO
TOLERANCE_APPLIED = NO
STAGE_A0_EXECUTED = NO
PARAMETER_SEARCH_EXECUTED = NO
CURRENT_HUMAN_REVIEW_MODIFIED = NO
SOURCE_AUDIT_RUN_MODIFIED = NO
```

## 10. Search Gate / Mandatory Stop

```text
SEARCH_GATE = CLOSED
reason = 6 / 12 Calibration Episodes available
G1_AUDIT_WEB_BATCH3_EXPORT = PASS_SEED_EXPORT_READY
MANDATORY_STOP = YES
```

下一步必须由 Design Owner 检查本 Export 后，另行授权 `FRESH_CALIBRATION_EPISODE_SELECTION`。
