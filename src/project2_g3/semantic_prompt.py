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
