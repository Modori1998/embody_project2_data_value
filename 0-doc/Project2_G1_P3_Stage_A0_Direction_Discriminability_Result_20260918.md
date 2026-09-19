# Project 2 G1-P3 Stage A0 Direction Discriminability Result

```text
DATE = 2026-09-18
TASK = STAGE_A0_DIRECTION_CANDIDATE_DISCRIMINABILITY_AUDIT
CALIBRATION_PROTOCOL_EFFECTIVE_VERSION = FROZEN_v1.1
STAGE = A0_DIRECTION_CANDIDATE_DISCRIMINABILITY_AUDIT
PARAMETER_CHANGE_ALLOWED = NO
PARAMETER_SEARCH_ALLOWED = NO
PARAMETER_SEARCH_EXECUTED = NO
FORMAL_SIGNAL_ONLY = YES
PRIVILEGED_SIMULATOR_STATE_ALLOWED = NO
DETECTOR_MODIFIED = NO
CONFIG_GENERATED = NO
STAGE_A_EXECUTED = NO
```

Drive 权威稿已真实读取：

| 文档 | fileId | 状态 |
|---|---|---|
| `Project2_G1_P3_Calibration_Protocol_FROZEN_v1_20260917.md` | `160L0a9BDvOcankT1gZJQsxEErZ6YWWAb` | READ_OK |
| `Project2_G1_P3_Calibration_Protocol_FROZEN_v1_1_PATCH_20260918.md` | `1Irqgq6gsN4SegnAgZfDx_Apg32oUjv-b` | READ_OK |

v1.1 只覆盖 Package-B Export 身份。本轮 A0 的 matching / guardrail / search surface / stop rule 继承 v1.0 §10–16、§20。

```text
G1_STAGE_A0 = PASS_READY_FOR_OWNER_GATE
```

完成本轮后 **STOP**。不进入 Stage A，不生成任何 config，不 sweep threshold / persistence。

---

## 1. Authority

```text
STAGE = A0
PARAMETER_SEARCH_EXECUTED = NO
```

本轮只做 Formal Signal / Candidate / Final lineage 的只读可分性分析。未改 Detector，未写 Candidate CSV，未重跑 immutable run。

---

## 2. Cohorts

从正式 Baseline Scoring artifact 派生，未硬编码 count。

```text
TOTAL_VALID_DIRECTION = 17
  Seed = 6
  Fresh = 11

TOTAL_FP = 10
DIRECTION_FP = 9
NON_DIRECTION_FP = 1
```

分析单元 = 独立 DIRECTION_CHANGE Final（representative type = `DIRECTION_CHANGE`，且不是 Gripper-primary merged cluster）。

Direction FP breakdown（Fresh UNASSIGNED 保持 UNASSIGNED，未重分类）：

```text
MODE_01 = 3   demo_242 @41 / @60 / @78
MODE_02 = 3   demo_278 @83 / @105 / @125
MODE_03 = 1   demo_242 @136
UNASSIGNED = 2   demo_162 @211, demo_255 @116
```

非 Direction FP（不进入 Stage A0 negative cohort）：

```text
demo_255-B0007 @135  IDLE_TO_MOVE  UNASSIGNED  REDUNDANT_SHORT_PAUSE  FRESH
```

Guardrail 基线（只读取正式 scoring，本轮不修改）：

```text
CALIBRATION_GRIPPER_RECALL = 1.0
CALIBRATION_MERGED_CLUSTER_RECALL = 1.0
SEED_VALID_DIRECTION_RECALL = 1.0
FRESH_VALID_DIRECTION_RECALL_BASELINE = 1.0
FN_BASELINE = 0
```

---

## 3. Evidence Value

Frozen 描述用 threshold = `1.2` rad，**未搜索**。

```text
VALID n=17
  range  = [1.329, 2.532]
  median = 1.624
  IQR    = [1.459, 2.269]

FP n=9
  range  = [1.466, 2.643]
  median = 1.917
  IQR    = [1.499, 2.098]

range overlap = YES  width ≈ 1.066
IQR overlap   = YES  width ≈ 0.599
pairwise ordering P(VALID > FP) = 0.444
sort_direction = FP_HIGHER_MEDIAN
```

矛盾点（threshold-only 直接失败）：

- `demo_242@78` MODE_01 evidence = **2.643**，高于全部 17 个 VALID（VALID max = 2.532）。
- VALID min = 1.329，低于全部 Direction FP。
- Seed 上 VALID median (1.930) > Seed FP median (1.729)；Fresh 上 **反向**：Fresh FP median (2.137) > Fresh VALID median (1.624)。

```text
THRESHOLD_ONLY_RISK = HIGH
```

