# Project 2 · G1-P3 · Unblinded Owner Review Mode — Result

- 日期：2026-09-22
- 任务：`ADD_G1_P3_UNBLINDED_OWNER_REVIEW_MODE`
- 目标 Run：`g1_design_diagnostic_20260922_135647_69bf2a94`（`run_stage = DESIGN_DIAGNOSTIC`）
- 事实源：`0-doc/80-audit-local/g1_p3_trajectory_mechanism_validation/02_selection_internal.csv`
- 结论：`PASS_READY_FOR_OWNER_UNBLINDED_REVIEW`
- 后续修订：**`FIX_UNBLINDED_MEDIA`（§8）** — 解盲页补齐 Episode 视频与帧对齐轴

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
- 新增 `src/project2_g1_audit_web/templates/unblinded_ui.js`（§8：解盲页专用前端脚本）
- 新增 `tests/test_g1_unblinded_owner_review.py`
- 改 `src/project2_g1_audit_web/app.py`（+275，§8 再 +42）
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

### 4.1 Episode 媒体与帧对齐（§8 补齐）

解盲复核若看不到视频就无法复核，因此解盲页与盲审页一样承载 Episode 媒体，
且复用**同一条帧轴**（两侧都走 `build_episode_view()`，只有外层 chrome 不同）：

| 元素 | 说明 |
| --- | --- |
| `<video>` | `src = /media/<run_id>/<episode_id>/video`，含 `data-source-sha256` / `data-needs-proxy` |
| `#frame-strip` | `data-fps = 20.0`、`data-length = <episode.length>`，含 `#strip-playhead`、`.strip-col`、`.strip-mark` |
| `#cur-frame` / `#cur-time` / `#jump-frame` / `#btn-jump-frame` / `[data-frame-delta]` | 帧读数与跳转 |
| `signal_boundary_plot` / `signal_plot` | 诊断曲线图，可点击放大 |
| `#ub-focus-frame` + `.ub-focus-col` | 当前事件的诊断 Boundary 帧，进页面即定位到该帧 |
| `#unblinded-pair-media` | 配对页左右并排两个 Arm 的视频 + 各自诊断帧定位 |

交互逻辑：帧 ↔ 视频 ↔ 标记轴同步仍由既有 `audit_sync.js` 承担（不复制一份 seek 算术）；
解盲页新增的 `unblinded_ui.js` 只做三件事——进页面定位诊断帧、配对页各 Arm 独立 seek、
按 decision 显隐 `reason_code` / `corrected_frame`。该脚本在盲审页不加载，
且第一句就是 `#unblinded-media` 存在性守卫。

---

## 5. 验收证据

### 5.1 单元 / 集成测试

```
python -m unittest discover -s tests -t tests
Ran 413 tests
FAILED (failures=6)      ← 全部为改动前既存失败，与本次改动无关（见 5.3）
```

新增 `tests/test_g1_unblinded_owner_review.py`：**57 passed**，覆盖 join 全失败模式、
盲审页零泄露、首次盲审保全、provenance 区分、append-only、字段可见性、禁用开关、非诊断 Run 拒绝，
以及 §8 的媒体交付（视频 / 帧轴 / 帧跳转 / 诊断曲线 / 诊断帧定位 / 配对页双视频 /
媒体路由可取 / **渲染不写 Run 目录** / 媒体不渗入盲审页 / **脚本 DOM 锚点契约**）。

### 5.2 真实数据端到端验收

`outputs/_scratch_unblinded_acceptance.py`（生产 owner DB 只读，写路径在 DB 副本上验证）：

```
UNBLINDED OWNER REVIEW ACCEPTANCE: 42/42 PASS
EVENT_COUNT = 20
PAIR_COUNT  = 10
```

含：20 个解盲案例页全部 200、10 个 Matched Pair 页全部 200、盲审页零泄露、
首次盲审 revision 逐字段保全（`review_id=78, decision=VALID, reviewer=DESIGN_OWNER`）、
新 revision 归属 `DESIGN_OWNER_UNBLINDED`、Calibration Export 仍被阻断、kill switch 返回 403。

§8 媒体部分（真实 Run）：`data/demo_211` 诊断帧 **169**、boundary `demo_211-B0007`，
页面对该帧定位成功；三条媒体路由实测
`video = 375570 B`、`signal_boundary_plot = 847203 B`、`signal_plot = 723718 B`；
配对页 2 个 `<video>`；渲染前后 Run 目录指纹**逐文件一致**。

