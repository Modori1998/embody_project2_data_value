# P2 Scope Change — Retrieval v1 HOLD / G3 Argus 主线（2026-10-12）

> STATUS = OWNER_APPROVED_DIRECTION / REVIEW_BRANCH_PENDING_MERGE
> SRC_MAIN_HEAD_BEFORE = b5fd9b97d1b32ffa98d6facd95bf663be12ac63e
> G3_FORMAL_TAXONOMY = PENDING_FREEZE
> G3_FORMAL_INFERENCE = NOT_STARTED

## Owner approved decisions

1. **Retrieval v1: HOLD_BY_OWNER.** 暂停尚未执行的 18-query Final Retrieval 与 Final Human Audit；保留 query/candidate cohort、协议、人工 rubric、所有既有审计与冻结证据。HOLD 不代表 GO、STOP、失败或成功。
2. **G3 semantic annotation: NEW_ACTIVE_PRIORITY.** 采用 Argus 核心思路，复用 P2 已冻结 G1/M2 Source、Clean RGB、EEF、Gripper、Action，新增可追溯的语义标注、局部事件、物体交互、任务结果（仅证据充分时）、标签校验、人工审计和索引导出。此次 Owner 决定明确覆盖旧的“Retrieval Gate GO/CONDITIONAL 后才允许 G3”这一执行顺序，不修改旧 Retrieval 实验语义。
3. **Argus core functional reimplementation:** 重点覆盖端到端标注/证据/运行追踪/人工复核/导出，不强制复现 Argus 全量 Dashboard、传感器、机器人型号及通用数据转换器。引用 Argus Apache-2.0 源码和设计必须归属清晰。
4. **Evaluation industrial-minimum:** 同一冻结 Qwen3-VL 模型、相同 Episode 隔离的人工独立金标，对照 A=RGB+Task 与 B=A+合法机器人运动/动作摘要。新增事件邻域图片 C 和高级质检分流 D 仅在开发期 Bad Case 提示必要时启动；有提升声明时必须提供对应公平对照。
5. **No ACT / training utility claim:** G3 v1 不训练 ACT/VLA、不自动 DROP/UPWEIGHT、不把标签正确自动映射为训练示范可用。标签质量、人工审核和数据训练价值分开。

## Immutable preservation

- G1 Frozen Segment 不改边界/配置；M2 Clean RGB/Time Alignment 不变；Action 为 normalized controller input，不是实际物理速度。
- 不让 reward/done、模拟器对象真值、Can_pos / Can_to_EEF 等 privileged information 进入 G3 推理或检验规则。
- Retrieval v1 的 formal Top-K、18-query cohort、Human rubric、Calibration/Final 隔离及冻结 Manifest 全部保留，不得以 G3 预测标签改写原评测 GT。
- G3 方案与输出 Schema 的具体候选标签、样本数、成功阈值、模型精确 revision、人工审计字段还需要单独冻结；不得因范围方向获批而宣称全部正式冻结。
- GitHub main 只有 PR 审核合并后才具权威效力；评测结果状态以真实运行记录为准。

## Next execution

1. 先将 v1 的 Design / Plan / Output Design 三份完整设计与本变更申请一并纳入 GitHub PR 后再合并。
2. 本地开始任何修改前在健康 Git worktree / fresh clone 执行 fetch、main fast-forward pull、干净状态检查，随后开 G3 专用分支。
3. G3 只读 Source/RGB 可观测性检查和少量 Qwen3-VL 基线推理，后续才是独立人工评测与 A/B 结果。

本 memo 只记录 Owner 范围批准和实施约束，不声称代码、模型评测或任何 GT 已完成。
