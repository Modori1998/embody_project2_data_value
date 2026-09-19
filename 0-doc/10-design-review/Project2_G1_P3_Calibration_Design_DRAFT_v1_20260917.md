# Project 2 G1-P3 Calibration Design DRAFT v1

```text
DATE = 2026-09-17
DOCUMENT_STATUS = DRAFT_v1
NOT_FROZEN = YES
TASK = G1-P3 CALIBRATION PROTOCOL DESIGN ONLY
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
G1_P3_CALIBRATION_DESIGN =
DRAFT_READY_FOR_OWNER_REVIEW
```

本轮只冻结 **怎么校准**，不执行校准，不选择最优参数，不把当前 6 条 Exploratory 静默改名为 Calibration / Evaluation。

---

# 0. Authority Confirmation

本设计真实读取了 Google Drive 当前权威稿（非只信本地副本标题）：

| 文档 | Drive fileId | 对本轮的约束 |
| --- | --- | --- |
| `Project_2_Engineering_Design_Master_v1_20260914.md` | `1Cd05zSFR6IF8rXby6RYmocZbmrUDH05b` | G1-D Human Calibration Loop 已冻结；Calibration / Evaluation 必须隔离；`tolerance_frames` = `DATA_CALIBRATION_PENDING`；Hard Boundary Recall 优先于单一总分 |
| `Project2_Development_Roadmap_and_Design_Gate_Plan_v1_20260914.md` | `1lQd5Nn4jxwiqwylEg40tCAl1jwDg5O6t` | G1-P3 = Human Calibration Loop；Calibration Set 首版目标 10–20；coarse→fine 搜索；Evaluation 只跑一次冻结 config |
| `02_robot_demonstration_mining_autolabel_design.md` | `1tgMOxq2_0taUT7LdHDsn4nvEqookCdAI` | Calibration Set ≠ Evaluation Set；数值阈值 `DATA_CALIBRATION_PENDING` |
| `Project2_G1_Human_Audit_Web_Design_FROZEN_v1_20260916.md` | `1v6ZtopYFfCIWG9kjCOmwJe2C-XWB4xRR` | P3 消费 `P2_G1_HUMAN_CALIBRATION_EXPORT_V1`，不直接读 SQLite；`boundary_id` 仅 RUN_STABLE_ONLY；`run_stage` ∈ {EXPLORATORY_AUDIT, CALIBRATION, EVALUATION} |

本地归因 SSOT：

```text
0-doc/80-audit-local/Project2_G1_Human_Review_Error_Attribution_Audit_20260917.md
G1_HUMAN_REVIEW_ERROR_ATTRIBUTION = PASS_READY_FOR_CALIBRATION_DESIGN
RUN_ID = g1_exploratory_audit_20260917_141541_fe251439
run_stage = EXPLORATORY_AUDIT
set_role = EXPLORATORY
```

确认事实：

```text
G1-P3 = Human Calibration Loop
Calibration / Evaluation 必须隔离
P3 消费 Human Calibration Export，而不是直接读 SQLite
formal tolerance_frames 仍未冻结
exploratory boundary_tolerance_window = 5
  = schema reserved for G1-P3 matching
  ≠ segmenter input
  ≠ 已冻结 metric tolerance
```

当前 6 条不得静默变成 Calibration Set，更不能成为 Evaluation Set。

---

# 1. 本轮范围 / 禁止事项

本 DRAFT 设计并冻结协议，不实现协议。

禁止（本轮已遵守）：

```text
修改 Detector
修改 threshold
执行 parameter search / grid search
生成 Calibration Run / Evaluation Run
选择最优参数
修改 SQLite
重新标注当前 6 条
实现 Batch 3 Export
把 EXPLORATORY 改名为 CALIBRATION / EVALUATION
```

允许：

```text
比较 matching 方案并给出推荐
把 tolerance 转成时间语义
定义 Canonical Human Boundary GT
定义 split / metrics / guardrails / search family
把证据不足的项标为 OWNER_DECISION_REQUIRED
```

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

正式 metric 比较的是：

```text
Canonical Human Boundary GT  (episode_id, gt_frame)
        ↔
Predicted Final Boundaries   (episode_id, pred_frame)
```

不是：

```text
old boundary_id  ↔  new boundary_id
```

Web Frozen Design 已写明：`boundary_id` = `RUN_STABLE_ONLY`。threshold / consolidation 一变，编号就会漂。用旧 ID 做 metric 会把「消失的 REDUNDANT」和「重新编号的 VALID」全部算错。

## 3.2 方案比较

### A. Exact Match

```text
match iff pred_frame == gt_frame
```

优点：无歧义。  
缺点：20 Hz 下 1 frame = 0.05 s。representative 选峰值、gripper persistence、consolidation 锚定都可能差 1–3 frames。Master 已允许 Tolerance Window。Exact Match 会把可接受的同一 physical transition 打成 FP+FN。  
结论：**不作为正式 matching rule。** 只保留为 diagnostic（`EXACT_HIT_COUNT`）。

