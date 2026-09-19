# Project 2 Engineering Design Master v1
## Robot Demonstration Mining & Auto-Labeling / Mining & Coverage

## 文档变更历史

> 维护规则：后续每次修改正文时必须追加记录；不得覆盖旧记录。核心 Design 变化必须先由 Design Owner Review，再更新 Roadmap / Daily Plan。

| 日期 | 版本 / 状态 | 变更内容 | 变更人 / 来源 |
|---|---|---|---|
| 2026-09-14 | **ACTIVE MASTER SSOT v1** | 仿照 Project 1 工程治理建立 P2 Engineering Master；冻结 P2 文档层级、四层开发架构、G0–G8 Design Gate 机制、Calibration/Evaluation 隔离、P1 Failure Query Optional 边界与 P3 接口。G0 CLOSED，G1 OPEN，其余 Gate 按依赖 pending。 | 用户 Design Owner + ChatGPT |
| 2026-09-14 | **G1/G3 SEMANTIC RESPONSIBILITY FREEZE** | 冻结 Segmentation 与 Semantic Labeling 的职责边界：G1 仅基于可泛化 robot signals 生成 unlabeled behavior segments，不负责 approach/grasp/place 等最终物理语义；G3 通过 RGB + Keyframes + robot/action summary 恢复 object relation 并赋受控物理语义；simulator object GT 仅作为 hidden Oracle / Evaluation Reference，不进入 Formal inference。G1 仍为 OPEN，待 Boundary Rule / Length Guard / Merge / Review Rubric 关闭。 | 用户 Design Owner + ChatGPT |
| 2026-09-14 | **G1-B BOUNDARY SEMANTICS FREEZE** | 冻结首版 Boundary 证据层级与 Rotation 角色：persistent gripper transition=Hard Boundary Candidate；persistent moving↔stationary、large+persistent main-direction change=Motion Boundary Candidate；EEF rotation regime change 与 recorded action change 仅作 Supporting Evidence，不得单独触发 Formal boundary。Rotation 定义为 EEF orientation change（基于 `robot0_eef_quat`），不是某一关节角变化；当前 Can task 中优先级低于 gripper / translation-speed / direction change。所有 temporal event 需 persistence/debounce，最终 numeric threshold 进入 DATA_CALIBRATION_PENDING。G1 仍 OPEN，待 Length Guard / Merge / Human Review Rubric。 | 用户 Design Owner + ChatGPT |
| 2026-09-14 | **G1-C LENGTH GUARD & MERGE FREEZE** | 冻结 Event-aware Merge：区分 Boundary Consolidation 与 Segment Merge；confirmed gripper transition 受 Hard Boundary Protection；`min_segment_length` 只触发 SHORT_SEGMENT_CANDIDATE review/merge，不直接 delete；短 pause 仅在前后 gripper 状态一致且 motion compatible 时桥接；短片段向更兼容邻居合并；`max_segment_length` 首版只触发 audit，不做 fixed-window forced split。所有数值阈值进入 DATA_CALIBRATION_PENDING。 | 用户 Design Owner + ChatGPT |
| 2026-09-14 | **G1-D HUMAN CALIBRATION LOOP FREEZE** | 冻结 Boundary-level Human Review 为主标注粒度，Episode-level 仅作自动聚合/备注；人工审查必须同时提供 video path、完整 Formal Signal Set plot、Candidate/Final/Suppressed Boundary 与 reason；人工标签结构化为 VALID / REDUNDANT / MISALIGNED / MISSED_BOUNDARY + corrected_frame + reason_code，并形成 Calibration Loop，用于 numeric threshold search 与有限 strategy search。Calibration Set 与独立 Evaluation Set 隔离；G1 Design 已冻结，但 Gate 仍需真实数据 calibration/evaluation 后关闭。 | 用户 Design Owner + ChatGPT |

---

# 0. 文档定位与 SSOT 治理

## 0.1 本 Master 负责什么

本文是 Project 2 的 **Engineering SSOT (Single Source of Truth，工程单一事实源)**。

本文负责：

1. P2 的端到端工程架构与阶段依赖；
2. Source / Segment / Label / Representation / Retrieval / Dedup / Coverage / Evaluation 的公共工程契约；
3. G0–G8 Design Gate 的定义、状态和上下游阻塞关系；
4. 用户 Design Owner 与 Codex Implementation Engineer 的责任边界；
5. Formal Config / Manifest 与上层 Design 的边界；
6. Project 1 Failure Query 与 Project 3 Exposure Signal 的接口边界。

