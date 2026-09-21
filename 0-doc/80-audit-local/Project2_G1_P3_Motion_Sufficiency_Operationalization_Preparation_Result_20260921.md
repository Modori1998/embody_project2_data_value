# Project 2 G1-P3 Motion Sufficiency Operationalization Preparation Result

```text
DATE = 2026-09-21
DOCUMENT_STATUS = ANALYSIS_PREPARATION_RESULT
TASK = MOTION_SUFFICIENCY_OPERATIONALIZATION_PREPARATION
SOURCE_OF_TRUTH = GITHUB_MAIN
G1_P3_DIRECTION_RULE_SHAPE = FROZEN_POST_MOTION_SUFFICIENCY_AND_TRAJECTORY_COHERENCE

NUMERIC_THRESHOLD_FROZEN = NO
WINDOW_FROZEN = NO
DETECTOR_MODIFIED = NO
CONFIG_GENERATED = NO
PARAMETER_SEARCH_EXECUTED = NO
STAGE_A_EXECUTED = NO
STAGE_B_EXECUTED = NO
PROTOCOL_PATCH_CREATED = NO
```

本轮回答的是 **operationalization｜操作化定义准备**，不是 threshold selection。
本文件**不**给出任何最终数值规则，也**不**修改 Frozen Design。

---

## 1. Git / SSOT State

```text
PRE_TASK_HEAD  = 66e4d5d81b4cfa574d551f58b5b65f4a89acfcc4
POST_PULL_HEAD = 5887c21abffbacec359d68a8d6a6c17a82179ab9
REMOTE_MAIN    = 5887c21abffbacec359d68a8d6a6c17a82179ab9
```

| Gate | Result |
|---|---|
| `git status --short` 前置 | clean |
| `git pull --ff-only origin main` | Fast-forward `66e4d5d..5887c21`（新增 Frozen Rule Shape 文档 1 个） |
| `LOCAL_HEAD == REMOTE_MAIN` | **PASS** |
| `5887c21…` is ancestor of HEAD | **PASS**（`merge-base --is-ancestor`） |

禁止项均未执行：无 `stash`、无 `reset`、无 `checkout` 丢弃修改、无覆盖本地文件。

---

## 2. Frozen Authority Readback

读取 `0-doc/10-design-review/Project2_G1_P3_Motion_Sufficiency_Rule_Shape_FROZEN_v1_20260921.md`。

| Item | Frozen Value | Readback |
|---|---|---|
| `DOCUMENT_STATUS` | `FROZEN_RULE_SHAPE_v1` | **PASS** |
| `G1_P3_DIRECTION_RULE_SHAPE` | `FROZEN_POST_MOTION_SUFFICIENCY_AND_TRAJECTORY_COHERENCE` | **PASS** |
| `NUMERIC_THRESHOLD_FROZEN` | `NO` | **PASS** |
| `WINDOW_FROZEN` | `NO` | **PASS** |
| `DETECTOR_MODIFIED` | `NO` | **PASS** |
| `POST_MOTION_SUFFICIENCY` | `SUPPORTED_AS_FORMAL_RULE_COMPONENT` | **PASS** |
| `TRAJECTORY_COHERENCE` | `SUPPORTED_AS_FORMAL_RULE_COMPONENT` | **PASS** |
| `NEXT_GATE` | `MOTION_SUFFICIENCY_OPERATIONALIZATION_PREPARATION` | **PASS** |

```text
FROZEN_RULE_SHAPE_READBACK = PASS
```

本轮严格遵守 §11 `Operationalization Search Boundary`：只比较 4 个候选定义，
不引入 acceleration / jerk / curvature / action magnitude / rotation magnitude /
new gripper feature / new heading feature，不做窗口 sweep。

---

## 3. Cohort Freeze

```text
VALID_DIRECTION = 17
DIRECTION_FP    = 9
TOTAL           = 26
package         : SEED = 13, FRESH = 13
DIRECTION_FP by mode : MODE_01 = 3, MODE_02 = 3, MODE_03 = 1, UNASSIGNED = 2
```

未加入 `NON_DIRECTION_FP`（`demo_255@135 IDLE_TO_MOVE`）、其它 episode 或未审核数据。

---

## 4. Candidate Operational Definitions

### 4.1 Post-motion Sufficiency

| ID | Field | Source | Definition | Provenance |
|---|---|---|---|---|
| **P8** | `post_speed_mean` | `01_stage_a0_direction_event_analysis.csv` | `mean(translation_speed_mps)` over `relative_frame ∈ [0, +7]` | 既有 Stage A0 派生字段（`speed_context_provenance = FORMAL_SIGNAL W=8 FROZEN_P1_DIRECTION_WINDOW`），**原样使用，不重新解释** |
| **P12** | `right_speed_reference` | `02_direction_event_window_trace.csv`（`relative_frame = 0` 行） | `median(translation_speed_mps)` over `relative_frame ∈ [+4, +12]` | 当前 `ANALYSIS_DERIVED_FIELD`（**未冻结**） |

### 4.2 Trajectory Coherence