### B. ±N frame tolerance matching（无一对一）

```text
pred 命中某个 GT  iff  |pred - gt| <= T
GT 被命中 iff 存在任意 pred 落入窗口
```

问题：一个 pred 可同时命中两个 GT；一个 GT 可同时吃掉两个 pred。这正是本协议必须禁止的。当前 6 条 GT 间距足够大，暂时不会爆，但协议不能依赖「GT 永远稀疏」。  
结论：**禁止作为正式规则。**

### C. One-to-one nearest matching within tolerance｜推荐

```text
1. 同一 episode 内生成所有 |pred_frame - gt_frame| <= T 的候选对
2. 按 |delta| ASC, pred_frame ASC, gt_frame ASC 排序
3. greedy：双方都未被占用则匹配
4. 每个 pred 最多 1 个 GT；每个 GT 最多 1 个 pred
```

这是一维时间轴上的 bipartite matching。数据是 frame 标量，不是高维；greedy-by-distance 与 Hungarian 在「唯一最近且窗口不重叠」时结果相同，且可逐步审计。

当前数据结构支持该规则：

- Human GT 可被压成 `(episode_id, gt_frame)`
- Predicted Final 已有 `frame`
- `candidate_type` 只作 diagnostic，不进入主匹配键

### D. Event-aware matching（按 type 限制）

例如要求 DIRECTION pred 只能配 DIRECTION GT。

风险：Canonical GT 来自 **physical event 的代表帧**。VALID 的 Gripper+Direction merged cluster 的 GT frame 是 gripper representative。新 run 若仍合并，pred type=GRIPPER；若 consolidation 变化，可能变成 DIRECTION 或拆成两条。用 type 硬约束会把「同一物理过渡、代表类型变了」判成 FN+FP。  
结论：**不作为主 matching。** 类型一致性只做 regression diagnostic。

## 3.3 正式推荐

```text
MATCHING_RULE =
ONE_TO_ONE_GREEDY_NEAREST_WITHIN_TOLERANCE

MATCH_KEY =
(episode_id, frame)

NOT_MATCH_KEY =
boundary_id
candidate_id
candidate_type
```

并列决规则（必须确定性）：

```text
sort key =
  |pred_frame - gt_frame| ASC
  pred_frame ASC
  gt_frame ASC
```

禁止：

```text
一个 predicted boundary 同时匹配两个 GT
一个 GT 同时吃掉两个 predicted boundary
跨 episode 匹配
用旧 run 的 boundary_id 继承匹配
```

## 3.4 TP / FP / FN / Matched-but-Misaligned

对每个 episode：

| 符号 | 定义 |
| --- | --- |
| **TP** | greedy 匹配成功的 (pred, GT) 对。`|pred-gt| <= T` |
| **FP** | 未被匹配的 Predicted Final |
| **FN** | 未被匹配的 Canonical GT |
| **Localization Error** | 对每个 TP：`|pred_frame - gt_frame|`（frame 与秒都记） |

**Matched-but-Misaligned 不作为 F1 的第四类。**

理由：Human Review 的 `MISALIGNED` 是 **某次 run 上相对该 run 预测帧的审核标签**。新 Calibration Run 的预测帧会变，旧 MISALIGNED 标签不能直接当新 run 的 outcome。  
若 `|delta| > 0` 且 `<= T`，计为 TP，并记入 Localization Error。这就是 Master 要求的 Localization，而不是再发明一个会改变 Precision/Recall 分母的类别。

可选 diagnostic（不进主目标）：

```text
EXACT_TP          |delta| = 0
NEAR_TP           0 < |delta| <= T
UNMATCHED_PRED    FP
UNMATCHED_GT      FN
```

## 3.5 Duplicate / 多 pred 落入同一 GT 窗口

greedy one-to-one 后：

```text
窗口内距离最近的 pred → TP
其余 pred → FP
```

这正对应「同一 physical transition 被切成两条 Final」的过切。MODE_01/02 的目标就是让这些 extra pred 消失，使 FP 下降。

## 3.6 多个 GT 靠得很近

若两个 Canonical GT 满足：

```text
|gt_i - gt_j| <= 2T
```

则存在 **GT_COLLISION_RISK**：最近邻可能配错。协议要求：

1. Canonical GT 构建后必须报告 `min_gt_spacing_frames`
2. 若 `min_gt_spacing <= 2T`，标定报告打 `GT_SPACING_WARN`，匹配仍执行，但 Design Owner 必须看见
3. 不得靠放宽 T 去「吃掉」过密 GT

当前 6 条若按 §7 Canonical 规则导出，独立 GT 最小间距远大于 2×5=10。这只是现状观察，**不是**把 T=5 合法化的证据。

## 3.7 Episode start / end

```text
EPISODE_START / EPISODE_END
不是 Canonical Human Boundary
不是 Predicted Final 的匹配对象
```