本文不负责：

- 每日学习内容；
- 当天具体代码文件路径和函数级实现；
- 某次实验的具体 segment ID / random seed；
- 依赖真实数据标定的最终 numeric threshold；
- 结果数字本身。

这些分别进入 Roadmap / Daily Plan / Formal Config / Code / Result / Audit。

## 0.2 文档层级

```text
Portfolio / 三项目总控
        ↓
02_robot_demonstration_mining_autolabel_design.md
Readable / Research Design
        ↓
Project_2_Engineering_Design_Master_v1_20260914.md
本文：Engineering SSOT
        ↓
Project2_Development_Roadmap_and_Design_Gate_Plan_v1_20260914.md
阶段执行 Authority
        ↓
Project_2/daily_plan/
Web Learning Plan / Codex Execution Plan
        ↓
Formal Config / Manifest
        ↓
Code / Result / Audit
```

## 0.3 冲突优先级

若文档冲突：

```text
Portfolio scope / hard deadline
→ 三项目总控优先

P2 核心工程契约 / Gate 状态
→ 本 Master 优先

项目解释、学习与面试理解
→ Readable Design 提供解释，但不得与 Master 冲突

阶段顺序 / USER-GATE / Done Criteria
→ Development Roadmap 优先，但不得新增核心 Design

具体运行参数 / IDs / thresholds / seeds
→ Formal Config / Manifest 优先，但不得违反上层 Design

当天任务 / 文件路径 / Codex 实施步骤
→ Daily Plan / Codex Plan
```

Daily Plan 不允许静默改变 Design。

```text
Implementation finding
→ Design Change Request
→ Design Owner Review
→ Master 更新
→ Gate Freeze
→ Roadmap / Plan 更新
→ Code 更新
```

---

# 1. Project 2 最终目标

P2 解决的是 **Content / Mining / Coverage（内容、挖掘与覆盖）**，不是再次做 Data Quality，也不是直接输出最终训练价值。

P2 要回答四个问题：

### Q1. 数据在做什么？

把长 Episode 转为可解释的 Behavior Segment，并生成受控语义标签。

### Q2. 哪些数据彼此相似？

建立可解释的 Segment Representation 与 Similarity Retrieval。

### Q3. 哪些内容重复、稀缺或缺覆盖？

基于 Retrieval neighborhood 形成 Dedup Candidate、Long-tail Ranking 和 Coverage Signal。

### Q4. 这些信号能否被人工验证，并给 P3 / Failure Analysis 使用？

通过独立人工评测证明 Mining Signal 有语义有效性；若 P1 Failure Query 可用，则作为 Optional model-driven query；P3 可把 P2 信号作为候选 Exposure Signal，但不能直接等价为 sampling weight。

强边界：

```text
rarity ≠ value
high similarity ≠ delete
coverage gap ≠ upweight
```

---

# 2. 最终端到端架构

```text
Layer 0｜Data Foundation
RoboMimic Can/MH
P1 RoboMimic Unified Source Contract
        ↓
Layer 1｜Semantic Unit Construction
Episode
→ Trajectory Segmentation
→ Segment
→ Keyframe + Action/State Summary
        ↓
Layer 2｜Semantic Representation
Segment
├─ VLM / Replaceable Labeler → Structured Label
├─ Frozen Visual Encoder → Visual Embedding
└─ Action/State Summary → Interpretable Feature
        ↓
Layer 3｜Dataset Mining
Similarity Retrieval
├─ Duplicate Candidate / Group
└─ Long-tail / Coverage Ranking
        ↓
Layer 4｜Validation & Connection
Human Calibration
→ Gate Freeze
→ Human Evaluation
→ [OPTIONAL] P1 Failure Retrieval / Coverage
→ P3 Candidate Exposure Signal
```

依赖原则：

> **Semantic Unit 先于 Representation；Representation 先于 Mining；Evaluation Protocol 先于正式结果。**

---

# 3. Source Foundation Contract｜G0 FROZEN

## 3.1 Primary Dataset

```text
PRIMARY_DATASET = RoboMimic Can/MH
TASK_WORLD = robosuite PickPlaceCan / Can manipulation
SOURCE_CONTRACT_AUTHORITY = Project 1 RoboMimic Unified Source Contract
```

