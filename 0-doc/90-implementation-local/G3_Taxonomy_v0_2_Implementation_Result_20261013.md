# G3 — Taxonomy v0.2 实现与配对基线结果（2026-10-13）

- **任务**：`P2_G3_TAXONOMY_V02_IMPLEMENTATION_AND_PAIRED_BASELINE`
- **分支**：`p2-g3-taxonomy-v02-baseline-20261013`（基于 `origin/main` @ `9e44687`，未合并）
- **工作树**：`C:/Users/95611/embody/_p2_g3_v02_wt`
- **运行**：
  - Run A（**首版 v0.2 Prompt，含实现缺陷**）：`g3_taxonomy_v02_20261013`
  - Run B（**修复后 v0.2.1 Prompt，本报告主结果**）：`g3_taxonomy_v02_20261013_r2`
- **一句话结论**：v0.2 把**事件层从近乎空转变成真正可用**（非空事件 6.7% → **80%**）、
  并让模型在**看不清的 4 帧短段**上从 `approach` 改为 `idle`（不再无依据断言动作），
  同时 `demo_47-S0003` 的"说没有运动却断言抓取"矛盾**消失**；
  但 `evidence_quality` 仍 **15/15 全部 sufficient（零弃权）**，
  新增的 `PHASE_NOTE` 规则**4 次触发全是误报**，且发现 llama.cpp 推理**不是逐 token 可复现**。
  **本轮不产出任何准确率**：无独立人工金标 → `NOT_ESTIMABLE`。

---

## A. Git 同步

| 项 | 值 |
|---|---|
| `git fetch origin --prune` | 直连失败（`Failed to connect to github.com:443`），经 WinINET 代理 `127.0.0.1:10808` 成功 |
| 同步前 main 工作树 | `0d568a5`（clean，仅 gitignore 的 `?? .cindy-worktrees/`） |
| `git pull --ff-only origin main` | **Fast-forward `0d568a5..9e44687`** |
| `rev-parse HEAD` / `origin/main` | 均为 **`9e44687e9774f1433372a3162d1b65db36633de2`** ✅ |
| 任务 worktree / 分支 | `_p2_g3_v02_wt` / `p2-g3-taxonomy-v02-baseline-20261013` |
| 对 `main` 的改动 | **无**（未 merge、未 force push、未 reset/clean/stash） |
| 未提交修改 / stash | **无** |

**v0.1 定向复用（差异审计）**：v0.1 分支（`p2-g3-json-prompt-baseline-20261013` @ `331d9af`）
相对 `main` 的 `src/project2_g3/` + 3 个脚本 + 2 个测试共 10 个文件是
**纯新增（4167 insertions / 0 deletions）**，与 `main` 无冲突。
10 个文件按 `git show` 定向恢复后**逐个 SHA 核对一致**；未合并整条 v0.1 分支，
未改动 `_p2_g3_json_wt` 工作树，v0.1 的 Prompt / Schema / 10 条预测与运行记录**原样保留**。

**环境补充（诚实披露）**：新 worktree 的 `outputs/` 为空，Development-pool 构造依赖
7 个历史清单（`outputs/` 被 gitignore），因此从主工作树**只读复制**这 7 个文件。

---

## B. 改动说明（每项针对 v0.1 的什么具体问题）

### B.1 新增字段：`event_assessment`

Owner Freeze 要求恰好新增 **1 个**顶层字段，枚举
`event_visible | no_event_visible | insufficient_evidence`，并与 `events` 有硬基数契约。

**针对 v0.1 的问题**：v0.1 把"事件是否发生"的不确定性塞在 `events` 数组里
（`none_observed` / `uncertain` 哨兵），导致 **9/10 样本 `events=[]`**，
而"没观察到"与"确证没有"无法区分，事件层几乎不携带信息。
v0.2 把**发生性**（`event_assessment`）与**结果性**（`event_outcome=unclear`）拆开。
v0.1 数组哨兵在 v0.2 中被判 `ILLEGAL_ENUM`（`retired_sentinel`），迁移显式版本化，不回溯改写旧 JSON。

### B.2 动作阶段定义收紧（状态 vs 动作）

9 个标签**不变**，但每条都有 `requires` / `forbidden` 成文规则
（`PHASE_EVIDENCE_RULES_V0_2`），并由 Prompt **程序生成**输出。

