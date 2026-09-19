# Project 2 G1-P3 Baseline Scoring Result

```text
DATE = 2026-09-18
TASK = G1_12EP_BASELINE_SCORING
CALIBRATION_PROTOCOL_EFFECTIVE_VERSION = FROZEN_v1.1
MATCHING_RULE_ID = MAX_CARDINALITY_MIN_TOTAL_DISTANCE_ONE_TO_ONE_V1
TOLERANCE_FRAMES = 3
TOLERANCE_SECONDS = 0.15
TOLERANCE_IS_SEARCH_AXIS = NO
CONFIG_SELECTION_RULE = LEXICOGRAPHIC_CONSTRAINED
BASELINE_SCORING = FROZEN
NEXT_GATE = STAGE_A0_DIRECTION_CANDIDATE_DISCRIMINABILITY_AUDIT
G1_BASELINE_SCORING = PASS_READY_FOR_STAGE_A0
MANDATORY_STOP = YES
```

本轮对已冻结的 12-Episode Baseline Calibration Run 与 Combined Canonical Human GT Snapshot 执行正式 Baseline Scoring。允许 matching / TP / FP / FN / metrics。禁止修改 Detector、GT、Stage A0 与任何参数搜索。

---

## 1. Authority

真实读取 Google Drive：

| 文档 | Drive fileId | DOCUMENT_STATUS |
|---|---|---|
| `Project2_G1_P3_Calibration_Protocol_FROZEN_v1_20260917.md` | `160L0a9BDvOcankT1gZJQsxEErZ6YWWAb` | `FROZEN_v1.0` |
| `Project2_G1_P3_Calibration_Protocol_FROZEN_v1_1_PATCH_20260918.md` | `1Irqgq6gsN4SegnAgZfDx_Apg32oUjv-b` | `FROZEN_v1.1` |

v1.0 重点：§3 Matching Contract、§4 tolerance_frames、§9 主指标、§10 Guardrails、§11 Error-mode metrics、§17 Lineage、§18 Scoring Procedure、§19 Config Selection、§22 完整闭环。

v1.1 Patch 明确：除 Package-B Export 身份外，v1.0 的 matching / tolerance / Canonical GT / guardrail / Search Gate 全部继续有效。**v1.1 未覆盖 matching/scoring contract。**

```text
CALIBRATION_PROTOCOL_EFFECTIVE_VERSION = FROZEN_v1.1
MATCHING_RULE_ID = MAX_CARDINALITY_MIN_TOTAL_DISTANCE_ONE_TO_ONE_V1
TOLERANCE_FRAMES = 3
TOLERANCE_SECONDS = 0.15
TOLERANCE_IS_SEARCH_AXIS = NO
CONFIG_SELECTION_RULE = LEXICOGRAPHIC_CONSTRAINED
REPORT_AUTHORITY_CONFLICT = NO
```

---

## 2. Inputs

### Baseline Run

```text
run_id = g1_calibration_20260918_141032_781e5d8b
run_stage = CALIBRATION
set_role = CALIBRATION
search_stage = BASELINE
episode_count = 12
config_hash = dde590e759a31cb8c865369e18256ebecbbd01bc94a58e1d3ca695bb50f2a630
signal_contract_hash = 24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d
PARAMETER_DIFF_COUNT = 0
VALIDATOR = PASS
Final semantics = MATERIALIZED_V1
```

### Canonical GT Snapshot

```text
canonical_gt_snapshot_id = g1_canonical_gt_20260918_131636_c9916b89
episode_count = 12
canonical_gt_count = 56
known_fp_anchor_count = 10
conflicts = 0
gt_spacing_warn = false
min_gt_spacing_frames = 9
```

---

## 3. Existing Capability Audit

项目中原先没有正式 matching engine / baseline scoring engine / scoring artifact contract。Canonical GT 只冻结了 `matching_rule_id` 与 `T=3` provenance，**未执行 matching**。

本轮只新增最小正式能力：

