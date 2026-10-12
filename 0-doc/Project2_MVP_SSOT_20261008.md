# Project 2 MVP SSOT｜Robot Demonstration Mining & VLA Data Curation MVP
## 2026-10-08｜ACTIVE MVP EXECUTION AUTHORITY

> Status: ACTIVE
> Repository: `Modori1998/embody_project2_data_value`
> Baseline main HEAD at rebaseline: `7efae2b710ef749b2e3aa793667eb43adad4d90c`
> This file is a NEW MVP SSOT. It does NOT replace or overwrite the full Project 2 Engineering SSOT.
> 2026-10-08 Retrieval-first amendment: Core MVP is now representation + cross-episode retrieval evidence; VLM / Dedup / Long-tail / Coverage are conditional extensions.

> 2026-10-09 Owner Freeze Reconciliation: Design Owner accepts the remaining MVP decisions discussed in chat. This confirmation is reconciled against newer already-frozen GitHub artifacts; it does not roll back `MVP_CORE_RETRIEVAL_PROTOCOL_v1` or the CLOSED_PASS M2 implementation.

### 2026-10-09 Owner Freeze Reconciliation

```text
OWNER_DECISION = CONFIRMED

M2_MIDDLE =
TEMPORAL_MIDDLE
floor((start_frame + end_frame) / 2)
STATUS = ALREADY_IMPLEMENTED_AND_FROZEN

M2_GRIPPER_EVENT =
CURRENT_CLOSED_PASS_RULE_RETAINS_AUTHORITY
GRIPPER_EVENT = segment.start_frame
iff left Final Boundary type = GRIPPER_TRANSITION
STATUS = ALREADY_IMPLEMENTED_AND_FROZEN
NOTE = supersedes earlier unimplemented "nearest-to-center among multiple events" suggestion

MOTION_ACTION_MAGNITUDE =
FORMAL_CORE_RETRIEVAL_FEATURE
action_magnitude_mean/max/std
STATUS = ALREADY_FROZEN_BY_MVP_CORE_RETRIEVAL_PROTOCOL_v1
NOTE = supersedes earlier "diagnostic-only" suggestion

M3_FORMAL_VLM_IF_BRANCH_OPENS =
Qwen3-VL-8B-Instruct
STATUS = OWNER_FROZEN_DEFAULT_MODEL_FAMILY
BRANCH_STATUS = CONDITIONAL_NON_BLOCKING
EXACT_CHECKPOINT_REVISION = RUNTIME_PIN_PENDING
G3_MVP_TAXONOMY = PENDING_MINIMAL_FREEZE

CORE_RETRIEVAL_PRIMARY =
GLOBAL_CROSS_EPISODE_RETRIEVAL
STATUS = ALREADY_FROZEN_BY_MVP_CORE_RETRIEVAL_PROTOCOL_v1

WITHIN_PHASE_FINE_GRAINED_RETRIEVAL =
SECONDARY_ANALYSIS
NOT_FORMAL_CORE_PRIMARY
NOTE = supersedes earlier unimplemented suggestion to make it the primary retrieval target
```

Authority rule for this reconciliation:

1. Existing later `FROZEN_v1` protocol / manifest and CLOSED_PASS implementation artifacts outrank earlier chat proposals when they conflict.
2. This owner confirmation freezes the compatible remaining choice for the conditional VLM branch without reopening the Core Retrieval protocol.
3. Any future change to Motion feature composition, GRIPPER_EVENT semantics, or Global-vs-Within-phase Formal Retrieval requires a new Design Change Request and protocol version.

---

# 0. 文档定位与权威关系

本文件定义 Project 2 的 **MVP Execution Scope（最小可交付执行范围）**，目标是把现有完整研究路线压缩为一个更贴合具身数据算法 / VLA 训练数据岗位的可运行、可评估、可面试展示的项目。

原详细设计继续保留，尤其包括：

- `0-doc/Project_2_Engineering_Design_Master_v1_20260914.md`
- `0-doc/Project2_Development_Roadmap_and_Design_Gate_Plan_v1_20260914.md`
- `0-doc/02_robot_demonstration_mining_autolabel_design.md`

权威规则：

