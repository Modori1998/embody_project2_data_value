# Project 2 G1 Audit Web — Implementation Batch 2 Result

```text
DATE = 2026-09-16
BATCH = Phase 4–5 only
CONTRACT = P2_G1_AUDIT_FOLDER_V1
G1_AUDIT_WEB_BATCH2 = PASS_READY_FOR_HUMAN_AUDIT_TRIAL
MANDATORY_STOP = YES
USER_LAYOUT_CHANGES_PRESERVED = YES
```

本批次实现 P1 Signal Review + P2 Boundary Review + Add Missed Boundary + 条件表单 + Web-owned SQLite append-only persistence + Save / Save & Next。未实现 Human Calibration Export / Batch 3 / G1-P3。

---

## 1. Drive Authority

| 项 | 值 |
| --- | --- |
| Drive file found | YES |
| title | `Project2_G1_Human_Audit_Web_Design_FROZEN_v1_20260916.md` |
| fileId | `1v6ZtopYFfCIWG9kjCOmwJe2C-XWB4xRR` |
| Document status | **FROZEN v1.0** |
| Contract | **P2_G1_AUDIT_FOLDER_V1** |

同步读取：

- `Project_2_Engineering_Design_Master_v1_20260914.md` (`1Cd05zSFR6IF8rXby6RYmocZbmrUDH05b`)
- `Project2_Development_Roadmap_and_Design_Gate_Plan_v1_20260914.md` (`1lQd5Nn4jxwiqwylEg40tCAl1jwDg5O6t`)
- `02_robot_demonstration_mining_autolabel_design.md` (`1tgMOxq2_0taUT7LdHDsn4nvEqookCdAI`)
- `M07_Detector_Iteration_Human_Audit_Web_Design_FROZEN_v1_20260916.md` (`1fqkB2yh12ZDSFTbM6UNkKnKL263V9ZHu`，M07 文档状态 FROZEN v1.2)

```text
G1_WEB_DESIGN_FOUND = YES
G1_WEB_DESIGN_STATUS = FROZEN v1.0
G1_AUDIT_CONTRACT = P2_G1_AUDIT_FOLDER_V1

G1_P1_HUMAN_VISUAL_REVIEW = DEFERRED
G1_P2_STATUS = PASS_READY_FOR_HUMAN_BOUNDARY_REVIEW
G1_P3 = BLOCKED_BY_HUMAN_BOUNDARY_GT
```

无冲突。Human Review SSOT = Web-owned SQLite；Audit Run READ ONLY。M07 只复用 append-only SQLite / Save & Next pattern，不复用 `human_semantic_reviews` / `detector_run_reviews`。

---

## 2. Current UI Baseline

Batch 1 之后用户布局优化全部保留：

- 左侧 Episode 队列
- 主区 **左视频 + Frame 对齐轴 sticky / 右诊断表可滚动**
- 视频原比例 1:1
- 两张 Signal 图一行放在 split 下方
- Frame strip ↔ 表格 ↔ 视频 seek

本批次仅在右侧原有（原先 disabled 的）tab 位置启用：

```text
[P1 Signal Review] [P2 Boundary Review] [Diagnostics｜诊断表]
```

Human Calibration Export 按钮 disabled。未整体替换模板、未恢复 Batch 1 初始上下堆叠布局。

```text
USER_LAYOUT_CHANGES_PRESERVED = YES
```

---

## 3. Phase 4 — P1 Signal Review

每个 Episode 固定六项：`TRANSLATION / DIRECTION / GRIPPER / ROTATION / ACTION / VIDEO_ALIGNMENT`。

下拉：`NOT_REVIEWED｜未审核` `PASS｜通过` `FAIL｜失败` `UNCERTAIN｜不确定`。中文解释以 help text 显示。Comment OPTIONAL textarea。`FAIL` / `UNCERTAIN` 会突出 comment 区，不强制填写。

`episode_note` 存 `episode_note_history`，不写 Audit Folder。

Reuse：相同 `episode_id` + `signal_contract_version` + `signal_contract_hash` 显示 `REUSED_SIGNAL_REVIEW｜复用历史 Signal 审核` 以及 `source_run_id` / `reviewed_at`。hash 不一致不得复用。

---

## 4. Phase 5 — P2 Boundary Review

只审核 `final_boundaries.csv` 中的 Final Boundary。每行显示 `boundary_id / frame / candidate_type｜中文 / reason / supporting_reasons / review_flags` + 条件表单。

- `VALID`：只 Comment
- `REDUNDANT`：Reason REQUIRED；`OTHER` → comment REQUIRED
- `MISALIGNED`：`corrected_frame` + Reason REQUIRED；`0 <= corrected_frame < episode_length`
- `MISSED_BOUNDARY` 不进入预测边界下拉

`+ 补充漏掉的 Boundary` 创建 Web-owned record。显示 ID `HUMAN_ADD_n` 不是权威 identity。权威 identity = `review_id`；编辑用实现列 `added_group_id` 把后续 history 行绑到同一条补充边界。本批次不做 Delete / tombstone。

`predicted_frame` 由 validated Run 的 CSV lookup，不信任浏览器。

---

## 5. Persistence

SQLite：`outputs/g1_audit_web/g1_audit_web_owner.sqlite3`

