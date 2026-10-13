# P2-G3 Phase 1C — 人工可观测性审核（A–G）

状态：`PENDING_HUMAN_REVIEW`。这是 Development 可观测性审核，不是正式 VLM Held-out 评测或 taxonomy freeze。

## A. Git 状态

2026-10-13 `git fetch origin --prune` 后核对：`main=b5fd9b97d1b32ffa98d6facd95bf663be12ac63e`；设计分支 `bb711c0f9613da42e0a000695371826d2d7148e1`；Phase 1B `ad3f71121bdc35f27ee905ee3a693319ca536e4f`。当前独立任务分支 `p2-g3-phase1c-human-observability-20261013` 基于 Phase 1B HEAD。主工作树有未跟踪 `.cindy-worktrees/`，未在其中执行 pull、reset 或 clean。设计 PR #1、main 和 Phase 1B 冻结分支未修改。

## B. 工具实现

`src/project2_g3/human_review.py` 实现确定性选样、产物校验、人工评分校验与独立保存、统计。`scripts/prepare_g3_phase1c.py` 生成锁定清单与空表；`scripts/run_g3_phase1c_review.py` 提供只监听 `127.0.0.1` 的标准库 HTTP 页面；`scripts/report_g3_phase1c.py` 生成报告。无新运行依赖；无需 VLM。

只读复用 Phase 1B 正式产物：`C:/Users/95611/embody/_p2_g3_phase1b_wt/outputs/g3_phase1b_ab/g3_phase1b_ab_20261012/`。该目录包含 59 条 A/B 盲化面板、分析员面板、封存键、UNSCORED 表及上下文和帧来源清单。已校验图片存在且非空、Segment 与 Episode 对应、帧来源在目标段外且无跨 Episode、盲化键可反查、选中图片 SHA256 与清单相符。未重新渲染。原始图片与封存键留在本机，不纳入 Git。

## C. 选样

从 59 条中按固定种子 `P2_G3_PHASE1C_SELECTION_20261013_V1` 锁定 24 条，每个 Episode 先选一条，随后优先补齐结构层，再按 SHA256 排序补满。没有使用图像观感或 Phase 1B 结构代理分数。短段 9、非短段 15；首段 5、末段 4、普通段 15；双侧邻居完整 15、不完整 9；覆盖 12 个 Episode。层间允许重叠。完整清单及每张图片哈希见 `phase1c_review_selection_manifest.csv`。

选中 Segment：`demo_120-S0001`、`S0003`、`S0004`、`S0005`；`demo_155-S0005`；`demo_165-S0001`、`S0002`；`demo_196-S0001`、`S0003`、`S0004`；`demo_227-S0002`、`S0003`、`S0005`；`demo_24-S0002`、`S0004`；`demo_277-S0005`；`demo_292-S0003`、`S0004`；`demo_33-S0002`；`demo_47-S0001`、`S0002`；`demo_74-S0004`；`demo_75-S0001`、`S0006`。

## D. 人工审核方式

在当前仓库根目录运行：

```powershell
python scripts/run_g3_phase1c_review.py --assets C:/Users/95611/embody/_p2_g3_phase1b_wt/outputs/g3_phase1b_ab/g3_phase1b_ab_20261012 --port 18871
```

打开 `http://127.0.0.1:18871/`。输入自己的 `reviewer_id` 并载入。上一条/下一条按钮及左右箭头切换；点击小图放大；可打开来源说明图核对目标帧、邻段帧与时间，但这会解除面板匿名。面板 1/2 的映射由本机封存键恢复，评分落盘为 A/B；B 的额外帧数可能暴露组别，故不能称完全双盲。评分、备注、跳过原因可随时保存并在退出后恢复；“查看未完成项”跳到第一条未完成；可导出 CSV/JSON。不同审核者分别保存在 `outputs/g3_phase1c_reviews/<reviewer_id>.json`，不会互相覆盖。

五项分别评分：`OBJECT_VISIBLE` 物体是否清楚可见；`MOTION_PHASE_DECIDABLE` 目标段主要动作阶段能否判断；`GRIPPER_TRANSITION_VISIBLE` 夹爪开合变化能否看到；`OBJECT_FOLLOWING_DECIDABLE` 能否判断物体跟随夹爪；`RELEASE_DECIDABLE` **目标段内**是否释放能否判断。各项取 `SUFFICIENT`、`PARTIAL`、`INSUFFICIENT` 或 `NOT_APPLICABLE`；未评为 `UNSCORED`。另记录邻段是否有帮助、事件是否在目标段外、主要限制（低分辨率、遮挡、画外、时间缺口、其他）、备注、审核者和时间。邻段出现释放只记录为段外事件，不得提高“目标段内释放”的评分。

评分后运行：

```powershell
python scripts/report_g3_phase1c.py --reviewer <reviewer_id> --output outputs/g3_phase1c_reviews/report.json
```

## E. 测试与质量

`python -m unittest discover -s tests -p 'test_project2_g3*.py'`：63 项通过（原 58 项 + 新增 5 项）。覆盖选样确定性、身份校验、无评分状态、跳过与恢复、不同审核者隔离、段外事件与目标段内释放分离。HTTP 冒烟测试：主页、24 条选样和图片读取成功。准备脚本对全部 59 条进行图片/清单/来源检查，选中 24 条的图片 SHA256 在服务启动时再次校验。未触碰 G1、M2、Retrieval 冻结资产。

## F. 结果状态

真实人工评分：**0**。`phase1c_review_sheet_UNSCORED.csv` 仅为空表，状态文件为 `phase1c_review_status_PENDING.json`；`DECISION=PENDING_HUMAN_REVIEW`。统计脚本在无有效评分时不输出改善率，也不将 Phase 1B 结构代理指标当作人工结果。

## G. 下一步

Owner 或独立审核者打开页面，完成 24 条评分并保存，必要时记录跳过原因。拿到真实评分后再按指标、成对变化、短段、首尾段和邻居完整性解读；核对改善、持平与退化案例及低分辨率占比。届时冻结 Context Window 是否默认/可选、证据帧预算及来源规则、人工 rubric、实验 Episode 切分、正式 taxonomy、Qwen3-VL 精确 revision 与提示词、成本上限和小样本 baseline 的停止条件。若低分辨率成为主要瓶颈，另提 256/512 原生渲染实验建议，由 Owner 决定；本轮不修改 128×128 正式契约。