**针对 v0.1 的问题**：v0.1 实测 `motion_phase` 与 `gripper_state` **完全共变 (5/5)**，
说明"夹爪闭合 → grasp"的捷径被直接使用。v0.2 明写
`gripper_state=closed` **不能**推出 `motion_phase=grasp`，并新增
`GRIPPER_CLOSED_GRASP_SHORTCUT_CANDIDATE` 候选规则。

### B.3 `gripper_state` 语义

固定为**最后一张有效目标帧**的夹爪构型（不再含糊为"任意一张"）。字段未与 `object_relation` 合并（按要求保留）。

### B.4 `evidence_quality` Rubric 收紧

仍三值，但**明确只评估 `motion_phase` 的证据充分度**（事件可见性由 `event_assessment` 负责），
并新增强制一致性：明确阶段 + `partial/insufficient` → 冲突候选；
`uncertain` + `sufficient` → 冲突候选。明写"**不得**因 4 帧就自动 insufficient""不得因夹爪清晰就自动 sufficient"。

### B.5 校验器最小扩展

- **确定性结构校验**（fail-closed）：`event_assessment` 存在性/枚举/与 `events` 基数契约、
  嵌套事件证据缺失、跨段引用、引用不存在帧。
  v0.2 把 **`EVENT_ASSESSMENT_EVENTS_MISMATCH`** 与 **`EMPTY_EVIDENCE_INDICES`** 列为硬非法
  （v0.1 的判定表**未改动**）。
- **语义冲突候选**（仅标记，不改写）：`PHASE_NOTE_MOTION_CONFLICT_CANDIDATE`（分句级否定识别，
  中英双语）、`EVIDENCE_PHASE_QUALITY_CONFLICT_CANDIDATE`、`EVENT_OUTCOME_UNSUPPORTED_CANDIDATE`、
  `GRIPPER_CLOSED_GRASP_SHORTCUT_CANDIDATE`、`EVENT_ASSESSMENT_CONFLICT`，
  以及保留的 `LABEL_NOTE_CONFLICT_CANDIDATE` / `EPISODE_LEVEL_CLAIM_CANDIDATE`。

### B.6 弃权统计拆分（新模块 `semantic_reporting.py`）

**针对 v0.1 的问题**：v0.1 只报了一个 `abstention_rate`，把"动作不确定""证据不足"
"没观察到事件"混成一团。v0.2 必须分别报告：`motion_phase_uncertain_rate`、
`evidence_quality_partial_or_insufficient_rate`、`event_assessment_insufficient_evidence_rate`、
`whole_annotation_abstained_rate`、`event_visible_rate`、`events_nonempty_rate`、
`review_required_rate`，以及分布与 `closed→grasp` 共变率。
v0.1 记录的 `event_assessment` 一律标 **`NOT_APPLICABLE`**，不当作同一指标跨版本比较。

### B.7 我在本轮引入并修复的一个缺陷（v0.2 → v0.2.1）

**Run A 的 v0.2 Schema 合法率 = 0.0（0/15）**，全部为 `INVALID_MODEL_OUTPUT`。
根因**不是**模型能力，而是**我写的首版 v0.2 Prompt 漏掉了输出字段清单**：

| 现象 | 根因 |
|---|---|
| 15/15 缺 `evidence_frame_indices` | **首版 v0.2 Prompt 全文从未出现该字段名** |
| 15/15 缺 `observation_note` | 只在散文里提过，未作为必填 JSON 键列出 |
| 15/15 `object_relation` 输出成字符串 | 未声明它是**数组** |

而 Owner 冻结的 v0.2 Output Design **本来就要求这 8 个键**。
因此这是**实现与冻结契约不一致**，不是 taxonomy/schema/QC 口径的变更。

**处理方式**（遵守"看到结果后不得静默改 v0.2 口径"）：
1. **Run A 原样保留**，作为"首版 Prompt 有缺陷"的证据（run id `g3_taxonomy_v02_20261013`）。
2. 新增 **`PROMPT_V0_2_1`**：用锚点插入把**必填字段块**（由 Schema 程序生成，
   逐字段给出名称 + 类型 + 数组性）加进模板；**v0.2 模板字节不变**，其余章节逐字不动。