P2 不重新建立 generic schema，不重新审计已经由 P1 冻结的：

- `agentview` camera；
- 128×128 RGB；
- temporal indexing；
- State / Action semantics；
- source_episode_id grouping / provenance；
- canonical pixel / HDF5 storage。

如果 P2 实际代码发现 Source Contract 与真实文件不一致，必须触发 Source Contract Change Request，不能在 P2 内偷偷新建第二套解释。

## 3.2 P1 Failure Query

```text
P1_POLICY_FAILURE_QUERY = OPTIONAL_INPUT
BLOCKS_SEGMENTATION = NO
BLOCKS_REPRESENTATION = NO
BLOCKS_RETRIEVAL = NO
BLOCKS_P2_FREEZE = NO
```

---

# 4. P2 Common Data Contracts

## 4.1 Episode Contract

最低必须可追溯：

```text
source_episode_id
frame/timestep
image reference
state reference
action reference
task/world provenance
```

## 4.2 Segment Contract

每个 Segment 至少包含：

```text
segment_id
source_episode_id
start_frame
end_frame
duration
boundary_reason / boundary evidence
segmentation_version
```

要求 Segment 能回溯到原始 Episode 与帧，不允许只保存不可追溯的 embedding row。

## 4.3 Segment Summary Contract

```text
segment_id
keyframe references
duration
EEF / motion summary
gripper start/end/change
optional motion magnitude summary
summary_version
```

Summary 只服务于行为理解与 Retrieval，不扩展成第二个 M07 Feature Bank。

## 4.4 Structured Label Contract

正式字段必须由 G3 冻结。原则上允许：

```text
motion_phase
object_relation / interaction state (optional)
gripper_state (optional)
success_evidence (optional)
model_reported_confidence
label_source
labeler_version
```

`model_reported_confidence` 不是 calibrated probability。

## 4.5 Representation Contract

Visual 与 Action/State evidence 必须保留来源边界：

```text
visual_embedding
visual_encoder_version
visual_normalization
segment_aggregation

action_state_feature
action_state_normalization
feature_version
```

第一版默认不允许把简单 concat 表述为“训练好的 Multimodal Embedding Model”。

## 4.6 Retrieval Edge Contract

```text
query_segment_id
neighbor_segment_id
visual_similarity
action_similarity / action_distance (if enabled)
retrieval_scope
rank
retrieval_version
```

## 4.7 Dedup Candidate Contract

```text
duplicate_candidate
candidate_evidence
duplicate_group_id (if grouped)
review_decision
review_reason
```

P2 默认输出 Candidate / Group，不直接输出 `delete=True`。

## 4.8 Rarity / Coverage Contract

```text
global_rarity_signal
within_phase_rarity_signal (if enabled)
neighbor_density / distance
label_frequency
coverage_dimension
review_category
review_reason
```

## 4.9 Evaluation Contract

必须区分：

```text
CALIBRATION_SET
EVALUATION_SET
```

Evaluation Set 冻结后不得用于继续调 threshold / fusion / taxonomy。

---

# 5. Design Gate System｜G0–G8

英文 **Design Gate** 指“设计门禁”：进入下一开发层之前，必须由 Design Owner 关闭的方案决策点。

| Gate | Design Scope | Design Owner 必须拍板 | 允许数据标定后再定 | 当前状态 | Downstream Block |
|---|---|---|---|---|---|
| G0 | Source Foundation | Dataset / Contract / provenance | 无 | **CLOSED** | 无 |
| G1 | Segmentation | signal family、boundary semantics、gripper event、length/merge、review rubric | motion threshold 等 numeric | **OPEN** | G2–G8 Formal |
| G2 | Segment Summary | keyframe policy、summary fields | 极少 | PENDING_G1 | G3/G4 batch |
| G3 | Label Taxonomy | taxonomy、structured fields、VLM inputs、confidence semantics | prompt wording微调 | PENDING_G1_G2 | Formal label eval |
| G4 | Representation | encoder family、aggregation、Visual/Action separation、normalization principle | exact model checkpoint if equivalent family | PENDING_G2 | G5–G7 |
| G5 | Retrieval | similarity semantics、fusion/filter、relevance rubric | fusion weight if used | PENDING_G4 | G6/G7 |
| G6 | Dedup | candidate semantics、threshold calibration protocol、grouping rule | final numeric threshold | PENDING_G5 | Formal dedup result |
| G7 | Long-tail/Coverage | rarity dimensions、kNN definition、global/within-label、review categories | final k / scale if calibrated | PENDING_G5 | Formal coverage result |
| G8 | Evaluation | calibration/eval split、GT rubric、metrics、freeze rule | exact sample IDs | PENDING_G6_G7 | Project formal result |