1. 已冻结的底层语义、Source Contract、G1 Segment 定义、G1/G3 语义职责边界与既有证据边界，继续以 Full Engineering SSOT 为准；**G3 完整 taxonomy 尚未冻结**，MVP 只允许后续单独冻结最小标签集合。
2. MVP 的范围、执行顺序、必做产物、砍项和验收标准，以本文件为当前执行 authority。
3. 本文件只做 Scope Compression（范围压缩），不删除 Full Design。
4. MVP 完成后，如继续做研究完整版，可重新回到 Full SSOT 的 G2–G8 路线。
5. 本文件不得被解释为 Full Project 2 已完成。

---

# 1. 为什么做 MVP Rebaseline

当前 GitHub 状态：

- G1 Design: FROZEN
- G1 Implementation: COMPLETE
- G1 Human Calibration: COMPLETE
- G1 Final Config: FROZEN_v1
- G1 Independent Human Evaluation: DEFERRED_NOT_EXECUTED
- G1 status: `CLOSED_WITH_EVALUATION_DEFERRED`
- G2 Design / Formal Implementation: OPEN

当前最适合进行 Scope Compression：G1 已有真实工程资产，而 G2–G7 尚未形成大量不可逆实现成本。

本次 Rebaseline 的求职依据来自 Google Drive 岗位池 `work项目岗位库_具身相关岗位` 的当前技能需求。高频且与 P2 直接相关的能力包括：

- 多模态机器人数据
- VLA 训练数据 / Data-centric Robot Learning
- 自动标注 / 预标注
- 数据质量、清洗、异常和噪声过滤
- Embedding / 向量检索
- 去重
- 长尾 / Corner Case / 难例
- 数据分布 / 多样性 / 覆盖
- Benchmark / 人工评测
- Data→Model 闭环意识

因此 MVP 优先证明：**能把机器人 demonstration 变成可自动标注、可向量检索、可去重、可找长尾和覆盖稀疏区的数据资产。**

---

# 2. P2 MVP 的唯一核心目标

Project 2 MVP 定位：

**Robot Demonstration Mining & VLA Data Curation MVP（机器人示范数据挖掘与 VLA 训练数据策划 MVP）**。

本轮采用：

**Retrieval-first MVP（检索优先 MVP）**。

核心命题不是“把所有数据工具都做一遍”，而是：

> **机器人行为片段的 Visual Representation（视觉表征）与 Robot Motion Representation（机器人运动表征）是否能支持人工认为真正相关的跨 Episode 相似检索，并提供可验证的独立或互补增量。**

输入：RoboMimic Can/MH robot demonstrations。

核心主链路：

~~~text
RoboMimic Episode
→ existing Frozen G1 Segment
→ minimal keyframes + robot motion summary
→ clean RGB model input
→ Motion-only retrieval
   vs
   SigLIP2-only retrieval
   vs
   optional fixed Late Fusion
→ cross-episode Top-K
→ independent human relevance audit
→ GO / CONDITIONAL / STOP
~~~

只有 Core Retrieval evidence 成立后，才条件进入：

~~~text
Single-VLM structured auto-label
Dedup Candidate
Long-tail / Sparse Candidate
Coverage summary
Curation Manifest
~~~

本项目核心先回答：

1. 不用视觉模型，只靠 robot motion 能检索到什么？
2. SigLIP2 视觉表征是否提供独立增量？
3. Visual 与 Motion 是否存在稳定互补？
4. Top-K 的“相关”是否经独立人工 rubric 验证，而不是由模型自己的标签循环定义？

Conditional Extension（条件增强）再回答：

- 数据里有哪些受控行为 / 交互语义？
- 哪些样本是近重复候选？
- 哪些样本属于稀疏 / 长尾候选？
- 哪些视角存在覆盖薄弱区？

本项目不直接回答：

- 哪些样本一定更有训练价值；
- 某个 rare sample 加权后一定提升 policy；
- 某个 coverage gap 补齐后一定提升成功率。

这些属于 Project 3 / 后续 Data→Model 验证。

---

# 3. MVP Multi-view Dataset Map

P2 MVP 不训练统一“超级 Embedding”，而保留互补证据。

| View | 中文解释 | Formal Source | MVP 角色 |
|---|---|---|---|
| Visual Instance View | 视觉实例视角 | SigLIP2 image embedding | **Core**：视觉相似检索 |
| Robot Motion View | 机器人运动视角 | EEF / gripper / action-state feature | **Core Baseline**：运动相似检索 |
| Semantic View | 语义视角 | 后续最小 G3 taxonomy + Single-VLM | **Conditional Branch**：行为组织与解释，不阻塞 Core Retrieval |

