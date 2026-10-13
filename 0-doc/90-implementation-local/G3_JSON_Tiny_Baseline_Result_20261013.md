# G3 — Structured JSON Tiny Baseline 结果（2026-10-13）

- **任务**：`P2_G3_JSON_PROMPT_TINY_BASELINE`
- **分支**：`p2-g3-json-prompt-baseline-20261013`（基于 `origin/main` @ `0d568a5`，未合并）
- **工作树**：`C:/Users/95611/embody/_p2_g3_json_wt`
- **运行 ID**：`g3_json_tiny_20261013`
- **运行时间**：2026-10-13 13:40–13:47（+08:00）
- **结论一句话**：JSON 接口在本地 4B 上**很可靠**（可解析率 **10/10**）、
  帧级证据**全部合法**（10/10）、跨段引用**零次**；
  但**Schema 合法率 9/10**（1 条漏了必填的嵌套字段）、
  **弃权率 0/10**（模型在全部 10 段都自称 `evidence_quality=sufficient`），
  且 `object_relation` / `events` 两个字段**实测退化**。
  **本轮不产出任何准确率，也没有人工语义金标。**

---

## A. Git 同步

| 项 | 值 |
|---|---|
| 仓库 | `Modori1998/embody_project2_data_value` |
| `git fetch origin --prune` | 直连 GitHub 被 reset（`Connection was reset`），经 WinINET 代理 `127.0.0.1:10808` 成功 |
| 同步前 main 工作树 | `41a5da3`（clean，仅有 gitignore 的 `?? .cindy-worktrees/`） |
| `git pull --ff-only origin main` | **Fast-forward `41a5da3..0d568a5`** |
| `git rev-parse HEAD` | `0d568a5eb4347d81152856873d0c08c60cff01d5` |
| `git rev-parse origin/main` | `0d568a5eb4347d81152856873d0c08c60cff01d5` ✅ 一致 |
| 任务 worktree / 分支 | `_p2_g3_json_wt` / `p2-g3-json-prompt-baseline-20261013` |
| 对 `main` 的改动 | **无**（未 merge、未 force push、未 reset/clean/stash） |
| 旧分支 / 其他 worktree | 未修改 |

未提交修改 / stash：**无**。同步前 main 工作树干净，未遇阻塞。

**已读 SSOT**：`Project2_MVP_SSOT_20261008.md`、
`P2_G3_Structured_JSON_and_Evidence_Contract_Owner_Freeze_20261013.md`、
`P2_G3_Argus_Design_v1_20261012.md`、`P2_G3_Argus_Output_Design_v1_20261012.md`、
`P2_G3_Phase1B_1C_Observability_Owner_Freeze_20261013.md`。

**复用的已有资产**（差异审计：均为该分支**新增**文件，`main` 上不存在，无冲突）：

| 文件 | 来源分支 @ SHA | 处理 |
|---|---|---|
| `scripts/probe_g3_local_vlm.py` | `p2-g3-local-vlm-deploy-20261013` @ `a1bc80b` | 定向复制，逐字节哈希核对一致 |
| `scripts/materialize_g3_vlm_rgb_frames.py` | 同上 | 定向复制，同上 |
| `tests/test_g3_local_vlm_probe.py`（31 项） | 同上 | 定向复制，同上，并**全通过** |

未合并整条实验分支；未重新下载模型；未装 CUDA Toolkit；未重写 Renderer；
未重做 G1/M2/Phase1B 逻辑。

**环境补充说明（诚实披露）**：新 worktree 的 `outputs/` 为空，
而 Development-pool 构造需要 7 个历史清单（`outputs/` 被 gitignore）。
因此从主工作树**只读复制**这 7 个清单到本 worktree 的 `outputs/`。
未写入任何 Run 目录，未修改任何冻结产物。

---

## B. Argus 参考与删减

详见 `G3_JSON_Prompt_Design_v0_1.md`。摘要：

**借鉴的机制**（上游 `Pantheon-Industries-Inc/argus` @
`ccfd313f18d9981ba3ad2868d7f7d8bc3ecb7629`）：

1. **JSON-only 接口** + `response_format={"type":"json_object"}`
   （`label/harness.py`），并容忍 Markdown 围栏以便诊断（`parse_response`）。