| ID | Source | Definition |
|---|---|---|
| **C8** | 由现有 trace 重新派生（不读新 raw data） | `min(left_straightness_w8, right_straightness_w8)`；left `[-8,-1]`，right `[0,+7]` |
| **C12** | `relative_frame = 0` 行既有 `left_straightness` / `right_straightness` | `min(left_straightness, right_straightness)`，窗口保持 README 当前定义（`[-12,-1]` / `[0,+11]`） |

```text
path_length      = Σ step_displacement_m
net_displacement = norm(Σ [step_dx, step_dy, step_dz])
straightness     = net_displacement / path_length
path_length < 1e-9  ->  NaN
```

**一致性验证（source consistency）**

| Check | Max abs delta | Result |
|---|---:|---|
| P8 vs 由 trace `[0,+7]` 重算 | 5.551e-17 | **PASS** |
| P12 vs 由 trace `[+4,+12]` 重算 | 0.000e+00 | **PASS** |
| C12 vs 由 trace `[-12,-1]`/`[0,+11]` 重算 | 3.331e-16 | **PASS** |
| C8 确定性重算 | 0.000e+00 | **PASS** |

---

## 5. Single-feature Distribution Review

`q25/median/q75` 采用线性插值分位数。

### 5.1 P8 — W8 post speed

| cohort | n | min | q25 | median | q75 | max |
|---|---:|---:|---:|---:|---:|---:|
| VALID | 17 | 0.05150 | 0.07799 | 0.08993 | 0.11577 | 0.21391 |
| FP | 9 | 0.02106 | 0.03232 | 0.03778 | 0.05711 | 0.10691 |
| SEED VALID | 6 | 0.05187 | 0.07637 | 0.08689 | 0.13909 | 0.21391 |
| FRESH VALID | 11 | 0.05150 | 0.08061 | 0.08993 | 0.11318 | 0.17262 |
| SEED FP | 7 | 0.02106 | 0.02856 | 0.03778 | 0.04819 | 0.10691 |
| FRESH FP | 2 | 0.03232 | 0.05039 | 0.06847 | 0.08654 | 0.10461 |

```text
range_overlap = 0.05541   iqr_overlap = 0.00000   FP below VALID floor = 6 / 9
```

### 5.2 P12 — W12 sustained post-motion reference

| cohort | n | min | q25 | median | q75 | max |
|---|---:|---:|---:|---:|---:|---:|
| VALID | 17 | 0.05348 | 0.08176 | 0.11113 | 0.14690 | 0.17718 |
| FP | 9 | 0.02176 | 0.02699 | 0.03183 | 0.04169 | 0.11559 |
| SEED VALID | 6 | 0.07895 | 0.08528 | 0.11516 | 0.15050 | 0.16685 |
| FRESH VALID | 11 | 0.05348 | 0.07775 | 0.11113 | 0.13401 | 0.17718 |
| SEED FP | 7 | 0.02313 | 0.02714 | 0.03183 | 0.04015 | 0.07506 |
| FRESH FP | 2 | 0.02176 | 0.04521 | 0.06867 | 0.09213 | 0.11559 |

```text
range_overlap = 0.06211   iqr_overlap = 0.00000   FP below VALID floor = 7 / 9
```

### 5.3 C8 — W8 min straightness

| cohort | n | min | q25 | median | q75 | max |
|---|---:|---:|---:|---:|---:|---:|
| VALID | 17 | 0.81572 | 0.89003 | 0.90289 | 0.94622 | 0.98294 |
| FP | 9 | 0.80927 | 0.82561 | 0.90734 | 0.92695 | 0.95549 |
| SEED VALID | 6 | 0.81572 | 0.84580 | 0.90896 | 0.94164 | 0.94689 |
| FRESH VALID | 11 | 0.82499 | 0.89557 | 0.90289 | 0.95394 | 0.98294 |
| SEED FP | 7 | 0.80927 | 0.86647 | 0.92373 | 0.93092 | 0.95549 |
| FRESH FP | 2 | 0.81298 | 0.82256 | 0.83215 | 0.84173 | 0.85132 |

```text
range_overlap = 0.13977   iqr_overlap = 0.03692   FP below VALID floor = 2 / 9
```

### 5.4 C12 — W12 min straightness

| cohort | n | min | q25 | median | q75 | max |
|---|---:|---:|---:|---:|---:|---:|
| VALID | 17 | 0.76987 | 0.84129 | 0.87285 | 0.91782 | 0.97301 |
| FP | 9 | 0.55287 | 0.74762 | 0.80861 | 0.91041 | 0.95120 |
| SEED VALID | 6 | 0.76987 | 0.78568 | 0.83618 | 0.89869 | 0.93407 |
| FRESH VALID | 11 | 0.77611 | 0.86639 | 0.90110 | 0.91554 | 0.97301 |
| SEED FP | 7 | 0.65103 | 0.76459 | 0.88416 | 0.92950 | 0.95120 |
| FRESH FP | 2 | 0.55287 | 0.61680 | 0.68074 | 0.74467 | 0.80861 |

```text
range_overlap = 0.18133   iqr_overlap = 0.06911   FP below VALID floor = 3 / 9
```

