# Project 2 G1 Human Review Error Attribution Audit

```text
DATE = 2026-09-17
TASK = READ-ONLY AUDIT + ERROR ATTRIBUTION
CONTRACT = P2_G1_AUDIT_FOLDER_V1
G1_WEB_DESIGN = FROZEN v1.0
RUN_ID = g1_exploratory_audit_20260917_141541_fe251439
PARENT_RUN_ID = g1_exploratory_audit_20260916_214523_1ba11d9d
DETECTOR_MODIFIED = NO
THRESHOLD_MODIFIED = NO
HUMAN_REVIEW_SQLITE_WRITTEN = NO
CALIBRATION_RUN_GENERATED = NO
EVALUATION_RUN_GENERATED = NO
G1_P3_IMPLEMENTED = NO
```

最终状态：

```text
G1_HUMAN_REVIEW_ERROR_ATTRIBUTION =
PASS_READY_FOR_CALIBRATION_DESIGN
```

本轮不修改 Detector，不选最优参数，不把本 6 条升级为 Calibration / Evaluation GT。

---

# 1. Authority / Run Identity

## 1.1 Google Drive

| 文档 | Drive fileId | 读取结论 |
| --- | --- | --- |
| `Project2_G1_Human_Audit_Web_Design_FROZEN_v1_20260916.md` | `1v6ZtopYFfCIWG9kjCOmwJe2C-XWB4xRR` | **FROZEN v1.0** |
| `Project_2_Engineering_Design_Master_v1_20260914.md` | `1Cd05zSFR6IF8rXby6RYmocZbmrUDH05b` | G1-A/B/C/D 冻结；Calibration/Evaluation 隔离 |
| `Project2_Development_Roadmap_and_Design_Gate_Plan_v1_20260914.md` | `1lQd5Nn4jxwiqwylEg40tCAl1jwDg5O6t` | G1-P3 = Human Calibration Loop；frame tolerance = `DATA_CALIBRATION_PENDING` |
| `02_robot_demonstration_mining_autolabel_design.md` | `1tgMOxq2_0taUT7LdHDsn4nvEqookCdAI` | 数值阈值 `DATA_CALIBRATION_PENDING` |

冻结事实：

```text
G1 Web Design = FROZEN v1.0
Contract = P2_G1_AUDIT_FOLDER_V1
Human Review SSOT = Web-owned SQLite
P2 Review Unit = Final Boundary
Audit Run = READ ONLY
Web 禁止按 mtime / 目录扫描猜 Run
Calibration 与 Evaluation 必须严格隔离
P3 消费 Export，不直接读 SQLite
```

P1 复用条件（Frozen）：`same episode_id + same signal_contract_version + same signal_contract_hash` → `REUSED_SIGNAL_REVIEW` 合法。

Boundary matching 的正式 `tolerance_frames`：**未冻结**。Master / Roadmap 均为 `DATA_CALIBRATION_PENDING`。当前 config 有 exploratory `boundary_tolerance_window=5`，注释写明 *Schema reserved for G1-P3 Human Boundary matching. Not used by the G1-P2 segmenter.* 因此本轮 **不得** 把它当正式 metric tolerance。漏检检索口径：

```text
EXACT + NEARBY DIAGNOSTIC SEARCH
DIAGNOSTIC_WINDOW_ONLY
FORMAL_TOLERANCE_FRAMES = NOT_FROZEN
```

## 1.2 本地事实报告

- `0-doc/80-audit-local/Project2_G1_Final_Boundary_Merged_Semantics_Audit_20260917.md`：进入物化前 `PRESERVED_BY_LINEAGE_ONLY`
- `0-doc/90-implementation-local/Project2_G1_Final_Boundary_Semantic_Materialization_Result_20260917.md`：child run `MATERIALIZED_V1`，`PASS_READY_FOR_USER_TRIAL`
- `0-doc/90-implementation-local/Project2_G1_Audit_Web_Implementation_Batch2_Result_20260916.md`：P1/P2 Web + SQLite SSOT；REDUNDANT 必须有 reason；MISALIGNED 必须有 `corrected_frame`；`OTHER` 必须有 comment