2. **受控枚举 + 有限自由文本** 的混合：Argus 固定
   `arm`/`contribution`/`outcome`/`severity`/`deliberate`，
   而对象名、动作短语、notes 保持自由（"There is no fixed vocabulary"）。
3. **显式弃权值**：`unclear` 系列 + "when unsure, say so in notes rather than guessing"。
4. **证据纪律**：时间必须取自给定帧时间戳；`state_changes` 只记物理结果；
   "List only relations you can actually see"。
5. **局部 / 全局分离**：per-step `progress` 与整段 `completion` 分开判断。
6. **单条标注自洽性检查**：`checks/label_consistency.py`
   只读一条标注自己的字段 + Episode 时长，**不看图像、不跨调用、不证明真值、
   从不修改标注**。这是本轮**最直接的借鉴对象**。

**因 P2 数据约束删减**：`timeline`（会诱导重新分段）、`progress` / `contribution`
（需整段视频视野）、`completion` / `success_predicate` / `goal_reached_at_s`
（Episode 级，任务禁止）、`state_changes`（需同物体前后视图）、`scene_graph`、
`recovery`（需跨段连线）、`instruction_variants`、`performance_review`、
`data_issues` / `operator_mistakes`、绝对时间 `t_s`、`arm` left/right（单臂无信息）。
**未**复制 Argus 的 Episode Prompt 或其 timeline/completion 语义。

---

## C. JSON Schema v0.1

见 `G3_JSON_Output_Design_v0_1.md`。要点：

- 模型自有字段 **7 个**：`motion_phase`、`object_relation`、`gripper_state`、
  `events`（含 `event_type` / `event_outcome` / `evidence_frame_indices`）、
  `evidence_frame_indices`、`evidence_quality`、`observation_note`。
- 枚举：`motion_phase`(9)、`object_relation`(6)、`gripper_state`(4)、
  `event_type`(5)、`event_outcome`(3)、`evidence_quality`(3)。
- 每层 `additionalProperties: false`；`segment_id` 等 8 个字段
  **由调用方注入**，模型若输出即判 `INVALID_MODEL_OUTPUT`。
- 状态机：`PROCESSING_ERROR` / `INVALID_INPUT` / `INVALID_MODEL_OUTPUT` /
  `REVIEW_REQUIRED` / `UNRESOLVED` / `VALID`。
- **未冻结**：全部枚举取值、基数/null 语义、`gripper_state` 是否保留、
  是否新增遮挡字段、各 CANDIDATE 规则严重度。

---

## D. Prompt v0.1

| 项 | 值 |
|---|---|
| 文件 | `0-doc/10-design-review/P2_G3_Semantic_Prompt_v0_1_20261013.txt` |
| 版本 | `P2_G3_ARGUS_INSPIRED_PROMPT_V0_1_CANDIDATE` |
| Template SHA-256 | `5a50475e590cce38923feb829e58971ea7d9a51303c4b8169f1251e671c79cb8` |
| Schema SHA-256（本次运行使用的 JSON Schema） | `b37d8c15711488a9cd14e7ec002175484af01616694f5ef1b0673084944e3978` |
| 逐样本 Prompt SHA-256 | 登记于 `sample_manifest.csv` / `model_requests.jsonl` |
| 输入策略 | `TARGET_KEYFRAMES_ONLY`（不默认加 Context Window） |

Prompt 五段：任务与冻结边界 → **逐帧身份配对表**
（`frame_index` / `role` / `source_episode_id` / `origin_segment_id` /
`是否目标段帧`）→ JSON-only 输出与**程序生成的**枚举清单 →
证据与不确定性规则 → 严格禁止清单。

**防漂移**：Prompt 里的枚举块由 `semantic_schema.ENUM_TABLE` **程序生成**，
有单测断言二者一致，Prompt 不可能与 Schema 脱钩。

**未事后改 Prompt**：v0.1 在推理前固定，看到错误后未回头调整。

已知设计缺陷（记录，不在本轮修）：v0.1 用 `grasp` 表达"夹爪闭合并环绕"
（把**状态**当**阶段**）；`object_relation` 与 `gripper_state` 语义重叠。
这些是 v0.2 议题。

---

