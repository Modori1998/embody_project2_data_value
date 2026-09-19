# Robot Demonstration Mining & Auto-Labeling
## 文档变更历史

> 维护规则：后续每次修改正文时，必须同步在本表新增一条记录；只追加，不覆盖既有记录。

| 日期 | 版本 / 状态 | 变更内容 | 变更人 / 来源 |
|---|---|---|---|
| 2026-08-20 | 初始版本 / 历史补录 | 文档创建；依据 Drive 创建时间补录。因此前无变更表，不追溯或猜测未记录的具体编辑内容。 | Drive metadata / 历史补录 |
| 2026-09-01 | 历史更新（内容未追溯） | Drive 显示该日存在文档更新；此前缺少变更记录，具体修改内容未可靠追溯。 | Drive metadata / 历史补录 |
| 2026-09-03 | HISTORY-LOG-INIT | 新增文档变更历史表；正文内容未改。 | ChatGPT（用户要求） |
| 2026-09-14 | **P2 SOURCE / SCOPE REBASELINE — CURRENT AUTHORITY** | Primary Dataset 冻结为 RoboMimic Can/MH；输入语义与字段契约复用 Project 1 RoboMimic Unified Source Contract；旧 9/10–9/16 时间表废止并改为 9/14 起压缩执行；Project 1 Policy Failure Query 改为 OPTIONAL_INPUT，不得阻塞 Segmentation / Embedding / Retrieval 主线；明确 P2 的 rarity / duplicate / coverage 只作为候选数据价值信号，不直接等价于真实训练价值。 | 用户 Design Owner + ChatGPT |
| 2026-09-14 | **ENGINEERING GOVERNANCE + DESIGN GATE REBASELINE** | 仿照 Project 1 文档治理，新增 Project 2 Engineering Master 与 Development Roadmap；在 Readable Design 中加入 G0–G8 Design Gate 总览、阶段依赖与 Calibration/Evaluation 隔离原则。当前 G0 Source Foundation=CLOSED，G1 Segmentation=OPEN，其余 Gate 按依赖等待。 | 用户 Design Owner + ChatGPT |
| 2026-09-14 | **G1/G3 SEMANTIC RESPONSIBILITY FREEZE** | 冻结行为切分与语义命名的职责边界：G1 使用 robot kinematics / gripper / recorded action 产生未命名 Segment；G3 使用 RGB + Keyframes + robot/action summary + VLM/Labeler 恢复 object relation 并赋 approach/grasp/lift/transport/place/retract 等物理语义；Can_pos / Can_to_EEF 等 simulator object GT 仅用于隐藏评测与错误分析。 | 用户 Design Owner + ChatGPT |
| 2026-09-14 | **G1-B BOUNDARY SEMANTICS FREEZE** | 冻结首版边界证据层级：gripper transition 为强候选；持续 moving↔stationary 与大幅且持续的主方向变化为运动候选；EEF Rotation 与 Action change 仅作辅助。Rotation 指 `robot0_eef_quat` 的末端整体姿态变化，不是某个关节单独旋转；当前 Can task 中 Rotation 不可单独触发切段。阈值与持续帧数留待数据标定。 | 用户 Design Owner + ChatGPT |

## 项目 2：机器人示范数据语义挖掘与自动标注设计文档

> **项目定位**：作为项目 1 的互补项目，重点覆盖目标岗位中高频出现、但 Data Quality 项目覆盖不足的能力：多模态机器人数据理解、自动标注、Embedding、相似检索、去重、长尾/Corner Case 挖掘。主线独立完成训练数据 Content / Coverage 建模；当 Project 1 已产生稳定 Policy Failure Case 时，可选将其作为 Retrieval Query，回溯训练数据侧的缺失、重复、长尾与标签问题。
>
> **时间预算**：**2026-09-14 起压缩执行**。旧 `2026-09-10 ～ 2026-09-16` 时间表已废止；具体日程由 `Project_2/daily_plan/` 当前计划控制，且不得等待 Project 1 全部完成后才启动。
>
> **核心原则**：Primary Dataset 固定为 **RoboMimic Can/MH**，并复用 Project 1 已冻结的 RoboMimic Source Contract / Adapter 语义，不重新建立竞争性 schema 或数据读取链路；不训练 VLA/VLM 大模型，也不为了 Project 2 再训练第二套 Policy。Project 1 的 Policy Failure Case 仅作为可选的模型驱动 Query，**不是** P2 前半程 Segmentation / Embedding / Retrieval 的前置依赖。

---

# 2026-09-14 Rebaseline｜CURRENT AUTHORITY

本节覆盖本文中与当前 Source、Timeline、Project 1 依赖关系冲突的旧描述。

```text
PROJECT_2_STATUS = ACTIVE_BOOTSTRAP
PRIMARY_DATASET = RoboMimic Can/MH
SOURCE_SCHEMA_AUTHORITY = Project 1 RoboMimic Unified Source Contract
OLD_GENERIC_SCHEMA = SUPERSEDED
OLD_2026-09-10_TO_2026-09-16_TIMELINE = SUPERSEDED
CURRENT_TIMELINE = COMPRESSED_FROM_2026-09-14
P1_POLICY_FAILURE_QUERY = OPTIONAL_INPUT
P1_FAILURE_QUERY_BLOCKS_SEGMENTATION = NO
P1_FAILURE_QUERY_BLOCKS_EMBEDDING_RETRIEVAL = NO
ENGINEERING_MASTER = Project_2_Engineering_Design_Master_v1_20260914.md
ROADMAP_PLAN = Project2_Development_Roadmap_and_Design_Gate_Plan_v1_20260914.md
```

P2 的核心问题是 **Content / Coverage**，不是再次判断绝对 Data Quality，也不是直接计算“真实训练价值”：

```text
P1 Quality:
数据是否可信 / 是否应修复、降权或过滤

P2 Mining & Coverage:
数据在做什么 / 哪些重复 / 哪些稀缺 / 哪些行为缺覆盖

P3 Exposure / Model Utility:
这些候选信号是否值得转化为更多或更少训练暴露，并最终改善 Policy
```

