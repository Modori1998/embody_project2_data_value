# P2 Flora–G3 Adapter v0.1｜原生标注保留、时间对齐与结构化事件打标方案

> 日期：2026-10-28  
> 文档状态：`DESIGN_PROPOSAL / IMPLEMENTATION_NOT_STARTED`（设计提案；不表示已实现、通过评测或冻结正式协议）  
> 目标仓库：`Modori1998/embody_project2_data_value`  
> 审阅基线：远端 `main` @ `d561f98e9be6c6e7e4652e07e7839df40326a8d2`（提交前读取）；实际提交版本以 GitHub Commit 为准。  
> 变更范围：**新增独立方案 Markdown**。不改现有 G1/M2、G3 v0.2 Schema/Prompt/Validator、历史 Run、模型和数据。  
> Owner 的当前方向：保留完整 Flora 原生 JSON，复用 P2 G3 v0.2 的八个模型输出字段，先用现有 15 条 Demo 验证接口和数据对齐；负例不足暂不阻塞设计。

## 0. 一页结论

**不需要重新发明结构化 JSON，也不需要现在改 Flora 模型。**

- Flora 原生标注提供 `Episode → 时间段 → Caption`，其中 Caption 是自然语言动作描述/意图，不是物理事件真值。
- P2 已有 G3 v0.2 结构化协议，提供 `motion_phase / object_relation / gripper_state / event_assessment / events / evidence_frame_indices / evidence_quality / observation_note`。
- 新增 **Flora–G3 Adapter（适配器）**：通过可信 Episode、时间、源帧映射将两种资产关联；**G3 的正式 target 仍是冻结的 G1 Segment**，不能拿 Flora 的时间段直接改写 G1 边界。
- Flora 片段可用作“候选动作/上下文线索”，G3 模型的具体事件必须由目标片段内可追溯的视觉证据支持。
- QC（Quality Control，数据质量控制）只消费有版本、有校验状态的候选标签；`VALID` 不是视觉真值，`grasp` 不是成功抓取；不自动产生训练数据 `KEEP/FILTER/DOWNWEIGHT` 决策。

## 1. 本次已获得的证据及不能外推的结论

当前用户导出的 `flora_native_all15_export.zip` 包含 15 个 Episode 的原生 JSON 和汇总 CSV。抽查与汇总结果：

- 15/15 Episode 有原生 JSON，31 个 Flora Segment，31/31 Caption 的 `status=complete`。
- 14 个 Episode 各有 2 个 Flora Segment；`demo_71` 有 3 个。
- `demo_2` 的前两个分段为 `[0.00, 3.75)`、`[3.75, 5.65)` 秒，文字分别表达“拿起红色杯子”和“放到架子中间”。
- 观察到跨段物体命名/描述口径变化、左右手变化等风险；需要视觉核验，不能从文字自动推出对象跟踪正确或任务成功。
- 上述是**工程完整性证据**，不是 G3 事件准确率、Flora 时间边界真值、失败检测能力或 QC 收益证据。

本次讨论暂不要求寻找新的负例；但**不得把“负例缺失”写成“视频里没有负例”**。历史 G3F 部分 G1 片段的人为参考事件集合为空，可作为开发诊断参考；这些标签**不能未经时间映射直接赋给 Flora 整段**。

## 2. 权威关系与冻结边界

### 2.1 必须继承，不得静默改动

1. `0-doc/Project2_MVP_SSOT_20261008.md`：P2 的 G0 数据源、Clean RGB、G1/M2 和 G3 语义职责边界。
2. `0-doc/10-design-review/P2_G3_Structured_JSON_and_Evidence_Contract_Owner_Freeze_20261013.md`：单个 JSON、有限枚举、帧级引用、调用方所有的可信身份、验证器不篡改原输出。
3. `0-doc/10-design-review/P2_G3_Taxonomy_v0_2_Design_Owner_Freeze_20261013.md`：九类 phase、object_relation、gripper_state、三类实质事件及不确定性语义。
4. `0-doc/10-design-review/P2_G3_Semantic_JSON_v0_2_Output_Design_Owner_Freeze_20261013.md`：八个 model-owned 字段及 `event_assessment/events` 的基数关系。
5. 现有实现：`src/project2_g3/semantic_schema.py`、`semantic_validation.py`、`phase_event_qc.py`。优先复用 v0.2 接口和校验，禁止建立一套同名但不同语义的旁路 Schema。

