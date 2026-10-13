# P2-G3 Phase 1C 极简人工可观测性审核

状态：`CONTEXT_DECISION=PENDING_HUMAN_REVIEW`。本轮仅判断额外视觉上下文是否更易理解，不生成语义 Ground Truth、VLM 准确率或显著性结论。

## Git 与来源

2026-10-13 已检查 `git status`、worktree 和远端 refs，并读取设计分支的 Design / Plan / Output Design。`origin/main=b5fd9b97d1b32ffa98d6facd95bf663be12ac63e`，设计分支 `bb711c0f9613da42e0a000695371826d2d7148e1`，Phase 1B `ad3f71121bdc35f27ee905ee3a693319ca536e4f`。复用已存在的 Phase 1C 独立工作树与任务分支。主工作树含未跟踪 `.cindy-worktrees/`，因此未在其中 pull。未修改 main、设计 PR、Phase 1B 或 G1/M2/Retrieval 冻结资产。

只读复用 Phase 1B 产物：`C:/Users/95611/embody/_p2_g3_phase1b_wt/outputs/g3_phase1b_ab/g3_phase1b_ab_20261012/`。准备脚本验证 59 条源图片、Episode/Segment 对应、上下文帧来源与封存 A/B 映射；10 条选中图片的 SHA256 再在页面启动时校验。图片和封存键不提交 Git。

## 10 条样本

`review_selection.csv` 以固定种子 `P2_G3_PHASE1C_SIMPLE10_20261013_V1` 从 59 条中选择：`demo_120-S0005`、`demo_165-S0003`、`demo_196-S0002`、`demo_227-S0005`、`demo_277-S0005`、`demo_292-S0002`、`demo_33-S0001`、`demo_47-S0003`、`demo_74-S0003`、`demo_75-S0001`。覆盖 10 个 Episode、短段 4、普通段 6、首段 2、末段 2、普通位置 6、双侧邻居完整 6、缺一侧 4。规则仅使用结构字段和 SHA256 排序，没有按图片观感选样。初始三问题表 `review_sheet_UNSCORED.csv` 全为 `UNSCORED`。

## 打开与填写

在本仓库根目录运行：

```powershell
python scripts/run_g3_phase1c_simple.py --assets C:/Users/95611/embody/_p2_g3_phase1b_wt/outputs/g3_phase1b_ab/g3_phase1b_ab_20261012 --port 18871
```

本机访问 `http://127.0.0.1:18871/`。如使用已授权的远程临时隧道，需同时使用本机 `outputs/g3_phase1c_remote/access_password.txt` 作为 `--auth-file`。远程网址由运行中的隧道给出，不写入版本库。

每条先看 A，仅评“能 / 不确定 / 不能”；保存后才能看 B。B 使用 Phase 1B 来源标注图，上排 A、下排 B，绿色表示目标帧，橙色表示邻段帧。第二题再评“能 / 不确定 / 不能”；第三题选一个主要限制原因。第三题保存后自动下一条。可前后翻页、放大、修改旧答案、跳过并写可选备注；每步自动保存。B 展示的是相邻时间信息，邻段事件不得作为当前段标签。真实结果本地保存在 `outputs/g3_phase1c_reviews/simple_review.json`，不纳入 Git。页面可导出 CSV 或 JSON。

## 统计、测试与停止点

```powershell
python scripts/report_g3_phase1c.py --output outputs/g3_phase1c_reviews/simple_report.json
python -m unittest discover -s tests -p 'test_project2_g3*.py'
```

无人评分时统计只输出 `PENDING_HUMAN_REVIEW`，无虚构改善率。有真实评分时按“不能 < 不确定 < 能”统计 A 弱而 B 能、改善、持平、退化、限制原因和 2–3 个案例。全部完成后仅给出规则透明的建议，仍由 Owner 决定是否冻结 Context Window。小样本主观判断不具备语义准确率或统计显著性含义。

64 项相关测试通过；另外用隔离临时结果目录验证 A 图片 200、未答 A 时 B 图片 403、保存 A 后 B 图片 200、逐步保存、恢复及 10 条导出。未调用 VLM、未改 128×128 RGB Contract、未训练模型。