表：

- `signal_review_history`
- `predicted_boundary_review_history`
- `human_added_boundary_history`（含 `added_group_id` 分组键）
- `episode_note_history`

全部 APPEND ONLY。当前值 = `MAX(review_id)` per Frozen key。`reviewer` 默认 `DESIGN_OWNER`。

浏览器 smoke 使用独立库：

```text
outputs/g1_audit_web/g1_audit_web_batch2_smoke.sqlite3
reviewer = TEMP_BROWSER_TRIAL
```

不写入 Design Owner 正式 SSOT。

---

## 6. Save Workflow

`保存` / `保存并下一条` 已启用。`上一条` / `下一条` 仍为不保存导航。

Save & Next：validate → DB commit → 成功才跳转。失败停留当前页并保留输入（`VALIDATION_FAILED`）。增强：`UNSAVED｜未保存` 指示。

---

## 7. Review Progress / Filters

队列显示：

```text
Signal Review: x / 6
Boundary Review: x / predicted_boundary_count
Missed Added: n
overall = NOT_REVIEWED | IN_PROGRESS | REVIEWED
```

新增 filter：`NOT_REVIEWED` `IN_PROGRESS` `REVIEWED` `SIGNAL_FAIL` `HAS_REDUNDANT` `HAS_MISALIGNED` `HAS_MISSED`。保留 `ALL` `REVIEW_REQUIRED` 与 quality / episode_id / counts。

Human Added 不影响 predicted boundary complete。

---

## 8. Code Changes

新增：

- `src/project2_g1_audit_web/reviews.py`
- `src/project2_g1_audit_web/templates/review_ui.js`
- `tests/test_g1_audit_web_reviews.py`

修改：

- `app.py` POST `/audit/{run_id}/episode/{episode_id}/review`
- `view.py` 队列 filter + progress
- `vocab.py` review / reason codes
- `audit.html` / `audit.css` 局部 review 控件
- `scripts/run_g1_audit_web.py` `--reviewer`

未修改：`src/project2_g1` detector、threshold、legacy `outputs/g1_p2_boundary_audit`、versioned run folder。

---

## 9. Tests

```text
python -m unittest discover -s tests -p "test_g1_audit_web*.py" -v
Ran 30 tests
OK
```

覆盖：PASS/FAIL/UNCERTAIN save/reload、comment、cross-run same-hash reuse、different hash no reuse、VALID/REDUNDANT/MISALIGNED、非法 pairing / frame / OTHER without comment、missed add+edit history、transaction rollback、Save / Save & Next、progress filters、immutability。

---

## 10. Browser Trial

真实 bootstrap run `g1_exploratory_audit_20260916_214523_1ba11d9d`，smoke sqlite：

- 打开 `data/demo_0`
- TRANSLATION = PASS + comment
- B0001 VALID / B0002 REDUNDANT+REDUNDANT_SHORT_PAUSE / B0003 MISALIGNED+corrected_frame=110+MISALIGNED_GRIPPER
- Add Missed frame=80 / MISSED_DIRECTION_CHANGE
- episode_note 保存
- Save 后重开：队列 `IN_PROGRESS`，`Signal Review: 1 / 6`，`Boundary Review: 3 / 3`，`Missed Added: 1`
- Save & Next → `data/demo_32`

条件字段（REDUNDANT reason / MISALIGNED frame）按 decision 显示。Export 保持 disabled。

试用服务器随后切回默认 owner sqlite，供 Design Owner 正式审核（干净 SSOT）。

---

## 11. Source Immutability

```text
outputs/g1_p2_boundary_audit
file_count = 42
tree_fingerprint = 9f22745ca60b6840d6a1844f35cfb3a93dbd229b72d5b4d5ee141312ed16d067
before == after

outputs/g1_audit_runs/g1_exploratory_audit_20260916_214523_1ba11d9d
tree_fingerprint = da1bc0abee824c0ae63b053fbceea53996373ba87e2d063fd8e223cac2e3c4d6
before == after
```

`config_hash` / threshold / Signal / Boundary 未改。

---

## 12. Problems / Unknowns

- `human_added_boundary_history.added_group_id` 是实现分组键，Frozen 15.3 最低列已全部包含；display ID 不是 identity。
- 浏览器 smoke 未写入 `g1_audit_web_owner.sqlite3`。
- 未实现 Human Calibration Export。

---

## 13. Final Status

```text
G1_AUDIT_WEB_BATCH2 = PASS_READY_FOR_HUMAN_AUDIT_TRIAL
```

---

## 14. Explicit Stop

确认：

- 未实现 Human Calibration Export
- 未进入 Batch 3
- 未进入 G1-P3
- 未调整 Detector threshold
- 未生成 Calibration Run
- 未生成 Evaluation Run

```text
STOP IMPLEMENTATION
```

下一步必须由 Design Owner **真正使用网页完成一小轮人工审核**。重点：下拉是否顺手、Reason Code 是否够、Comment 是否够、corrected_frame 是否容易填、Add Missed 是否自然、Save & Next 是否高效、P1/P2 是否容易混淆。

只有明确收到 `CONTINUE_TO_G1_AUDIT_WEB_BATCH3` 才允许开发 Human Calibration Export。