原则：

- Visual / Robot evidence 分开保存。
- Motion-only 必须真实进入检索对照，不能只“存字段”。
- Semantic label 不直接塞入 visual embedding。
- G3-derived text embedding 不进入 Formal Core Retrieval。
- 如做融合，只允许 score/rank 层的透明 Late Fusion（后期分数融合）。
- Late Fusion 规则必须在 final retrieval human audit 前冻结，禁止看完 final audit 再调权重。
- Predicted motion_phase 可以作为实验性 filter，但**不能作为 Formal relevance GT**。
- same predicted label 不等于 relevant。

---

# 4. MVP 模块与前置契约

## MVP-P0A｜RGB Source and Alignment Contract｜P0 前置

当前 Can/MH raw / low_dim 不存 RGB；现有 G1 Audit MP4 来自 MuJoCo state 重渲染，并叠加 Episode ID / frame number。

因此 Formal Model RGB 输入冻结为：

~~~text
MVP_RGB_SOURCE_AND_ALIGNMENT_CONTRACT = v1

RGB_SOURCE =
P1 RoboMimicStateRenderer direct render from source STATE_t

MODEL_RGB[t] =
render(STATE_t)

TEMPORAL_ALIGNMENT =
MODEL_RGB[t] ↔ PROPRIO[t] ↔ ACTION[t]

MODEL_INPUT_COLOR_SPACE =
RGB

TEXT_OVERLAY =
FORBIDDEN

AUDIT_MP4_FRAME_AS_MODEL_INPUT =
FORBIDDEN

LOSSY_VIDEO_ROUNDTRIP =
FORBIDDEN

FORMAL_FRAME_EXPORT =
direct renderer RGB → lossless PNG / in-memory RGB

CAMERA / RESOLUTION / RENDERER CONFIG =
inherit active P1 renderer and record exact runtime provenance
~~~

解释：

- **Clean RGB｜干净 RGB**：直接使用 renderer 返回的原始画面，不先写入带字 MP4 再截图。
- **Alignment｜时间对齐**：frame index t 必须对应同一个 source state/proprio/action 时间索引。
- 任何 resize / crop / normalization 属于后续 encoder preprocessing，必须单独 version，不得隐式改变 source RGB contract。

状态：

~~~text
RGB_CONTRACT_DESIGN = FROZEN_v1
RGB_RUNTIME_VALIDATION = PENDING_LOCAL_SMOKE
~~~

Runtime smoke 未通过前，禁止开始正式 SigLIP2 / VLM batch。

---

## MVP-P0B｜Minimal G3 Taxonomy Authority Fix｜P0 前置

Full Engineering SSOT 已冻结的是：

~~~text
G1 = unlabeled segment boundary
G3 = semantic naming from RGB/keyframes + robot/action summary
~~~

但完整 G3 taxonomy 当前**没有正式关闭 Design Gate**。

因此本 MVP 状态修正为：

~~~text
G3_SEMANTIC_RESPONSIBILITY = FROZEN
G3_MVP_TAXONOMY = PENDING_MINIMAL_FREEZE
~~~

旧文档中的：

~~~text
approach / grasp / lift / transport / place / retract / idle / recovery / other
~~~

只能作为候选最小集合，不能在 Owner Freeze 前称为 Formal Frozen Taxonomy。

该 P0 **只阻塞 VLM branch**，不阻塞不依赖 semantic label 的 Global Retrieval core。

---

## MVP-M1｜Existing Segment Foundation

直接复用现有 Frozen G1 Segment。

必须保留：

- source_episode_id / segment_id
- start_frame / end_frame
- segmentation_version / config provenance

不再执行：

- 24-Episode held-out Human Evaluation
- G1 formal held-out scoring

Claim Boundary：

- 可以说 G1 segmentation 已实现、已 calibration、final config frozen。
- 不得说 held-out evaluation passed。

可选轻量检查：

**Downstream Input Applicability Audit（下游输入适用性核查）** 只在后续 retrieval bad case 指向 segmentation 时触发；规模限制为 3–5 Episode / 10–20 Segment，不计算 G1 Precision/Recall/F1，不替代已延期的 Independent Evaluation。

---

## MVP-M2｜Minimal Keyframe + Robot Summary

Keyframe policy 最小化为：