因此，P2 输出的 `rarity / duplicate / coverage gap / behavior diversity` 均属于 **Data-side Proxy / Candidate Data Value Signal**。

**禁止直接推导：**

```text
rare = valuable
high similarity = delete
coverage gap = upweight
```

这些结论必须经过人工语义 Review；若要上升为训练价值或 sampling / exposure 策略，需要进入 Project 3 或其他固定预算 Model-side 实验验证。

---


# 0.2 Development Roadmap + Design Gate Overview｜2026-09-14 CURRENT AUTHORITY

P2 后续不再按“把 7 个功能一次性全部开发完”的方式推进，而按 **Semantic Unit → Representation → Mining → Evaluation** 的依赖关系逐 Gate 关闭。

英文术语先统一：

- **Development Roadmap**：开发路线图，定义阶段顺序、上下游依赖与每阶段 Done Criteria；
- **Design Gate**：设计门禁，在进入下一阶段前必须由 Design Owner 明确拍板的方案问题；
- **SSOT (Single Source of Truth)**：单一事实源，发生冲突时具有最高工程解释权的文档；
- **Calibration Set**：标定集，用于阈值、规则、融合方案等开发期选择；
- **Evaluation Set**：评测集，冻结后只用于正式评价，禁止继续调参。

P2 的四层主架构固定为：

```text
Layer 0｜Data Foundation
RoboMimic Can/MH
        ↓
Layer 1｜Semantic Unit Construction
Episode → Segment → Keyframe / Action-State Summary
        ↓
Layer 2｜Semantic Representation
Segment → VLM Label + Visual Embedding + Action/State Feature
        ↓
Layer 3｜Dataset Mining
Retrieval → Dedup → Long-tail / Coverage
        ↓
Layer 4｜Validation & Model Connection
Human Evaluation → [OPTIONAL] P1 Failure Query → P3 Candidate Exposure Signal
```

核心依赖原则：

> **先定义“比较的基本单位是什么”，再定义“如何表示这个单位”，然后才能讨论相似、重复、稀缺和覆盖。**

因此 Segment 与 Representation 是 P2 的两个一级地基；任何 Daily Plan / Codex Plan 都不得绕过对应 Design Gate 直接冻结下游结果。

## 0.2.1 G0–G8 Design Gate 总表

| Gate | 英文名称 | 中文解释 | 必须由用户拍板的核心问题 | 当前状态 | 是否阻塞后续 |
|---|---|---|---|---|---|
| G0 | Source Foundation Gate | 数据源基础门禁 | Primary Dataset、Source Contract、字段语义与 split/provenance 继承关系 | **CLOSED** | 已关闭 |
| G1 | Segmentation Gate | 轨迹分段门禁 | motion signal、boundary、gripper event、min/max length、merge rule、人工验收 rubric | **OPEN / NEXT** | **阻塞正式 G2–G8** |
| G2 | Segment Summary Gate | 片段摘要门禁 | keyframe policy、max-motion 去重、Action/State Summary 最小字段 | PENDING_G1 | 阻塞 G3/G4 正式批量运行 |
| G3 | Label Taxonomy Gate | 标签体系门禁 | phase taxonomy、single/multi-field schema、VLM 输入、confidence 语义、人工 review | PENDING_G1/G2 | 阻塞正式 Auto-label 评测 |
| G4 | Representation Gate | 表征门禁 | frozen visual encoder、segment aggregation、Visual 与 Action/State 表征边界、normalization | PENDING_G2 | **阻塞 Retrieval / Dedup / Long-tail** |
| G5 | Retrieval Gate | 相似检索门禁 | “相似”的语义、Visual/Action 融合、phase filtering、relevance rubric | PENDING_G4 | 阻塞 G6/G7 正式定义 |
| G6 | Dedup Gate | 重复候选门禁 | duplicate candidate、threshold 标定、grouping/transitivity、输出只到 candidate/group | PENDING_G5 | 独立关闭 |
| G7 | Long-tail / Coverage Gate | 长尾与覆盖门禁 | rarity formula、kNN 口径、global vs within-phase、coverage 维度、人工分类 | PENDING_G5 | 独立关闭 |
| G8 | Evaluation Protocol Gate | 正式评测协议门禁 | Calibration/Evaluation 隔离、人工 GT rubric、metrics、冻结后禁止调参 | PENDING_G6/G7 | **阻塞正式结果与 Project Freeze** |

## 0.2.2 Design Gate 状态规则

Gate 只能处于以下状态之一：

```text
PENDING
→ OPEN_FOR_REVIEW
→ FROZEN / CLOSED
```

数值阈值若必须依赖真实数据分布，不应伪装成已冻结 Design，应标记：

```text
DATA_CALIBRATION_PENDING
```

例如 Dedup cosine threshold、kNN 的最终 `k`、motion threshold 可以在 Gate 中冻结“怎么标定”，但最终数值进入 Formal Config / Manifest，而不是写死进上层 Design。

## 0.2.3 当前 Gate 状态

```text
PROJECT_2_STATUS = ACTIVE_BOOTSTRAP
G0_SOURCE_FOUNDATION = CLOSED
G1_SEGMENTATION = OPEN_FOR_REVIEW
G2_SEGMENT_SUMMARY = PENDING_G1
G3_LABEL_TAXONOMY = PENDING_G1_G2
G4_REPRESENTATION = PENDING_G2
G5_RETRIEVAL = PENDING_G4
G6_DEDUP = PENDING_G5
G7_LONG_TAIL_COVERAGE = PENDING_G5
G8_EVALUATION_PROTOCOL = PENDING_G6_G7
OPTIONAL_P1_FAILURE_QUERY = NOT_A_BLOCKER
```

## 0.2.4 Evaluation Leakage Guard｜评测泄漏保护

P2 正式增加一条强约束：**用于选择规则/阈值的人工样本不得同时充当最终结果的唯一评测样本。**