引擎把它们当 segment 端点，不进入 `final_boundaries.csv` 的审核单元。Matching **不做** start/end 特例：不自动把 frame=0 / frame=n-1 配成 GT，也不对靠近两端的 pred 放宽 T。

若未来 Human Added 明确加在 0 或末帧，按普通 GT 处理。

## 3.8 不按 Primary Type 过滤主指标

主 Precision / Recall / F1 在 **全部 Final vs 全部 Canonical GT** 上计算。  
Guardrail 与 error-mode 指标再按 **GT 来源子集** 或 **pred 诊断标签** 切片（见 §10 / §11）。这样合并簇代表类型变化不会直接打崩总分，同时又能量化「Gripper 是否被漏掉」。

---

# 4. tolerance_frames 时间语义

采样：

```text
20 Hz
dt ≈ 0.05 s
```

| ±N frames | 时间半宽 | 全窗口宽度 | 与当前 exploratory 机制的相对位置 |
| ---: | ---: | ---: | --- |
| ±1 | 0.05 s | 0.10 s | 小于 1 个 persistence tick |
| ±2 | 0.10 s | 0.20 s | 接近 gripper/motion persistence=4 的一半 |
| ±3 | 0.15 s | 0.30 s | 约 3 ticks；仍可视为同一瞬间过渡 |
| ±5 | 0.25 s | 0.50 s | schema reserved；≈ pause_bridge/consolidation 的短边 |

物理语义（Can 桌面操作，非正式数据拟合）：

- 夹爪开合本身持续数帧（exploratory `gripper_persistence_frames=4` = 0.20 s）。把「同一 gripper transition」的定位误差看成 ±0.15–0.25 s 是协议层合理范围。
- 方向转折的 representative 是 evidence 峰值，峰值相对视觉转折差 1–3 frames 常见。
- 0.50 s（±5 的全宽）开始接近「相邻但不同的微操作」；本样本独立 VALID DIRECTION 最小间距约 13 frames = 0.65 s，所以 ±5 在 **当前 6 条** 上撞车风险低，但不能外推到更密的未来 GT。

**不能**因为 config 里已有 `boundary_tolerance_window=5` 就冻结 5。该字段注释写明：*Schema reserved for G1-P3 Human Boundary matching. Not used by the G1-P2 segmenter.*

**不能**从当前 6 条估计最佳 T：MISALIGNED=0，没有 corrected_frame 分布。

```text
TOLERANCE_DESIGN =
NEEDS_EXPLICIT_OWNER_DECISION

TOLERANCE_POLICY =
OWNER_DECISION_REQUIRED

CANDIDATE_SET =
{ ±3 frames = 0.15 s ,  ±5 frames = 0.25 s }
```

Designer 倾向（**不是冻结值**）：

```text
DESIGNER_RECOMMENDATION_NOT_FROZEN = ±3
```

理由：更接近「同一瞬间过渡」而不是「半秒内任意事件」；与 persistence/debounce 同量级；当前 GT 间距下 ±3 与 ±5 都不会误配独立 event。  
若 Owner 更担心 representative 峰值漂移，可选 ±5。  
**禁止**把 T 放进 parameter search。T 是 metric 合同，不是 Detector 旋钮。选定后，Calibration 与 Evaluation 使用同一 T，且 Evaluation 不得再改 T。

诊断窗口（不进正式 F1）：

```text
DIAGNOSTIC_TOLERANCE_SWEEP = {1, 2, 3, 5}
仅报告敏感性，不用于选 config
```

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
CANONICAL_GT_RULE = YES_AS_DRAFT_RECOMMENDATION
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

# 6. Human GT Export 对接（只设计接口）

Frozen 逻辑名：

```text
P2_G1_HUMAN_CALIBRATION_EXPORT_V1
```

目录（Web Design FROZEN）：

```text
human_calibration_export/
├── export_meta.json
├── signal_review.csv
├── predicted_boundary_review.csv
└── human_added_boundary.csv
```

## 6.1 何时执行 Batch 3 Export

建议触发条件（全部满足）：

```text
1. 本 Calibration Design 经 Owner Review（可带少量修订）后不再改 matching/T/GT 规则
2. Calibration Episode 名单已按 §8 规则冻结到 Manifest
3. 这些 Episode 的 P1 全 PASS 或 Owner 书面接受例外
4. 这些 Episode 的 P2 无 NOT_REVIEWED
5. Web 实现 Export（当前 Batch 3 尚未做；本轮不实现）
```

当前 6 条 Exploratory **可以**在 Owner 接受 Seed 政策后被 Export，但 Export 的 `run_stage` 必须仍记录源 run 为 `EXPLORATORY_AUDIT`。不得改写源 Audit Run 的 `set_role`。

## 6.2 Export 字段 → Canonical / Scoring

`export_meta.json`（Frozen 最低集 + P3 需要的扩展，扩展待 Batch 3 实现时写入，本轮不改 Web）：

