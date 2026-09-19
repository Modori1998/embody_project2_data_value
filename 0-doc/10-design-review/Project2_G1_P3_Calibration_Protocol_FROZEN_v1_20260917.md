# Project 2 G1-P3 Calibration Protocol FROZEN v1

```text
DATE = 2026-09-17
DOCUMENT_STATUS = FROZEN_v1.0
FROZEN = YES
SOURCE_DRAFT = Project2_G1_P3_Calibration_Design_DRAFT_v1_20260917.md
OWNER_REVIEW = PASS
OWNER_DECISION_DATE = 2026-09-17
TASK = G1-P3 CALIBRATION PROTOCOL
IMPLEMENTATION_STATUS = NOT_STARTED
DETECTOR_MODIFIED = NO
THRESHOLD_MODIFIED = NO
PARAMETER_SEARCH_EXECUTED = NO
GRID_SEARCH_EXECUTED = NO
CALIBRATION_RUN_GENERATED = NO
EVALUATION_RUN_GENERATED = NO
SQLITE_WRITTEN = NO
HUMAN_RELABEL = NO
EXPORT_IMPLEMENTED = NO
OPTIMAL_CONFIG_SELECTED = NO
```

最终状态：

```text
G1_P3_CALIBRATION_PROTOCOL =
FROZEN_READY_FOR_BATCH3_AND_CALIBRATION_SET_BUILD
```

本文件冻结的是 **怎么校准**，不是“已经完成校准”。截至本文件冻结时，尚未修改 Detector、尚未搜索参数、尚未生成正式 Calibration / Evaluation 结果。

---

# 0. Authority Confirmation

本 Protocol 以 Google Drive 当前权威稿与已完成人工审计为事实源：

| 文档 | Drive fileId | 对本轮的约束 |
| --- | --- | --- |
| `Project_2_Engineering_Design_Master_v1_20260914.md` | `1Cd05zSFR6IF8rXby6RYmocZbmrUDH05b` | G1-D Human Calibration Loop；Calibration / Evaluation 必须隔离；Hard Boundary Recall 优先于单一总分 |
| `Project2_Development_Roadmap_and_Design_Gate_Plan_v1_20260914.md` | `1lQd5Nn4jxwiqwylEg40tCAl1jwDg5O6t` | G1-P3 = Human Calibration Loop；首版 Calibration 目标 10–20；coarse→fine；Evaluation 使用冻结 config |
| `02_robot_demonstration_mining_autolabel_design.md` | `1tgMOxq2_0taUT7LdHDsn4nvEqookCdAI` | Calibration Set ≠ Evaluation Set；参数必须基于 Human Calibration 冻结 |
| `Project2_G1_Human_Audit_Web_Design_FROZEN_v1_20260916.md` | `1v6ZtopYFfCIWG9kjCOmwJe2C-XWB4xRR` | P3 消费 `P2_G1_HUMAN_CALIBRATION_EXPORT_V1`；不直接读 SQLite；`boundary_id` 仅 RUN_STABLE_ONLY |
| `Project2_G1_Human_Review_Error_Attribution_Audit_20260917.md` | `177ngPA1W6Xt5BlJAKW_tgabMww9BFJxb` | 6 条 Exploratory 人工审核完整；P1 全 PASS；P2 24 VALID / 7 REDUNDANT；主要问题为 Direction FP |

冻结前事实：

```text
RUN_ID = g1_exploratory_audit_20260917_141541_fe251439
run_stage = EXPLORATORY_AUDIT
set_role = EXPLORATORY
EPISODES = 6
P1 = 36 PASS / 0 FAIL / 0 UNCERTAIN / 0 NOT_REVIEWED
P2 = 31 Final / 24 VALID / 7 REDUNDANT / 0 MISALIGNED / 0 MISSED
```

当前 6 条源 Run 的身份保持不变，不得把源 Run 改名为 `CALIBRATION` 或 `EVALUATION`。

## 0.1 Owner Review｜Draft → Frozen 决策差异

Design Owner 已拍板以下变更；这些决定取代 DRAFT v1 中对应的 `OWNER_DECISION_REQUIRED`：

1. **Matching Rule｜匹配规则**：从 greedy nearest 改为 `MAX_CARDINALITY_MIN_TOTAL_DISTANCE_ONE_TO_ONE`；先最大化 TP 数，再最小化总定位误差。
2. **Tolerance｜匹配容差**：冻结为 `±3 frames`，在 20 Hz 下为 `±0.15 s`；它是 metric contract，不是搜索轴。
3. **Calibration Seed｜校准种子**：当前 6 条 Exploratory 全部进入 Calibration Seed；保留完整 provenance；永久禁止进入 Evaluation。
4. **Calibration Set 大小**：冻结为 `12 Episodes = 当前 6 条 Seed + 6 条全新 Calibration Episode`。
5. **Search Gate｜搜参门禁**：12 条全部完成 Human Review、Export 与 Canonical GT freeze 之前，禁止参数搜索。
6. **Direction Guardrail｜方向保护约束**：Seed 中 6 条已知合法独立 Direction 必须 `HARD=100%`；新增 6 条上的合法 Direction 采用 `HARD NON-REGRESSION vs baseline`。
7. **Batch 3 Export**：允许先导出当前 6 条作为第一包；但该 Seed Export 不打开 Search Gate。
8. **Stage A0**：正式 Stage A 搜参前新增 `Direction Candidate Discriminability Audit｜方向候选可分性审计`；若现有 Formal Signal / candidate 属性不能支持可解释区分，必须返回 Design Review，而不是机械扫参数。

除上述 Owner 决策外，DRAFT v1 的 Canonical GT、Calibration/Evaluation 隔离、分阶段搜索、Config Selection 与 Stop Rule 的总体方向保持不变。

---

# 1. 本轮范围 / 禁止事项

本 FROZEN Protocol 冻结 **Calibration 的数据、GT、matching、metric、guardrail、search、selection、stop 与 evaluation 规则**；它本身不执行校准。

截至冻结时禁止且尚未发生：

```text
修改 Detector
修改 threshold / persistence / consolidation
执行 parameter search / grid search
生成用于选参的新 Detector 结果
选择最优 config
修改 Human Review SQLite
重新标注当前 6 条
生成正式 Evaluation Run
```

冻结后允许按顺序进入：

```text
Batch 3 Seed Export
→ 新 6 条 Calibration Episode 选择与 baseline audit run
→ 新 6 条 Human Review
→ Fresh Export
→ Combined Canonical GT Snapshot（12 条）
→ Baseline Scoring
→ Stage A0
→ Stage A / B / C Calibration
```

任何实现若与本 Protocol 冲突，必须停止并回到 Design Review；不得由 Implementation 层静默改协议。

---

# 2. 当前 Exploratory 事实基线

来源：Error Attribution Audit 20260917；不重新解释、不升级角色。

```text
EPISODES = 6
P1: 36 PASS / 0 FAIL / 0 UNCERTAIN / 0 NOT_REVIEWED
P2: FINAL_TOTAL=31  VALID=24  REDUNDANT=7  MISALIGNED=0  MISSED=0
```

保护行为：

```text
GRIPPER_TRANSITION Primary     18 VALID / 0 REDUNDANT
DIRECTION_CHANGE Primary        6 VALID / 7 REDUNDANT
GRIPPER + DIRECTION merged      全部 VALID
```

错误画像：

| Mode | 机器对象 | Human | Count | Evidence |
| --- | --- | --- | ---: | --- |
| MODE_01 | DIRECTION jitter → 独立 Final | REDUNDANT_DIRECTION_JITTER | 3 | HIGH |
| MODE_02 | 人工 SHORT_PAUSE，机器 DIRECTION KEEP；pause_bridge 不参与 | REDUNDANT_SHORT_PAUSE | 3 | HIGH |
| MODE_03 | DIRECTION Final 距后续 GRIPPER cluster 10 frames；window=8 未合并 | REDUNDANT_SHORT_PAUSE | 1 | MEDIUM |

