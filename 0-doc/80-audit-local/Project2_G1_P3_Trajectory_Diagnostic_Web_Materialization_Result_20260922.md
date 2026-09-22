# Project 2 — G1-P3 Trajectory Mechanism Diagnostic Set → Audit Web Materialization Result

```text
DOCUMENT_STATUS   = DESIGN_DIAGNOSTIC_WEB_MATERIALIZATION_RESULT
TASK              = MATERIALIZE_G1_P3_TRAJECTORY_DIAGNOSTIC_SET_TO_AUDIT_WEB
RUN_STAGE         = DESIGN_DIAGNOSTIC
SET_ROLE          = DESIGN_DIAGNOSTIC
BUILD_DATE        = 2026-09-22
DETECTOR_MODIFIED = NO
CONFIG_CHANGE     = NO
PARAMETER_CHANGE  = NO
THRESHOLD_SELECTED = NO
HUMAN_LABEL_CREATED = NO
UNBLINDING_EXECUTED = NO
```

---

## 1. 结论摘要

已把 20 条 **Trajectory Mechanism Diagnostic Set** 样本接入现有 G1 Human Audit Web，
构建为一个完全独立的 `DESIGN_DIAGNOSTIC` Run，供 Design Owner 逐条盲审
`VALID / REDUNDANT / MISALIGNED`。

| 项 | 值 |
| --- | --- |
| `DESIGN_DIAGNOSTIC_RUN_ID` | `g1_design_diagnostic_20260922_135647_69bf2a94` |
| `run_stage` / `set_role` | `DESIGN_DIAGNOSTIC` / `DESIGN_DIAGNOSTIC` |
| event 数 | **20** |
| distinct episode | **20** |
| 每 episode 可审 Final Boundary | **1** |
| `diagnostic_set_id` | `g1_trajectory_mechanism_diag_20260921_000000_b61ef198` |
| BLINDING_AUDIT | **PASS** |
| CALIBRATION_EXPORT_BLOCKED | **YES** |
| 初始 review 状态 | `NOT_REVIEWED`（20/20） |

**最终状态：`PASS_READY_FOR_OWNER_BLINDED_REVIEW`。**

---

## 2. 唯一事件来源

Web 输入**只来自**：

```text
0-doc/80-audit-local/g1_p3_trajectory_mechanism_validation/03_selection_blinded.csv
```

- 未读取 `02_selection_internal.csv`；
- 未重新选择样本、未重新计算 selection、未重新匹配；
- `diagnostic_event_id ↔ episode/frame` 映射逐条保持；
- 未解盲、未计算 Arm A/B REDUNDANT rate、未判断 C12 SUPPORTED / NOT_SUPPORTED。

### 2.1 冻结检测器一致性（硬门禁）

对 20 条样本逐条重放冻结 Detector（`run_boundary_engine` + `compute_formal_signals`），
比对其输出的 `boundary_id` / `frame` / `representative_candidate_id` /
`member_candidate_ids` / `candidate_type` 与盲化清单：

```text
20 / 20  MATCH
```

任何一项漂移都会 fail-fast 中止构建。Detector 未做任何修改。

---

## 3. 最小 additive 契约扩展

新增 `run_stage = DESIGN_DIAGNOSTIC`、`set_role = DESIGN_DIAGNOSTIC`：

| 文件 | 变更 |
| --- | --- |
| `src/project2_g1_audit_web/contract.py` | `ALLOWED_RUN_STAGES` / `ALLOWED_SET_ROLES` / `STAGE_TO_SET_ROLE` 增加 `DESIGN_DIAGNOSTIC`；新增 `DESIGN_DIAGNOSTIC_*` 常量与 `is_design_diagnostic()` / `blocked_downstreams()` |
| `src/project2_g1_audit_web/calibration_export.py` | `resolve_export_role()` 对 `DESIGN_DIAGNOSTIC` 显式早退 `None` |
| `src/project2_g1_audit_web/vocab.py` | 新增 `DESIGN_DIAGNOSTIC` / `DESIGN_DIAGNOSTIC_ONLY` 词条 |
| `src/project2_g1_audit_web/view.py` | `RunHeader` 增加 `design_diagnostic_only` |
| `src/project2_g1_audit_web/templates/audit.html` | 新增 `design-diagnostic-banner` |