```text
export_id
source_run_id
run_stage
config_hash
signal_contract_hash
created_at
review_snapshot_time
episode_count
```

建议 Batch 3 增加（接口设计，未实现）：

```text
export_contract = P2_G1_HUMAN_CALIBRATION_EXPORT_V1
set_role_intended            # CALIBRATION_SEED / CALIBRATION / EVALUATION_HOLD
must_not_feed_evaluation
canonical_gt_snapshot_id     # 可由 P3 派生后回填，不要求 Web 当时就有
```

`predicted_boundary_review.csv` → Canonical 的 VALID/MISALIGNED 行 + known-FP 锚点。  
`human_added_boundary.csv` → Canonical 的 HUMAN_ADDED 行。  
`signal_review.csv` → Calibration Episode 准入门（P1 FAIL 则该 episode 不得用于选参，除非 Owner 例外）。

P3 对 Evaluation Export 的硬约束（Frozen Web Design 已有）：

```text
MUST_NOT_FEED_BACK_TO_CALIBRATION
```

---

# 7. 当前 6 条 Exploratory 的角色

```text
Exploratory Audit
= failure-mode discovery
+ Calibration protocol design evidence
≠ 正式 Calibration metric dataset（缺省）
≠ Evaluation Set（永久禁止）
```

允许的升级路径（必须显式，禁止静默）：

```text
EXPLORATORY_SEED_FOR_CALIBRATION
```

含义：

1. 保持源 run：`run_stage=EXPLORATORY_AUDIT`，`set_role=EXPLORATORY` 不变。
2. 经 Batch 3 Export 后，P3 派生 Canonical GT snapshot，标记：

```text
gt_origin = EXPLORATORY_AUDIT_DISCOVERY
source_run_id = g1_exploratory_audit_20260917_141541_fe251439
usable_as = CALIBRATION_SEED
forbidden_as = EVALUATION
search_surface_leakage = YES
```

3. 正式 Calibration Run 使用 `run_stage=CALIBRATION`、`set_role=CALIBRATION`，episode 可包含这 6 条 **加上** 按规则新选的保护样本。
4. 新 Calibration Run 必须重新生成预测；人工 **不必** 对未改 signal contract 的 P1 重标；P2 不必对旧 boundary_id 重标。评分走 Canonical GT matching。
5. 若 Owner 要求「校准 GT 必须是未见过 search surface 的样本」，则这 6 条只留作 diagnostic fixture，另选 10–20 条全新 Calibration。这是 Owner 决策，见 §19。

风险（必须披露）：

```text
这 6 条已经用于发现 MODE_01/02/03 并设计 search surface。
用它们选参，会高估对「已看见的失败模式」的改善。
因此它们永远不能进入 Evaluation Set。
```

---

# 8. Calibration / Evaluation Dataset Design

## 8.1 数量权威

Roadmap P2-S1C：

```text
首版 CALIBRATION_SET = 10–20 Episodes
具体 IDs 冻结在 Manifest
```

当前只有 6 条已审核 Exploratory，**不够单独构成正式 Calibration Set**，更不够当评测集。

## 8.2 Calibration Episode Selection Rule

不在本轮点名新 `demo_*`，除非它们已在候选池中。当前明确候选池 = 这 6 条 smoke episodes。其余从 Can/MH 按规则抽。

必须同时覆盖（同一 episode 可满足多项）：

| 覆盖轴 | 本 6 条现状 | 规则要求 |
| --- | --- | --- |
| 简单 / 短 | demo_32 (98), demo_0 (118) | 至少 2 条短、低 Final 数、全 VALID 类 |
| 复杂 / 长 | demo_278 (206, 9 Final), demo_242 (232, 10 Final) | 至少 2 条长或高 Final 数 |
| GRIPPER-heavy | BETTER 三条多为 Gripper 代表 + 合并 Direction | 至少 3 条 Gripper Primary 占主导且现网切对 |
| DIRECTION-heavy | demo_278 / demo_242 | 至少 2 条含独立 Direction |
| direction jitter | demo_242 MODE_01 | 至少 1 条（可 seed） |
| short-pause-like | demo_278 MODE_02 | 至少 1 条（可 seed） |
| merged cluster | demo_0/32/179/230/242 多条 VALID 合并簇 | 至少 3 条 |
| 独立有效 direction | 6 条 VALID DIRECTION | 至少 3 个 event，最好跨 episode |
| 质量分层 | BETTER/OKAY/WORSE 都有 | 不要只抽 WORSE |
| Positive preservation | demo_0/32/179/230 全 VALID | **必须**包含「现在切对」的例子 |
| Error correction | demo_278/242 | **必须**包含「现在切错」的例子 |

禁止：

```text
只选当前错误 Episode
只优化消灭 FP
把 Evaluation 候选先拿来「看看再决定」
用 quality_group 或 RoboMimic split=TRAIN 代替 P2 set_role
```

建议构成（数量由 Owner 在 10–20 内拍板）：