`evidence_value` 在 VALID 与 REDUNDANT 独立 DIRECTION 上重叠约 `1.47–2.64`。因此 **不得** 把「提高 direction threshold」当作默认解。

独立 VALID DIRECTION Final（必须保护）：

```text
demo_278-B0002 @23
demo_278-B0003 @39
demo_278-B0004 @52
demo_242-B0002 @20
demo_242-B0011 @224
demo_230-B0003 @108
```

独立 REDUNDANT DIRECTION Final（校准主目标）：

```text
MODE_01  demo_242-B0003 @41 / B0004 @60 / B0005 @78
MODE_02  demo_278-B0005 @83 / B0006 @105 / B0007 @125
MODE_03  demo_242-B0008 @136   (距 GRIPPER @146 = 10 frames)
```

本样本相邻独立 DIRECTION Final 最小间距约 13 frames（demo_278 VALID @39→@52）。MODE_01/02 错误链间距 18–22 frames。因此 ±3 / ±5 的 matching window **不会**把两个独立 physical event 配成一对；但不能用这 6 条拟合 tolerance，因为 MISALIGNED=0。

---

# 3. Boundary Matching Contract

## 3.1 匹配对象

正式 metric 比较：

```text
Canonical Human Boundary GT  (episode_id, gt_frame)
        ↕
Predicted Final Boundaries   (episode_id, pred_frame)
```

正式匹配 **不依赖** `old boundary_id / candidate_id / candidate_type`。`boundary_id` 仅在单次 Run 内稳定，不能作为跨 Run GT key。

## 3.2 正式 Matching Rule

```text
MATCHING_RULE_ID = MAX_CARDINALITY_MIN_TOTAL_DISTANCE_ONE_TO_ONE_V1
MATCHING_RULE = MAX_CARDINALITY_MIN_TOTAL_DISTANCE_ONE_TO_ONE
TOLERANCE_FRAMES = 3
```

同一 Episode 内：

1. 仅生成满足 `|pred_frame - gt_frame| <= 3` 的候选 pair；
2. 在所有合法 one-to-one matching 中，**第一目标最大化匹配对数量**，即最大化 TP；
3. 在 TP 数相同的 matching 中，**第二目标最小化** `Σ |pred_frame - gt_frame|`；
4. 若匹配数与总距离仍完全相同，采用 deterministic tie-break：将匹配 pair 按 `(gt_frame ASC, pred_frame ASC)` 排序，选择 lexicographically minimal 的 pair list；
5. 每个 predicted boundary 最多匹配 1 个 GT；每个 GT 最多匹配 1 个 prediction；禁止跨 Episode 匹配。

这取代 DRAFT v1 的 greedy nearest。原因：greedy 在 GT tolerance window 重叠时可能先占用一个局部最近 pair，从而减少本可获得的 TP 数；正式 metric 必须优先保证最大 matching cardinality。

实现可使用：

- dynamic programming｜动态规划；
- min-cost max-flow｜最小费用最大流；
- 或其他能严格满足上述两级目标与 deterministic tie-break 的算法。

实现算法属于 Implementation Detail；**输出规则不可变**。

## 3.3 为什么不用 Exact / 无一对一 / Type-aware

- `Exact Match`：1 frame = 0.05 s，过于严格；只保留为 `EXACT_TP` diagnostic。
- 单纯 `±T` 但不做 one-to-one：会让一个 prediction 命中两个 GT，或一个 GT 吃掉两个 prediction，禁止。
- `Type-aware matching`：不作为主匹配。Merged Cluster 的 representative type 可能随 consolidation 改变；type 只做 regression diagnostic。

## 3.4 TP / FP / FN / Localization

| 符号 | 冻结定义 |
| --- | --- |
| **TP** | 正式 one-to-one matching 中成功匹配的 pair |
| **FP** | 未匹配的 Predicted Final |
| **FN** | 未匹配的 Canonical GT |
| **Localization Error** | 每个 TP 的 `|pred_frame-gt_frame|`，同时记录 frame 与秒 |

`Matched-but-Misaligned` 不作为 F1 第四类。`0 < |delta| <= 3` 仍计 TP，但进入 Localization Error。

可选 diagnostic：

```text
EXACT_TP       |delta| = 0
NEAR_TP        0 < |delta| <= 3
UNMATCHED_PRED FP
UNMATCHED_GT   FN
```

## 3.5 Duplicate Prediction

若同一个 GT tolerance window 内出现多个 prediction，one-to-one matching 最多保留一个 TP，其余未匹配 prediction 为 FP。这正是 over-segmentation 的正式计分方式。

## 3.6 GT Collision Risk

若 Canonical GT 中存在：

```text
|gt_i - gt_j| <= 2 * T = 6 frames
```

则打：

```text
GT_SPACING_WARN = YES
```

并报告 `min_gt_spacing_frames`。Matching 仍按正式规则执行；不得临时放宽或缩小 T 来“修”分数。必要时 Design Owner 单独检查 GT 是否真是两个独立 physical transition。

## 3.7 Episode Start / End

`EPISODE_START / EPISODE_END` 默认不是 Canonical Human Boundary，也不是 Predicted Final 的匹配对象。若未来 Human Added 明确加在 frame 0 / last frame，则按普通 GT 处理，不另开特殊 tolerance。

## 3.8 主指标不按 Primary Type 过滤

Precision / Recall / F1 在全部 Predicted Final vs 全部 Canonical GT 上计算。Gripper、Direction、Merged Cluster 的类型信息只用于 guardrail / diagnostic slicing。

---

# 4. tolerance_frames 时间语义

当前数据采样：

```text
20 Hz
dt ≈ 0.05 s
```

冻结：

```text
TOLERANCE_POLICY = FIXED_PROTOCOL_CONSTANT
TOLERANCE_FRAMES = 3
TOLERANCE_SECONDS = 0.15
TOLERANCE_IS_SEARCH_AXIS = NO
```

物理语义：±3 frames（±0.15 s）用于吸收 representative peak、persistence 与 consolidation 锚点带来的小幅定位漂移，同时仍保持“同一瞬间 physical transition”的约束。DRAFT v1 的 ±5（±0.25 s）不采用为正式 metric tolerance，因为半秒级全窗口更容易覆盖相邻微操作。

重要约束：

- 这个 `3` **不是**从当前 6 条拟合出来的；当前 6 条 `MISALIGNED=0`，没有足够 localization 标注用于拟合 T；
- 这个 `3` **不是**沿用 exploratory schema 的 `boundary_tolerance_window=5`；
- T 一旦冻结，Calibration 与 Evaluation 全程相同，禁止为了某个 config 的 F1 更高而修改；
- Detector search 不得包含 `tolerance_frames`。

可以额外报告：

```text
DIAGNOSTIC_TOLERANCE_SWEEP = {1,2,3,5}
```

但它只能说明 metric sensitivity，不得用于选择 config，也不得替代正式 `T=3` 的结果。

---

# 5. Canonical Human Boundary GT

这是 G1-P3 的核心解耦：Human Review 绑定 **某次 run 的预测对象**；Calibration metric 绑定 **episode 上的人类认为应存在的切分时刻**。

## 5.1 正式规则

从一次已完成的 Human Calibration Export 构建：