- `src/project2_g1/boundary_matching.py`
- `src/project2_g1/baseline_scoring.py`
- `scripts/run_g1_baseline_scoring.py`
- `tests/test_g1_boundary_matching.py`
- `tests/test_g1_baseline_scoring.py`

未重构 G1 Detector pipeline。

Matching 实现：在 frame-sorted 序列上的 **non-crossing DP**。一维 L1 + `|Δ|≤T` 下，交叉 matching 可非交叉化且保持合法性、不增加总距离、并得到 lexicographically 更小的 `(gt_frame, pred_frame)` list，因此三级目标（max cardinality → min total distance → lex-min pair list）由该 DP 严格取得。禁止 greedy nearest。

---

## 4. Matching / Main Metrics

```text
TP = 56
FP = 10
FN = 0
EXACT_TP = 56
NEAR_TP = 0

Precision = 56/66 = 0.8484848484848485
Recall = 1.0
F1 = 112/122 = 0.9180327868852458
```

Matching 按 `(episode_id, frame)` + 冻结规则；不使用 `boundary_id` 相等、不按 candidate type 过滤、不跨 Episode。

Zero-denominator：项目没有既有 P/R/F1 0/0 convention。实现遇到 0 分母会 `REPORT_METRIC_ZERO_DENOMINATOR_CONTRACT_GAP` 并停止。本轮官方 12-Episode 路径未出现 0 分母。

---

## 5. Localization

```text
mean_frames = 0.0
median_frames = 0.0
p90_frames = 0.0
max_frames = 0
mean_seconds = 0.0
```

NEAR_TP 仍计 TP，不记 FP。本轮全部为 EXACT。

---

## 6. Episode / Over-segmentation

```text
episode_oversegmented_count = 4
total_oversegmentation = 10
mean_pred = 5.5
mean_gt = 4.666666666666667
```

Over-segmented episodes：

| episode | n_gt | n_pred | over |
|---|---:|---:|---:|
| `data/demo_162` | 3 | 4 | 1 |
| `data/demo_242` | 6 | 10 | 4 |
| `data/demo_255` | 6 | 8 | 2 |
| `data/demo_278` | 6 | 9 | 3 |

其余 8 条 over = 0。与 sanity expectation 一致；未硬编码。

---

## 7. Guardrails

命中来自正式 GT↔Prediction matching，不是第二套 type-aware matching。prediction representative type 不要求等于 GT class。

```text
CALIBRATION_GRIPPER_RECALL = 1.0          (10/10 GRIPPER_PRIMARY)
CALIBRATION_MERGED_CLUSTER_RECALL = 1.0   (26/26 MERGED_GRIPPER_CLUSTER)
SEED_VALID_DIRECTION_RECALL = 1.0         (6/6 SEED + VALID_DIRECTION_PRIMARY)
FRESH_VALID_DIRECTION_RECALL_BASELINE = 1.0  (11/11 FRESH + VALID_DIRECTION_PRIMARY)
FN_BASELINE = 0
```

以上均从 matching 结果计算，不是常量写死。

---

## 8. Known FP / Error Modes

```text
KNOWN_FP_ANCHOR_TOTAL = 10

MODE_01: remaining = 3  fixed = 0
MODE_02: remaining = 3  fixed = 0
MODE_03: remaining = 1  fixed = 0
UNASSIGNED: remaining = 3  fixed = 0

NEW_UNANCHORED_FP = 0
```

Anchor scope = 全部 `known_false_positive_anchor`（含 UNASSIGNED）。§5.3 已把 UNASSIGNED 列为 known-FP `error_mode`；Fresh 3 条是正式锚点，不得称为 NEW FP。

```text
REPORT_ANCHOR_SCOPE_CONTRACT_CONFLICT = NO
```

FP↔anchor 使用同一套 max-cardinality / min-distance / lex one-to-one，T=3。不用旧 `boundary_id` 判定。

---

## 9. Fragmentation

```text
1_2_frame_segment_ratio = 0.0    (0 / 78 segments)
segments_per_episode = 6.5
short_segment_ratio = NOT_COMPUTED_CONTRACT_GAP
FRAGMENTATION_SHORT_RATIO_CONTRACT_GAP = YES
```

