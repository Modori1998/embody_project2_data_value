# Project 2 · G1-P3 · Unblinded Owner Review Mode — Result

- 日期：2026-09-22
- 任务：`ADD_G1_P3_UNBLINDED_OWNER_REVIEW_MODE`
- 目标 Run：`g1_design_diagnostic_20260922_135647_69bf2a94`（`run_stage = DESIGN_DIAGNOSTIC`）
- 事实源：`0-doc/80-audit-local/g1_p3_trajectory_mechanism_validation/02_selection_internal.csv`
- 结论：`PASS_READY_FOR_OWNER_UNBLINDED_REVIEW`

---

## 1. 交付内容

在既有 G1 Audit Web 的 `DESIGN_DIAGNOSTIC` Run 上，**新增**一个仅供 Design Owner 使用的「解盲复核模式」。
原有盲审页面与首次盲审结果均保持不变。

新增路由：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/audit/<run_id>/unblinded` | 入口，303 跳到第一个事件 |
| GET | `/audit/<run_id>/unblinded/episode/<episode_id>` | 单案例解盲复核页 |
| GET | `/audit/<run_id>/unblinded/pair/<pair_id>` | Matched Pair 并排对照页 |
| POST | `/audit/<run_id>/unblinded/episode/<episode_id>/review` | 提交复核（append-only 新 revision） |

新增/修改文件：

- 新增 `src/project2_g1_audit_web/unblinded.py` — 严格 1:1 join、C12/P12 中文解释、provenance
- 新增 `src/project2_g1_audit_web/templates/unblinded.html`
- 新增 `src/project2_g1_audit_web/templates/unblinded_pair.html`
- 新增 `tests/test_g1_unblinded_owner_review.py`
- 改 `src/project2_g1_audit_web/app.py`（+275）
- 改 `src/project2_g1_audit_web/reviews.py`（+181 / −35）
- 改 `src/project2_g1_audit_web/templates/audit.html`（+2，仅一个不含任何设计 token 的入口链接）

---

## 2. 严格 1:1 Join 契约

Join key = **`episode_id` + `boundary_id`**，**精确字符串相等**，一对一，要求 **20/20**。
禁止任何 fuzzy match。以下情况一律 fail-fast（页面报 `UNBLINDED_JOIN_FAILED`，不渲染部分视图）：

| 失败模式 | 错误码 |
| --- | --- |
| Run 事件在解盲源中缺失 | `MISSING_IN_UNBLIND_SOURCE` |
| 解盲源存在 Run 没有的行 | `EXTRA_IN_UNBLIND_SOURCE` |
| 解盲源 join key 重复 | `duplicate join keys` |
| 帧不一致（`event_frame` ≠ Run `frame`） | `frame mismatch` |
| 仅能按单一字段模糊对上 | `FUZZY_MATCH_REJECTED` |
| 事件数 / 配对数不符 | `EVENT_COUNT_MISMATCH` / `PAIR_COUNT_MISMATCH` |
| Arm 与 C12 四分位不一致 | `arm ... must sit in ...` |
| 非 `DESIGN_DIAGNOSTIC` Run | `UNBLINDED_NOT_APPLICABLE` |

C12 分组由 `C12_percentile` 按冻结四分位规则推导：`≤ 0.25` → `LOW C12`；`≥ 0.75` → `HIGH C12`。
实测 20 个事件全部落在两个诊断臂内，Arm A ⇒ LOW（10 个），Arm B ⇒ HIGH（10 个），配对 10 对。

---

## 3. 盲态与首次盲审的保全

三层保证：

1. **Run 目录零写入。** 解盲信息在渲染时从 `0-doc/.../02_selection_internal.csv` 读取，从不落进 Run 目录。
   复核后 `audit_blinding_run_folder()` 仍为 **0 违规**，`blinding_contract = PASS`。
2. **盲审页面仍保持盲态。** 盲审页只新增一个入口链接，不含任何被禁 token。
   实测对 `arm / p12 / c12 / coherence / pair_id / match_distance / selection_reason` 等探针零命中。
3. **首次盲审结果不被覆盖。** 复核走同一 append-only SSOT，但以**独立 reviewer 身份**
   （`DESIGN_OWNER_UNBLINDED`）追加新 revision，因此 provenance 可直接由已存字段推导，**无需改表结构**：

   - `FIRST_BLINDED_REVIEW` = `reviewer = DESIGN_OWNER`
   - `OWNER_UNBLINDED_REVIEW` = `reviewer = DESIGN_OWNER_UNBLINDED`

   页面同时展示 `review_id` / `reviewed_at` / `revision_count`，两类结果可区分。
   复核写入**只碰 `predicted_boundary_review_history`**，绝不触碰 signal / added / note 三张表。

---

## 4. 解盲页展示字段

必须展示项全部落地（页面元素 id 便于机器校验）：

`ub-arm`（Arm A/B）、`ub-c12-group`（LOW/HIGH C12）、`ub-c12`（4 位小数）、`ub-p12`（4 位小数）、
`ub-pair-id`（P01~P10）、`ub-direction-evidence`、`ub-run-length`、`ub-first-blind-decision`
（含 reason_code / comment / review_id / reviewed_at）、`ub-c12-explanation`、`ub-p12-explanation`（中文解释原文）、
`btn-open-matched-pair`（Matched Pair 区块 + Open Matched Pair）。

复核表单：`VALID / REDUNDANT / MISALIGNED` + `reason_code` + `comment`（+ `corrected_frame`）。
下拉默认是中性占位 `—（请选择）`，**不预选任何标签、不给推荐答案**（页面显式标注 `NO AUTO LABELLING`）。
`NOT_REVIEWED` 被明确拒绝——本模式的目的是重新判定，不是擦除判定。

页面显著标注：

```text
UNBLINDED OWNER REVIEW
FIRST BLINDED RESULT IS PRESERVED
```

---

## 5. 验收证据

### 5.1 单元 / 集成测试

```
python -m unittest discover -s tests -t tests
Ran 400 tests
FAILED (failures=6)      ← 全部为改动前既存失败，与本次改动无关（见 5.3）
```

新增 `tests/test_g1_unblinded_owner_review.py`：**44 passed**，覆盖 join 全失败模式、
盲审页零泄露、首次盲审保全、provenance 区分、append-only、字段可见性、禁用开关、非诊断 Run 拒绝。

### 5.2 真实数据端到端验收

`outputs/_scratch_unblinded_acceptance.py`（生产 owner DB 只读，写路径在 DB 副本上验证）：

```
UNBLINDED OWNER REVIEW ACCEPTANCE: 30/30 PASS
EVENT_COUNT = 20
PAIR_COUNT  = 10
```

含：20 个解盲案例页全部 200、10 个 Matched Pair 页全部 200、盲审页零泄露、
首次盲审 revision 逐字段保全（`review_id=78, decision=VALID, reviewer=DESIGN_OWNER`）、
新 revision 归属 `DESIGN_OWNER_UNBLINDED`、Calibration Export 仍被阻断、kill switch 返回 403。

生产库复核后仍为 **20 revisions / 20 episodes / 全部 `DESIGN_OWNER`**——即首次盲审未被改动。

### 5.3 既存失败（与本次改动无关，已证明）

6 个失败全部是**对 `outputs/**` 产物的固定指纹断言**，与 `src/project2_g1_audit_web` 无关：

- `test_g1_12ep_baseline_calibration` / `test_g1_baseline_scoring` / `test_g1_stage_a0`：产物指纹
- `test_g1_fresh_calibration_run`：manifest 集合与 screening CSV
- `test_g1_trajectory_diagnostic_audit_web::test_no_prior_review_is_copied_in`：断言生产 owner DB 中该 Run 无审核记录，
  但 Design Owner 已于 2026-09-22 完成 20/20 盲审，该断言按设计已过期

**证明方式**：把本次改动的 3 个文件临时还原到 `HEAD`（`git diff --numstat` 为空确认 pristine），
单独运行这 6 个测试 → 同样 **6 FAILED**。随后从校验过的备份恢复（3 个文件 sha256 与改动前完全一致）。

---

## 6. 复现

```bash
# 全量测试
python -m unittest discover -s tests -t tests

# 端到端验收（只读生产库）
python outputs/_scratch_unblinded_acceptance.py

# 启动 Web（本地 Owner 使用）
py -3 scripts/run_g1_audit_web.py
# 盲审入口  : http://127.0.0.1:8766/audit/<run_id>
# 解盲复核  : http://127.0.0.1:8766/audit/<run_id>/unblinded
```

解盲模式默认开启（本地 Owner Web）；可用环境变量关闭：

```bash
G1_AUDIT_WEB_UNBLINDED_OWNER_REVIEW=0
```

---

## 7. 环境事件记录：项目 `.git` 目录丢失与恢复

本次执行过程中发生一起**与本次功能无关**的环境事故，如实记录：

- 为对比基线执行 `git stash push` 时返回
  `fatal: b0cc64bb6bb4f5397da43a566948f6e56b49de23 is not a valid object`，
  随后 `4-Project2_data_value/.git` **整个目录消失**（该项目为独立仓库，非 linked worktree，
  父目录 `embody/` 无对应仓库）。
- 该现象与本机既有记录一致：`embody/` 下已有 `Project1_dot_git_damaged_*`、
  `Project1_dot_git_pre_worktree_reassociation_*` 等多起同类 `.git` 损毁痕迹。
- **未提交的工作零丢失**：改动文件已先备份到
  `embody/Project2_dot_git_lost_recovery_20260922_172720/`（含 sha256 清单），恢复后逐一比对一致。
- **恢复方式**：以 GitHub 为唯一权威重新 clone（`HEAD = b40218ec…`，与远端一致），
  将该 clone 的 `.git` 复制回项目目录。远端 `refs/heads/main` 在事故前后均为
  `b40218ecdea5035d58de05d84b28eaee9483755c`，**已提交内容全部安全**。
- **教训**：本环境下不要用 `git stash`（需要写对象库）；比较改动一律用 `git diff --numstat`，
  `git status` 在 index stat 缓存失配时会给出大量假 `M`（本次 130 个假阳性 vs 真实 3 个）。