**特别约束**：当前正式 G3 的 target 是已有 **G1 Segment（已冻结轨迹片段）**。Flora 的片段是独立的 Proposal（候选时间窗），不重新命名、不合并、不删除现有 G1 Segment，也不改写历史 G3 实验的目标范围、帧索引或真值。

### 2.2 需要新增、但尚未冻结的部分

本提案新增 `P2_FLORA_G3_ADAPTER_V0_1_PROPOSED` 关联记录、跨时间基准映射报告、可选 Caption 上下文输入策略和 Pilot 流程。它们是 Adapter 设计，不等同于提升 `G3_FORMAL_TAXONOMY_V1` 的冻结状态。

## 3. 推荐的数据架构

```text
RoboMimic Can/MH 原始状态、Clean RGB、G1/M2 （已有权威源）
          │
          ├── Frozen G1 Segment / Frame Evidence Manifest
          │                 │
          │                 ▼
          │          G3 v0.2 Labeler（Qwen）
          │                 │
          │                 ▼
          │          原始响应 + Validator + 人工参考
          │                 │
          └─────────────────┴─────────────────┐
                                              │
Flora 官方 TempSeg + Captioner                 │
          │                                   │
          ▼                                   │
Flora Native JSON（不可变）                     │
          │                                   │
          └── Flora–G3 Adapter：身份与时间映射 ────┘
                          │
                          ▼
                事件索引 / Review Queue
                          │
                          ▼
          Retrieval / Coverage / QC 候选分析
```

物理保存原则：

- **原生层**：`flora_native/<episode_id>.json` 原封不动，保留原文件 SHA256；不要为适配器删字段或重写原生 JSON。
- **关联层**：`flora_g1_links.jsonl`；一条记录表示一个 Flora Segment 对一个 G1 Segment 的关系，允许 1:N、N:1、部分重叠和未映射。
- **推理层**：`g3_predictions.jsonl`；model-owned 八字段独立保存，配套 raw response、Prompt/模型和 Evidence Manifest。
- **复核层**：`validation_findings.jsonl`、`human_reference.csv`（可为空或缺失）、`review_queue.csv`。不能把人工结论写回模型原始预测。
- **报告层**：`alignment_audit.csv`、`pilot_summary.md`。正式的用户可查询视图通过 join/索引生成，不作为原始 SSOT。

## 4. 字段契约

### 4.1 Flora：全部原样保留

原生 JSON 的 Episode 顶层字段为：

| 原字段 | 职责 | 适配层处理 |
|---|---|---|
| `schema_version` | 原生数据协议版本 | 原样保留 |
| `duration_s` | 视频时长 | 作为时间校验依据 |
| `segments` | 片段数组 | 每段建立稳定的调用方 link ID |
| `elapsed_s` | 本次推理耗时 | 原样保留，不当质量分数 |
| `source_clock` | 时间零点/时间基准 | 对齐必须读取 |
| `camera_roles` | 输入相机角色 | 用于视角映射检查 |
| `profile` | Flora 运行 profile | 保存 `YAM`；它不是 RoboMimic 机器人身份真值 |
| `model_revisions` | TempSeg/Captioner/基座模型版本 | 原样保留，用于复现 |
| `input_sha256` | Flora 视频输入哈希 | 绑定 MP4 来源；不能直接等同 Clean RGB 来源哈希 |
| `pipeline` | Temporal Windows、帧计划、Caption 输入/Prompt 审计 | **全部保留**，用于定位模型到底看了哪些帧 |

`segments[i]` 中的 `start_s`、`end_s`、`caption`、`status`、`segmentation_provenance` 全部原样保留。`pipeline.caption_inputs` 中的 TARGET/BEFORE/AFTER、帧索引、Prompt 哈希如存在，一律保留原始记录；不得把“Captioner 看过邻居帧”理解为“邻居事件发生于目标片段”。

若未来 Flora 原生版本新增字段，**原始层应无损保留未知字段**；适配器只从已知字段提取索引，遇到不兼容的版本显式报警，禁止静默丢弃。

### 4.2 P2 G3：复用八个模型输出字段，不新建同义字段

