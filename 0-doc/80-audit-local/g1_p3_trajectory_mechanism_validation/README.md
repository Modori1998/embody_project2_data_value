# G1-P3 Trajectory Mechanism Validation — Diagnostic Set

```text
DIRECTORY_ROLE = G1_P3_TRAJECTORY_MECHANISM_DESIGN_DIAGNOSTIC_SET
DATASET_ROLE   = DESIGN_DIAGNOSTIC_SET
DESIGN_VERSION = FROZEN_TARGETED_MATCHED_DIAGNOSTIC_V1
SELECTION      = RANK_BASED_BLINDED_MATCHED
SOURCE_OF_TRUTH = GITHUB_MAIN

MUST_NOT_ENTER_CALIBRATION_GT            = YES
MUST_NOT_ENTER_EVALUATION_GT             = YES
MUST_NOT_BE_USED_FOR_THRESHOLD_SELECTION = YES
NO HUMAN LABEL YET                       = YES
FORMAL_DETECTOR_INPUT                    = NO
```

---

## 1. Purpose

本目录是一个 **Design Diagnostic Set｜设计诊断集**，只回答 Frozen Validation
Design §2 的唯一主问题：

> 在**后段运动已经足够持续**（P12 较高）的新 Direction candidates 中，
> **较低 Trajectory Coherence（C12 低）** 是否确实更容易富集人工判定的
> **REDUNDANT** boundary？

中文：

> 在后续运动已经足够持续的前提下，轨迹一致性差，是否真的更容易代表
> “回摆 / 绕动 / jitter / detour 导致的不应独立切段”？

本目录**不**回答、也**禁止**被用来回答：

- P12 / C12 的 numeric threshold；
- 最终 Detector F1；
- 最终 Calibration threshold；
- Event Consolidation / Gripper proximity rule；
- Independent Evaluation。

```text
PRIMARY_HYPOTHESIS = LOW_C12_ENRICHES_REDUNDANT_GIVEN_HIGH_P12
```

本目录**没有任何人工标签**，也不包含任何 review 结果。

---

## 2. Frozen Design Source

```text
0-doc/10-design-review/
  Project2_G1_P3_Trajectory_Mechanism_Validation_Design_FROZEN_v1_20260921.md
  DOCUMENT_STATUS = FROZEN_VALIDATION_DESIGN_v1
  FROZEN_DESIGN_COMMIT = ff2a33cf4b956eb57d11dd608d3b3fbd67d602d0
```

上游权威（只读）：

```text
0-doc/10-design-review/
  Project2_G1_P3_Motion_Sufficiency_Rule_Shape_FROZEN_v1_20260921.md
0-doc/80-audit-local/
  Project2_G1_P3_Motion_Sufficiency_Operationalization_Preparation_Result_20260921.md
0-doc/80-audit-local/g1_p3_rule_analysis/03_motion_sufficiency_operationalization_event.csv
0-doc/80-audit-local/g1_p3_rule_analysis/04_motion_sufficiency_operationalization_summary.csv
```

本设计**不**冻结 P12 / C12 的 Detector 定义：

```text
P12_DETECTOR_DEFINITION_FROZEN = NO
C12_DETECTOR_DEFINITION_FROZEN = NO
WINDOW_FROZEN_AS_FINAL_CONFIG  = NO
```

本目录中的 P12 / C12 只用于**让新样本选择规则固定、可复现**。

---

## 3. Candidate Source Provenance

```text
baseline_run_id        = g1_calibration_20260918_141032_781e5d8b
config_version         = g1_p2_exploratory_segmentation.v0
config_hash            = dde590e759a31cb8c865369e18256ebecbbd01bc94a58e1d3ca695bb50f2a630
segmentation_version   = G1-P2-EXPLORATORY-v0
signal_contract_version= g1_p1_signal_contract.v0
signal_contract_hash   = 24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d
source_dataset_id      = robomimic_v15_can_mh
```

**没有**任何既有的全数据 / 大范围 Final Boundary materialization 可复用：
现有所有 audit run 只覆盖 12 个 Calibration episode。

因此本轮执行一次 **READ_ONLY_BASELINE_MATERIALIZATION**：

```text
DETECTOR_CODE_CHANGE = NO
CONFIG_CHANGE        = NO
PARAMETER_CHANGE     = NO
```