- START
- MIDDLE
- END
- GRIPPER_EVENT（存在时加入）

首版不做复杂 keyframe ablation。

Robot Motion Summary 最小字段：

- duration
- EEF net displacement
- EEF path length
- EEF main direction / coarse direction change
- gripper start state
- gripper end state
- gripper transition
- action magnitude summary（若 source contract 允许并明确 normalized-controller-input 语义）

Done：

- Segment → Keyframes 可追溯
- Segment → Motion Summary 可复现
- Clean RGB / Action / State 时间对应正确
- Action/State feature 后续必须进入 Motion-only retrieval baseline

---

## MVP-M4｜Core Representation

### A. Motion-only Baseline｜运动基线

从 M2 的 robot summary 构造 versioned action/state feature，并定义可复现 normalization + distance / similarity。

目的：

> 不使用视觉模型时，机器人运动特征本身能做到什么程度？

### B. SigLIP2-only｜视觉主路径

Formal Primary Visual Encoder：

- **SigLIP2 Image Encoder**
- Formal path = IMAGE_ONLY
- 输入必须来自 MVP_RGB_SOURCE_AND_ALIGNMENT_CONTRACT_v1
- 不输入 G3-derived text

Segment Visual Embedding 首版：

- same selected keyframes
- same deterministic preprocessing
- one frame embedding per keyframe
- per-frame L2 normalize
- mean pooling
- segment-level L2 normalize

同时保留 frame-level embedding 和 provenance。

### C. Late Fusion｜可选后期融合

只有 Motion-only 与 SigLIP2-only 都可运行后才允许。

要求：

- score/rank 层透明融合；
- fusion rule / weight 在 final human audit 前冻结；
- final audit 后不得调权重再复报同一结果。

### D. DINOv2

~~~text
DINOv2 = CONDITIONAL_EXTENSION
~~~

不再是 Core Must-have。只有 Core Retrieval 结果需要解释视觉 encoder failure 时再做小样本 sanity comparison。

---

## MVP-M5｜FAISS Top-K Retrieval｜Core

FAISS 保留作为向量检索工程组件：

- L2-normalized embedding
- cosine-equivalent exact search
- FAISS IndexFlatIP

但 Formal Core Result 证明的是：

~~~text
Human-reviewed retrieval relevance
~~~

而不是“用了 FAISS”。

Formal retrieval 必须包含：

1. Motion-only Top-K
2. SigLIP2-only Top-K
3. Optional frozen Late Fusion Top-K

### Formal Retrieval Isolation

~~~text
query.source_episode_id != neighbor.source_episode_id
~~~

即 **Cross-episode Retrieval（跨 Episode 检索）**。

同一 Episode 的相邻 segment 不允许进入 Formal P@5 success evidence。

### Relevance Ground Truth

~~~text
RETRIEVAL_RELEVANCE_GT =
INDEPENDENT_HUMAN_JUDGMENT
~~~

禁止：

- 用 VLM 自己预测的 motion_phase 直接给检索结果判 relevant；
- same predicted label = relevant；
- 用同一模型标签先筛候选、再用相同标签给自己打分。

Global Retrieval 作为 Formal Core 主结果。

Within-phase Retrieval 可做 secondary analysis，但只有在 phase 来源与 relevance rubric 明确隔离时才能报告。

---

## MVP-M3｜Single-VLM Structured Auto-Label｜Conditional Branch

VLM 不再阻塞 Core Retrieval。

进入条件：

~~~text
G3_MVP_TAXONOMY = FROZEN_MINIMAL
AND
RGB_RUNTIME_VALIDATION = PASS
~~~

输出目标可包含：

- motion_phase
- object_relation[]
- gripper_semantic_state
- local_success_evidence
- evidence_quality
- label provenance

执行：

- minimal taxonomy Owner Freeze
- small calibration batch
- prompt / parser / schema 修正
- prompt freeze
- small independent human review
- 仅在证据足够时扩大 batch

禁止：

- 用第二个 VLM 静默 fallback
- semantic cherry-picking
- parser 把非法语义自动改成合法语义
- 让 VLM branch 阻塞 Core Retrieval MVP

---

## MVP-M6｜Dedup + Long-tail + Coverage｜Conditional Extensions

只有 Core Retrieval Gate 为 GO / CONDITIONAL 且证据足以支撑后，才进入。

### Dedup Candidate