## E. 10 Segment Baseline（真实推理）

### E.1 配置

模型 `Qwen3-VL-4B-Instruct-GGUF` Q4_K_M（LLM sha256 `66358cb1…0a0a`，
mmproj F16 sha256 `256f3a43…5331`，revision `1cd86afb…2266`）；
llama.cpp b11577 CUDA 12.4；`temperature=0`、`seed=1234`、`max_tokens=512`、
`response_format=json_object`；单请求无并行。

### E.2 总体统计（分母 = 10 次已发起请求）

| 指标 | 值 |
|---|---|
| 已发起模型请求 | **10** |
| HTTP 200 | **10 / 10 = 1.00** |
| **JSON 可解析率** | **10 / 10 = 1.00** |
| **Schema 合法率** | **9 / 10 = 0.90** |
| **帧级证据引用合法率** | **10 / 10 = 1.00** |
| **超出目标段证据次数** | **0** |
| 引用不存在帧次数 | **0** |
| 截断次数（`finish_reason=length`） | **0** |
| `uncertain` 弃权样本数 / 弃权率 | **0 / 10 = 0.00** |
| Note/Enum 冲突候选数 | **0** |
| 平均耗时 | **2.224 s**（最大 2.746 s） |
| 平均 prompt / completion tokens | **976.5 / 105.6** |
| 显存峰值 | **4838 MiB**（总 8188 MiB，剩余约 3.35 GiB） |
| QC 状态分布 | `VALID` 9、`INVALID_MODEL_OUTPUT` 1 |
| 检查项触发 | `MISSING_REQUIRED_FIELD` ×1、`EVIDENCE_SUFFICIENCY_CANDIDATE` ×1 |
| 合法模型输入违规 | **0** |

### E.3 门槛判定（事前登记）

| 门槛 | 阈值 | 实测 | 结果 |
|---|---|---|---|
| `illegal_model_inputs` | ≤ 0 | 0 | ✅ |
| `json_parse_rate` | ≥ 0.90 | 1.00 | ✅ |
| `schema_valid_rate` | ≥ 0.90 | 0.90 | ✅（刚好达线） |
| `frame_evidence_valid_rate` | ≥ 0.90 | 1.00 | ✅ |
| `truncated_outputs` | ≤ 0 | 0 | ✅ |
| 跨段引用全部被标记 | — | 0 次引用 | ✅（无越界可标记） |

**`all_gates_pass = true`。**

> **必须说明**：`schema_valid_rate = 0.90` 是**刚好等于**阈值。
> 若把门槛设为 0.95 即为失败。门槛是**工程契约门槛**，
> **不是**语义准确率阈值，事后未调整。

### E.4 逐样本

| # | Segment | 状态 | 耗时 | 输出 tok | 显存 |
|---|---|---|---|---|---|
| 1 | `demo_120-S0005` | VALID | 2.75 s | 111 | 4838 |
| 2 | `demo_165-S0003` | VALID | 2.11 s | 97 | 4838 |
| 3 | `demo_196-S0002` | VALID | 1.92 s | 92 | 4838 |
| 4 | `demo_227-S0005` | VALID | 1.96 s | 96 | 4838 |
| 5 | `demo_277-S0005` | VALID | 2.34 s | 114 | 4838 |
| 6 | `demo_292-S0002` | VALID | 2.25 s | 107 | 4838 |
| 7 | `demo_33-S0001` | VALID | 2.06 s | 98 | 4838 |
| 8 | `demo_47-S0003` | **INVALID_MODEL_OUTPUT** | 2.63 s | 133 | 4838 |
| 9 | `demo_74-S0003` | VALID | 2.17 s | 110 | 4838 |
| 10 | `demo_75-S0001` | VALID | 2.06 s | 98 | 4838 |

`finish_reason` 全部为 `stop`。

### E.5 字段使用分布（实测）

| 字段 | 分布 | 解读 |
|---|---|---|
| `motion_phase` | `grasp` 5、`approach` 5 | 9 个候选值只用到 **2 个** |
| `gripper_state` | `closed` 5、`open` 5 | 与 `motion_phase` 完全共变 |
| `object_relation` | `gripper_around` 8、`object_static` 2 | **近似常量**，6 个候选值只用到 2 个 |
| `events` | **空数组 9/10** | 事件层**信息量接近零** |
| `event_outcome` | `success` ×1 | 仅 `demo_47-S0003` |
| `evidence_quality` | `sufficient` 10/10 | **零弃权** |