3. 新 run id **`..._r2`** 重跑，作为本报告主结果。
4. 新增**回归测试**锁死该缺陷：断言 v0.2.1 Prompt 必须点齐全部 8 个键，并断言 v0.2.1 只比 v0.2 多出那一段。

**Schema / 枚举 / Rubric / QC 规则在两版之间完全未变**（有单测断言）。

---

## C. 测试

| 套件 | 数量 | 结果 |
|---|---|---|
| `test_g3_semantic_json_v02_contract.py`（**新增**） | **84** | ✅ 全部通过（1 项数据集相关用例在无 h5py 环境自动 skip） |
| `test_g3_semantic_json_contract.py`（v0.1，复用未改） | 79 | ✅ 全通过 |
| `test_g3_local_vlm_probe.py`（复用未改） | 31 | ✅ 全通过 |
| **合计** | **194** | ✅ 全通过（渲染器环境下 0 skip） |

新增用例覆盖任务要求的 14 项，另加：v0.1 兼容性（含 **v0.1 Prompt template SHA 与 Schema SHA 断言不变**）、
v0.2.1 缺陷回归、报告模块的字段级比率与 `NOT_APPLICABLE` 语义。

**既有历史失败（与本轮无关，未修改任何 G1 源码）**：
`tests/test_g1_p2_privileged_leakage.py` 等此前已在 pristine `main` 上复现的失败依旧存在，
本轮**没有**触碰 `src/project2_g1` / `src/project2_mvp`。

---

## D. 三个已知案例（Run B，v0.2.1）

> 这三条属于**历史已见诊断案例**，只作开发回归，**不能**用于任何未知样本泛化或准确率声明。

### D.1 `demo_33-S0001`（4 帧首段）

| | v0.1 | v0.2 |
|---|---|---|
| `motion_phase` | `approach` | **`idle`** |
| `gripper_state` | `open` | `open` |
| `object_relation` | `["object_static"]` | `["object_static"]` |
| `event_assessment` | —（无此字段） | `no_event_visible` |
| `events` | `[]` | `[]` |
| `evidence_frame_indices` | `[0,1,3]` | **缺失** → `INVALID_MODEL_OUTPUT` |
| `evidence_quality` | `sufficient` | `sufficient` |
| QC | `VALID` | **`INVALID_MODEL_OUTPUT`**（`MISSING_REQUIRED_FIELD`） |

note（v0.2）：`机器人夹爪保持打开状态，红色罐子静止在木板上，未观察到任何动作变化。`

**变化解读**：v0.1 说"正在靠近（approach）"，v0.2 改判 **`idle` 并声明未观察到动作变化**——
在只有 4 帧、无可见变化的情况下，v0.2 的判断**更保守也更诚实**（这也是 Owner 在 Phase-1C 说"看不懂"的那两条之一）。
**但**模型仍漏掉了顶层 `evidence_frame_indices`，因此结构非法。**改进与缺陷同时存在，不可只报一半。**

### D.2 `demo_75-S0001`（4 帧首段）

与 D.1 几乎相同（`approach` → **`idle`**，`no_event_visible`），差别是它输出了
`evidence_frame_indices: []`（空数组而非缺失）→ `REVIEW_REQUIRED`
（`EVIDENCE_QUALITY_WITHOUT_CITATION`：自称 sufficient 却零引用）。

### D.3 `demo_47-S0003`（41 帧）— 本轮最有价值的单点改善

| | v0.1 | v0.2 |
|---|---|---|
| `motion_phase` | `grasp` | `grasp` |
| `object_relation` | `["gripper_around"]` | `["gripper_contact_visible"]` |
| `gripper_state` | `closed` | `closed` |
| `event_assessment` | — | **`event_visible`** |
| `events` | `[]` | **`[{grasp_attempt, unclear, [50,70,90]}]`** |
| `evidence_quality` | `sufficient` | `sufficient` |
| note | `...closed around the red can... **No motion is observed in the segment.**` | `夹爪闭合并接触物体，物体位于夹爪正下方；无明显位移或搬运迹象。` |
| QC | `VALID`（但含未捕获矛盾） | `REVIEW_REQUIRED` |