### 5.5 Distribution reading

- **P8 / P12**：IQR **完全不重叠**（`iqr_overlap = 0`），VALID / FP 存在真实分布位移。
  VALID 的 q25（P8 = 0.07799 / P12 = 0.08176）已高于 FP 的 max 减一个异常值。
- **C8 / C12**：IQR **明显重叠**（0.03692 / 0.06911），中位数几乎不可分
  （C8: 0.90289 vs 0.90734；C12: 0.87285 vs 0.80861）。
  Trajectory 维度的分离**不来自分布位移，只来自极少数 FP 的极端尾部值**。
  这是本轮最重要的结构性发现。

---

## 6. Zero-VALID Envelope Diagnostic

```text
VALID_FLOOR(feature) = 当前 17 VALID 中该 feature 的 minimum
FP_BELOW_VALID_FLOOR = feature < VALID_FLOOR
```

> **这是 Calibration Envelope Diagnostic｜校准包络诊断，不是 Detector threshold。**
> 严禁读作 “因此 threshold = VALID_FLOOR”。

| feature | VALID_FLOOR | floor set by | 2nd lowest VALID | VALID 侧余量 | FP below | 最近被覆盖 FP | FP 侧余量 | 最近未覆盖 FP | 间距 |
|---|---:|---|---|---:|---:|---|---:|---|---:|
| P8 | 0.051498 | `demo_255@14` | 0.051873 | **0.000375** | 6/9 | `demo_242@78` 0.039270 | 0.012228 | `demo_242@60` 0.057106 | 0.005608 |
| P12 | 0.053480 | `demo_260@66` | 0.059049 | **0.005569** | 7/9 | `demo_278@105` 0.041691 | 0.011789 | `demo_242@60` 0.075062 | 0.021582 |
| C8 | 0.815722 | `demo_278@39` | 0.824994 | **0.009272** | 2/9 | `demo_162@211` 0.812976 | **0.002747** | `demo_242@136` 0.825608 | 0.009886 |
| C12 | 0.769871 | `demo_278@39` | 0.770550 | **0.000680** | 3/9 | `demo_242@60` 0.747618 | 0.022252 | `demo_278@83` 0.781553 | 0.011682 |

**FP event lists**

```text
P8  below floor (6) : demo_242@78, demo_242@136, demo_255@116,
                      demo_278@83, demo_278@105, demo_278@125
P12 below floor (7) : 上述 6 个 + demo_242@41
C8  below floor (2) : demo_162@211, demo_278@83
C12 below floor (3) : demo_162@211, demo_242@60, demo_242@136
```

**关键诊断结论**

1. **P8 的 VALID 包络几乎是刀锋**：floor 由 `demo_255@14`（0.051498）设定，
   第二低 `demo_242@224`（0.051873）仅高出 **0.000375**。
2. **P12 的 VALID 包络显著更稳**：floor 由 `demo_260@66` 设定，
   第二低 `demo_255@63` 高出 **0.005569**（约为 P8 的 **14.9 倍**余量）。
   原因是 `[+4,+12]` 的 median 抑制了切点后立即过渡帧，
   而 `demo_255@14` / `demo_242@224` 恰恰是“切点瞬间速度低、但后段持续”的 VALID 反例。
3. **C8 的 FP 包络是刀锋**：最近被覆盖 FP `demo_162@211`（0.812976）
   距 floor 仅 **0.002747**；且 floor（`demo_278@39`，VALID）与
   `demo_278@83`（FP，0.809270）**同属 episode `demo_278`**，是同一集内的近似并列。
4. **C12 的 VALID 包络是刀锋**：floor 0.769871（`demo_278@39`），
   第二低 `demo_230@108` 0.770550 仅高出 **0.000680**。
   C12 的 floor 完全由 SEED 事件决定。
5. 两个 trajectory 候选都是**一侧刀锋**：C8 刀锋在 FP 侧，C12 刀锋在 VALID 侧。

---

## 7. Joint Rule-shape Diagnostic

诊断条件（**只读**）：

```text
Pair8  : FP explained if P8  < min_VALID(P8)   OR C8  < min_VALID(C8)
Pair12 : FP explained if P12 < min_VALID(P12)  OR C12 < min_VALID(C12)
```

| Pair | FP covered | VALID rejected | unexplained FP |
|---|---:|---:|---|
| **Pair8** | **7 / 9** | **0 / 17** | `demo_242@41`, `demo_242@60` |
| **Pair12** | **9 / 9** | **0 / 17** | （无） |

`VALID rejected = 0` 已**实际逐条计算验证**（非预设），因为使用 VALID envelope。
Pair12 复现了 Frozen Design §6 记录的 Calibration observation（9/9 + 0/17）。

**Pair8 的两条未解释 FP 是本轮核心**

| event | 为什么 W8 漏掉 |
|---|---|
| `demo_242@41` | 衰减发生在 `relative_frame ≥ +8`，**落在 W8 post 窗口 `[0,+7]` 之外**；只有 P12 覆盖。 |
| `demo_242@60` | 轨迹不一致发生在 left `relative_frame ∈ [-12,-9]`，**落在 W8 left 窗口 `[-8,-1]` 之外**；只有 C12 覆盖。 |

