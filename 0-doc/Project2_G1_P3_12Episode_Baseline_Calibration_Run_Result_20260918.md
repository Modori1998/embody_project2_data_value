# Project 2 G1-P3 12-Episode Baseline Calibration Run Result

```text
DATE = 2026-09-18
TASK = 12_EPISODE_BASELINE_CALIBRATION_RUN_AUDIT_AND_MATERIALIZATION
CALIBRATION_PROTOCOL_EFFECTIVE_VERSION = FROZEN_v1.1
BASELINE_CALIBRATION_RUN_REQUIRED = YES
COMBINED_CANONICAL_GT = FROZEN
canonical_gt_snapshot_id = g1_canonical_gt_20260918_131636_c9916b89
EXISTING_BASELINE_RUN_PRE_AUDIT = NOT_FOUND
EXISTING_BASELINE_RUN_POST_AUDIT = FOUND
run_id = g1_calibration_20260918_141032_781e5d8b
G1_12EP_BASELINE_CALIBRATION_RUN = PASS_READY_FOR_BASELINE_SCORING
MANDATORY_STOP = YES
MATCHING_EXECUTED = NO
TOLERANCE_APPLIED = NO
TP_FP_FN_COMPUTED = NO
PRECISION_RECALL_F1_COMPUTED = NO
BASELINE_SCORING_EXECUTED = NO
STAGE_A0_EXECUTED = NO
PARAMETER_SEARCH_EXECUTED = NO
DETECTOR_PARAMETER_MODIFIED = NO
```

本轮先按 Frozen Calibration Protocol 对 `outputs/g1_audit_runs/` 与 `g1_audit_run_registry.json` 做正式身份审计。审计前不存在合法 12-Episode CALIBRATION Baseline Run，因此用完全未修改的 exploratory baseline config 生成一条 immutable 12-Episode 预测 Run。未执行 matching / scoring / Stage A0 / 参数搜索。未复制 P2 Human Review，未 rebind Owner SQLite。

---

## 1. Authority

真实读取 Google Drive：

| 文档 | Drive fileId | DOCUMENT_STATUS |
|---|---|---|
| `Project2_G1_P3_Calibration_Protocol_FROZEN_v1_20260917.md` | `160L0a9BDvOcankT1gZJQsxEErZ6YWWAb` | `FROZEN_v1.0` |
| `Project2_G1_P3_Calibration_Protocol_FROZEN_v1_1_PATCH_20260918.md` | `1Irqgq6gsN4SegnAgZfDx_Apg32oUjv-b` | `FROZEN_v1.1` |

本轮执行依据：v1.0 Section 17 Calibration Run Lineage、Section 18 Calibration Scoring Procedure、Section 22 完整闭环、Section 25 下一步 Gate。v1.1 只覆盖 Package-B Export 身份，不改变 Baseline Run 的 scientific identity。

```text
CALIBRATION_PROTOCOL_EFFECTIVE_VERSION = FROZEN_v1.1
BASELINE_CALIBRATION_RUN_REQUIRED = YES

Required identity:
run_stage = CALIBRATION
set_role = CALIBRATION
episode_count = 12
search_stage = BASELINE
config = current exploratory baseline unchanged
```

Canonical GT Snapshot（只读 manifest，不 matching / scoring）：

```text
canonical_gt_snapshot_id = g1_canonical_gt_20260918_131636_c9916b89
COMBINED_CANONICAL_GT = FROZEN
Episode count = 12
Canonical GT = 56
Known FP Anchor = 10
```

---

## 2. Existing Run Audit

Phase A 只读检查 Registry + run_meta + episode manifest + config/signal identity。**不按 run_id 名称、mtime、latest 猜测。**

| 已审计 run_id | qualifies | 拒绝原因 |
|---|---|---|
| `g1_exploratory_audit_20260916_214523_1ba11d9d` | false | `run_stage=EXPLORATORY_AUDIT`；episode_count=6；search_stage 缺失；exact-set 失败 |
| `g1_exploratory_audit_20260917_141541_fe251439` | false | `run_stage=EXPLORATORY_AUDIT`；episode_count=6；search_stage 缺失；exact-set 失败 |
| `g1_calibration_20260917_222604_d4425fc3` | false | NTFS 拒绝读取 `run_meta.json`（历史 locked run；本轮不删除、不作为 HR source） |
| `g1_calibration_20260918_094455_df2ce8b2` | false | episode_count=6；search_stage 缺失；exact-set 缺 Seed 6 |

