"""Presentation-layer vocabulary for G1 Audit Web. Stored codes stay English."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

LOGGER = logging.getLogger("g1_audit_web_ui_vocab")
UNKNOWN_UI_LABEL = "UNKNOWN_CODE"


@dataclass(frozen=True)
class VocabTerm:
    code: str
    zh: str
    en: str
    description_zh: str
    kind: str = "system"


UI_VOCABULARY: dict[str, VocabTerm] = {
    "ALL": VocabTerm("ALL", "全部", "All", "显示当前 Run 的全部 Episode。"),
    "NOT_REVIEWED": VocabTerm("NOT_REVIEWED", "未审核", "Not reviewed", "尚未填写人工审核。"),
    "IN_PROGRESS": VocabTerm("IN_PROGRESS", "审核中", "In progress", "已有部分 Signal 或 Boundary 审核。"),
    "REVIEWED": VocabTerm("REVIEWED", "已审完", "Reviewed", "六项 Signal 与全部预测 Final Boundary 均已审核。"),
    "SIGNAL_FAIL": VocabTerm("SIGNAL_FAIL", "Signal 失败", "Signal fail", "任一 P1 Signal Review 为 FAIL。"),
    "HAS_REDUNDANT": VocabTerm("HAS_REDUNDANT", "含冗余边界", "Has redundant", "存在人工标记为 REDUNDANT 的预测边界。"),
    "HAS_MISALIGNED": VocabTerm("HAS_MISALIGNED", "含偏移边界", "Has misaligned", "存在人工标记为 MISALIGNED 的预测边界。"),
    "HAS_MISSED": VocabTerm("HAS_MISSED", "含漏检补充", "Has missed", "存在人工补充的漏掉边界。"),
    "REVIEW_REQUIRED": VocabTerm("REVIEW_REQUIRED", "需要人工复核", "Review required", "manifest 标记需要人工复核。"),
    "PASS": VocabTerm("PASS", "通过", "Pass", "该项 Signal 与视频/证据一致。"),
    "FAIL": VocabTerm("FAIL", "失败", "Fail", "该项 Signal 与视频/证据不一致。"),
    "UNCERTAIN": VocabTerm("UNCERTAIN", "不确定", "Uncertain", "人工无法确定该项 Signal。"),
    "TRANSLATION": VocabTerm("TRANSLATION", "末端平移", "Translation", "末端平移 / 速度是否与视频中的实际运动对应。"),
    "DIRECTION": VocabTerm("DIRECTION", "主方向变化", "Direction", "主要运动方向变化证据是否与真实轨迹变化一致。"),
    "GRIPPER": VocabTerm("GRIPPER", "夹爪", "Gripper", "实际夹爪状态 / 控制指令变化是否与视频对应。"),
    "ROTATION": VocabTerm("ROTATION", "末端旋转", "Rotation", "末端姿态变化证据是否合理。"),
    "ACTION": VocabTerm("ACTION", "控制指令", "Action", "控制指令变化是否存在明显异常或时间错位。"),
    "VIDEO_ALIGNMENT": VocabTerm("VIDEO_ALIGNMENT", "视频对齐", "Video alignment", "视频与所有 Signal 是否位于同一 frame / timestep 时间轴。"),
    "REUSED_SIGNAL_REVIEW": VocabTerm("REUSED_SIGNAL_REVIEW", "复用历史 Signal 审核", "Reused signal review", "相同 episode_id 与相同 signal contract 下复用历史 P1 审核。"),
    "REDUNDANT_SHORT_PAUSE": VocabTerm("REDUNDANT_SHORT_PAUSE", "短暂停造成的冗余切分", "Redundant short pause", "短暂停造成的冗余切分。"),
    "REDUNDANT_DIRECTION_JITTER": VocabTerm("REDUNDANT_DIRECTION_JITTER", "方向抖动 / 微调造成的冗余切分", "Redundant direction jitter", "方向抖动或微调造成的冗余切分。"),
    "REDUNDANT_ROTATION": VocabTerm("REDUNDANT_ROTATION", "旋转证据造成的冗余判断", "Redundant rotation", "旋转证据造成的冗余判断。"),
    "REDUNDANT_ACTION_JITTER": VocabTerm("REDUNDANT_ACTION_JITTER", "控制指令抖动造成的冗余判断", "Redundant action jitter", "控制指令抖动造成的冗余判断。"),
    "MISALIGNED_GRIPPER": VocabTerm("MISALIGNED_GRIPPER", "夹爪边界位置偏移", "Misaligned gripper", "夹爪边界位置偏移。"),
    "MISALIGNED_MOTION_CHANGE": VocabTerm("MISALIGNED_MOTION_CHANGE", "运动变化边界位置偏移", "Misaligned motion change", "运动变化边界位置偏移。"),
    "MISSED_GRIPPER_TRANSITION": VocabTerm("MISSED_GRIPPER_TRANSITION", "漏检夹爪切换", "Missed gripper transition", "漏检夹爪切换。"),
    "MISSED_MOVE_STOP": VocabTerm("MISSED_MOVE_STOP", "漏检运动→静止", "Missed move to stop", "漏检运动转入静止。"),
    "MISSED_STOP_MOVE": VocabTerm("MISSED_STOP_MOVE", "漏检静止→运动", "Missed stop to move", "漏检静止转入运动。"),
    "MISSED_DIRECTION_CHANGE": VocabTerm("MISSED_DIRECTION_CHANGE", "漏检主方向变化", "Missed direction change", "漏检主要方向变化。"),
    "OTHER": VocabTerm("OTHER", "其他", "Other", "其他原因，需填写 comment。"),
    "EXPLORATORY_AUDIT": VocabTerm("EXPLORATORY_AUDIT", "探索审核", "Exploratory audit", "用于形成第一批 Human GT。"),
    "CALIBRATION": VocabTerm("CALIBRATION", "校准集运行", "Calibration", "正式 Calibration Set Run；具体用途由 calibration_role 标明，不等于已经调参。"),
    "EVALUATION": VocabTerm("EVALUATION", "独立评测", "Evaluation", "Final Config Freeze 后运行，不得继续调参。"),
    "DESIGN_DIAGNOSTIC": VocabTerm(
        "DESIGN_DIAGNOSTIC",
        "设计诊断",
        "Design diagnostic",
        # Reviewer-facing tooltip. Deliberately free of any diagnostic-design
        # token (see the blinding contract in trajectory_diagnostic_run.py).
        "Design Diagnostic｜设计诊断，只用于设计机制盲审。可人工审核，但不得进入 Calibration Export、Canonical GT 或 Evaluation。",
    ),
    "DESIGN_DIAGNOSTIC_ONLY": VocabTerm(
        "DESIGN_DIAGNOSTIC_ONLY",
        "仅用于机制诊断",
        "Design diagnostic only",
        "该 Run 只用于设计机制诊断，不可作为 GT、不可用于阈值选择、不进入正式 Detector 输入。",
    ),
    "EXPLORATORY_ONLY": VocabTerm("EXPLORATORY_ONLY", "探索性切分", "Exploratory only", "当前切分未校准、未冻结。"),
    "THRESHOLD_NOT_FROZEN": VocabTerm("THRESHOLD_NOT_FROZEN", "阈值未冻结", "Threshold not frozen", "当前 threshold 只是探索默认值。"),
    "NO_TUNING": VocabTerm("NO_TUNING", "禁止继续调参", "No tuning", "Evaluation Run 不得回灌 Calibration。"),
    "EXPLORATORY": VocabTerm("EXPLORATORY", "探索集", "Exploratory set", "set_role = EXPLORATORY。"),
    "BASELINE_HUMAN_AUDIT": VocabTerm("BASELINE_HUMAN_AUDIT", "基线人工审核", "Baseline human audit", "使用未修改 baseline 生成 P1/P2 证据，供正式人工审核。"),
    "BASELINE_UNMODIFIED": VocabTerm("BASELINE_UNMODIFIED", "基线未修改", "Baseline unmodified", "Detector 与 Signal 参数和 Exploratory baseline 完全相同。"),
    "NOT_STARTED": VocabTerm("NOT_STARTED", "尚未开始", "Not started", "该流程尚未开始。"),
    "CLOSED": VocabTerm("CLOSED", "关闭", "Closed", "Calibration Search Gate 关闭。"),
    "AUTO_REGISTERED": VocabTerm("AUTO_REGISTERED", "自动登记", "Auto registered", "Contract PASS 后自动写入 Registry。"),
    "MANUAL_ADDED": VocabTerm("MANUAL_ADDED", "手工新增", "Manual added", "Design Owner 手工加入。"),
    "MANUAL_OVERRIDE": VocabTerm("MANUAL_OVERRIDE", "手工覆盖路径", "Manual override", "Owner 覆盖了 Registry 路径。"),
    "DISABLED_BY_OWNER": VocabTerm("DISABLED_BY_OWNER", "Owner 停用", "Disabled by owner", "恢复前不可打开。"),
    "GRIPPER_TRANSITION": VocabTerm("GRIPPER_TRANSITION", "夹爪切换", "Gripper transition", "夹爪开合状态切换候选。"),
    "MOVE_TO_IDLE": VocabTerm("MOVE_TO_IDLE", "运动→静止", "Move to idle", "运动转入静止。"),
    "IDLE_TO_MOVE": VocabTerm("IDLE_TO_MOVE", "静止→运动", "Idle to move", "静止转入运动。"),
    "DIRECTION_CHANGE": VocabTerm("DIRECTION_CHANGE", "主方向变化", "Direction change", "主要运动方向变化。"),
    "KEEP": VocabTerm("KEEP", "保留", "Keep", "候选作为最终边界保留。"),
    "RETAIN_HARD": VocabTerm("RETAIN_HARD", "强边界保护保留", "Retain hard", "Hard Boundary 受保护，不得因短片段规则删除。"),
    "MERGE_CONSOLIDATION": VocabTerm("MERGE_CONSOLIDATION", "合并为同一边界事件", "Merge consolidation", "邻近候选合并为同一物理过渡。"),
    "MERGE_LEFT": VocabTerm("MERGE_LEFT", "向左邻合并", "Merge left", "并入左侧邻近边界。"),
    "MERGE_RIGHT": VocabTerm("MERGE_RIGHT", "向右邻合并", "Merge right", "并入右侧邻近边界。"),
    "SUPPRESS_DEBOUNCE": VocabTerm("SUPPRESS_DEBOUNCE", "去抖抑制", "Suppress debounce", "同类型重复候选被去抖抑制。"),
    "SUPPRESS_SHORT_PAUSE": VocabTerm("SUPPRESS_SHORT_PAUSE", "短暂停桥接抑制", "Suppress short pause", "短暂停被桥接，不单独成界。"),
    "SHORT_SEGMENT_CANDIDATE": VocabTerm("SHORT_SEGMENT_CANDIDATE", "短片段候选", "Short segment candidate", "片段短于 min_segment_length。"),
    "VALID": VocabTerm("VALID", "有效边界", "Valid", "人工确认该预测边界有效。"),
    "REDUNDANT": VocabTerm("REDUNDANT", "冗余边界", "Redundant", "人工认为该预测边界多余。"),
    "MISALIGNED": VocabTerm("MISALIGNED", "边界位置偏移", "Misaligned", "边界存在但帧位置需要校正。"),
    "MISSED_BOUNDARY": VocabTerm("MISSED_BOUNDARY", "漏检边界", "Missed boundary", "需要人工补充的漏掉边界。"),
    "BETTER": VocabTerm("BETTER", "较好", "Better", "质量分组 BETTER。"),
    "OKAY": VocabTerm("OKAY", "一般", "Okay", "质量分组 OKAY。"),
    "WORSE": VocabTerm("WORSE", "较差", "Worse", "质量分组 WORSE。"),
    "video": VocabTerm("video", "Episode 视频", "Episode video", "当前 Episode 的 RGB 视频。"),
    "signal_boundary_plot": VocabTerm(
        "signal_boundary_plot",
        "Signal Boundary 图",
        "Signal boundary plot",
        "主审核图：Candidate / Suppressed / Final Boundary overlay。",
    ),
    "signal_plot": VocabTerm("signal_plot", "P1 Signal 图", "P1 signal plot", "无 Boundary overlay 的 P1 主 Signal 图。"),
}


SIGNAL_AUDIT_QUESTIONS = {
    "TRANSLATION": "视频里机器人移动、减速、停止时，这些 Signal 是否有对应变化？",
    "DIRECTION": "主要运动方向明显变化时，Direction Signal 是否有合理响应？",
    "GRIPPER": "视频里夹爪开闭时，Gripper Signal 是否对应变化？",
    "ROTATION": "末端姿态明显旋转时，Rotation Signal 是否有合理响应？",
    "ACTION": "Action Signal 是否存在明显异常、错位或不合理跳变？",
    "VIDEO_ALIGNMENT": "Video 与所有 Signal 是否存在整体时间错位？",
}


@dataclass(frozen=True)
class SignalReviewGuide:
    """Presentation-only subplot mapping for the published P1 signal_plot.png."""

    primary: str
    support: str = ""
    note: str = ""
    question: str = ""


# Numbered against the published G1-P1 PNG titles (demo_0 / current Audit Run).
# Formal subplots = 1–7. Subplot 8 = PRIVILEGED_AUDIT_ONLY Can_pos.
SIGNAL_REVIEW_GUIDES = {
    "TRANSLATION": SignalReviewGuide(
        primary="主要看：子图 1「末端位置」；子图 2「平移步长 / 速度」",
        question=SIGNAL_AUDIT_QUESTIONS["TRANSLATION"],
    ),
    "DIRECTION": SignalReviewGuide(
        primary="主要看：子图 3「主方向变化证据」",
        support="辅助看：子图 1「末端位置」；子图 2「平移步长 / 速度」",
        question=SIGNAL_AUDIT_QUESTIONS["DIRECTION"],
    ),
    "GRIPPER": SignalReviewGuide(
        primary="主要看：子图 4「实际夹爪状态」",
        support="辅助看：子图 5「夹爪指令」",
        note="主要看实际状态；command 用来判断指令与实际执行是否合理对应，两者不必完全重合。",
        question=SIGNAL_AUDIT_QUESTIONS["GRIPPER"],
    ),
    "ROTATION": SignalReviewGuide(
        primary="主要看：子图 6「末端旋转变化」",
        question=SIGNAL_AUDIT_QUESTIONS["ROTATION"],
    ),
    "ACTION": SignalReviewGuide(
        primary="主要看：子图 7「控制指令变化幅度」",
        support="辅助看：子图 5「夹爪指令」",
        note="Action 是控制器指令，不是实际运动轨迹；只查明显异常、时间错位或不合理跳变。",
        question=SIGNAL_AUDIT_QUESTIONS["ACTION"],
    ),
    "VIDEO_ALIGNMENT": SignalReviewGuide(
        primary="主要看：子图 1–7 的关键变化时刻是否与视频同步",
        note="重点检查：平移、夹爪、旋转等明显事件是否整体提前/滞后。子图 8 不作为对齐评分依据。",
        question=SIGNAL_AUDIT_QUESTIONS["VIDEO_ALIGNMENT"],
    ),
}

PRIVILEGED_SUBPLOT_HINT = "子图 8 为特权审计参考（Can 位置），不属于 Formal Signal 评分项。"


def ui_term(code: str | None) -> VocabTerm:
    raw = str(code or "").strip()
    if raw == "":
        return VocabTerm("", "", "", "", "empty")
    found = UI_VOCABULARY.get(raw)
    if found is not None:
        return found
    LOGGER.warning("UNKNOWN UI LABEL RAW CODE = %s", raw)
    return VocabTerm(
        code=raw,
        zh=f"{UNKNOWN_UI_LABEL}::{raw}",
        en=raw,
        description_zh=f"UNKNOWN_CODE::{raw}",
        kind="unknown",
    )


def signal_audit_question(code: str | None) -> str:
    return SIGNAL_AUDIT_QUESTIONS.get(str(code or "").strip(), "")


def signal_review_guide(code: str | None) -> SignalReviewGuide:
    key = str(code or "").strip()
    found = SIGNAL_REVIEW_GUIDES.get(key)
    if found is not None:
        return found
    return SignalReviewGuide(primary="", question=signal_audit_question(key))


def dropdown_option_label(code: str) -> str:
    term = ui_term(code)
    if term.kind == "unknown":
        return f"{UNKNOWN_UI_LABEL}::{code}"
    return f"{term.code}｜{term.zh}"


def display_code(code: str | None) -> str:
    raw = str(code or "").strip()
    if raw == "":
        return ""
    if "|" in raw:
        parts = [part.strip() for part in raw.split("|") if part.strip()]
        return " | ".join(display_code(part) for part in parts)
    term = ui_term(raw)
    if term.kind == "unknown":
        return f"{UNKNOWN_UI_LABEL}::{raw}"
    return f"{term.code}｜{term.zh}"