两条都是 **`demo_242` 同一 episode、同一 MODE_01**。也就是说：
**W12 相对 W8 的全部增量，当前仅由 1 个 episode 的 2 个事件承载。**

---

## 8. Critical Counterexample Review

`P8b/P12b/C8b/C12b` = 是否低于对应 VALID floor。

| event | human_class | mode | P8 | P12 | C8 | C12 | P8b | P12b | C8b | C12b | Pair8 | Pair12 |
|---|---|---|---:|---:|---:|---:|:-:|:-:|:-:|:-:|:-:|:-:|
| `demo_242@41` | DIRECTION_FP | MODE_01 | 0.106912 | 0.038618 | 0.923730 | 0.910406 | f | **t** | f | f | ✗ | **✓** |
| `demo_242@60` | DIRECTION_FP | MODE_01 | 0.057106 | 0.075062 | 0.907340 | 0.747618 | f | f | f | **t** | ✗ | **✓** |
| `demo_242@78` | DIRECTION_FP | MODE_01 | 0.039270 | 0.031833 | 0.934892 | 0.951199 | **t** | **t** | f | f | ✓ | ✓ |
| `demo_278@83` | DIRECTION_FP | MODE_02 | 0.021065 | 0.026987 | 0.809270 | 0.781553 | **t** | **t** | **t** | f | ✓ | ✓ |
| `demo_278@105` | DIRECTION_FP | MODE_02 | 0.032403 | 0.041691 | 0.926952 | 0.948598 | **t** | **t** | f | f | ✓ | ✓ |
| `demo_278@125` | DIRECTION_FP | MODE_02 | 0.024721 | 0.023128 | 0.955488 | 0.884155 | **t** | **t** | f | f | ✓ | ✓ |
| `demo_242@136` | DIRECTION_FP | MODE_03 | 0.037777 | 0.027287 | 0.825608 | 0.651030 | **t** | **t** | f | **t** | ✓ | ✓ |
| `demo_162@211` | DIRECTION_FP | UNASSIGNED | 0.104612 | 0.115593 | 0.812976 | 0.552866 | f | f | **t** | **t** | ✓ | ✓ |
| `demo_255@116` | DIRECTION_FP | UNASSIGNED | 0.032321 | 0.021755 | 0.851324 | 0.808610 | **t** | **t** | f | f | ✓ | ✓ |
| `demo_242@224` | VALID_DIRECTION | SEED | 0.051873 | 0.078953 | 0.831059 | 0.831059 | f | f | f | f | ✗ | ✗ |
| `demo_255@14` | VALID_DIRECTION | FRESH | 0.051498 | 0.163873 | 0.900965 | 0.911370 | f | f | f | f | ✗ | ✗ |
| `demo_260@75` | VALID_DIRECTION | FRESH | 0.058937 | 0.111128 | 0.844554 | 0.872850 | f | f | f | f | ✗ | ✗ |

```text
critical_event_coverage = 12 / 12 PRESENT
```

**低值 VALID 反例为什么仍然安全**

- `demo_255@14`：P8 恰好是 P8 的 floor（0.051498），但 P12 = 0.163873
  —— 在 Sustained 语境下是 cohort 内偏高值；C8/C12 均 ~0.90。
- `demo_242@224`：P8 = 0.051873（第二低），P12 = 0.078953；C8/C12 = 0.831059。
  **注意**：该事件是唯一被 edge clip 的事件（`window_right_frames = 8`），
  因此其 right 侧 W12 窗口退化到 8 帧，与 W8 right 窗口**完全相同**，
  `C12_right == C8_right == 0.831059`。该事件的 W8/W12 右侧对比**结构上不可用**。
- `demo_260@75`：P8 = 0.058937，P12 = 0.111128；C8 = 0.844554，C12 = 0.872850，均在包络内。

---

## 9. 特别解释：`demo_242@41` 与 `demo_242@60`

### 9.1 `demo_242@41` — W8 看起来仍充分，P12 显示明显衰减

**实际数字**

```text
W8 post 窗口 [0,+7] 逐帧 translation_speed_mps：
  rf=0 0.07430  rf=1 0.12717  rf=2 0.10692  rf=3 0.14603
  rf=4 0.11317  rf=5 0.11574  rf=6 0.09624  rf=7 0.07572
  -> mean = 0.106912   （= P8，高）

Sustained 窗口 [+4,+12] 逐帧 translation_speed_mps：
  rf=4 0.11317  rf=5 0.11574  rf=6 0.09624  rf=7 0.07572  rf=8 0.03606
  rf=9 0.03862  rf=10 0.01311  rf=11 0.02435  rf=12 0.03184
  -> median = 0.038618 （= P12，低）
```

**衰减起点**：`rf = 8`（0.03606）——**正好落在 W8 post 窗口 `[0,+7]` 之外**。
W8 窗口内包含 rf=1/3/4/5 这些最高的过渡帧（0.127 / 0.146 / 0.113 / 0.116），
这些帧属于切点后的立即过渡，而非“新的持续运动阶段”。