首版只输出 candidate，不自动 delete，不做复杂 graph transitivity。

人工 rubric：

- DUPLICATE
- NEAR_DUPLICATE
- NOT_DUPLICATE

### Long-tail / Sparse Candidate

使用简单可解释的 kNN neighborhood density / mean neighbor distance。

必须加入 baseline 对照，例如：

~~~text
kNN rarity Top-N
vs
random N
~~~

或预先冻结的 label-frequency baseline。

人工 review category：

- meaningful variation
- rare behavior / interaction
- recovery / hard case
- bad data
- label error
- representation artifact

不得把高 kNN distance 直接解释为高价值。

### Coverage

若进入该 extension，输出：

- Semantic Coverage（仅当 VLM branch 已完成并经 review）
- Visual Instance Coverage
- Robot Motion Coverage

禁止：

- rare = valuable
- duplicate candidate = delete
- coverage gap = automatic upweight

---

# 5. MVP Core Evaluation

MVP 核心只要求一个小型、独立的 Retrieval Human Audit（检索人工审计）。

## 5.1 Core Retrieval Experiment

同一批 query、同一 candidate population、同一 Episode 隔离规则，比较：

| Retrieval | 中文解释 | 测试目的 |
|---|---|---|
| Motion-only | 仅机器人运动特征 | 不使用视觉模型能做到什么 |
| SigLIP2-only | 仅视觉特征 | 视觉是否带来独立收益 |
| Optional Late Fusion | 冻结后的后期融合 | 两类信息是否互补 |

正式指标：

- Precision@5
- query-level result breakdown
- representative success / failure cases
- 若 relevance 有多级评分，可增加 nDCG@5

Human relevance rubric 必须在 final audit 前冻结。

Formal query / neighbor 必须 Cross-episode。

## 5.2 Retrieval Gate

### GO

满足至少一种：

~~~text
A. SigLIP2-only 相对 Motion-only 有稳定、可解释的 P@5 增量
OR
B. 两者 query-level failure pattern 明显互补，且预先冻结的 Late Fusion 改善总体结果
~~~

并且：

- Human relevance 判定稳定；
- 结果不是由极少数 Episode 单独驱动；
- Top-K 不是明显由文字叠层、视频压缩或其他输入伪影驱动。

### CONDITIONAL

- 总体均值接近，但存在可重复的 query-level 互补；
- 或样本量不足以做稳定结论，但 failure mode 可解释。

允许做一次有限反例分析，不允许无限加功能掩盖不确定性。

### STOP

- SigLIP2 与 Motion-only 都无法超过简单/随机相关性水平；
- Human relevance rubric 本身不稳定；
- 视觉 Top-K 主要由背景、渲染伪影、错误切段等非目标因素驱动；
- 增加更多模块不能直接修复核心 representation/retrieval 证据链。

### INCONCLUSIVE

样本量或 Episode 覆盖不足，不能强行判 GO。

## 5.3 Conditional Extension Evaluation

只有对应 extension 实际执行时才要求：

### VLM Auto-label

- reviewed Accuracy
- Macro-F1 / confusion matrix where applicable

### Dedup

- Reviewed Duplicate Precision on top candidates

### Long-tail

- Meaningful Rare Yield
- 与 random / frozen baseline 的对照
- top-ranked review category distribution

规则：

- calibration sample 与 final human audit sample 不复用；
- 不允许用 final reviewed set 继续调 prompt / threshold / fusion 后再报同一套结果。

---

# 6. MVP Core Results + Conditional Extensions

旧的“五项全部 Must-have 才可展示”取消。

## CORE-RESULT-1｜Versioned Segment Inputs

必须有：

- Frozen G1 segment provenance
- minimal keyframe indices
- clean RGB contract + runtime validation
- Action/State / Motion feature provenance

## CORE-RESULT-2｜Motion vs Vision Retrieval

必须有：

- Motion-only retrieval
- SigLIP2-only retrieval
- Cross-episode Top-K
- independent Human Precision@5
- query-level success / failure cases

Optional：

- frozen Late Fusion

## CORE-RESULT-3｜Runnable Retrieval Asset

必须有：

- FAISS Top-K retrieval
- reproducible query / neighbor manifest
- representative Top-K case panels
- README / result summary

达到 CORE-RESULT-1~3，即具备当前 P2 MVP 的核心求职展示价值。