Gate 状态只允许：

```text
PENDING
OPEN_FOR_REVIEW
FROZEN / CLOSED
```

数据依赖的最终数值统一标记：

```text
DATA_CALIBRATION_PENDING
```

---

# 6. G1｜Trajectory Segmentation Design Contract｜OPEN

## 6.1 目标

把 Episode 转换成后续 Mining 的最小连续行为单元，而不是追求 SOTA semantic segmentation。

G1 的正式输出冻结为 **Unlabeled Behavior Segment（未命名行为片段）**。G1 只回答：

> **哪里可能发生了值得切分的行为状态变化？**

G1 不负责直接判断：

```text
approach
grasp
lift
transport
place
retract
```

这些最终物理语义由 G3 Label Taxonomy / VLM 阶段负责。

## 6.2 G1→G3 Semantic Responsibility｜FROZEN

### Formal G1 Boundary Inputs

首版 Formal Boundary Proposal 只允许使用未来真实机器人数据中通常可获得、且当前 Can/MH 已有的 robot-side signals：

```text
Layer 1 — Robot Kinematics
- EEF position / realized translation
- EEF orientation / realized rotation
- derived EEF velocity / motion change

Layer 2 — Interaction
- gripper state / aperture
- gripper transition

Layer 3 — Command
- source-native recorded action
- command change evidence
```

语义原则：

```text
realized motion = Primary evidence
commanded motion = Supporting evidence
gripper event = independent interaction evidence
```

### Formal G1 禁止使用的 Simulator Privileged Inputs

以下字段即使 Can/MH / simulator 可提供，也不得进入 Formal Boundary Proposal：

```text
Can_pos
Can_quat
Can_to_robot0_eef_*
raw object / object-state GT
reward
done
success
```

### Privileged Oracle / Evaluation Reference

上述 simulator object GT 可以保留在受限 evaluator / audit namespace 中，用于：

1. **Boundary Evaluation**：比较 Formal Boundary 是否接近真实物理 interaction transition；
2. **Semantic Label Evaluation**：检查 G3 输出的 grasp/place 等标签是否与 object motion / relative relation 一致；
3. **Error Analysis**：区分是 G1 切分错误、G3 视觉语义错误，还是数据本身异常。

这里的 **Oracle（理想参考 / 上帝视角参考）** 仅表示“评测答案”，不表示 Formal 模型可以消费这些字段。

### G3 的语义来源

最终 object-centric physical semantics 由：

```text
RGB / Keyframes
+ gripper / EEF / action-state summary
→ VLM / Replaceable Labeler
→ object relation / interaction state
→ controlled motion phase label
```

需要恢复的是足以完成行为命名的 **Object Relation（物体关系信息）**，例如：

```text
gripper approaching can
gripper around can
can moving with gripper
can resting after release
gripper moving away from can
```

不要求 Formal pipeline 从 RGB 恢复毫米级 `Can_pos`。


## 6.3 G1-B Boundary Semantics｜FROZEN

首版 Boundary 证据按强弱分层，不把所有 signal 混成一个不可解释 scalar：

```text
Hard Boundary Candidate
- persistent gripper open → close
- persistent gripper close → open

Motion Boundary Candidate
- persistent moving → stationary
- persistent stationary → moving
- large + persistent main-direction change

Supporting Evidence only
- EEF rotation regime change
- recorded action / command change
```

冻结解释：

- **EEF Rotation（末端姿态旋转）** 指 `robot0_eef_quat` 所表示的末端执行器整体朝向变化，不等价于某一个 Panda joint 的旋转；7-DoF 关节可共同实现同一 EEF orientation change。
- 当前 Can PickPlace 首版中，Rotation 主要用于辅助确认“运动模式是否真的改变”，例如 translation main-direction change 同时伴随明显姿态调整；**Rotation alone 不得切段**。
- Rotation 在 insertion / assembly / pouring 等姿态语义更强的任务中可升级权重，但不得反向改变当前 Can/MH v1 口径。
- recorded Action 表示 command intent，不代表 realized physical motion；Action spike / command change 单独不足以形成 boundary。
- single-frame velocity fluctuation、instantaneous sign flip、short pause、rotation noise 均不足以单独触发 Formal boundary。
- 所有 temporal event 必须经过 **Persistence（持续性要求）** 与 **Debounce（去抖）**；最终 frame count / speed / angle 等 numeric threshold 标记为 `DATA_CALIBRATION_PENDING`。