`moving_with_gripper`、`gripper_contact_visible`、`object_not_visible`、
`grasp_attempt`、`release_attempt`、`object_motion`、`none_observed`
在本轮 10 条中**从未被使用**。

### E.6 与 Phase-1C 人工结果的关系

Phase-1C 的 10 条人工回答是**可理解性自评**，**不是语义金标**。
本轮**没有**用它计算任何准确率。

仅作描述性观察：Owner 在 Phase-1C 把 `demo_33-S0001` 与 `demo_75-S0001`
（都是 4 帧首段）评为 `CANNOT`（看不懂），
而本轮模型对这两段仍给出 `evidence_quality=sufficient`。
**这不能称为"模型错误率"**，但提示**弃权行为与人类可理解性明显脱节**。

---

## F. 错误分析

### F.1 已证明错误（`DETERMINISTIC`，结构性可证）

**1 条**：`demo_47-S0003` 的 `events[0]` **缺少必填字段 `evidence_frame_indices`**。

模型原始输出（不可变，节选）：

```json
"events": [
  { "event_type": "grasp_attempt", "event_outcome": "success" }
],
"evidence_frame_indices": [50, 70, 90],
"evidence_quality": "sufficient",
"observation_note": "Robot's gripper is closed and surrounding the can. The can is visible and stationary. No motion is observed in the segment."
```

→ 判定 `INVALID_MODEL_OUTPUT`（`MISSING_REQUIRED_FIELD`）。
**同类**：`EVIDENCE_SUFFICIENCY_CANDIDATE` —— 断言 `event_outcome=success`
但支持帧少于 2 个，无法体现事件前后变化。

> 注：该段正是上一轮出现跨段越界的同一段（`demo_47-S0003`）。
> 两轮都在这一段出问题，是该段本身证据结构特殊（3 关键帧全在"持物"状态内），
> 但**不能**因此说这两轮的错误是同一个原因。

### F.2 待复核候选（`CANDIDATE`，程序无法选边）

**1 条**：上述 `EVIDENCE_SUFFICIENCY_CANDIDATE`。
其余 `LABEL_NOTE_CONFLICT_CANDIDATE`、`EPISODE_LEVEL_CLAIM_CANDIDATE`、
`PHASE_EVENT_CONFLICT_CANDIDATE` 等**均未触发**（0 次）。

### F.3 跨段引用

**0 次**。10 条主基线中模型引用的帧**全部**是目标段关键帧
（`is_target_segment_frame=True`），无越界、无不存在的帧。

### F.4 检查器未覆盖的矛盾（如实记录，未回填规则）

`demo_47-S0003` 的 note 写 **"No motion is observed in the segment"**，
同时 `motion_phase=grasp` 且 `events[0].event_outcome=success`。
这是**语义矛盾**（既说没观察到运动，又断言一次成功的抓取尝试），
但 v0.1 检查器**没有对应规则**。

**处理方式**：如实记录为已知缺口，**不在看到结果后临时加规则**
（那等于用测试集调检查器）。已建议 v0.2 增
`OUTCOME_CONTRADICTS_OBSERVED_MOTION_CANDIDATE` 并先写合成单测。

### F.5 不确定判断

**0 次弃权**。模型在全部 10 段都声明 `evidence_quality=sufficient`，
包括 4 帧的短段。`uncertain` / `unclear` / `insufficient` **一次未用**。
**这是本轮最值得关注的负面发现**：接口**允许**弃权且 Prompt **要求**
看不清就说看不清，但模型**没有这样做**——弃权能力存在≠会被使用。

### F.6 `object_relation` 与 note 的内部张力（未触发规则）

`demo_196-S0002` 与 `demo_227-S0005` 的 note 都写
"gripper is open and not in contact with the can"，但
`object_relation` 仍为 `['gripper_around']`。
v0.1 **没有**针对 `gripper_around` 的定义性规则（"环绕"≠"接触"），
因此未触发。这属于**枚举语义定义不足**，不是程序漏检——
需要 Owner 在 taxonomy 阶段定义 `gripper_around` 的判据。