```text
Human Calibration Set
用于：
- segmentation rule calibration
- dedup threshold calibration
- retrieval fusion / filtering decision
- rarity hyperparameter calibration

        ↓ 规则冻结

Human Evaluation Set
仅用于：
- Auto-label Accuracy / Confusion Matrix
- Retrieval Precision@K
- Duplicate Precision
- Long-tail / Coverage human review
```

具体样本数可以根据项目压缩程度调整，但“开发标定”和“最终评测”的职责必须隔离。若样本规模过小无法完全独立，应明确 limitation，不得把同集调参结果包装成独立测试性能。

## 0.2.5 P2 文档治理链

从本次更新起，P2 文档职责固定为：

```text
Portfolio / 三项目总控
        ↓
02_robot_demonstration_mining_autolabel_design.md
Research / Readable Design：解释项目为什么做、核心算法逻辑、面试理解
        ↓
Project_2_Engineering_Design_Master_v1_20260914.md
Engineering SSOT：工程契约、G0–G8 Gate、接口与状态
        ↓
Project2_Development_Roadmap_and_Design_Gate_Plan_v1_20260914.md
Roadmap / Execution Authority：阶段顺序、USER-GATE、Codex 可实施内容、Done Criteria
        ↓
Project_2/daily_plan/
每日 Web Learning Plan / Codex Execution Plan
        ↓
Formal Config / Manifest
        ↓
Code / Result / Audit
```

Daily Plan 不允许自行新增或改变核心 Design。实施中如果发现 Gate 需要改动：

```text
发现问题
→ Design Change Request
→ 用户 Review
→ 更新 Engineering Master / 对应 Readable Design
→ Gate Freeze
→ 再更新 Roadmap / Daily Plan / Code
```

---

# 0. 一句话理解项目 2

项目 1 回答：

> **哪些机器人数据有质量问题，应该怎么处理？**

项目 2 回答：

> **这些机器人示范分别在做什么、哪些相似、哪些重复、哪些稀缺；当 Policy 失败时，能否用这些能力定位训练数据中的覆盖不足、重复过多、行为缺失或标签问题？**

完整流程：

```text
Robot Demonstration Episodes
        ↓
Trajectory Segmentation
        ↓
抽取关键帧 + Action/State 摘要
        ↓
VLM Auto-Labeling
        ↓
Visual Embedding + Action Feature
        ↓
Similarity Retrieval
        ↓
Deduplication
        ↓
Long-tail / Corner Case Mining
        ↓
[OPTIONAL] Policy Failure Retrieval / Coverage Analysis
        ↓
人工 Review + Curation Manifest / Data Recommendation
```

---


# 0.1 AI 协作分级：项目 2 的本人投入边界

| 等级 | 定义 | 你的亲自下场程度 |
|---|---|---|
| **A：核心面试区** | Embedding、Retrieval、Long-tail、阈值与人工评测等高概率深挖内容 | **核心算法/定义、阈值或排序口径、代表性样本和 Failure Case 必须亲自做；AI 只能帮助补工程代码和加速实验。** |
| **B：协作区** | Keyframe、VLM 调用等原理要懂但工程实现区分度较低的环节 | **策略和输入输出由你定，AI 可以主写 SDK/API/批处理代码；你必须自己调过一轮并看过错误案例。** |
| **C：工程区** | IO、Manifest、缓存、目录、CLI、报告汇总等脚手架 | **允许 AI 基本包办，你负责检查正确性、可复现性和上下游接口。** |

项目 2 的总原则：**本人重点投入 Trajectory Segmentation、Label Taxonomy、Embedding/Cosine、Retrieval、Dedup Threshold、Long-tail / Coverage 定义与 50–100 个 Segment 的人工评测；Policy Failure Retrieval 在 P1 Query 可用时再接入，不作为主线 blocker。VLM API、Keyframe 文件处理、批量编码、Manifest 和 Pipeline 工程尽量交给 AI。**

# 1. 术语词典

| 术语 | 含义 |
|---|---|
| Demonstration | 一条人类/策略控制机器人完成任务的示范轨迹 |
| Segment | 从一整条 Episode 中切出来的一段连续行为 |
| Temporal Segmentation | 按时间把长轨迹分成多个行为片段 |
| Auto-Labeling | 使用规则或模型自动给数据生成标签 |
| VLM | Vision-Language Model，视觉语言模型 |
| Embedding | 把图像/文本等映射成固定长度向量，用于比较语义相似性 |
| Retrieval | 给定一个样本，找到最相似的一批样本 |
| Cosine Similarity | 余弦相似度，常用于比较两个 Embedding 的方向是否相似 |
| Deduplication | 去重，识别高度相似或重复数据 |
| Long-tail | 数量较少、低频但可能重要的数据模式 |
| Corner Case | 边界/罕见/特殊场景 |
| kNN | k-Nearest Neighbors，最近邻方法 |
| Precision@K | Top-K 结果中真正正确的比例 |
| Keyframe | 能代表一个 Segment 主要视觉状态的关键帧 |

---

# 2. 为什么需要第二个项目

Data Quality 解决：

```text
数据有没有坏？
轨迹是否异常？
```

但具身数据算法岗位还经常需要：

```text
数据里有什么行为？
数据覆盖了哪些场景？
哪些样本高度重复？
哪些行为很少见？
哪些数据应该补采？
```

这些问题更接近：

- Data Mining；
- Auto Annotation；
- Embedding Retrieval；
- Data Diversity；
- Long-tail / Corner Case Mining。

因此项目 2 不再重复做 Idle / Z-score / Jerk，而是补另一条能力轴。

---

# 3. 项目边界

## 3.1 必须完成

1. 从 Episode 生成 Segment；
2. 为 Segment 抽取关键帧；
3. 使用一个预训练 VLM 或可替换的 Labeler 生成行为标签；
4. 提取视觉 Embedding；
5. 提取简单 Action/State 统计特征；
6. 实现 Similarity Retrieval；
7. 实现 Deduplication；
8. 实现 Long-tail Ranking；
9. 人工标注一个小型评测集；
10. 输出统一 Mining Manifest 和评测报告；
11. **可选增强**：当 Project 1 已产生稳定代表性 Policy Failure 时，将其作为 Query，完成“Failure → 相似训练 Segment → Coverage / Duplicate / Long-tail / Label 问题”的小型回溯分析；该项不得阻塞 P2 主线冻结。