`heading_angle_rad` 与 `evidence_value` 在全部 26 个事件上 delta = 0。它是 evidence 的重复表达，不是独立证据。

---

## 4. Persistence / Run Length

Candidate CSV 没有物化 `run_length`。本轮按冻结 `T=1.2, P=3` 用 `persistent_high_runs` 无歧义重建，provenance = `ANALYSIS_DERIVED`。全部 26 条都匹配到唯一 peak_frame。`peak_width` 与 `run_length` 同源。

```text
VALID
  range  = [4, 13]
  median = 7
  IQR    = [5, 8]

FP
  range  = [4, 17]
  median = 8
  IQR    = [6, 10]

range overlap = YES  width = 9
IQR overlap   = YES  width = 2
P(VALID > FP) = 0.301
sort_direction = FP_HIGHER_MEDIAN
```

FP 的 run 往往 **更长**，不是更短的 jitter spike：

- Fresh UNASSIGNED `demo_162@211` run_length = 17（全表最长）
- MODE_01 `@60` = 13，`@41` = 8
- VALID 最短为 4：`demo_150@63`、`demo_230@108`

把 persistence 从 3 提到 5，会先碰到 2 个 VALID，而只碰到 1 个 FP（`demo_278@105` MODE_02 run_length=4）。

```text
PERSISTENCE_ONLY_RISK = HIGH
```

Joint（evidence × run_length，单调提高双下界，**不是 sweep**）：

```text
VALID min-box = evidence>=1.329 AND run_length>=4
FP outside that box = 0 / 9
FP inside that box  = 9 / 9
```

Stage A 的冻结 search surface 是 `direction_change_threshold × direction_persistence_frames`。在当前分布上，**单调抬高这两个下界无法在不伤 VALID 的前提下删掉任何一个 Direction FP**。这是 SEARCH_RATIONALE，不是 SEARCH_RESULT。

---

## 5. Motion Context

W=8 = 冻结 P1 `direction_window_frames`，不是 Detector 搜索轴。±3/±5/±8 仅 DIAGNOSTIC_ONLY，未选最优窗口。

### Speed

`local_speed_min` 是最强的单变量派生量之一：

```text
VALID local_speed_min
  median=0.0488  IQR=[0.0307, 0.0552]  range=[0.0131, 0.0990]
FP local_speed_min
  median=0.0196  IQR=[0.0162, 0.0244]  range=[0.0097, 0.0361]
IQR overlap = NO
range overlap = YES
Seed+Fresh 方向一致：VALID_HIGHER
P(VALID > FP) = 0.856
```

IQR 不重叠，但 **range 重叠且不能当硬门**：VALID `demo_255@14` local_speed_min=0.0131，低于多数 FP。若用 `local_speed_min >= 0.025` 一类规则，会杀掉至少 `demo_255@14`、`demo_242@224`、`demo_260@75` 三个 VALID。

`translation_speed_at_event` / `smoothed_speed_at_event`：VALID 中位数更高，Seed+Fresh 同向，但 IQR 仍重叠。

`idle_fraction_in_window`：绝大多数事件为 0。MODE_02 `@83` 才有 0.118。`motion_state_candidate` 只作 diagnostic，未升级为切分依据。demo_278 无 MOVE_TO_IDLE / IDLE_TO_MOVE candidate，与 Protocol §15 SEMANTIC MISMATCH 一致。

### Pre / Post displacement

```text
VALID min_displacement_m
  median=0.0313  IQR=[0.0263, 0.0425]  min=0.0172
FP min_displacement_m
  median=0.0125  IQR=[0.0105, 0.0180]  min=0.0068
IQR overlap = NO
range overlap = YES
```

MODE_02 三个事件 post_displacement 均 < 0.013 m（`@83` 仅 0.0068 m）。这支持 Protocol §12.4 已写过的 “更严 displacement gate” 作为 **Design 候选**，不是本轮实现。VALID `demo_242@224` min_displacement=0.0172，已经接近若干 FP，硬抬 displacement 会伤这条 Seed VALID。

---

## 6. Gripper / Support Context

```text
distance_to_nearest_gripper_final
  VALID median=49  IQR=[33, 55]  min=9
  FP    median=20  IQR=[10, 36]  min=9
  range overlap = YES
  Seed+Fresh 同向 VALID_HIGHER
```

MODE_03 `demo_242@136` 距下一 Gripper Final = **10 frames**（Gripper @146），与冻结事实一致。本轮只记录距离，不扩大 consolidation window。

`signed_distance_to_next_gripper` IQR 无重叠（VALID q25=52.5 vs FP q75=36），pairwise 0.926，但是 VALID `demo_255@14` / `demo_270@13` 距离也是 9–10，不能当全局 near-gripper 拒绝规则。