```text
CALIBRATION_SEED  ⊂  当前 6 条 Exploratory（推荐全收，因其 complementary）
+ CALIBRATION_HOLD_IN_NEW  = 尚未用于设计 search surface 的新 episode
  其中至少一半是 preservation-like（预期当前 detector 大体正确）
```

```text
CALIBRATION_SET_POLICY =
SELECTION_RULE_FROZEN_IN_THIS_DRAFT
EPISODE_IDS = NOT_PICKED_THIS_ROUND_EXCEPT_SEED_POOL
SEED_POOL = the_6_exploratory
TARGET_N = 10–20
```

## 8.3 Evaluation Episode Selection Rule

```text
EVALUATION_SET_POLICY =
DISJOINT_FROM_CALIBRATION_AND_EXPLORATORY
NEVER_USED_FOR =
  threshold selection
  strategy selection
  tolerance selection
  search-surface design
  error-mode invention
```

规则：

1. 与 Calibration Set、Exploratory 6 条 **episode_id 完全不相交**
2. 覆盖轴与 Calibration 同构（简单/复杂、Gripper/Direction、合并簇），避免评测集全是 BETTER 短轨迹
3. 正式 Evaluation GT 在 **Config Freeze 之后** 才允许用于打分；此前这些 episode 甚至不应进入带 Human Review 的「边看边调」循环
4. 允许预先选 ID 进 `EVALUATION_HOLD` Manifest，但 `run_stage` 在 Freeze 前不得跑正式 EVALUATION
5. Evaluation Human GT 可以保存，**禁止回灌 Calibration / 禁止改 T / 禁止改 search**
6. 若 Evaluation 差：返回 Design Review，另开新 Evaluation Set 或接受 limitation。不得在原 Evaluation Set 上继续调参

本轮 **不挑选** 具体 Evaluation episode IDs。当前 workspace 没有独立 Evaluation 候选池 Manifest。

## 8.4 Run 身份隔离

Frozen Web Design：

```text
v1 不允许一个 Run 混合 Calibration + Evaluation Episode

run_stage = EXPLORATORY_AUDIT → set_role = EXPLORATORY
run_stage = CALIBRATION       → set_role = CALIBRATION
run_stage = EVALUATION        → set_role = EVALUATION
```

正式 Calibration 迭代：

```text
run_stage = CALIBRATION
parent_run_id = <previous calibration or exploratory seed>
config_version = human-readable
config_hash = SHA256(canonicalized segmentation config)
signal_contract_hash = ...
created_at = ...
immutable run directory
禁止 overwrite
```

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

校准主目标：减少 REDUNDANT Direction Final。  
硬约束：不能为了消灭 7 个 Direction FP 把合法 Direction / Gripper / 合并簇一起抑制。

保护子集来自 Canonical GT 的 `protected_class`，在 seed 上可从 Exploratory 审核物化：

```text
G_GRIPPER
  = Canonical GT 来自 VALID GRIPPER_TRANSITION Primary
  当前 seed：18

G_VALID_DIRECTION
  = Canonical GT 来自 VALID DIRECTION_CHANGE Primary（独立，未并入夹爪）
  当前 seed：6

G_MERGED_CLUSTER
  = Canonical GT 来自 VALID 且 member 同时含 GRIPPER 与 DIRECTION
  当前 seed：13 簇，全部 VALID
```

指标：

```text
GRIPPER_RECALL
  = TP ∩ G_GRIPPER  /  |G_GRIPPER|

KNOWN_VALID_DIRECTION_RECALL
  = TP ∩ G_VALID_DIRECTION  /  |G_VALID_DIRECTION|

KNOWN_VALID_MERGED_CLUSTER_RECALL
  = TP ∩ G_MERGED_CLUSTER  /  |G_MERGED_CLUSTER|
```

形式：

| Guardrail | 形式 | 选参时 |
| --- | --- | --- |
| GRIPPER_RECALL | **HARD** | 必须 = 1.0。任何 FN 直接淘汰 config |
| KNOWN_VALID_MERGED_CLUSTER_RECALL | **HARD** | 必须 = 1.0 |
| KNOWN_VALID_DIRECTION_RECALL | **HARD on seed / SOFT later** | Seed 上 6/6 必须保持。新 Calibration 扩样本后，若 Owner 未改规则，默认仍 HARD=1.0；若新样本证明部分「VALID Direction」本身有争议，才允许 Owner 改成「最多 1 个 FN」 |
| Overall FN 相对 baseline 上升 | **HARD** | `FN_new > FN_baseline` → 淘汰（baseline = exploratory config 在同一 Canonical GT 上的匹配结果） |
| 新 error mode / 新 DIRECTION-only FP 大爆发 | **SOFT** | 报告；若 Precision 升但出现新的 gripper 附近碎片，人工看 |

解释：当前 seed 上 Gripper / 合并簇 / 合法独立 Direction 是 **零容忍回归**。样本小，HARD=100% 可执行。这不是声称生产系统永远 100%，而是 **这轮校准不允许用它们换 FP**。