## 3.2 明确不做

- 不训练 VLM；
- 不训练 VLA；
- 不为 Project 2 重新训练第二套 Policy；
- 不做复杂 3D / Point Cloud；
- 不做 SLAM；
- 不做生产级向量数据库；
- 不做百万级数据工程；
- 不声称简单拼接向量就是“训练好的多模态 Embedding 模型”；
- 不追求语义切分 SOTA。

---

# 3.3 项目 2 的权威阅读来源：不是凭空设计 Mining Pipeline

> **面试掌握等级：A/B 混合** —— 不要求把这些项目都复现，但必须知道它们公开的数据表示、标注、质量标签和多本体对齐思路，避免 Project 2 变成“自己随便想了一个 Embedding + VLM Demo”。

## 岗位池强制覆盖

| 项目 | Project 2 重点 |
|---|---|
| **LeRobot** | Episode / Frame / Task / Video / Metadata，以及 Dataset Editing；作为数据组织与工具链参考，不再作为 P2 Primary Dataset |
| **Open X-Embodiment** | 不同 embodiment / action space / frequency 的统一表示问题 |
| **UMI** | Ego-centric / human demonstration、SLAM/pose tracking 质量门槛，以及人类示范如何转成训练数据 |

## 头部开源项目补充

| 项目 | 重点学习 | 是否直接复现 |
|---|---|---|
| **LingBot-VLA 2.0** | 大规模 robot + egocentric 数据过滤、统一 action/state representation、normalization | 阅读；不重复做其完整 pretraining pipeline |
| **Qwen-RobotManip** | representation / motion / behavior 三层 alignment；canonical state-action + mask；human-to-robot synthesis | 精读；用于理解 Cross-Embodiment 与多模态数据 |
| **RDT2** | UMI 大规模数据、Action Normalizer、Action Tokenizer reconstruction error / applicability check | 阅读；用于理解 action representation validity |
| **Galaxea Open-World / G0 / GalaxeaVLA** | fine-grained subtask language annotation、`quality_index` / `coarse_quality_index` | **重点阅读；直接影响 Label Taxonomy 与人工 Review 字段设计** |
| **GigaWorld / GigaDatasets** | LeRobot-style preprocessing、自动 caption / depth 数据准备、curation/evaluation/visualization 框架 | 补充阅读，不把框架本身当 QC 算法 |
| **Unitree LeRobot** | 失败 Episode 删除、Segment 裁剪、Replay | 阅读；理解人工 Curation 在真实机器人数据链路中的位置 |

## 本项目真正实现什么

这些权威来源用于约束设计，但 Project 2 不照搬某一个项目。

真正亲手实现的仍是：

```text
Trajectory Segmentation
→ Keyframe / Segment Summary
→ VLM Auto-Labeling
→ Embedding
→ Retrieval
→ Dedup Candidate
→ Long-tail / Corner Case Mining
→ Manual Evaluation
```

其中最需要你亲自掌握的是：

- Segment Boundary 为什么这样定义；
- Label Taxonomy 为什么这样定；
- Embedding / Cosine Similarity 表示什么；
- “相似”为什么不等于“应该删除”；
- Embedding Outlier 为什么不等于“高价值 Long-tail”；
- 人工 Ground Truth 与 Failure Analysis。

---

# 4. 输入数据

> **面试掌握等级：B（协作区）** —— P2 不再重新定义 generic schema。数据读取、字段语义、时间索引、图像规格、State / Action 语义、split grouping 等，直接复用 Project 1 当前冻结的 RoboMimic Source Contract；你仍必须能解释这些字段在 Can/MH 中真实代表什么。

## 4.1 Primary Dataset｜FROZEN

```text
PRIMARY_DATASET = RoboMimic Can/MH
TASK / WORLD = Can manipulation / robosuite
SOURCE_CONTRACT = Project 1 RoboMimic Unified Source Contract
```

选择 Can/MH 的原因是：P2 研究的是 demonstration 的行为语义、相似性、重复度与覆盖关系，而 Can/MH 与 Project 1 的 M07 demonstration-quality population 对齐，可以直接复用已经审计过的数据语义、episode 结构和 human demonstration 理解，避免再开新的 Dataset Audit。

## 4.2 P2 使用的逻辑输入

P2 内部仍需要以下**逻辑字段**：

```text
source_episode_id
frame / timestep index
timestamp or frozen temporal index
canonical RGB image
state / proprio fields allowed by Source Contract
action
task / task identity
```

这些是 P2 算法消费的逻辑输入，不代表重新建立一套独立 schema。字段命名、shape、单位、camera、128×128 图像规格、action semantics 等一律继承 Project 1 Source Contract。

## 4.3 Source Boundary

第一版不重新下载 LeRobot Dev Dataset，也不做多数据集泛化实验。LeRobot / Open X / UMI 等继续作为方法与数据组织参考。若未来需要第二数据源验证，必须作为 Extension 单独立项，不得阻塞 P2 MVP。

---

# 5. Step 1：Trajectory Segmentation

> **面试掌握等级：A（核心面试区）** —— Motion Magnitude、边界规则、最短/最长 Segment 和典型切错案例必须由你亲自设计、实现第一版并人工检查至少 10 个 Episode。


## 5.1 这是什么

一个 Episode 可能有 200~500 帧。

直接给整条轨迹一个标签：

```text
pick_place
```

信息太粗。

真实过程可能是：

```text
Approach
→ Grasp
→ Lift
→ Transport
→ Place
→ Retract
```

因此先把 Episode 切成多个连续 Segment。

这里必须区分两个问题：

