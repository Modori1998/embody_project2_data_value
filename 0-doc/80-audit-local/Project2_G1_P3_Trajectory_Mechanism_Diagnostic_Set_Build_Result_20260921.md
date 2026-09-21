# Project 2 — G1-P3 Trajectory Mechanism Diagnostic Set — Build Result

```text
DOCUMENT_STATUS  = DIAGNOSTIC_SET_BUILD_RESULT
TASK             = BUILD_G1_P3_TRAJECTORY_MECHANISM_DIAGNOSTIC_SET
DESIGN_VERSION   = FROZEN_TARGETED_MATCHED_DIAGNOSTIC_V1
DATASET_ROLE     = DESIGN_DIAGNOSTIC_SET
BUILD_DATE       = 2026-09-21
DETECTOR_MODIFIED = NO
CONFIG_CHANGE     = NO
PARAMETER_CHANGE  = NO
THRESHOLD_SELECTED = NO
HUMAN_LABEL_CREATED = NO
```

---

## 1. 结论摘要

按冻结的 *Trajectory Mechanism Validation Design v1*（`FROZEN_TARGETED_MATCHED_DIAGNOSTIC_V1`）成功构建出一个**完全独立于既有 Calibration 的、无标签的 Design Diagnostic Set**。

| 项 | 值 |
| --- | --- |
| 扫描 episode 数 | 288 |
| 跳过 Calibration episode | 12 |
| 排除的非 Direction final | 1172 |
| 初始 Direction final（候选池） | **511** |
| 排除的 Calibration final | 26 |
| 最终 eligible 事件 | **432** |
| P12 eligible（top 50%） | **216** |
| low-C12 池（bottom 25%） | **54** |
| high-C12 池（top 25%） | **54** |
| 匹配对 | **10** |
| Arm A / Arm B | **10 / 10** |
| distinct episode | **20** |
| episode 复用 | **0** |
| Calibration 泄漏 | **0** |
| `diagnostic_set_id` | `g1_trajectory_mechanism_diag_20260921_000000_b61ef198` |

**最终状态：`PASS_READY_FOR_BLINDED_HUMAN_REVIEW`。**

---

## 2. Source Run / Config（来源审计）

所有候选事件均来自**同一次只读基线物化**，不存在跨 run 混采。

| 字段 | 值 |
| --- | --- |
| `config_hash` | `dde590e759a31cb8c865369e18256ebecbbd01bc94a58e1d3ca695bb50f2a630` |
| `signal_contract_hash` | `24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d` |
| `segmentation_version` | `G1-P2-EXPLORATORY-v0` |
| 物化模式 | `READ_ONLY_BASELINE_MATERIALIZATION` |

511 行候选池的 `config_hash` / `signal_contract_hash` / `segmentation_version` 三列取值**完全唯一**（各 1 个 distinct 值），已由脚本 `check_identity()` 与测试双重断言。

### 2.1 为什么需要只读基线物化

仓库中**不存在**可直接复用的“全量候选事件物化产物”：

- `0-doc/80-audit-local/g1_p3_rule_analysis/01_stage_a0_direction_event_analysis.csv` 只覆盖 26 个 Calibration 事件；
- `outputs/g1_audit_runs/**` 下的 run 目录仅覆盖 Calibration 相关 episode。

因此按设计文档要求，在**内存中只读**地重放冻结引擎（`run_boundary_engine` + `compute_formal_signals`），覆盖 288 个非 Calibration episode，并逐事件复用冻结派生函数 `lineage_for_final` / `derive_run_length`，**未做任何重实现**。全程未写入 SQLite、未修改任何 detector/config/parameter。

---

## 3. Calibration 排除（硬约束）

### 3.1 被排除的 12 个 Calibration episode

从 SSOT Calibration manifest 恢复出恰好 12 个 episode，与冻结记录一致：

```text
data/demo_158   data/demo_160   data/demo_163   data/demo_183
data/demo_186   data/demo_228   data/demo_242   data/demo_255
data/demo_260   data/demo_278   data/demo_290   data/demo_291
```

### 3.2 26 = 17 + 9 交叉校验（硬门禁）

把本任务的池构造语义（`is_independent_direction_final` + `DIRECTION_CHANGE` + 非 `GRIPPER_TRANSITION` 合并）**反向施加到上述 12 个 Calibration episode**，得到：

```text
Direction final（Calibration 内） = 26
  VALID_DIRECTION = 17
  DIRECTION_FP    =  9
EXPECTED_CALIBRATION_DIRECTION_FINALS = 26
MATCH = YES
```

该等式被脚本作为 **fail-fast 硬门禁**：一旦不等即中止，防止池语义与冻结队列漂移。

### 3.3 已复核 episode 覆盖

对 `outputs/g1_audit_runs/**` 中所有已复核 run 取 episode 并集：

