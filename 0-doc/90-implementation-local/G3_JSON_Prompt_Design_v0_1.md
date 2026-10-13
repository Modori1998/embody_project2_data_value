# G3 — Argus 上游参考与 P2 Prompt v0.1 设计（2026-10-13）

> **状态**：`PROMPT_V0_1 = CANDIDATE_IMPLEMENTED_NOT_OWNER_FROZEN`
> **上游固定**：`Pantheon-Industries-Inc/argus` @ `ccfd313f18d9981ba3ad2868d7f7d8bc3ecb7629`
> **实际阅读**：`label/prompts.py`、`label/harness.py`、`checks/label_consistency.py`
> **Prompt 交付物**：`0-doc/10-design-review/P2_G3_Semantic_Prompt_v0_1_20261013.txt`
> **Prompt template SHA-256**：`5a50475e590cce38923feb829e58971ea7d9a51303c4b8169f1251e671c79cb8`
> **Schema 版本**：`P2_G3_SEMANTIC_JSON_V0_1_CANDIDATE`

---

## 1. Argus 实际怎么做（逐条回答任务要求）

### 1.1 Argus 怎样要求模型生成 JSON

`label/prompts.py` 的 `SCHEMA` 块开头就是硬约束：

> `Return ONLY JSON with this shape.`

`label/harness.py` 进一步在请求里设置
`"response_format": {"type": "json_object"}`（OpenAI 兼容路径与另一条路径都设置）。
它还记录：模型有时会忽略 `json_object` 而把 JSON 包在 Markdown 围栏里，
因此 `parse_response()` 专门处理围栏再解析。
harness **不发送** temperature / top_p / seed，也不固定 provider。

**P2 v0.1 借鉴**：同样是 "只输出一个 JSON 对象" + `response_format=json_object`；
但我们**固定** `temperature=0`、`seed=1234`、单一本地模型与运行时，以保证可复现。

### 1.2 哪些字段采用固定类别

Argus 用有限枚举的字段（取自 `SCHEMA`）：

| 字段 | 枚举 |
|---|---|
| `timeline[].arm` | `left` / `right` / `both` |
| `timeline[].contribution` | `advancing` / `wasteful` / `idle` |
| `key_events[].outcome` | `success` / `failure` / `unclear` |
| `completion.task_completed` | `success` / `success_then_undone` / `failure` / `partial` / `unclear` |
| `data_issues[].severity` | `low` / `medium` / `high` |
| `operator_mistakes[].severity` | `low` / `medium` / `high` |
| `operator_mistakes[].deliberate` | `yes` / `no` / `unclear` |
| `recovery[].recovered` | `true` / `false` |
| `progress` | `0..1` 浮点 |

`data_issues.category` / `operator_mistakes.category` 是**半开放**的：
给出可复用 tag 清单（`DATA_ISSUE_TAGS` / `OPERATOR_MISTAKE_TAGS`），
但 Prompt 明确写 "they are never a closed list"、**"Coin your own when none fits"**。

**P2 v0.1 借鉴**：核心分类字段用有限枚举；`P2` **不**采用"自己造 tag"的半开放设计——
4B 模型在受控枚举下更不容易漂移，且 P2 需要可比对的标签。

### 1.3 哪些字段保留自然语言

Argus 明确保留自由文本的位置：对象 `name` / `attributes` / `location`
（"There is no fixed vocabulary"）、`timeline[].action`（自由动词短语）、
`timeline[].notes`、`task_summary`、`success_predicate`、`performance_review`、
`how_to_fix`、`instruction_variants`、各类 `evidence` 描述。

**P2 v0.1 借鉴**：保留 `observation_note` 一个自由文本字段（一到两句），
其余全部受控。**不**保留多套自由文本字段——Owner Freeze 明确要求
note 不得成为"第二套竞争性分类"。

### 1.4 如何表达"无法确定"

Argus 的弃权值散布在枚举里：
`outcome=unclear`、`task_completed=unclear`、`deliberate=unclear`、
`goal_reached_at_s=null`、`completed_at_s=null`。
Prompt 反复要求："Only claim what the frames show; when unsure, say so in
notes rather than guessing."；`contribution` 的不确定性写到 `notes`。

**P2 v0.1 借鉴**：每个分类字段都有显式弃权值
（`uncertain` / `unclear` / `insufficient` / `none_observed`），
并在 `semantic_schema.ABSTENTION_VALUES` 中机器可读地登记。
**关键差异**：Argus 允许"在 notes 里说明不确定"作为唯一出口；
P2 要求**枚举本身**就能表达不确定，因为我们要对弃权率做统计。