```text
G1 Segmentation / Boundary Proposal
= 哪里应该切一刀？
= 输出未命名 Segment

G3 Semantic Labeling
= 这一段到底是什么？
= 输出 approach / grasp / lift / transport / place / retract ...
```

所以 G1 本身不要求仅凭 EEF 就判断“正在接近 Can”或“正在撤离”。它只负责找到运动/交互状态发生明显变化的位置。真正需要的 object-centric semantics（物体关系语义）在 G3 通过 RGB/Keyframes + VLM/Labeler 获得。

## 5.2 第一版不要做复杂模型

使用可解释的 Motion / Interaction Boundary Baseline。首版 Formal Signal Set 冻结为三层：

```text
Layer 1 — Robot Kinematics（机器人运动学）
EEF position / orientation / derived velocity
→ 机器人末端实际怎么运动

Layer 2 — Interaction（交互）
gripper state / transition
→ 是否发生抓取/释放相关的夹爪状态变化

Layer 3 — Command（控制指令）
source-native recorded action / action change
→ 控制器想让机器人怎么动，作为辅助证据
```

语义原则：`realized motion > commanded motion`，gripper interaction event 不与普通 motion magnitude 强行混成一个不可解释的 scalar。

候选流程：

1. 从 EEF State 计算 realized translation / rotation / velocity change；
2. 识别 gripper state / transition；
3. 计算 recorded Action 的 command-change evidence；
4. 根据运动开始/停止、显著变化或交互事件生成候选边界；
5. 设置最短 Segment 长度，避免碎片；
6. 设置最长 Segment 长度，必要时再切分。

示意：

```text
Frame
0────────50────────100────────150────────200

Motion
____████████____███████_____████████____

Segment
    S1           S2          S3
```


### G1-B Boundary Semantics｜FROZEN

首版不把 Translation / Rotation / Gripper / Action 等价处理，而按证据强度分层：

```text
Hard Boundary Candidate
- 持续的 gripper open→close / close→open

Motion Boundary Candidate
- 持续 moving→stationary
- 持续 stationary→moving
- 大幅且持续的主要运动方向变化

Supporting Evidence
- EEF rotation regime change
- recorded action / command change
```

这里的 **Rotation（旋转）** 专指 `robot0_eef_quat` 描述的 EEF 整体姿态变化。Panda 的 7 个关节可能共同产生该姿态变化，因此 P2 不用“某个 joint 是否转动”直接决定 Segment。当前 PickPlaceCan 中，Rotation 常出现在接近物体时的腕部姿态微调、抓取前对齐、抓起后重新定向、运输/放置前的姿态调整；其中大量属于同一行为内部调整，所以 **Rotation alone 不切段**。

当前 Can/MH v1 的优先级冻结为：

```text
Gripper transition
> EEF translation / speed state
> EEF main-direction change
> EEF rotation
> Action change
```

所有边界事件都要求 **Persistence（持续性）** / **Debounce（去抖）**，避免单帧抖动、短 pause、方向瞬时翻转或 action spike 造成过切。具体速度阈值、角度阈值、持续帧数均留到真实 Can/MH 数据上标定。

## 5.3 Simulator Object GT 的角色｜FROZEN

当前 Can/MH / simulator 侧可以保留 `Can_pos`、`Can_quat`、`Can_to_robot0_eef_*`、object-state 等特权参考信息，但它们**不进入 Formal G1 Boundary Proposal**。

原因不是这些信息没用，而是它们属于 simulator 直接给出的上帝视角真值；真实机器人数据通常需要通过视觉/感知才能获得等价信息。

它们在 P2 中承担 **Oracle / Evaluation Reference（理想参考 / 评测答案）**：

```text
Formal G1 boundary
← compare →
真实 object interaction transition

G3 VLM semantic label
← compare →
simulator object relation / motion reference
```

用途包括：

- 判断预测 boundary 是否接近真实抓取/释放等物理 transition；
- 判断 G3 的 grasp/place 等标签是否与 object motion 一致；
- 错误分析时区分“切错了”还是“视觉语义标错了”。

注意：这里不是利用 object GT 给 Formal Segmenter 偷看答案。

## 5.4 输出

```text
episode_id
segment_id
start_frame
end_frame
duration
motion_score
```

## 5.5 验收

人工看 10 个 Episode，确认：

- 没有大量 1~2 帧碎片；
- 主要运动阶段大体被分开；
- 切分结果可以用于后续 Labeling。

不要求达到“完美语义分段”。

---

# 6. Step 2：Keyframe 与 Segment Summary

> **面试掌握等级：B（协作区）** —— first/middle/last/max-motion 的选帧策略和信息损失你要能解释，抽帧、统计、文件保存等代码可以让 AI 主写。


## 6.1 为什么不能把全部视频帧都送给模型

成本高、处理慢，而且 7 天项目没有必要。

每个 Segment 先抽：

```text
first frame
middle frame
last frame
```

如果 Segment 较长，可以增加最大运动变化处的 1 帧。

## 6.2 同时生成 Action / State Summary

例如：

```text
duration
mean_action_delta
max_action_delta
mean_state_delta
max_state_delta
gripper_start
gripper_end
```

这些数字可以帮助判断：

- 是否抓取；
- 是否几乎静止；
- 是否存在快速运动。

## 6.3 输出

```text
segment_id
keyframe_paths
action_summary
state_summary
task
```

---

# 7. Step 3：VLM Auto-Labeling

> **面试掌握等级：B（协作区，Label Taxonomy 按 A 级掌握）** —— VLM API/重试/JSON 解析可交给 AI，但标签体系、Prompt 输入、结构化输出、confidence 含义和 hallucination/error case 必须由你亲自调试与复核。


## 7.1 这是什么

给预训练 VLM 几张关键帧、任务文本，并按 G2 冻结口径提供必要的 robot/action summary，让模型输出一个结构化标签。

G3 的关键任务不是恢复毫米级 `Can_pos`，而是从视觉中恢复足以完成行为命名的 **Object Relation（物体关系）**，例如：

```text
gripper approaching can
gripper around can
can moving with gripper
can resting after release
gripper moving away from can
```

