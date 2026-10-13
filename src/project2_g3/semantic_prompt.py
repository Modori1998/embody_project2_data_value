"""P2-G3 Argus-inspired P2 prompt v0.1 (CANDIDATE, versioned, hashed).

What is borrowed from Argus (``Pantheon-Industries-Inc/argus`` @
``ccfd313f18d9981ba3ad2868d7f7d8bc3ecb7629``, ``label/prompts.py``)
-------------------------------------------------------------------------
* **JSON-only interface**: Argus says "Return ONLY JSON with this shape" and the
  harness additionally sends ``response_format={"type":"json_object"}``.  P2
  keeps both.
* **Controlled enums for categorical fields + free text only where genuinely
  free**: Argus fixes ``arm`` (left/right/both), ``contribution``
  (advancing/wasteful/idle), ``outcome`` (success/failure/unclear),
  ``severity`` (low/medium/high), ``deliberate`` (yes/no/unclear); it keeps
  object ``name``/``attributes``, timeline ``action``, ``notes``,
  ``task_summary``, ``performance_review`` free-form and says explicitly
  "There is no fixed vocabulary".
* **Explicit abstention**: Argus uses ``unclear`` for
  ``outcome``/``completion``/``deliberate`` and instructs "Only claim what the
  frames show; when unsure, say so in notes rather than guessing".
* **Evidence discipline**: "Times in start_s/end_s must be drawn from the frame
  timestamps you were given"; ``state_changes`` records physical results, not
  motions; "List only relations you can actually see".
* **Local vs global separation**: Argus separates per-step ``progress`` /
  ``contribution`` from whole-episode ``completion``, and requires
  ``success_predicate`` to be judged globally.

What P2 deliberately drops, and why
-----------------------------------
=========================  ==================================================
Argus construct            Why P2 v0.1 drops it
=========================  ==================================================
``timeline`` (multi-phase)  P2's unit is ONE frozen G1 segment; a timeline of
                            phases would invite re-segmentation, which is
                            forbidden.
``progress`` 0..1,          Needs the whole video in view. The model sees a few
``contribution``            keyframes and cannot know the absolute task level.
``completion`` /            Episode-level. A handful of segment keyframes cannot
``success_predicate``       support any task-completion claim.
``goal_reached_at_s`` /     Episode-level timing; not observable from a segment.
``completed_at_s``
``state_changes``           Needs before/after views of the same object; a
                            3-keyframe segment cannot establish it reliably.
``scene_graph``             Not needed for the v0.1 label and adds hallucination
                            surface.
``recovery``                Requires cross-segment linkage and episode scope.
``instruction_variants``    A data-augmentation artifact, not an annotation of
                            the segment under view.
``performance_review``      Episode-level execution quality; explicitly a
                            non-goal for G3 v1 labels.
``data_issues`` /           Dataset-quality tagging; separate concern from
``operator_mistakes``       segment semantics.
absolute ``t_s`` floats     P2 uses the frozen ``frame_index`` identity from the
                            G1/M2 contract instead of free-floating times.
``arm`` left/right          P2 Can/MH single-arm: the field carries no
                            information and only adds a wrong-value surface.
=========================  ==================================================
"""

from __future__ import annotations

import hashlib
from typing import Any, Sequence

from . import semantic_schema as S

SEMANTIC_PROMPT_VERSION = "P2_G3_ARGUS_INSPIRED_PROMPT_V0_1_CANDIDATE"

DEFAULT_TASK_TEXT = "pick up the can and place it into the correct box"