### 1.5 如何描述 Timeline / Key Events / Recovery

- **Timeline**：`timeline_columns` + `timeline` 组成**列式**二维数组
  （避免每个 segment 重复几百次 key）。每行一个"动作阶段"，
  带 `start_s` / `end_s` / `action` / `object` / `destination` /
  `spatial_relation` / `contribution` / `progress` / `notes`。
  时间必须来自给定帧时间戳，要求"Cover the whole episode with no large
  unexplained gaps"。
- **Key Events**：`key_events` 是**短列表**，只标记"人判断进度会标的那些瞬间"，
  每个带 `t_s` / `label` / `kind` / `outcome` / `note`。
  粒度按任务自然单位（叠杯=每个杯子；折衣=每次折叠）。
- **Recovery**：`recovery[]` 把**每个失败**与"操作者实际怎么补救"配对；
  同一目标反复失败算**一条**（从第一次到成功那次）；
  未补救则 `recovered=false`、`correction=null`，只写理想补救 `how_to_fix`。
  另有 `success_then_undone` 专门表达"达成了又被破坏"。

**P2 v0.1 的处理**：**三者都不采用**（原因见 §2）。
P2 的单位是**一个冻结 G1 Segment**，没有 Episode 级时间轴，
没有多段 timeline，也不可能可靠判断 recovery。若强行近似，等于要求 4B
重做分段与跨段连线，既越权又必然幻觉。

### 1.6 Argus 的内部一致性检查实际检查什么

`checks/label_consistency.check()` 只读**一条标注自身**的字段与 Episode 时长，
**不**看任何图像，**不**跨独立调用比较，**不**证明视觉真值。
查出即报告，**从不修改**标注。实际规则（docstring 与代码一致）：

`outcome_vs_alignment`、`outcome_vs_partial`、`alignment_vs_match`、
`undone_timing`、`nothing_after_goal`、`progress_vs_outcome`、
`goal_times_differ`、`progress_before_goal`、`progress_past_goal`、
`time_past_end`。

多数规则是"同一标注里两个字段不可能同时为真"，例如
"outcome 说达标，但 timeline 里 progress 只到 0.8"。

**P2 v0.1 借鉴（这是最直接的借鉴）**：`semantic_validation.check_label_consistency()`
同样是**单条标注自洽性**检查，同样**只看存储的字段**，同样**从不修改**原始输出，
并把结果分成 `DETERMINISTIC`（结构性可证）与 `CANDIDATE`（需人工裁决）两类。
**关键差异**：Owner Freeze 明确要求区分"已证明错误"与"待复核候选"，
Argus 的规则集没有这个分级；P2 增加了 `scope` 字段与状态机。

---

## 2. 因为 P2 数据约束被删减的内容

| Argus 构造 | 为什么 P2 v0.1 删除 |
|---|---|
| `timeline`（多阶段） | P2 单位是**一个冻结 Segment**；让模型输出 timeline 等于邀请它重新分段，而 Frozen G1 边界不可改 |
| `progress` 0..1 / `contribution` | 需要"整段视频在视野内"才能判断绝对任务进度；模型只看 3 张关键帧 |
| `completion` / `success_predicate` / `goal_reached_at_s` / `completed_at_s` | **Episode 级**结论；几张段内关键帧无法支撑，且任务明确禁止判断任务成败 |
| `state_changes` | 需要同一物体的"前/后"可视图；3 帧段不足以可靠建立 |
| `scene_graph` | 对 v0.1 标签无用，纯粹增加幻觉面 |
| `recovery` | 需要跨段连线与 Episode 视野 |
| `instruction_variants` | 是数据增强产物，不是对当前段的标注 |
| `performance_review` | Episode 级执行质量，G3 v1 明确非目标 |
| `data_issues` / `operator_mistakes` | 数据集质量打标，与"段语义"是不同关注点 |
| 绝对时间 `t_s` 浮点 | P2 用 G1/M2 冻结的 `frame_index` 身份，不用自由浮动时间 |
| `arm` left/right | P2 Can/MH 是单臂，该字段无信息量，只增加错误值面 |

**没有做的事**：没有把 Argus 的 Episode Prompt 直接搬给 4B；没有复制 Argus 的
词汇表；没有复制其 timeline/completion 语义。P2 的 Prompt 是**独立撰写**的
P2 专用文本（见交付文件），只借用 §1 列出的机制。

---

## 3. P2 Prompt v0.1 的结构

`render_prompt()` 生成的 Prompt 分五段（顺序即约束强度递减）：

