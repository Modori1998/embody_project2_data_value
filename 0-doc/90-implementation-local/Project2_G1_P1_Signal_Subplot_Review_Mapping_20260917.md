# Project 2 G1 P1 Signal Subplot → Review Mapping

```text
DATE = 2026-09-17
CONTRACT = P2_G1_AUDIT_FOLDER_V1
G1_P1_SUBPLOT_MAPPING_PATCH = PASS_READY_FOR_USER_TRIAL
NUMBERING_AUTHORITY = published signal_plot.png titles
```

本轮仅 UI help text。未改 `plot.py`、Signal 公式、Review enum、SQLite、Detector。

---

## 0. Drive / Code Authority

Drive：`Project2_G1_Human_Audit_Web_Design_FROZEN_v1_20260916.md`（`1v6ZtopYFfCIWG9kjCOmwJe2C-XWB4xRR`）

```text
status = FROZEN v1.0
P1 Signal Review = first-class audit stage
```

代码：`src/project2_g1/plot.py`、`signals.py`、`config.py`。

真实图：

- `outputs/g1_p1_signal_audit/demo_0/signal_plot.png`
- `outputs/g1_audit_runs/g1_exploratory_audit_20260916_214523_1ba11d9d/diagnostic/demo_0/signal_plot.png`

两图标题编号一致。审核员看到的是 **PNG 上印出的 1–8 编号**。

### plot.py 与已发布 PNG 的差异（本轮不改图）

当前仓库 `plot.py` 若重新出图，会在第 3 行插入 `Motion state evidence`，后续编号 +1，privileged 变成第 9 张。

**本轮 UI 编号对齐已发布 PNG，不对齐尚未重跑的 plot.py 行号。** 否则审核员会对错图。

---

## 1. Actual 8 Subplots

权威编号 = PNG 标题。

### Subplot 1

```text
title = 1. EEF position x/y/z
signals = eef_x, eef_y, eef_z
physical meaning = 末端执行器实现位置（米）
formal / supporting / privileged = FORMAL Layer1 kinematics / primary translation evidence
```

### Subplot 2

```text
title = 2. translation_step_norm / translation_speed
signals = translation_step_norm, translation_speed, smoothed_translation_speed
physical meaning = 实现平移步长与速度；smoothed_speed 仅为 exploratory 可视化
formal / supporting / privileged = FORMAL Layer1 translation
```

### Subplot 3

```text
title = 3. Main-direction change evidence (windowed 3D heading; threshold DATA_CALIBRATION_PENDING)
signals = direction_change_evidence
physical meaning = 窗口化 3D 主方向变化证据（弧度）
formal / supporting / privileged = FORMAL Layer1 direction evidence
```

### Subplot 4

```text
title = 4. gripper qpos / gripper state evidence
signals = gripper_qpos[0], gripper_qpos[1], aperture=q0-q1, gripper_change_evidence
physical meaning = 实际夹爪状态 / 开度变化证据；aperture 不是 OPEN/CLOSED 定义
formal / supporting / privileged = FORMAL Layer2 realized gripper state
```

### Subplot 5

```text
title = 5. gripper command (ACTION_t channel 6, normalized)
signals = gripper_command_raw, gripper_command_change
physical meaning = 控制器夹爪指令（source-native ACTION 第 6 通道），不是实际夹爪轨迹
formal / supporting / privileged = FORMAL Layer3 command intent
```

### Subplot 6

```text
title = 6. EEF rotation delta / angular speed (SUPPORTING EVIDENCE ONLY)
signals = eef_rotation_delta_rad, eef_angular_speed_rad_s
physical meaning = 末端姿态测地线变化 / 角速度
formal / supporting / privileged = FORMAL but supporting-evidence-only vs segmenter
```

对 P1 `ROTATION` 审核项，这仍是该项目的 **Primary 图**。`SUPPORTING EVIDENCE ONLY` 指它不单独产生 Boundary，不是说审核员不用看。

### Subplot 7

```text
title = 7. recorded action change magnitude (SUPPORTING EVIDENCE ONLY; normalized command, not physical velocity)
signals = action_change_magnitude
physical meaning = 记录控制指令变化幅度；归一化 command，不是物理速度
formal / supporting / privileged = FORMAL Layer3 command, supporting-only vs segmenter
```

对 P1 `ACTION` 审核项，这是 **Primary 图**。

### Subplot 8

