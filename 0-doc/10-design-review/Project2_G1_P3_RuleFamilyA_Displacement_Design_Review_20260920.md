# Project 2 G1-P3 Rule Family A Displacement Design Review

```text
DATE = 2026-09-20
DOCUMENT_STATUS = ACTIVE_DESIGN_REVIEW_RESULT
TASK = RULE_FAMILY_A_FORMAL_DESIGN_REVIEW
SOURCE_OF_TRUTH = GITHUB_MAIN

DETECTOR_MODIFIED = NO
CONFIG_GENERATED = NO
PARAMETER_SEARCH_EXECUTED = NO
DISPLACEMENT_CUTOFF_SELECTED = NO
STAGE_A_EXECUTED = NO
STAGE_B_EXECUTED = NO
```

本轮不是重新做数据分析、重算 displacement、参数搜索或 Detector 修改。本轮是
`Evidence → Engineering Interpretation → Design Classification`。
证据只来自 GitHub main 上的 Preparation Result（及 prep_id 一致的只读 runtime artifact），不重跑任何 Preparation。

---

## 1. GitHub Authority Readback

```text
repo = Modori1998/embody_project2_data_value
branch = main
HEAD = 8a1d69b2b784bb7b329998966dabbcad63a15c09
origin/main = 8a1d69b2b784bb7b329998966dabbcad63a15c09
LOCAL_HEAD == ORIGIN_MAIN = YES
WORKTREE = CLEAN
```

LATEST_ENGINEERING_MASTER = `0-doc/Project_2_Engineering_Design_Master_v1_20260914.md`
LATEST_ROADMAP = `0-doc/Project2_Development_Roadmap_and_Design_Gate_Plan_v1_20260914.md`
LATEST_PROTOCOL = `FROZEN_v1.1`（`Project2_G1_P3_Calibration_Protocol_FROZEN_v1_20260917.md` + `..._v1_1_PATCH_20260918.md`）
LATEST_BASELINE_SCORING = `0-doc/Project2_G1_P3_Baseline_Scoring_Result_20260918.md`
LATEST_STAGE_A0 = `0-doc/Project2_G1_P3_Stage_A0_Direction_Discriminability_Result_20260918.md`
LATEST_A_PREPARATION = `0-doc/Project2_G1_P3_RuleFamilyA_Displacement_Preparation_Result_20260918.md`

Roadmap 位置确认：当前仍位于 `P2-S1C`（Human Calibration + Threshold / Strategy Search）；
`P2-S1D`（Final Config Freeze + Independent Evaluation）尚未进入。

```text
EFFECTIVE_PROTOCOL = FROZEN_v1.1
```

## 2. Supersession Search

扫描 `0-doc/`、`0-doc/10-design-review/`、`0-doc/80-audit-local/`、`0-doc/90-implementation-local/`。

```text
SUPERSEDING_DOC_FOUND = NO
AUTHORITY_CONFLICT = NO
```

`Project2_G1_P3_RuleFamilyA_Displacement_Preparation_Result_20260918.md` 是 scope 内最新且唯一的 Rule Family A 证据输入，无更晚、同 scope、明确 supersede 的文档。

## 3. Current State Reconstruction

### Baseline Scoring

```text
TP = 56
FP = 10
FN = 0
EXACT_TP = 56

VALID_DIRECTION = 17  (Seed = 6, Fresh = 11)
DIRECTION_FP = 9  (MODE_01 = 3, MODE_02 = 3, MODE_03 = 1, UNASSIGNED = 2)
NON_DIRECTION_FP = 1  (outside Rule Family A scope)

SEED_VALID_DIRECTION_RECALL = 1.0       (6/6, HARD guardrail)
FRESH_VALID_DIRECTION_RECALL_BASELINE = 1.0  (11/11)
FN_BASELINE = 0
```

### Stage A0

Stage A0 已证明 threshold-only 与 persistence-only 都不可作为主路线，threshold × persistence 的单调搜索在当前分布上无法在保护 17 条 VALID 的前提下删除任何 Direction FP：