当前首版证据优先级：

```text
1. Gripper transition
2. EEF translation / speed state
3. EEF main-direction change
4. EEF rotation
5. Action change
```

## 6.4 G1-C Length Guard & Merge｜FROZEN

首版采用 **Event-aware Merge（事件感知合并）**，禁止仅按长度粗暴删除或强拆 Segment。

### Boundary Consolidation（边界聚合）

相邻多个 candidate 若来自同一次物理 transition，应先聚合成一个 boundary event，而不是形成多个紧邻切分点：

```text
gripper transition @t
direction change @t+Δ1
rotation support @t+Δ2
→ one consolidated boundary event
```

### Hard Boundary Protection（强边界保护）

经过 persistence / debounce 确认的 gripper transition 不允许仅因为相邻 Segment 很短而被长度规则跨越删除。

注意：保护的是 boundary，不要求 gripper transition 必须独立形成一个 1–4 frame 的 micro-segment。

### Short Segment Handling（短片段处理）

```text
segment_length < min_segment_length
→ SHORT_SEGMENT_CANDIDATE
→ review neighbor compatibility
→ merge / retain
≠ direct delete
```

### Pause Bridging（短暂停顿桥接）

短 stationary / pause 只有在以下条件同时满足时才允许跨越合并：

- 无 Hard Boundary；
- 前后 gripper state compatible；
- 前后 translation / speed / main-direction 属于兼容 motion regime；
- 无新的主要 motion transition 证据。

### Neighbor-Compatible Merge（邻域兼容合并）

短 Segment 优先合并到更兼容的一侧，证据优先级继承 G1-B：

```text
gripper
> translation / speed
> main-direction
> rotation
> action
```

### Max Length Guard（最大长度保护）

首版 `max_segment_length` 仅作为 **Audit Guard（审计保护）**：

```text
segment too long
→ audit flag
→ search for valid secondary boundary if available
≠ blind fixed-window split
```

以下数值全部进入 `DATA_CALIBRATION_PENDING`：

```text
min_segment_length
pause_bridge_duration
boundary_consolidation_window
max_segment_length
```

## 6.5 G1-D Boundary-level Human Calibration Loop｜FROZEN

G1 人工审查主粒度冻结为 **Boundary-level Review（边界级审查）**。Episode-level 不再作为主要人工标签，只用于自动聚合 summary、备注和阻塞问题记录。

### Primary Human Annotation

预测边界与人工补充边界统一结构化为：

```text
VALID
REDUNDANT
MISALIGNED
MISSED_BOUNDARY
```

其中：

- `VALID`：确实发生值得切分的 interaction / motion transition；
- `REDUNDANT`：前后本质仍属于同一行为状态；
- `MISALIGNED`：事件找到了，但 frame 位置偏早/偏晚，必须记录 `corrected_frame`；
- `MISSED_BOUNDARY`：人工认为应切但算法未产生 final boundary。

人工标注还必须记录 `reason_code`，用于 error attribution。首版允许：

```text
REDUNDANT_SHORT_PAUSE
REDUNDANT_DIRECTION_JITTER
REDUNDANT_ROTATION
REDUNDANT_ACTION_JITTER
MISSED_GRIPPER_TRANSITION
MISSED_MOVE_STOP
MISSED_STOP_MOVE
MISSED_DIRECTION_CHANGE
MISALIGNED_GRIPPER
MISALIGNED_MOTION_CHANGE
OTHER
```

### Mandatory Review Evidence

每个 calibration / evaluation Episode 必须提供：

1. **Video path / video reference**：可直接打开完整 Episode；
2. **Full Formal Signal Set Plot**：与 Formal Segmenter 实际使用信号一一对应，统一 frame/timestep x-axis；
3. **Boundary overlays**：Candidate / Final / Suppressed Boundary 必须区分，并标记 reason；
4. **Segmentation manifest**：可追溯 boundary reason、segment start/end、config/version；
5. **Human boundary review table**：保存人工标签、corrected_frame、reason_code、note。