即**原样运行既有 frozen baseline Detector**（`run_boundary_engine` + 既有
`compute_formal_signals`），在内存中收集 Final Boundaries，**不落盘任何
per-episode 产物**（不写 PNG / 不写视频），只为构建候选池。

覆盖范围：数据集中全部 **300** 个 episode 中的 **288** 个非 Calibration episode。

候选池构造语义**逐字复用** Stage A0 的 frozen 派生函数
（`lineage_for_final` / `derive_run_length`），未重新实现：

```text
is_independent_direction_final =
    final.candidate_type == "DIRECTION_CHANGE"
    and not (member_candidate_count >= 2 and "GRIPPER_TRANSITION" in member_candidate_types)
```

> **交叉验证**：把同一语义应用到 12 个 Calibration episode 上，
> 得到 **26** 个 Direction Final Boundaries —— 与冻结的 Calibration
> Direction cohort（17 VALID + 9 DIRECTION_FP）**完全一致**。
> 该计数在脚本中作为硬门控（`EXPECTED_CALIBRATION_DIRECTION_FINALS = 26`），
> 不一致即 fail-fast。

---

## 4. Calibration Episodes Excluded

从 GitHub SSOT artifact 恢复（非硬编码信任）：

```text
outputs/g1_p3_canonical_gt/g1_canonical_gt_20260918_131636_c9916b89/
  combined_calibration_manifest.json
```

```text
CALIBRATION_EPISODES_EXCLUDED = 12

SEED  : demo_0, demo_32, demo_179, demo_230, demo_242, demo_278
FRESH : demo_150, demo_162, demo_213, demo_255, demo_260, demo_270
```

SSOT 名单与 Frozen Validation Design §3 完全一致，**无差异**。

**Human Review 覆盖范围校验**：脚本读取
`outputs/g1_audit_web/g1_audit_run_registry.json`，检查所有已注册 audit run
实际打开的 episode 并集：

```text
union_of_run_covered_episodes        = 12
covered_episodes_outside_calibration = 0
```

即**不存在任何已人工审核、但位于 Calibration 集之外**的 episode，
因此 episode 级排除已完整覆盖 Frozen Design §4 的
“已进入现有 Calibration 的 event”与“已人工审核并用于 Rule Discovery 的 event”。

> 只读取 run registry JSON 与 run 目录名，**不读** review 数据库，
> **不**把任何 review 数据当作 candidate source。

---

## 5. Candidate Filtering

候选池只包含 **independent Direction Final Boundary**。

排除规则（**固定优先级顺序**，用于确定 exclusion 计数归属）：

| # | 排除 | Reason code | 说明 |
|---|---|---|---|
| 1 | 非 independent Direction final | `GRIPPER_PRIMARY_MERGED_FINAL` | Gripper-primary merged Final Boundary |
| 2 | 左右上下文不足 12 帧 | `EDGE_CONTEXT_INCOMPLETE` | `event_frame < 12` 或 `n_frames - event_frame < 12` |
| 3 | 距最近 gripper final ≤ 12 帧 | `NEAR_GRIPPER_CONSOLIDATION_CONTEXT` | 隔离 Event Consolidation |
| 4 | `path_length < 1e-9` | `DEGENERATE_TRAJECTORY_CONTEXT` | 退化轨迹，输出 NaN 而非异常大值 |
| 5 | `run_length` 不可得 | `RUN_LENGTH_NOT_AVAILABLE` | matching 变量缺失 |

非 Direction 的 Final Boundary（`GRIPPER_TRANSITION`）在池构造阶段即排除，
不进入上表，单独计数。

### 5.1 Consolidation Isolation（Frozen Design §4）

```text
distance_to_nearest_gripper_final <= 12 frames  ->  EXCLUDED
```

这是 **DIAGNOSTIC_SELECTION_EXCLUSION**，
**不是** Detector Rule，也**不**冻结为 Detector 参数。

### 5.2 Edge Context（Frozen Design §10）

```text
left_context_frames  = event_frame
right_context_frames = n_frames - event_frame
要求：两者均 >= 12
```

