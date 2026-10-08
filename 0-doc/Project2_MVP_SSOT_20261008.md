# Project 2 MVP SSOT｜Robot Demonstration Mining & VLA Data Curation MVP
## 2026-10-08｜ACTIVE MVP EXECUTION AUTHORITY

> Status: ACTIVE
> Repository: `Modori1998/embody_project2_data_value`
> Baseline main HEAD at rebaseline: `7efae2b710ef749b2e3aa793667eb43adad4d90c`
> This file is a NEW MVP SSOT. It does NOT replace or overwrite the full Project 2 Engineering SSOT.

---

# 0. 文档定位与权威关系

本文件定义 Project 2 的 **MVP Execution Scope（最小可交付执行范围）**，目标是把现有完整研究路线压缩为一个更贴合具身数据算法 / VLA 训练数据岗位的可运行、可评估、可面试展示的项目。

原详细设计继续保留，尤其包括：

- `0-doc/Project_2_Engineering_Design_Master_v1_20260914.md`
- `0-doc/Project2_Development_Roadmap_and_Design_Gate_Plan_v1_20260914.md`
- `0-doc/02_robot_demonstration_mining_autolabel_design.md`

权威规则：

1. 已冻结的底层语义、Source Contract、G1 Segment 定义、G3 taxonomy、证据边界，继续以 Full Engineering SSOT 为准。
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

**Robot Demonstration Mining & VLA Data Curation MVP（机器人示范数据挖掘与 VLA 训练数据策划 MVP）**

输入：RoboMimic Can/MH robot demonstrations。

输出：Segment-level 多视角 Dataset Map（片段级多视角数据地图）和 Curation Manifest（数据策划清单）。

主链路：

RoboMimic Episode
→ existing G1 Segment
→ minimal keyframes + robot summary
→ VLM structured auto-label
→ visual embedding + action/state feature
→ FAISS Top-K retrieval
→ duplicate candidate
→ long-tail / sparse coverage candidate
→ small human audit
→ curation manifest + README + representative cases

本项目回答：

1. 数据里有哪些行为 / 交互语义？
2. 同一种行为内部有哪些视觉 / 操作模式？
3. 哪些样本彼此高度相似甚至近重复？
4. 哪些样本属于稀疏 / 长尾 / Corner Case 候选？
5. 哪些语义或实例区域覆盖薄弱？

本项目不直接回答：

- 哪些样本一定更有训练价值；
- 某个 rare sample 加权后一定提升 policy；
- 某个 coverage gap 补齐后一定提升成功率。

这些属于 Project 3 / 后续 Data→Model 验证。

---

# 3. MVP Multi-view Dataset Map

P2 MVP 不寻找一个统一的超级 Embedding，而保留三条互补证据。

| View | 中文解释 | Formal Source | 主要作用 |
|---|---|---|---|
| Semantic View | 语义视角 | G3 VLM structured labels | 行为阶段、物体关系、夹爪状态、局部成功证据 |
| Visual Instance View | 视觉实例视角 | SigLIP2 image embedding | 细粒度视觉相似、近重复、视觉稀疏性 |
| Robot Motion View | 机器人运动视角 | EEF / gripper / action-state feature | 运动模式和操作轨迹差异 |

原则：

- Semantic label 不直接塞入 visual embedding。
- G3-derived text embedding 不进入 Formal MVP。
- Visual / Robot evidence 分开保存。
- 如后续需要融合，只允许在 score/rank 层做透明 late fusion。

---

# 4. MVP 必做模块

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

---

## MVP-M2｜Minimal Keyframe + Robot Summary

Keyframe policy 最小化为：

- START
- MIDDLE
- END
- GRIPPER_EVENT（存在时加入）

首版不做复杂 keyframe ablation。

Robot Summary 最小字段：

- duration
- EEF net displacement
- EEF path length
- EEF main direction / coarse direction change
- gripper start state
- gripper end state
- gripper transition
- optional action magnitude summary

Done：

- Segment → Keyframes 可追溯
- Segment → Summary 可复现
- Image / Action / State 时间对应正确

---

## MVP-M3｜Single-VLM Structured Auto-Label

不再做多 VLM Formal Benchmark。

Formal MVP 只选择一个可稳定运行的 VLM，使用已冻结 G3 taxonomy。

输出至少包含：

- motion_phase
- object_relation[]
- gripper_semantic_state
- local_success_evidence
- evidence_quality
- label provenance

执行：

- small calibration batch
- prompt / parser / schema 修正
- prompt freeze
- batch auto-label
- small independent human review

禁止：