Formal Signal Set plot 至少包含：

```text
EEF translation displacement / speed
moving / stationary state
main-direction change evidence
gripper qpos / derived state / transition
EEF quaternion-derived angular change
recorded action-change evidence
candidate boundaries
final boundaries
suppressed boundaries
```

Simulator `Can_pos / Can_to_EEF / object motion` 可作为单独 **Privileged Audit Overlay（特权审计叠加）**，但必须明确标识 `AUDIT ONLY / NOT USED BY SEGMENTER`。

### Calibration Loop

```text
Segmentation Config vN
→ Calibration Episodes
→ Video + Full Signal Plot + Boundary Output
→ Boundary-level Human Review
→ Human Boundary Reference
→ Precision / Recall / F1 / Localization / Fragmentation / Hard-Boundary Recall
→ Error Attribution
→ Numeric Threshold Search + Limited Strategy Search
→ Config vN+1
→ Re-run
→ Design Owner Review
→ Freeze Final Config
```

数值阈值搜索可以针对：

```text
motion_speed_threshold
motion_persistence
direction_angle_threshold
direction_persistence
pause_bridge_duration
boundary_consolidation_window
min_segment_length
```

Strategy Search 只允许比较已冻结设计边界内的有限、可解释规则组合；不得在 calibration 中静默改变 G1/G3 职责或引入 simulator object GT 作为 Formal 输入。

### Metrics & Guardrails

至少计算：

- **Boundary Precision（边界精确率）**：反映过切；
- **Boundary Recall（边界召回率）**：反映漏切；
- **Boundary F1**：综合参考，不作为唯一目标；
- **Localization Error（边界定位误差）**：比较 predicted frame 与 human corrected frame；
- **Fragmentation Metrics（碎片化指标）**：1–2 frame ratio、short segment ratio、segments/episode；
- **Hard Interaction Boundary Recall（强交互边界召回）**：gripper transition 等强边界作为 guardrail，优先级高于单一总分。

Boundary matching 允许 **Tolerance Window（容忍时间窗）**，具体 `±δ frames` 标记为 `DATA_CALIBRATION_PENDING`。

### Calibration / Evaluation Isolation

```text
CALIBRATION_SET
→ human review
→ threshold / strategy selection
→ final config freeze

EVALUATION_SET
→ run frozen final config once
→ evaluate only
→ no further tuning
```

不得使用 Evaluation Set 继续调整 threshold、merge rule、strategy 或 review taxonomy。

## 6.6 必须关闭的 Design Questions

G1 的架构级 Design Questions 已全部冻结。当前剩余工作不是继续改设计，而是完成真实 Can/MH 数据上的 `DATA_CALIBRATION_PENDING` 数值标定与独立 Evaluation。若 calibration 结果暴露结构性缺陷，必须走 Design Change Request。

## 6.7 开发约束

第一版优先可解释 Motion Boundary Baseline，不直接训练复杂 segmentation model。

Formal batch 前必须先完成 Boundary-level Calibration Review；Calibration Episode 数量首版目标 10–20 个，具体样本数进入 Manifest。人工审查保留 error taxonomy、corrected frame 与代表性失败案例。Episode-level 仅作自动聚合 summary，不替代 Boundary-level 人工标签。

## 6.8 G1 Done Criteria

```text
SEGMENTATION_DESIGN_FROZEN = YES
BOUNDARY_LEVEL_HUMAN_CALIBRATION = COMPLETE
CALIBRATION_CONFIG_FROZEN = YES
INDEPENDENT_EVALUATION_RUN = COMPLETE
BOUNDARY_REASON_TRACEABLE = YES
NO_MASS_1_2_FRAME_FRAGMENTATION = YES
HARD_INTERACTION_BOUNDARY_RECALL = ACCEPTABLE
MAJOR_BEHAVIOR_PHASES_ROUGHLY_SEPARABLE = YES
```

---

# 7. G2｜Keyframe & Segment Summary Contract｜PENDING_G1

必须冻结：

- first / middle / last 是否为固定 keyframe；
- max-motion frame 是否加入；
- 与已有 keyframe 重复时如何去重；
- Action/State Summary 的最小字段。

原则：只保留支持 Labeling / Retrieval 的信息，不扩张成复杂特征工程。

