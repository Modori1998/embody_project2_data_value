# Project 2 G1-P3 Combined Canonical Human GT Result

```text
DATE = 2026-09-18
TASK = COMBINED_12_EPISODE_CANONICAL_GT_BUILD
CALIBRATION_PROTOCOL = FROZEN_v1.1
EXPORT_CONTRACT = P2_G1_HUMAN_CALIBRATION_EXPORT_V1
CANONICAL_GT_CONTRACT_VERSION = P2_G1_CANONICAL_HUMAN_BOUNDARY_GT_V1
COMBINED_CANONICAL_GT = FROZEN
SEARCH_GATE = OPEN_FOR_BASELINE_SCORING
G1_COMBINED_CANONICAL_GT = PASS_READY_FOR_BASELINE_SCORING
MANDATORY_STOP = YES
MATCHING_EXECUTED = NO
BASELINE_SCORING_EXECUTED = NO
STAGE_A0_EXECUTED = NO
PARAMETER_SEARCH_EXECUTED = NO
```

本轮只从两个正式 Human Calibration Export 构建 versioned + immutable 的 12-Episode Combined Canonical Human Boundary GT Snapshot，并生成 Known False Positive Anchors。未执行 matching、TP/FP/FN、Baseline Scoring、Stage A0 或任何参数搜索。

---

## 1. Authority

真实读取 Google Drive：

| 文档 | Drive fileId | DOCUMENT_STATUS |
|---|---|---|
| `Project2_G1_P3_Calibration_Protocol_FROZEN_v1_1_PATCH_20260918.md` | `1Irqgq6gsN4SegnAgZfDx_Apg32oUjv-b` | `FROZEN_v1.1` |
| `Project2_G1_Human_Audit_Web_Design_FROZEN_v1_1_PATCH_20260918.md` | `1UNriIfJXOIVsmfK5AyNpMk5MRIz1VROu` | `FROZEN_v1.1` |
| `Project2_G1_P3_Calibration_Protocol_FROZEN_v1_20260917.md` | `160L0a9BDvOcankT1gZJQsxEErZ6YWWAb` | `FROZEN_v1.0` |

本地继承：

```text
0-doc/10-design-review/Project2_G1_P3_Calibration_Protocol_FROZEN_v1_20260917.md
0-doc/10-design-review/Project2_G1_P3_Calibration_Protocol_FROZEN_v1_1_PATCH_20260918.md
```

Authority 冲突检查：

```text
REPORT_AUTHORITY_CONFLICT = NO
```

v1.1 Patch 只覆盖 Package B Export 身份；v1.0 的 Canonical GT / matching / Search Gate 继续有效。两个正式 Export 均已存在后，Combined Canonical GT 是 Frozen Protocol 允许的下一步。v1.1 §8 的 “禁止 Canonical GT” 是上一轮 Fresh Export Patch 的 stop gate，不是对本轮的永久禁令。

```text
CALIBRATION_PROTOCOL = FROZEN_v1.1
G1_HUMAN_AUDIT_WEB_DESIGN = FROZEN_v1.1
P3_READS_EXPORT_ONLY = YES
P3_DIRECT_SQLITE_CONSUMPTION = FORBIDDEN
```

---

## 2. Source Exports

```text
Seed export  = g1_cal_seed_export_20260917_214637_2f8d8802
Fresh export = g1_cal_export_20260918_120335_81c068bf
validation   = PASS
```

### Package A / Seed

```text
source_run_id = g1_exploratory_audit_20260917_141541_fe251439
intended_role = CALIBRATION_SEED
source_run_stage = EXPLORATORY_AUDIT
source_set_role = EXPLORATORY
must_not_feed_evaluation = true
episodes = 6
signal rows = 36 / 36 PASS
predicted rows = 31
VALID = 24
REDUNDANT = 7
MISALIGNED = 0
human_added = 0
file SHA256 = PASS
disk readback = PASS
```

### Package B / Fresh