| 源标签 | 是否进入 Canonical GT | `gt_frame` | `gt_source` |
| --- | --- | --- | --- |
| VALID | 是 | `predicted_frame` | `VALID_INHERIT` |
| MISALIGNED | 是 | `corrected_frame`（必填） | `MISALIGNED_CORRECTED` |
| REDUNDANT | **否** | — | 只留 provenance，作为 known-FP 诊断锚点 |
| MISSED / Human Added | 是 | `human_added_frame` | `HUMAN_ADDED` |
| NOT_REVIEWED | 阻断 | — | 该 episode 不得进入 Calibration scoring |

同一 `(episode_id, gt_frame)` 去重：保留更强来源。优先级：

```text
MISALIGNED_CORRECTED > HUMAN_ADDED > VALID_INHERIT
```

若去重后仍冲突，打 `CANONICAL_GT_CONFLICT` 并阻断该 episode。

## 5.2 Provenance 必须保留，metric 不得依赖

每条 Canonical GT 行至少：

```text
gt_id                      # episode 内稳定，例如 demo_278-HGT0002
episode_id
gt_frame
gt_source                  # VALID_INHERIT / MISALIGNED_CORRECTED / HUMAN_ADDED
protected_class            # GRIPPER_PRIMARY / VALID_DIRECTION_PRIMARY /
                           # MERGED_GRIPPER_CLUSTER / OTHER
source_run_id
source_boundary_id         # 可空（HUMAN_ADDED 无预测 id）
source_review_id
human_decision
reason_code
comment
```

`gt_id` 在 **同一次 Canonical GT snapshot** 内稳定。它不是 Detector `boundary_id`。新 Calibration Run 只通过 `(episode_id, gt_frame)` + matching rule 对齐。

## 5.3 已知-FP 锚点（不进 Recall 分母）

REDUNDANT 预测导出为 `known_false_positive_anchor`：

```text
episode_id
anchor_frame = predicted_frame
error_mode                 # MODE_01 / MODE_02 / MODE_03 / UNASSIGNED
source_boundary_id
reason_code
```

用途：每轮新 run 问「这个错误还在不在」。  
**不**把它们放进 Canonical GT，否则 Recall 会要求系统重新预测一条人类不要的边界。

## 5.4 该规则是否应成为正式 Canonical GT

```text
CANONICAL_GT_RULE = FROZEN
```

这应当成为正式规则。它直接解决「REDUNDANT 在新 run 消失、新 boundary_id 改变」之后无法打分的问题。

已知风险（必须写进 Owner Review，不是否决项）：

1. **VALID 继承了旧 representative 的帧偏。** 本样本 MISALIGNED=0，不代表 representative 已验证。若人类把略偏的帧标成 VALID，GT 会固化该偏。缓解：Localization Error 持续报告；若未来出现系统偏，走 Design Change，允许把一批 VALID 改标 MISALIGNED 后重建 Canonical snapshot（新 snapshot id，不覆盖旧 GT）。
2. **REDUNDANT 若其实是「应存在但帧错了」的 MISALIGNED，会被错误丢弃。** 本样本 7 条 REDUNDANT 都是「不该单独成刀」，不是位置问题。若未来审核纪律松，会漏 GT。缓解：codebook 继续强制 MISALIGNED 必须填 `corrected_frame`；Calibration 抽查。
3. **Merged cluster 只产生 1 条 GT（代表帧）。** 这是对的：人类接受的是一个 physical event。新 run 若拆成 Gripper + Direction 两条 Final，第二条成为 FP。这正是 consolidation regression 的可观测形式。
4. **Exploratory 6 条若进入 Calibration Seed，其 GT 已被用于设计 search surface。** 见 §8。它们可以当校准 GT，不能当评测 GT。

## 5.5 与 Export 的关系

```text
Web SQLite
  → P2_G1_HUMAN_CALIBRATION_EXPORT_V1   # review-layer，按旧 run 对象
  → Canonical Human Boundary GT snapshot # matching-layer，按 episode+frame
  → 新 Calibration Run Finals
  → MATCHING_RULE
  → Metrics
```

P3 **禁止**直接读 SQLite。P3 读 Export，再派生 Canonical GT。Canonical snapshot 自身也必须 versioned / immutable。

---

# 6. Human GT Export 对接

Frozen 逻辑名：

```text
P2_G1_HUMAN_CALIBRATION_EXPORT_V1
```

P3 只读 Export，不直接读 Web SQLite。

## 6.1 Batch 3 Export 冻结顺序

### Package A — 当前 6 条 Seed

Owner 已批准：

```text
BATCH3_EXPORT_CURRENT_6 = YES
EXPORT_ROLE = CALIBRATION_SEED_FIRST_PACKAGE
SEARCH_SURFACE_LEAKAGE = YES
MUST_NOT_FEED_EVALUATION = YES
```

Protocol 冻结后即可实现并导出当前 6 条。源 Run 仍是：

```text
run_stage = EXPLORATORY_AUDIT
set_role = EXPLORATORY
```

不得为了 Export 修改源 Run 身份。

Package A 可以生成 **Seed Canonical GT Snapshot** 供工程验证 matching / export / provenance，但：

```text
SEARCH_GATE = CLOSED
```

仅有 6 条 Seed 时禁止 Stage A 参数搜索。

### Package B — 新 6 条 Fresh Calibration

从 Can/MH 按 §8 规则选出 6 条全新 Calibration Episode，生成 baseline calibration audit run，完成 P1/P2 Human Review 后再 Export。

### Combined Snapshot — 正式搜参 GT

只有：

```text
Seed 6 Export
+
Fresh 6 Export
=
12 Episode Combined Canonical GT Snapshot
```

并完成一致性校验、manifest freeze 后，才允许：

```text
SEARCH_GATE = OPEN
```

## 6.2 Export 最低目录

```text
human_calibration_export/
├── export_meta.json
├── signal_review.csv
├── predicted_boundary_review.csv
└── human_added_boundary.csv
```

`export_meta.json` 至少需要：

```text
export_contract = P2_G1_HUMAN_CALIBRATION_EXPORT_V1
export_id
source_run_id
run_stage
config_hash
signal_contract_hash
created_at
review_snapshot_time
episode_count
set_role_intended
must_not_feed_evaluation
```

`predicted_boundary_review.csv` → VALID / MISALIGNED 转 Canonical GT；REDUNDANT 转 known-FP anchor。  
`human_added_boundary.csv` → HUMAN_ADDED GT。  
`signal_review.csv` → P1 gate 与 signal contract provenance。

P3 生成的 Canonical GT snapshot 必须 versioned / immutable，并保存其所有 source export IDs。

---

# 7. 当前 6 条 Exploratory 的冻结角色

当前 6 条：

```text
Exploratory Audit
= failure-mode discovery
+ calibration protocol design evidence
+ CALIBRATION_SEED
≠ Evaluation
```

Owner 决策：

```text
CURRENT_6_AS_CALIBRATION_SEED = YES_ALL_6
SEED_COUNT = 6
SEED_NEVER_EVALUATION = YES
```

源 Run 保持：

```text
run_stage = EXPLORATORY_AUDIT
set_role = EXPLORATORY
```

Batch 3 Export / Canonical GT 中必须保留：

```text
gt_origin = EXPLORATORY_AUDIT_DISCOVERY
source_run_id = g1_exploratory_audit_20260917_141541_fe251439
usable_as = CALIBRATION_SEED
forbidden_as = EVALUATION
search_surface_leakage = YES
```

这 6 条可以参与 Calibration config selection，因为它们包含 error-correction 与 positive-preservation 两类案例；但改善幅度必须被视为“已见 failure mode 上的校准收益”，不能当泛化结论。泛化只能由独立 Evaluation 给出。

---

# 8. Calibration / Evaluation Dataset Design

## 8.1 Calibration Set 数量冻结