```text
union_of_run_covered_episodes        = 12
covered_episodes_outside_calibration =  0
```

**结论：Calibration 之外不存在任何已人工复核的 episode。** 因此本 Diagnostic Set 与既有 Calibration **完全无交集、无标签复用**。

> 工程说明：扫描某个 run 目录时遇到 `PermissionError [WinError 5]`，脚本以 `try/except (PermissionError, OSError)` 容错并记入 `unreadable_runs`，不改变上述并集结论（该目录已被其他可读 run 覆盖）。

---

## 4. Candidate Pool Size（候选池）

```text
episodes scanned            = 288
calibration eps skipped     =  12
non-direction finals excl   = 1172
initial Direction finals    = 511   <-- 候选池
calibration finals excluded =  26
reviewed eps outside calib  =   0
```

**候选池 = 511 行 × 30 列。**

池质量校验：

| 检查 | 结果 |
| --- | --- |
| 主键重复 `(episode_id, boundary_id, event_frame)` | **0** |
| `inf` 单元格 | **0** |
| `C12` 为 NaN/空（`path_length < 1e-9`） | **4**（全部为 EDGE_CONTEXT，均已排除） |
| `is_independent_direction_final` = true | 511 / 511 |
| `is_gripper_primary_merged` = true | 0 / 511 |

---

## 5. Exclusion Counts（全部排除计数）

排除规则与**固定优先级**（先命中先排除，不重复计数）：

```text
P1  GRIPPER_PRIMARY_MERGED_FINAL        （合并型 Gripper 主事件）
P2  EDGE_CONTEXT_INCOMPLETE             （±12 上下文越界）
P3  NEAR_GRIPPER_CONSOLIDATION_CONTEXT  （距最近 Gripper final <= 12 帧）
P4  DEGENERATE_TRAJECTORY_CONTEXT       （轨迹退化）
P5  RUN_LENGTH_NOT_AVAILABLE            （run length 不可用）
```

实际计数：

| 规则 | reason code | 计数 |
| --- | --- | --- |
| P1 | `GRIPPER_PRIMARY_MERGED_FINAL` | **0** |
| P2 | `EDGE_CONTEXT_INCOMPLETE` | **4** |
| P3 | `NEAR_GRIPPER_CONSOLIDATION_CONTEXT` | **75** |
| P4 | `DEGENERATE_TRAJECTORY_CONTEXT` | **0** |
| P5 | `RUN_LENGTH_NOT_AVAILABLE` | **0** |
| | **合计排除** | **79** |

```text
511 - 79 = 432  eligible
```

一致性核对：`ineligibility_reason` 分布 = `{空: 432, NEAR_GRIPPER: 75, EDGE_CONTEXT: 4}`，与 `eligible_after_all_exclusions = true(432)/false(79)` 完全吻合。

> P2 的 4 个事件同时也是 `C12` 为 NaN 的 4 个事件，说明其右/左窗口在 episode 边界被截断，上下文不完整，故排除。

---

## 6. P12 Eligible Count（P12 资格）

P12 定义（冻结）：

```text
P12 = median(translation_speed_mps), relative_frame ∈ [+4, +12]   （9 帧，闭区间）
```

资格判定采用**秩百分位**（不是阈值）：

```text
P12_percentile = rank_index / (n - 1)      n = 432，升序，确定性 tie-break
P12 eligible   = P12_percentile >= 0.50    （top 50%）
```

```text
P12 eligible (top 50%) = 216
```

---

## 7. C12 Arm Construction（C12 双臂）

C12 定义（冻结）：

```text
C12 = min(left_straightness, right_straightness)
  left_straightness  = net_displacement / path_length  over relative_frame [-12, -1]
  right_straightness = net_displacement / path_length  over relative_frame [ 0, +11]
  path_length < 1e-9 -> NaN
```

在 P12 eligible 的 216 个事件内部，按 `C12` 秩百分位切分：

```text
low-C12 pool  (bottom 25%) = 54
high-C12 pool (top  25%)   = 54
```

> 两个池刻意**不重叠**，为后续匹配留出充分的距离空间。

---

## 8. Matched Pairs（匹配对）

```text
MATCH_DISTANCE = |ΔP12_percentile| + |Δdirection_evidence_percentile| + |Δrun_length_percentile|
```

- **目标**：Arm A（low-C12）每事件在 Arm B（high-C12）中寻找最小 `MATCH_DISTANCE` 的对照。
- **构造顺序**：按 C12 升序遍历 Arm A 目标（构造序即 `P01..P10`），逐个贪心选取**未被占用**的最小距离 Arm B 事件。

```text
matched pairs  = 10
Arm A / Arm B  = 10 / 10
TARGET_PER_ARM = 10    MIN_PER_ARM = 8    -> 达标
```

