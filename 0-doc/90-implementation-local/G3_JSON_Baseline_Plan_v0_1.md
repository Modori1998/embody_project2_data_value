# G3 — Tiny JSON Baseline 计划 v0.1（2026-10-13）

> **状态**：`PLAN_V0_1`，事前登记（pre-registered）。
> **性质**：**小样本工程可行性基线**。不是正式语义准确率评测。
> **实现**：`scripts/run_g3_json_tiny_baseline.py`

---

## 1. 本轮要回答什么（以及不回答什么）

**回答**：
1. 冻结的输出架构（单 JSON + 受控枚举 + 短 note + 帧级证据 + 确定性校验）
   在**真实机器人 RGB** 上，用本地 4B 是否**跑得通**？
2. JSON 可解析率、Schema 合法率、帧级证据合法率各是多少？
3. 跨段证据误引是否被程序拦住？
4. 哪些字段/枚举在真实使用中**退化**（信息量接近零）？
5. 模型是否会诚实弃权？

**不回答**：
- 动作识别**准确率**——本轮**没有人工语义金标**，任何"准确率"都是造假。
- 正式 Held-out 表现。
- 8B 的表现。
- taxonomy 是否应当冻结。

> **硬约束**：本轮所有指标**不得**被称为"动作识别准确率"。

---

## 2. 样本选择（只用事前结构信息）

### 2.1 三层来源

1. **Development pool** = 可读数据集 Episode
   − 历史 G1 使用（exploratory / calibration / design diagnostic）
   − **24** 个冻结 G1 Evaluation Episode
   − **63** 个冻结 Core Retrieval Episode（36 候选库 + 9 校准 + 18 终局）
   实测：数据集 300 → Development pool **181**。
   选择不查任何 query / 候选 / 人工标签 / embedding / 检索分数。
2. **Phase-1 probe 12 Episode**：在 Development pool 上按 frame_count 三分位分层，
   层内按 `SHA256("P2_G3_PHASE1_PROBE_20261012"|episode_id)` 排序取前 4。
   实测复现得到与前轮完全一致的 12 个 Episode
   （`demo_155, 33, 24, 47, 120, 227, 196, 165, 74, 277, 292, 75`）。
3. **Pinned 10 Segment**：沿用 Phase-1C 轻量审核的固定盐
   `P2_G3_PHASE1C_SIMPLE10_20261013_V1` 在 59 段上的确定性选样。
   该选样**只用结构字段 + SHA256 排序**，**没有**按图片观感或模型输出挑选。

### 2.2 固定的 10 条样本

| # | Segment | 区间 | 长度 | 分层 |
|---|---|---|---|---|
| 1 | `demo_120-S0005` | [174, 177] | 4 | SHORT \| LAST \| INCOMPLETE |
| 2 | `demo_165-S0003` | [82, 164] | 83 | NORMAL \| INTERIOR \| COMPLETE |
| 3 | `demo_196-S0002` | [4, 39] | 36 | NORMAL \| INTERIOR \| COMPLETE |
| 4 | `demo_227-S0005` | [77, 145] | 69 | NORMAL \| INTERIOR \| COMPLETE |
| 5 | `demo_277-S0005` | [219, 223] | 5 | SHORT \| LAST \| INCOMPLETE |
| 6 | `demo_292-S0002` | [4, 74] | 71 | NORMAL \| INTERIOR \| COMPLETE |
| 7 | `demo_33-S0001` | [0, 3] | 4 | SHORT \| FIRST \| INCOMPLETE |
| 8 | `demo_47-S0003` | [50, 90] | 41 | NORMAL \| INTERIOR \| COMPLETE |
| 9 | `demo_74-S0003` | [113, 129] | 17 | NORMAL \| INTERIOR \| COMPLETE |
| 10 | `demo_75-S0001` | [0, 3] | 4 | SHORT \| FIRST \| INCOMPLETE |

覆盖：**10 个不同 Episode**（每段来自不同 Episode）、短段 4 / 普通段 6、
首段 2 / 末段 2 / 内部 6、双侧邻段完整 6 / 缺一侧 4。