---

# 8. G3｜Label Taxonomy & VLM Contract｜PENDING_G1/G2

## 8.0 G1→G3 Interface｜FROZEN

G3 接收的是 G1 已切分但未命名的 Segment。

```text
G1: robot-side signals
→ unlabeled behavior segments

G2: segment → keyframes + robot/action summary

G3: RGB/keyframes + summary
→ infer object relation / interaction semantics
→ controlled physical phase label
```

因此 `approach / grasp / lift / transport / place / retract` 属于 G3 语义输出，不属于 G1 Boundary Detector 的直接输出。Simulator `Can_pos / Can_to_EEF` 仅用于独立评测与错误分析，不得作为 G3 Formal Labeler 的 hidden shortcut。

## 8.1 Label Taxonomy

标签必须是受控集合，禁止 VLM 自由生成无法统计的长尾文本标签。

必须由 Design Owner 冻结：

- phase 粒度；
- single-label 还是 structured multi-field；
- `other / uncertain` 的处理；
- 人工 GT rubric。

## 8.2 VLM 输入边界

必须明确 VLM 实际消费：

```text
keyframes only
or
keyframes + task text
or
keyframes + selected action/state summary
```

不同输入不能在结果不记录 provenance 的情况下混用。

## 8.3 Confidence

VLM 自报 confidence 仅作：

```text
review priority / model-reported confidence
```

不得称为 calibrated probability。

---

# 9. G4｜Representation Contract｜PENDING_G2

G4 是 P2 一级关键 Gate。

必须冻结：

1. Frozen visual encoder family；
2. 多 keyframe → segment representation 的 aggregation；
3. L2 normalization 等归一化语义；
4. Visual evidence 与 Action/State evidence 是否分开检索；
5. 若融合，融合发生在 score/rank 层还是 vector concat 层。

MVP 默认倾向：

```text
Visual Embedding
+
Interpretable Action/State Feature
→ separate similarity / distance evidence
→ optional transparent rank/score fusion
```

除非后续 Gate 明确修改，不把简单 vector concat 包装为 learned multimodal representation。

---

# 10. G5｜Similarity Retrieval Contract｜PENDING_G4

必须先定义“relevant / similar”是什么意思。

至少区分：

```text
visual similarity
behavior-phase similarity
action similarity
overall semantic relevance
```

必须冻结：

- query scope：global 或 within-phase；
- Visual / Action evidence 是否融合；
- 如融合，规则与 calibration 方法；
- Retrieval Ground Truth / relevance rubric；
- Primary metric：Precision@5 / Precision@10 等。

第一版不需要 FAISS；小规模可直接 exact cosine / NumPy / sklearn。

---

# 11. G6｜Deduplication Contract｜PENDING_G5

Dedup 是 Retrieval 上的 decision layer。

```text
Retrieval neighbor
→ Duplicate Candidate
→ Human-calibrated rule
→ Duplicate Group
```

必须冻结：

1. Duplicate Candidate 的证据组合；
2. threshold calibration protocol；
3. group transitivity：`A≈B, B≈C, A !≈ C` 如何处理；
4. Human review decision；
5. P2 只输出 candidate/group，不自动删除。

最终 numeric threshold 允许 `DATA_CALIBRATION_PENDING`。

---

# 12. G7｜Long-tail / Coverage Contract｜PENDING_G5

## 12.1 Long-tail 不等于异常

Embedding outlier 可能是：

- true rare behavior；
- meaningful variation；
- recovery / hard case；
- bad data；
- label error；
- representation artifact。

因此只能 Rank → Human Review。

## 12.2 必须冻结的 Design

- kNN rarity definition：mean distance / kth-neighbor / density 等；
- global rarity 与 within-phase rarity 是否同时保留；
- label frequency 的角色；
- Coverage 维度。

Coverage 至少区分：

```text
semantic coverage
neighborhood coverage
[OPTIONAL] failure-neighborhood coverage
```

## 12.3 P3 边界

P2 输出 Candidate Data Value Signal，不输出 sampling weight。

---

# 13. G8｜Evaluation Protocol Contract｜PENDING_G6/G7

G8 是正式结果前的最终 Gate。

## 13.1 Calibration / Evaluation Isolation

```text
Human Calibration Set
→ 规则 / threshold / fusion / taxonomy calibration
→ Freeze

Human Evaluation Set
→ Final metrics only
```