### F.7 可选边界回归（`demo_47-S0003`）

| 变体 | 图片 | 状态 | 引用帧 | 跨段标记 |
|---|---|---|---|---|
| `target_only` | 3（50/70/90） | `VALID` | [50, 70, 90] | 0 |
| `target_plus_neighbour` | 6（49/91/94 上下文 + 50/70/90 目标） | `INVALID_MODEL_OUTPUT` | [50, 70, 90] | **0** |

- 加入邻段上下文后，模型**仍然只引用目标段帧**，
  **没有**把邻段帧当作目标段证据 → `TARGET_CONTEXT_CROSS_BOUNDARY` **未触发**。
- 邻段变体仍然漏了 `events[0].evidence_frame_indices`，
  并再次给出同一处 note/字段矛盾。

**诚实结论**：
1. 该守卫**会**拦截跨段引用（已由合成单测证明）。
2. 但在这次真实样本上**没有被触发**，因此
   **不能**说"跨段误归因已解决"，也**不能**说"加入上下文无害"——
   只做了 **1 个段、1 个变体**。
3. 该结果**未计入** 10 条主基线分母。

---

## G. 交付物与后续

### G.1 新增文件

**核心库**（`src/project2_g3/`）
`__init__.py`、`semantic_schema.py`（枚举 + JSON Schema + 语义护栏）、
`semantic_validation.py`（解析 + A/B/C 三类检查 + 状态机）、
`semantic_prompt.py`（Prompt v0.1 + 哈希）、
`dev_segments.py`（Development pool + 冻结分段复算 + 固定样本 + 邻段帧规则）

**脚本**
`scripts/run_g3_json_tiny_baseline.py`（主运行器，含可选边界回归）
`scripts/probe_g3_local_vlm.py`、`scripts/materialize_g3_vlm_rgb_frames.py`（定向复用）

**测试**
`tests/test_g3_semantic_json_contract.py`（**79 项**）
`tests/test_g3_local_vlm_probe.py`（**31 项**，复用）

**文档**
`G3_JSON_Prompt_Design_v0_1.md`、`G3_JSON_Output_Design_v0_1.md`、
`G3_JSON_Baseline_Plan_v0_1.md`、本文件、
`0-doc/10-design-review/P2_G3_Semantic_Prompt_v0_1_20261013.txt`

**证据**（脱敏）
`0-doc/10-design-review/evidence/P2_G3_JSON_Tiny_Baseline_20261013/`
（12 个文件：运行身份、Schema、样本清单、帧清单、请求、原始回复、
标注、QC 发现、复核队列、汇总、边界回归）

### G.2 测试

| 套件 | 数量 | 结果 |
|---|---|---|
| `test_g3_semantic_json_contract.py`（新增） | **79** | ✅ 全通过 |
| `test_g3_local_vlm_probe.py`（复用，31 项不回归） | **31** | ✅ 全通过 |
| 复用代码回归子集（stage_b / stage_c / mvp_m2 / rgb_input_contract / boundary_engine / p1+p2 privileged_leakage） | 52 | ✅ 51 通过，**1 项既有失败** |

**既有失败披露（与本轮无关，已在 pristine `main` 与未改动的部署分支复现）**：
- `tests/test_g1_p2_privileged_leakage.py::test_engine_files_do_not_reference_privileged_keys`
  —— 断言 `run_boundary_engine` 参数个数为 2，实际为 3。在 `main` 工作树与
  `a1bc80b` 部署分支工作树上**同样失败**。
- `tests/test_g1_12ep_baseline_calibration.py` —— 依赖完整 `outputs/` 注册表
  与机器相关指纹；在 pristine `main` 工作树亦失败（另一条用例）。
  已通过"临时移走复制目录"实验证明**不是**本轮的 `outputs/` 复制导致。

本轮**未修改**任何既有 G1/M2/MVP 源码（`git status` 仅新增文件）。

### G.3 提交与远端

见文末"远端提交"。**不修改 `main`，不自动合并**。

### G.4 需要 Owner 决策的事

1. **taxonomy**：`motion_phase` 是否区分"状态 vs 阶段"；
   `object_relation` 是否与 `gripper_state` 合并；
   `gripper_around` 的判据定义。