```text
THRESHOLD_ONLY_RISK = HIGH   (evidence 在 VALID/FP 上 range 与 IQR 均重叠，
                             MODE_01 @78 evidence=2.643 > VALID max=2.532)
PERSISTENCE_ONLY_RISK = HIGH (FP run_length 中位数 8 > VALID 中位数 7)
JOINT_MIN_BOX: FP outside = 0/9，FP inside = 9/9
STAGE_A_THRESHOLD_PERSISTENCE_SEARCH = OWNER_REVIEW_REQUIRED
G1_STAGE_A0 = PASS_READY_FOR_OWNER_GATE
```

### Rule Family A Preparation

```text
PREP_ID = g1_rule_family_a_prep_20260918_173501
A_PREP_EVIDENCE_STATUS = READY_FOR_RULE_FAMILY_A_REVIEW
```

## 4. Physical Interpretation｜位移为什么有意义

`pre_displacement_m = ‖Σ delta_xyz[t-8:t]‖₂`、`post_displacement_m = ‖Σ delta_xyz[t:t+8]‖₂`，
与 `direction_change_evidence` 使用相同的左右 W=8 窗口，度量的是方向候选切点**两侧各自累积的净平移量**（单位 meter）。

物理含义：

- `direction_change_evidence` 度量的是左右速度向量的**夹角**（方向转了多少），但它对**两侧是否有真实位移**不敏感：在极低位移时，`arccos(cosine)` 对噪声高度放大，能把一次几乎不动的微调编码成大角度“转向”。
- displacement 补的正是这一维：**这个候选边界是否真的由两个“充分运动阶段”构成**。若某一侧净位移近零，则该侧本质是“静止 / 短暂停 / 微调”，不是一个真实的运动方向切换。

这就是“位移充分性”作为物理条件的原因：它是 `direction_change_evidence` 之外的**运动幅度（magnitude）维度**，与方向角度（direction）维度正交互补。A0 中 `heading_angle_rad ≡ evidence_value`（只讲角度）无法区分，displacement 提供了角度之外的独立信息。

## 5. Evidence Recap（只读恢复，不重算）

### 边际分布

| 字段 | VALID (n=17) median / IQR / range | FP (n=9) median / IQR / range | range overlap | IQR overlap |
|---|---|---|---|---|
| pre | 0.040708 / [0.032586, 0.047502] / [0.020009, 0.099797] | 0.022661 / [0.017944, 0.027872] / [0.010488, 0.057515] | YES | NO |
| post | 0.034318 / [0.028948, 0.046074] / [0.017244, 0.084162] | 0.012475 / [0.011427, 0.020726] / [0.006819, 0.039503] | YES | NO |
| min(pre,post) | 0.031255 / [0.026288, 0.042484] / [0.017244, 0.084162] | 0.012475 / [0.010488, 0.018023] / [0.006819, 0.039503] | YES | NO |

三个字段的 IQR 在 VALID vs FP 之间均**不重叠**，Seed+Fresh 同向（VALID_HIGHER）；但 range 全部重叠。

```text
SEED_PATTERN = VALID_HIGHER_MEDIAN_WITH_RANGE_OVERLAP
FRESH_PATTERN = VALID_HIGHER_MEDIAN_WITH_RANGE_OVERLAP
CONSISTENCY = INSUFFICIENT
INSUFFICIENT_FRESH_NEGATIVE_EVIDENCE = YES
```

### 关键事实

- FP 的 min(pre,post) 最大值 = **0.039503**（MODE_01 @41），高于 VALID 中位数 0.031255。
- VALID 的 min(pre,post) 最小值 = **0.017244**（SEED demo_242@224），低于 FP 的 q75（0.018023）。
- MODE_02 三条 post 全部 < 0.013 m（@83 仅 0.006819）。
- Fresh Direction FP 只有 2 条：`demo_162@211` min=0.034185（高），`demo_255@116` min=0.010488（低）。

## 6. Design Review Question 1 — Hard Gate Feasibility

针对 `min(pre,post) < threshold → reject` 的硬门控语义逐项评审：