当前 Final 语义：

```text
Final Boundary
= Representative Boundary（切分点）
+ Materialized Merged Evidence（成员类型/帧）
```

网页：Primary｜代表事件 + Merged Evidence｜合并证据。

## 1.3 目标 Run（Registry + Validator，未用 mtime）

通过 `g1_audit_run_registry.json` → `G1AuditWebInput.load_validated_run` 读取。

```text
run_id = g1_exploratory_audit_20260917_141541_fe251439
parent_run_id = g1_exploratory_audit_20260916_214523_1ba11d9d
run_stage = EXPLORATORY_AUDIT
set_role = EXPLORATORY
final_boundary_semantics = MATERIALIZED_V1
contract_version = P2_G1_AUDIT_FOLDER_V1
config_hash = dde590e759a31cb8c865369e18256ebecbbd01bc94a58e1d3ca695bb50f2a630
signal_contract_hash = 24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d
episode_count = 6
g1_p2_status = EXPLORATORY_ONLY
```

SQLite：`outputs/g1_audit_web/g1_audit_web_owner.sqlite3`，只读 URI `mode=ro`。Reviewer = `DESIGN_OWNER`。当前状态 = `MAX(review_id)` per Frozen key。

---

# 2. Human Review Integrity

```text
EPISODE_COUNT = 6
HUMAN_REVIEW_INTEGRITY = PASS
REVIEW_CHANGED_COUNT
  signal   = 0
  boundary = 0
  added    = 0
episode_note_history rows = 0
```

当前有效审核没有「先标 A 再改成 B」的翻盘。demo_0 的 P1 曾分两次保存（先 5 项、后补 TRANSLATION），但同一 signal 的 label 没有互相覆盖成不同决策。

Schema QA：

- 7 条 REDUNDANT 均有合法 reason（无 `OTHER`，comment 可空）
- MISALIGNED = 0
- HUMAN_ADDED = 0
- 无 `NOT_REVIEWED` Final

---

# 3. P1 Signal Gate

`P1_TOTAL_ITEMS = 36`

| Episode | TRANSLATION | DIRECTION | GRIPPER | ROTATION | ACTION | ALIGNMENT | 来源 |
| ------- | ----------- | --------- | ------- | -------- | ------ | --------- | ---- |
| demo_0 | PASS | PASS | PASS | PASS | PASS | PASS | REUSED_REVIEW（parent `…1ba11d9d`） |
| demo_32 | PASS | PASS | PASS | PASS | PASS | PASS | DIRECT_REVIEW |
| demo_179 | PASS | PASS | PASS | PASS | PASS | PASS | DIRECT_REVIEW |
| demo_278 | PASS | PASS | PASS | PASS | PASS | PASS | DIRECT_REVIEW |
| demo_242 | PASS | PASS | PASS | PASS | PASS | PASS | DIRECT_REVIEW |
| demo_230 | PASS | PASS | PASS | PASS | PASS | PASS | DIRECT_REVIEW |

```text
PASS = 36
FAIL = 0
UNCERTAIN = 0
NOT_REVIEWED = 0

P1_SIGNAL_GATE = PASS
UPSTREAM_SIGNAL_RISK = NO（全部 P2 错误所在 Episode 的 DIRECTION/GRIPPER 均为 PASS）
```

合法复用：仅 demo_0。child 与 parent 的 `signal_contract_version/hash` 相同。

---

# 4. P2 Overall Review Summary

```text
FINAL_BOUNDARY_TOTAL = 31
VALID = 24
REDUNDANT = 7
MISALIGNED = 0
NOT_REVIEWED = 0
HUMAN_ADDED_MISSED = 0
```

Reason 分布：

| Reason | Count | Episodes |
| --- | ---: | --- |
| REDUNDANT_DIRECTION_JITTER | 3 | demo_242 |
| REDUNDANT_SHORT_PAUSE | 4 | demo_278 ×3，demo_242 ×1 |
| MISALIGNED_* | 0 | — |
| MISSED_* | 0 | — |

```text
CALIBRATION_READINESS = READY_TO_DESIGN_CALIBRATION
```