| G3 v0.2 字段 | 含义与边界 |
|---|---|
| `motion_phase` | 一个冻结 G1 目标片段的主要可见动作阶段；取 approach/grasp/lift/transport/place/retract/idle/other/uncertain |
| `object_relation` | 物体与夹爪的可见关系枚举数组；不直接等于事件真值 |
| `gripper_state` | **实际供模型查看的最后一个有效 target 帧**上的夹爪开合状态，不等于夹持成功 |
| `event_assessment` | `event_visible` / `no_event_visible` / `insufficient_evidence`，区分“未看见”与“无法判断” |
| `events` | 实质事件 `grasp_attempt`、`release_attempt`、`object_motion`；每项含 `event_type`、`event_outcome`、`evidence_frame_indices` |
| `evidence_frame_indices` | 支持主要 `motion_phase` 的可信目标帧引用；与事件项内的帧引用分开 |
| `evidence_quality` | 对**主要动作阶段**证据是否充分的判断：sufficient/partial/insufficient；不是模型正确率 |
| `observation_note` | 简短、基于可见证据的说明；是可审计的模型陈述，不是 Ground Truth |

冻结的逻辑：`event_visible` 对应非空且有目标帧证据的 `events`；`no_event_visible` 与 `insufficient_evidence` 必须对应 `events=[]`。`grasp` 不蕴含抓取成功，`closed` 不蕴含持有物体；`object_motion` 的 event_outcome 不得凭动作意图制造任务成功结论。

### 4.3 可信调用方元数据：与模型输出隔离

关联记录至少包含：

- `source_dataset`、`source_episode_id`，由 P2 已审计源清单给定，不从 Caption 猜。
- `flora_native_json_path`、`flora_native_json_sha256`、`flora_input_video_sha256`。
- `flora_segment_index`（明确零基索引）、`flora_segment_link_id`（由调用方生成，不让模型写）、`flora_start_s`、`flora_end_s`。
- `g1_segment_id`、`g1_interval_frames_inclusive`、`g1_segmentation_version`、`mapping_status`、`overlap_interval`、`alignment_manifest_sha256`。
- `model_revision`、`prompt_sha256`、`evidence_pack_sha256`、`run_id`、`input_variant`，由调用方注入。
- 若只有初步视频文件名匹配、未完成源 ID/时钟核验，`mapping_status` 必须保持 `UNVERIFIED`，不得伪造 G1 ID。

### 4.4 示例——仅展示 Adapter 包装形状，不是推理结果

```json
{
  "adapter_schema_version": "P2_FLORA_G3_LINK_V0_1_PROPOSED",
  "source_episode_id": "demo_2",
  "flora_native": {
    "raw_json_path": "flora_native/demo_2.json",
    "raw_json_sha256": "<to-be-computed>",
    "segment_index": 0,
    "start_s": 0.0,
    "end_s": 3.75,
    "caption": "Pick up the red cup from the left table with the right hand."
  },
  "g1_target": {
    "segment_id": null,
    "interval_frames_inclusive": null,
    "mapping_status": "UNVERIFIED"
  },
  "g3": {
    "schema_version": "P2_G3_SEMANTIC_JSON_V0_2_CANDIDATE",
    "status": "NOT_RUN",
    "prediction": null
  },
  "validation": {
    "status": "NOT_RUN",
    "human_reference_status": "NOT_COLLECTED"
  }
}
```

上例中 `g1_target` 为 null 是因为尚未对齐，不是暗示 `demo_2` 没有 G1 Segment。真实运行时建议**引用**原生 JSON，而非复制原生 `pipeline` 到每个关联行；若报表冗余展示 Caption，应注明其权威副本仍是 raw JSON。

## 5. 时间基准、帧对齐与多对多关系

### 5.1 必须处理的时间基准差异