**变化解读（v0.1 的两个问题都消失了）**：
1. v0.1 在 v0.1 轮次曾输出 `event_outcome=success` 且**漏掉嵌套证据字段**；
   本轮 v0.2 输出的是 **`grasp_attempt` + `event_outcome=unclear` + 完整支持帧 `[50,70,90]`**——
   "发生性可观察、结果不确定"被正确表达，**不再无依据断言抓取成功**。
2. v0.1 的 note 写"No motion is observed"却把 `motion_phase` 定为 `grasp`（自相矛盾）；
   v0.2 note 改为"无明显位移或搬运迹象"——否定的对象是**位移**而非抓取本身，**矛盾消失**。

**但**该条被 QC 判为 `REVIEW_REQUIRED`，触发 `PHASE_NOTE_MOTION_CONFLICT_CANDIDATE`——
**这是一次误报**，见 F.2。

---

## E. 新 Development 样本（8–12 条，episode-disjoint）

### E.1 选样与冻结

- 固定盐 `P2_G3_TAXONOMY_V02_20261013`；候选池 = Development pool（181）**减去整个 12 个 Phase-1 探针 Episode** → **169**。
  这比"只排除 v0.1 用过的 10 个"**更严格**：三条诊断案例所在的 Episode 全部被排除。
- 12 个 Episode（= 配额 4 × 3 个时长层）→ 每个 Episode **恰好 1 个 Segment**
  （在 length ≥ 4 的段中按 `SHA256(盐|segment_id)` 取最小）。**全部在模型调用前冻结。**
- **未使用**：v0.1 的 10 个 Episode、诊断案例所属 Episode、正式 Held-out、任何冻结独立评估 Episode。

| # | Segment | 区间 | 长度 | Episode 时长层 | 夹爪行程 | 末端路径(m) |
|---|---|---|---|---|---|---|
| 1 | `demo_2-S0003` | [63,106] | 44 | SHORT | 0.0178 | 0.583 |
| 2 | `demo_4-S0003` | [69,136] | 68 | SHORT | 0.0110 | 0.878 |
| 3 | `demo_28-S0003` | [14,62] | 49 | SHORT | 0.0138 | 0.192 |
| 4 | `demo_180-S0001` | [0,3] | **4** | SHORT | 0.0111 | **0.005** |
| 5 | `demo_159-S0003` | [81,150] | 70 | MEDIUM | **0.0880** | 0.693 |
| 6 | `demo_169-S0002` | [4,28] | 25 | MEDIUM | 0.0181 | 0.194 |
| 7 | `demo_172-S0004` | [166,169] | **4** | MEDIUM | 0.0126 | **0.015** |
| 8 | `demo_232-S0002` | [4,49] | 46 | MEDIUM | 0.0188 | 0.265 |
| 9 | `demo_71-S0003` | [34,106] | 73 | LONG | 0.0171 | 0.193 |
| 10 | `demo_72-S0002` | [4,88] | 85 | LONG | 0.0191 | 0.363 |
| 11 | `demo_183-S0003` | [67,104] | 38 | LONG | **0.1156** | 0.131 |
| 12 | `demo_216-S0002` | [4,70] | 67 | LONG | 0.0318 | 0.406 |

覆盖：短段 2 条（含 4 帧静默段）、长段、夹爪活动最强段、高位移段、静默段。
**夹爪行程/末端路径是 proprio 派生的结构代理量，仅用于描述覆盖，从未进入模型输入，也不是事件金标。**

### E.2 配对结果（同一 RGB / 模型 / 参数 / 输出预算）

**v0.1 与 v0.2 使用同一批帧、同一模型 revision、同 `temperature=0`/`seed=1234`/`max_tokens=512`；
唯一差异是 v0.2 的指令与 Schema。**