不足则 `EDGE_CONTEXT_INCOMPLETE = YES` 并从 eligible pool 排除。
原因：本次比较的是 C12 mechanism，不同窗口长度不能混进同一个 rank pool。
这是 **Diagnostic Set data-quality rule**，不是 Detector edge policy。

对 edge-incomplete 的候选，P12 / C12 **不输出数值**（NaN），
避免用不完整窗口伪造特征值。

---

## 6. P12 — Sustained Post-motion Context

```text
P12 = median(translation_speed_mps)
      over relative_frame ∈ [+4, +12]      （9 帧，含端点）
```

- 只使用现有 Formal signal `translation_speed`；
- 严格 **median**，窗口严格 `[+4, +12]`；
- **禁止**替换为 mean / local_speed_min / P8 / 其它窗口。

---

## 7. C12 — Trajectory Coherence

基于 EEF translation：

```text
left  window: relative_frame ∈ [-12, -1]
right window: relative_frame ∈ [0, +11]

path_length      = Σ step_displacement_m
net_displacement = norm(Σ [step_dx, step_dy, step_dz])
straightness     = net_displacement / path_length
C12              = min(left_straightness, right_straightness)

path_length < 1e-9  ->  NaN  ->  DEGENERATE_TRAJECTORY_CONTEXT（排除）
```

**公式保真校验**：对 4 个 Calibration 事件逐条重算，与冻结的
`02_direction_event_window_trace.csv` **逐位一致**：

| event | left_straightness | right_straightness | C12 | P12 |
|---|---|---|---|---|
| `demo_242@41` | 0.958475 ✓ | 0.910406 ✓ | 0.910406 ✓ | 0.038618 ✓ |
| `demo_242@60` | 0.747618 ✓ | 0.862719 ✓ | 0.747618 ✓ | 0.075062 ✓ |
| `demo_162@211` | 0.552866 ✓ | 0.889920 ✓ | 0.552866 ✓ | 0.115593 ✓ |
| `demo_255@14` | 0.911370 ✓ | 0.948511 ✓ | 0.911370 ✓ | 0.163873 ✓ |

---

## 8. Rank-based Selection（无 Calibration Threshold）

本轮**禁止**使用 Calibration 中的
`0.045 / 0.050 / 0.75 / 0.76 / VALID_FLOOR` 来筛选新样本。
所有 percentile 只来自**新的 DESIGN DIAGNOSTIC CANDIDATE POOL**。

Percentile 定义（升序秩百分位）：

```text
percentile(value) = rank_index / (n - 1)        （按 (值, episode_id, event_frame, boundary_id) 排序）
最低值 -> 0.0 ；最高值 -> 1.0
```

### 8.1 P12 Eligibility

```text
P12_ELIGIBLE_POOL = percentile_P12 >= 0.50      （在 eligible pool 内）
```

即按 P12 排序的 **top 50%**。这是 **selection percentile，不是 Detector threshold**。

### 8.2 两个 Diagnostic Arm

在 `P12_ELIGIBLE_POOL` 内**重新计算** C12 percentile：

| Arm | 内部含义 | 定义 |
|---|---|---|
| **Arm A** | Low Coherence **Target** | `C12_percentile <= 0.25`（bottom 25%） |
| **Arm B** | High Coherence **Control** | `C12_percentile >= 0.75`（top 25%） |

---

## 9. Matching

Arm B 不是随便挑高 C12，而是逐个匹配 Arm A。

```text
MATCH_DISTANCE =
    |Δ P12 percentile|
  + |Δ direction_evidence percentile|
  + |Δ run_length percentile|
```

三个 percentile 均在 `P12_ELIGIBLE_POOL` 内计算（与 arm 构造同一参照池）。

对每个 Arm A event，在当前**未被使用**的 Arm B candidate 中选择
`MATCH_DISTANCE` 最小者；tie-break：`episode_id ASC, event_frame ASC`。
每个 Arm B candidate 只能使用一次。**禁止使用 human label 参与匹配。**

**工程决定（设计未指定，本目录明确记录）**：Arm A 的匹配迭代顺序采用
Arm A 的构造顺序（C12 ASC, episode_id ASC, event_frame ASC）。
Frozen Design §10 只规定“逐个 greedy”，未规定遍历顺序；本目录固定为上述顺序以保证确定性。

---

## 10. Episode Diversity Rules