Roadmap 允许首版 10–20 Episodes；Owner 冻结本版为：

```text
CALIBRATION_TARGET_N = 12
CALIBRATION_SEED_N = 6
CALIBRATION_FRESH_N = 6
```

即：

```text
12 = 当前 6 条 Exploratory Seed + 6 条全新 Calibration Episode
```

## 8.2 Fresh 6 Episode Selection Rule

新增 6 条必须在 **参数搜索开始之前** 一次性选定并写入 Calibration Manifest。选择时覆盖以下轴，且不得只选“看起来容易修”的错误样本：

| 覆盖轴 | 冻结要求 |
| --- | --- |
| 短 / 简单 | 至少 1 条新的低 Final 数样本 |
| 长 / 复杂 | 至少 1 条新的长轨迹或高 Final 数样本 |
| GRIPPER-heavy | 新样本中必须覆盖 |
| DIRECTION-heavy | 新样本中必须覆盖 |
| merged cluster | 新样本中必须覆盖 |
| 独立有效 Direction | 新样本中必须覆盖 |
| preservation-like | 新 6 条至少一半应是 baseline 预期大体正确的样本 |
| correction-like | 允许包含新的过切 / 漏切 / jitter，但不得只选失败样本 |

Fresh 6 在选择时不得查看未来 Evaluation 候选的人类标签或评测结果。

## 8.3 Human Review Gate

```text
ALL_12_HUMAN_REVIEW_COMPLETE_BEFORE_PARAMETER_SEARCH = YES
```

具体顺序：

1. 冻结 12 条 Calibration Manifest；
2. 使用 **当前 exploratory config 原样** 生成 baseline calibration audit run（`run_stage=CALIBRATION`）；
3. Seed 6 的 P1 可在 `signal_contract_version/hash` 相同条件下复用；Seed 6 的 P2 GT 来自 Package A，不要求在新 run 按 boundary_id 重标；
4. Fresh 6 必须完成 P1 与 P2 Human Review；
5. 导出 Package B；
6. 合成 12 条 Combined Canonical GT Snapshot；
7. Snapshot freeze 后才允许 baseline scoring 与参数 search。

Baseline calibration audit run 可以先生成后补 GT；它在 GT freeze 前 **不可用于 config selection**。Scoring artifact 必须显式引用最终 `canonical_gt_snapshot_id`。

## 8.4 Evaluation Set Policy

```text
EVALUATION_SET_POLICY = DISJOINT_FROM_EXPLORATORY_AND_CALIBRATION
```

Evaluation Episode ID 必须与当前 6 条 Seed 和新增 Fresh 6 完全不相交。Evaluation 不得用于：

```text
threshold selection
strategy selection
tolerance selection
search-surface design
error-mode invention
```

Evaluation 仅在 Config Freeze 后首次正式计分；若结果差，返回 Design Review，不能继续在同一 Evaluation Set 上调参。

本 Protocol 不冻结 Evaluation Episode 数量与具体 ID；这不阻塞 Calibration。

## 8.5 Run Identity

v1 不允许一个 Run 混合 Calibration / Evaluation：

```text
run_stage = EXPLORATORY_AUDIT → set_role = EXPLORATORY
run_stage = CALIBRATION       → set_role = CALIBRATION
run_stage = EVALUATION        → set_role = EVALUATION
```

每次 Detector config 变化必须新 immutable Run，禁止覆盖。

---

# 9. Calibration Objective 与主指标

不要只优化 Precision，也不要只优化 Recall。本样本无 MISSED、主症是 REDUNDANT，但未来必须保护 Recall。

## 9.1 主指标（每个 Calibration Run 必出）

在冻结 matching rule + 冻结 T 下：

```text
Boundary Precision = TP / (TP + FP)
Boundary Recall    = TP / (TP + FN)
Boundary F1        = 2PR / (P+R)
```

分母是 Canonical GT（Recall）与 Predicted Final（Precision），不是旧 boundary_id。

## 9.2 过切 / 规模指标

```text
Episode-level over-segmentation count
  = max(0, n_pred - n_gt)  的 episode 计数，以及 per-episode 值

Mean predicted boundaries per episode

REDUNDANT_PROXY = FP
  在无新 human review 时，FP 是「多余预测」的操作定义

MISSED_PROXY = FN

MISALIGNED_PROXY
  = Localization Error 分布（mean / median / p90 of |delta| on TP）
  不是 Human Review 的 MISALIGNED 计数
  当前 seed 无 MISALIGNED 标签，localization 基线未知
```

Master 仍要求的 fragmentation diagnostic（保留，不作为选参第一键）：

```text
1–2 frame segment ratio
short_segment_ratio
segments_per_episode
```

## 9.3 不作为唯一赢家的量

```text
F1 最大 ≠ 自动采用
Precision 最大 ≠ 自动采用（可能靠删光 Direction）
```

---

# 10. Protected Constraints / Guardrail Metrics

校准主目标是减少 REDUNDANT Direction Final，但不能以破坏已知正确行为为代价。

Canonical GT snapshot 需要物化 `protected_class`。至少：

```text
G_GRIPPER
G_VALID_DIRECTION_SEED
G_VALID_DIRECTION_FRESH
G_MERGED_CLUSTER
```

## 10.1 Seed Hard Guardrails

当前 6 条 Seed 已被人工完整审核并用于设计 search surface，因此这些行为零容忍回归：

```text
SEED_GRIPPER_RECALL = 1.0              HARD
SEED_MERGED_CLUSTER_RECALL = 1.0       HARD
SEED_VALID_DIRECTION_RECALL = 1.0      HARD
```

Seed 已知合法独立 Direction = 6 条；任何 config 杀掉其中任意一条，直接淘汰。

## 10.2 Fresh Calibration Guardrails

Fresh 6 用来防止“只记住 Seed”。Direction 采用 Owner 冻结的 non-regression rule：

```text
FRESH_VALID_DIRECTION_RECALL_NEW
>=
FRESH_VALID_DIRECTION_RECALL_BASELINE
```

这是 HARD constraint。它不强制 Fresh 上绝对 100%，因为 Fresh 数据可能首次暴露 baseline 本身的合法 Direction 漏检或边界争议。

Gripper / merged interaction 仍保持 HARD 保护：

```text
CALIBRATION_GRIPPER_RECALL = 1.0 HARD
CALIBRATION_MERGED_CLUSTER_RECALL = 1.0 HARD
```

若 Fresh GT 显示上述目标在 baseline 已无法达到 1.0，且所有邻近 config 均无法恢复，则停止搜索并返回 Design Review；不得静默降低 guardrail。

## 10.3 Overall FN Guardrail

```text
FN_new <= FN_baseline   HARD
```

Baseline 指冻结的 12 条 Canonical GT 上、当前 exploratory config 的正式 matching 结果。

解释：这一轮校准允许减少 FP，但不允许通过制造新的漏检换 Precision。

## 10.4 Guardrail 失败处理

任何 HARD guardrail 失败：

```text
CONFIG_REJECTED = YES
```

不得再用 F1、MODE fixed 数或“视觉上更简洁”挽救该 config。

---

# 11. Error-mode-specific Metrics

每个 Calibration Run 必须能回答：

```text
MODE_01 fixed how many
MODE_02 fixed how many
MODE_03 fixed or not
是否引入新的 FN
```

操作定义（用 known-FP 锚点，不靠旧 boundary_id 相等）：

对每个 `known_false_positive_anchor`：

```text
仍存在 FP 落入 |pred - anchor_frame| <= T 且该 pred 未被配到任何 Canonical GT
  → MODE_k_REMAINING += 1
否则
  → MODE_k_FIXED += 1
```