这不是 Evaluation PASS，也不是把这 6 条宣布为 Calibration Set。

---

# 5. Episode-level Results

| Episode | quality | length | Final | VALID | REDUNDANT | MISALIGNED | MISSED | Valid Rate | Error Count |
| ------- | ------- | -----: | ----: | ----: | --------: | ---------: | -----: | ---------: | ----------: |
| demo_0 | BETTER | 118 | 3 | 3 | 0 | 0 | 0 | 100% | 0 |
| demo_32 | BETTER | 98 | 3 | 3 | 0 | 0 | 0 | 100% | 0 |
| demo_179 | BETTER | 149 | 3 | 3 | 0 | 0 | 0 | 100% | 0 |
| demo_278 | OKAY | 206 | 9 | 6 | 3 | 0 | 0 | 67% | 3 |
| demo_242 | WORSE | 232 | 10 | 6 | 4 | 0 | 0 | 60% | 4 |
| demo_230 | WORSE | 123 | 3 | 3 | 0 | 0 | 0 | 100% | 0 |
| **合计** | | | **31** | **24** | **7** | **0** | **0** | 77% | **7** |

错误全部落在 OKAY/WORSE 两条较长 demo；三条 BETTER 与 demo_230 的 Final 全部 VALID。样本太小，不当作质量分层的统计结论。

---

# 6. REDUNDANT Error Attribution

Exploratory 后处理事实（本轮不改数值）：

```text
direction_persistence_frames = 3
debounce_frames = 4
boundary_consolidation_window = 8
pause_bridge_duration = 10
pause_bridge 仅匹配 MOVE_TO_IDLE → IDLE_TO_MOVE，且夹爪/朝向兼容、无 Hard Boundary
```

## 6.1 demo_278-B0005

```text
Human: REDUNDANT｜冗余边界 / REDUNDANT_SHORT_PAUSE｜短暂停造成的冗余切分
comment: （空）

Machine lineage:
DIRECTION_CHANGE @83
evidence_value ≈ 1.73  PERSISTENT  source=direction_change_evidence
supporting = ACTION_SUPPORT
Decision = KEEP（cluster representative）
→ Final B0005  单成员  Primary=DIRECTION_CHANGE

Attribution:
Candidate Over-generation｜候选过生成
CANDIDATE_OVER_GENERATION
evidence = HIGH
error_mode = MODE_02
```

解释：视频里这段更像短暂停、不值得单独切段，但 Direction Detector 产生了 Candidate，持续性规则把它标成 PERSISTENT，后处理 KEEP 成 Final。本 Episode **没有任何** MOVE_TO_IDLE / IDLE_TO_MOVE，`pause_bridge` / `SUPPRESS_SHORT_PAUSE` **不可能**作用到这条。不是抑制规则漏杀暂停对，而是方向候选不该成为切分点。

## 6.2 demo_278-B0006

```text
Human: REDUNDANT / REDUNDANT_SHORT_PAUSE

Machine:
DIRECTION_CHANGE @105  evidence ≈ 1.50  PERSISTENT
Decision = KEEP → Final B0006  单成员

与邻 Final 间距：B0005@83 → 本条@105 = 22 帧；本条 → B0007@125 = 20 帧
均 ≫ consolidation window=8

Attribution: 同 6.1  CANDIDATE_OVER_GENERATION  HIGH  MODE_02
```

解释：连续方向切分的中间一刀。人工看成短暂停冗余；机器看成另一次稳定方向变化。

## 6.3 demo_278-B0007

```text
Human: REDUNDANT / REDUNDANT_SHORT_PAUSE

Machine:
DIRECTION_CHANGE @125  evidence ≈ 2.10  PERSISTENT  ACTION_SUPPORT
Decision = KEEP → Final B0007  单成员
下一 Final = GRIPPER @135（差 10 帧，略超 window=8，未并入夹爪簇）

Attribution: 主因仍是 CANDIDATE_OVER_GENERATION  HIGH  MODE_02
次要观察：10 vs 8 也碰到 consolidation 边界，但不改主归因
```

解释：夹爪切换前 10 帧的方向切分被单独留下。

## 6.4 demo_242-B0003

