# G1-P3 Rule Analysis Evidence Export

```text
DIRECTORY_ROLE = G1-P3_RULE_DISCOVERY_REVIEW_EVIDENCE
EVIDENCE_STATUS = READY_FOR_WEB_RULE_DISCOVERY_REVIEW
FORMAL_DETECTOR_INPUT = NO
SOURCE_OF_TRUTH = GITHUB_MAIN
```

---

## Purpose

本目录**只**用于网页端 **Rule Discovery Review｜候选规则发现评审** 所需的最小事件级证据。

它是**只读分析导出**，回答以下问题所需的原始数据：

1. 哪些 Direction FP 可以由 **Motion Sufficiency**（运动充分性）解释；
2. 哪些 high-displacement FP 可能存在 **speed valley**（相对速度谷）；
3. 是否存在 trajectory **reversal / jitter / detour**；
4. VALID counterexample 为什么虽然低速或低位移仍应保留；
5. 是否存在简单、可解释的二维/三维联合规则。

**本目录不是 Formal Detector input。**
不包含任何最终 rule、threshold、cutoff、classifier 或 A/B/C 规则选择。

---

## Source Identity

```text
baseline_run_id        = g1_calibration_20260918_141032_781e5d8b
baseline_score_id      = g1_baseline_score_20260918_155714_42295cc6
canonical_gt_snapshot  = g1_canonical_gt_20260918_131636_c9916b89
stage_a0_analysis_id   = g1_stage_a0_20260918_162418_7cbf826e
rule_family_a prep_id  = g1_rule_family_a_prep_20260918_173501
config_hash            = dde590e759a31cb8c865369e18256ebecbbd01bc94a58e1d3ca695bb50f2a630
signal_contract_hash   = 24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d
calibration_protocol   = FROZEN_v1.1
git HEAD at export     = eac8603ddaac9d3223ddd96ad14edaabc87b0d9e
```

**Dataset identity**

```text
dataset        = RoboMimic v1.5 Can/MH (low_dim + raw dual-HDF5)
raw HDF5       = C:\Users\95611\embody\1-dataset\robomimic\demo_v15.hdf5
raw size       = 79780388 bytes
control rate   = 20 Hz (nominal dt = 0.05 s)
```

**HUMAN_LABEL_SOURCE**

```text
HUMAN_LABEL_SOURCE = g1_stage_a0_20260918_162418_7cbf826e /
                     stage_a0_direction_event_analysis.csv
                     (frozen Canonical GT / Baseline Scoring / Stage A0 lineage)
```

Human label **不**来自重新读取 Web SQLite，**不**来自重新人工标注，**不**修改 Human Review。

---

## Cohort

```text
VALID_DIRECTION = 17
DIRECTION_FP    =  9
TOTAL           = 26

DIRECTION_FP by mode : MODE_01 = 3, MODE_02 = 3, MODE_03 = 1, UNASSIGNED = 2
package              : SEED = 13, FRESH = 13
```

`NON_DIRECTION_FP = 1`（`demo_255@135 IDLE_TO_MOVE`，outside Rule Family A scope）
**不进入**本证据包主表。

---

## Files

| File | Rows | Columns | Size (bytes) | SHA256 |
|---|---:|---:|---:|---|
| `01_stage_a0_direction_event_analysis.csv` | 26 (+header) | 61 | 36,721 | `db6060e80ae0353e9d74d41ffca990d2d177027458ef65cca479e0cd239d760e` |
| `02_direction_event_window_trace.csv` | 645 (+header) | 43 | 410,697 | `f4c081df2f83f3a3650361f5f5afb7cb3936569540571255305e13c5ce457fb6` |
| `README.md` | — | — | 16,929 | (self; see export run log) |

File size gate：event CSV < 1 MB ✅ ｜ trace CSV < 5 MB ✅ ｜ README < 100 KB ✅
**No Git LFS.**

### Canonical bytes / line endings

上表的 size 与 SHA256 是 **canonical LF** 形式的字节数，即 **GitHub blob（SSOT artifact）的真实内容**。