1. **任务**：声明只标注一个冻结 Segment，给出 `source_episode_id`、
   `segment_id`、冻结区间 `[start, end]`，并明确
   "你不能重新定义 Segment 边界"。
2. **输入证据**：一张 Markdown 表，把**每张图**与
   `frame_index` / `role` / `source_episode_id` / `origin_segment_id` /
   `是否目标段帧` **逐行配对**。禁止"只给六张无来源图片"。
3. **输出格式**：只输出一个合法 JSON 对象、不要围栏；随后是从
   `semantic_schema.ENUM_TABLE` **程序生成**的枚举清单
   （单一事实来源，Prompt 不可能与 Schema 漂移）；再逐字段说明。
4. **证据与不确定性规则**：肯定性判断必须给支持帧；支持帧只能引用
   "是否目标段帧 = 是"的帧；看不清必须用 uncertain/unclear/insufficient；
   `events` 可以为 `[]`。
5. **严格禁止**：禁止把邻段事件写成当前段；禁止推断接触力 / 抓取成功 /
   滑落 / 任务完成 / 精确接触时刻 / 未展示的完整 Episode 动作；
   禁止特权字段；禁止把"夹爪闭合"等同"已抓住"、
   把"没看到物体运动"等同"抓取失败"。

**v0.1 默认输入**：`TARGET_KEYFRAMES_ONLY`（3 张：START/MIDDLE/END，
含 `GRIPPER_EVENT` 时按其规则去重）。**不默认加入 Context Window**，
与 `CONTEXT_POLICY_DECISION=KEEP_CONTEXT_OPTIONAL` 一致。

**Prompt 文本哈希**：template 哈希见文首；每次请求的**实际** Prompt
（含该段的帧身份表）在 `sample_manifest.csv` 与 `model_requests.jsonl` 里
逐样本登记 `prompt_sha256`，因此"模型到底收到什么"可逐条核验。

**禁止反悔条款**：本轮在 10 条样本推理**之前**固定 Prompt 与 Schema；
看到预测错误后**没有**回头改 Prompt 或样本。所有 v0.1 缺陷记录在案，
留作 v0.2 提案，不在本轮修正。

---

## 4. 与现有 G3 文档的兼容性核对

| 现有 G3 提议 | v0.1 是否兼容 | 说明 |
|---|---|---|
| Owner Freeze：单 JSON 对象 + 受控枚举 + 短 note + 帧级证据 + 确定性 QC | ✅ 完全遵循 | 见 `G3_JSON_Output_Design_v0_1.md` |
| Owner Freeze：`segment_id` 等由调用方注入，不采信模型自报 | ✅ 遵循 | `CALLER_OWNED_FIELDS`，模型若输出即判 `INVALID_MODEL_OUTPUT` |
| Owner Freeze：上下文策略 `KEEP_CONTEXT_OPTIONAL` | ✅ 遵循 | 默认 target-only；邻段仅用于可选回归实验 |
| Argus Output Design 草案 `P2_G3_LABEL_V1_DRAFT` | ⚠️ 部分沿用 | 沿用了 `motion_phase` / `object_relation` / `events` / `evidence_quality` 命名；但**砍掉** `object_description` 与 `model_reported_confidence`（后者是未校准自报，见下） |
| Argus Output Design 草案 `object_relation` 数组基数 | ✅ 沿用数组 | v0.1 要求 `minItems=1`、`uniqueItems`（草案未定基数，属待冻结项） |
| G3 Design 提议的 `grasp_attempt` 等事件名 | ✅ 沿用 | `grasp_attempt` / `release_attempt` / `object_motion` 与既有提议一致 |

**未采用的草案字段说明**：`model_reported_confidence` 在 v0.1 中**删除**。
理由：Argus 自身不要求置信度；4B 的自报置信度无法校准，
并且会成为"看起来像证据、实际不可用"的字段。取而代之的是受控的
`evidence_quality` 枚举 + 弃权值。

---

## 5. v0.1 已知设计缺陷（待 v0.2，本轮不改）

1. `events` 在实践中几乎恒为空（10 条里 9 条），事件层信息量接近零。
2. `object_relation` 退化为近似常量（`gripper_around` 8/10）。
3. `gripper_state` 与 `object_relation` 语义重叠，模型用
   "夹爪闭合并环绕" 去表达 `motion_phase=grasp`，即把**状态**当**阶段**。
4. 没有任何字段承载"物体是否可见/被遮挡"，导致 `evidence_quality`
   只能靠模型自觉。
5. 缺少"该段是否根本不该被语义标注"的显式状态（例如纯静止段）。

这些都需要 Owner 在 taxonomy freeze 时决定，v0.1 不做静默修改。