1. **VALID / FP range overlap**：YES。VALID min 0.017244 < FP max 0.039503，无单一 threshold 可切分。
2. **high-displacement FP**：存在。`demo_242@41`（MODE_01）min=0.039503、pre=0.057515，高于 VALID 中位数；`demo_162@211`（Fresh）min=0.034185。
3. **low-displacement VALID**：存在。`demo_242@224` min=0.017244（全表最低 VALID）、`demo_255@14` min=0.018559、`demo_260@75` min=0.019910。
4. **Fresh 反例**：双向存在。`demo_255@14`（Fresh VALID，min=0.018559）是低位移合法方向；`demo_162@211`（Fresh FP，min=0.034185）是高位移 FP。
5. **是否破坏现有 guardrail**：会。`demo_242@224` 是 **SEED** VALID，受 `SEED_VALID_DIRECTION_RECALL = 1.0`（HARD）保护，且它是全部 17 条 VALID 中位移最低者。任何能删到它的 displacement 门直接违反 HARD guardrail；任何保住它的门（threshold < 0.0172）则只能删掉最低的 6 条 FP（@83/@105/@125/@136/@78/@116），永远删不掉 @41 / @60 / @211 三条中高位移 FP，且对 `demo_242@60`（min=0.018023，恰夹在两个最低 VALID @224=0.017244 与 @14=0.018559 之间）无任何安全余量。

结论：displacement **不能**作为独立硬门控。range 重叠 + 高位移 FP + 低位移 VALID + Seed 硬 guardrail 四者共同关闭了 "min(pre,post) < threshold → reject" 的设计语义。

```text
HARD_DISPLACEMENT_GATE_SUPPORTED = NO
```

## 7. Design Review Question 2 — Auxiliary Evidence Feasibility

位移不单独决定 Candidate 留删，而是作为「运动是否真实充分」的一项证据，进入联合 Motion Sufficiency Context（概念上：Direction Change + Persistence + Motion Sufficiency → Candidate Acceptance）。

支持点：

- 三个字段 IQR 在 VALID vs FP 之间不重叠，Seed+Fresh 同向 VALID_HIGHER —— 这是真实的群体级可分性，不是噪声。
- MODE_02 三条被位移完全解释（post 近零）。
- MODE_01 @78（evidence 全表最高 2.643，但弱侧位移 0.014685）证明 displacement 提供 direction evidence 之外的**新信息**。
- 它与 A0 中 `local_speed_min`（P(VALID>FP)=0.856）互为印证，同属运动幅度维度。

限制点（为何不能单独 reject）：

- range 重叠、存在高位移 FP（@41）与低位移 VALID（@224）。
- Fresh n=2 且行为不一致，无法外推。
- 它只能作为联合证据中的一项，不能独立决定留删。

```text
AUXILIARY_DISPLACEMENT_EVIDENCE_SUPPORTED = YES
```

## 8. MODE_02 Review

MODE_02 = demo_278 @83 / @105 / @125，Human = REDUNDANT_SHORT_PAUSE。

| event | pre | post | min | local_speed_min |
|---|---:|---:|---:|---:|
| @83 | 0.022661 | 0.006819 | 0.006819 | 0.009678 |
| @105 | 0.017944 | 0.012014 | 0.012014 | 0.019469 |
| @125 | 0.013311 | 0.009448 | 0.009448 | 0.010307 |

三条 post 全部 < 0.013 m，min(pre,post) 全部落在 FP 分布底部；`@83` 是全部 26 条事件中 min 最低者（0.006819）。三条 local_speed_min 也全部偏低。

解释：人类判为「短暂停 / 微调」的事件，在 Formal Signal 上表现为**切点一侧真实运动不足**（weak post-motion / motion insufficiency）。左右 W=8 窗内的净位移近零，说明该“转向”不是由两个充分运动阶段构成，而是减速—再加速过程中的角度噪声被编码为大 heading 角。这与 Protocol §15 的 SEMANTIC MISMATCH 一致，且 displacement 与 speed 两个幅度量都在此高度一致。

```text
MODE_02_DISPLACEMENT_EXPLANATION = STRONG
```

## 9. MODE_01 Review

MODE_01 = demo_242 @41 / @60 / @78，Human = REDUNDANT_DIRECTION_JITTER。

- `demo_242@78`：evidence = **2.643**（全表最高，> 全部 VALID max 2.532），但 min(pre,post) = 0.014685，弱侧位移很低。**方向 evidence 很强、弱侧位移偏低**，displacement 在此提供 direction evidence 之外的独立信息 → 支持 displacement 的价值。
- `demo_242@60`：min = 0.018023，偏低但恰夹在两个最低 VALID（@224=0.017244、@14=0.018559）之间 → 部分一致。
- `demo_242@41`：pre=0.057515、min=0.039503，**高于 VALID 中位数** 的高位移 FP。displacement 无法解释这条 jitter FP。