## CONDITIONAL-EXTENSION-A｜Structured Auto-label

只有 G3 minimal taxonomy 与 RGB contract 通过后进入。

## CONDITIONAL-EXTENSION-B｜Dedup Candidate Mining

只有 Core Retrieval 有可解释相似性证据后进入。

## CONDITIONAL-EXTENSION-C｜Long-tail / Coverage

只有 representation/retrieval evidence 足够且有 baseline + human review 时进入。

## CONDITIONAL-EXTENSION-D｜Curation Manifest

作为已有结果的统一汇总资产，不作为新的独立算法系统。

---

# 7. Formal MVP Output Contract

Core 最低产物：

- segment_manifest
- keyframe_summary
- clean_rgb_provenance
- visual_embedding_metadata
- action_state_feature
- retrieval_neighbors
- retrieval_human_review
- retrieval_evaluation_summary
- README / representative cases

Conditional Extension 执行后可追加：

- structured_label
- duplicate_candidates
- rarity_coverage_ranking
- curation_manifest

### Curation Manifest schema 修正

若生成 curation_manifest，不得把“证据标签”和“处置动作”混在同一枚举。

至少分为：

~~~text
segment_id
semantic_label (optional)
nearest_neighbor_ids
visual_similarity
motion_similarity
rarity_score (optional)
coverage_bucket (optional)

candidate_tags[]
review_status
triage_action
review_decision
~~~

candidate_tags[] 可多选，例如：

- DUPLICATE_CANDIDATE
- RARE_CANDIDATE
- COVERAGE_SPARSE

review_status：

- UNREVIEWED
- REVIEWED

triage_action MVP 只允许：

- KEEP
- REVIEW

不得直接输出：

- DROP
- UPWEIGHT

一个 segment 可以同时具有多个 candidate tags；candidate evidence 不自动等于训练处置决策。

---

# 8. MVP Cut List｜明确砍项

以下内容全部移到 POST_MVP / FULL_DESIGN，不阻塞 Core Retrieval MVP Freeze：

1. G1 24-Episode Independent Human Evaluation
2. 3-VLM Formal Benchmark
3. DINOv2 / SigLIP2 / R3M 三路 Formal Encoder Benchmark
4. DINOv2 全量 benchmark（仅保留 conditional sanity）
5. R3M
6. CLIP
7. learned multimodal fusion
8. advanced vector DB / HNSW / distributed ANN
9. complex duplicate graph transitivity / auto-delete
10. multiple clustering / rarity algorithm comparison
11. full three-view Coverage system before Core Retrieval evidence
12. second robot dataset generalization
13. P1 Failure Query integration
14. ROS / real-robot / 3D point cloud 扩张
15. policy retraining
16. data mixing / sampling optimization
17. automatic data-value claim

以下模块不是删除，而是 Conditional：

- Single-VLM structured auto-label
- lightweight Dedup Candidate
- lightweight Long-tail / Coverage
- Curation Manifest

这些只有在 Core Retrieval Gate 后按证据进入。

---

# 9. Post-MVP / Conditional 保留能力

Core Retrieval 完成后，如需增强，优先级：

1. minimal G3 taxonomy freeze + Single-VLM structured auto-label
2. lightweight Dedup Candidate + human precision
3. lightweight rarity ranking + random/frozen baseline
4. Curation Manifest summary
5. DINOv2 small sanity comparison
6. free-text dataset search UI
7. richer score-level fusion
8. richer dedup grouping
9. second dataset / cross-dataset generalization
10. P1 Failure Query case study
11. P3 Data Mix / Exposure Optimization

---

# 10. MVP Claim Boundary

Core Retrieval MVP 完成后允许声称：

- built a segment-to-retrieval robot demonstration pipeline
- versioned clean RGB + robot-motion segment representation
- SigLIP2 visual embedding
- Action/State feature-based motion retrieval baseline
- FAISS vector retrieval
- cross-episode human-reviewed Precision@5
- analyzed complementary / failure cases between visual and motion retrieval

只有对应 Conditional Extension 实际完成并有人审证据后，才允许追加：

- VLM-based structured auto-labeling
- duplicate candidate mining
- long-tail / sparse coverage mining
- curation manifest

MVP 不允许声称：

- G1 held-out segmentation evaluation passed
- Formal VLM generalization established beyond reviewed population
- SigLIP2 globally superior to all encoders
- same VLM-predicted phase proves retrieval relevance
- duplicate candidates should be deleted
- rare data has higher training value
- coverage gaps should be automatically upweighted
- curation improves VLA policy performance

