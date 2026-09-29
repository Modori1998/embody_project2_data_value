# Project 2 Development Roadmap and Design Gate Plan v1
## 2026-09-14 Rebaseline｜ACTIVE EXECUTION AUTHORITY

## 文档变更历史

| 日期 | 版本 / 状态 | 变更内容 | 变更人 / 来源 |
|---|---|---|---|
| 2026-09-14 | **v1 ACTIVE ROADMAP** | 基于 P2 Rebaseline 与 G0–G8 Engineering Design，建立阶段开发顺序、USER-GATE、Codex 权限、Done Criteria 与 Change Control。日期不替代 Portfolio hard deadline；阶段顺序是当前执行 authority。 | 用户 Design Owner + ChatGPT |
| 2026-09-14 | **G1/G3 SEMANTIC RESPONSIBILITY FREEZE** | 同步 Engineering Master：G1 只生成 unlabeled behavior segments；G3 基于 RGB/Keyframes + robot/action summary 恢复 object relation 并赋物理语义；simulator object GT 仅作 Oracle/Evaluation Reference。G1 继续 OPEN，下一讨论聚焦 Boundary Rule。 | 用户 Design Owner + ChatGPT |
| 2026-09-14 | **G1-B BOUNDARY SEMANTICS FREEZE** | 冻结 Boundary 证据层级：gripper transition 为 Hard Candidate；persistent moving↔stationary 与 large+persistent direction change 为 Motion Candidate；EEF rotation / recorded action 仅作 Supporting Evidence。Rotation 定义为 EEF orientation change，不是特定 joint；当前 Can task 不允许 Rotation-alone cut。numeric threshold 继续 DATA_CALIBRATION_PENDING。 | 用户 Design Owner + ChatGPT |
| 2026-09-14 | **G1-C LENGTH GUARD & MERGE FREEZE** | 冻结 Event-aware Merge：Boundary Consolidation 与 Segment Merge 分离；confirmed gripper transition 受 Hard Boundary Protection；min length 只触发 review/merge；short pause 仅在前后 gripper 与 motion compatible 时桥接；max length 首版只做 audit，不做 fixed-window forced split。 | 用户 Design Owner + ChatGPT |
| 2026-09-14 | **G1-D HUMAN CALIBRATION LOOP FREEZE** | 冻结 Boundary-level Human Review 为主标注粒度；Episode-level 仅作自动聚合。审查必须提供 video path、完整 Formal Signal Set plot、Candidate/Suppressed/Final Boundary 与 reason。人工标签进入 threshold/strategy calibration loop；Calibration Set 与 Independent Evaluation Set 严格隔离。 | 用户 Design Owner + ChatGPT |
| 2026-09-14 | **G1 IMPLEMENTATION REBASELINE** | G1-A～D 架构级设计已冻结。G1 状态从“等待设计讨论”切换为 `DESIGN_FROZEN / IMPLEMENTATION_READY / OPEN_FOR_CALIBRATION`。Roadmap 将 G1 实施拆为 4 个带验收点的 phase；G2 Design 可并行讨论，但 G2 Formal implementation 仍等待 G1 Final Config / Evaluation 关闭。 | 用户 Design Owner + ChatGPT |
| 2026-09-23 | **G1-P3 CALIBRATION PROTOCOL v1.2 FREEZE** | 基于 Stage A0、P12/C12 operationalization、20-event Design Diagnostic 与 Owner Adjudication，冻结当前 Calibration Search：保持 baseline Direction Candidate Generation，不再机械搜索 direction threshold × persistence；Stage A1 搜索 P12-only，Stage A2 仅把 C12 作为 conditional strategy candidate，随后进入既有 Stage B consolidation / Stage C regression。20-event Diagnostic Set 永久禁止参与 threshold selection / Calibration GT / Evaluation。 | 用户 Design Owner + ChatGPT |
| 2026-09-24 | **G1-P3 STAGE A OWNER SELECTION / STAGE B GATE OPEN** | Design Owner 选择 `A1-007-C002` 作为进入后续校准阶段的 Stage A Candidate Acceptance 配置：`tau_P12=0.04758563666765155`、`tau_C12=0.690169167642685`。Residual FP 复核维持原 Human GT：`demo_242@60` 为 Acceptance residual，不作为 Stage B 优化目标；`demo_255@135` 与 `GRIPPER_TRANSITION@125` 属同一 physical event，确认存在 under-consolidation，故打开 Stage B，只允许固定 A1-007-C002 后比较 `boundary_consolidation_window ∈ {8,10,12}`。Final Config 仍未冻结，Evaluation 仍禁止触碰。 | 用户 Design Owner + ChatGPT |
| 2026-09-26 | **G1-P3 STAGE B OWNER DECISION / STAGE C GATE OPEN** | Stage B 单因素比较已完成：window=10/12 均能修复 `demo_255@125/@135` 的 under-consolidation，但分别引入 4/6 个 FN、Fresh valid-Direction recall 退化及 `NEW_UNANCHORED_FP=1`，违反 Frozen HARD guardrails；`STAGE_B_SAFE_CANDIDATES=[]`。Design Owner 因此拒绝 10/12，不把 window=8 记为 Stage B 优化胜者，而是 `NO_SAFE_INCREMENTAL_CHANGE` 后保留 parent window=8 进入 Stage C。`demo_255@135` 保留为已知 residual under-consolidation；Stage C 只做 regression，不再新增搜索轴。 | 用户 Design Owner + ChatGPT |
| 2026-09-27 | **G1-P3 FINAL CALIBRATION CONFIG FREEZE / P2-S1D GATE OPEN** | Stage C Regression 通过：固定 `A1-007-C002`、`tau_P12=0.04758563666765155`、`tau_C12=0.690169167642685`、retained parent `boundary_consolidation_window=8`，复现 `TP/FP/FN=56/2/0`、Recall=1.0、全部 HARD guardrail PASS、`NEW_UNANCHORED_FP=0`、deterministic replay PASS、protected artifact identity PASS。Design Owner 明确确认冻结；两个已知 residual 保留，不再使用 Calibration Set 调参。G1 Final Config 进入 `FROZEN_v1`，下一 Gate 为 P2-S1D Independent Evaluation。 | 用户 Design Owner + ChatGPT |
| 2026-09-27 | **P2-S1D EVALUATION MANIFEST GATE CLARIFICATION** | 依据 Frozen Calibration Protocol v1 §8.4 / §21，Evaluation Episode 数量与具体 ID 尚未被冻结；因此正式 Independent Evaluation 运行前必须先完成 Evaluation Manifest 设计与 Owner Freeze。此 Gate 不改变已冻结 Final Config，仅防止 Implementation 层自行选择 Evaluation episode 或提前触碰 Evaluation GT。 | ChatGPT（按 Frozen Protocol 落地） |
| 2026-09-29 | **G1-P4 INDEPENDENT EVALUATION MANIFEST FROZEN v1** | Design Owner 选择 deterministic Medium proposal，正式冻结 24 条 held-out Evaluation episodes。Preparation audit：300 total、32 historical excluded、268 eligible、0 unreadable；Disjointness PASS、Leakage PASS；选择未使用 human label、Evaluation GT、Frozen Config score、FP/FN 或结果型 cherry-pick。`FORMAL_EVALUATION_RUN_ALLOWED=YES`，下一 Gate 为正式 Evaluation Audit Run + Human Review。 | 用户 Design Owner + ChatGPT |