```text
title = PRIVILEGED_AUDIT_ONLY / NOT_USED_BY_SEGMENTER | Can_pos overlay
signals = Can_pos_x, Can_pos_y, Can_pos_z
physical meaning = 仿真罐子 Object GT 位置
formal / supporting / privileged = PRIVILEGED_AUDIT_ONLY
```

**不属于 Formal P1 Signal Review 的评分依据。** 不得因 Can GT 与 Signal 不一致而改变 Formal PASS/FAIL 语义。

---

## 2. Review Mapping

| Review Item | 中文 | Primary Subplot | Supporting Subplot | 不需要看的图 | 审核问题 |
| --- | --- | --- | --- | --- | --- |
| TRANSLATION | 末端平移 | 1 末端位置；2 平移步长 / 速度 | — | 8 | 视频里移动、减速、停止是否与位置/速度对应 |
| DIRECTION | 主方向变化 | 3 主方向变化证据 | 1 末端位置；2 平移步长 / 速度 | 8 | spike 是否对应真实轨迹转向 |
| GRIPPER | 夹爪 | 4 实际夹爪状态 | 5 夹爪指令 | 8 | 视频开闭是否对应实际状态 |
| ROTATION | 末端旋转 | 6 末端旋转变化 | — | 8 | 明显旋转时旋转证据是否合理 |
| ACTION | 控制指令 | 7 控制指令变化幅度 | 5 夹爪指令 | 8 | 是否有异常跳变 / 时间错位 |
| VIDEO_ALIGNMENT | 视频对齐 | 子图 1–7 整体关键事件时刻 | — | 8 | 视频与 Formal Signal 是否整体提前/滞后 |

Subplot 5 同时服务 GRIPPER（指令 vs 实际）和 ACTION（action channel context）。

---

## 3. Privileged Plot Handling

第 8 图 = `PRIVILEGED_AUDIT_ONLY` Can 位置。

- 不是 6 个 Review Item 的 Primary
- 不是 VIDEO_ALIGNMENT 的评分依据
- P1 Review 区顶部一句提示，不在每项重复

---

## 4. UI Text Added

TRANSLATION

```text
主要看：子图 1「末端位置」；子图 2「平移步长 / 速度」
视频里机器人移动、减速、停止时，这些 Signal 是否有对应变化？
```

DIRECTION

```text
主要看：子图 3「主方向变化证据」
辅助看：子图 1「末端位置」；子图 2「平移步长 / 速度」
主要运动方向明显变化时，Direction Signal 是否有合理响应？
```

GRIPPER

```text
主要看：子图 4「实际夹爪状态」
辅助看：子图 5「夹爪指令」
主要看实际状态；command 用来判断指令与实际执行是否合理对应，两者不必完全重合。
视频里夹爪开闭时，Gripper Signal 是否对应变化？
```

ROTATION

```text
主要看：子图 6「末端旋转变化」
末端姿态明显旋转时，Rotation Signal 是否有合理响应？
```

ACTION

```text
主要看：子图 7「控制指令变化幅度」
辅助看：子图 5「夹爪指令」
Action 是控制器指令，不是实际运动轨迹；只查明显异常、时间错位或不合理跳变。
Action Signal 是否存在明显异常、错位或不合理跳变？
```

VIDEO_ALIGNMENT

```text
主要看：子图 1–7 的关键变化时刻是否与视频同步
重点检查：平移、夹爪、旋转等明显事件是否整体提前/滞后。子图 8 不作为对齐评分依据。
Video 与所有 Signal 是否存在整体时间错位？
```

区顶：

```text
子图 8 为特权审计参考（Can 位置），不属于 Formal Signal 评分项。
```

---

## 5. Files Changed

- `src/project2_g1_audit_web/vocab.py`
- `src/project2_g1_audit_web/app.py`（Jinja globals）
- `src/project2_g1_audit_web/templates/audit.html`
- `src/project2_g1_audit_web/templates/audit.css`（`?v=6`，仅小字号）
- `tests/test_g1_audit_web_layout.py`

未改：`plot.py`、`signals.py`、`reviews.py` schema、P2 布局。

---

## 6. Tests

```text
python -m unittest discover -s tests -p "test_g1_audit_web*.py" -v
Ran 35 tests
OK
```

覆盖：6 项 mapping 文案、Privileged 提示、不把子图 8 写成「主要看」、Save 仍可用、P2 布局未改。