- Flora 的 `source_clock` 是“相对首个原始视频 presentation timestamp 的秒数”，不能直接假定等于 P2 G1 的 0 起始 `state` 帧编号。
- 本批 MP4 的名义频率为 20 fps，但 **不能仅凭 `round(time_s * 20)` 把索引视为已验证**。以真实 PTS、视频解码帧序、渲染导出 Manifest 和源 Episode ID 为准。
- Flora 时间段建议在 Adapter 中统一解释为半开区间 `[start_s, end_s)` 用于重叠计算；P2 冻结 G1 `[start_frame,end_frame]` 为包含端点的原有契约。映射器必须显式完成两种边界语义的转换，末帧/零时长/短片段单独测试。
- 若视频导出过程中存在帧抽样、丢帧、变速、裁剪、首帧偏移或显示叠字，不能使用简单算术映射，应生成 `video_frame → original_source_frame` 的可信索引表；无证据即 `UNALIGNED`。
- 本次只使用 Flora 单路 `main` 视频；与 P2 `agentview` / Clean RGB 的角色匹配应由视频恢复记录核验，不能凭名称推测。

### 5.2 关联状态与覆盖

对每个 Flora Segment × G1 Segment 计算真实时间域交集；支持：

- `EXACT / PARTIAL_OVERLAP / MULTIPLE_G1_TARGETS / NO_OVERLAP / UNALIGNED`（Adapter 诊断枚举，仅属本提案）。
- 记录交集时长、双方覆盖比例、边界偏差及映射依据；**不要设置未经标定的强制匹配阈值**。
- 可以出现 1 个 Flora Segment 跨 3 个 G1 Segment；它应关联 3 条 link，而不是把 G1 改成一个片段。
- 可以出现 1 个 G1 Segment 对应 2 个 Flora Segment；G3 标签仍落在原 G1 target，Flora Caption 只能作为多个可追溯的上下文候选。
- G3 `evidence_frame_indices` 只能来自冻结 G1 目标帧且确实提供给该次模型请求，Flora 源视频 frame_plan 不自动等于 G3 证据帧。

## 6. 模型输入与证据隔离

### 6.1 不改变正式 P2 视觉来源

P2 正式视觉证据沿用 `P1 RoboMimicStateRenderer` 从对应 `STATE_t` 直接渲染的无损、无文字覆盖 RGB，记录图像 SHA256 与源 state/frame 身份。Flora 的 MP4 只能作为预标注与时间候选来源，**不能静默取代既有 Clean RGB Contract**；若为探索方便使用 MP4 截帧，必须标为非正式探索分支并单独报告输入差异。

输入的有序 TARGET 帧应来自同一冻结 G1 target；如果探索前后上下文，需保留 BEFORE/AFTER role，不得把上下文引用放进 target 内的事件证据。

### 6.2 Caption 是先验信息，不是视觉真值

按顺序评估两种输入变体：

- **A — Vision-only（仅视觉）**：保留现有 G3 v0.2 的 target frames 与 Prompt，不给模型 Flora Caption；这是控制组。
- **B — Vision + Flora Caption（视觉加 Flora 文字提示）**：在完全相同的 target frames、视觉模型、采样参数和 Schema 下加入明确标记为 `unverified_action_hint` 的原生 Caption。Prompt 明确要求“Caption 可错，视觉与可信帧优先；不从 Caption 推断抓取成功、object_motion 或右/左手”。

两种变体共用相同的可信 frame manifest 和 Validator；输出 Run ID、Prompt SHA 必须区分。**不允许把“Flora 时间窗口变化”与“引入 Caption”同时作为一个因素声称单独的效果**。若之后研究时间窗增益，固定 Caption 是否存在和视觉预算，再独立比较 G1-only 与 Flora-guided 帧选择。

## 7. 15 条 Demo 的实施顺序（不需要新负例即可启动）

| 阶段 | 本轮工作 | 验收与状态 |
|---|---|---|
| P0 原生基线整理 | 导入 15 JSON，计算原文件 hash，核对 Episode/Segment 数、Caption、各字段；只复制数据到隔离的本地输出目录 | 15/15 文件可读、31/31 原始 Segment 可索引；原文件字节不变 |
| P1 来源与时间对齐 | 找原 MP4 导出 Manifest、P2 Source Contract、G1 Segment 清单、原始 state/frame；生成 link/audit | 每条 link 有证据或显式 UNVERIFIED；不能将对齐失败算成功 |
| P2 Schema/Validator 适配 | 复用 G3 v0.2 校验器；为 Adapter 增加独立包装校验和 target/context 检查 | 100% 结构校验用例通过；模型原始响应不可修改 |
| P3 微型 Baseline | 先选 2 个已有人工正事件参考 + 2 个空事件参考的 **G1 Segment**；跑 Vision-only，核验 JSON/帧证据/人工事件结果 | 形成 TP/FP/FN 明细和错误案例；若人工参考不足，标 NOT_ESTIMABLE |
| P4 小规模对照 | 在相同目标 G1 片段上进行 A/B（是否提供 Flora Caption），再考虑帧数/窗口实验 | 固定除单变量外的其他配置；区分事件召回改善与新增 FP |
| P5 扩展与数据资产 | 若 P0–P4 可解释再推广到全部 15 Episode 的适配与结构化预测 | 完整溯源、可复用查询索引；不宣称独立泛化或训练 QC 效果 |