```text
MODE_01_FIXED / MODE_01_REMAINING     目标 3
MODE_02_FIXED / MODE_02_REMAINING     目标 3
MODE_03_FIXED ∈ {0,1}                 目标 1，MEDIUM，允许残留
NEW_FN = FN_new - FN_baseline
NEW_UNANCHORED_FP
  = FP 中未匹配任何 MODE 锚点的多余预测
```

MODE_03 只有 1 条 MEDIUM，不得为了它单独发动全局大搜索。

---

# 12. 真实 Detector 参数与 Search Surface

只设计 family，不给最终数值，不执行搜索。

## 12.1 方向候选实际怎么生成

G1-P1 `window_direction_change_evidence`（`signals.py`）：

```text
对每个 t：
  v_left  = sum(delta_xyz[t-W : t])
  v_right = sum(delta_xyz[t : t+W])
  若 ||v_left|| 或 ||v_right|| < min_window_displacement_m → evidence[t]=0
  否则 evidence[t] = arccos(cosine(v_left, v_right))
```

当前 exploratory：`W = direction_window_frames = 8`（P1 runtime defaults），`min_window_displacement_m = 0.005`。

G1-P2 `_generate_direction_candidates`（`boundary_engine.py`）：

```text
persistent_high_runs(
  signals.direction_change_evidence,
  direction_change_threshold,      # exploratory 1.2 rad
  direction_persistence_frames,    # exploratory 3
)
→ (peak_frame, peak_value, run_length)
→ Candidate DIRECTION_CHANGE
   evidence_value = peak_value
   extra["run_length"] = run_length   # 运行时有，candidate CSV 未写出
```

**关键分裂：**

| 参数名 | 实际用在哪 | 改它的后果 |
| --- | --- | --- |
| P1 `direction_window_frames` / `direction_min_window_displacement_m` | **构造** `direction_change_evidence` | 改变 signal 时间序列；`signal_contract_hash` 变；P1 review 不能复用 |
| P2 `direction_change_threshold` / `direction_persistence_frames` | 在已有 evidence 上取 persistent peak | 改变候选；P1 可复用 |
| P2 `direction_window_frames` / `direction_min_window_displacement_m` / `direction_compatibility_threshold` | **仅** `pause_bridge` 的 pre/post heading 兼容检查 | 不改变方向候选生成 |

不得把 P2 的 `direction_window_frames` 误写成「方向候选窗口」。候选窗口在 P1 evidence 里。

## 12.2 当前真实可调参数（P2 config，全部 EXPLORATORY）

来自 `G1P2Config`，本轮不改值：

```text
# 候选生成
motion_speed_threshold
motion_persistence_frames
direction_change_threshold          ← Stage A 主轴
direction_persistence_frames        ← Stage A 主轴
gripper_state_threshold
gripper_persistence_frames

# 后处理
debounce_frames
boundary_consolidation_window       ← Stage B 有限轴
pause_bridge_duration               ← 本轮不作为主轴（见 §14）
min_segment_length
max_segment_length

# schema / support
boundary_tolerance_window           ← 不是 segmenter；不得当 Detector 搜索轴
rotation_support_threshold          ← supporting only，不能单独成刀
action_support_threshold
support_window_frames
direction_compatibility_threshold   ← pause_bridge only
direction_window_frames             ← pause_bridge only（P2）
direction_min_window_displacement_m ← pause_bridge only（P2）
```

Roadmap 允许搜索的名单含 motion / direction / pause_bridge / consolidation / min_segment_length。本设计 **收缩** 实际搜索轴，因为归因显示失败层是方向候选过生成，不是 pause_bridge，也不是 gripper。

### 12.3 正式 Search Surface（FROZEN）

```text
SEARCH_STRATEGY = STAGED_CALIBRATION
SEARCH_SURFACE = STAGED_AND_BOUNDED
```

### Stage A0 — Direction Candidate Discriminability Audit｜方向候选可分性审计

**不改任何参数。** 在 12 条 Frozen Canonical GT 上，对 baseline 中所有独立 DIRECTION prediction / candidate 做 VALID vs FP 对照，至少检查：

```text
evidence_value
run_length（若可从 runtime / 派生分析安全获得）
translation_speed / smoothed_translation_speed
pre/post displacement
local speed valley / idle context
distance to nearest gripper transition
supporting_reasons
evidence peak shape
```

全部只能来自 Formal Signals / Candidate lineage；禁止 privileged simulator state。

A0 Gate：

```text
如果 threshold / persistence 或已有 Formal Signal 派生量显示可解释的 discriminability
→ 允许进入 Stage A

如果 VALID 与 FP 在可用 Formal Signal 上无法形成可解释区分
→ STOP SEARCH
→ DESIGN REVIEW
```

禁止在“已知不可分”时机械扫参数碰碰运气。

### Stage A — Direction Candidate Quality

只有 A0 PASS 后才允许搜索：

```text
direction_change_threshold
direction_persistence_frames
```

采用 coarse→fine、两轴受控搜索；不得混入 consolidation / pause / P1 evidence window。

### Stage B — Limited Consolidation

仅在 Stage A 稳定、guardrail 全绿且 MODE_03 仍值得处理时，单因素比较：

```text
boundary_consolidation_window ∈ {8, 10, 12}
```

`>12` 本版禁止作为候选。

### Stage C — Regression Only

不新增搜索轴，仅复查：

```text
Seed guardrails
Fresh non-regression
NEW_FN
NEW_UNANCHORED_FP
fragmentation
Localization
```

### 本版不搜索

```text
pause_bridge_duration
Gripper thresholds
rotation/action support thresholds
tolerance_frames
```

P1 `direction_window_frames / min_window_displacement` 属于 signal contract changing option；若未来进入，必须新 `signal_contract_hash` + 重做 P1 Review，不能藏进本轮 Stage A。

# 12.4 为什么 threshold-only 不够

VALID vs REDUNDANT 独立 DIRECTION 的 `evidence_value` 重叠。例子：

```text
REDUNDANT MODE_01  @78  evidence ≈ 2.64
VALID     demo_278-B0004  仅 ACTION_SUPPORT
REDUNDANT MODE_02  @105 evidence ≈ 1.50  无 supporting
VALID     demo_242-B0002  ROTATION+ACTION
```

提高 `direction_change_threshold` 可能杀掉部分低分 FP，也会威胁低分 VALID，且杀不掉高分 jitter（2.64）。  
因此 Stage A 必须 **同时看 persistence**，并做 **离线 feature 对照**（§13），而不是只扫 threshold。

可解释 strategy（仍用 Formal Signals，不引入 object GT）：

1. 更长的 `direction_persistence_frames`：jitter 可能是短 run，合法转向可能是长 run。`run_length` 已在 `persistent_high_runs` 的 extra 里，CSV 未落地 → 标为 OPTIONAL FEATURE。
2. 在候选接受时增加 **位移门控**（用已有 `heading_vector` + `direction_min_window_displacement_m` 思想，但是对候选而非 pause_bridge）。当前候选路径 **没有** 这一步。这是 limited strategy candidate，不是本轮实现。
3. **gripper proximity**：靠近后续 GRIPPER 且未并入簇 → MODE_03。优先用有限 consolidation，而不是新模型。
4. **idle / 局部速度谷**：MODE_02 视觉像短暂停，但 episode 无 MOVE_TO_IDLE。需要查 `translation_speed` / `motion_state_candidate` 在该帧是否其实低速。这是 SEMANTIC MISMATCH INVESTIGATION，不是把 pause_bridge_duration 加大。

禁止使用：

```text
object GT / Can_pos / Can_to_EEF
reward / done / success
privileged simulator state
learned segmentation model
RGB 作为 Formal 切分依据
```

---