必须明确承认：

```text
Displacement cannot explain all MODE_01 FP.
```

MODE_01 三条中一条强支持（@78）、一条部分（@60）、一条反例（@41）。

```text
MODE_01_COVERAGE = PARTIAL
main counterexample = demo_242@41 (high-displacement FP)
```

## 10. Fresh Generalization

Fresh Direction FP = 2（UNASSIGNED）：

- `demo_162@211`：min=0.034185（高位移 FP，且 run_length=17 全表最长）
- `demo_255@116`：min=0.010488（低位移 FP，接近底部）

一条高、一条低，行为不一致。

```text
FRESH_FP_PATTERN = HETEROGENEOUS
generalization status = INSUFFICIENT_FRESH_NEGATIVE_EVIDENCE (维持)
```

不得把 Seed 上“低位移 FP / 高位移 VALID”的模式外推成 Fresh 结论。Fresh n=2，任何“Fresh 已验证”的 displacement 分割声明都证据不足。

## 11. VALID Safety Review

最低 displacement 的 VALID 反例（来自 Preparation 的 Lowest VALID Counterexamples）：

| rank | event | package | pre | post | min |
|---:|---|---:|---:|---:|---:|
| 1 | demo_242@224 | SEED | 0.020009 | 0.017244 | 0.017244 |
| 2 | demo_255@14 | FRESH | 0.047502 | 0.018559 | 0.018559 |
| 3 | demo_260@75 | FRESH | 0.033963 | 0.019910 | 0.019910 |
| 4 | demo_255@75 | FRESH | 0.024536 | 0.037290 | 0.024536 |
| 5 | demo_278@52 | SEED | 0.026288 | 0.029863 | 0.026288 |

- **lowest pre VALID** = `demo_242@224`（0.020009）
- **lowest post VALID** = `demo_242@224`（0.017244）
- **lowest min(pre,post) VALID** = `demo_242@224`（0.017244）

最易被误杀的合法 Direction：

1. `demo_242@224`（SEED）：pre/post 双侧都低，是全部 VALID 中位移最低者，且受 `SEED_VALID_DIRECTION_RECALL = 1.0` HARD 保护。任何 displacement 门在这里零余量。
2. `demo_255@14`（FRESH）：pre 强（0.0475）post 弱（0.0186）的**非对称合法方向**。min() 会把它的弱侧当成“不足”而误杀；这说明合法方向完全可以是“一侧充分、一侧接近静止”（例如接近抓取点后的定向停顿再移动）。
3. `demo_260@75`（FRESH）：min=0.0199，紧贴 FP @60（0.0180）。

```text
VALID_SAFETY_RISK = HIGH
```

理由：最低位移 VALID（0.0172）与 FP 集群（q75=0.0180）几乎贴着，且其中包含一条受 HARD 保护的 SEED 事件和至少两条 Fresh 合法非对称方向。位移门若引入，误杀合法 Direction 的风险不是边缘风险，而是结构性的。

## 12. Shape Review

### Shape A — pre sufficient AND post sufficient（双侧分别满足）

- 保留方向性，能指出“运动后停住”或“几乎从静止起步”是哪一侧不足。
- 需要两个条件（两个 threshold 或同一 threshold 双侧判断）。

### Shape B — min(pre,post) sufficient（较弱侧位移要求）

- 单变量表达“两侧都充分”的等价含义：较弱侧是 binding constraint。
- 物理解释更紧凑：Direction Boundary 是否真的由两个充分运动阶段构成，取决于**最弱的一侧**。

| 维度 | Shape A | Shape B |
|---|---|---|
| Physical Interpretability | 高，保留左右方向 | 高，弱侧即决定项 |
| Complexity | 更高（双条件） | 更低（单变量） |
| Debuggability | 更细（可指认哪一侧） | 略粗（只知弱侧） |
| Counterexample Transparency | 好（能看到不对称） | 好（min 直接暴露反例） |
| Future Calibration Complexity | 更高（需标定双侧/双阈值） | 更低（单一阈值标定） |