- 用第二个 VLM 静默 fallback
- semantic cherry-picking
- parser 把非法语义自动改成合法语义

---

## MVP-M4｜Visual Representation + Small Baseline

Formal Primary Visual Encoder：

- **SigLIP2 Image Encoder**
- Formal path = IMAGE_ONLY
- 不输入 G3-derived text

原因：

- 覆盖 multimodal representation / visual embedding / vector retrieval 能力；
- 保留未来 user free-text → Segment retrieval 的扩展能力；
- 避免把 VLM 标签重新编码进视觉表征造成循环评价。

Small Sanity Baseline：

- **DINOv2**
- 只在小样本 Query 上比较 Fine-grained Retrieval，不要求全量双跑。

明确移出 MVP Formal Benchmark：

- CLIP
- R3M

R3M 保留在 Full Design / Post-MVP。

Segment Visual Embedding 首版：

- same selected keyframes
- same deterministic preprocessing
- one frame embedding per keyframe
- per-frame L2 normalize
- mean pooling
- segment-level L2 normalize

同时保留 frame-level embedding 和 provenance。

---

## MVP-M5｜FAISS Top-K Retrieval

正式加入 FAISS，作为求职可识别的向量检索工程能力。

默认：

- L2-normalized embedding
- cosine-equivalent exact search
- FAISS `IndexFlatIP`

支持：

1. Image/Segment → Top-K Segment retrieval
2. within-phase retrieval
3. global retrieval

Optional Demo：

- user free-text → SigLIP2 Text Encoder → Top-K Segment

注意：

- free-text 来源必须是用户独立输入或预先冻结的 canonical query；
- 不用 G3 预测标签派生 text 作为 Formal Retrieval GT。

---

## MVP-M6｜Dedup + Long-tail + Coverage

### Dedup Candidate

首版只输出 candidate，不做自动删除和复杂 graph grouping。

证据：

- semantic compatible / same phase context
- high visual similarity
- optional robot motion consistency

人工 rubric：

- DUPLICATE
- NEAR_DUPLICATE
- NOT_DUPLICATE

### Long-tail / Sparse Candidate

首版只使用简单可解释的 kNN neighborhood density / mean neighbor distance。

同时保留：

- global rarity
- within-phase rarity
- semantic label frequency

人工 review category：

- meaningful variation
- rare behavior / interaction
- recovery / hard case
- bad data
- label error
- representation artifact

### Coverage

MVP Coverage 不是一个单一分数，至少输出：

- Semantic Coverage
- Visual Instance Coverage
- Robot Motion Coverage

禁止：

- rare = valuable
- duplicate candidate = delete
- coverage gap = automatic upweight

---

# 5. MVP Evaluation

MVP 不做论文级 Formal Evaluation，但必须保留一个小型独立 Human Audit（人工审计）。

正式评价轴：

## 5.1 Auto-label

- reviewed Accuracy
- Macro-F1 / confusion matrix where applicable

## 5.2 Retrieval

- Precision@5
- nDCG@5（有多级 relevance 时）
- representative success / failure cases

必须同时看：

- Semantic Retrieval（行为意义相似）
- Within-phase Fine-grained Retrieval（同类内部细粒度实例相似）

## 5.3 Dedup

- Reviewed Duplicate Precision on top candidates

## 5.4 Long-tail

- Meaningful Rare Yield
- top-ranked review category distribution

所有 sample count / K / threshold：

- `DATA_CALIBRATION_PENDING`

规则：

- calibration sample 与 final human audit sample 不复用；
- 不允许用 final reviewed set 继续调 prompt / threshold 后再报同一套结果。

---

# 6. MVP Five Must-have Results

MVP 只有以下 5 个结果全部出现，才算可用于求职展示。

## RESULT-1｜Structured Auto-label Result

必须有：

- segment-level structured labels
- human-reviewed subset
- accuracy / error cases

## RESULT-2｜Versioned Segment Representation

必须有：

- SigLIP2 visual embedding
- Action/State feature
- encoder / preprocessing / aggregation / normalization provenance

## RESULT-3｜Runnable Vector Retrieval

必须有：

- FAISS Top-K retrieval
- Precision@5
- at least several visual Top-K case panels

Optional bonus：free-text retrieval demo。

## RESULT-4｜Duplicate + Rare Candidate Mining

必须有：

- duplicate candidate list
- reviewed duplicate precision
- rarity ranking
- meaningful rare case examples

## RESULT-5｜Dataset Coverage + Curation Manifest

必须有：

- semantic distribution
- visual / rarity distribution
- motion distribution summary
- curation manifest
- README/result summary