#: Placeholders: ``{task_text}``, ``{source_episode_id}``, ``{segment_id}``,
#: ``{start_frame}``, ``{end_frame}``, ``{frame_table}``, ``{enums}``.
PROMPT_TEMPLATE = """你是一个机器人示范的语义标注助手。你只标注一个**已经冻结的机器人动作 Segment**。

# 1. 任务
- 任务背景：{task_text}
- 目标 Episode：{source_episode_id}
- 目标 Segment：{segment_id}，冻结帧区间为 [{start_frame}, {end_frame}]（含两端）。
- 你不能重新定义 Segment 边界。分段已经由上游冻结，你只描述这个区间内**可见**的行为。

# 2. 输入证据
- 你会收到一组按时间顺序排列的真实机器人 RGB 画面（Clean RGB，无文字标注、无 Overlay）。
- 每张图的身份如下，顺序与图像顺序严格一致：

{frame_table}

- 只有"是否目标段帧 = 是"的图，才属于你要标注的 Segment。
- 若某张图的"是否目标段帧 = 否"，它属于相邻 Segment，**只是上下文**。

# 3. 只输出一个 JSON 对象
只返回**一个合法 JSON 对象**。不要 Markdown 代码围栏，不要解释，不要 JSON 之外的任何文字。

{enums}

字段说明：
- motion_phase：该 Segment 主要的可见动作阶段（单选）。
- object_relation：夹爪与目标物体的可见关系（可多选，至少一项）。
- gripper_state：**只能**描述夹爪本身的开合构型，不能代表物体是否被抓住。
- events：该 Segment 内候选事件（可以为空数组 []）。
- evidence_frame_indices：支持你整体判断的目标段帧号。
- evidence_quality：你获得的画面是否足以支撑上述判断。
- observation_note：一到两句，只写**可见事实**与不确定之处。

# 4. 证据与不确定性规则
- 任何**肯定性**判断都必须给出支持帧；支持帧只能引用上表中"是否目标段帧 = 是"的帧。
- 看不清时必须使用 uncertain / unclear / insufficient，不要猜。
- 如果没有观察到事件，events 可以是 []，或使用 event_type = "none_observed"。
- 不确定的字段请明确标注证据不足，而不是给出一个猜测值。

# 5. 严格禁止
- 不得把相邻 Segment 的事件写成当前 Segment 内发生的事件。
- 不得推断接触力、抓取是否成功、物体是否滑落、任务是否完成、精确接触时刻。
- 不得描述输入图像没有展示的完整 Episode 动作。
- 不得使用模拟器特权字段（reward / done / object GT / simulator states）。
- 不得声称任务级别完成；单个 Segment 不足以判断任务成败。
- 不得把"夹爪闭合"等同于"已经抓住"，也不得把"没看到物体运动"等同于"抓取失败"。
"""


def render_enum_block() -> str:
    """Render the enum section straight from the schema (single source of truth)."""

    lines: list[str] = ["候选取值（必须严格使用其中之一的拼写）："]
    for key, label in (
        ("motion_phase", "motion_phase"),
        ("object_relation", "object_relation"),
        ("gripper_state", "gripper_state"),
        ("event_type", "events[].event_type"),
        ("event_outcome", "events[].event_outcome"),
        ("evidence_quality", "evidence_quality"),
    ):
        values = ", ".join(f'"{v}"' for v in S.ENUM_TABLE[key])
        lines.append(f"- {label}: {values}")
    return "\n".join(lines)