```text
source_run_id = g1_calibration_20260918_094455_df2ce8b2
intended_role = CALIBRATION
source_run_stage = CALIBRATION
source_set_role = CALIBRATION
calibration_role = BASELINE_HUMAN_AUDIT
calibration_config_role = BASELINE_UNMODIFIED
must_not_feed_evaluation = true
episodes = 6
signal rows = 36 / 36 PASS
predicted rows = 35
VALID = 32
REDUNDANT = 3
MISALIGNED = 0
human_added = 0
file SHA256 = PASS
disk readback = PASS
```

未读取 `g1_audit_web_owner.sqlite3` 构建 GT。未修改两个 Export。

---

## 3. Episode Manifest

从两个 Export 实际读取，不使用 Prompt 手抄作为输入：

```text
total   = 12
seed    = 6
fresh   = 6
overlap = 0
DUPLICATE_EPISODE_ID = 0
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

与冻结 `fresh_calibration_manifest_v1.json` exact-set 一致。

---

## 4. P1 Gate

```text
PASS         = 72 / 72
FAIL         = 0
UNCERTAIN    = 0
NOT_REVIEWED = 0
```

两包均无 P1 非 PASS，未阻断 Snapshot。

---

## 5. Human Review Input

```text
Predicted Reviewed = 66   # 31 + 35
VALID              = 56   # 24 + 32
REDUNDANT          = 10   # 7 + 3
MISALIGNED         = 0
Human Added        = 0
NOT_REVIEWED       = 0
```

---

## 6. Canonical GT

```text
snapshot_id = g1_canonical_gt_20260918_131636_c9916b89
canonical_gt_count = 56
VALID_INHERIT = 56
MISALIGNED_CORRECTED = 0
HUMAN_ADDED = 0
conflicts = 0
deduped = 0
```

无 episode 内同 frame conflict / dedupe，因此：

```text
EXPECTED_CANONICAL_GT_PRE_DEDUP = 56
ACTUAL_CANONICAL_GT = 56
```

`gt_id` 形如 `data/demo_278-HGT0001`，仅在本 snapshot 内稳定；未把 `boundary_id` 当作 `gt_id`。

`protected_class` 由 Export 内 materialized Final provenance 派生，未改变 `gt_frame`，未按 class 过滤：

```text
MERGED_GRIPPER_CLUSTER = 26
VALID_DIRECTION_PRIMARY = 17
GRIPPER_PRIMARY = 10
OTHER = 3
```

`OTHER` 为非 Gripper / 非 Direction representative 的 VALID Final（例如独立 motion start/stop），按 Frozen 规则不猜测。

```text
min_gt_spacing_frames = 9
gt_spacing_warn = false
```

相邻 Canonical GT 最小间距 9 frames > `2 * T = 6`，未触发 GT spacing warn。该诊断不是 matching。

---

## 7. Known FP Anchors

```text
count = 10
Seed  = 7
Fresh = 3
```

Seed 保留正式 Error Attribution mapping：

```text
MODE_01 = 3   # demo_242 REDUNDANT_DIRECTION_JITTER
MODE_02 = 3   # demo_278 REDUNDANT_SHORT_PAUSE
MODE_03 = 1   # demo_242 REDUNDANT_SHORT_PAUSE @136
```

Fresh 3 条 `REDUNDANT_SHORT_PAUSE`：

```text
error_mode = UNASSIGNED
```

未根据聊天内容私自赋 MODE_01/02/03。reason_code 仍保留。

---

## 8. Output Artifacts

```text
snapshot_root =
outputs/g1_p3_canonical_gt/g1_canonical_gt_20260918_131636_c9916b89/

meta          = canonical_gt_meta.json
manifest      = combined_calibration_manifest.json
canonical GT  = canonical_human_boundary_gt.csv
known FP      = known_false_positive_anchor.csv
```

SHA256：

```text
canonical_human_boundary_gt.csv =
28ad32caa0a24f8034628fc1aa9b8e502d5b356eee660fc7f1076d09ff47dfcd