---

# 0. 文档定位

本文负责 **Roadmap / Execution Authority（路线图与阶段执行权威）**，回答：

1. 下一步先做什么；
2. 哪个 Design Gate 必须先讨论；
3. 用户必须拍板什么；
4. Codex 可以直接实现什么；
5. 什么证据满足后才能进入下一阶段。

本文不允许新增核心 Design。核心方案以：

`Project_2_Engineering_Design_Master_v1_20260914.md`

为准。

当前状态：

```text
PROJECT_2 = ACTIVE_BOOTSTRAP
G0 = CLOSED
G1_DESIGN = FROZEN
G1_IMPLEMENTATION = READY
G1_GATE = OPEN_FOR_INDEPENDENT_EVALUATION
G1_P3_CALIBRATION_PROTOCOL = FROZEN_v1.2
G1_P3_STAGE_A = CLOSED_OWNER_SELECTED_A1_007_C002
G1_P3_STAGE_B = CLOSED_NO_SAFE_INCREMENTAL_CHANGE
G1_P3_STAGE_B_EFFECTIVE_WINDOW = RETAIN_PARENT_8
G1_P3_STAGE_C = CLOSED_PASS
G1_CALIBRATION_CONFIG = FROZEN_v1
G1_FINAL_CONFIG = FROZEN_FOR_INDEPENDENT_EVALUATION
G1_P4_GATE = OPEN
G1_P4_EVALUATION_MANIFEST = FROZEN_v1
G1_P4_EVALUATION_EPISODE_COUNT = 24
G1_P4_FORMAL_EVALUATION_RUN_ALLOWED = YES
G1_P3_NEXT_GATE = P2_S1D_FORMAL_EVALUATION_AUDIT_RUN_AND_HUMAN_REVIEW
G2_DESIGN = MAY_PROCEED_IN_PARALLEL
G2_FORMAL_IMPLEMENTATION = BLOCKED_BY_G1_CLOSE
P1_FAILURE_QUERY = OPTIONAL
P1_PROJECT = CONTINUES_IN_PARALLEL
```