```text
EXISTING_BASELINE_RUN = NOT_FOUND
```

因此允许生成新的 immutable 12-Episode Baseline Run。

生成并通过 Validator + Registry 后复审：

```text
EXISTING_BASELINE_RUN = FOUND
run_id = g1_calibration_20260918_141032_781e5d8b
MANIFEST_EXACT_MATCH = PASS
CONFIG_HASH_MATCH = PASS
SIGNAL_HASH_MATCH = PASS
PARAMETER_DIFF_COUNT = 0
VALIDATOR = PASS
```

复审 FOUND 的是本轮新生成的同一条 Run，**没有第二条 qualifying run**，因此未重复 materialize。

---

## 3. Baseline Run

```text
run_id = g1_calibration_20260918_141032_781e5d8b
run_stage = CALIBRATION
set_role = CALIBRATION
search_stage = BASELINE
episode_count = 12
calibration_config_role = BASELINE_UNMODIFIED
parameter_search_executed = false
final_boundary_semantics = MATERIALIZED_V1
human_review_status = NOT_REQUIRED
calibration_manifest_id = g1_canonical_gt_20260918_131636_c9916b89
canonical_gt_snapshot_id = g1_canonical_gt_20260918_131636_c9916b89
run_root = outputs/g1_audit_runs/g1_calibration_20260918_141032_781e5d8b
```

本 Run 是 **machine prediction baseline for scoring**，不是新的 GT 来源。未复制旧 P2 review，未要求 Owner 再审 12 条。P2 `NOT_REVIEWED` 不是本 Run 成为 scoring baseline 的阻断条件。

---

## 4. Scientific Identity

```text
config_hash = dde590e759a31cb8c865369e18256ebecbbd01bc94a58e1d3ca695bb50f2a630
signal_contract_hash = 24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d
config_version = g1_p2_exploratory_segmentation.v0
segmentation_version = G1-P2-EXPLORATORY-v0
signal_contract_version = g1_p1_signal_contract.v0
PARAMETER_DIFF_COUNT = 0
DETECTOR_PARAMETER_MODIFIED = NO
```

未调整 threshold / persistence / debounce / consolidation / pause bridge，未增加 Formal Signal。

### parent_run_id 选择

```text
parent_run_id = g1_exploratory_audit_20260917_141541_fe251439
```

选择理由（lineage contract，非猜测）：

1. Frozen Protocol 的 scientific baseline origin 是 Seed exploratory run `fe251439`：未修改 exploratory config 的首次正式 Audit Folder。
2. Fresh 6-ep run `df2ce8b2` 自身的 `parent_run_id` 也是 `fe251439`。12-ep Baseline 是 **同一 config 在更大 Episode exact-set 上的 materialization**，不是 Fresh-6 的参数突变子代。
3. 不得把 locked `d4425fc3` 当作 parent 或 Fresh Human Review source。
4. Scientific identity **不依赖 parent 名称**，由 `config_hash + signal_contract_hash + Combined 12-Episode exact-set` 保证。

---

## 5. Episode Manifest

直接读取：

`outputs/g1_p3_canonical_gt/g1_canonical_gt_20260918_131636_c9916b89/combined_calibration_manifest.json`

```text
EPISODE_COUNT = 12
MISSING = 0
EXTRA = 0
DUPLICATE = 0
exact_set = PASS
total = 12
Seed = 6
Fresh = 6
```

Seed 6：

```text
data/demo_0
data/demo_32
data/demo_179
data/demo_230
data/demo_242
data/demo_278
```

Fresh 6：

```text
data/demo_150
data/demo_162
data/demo_213
data/demo_255
data/demo_260
data/demo_270
```

---

## 6. Prediction Consistency

逐 Episode 对照：episode_length、candidate count、final count、Final frames、representative candidate type、member_candidate_frames、member_candidate_types、segment boundaries。