Baseline Calibration Run（exploratory config，不改参数）必须先打出这些 guardrail 的基线值，作为后续所有 config 的对照。

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

## 12.3 正式 Search Surface（推荐）

```text
SEARCH_SURFACE =
STAGED_AND_BOUNDED

STAGE_A_PRIMARY =
  direction_change_threshold
  direction_persistence_frames

STAGE_B_LIMITED =
  boundary_consolidation_window ∈ {8, 10, 12}   # 讨论范围，本轮不跑
  不可无限扩大

STAGE_C_REGRESSION =
  不搜新轴
  只复查 guardrail / NEW_FN / gripper / merged / valid-direction

OUT_OF_SCOPE_UNTIL_SEMANTIC_MISMATCH_INVESTIGATION =
  pause_bridge_duration
  pause_bridge 触发条件改写（那是 Design Change，不是数值搜索）

CONTRACT_CHANGING_OPTIONAL_LATER =
  P1 direction_window_frames
  P1 direction_min_window_displacement_m
  若进入，必须新 signal_contract_hash + 重做 P1 review
  不得藏进 Stage A 网格

NOT_A_SEARCH_AXIS =
  boundary_tolerance_window / tolerance_frames
  gripper_* （本样本 18/18 VALID，禁止为 Direction FP 去动 Hard Boundary）
  rotation/action support thresholds（不能单独成刀）
```

## 12.4 为什么 threshold-only 不够

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

比较：

| | Grid Search | Staged Search |
| --- | --- | --- |
| 做法 | 多参数笛卡尔积 | 先候选质量，再有限 consolidation，再回归 |
| 可解释性 | 差：不知道是谁修好的 | 好：每阶段对应 MODE |
| 规模 | P2 正式参数约 18 个；即使只取 Roadmap 的 7 个，粗网格也爆炸 | Stage A 两轴 + Stage B 三值 |
| 与归因对齐 | 弱 | 强：MODE_01/02→A，MODE_03→B |

真实参数规模下的建议：

```text
SEARCH_STRATEGY = STAGED_CALIBRATION
NOT_FULL_GRID
```

```text
Stage A  Direction candidate quality
  只动 P2 direction_change_threshold × direction_persistence_frames
  对照 known VALID vs REDUNDANT Direction
  目标：MODE_01 / MODE_02 下降，且 G_VALID_DIRECTION Recall 不降

Stage B  Consolidation
  仅当 Stage A 后 MODE_03 仍在，或 A 已稳定
  window ∈ {8,10,12} 单因素
  同时盯独立 Direction 是否被误 merge

Stage C  Interaction / regression
  不引入新轴
  复查 GRIPPER / MERGED / VALID_DIRECTION / NEW_FN / fragmentation
  若只有 trade-off → STOP
```

coarse→fine 允许在 **单一轴内部** 先宽后窄，例如 persistence 先 {3,4,5,6} 再局部加密。禁止把 consolidation、pause_bridge、P1 window 一次性乘进去。

Roadmap 示例 strategy A/B/C/D（move+gripper ± direction ± pause ± consolidation）是架构级能力开关。当前引擎 **已经** 开着 direction + pause + consolidation。本轮不是开关这些能力，而是校准已开能力的数值，并调查 pause 语义错配。

---

# 17. Calibration Run Lineage

未来正式 Run：

```text
run_stage = CALIBRATION
```

每个 Detector 参数 / strategy 改动 → **新的 immutable run directory**。禁止覆盖。

`run_meta.json` 最低字段（Web Frozen + 本设计）：

```text
contract_version
run_id
run_stage                  # CALIBRATION
set_role                   # CALIBRATION（manifest 每行）
created_at
parent_run_id              # 指向 baseline 或上一轮
config_version
config_hash
segmentation_version
signal_contract_version
signal_contract_hash
source_dataset_id
episode_count
canonical_gt_snapshot_id
human_export_id
matching_rule_id
tolerance_frames           # Owner 选定后写入，此后只读
search_stage               # A / B / C / BASELINE
```

Baseline：

```text
第一轮正式 Calibration Run
= 当前 exploratory config 原样
+ set_role=CALIBRATION 的 episode 集
+ 冻结 matching / T / Canonical GT
不改 threshold
用于产生可比较的 TP/FP/FN 基线
```

---

# 18. Calibration Scoring Procedure

对每个新 immutable Calibration Run：

```text
1. 读取 Canonical Human Boundary GT snapshot
   （不是 SQLite，不是旧 boundary_id）
2. 读取本 run 的 Predicted Final Boundaries
3. 按冻结 MATCHING_RULE + tolerance_frames 匹配
4. 计算 TP / FP / FN / Precision / Recall / F1
5. Localization Error
6. Guardrail recalls
7. MODE_01/02/03 remaining vs fixed
8. NEW_FN / NEW_UNANCHORED_FP
9. over-segmentation / mean pred count
10. 与 parent/baseline 做差分表
```