再结合 gripper / EEF / action summary，将 G1 的 unlabeled Segment 映射到受控物理语义。

例如输入：

```text
Task: pick up the red cube and place it in the box
Frames: start / middle / end
```

目标输出：

```json
{
  "motion_phase": "grasp",
  "object": "red cube",
  "interaction": "contact",
  "success_evidence": "uncertain",
  "confidence": 0.82
}
```

## 7.2 标签体系必须小

第一版固定几个行为阶段：

```text
approach
grasp
lift
transport
place
retract
idle
recovery
other
```

不要让 VLM 自由生成几十种标签，否则后面无法统计。

## 7.3 Labeler 接口

```python
label = labeler.predict(segment)
```

VLM 只是实现之一。

这样后续可以替换模型，而不用改整个 Pipeline。

## 7.4 自动标注输出

```text
segment_id
motion_phase
object
interaction
confidence
label_source
```

其中：

```text
label_source = vlm_auto
```

人工校正后：

```text
label_source = manual_review
```

---

# 8. Step 4：Embedding Representation

> **面试掌握等级：A（核心面试区）** —— 你必须亲自把一批真实图像编码成向量，理解维度、归一化、segment 聚合和视觉/Action 表征边界，并能解释为什么这种 representation 合理或不合理。


## 8.1 Embedding 是什么

一张图片经过预训练视觉编码器以后，得到一个向量：

```text
image
↓
encoder
↓
[0.13, -0.44, 0.08, ...]
```

相似场景的向量通常更接近。

## 8.2 本项目使用两类 Representation

### A. Visual Embedding

对关键帧提取预训练视觉 Embedding，然后对 Segment 聚合：

```text
start embedding
middle embedding
end embedding
↓
mean / concatenate summary
↓
segment_visual_embedding
```

### B. Action Feature

不是训练 Action Encoder，而是生成简单、可解释的特征：

```text
action mean
action std
motion magnitude
gripper change
duration
```

## 8.3 不做虚假包装

项目表述应写：

> Visual Embedding + Action/State Feature-based Retrieval

不要写成：

> “训练了一个多模态 Embedding Foundation Model”。

---

# 9. Step 5：Similarity Retrieval

> **面试掌握等级：A（核心面试区）** —— Cosine Similarity 建议你自己实现一次并亲自检查 Top-K 检索结果，能回答为什么用 cosine、什么时候会失效以及如何评价 Retrieval。


## 9.1 目标

给定 Segment A：

```text
找到最相似的 Top-10 / Top-20 Segment
```

用途：

- 找相似行为；
- 找相似 Failure Case；
- 找重复数据；
- 辅助人工 Review。

## 9.2 第一版实现

视觉侧：

```text
Cosine Similarity
```

Action 侧：

```text
归一化后的 feature distance
```

可先分别检索，再做简单排序融合。

不要求第一版上 FAISS；数据量小可以直接 NumPy / sklearn。

## 9.3 输出

```text
query_segment_id
neighbor_segment_id
visual_similarity
action_similarity
rank
```

---

# 10. Step 6：Deduplication

> **面试掌握等级：A（核心面试区）** —— 去重阈值、candidate 定义和“相似不等于该删除”的判断必须由你根据真实样本决定，批量 pair 计算和导出代码可以交给 AI。


## 10.1 问题

如果 1000 个 Segment 中：

```text
400 个几乎完全一样的 approach
```

全部保留可能导致训练分布被重复动作主导。

## 10.2 第一版规则

候选重复要求至少满足：

```text
高 Visual Similarity
+
相近 Motion Phase
```

可选再加：

```text
相近 Action Feature
```

输出 duplicate group：

```text
group_001
├── segment_020
├── segment_103
└── segment_401
```

## 10.3 注意

相似 ≠ 一定应该删除。

同一行为在不同光照、物体位置、机器人姿态下可能仍有训练价值。

因此第一版输出：

```text
duplicate_candidate
```

而不是自动 `delete=True`。

---

# 11. Step 7：Long-tail / Corner Case Mining

> **面试掌握等级：A（核心面试区）** —— rarity score 的构成、kNN 邻域、label frequency 与高价值/坏数据的区别必须亲自理解，并亲自分类 Top long-tail 样本。


## 11.1 Long-tail 不是异常

某个 Segment 在 Embedding 空间很孤立，可能是：

1. 真正异常数据；
2. 新场景；
3. 少见动作；
4. Failure Recovery；
5. 标注错误。

因此只能先 Rank，再人工 Review。

## 11.2 第一版 Long-tail Score

使用最近邻密度思路：

```text
每个 Segment
↓
找到 k 个最近邻
↓
计算平均邻居距离
↓
距离越大 → 越稀有
```

再结合：

```text
motion_phase frequency
```

输出：

```text
segment_id
rarity_score
nearest_neighbor_distance
label_frequency
review_reason
```

## 11.3 人工分类

Top-20 至少人工分成：

```text
true rare behavior
failure/recovery
bad data
label error
normal but visually different
```

这一步非常重要，因为 Data Value 不能仅靠距离决定。**Rarity / Embedding Outlier / Label Frequency 都只是 Data-side Proxy，不等于对 Policy 的真实训练价值。** 能否称为“高价值”，优先看它是否与模型 Failure、能力覆盖或训练后性能变化形成证据链。

---

# 12. 小型 Ground Truth 与评测

> **面试掌握等级：A（核心面试区）** —— 约 100 个 Segment 的人工标签、Retrieval/Dedup/Long-tail 人审和 Failure Analysis 必须由你本人完成，这是证明项目不是“AI 自动跑出来”的最关键证据。


项目时间只有 7 天，不追求大规模标注。

人工目标选取 **50–100 个 Segment** 作为 Evaluation Set；时间允许优先接近 100，压缩执行时最低不少于 50，并保证 Retrieval / Dedup / Long-tail 的代表性 case 有人工审阅。

## 12.1 Auto Label

人工给 Ground Truth `motion_phase`。

指标：

```text
Label Accuracy
Confusion Matrix
```