```text
Human: REDUNDANT / REDUNDANT_DIRECTION_JITTER｜方向抖动造成的冗余切分

Machine:
DIRECTION_CHANGE @41  evidence ≈ 1.92  PERSISTENT  ACTION_SUPPORT
Decision = KEEP → Final B0003  单成员
P1 DIRECTION = PASS  → UPSTREAM_SIGNAL_RISK = NO

Attribution: CANDIDATE_OVER_GENERATION  HIGH  MODE_01
```

解释：运动方向没有形成值得单独切段的稳定变化，Direction Detector 仍生成 Candidate，后处理 KEEP。

## 6.5 demo_242-B0004

```text
Human: REDUNDANT / REDUNDANT_DIRECTION_JITTER
Machine: DIRECTION_CHANGE @60  evidence ≈ 1.47  PERSISTENT  KEEP → B0004
Attribution: CANDIDATE_OVER_GENERATION  HIGH  MODE_01
```

## 6.6 demo_242-B0005

```text
Human: REDUNDANT / REDUNDANT_DIRECTION_JITTER
Machine: DIRECTION_CHANGE @78  evidence ≈ 2.64  PERSISTENT  KEEP → B0005
Attribution: CANDIDATE_OVER_GENERATION  HIGH  MODE_01
```

B0003/B0004/B0005 间距 19 / 18 帧，都大于 debounce=4 与 consolidation=8。去抖窗口按当前规则本来就不会把它们收掉。

## 6.7 demo_242-B0008

```text
Human: REDUNDANT / REDUNDANT_SHORT_PAUSE

Machine:
DIRECTION_CHANGE @136  evidence ≈ 1.47  PERSISTENT  ACTION_SUPPORT
Decision = KEEP → Final B0008  单成员
右侧 Final B0009 = GRIPPER @146（差 10 帧）
B0009 成员已吸收 MOVE_TO_IDLE@147 与 DIRECTION@152
IDLE_TO_MOVE@153 走 MERGE_RIGHT，目标 B0010 未进入 Final 表（允许，Frozen：target 可指向随后 deactivate 的 id）

Attribution:
Consolidation Failure｜聚合失败
CONSOLIDATION_FAILURE
evidence = MEDIUM
error_mode = MODE_03
次要解释：该方向候选本身也可能是过生成（不硬猜为唯一原因）
```

解释：夹爪切换前 10 帧的方向切分刚好卡在 exploratory consolidation window=8 之外，形成多余 Final。本轮 **不** 给出新的 window 数值。

---

# 7. MISALIGNED Error Attribution

```text
MISALIGNED = 0
```

本样本无人标位置偏移，无从比较 representative vs human corrected_frame。**不能**据此认为 `_pick_representative()` 已验证正确；只能说这次 6 条里没有暴露该层。

---

# 8. MISSED Boundary Attribution

```text
HUMAN_ADDED_MISSED = 0
```

检索口径（因无正式 tolerance）：

```text
EXACT + NEARBY DIAGNOSTIC SEARCH
DIAGNOSTIC_WINDOW_ONLY
exploratory config boundary_tolerance_window = 5
  仅 schema 预留，不是 Frozen GT matching metric
```

无漏检对象，四种 MISSED 分层（生成失败 / 抑制 / 错误合并 / 代表点）均无案例。

---

# 9. Error Mode Bank

真实出现的模式（未预设的 MODE_04 representative 偏移 **本样本不存在**）：

| Error Mode | Human Symptom | Detector Layer | Signal / Candidate Type | Count | Episodes | Evidence Strength |
| ---------- | ------------- | -------------- | ----------------------- | ----: | -------- | ----------------- |
| MODE_01 | REDUNDANT_DIRECTION_JITTER | Candidate generation（方向过生成，后处理 KEEP） | DIRECTION_CHANGE 单成员 | 3 | demo_242 | HIGH |
| MODE_02 | REDUNDANT_SHORT_PAUSE，但机器是 DIRECTION KEEP；pause_bridge 无 MOVE/IDLE 对可作用 | Candidate generation（方向过生成；暂停桥接层未参与） | DIRECTION_CHANGE 单成员 | 3 | demo_278 | HIGH |
| MODE_03 | REDUNDANT_SHORT_PAUSE，方向 Final 距后续夹爪簇 10 帧，window=8 未合并 | Consolidation | DIRECTION_CHANGE 单成员，邻接 GRIPPER cluster | 1 | demo_242 | MEDIUM |