**现有 `EXPLORATORY_AUDIT` / `CALIBRATION` / `EVALUATION` 行为未改变**（回归测试通过）。

---

## 4. 下游硬阻断

```text
CALIBRATION_EXPORT_ELIGIBLE = false
CANONICAL_GT_ELIGIBLE       = false
EVALUATION_ELIGIBLE         = false
```

- `resolve_export_role()` → `None`（结构上不可能导出）；
- `assess()["ready"] = false` → 页面按钮渲染为 `EXPORT_BLOCKED`；
- `POST /audit/<run>/episode/<ep>/export` → HTTP 400 `EXPORT_BLOCKED`。

---

## 5. Blinding｜盲化硬门禁

### 5.1 禁止 token

```text
arm, p12, c12, coherence, target, control,
pair_id, match_distance, selection_reason, expected
```

（`VALID` / `REDUNDANT` / `MISALIGNED` 是合法审核标签，**不**在禁止集合内。）

唯一豁免标识符：`target_boundary_id` —— 既有冻结 Detector 列名。

### 5.2 审计范围与结果

对**列名与单元格取值**双重扫描，覆盖 reviewer-facing payload：

| 审计对象 | 结果 |
| --- | --- |
| 输入盲化清单 `03_selection_blinded.csv` | PASS |
| 构建后整个 run 目录（全部文本产物） | PASS |
| 页面 HTML（首页 / 审核页） | PASS |

盲化实现为**构建期 fail-fast**：任一 token 出现即中止，不产出 Run。

### 5.3 一处刻意的措辞收敛

冻结设计 §12 要求对 reviewer 隐藏 C12。因此：

- 词条 `DESIGN_DIAGNOSTIC` 的中文短标签为「设计诊断」，`description_zh`（会渲染进 tooltip）
  刻意写作「只用于设计机制盲审」，**不含 C12**；
- `run_meta.iteration_note` 同样不含 C12。

阶段用途（验证 C12 机制）记录在本文件与集合 README 等**非 reviewer-facing** 文档中。

---

## 6. Materialization 细节

- 每个选中事件成为该 episode **唯一**可审 Final Boundary；
- 冻结 Detector 的 `candidate_boundaries.csv` / `boundary_decisions.csv` /
  `segment_manifest.csv` **逐字保留**作为审核上下文；
- 仅 `final_boundaries.csv` 收敛为 1 行（本轮审核目标）；
- `final_boundary_count = 1`；`review_required = true`。

> 工程说明：由于审核目标被收敛为 1 条，Decisions 表中那些「被 Detector 保留但不在本轮
> 审核清单」的候选会显示既有 UI 标签 `not in final_boundaries.csv`。这是 Web 既有的
> 透明提示行为，非数据缺陷。

### 6.1 Media / Signal

- 20 个 episode 均不在任何既有 Run 中（与既有 12 个已覆盖 episode **零交集**），
  因此无 media 可复用，全部按现有 Web pipeline 用冻结 renderer 新渲染；
- video / signal_plot / signal_boundary_plot 全部生成；
- 渲染帧数逐条与 episode `num_steps` 校验一致（**20 / 20 帧数精确匹配**）。

> 渲染很慢（20 条合计约 1 小时 27 分），因此渲染产物落在
> `outputs/g1_audit_web/diagnostic_media_cache/<native>.mp4` 这一**带校验的缓存**里，
> 再复制进不可变 Run 目录。缓存条目按帧数校验、写入用 `*.part.mp4` 原子替换，
> 因此构建可安全重入：中断后重跑只会补渲缺失 episode，不会重渲已完成部分。
> 缓存位于 gitignored 的 `outputs/` 下，不进入版本库。

### 6.2 Review Storage

- 继续使用既有 append-only Web-owned SQLite；
- 以 `run_id + episode_id + boundary_id` 保存独立 provenance；
- 既有 Calibration review **未被复制**进来；
- 20/20 初始 `P2 review = NOT_REVIEWED`。

---

## 6.3 验收证据（对**真实 Run** 执行）

对 `g1_design_diagnostic_20260922_135647_69bf2a94` 逐项执行，**22 / 22 全部通过**：