| 对照 | source run | 结果 |
|---|---|---|
| Seed 6 | `g1_exploratory_audit_20260917_141541_fe251439` | PASS（differences=[]） |
| Fresh 6 | `g1_calibration_20260918_094455_df2ce8b2` | PASS（differences=[]） |

```text
BASELINE_PREDICTION_CONSISTENCY = PASS
Seed 6 = PASS
Fresh 6 = PASS
Final frame consistency = PASS
REPORT_PIPELINE_DRIFT = NO
```

未进入 Baseline Scoring。

---

## 7. Validator

```text
validator = PASS
contract_version = P2_G1_AUDIT_FOLDER_V1
final_member_semantics = MATERIALIZED
```

PASS 后才注册 Registry。未使用 mtime guess / recursive latest discovery。

---

## 8. Registry

```text
registry_status = AUTO_REGISTERED
registry_path = outputs/g1_audit_web/g1_audit_run_registry.json
registered_at = 2026-09-18T15:24:21.328626+08:00
enabled = true
owner_note = 12-Episode Calibration Baseline; unmodified exploratory config; Canonical GT frozen; scoring not executed
```

---

## 9. Immutability

本轮只新增一条 12-Episode Baseline Run 与 Registry 条目。未修改：

| 对象 | fingerprint / sha256 |
|---|---|
| Seed Export `g1_cal_seed_export_20260917_214637_2f8d8802` | `8ba31e9721ee3554b3b56b3bc46ff041c175b39865ea76c918f931b0a6d355c7` |
| Fresh Export `g1_cal_export_20260918_120335_81c068bf` | `01a3c732ae8b193a72ede845363105d0742b2f8357685e1f61d0a1b52dc3eb1f` |
| Canonical GT Snapshot | `335a8d62d9871e26f34a6e887206cbb48504dfc551337c024086e7252ac399ef` |
| Owner SQLite | `076b3fe1504b23334cc861b32fb3145efaa92f187aa4002be1afcee7bc96c718` |
| Seed source `fe251439` run_meta | `15f06215aab21648bd0091e93d9322c98145a8ca774a7b76ed7afb191759cda7` |
| Fresh source `df2ce8b2` run_meta | `cc10f11f90bd7148bda9d33626d546c7578c5a4c7de61c19685db255a68ad864` |
| Frozen Protocol v1.0 本地 | `d75c05d7a0cad0ba2298225745314af7a313ad70e19d331b3b49205fb7e81c1a` |
| Frozen Protocol v1.1 Patch 本地 | `011eab45065026d2c697daafa06826c80c873129c687bd97799a95e9af4ef175` |

`g1_calibration_20260917_222604_d4425fc3` 保持历史不变，未删除。

---

## 10. Explicit Non-Scope

```text
MATCHING_EXECUTED = NO
TOLERANCE_APPLIED = NO
TP_FP_FN_COMPUTED = NO
PRECISION_RECALL_F1_COMPUTED = NO
BASELINE_SCORING_EXECUTED = NO
STAGE_A0_EXECUTED = NO
PARAMETER_SEARCH_EXECUTED = NO
DETECTOR_PARAMETER_MODIFIED = NO
HUMAN_REVIEW_REBIND = NO
```

---

## 11. Search Gate

```text
COMBINED_CANONICAL_GT = FROZEN
SEARCH_GATE = OPEN_FOR_BASELINE_SCORING
```

下一步允许 Baseline Scoring。本轮 **STOP**，不自动开始 Scoring。

---

## 12. Tests

`python -m unittest discover -s tests -p "test_g1_12ep_baseline_calibration.py"`

```text
Ran 13 tests in 0.079s
OK
```

覆盖：qualifying run discovery；wrong episode count/set；wrong config/signal hash；wrong search_stage；12 exact-set；parameter diff zero；validator PASS；MATERIALIZED_V1；Seed/Fresh prediction consistency；source immutability。

---

## 13. Final Status

```text
G1_12EP_BASELINE_CALIBRATION_RUN = PASS_READY_FOR_BASELINE_SCORING
MANDATORY_STOP = YES
```