```text
line endings = LF (\n) only, no CR
no BOM
encoding     = UTF-8
```

导出脚本显式使用 `lineterminator="\n"`。**必须如此**：本仓库 `core.autocrlf=true`，
Python `csv` 模块默认写 `\r\n`，若不在脚本里固定 LF，`git commit` 会把 CRLF 静默改写成 LF，
导致「本地被哈希的文件」与「GitHub 上的 blob」字节不同、README 记录的 SHA256 无法复核。
固定 LF 后 working tree == git blob == GitHub artifact，SHA256 可独立验证。

> 本地若重新 clone 且 `core.autocrlf=true`，checkout 会把这两个 CSV 还原为 CRLF 工作副本。
> 复核 SHA256 时请以 **repo blob**（`git cat-file blob <oid>` / GitHub 原始文件）为准，或先
> `git checkout -- .` 之外的方式取 LF 版本；`scripts/export_g1_p3_rule_analysis_evidence.py`
> 重新生成的文件始终是 LF，可直接复核。

---

## Artifact 1 — Event-Level Table

源：`outputs/g1_p3_stage_a0/g1_stage_a0_20260918_162418_7cbf826e/stage_a0_direction_event_analysis.csv`

标准化方式：**保留源文件全部 58 列（逐字符原样，不重新舍入）**，仅追加 3 个别名字段：

| Alias column | Meaning |
|---|---|
| `event_frame` | = 源 `pred_frame`（Stage A0 事件帧） |
| `event_type` | 固定 `DIRECTION_CHANGE` |
| `support` | = 源 `support_combination` |

**语义字段映射（web 端可直接解析）**

| Required semantic | Actual column in this file |
|---|---|
| `episode_id` | `episode_id`（`data/demo_XXX`） |
| `event_frame` | `event_frame`（别名，= `pred_frame`） |
| `human_class` | `human_class`（`VALID_DIRECTION` / `DIRECTION_FP`） |
| `package` / `source_package` | `source_package`（`SEED` / `FRESH`） |
| `error_mode` | `error_mode`（`MODE_01/02/03`、`UNASSIGNED`、VALID 为空） |
| `evidence_value` | `evidence_value` |
| `heading_angle_rad` | `heading_angle_rad` |
| `run_length` | `run_length` |
| `translation_speed_at_event` | `translation_speed_at_event` |
| `smoothed_speed_at_event` | `smoothed_speed_at_event` |
| `local_speed_min` | `local_speed_min` |
| `idle_fraction_in_window` | `idle_fraction_in_window` |
| `pre/post/min_displacement_m` | `pre_displacement_m` / `post_displacement_m` / `min_displacement_m` |
| `distance_to_nearest_gripper_final` | `distance_to_nearest_gripper_final` |
| `signed_distance_to_next_gripper` | `signed_distance_to_next_gripper` |
| `support` / supporting_reasons | `support_combination`（+ 别名 `support`）、`rotation_support`、`action_support` |
| candidate / final lineage | `pred_boundary_id`、`gt_id`、`representative_candidate_id`、`member_candidate_count`、`member_candidate_types`、`is_independent_direction_final`、`is_gripper_primary_merged` |

源文件 `evidence_value_provenance`、`displacement_provenance`、`heading_homology_note` 等 provenance 列全部保留。

---

## Event Window（Artifact 2）

```text
ANALYSIS_EXPORT_WINDOW
WINDOW_LEFT  = 12 frames
WINDOW_RIGHT = 12 frames
relative_frame ∈ [-12, +12]
20 Hz  ->  ±12 frames = ±0.6 s
```

> 这是 **ANALYSIS_EXPORT_WINDOW**，**不是 Detector 参数**。
> **禁止**把 ±12 写入正式 Detector Contract。它只用于本次证据导出。

**Edge clip**：episode 边缘允许 clip。本包仅 1 个事件被裁剪：

| event | window_left_frames | window_right_frames | episode_n_frames |
|---|---:|---:|---:|
| `demo_242@224` | 12 | 8 | 232 |