Supporting reasons（supporting only，不升级为 Formal Boundary）：

| 组合 | VALID 17 | Direction FP 9 |
|---|---:|---:|
| NONE | 8 | 3 |
| ACTION_SUPPORT only | 2 | 5 |
| ROTATION_SUPPORT only | 2 | 1 |
| BOTH | 5 | 0 |

Fresh VALID 大量 NONE（尤其 demo_260 四条全 NONE）。不能因为 Seed 上 ROTATION+ACTION 看起来更像 VALID 就升级 support。

---

## 7. Seed vs Fresh

```text
consistent_patterns =
  local_speed_min VALID_HIGHER
  min/pre/post displacement VALID_HIGHER
  translation/smoothed speed VALID_HIGHER
  distance_to_nearest_gripper VALID_HIGHER
  signed_distance_to_next_gripper VALID_HIGHER

seed_only_patterns / reversed =
  evidence_value：Seed VALID_HIGHER，Fresh FP_HIGHER
  run_length：Seed TIE，Fresh FP_HIGHER（Fresh FP 更长）
  local_area_above_threshold：Fresh FP 更大

fresh_specific_patterns =
  Fresh Direction FP 只有 2 条，且都是 UNASSIGNED
  两条都是高 evidence（1.986 / 2.287）+ 长 run（17 / 10）
  不能把 Seed MODE_01/02/03 机制外推成 Fresh 分类
```

Fresh Direction FP n=2，对任何 Stage A 搜索的 generalization 都不够。

---

## 8. MODE Analysis

机制不共享。

### MODE_01（demo_242 @41/60/78）= 高 evidence 连续转向，不像短 spike

- evidence 1.466 / 1.917 / **2.643**；run_length 8 / 13 / 7
- `@78` 是全表最高 evidence
- 距 gripper 18–37 frames，不是 MODE_03
- 两条 NONE support，一条 ACTION
- **threshold 与 persistence 都无法切**：抬 threshold 会先杀掉全部 VALID；它们的 run 不短

### MODE_02（demo_278 @83/105/125）= 低位移 / 低速谷，但 evidence 仍过 1.2

- post_displacement 0.0068 / 0.0120 / 0.0094 m
- local_speed_min 0.0097 / 0.0195 / 0.0103
- 该 episode 没有 MOVE_TO_IDLE / IDLE_TO_MOVE，pause_bridge 无法作用
- evidence 仍达 1.50–2.10，run 4–9
- 更像 displacement / speed-context 问题，不是 threshold 问题

### MODE_03（demo_242 @136）= 近 Gripper 的独立 Direction Final

- 距 gripper final = 10 frames
- evidence 1.468，run_length 6，中等
- 属于 consolidation 距离问题；冻结 Stage B 窗口候选 `{8,10,12}`，**不是 Stage A surface**

### UNASSIGNED Fresh（demo_162 @211, demo_255 @116）

- 保持 UNASSIGNED
- 高 evidence（1.99 / 2.29）+ 长 run（17 / 10）
- `@116` 距 gripper=9，兼有 near-gripper 色彩；`@211` 距 gripper=20，更像长持续性 heading 变化
- n=2，禁止据此发明新 mode

---

## 9. Main Findings

按证据强度排序：

1. **9/9 Direction FP 都落在 VALID 的 (evidence, run_length) 最小下界盒内。** 单调抬高 Stage A 两个参数，删不掉任何一个 Direction FP，除非牺牲 VALID。
2. **MODE_01 @78 evidence=2.643 > VALID max=2.532。** threshold-only 在这条上逻辑关闭。
3. **FP 的 run_length 中位数（8）高于 VALID（7）。** persistence-only 方向与“短 jitter”叙事相反。
4. **evidence 的 Seed/Fresh 方向相反。** 不能把 Seed 上“VALID evidence 更高”当成可推广规律。
5. **`local_speed_min` 与 `min_displacement_m` 的 IQR 在 VALID vs FP 之间不重叠**，Seed+Fresh 同向。但这是派生信号，且 VALID 里已有低速/低位移反例（`demo_255@14`、`demo_242@224`）。可写 DESIGN_CHANGE_CANDIDATE，不能直接当 Stage A 参数。
6. **`heading_angle_rad` ≡ `evidence_value`。** 禁止把它当成第二条独立证据。
7. **MODE_03 距离 gripper = 10 frames**，只支持以后 Stage B 有限 consolidation 讨论，本轮不试 window。
8. **10 个 FP 里有 1 个非 Direction（IDLE_TO_MOVE @135）。** 不进入 Direction negative cohort，不进入 Stage A search surface。
9. **Rotation/Action 仍是 supporting only。** Fresh VALID 大量 NONE。
10. Fresh Direction FP 只有 2 条 UNASSIGNED，任何“Fresh 已验证”的分割声明都证据不足。