---

# 1. 总路线

```text
Phase A｜Semantic Unit Foundation
G0 Source Foundation [CLOSED]
→ G1 Design A–D [FROZEN]
→ G1-P1 Signal Contract & Audit Harness
→ G1-P2 Boundary Engine & Postprocess
→ G1-P3 Boundary-level Human Calibration Loop
→ G1-P4 Final Config Freeze & Independent Evaluation
→ G1 Gate Close

Phase B｜Segment Semantics
G2 Keyframe / Summary Design
→ implementation
→ G3 Label Taxonomy Design
→ VLM small-batch labeling
→ 20–30 Segment review

Phase C｜Representation & Retrieval
G4 Representation Design
→ Embedding implementation
→ representation sanity cases
→ G5 Retrieval Design
→ Top-K retrieval + human audit

Phase D｜Dataset Mining
G6 Dedup Design
→ duplicate candidates / groups
G7 Long-tail / Coverage Design
→ rarity / coverage ranking

Phase E｜Formal Evaluation & Freeze
G8 Evaluation Protocol Freeze
→ Calibration set closed
→ Evaluation set frozen
→ formal metrics / case study
→ Unified Mining Manifest
→ README / Result Table

Phase F｜OPTIONAL
P1 Failure Query
→ retrieval / coverage case study
```

强依赖：

```text
G1 Design Freeze → G2 Design discussion allowed
G1 Gate Close → G2 Formal implementation / G3 Formal batch
G2 → G4
G4 → G5
G5 → G6/G7
G6+G7 → G8
G8 → Formal Result / Freeze
```

---

# 2. Roadmap Task IDs

```text
P2-F0  Source Foundation Alignment
P2-S1  G1 Segmentation Implementation + Calibration
  P2-S1A  Signal Contract + Audit Harness
  P2-S1B  Boundary Engine + Postprocess
  P2-S1C  Human Calibration + Threshold/Strategy Search
  P2-S1D  Final Config Freeze + Independent Evaluation
P2-S2  Keyframe / Segment Summary
P2-L1  Label Taxonomy + VLM Small Batch
P2-R1  Representation Design + Embedding
P2-R2  Retrieval Design + Top-K Audit
P2-D1  Dedup Candidate / Group
P2-C1  Long-tail / Coverage Mining
P2-E1  Evaluation Protocol + Formal Human Eval
P2-M1  Unified Mining Manifest + Result Package
P2-O1  Optional P1 Failure Query Case
P2-FR  Project 2 Freeze
```

---

# 3. Phase A｜Semantic Unit Foundation

## P2-F0｜Source Foundation Alignment

### Roadmap Role

确认 P2 真实代码复用 P1 Source Contract，不重做 schema。

### USER-VERIFY

用户只需确认：

- Can/MH 是当前 Primary Dataset；
- 实际 reader 没有改变 P1 temporal / action / state / image semantics；
- source_episode_id 可追溯。

### CODEX

- 最小 reader smoke；
- episode list / shape / dtype / key audit；
- provenance 输出；
- 不新增 competing adapter。

### Done Criteria

```text
G0 = CLOSED
P2_READER_SMOKE = PASS
PROVENANCE = TRACEABLE
```

---

## P2-S1｜G1 Segmentation Implementation + Calibration

### Roadmap Role

G1 的架构级设计已完成冻结。当前任务不是继续拍脑袋定义 segmentation 规则，而是把冻结设计实现为可审计、可人工标注、可参数寻优、可独立评估的 **Calibration Harness（校准框架）**，最终冻结 G1 Formal Config。

当前冻结契约：