**P8 / P12 比值** = 0.106912 / 0.038618 = **2.77×**。

**统计量 / 窗口解耦（同一事件内可量化）**

| 组合 | 值 | 相对 P8 |
|---|---:|---:|
| `mean[0,+7]` = P8 | 0.106912 | — |
| `median[0,+7]` | 0.110046 | +0.003134（statistic，同窗口） |
| `mean[+4,+12]` | 0.060540 | −0.046372（**window/delay**） |
| `median[+4,+12]` = P12 | 0.038618 | −0.068294（合计） |

总降幅 0.068294 中：**窗口后移（延迟观察）贡献 0.046372 ≈ 67.9%**，
**mean→median 统计量贡献 0.021922 ≈ 32.1%**。

> 两个因素都真实存在，且**在本事件内**可量化分解；但这是单事件分解，
> 不构成 cohort 级的因果归因（见 §11）。

### 9.2 `demo_242@60` — W8 轨迹一致性仍在 VALID 范围，W12 暴露长期不一致

**实际数字**

```text
left  W8  [-8,-1] : path = 0.019474 m  net = 0.018023 m  -> straightness = 0.925446
left  W12 [-12,-1]: path = 0.027650 m  net = 0.020672 m  -> straightness = 0.747618
right W8  [0,+7]  : path = 0.022842 m  net = 0.020726 m  -> straightness = 0.907340
right W12 [0,+11] : path = 0.040505 m  net = 0.034944 m  -> straightness = 0.862719
```

**左侧（失败侧）分解**：

- 窗口从 `[-8,-1]` 扩到 `[-12,-1]`，额外 4 帧 `[-12,-9]`；
- path 增长 0.019474 → 0.027650 = **+42.0%**；
- net 只增长 0.018023 → 0.020672 = **+14.7%**；
- 即：额外 4 帧贡献了 0.008176 m 的**路径长度**，却只贡献 0.002649 m 的**净位移**。

结论：切点更早的 `[-12,-9]` 段存在**回摆 / detour**，其运动方向与 `[-8,-1]` 段的净方向不一致；
`[-8,-1]` 本身已经“拉直”，所以 W8 看不到。

**判定对比**

```text
C8  = min(0.925446, 0.907340) = 0.907340  vs  C8  floor 0.815722  -> 高 0.091618（未覆盖）
C12 = min(0.747618, 0.862719) = 0.747618  vs  C12 floor 0.769871  -> 低 0.022252（覆盖）
```

C8 = 0.907340 高于 C8 VALID 的 median（0.90289），也高于 17 个 VALID 中的 9 个，
而 C12 = 0.747618 落在 C12 floor 之下。**右侧 0.862719 保持连贯，问题只在左侧。**

### 9.3 同族补充（`demo_162@211`、`demo_242@136`）

| event | side | W8 path → W12 path | W8 net → W12 net | W8 str → W12 str |
|---|---|---|---|---|
| `demo_162@211` | left | 0.042049 → 0.067102（**+59.6%**） | 0.034185 → 0.037098（+8.5%） | 0.812976 → 0.552866 |
| `demo_242@136` | right | 0.015111 → 0.020321（**+34.5%**） | 0.012475 → 0.013229（+6.0%） | 0.825608 → 0.651030 |

同样是 **path 大幅膨胀、net 几乎不动** 的曲率特征。
注意 `demo_162@211` 在 C8 下仅以 0.002747 之差低于 C8 floor，
在 C12 下则以 0.217005 之差远低于 C12 floor —— W12 的表达裕度大得多。

---

## 10. Window Interpretation（W8 vs W12）

```text
W8  = 当前 Direction evidence 的既有窗口尺度（Formal，P1 冻结）
W12 = 当前 Rule Discovery analysis context（ANALYSIS_EXPORT_WINDOW，非 Detector 参数）
```

| 候选 | 帧长变化 | 是否延迟观察 | 统计量变化 | 轨迹上下文变化 |
|---|---|---|---|---|
| P8 → P12 | 8 帧 → 9 帧（几乎不变） | **是**（`[0,+7]` → `[+4,+12]`，跳过立即过渡） | **是**（mean → median） | 不适用 |
| C8 → C12 | 8 帧 → 12 帧（**变长**） | 左侧扩到更早（`-8` → `-12`），右侧扩到更晚（`+7` → `+11`） | 否（两者都是 net/path 比值） | **是** |

**回答 §14 的四选项**

1. **更长观察时间**：对 P12 **不成立**（8 帧 vs 9 帧，长度几乎相同）；
   对 C12 **成立**（8 帧 vs 12 帧）。
2. **延迟观察 post-motion**：对 P12 **成立且是主因**（`@41` 内贡献 67.9%）。
   对 C12 的右侧窗口**部分成立**（`+7` → `+11`），但对 `@60` 的实际失败侧（left）
   不是延迟而是**向前扩窗**（`-8` → `-12`）。