禁止：

```text
new boundary_id == old boundary_id  作为命中
用 Evaluation Export 调参
改 T 来让 F1 变好看
```

---

# 19. Config Selection Rule

不透明加权分禁止。

```text
CONFIG_SELECTION_RULE =
LEXICOGRAPHIC_CONSTRAINED
```

对通过准入的 config，按下列字典序比较；任一层 HARD 失败即淘汰，不看后面的 F1。

```text
L0  Feasibility
    P1 signal gate 通过
    匹配合同与 T 未改
    Canonical GT snapshot 相同

L1  HARD guardrails
    GRIPPER_RECALL = 1.0
    KNOWN_VALID_MERGED_CLUSTER_RECALL = 1.0
    KNOWN_VALID_DIRECTION_RECALL = 1.0     # seed；扩样本后见 §10
    FN_new <= FN_baseline

L2  主校准目标
    MODE_01_REMAINING + MODE_02_REMAINING  更小者胜
    若并列：FP 更小者胜（即 REDUNDANT_PROXY）

L3  MODE_03
    MODE_03_FIXED 优先，但不允许用 L1 失败换取
    MEDIUM 单条允许残留，若 L2 已明显改善

L4  综合参考
    Boundary F1 更高者胜
    再并列：Localization p90 更小
    再并列：mean predicted boundaries 更接近 n_gt
    再并列：更简单的改动（更少搜索轴被改动）胜
```

解释：先保护 Gripper / 合并簇 / 合法独立 Direction / 不制造漏检，再消灭已归因的 Direction FP，F1 只在约束满足后当决胜。这对应 Master「Hard Interaction Boundary Recall 优先级高于单一总分」。

---

# 20. Stop Rule

停止 Calibration、冻结 config、进入 Evaluation，当下列任一 **停止条件** 成立，且 L1 guardrail 仍绿：

```text
STOP_RULE =

S1  MODE_01 与 MODE_02 的 remaining = 0
    或 remaining 已明显下降且下一档参数开始降低 VALID Direction Recall

S2  继续改参只在 Precision 与 Recall / 合法 Direction 之间 trade-off
    连续两轮 Stage A/B 无法同时改善 L2 且保持 L1

S3  Protected behavior 开始退化
    任何 HARD guardrail < 1.0 → 该 config 淘汰；
    若所有邻近点都退化 → 停止搜索，回到 Design Review
    （可能需要 SEMANTIC MISMATCH 或 Design Change，而不是再扫网格）

S4  Calibration set 改善无法再提供泛化信息
    只剩对 seed 6 条的记忆性修补（例如专为 demo_242 @136 调 window）
    而新的 CALIBRATION_HOLD_IN_NEW 上无对应收益

S5  Owner 书面宣布 CALIBRATION_CONFIG_FROZEN
```

然后：

```text
FROZEN CONFIG
→ EVALUATION
不得再用 Evaluation 反馈改参
```

MODE_03 单独残留 **不是** 必须继续搜的理由。

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
Exploratory Audit
  run_stage=EXPLORATORY_AUDIT
  当前 6 条 fe251439
        ↓
Error Attribution
  PASS_READY_FOR_CALIBRATION_DESIGN
        ↓
Calibration Protocol Freeze          ← 本 DRAFT；Owner Review 后才算冻结
  MATCHING_RULE / T / Canonical GT / split / metrics / search / stop
        ↓
Batch 3 Human Calibration Export     ← 尚未实现；P3 只读 Export
        ↓
Calibration Set + Canonical Human GT
  含可选 EXPLORATORY_SEED，禁止当 Evaluation
        ↓
Baseline Calibration Run
  同 exploratory 参数，新 run_id，run_stage=CALIBRATION
        ↓
Detector Iteration                   ← 仅 Stage A/B/C，不可覆盖旧 run
        ↓
New Immutable Calibration Run
        ↓
GT Matching + Metrics
  Canonical GT ↔ new Finals
        ↓
Config Selection
  lexicographic L0–L4
        ↓
Stop Rule → Config Freeze
        ↓
Independent Evaluation Run
  全新 episode，只跑一次
        ↓
Final G1 Freeze
  或 Evaluation 失败 → Design Review（不回灌原 Eval Set）
```

---

# 23. Design Decisions（本 DRAFT 明确项）

```text
MATCHING_RULE =
  ONE_TO_ONE_GREEDY_NEAREST_WITHIN_TOLERANCE
  match_key = (episode_id, frame)
  uniqueness = bipartite 1-1
  type-aware = DIAGNOSTIC_ONLY

TOLERANCE_POLICY =
  OWNER_DECISION_REQUIRED
  candidates = {±3 frames = 0.15s, ±5 frames = 0.25s}
  designer_recommendation_not_frozen = ±3
  not_from_exploratory_schema_5
  not_fitted_from_current_6
  T is metric contract, not a search axis

TOLERANCE_DESIGN =
  NEEDS_EXPLICIT_OWNER_DECISION