若由于样本规模限制需要复用，必须显式标记 non-independent limitation。

## 13.2 Formal Evaluation Scope

最低覆盖：

```text
Auto-label
- Accuracy
- Confusion Matrix

Retrieval
- Precision@5
- Precision@10

Dedup
- Duplicate Precision on reviewed top candidates

Long-tail / Coverage
- Top-ranked human category distribution
- representative cases
```

正式样本 ID、具体 Calibration/Evaluation 数量进入 Manifest，不写死在 Master。

---

# 14. Optional｜P1 Failure Retrieval / Coverage Interface

只有当 P1 已有稳定可解释 Failure Query 时接入：

```text
P1 Policy Failure Segment
→ P2 Representation
→ Top-K Training Segments
→ Human Review
→ Coverage Gap / Duplicate Dominance / Missing Recovery / Label Issue candidate explanation
```

Claim Boundary：

> 该分析提供训练数据侧的解释证据，不证明数据缺口是 Policy Failure 的唯一因果原因。

---

# 15. Project 3 Interface

P2 可向 P3 提供：

```text
behavior phase labels
duplicate groups
rarity signals
coverage gap signals
reviewed recovery / hard-case groups
```

P3 必须重新定义：

```text
Target Exposure
Sampling / Reweight rule
Guardrail
Actual Exposure Audit
Fixed-budget Policy Utility
```

禁止：

```text
P2 rarity score → 直接作为 sampling weight
```

---

# 16. Formal Config / Manifest 与 Design 的边界

以下内容不应写死进 Master：

- 最终 episode / segment ID；
- Calibration / Evaluation 的具体样本列表；
- random seed；
- motion numeric threshold；
- Dedup numeric threshold；
- kNN 最终 k（若需数据标定）；
- encoder exact checkpoint（若 Gate 只冻结 family/contract）；
- exact fusion weight；
- concrete output file paths；
- config / manifest hash。

这些进入 Formal Config / Manifest。

---

# 17. 当前设计状态

| 模块 | 状态 | SSOT |
|---|---|---|
| P2 Project Scope | FROZEN / ACTIVE_BOOTSTRAP | Readable Design + 本 Master |
| Source Foundation | **G0 CLOSED** | P1 Source Contract + 本 Master |
| Trajectory Segmentation | **G1 OPEN_FOR_REVIEW** | 本 Master |
| Keyframe / Summary | PENDING_G1 | 本 Master |
| Label Taxonomy / VLM | PENDING_G1_G2 | 本 Master |
| Representation | PENDING_G2 | 本 Master |
| Retrieval | PENDING_G4 | 本 Master |
| Dedup | PENDING_G5 | 本 Master |
| Long-tail / Coverage | PENDING_G5 | 本 Master |
| Evaluation Protocol | PENDING_G6_G7 | 本 Master |
| P1 Failure Query | OPTIONAL / NON-BLOCKING | 本 Master |
| P3 Exposure Interface | CONTRACT FROZEN AT BOUNDARY | 本 Master + P3 SSOT |

---

# 18. 下游 AI 最小必读集合

开发任何 P2 主线任务前至少读取：

```text
1. 02_robot_demonstration_mining_autolabel_design.md
2. Project_2_Engineering_Design_Master_v1_20260914.md
3. Project2_Development_Roadmap_and_Design_Gate_Plan_v1_20260914.md
4. Project 1 RoboMimic Unified Source Contract
5. 当前 Daily Codex Execution Plan
6. 当前 Formal Config / Manifest（若已存在）
7. 当前 repo / result / audit
```

如果任务涉及 G4–G8，必须同时读取对应已冻结 Gate 的最新 Review/decision 记录，不允许从旧聊天或旧 plan 猜结论。

---

# 19. Project Freeze 最低条件

P2 不以“所有想法都做完”为冻结条件。

Formal Freeze 最低需要：

```text
G0–G8 required gates CLOSED
Episode → Segment traceability
Keyframe / Summary runnable
Controlled Auto-label taxonomy
Visual Embedding + Action/State evidence
Top-K Retrieval
Dedup Candidate / Group
Long-tail / Coverage ranking
Calibration/Evaluation isolation recorded
Human-reviewed formal evaluation
Unified Mining Manifest
README / Result Table / representative cases
```

P1 Failure Query 仍为 Optional，不得阻塞 P2 Freeze。