未出现：

- Persistence/Debounce 单独作为主因（这 7 条都已 `PERSISTENT`，且间距 > debounce=4）
- Suppression Failure：`SUPPRESS_SHORT_PAUSE` 从未作用到这些错误对象
- Hard Boundary 过保留：所有 GRIPPER Primary 均为 VALID
- Representative selection 错误：无 MISALIGNED
- 漏检四类

---

# 10. Primary / Merged Evidence Outcome Analysis

只描述当前 31 条 Final，不做显著性结论。

### Primary type → Human outcome

| Primary Type | VALID | REDUNDANT | MISALIGNED |
| ------------ | ----: | --------: | ---------: |
| GRIPPER_TRANSITION | 18 | 0 | 0 |
| DIRECTION_CHANGE | 6 | 7 | 0 |
| MOVE_TO_IDLE | 0 | 0 | 0 |
| IDLE_TO_MOVE | 0 | 0 | 0 |

本样本 **全部错误都是 DIRECTION_CHANGE 作为 Primary 的单成员 Final**。Gripper 代表事件 18/18 VALID。

### Merged evidence composition → Human outcome

成员顺序按物化规则 `frame ASC, candidate_id ASC`，下表把 `GRIPPER+DIRECTION` 与 `DIRECTION+GRIPPER` 合成同一 composition。

| Composition | VALID | REDUNDANT |
| --- | ----: | --------: |
| GRIPPER_TRANSITION only | 5 | 0 |
| GRIPPER_TRANSITION + DIRECTION_CHANGE | 11 | 0 |
| GRIPPER_TRANSITION + DIRECTION_CHANGE + IDLE_TO_MOVE | 1 | 0 |
| GRIPPER_TRANSITION + MOVE_TO_IDLE + DIRECTION_CHANGE | 1 | 0 |
| DIRECTION_CHANGE only | 6 | 7 |

观察：一旦方向变化被并进夹爪簇（Merged Evidence），人工全部判 VALID。被判冗余的 7 条全是 **未合并的 DIRECTION-only Final**。

VALID 的独立方向切分仍然存在：demo_278-B0002/B0003/B0004、demo_242-B0002/B0011、demo_230-B0003。消灭 DIRECTION FP 时不能把这些一起删掉。

`evidence_value` 在 VALID 与 REDUNDANT 方向候选上完全重叠（约 1.47–2.64），**不能**单靠提高阈值分开。本轮不给新阈值。

---

# 11. P1 ↔ P2 Interaction

全部 P2 错误 Episode 的 P1：

```text
DIRECTION = PASS
VIDEO_ALIGNMENT = PASS
```

因此：

```text
UPSTREAM_SIGNAL_RISK = NO
```

更可能是 **boundary 规则 / 方向候选生成 / persistence / consolidation**，而不是 Signal 画错。本轮没有「DIRECTION=FAIL 同时 REDUNDANT_DIRECTION_JITTER」的案例。

---

# 12. Detector Change Surface

只指出层，不给参数。

暴露出问题的层：

1. **Direction candidate generation**  
   证据：7 条 REDUNDANT Primary 全是 `DIRECTION_CHANGE`；其中 3 条人工明确 jitter。  
   下一轮值得校准的参数族：direction evidence / persistence（不给数值）。

2. **Consolidation**  
   证据：1 条 MEDIUM（demo_242-B0008，10 帧 vs window=8）。  
   值得在 Calibration 设计里列为候选 strategy，不是本轮结论。

3. **Pause bridge / short-pause suppression**  
   **本样本未直接失败**：错误对象不是 MOVE↔IDLE 对。但人工 4 次使用 `REDUNDANT_SHORT_PAUSE` 打在 DIRECTION Final 上，说明「短暂停」视觉与当前 pause_bridge 触发条件可能不对齐。Calibration 设计需要把这层列为 **待观察**，不能写成「pause_bridge 已证伪」。