`min_segment_length=8` 仍为 EXPLORATORY，Frozen Protocol 未冻结 short_segment threshold，因此不发明阈值。该 gap **不阻断** 核心 Baseline Scoring。

---

## 10. Artifacts

```text
score_id = g1_baseline_score_20260918_155714_42295cc6
score_root = outputs/g1_p3_scoring/g1_baseline_score_20260918_155714_42295cc6
metric_version = P2_G1_CALIBRATION_SCORING_V1
```

文件：

- `score_meta.json`
- `matching_pairs.csv`
- `unmatched_predictions_fp.csv`
- `unmatched_gt_fn.csv`（header only，0 rows）
- `episode_metrics.csv`
- `guardrail_metrics.json`
- `known_fp_anchor_status.csv`
- `baseline_metrics.json`

写入方式：temp directory → write → validate → atomic rename。已有 score_id 禁止 overwrite。

---

## 11. Validation / Tests

```text
tests.test_g1_boundary_matching  = 12 OK
tests.test_g1_baseline_scoring   = 15 OK
schema = PASS
matching_contract = PASS
provenance = PASS
immutability = PASS
```

Matching 覆盖：exact / near / outside ±3 / one-GT-many-pred / greedy 更少 TP 的 overlap / min distance / lex tie-break / 禁止跨 Episode / empty GT / empty pred / brute-force oracle。

Scoring 覆盖：snapshot identity、run identity、12 exact-set、config/signal hash、T=3、GT spacing、TP/FP/FN、P/R/F1、localization、episode metrics、guardrails、known-FP remaining/fixed、UNASSIGNED、NEW_UNANCHORED_FP、empty FN schema、artifact round-trip、immutability。

---

## 12. Immutability

| 对象 | 结果 | fingerprint |
|---|---|---|
| Baseline Run | PASS | `run_meta` `4a9b5e973e5c093e554488b45bcfbc1ecfa006bce04da9b1a0a3a6a18de172e8` |
| Canonical GT Snapshot | PASS | `335a8d62d9871e26f34a6e887206cbb48504dfc551337c024086e7252ac399ef` |
| Seed Export | PASS | `8ba31e9721ee3554b3b56b3bc46ff041c175b39865ea76c918f931b0a6d355c7` |
| Fresh Export | PASS | `01a3c732ae8b193a72ede845363105d0742b2f8357685e1f61d0a1b52dc3eb1f` |
| Owner SQLite | PASS | `076b3fe1504b23334cc861b32fb3145efaa92f187aa4002be1afcee7bc96c718` |
| Frozen Protocol v1.0 | PASS | `d75c05d7a0cad0ba2298225745314af7a313ad70e19d331b3b49205fb7e81c1a` |
| Frozen Protocol v1.1 | PASS | `011eab45065026d2c697daafa06826c80c873129c687bd97799a95e9af4ef175` |
| Dataset | PASS | before/after hash match |

本轮 Source 全部 READ ONLY。只新增 scoring artifact。

---

## 13. Explicit Non-Scope

```text
DETECTOR_MODIFIED = NO
CONFIG_MODIFIED = NO
THRESHOLD_MODIFIED = NO
PERSISTENCE_MODIFIED = NO
CONSOLIDATION_MODIFIED = NO
TOLERANCE_MODIFIED = NO
CANONICAL_GT_MODIFIED = NO
HUMAN_REVIEW_MODIFIED = NO
STAGE_A0_EXECUTED = NO
PARAMETER_SEARCH_EXECUTED = NO
EVALUATION_EXECUTED = NO
```

---

## 14. Gate / Final Status

```text
BASELINE_SCORING = FROZEN
NEXT_GATE = STAGE_A0_DIRECTION_CANDIDATE_DISCRIMINABILITY_AUDIT
PARAMETER_SEARCH = FORBIDDEN until STAGE_A0 = PASS

G1_BASELINE_SCORING = PASS_READY_FOR_STAGE_A0
MANDATORY_STOP = YES
```

STOP。不执行 Stage A0。不调任何参数。