其余 25 个事件均为完整 25 行（`relative_frame = -12 … +12`）。
每个事件实际可用行数记录在 `window_left_frames` / `window_right_frames` / `edge_clipped` / `episode_n_frames` 列中。

---

## Field Semantics

### Identity

`episode_id`（`data/demo_XXX`）、`episode_key`（`demo_XXX`）、`event_frame`、`frame`（绝对帧号）、
`relative_frame`（= `frame - event_frame`）、`time_relative_s`（= `relative_frame / 20`）、
`human_class`、`source_package`、`error_mode`、`event_type`（固定 `DIRECTION_CHANGE`）。

### Motion｜运动字段（逐帧，Formal Signal）

| Column | Definition |
|---|---|
| `eef_x` / `eef_y` / `eef_z` | `robot0_eef_pos[t]`，单位 **meter**（P1 freeze） |
| `step_dx` / `step_dy` / `step_dz` | `delta[t] = pos[t] - pos[t-1]`，`delta[0] = 0`（meter） |
| `step_displacement_m` | `‖delta_xyz[t]‖₂`，即该帧实际移动距离（meter） |
| `translation_speed_mps` | `step_displacement_m / 0.05`（meter / second） |
| `smoothed_speed_mps` | `smoothed_translation_speed[t]`（因果滑动平均，P1 exploratory window=5） |
| `direction_evidence` | `direction_change_evidence[t]` = `arccos(cosine)` 于左右 W=8 窗口向量和；**每一帧都自然有定义** |

### Path Length｜路径长度

> **Path Length = 窗口内每帧实际移动距离之和**（Σ `step_displacement_m`）。

沿用 frozen 的半开区间约定（`heading_vector(a,b) = Σ delta[a:b]`）：

```text
left_path_length_m  = Σ step_displacement_m  for relative_frame ∈ [-12, -1]
right_path_length_m = Σ step_displacement_m  for relative_frame ∈ [ 0, +11]
```

### Net Displacement｜净位移

> **Net Displacement = 窗口起点到终点的直线距离**（向量和的范数）。

```text
left_net_displacement_m  = ‖Σ delta[t-12 : t]‖
right_net_displacement_m = ‖Σ delta[t : t+12]‖
```

与 Artifact 1 的 `pre_displacement_m` / `post_displacement_m` **函数形式完全相同**，仅窗口由 W=8 扩到 W=12。

### Straightness Ratio｜直线性比值

> **Straightness Ratio = 净位移 / 路径长度**，理论范围 0 ~ 1。

```text
left_straightness  = left_net_displacement_m  / left_path_length_m
right_straightness = right_net_displacement_m / right_path_length_m
```

`path_length < 1e-9` → **NaN**（不制造异常大值）。

### Relative Speed Valley｜相对速度谷

> **Relative Speed Valley = 切点附近速度相对左右运动参考速度的下降程度**。

```text
left_speed_reference  = median(translation_speed_mps) over relative_frame ∈ [-12, -4]
right_speed_reference = median(translation_speed_mps) over relative_frame ∈ [ +4, +12]
event_speed_reference = min(translation_speed_mps)    over relative_frame ∈ [ -2,  +2]

speed_valley_ratio_left  = event_speed_reference / left_speed_reference
speed_valley_ratio_right = event_speed_reference / right_speed_reference
speed_valley_ratio_min   = min(speed_valley_ratio_left, speed_valley_ratio_right)
```

**实际定义声明**：`event_speed_reference` 采用 **minimum**（非 median）。
**分母保护规则**：`|denominator| < 1e-9` → 输出 **NaN**，不做硬除。本包未触发该规则。

> 本轮**不选择任何 ratio threshold**。ratio 只是只读描述量。

### Reversal / Turn Context

```text
left_to_right_cosine = cos( left_net_vector , right_net_vector )   (W=12)
turn_angle_rad       = arccos(clip(left_to_right_cosine, -1, 1))
```

**turn_angle_rad 与 direction evidence 的关系（必须明确）**