---

## 10. A0 Evidence Classification

```text
MIXED_INSUFFICIENT
```

原因：

- A 不成立：evidence / run_length 没有可解释的 Stage A 搜索依据；joint min-box 外 FP = 0。
- B 部分成立但不干净：speed / displacement 的 IQR 可分，可解释，且 Seed+Fresh 同向；但 range 重叠、VALID 反例存在、且不能覆盖 MODE_01 高 evidence。
- C 不成立：不是“所有 Formal Signal 都不可分”，MODE_02 的低位移/低速谷是清楚的。
- D 成立：部分 mode（MODE_02 displacement/speed，MODE_03 gripper 距离）可描述；MODE_01 在当前 Formal Signal 上与 VALID 同云；Fresh n=2 UNASSIGNED 不足以谈 generalization。

因此必须 **Owner Review**，而不是自动打开 Stage A。

---

## 11. Search Implication

```text
STAGE_A_THRESHOLD_PERSISTENCE_SEARCH = OWNER_REVIEW_REQUIRED

DESIGN_CHANGE_CANDIDATE =
  1. 更严的 pre/post window displacement gate
     （Protocol §12.4 已列为 limited strategy candidate；
       本轮不实现、不改 P1 signal contract）
  2. Candidate Acceptance Rule：独立 Direction 需要
     非谷值速度 / 非近零位移 的局部运动上下文
     （VALID 已有反例，必须 Owner 决定是否值得做 Design Review）
  3. MODE_03 的 gripper proximity 留给 Stage B consolidation {8,10,12}
     本轮不试 window
```

本轮 **没有** 把上述任何一项实现进 Detector 或 Acceptance Rule。

若 Owner 仍要求进入 Stage A：A0 证据显示 threshold × persistence 的单调搜索 **没有** 能同时保住 17 条 VALID Direction 并删掉 MODE_01 的合理区间。那将是带已知失败模式的搜索，而不是 A0-supported search。

---

## 12. Artifacts

```text
analysis_id  = g1_stage_a0_20260918_162418_7cbf826e
analysis_root =
  outputs/g1_p3_stage_a0/g1_stage_a0_20260918_162418_7cbf826e/
```

包含：

- `stage_a0_meta.json`
- `stage_a0_direction_event_analysis.csv`（26 行，每行一个独立 Direction Final）
- `stage_a0_feature_summary.csv`
- `stage_a0_mode_summary.csv`
- `stage_a0_non_direction_fp.csv`
- `stage_a0_pairwise.json`（无 classifier）
- `stage_a0_decision.json`
- `stage_a0_findings.md`
- `plots/01`–`07`（点标注 episode_id@frame，FP 额外标注 MODE）

versioned / immutable / atomic write（先写 `.tmp-*` 再 rename）。

---

## 13. Validation

```text
tests = 22 PASS  (tests/test_g1_stage_a0.py)
immutability =
  BASELINE_RUN_UNCHANGED = PASS
  BASELINE_SCORE_UNCHANGED = PASS
  CANONICAL_GT_UNCHANGED = PASS
  SEED_EXPORT_UNCHANGED = PASS
  FRESH_EXPORT_UNCHANGED = PASS
  OWNER_SQLITE_UNCHANGED = PASS
  FROZEN_PROTOCOL_UNCHANGED = PASS
  DATASET_UNCHANGED = PASS
privileged_signal_used = NO
```

测试覆盖：VALID cohort、Direction FP cohort、非 Direction 排除、Seed/Fresh provenance、Candidate↔Final lineage、run_length 派生、window clip、gripper 距离、support 解析、无 privileged 字段、确定性排序、源不可变、无 config / 无搜参、plots 物化。

---

## 14. Explicit Non-Scope

```text
DETECTOR_MODIFIED = NO
CONFIG_GENERATED = NO
PARAMETER_SEARCH_EXECUTED = NO
STAGE_A_EXECUTED = NO
THRESHOLD_SWEEP = NO
PERSISTENCE_SWEEP = NO
CONSOLIDATION_WINDOW_TRIED = NO
CLASSIFIER_TRAINED = NO
```

---

## 15. Final Status

```text
G1_STAGE_A0 = PASS_READY_FOR_OWNER_GATE
```

等待 Design Owner 审核 A0 证据后，再决定：

1. 返回 Design Review（新 Acceptance Rule / displacement gate / semantic mismatch），或
2. 明知 MODE_01 不可分仍做有限 Stage A（A0 **不支持** 这是有合理搜索区间的），或
3. 跳过 Stage A，仅把 MODE_03 留给 Stage B 讨论。

**STOP。**