```text
G1 output = unlabeled behavior segment
G1 does NOT output approach/grasp/lift/place/retract semantics
Formal G1 input = robot kinematics + gripper + recorded action
Simulator object GT = privileged evaluator/audit only

Boundary evidence hierarchy:
- Hard: persistent gripper transition
- Motion: persistent moving↔stationary
- Motion: large+persistent main-direction change
- Supporting only: EEF rotation regime change
- Supporting only: recorded action / command change
- Rotation alone = NO CUT

Length / merge:
- Boundary Consolidation != Segment Merge
- confirmed gripper boundary is protected
- min_length only marks SHORT_SEGMENT_CANDIDATE
- short pause may bridge only when neighboring gripper/motion are compatible
- short segment merges toward the more compatible neighbor
- max_length first version = AUDIT ONLY, no blind forced split

Human calibration:
- primary annotation granularity = Boundary-level
- Episode-level = automatic aggregate / notes only
- labels = VALID / REDUNDANT / MISALIGNED / MISSED_BOUNDARY
- MISALIGNED keeps corrected_frame
- review keeps reason_code / error taxonomy
- Calibration Set != Evaluation Set
```

所有具体 numeric threshold 继续标记：

```text
DATA_CALIBRATION_PENDING
```

---

### G1 开发方式｜必须分 Phase，不一次性黑盒开发

G1 在一个 umbrella task 下拆成四个 implementation phase。Phase 之间不是重新做 Design Gate，而是 **implementation acceptance checkpoint（实施验收点）**。允许同一 branch 连续开发，但每个 Phase 必须先产出可检查证据，再进入下一 Phase。

原因：

1. Signal derivation、时间对齐或单位一旦错误，会污染后续全部 boundary/search 逻辑；
2. G1-D 要求人实际看 video + full signal plot，review schema 必须先验证可用；
3. calibration search 的目标来自人工 Boundary GT，无法在人工标注之前证明寻优正确；
4. Evaluation Set 只能在 final config freeze 后运行，天然不能与 calibration 一次性完成。

---

### P2-S1A｜G1-P1 Signal Contract + Audit Harness

#### CODEX

实现并验证所有 Formal Base Signal 与审计骨架：

```text
EEF translation displacement / speed
moving / stationary state
main-direction change evidence
gripper qpos / derived gripper state / transition
EEF quaternion-derived angular change
action / command change evidence
```

同时建立：

```text
episode provenance
frame/timestep alignment
video path / rendered video reference
full-signal shared-x-axis plot
privileged object audit namespace (strictly separated)
config / version / logging / tests
```

#### 强制审计图

每个 Episode 的正式审计图必须在同一时间轴展示当前 Formal segmentation 使用的 **全部 Base Signal Set**。后续 P2-S1B 加入边界后，图上必须继续叠加 Candidate / Suppressed / Final Boundary 与 reason。

Simulator object GT 若展示，只能作为第二层 `PRIVILEGED AUDIT ONLY / NOT USED BY SEGMENTER` overlay，不得混入 Formal signal computation。

#### STOP / USER-VERIFY

进入 P2-S1B 前至少确认：

```text
SIGNAL_TIME_ALIGNMENT = PASS
SIGNAL_SEMANTICS = PASS
FULL_SIGNAL_PLOT_READABLE = YES
FORMAL_PRIVILEGED_SEPARATION = PASS
```

不要求此 Phase 得到最终 segmentation。

---

### P2-S1B｜G1-P2 Boundary Engine + Postprocess

#### CODEX

基于冻结的 G1-B/C 实现：

```text
Boundary Candidate Generator
→ persistence / debounce
→ Hard vs Motion vs Supporting evidence
→ Boundary Consolidation
→ Pause Bridging
→ Short Segment Handling
→ Neighbor-Compatible Merge
→ Max Length Audit Flag
→ Final Unlabeled Segment Manifest
```

每个 boundary 必须保留 trace：

```text
candidate_frame
candidate_reason
candidate_evidence
candidate_status = retained / suppressed / consolidated
final_boundary_frame
final_boundary_reason
config_version
segmentation_version
```

产出至少包括：

```text
segment_manifest.csv/parquet
boundary_candidate_manifest.csv/parquet
audit plots with Candidate/Suppressed/Final Boundary
video reference
representative episode audit package
```

#### STOP / USER-VERIFY

进入 P2-S1C 前，先人工看小样本，确认：

```text
BOUNDARY_REASON_TRACEABLE = YES
NO_SCHEMA_AMBIGUITY = YES
NO_MASS_1_2_FRAME_FRAGMENTATION = preliminarily YES
HARD_GRIPPER_BOUNDARY_VISIBLE = YES
AUDIT_PLOT_SUPPORTS_MANUAL_REVIEW = YES
```

若发现的是实现 bug / signal alignment bug，直接修复；若发现冻结设计本身结构性错误，走 Design Change Request，不允许 Codex 静默改规则。

---

### P2-S1C｜G1-P3 Boundary-level Human Calibration Loop

#### Calibration Review Package