2. **`events` 去留**：实测 9/10 为空，是否保留该字段或改为可选。
3. **弃权校准**：模型 0/10 弃权，但人工对其中 2 段说"看不懂"。
   是否需要把弃权做成**可强制的输出契约**，或改为**事后触发**的复核策略。
4. **v0.2 检查规则**：是否新增
   `OUTCOME_CONTRADICTS_OBSERVED_MOTION_CANDIDATE` 等规则。
5. **正式实验设计**：8B checkpoint、Vision-only vs Vision+State A/B、
   人工金标 rubric、Episode-disjoint Held-out、指标与阈值。

---

## 人话总结

1. **这次比上一轮 Smoke Test 新增了什么？**
   上一轮只是"模型能不能看图"——自发文本、无结构、无法机器核验，
   而且它把邻段画面当成目标段来讲。这一轮把**输出变成受控 JSON**：
   枚举固定、每条肯定判断必须给帧号、程序逐帧回查清单、
   原始回复先落盘再解释。**首次做到可以机器判"这条标注的结构是否合规、
   引用的帧是否合法"**，并有 79 项单测锁住契约。

2. **为什么这次的 JSON 比上一轮更适合 P2？**
   上一轮的自由文本没法自动核对，也没法做统计。
   这次的 JSON 让"引用越界帧"变成**可自动拦下的硬错误**——
   程序能证明某帧号是否属于目标段（这是清单比对），
   而不是靠人读文本猜。同时它把"我不确定"变成**一等公民**（枚举值），
   这样弃权率可以被测量，而不是被淹没在措辞里。

3. **是否减少了跨段证据错误和字段矛盾？**
   **部分减少，但不能宣称解决。**
   本轮 10 条里跨段引用 **0 次**、字段矛盾候选 **0 次**——
   比上一轮明显干净。但这**不能**全归功于 JSON：
   本轮是 **target-only 3 张图**，上一轮出问题的场景是 **6 张图含邻段**。
   我们额外做了 `demo_47-S0003` 的 6 图对照，模型这次也只引用了目标段帧，
   但只有 **1 段 1 次**，样本量根本不足以证明"误归因已解决"。
   而且程序**只能**发现"被引用"的越界帧，
   发现不了"note 用文字描述邻段事件却没引帧"的情况——这个检测上限必须说清楚。

4. **4B 能否完成初步语义标注？**
   **能跑通，但还不能信。** 好消息：JSON 可解析 10/10、
   帧证据合法 10/10、平均 2.2 秒、显存峰值 4.8 GB，工程上完全可用。
   坏消息有三条：
   (a) 10 条里 1 条漏了必填的嵌套字段（Schema 合法率 0.90，刚好卡在门槛线上）；
   (b) **一次都没说"我看不清"**，10 段全自称证据充分，连 4 帧的短段也是——
   这和人在 Phase-1C 说"这两段看不懂"明显脱节；
   (c) `object_relation` 退化成一个近乎常量的字段（8/10 都是 `gripper_around`），
   `events` 9/10 是空数组，**这两个字段目前几乎没有信息量**。

5. **距离正式 8B Baseline 还缺什么？**
   - **人工语义金标**（本轮只有可理解性自评，不能算准确率）；
   - **Episode-disjoint 的 Held-out 划分**；
   - **taxonomy 冻结**：现在 `motion_phase` 被当"状态"用、
     `object_relation` 与 `gripper_state` 语义重叠，字段定义没定下来，
     换 8B 也解决不了"字段本身没定义清"的问题；
   - **弃权机制**：要么做成强约束，要么改为事后复核策略；
   - **检查器补规则**并先在合成用例上单测；
   - 正式 8B checkpoint 与 Vision-only vs Vision+State 的 A/B 设计。
   换句话说：**4B 已经把"管道"跑通了，现在卡住的是"标签的定义"
   和"人怎么核对"，不是算力。**

---

## 停止点

本轮到此停止。**未**进入正式 Held-out 评测、8B 运行、高分辨率契约变更、
ACT/VLA 训练；**未**把 v0.1 自动冻结为正式 Taxonomy v1；
**未**修改 `main`，**未**自动合并。