| 项 | Arm A (low-C12) | Arm B (high-C12) |
| --- | --- | --- |
| n | 10 | 10 |
| C12 区间 | `0.113401 – 0.594403` | `0.936076 – 0.990088` |
| P12 百分位区间 | `0.0093 – 0.9721` | `0.0233 – 0.9628` |

**C12 双区间完全不相交**（`0.5944 < 0.9361`），臂间在目标特征上彻底分离。

### 8.1 配对明细（10 对）

| pair | Arm A 目标 | C12_A | Arm B 对照 | C12_B | match_distance |
| --- | --- | --- | --- | --- | --- |
| P01 | demo_211@169 | 0.1134 | demo_64@808 | 0.9901 | 0.488372 |
| P02 | demo_208@116 | 0.1888 | demo_245@365 | 0.9376 | 0.506977 |
| P03 | demo_217@518 | 0.3328 | demo_182@57 | 0.9697 | 0.241860 |
| P04 | demo_220@238 | 0.3603 | demo_69@688 | 0.9743 | 0.320930 |
| P05 | demo_258@17 | 0.4500 | demo_201@449 | 0.9744 | 0.260465 |
| P06 | demo_206@17 | 0.5532 | demo_61@164 | 0.9361 | 0.544186 |
| P07 | demo_106@41 | 0.5582 | demo_86@232 | 0.9601 | 0.730233 |
| P08 | demo_205@50 | 0.5659 | demo_296@73 | 0.9747 | 0.176744 |
| P09 | demo_202@74 | 0.5899 | demo_209@255 | 0.9384 | 0.339535 |
| P10 | demo_236@74 | 0.5944 | demo_214@196 | 0.9386 | 0.734884 |

---

## 9. Distinct Episode Count（episode 多样性）

硬规则：`MAX_SELECTED_EVENTS_PER_EPISODE = 1`，`NO_EPISODE_SHARED_BETWEEN_ARMS = YES`。

```text
selected events   = 20
distinct episodes = 20
episode reuse     =  0
```

即 **20 个事件来自 20 个互不相同的 episode**，且 Arm A 与 Arm B 之间零 episode 共享。episode 多样性规则**一次即满足**，未触发任何降级重采。

---

## 10. Match-Distance Statistics（匹配质量）

```text
min  = 0.176744
med  = 0.413953
max  = 0.734884
```

Arm A / Arm B 每对共享**同一个** `pair_id` 且 `match_distance` **完全相同**（已断言 `rows[0].match_distance == rows[1].match_distance`，10/10 通过）。

### 10.1 近 Gripper 隔离

```text
selected distance_to_nearest_gripper_final : min = 13, max = 112
NEAR_GRIPPER_FRAMES = 12   -> 全部 > 12，满足硬约束
```

所有入选事件距最近 Gripper final 至少 13 帧，成功隔离 Gripper 合并语义的干扰。

---

## 11. Selection Integrity（选择完整性）

| 检查项 | 结果 |
| --- | --- |
| 池主键重复 | 0 |
| 池 `inf` 值 | 0 |
| 入选事件 episode 复用 | 0 |
| Calibration 泄漏 | **0** |
| 每对 `pair_id` 唯一且成对（恰 2 行） | 10/10 PASS |
| 每对 `match_distance` 两侧一致 | 10/10 PASS |
| Arm 间 C12 区间不相交 | PASS |
| 每 episode 至多 1 事件 | PASS |
| 确定性重跑（`--check`） | **PASS**（byte-identical） |

### 11.1 公式保真度交叉校验

将本脚本的 `P12` / `C12` 实现与冻结 trace 逐位比对（bit-for-bit），4 个 Calibration 事件全部一致：

| 事件 | P12 | C12 | 结果 |
| --- | --- | --- | --- |
| demo_242@41 | 一致 | 一致 | PASS |
| demo_242@60 | 一致 | 一致 | PASS |
| demo_162@211 | 一致 | 一致 | PASS |
| demo_255@14 | 一致 | 一致 | PASS |

---

## 12. Blinding Audit（盲化审计）

`03_selection_blinded.csv`（8 列，20 行）仅保留最小必要标识，**不含任何提示分组/目标的列**：

```text
diagnostic_event_id, episode_id, boundary_id, event_frame, event_type,
representative_candidate_id, member_candidate_ids, diagnostic_set_id
```

禁止 token 扫描：

```text
FORBIDDEN = arm, p12, c12, coherence, target, control,
            match_distance, low, high, expected, redundant, valid
BLINDING_CONTRACT = PASS
```