首版从 Can/MH 选 10–20 个 `CALIBRATION_SET` Episodes，具体 IDs 冻结在 Manifest。每个 Episode 必须提供：

```text
video_path / rendered_video_path
full Formal Signal Set plot
Candidate Boundary
Suppressed / Consolidated Boundary
Final Boundary
boundary reason / evidence
segment manifest
human review template
```

#### Human Annotation｜主粒度 = Boundary

人工结构化标签：

```text
VALID
REDUNDANT
MISALIGNED + corrected_frame
MISSED_BOUNDARY + human_frame
reason_code
optional_note
```

Episode-level 不要求再手工维护 `OVER_SEGMENTED / UNDER_SEGMENTED / ACCEPTABLE` 主标签；它由 boundary review 自动汇总，并允许附加 `episode_note / blocking_issue`。

#### Evaluator

至少计算：

```text
Boundary Precision
Boundary Recall
Boundary F1
Boundary Localization Error
Hard Interaction Boundary Recall
1–2 frame fragmentation ratio
short segment ratio
segments per episode (diagnostic only)
error reason distribution
```

Boundary matching 使用 `Tolerance Window（容忍时间窗）`；最终 frame tolerance 仍为 `DATA_CALIBRATION_PENDING`。

#### Calibration Search — v1.2 Active Override

当前 G1-P3 Calibration Search 以：

`0-doc/10-design-review/Project2_G1_P3_Calibration_Protocol_FROZEN_v1_2_PATCH_20260923.md`

为有效协议。它覆盖本 Roadmap 早期的通用 numeric-search 列表；未被 v1.2 明确覆盖的 matching、GT、guardrail、Stage B/C、Evaluation 隔离继续沿用 v1.0/v1.1。

当前执行顺序冻结为：

```text
Baseline Direction Candidate Generation
(direction evidence + persistence; 当前 baseline 参数固定，不作为本轮主搜索轴)
        ↓
Stage A1 — P12-only Candidate Acceptance
        ↓
Stage A2 — P12 + Conditional C12 Tail Guard
             C12 只有在相对 P12-only 有增量收益且 guardrail 全通过时才可晋级
        ↓
Design Owner Stage A Selection
A1-007-C002
tau_P12 = 0.04758563666765155
tau_C12 = 0.690169167642685
        ↓
Stage B — Limited Consolidation {8,10,12}
             EXECUTED；10/12 均违反 HARD guardrails
             OWNER DECISION = NO_SAFE_INCREMENTAL_CHANGE
             RETAIN parent window=8；不把 residual FP 当作扩大全局 window 的理由
        ↓
Stage C — Regression / Guardrail
             CLOSED_PASS；不新增搜索轴
        ↓
Design Owner Config Freeze
             CALIBRATION_CONFIG_FROZEN = YES
             G1_FINAL_CONFIG = FROZEN_FOR_INDEPENDENT_EVALUATION
        ↓
P2-S1D Independent Evaluation
```

其中：

- **P12 — Sustained Post-motion Context｜持续后段运动上下文**：进入正式 Calibration search component；
- **C12 — Trajectory Coherence｜轨迹一致性**：仅为 `CONDITIONAL_STRATEGY_CANDIDATE`，不得因 Owner-adjudicated diagnostic result 直接升级成 unconditional hard gate；
- 旧 `direction_change_threshold × direction_persistence_frames` 路线已由 Stage A0 判定为缺乏可解释分离力，本轮保持 baseline，不再机械二维扫参；
- 20-event `DESIGN_DIAGNOSTIC_SET` 只提供机制证据，`MUST_NOT_BE_USED_FOR_THRESHOLD_SELECTION = YES`；
- numeric threshold 只能使用既有 12-Episode Calibration GT 选择；
- Evaluation Set 继续完全隔离，Config Freeze 前不得触碰。

具体 operational definition、bounded lookahead、edge fallback、threshold candidate construction 与 C12 promotion gate 以 v1.2 Patch 为准。

#### Error Attribution → Strategy Feedback

人工 reason 必须能够聚合到具体改进方向，例如：

```text
REDUNDANT_SHORT_PAUSE
→ pause/persistence/bridging

REDUNDANT_DIRECTION_JITTER
→ direction threshold/persistence

MISSED_DIRECTION_CHANGE
→ direction threshold/persistence

MISALIGNED_*
→ smoothing / event localization / representative frame

multiple nearby candidates for one event
→ consolidation window
```

Calibration 的目标不是只把 F1 做高，而是同时满足 Hard Boundary Recall、fragmentation 等 guardrail。