生产库复核后仍为 **20 revisions / 20 episodes / 全部 `DESIGN_OWNER`**——即首次盲审未被改动。
Run 目录 `audit_blinding_run_folder()` 复核后仍为 **0 违规**。


### 5.3 既存失败（与本次改动无关，已证明）

6 个失败全部是**对 `outputs/**` 产物的固定指纹断言**，与 `src/project2_g1_audit_web` 无关：

- `test_g1_12ep_baseline_calibration` / `test_g1_baseline_scoring` / `test_g1_stage_a0`：产物指纹
- `test_g1_fresh_calibration_run`：manifest 集合与 screening CSV
- `test_g1_trajectory_diagnostic_audit_web::test_no_prior_review_is_copied_in`：断言生产 owner DB 中该 Run 无审核记录，
  但 Design Owner 已于 2026-09-22 完成 20/20 盲审，该断言按设计已过期

**证明方式**：把本次改动的 3 个文件临时还原到 `HEAD`（`git diff --numstat` 为空确认 pristine），
单独运行这 6 个测试 → 同样 **6 FAILED**。随后从校验过的备份恢复（3 个文件 sha256 与改动前完全一致）。

### 5.4 浏览器 DOM 行为验证（§8 媒体）

Python 测试只能证明媒体标记**存在**，不能证明它**能用**。因此对真实渲染页面做了一次
DOM 级行为验证：把线上页面载入 jsdom，在页面上下文里按顺序执行 `audit_sync.js` 与
`unblinded_ui.js`，断言帧 ↔ 视频 ↔ 标记轴的实际行为。

```
UNBLINDED DOM BEHAVIOUR CHECK: 35/35 PASS
```

关键结论（真实 Run，`data/demo_211`）：

| 断言 | 实测 |
| --- | --- |
| 进页面定位诊断帧（不是 frame 0） | `cur-frame = 169` |
| 时间读数 = frame / fps | `cur-time = 8.45` s（fps = 20） |
| 播放头位置 | `left = 47.606%`（= 169/355） |
| 标记轴状态文案 | `frame 169 · demo_211-B0007, demo_211-C0008 · 8.45s` |
| 诊断帧列被标记 + 选中 | `.ub-focus-col` + `.sync-on` 同时成立 |
| `video.load()` 确实被调用 | jsdom 报 `HTMLMediaElement's load() method` 未实现 → 反证已调用 |
| `loadedmetadata` 后完成 seek | `currentTime = 8.45` |
| 帧导航 / 跳转 / 点标记列 / 回到诊断帧 | 168 → 10 → 4 → 169 全部正确 |
| 条件字段随 decision 显隐 | `VALID` 全隐；`MISALIGNED` 显两项；`REDUNDANT` 仅显 reason_code；选项按 `data-for` 互斥启用 |
| 配对页两 Arm **独立** seek | Arm A `169` (8.45 s)、Arm B `808` (40.40 s)，互不影响 |
| 无意外 JS 异常 | 除 jsdom 未实现 `load()` 外零错误 |

> `preload="none"` 下 `readyState` 恒为 0、`loadedmetadata` 永不自动触发，
> 故 `video.load()` 是必需的；jsdom 的"未实现"报错恰好成为该调用的**正向证据**。
> jsdom 不实现媒体解码，因此"能否真正播放"以 5.2 的代理路由实测（`video/mp4`, 167465 B）为准。

---

## 6. 复现