| 指标 | v0.1 | v0.2 | 说明 |
|---|---|---|---|
| 模型请求数 | 15 | 15 | 3 诊断 + 12 新样本 |
| HTTP 200 | 15/15 | 15/15 | |
| **JSON 可解析率** | **1.000** | **1.000** | |
| **Schema 合法率（总）** | **0.9333** | **0.9333** | 各自按对应版本 Schema |
| ├ 诊断案例 3 条 | 1.000 | **0.6667** | v0.2 在这 3 条上更差（`demo_33` 漏字段） |
| └ 新样本 12 条 | 0.9167 | **1.0000** | v0.2 在**新样本**上完全合规 |
| 帧引用合法率 | 1.000 | 1.000 | |
| 非法帧引用数 | 0 | 0 | |
| 跨段引用数 | 0 | 0 | |
| **主要动作类别分布** | approach=9, grasp=6 | approach=5, grasp=6, **idle=3**, **retract=1** | v0.2 启用更多类别 |
| 声明式动作阶段比例 | 1.000 | 0.800 | |
| grasp 阶段数 | 6 | 6 | |
| closed 夹爪数 | 6 | 7 | |
| **grasp 与 closed 同时出现** | **6** | **6** | |
| **closed→grasp 共变率** | **1.000** | **0.8571** | v0.2 首次出现"closed 但不是 grasp" |
| **非空事件比例** | **0.0667** | **0.8000** | 事件层从空转变为可用 |
| `evidence_quality` 分布 | sufficient=15 | sufficient=15 | **两版都零弃权** |
| `motion_phase` uncertain 率 | 0.000 | 0.000 | |
| `evidence_quality` partial/insufficient 比例 | 0.000 | 0.000 | |
| 整条标注完全弃权率 | 0.000 | 0.000 | |
| **`event_assessment` 分布** | **NOT_APPLICABLE** | `event_visible=12, no_event_visible=3, insufficient=0` | v0.1 无此字段，**不得跨版本比较** |
| `event_visible` 比例 | NOT_APPLICABLE | 0.800 | |
| REVIEW_REQUIRED 比例 | 0.0667 | 0.4000 | v0.2 规则更严（含误报） |
| 冲突候选（CANDIDATE / DETERMINISTIC） | 2 / 1 | 4 / 4 | |
| 截断次数 | 0 | 0 | |
| 平均耗时 | 2.817 s | 4.516 s | v0.2 Prompt 长约 2.0k → 3.4k 字符 |
| 显存峰值 | 4838 MiB | 4838 MiB | |
| **人工参考符合情况** | **NOT_ESTIMABLE** | **NOT_ESTIMABLE** | 无独立人工金标 |

### E.3 事前工程门槛（两版各自判定）

| 门槛 | 阈值 | v0.1 | v0.2 |
|---|---|---|---|
| 截断输出 | ≤ 0 | 0 ✅ | 0 ✅ |
| 非法帧引用 | ≤ 0 | 0 ✅ | 0 ✅ |
| 跨段引用 | ≤ 0 | 0 ✅ | 0 ✅ |
| JSON 可解析率 | ≥ 0.90 | 1.000 ✅ | 1.000 ✅ |
| Schema 合法率 | ≥ 0.90 | 0.933 ✅ | 0.933 ✅ |
| 帧引用合法率 | ≥ 0.90 | 1.000 ✅ | 1.000 ✅ |
| Schema 非法不得判 VALID | 强制 | ✅ | ✅ |
| **`all_gates_pass`** | | **true** | **true** |

> 门槛在**任何模型调用前**写死在代码里，事后**未调整**。
> **反向披露**：Run A（首版 v0.2 Prompt）的 v0.2 Schema 合法率为 **0.0**，`all_gates_pass = false`。
> 该失败**如实保留**，未删改。

### E.4 可复现性（重要负面发现）

对 v0.1 臂在**两次独立运行**（同一 Prompt、同一参数、同 `temperature=0`、同 `seed=1234`）比较：
**15 条中 11 条逐字节相同，4 条不同**。

→ **llama.cpp CUDA 推理在本机不是逐 token 可复现的。**
这意味着：(a) 任何"重跑对比"都含采样噪声；
(b) 未来正式实验必须记录这一点，不能把单次运行的差异全部归因于 Prompt/Schema 变更。
（v0.1 轮次的一次重复曾逐字一致，说明并非总是发散；短/简单样本更稳定。）

---

## F. 语义问题分析

### F.1 是否还把"夹爪闭合"等同于"抓取"？

**部分缓解，未解决。**
- v0.1：`gripper_state` 与 `motion_phase` **完全共变（closed↔grasp 6/6 = 1.000）**，捷径明显。
- v0.2：共变率降到 **0.857**（7 次 closed 中 6 次 grasp），**首次出现"closed 但非 grasp"**。
- 但 6 个 grasp 段的 note **全部**写成"夹爪闭合并接触物体"，
  即模型仍在用**静态夹爪状态 + 接触**描述来支撑 `grasp`，
  而非描述"闭合的**变化过程**"。