#### STOP / USER-VERIFY

由 Design Owner 选择最终候选 config / strategy。选定后：

```text
CALIBRATION_CONFIG_FROZEN = YES
```

冻结后不得再用 Evaluation Set 调参。

---

### P2-S1D｜G1-P4 Final Config Freeze + Independent Evaluation

#### CODEX

使用完全冻结的 config 在独立 `EVALUATION_SET` 上只运行一次正式 G1 pipeline：

```text
Frozen Config
→ Independent Episodes
→ Segmentation
→ Audit Package
→ Boundary-level Evaluation
→ Result / Failure Cases
```

Evaluation Set 禁止继续调整：

```text
threshold
merge rule
strategy
tolerance taxonomy
review taxonomy
```

若 Evaluation 暴露结构性失败，只能记录为 Design Change Request；不能在原 Evaluation Set 上边看边调。

### G1 Done Criteria

```text
SEGMENTATION_DESIGN_FROZEN = YES
P2-S1A_SIGNAL_AUDIT = PASS
P2-S1B_BOUNDARY_ENGINE = PASS
BOUNDARY_LEVEL_HUMAN_CALIBRATION = COMPLETE
CALIBRATION_CONFIG_FROZEN = YES
INDEPENDENT_EVALUATION_RUN = COMPLETE
BOUNDARY_REASON_TRACEABLE = YES
NO_MASS_1_2_FRAME_FRAGMENTATION = YES
HARD_INTERACTION_BOUNDARY_RECALL = ACCEPTABLE
MAJOR_BEHAVIOR_PHASES_ROUGHLY_SEPARABLE = YES
G1 = CLOSED
```

### 与 G2 的并行边界

```text
G2 Design discussion / Keyframe policy exploration
= MAY RUN IN PARALLEL after G1 Design Freeze

G2 Formal implementation / batch materialization
= WAIT FOR G1 Final Config + Independent Evaluation / G1 Close
```

因此当前允许：Codex 开发 G1；Web 端同步讨论 G2 Design。禁止因为 G2 讨论并行而让下游代码依赖未冻结的临时 segmentation config。

# 4. Phase B｜Segment Semantics

## P2-S2｜G2 Keyframe / Segment Summary

### USER-GATE

冻结：

- first/middle/last；
- max-motion 是否加入；
- keyframe duplicate handling；
- Action/State Summary 的最小字段。

### CODEX

- keyframe extractor；
- summary calculator；
- keyframe path / provenance；
- segment viewer。

### Done Criteria

```text
G2 = CLOSED
SEGMENT → KEYFRAMES = TRACEABLE
SEGMENT → SUMMARY = REPRODUCIBLE
```

---

## P2-L1｜G3 Label Taxonomy + VLM Small Batch

### USER-GATE

冻结：

- Can task 的 phase taxonomy；
- single-label vs structured fields；
- `other / uncertain`；
- VLM 输入范围；
- 如何从 RGB/Keyframes + robot/action summary 恢复足以命名行为的 object relation；
- confidence 仅作为 model-reported signal；
- human GT rubric。

已冻结的职责边界：G3 负责把 G1 的 unlabeled segment 命名为受控物理语义；不要求从视觉恢复毫米级 object pose；simulator object GT 只能用于独立 evaluation / error analysis。

### CODEX

- replaceable Labeler interface；
- API/model wrapper；
- retry / JSON parsing / cache；
- small-batch runner。

### 执行顺序

```text
20–30 Segment small batch
→ Human review
→ taxonomy error analysis
→ Design Owner freeze
→ only then scale
```

### Done Criteria

```text
G3 = CLOSED
CONTROLLED_TAXONOMY = YES
SMALL_BATCH_REVIEW = COMPLETE
HALLUCINATION_CASES = RECORDED
```

---

# 5. Phase C｜Representation & Retrieval

## P2-R1｜G4 Representation Design + Embedding

### USER-GATE

必须讨论：

1. frozen visual encoder；
2. 多 keyframe aggregation；
3. L2 normalization；
4. Visual 与 Action/State evidence 分开还是 vector concat；
5. 如有融合，发生在 representation 还是 score/rank 层。

当前 MVP 优先方向：

```text
Visual Embedding
+
Action/State interpretable features
→ separate evidence
→ transparent optional fusion
```

### CODEX

- batch embedding；
- caching；
- metadata/version；
- feature normalization implementation；
- sanity pair report。

### USER-VERIFY

至少人工构造四类 sanity pairs：

```text
similar visual + similar action
similar visual + different action
different visual + similar action
different visual + different action
```