# 13. Direction Candidate Calibration Analysis Fields

本节首先服务于 **Stage A0 Direction Candidate Discriminability Audit**。Stage A0 的目标不是选参数，而是先判断现有 Formal Signals / candidate 属性是否足以解释“合法独立 Direction”与“冗余独立 Direction”的差异。

当前 Seed 已有 6 VALID vs 7 REDUNDANT；Fresh 6 完成审核后必须把新的 Direction 样本一并纳入 A0。

未来每次 Calibration Analysis 必须并排比较：

**6 个独立 VALID DIRECTION Final** vs **7 个独立 REDUNDANT DIRECTION Final**。

### 13.1 现有、可直接用的字段

来自 `candidate_boundaries.csv` / `final_boundaries.csv` / FormalSignals：

| 字段 | 存在位置 | 用途 |
| --- | --- | --- |
| `frame` | CSV | 定位 |
| `evidence_value` | candidate CSV | 即 peak `direction_change_evidence`；已证明重叠 |
| `supporting_reasons` | CSV | ACTION_SUPPORT / ROTATION_SUPPORT；非干净分隔符 |
| `persistence_status` | CSV | 本样本全是 PERSISTENT，无区分力 |
| `primary_reason` | CSV | 全是 PERSISTENT_DIRECTION_CHANGE |
| `direction_change_evidence[t]` | FormalSignals | 可看峰值形状，不只看标量 |
| `translation_speed[t]` / `smoothed_translation_speed` | FormalSignals | MODE_02 是否其实是低速 |
| `translation_step_norm` / `delta_x/y/z` | FormalSignals | 局部位移 |
| `gripper_aperture` / `gripper_change_evidence` | FormalSignals | 近夹爪过渡 |
| `action_change_magnitude` | FormalSignals | 与 ACTION_SUPPORT 同源 |
| `eef_rotation_delta_rad` / `eef_angular_speed_rad_s` | FormalSignals | supporting only |
| `motion_state_candidate` | FormalSignals（exploratory，非 Formal 切分依据） | 诊断 idle context |
| member/representative 物化字段 | final CSV | 是否独立 vs 已合并 |

可用现有函数 **计算但不落盘** 的量：

```text
heading_vector(pre_window) / heading_vector(post_window)
heading_angle(pre, post)
||pre||, ||post||                         # 最小位移
dist_to_nearest_gripper_final
dist_to_nearest_move_idle_candidate
```

`heading_vector` / `heading_angle` 已在 `boundary_engine.py`，目前服务于 pause_bridge，不服务于方向候选过滤。

### 13.2 OPTIONAL FEATURE FOR CALIBRATION ANALYSIS

当前没有、分析时需要、**本轮不得实现**：

```text
candidate.run_length 写入 CSV          # extra 已有
pre_window_displacement_m
post_window_displacement_m
local_speed_minimum
idle_fraction_in_window
dist_to_nearest_gripper_transition
dist_to_nearest_move_to_idle
dist_to_nearest_idle_to_move
evidence_peak_width
```

这些只能从 Formal Signals 派生。写出它们是为了以后解释 VALID vs REDUNDANT，不是为了把 privileged 状态偷进来。

### 13.3 本样本已能说的、还不能说的

能说：

- 全部 7 个错误都是 DIRECTION-only Primary KEEP
- 并进夹爪簇的 Direction 全部 VALID
- evidence_value 不能线性分开
- 错误间距 ≫ debounce=4 与 consolidation=8（MODE_03 除外：差 10）
- pause_bridge 因缺少 MOVE_TO_IDLE→IDLE_TO_MOVE 对而未参与 MODE_02

不能说（留给 Calibration Analysis，不在本轮猜）：

- VALID 的 run_length 是否系统性更长
- MODE_02 帧上 smoothed speed 是否形成谷
- 合法独立 Direction 是否总有更大 pre/post displacement

---

# 14. Consolidation Strategy

MODE_03 = 1 条 MEDIUM：Direction @136 vs Gripper cluster @146，差 10 frames；exploratory `boundary_consolidation_window=8`。

聚类实现事实（`_cluster_candidates`）：窗口是相对 **当前簇第一个成员**，且 gripper 与 opposite motion 有兼容性约束。扩大窗口会把「第一个成员起 T 帧内」的兼容候选并成一事。

```text
boundary_consolidation_window
= LIMITED STRATEGY CANDIDATE
≠ 主要全局搜索轴
```

可讨论的 bounded range（不执行）：

```text
{8, 10, 12} frames
= {0.40 s, 0.50 s, 0.60 s}
```

风险：

```text
window 太大
→ 不同 physical transition 被错误 merge
  本样本独立 VALID DIRECTION 最小间距 ≈ 13 frames (0.65 s)
  因此 12 已靠近危险区；>12 本轮直接禁止作为候选

window 太小
→ 同一 transition 被切成两个 Final
  MODE_03 就是 10 vs 8
```

Stage B 只允许在 Stage A 已改善 MODE_01/02、且 guardrail 仍绿时，对 `{8,10,12}` 做 **一次一个值** 的对照。不得与 threshold、persistence、pause_bridge 组成大网格。

demo_278-B0007 @125 距 Gripper @135 也是 10 frames，但归因主因是 MODE_02 过生成。若只把 window 调到 10，可能「顺便」吞掉 B0007，造成假改善，掩盖候选质量问题。这是 consolidation 必须后置的原因。

---

# 15. Pause Bridge 与 SEMANTIC MISMATCH

人工 4 次 `REDUNDANT_SHORT_PAUSE`（demo_278 ×3 + demo_242-B0008）。  
机器错误对象是 `DIRECTION_CHANGE` KEEP，不是 `MOVE_TO_IDLE → IDLE_TO_MOVE`。

`pause_bridge` 资格（`_pause_pair_eligible`）要求：

```text
left type  = MOVE_TO_IDLE
right type = IDLE_TO_MOVE
duration ∈ (0, pause_bridge_duration]
pre/post heading 位移 >= direction_min_window_displacement_m
heading 角差 <= direction_compatibility_threshold
夹爪状态兼容
两侧都不是 Hard gripper
```

demo_278 **没有任何** MOVE_TO_IDLE / IDLE_TO_MOVE，桥接层不可能作用到 MODE_02。

```text
不要简单扩大 pause_bridge_duration
```

加大 duration 不会让 DIRECTION 候选变成可桥接的 pause 对。

```text
SEMANTIC_MISMATCH_INVESTIGATION
= 为什么人类视觉上的「短暂停」
  在 Formal Signals 抽象中表现为 DIRECTION_CHANGE
```

调查问题（分析，不改代码）：

1. 该帧 `translation_speed` / `smoothed_translation_speed` 是否实际下降，但未跨过 `motion_speed_threshold` 的 persistent binary transition？
2. `window_direction_change_evidence` 是否把「减速—再加速」或「小圆弧」编码成大 heading 角？
3. 左右窗 W=8 是否在低位移时仍过了 0.005 m 门（过门后 arccos 对噪声敏感）？
4. 若位移门在 P1 已把 evidence 置 0，为何这些帧仍有 1.5–2.1 的峰值？

在调查结束前：

```text
pause_bridge_duration = NOT_A_PRIMARY_SEARCH_AXIS
pause_bridge 规则改写 = DESIGN_CHANGE_REQUEST，不是 Calibration 数值搜索
```

---

# 16. Search Strategy

```text
SEARCH_STRATEGY = STAGED_CALIBRATION
NOT_FULL_GRID = YES
```

执行顺序冻结为：