## 12.2 Retrieval

随机选若干 Query，人审 Top-K 是否属于相同/相关行为。

指标：

```text
Retrieval Precision@5
Retrieval Precision@10
```

## 12.3 Dedup

人工检查 Top duplicate candidates。

指标：

```text
Duplicate Precision@20
```

## 12.4 Long-tail

人工检查 rarity Top-20。

指标：

```text
Useful Long-tail Precision@20
```

这里“Useful”至少包含：

```text
rare behavior
failure / recovery
valuable corner case
```

---

# 13. 与项目 1 的连接

> **面试掌握等级：A/B 混合** —— 除了能解释 Quality、Value、Mining 三者如何互补，还必须能说明：数据侧的 rarity / similarity 只是 proxy，真正靠近模型的数据算法需要从 Policy Failure 回到训练数据，形成可审计的证据链；Manifest join/批处理代码可以让 AI 完成，但 Failure Query 的选择、Top-K 人审和结论边界必须本人判断。

## 13.1 Project 1 → Project 2：Failure Case 作为 OPTIONAL Retrieval Query

Project 1 的代表性 Failure Case 是 P2 的**可选模型驱动 Query**，不是 P2 前半程前置依赖。P2 必须先独立跑通 Episode → Segment → Embedding → Retrieval；当 P1 已产生可用 Failure Case 后，再把它接入同一 Retrieval 表示空间：

```text
Policy Failure Episode / Segment
        ↓
映射到 Project 2 Segment 表示
        ↓
Top-K Similar Training Segments
        ↓
人工比较 success / failure / motion_phase / duplicate / rarity / QC risk
        ↓
判断可能的数据侧问题
```

至少检查四类假设：

- **Coverage Gap**：失败行为附近几乎没有相似训练样本；
- **Duplicate Dominance**：相似样本很多，但高度重复、有效多样性低；
- **Missing Behavior / Recovery**：缺少某个关键 phase、recovery 或边界行为；
- **Label / Quality Issue**：相似样本存在，但标签、同步或 QC 风险明显。

输出只允许写成“evidence / hypothesis”，除非有额外对照实验，不直接声称因果。

若 P1 Failure Query 在 P2 冻结前可用，则输出 `failure_retrieval_case_study.md`，包含 Query、Top-K 样本、人工判断、数据侧假设、证据边界和下一轮数据建议；若暂不可用，则记录为 `OPTIONAL_PENDING`，不得因此延后 Segmentation / Retrieval / Dedup / Coverage 主线。


> **面试掌握等级：B（协作区）** —— 你要能解释 Quality、Value、Mining 三者如何互补以及为什么不能把所有离群样本都当异常；具体 Manifest join/数据拼接可以让 AI 完成。


项目 1 的 QC Result：

```text
segment/frame 是否有质量问题
```

项目 2 的 Mining Result：

```text
segment 做什么、是否重复、是否稀缺
```

合并以后可以形成：

```text
High QC Risk + Low Value
→ Filter / Review

Low QC Risk + High Duplicate
→ Downsample

Low QC Risk + High Rarity
→ Preserve / Review Candidate；只有出现模型 Failure / Coverage 等额外证据时才考虑 Upweight

High Motion Abnormal + Recovery Label
→ Hard Case Review，不自动删除
```

这就是更完整的：

> **Quality + Content/Coverage Signals + Model Failure Feedback**

其中 P2 的信号是候选数据价值证据，不直接宣称为真实训练价值。

---

# 14. Unified Mining Manifest

> **面试掌握等级：C（工程区）** —— Manifest 字段由你确认够支撑分析即可，schema class、CSV/Parquet 写出和字段拼装可以让 AI 主导。


最终每个 Segment 形成一行：

```text
dataset_id
episode_id
segment_id
start_frame
end_frame

task
motion_phase
auto_label_confidence

visual_embedding_id
action_feature_id

duplicate_group_id
duplicate_score
rarity_score

qc_risk
policy_failure_query_flag
nearest_failure_query_id
coverage_evidence
recommended_action
review_reason
```

文件：

```text
outputs/segment_mining_manifest.csv
```

---

# 15. 项目代码结构

> **面试掌握等级：C（工程区）** —— 目录、config、CLI、批处理、缓存、日志和 utils 可以让 AI 包办，你只需要知道模块职责和能否复现。


```text
robot-demo-mining/
│
├── README.md
├── configs/
│   ├── segmentation.yaml
│   ├── labeling.yaml
│   └── mining.yaml
│
├── src/
│   ├── adapters/
│   ├── segmentation/
│   │   └── motion_boundary.py
│   ├── labeling/
│   │   ├── base_labeler.py
│   │   └── vlm_labeler.py
│   ├── features/
│   │   ├── keyframes.py
│   │   ├── visual_embedding.py
│   │   └── action_features.py
│   ├── retrieval/
│   │   └── similarity.py
│   ├── mining/
│   │   ├── dedup.py
│   │   └── long_tail.py
│   └── evaluation/
│       └── metrics.py
│
├── scripts/
│   ├── build_segments.py
│   ├── auto_label_segments.py
│   ├── build_embeddings.py
│   ├── retrieve_similar.py
│   ├── mine_duplicates.py
│   ├── mine_long_tail.py
│   └── evaluate_mining.py
│
└── outputs/
    ├── segments.csv
    ├── auto_labels.csv
    ├── retrieval_results.csv
    ├── duplicate_groups.csv
    ├── long_tail_rank.csv
    ├── segment_mining_manifest.csv
    └── evaluation_summary.csv
```

---

# 16. 一次完整运行长什么样

> **面试掌握等级：B（协作区）** —— Pipeline 串联可以由 AI 编排，但你必须亲自完成至少一次端到端运行，并能从任一 Top-K 结果追溯回原始 Segment 和关键帧。