3. **median statistic**：只对 P12 成立（`@41` 内贡献 32.1%）；C12 不使用 median。
4. **trajectory longer-context**：对 C12 成立且是唯一机制。

```text
CAUSAL_FACTOR_NOT_IDENTIFIED
```

**理由**：单事件（`@41`）内可以量化 window vs statistic 的贡献比，
但 **cohort 级的 9/9 + 0/17 依赖的是 17 个 VALID 的 minimum 包络**，
而该包络由 `demo_260@66`（P12 floor）/ `demo_278@39`（C12 floor）等少数事件决定。
把“9/9 的收益”归因到某个单一因素，在当前 evidence 下**不可辨识**。
不把已知的机制解释伪装成已知的因果结论。

---

## 11. Signal Contract Impact

问题：未来若正式采用 **P12** 和/或 **C12**，是否必须修改 **P1 Signal Contract**？

```text
SIGNAL_CONTRACT_CHANGE_REQUIRED = NO
```

**理由**

| 候选 | 所需基础信号 | 是否已在 P1 Formal Signal Contract 内 |
|---|---|---|
| P8 | `translation_speed`（W=8 post 窗口） | 是（既有 `post_speed_mean` 已导出） |
| P12 | `translation_speed`（`[+4,+12]` median） | 是，仅换窗口与统计量 |
| C8 / C12 | EEF translation `robot0_eef_pos` 的逐帧 delta | 是（`step_dx/dy/dz`、`step_displacement_m` 已导出） |

四个候选**全部由已有 EEF translation / translation speed 派生**，
不引入新的 privileged signal，也不新增基础信号通道。

**应归入的层级**

```text
Base Signal｜基础信号            = EEF translation + Formal translation speed   -> 不变
P3 Candidate Acceptance Derived Context｜P3 候选接纳派生上下文
                                = event-relative 窗口偏移 + 派生统计量          -> 新增内容在此层
```

因此修改的是 **P3 Candidate Acceptance 的派生上下文定义**，
不是 P1 Base Signal Contract。

**必须同时记录的两个前提（否则该结论不成立）**

1. **有界前视（bounded lookahead）**：P12（`[+4,+12]`）与 C12（右侧到 `+11`）
   都需要在候选切点**之后**读取最多 12 帧（20 Hz 下 ≈ 0.6 s）。
   这要求 Candidate Acceptance 阶段能访问候选帧之后的有界帧窗口。
   这是**窗口 / 架构问题**，不是 Signal Contract 问题；
   但如果 Detector 需要严格因果在线输出，该前视会带来约 0.6 s 判定延迟。
   → 记为 Design Review 待决项，本轮不决策。
2. **episode 边缘裁剪**：`demo_242@224` 右侧仅 8 帧，W12 右窗退化。
   采用 C12 时必须显式定义边缘行为（当前 README 允许 clip，退化后
   `C12_right` 与 `C8_right` 相同）。

---

## 12. Seed / Fresh Generalization

| feature | SEED VALID med | SEED FP med | 方向 | FRESH VALID med | FRESH FP med | 方向 | 分布层一致性 |
|---|---:|---:|---|---:|---:|---|---|
| P8 | 0.08689 | 0.03778 | VALID > FP ✓ | 0.08993 | 0.06847 | VALID > FP ✓ | **一致** |
| P12 | 0.11516 | 0.03183 | VALID > FP ✓ | 0.11113 | 0.06867 | VALID > FP ✓ | **一致** |
| C8 | 0.90896 | 0.92373 | VALID < FP ✗ | 0.90289 | 0.83215 | VALID > FP ✓ | **冲突** |
| C12 | 0.83618 | 0.88416 | VALID < FP ✗ | 0.90110 | 0.68074 | VALID > FP ✓ | **冲突** |

**包络层（minimum）一致性** —— 各 package 内是否仍有 FP 低于本 package 的 VALID min：

| feature | SEED: VALID min / SEED FP below | FRESH: VALID min / FRESH FP below | 包络层一致性 |
|---|---|---|---|
| P8 | 0.051873 / 5 of 7 | 0.051498 / 1 of 2 | 一致 |
| P12 | 0.078953 / 7 of 7 | 0.053480 / 1 of 2 | 一致 |
| C8 | 0.815722 / 1 of 7 | 0.824994 / 1 of 2 | 一致 |
| C12 | 0.769871 / 2 of 7 | 0.776111 / 1 of 2 | 一致 |

**必须并列陈述的两种读法**

- **包络层（minimum）读法**：四个候选在 SEED / FRESH 内**都保持同方向**（每个 package 都有 FP 低于其 VALID min）。
- **分布层（median）读法**：P8 / P12 一致；**C8 / C12 在 SEED 出现方向反转**
  （SEED FP median 高于 SEED VALID median）。

反转的实质：SEED 有 7 个 FP，其 median straightness ≈ 0.92，
说明**多数 SEED FP 并不是轨迹不一致的**；轨迹维度只解释其中 1~2 个极端事件。
这再次印证 §5.5：trajectory 的分离是**包络型**而非**位移型**，因此更脆弱。

**Fresh 专项**