```text
TARGET_PER_ARM               = 10
ALLOWED_RANGE_PER_ARM        = 8 .. 12
MIN_PER_ARM                  = 8
MAX_SELECTED_EVENTS_PER_EPISODE = 1
NO_EPISODE_SHARED_BETWEEN_ARMS  = YES
```

Arm A 按 `C12 ASC, episode_id ASC, event_frame ASC` 扫描，**每个 episode 最多一个**。

Arm B 的 control episode **不得**等于任何 Arm A episode（Arm A 的全部 episode
在匹配开始前即被整体保留），也**不得**已被任何其它 selected event 使用。

若 `matched_pairs < 8`：

```text
VALIDATION_SET_BUILD = INSUFFICIENT_DIVERSITY   （STOP，不硬凑样本）
```

---

## 11. Blinding Contract

`03_selection_blinded.csv` 是未来 Web review 的**唯一 selection manifest**，
只包含必要身份信息：

```text
diagnostic_event_id, episode_id, boundary_id, event_frame,
event_type, representative_candidate_id, member_candidate_ids, diagnostic_set_id
```

**不得**包含：arm、P12、C12、rank percentile、match_distance、hypothesis、
expected label。

自动审计（大小写不敏感、整文件子串扫描）禁止 token：

```text
arm, p12, c12, coherence, target, control, match_distance,
low, high, expected, redundant, valid
```

出现任一 token 即 `STOP / BLINDING_CONTRACT_VIOLATION`。

`02_selection_internal.csv` 是 **Engineering Audit artifact**，
**禁止**在未来人工 Review 页面展示。

> 注意：`diagnostic_set_id` 与 `DESIGN_VERSION` 不写入 blinded manifest ——
> `FROZEN_TARGETED_MATCHED_DIAGNOSTIC_V1` 含 `TARGETED`，
> 会命中禁止 token `target`。

---

## 12. Future Review Restrictions

未来人工审核必须：

- 建立**独立** `run_id`，`run_stage = DESIGN_DIAGNOSTIC`（或等价不可混淆 stage）；
- 仍走 append-only Web review；
- 只显示 blinded manifest 提供的内容；
- 允许 label 仅 `VALID / REDUNDANT / MISALIGNED`；
- REDUNDANT 继续使用既有 reason taxonomy，**不得**新增会泄露假设的标签
  （例如 `LOW_C12`）；
- 导出 immutable diagnostic export；
- **不得**把 diagnostic review 写回现有 Calibration GT。

审核完成后只比较：

```text
REDUNDANT_RATE_ARM_A  vs  REDUNDANT_RATE_ARM_B
REDUNDANT_RATE = REDUNDANT / reviewed events
```

MISALIGNED 单独报告，**不得**偷偷算成 REDUNDANT。

判定门槛已在 Frozen Design §15 预先冻结，审核后**不得**再改口径。

---

## 13. Files

| File | Rows | Columns | Canonical LF SHA256 |
|---|---:|---:|---|
| `01_candidate_pool.csv` | 511 (+header) | 30 | `2d63c86156c773e59f6bbc9baee9458fe3abcfa14194203cc761fb806a2754e8` |
| `02_selection_internal.csv` | 20 (+header) | 18 | `7588a0650bdf75493d2eec3780fb0e0a7ce6b3a64af667db827faf305473d9f8` |
| `03_selection_blinded.csv` | 20 (+header) | 8 | `bfa63c28c22050a0d9ba64e55e5c9a412ad8be87145322f08f370cde7f86aaee` |

`01_candidate_pool.csv` **不含任何 human label**：没有
`human_class` / `VALID` / `FP` / review 结果列。

### Canonical bytes / line endings

```text
line endings = LF (\n) only, no CR
no BOM
encoding     = UTF-8
```

导出脚本**自行渲染 CSV**（显式 `\n`），不依赖 `csv.writer` 默认 CRLF，
也不依赖 `core.autocrlf`。复核哈希时以 **repo blob**
（`git cat-file blob <oid>` / GitHub 原始文件）为准。

---

## 14. Validation