def render_frame_table(frames: Sequence[Any]) -> str:
    """Markdown table pairing every image with its trusted frame identity.

    ``frames`` items expose ``frame_index``, ``role``, ``source_episode_id``,
    ``origin_segment_id`` and ``is_target_segment_frame``.
    """

    rows = [
        "| 图像顺序 | frame_index | role | source_episode_id | origin_segment_id | 是否目标段帧 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for position, entry in enumerate(frames, 1):
        is_target = getattr(entry, "is_target_segment_frame", None)
        if is_target is None and isinstance(entry, dict):
            is_target = entry.get("is_target_segment_frame")
        target_flag = "是" if is_target else "否"
        rows.append(
            f"| {position} | {getattr(entry, 'frame_index', entry.get('frame_index') if isinstance(entry, dict) else '?')} "
            f"| {getattr(entry, 'role', entry.get('role') if isinstance(entry, dict) else '?')} "
            f"| {getattr(entry, 'source_episode_id', entry.get('source_episode_id') if isinstance(entry, dict) else '?')} "
            f"| {getattr(entry, 'origin_segment_id', entry.get('origin_segment_id') if isinstance(entry, dict) else '?')} "
            f"| {target_flag} |"
        )
    return "\n".join(rows)


def render_prompt(
    *,
    source_episode_id: str,
    segment_id: str,
    start_frame: int,
    end_frame: int,
    frames: Sequence[Any],
    task_text: str = DEFAULT_TASK_TEXT,
) -> str:
    """Return the exact prompt string for one segment request."""

    return PROMPT_TEMPLATE.format(
        task_text=task_text,
        source_episode_id=source_episode_id,
        segment_id=segment_id,
        start_frame=int(start_frame),
        end_frame=int(end_frame),
        frame_table=render_frame_table(frames),
        enums=render_enum_block(),
    )


def prompt_sha256(text: str) -> str:
    """SHA-256 over the exact UTF-8 bytes of a rendered prompt."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def template_sha256() -> str:
    """SHA-256 of the versioned template file content."""

    return prompt_sha256(PROMPT_TEMPLATE)


def template_file_content() -> str:
    """Content of the versioned prompt artifact committed to the repo."""

    header = (
        f"# {SEMANTIC_PROMPT_VERSION}\n"
        f"# schema_version: {S.SEMANTIC_SCHEMA_VERSION}\n"
        "# status: CANDIDATE_V0_1_NOT_OWNER_FROZEN\n"
        "#\n"
        "# Upstream reference: Pantheon-Industries-Inc/argus @\n"
        "#   ccfd313f18d9981ba3ad2868d7f7d8bc3ecb7629  label/prompts.py\n"
        "# This is an independently authored P2-specific prompt. It borrows the\n"
        "# JSON-only interface, controlled-enum + short-note split and explicit\n"
        "# abstention pattern; it is NOT a copy of the Argus episode prompt.\n"
        "#\n"
        "# Placeholders: {task_text} {source_episode_id} {segment_id}\n"
        "#               {start_frame} {end_frame} {frame_table} {enums}\n"
        "#\n"
        "# The sha256 below is over PROMPT_TEMPLATE as embedded in\n"
        "# src/project2_g3/semantic_prompt.py, i.e. this file minus these\n"
        "# leading '#' comment lines.\n"
        f"# prompt_template_sha256: {template_sha256()}\n"
        "\n"
    )
    return header + PROMPT_TEMPLATE


# =========================================================================== #
# v0.2 prompt (Owner-frozen development spec, 2026-10-13)
#
# The v0.1 template above is untouched.  v0.2 adds the state-vs-action
# distinction, per-phase observable-evidence rules, the event_assessment /
# events relationship, and the three-level evidence_quality rubric.  The
# rule/enum text is generated from `semantic_schema` so the prompt cannot drift
# from the frozen spec.
# =========================================================================== #

SEMANTIC_PROMPT_VERSION_V0_2 = "P2_G3_ARGUS_INSPIRED_PROMPT_V0_2_CANDIDATE"

#: v0.2.1 is a **defect fix to the prompt only**.
#:
#: The first v0.2 prompt implementation (``PROMPT_TEMPLATE_V0_2``) descriptive
#: prose replaced the v0.1 per-field block and, as a result, never named the
#: ``evidence_frame_indices`` top-level key, never said ``object_relation`` is an
#: array, and never stated ``observation_note`` is required.  All 15 real v0.2
#: outputs of the first run therefore omitted one or more mandatory keys.
#:
#: The Owner-frozen v0.2 Output Design already mandates those eight keys, so
#: this is a correction of the *implementation* to match the frozen contract ---
#: not a change to the taxonomy, the schema, the enums or any QC rule.  The
#: first run is preserved under its own run id and is never rewritten; the fixed
#: prompt runs under a new version tag and a new run id.
SEMANTIC_PROMPT_VERSION_V0_2_1 = "P2_G3_ARGUS_INSPIRED_PROMPT_V0_2_1_CANDIDATE"


def render_required_fields_v0_2() -> str:
    """Explicit required-key block, generated from the frozen schema.

    Types and cardinality are stated so the model cannot infer a subset.  This
    is the block whose absence caused the first v0.2 run to drop mandatory keys.
    """

    schema = S.json_schema_v0_2()
    props = schema["properties"]
    lines: list[str] = []
    for key in S.MODEL_OWNED_FIELDS_V0_2:
        spec = props[key]
        kind = spec.get("type")
        if kind == "array":
            item_type = (spec.get("items") or {}).get("type")
            if item_type == "object":
                nested = ", ".join(f'"{n}"' for n in spec["items"]["required"])
                lines.append(
                    f'- `{key}`：对象数组，元素必须包含 {nested}；'
                    "其中 `evidence_frame_indices` 是整数数组（至少一个目标段帧号）。"
                )
            else:
                minimum = spec.get("minItems", 0)
                required = "至少一项" if minimum else "可为空数组"
                lines.append(f'- `{key}`：**{item_type} 数组**（{required}）。')
        else:
            enum = spec.get("enum")
            if enum:
                values = ", ".join(f'"{v}"' for v in enum)
                lines.append(f'- `{key}`：字符串，取值 {values}。')
            else:
                lines.append(f'- `{key}`：字符串（一到两句可见事实）。')
    lines.append("")
    lines.append(
        "请按上述字段名与类型完整输出；不要省略任何字段，"
        "不要把数组字段写成字符串。"
    )
    return "\n".join(lines)


def render_prompt_v0_2_1(
    *,
    source_episode_id: str,
    segment_id: str,
    start_frame: int,
    end_frame: int,
    frames: Sequence[Any],
    task_text: str = DEFAULT_TASK_TEXT,
) -> str:
    """Return the exact v0.2.1 prompt string for one segment request."""

    return PROMPT_TEMPLATE_V0_2_1.format(
        task_text=task_text,
        source_episode_id=source_episode_id,
        segment_id=segment_id,
        start_frame=int(start_frame),
        end_frame=int(end_frame),
        frame_table=render_frame_table(frames),
        enums=render_enum_block_v0_2(),
        required_fields=render_required_fields_v0_2(),
        phase_rules=render_phase_rules_v0_2(),
        event_rules=render_event_rules_v0_2(),
        rubric=render_rubric_v0_2(),
    )


def template_sha256_v0_2_1() -> str:
    return prompt_sha256(PROMPT_TEMPLATE_V0_2_1)


def template_file_content_v0_2_1() -> str:
    header = (
        f"# {SEMANTIC_PROMPT_VERSION_V0_2_1}\n"
        f"# schema_version: {S.SEMANTIC_SCHEMA_VERSION_V0_2}\n"
        "# status: V0_2_1_PROMPT_DEFECT_FIX (schema/taxonomy/QC unchanged)\n"
        "#\n"
        "# Supersedes the prompt *implementation* of\n"
        f"#   {SEMANTIC_PROMPT_VERSION_V0_2}\n"
        "# which failed to name the `evidence_frame_indices` top-level key and\n"
        "# the array/required nature of `object_relation` and `observation_note`.\n"
        "# The frozen Owner schema already mandated all eight keys; no taxonomy,\n"
        "# enum, evidence-rubric or QC rule was changed.  The first v0.2 run is\n"
        "# preserved unchanged under its own run id.\n"
        "#\n"
        f"# prompt_template_sha256: {template_sha256_v0_2_1()}\n"
        "\n"
    )
    return header + PROMPT_TEMPLATE_V0_2_1

PROMPT_TEMPLATE_V0_2 = """你是一个机器人示范的语义标注助手。你只标注一个**已经冻结的机器人动作 Segment**。

# 0. 最重要的一点：状态 vs 动作
- **状态**是某个采样瞬间夹爪/物体看起来的构型。
- **动作**是跨多个有序采样可观察到的**变化/过程**。
- `gripper_state=closed` **不能**推出 `motion_phase=grasp`：闭合也可能是在持物、搬运或静止。
- `grasp` 只是**尝试阶段**，永远不是“已经成功获取”的证明。
- 任何单个瞬间的状态，都不足以支撑一个动作阶段判断。

# 1. 任务
- 任务背景：{task_text}
- 目标 Episode：{source_episode_id}
- 目标 Segment：{segment_id}，冻结帧区间为 [{start_frame}, {end_frame}]（含两端）。
- 你不能重新定义 Segment 边界。分段已由上游冻结，你只描述该区间内**可见**的行为。

# 2. 输入证据
- 你会收到一组按时间顺序排列的真实机器人 RGB 画面（Clean RGB，无文字标注、无 Overlay）。
- 每张图的身份如下，顺序与图像顺序严格一致：

{frame_table}

- 只有“是否目标段帧 = 是”的图，才属于你要标注的 Segment。
- 若某张图的“是否目标段帧 = 否”，它属于相邻 Segment，**只是上下文**，不得当作目标段证据。
- `gripper_state` 描述的是**最后一张有效目标帧**里的夹爪构型（不是任意一张，也不是之前某张更清晰的帧）。

# 3. 只输出一个 JSON 对象
只返回**一个合法 JSON 对象**。不要 Markdown 代码围栏，不要解释，不要 JSON 之外的任何文字。

{enums}

# 4. motion_phase 的可观察条件（逐条执行）
{phase_rules}

# 5. events 与 event_assessment
- `event_assessment` 回答“**事件是否可被观察到**”，只能三选一：
  - `event_visible`：提供的目标帧支持至少一个可具体命名的事件。此时 `events` **必须非空**，且每个事件都要带目标段帧引用。
  - `no_event_visible`：**在采样的目标帧里没有观察到**任何事件。此时 `events` **必须为 `[]`**。
    这**不等于**“确定没有发生”——未采样区间仍然未知。
  - `insufficient_evidence`：给定画面无法可靠判断事件是否发生。此时 `events` **必须为 `[]`**，并在 note 里说明限制。
- 具体事件的触发条件：
{event_rules}
- 事件**发生**了但**结果**不知道时：`event_assessment=event_visible`，`event_outcome=unclear`。
  “事件是否发生不确定”和“事件结果不确定”是两件事，不要混。
- 单张静止的 `closed` 夹爪**不是** `grasp_attempt`；仅仅几张看起来相近的静止画面也不够。
- 长距离的连续搬运可能确实 `events=[]`；**不要**为了凑事件率而编造事件。
- `object_motion` 只表示物体发生了可分辨位移，**不得**由此推断任务成功或失败。
- 本响应中**没有** Episode 级任务结果字段，也不要写。

# 6. evidence_quality 的三级标准（只针对 motion_phase）
{rubric}
- 一致性要求：若 `motion_phase` 是明确阶段，而 `evidence_quality` 是 `partial`/`insufficient`，
  这在本规范下是**冲突候选**，除非能具体说明理由。
- **不要**因为 Segment 只有 4 帧就自动给 `insufficient`：请判断**可见变化**，不是帧数。
- **不要**因为夹爪清晰可见就自动给 `sufficient`。

# 7. 严格禁止
- 不得把相邻 Segment 的事件写成当前 Segment 内发生的事件。
- 不得推断接触力、抓取成功、释放成功、物体滑落、任务是否完成、精确接触时刻。
- 不得描述输入图像没有展示的完整 Episode 动作。
- 不得使用模拟器特权字段（reward / done / object GT / simulator states）。
- 不得把“夹爪闭合”等同于“已经抓住”。
- 不得把“没看到物体运动”理解为“确定没有发生”。
- 不得重新定义 Segment 边界。

# 8. observation_note
一到两句，只写**可观察事实**与不确定之处。它不是第二套分类，不要复述枚举字段。
"""


#: Anchor present in the frozen v0.2 template, used to insert the required-field
#: block without editing ``PROMPT_TEMPLATE_V0_2`` itself.
_V02_ANCHOR = "# 4. motion_phase 的可观察条件（逐条执行）"

#: v0.2.1 template = frozen v0.2 template + an explicit required-key block.
#: Built by anchored insertion so the v0.2 bytes stay untouched and the diff is
#: auditable in one line.
PROMPT_TEMPLATE_V0_2_1 = PROMPT_TEMPLATE_V0_2.replace(
    _V02_ANCHOR,
    "# 3.1 输出必须包含的顶层字段（缺一不可，缺任何一个都算非法输出）\n"
    "{required_fields}\n\n" + _V02_ANCHOR,
    1,
)


def render_enum_block_v0_2() -> str:
    """Render the v0.2 enum section from the frozen schema."""

    lines: list[str] = ["候选取值（必须严格使用其中之一的拼写）："]
    for key, label in (
        ("motion_phase", "motion_phase"),
        ("object_relation", "object_relation"),
        ("gripper_state", "gripper_state"),
        ("event_assessment", "event_assessment"),
        ("event_type", "events[].event_type"),
        ("event_outcome", "events[].event_outcome"),
        ("evidence_quality", "evidence_quality"),
    ):
        values = ", ".join(f'"{v}"' for v in S.ENUM_TABLE_V0_2[key])
        lines.append(f"- {label}: {values}")
    lines.append(
        "- 注意：events[].event_type 在 v0.2 只有上述三个实质类型；"
        "旧版的 none_observed / uncertain 已移到 event_assessment，不要再使用。"
    )
    return "\n".join(lines)


def render_phase_rules_v0_2() -> str:
    lines: list[str] = []
    for phase in S.MOTION_PHASE_V0_2:
        rule = S.PHASE_EVIDENCE_RULES_V0_2[phase]
        lines.append(f"- `{phase}`（{rule['zh']}）：需要 {rule['requires']}；禁止 {rule['forbidden']}。")
    return "\n".join(lines)


def render_event_rules_v0_2() -> str:
    return "\n".join(
        f"  - `{name}`：{text}" for name, text in S.EVENT_TRIGGER_RULES_V0_2.items()
    )


def render_rubric_v0_2() -> str:
    return "\n".join(
        f"- `{name}`：{text}" for name, text in S.EVIDENCE_QUALITY_RUBRIC_V0_2.items()
    )


def render_prompt_v0_2(
    *,
    source_episode_id: str,
    segment_id: str,
    start_frame: int,
    end_frame: int,
    frames: Sequence[Any],
    task_text: str = DEFAULT_TASK_TEXT,
) -> str:
    """Return the exact v0.2 prompt string for one segment request."""

    return PROMPT_TEMPLATE_V0_2.format(
        task_text=task_text,
        source_episode_id=source_episode_id,
        segment_id=segment_id,
        start_frame=int(start_frame),
        end_frame=int(end_frame),
        frame_table=render_frame_table(frames),
        enums=render_enum_block_v0_2(),
        phase_rules=render_phase_rules_v0_2(),
        event_rules=render_event_rules_v0_2(),
        rubric=render_rubric_v0_2(),
    )


def template_sha256_v0_2() -> str:
    return prompt_sha256(PROMPT_TEMPLATE_V0_2)


def template_file_content_v0_2() -> str:
    header = (
        f"# {SEMANTIC_PROMPT_VERSION_V0_2}\n"
        f"# schema_version: {S.SEMANTIC_SCHEMA_VERSION_V0_2}\n"
        "# status: V0_2_DEV_SPEC_OWNER_APPROVED_FROZEN_FOR_IMPLEMENTATION\n"
        "#\n"
        "# Frozen sources:\n"
        "#   0-doc/10-design-review/P2_G3_Taxonomy_v0_2_Design_Owner_Freeze_20261013.md\n"
        "#   0-doc/10-design-review/P2_G3_Evidence_Rubric_v0_2_Plan_Owner_Freeze_20261013.md\n"
        "#   0-doc/10-design-review/P2_G3_Semantic_JSON_v0_2_Output_Design_Owner_Freeze_20261013.md\n"
        "#\n"
        "# Upstream reference: Pantheon-Industries-Inc/argus @\n"
        "#   ccfd313f18d9981ba3ad2868d7f7d8bc3ecb7629  label/prompts.py\n"
        "# Independently authored P2-specific prompt; not a copy of the Argus\n"
        "# episode prompt.  The v0.1 template is preserved separately in\n"
        "# P2_G3_Semantic_Prompt_v0_1_20261013.txt and is NOT overwritten.\n"
        "#\n"
        "# Placeholders: {task_text} {source_episode_id} {segment_id}\n"
        "#   {start_frame} {end_frame} {frame_table} {enums}\n"
        "#   {phase_rules} {event_rules} {rubric}\n"
        "#\n"
        "# The sha256 below is over PROMPT_TEMPLATE_V0_2 as embedded in\n"
        "# src/project2_g3/semantic_prompt.py, i.e. this file minus these\n"
        "# leading '#' comment lines.  The enum / phase-rule / event-rule /\n"
        "# rubric blocks are generated at render time from semantic_schema.\n"
        f"# prompt_template_sha256: {template_sha256_v0_2()}\n"
        "\n"
    )
    return header + PROMPT_TEMPLATE_V0_2