### Done Criteria

```text
G4 = CLOSED
REPRESENTATION_VERSIONED = YES
SANITY_CASES_REVIEWED = YES
```

---

## P2-R2｜G5 Retrieval Design + Top-K Audit

### USER-GATE

冻结：

- relevant 的语义；
- global vs within-phase search；
- Visual/Action evidence 是否融合；
- relevance rubric；
- P@5/P@10 的人工判定口径。

### CODEX

- exact cosine Top-K；
- retrieval table；
- query viewer；
- no FAISS requirement in MVP。

### USER-VERIFY

亲自检查代表性 Query 的 Top-K：

- 好检索；
- 视觉近但动作不近；
- 标签近但视觉差；
- 明显 retrieval failure。

### Done Criteria

```text
G5 = CLOSED
TOP_K_RETRIEVAL = RUNNABLE
RELEVANCE_RUBRIC = FROZEN
```

---

# 6. Phase D｜Dataset Mining

## P2-D1｜G6 Dedup Candidate / Group

### USER-GATE

冻结：

- duplicate candidate evidence；
- threshold calibration procedure；
- transitivity / grouping；
- review decision rubric。

### Calibration Rule

```text
sample candidate pairs
→ manual duplicate / non-duplicate
→ inspect similarity evidence
→ freeze calibration rule
→ numeric threshold in Formal Config
```

### CODEX

- pair generation；
- graph/group implementation；
- review export；
- duplicate ratio / group summary。

### Done Criteria

```text
G6 = CLOSED
DUPLICATE_CANDIDATES = AVAILABLE
AUTO_DELETE = NO
```

---

## P2-C1｜G7 Long-tail / Coverage Mining

### USER-GATE

冻结：

- kNN rarity definition；
- global vs within-phase rarity；
- label frequency role；
- coverage dimensions；
- top-ranked review categories。

人工分类建议固定为：

```text
true rare behavior
meaningful variation
recovery / hard case
bad data
label error
representation artifact
```

### CODEX

- nearest-neighbor statistics；
- rarity ranking；
- coverage summary；
- review package。

### Done Criteria

```text
G7 = CLOSED
RARITY_RANKING = AVAILABLE
COVERAGE_SIGNAL = AVAILABLE
VALUE_CLAIM = NOT_AUTO_ASSIGNED
```

---

# 7. Phase E｜Formal Evaluation & Freeze

## P2-E1｜G8 Evaluation Protocol

### USER-GATE

必须冻结：

```text
Calibration Set
vs
Evaluation Set
```

以及每个任务的人工 GT rubric。

### 最低 Formal Metrics

```text
Auto-label:
Accuracy + Confusion Matrix

Retrieval:
Precision@5 + Precision@10

Dedup:
Reviewed Duplicate Precision

Long-tail / Coverage:
Top-ranked human review distribution + representative cases
```

### CODEX

- sample manifest；
- metric implementation；
- confusion matrix/result table；
- reproducible report export。

### Done Criteria

```text
G8 = CLOSED
CALIBRATION_EVALUATION_ROLE_SEPARATED = YES
FORMAL_EVAL_FROZEN = YES
```

---

## P2-M1｜Unified Mining Manifest + Result Package

Codex 主导工程汇总，用户做最终 claim review。

最低输出：

```text
segment_manifest
keyframe_summary
structured_label
representation metadata
retrieval_neighbors
duplicate_candidates/groups
rarity/coverage ranking
human review fields
evaluation_summary
README / Result Table / representative cases
```

---

# 8. Phase F｜P2-O1 Optional P1 Failure Query

前置：P1 提供稳定可解释 Failure Segment / Episode。

```text
P1 Failure Query
→ P2 Representation
→ Top-K Training Segments
→ Human Review
→ candidate data-side explanation
```

如果 P1 query 不可用：

```text
SKIP_WITHOUT_BLOCKING_P2_FREEZE = YES
```

---

# 9. Parallel Development Rules｜与 Project 1 并行规则

```text
P1 = ACTIVE_CLOSEOUT
P2 = ACTIVE_BOOTSTRAP / DEVELOPMENT
P3 = NOT_STARTED
```

P2 不等待 P1 全部结束，但必须遵守：

- Source Contract 复用 P1；
- P1 Failure Query Optional；
- 用户同时推进时优先处理 Gate/Review，而不是重复写工程代码；
- Codex 可并行准备脚手架，但不得越过未冻结 Gate 生成 Formal claims。

---

# 10. Cut / De-scope Order｜进度不足时砍项

优先砍：