```text
FRESH Direction FP = 2  : demo_162@211, demo_255@116
FRESH 低速 VALID        : demo_255@14, demo_260@75
```

- `demo_162@211`：P8/P12 都不覆盖；**C8（0.812976）与 C12（0.552866）都覆盖**。
  这是唯一一个靠 trajectory 维度被 FRESH 覆盖的 FP，且 C8 侧余量仅 0.002747。
- `demo_255@116`：靠速度维度覆盖（P8 0.032321 / P12 0.021755），trajectory 不覆盖。
- `demo_255@14`：P8 恰为 P8 floor（0.051498），是 P8 包络最脆弱的支点；P12 下为 0.163873（安全）。
- `demo_260@75`：四个候选均安全。

```text
FRESH_NEGATIVE_EVIDENCE_LIMITED = YES
```

事实未变化：FRESH 只有 **2** 个 Direction FP，无法用 2 个负例支撑 W12 相对 W8 的增量结论。
W12 的全部增量（`@41`、`@60`）**都来自 SEED**，且同属 `demo_242`。

---

## 13. Recommendation（建议，不冻结）

```text
OPERATIONALIZATION_RECOMMENDATION = MIXED_NEEDS_DESIGN_REVIEW
```

**Post-motion 轴 → 明确倾向 W12 Sustained Context（P12）**

- 包络覆盖 7/9 > 6/9；
- VALID 侧余量 0.005569 vs P8 的 0.000375（约 14.9×）；
- IQR 完全不重叠（分布位移真实存在）；
- 机制清晰且落在冻结语义内：`@41` 的衰减起点在 W8 窗口之外；
- SEED / FRESH 方向一致。
- P8 的唯一优势是它是**既有 Formal 字段**、零新增定义成本；但其包络是刀锋。

**Trajectory 轴 → 真·混合，需要 Design Review**

| | C8 | C12 |
|---|---|---|
| FP 包络覆盖 | 2/9 | **3/9** |
| 最近被覆盖 FP 的余量 | **0.002747（刀锋）** | 0.022252 |
| VALID 侧余量 | **0.009272** | 0.000680（刀锋） |
| SEED / FRESH 分布方向 | 冲突 | 冲突 |
| 同 episode 近似并列 | 有（`demo_278@39` VALID vs `demo_278@83` FP） | 无 |
| 边缘裁剪事件对比可用性 | 可用 | `demo_242@224` 右侧不可用 |

- C8 更稳的 **VALID 侧**，但 FP 侧刀锋（0.002747）且存在同 episode 近似并列；
- C12 更好的 **FP 侧**（0.022252）且多覆盖 1 个 FP（`demo_242@136`），
  但 VALID 侧刀锋（0.000680）且 floor 完全由 SEED 决定。

**为什么不是 PREFER_W12_SUSTAINED_CONTEXT**

虽然 Pair12 = 9/9 + 0/17 优于 Pair8 = 7/9 + 0/17，但：

1. W12 的增量仅由 **1 个 episode（`demo_242`）的 2 个 SEED 事件**承载；
2. 两个 trajectory 候选都出现 **SEED / FRESH 分布方向反转**；
3. 两个 trajectory 候选都是 **单侧刀锋**（C8 在 FP 侧、C12 在 VALID 侧）；
4. FRESH 只有 2 个负例（`FRESH_NEGATIVE_EVIDENCE_LIMITED = YES`）；
5. `demo_242@224` 的 W8/W12 右侧对比**结构上不可用**。

**为什么不是 PREFER_W8_EXISTING_CONTEXT**

- W8 组合在冻结语义的**两个旗舰反例**上失效：
  `@41`（Post-motion Sufficiency）与 `@60`（Trajectory Coherence）；
- P8 的 VALID 包络余量仅 0.000375，比 P12 脆弱约 15 倍；
- `@60` 的 C8 = 0.907340 高于 17 个 VALID 中的 12 个，等于对长期轨迹不一致**完全无感**。

**为什么不是 INSUFFICIENT_OPERATIONALIZATION**

四个候选都有清晰 provenance、可复现、可解释，
且 P8 / P12 在 IQR 层面已实现完全不重叠的分布分离 —— 不构成“无法操作化”。

**若 Design Owner 必须二选一**：Post-motion 轴取 **P12**，
Trajectory 轴**暂不单独定论**（建议在 Calibration Protocol Patch 中把 trajectory
作为**辅助**条件而非独立门控，或先补充 FRESH 负例）。

---

## 14. Protocol Patch Gate

```text
CALIBRATION_PROTOCOL_PATCH = NOT_READY
```

判定依据（三个条件）：

| 条件 | 判定 | 说明 |
|---|---|---|
| rule shape 有清晰 operational definition | **PARTIAL** | Post-motion 轴清晰（P12）；Trajectory 轴两个候选各有单侧刀锋，未收敛 |
| Seed / Fresh 无方向冲突 | **FAIL** | C8 / C12 在 SEED 出现 median 方向反转（分布层读法） |
| 关键 VALID counterexample 可解释 | **PASS** | `demo_242@224`、`demo_255@14`、`demo_260@75` 全部可解释（§8） |

