# G3 — 候选结构化 JSON 输出设计 v0.1（2026-10-13）

> **状态**：`SCHEMA_V0_1 = CANDIDATE_IMPLEMENTED_NOT_OWNER_FROZEN`
> **版本号**：`P2_G3_SEMANTIC_JSON_V0_1_CANDIDATE`
> **冻结边界**：Owner 已冻结**输出架构**
> （`G3_OUTPUT_ARCHITECTURE=FROZEN_JSON_ENUM_NOTE_FRAME_EVIDENCE_QC_V1`）；
> **本文的字段、枚举取值与基数是候选提案，尚未冻结。**
> **实现**：`src/project2_g3/semantic_schema.py`、`semantic_validation.py`

---

## 1. 模型自有的最小载荷（v0.1 候选）

```json
{
  "motion_phase": "transport",
  "object_relation": ["moving_with_gripper"],
  "gripper_state": "uncertain",
  "events": [
    {
      "event_type": "object_motion",
      "event_outcome": "unclear",
      "evidence_frame_indices": [70, 90]
    }
  ],
  "evidence_frame_indices": [50, 70, 90],
  "evidence_quality": "partial",
  "observation_note": "物体似乎随夹爪移动，接触点被遮挡，无法确认是否已夹住。"
}
```

> 这是**形状示意**，不是真实模型结果，也不是冻结示例。
> 真实结果见 `evidence/P2_G3_JSON_Tiny_Baseline_20261013/`。

`additionalProperties: false` 在**每一层**生效（含 `events[]` 元素）。

## 2. 字段与候选枚举

| 字段 | 类型 | 必填 | 候选取值 | 语义边界（不得越界解读） |
|---|---|---|---|---|
| `motion_phase` | string | ✅ | `approach` `grasp` `lift` `transport` `place` `retract` `idle` `other` `uncertain` | `grasp` 是**行为类别**，**不代表抓取成功** |
| `object_relation` | string[] (≥1, 去重) | ✅ | `gripper_around` `gripper_contact_visible` `moving_with_gripper` `object_static` `object_not_visible` `uncertain` | `gripper_around` 仅指夹爪在视觉上环绕物体；**不**断言接触、力或已握住 |
| `gripper_state` | string | ✅ | `open` `closed` `partially_open` `uncertain` | **只**描述夹爪构型；`closed` **绝不**等于 `holding` 或任务成功 |
| `events` | object[] | ✅（可为空数组） | 元素见下 | 允许 `[]`；`none_observed` 是合法观察 |
| `events[].event_type` | string | ✅ | `grasp_attempt` `release_attempt` `object_motion` `none_observed` `uncertain` | "尝试"≠"成功" |
| `events[].event_outcome` | string | ✅ | `success` `failure` `unclear` | **局部**结果，**不得**提升为 Episode 级任务结果 |
| `events[].evidence_frame_indices` | int[] (≥1) | ✅ | 目标段帧号 | 必须来自该段；不得引用邻段帧 |
| `evidence_frame_indices` | int[] | ✅（可与空） | 目标段帧号 | 整体判断的支持帧 |
| `evidence_quality` | string | ✅ | `sufficient` `partial` `insufficient` | 描述"画面是否够用"，不是置信度 |
| `observation_note` | string (1..400 字符) | ✅ | 自由文本 | 一到两句**可见事实 + 不确定处**；**不是**第二套分类 |

### 2.1 弃权值（机器可读登记）

```python
ABSTENTION_VALUES = {
  "motion_phase":     ("uncertain",),
  "object_relation":  ("uncertain",),
  "gripper_state":    ("uncertain",),
  "event_type":       ("uncertain", "none_observed"),
  "event_outcome":    ("unclear",),
  "evidence_quality": ("insufficient", "partial"),
}
```

当 `motion_phase`、`gripper_state` 与 `object_relation` **全部**取弃权值时，
判定为 `UNRESOLVED`——这是一种**诚实的弃权**，不是错误。

## 3. 调用方注入的可信身份（模型不得提供）

```python
CALLER_OWNED_FIELDS = (
  "schema_version", "run_id", "source_episode_id", "segment_id",
  "segment_interval_frames", "prompt_sha256", "model_revision",
  "evidence_pack_sha256",
)
```

模型若输出这些字段 → `CALLER_OWNED_FIELD_IN_MODEL_OUTPUT` → `INVALID_MODEL_OUTPUT`。
依据 Owner Freeze："`segment_id` is intentionally **not** model-owned"。

## 4. 语义护栏（写进代码，不只是文档）

| 护栏 | 落地方式 |
|---|---|
| `grasp` 阶段 ≠ 成功抓取 | 枚举注释 + Prompt 明示 + `candidate_taxonomy()["semantic_guards"]` |
| `gripper_state=closed` ≠ `holding` | 同上；`events[].event_outcome` 不得由 `gripper_state` 推导 |
| 没看到物体运动 ≠ 抓取失败 | Prompt 明示；`none_observed` 合法 |
| 单段不能判断任务成败 | 无 `completion` 字段；note 出现任务级措辞 → `EPISODE_LEVEL_CLAIM_CANDIDATE` |
| 看不清必须允许 `uncertain` | 每个分类字段都有弃权值 |
| 未观察到事件时 `events` 可为 `[]` | 结构允许；空数组不报错 |
| 肯定判断必须给支持帧 | `events[].evidence_frame_indices` 必填且 ≥1 |
| note 不是第二套标签 | note 只做观察说明；与枚举矛盾 → `LABEL_NOTE_CONFLICT_CANDIDATE` |

## 5. 校验状态机