**Segment 身份不信任常量**：运行时会用**冻结 G1 引擎 + 冻结配置**
（`A1-007-C002`、`τ_P12`、`τ_C12`、`window=8`）对每个 Episode **重新计算**分段，
逐条比对 `segment_id` 与 `[start, end]`；不一致则 `STOP_PINNED_SEGMENT_INTERVAL_CHANGED`
直接停机，绝不静默换段。实测 10/10 与冻结区间一致。

### 2.3 与 Phase-1C 人工结果的关系（重要）

Phase-1C 的 10 条人工回答是**可理解性自评**
（"只看目标段原图，人能看懂动作吗？"），
**不是语义金标**。因此：

- 本轮**不**用它们计算任何准确率；
- 本轮**不**以它们为分母；
- 只可用于事后观察"人工说看不清的段，模型是否也表现出不确定"
  （本轮观察见结果报告，属描述性说明，不是正确率）。

---

## 3. 固定配置（推理前锁定）

| 项 | 值 |
|---|---|
| 模型 | `Qwen/Qwen3-VL-4B-Instruct-GGUF` @ `1cd86afb9a95c410a6038ab3b40d8b578c892266` |
| LLM 文件 / SHA-256 | `Qwen3VL-4B-Instruct-Q4_K_M.gguf` / `66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a` |
| mmproj 文件 / SHA-256 | `mmproj-Qwen3VL-4B-Instruct-F16.gguf` / `256f3a43bd4205ffef48d6b92715e1e70b5b0e9aef06522584967513a9985331` |
| 引擎 | llama.cpp b11577（`0.6.0-dev`, commit `cbe28bb3c`），CUDA 12.4 构建 |
| 服务参数 | `-ngl 99 -c 4096 -np 1 --host 127.0.0.1 --port 8080 --no-webui --jinja --temp 0 --seed 1234` |
| 输入策略 | **`TARGET_KEYFRAMES_ONLY`**（M2 START/MIDDLE/END，含 GRIPPER_EVENT 去重） |
| `temperature` | **0.0** |
| `seed` | **1234** |
| `max_tokens` | **512**（先按 512 设，实测 `finish_reason` 全为 `stop`，无截断） |
| `response_format` | `{"type": "json_object"}`（不施加语法约束，以检验 Prompt 本身） |
| 并发 | 单请求、无并行 |
| Schema 版本 | `P2_G3_SEMANTIC_JSON_V0_1_CANDIDATE` |
| Prompt 版本 | `P2_G3_ARGUS_INSPIRED_PROMPT_V0_1_CANDIDATE` |
| Prompt template SHA-256 | `5a50475e590cce38923feb829e58971ea7d9a51303c4b8169f1251e671c79cb8` |
| 逐样本 Prompt SHA-256 | 登记在 `sample_manifest.csv` / `model_requests.jsonl` |

**RGB 合法性**：每帧由**冻结 Renderer** 按原帧索引重新渲染
（`MODEL_RGB[t] = render(STATE_t)`，`MUJOCO_GL=wgl`），
128×128、`overlay_applied=false`、`audit_mp4_used=false`、
`lossy_video_roundtrip=false`，并记录 `pixel_sha256`。
**未**使用 A/B 拼图、带标注面板、审核 MP4 或裁剪图。
**未**修改 RGB Contract。

---

## 4. 事前登记的工程门槛

门槛在**看到任何模型输出之前**写死在 `run_g3_json_tiny_baseline.py::GATES`：

| 门槛 | 阈值 | 性质 |
|---|---|---|
| `illegal_model_inputs` | **≤ 0** | 输入必须合法（fail closed） |
| `json_parse_rate` | **≥ 0.90** | 接口可用性 |
| `schema_valid_rate` | **≥ 0.90** | 结构契约 |
| `frame_evidence_valid_rate` | **≥ 0.90** | 证据可核验 |
| `truncated_outputs` | **≤ 0** | 不得把截断当短答案 |
| `detected_cross_boundary_references` | 必须全部被标记 | 见下 |