`turn_angle_rad` 与 `direction_change_evidence` / `heading_angle_rad` **属于同一函数族**
（都是左右窗口向量和之间的夹角），**不是独立的新信号**：

- 差别**仅在窗口宽度**：`direction_evidence` 用冻结 W=8；`turn_angle_rad` 用 ANALYSIS_EXPORT_WINDOW W=12。
- 因此 `turn_angle_rad ≠ evidence_value` 数值上不等价（窗口不同），但也**不构成独立的第三维信息**。
- 本包**不把它当作独立 feature**。Stage A0 已确认 `heading_angle_rad` 与 `direction_change_evidence`
  在窗口位移 ≥ 0.005 m 时同源（`heading_homology_note = HOMOLOGOUS_..._NOT_INDEPENDENT`），
  `turn_angle_rad` 只是该同源量的 W=12 版本。

真正独立于「方向角度」维度的是**运动幅度维度**：`translation_speed` / `path_length` / `net_displacement` /
`straightness` / `speed_valley_ratio`。

### Gripper Context

| Column | Definition |
|---|---|
| `gripper_value` | `gripper_aperture[t] = qpos[t,0] - qpos[t,1]`（source-native aperture，**不是** OPEN/CLOSED 定义） |
| `gripper_change_evidence` | `‖qpos[t] - qpos[t-1]‖`（Formal per-frame gripper change magnitude） |

**`gripper_transition_flag` 作为正式 signal 不存在**（NOT_AVAILABLE）。Formal Signal Contract 中
gripper 相关的逐帧量只有 `gripper_aperture` / `gripper_change_evidence`；本包不伪造该 flag。

**未**从 simulator object state 推导任何 gripper / object semantic。

### Action / Rotation Supporting Context

`rotation_support_flag`、`action_support_flag`：来自 Stage A0 `rotation_support` / `action_support`，
为 **event-level metadata**，重复到该 event 的所有 trace 行。

```text
supporting only —— 不得升级为 Formal Boundary Evidence。
```

### Event-level fields repeated on trace rows

以下字段为 event-level，重复写入该 event 的全部 trace 行：
`speed_valley_*`、`*_path_length_m`、`*_net_displacement_m`、`*_straightness`、
`left_to_right_cosine`、`turn_angle_rad`、`window_*_frames`、`edge_clipped`、`episode_n_frames`、
`heading_angle_rad_event`、`rotation_support_flag`、`action_support_flag`。

---

## Consistency Check（Artifact 1 ↔ Artifact 2）

| Check | Result |
|---|---|
| `episode_id` / `event_frame` / `human_class` / `error_mode` / `source_package` 一致 | **PASS**（26/26 完全一致） |
| `direction_evidence` @ event frame vs Stage A0 `evidence_value` | **PASS**，max abs delta = **0.00e+00**（逐条精确相等） |
| `heading_angle_rad_event` vs Stage A0 `heading_angle_rad` | **PASS**（同源重复） |
| W=8 displacement 由 EEF path 恢复 vs Stage A0 `pre_displacement_m` | **PASS**，max abs delta = **6.94e-18** |
| W=8 displacement 由 EEF path 恢复 vs Stage A0 `post_displacement_m` | **PASS**，max abs delta = **6.94e-18** |

**定义差异（不硬写 PASS）**：
Artifact 2 的 `left_net_displacement_m` / `right_net_displacement_m` 使用 **W=12**，
Artifact 1 的 `pre_displacement_m` / `post_displacement_m` 使用 **冻结 W=8**。
二者**函数形式相同、窗口宽度不同**，因此**数值上不等价，不能直接比较**。
上面第 4、5 行用「同样的 W=8 公式重新计算」完成一致性验证，而非拿 W=12 去对齐 W=8。

---

## Validation

```text
event_count                 = 26
VALID_DIRECTION             = 17
DIRECTION_FP                =  9
trace_rows                  = 645
trace_unique_events         = 26
relative_frame_range        = -12 .. +12
duplicate_keys              = 0
inf_count                   = 0
NaN_summary                 = 无 NaN；无 inf
identity_consistent         = True
critical_event_coverage     = 12/12 PRESENT
determinism (byte-identical re-run) = PASS
```