最后一项必须由 Project 3 / model retraining evidence 支持。

---

# 11. Execution Order

当前执行顺序固定为：

~~~text
P0A — Freeze + locally validate clean RGB input contract
    ↓
M2 — Minimal Keyframe + Robot Motion Summary
    ↓
Core Retrieval Protocol Freeze
    ↓
Retrieval Manifest Preparation
    ↓
Owner Manifest Freeze
    ↓
Runtime Preflight + exact SigLIP2 revision pin
    ↓
Motion-only + SigLIP2-only Retrieval
    ↓
Calibration blind Human Audit
    ↓
Final blind Human Audit
    ↓
Formal P@5 scoring
    ↓
GO / CONDITIONAL / STOP / INCONCLUSIVE
~~~

Core Retrieval Protocol 已冻结于：

~~~text
0-doc/10-design-review/
Project2_MVP_Core_Retrieval_Protocol_FROZEN_v1_20261008.md
~~~

如果 GO / CONDITIONAL 且证据支持：

~~~text
P0B — Freeze minimal G3 taxonomy
→ M3 Single-VLM branch
→ lightweight Dedup
→ lightweight Rarity / Coverage
→ Curation Manifest
~~~

如果 STOP：

~~~text
STOP feature expansion
→ preserve failure evidence
→ do not add VLM / Dedup / Coverage merely to enlarge the pipeline
~~~

DINOv2 不阻塞 Core，只有需要定位视觉 representation failure 时再作为 conditional sanity baseline。

任何额外工作必须先回答：

> 它是否直接增强 Core Retrieval 证据，或是已经满足条件的 Conditional Extension？

若答案为否，默认进入 POST_MVP。

---

# 12. Local Implementation Rule

所有本地开发 Prompt / Codex 执行在没有特殊说明时，必须先：

1. `git checkout main`
2. `git pull --ff-only origin main`
3. 确认本地 HEAD == 远端 `origin/main`
4. 再开始最小定向修改

禁止基于旧本地缓存直接实现。

---

# 13. Current Status After Retrieval-first Rebaseline