- 新增的 `GRIPPER_CLOSED_GRASP_SHORTCUT_CANDIDATE` 之所以**没有触发**，
  是因为这些样本都带了 `grasp_attempt` 事件（规则设计为"有事件即不判捷径"），
  **所以该规则在本轮实际上未被有效检验**。这是规则设计的保守性，也是覆盖不足。

### F.2 事件层是否仍为空？

**显著改善。** 非空事件比例 **6.7% → 80%**（1/15 → 12/15）。
v0.2 的 `event_visible=12`、`no_event_visible=3`、`insufficient_evidence=0`。
事件类型全部是 `grasp_attempt`/`object_motion`，`event_outcome` 多为 `unclear`。

**但不能据此说"更好"**：`event_visible` 变多**本身不是优点**。
本轮**没有人工参考**判定这 12 个"可见事件"是否真的发生，因此只能说
"事件层从空转变为有内容"，**不能**说事件识别更准。
Owner Freeze 已警告："Do not force extra events to raise event rate."

### F.3 是否合理使用不确定性？

**没有。这是本轮最值得关注的负面结果。**
- `motion_phase=uncertain`：**0/15**（两版都是）
- `evidence_quality=partial|insufficient`：**0/15**（两版都是）
- `event_assessment=insufficient_evidence`：**0/15**
- 整条完全弃权：**0/15**

v0.2 Prompt 明确要求"看不清就用 uncertain / 证据不足就说证据不足"，
并在枚举/规则里完整提供了弃权通道，**模型一次都没有使用**。
对照 Phase-1C 人工把 `demo_33-S0001`、`demo_75-S0001` 评为"看不懂"，
模型对这两段仍给 `evidence_quality=sufficient`。
→ **弃权能力"存在≠会被使用"**，需要契约或事后机制，而不是继续加强措辞。

### F.4 Phase/Note 冲突规则：4 次触发**全部是误报**

`PHASE_NOTE_MOTION_CONFLICT_CANDIDATE` 在本轮触发 4 次，全部同一形态：

| Segment | phase | 命中分句 | 命中词 |
|---|---|---|---|
| `demo_47-S0003` | grasp | 无明显位移或搬运迹象 | 位移 |
| `demo_2-S0003` | grasp | 无明显位移 | 位移 |
| `demo_172-S0004` | grasp | 无明显位移 | 位移 |
| `demo_183-S0003` | grasp | 未见明显位移 | 位移 |

**根因（我的规则缺陷）**：规则把**通用运动词**（位移/移动/运动/motion）
用于**所有**明确阶段。但 `grasp` 的特征运动是**闭合**，不是位移——
"没有位移"与"是抓取阶段"**并不矛盾**。
本轮实测 **precision = 0/4**，且 v0.2 的措辞改善使历史真阳性（"No motion is observed" + grasp）**未再出现**，
所以这 4 次**全是误报**，也**没有真阳性**可供对照。

**处理方式**：按协议**不在本轮修改**（事后改规则等于用测试集调检查器）。
列为 **v0.3 候选**：否定匹配只允许针对**该阶段自己的特征动词**
（grasp↔闭合、approach↔靠近、transport/lift↔位移…），并先写合成单测。

### F.5 其它候选规则

`EVENT_OUTCOME_UNSUPPORTED_CANDIDATE`、`EVIDENCE_PHASE_QUALITY_CONFLICT_CANDIDATE`、
`GRIPPER_CLOSED_GRASP_SHORTCUT_CANDIDATE`、`EVENT_ASSESSMENT_CONFLICT` **在本轮均未触发**。
4 次确定性发现全部是 `EVIDENCE_QUALITY_WITHOUT_CITATION`
（自称 sufficient 却零引用支持帧）与 `demo_33` 的缺失字段。

### F.6 人工参考是否支持变化？

**不支持任何结论。** 已生成**盲审模板**
`evidence/P2_G3_Taxonomy_v0_2_20261013/human_reference_template.csv`（15 行），
只含 4 项人工判据（`phase_ref`、`event_assessment_ref`、`event_type_ref`、`evidence_quality_ref`），
**不含任何模型答案**。在收到独立人工参考之前：