```
PROCESSING_ERROR        传输/服务失败，或不可用回复（不是数据质量问题！）
INVALID_INPUT           调用前请求本身非法（fail closed，不发起模型调用）
INVALID_MODEL_OUTPUT    不可解析 / Schema 非法 / 引用不存在的帧 / 跨段引用 / 截断
REVIEW_REQUIRED         结构合法但带复核候选
UNRESOLVED              结构合法、无候选、模型在实质字段上诚实弃权
VALID                   结构合法、无候选、无弃权
```

**判定优先级**：`PROCESSING_ERROR → INVALID_MODEL_OUTPUT → REVIEW_REQUIRED → UNRESOLVED → VALID`

### 5.1 检查清单

**A. JSON / Schema（`DETERMINISTIC`，fail-closed）**
`JSON_UNPARSEABLE`、`JSON_NOT_AN_OBJECT`、`OUTPUT_TRUNCATED`
（含 `finish_reason=length`）、`MARKDOWN_FENCE_WRAPPER`、
`MISSING_REQUIRED_FIELD`、`WRONG_TYPE`、`ILLEGAL_ENUM`、
`FORBIDDEN_EXTRA_FIELD`、`CALLER_OWNED_FIELD_IN_MODEL_OUTPUT`、
`EMPTY_OBJECT_RELATION`、`DUPLICATE_ENUM_VALUE`、`EMPTY_EVIDENCE_INDICES`、
`NOTE_TOO_LONG`、`EMPTY_NOTE`

**B. 帧级证据（`DETERMINISTIC`，fail-closed）**
`EMPTY_FRAME_MANIFEST`、`DUPLICATE_FRAME_IN_MANIFEST`、
`FRAME_SOURCE_EPISODE_MISMATCH`、`FRAME_TARGET_SEGMENT_MISMATCH`、
`FRAME_PIXEL_SHA_INVALID`、`TARGET_FRAME_OUTSIDE_INTERVAL`、
`FRAME_NOT_IN_REQUEST_MANIFEST`、`FRAME_OUTSIDE_TARGET_SEGMENT`、
**`TARGET_CONTEXT_CROSS_BOUNDARY`**（把邻段上下文帧当作目标段事件证据）

**C. 标注自洽（`CANDIDATE`，交人工）**
`LABEL_NOTE_CONFLICT_CANDIDATE`、`EPISODE_LEVEL_CLAIM_CANDIDATE`、
`PHASE_EVENT_CONFLICT_CANDIDATE`、`EVENT_NONE_OBSERVED_MIXED_CANDIDATE`、
`EVENT_RELATION_CONFLICT_CANDIDATE`、`EVIDENCE_SUFFICIENCY_CANDIDATE`
（断言确定性结果但支持帧 < 2，无法体现事件前后变化）、
`EVIDENCE_QUALITY_WITHOUT_CITATION`

### 5.2 为什么 B 与 C 必须分开

程序**可以**证明"N 号帧是否属于目标段"——这是清单比对，是确定性的。
程序**不能**仅凭帧号证明"模型看到的语义是对的"。
因此：

- 引用越界 → `DETERMINISTIC`，fail-closed，自动索引不可用；
- 语义矛盾（note 说张开、字段说 closed）→ `CANDIDATE`，
  只标记、**不选边、不改写**，交人工复核。

**校验器从不修改模型原始答案**：原始回复在解释之前就以不可变形式落盘
（`raw_model_responses.jsonl` + `raw_response_sha256`），
`label_qc_findings.jsonl` 只记录发现。

### 5.3 已知覆盖缺口（本轮实测发现，未回填）

`demo_47-S0003` 的输出里，`observation_note` 写
"No motion is observed in the segment"，同时
`motion_phase=grasp` 且 `events[0].event_outcome=success`。
这构成**语义矛盾**，但 v0.1 检查器**没有**对应规则（现有
`EVENT_RELATION_CONFLICT_CANDIDATE` 只覆盖 `moving_with_gripper` 情形）。

**处理方式**：如实记录为"检查器未覆盖的矛盾"，
**不在看到结果后临时新增规则**（那等于用测试集调检查器）。
建议 v0.2 增加 `OUTCOME_CONTRADICTS_OBSERVED_MOTION_CANDIDATE` 规则，
并需先以合成用例单测。

## 6. 复核队列与下游

`annotation_review_queue.csv` 每条记录：
`annotation_review_status`、`review_reasons`、
`candidate_finding_count`、`deterministic_finding_count`、
`cross_boundary_references`、`invalid_references`、
**`training_disposition = NOT_EVALUATED`**（G3 v1 全程固定）。

**没有** `AUTO_ACCEPT → KEEP` 映射。语义候选标记 ≠ 训练数据取舍决定。
`PROCESSING_ERROR` / `INVALID_INPUT` 是流水线故障，
**绝不**记为"机器人示范质量差"。

## 7. v0.1 未冻结项（须 Owner 另行决定）

1. `motion_phase` 取值是否需要拆分状态与阶段（v0.1 实测被当状态用）。
2. `object_relation` 是否与 `gripper_state` 合并（语义重叠）。
3. `events` 若持续为空，是否保留该字段。
4. `object_relation` / `events` 的基数与 null 语义。
5. `gripper_state` 是否留在主 MVP（Owner Freeze 已列为待定）。
6. 是否需要"物体可见性 / 遮挡"独立字段以支撑 `evidence_quality`。
7. 各类 `CANDIDATE` 规则的具体严重度与人工裁决流程。
8. 是否需要 `not_semantically_labelable` 之类的段级豁免状态。
9. 正式 8B checkpoint、Vision-only vs Vision+State A/B、人工金标与 Held-out。