结论：**NOT_READY**。本轮**未创建** Protocol Patch，符合任务约束。

---

## 15. Validation

```text
event_rows                 = 26
VALID_DIRECTION            = 17
DIRECTION_FP               =  9
duplicate_event_key        =  0
inf_count                  =  0
nan_count                  =  0（无 NaN；degenerate-path 规则已实现但本包未触发）
P8  source consistency     = PASS (max abs delta = 5.551e-17)
P12 source consistency     = PASS (max abs delta = 0.000e+00)
C12 source consistency     = PASS (max abs delta = 3.331e-16)
C8  deterministic recompute= PASS (max abs delta = 0.000e+00)
critical_event_coverage    = 12 / 12
determinism (--check)      = PASS (byte-identical, LF preserved)
tests                      = 52 passed
```

---

## 16. Artifacts

| Artifact | Path |
|---|---|
| Result MD | `0-doc/80-audit-local/Project2_G1_P3_Motion_Sufficiency_Operationalization_Preparation_Result_20260921.md` |
| Event CSV (26 rows) | `0-doc/80-audit-local/g1_p3_rule_analysis/03_motion_sufficiency_operationalization_event.csv` |
| Summary CSV | `0-doc/80-audit-local/g1_p3_rule_analysis/04_motion_sufficiency_operationalization_summary.csv` |
| Script | `scripts/prepare_g1_motion_sufficiency_operationalization.py` |
| Test | `tests/test_g1_motion_sufficiency_operationalization.py` |

**Event CSV columns**：`episode_id, episode_key, event_frame, human_class, source_package, error_mode,
P8_post_speed_mean, P12_right_speed_reference, C8_left/right/min_straightness,
C8_left/right_path_length_m, C8_left/right_net_displacement_m,
C12_left/right/min_straightness, C12_recomputed_left/right_straightness,
P8/P12/C8/C12_below_valid_floor, Pair8_explained, Pair12_explained, *_window`

**Summary CSV**：`feature, cohort, n, min, q25, median, q75, max, range_overlap, iqr_overlap,
fp_below_valid_floor_count`（28 rows = 4 features × 7 cohorts）

**Reproduce**

```bash
python scripts/prepare_g1_motion_sufficiency_operationalization.py
python scripts/prepare_g1_motion_sufficiency_operationalization.py --check
python -m unittest tests.test_g1_motion_sufficiency_operationalization
```

---

## 17. Integrity

```text
CSV_LINE_ENDING = LF (\n) only, no CR
CSV_ENCODING    = UTF-8, no BOM
```

| File | CR | LF | BOM | Canonical LF SHA256 |
|---|---:|---:|---|---|
| `03_motion_sufficiency_operationalization_event.csv` | 0 | 27 | no | `be70380d1920f665efb4419ebf9c4e7311277e964e13407ef163509da65ddafe` |
| `04_motion_sufficiency_operationalization_summary.csv` | 0 | 29 | no | `19d4d95983ff3dec6abea3d33c72be2979e5a050f326b14090e6763683f0119e` |

脚本显式 `lineterminator="\n"`（自行渲染，不依赖 `csv.writer` 默认 CRLF），
不依赖 `core.autocrlf`。

**既有证据不可变性**（worktree blob oid == committed blob oid）

| File | worktree | HEAD blob | Result |
|---|---|---|---|
| `01_stage_a0_direction_event_analysis.csv` | `d807bc67…` | `d807bc67…` | **UNCHANGED** |
| `02_direction_event_window_trace.csv` | `0c023f9b…` | `0c023f9b…` | **UNCHANGED** |

```text
Frozen Motion Sufficiency Rule Shape = UNCHANGED
Rule Family A Review                 = UNCHANGED
Frozen Protocol                      = UNCHANGED
Detector code                        = UNCHANGED
config                               = UNCHANGED
```

（`git status --short` 仅显示 4 个新增文件，无任何修改文件。）

---

## 18. Non-Scope

```text
NO THRESHOLD SELECTED
NO PARAMETER SEARCH
NO GRID SEARCH / NO BEST F1
NO CLASSIFIER / NO DECISION TREE / NO AUTO FEATURE SELECTION
NO WINDOW SWEEP (仅比较 W8 vs W12)
NO EXTRA FEATURE FAMILY（未引入 acceleration / jerk / curvature / action / rotation / gripper / heading）
NO DETECTOR CHANGE
NO CONFIG GENERATED
NO PROTOCOL PATCH CREATED
NO STAGE A / STAGE B
NO MASTER / ROADMAP UPDATE
NO PRIVILEGED SIGNAL
NO WEB SQLITE READ
```

本轮所有 `VALID_FLOOR` 数值均为 **Calibration Envelope Diagnostic｜校准包络诊断**，
**不是 Detector threshold**，不得写入 Detector config。

```text
FINAL_STATUS = G1_P3_MOTION_SUFFICIENCY_OPERATIONALIZATION =
               PASS_READY_FOR_DESIGN_REVIEW
```

**Mandatory Stop** —— 本轮到此为止，不进入下一步。