在单阈值语义下两者等价（pre≥T ∧ post≥T ⟺ min≥T）。作为“未来 Motion Sufficiency Context 中的位移分量”，更倾向紧凑、可调、可解释的单变量形式。

```text
PREFERRED_FUTURE_SHAPE = B
```

（不选择任何数值 threshold。）

## 13. Separation of Concerns

```text
MODE_03 primary layer = EVENT_CONSOLIDATION
non-Direction near-Gripper FP = EVENT_CONSOLIDATION
```

`demo_242@136`（MODE_03）距下一 Gripper Final 仅 10 frames（Gripper @146），属于「多个 Candidate 属于同一真实物理事件」的 consolidation 距离问题，留给 Stage B `{8,10,12}` 讨论，不是 Candidate Acceptance 错误。

非 Direction near-Gripper FP（`demo_255-B0007 @135 IDLE_TO_MOVE`）也属于 EVENT_CONSOLIDATION。

这些 event 的 displacement 也低（@136 min=0.012475），但**不能因此把它们重归类到 Rule Family A**。低位移是它们的伴随特征，不是它们的失败主层。

## 14. Formal Counterexample Table

| event | label | Seed/Fresh | mode | pre | post | min | supports A? | interpretation |
|---|---|---|---|---:|---:|---:|---|---|
| demo_242@41 | DIRECTION_FP | SEED | MODE_01 | 0.057515 | 0.039503 | 0.039503 | CONTRADICT | 高位移 jitter FP（> VALID 中位数），位移无法解释 |
| demo_242@60 | DIRECTION_FP | SEED | MODE_01 | 0.018023 | 0.020726 | 0.018023 | PARTIAL | 弱侧偏低，但夹在最低两条 VALID 之间 |
| demo_242@78 | DIRECTION_FP | SEED | MODE_01 | 0.027872 | 0.014685 | 0.014685 | SUPPORT | 方向 evidence 全表最高但弱侧位移低，位移提供新信息 |
| demo_278@83 | DIRECTION_FP | SEED | MODE_02 | 0.022661 | 0.006819 | 0.006819 | SUPPORT | 全表最低 min，post 近零 |
| demo_278@105 | DIRECTION_FP | SEED | MODE_02 | 0.017944 | 0.012014 | 0.012014 | SUPPORT | post 低，短暂停 |
| demo_278@125 | DIRECTION_FP | SEED | MODE_02 | 0.013311 | 0.009448 | 0.009448 | SUPPORT | pre/post 双侧都低 |
| demo_242@136 | DIRECTION_FP | SEED | MODE_03 | 0.027274 | 0.012475 | 0.012475 | (out of scope) | 位移低但 primary layer = consolidation（距 Gripper 10 frames） |
| demo_162@211 | DIRECTION_FP | FRESH | UNASSIGNED | 0.034185 | 0.036250 | 0.034185 | CONTRADICT | 高位移 FP，run_length=17 最长 |
| demo_255@116 | DIRECTION_FP | FRESH | UNASSIGNED | 0.010488 | 0.011427 | 0.010488 | SUPPORT | 低位移 FP，近底部 |
| demo_242@224 | VALID | SEED | — | 0.020009 | 0.017244 | 0.017244 | CONTRADICT | 全表最低 VALID min，SEED HARD guardrail |
| demo_255@14 | VALID | FRESH | — | 0.047502 | 0.018559 | 0.018559 | CONTRADICT | 非对称合法方向：pre 强 post 弱 |
| demo_260@75 | VALID | FRESH | — | 0.033963 | 0.019910 | 0.019910 | CONTRADICT | 弱侧低，紧贴 FP @60 |
| demo_255@75 | VALID | FRESH | — | 0.024536 | 0.037290 | 0.024536 | CONTRADICT | 非对称合法方向：pre 弱 post 强 |
| demo_278@52 | VALID | SEED | — | 0.026288 | 0.029863 | 0.026288 | CONTRADICT | 双侧偏低但仍为合法 Direction |

```text
SUPPORT     = 6  (MODE_01@78；MODE_02 三条；Fresh FP @116 一条 + MODE_03 低位移伴随但归 consolidation)
CONTRADICT  = 7  (高位移 FP @41/@211；低位移 VALID @224/@14/@260-75/@255-75/@278-52)
PARTIAL     = 1  (MODE_01@60)
```