```text
Stage A0  Direction Candidate Discriminability Audit
          参数不变，只做可分性分析
          ↓ PASS 才继续

Stage A   Direction candidate quality
          direction_change_threshold × direction_persistence_frames
          coarse→fine
          ↓

Stage B   Limited consolidation
          boundary_consolidation_window ∈ {8,10,12}
          单因素
          ↓

Stage C   Regression only
          不新增轴
```

### Stage A0 Stop Gate

如果 12 条数据上 VALID Direction 与 FP Direction 在 threshold / persistence / Formal Signal 派生量上没有可解释区分：

```text
STAGE_A0 = FAIL_NO_DISCRIMINABILITY
STOP PARAMETER SEARCH
RETURN DESIGN REVIEW
```

此时应讨论 Candidate Acceptance Rule / Formal Signal abstraction，而不是继续扩大网格。

### 为什么禁止 Full Grid

- 当前 failure attribution 已明确 MODE_01/02 主层是 Direction candidate quality；
- MODE_03 只有 1 条 MEDIUM，不足以把 consolidation 变成全局主轴；
- 多轴笛卡尔积会降低可解释性，并容易用 consolidation “吞掉” Direction FP，形成假改善；
- Search 必须让每个阶段与明确 Error Mode 对齐。

coarse→fine 只允许在单一阶段内部进行。

---

# 17. Calibration Run Lineage

正式 Calibration Episode Manifest 冻结后，使用当前 exploratory config 原样生成 Baseline Calibration Audit Run：

```text
run_stage = CALIBRATION
set_role = CALIBRATION
episode_count = 12
search_stage = BASELINE
config = current exploratory config unchanged
```

每个后续参数 / strategy 改动都必须生成新的 immutable run directory；禁止覆盖。

Run 继续遵守 `P2_G1_AUDIT_FOLDER_V1` 的既有 identity：

```text
contract_version
run_id
run_stage
created_at
parent_run_id
config_version
config_hash
segmentation_version
signal_contract_version
signal_contract_hash
source_dataset_id
episode_count
```

允许 additive calibration metadata，例如：

```text
calibration_manifest_id
search_stage = BASELINE / A / B / C
```

**Scoring provenance 不要求在 Run 生成时已经存在。** Human GT 可能在 Baseline Run 生成后才完成，因此以下内容应写入独立 versioned scoring artifact / score_meta，而不是伪造进尚未完成 GT 的 Run：

```text
canonical_gt_snapshot_id
human_export_ids
matching_rule_id = MAX_CARDINALITY_MIN_TOTAL_DISTANCE_ONE_TO_ONE_V1
tolerance_frames = 3
scored_at
```

这样 Baseline Run 可先用于 Fresh 6 Human Audit；12 条 Canonical GT freeze 后，再对同一个 immutable Baseline Run 评分，无需重跑相同 Detector config。

---

# 18. Calibration Scoring Procedure

Search Gate 打开后，对 Baseline 与每个新 immutable Calibration Run：

```text
1. 读取同一个 12-Episode Canonical Human Boundary GT snapshot
2. 读取本 Run 的 Predicted Final Boundaries
3. 使用冻结：
   MATCHING_RULE_ID = MAX_CARDINALITY_MIN_TOTAL_DISTANCE_ONE_TO_ONE_V1
   TOLERANCE_FRAMES = 3
4. 计算 TP / FP / FN / Precision / Recall / F1
5. 计算 Localization Error
6. 计算 Seed / Fresh guardrails
7. 计算 MODE_01/02/03 remaining vs fixed
8. 计算 NEW_FN / NEW_UNANCHORED_FP
9. 计算 over-segmentation / mean pred count / fragmentation
10. 与 baseline / parent 生成差分表
```

正式 scoring artifact 必须记录：

```text
run_id
canonical_gt_snapshot_id
human_export_ids
matching_rule_id
tolerance_frames
metric_version
```

禁止：

```text
new boundary_id == old boundary_id 作为命中
直接读取 Web SQLite 做 P3 scoring
使用不同 T 给不同 config 打分
使用 Evaluation GT 调 Calibration 参数
```

Baseline Scoring 必须先完成；后续所有 config 都与同一个 baseline 和同一个 Canonical GT snapshot 比较。

---

# 19. Config Selection Rule

```text
CONFIG_SELECTION_RULE = LEXICOGRAPHIC_CONSTRAINED
```

禁止不透明加权总分。任何 HARD constraint 失败即淘汰，不看后面的 F1。

```text
L0  Feasibility
    signal_contract_hash 与协议一致
    matching_rule_id 固定
    T = 3 固定
    canonical_gt_snapshot_id 相同

L1  HARD guardrails
    CALIBRATION_GRIPPER_RECALL = 1.0
    CALIBRATION_MERGED_CLUSTER_RECALL = 1.0
    SEED_VALID_DIRECTION_RECALL = 1.0
    FRESH_VALID_DIRECTION_RECALL_new >= FRESH_VALID_DIRECTION_RECALL_baseline
    FN_new <= FN_baseline

L2  主校准目标
    MODE_01_REMAINING + MODE_02_REMAINING 更少者胜
    若并列：总体 FP 更少者胜

L3  MODE_03
    MODE_03_FIXED 优先，但不得用 L1 失败交换
    该单例为 MEDIUM，允许残留

L4  综合参考
    Boundary F1 更高
    再并列：Localization p90 更小
    再并列：mean predicted boundaries 更接近 n_gt
    再并列：改动更简单、搜索轴更少者胜
```

解释：先保护 Gripper、Merged Cluster、已知合法 Direction 与 Fresh non-regression，再减少已归因 FP；F1 只在约束满足后作为参考决胜。

---

# 20. Stop Rule

Calibration 停止规则包括 **前置停止** 与 **搜索后停止**。

## 20.1 Stage A0 前置停止

如果 A0 显示现有 Formal Signal / candidate 属性无法对 VALID vs FP Direction 提供可解释区分：

```text
STOP_BEFORE_STAGE_A = YES
RETURN_DESIGN_REVIEW = YES
```

禁止机械扫 threshold × persistence。

## 20.2 搜索后停止

在 HARD guardrail 保持通过的前提下，满足任一条件即可停止并进入 Config Freeze：

```text
S1  MODE_01 + MODE_02 remaining = 0
    或已明显下降，而下一档参数开始损伤合法 Direction

S2  连续两轮 Stage A/B 只能在 Precision 与 Recall /合法 Direction 之间 trade-off

S3  所有邻近 config 都触发 HARD guardrail 退化
    → 返回 Design Review

S4  改善只发生在 Seed 6 条，Fresh 6 无对应收益
    → 视为 seed memorization，停止继续“记忆性修补”

S5  MODE_03 单例仍残留，但修它需要扩大 consolidation 并引入新回归
    → 允许保留

S6  Design Owner 宣布 CALIBRATION_CONFIG_FROZEN
```

冻结后：

```text
FROZEN CONFIG
→ Independent Evaluation
```

Evaluation 结果不得回灌到同一轮 Calibration。

---

# 21. Independent Evaluation Protocol

```text
Evaluation Set 必须在 Calibration 完成后首次正式运行
run_stage = EVALUATION
```

禁止参与：

```text
threshold selection
strategy selection
tolerance selection
error-mode 再定义
Canonical GT 规则修改
```

输出：

```text
Precision / Recall / F1
Localization Error
Guardrail recalls（若 Evaluation GT 也按同一 Canonical 规则构建）
error mode breakdown（若 Evaluation 上也做了同类 reason；
  未审核前只报告 FP/FN 切片，不得把 Calibration 的 MODE 锚点套到未见过的 episode 上假装「MODE_01=0」）
fragmentation diagnostics
```

若 Evaluation 差：

```text
不能继续调同一个 Evaluation Set
返回 Design Review
记录 Design Change Request
需要新的独立 Evaluation Set，或明确 limitation 后停止声称独立评测
```