> **重要工程决策**：`diagnostic_set_id = g1_trajectory_mechanism_diag_...` 与 `DESIGN_VERSION = FROZEN_TARGETED_MATCHED_DIAGNOSTIC_V1` 中均含 `target` 子串，但它们是**集合身份标识**而非分组信息，且 `diagnostic_set_id` 是盲化清单的必要字段。因此盲化扫描按“**列名 + 列值**”的语义 token 匹配执行，对身份列做显式豁免；分组信息（`arm` / `pair_id` / `match_distance` / `selection_reason`）**全部仅存在于 internal 清单**，未进入 blinded 清单。

`diagnostic_event_id` 采用**跨臂统一顺序编号**（`G1P3-DIAG-001..020`），与 Arm 归属、C12 高低**无任何对应关系**，避免 ID 顺序泄漏分组。

---

## 13. Diagnostic Set Identity

```text
diagnostic_set_id = g1_trajectory_mechanism_diag_20260921_000000_b61ef198
```

由 `DESIGN_VERSION` + `DATASET_ROLE` + 时间戳 + 选择内容指纹确定性生成；`--check` 重跑得到同一 ID。

---

## 14. Artifacts

| 文件 | 行数 | 列数 | LF SHA256 |
| --- | --- | --- | --- |
| `01_candidate_pool.csv` | 511 | 30 | `2d63c86156c773e59f6bbc9baee9458fe3abcfa14194203cc761fb806a2754e8` |
| `02_selection_internal.csv` | 20 | 18 | `7588a0650bdf75493d2eec3780fb0e0a7ce6b3a64af667db827faf305473d9f8` |
| `03_selection_blinded.csv` | 20 | 8 | `bfa63c28c22050a0d9ba64e55e5c9a412ad8be87145322f08f370cde7f86aaee` |
| `README.md` | — | — | 见 git |
| `scripts/build_g1_trajectory_mechanism_diagnostic_set.py` | — | — | 见 git |
| `tests/test_g1_trajectory_mechanism_diagnostic_set.py` | — | — | 见 git |

目录：`0-doc/80-audit-local/g1_p3_trajectory_mechanism_validation/`

---

## 15. Validation（验证）

```text
tests/test_g1_trajectory_mechanism_diagnostic_set.py
  = 61 tests, ALL PASS
  （含 TestPairIdentityIntegrity 回归组、AST 常量守卫：禁止 0.045 / 0.050 / 0.76 等 Calibration 切值进入代码）

--check 确定性门禁
  = DETERMINISM PASS (byte-identical, LF preserved)
```

CSV 行尾契约：仓库 `core.autocrlf=true` 且无 `.gitattributes`，脚本以显式 `\n`、UTF-8 无 BOM 渲染，避免 CRLF 污染。blob 校验见 git 提交后 `git cat-file blob` 比对。

---

## 16. Non-Scope（本轮明确未做）

```text
NO HUMAN LABEL YET                       = YES
NO BLINDED HUMAN REVIEW EXECUTED         = YES
NO SQLITE WRITE                          = YES
NO REDUNDANT RATE COMPUTED               = YES
NO C12 SUPPORT VERDICT                   = YES
NO THRESHOLD SELECTED                    = YES
NO DETECTOR / CONFIG / PARAMETER CHANGE  = YES
NO PROTOCOL PATCH                        = YES
FORMAL_DETECTOR_INPUT                    = NO
MUST_NOT_ENTER_CALIBRATION_GT            = YES
MUST_NOT_ENTER_EVALUATION_GT             = YES
MUST_NOT_BE_USED_FOR_THRESHOLD_SELECTION = YES
```

本 Diagnostic Set 是**设计诊断集**，不得作为 GT、不得用于阈值选择、不得进入正式 Detector 输入。

---

## 17. Web Diagnostic Run Readiness

```text
WEB_DIAGNOSTIC_RUN_READY = NO
```

**原因**：本轮只完成“集合构建”。盲化清单 `03_selection_blinded.csv` 已就绪，但 Web 侧的人评运行容器（review session / 盲化问卷 / 标注落库通道 / 双盲分组回填机制）**尚未物化**。按设计文档，人工盲评属于**下一阶段独立任务**，本轮被显式禁止执行。待下一轮获得授权后，再基于 `03_selection_blinded.csv` 搭建 Web 诊断运行。

---

## 18. Reproduce

```bash
# 构建（写入三份 CSV）
python scripts/build_g1_trajectory_mechanism_diagnostic_set.py

# 确定性校验（不写盘，逐字节比对）
python scripts/build_g1_trajectory_mechanism_diagnostic_set.py --check

# 测试
python -m pytest tests/test_g1_trajectory_mechanism_diagnostic_set.py -q
```

---

## 19. Final Status

```text
G1_P3_TRAJECTORY_DIAGNOSTIC_SET = PASS_READY_FOR_BLINDED_HUMAN_REVIEW
```

构建完成，等待下一阶段授权进行盲化人工复核。