---

# 7. Formal MVP Output Contract

最低产物：

- `segment_manifest`
- `keyframe_summary`
- `structured_label`
- `visual_embedding_metadata`
- `action_state_feature`
- `retrieval_neighbors`
- `duplicate_candidates`
- `rarity_coverage_ranking`
- `human_review`
- `evaluation_summary`
- `curation_manifest`
- `README / representative cases`

Curation Manifest 至少包含：

- segment_id
- semantic_label
- nearest_neighbor_ids
- visual_similarity
- duplicate_candidate
- rarity_score
- coverage_bucket
- review_status
- recommended_action

`recommended_action` 仅允许：

- KEEP
- REVIEW
- DUPLICATE_CANDIDATE
- RARE_CANDIDATE

不得直接输出 DROP / UPWEIGHT 作为训练决策。

---

# 8. MVP Cut List｜明确砍项

以下内容全部移到 `POST_MVP / FULL_DESIGN`，不阻塞 MVP Freeze：

1. G1 24-Episode Independent Human Evaluation
2. 3-VLM Formal Benchmark
3. DINOv2 / SigLIP2 / R3M 三路 Formal Encoder Benchmark
4. R3M
5. CLIP
6. learned multimodal fusion
7. advanced vector DB / HNSW / distributed ANN
8. complex duplicate graph transitivity / auto-delete
9. multiple clustering / rarity algorithm comparison
10. second robot dataset generalization
11. P1 Failure Query integration
12. ROS / real-robot / 3D point cloud expansion only for resume keyword stuffing
13. policy retraining
14. data mixing / sampling optimization
15. automatic data-value claim

这些砍项不表示无价值，只表示对当前求职 MVP 不是最短路径。

---

# 9. Post-MVP 保留能力

MVP 完成后，如需继续增强，可按优先级恢复：

1. DINOv2 vs SigLIP2 expanded benchmark
2. R3M robot-specific representation check
3. free-text dataset search UI
4. multimodal score-level fusion
5. richer dedup grouping
6. second dataset / cross-dataset generalization
7. P1 Failure Query case study
8. P3 Data Mix / Exposure Optimization

---

# 10. MVP Claim Boundary

MVP 允许声称：

- built robot demonstration segmentation-to-curation pipeline
- VLM-based structured auto-labeling
- segment-level multimodal representation
- SigLIP2 visual embedding
- FAISS vector retrieval
- duplicate candidate mining
- long-tail / sparse coverage mining
- human-reviewed retrieval / dedup / rare-case evaluation

MVP 不允许声称：

- G1 held-out segmentation evaluation passed
- Formal VLM generalization established beyond reviewed population
- SigLIP2 globally superior to all encoders
- duplicate candidates should be deleted
- rare data has higher training value
- coverage gaps should be automatically upweighted
- curation improves VLA policy performance

最后一项必须由 Project 3 / model retraining evidence 支持。

---

# 11. Execution Order

当前执行顺序固定为：

1. `MVP-M2` Minimal Keyframe + Robot Summary
2. `MVP-M3` Single-VLM Structured Auto-Label
3. `MVP-M4` SigLIP2 Representation + DINOv2 Small Sanity Baseline
4. `MVP-M5` FAISS Top-K Retrieval
5. `MVP-M6` Dedup + Long-tail + Coverage
6. Small Human Audit
7. Curation Manifest + README + representative cases
8. MVP Freeze

任何额外工作必须先回答：

> 它是否直接提高上述 5 个 Must-have Results 的完成度或求职证据强度？

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

# 13. Current Status After MVP Rebaseline

- FULL_PROJECT2_SSOT = PRESERVED
- MVP_SSOT = ACTIVE
- G1 = CLOSED_WITH_EVALUATION_DEFERRED
- MVP-M2 = NEXT
- MVP-M3 = PENDING_M2
- MVP-M4 = PENDING_M3_INPUT_CONTRACT
- MVP-M5 = PENDING_M4
- MVP-M6 = PENDING_M5
- PROJECT3_VALUE_VALIDATION = NOT_IN_P2_MVP

NEXT ACTION:

**Implement MVP-M2 Minimal Keyframe + Robot Summary on current main, then immediately connect one VLM small batch instead of expanding G2 research scope.**

---

# 14. Change Control

本 MVP SSOT 的范围变化必须满足：

Implementation Evidence / Job Requirement Change
→ MVP Scope Change Proposal
→ Design Owner Review
→ update this MVP SSOT

不得通过 Implementation 层静默扩大 scope。