Evaluation Human Review 可存档，Web Frozen：`MUST_NOT_FEED_BACK_TO_CALIBRATION`。

---

# 22. 完整闭环

```text
Exploratory Audit（当前 6）
  ↓
Error Attribution
  ↓
Calibration Protocol FROZEN v1              ← 当前文档
  ↓
Batch 3 Export Package A（Seed 6）
  ↓
选择 Fresh 6 + 冻结 12-Episode Calibration Manifest
  ↓
Baseline Calibration Audit Run（config 不变，12 条）
  ↓
Fresh 6 Human Review
  ↓
Batch 3 Export Package B（Fresh 6）
  ↓
Combined Canonical Human GT Snapshot（12 条）
  ↓
SEARCH_GATE = OPEN
  ↓
Baseline Scoring（T=3 + max-cardinality/min-distance matching）
  ↓
Stage A0 Direction Candidate Discriminability Audit
  ├─ FAIL → Design Review
  └─ PASS
       ↓
Stage A Direction threshold × persistence
  ↓
Stage B Limited Consolidation {8,10,12}
  ↓
Stage C Regression
  ↓
Lexicographic Config Selection
  ↓
Stop Rule → Config Freeze
  ↓
Independent Evaluation（全新 episode）
  ↓
Final G1 Freeze
或 Evaluation 失败 → Design Review
```

关键 Gate：

```text
Seed Export 完成 ≠ 可以搜参
12 条 GT Freeze 才能 OPEN SEARCH_GATE
Evaluation 永远不用于调参
```

---

# 23. Frozen Design Decisions

```text
MATCHING_RULE_ID =
  MAX_CARDINALITY_MIN_TOTAL_DISTANCE_ONE_TO_ONE_V1

MATCHING_OBJECTIVE =
  1) maximize TP / matched pair count
  2) minimize total |pred_frame - gt_frame|
  3) deterministic lexicographic tie-break

MATCH_KEY =
  (episode_id, frame)

TOLERANCE_POLICY =
  FIXED ±3 frames = ±0.15s @20Hz
  NOT_A_SEARCH_AXIS

CANONICAL_GT_RULE =
  VALID      → gt_frame = predicted_frame
  MISALIGNED → gt_frame = corrected_frame
  REDUNDANT  → not GT; known-FP anchor
  MISSED     → gt_frame = human_added_frame
  metric 不依赖旧 boundary_id

CALIBRATION_SET_POLICY =
  TARGET_N = 12
  Seed 6 = 当前 Exploratory 全收
  Fresh 6 = 参数搜索前一次性选定
  ALL_12_HUMAN_REVIEW_COMPLETE_BEFORE_SEARCH = YES
  Seed 永远禁止作为 Evaluation

EVALUATION_SET_POLICY =
  disjoint episode_id
  unused for tuning / T / strategy
  only after Config Freeze

PRIMARY_METRICS =
  Precision / Recall / F1
  Localization Error
  over-segmentation
  mean predicted boundaries
  fragmentation diagnostics

PROTECTED_GUARDRAILS =
  CALIBRATION_GRIPPER_RECALL HARD = 1.0
  CALIBRATION_MERGED_CLUSTER_RECALL HARD = 1.0
  SEED_VALID_DIRECTION_RECALL HARD = 1.0
  FRESH_VALID_DIRECTION_RECALL HARD = non-regression vs baseline
  FN_new <= FN_baseline HARD

SEARCH_STRATEGY =
  Stage A0 discriminability audit
  → Stage A direction threshold × persistence
  → Stage B consolidation {8,10,12}
  → Stage C regression

SEARCH_GATE =
  CLOSED until 12-Episode Combined Canonical GT Snapshot frozen

BATCH3_EXPORT =
  current Seed 6 may export immediately as Package A
  Fresh 6 export later as Package B

CONFIG_SELECTION_RULE =
  LEXICOGRAPHIC_CONSTRAINED

STOP_RULE =
  A0 no discriminability → Design Review
  or modes reduced / only trade-offs / protected regression / seed memorization
  → Config Freeze → Evaluation
```

---

# 24. Owner Decisions Resolved

DRAFT v1 的 Owner Decision Gate 已关闭：

| 原待决项 | Frozen 决策 |
| --- | --- |
| `tolerance_frames` | **±3 frames（±0.15 s）** |
| 当前 6 条是否进 Seed | **全部 6 条进入 CALIBRATION_SEED；永久禁止 Evaluation** |
| Calibration N | **12 = 6 Seed + 6 Fresh** |
| 新样本何时完成 Human Review | **参数搜索前全部完成** |
| Seed Valid Direction Recall | **HARD = 100%** |
| Fresh Valid Direction Recall | **HARD non-regression vs baseline** |
| Batch 3 是否先导出当前 6 条 | **YES，Package A；但 Search Gate 仍 CLOSED** |
| greedy matching | **否决；改为 maximum-cardinality + minimum-total-distance one-to-one** |
| Stage A 前是否直接搜参 | **否；先做 Stage A0 discriminability audit** |

当前没有阻塞 Protocol Freeze 的 Owner Decision。Evaluation Episode 数量与具体 ID 留到 Config Freeze 前的 Evaluation Manifest 设计，不阻塞 G1-P3 Calibration。

---

# 25. 下一步 Gate

本 Protocol 已 FROZEN。下一阶段不是直接搜参数，而是：

```text
NEXT_GATE =
BATCH3_SEED_EXPORT_AND_CALIBRATION_SET_BUILD
```

严格顺序：

```text
1. 实现 Batch 3 Human Calibration Export
2. 导出当前 Seed 6（Package A）
3. 从数据池选择 Fresh 6，冻结 12-Episode Calibration Manifest
4. 用 baseline config 生成 12 条 CALIBRATION audit run
5. Fresh 6 完成人工审核
6. 导出 Fresh 6（Package B）
7. 生成并冻结 Combined Canonical GT Snapshot（12 条）
8. Baseline Scoring
9. Stage A0
10. 只有 A0 PASS 才允许 Stage A 参数搜索
```

在第 7 步完成前：

```text
PARAMETER_SEARCH = FORBIDDEN
SEARCH_GATE = CLOSED
```

---

# 26. 冻结时仍未做（刻意）

```text
未修改 Detector / threshold / persistence / consolidation / pause_bridge
未执行任何 parameter search / grid search
未生成用于选参的新 Detector config
未生成 Evaluation Run
未改 Human Review SQLite
未重新标注当前 6 条
未实现 Batch 3 Export
未选择 Fresh 6 IDs
未生成 12-Episode Calibration Manifest
未生成 Combined Canonical GT Snapshot
未执行 Baseline Scoring
未执行 Stage A0 / A / B / C
未选择 optimal config
```

因此：

```text
CALIBRATION_PROTOCOL = FROZEN
FORMAL_CALIBRATION_EXECUTION = NOT_STARTED
```

---

# 27. 文档状态

```text
DOCUMENT = Project2_G1_P3_Calibration_Protocol_FROZEN_v1_20260917.md
SOURCE_DRAFT = Project2_G1_P3_Calibration_Design_DRAFT_v1_20260917.md
STATUS = FROZEN_v1.0
FROZEN = YES
OWNER_REVIEW = PASS

G1_P3_CALIBRATION_PROTOCOL =
FROZEN_READY_FOR_BATCH3_AND_CALIBRATION_SET_BUILD
```

任何后续对 matching rule、T、Canonical GT、Calibration Set N、guardrail 或 Calibration/Evaluation 隔离的修改，都必须新建 Protocol 版本并经过 Design Owner Review；Implementation 不得原地静默修改本文件的冻结契约。