| 检查项 | 结果 |
| --- | --- |
| Run 可加载；`run_stage` / `set_role` = `DESIGN_DIAGNOSTIC` | PASS |
| episode 数 20、distinct episode 20 | PASS |
| episode 集合 == `03_selection_blinded.csv` | PASS |
| 每 episode 恰好 1 个审核目标，且 `boundary_id` / `frame` 与盲化清单逐条一致 | PASS |
| Run 目录全 token 致盲扫描（`violations = []`） | PASS |
| 页面级致盲扫描（22 个页面 × 10 个探针） | PASS |
| 严格扫描器仍能命中全部探针（防"扫描器被削弱"） | PASS |
| `resolve_export_role()` → `None`；`assess()["ready"] == false` | PASS |
| `POST .../export` → HTTP 400 `EXPORT_BLOCKED` | PASS |
| 20/20 episode 可浏览 | PASS |
| 20/20 可提交 `VALID` / `REDUNDANT` / `MISALIGNED` | PASS |
| review 刷新/重开进程后不丢失 | PASS |
| append-only 历史正常记录 | PASS |
| 生产 review 库在本轮验收前后均为 0 条本 Run 记录 | PASS |
| 既有 Audit Web 回归（8 个既有测试模块） | 68 passed |

> 验收中的提交动作在 owner SQLite 的**临时副本**上执行，
> 生产库始终保持 `NOT_REVIEWED`，不会产生任何合成人工标签。
>
> `MISALIGNED` 依既有校验规则需同时提供 `corrected_frame`，
> `REDUNDANT` / `MISALIGNED` 复用既有 reason taxonomy —— 未新增标签体系。

### 6.3.1 页面级致盲口径说明

`target` / `control` 两个 token 只在**纯文本产物**扫描中作为禁止项；
页面 HTML 扫描使用 reviewer-facing 探针集合（不含二者），
因为基础模板中存在与诊断无关的通用标记（如 JS `event.target`）。
`target_boundary_id` 作为既有冻结 Detector 列名在文本扫描中单独豁免。
此口径与测试中的 `FORBIDDEN_PROBES` 完全一致。

---

## 7. 运行环境说明

本轮涉及两个解释器，原因是有意不污染既有环境：

| 用途 | 解释器 | 原因 |
| --- | --- | --- |
| Materialization | `C:\Users\95611\miniconda3\envs\project1_robomimic_audit_v150\python.exe` | 唯一具备冻结渲染栈（`robosuite` / `mujoco` / `robomimic` / `cv2`）的环境 |
| Tests | managed venv (`fastapi` / `httpx` / `pytest`) | 隔离环境，不修改用户 conda env |

---

## 8. Reproduce

```bash
# 1) 物化（需要渲染栈）
"C:/Users/95611/miniconda3/envs/project1_robomimic_audit_v150/python.exe" \
  scripts/materialize_g1_p3_trajectory_diagnostic_audit_run.py

# 2) 测试
python -m pytest tests/test_g1_trajectory_diagnostic_audit_web.py -q

# 3) 启动 Web
python scripts/run_g1_audit_web.py
#   -> http://127.0.0.1:8766/
```

---

## 9. Non-Scope（本轮明确未做）

```text
UNBLINDING_EXECUTED              = NO
READ_02_SELECTION_INTERNAL       = NO
ARM_A_B_REDUNDANT_RATE_COMPUTED  = NO
C12_SUPPORT_VERDICT              = NO
CALIBRATION_GT_GENERATED         = NO
CANONICAL_GT_MODIFIED            = NO
EVALUATION_MODIFIED              = NO
THRESHOLD_SEARCH                 = NO
DETECTOR_MODIFIED                = NO
PROTOCOL_PATCH                   = NO
```

---

## 10. Final Status

```text
DESIGN_DIAGNOSTIC_RUN_ID       = g1_design_diagnostic_20260922_135647_69bf2a94
WEB_URL                        = http://127.0.0.1:8766/audit/g1_design_diagnostic_20260922_135647_69bf2a94
启动命令                        = python scripts/run_g1_audit_web.py
EVENT_COUNT                    = 20
BLINDING_AUDIT                 = PASS
CALIBRATION_EXPORT_BLOCKED     = YES
FINAL_STATUS                   = PASS_READY_FOR_OWNER_BLINDED_REVIEW
```

等待 Design Owner 盲审；审核完成后由后续独立任务解盲与分析。