- FULL_PROJECT2_SSOT = PRESERVED
- MVP_SSOT = ACTIVE_RETRIEVAL_FIRST
- G1 = CLOSED_WITH_EVALUATION_DEFERRED
- MVP_RGB_SOURCE_AND_ALIGNMENT_CONTRACT = FROZEN_v1
- MVP_P0A_RGB_INPUT_CONTRACT = CLOSED_PASS
- RGB_RUNTIME_VALIDATION = PASS
- RGB_RUNTIME_VALIDATION_RESULT = Project2_MVP_RGB_Runtime_Validation_Result_20261008.md
- G3_SEMANTIC_RESPONSIBILITY = FROZEN
- G3_MVP_TAXONOMY = PENDING_MINIMAL_FREEZE
- MVP-M2 = CLOSED_PASS
- MVP_M2_RUNTIME_VALIDATION = PASS
- READY_FOR_CORE_RETRIEVAL = YES
- MVP_M2_RESULT = Project2_MVP_M2_Keyframe_and_Robot_Motion_Summary_Result_20261008.md
- MVP_M2_PRE_RETRIEVAL_HARDENING = CLOSED_PASS
- MVP-M4_M5_CORE_RETRIEVAL = PROTOCOL_FROZEN_v1
- CORE_RETRIEVAL_PROTOCOL = FROZEN_v1
- CORE_RETRIEVAL_PROTOCOL_DOC = Project2_MVP_Core_Retrieval_Protocol_FROZEN_v1_20261008.md
- CORE_RETRIEVAL_PROTOCOL_ADDENDUM = FROZEN_v1
- CORE_RETRIEVAL_PROTOCOL_ADDENDUM_DOC = Project2_MVP_Core_Retrieval_Protocol_Addendum_FROZEN_v1_20261009.md
- CORE_RETRIEVAL_MANIFEST = FROZEN_v1
- CORE_RETRIEVAL_MANIFEST_DOC = Project2_MVP_Core_Retrieval_Manifest_FROZEN_v1_20261009.md
- CORE_RETRIEVAL_MANIFEST_CSV = Project2_MVP_Core_Retrieval_Manifest_FROZEN_v1_20261009.csv
- CORE_RETRIEVAL_RUNTIME_PREFLIGHT = PASS
- CORE_RETRIEVAL_INFERENCE = READY_FOR_FORMAL_CORE_RETRIEVAL_EXECUTION
- CORE_RETRIEVAL_FORMAL_REPRESENTATION = PASS
- FORMAL_63_EPISODE_MATERIALIZATION = PASS
- CALIBRATION_RETRIEVAL = READY_FOR_HUMAN_AUDIT
- CALIBRATION_HUMAN_AUDIT_EVIDENCE = TEMPORAL_CONTEXT_READY
- TEMPORAL_EVIDENCE_ADDENDUM = FROZEN_v1
- TEMPORAL_EVIDENCE_ADDENDUM_DOC = Project2_MVP_Human_Audit_Temporal_Evidence_Addendum_FROZEN_v1_20261010.md
- CALIBRATION_HUMAN_AUDIT_EVIDENCE_RESULT = Project2_MVP_Calibration_Human_Audit_Temporal_Evidence_Result_20261010.md
- CALIBRATION_HUMAN_AUDIT_PACKAGE = outputs/mvp_core_retrieval_human_audit/calibration_blind_audit_temporal_v1_20261010
- CALIBRATION_AUDIT_ITEMS = 95
- CALIBRATION_SEGMENT_GIFS = 71/71 PASS
- CALIBRATION_AUDIT_ORDER_UNCHANGED = YES
- CALIBRATION_METHOD_SCORE_RANK_HIDDEN = YES
- CALIBRATION_RETRIEVAL_RERUN = NO
- HUMAN_RELEVANCE_CALIBRATION = CLOSED_PASS
- HUMAN_RELEVANCE_RUBRIC = FROZEN_v1
- HUMAN_RELEVANCE_RUBRIC_DOC = Project2_MVP_Human_Relevance_Rubric_Clarification_FROZEN_v1_20261012.md
- CALIBRATION_RUBRIC_STABILITY = PASS
- CALIBRATION_FIRST_PASS_LABELS = ARCHIVED_95_ITEMS
- CALIBRATION_FIRST_PASS_UNSURE = 31/95
- CALIBRATION_UNSURE_REAUDIT = COMPLETED_31_ITEMS
- CALIBRATION_UNSURE_REAUDIT_SOURCE = 01_calibration_human_audit_pairs_filled_20261011.csv
- CALIBRATION_UNSURE_REAUDIT_RESULT = 03_calibration_unsure_reaudit_filled_20261012.csv
- CALIBRATION_RECONCILED_LABELS = 04_calibration_human_audit_reconciled_20261012.csv
- CALIBRATION_RECONCILED_UNSURE = 0/95
- CALIBRATION_FIRST_PASS_BINARY_REPEAT_QC = 10/12 PASS
- CALIBRATION_RECONCILED_BINARY_REPEAT_CONSISTENCY = 11/12 SUPPORTIVE_ONLY
- CALIBRATION_REAUDIT_COMPARISON = 05_calibration_unsure_reaudit_comparison_20261012.md
- FINAL_RETRIEVAL = READY_FOR_EXECUTION
- FINAL_HUMAN_AUDIT_RUBRIC = LOCKED_TO_FROZEN_v1
- CORE_V1_LATE_FUSION = DISABLED
- MVP-M3_VLM = CONDITIONAL_NON_BLOCKING
- MVP-M6_DEDUP_LONGTAIL_COVERAGE = CONDITIONAL_AFTER_RETRIEVAL_GATE
- DINOV2 = CONDITIONAL_EXTENSION
- PROJECT3_VALUE_VALIDATION = NOT_IN_P2_MVP

NEXT = FINAL_RETRIEVAL

**The clarified Human relevance rubric is now FROZEN_v1. Run the already-frozen 18-query Final Retrieval using the existing Candidate Bank and representation contracts, then build the blind Final Human Audit package under the frozen rubric. Do not compute Formal P@5 or make a GO / CONDITIONAL / STOP decision until Final Human labels are frozen and Final repeat QC is checked.**

---

# 14. Change Control

本 MVP SSOT 的范围变化必须满足：

Implementation Evidence / Job Requirement Change
→ MVP Scope Change Proposal
→ Design Owner Review
→ update this MVP SSOT

不得通过 Implementation 层静默扩大 scope。