```
SEMANTIC_ACCURACY = NOT_ESTIMABLE
EVENT_METRIC      = NOT_ESTIMABLE
```

未从 reward/done/特权字段或模型预测生成任何"人工金标"。

---

## G. GitHub 交付

**分支**：`p2-g3-taxonomy-v02-baseline-20261013`（未合并 `main`）

### G.0 版本哈希（本轮冻结口径）

| 对象 | 版本字符串 | SHA-256 |
|---|---|---|
| Prompt v0.1（未改） | `P2_G3_ARGUS_INSPIRED_PROMPT_V0_1_CANDIDATE` | `5a50475e590cce38923feb829e58971ea7d9a51303c4b8169f1251e671c79cb8` |
| Schema v0.1（未改） | `P2_G3_SEMANTIC_JSON_V0_1_CANDIDATE` | `b37d8c15711488a9cd14e7ec002175484af01616694f5ef1b0673084944e3978` |
| **Prompt v0.2**（首版，含缺陷，Run A 使用） | `P2_G3_ARGUS_INSPIRED_PROMPT_V0_2_CANDIDATE` | **`9806d014408806233473cec0603df9e2da0f390e5ec16a2aefd86031e56ba486`** |
| **Prompt v0.2.1**（修复版，Run B 主结果） | `P2_G3_ARGUS_INSPIRED_PROMPT_V0_2_1_CANDIDATE` | **`11b874a3daba9d42398a50bef8473c01924a672f06acda09e0ac3933110e53b4`** |
| **Schema v0.2**（两版 Prompt 共用） | `P2_G3_SEMANTIC_JSON_V0_2_CANDIDATE` | **`4cbec780693511c6e029a1fc005a7c523e5af7ea6a4ba127c7b9fc44253d0ad7`** |

> 上表 Schema v0.2 SHA-256 取自运行目录 `run_manifest.json` 的 `schema_sha256.v0_2`（由运行器在**调用前**计算并记录），
> 不是人工填写。每道题实际使用的 Prompt（含该段帧身份表）在 `sample_manifest.csv` 与逐条请求记录中登记 `prompt_sha256`。
> Prompt 文件位于 `0-doc/10-design-review/P2_G3_Semantic_Prompt_v0_2_20261013.txt` 与 `..._v0_2_1_20261013.txt`。

### G.1 新增 / 修改
- `src/project2_g3/semantic_schema.py`（**追加** v0.2 枚举/Schema/规则/护栏）
- `src/project2_g3/semantic_validation.py`（**追加** v0.2 校验器与状态判定）
- `src/project2_g3/semantic_prompt.py`（**追加** v0.2 与 v0.2.1 模板）
- `src/project2_g3/semantic_reporting.py`（**新增**：字段级比率、配对表、门槛）
- `src/project2_g3/dev_segments.py`（**追加** v0.2 episode-disjoint 选样）
- `scripts/run_g3_taxonomy_v02_paired.py`（**新增**配对运行器）
- `tests/test_g3_semantic_json_v02_contract.py`（**新增** 84 项）
- v0.1 的 10 个文件按 SHA 定向复用（未改字节）
- 文档：本报告、Prompt v0.2 与 v0.2.1 文件、Schema v0.2 JSON、样本 Manifest、
  配对结果、QC Findings、原始回复与哈希、人工参考模板、候选 Schema

**未提交**：模型权重、原始 RGB、本地缓存、敏感路径、凭据。
证据为脱敏副本（本地路径 → `<LOCAL_ROOT>`），本地原件与哈希映射保留在运行目录。

**未完成 / 需 Owner 决策**：
1. **v0.3 候选规则修正**：`PHASE_NOTE` 改为阶段专属动词匹配（本轮实测 4/4 误报）。
2. **弃权机制**：0/15 弃权是否可接受？是否改为强约束输出或事后复核触发？
3. `object_relation` 与 `gripper_state` 是否合并（本轮按要求未合并）。
4. 事件层"变多"是否需要人工参考支撑才能叫改善（当前 `NOT_ESTIMABLE`）。
5. 正式 8B、Held-out、Vision-only vs Vision+State A/B、人工金标 rubric。
6. `PROMPT_V0_2`（缺陷版）是否需要在后续文档中标记为已弃用而非保留可选。