```text
1. build_segments.py
   ↓
segments.csv

2. auto_label_segments.py
   ↓
auto_labels.csv

3. build_embeddings.py
   ↓
visual embeddings + action features

4. retrieve_similar.py
   ↓
retrieval_results.csv

5. mine_duplicates.py
   ↓
duplicate_groups.csv

6. mine_long_tail.py
   ↓
long_tail_rank.csv

7. evaluate_mining.py
   ↓
evaluation_summary.csv

8. [OPTIONAL] analyze_failure_retrieval.py
   ↓
failure_retrieval_case_study.md
```

---

# 16.1 实现阶段 A/B/C 总表

| 实现阶段 | 等级 | 你本人必须做到什么 |
|---|---|---|
| 输入数据确认 | **B** | 亲自核对字段语义与时间关系，读取/Adapter 代码可复用或 AI 生成。 |
| Step 1 Trajectory Segmentation | **A** | 亲自设计并实现第一版边界逻辑，人工检查至少 10 个 Episode 的切分好坏。 |
| Step 2 Keyframe & Summary | **B** | 亲自决定选帧策略并理解信息损失，抽帧和统计代码可让 AI 主写。 |
| Step 3 VLM Auto-Labeling | **B** | 亲自设计 taxonomy/Prompt 并复核错误样本，API 与批处理工程可交给 AI。 |
| Step 4 Embedding Representation | **A** | 亲自跑 embedding、看向量与归一化，并解释视觉/Action 表征如何构成。 |
| Step 5 Similarity Retrieval | **A** | 自己实现一次 cosine 并亲自检查 Top-K 检索及失败案例。 |
| Step 6 Deduplication | **A** | 亲自标定阈值、看重复候选，并解释为什么相似样本不一定删除。 |
| Step 7 Long-tail Mining | **A** | 亲自定义/理解 rarity、检查 Top long-tail，并区分“稀有”与“真正高训练价值”；不得仅凭距离做价值结论。 |
| Ground Truth & Evaluation | **A** | 约 100 个 Segment 的人工评测和 Failure Analysis 必须本人完成。 |
| Policy Failure Retrieval / Coverage | **A / Optional** | P1 Failure Query 可用时亲自检查相似训练样本、覆盖缺口与可能的数据侧解释；不可用时不得阻塞 P2 主线。 |
| Unified Mining Manifest | **C** | AI 可主写，自己验收字段能支撑检索、去重、长尾和后续 Curation。 |
| End-to-End Pipeline | **B** | AI 可串联工程，但你必须亲自跑通并会追溯每个结果的来源。 |

# 17. 最低成功标准

旧 `9/16 Freeze` 已废止。P2 从 2026-09-14 起压缩执行，具体 Freeze 日由当前 `Project_2/daily_plan/` 控制，但不得以“等待 P1 Failure Query”为理由顺延。

主线最低交付：

```text
✓ RoboMimic Can/MH → Segment
✓ Keyframe
✓ VLM Auto Label / structured label output
✓ Visual Embedding
✓ Action/State Feature
✓ Top-K Retrieval
✓ Duplicate Candidate Mining
✓ Long-tail / Coverage Ranking
✓ 50–100 Segment 小型人工评测集
✓ evaluation_summary.csv
✓ README

OPTIONAL：
○ ≥1 组 Project 1 Policy Failure Retrieval / Coverage Case Study
```

以下任何一项没做都不应该阻塞项目冻结：

```text
FAISS
Vector DB
3D Embedding
VLA Fine-tuning
复杂时序 Transformer Segmentation
大规模自动标注服务
```

---

# 18. 最终面试叙事

> 在 Data Quality 项目之外，我进一步针对机器人示范数据的语义组织与模型失败回溯问题构建了一个轻量数据挖掘流程：先基于 Action/State 运动变化将长 Episode 切成行为 Segment，再使用关键帧和预训练 VLM 生成受控行为标签；随后提取视觉 Embedding 与可解释 Action/State 特征，实现相似示范检索、重复候选识别和基于局部密度的 Long-tail Ranking。通过约 100 个 Segment 的人工评测集验证 Auto-Label、Retrieval、Dedup 与 Long-tail 指标，并把 Project 1 的代表性 Policy Failure 作为 Query 回查训练集中相似成功/失败样本与覆盖情况。这样既能区分低质量、冗余、长尾和 Hard Case，也避免把“稀缺”直接包装成“高训练价值”，最终形成 Data→Model→Failure→Data 的闭环证据。

---

# 19. 三项目中的能力分工与 Project 3 接口

| 能力 | Project 1 | Project 2 | Project 3 |
|---|---:|---:|---:|
| Robot Dataset / Semantics | 主 | 复用 | 复用 |
| Data Quality / Anomaly | 主 | 辅 | 作为可选信号 |
| Filter / Repair / QC Curation | 主 | 辅 | - |
| Benchmark B-QC / Fixed Policy Harness | 主 | 复用结果 | **复用 Harness** |
| Multimodal Auto-Label | - | 主 | 使用标签 / group |
| Embedding / Retrieval | - | 主 | 使用候选 group signal |
| Dedup / Effective Diversity | 基础 | 主 | 用于 Replay / Exposure Guardrail |
| Long-tail / Coverage | 人审 | 主 | **候选 Exposure Signal** |
| Sampling / Data Mix / Exposure | - | 只给数据侧证据 | **主** |
| Actual Exposure Audit | 公平性审计 | - | **主** |
| Data→Model→Failure→Data | Quality 闭环 | Failure Retrieval / Coverage | Exposure → Model Utility 闭环 |

三个项目关系：

```text
Project 1：Quality / Curation
        ↓ 提供 Fixed Model / Fixed Budget / Evaluation Harness
Project 2：Semantic Mining / Retrieval / Coverage
        ↓ 提供 label / duplicate / rarity / coverage candidate signals
Project 3：Data Mix / Exposure Optimization
        ↓ 验证不同 exposure strategy 是否改变 Policy Utility
```

注意：

> Project 2 的 rarity / coverage / duplicate 只是 Data-side evidence，不自动等于 Project 3 的 sampling weight。进入 Project 3 前必须经过 Target Exposure、Replay 上限与人工 Guardrail。