**关于"零未拦截的跨段事件"**：程序能证明的是
"所有被**引用**的越界帧都被标记"；
**不能**证明"note 里用文字描述的邻段事件"一定被发现。
因此该门槛只登记"实际被标记的跨段引用数"，
并在报告里明确这一检测上限，**不得**宣称跨段误归因已解决。

**门槛不做事后调整**：未达标即如实报告失败，不修改口径。

---

## 5. 统计口径（分子 / 分母）

分母 = **已发起的模型请求数**（`model_requests_attempted`）。
`PROCESSING_ERROR`（传输失败）单独计数，**不**计入"模型出错"，
也**不**把流水线故障算作机器人示范质量差。

| 指标 | 定义 |
|---|---|
| `http_200_rate` | HTTP 200 数 / 请求数 |
| `json_parse_rate` | 可解析为 JSON 对象数 / 请求数 |
| `schema_valid_rate` | 结构合法数 / 请求数 |
| `frame_evidence_valid_rate` | 引用全部合法数 / 请求数 |
| `cross_boundary_reference_count` | 被标记的跨段引用总条数 |
| `invalid_frame_reference_count` | 引用不存在 / 越区间帧总条数 |
| `truncated_output_count` | `finish_reason=length` 数 |
| `abstained_count` / `abstention_rate` | 实质字段全部弃权的样本数 / 比例 |
| `mean_wall_seconds`、`mean_completion_tokens` | 延迟与输出规模 |
| `peak_vram_used_mib` | 每次调用后读 `nvidia-smi` 的最大值（含常驻模型，非增量） |
| `qc_status_counts` | 各 QC 状态样本数 |
| `finding_counts_by_check` / `by_scope` | 各检查项触发次数；`DETERMINISTIC` vs `CANDIDATE` |

---

## 6. 可选边界回归（不进入主分母）

对上一轮出现问题的 `demo_47-S0003` 额外做一次对照：

| 变体 | 输入 |
|---|---|
| `target_only` | 目标段关键帧 50 / 70 / 90（3 张） |
| `target_plus_neighbour` | 邻段上下文 49（PREV_END）/ 91（NEXT_START）/ 94（NEXT_MID）+ 目标段 50 / 70 / 90（6 张） |

两变体使用**同一模型、同一 Schema、同一 Prompt 模板**，
差别只在**明确标识的不同输入 Manifest**
（每帧登记 `role` / `origin_segment_id` / `is_target_segment_frame`）。

检查：程序是否发现邻段帧被错误引用（`TARGET_CONTEXT_CROSS_BOUNDARY`）。

**约束**：该结果**不并入** 10 条主基线的成功率分母；
**且不得**因单次未发现问题就宣称跨段误归因已解决。

---

## 7. 产出物

```
outputs/p2_g3_json_tiny_baseline/<run_id>/
  run_manifest.json                  运行身份、模型/提示/模式版本、门槛
  candidate_schema.json              本次使用的 JSON Schema
  sample_manifest.csv                10 条固定样本 + 帧哈希 + 逐样本 Prompt SHA
  frame_manifest.jsonl               每帧身份（合法模型输入清单）
  model_requests.jsonl               调用方可信身份 + 请求哈希
  raw_model_responses.jsonl          原始回复（不可变）+ 回复哈希
  structured_segment_labels.jsonl    解析后的标注 + QC 状态
  label_qc_findings.jsonl            每条发现
  annotation_review_queue.csv        复核队列（training_disposition=NOT_EVALUATED）
  baseline_summary.json              统计与门槛判定
  boundary_regression/…              可选边界回归（独立目录）
```

**不提交 Git**：模型权重、原始 RGB、大批渲染图、凭据。
提交的是**脱敏**证据副本（本地路径替换为 `<LOCAL_ROOT>`），
本地原件与哈希映射保留在运行目录。

---

## 8. 停止条件（本轮）

完成即停：GitHub main 同步 → Prompt/Schema/校验器实现 → 测试通过 →
10 条真实推理完成 → 报告与小型证据上开发分支。

**不**进入：正式 Held-out 评测、8B 运行、高分辨率契约变更、ACT 训练，
**也不**把 v0.1 自动冻结为正式 Taxonomy v1。