known_false_positive_anchor.csv =
7acd5847056ffed48423a832a169bdf8a5cfdb6a0197ac16e983b0e51fdca813
```

实现文件：

```text
src/project2_g1/canonical_gt.py
scripts/build_g1_combined_canonical_gt.py
tests/test_g1_canonical_gt.py
```

---

## 9. Validation

```text
schema              = PASS
provenance          = PASS
episode exact-set   = PASS
immutability        = PASS
atomic build        = PASS
P1 gate             = PASS
export SHA256       = PASS
evaluation leakage  = PASS
gt_id deterministic = PASS
```

tests：

```text
test_g1_canonical_gt.py = 16 PASS / 0 FAIL
```

覆盖：two-export validation、12 unique exact-set、Seed/Fresh no overlap、VALID→GT、MISALIGNED→corrected GT、REDUNDANT→known FP only、Human Added→GT、NOT_REVIEWED block、P1 non-PASS block、same-frame dedupe、source conflict block、GT id deterministic、snapshot immutable、atomic build、round-trip、source exports unchanged、SQLite unread。

---

## 10. Explicit Non-Scope

```text
MATCHING_EXECUTED = NO
TOLERANCE_APPLIED = NO
BASELINE_SCORING_EXECUTED = NO
STAGE_A0_EXECUTED = NO
PARAMETER_SEARCH_EXECUTED = NO
DETECTOR_MODIFIED = NO
HUMAN_REVIEW_MODIFIED = NO
EXPORT_MODIFIED = NO
SQLITE_READ_FOR_GT = NO
```

`matching_rule_id` 与 `tolerance_frames=3` 仅写入 snapshot provenance，本轮未应用。

---

## 11. Immutability

```text
SEED_EXPORT_UNCHANGED = PASS
  8ba31e9721ee3554b3b56b3bc46ff041c175b39865ea76c918f931b0a6d355c7

FRESH_EXPORT_UNCHANGED = PASS
  01a3c732ae8b193a72ede845363105d0742b2f8357685e1f61d0a1b52dc3eb1f

OWNER_SQLITE_UNCHANGED = PASS
  076b3fe1504b23334cc861b32fb3145efaa92f187aa4002be1afcee7bc96c718

SOURCE_SEED_RUN_UNCHANGED = PASS
  4ec155960e70187a89948e1fa9193d0dc4837eb6c1d36dc96016be54df3db4fe

SOURCE_FRESH_RUN_UNCHANGED = PASS
  20b7255b93567b753cac2b2c63f41eb7569c9a10fa701a5a4ab42f94d7f22297

FROZEN_V1_0_UNCHANGED = PASS
  d75c05d7a0cad0ba2298225745314af7a313ad70e19d331b3b49205fb7e81c1a

FROZEN_V1_1_PROTOCOL_PATCH_UNCHANGED = PASS
  011eab45065026d2c697daafa06826c80c873129c687bd97799a95e9af4ef175

FROZEN_V1_1_WEB_PATCH_UNCHANGED = PASS
  5fab901254d5b49f5cc760b66e212c1c8cd41b44631d04953e537afe907ada80

DATASET_UNCHANGED = PASS
  demo_v15.hdf5    = 6f5a0e96fc375468ae19ccac86a6dee3b4d3862ef0fe37ca2d02e93d9046fe6b
  low_dim_v15.hdf5 = c4a34c837913446d295c6ca38f2b31888d69812198478af470ecb84a99e9f7d7
```

---

## 12. Search Gate / Final Status

```text
COMBINED_CANONICAL_GT = FROZEN
SEARCH_GATE = OPEN_FOR_BASELINE_SCORING
PARAMETER_SEARCH_STARTED = NO
```

按 Frozen Protocol，下一步只允许：

```text
BASELINE_SCORING
```

然后才是 Stage A0。Stage A0 PASS 之前禁止真正 Stage A 参数搜索。

```text
G1_COMBINED_CANONICAL_GT =
PASS_READY_FOR_BASELINE_SCORING
```

```text
MANDATORY_STOP = YES
```