1. FAISS / Vector DB；
2. 高级多模态融合；
3. 复杂 learned segmentation；
4. 第二数据源泛化；
5. P1 Failure Optional Case；
6. 大规模人工标注。

尽量不砍：

```text
G1 Segment validity
G4 Representation validity
G5 Retrieval human audit
G6 Dedup human calibration
G7 Long-tail human interpretation
G8 Calibration/Evaluation separation
```

---

# 11. Roadmap Change Control

任何以下变化都必须回到 Master：

- Segment 基本定义变化；
- Label taxonomy 粒度变化；
- Representation 从 separate evidence 改为 vector-level fusion；
- Retrieval relevance definition 改变；
- Dedup 从 candidate 变成自动删除；
- rarity 被直接解释为 value；
- Evaluation Set 被用于调参。

流程：

```text
Implementation evidence
→ CHANGE_REQUEST
→ Design Owner Review
→ Master update
→ Gate status update
→ Roadmap update
→ Daily Plan / Codex implementation
```

---

# 12. 每日责任分工

## USER-GATE｜用户必须拍板

- G1/G3/G4/G5/G6/G7/G8 的核心定义；
- 人工样本 rubric；
- threshold calibration 方法；
- representative success/failure cases；
- claim boundary。

## USER-VERIFY｜用户必须检查

- 10–20 Episode segmentation；
- 20–30 Segment VLM small batch；
- embedding sanity pairs；
- Top-K retrieval；
- duplicate candidates；
- long-tail top cases；
- formal Evaluation samples。

## CODEX｜可主导

- reader / IO；
- manifest；
- visualization/viewer scaffolding；
- VLM API wrapper；
- batch embedding；
- exact retrieval；
- pair/group calculations；
- metrics / report；
- CLI / tests / cache / logging。

---

# 13. 下游 Daily Plan 生成规则

每天的 Web Plan / Codex Plan 开始前必须先读取：

```text
1. Project_2_Engineering_Design_Master_v1_20260914.md
2. Project2_Development_Roadmap_and_Design_Gate_Plan_v1_20260914.md
3. 02_robot_demonstration_mining_autolabel_design.md
4. 当前已关闭 Gate 的 decision / audit
5. 前一天真实 repo / result / audit
```

Daily Plan 必须先声明：

```text
CURRENT_GATE
BLOCKED_DOWNSTREAM
USER_DECISION_NEEDED
CODEX_ALLOWED_SCOPE
```

如果当前 Gate 尚未关闭，不能把后续 Formal Task 当成当天必做项。

---

# 14. 当前下一步

```text
NEXT = P2-S1D / G1-P4 FORMAL EVALUATION AUDIT RUN + HUMAN REVIEW
G1_DESIGN = FROZEN
G1_GATE = OPEN_FOR_INDEPENDENT_EVALUATION
G1_P3_STAGE_A = CLOSED_OWNER_SELECTED_A1_007_C002
G1_P3_STAGE_B = CLOSED_NO_SAFE_INCREMENTAL_CHANGE
G1_P3_STAGE_B_EFFECTIVE_WINDOW = RETAIN_PARENT_8
G1_P3_STAGE_C = CLOSED_PASS
G1_CALIBRATION_CONFIG = FROZEN_v1
G1_FINAL_CONFIG = FROZEN_FOR_INDEPENDENT_EVALUATION
G1_P4_GATE = OPEN
G2_DESIGN = MAY_PROCEED_IN_PARALLEL
```

当前 G1 Calibration 已关闭搜索。冻结配置为 `A1-007-C002`，`tau_P12=0.04758563666765155`，`tau_C12=0.690169167642685`，`boundary_consolidation_window=8`。Calibration Set 及其两个 known residual 不得再用于任何规则或参数调整。

优先执行：

```text
P2-S1D Formal Evaluation Audit Run
→ 只使用 FROZEN_v1 的 24 条 Evaluation episode
→ 使用 Frozen Config 一次性生成正式 EVALUATION segmentation / audit package
→ 启动 Human Evaluation Audit，生成 Evaluation GT
→ 按 Frozen matching/tolerance 正式计分
→ 输出 Boundary-level Evaluation + Failure Cases
→ 禁止基于 Evaluation 结果调参
→ Design Owner G1 Evaluation Review
→ G1 Close（仅在 Evaluation review 通过后）
```

并行允许：

```text
Web: G2 Segment Summary / Keyframe Design
```

仍禁止：Dedup threshold、rarity formula、VLM 大批量实现、依赖临时 segmentation config 的下游正式 batch。