初步优先检查 `demo_2`、`demo_4`、`demo_159`（历史漏检诊断）、`demo_169`（左右手描述变化）、`demo_71`（三段且跨度较长）。这五条都是 **开发/诊断案例**，不是新的独立测试集。

原 P2-G3F 中已有 `demo_180-S0001`、`demo_169-S0002`、`demo_232-S0002`、`demo_72-S0002` 等“人工标注的事件集合为空”的 **G1 Segment**；可以作为 `event_presence` 开发案例，但**只有在同源、时间和 G1 ID 核验完成后**才能用。`events=[]` 不必然等于该物理区间真实没有发生任何动作。

## 8. 建议测量指标与通过条件

**工程可用性（P0–P2）**：

1. `native_json_preservation_rate=15/15`：所有 Flora 原文件重新计算 SHA 与导入前一致；字段不丢失，未知字段不删除。
2. `flora_segment_indexing=31/31`：每段具备稳定、可检索的原生引用；该要求不等于 31 段成功映射到 G1。
3. `source_alignment_audit_coverage=15/15`：每个 Episode 必须输出映射成功或失败的明确理由；成功映射率单独报告、不得猜测 100%。
4. 模型请求的 `evidence_frame_indices` 合法性：目标帧均出自实际供应的、归属正确的 source/frame manifest；非法引用 **fail closed**，原始响应保留。
5. 重放 Adapter/Validator 的结果确定性：相同来源文件及配置产生相同关联/校验结果；历史冻结输出不可改。

**语义可用性（P3–P4，仅对人工已核对的目标 G1 片段）**：

- 统计 `object_motion`、`grasp_attempt`、`release_attempt` 各类 TP/FP/FN、Precision、Recall、F1，给每类样本量和缺失类别情况。
- 单独统计 `event_assessment` 三状态、Schema 合法率、帧引用合法率、语义矛盾待复核率。
- 识别 Caption 提示引入的 FP：尤其“文字写 picked up，但图像仅显示手靠近/物体静止”。
- 记录 A/B 每一个改变的事件及证据帧，不只看总 F1。
- 小样本、开发集已用、欠缺真实独立负例时只能报告 **DEV_DIAGNOSTIC / NOT_FORMAL_EVALUATION**，不报 held-out 泛化、QC 因果收益或训练策略有效性。

**阶段 Gate**：P0/P1 完成可以批准 Adapter 工程；P3/P4 需有经核对的参考集且不会引入不可接受 FP 才讨论扩大推理。本文**不预先宣布效果成功阈值或声称已完成 Baseline**；具体阈值在正式运行之前预注册。

## 9. QC 下游消费：约束比自动筛除更重要

- `motion_phase` 可辅助阶段分布/覆盖统计；`events` 用于事件级检索、误报/漏报复核；`object_relation` 用于解释物体与夹爪行为；`evidence_quality` 用于复核优先级。
- `VALID` 只表示通过格式和可验证的来源逻辑检查，**不是人工证实标签正确**。`REVIEW_REQUIRED`、`UNRESOLVED` 等与训练数据保留/删除完全不同。
- 将结构化事件与 P1/M07 轨迹质量信号关联时，必须明确对齐粒度（G1 Segment vs Episode）和标签来源；不能把 Pause/Oscillation/Reversal 直接当成 `object_motion=false`。
- 输出只是 `QC_CANDIDATE_ONLY`：可用于 REVIEW、覆盖分析与检索，不自动发出 `DROP`、`KEEP`、`UPWEIGHT` 或训练收益结论。未来若引入 Rewarder 或多模型对照，单独设立新的版本化实验。