未被本样本暴露、必须默认保护的层：

- Hard-boundary protection：Gripper Primary 18/18 VALID
- Representative selection：无 MISALIGNED；Gripper+Direction 合并簇 13/13 VALID
- Debounce：错误间距都大于 4，当前 debounce 本来就不会收它们

禁止本轮输出：任何「应改为 N」的数字。

---

# 13. Correct Behavior That Must Be Preserved

| Detector mechanism | VALID | REDUNDANT | MISALIGNED |
| --- | ----: | --------: | ---------: |
| GRIPPER_TRANSITION Primary | 18 | 0 | 0 |
| DIRECTION_CHANGE Primary | 6 | 7 | 0 |
| MOVE_TO_IDLE 仅作 Merged Evidence | 含于 1 条 VALID 簇 | 0 | 0 |
| IDLE_TO_MOVE 仅作 Merged Evidence | 含于 1 条 VALID 簇 | 0 | 0 |
| RETAIN_HARD / 夹爪簇代表 | 全部对应 VALID | 0 | 0 |
| MERGE_CONSOLIDATION 进夹爪簇 | 成员方向被吸收后 Final VALID | 0 | 0 |

BETTER 三条（demo_0/32/179）Final 全部 VALID，且多为 Gripper 代表 + Direction 合并证据。调 Direction 时必须保留：

- 被并进夹爪过渡的 direction member
- 人工接受的独立方向切分（上表 6 条 VALID DIRECTION）

---

# 14. Calibration Readiness

```text
run_stage = EXPLORATORY_AUDIT
set_role = EXPLORATORY
```

**不得**静默升级为 `CALIBRATION` 或 `Evaluation GT`。

```text
CALIBRATION_READINESS = READY_TO_DESIGN_CALIBRATION
```

条件核对：

- Human Review complete：是（6/6，36/36 Signal，31/31 Final）
- Review schema valid：是
- P1 无阻断性 FAIL：是
- P2 error modes 可解释：是（3 个 mode）
- 样本不是独立评测集：明确

不是 `READY_TO_DEPLOY`。不是 Evaluation PASS。

---

# 15. Source Immutability

分析前后 fingerprint（SHA256）：

| 对象 | before | after | 结果 |
| --- | --- | --- | --- |
| Owner SQLite | `2b262a201fedba71d37366aa58f228a3d98903f29cf3cd1adc3870f7c9b51502` size=61440 | 相同 | **OWNER_SQLITE_UNCHANGED = PASS** |
| Child Audit Run tree | `4ec155960e70187a89948e1fa9193d0dc4837eb6c1d36dc96016be54df3db4fe` files=44 | 相同 | **AUDIT_RUN_UNCHANGED = PASS** |

SQLite 以 `file:...?mode=ro` 打开。派生文件只写：

```text
0-doc/80-audit-local/Project2_G1_Human_Review_Error_Attribution_Audit_20260917.md
outputs/g1_human_review_analysis/20260917_error_attribution/
  boundary_error_attribution.csv
  episode_review_summary.csv
  analysis_summary.json
  build_error_attribution.py
```

---

# 16. Recommended Next Design Step

等待 Design Owner 决定 G1-P3 **Calibration 设计**（不是本轮改 threshold）。

建议设计时纳入：

1. Direction candidate 的 FP/TP 成对观察（本样本 7 REDUNDANT vs 6 VALID）
2. 「DIRECTION-only Final」vs「Direction 作为夹爪 Merged Evidence」分开计分
3. Consolidation window 仅作 **有限 strategy 候选**，用 B0008 做诊断案例，不做网格搜索结论
4. 人工 `REDUNDANT_SHORT_PAUSE` 与机器 pause_bridge 触发条件的对齐检查
5. 正式 `tolerance_frames` 仍 `DATA_CALIBRATION_PENDING`，先冻结 matching 规则再 search
6. **独立 Evaluation Set** 另建；这 6 条 Exploratory 不得回灌成评测

本轮 **STOP**。不改 Detector，不重跑，不生成新 Run。