```text
candidate_pool_rows              = 511
duplicate_key                    = 0
inf                              = 0
NaN                              = 4（全部为 EDGE_CONTEXT_INCOMPLETE，且全部已排除）
selected_events                  = 20
Arm A / Arm B                    = 10 / 10
distinct_episodes                = 20
episode_reuse                    = 0
calibration_leakage              = 0
selected_min_gripper_distance    = 13（> 12）
selected_edge_incomplete         = 0
selected_NaN                     = 0
BLINDING_CONTRACT                = PASS
determinism (--check)            = PASS（byte-identical, LF preserved）
```

---

## 15. Reproduce

```bash
python scripts/build_g1_trajectory_mechanism_diagnostic_set.py
python scripts/build_g1_trajectory_mechanism_diagnostic_set.py --check
python -m unittest tests.test_g1_trajectory_mechanism_diagnostic_set
```

依赖：`numpy` + `h5py`（读 READ_ONLY raw HDF5）+ `matplotlib`
（`stage_a0_analysis` 的传递依赖，用于复用 frozen 派生函数）。

`--limit-episodes N` 仅供调试；正式产物必须不带该参数运行。

---

## 16. Non-Scope

```text
NO DETECTOR MODIFICATION
NO SEGMENTATION CHANGE
NO CANDIDATE GENERATION CHANGE
NO CANDIDATE ACCEPTANCE CHANGE
NO EVENT CONSOLIDATION CHANGE
NO CONFIG GENERATION
NO NUMERIC THRESHOLD SELECTION
NO CALIBRATION VALID_FLOOR USAGE
NO CLASSIFIER / NO DECISION TREE / NO AUTO FEATURE SEARCH
NO PRIVILEGED SIMULATOR STATE
NO WEB SQLITE AS CANDIDATE SOURCE
NO HUMAN LABEL
NO HUMAN REVIEW EXECUTED
NO CALIBRATION GT CHANGE
NO EVALUATION GT CHANGE
NO PROTOCOL PATCH
NO MASTER / ROADMAP UPDATE
```

本目录在**设计阶段**不给出 C12 supported / not supported 的结论；该结论只能在
人工审核完成后，由 `REDUNDANT_RATE_ARM_A vs REDUNDANT_RATE_ARM_B` 比较给出。
该审核已完成，结果见 §17。

---

## 17. Review Result & Frozen History

人工审核已完成，两套读数与完整追加历史已冻结：

| 文件 | 角色 |
| --- | --- |
| `05_review_history.csv` | 20 个 boundary 的**完整** append-only 审核历史（保留每一个 revision） |
| `05_owner_adjudication_result.md` | 官方结果记录（blinded 与 owner-adjudicated 两套读数 + 冻结门逐项判定） |

关键读数：

```text
BLINDED_GATE_RESULT           = NOT_SUPPORTED_AS_GENERAL_ACCEPTANCE_COMPONENT
                                (LOW 1/10 = 10%, HIGH 1/10 = 10%)
OWNER_ADJUDICATED_GATE_RESULT = SUPPORTED_FOR_PROTOCOL_PATCH_REVIEW
                                (LOW 4/10 = 40%, HIGH 0/10 = 0%)
```

`05_review_history.csv` 由以下脚本生成，可确定性重建：

```text
python scripts/export_g1_p3_diagnostic_review_history.py
python scripts/export_g1_p3_diagnostic_review_history.py --check   # 只校验不写
```

冻结约定：

```text
SORT_ORDER   = diagnostic_event_id ASC, review_id ASC
ENCODING     = UTF-8 (no BOM), LF
COLUMN_ORDER = diagnostic_event_id, episode_id, boundary_id, event_frame,
               arm, pair_id, P12, C12,
               review_id, reviewer, reviewed_at,
               human_decision, reason_code, corrected_frame, comment, review_phase
PROVENANCE   = reviewer=DESIGN_OWNER           -> FIRST_BLINDED_REVIEW
               reviewer=DESIGN_OWNER_UNBLINDED  -> OWNER_UNBLINDED_ADJUDICATION
```

`review_phase` 只由存储的 reviewer 身份推导，**不**由时间戳猜测；未登记的
reviewer 直接报错而非静默导出。`arm` / `pair_id` / `P12` / `C12` 来自
`02_selection_internal.csv`，**不**来自人工审核数据库。

本目录仍**不**构成 threshold、detector 或 evaluation 结论；详见
`05_owner_adjudication_result.md` §8 Interpretation Boundary。