**NaN / inf audit**：trace 中 **无 inf**；**无 NaN**。
原因是所有 26 个事件的左右参考窗口与 path/net 窗口在 clip 后仍非空（唯一被裁剪的
`demo_242@224` 右侧仍有 8 帧）。NaN 规则已实现并保留（分母 < 1e-9、path_length < 1e-9 → NaN），
本包未触发。

### Critical Event Coverage

| event | class | present |
|---|---|---|
| `demo_242@41` | DIRECTION_FP MODE_01 | ✅ |
| `demo_242@60` | DIRECTION_FP MODE_01 | ✅ |
| `demo_242@78` | DIRECTION_FP MODE_01 | ✅ |
| `demo_278@83` | DIRECTION_FP MODE_02 | ✅ |
| `demo_278@105` | DIRECTION_FP MODE_02 | ✅ |
| `demo_278@125` | DIRECTION_FP MODE_02 | ✅ |
| `demo_242@136` | DIRECTION_FP MODE_03 | ✅ |
| `demo_162@211` | DIRECTION_FP UNASSIGNED | ✅ |
| `demo_255@116` | DIRECTION_FP UNASSIGNED | ✅ |
| `demo_242@224` | VALID_DIRECTION SEED | ✅ |
| `demo_255@14` | VALID_DIRECTION FRESH | ✅ |
| `demo_260@75` | VALID_DIRECTION FRESH | ✅ |

筛选方式（示例）：

```bash
grep -E '^data/demo_242,demo_242,41,' 02_direction_event_window_trace.csv
grep -E '^data/demo_278,demo_278,(83|105|125),' 02_direction_event_window_trace.csv
```

---

## Privileged Signal Audit

```text
PRIVILEGED_SIGNAL_USED = NO
```

只使用：

- EEF position（`robot0_eef_pos`）
- Formal speed（`translation_speed` / `smoothed_translation_speed`）
- Formal direction evidence（`direction_change_evidence`）
- gripper（`robot0_gripper_qpos` → aperture / change）
- recorded action supporting info、rotation supporting info
- Human calibration label / lineage

**未使用**：simulator object GT、object pose、reward、success、done、terminal semantic、
privileged contact state、task completion state，或任何 G1 Formal Signal Contract 禁止的 privileged field。
（未读取 `next_obs` / `states` / `rewards` / `dones` / `obs/object`。）

---

## Determinism

```text
DETERMINISTIC = YES
固定排序      = episode_id ASC, event_frame ASC, frame ASC
random sampling = NONE
```

相同输入重复运行 → **CSV bytes 完全一致**（`--check` 已通过，byte-identical 含 LF 行尾）。

---

## Reproduce

```bash
python scripts/export_g1_p3_rule_analysis_evidence.py
python scripts/export_g1_p3_rule_analysis_evidence.py --check   # determinism gate
```

需要 `numpy` + `h5py`（读取 READ_ONLY raw HDF5）。

---

## Non-Scope

```text
NO DETECTOR CHANGE
NO THRESHOLD SELECTION
NO CLASSIFIER
NO PARAMETER SEARCH
NO NEW HUMAN LABEL
NO PRIVILEGED SIGNAL
NO FINAL RULE
```

```text
DETECTOR_MODIFIED        = NO
CONFIG_MODIFIED          = NO
PARAMETER_SEARCH_EXECUTED= NO
THRESHOLD_SELECTED       = NO
CLASSIFIER_TRAINED       = NO
HUMAN_LABEL_MODIFIED     = NO
FROZEN_PROTOCOL_MODIFIED = NO
ENGINEERING_MASTER_MODIFIED = NO
ROADMAP_MODIFIED         = NO
RULE_FAMILY_A_REVIEW_MODIFIED = NO
```

本目录**不**给出 best rule / best threshold / best speed valley ratio / best straightness cutoff /
A/B/C rule winner / classifier accuracy / F1 optimization。**只提供数据证据。**
