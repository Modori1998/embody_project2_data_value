# G3F Phase–Event Prompt Design (v0.2.2 candidate) — 2026-10-14

Base main: `05228ce2dfe5cb8a759b1b3d7431359ad296c5da`.

## 1. Principle: minimal targeted change

* `PROMPT_TEMPLATE_V0_2_1` is **not touched**. Its SHA-256 stays
  `11b874a3daba9d42398a50bef8473c01924a672f06acda09e0ac3933110e53b4`, which is
  also the value frozen in the G3D2 manifest.
* New version: `P2_G3_ARGUS_INSPIRED_PROMPT_V0_2_2_CANDIDATE`, built from the
  v0.2.1 template by two anchored replacements, so the diff is auditable.
* Unchanged: the model, the RGB inputs, Segment identity, the JSON Schema, the
  `motion_phase` enum, the `event_type` enum, the per-phase evidence rules, the
  event trigger rules, the evidence-quality rubric, the required-field block and
  all sampling parameters.

| | v0.2.1 | v0.2.2 |
|---|---|---|
| version string | `P2_G3_ARGUS_INSPIRED_PROMPT_V0_2_1_CANDIDATE` | `P2_G3_ARGUS_INSPIRED_PROMPT_V0_2_2_CANDIDATE` |
| template SHA-256 | `11b874a3…0e53b4` | `61ac6bcea3a67a92b6dbd3a3d55209f990ad09f147aba84cb4b8b1cf892c4702` |
| schema | v0.2 (unchanged) | v0.2 (unchanged) |

## 2. Change 1 — remove the conflicting sentence, state the coherence rule

Removed (exactly one line):

> `- 长距离的连续搬运可能确实 \`events=[]\`；**不要**为了凑事件率而编造事件。`

Replaced by:

> - motion_phase 表示整个 Segment 的主要可见动作阶段，events[] 表示该 Segment 内所有有视觉证据支持的事件。二者独立判断，但必须保持语义一致。
> - 如果可比目标帧明确显示物体发生可分辨位移，无论发生在 lift、transport、place 或其他阶段，都应输出 object_motion。
> - 对于持续搬运，如果物体随夹爪移动的视觉证据充分，应同时满足 motion_phase=transport 与 events[] 包含 object_motion。
> - 持续搬运不要求当前 Segment 内重新发生 grasp_attempt 或 release_attempt。这些事件只有在当前 Segment 中观察到相应局部变化过程时才输出。
> - EEF 位移或夹爪 CLOSED 状态本身不能证明物体移动。如果物体位移不可观察，不得仅凭机器人状态输出 object_motion，也不得缺乏相应视觉证据而确认 transport。
> - `lift` 若由可见物体上移证据支持，应有 `object_motion`。
> - `object_motion` 不要求主阶段一定是 transport。
> - 抓取阶段也可能存在物体移动。
> - approach 期间意外碰动物体，也可能存在 object_motion。
> - 事件可以跨不同时间区间发生，不应由单一主导 Phase 排除其他事件。

This keeps the anti-hallucination intent ("不要为了凑事件率而编造事件" is
replaced by the explicit "如证据不足，应修正不受支持的判断，而不是编造事件")
while removing the licence to omit a schema-entailed event.

## 3. Change 2 — short pre-output self-check

Inserted immediately before `# 8. observation_note`:

> `# 7.1 输出前一致性自检`
> 在输出最终 JSON 前，核对 motion_phase、object_relation、events[] 和 observation_note 是否与同一组视觉证据一致。如果判断为 transport/lift，检查是否存在相应的可见物体位移以及 object_motion 事件；如证据不足，应修正不受支持的判断，而不是编造事件。

No chain-of-thought is requested and no new JSON field is added.

## 4. Full diff (v0.2.1 → v0.2.2)

```diff
@@ section 5 (events) @@
 - 单张静止的 `closed` 夹爪**不是** `grasp_attempt`；仅仅几张看起来相近的静止画面也不够。
-- 长距离的连续搬运可能确实 `events=[]`；**不要**为了凑事件率而编造事件。
+- motion_phase 表示整个 Segment 的主要可见动作阶段，events[] 表示该 Segment 内所有有视觉证据支持的事件。二者独立判断，但必须保持语义一致。
+- 如果可比目标帧明确显示物体发生可分辨位移，无论发生在 lift、transport、place 或其他阶段，都应输出 object_motion。
+- 对于持续搬运，如果物体随夹爪移动的视觉证据充分，应同时满足 motion_phase=transport 与 events[] 包含 object_motion。
+- 持续搬运不要求当前 Segment 内重新发生 grasp_attempt 或 release_attempt。这些事件只有在当前 Segment 中观察到相应局部变化过程时才输出。
+- EEF 位移或夹爪 CLOSED 状态本身不能证明物体移动。如果物体位移不可观察，不得仅凭机器人状态输出 object_motion，也不得缺乏相应视觉证据而确认 transport。
+- `lift` 若由可见物体上移证据支持，应有 `object_motion`。
+- `object_motion` 不要求主阶段一定是 transport。
+- 抓取阶段也可能存在物体移动。
+- approach 期间意外碰动物体，也可能存在 object_motion。
+- 事件可以跨不同时间区间发生，不应由单一主导 Phase 排除其他事件。
 - `object_motion` 只表示物体发生了可分辨位移，**不得**由此推断任务成功或失败。
@@ before section 8 @@
+# 7.1 输出前一致性自检
+在输出最终 JSON 前，核对 motion_phase、object_relation、events[] 和 observation_note 是否与同一组视觉证据一致。如果判断为 transport/lift，检查是否存在相应的可见物体位移以及 object_motion 事件；如证据不足，应修正不受支持的判断，而不是编造事件。
+
 # 8. observation_note
```

The machine-readable diff is `semantic_prompt.template_diff_v0_2_1_v0_2_2()`;
the versioned artifact is `template_file_content_v0_2_2()`.

## 5. No known-answer leakage

* The replacement text is generic. It names no Segment, no object, no frame
  index and no correct event set.
* It deliberately does **not** say "demo_2/4/159 have object_motion".
* The audit (`G3F_Phase_Event_Conflict_Audit.md`) is written after the prompt is
  frozen and is not fed back into the prompt.

## 6. Traceability

`tests/test_g3f_phase_event.py` asserts that v0.2.1 is byte-identical to the
frozen SHA, that the carry sentence is gone from v0.2.2, that the self-check is
present, and that every required key and enum value still survives through the
schema-generated blocks.