---

## 人话回答

**1. v0.2 相比 v0.1 真正改善了什么？**
两件是实打实的：**①事件层活过来了**——v0.1 里 15 条只有 1 条有内容
（因为"事件是否发生"没法表达，模型干脆全填空），v0.2 变成 12/15 有明确事件，
而且事件自带目标段帧号；**②"说没有运动却断言抓取"这种自相矛盾消失了**——
`demo_47` 从"没有观察到运动 + 抓取成功"变成"夹爪闭合接触物体 + 尝试抓取、结果不明"，
这正是规范想要的行为。另外在两条 4 帧短段上，模型从"正在靠近"改判成
**"静止、未观察到动作变化"**，比 v0.1 更保守也更诚实。

**2. 哪些只是 JSON 格式改善，哪些才可能是动作理解改善？**
**只是格式/契约层面的**：`event_assessment` 字段本身、事件基数契约、
`evidence_frame_indices` 必填、`object_relation` 必须是数组、
报告里那些拆分后的弃权比率。这些让结果**可机器核验**，但不代表模型看得更懂。
**才可能是动作理解层面的**（要注意：仍无人工金标，只能说"可能"）：
`idle` 类别被真正启用（说明模型不再强行给一个动作）、
`closed→grasp` 共变率从 1.000 降到 0.857、以及 `demo_47` 那处矛盾的消失。
**唯一能确定的**是：v0.2 在**新样本 12 条上 Schema 100% 合规**，
但这是"会不会按格式答"，不是"答得对不对"。

**3. 4B 目前最值得关注的错误是什么？**
**三个，按严重度排序**：
①**从不弃权**——15 条里 `uncertain`、`partial/insufficient`、`insufficient_evidence`
**一次都没出现**，全说"证据充分"，连人在 Phase-1C 说看不懂的 4 帧段也说充分。
这是最要命的：一个从不承认不确定的标注器没法用于筛选。
②**仍在用静态状态代替动作**——6 个 grasp 段的说明**全是**"夹爪闭合并接触物体"，
描述的是**某一刻的样子**，不是"闭合的过程"，v0.2 想根治的捷径其实还在。
③**我加的检查规则本身不可靠**——`PHASE_NOTE` 4 次触发**全是误报**
（把"没有位移"当成否定"抓取"），本轮既没真阳性也没帮上忙。
另外附带一个工程事实：**同参数重跑不是逐字一致的**（15 条里 4 条不同），
以后做对比不能把差异全算到 Prompt 头上。

**4. 是否具备进入正式 8B 实验设计的条件？**
**具备"设计"条件，但不具备"直接开跑"条件。**
具备的：输出契约已可机验、配对流程与门槛已跑通、诊断案例与 12 条新样本已冻结、
证据与哈希可追溯。缺的三件必须 Owner 先定：
**弃权机制**（现在等于没有）、**taxonomy 里 grasp 的"过程 vs 状态"到底怎么判**、
**人工金标 rubric**（没有它，8B 跑出来也只能得 `NOT_ESTIMABLE`）。
在这三件定下来之前跑 8B，只会得到"格式合规率"这一个数字。

**5. 哪些项目只需 Owner 决策、不需要继续开发？**
- **弃权机制选型**：强约束输出契约 vs 事后触发复核 —— 纯决策。
- **`object_relation` 与 `gripper_state` 是否合并** —— 本轮按要求没合并，是纯决策。
- **`PHASE_NOTE` 规则是否按阶段专属动词收紧** —— 方向已明确，只需批准，改动很小。
- **`demo_33/75` 这两条 4 帧段**：人看不懂、模型说充分——
  到底算"该弃权"还是"本来就该标 idle"，需要 Owner 给口径。
- **`PROMPT_V0_2`（缺陷版）的处置**：标为弃用还是继续保留可选。
- **正式 8B 的 checkpoint 与 Vision-only / Vision+State 的 A/B 设计** —— 纯决策。

---

## 停止点

本轮到此停止：**未**运行正式 8B、**未**训练 ACT/VLA、**未**改动冻结数据、
**未**运行 Held-out、**未**改动 RGB 分辨率契约、**未**把 v0.2 提升为正式 Taxonomy v1、
**未**合并 `main`。