## 10. 建议目录与本地可交付物（实施阶段，不是本次已产出）

```text
outputs/flora_g3_adapter/v0_1/<run_id>/
  run_manifest.json                 # Git HEAD、版本与 SHA、输入策略
  native_inventory.csv              # 15 Episode / 31 Segment
  flora_g1_links.jsonl              # Flora ↔ G1 多对多关系
  alignment_audit.csv               # 来源时间轴和帧对齐审计
  evidence_packs.jsonl              # 可信 G1 target frame manifest
  raw_model_responses.jsonl         # 原始 Qwen 输出，不篡改
  g3_predictions.jsonl              # G3 v0.2 八字段
  validation_findings.jsonl         # 校验/矛盾，不自动改标签
  human_reference.csv               # 需要独立人工完成；允许为空
  review_queue.csv                  # 复核队列，不等于训练数据 disposition
  pilot_metrics.json                # 有分母、有真值时才计算
  pilot_summary.md                  # 状态、失败案例和限制
```

原生 JSON、MP4、干净 PNG、HDF5、模型权重、大型实验输出仅保存在受控数据目录/现有忽略目录，**不要因“同步 Git”把这些大文件直接提交**。Git 中只放设计、可复用代码、测试与经过脱敏/授权的小型证据摘要。

## 11. 必须覆盖的最小测试用例

1. 无损解析并 roundtrip/引用 Flora 原生 JSON，保留全部 10 个顶层键及未来新增键。
2. 非法或缺失 `source_clock`、视频哈希不匹配、Episode 名称相同但 source manifest 不一致 → 失败/UNVERIFIED。
3. `[start_s,end_s)` 与 G1 闭区间端点转换、最后一帧、跨多个 G1、完全不重叠、时钟偏移、短片段。
4. **无新增 Web 服务依赖**；只测输入文件、对齐器、Validator，并支持离线回放。
5. 事件引用不存在帧、引用 BEFORE/AFTER 邻居帧、跨 target 范围 → INVALID/REVIEW，原始预测不能被修补。
6. `event_assessment=event_visible` 却 `events=[]`，或 `no_event_visible` 却有 events → 结构无效。
7. `gripper_state=closed`、`motion_phase=grasp` 不自动推出 success；物体静止的 note 却有 `object_motion` → 矛盾候选。
8. 相同输入重复运行索引和 hash 一致；任一 Prompt/帧选择/模型版本变化必须生成不同 Run ID。

> 测试清单是未来验收约束，不表示本次已跑测试。无需在方案评审阶段触发 GPU 模型推理。

## 12. 开工顺序与工作边界

下一次本地实施前先 `git fetch origin` 并在安全的独立工作区 `git pull --ff-only origin main`；若本地活跃分支存在未提交修改/分叉，不强制 rebase/reset/stash，优先独立 worktree。GitHub 不通优先排查 VPN。

实施顺序只建议：**P0 资产清点 → P1 无模型对齐审计 → P2 Schema/Validator 接线与单元测试 → P3 四样本 Baseline → P4 Caption 有无对照 → 再议全量推理**。当前不训练模型、不重跑 Flora、不消耗独立测试集、不在未验证对齐时做新的 G3 准确率声明。

### 英文术语简释

- `Adapter`：适配器；把两套输出在不更改原格式的情况下可靠关联。
- `Native JSON`：原生 JSON；Flora 原样生成的数据，包含完整推理审计。
- `SSOT (Single Source of Truth)`：单一事实源；同一信息发生冲突时以哪个来源为准。
- `Provenance`：来源溯源；数据、时间、模型、Prompt 和证据帧的可信记录。
- `Ground Truth`：参考真值；经独立人工或可信参考审计确认的标签。
- `Pilot`：小规模试验；先验证接口和真实事件判断，避免盲目全量推理。
- `Fail closed`：遇到来源/证据不合法时明确拒绝自动通过，而不是自动修补数据。

---

**本文件仅提出 Adapter v0.1 的设计和验收方案。现有 G3 v0.2 的冻结定义继续有效；是否进入具体实施、是否更改 G3 输入策略、是否成为正式 G3 v1，须在独立实验和 Owner 决定后另行版本化。**
