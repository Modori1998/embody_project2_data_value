# Project 2 G1 Audit Web — P1 Signal Review Layout Patch Result

```text
DATE = 2026-09-17
PATCH = P1 Signal Review Layout only
CONTRACT = P2_G1_AUDIT_FOLDER_V1
G1_P1_LAYOUT_PATCH = PASS_READY_FOR_USER_TRIAL
PRESERVE_CURRENT_P2_LAYOUT = YES
FRAME_CURSOR = DEFERRED
OWNER_SQLITE_POLLUTED = NO
```

本轮是 UI / UX PATCH，不改变 Review 业务语义、SQLite schema、Detector、Signal、Boundary 或 Audit Run Contract。

---

## 1. Drive Authority

| 项 | 值 |
| --- | --- |
| Drive file found | YES |
| title | `Project2_G1_Human_Audit_Web_Design_FROZEN_v1_20260916.md` |
| fileId | `1v6ZtopYFfCIWG9kjCOmwJe2C-XWB4xRR` |
| Document status | **FROZEN v1.0** |
| Contract | **P2_G1_AUDIT_FOLDER_V1** |

确认：

```text
P1 Signal Review = 一等审核阶段
TRANSLATION / DIRECTION / GRIPPER / ROTATION / ACTION / VIDEO_ALIGNMENT
```

业务 enum / identity 未改。Frozen §12 的默认堆叠布局属于页面骨架参考；§24 将 CSS / 按钮布局微调列为实现细节。本补丁按 Design Owner 试用反馈，为 P1 提供独立主工作区。

---

## 2. Problem Confirmed

旧布局对 P2 合适（左 Video + 右 Boundary Review），但对 P1 不合适。

P1 审核对象是整条 Episode 的 **Video ↔ Formal Signal** 对应，不是某个 Boundary frame。原先 Video 在左上、Signal Plot 在页面下方并排超长图，P1 需要大距离滚动才能对照。

---

## 3. P1 Layout Patch

P1 激活时主工作区：

```text
Video + Frame context/nav  |  signal_plot.png（一等主图）  |  P1 Review
≈ 25–30%                  |  ≈ 50–55%                    |  ≈ 20–25%
```

- `signal_plot` 列 `width: 100%; height: auto`，可点击放大（复用已有 dialog）
- `signal_boundary_plot` 不进入 P1 主工作区
- Video 列 sticky；P1 Review 列 sticky（窄屏 Review 回到下方，避免 overflow）
- 顶部增加 P1 说明：这不是 Boundary 审核
- 每项 Signal 增加一句审核问题

切 Tab 为纯前端 `data-mode` 切换，不 reload，表单字段始终在同一 form 中。

---

## 4. P2 Preservation

```text
PRESERVE_CURRENT_P2_LAYOUT = YES
```

P2 / Diagnostics 仍为：

```text
左 Video + Frame Axis sticky
右 Boundary Review / Diagnostic Tables
```

允许的共享小改：下方不再无条件并排两张超长图。P2 主图改为 `signal_boundary_plot`；`signal_plot` 折叠为「次级查看」。未恢复 Batch 1 上下堆叠，未重排 Boundary Review。

---

## 5. Frame Context

Video 区高可见：

```text
Current Frame: XX / T
Current Time: X.XX s
FPS: 20
```

FPS 来自已有 `view.control_hz`（当前 Run 展示逻辑），未改 Audit Contract。`run_meta.json` / `config_snapshot.json` 无独立 fps 字段。

Frame 导航：保留 Frame Axis；新增 `-1 / +1 / -5 / +5` 与 Jump to Frame。播放 `timeupdate` 更新 Current Frame。

```text
Synchronized Frame Cursor = DEFERRED
```

原因：静态 PNG 无可靠 plot 数据区 ↔ frame 像素映射；禁止 magic pixel。

---

## 6. Code Changes

修改：

- `templates/audit.html`
- `templates/audit.css`（`?v=5`）
- `templates/review_ui.js`（`?v=2`，`data-mode`）
- `templates/audit_sync.js`（`?v=5`，frame readout / nav）
- `vocab.py`：展示用 `SIGNAL_AUDIT_QUESTIONS`
- `app.py`：Jinja global `signal_audit_question`（纯展示）
- `tests/g1_audit_web_fixtures.py`：测试 Run 补 `signal_plot.png`
- `tests/test_g1_audit_web_layout.py`

未修改：`reviews.py`、`contract.py`、`registry.py`、`bootstrap.py`、detector / signal / boundary engine。

---

## 7. Tests

```text
python -m unittest discover -s tests -p "test_g1_audit_web*.py" -v
Ran 35 tests
OK
```

覆盖：P1 video + signal_plot + review；P2 split + boundary plot primary；tab JS 不 reload；Save 仍可用；preload=none；owner SQLite 未被测试 reviewer 写入。

---

## 8. Browser Trial

http://127.0.0.1:8766/ 真实 bootstrap run：

- `demo_0` P1：Video / 大 Signal Plot / P1 Review 同一主工作区；Current Frame 0/118；FPS 20
- `demo_0` P2：左 Video、右 Boundary Review，无退化
- `demo_278` P2：9 条 Final Boundary Review 仍在右侧
- 未点击 Save；owner SSOT 仍为 0 行

---

## 9. Screenshots

- `0-doc/Project2_G1_Audit_Web_P1_Layout_Patch_p1_demo0.png`
- `0-doc/Project2_G1_Audit_Web_P1_Layout_Patch_p2_demo0.png`
- `0-doc/Project2_G1_Audit_Web_P1_Layout_Patch_p2_demo278.png`

```text
P1_LAYOUT_PATCH = PASS
P2_LAYOUT_REGRESSION = NO
```

---

## 10. Problems / Deferred

```text
Synchronized Frame Cursor = DEFERRED
```

P2 下方双图并排改为 boundary 主图 + signal_plot 折叠，属于本补丁明确允许的共享小改。

浏览器 smoke 未写入 `g1_audit_web_owner.sqlite3`。

---

## 11. Final Status

```text
G1_P1_LAYOUT_PATCH = PASS_READY_FOR_USER_TRIAL
```

未进入 Batch 3 / Human Calibration Export / G1-P3 / Detector / Threshold。等待 Design Owner 再次试用。