```bash
# 全量测试
python -m unittest discover -s tests -t tests

# 端到端验收（只读生产库）
python outputs/_scratch_unblinded_acceptance.py

# DOM 行为验证（需先起 Web；见 §5.4）
NODE_PATH="$HOME/.workbuddy-ai/binaries/node/workspace/node_modules" \
  node outputs/_scratch_dom_check.cjs

# 启动 Web（本地 Owner 使用）
py -3 scripts/run_g1_audit_web.py
# 盲审入口  : http://127.0.0.1:8766/audit/<run_id>
# 解盲复核  : http://127.0.0.1:8766/audit/<run_id>/unblinded

# 若 8766 被旧进程占用（旧进程会 404 新路由），换端口起一个新实例：
py -3 scripts/run_g1_audit_web.py --port 8770
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

---

## 8. 后续修订：`FIX_UNBLINDED_MEDIA`

### 8.1 问题

Design Owner 反馈：**「新改的网页内容缺失，解盲没有相应的视频」**。

复核确认属实，属 §3/§5 交付缺陷：解盲页只渲染了诊断字段，
`unblinded.html` 中没有任何 `<video>`、没有帧对齐轴、没有诊断曲线，
`unblinded_page_context()` 也从未返回媒体上下文，`load_unblinded()` 更没有调用 `bind_media()`。
结果是**解盲复核在信息上不可执行**——Owner 拿不到视频，无法判断边界是否冗余或错位。

### 8.2 修复

| 位置 | 改动 |
| --- | --- |
| `app.py` | 新增 `load_unblinded_view(loaded, event)`：走 `build_episode_view()` 建视图并 `bind_media()`；案例页与配对页都调用 |
| `app.py` | `unblinded_page_context()` 增加 `view` 与 `focus_frame`；媒体错误走 `UNBLINDED_MEDIA_ERROR`（400，不静默降级） |
| `templates/unblinded.html` | 新增 Episode 媒体区块：视频、帧读数/跳转、`#frame-strip`、诊断曲线、诊断帧高亮 |
| `templates/unblinded_pair.html` | 新增 `#unblinded-pair-media`：两 Arm 视频并排 + 各自诊断帧定位按钮 |
| `templates/unblinded_ui.js` | **新增**：进页面定位诊断帧、配对页各 Arm 独立 seek、按 decision 显隐条件字段 |

### 8.3 三条不变量仍然成立

1. **盲审页仍盲。** 媒体只加在 `unblinded.html` / `unblinded_pair.html`。
   测试 `test_unblinded_media_does_not_leak_into_the_blind_page` 断言盲审页不含
   `unblinded-media` / `unblinded_ui.js` / `ub-focus-frame` / `ub-arm` / `ub-c12`；
   既有 `test_reviewer_payload_leaks_no_diagnostic_token` 仍对 10 个探针零命中。
2. **首次盲审结果仍保全。** 本次改动不触碰任何写路径；生产库复核后
   该 Run 仍为 **20 revisions / 20 episodes / 全部 `DESIGN_OWNER`**。
3. **Run 目录零写入。** `audit_blinding_run_folder()` 仍 **0 违规**；
   新增测试 `test_unblinded_media_rendering_leaves_the_run_folder_untouched`
   对渲染前后的 Run 目录做逐文件 `(size, mtime_ns)` 指纹比对，断言完全一致。

### 8.4 顺带修正的可用性缺陷

- `reason_code` / `corrected_frame` 原先**始终可见**，与盲审页「按 decision 显隐」的既有规则不一致；
  现已对齐（`.cond-reason` / `.cond-frame` / `option[data-for]`，机制与盲审页同构）。
- 进页面默认停在 frame 0；现定位到该事件的诊断 Boundary 帧（实测 `demo_211` → frame 169）。
- 跳帧复用 `audit_sync.js` 的 `select()` 路径（对目标 `.strip-col` 派发 click），
  不复制 seek 算术，避免两套帧轴实现漂移。

### 8.5 未改动

`unblinded.py`（join / provenance / 中文解释）、`reviews.py`（append-only 写路径）、
`audit.html`（除 §1 已交付的入口链接）均**未改动**。
`audit_sync.js` 亦未改动——它原本就对缺失锚点做 null 守卫，可直接复用。

### 8.6 验证

| 层 | 手段 | 结果 |
| --- | --- | --- |
| 标记存在 | Python：`test_g1_unblinded_owner_review.py` | 57 passed（13 个媒体用例） |
| 端到端 + 路由 + Run 目录只读 | Python：`_scratch_unblinded_acceptance.py` | 42/42 PASS |
| **行为可用** | **jsdom：`_scratch_dom_check.cjs`** | **35/35 PASS**（见 §5.4） |
| 不回归 | 全量 `unittest discover` | 413 tests，仍是同一批 6 个既存失败 |
| 盲态未破 | `audit_blinding_run_folder()` | 0 违规 |
| 首次盲审未破 | 生产 owner DB 直查 | 20 revisions / 20 episodes / 全 `DESIGN_OWNER` |