## 15. Final Rule Family A Classification

```text
RULE_FAMILY_A_CLASSIFICATION = DISPLACEMENT_SUPPORTED_AS_AUXILIARY_EVIDENCE (A2)
```

中文：位移有真实、独立的物理价值，但不能单独 reject Candidate；应进入后续联合 Motion Sufficiency Design。

排除其他选项的理由：

- **A1 (SIMPLE_HARD_DISPLACEMENT_RULE_SUPPORTED)** 不成立：range 重叠、存在高位移 FP（@41）、低位移 VALID（@224）、且硬门会违反 `SEED_VALID_DIRECTION_RECALL=1.0` HARD guardrail。
- **A3 (MODE_SPECIFIC_DISPLACEMENT_EVIDENCE)** 低估了位移：它不只是解释部分 mode，而是与 direction 正交的运动幅度维度，MODE_02 被完全解释、@78 提供新信息、三个字段 IQR 全不重叠且 Seed+Fresh 同向。
- **A4 (DISPLACEMENT_NOT_ROBUST_ENOUGH)** 不成立：群体级可分性（IQR 不重叠）与机制解释（MODE_02）都足够稳健，只是不能独立当硬门。

## 16. Rule Family B Handoff

```text
RULE_FAMILY_B_REVIEW = RECOMMENDED
```

位移（运动幅度）与局部速度上下文（local speed）同属幅度维度，且 A0 中 `local_speed_min` 是最强单变量派生量（P(VALID>FP)=0.856，IQR 不重叠，Seed+Fresh 同向）。Rule Family B 值得继续，以回答 displacement 未解决的 FP 与 VALID 反例。

A 留下的 unresolved 问题（交给 B 解释）：

1. `demo_242@41`（MODE_01 高位移 FP）：是否发生在低速 valley？—— 当前 local_speed_min=0.0361，并不低，B 可能也解释不了这条，需单独追问其 jitter 机制（run_length=8、evidence=1.917）。
2. `demo_162@211`（Fresh 高位移 FP，run=17）：local_speed_min=0.0200 偏低，B 的局部速度谷上下文可能解释这条长持续性 heading 变化。
3. `demo_255@14`（VALID 反例）：local_speed_min=0.0131 是全部 VALID 最低，displacement 与 speed 会**共享同一条 VALID 反例**，B 若引入速度门需先解决这条。
4. `demo_242@60`（MODE_01）：min=0.018、run=13，displacement 与 persistence 都切不动，B 需回答其局部运动上下文是否异常。

```text
RULE_FAMILY_B_STARTED = NO
```

## 17. Explicit Non-Scope

```text
DETECTOR_MODIFIED = NO
CONFIG_GENERATED = NO
PARAMETER_SEARCH_EXECUTED = NO
DISPLACEMENT_CUTOFF_SELECTED = NO
STAGE_A_EXECUTED = NO
STAGE_B_EXECUTED = NO
RULE_FAMILY_B_STARTED = NO
SIMPLE_ACCEPTANCE_RULE_SUPPORTED = NOT_DECIDED (需 A/B/C/D 完成后的总 Owner Gate)
RULE_FAMILY_SUPPORTED_BUT_THRESHOLD_NOT_READY = NOT_DECIDED
NO_ROBUST_ACCEPTANCE_RULE = NOT_DECIDED
MIXED_MODE_SPECIFIC = NOT_DECIDED
```

未修改 `Project_2_Engineering_Design_Master_v1_20260914.md` 与 `Project2_Development_Roadmap_and_Design_Gate_Plan_v1_20260914.md`（Rule Family A/B/C/D 总 Owner Gate 未完成前不得改长期 SSOT）。

## 18. Final Status

```text
G1_RULE_FAMILY_A_FORMAL_DESIGN_REVIEW = PASS_READY_FOR_RULE_FAMILY_B
```

Rule Family A 结论：displacement 进入 Direction Candidate Acceptance 的角色为 **Auxiliary Evidence（辅助证据）**，进入后续联合 Motion Sufficiency Design；不作为独立硬门控；首选未来 shape 为弱侧位移要求（Shape B）。

等待 Design Owner 确认后再决定是否启动 Rule Family B。