CANONICAL_GT_RULE =
  VALID      → gt_frame = predicted_frame
  MISALIGNED → gt_frame = corrected_frame
  REDUNDANT  → 不进入 GT；进入 known-FP 锚点
  MISSED     → gt_frame = human_added_frame
  metric 不依赖旧 boundary_id
  provenance 必须保留

CALIBRATION_SET_POLICY =
  selection rule，不在本轮点新 ID
  target_n = 10–20
  must include preservation + error cases
  exploratory 6 = seed 候选，不是自动正名
  EXPLORATORY_SEED_ALLOWED = YES_WITH_PROVENANCE
  SEED_NEVER_EVALUATION = YES

EVALUATION_SET_POLICY =
  disjoint episode_id
  unused until config freeze
  no tuning / no T change / no strategy change
  failure → Design Review, not retune-on-eval

PRIMARY_METRICS =
  Boundary Precision
  Boundary Recall
  Boundary F1
  over-segmentation count
  mean predicted boundaries per episode
  FP as REDUNDANT_PROXY
  FN as MISSED_PROXY
  Localization Error on TP as MISALIGNED_PROXY

PROTECTED_GUARDRAILS =
  GRIPPER_RECALL HARD = 1.0
  KNOWN_VALID_MERGED_CLUSTER_RECALL HARD = 1.0
  KNOWN_VALID_DIRECTION_RECALL HARD = 1.0 on seed
  FN_new <= FN_baseline HARD

SEARCH_STRATEGY =
  STAGED_CALIBRATION
  A direction candidate quality
  B limited consolidation
  C regression only
  NOT full grid

SEARCH_SURFACE =
  Stage A: direction_change_threshold, direction_persistence_frames
  Stage B: boundary_consolidation_window ∈ {8,10,12}
  pause_bridge_duration = NOT_PRIMARY
  P1 evidence windows = contract-changing optional later
  tolerance = NOT_A_SEARCH_AXIS

CONFIG_SELECTION_RULE =
  LEXICOGRAPHIC_CONSTRAINED
  L1 guardrails → L2 MODE_01/02+FP → L3 MODE_03 → L4 F1/localization/simplicity

STOP_RULE =
  modes reduced OR only trade-offs remain OR protected regression OR seed-memorization
  then FROZEN CONFIG → EVALUATION
```

---

# 24. Owner 必须亲自决定的事项

证据不足或涉及评测泄漏，本 DRAFT **不代为拍板**：

```text
OWNER_DECISION_REQUIRED_1
  tolerance_frames ∈ {±3, ±5}
  或书面选择其他 protocol-level T
  选定后 Calibration 与 Evaluation 共用，禁止再搜

OWNER_DECISION_REQUIRED_2
  当前 6 条 Exploratory 是否整包进入 CALIBRATION_SEED
  选项：
    A. 全 6 条 seed + 另选新样本补到 10–20
    B. 6 条只作 diagnostic fixture，Calibration GT 全部新选
    C. 只 seed 错误条（278/242）—— 本设计反对，因缺少 preservation

OWNER_DECISION_REQUIRED_3
  Calibration 目标 N 在 10–20 内的具体数字
  以及新样本是否必须在 search 开始前全部完成 Human Review

OWNER_DECISION_REQUIRED_4
  KNOWN_VALID_DIRECTION_RECALL 在扩样本后是否保持 HARD=1.0
  还是允许 1 个 FN 的 soft cap

OWNER_DECISION_REQUIRED_5
  Batch 3 Export 是否以这 6 条 Exploratory 为第一包
  （实现仍未开始；本轮只问政策）
```

---

# 25. 下一步 Gate

本文件不是 FROZEN。下一步：

```text
1. Design Owner Review 本 DRAFT
2. 拍板 §24 的 3–5 项
3. 若无结构性反对 → 把本 DRAFT 升为 FROZEN Calibration Protocol
   （另开文档版本，不把本文件直接改名 FROZEN）
4. 然后才允许：
     Batch 3 Export 实现
     Canonical GT snapshot 实现
     Baseline Calibration Run
     Stage A 搜索
5. 在此之前禁止 parameter search
```

```text
NEXT_GATE =
OWNER_REVIEW_OF_G1_P3_CALIBRATION_DESIGN_DRAFT_V1
```

---

# 26. 本轮未做（刻意）

```text
未修改 Detector / threshold / consolidation / pause_bridge
未执行任何 search
未生成 Calibration / Evaluation Run
未改 SQLite
未重标 6 条
未实现 Export
未挑选 Evaluation episode IDs
未冻结 tolerance_frames 的最终整数
```

---

# 27. 文档状态

```text
DOCUMENT = Project2_G1_P3_Calibration_Design_DRAFT_v1_20260917.md
STATUS   = DRAFT_v1
FROZEN   = NO

G1_P3_CALIBRATION_DESIGN =
DRAFT_READY_FOR_OWNER_REVIEW
```
