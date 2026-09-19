# Project 2 G1 Final Boundary Merged Semantics Audit

```text
DATE = 2026-09-17
TASK = READ / INSPECT / REPORT ONLY
CONTRACT = P2_G1_AUDIT_FOLDER_V1
ENGINE_FILES_MODIFIED = NO
SCHEMA_MODIFIED = NO
WEB_MODIFIED = NO
SQLITE_MODIFIED = NO
NEW_RUN_GENERATED = NO
```

本轮只确认：多个 Candidate 合并成一个 Final Boundary 之后，Final 表直接保留了什么，以及 member 语义能否按引用恢复。

权威代码：

- `src/project2_g1/boundary_engine.py`
- `src/project2_g1/boundary_io.py`

权威 CSV（smoke 与 Web bootstrap 内容一致）：

- `outputs/g1_p2_boundary_audit/demo_0/{candidate_boundaries,boundary_decisions,final_boundaries}.csv`
- `outputs/g1_audit_runs/g1_exploratory_audit_20260916_214523_1ba11d9d/diagnostic/demo_0/` 同文

---

## 0. Direct answers

```text
FINAL_DIRECT_TYPE = GRIPPER_TRANSITION
FINAL_DIRECT_FRAME = 56

MEMBER_IDS_PRESENT = YES
MEMBER_TYPE_FRAME_DIRECTLY_PRESENT = NO
MEMBER_SEMANTICS_PRESERVED_BY_REFERENCE = YES
WEB_MEMBER_SEMANTICS_DIRECTLY_VISIBLE = NO

SEMANTIC_STATE = PRESERVED_BY_LINEAGE_ONLY
```

一句话：

> 对于 `B0002@56`，系统**仍然知道** `C0003 = DIRECTION_CHANGE @57`，但 **Final 行本身不展开** 这条语义；必须用 `member_candidate_ids` 去 `candidate_boundaries.csv`（或 `boundary_decisions.csv`）join 才能读到 type/frame。

当前 Final schema **没有把 member 的 type/frame 内联进 Final 行**。这不是删除，是 **lineage-only**：ID 还在，展开语义不在 Final 直接字段里。

---

## 1. B0002 complete lineage

### Final Boundary

来源：`outputs/g1_p2_boundary_audit/demo_0/final_boundaries.csv`

```text
Final Boundary:
boundary_id           = demo_0-B0002
frame                 = 56
candidate_type        = GRIPPER_TRANSITION
reason                = PERSISTENT_GRIPPER_OPEN_TO_CLOSE
member_candidate_ids  = demo_0-C0002|demo_0-C0003
supporting_reasons    = ACTION_SUPPORT
review_flags          = (empty)
polarity              = OPEN_TO_CLOSE
config_version        = g1_p2_exploratory_segmentation.v0
segmentation_version  = G1-P2-EXPLORATORY-v0
```

Web bootstrap 同文件内容相同。

### Member lookup: C0002

来源：`outputs/g1_p2_boundary_audit/demo_0/candidate_boundaries.csv`

```text
candidate_id       = demo_0-C0002
frame              = 56
candidate_type     = GRIPPER_TRANSITION
primary_reason     = PERSISTENT_GRIPPER_OPEN_TO_CLOSE
supporting_reasons = (empty)
source_signal      = gripper_aperture
evidence_value     = 0.008209197499796553
polarity           = OPEN_TO_CLOSE
persistence_status = PERSISTENT
```

Decision 行：`KEEP` · `hard boundary anchored as cluster representative` · `target_boundary_id = demo_0-B0002`

### Member lookup: C0003

```text
candidate_id       = demo_0-C0003
frame              = 57
candidate_type     = DIRECTION_CHANGE
primary_reason     = PERSISTENT_DIRECTION_CHANGE
supporting_reasons = ACTION_SUPPORT
source_signal      = direction_change_evidence
evidence_value     = 2.3566302539306
polarity           = DIRECTION_CHANGE
persistence_status = PERSISTENT
```

Decision 行：`MERGE_CONSOLIDATION` · `consolidated into demo_0-B0002 anchored at GRIPPER_TRANSITION@56` · `target_boundary_id = demo_0-B0002`

C0003 **没有从 Candidate 表删除**。它以完整一行继续存在。

---

## 2. 关键问题 1 — Final 表直接保留了什么？

`boundary_io.py` 中 `final_boundaries.csv` 字段完全来自 `BoundaryEvent.to_row()`。写入时：

```text
member_candidate_ids = "|".join(self.member_candidate_ids)
supporting_reasons   = "|".join(self.supporting_reasons)
```

`consolidate_candidates()` 填充这些字段的方式：

```text
frame              = representative.frame
candidate_type     = representative.candidate_type
reason             = representative.primary_reason
polarity           = representative.polarity
member_candidate_ids = [member.candidate_id for member in cluster]
supporting_reasons   = union(member.supporting_reasons for member in cluster)
```

逐列：

| 列 | B0002 实际值 | 含义 |
| --- | --- | --- |
| `boundary_id` | `demo_0-B0002` | 新 Final ID，不是 candidate_id |
| `frame` | `56` | **只保存 representative frame** |
| `candidate_type` | `GRIPPER_TRANSITION` | **只保存 representative type**，不聚合 member types |
| `reason` | `PERSISTENT_GRIPPER_OPEN_TO_CLOSE` | representative 的 `primary_reason` |
| `member_candidate_ids` | `demo_0-C0002\|demo_0-C0003` | **只有 ID**，不含 type/frame |
| `supporting_reasons` | `ACTION_SUPPORT` | member 上已有的 **evidence tag 并集**，不是 member type |
| `review_flags` | empty | 本事件无 REVIEW_REQUIRED |
| `polarity` | `OPEN_TO_CLOSE` | representative polarity（夹爪开→合），不是 DIRECTION_CHANGE |
| `config_version` | `g1_p2_exploratory_segmentation.v0` | 配置身份 |
| `segmentation_version` | `G1-P2-EXPLORATORY-v0` | 切分身份 |

### A. `candidate_type`

只保存 **representative candidate type**。

B0002 = `GRIPPER_TRANSITION`。不会写成 `GRIPPER_TRANSITION|DIRECTION_CHANGE`。

### B. `frame`

只保存 **representative frame = 56**。不保存 `57`，也没有 `member_frames` 列。

### C. `member_candidate_ids`

只保存 ID 字符串：

```text
demo_0-C0002|demo_0-C0003
```

ID 顺序 = cluster 内按 **frame 升序**（`_cluster_candidates` 先 `sorted(..., key=frame)`），不是 type 优先级顺序。不含 type/frame。

### D. `supporting_reasons`

**不会**把 `C0003 = DIRECTION_CHANGE` 存成 supporting semantic。

它只保存 Candidate 上已有的 evidence tag：

```text
ROTATION_SUPPORT
ACTION_SUPPORT
```

这些 tag 来自 `attach_supporting_evidence()`：仅当 `candidate_type in MOTION_TYPES`（`MOVE_TO_IDLE` / `IDLE_TO_MOVE` / `DIRECTION_CHANGE`）且窗口内旋转/指令峰值过阈值时追加。Gripper candidate 不会被打上这些 tag。

因此 B0002 的 `ACTION_SUPPORT` 来自 **C0003 自己的 supporting_reasons**，不是来自把 `DIRECTION_CHANGE` 提升为 Final 语义。

反例：`demo_179-B0001` 同样是 gripper + direction merge，但 C0002 没有 ACTION/ROTATION tag，于是 Final `supporting_reasons` 为空。说明 **merged DIRECTION_CHANGE 不会自动出现在 Final.supporting_reasons**。

---

## 3. 关键问题 2 — C0003 语义是否“保留但需要 join”？

```text
MEMBER_SEMANTICS_PRESERVED_BY_REFERENCE = YES
```

证据：

1. `candidate_boundaries.csv` 仍有完整一行 `demo_0-C0003`，含 `DIRECTION_CHANGE` / `57` / `source_signal` / `evidence_value` / `polarity`。
2. `final_boundaries.csv` 的 `B0002.member_candidate_ids` 含稳定 ID `demo_0-C0003`。
3. `boundary_decisions.csv` 另有一条可追溯路径：`C0003.decision = MERGE_CONSOLIDATION` 且 `target_boundary_id = demo_0-B0002`，该行同时带 `frame` 与 `candidate_type`（`_decision_rows()` 从 Candidate 对象回填）。

```text
Final 自身不展开 member semantics
但可以通过 member_candidate_ids join Candidate 表恢复
也可以通过 Decision.target_boundary_id 反向 join
```

没有任何一步删除 C0003 的 type/frame。丢失的只是 **Final 行上的内联展开**。

---

## 4. 关键问题 3 — Web 当前能不能方便看出来？

读取：`src/project2_g1_audit_web/templates/audit.html`、`view.py`、`reviews.py`。

Web **不 join** Candidate 来展开 member。Final / P2 卡片直接渲染 CSV 字符串：

- Diagnostics「Final Boundary」表：`member_candidate_ids` 原样显示 `demo_0-C0002|demo_0-C0003`
- 同一行的 `candidate_type` / `frame` 只显示代表点 `GRIPPER_TRANSITION` / `56`
- P2 卡片同样只展示 `member_candidate_ids` 字符串

同一 Final 行 **看不到**：

```text
C0002 @56 GRIPPER_TRANSITION
C0003 @57 DIRECTION_CHANGE
```

必须再去 Diagnostics 的 Candidate 表（或 Decisions 表）手工查 ID。

Frame 轴会在 56 和 57 分别打 mark，title 含各自 `type`，但那不是 Final 行展开，也不能替代 join。

```text
WEB_MEMBER_SEMANTICS_DIRECTLY_VISIBLE = NO
```

---

## 5. 关键问题 4 — representative 选择规则（代码，不是设计文档）

```text
file     = src/project2_g1/boundary_engine.py
function = _pick_representative
```

```python
TYPE_PRIORITY = {
    CANDIDATE_GRIPPER: 0,          # GRIPPER_TRANSITION
    CANDIDATE_MOVE_TO_IDLE: 1,     # MOVE_TO_IDLE
    CANDIDATE_IDLE_TO_MOVE: 1,     # IDLE_TO_MOVE
    CANDIDATE_DIRECTION: 2,        # DIRECTION_CHANGE
}

def _pick_representative(cluster: list[BoundaryCandidate]) -> BoundaryCandidate:
    return sorted(
        cluster,
        key=lambda item: (TYPE_PRIORITY.get(item.candidate_type, 9), item.frame),
    )[0]
```

选择键 = `(TYPE_PRIORITY, frame)` 升序，取第一名。

对应关系：

```text
Hard     = GRIPPER_TRANSITION          priority 0
Motion   = MOVE_TO_IDLE / IDLE_TO_MOVE  priority 1
Lower    = DIRECTION_CHANGE             priority 2
tie-break = 更早的 frame
```

这就是代码里的 **Hard > Motion > Direction**。Rotation / Action **不是** Candidate type，不能当 representative；它们只作为 `ROTATION_SUPPORT` / `ACTION_SUPPORT` 挂在 Motion/Direction candidate 上（`attach_supporting_evidence`）。

对 cluster：

```text
C0002 GRIPPER_TRANSITION @56   priority 0
C0003 DIRECTION_CHANGE   @57   priority 2
```

`_pick_representative` 必选 C0002。随后 `consolidate_candidates()`：

```text
event.frame          = 56
event.candidate_type = GRIPPER_TRANSITION
event.reason         = C0002.primary_reason
C0002 decision       = KEEP  ("hard boundary anchored as cluster representative")
C0003 decision       = MERGE_CONSOLIDATION
                       ("consolidated into demo_0-B0002 anchored at GRIPPER_TRANSITION@56")
```

窗口：`G1P2Config.boundary_consolidation_window = 8`（默认）。`_cluster_candidates` 以 **cluster 最早一帧** 为锚，后续 candidate 若 `frame - first.frame <= 8` 且 `_compatible_for_cluster` 通过，则并入。56 与 57 差 1 帧，进入同一 cluster。

同极性冲突的两个 Gripper、或相反的 `MOVE_TO_IDLE`/`IDLE_TO_MOVE` 不会并进同一 cluster。

---

## 6. 关键问题 5 — 三层语义状态

### Layer A — Final direct fields

```text
primary type  = GRIPPER_TRANSITION
primary frame = 56
```

只代表 **representative = gripper @56**。不是 cluster 的并集语义。

### Layer B — Lineage

```text
member_candidate_ids = demo_0-C0002|demo_0-C0003
```

保留。稳定、可 join。

### Layer C — Recoverable full semantics

Join Candidate 表可恢复：

```text
C0002 @56 GRIPPER_TRANSITION
C0003 @57 DIRECTION_CHANGE
```

Join Decision 表至少可恢复 type + frame + merge 原因，但 evidence / source_signal / polarity 仍以 Candidate 表为准。

```text
SEMANTIC_STATE = PRESERVED_BY_LINEAGE_ONLY
```

不是 `FULLY_PRESERVED_IN_FINAL`（Final 行没有 member type/frame）。  
不是 `LOST` / `PARTIALLY_LOST`（C0003 行仍完整存在，join key 仍在）。

---

## 7. 更多真实 MERGE_CONSOLIDATION

扫描范围：`outputs/g1_p2_boundary_audit/` 全部 6 个 smoke episode。  
Web bootstrap diagnostic 目录与之一一相同。

```text
MERGE finals              = 13
episodes with MERGE       = demo_0, demo_32, demo_179, demo_230, demo_242
demo_278                  = 无 MERGE_CONSOLIDATION
```

组合统计：

| Member type set | 次数 |
| --- | ---: |
| GRIPPER_TRANSITION + DIRECTION_CHANGE | 11 |
| GRIPPER + DIRECTION + IDLE_TO_MOVE | 1 |
| GRIPPER + MOVE_TO_IDLE + DIRECTION | 1 |
| **motion + direction（无 gripper）** | **0** |

当前 smoke **没有**「只有 motion + direction」的 consolidation。所有 MERGE 的 representative 都是 `GRIPPER_TRANSITION`。这与 `TYPE_PRIORITY[GRIPPER]=0` 一致：cluster 里一旦有夹爪，代表点必是夹爪。

抽查表（含 gripper+direction、以及仅有的两类三 member 组合）：

| Final Boundary | Representative | Member 1 | Member 2 | Final direct semantics | Recoverable via join |
| --- | --- | --- | --- | --- | --- |
| demo_0-B0002 | GRIPPER @56 OPEN_TO_CLOSE | C0002 @56 GRIPPER_TRANSITION | C0003 @57 DIRECTION_CHANGE | type=GRIPPER_TRANSITION frame=56 support=ACTION_SUPPORT | YES：C0003 仍为 DIRECTION_CHANGE @57 |
| demo_0-B0003 | GRIPPER @112 CLOSE_TO_OPEN | C0004 @112 GRIPPER_TRANSITION | C0005 @113 DIRECTION_CHANGE | type=GRIPPER_TRANSITION frame=112 support=ROTATION_SUPPORT\|ACTION_SUPPORT | YES |
| demo_32-B0002 | GRIPPER @53 OPEN_TO_CLOSE | C0004 @53 GRIPPER_TRANSITION | C0003 @49 DIRECTION_CHANGE | type=GRIPPER_TRANSITION frame=53 support=ACTION_SUPPORT | YES；direction 在 gripper **之前** 仍选 gripper |
| demo_179-B0001 | GRIPPER @4 CLOSE_TO_OPEN | C0001 @4 GRIPPER_TRANSITION | C0002 @9 DIRECTION_CHANGE | type=GRIPPER_TRANSITION frame=4 support=**empty** | YES；merged direction **未**写入 supporting_reasons |
| demo_179-B0002 | GRIPPER @71 OPEN_TO_CLOSE | C0003 @71 GRIPPER | C0004 @73 DIRECTION；C0005 @78 IDLE_TO_MOVE | type=GRIPPER_TRANSITION frame=71 support=ACTION_SUPPORT | YES：三 member 均可按 ID join |
| demo_230-B0002 | GRIPPER @54 OPEN_TO_CLOSE | C0004 @54 GRIPPER_TRANSITION | C0003 @52 DIRECTION_CHANGE | type=GRIPPER_TRANSITION frame=54 support=ACTION_SUPPORT | YES |
| demo_242-B0009 | GRIPPER @146 OPEN_TO_CLOSE | C0011 @146 GRIPPER | C0012 @147 MOVE_TO_IDLE；C0013 @152 DIRECTION | type=GRIPPER_TRANSITION frame=146 support=ACTION_SUPPORT | YES；MOVE_TO_IDLE 与 DIRECTION 都不进入 Final.candidate_type |

`demo_242-B0002` 等 DIRECTION-only Final 是 **单 member、无 MERGE**，不在本表。它们证明：没有 gripper 抢代表点时，DIRECTION 可以自己成为 Final type；一旦和 gripper 进同一 8 帧 cluster，Final type 就会变成 gripper。

---

## 8. 结论

当前 Final schema 对合并语义的状态是：

```text
SEMANTIC_STATE = PRESERVED_BY_LINEAGE_ONLY
```

- Final 直接字段 = **只剩代表候选** 的 type / frame / reason / polarity。
- Member 身份 = **只保留 ID 列表**。
- Member 的 type@frame 以及证据 = **完整留在 Candidate 表**，join 可恢复。
- `supporting_reasons` **不是** member-type 摘要；不能用来推断「里面有没有 DIRECTION_CHANGE」。
- Web Final 行 **不展开** member 语义。

对用户关心的案例：

```text
B0002 @56 后续仍能知道 C0003 = DIRECTION_CHANGE @57
方式 = member_candidate_ids 中的 demo_0-C0003
        JOIN candidate_boundaries.csv
        （或 JOIN boundary_decisions.csv 的 candidate_id / target_boundary_id）
不是 = 读 Final.candidate_type / Final.frame / Final.supporting_reasons
```

---

## 9. OPTIONAL_FUTURE_ENRICHMENT

本轮不实施。若以后要让 Final 行或 P2 卡片不 join 也能看见 member 语义，才需要另开任务讨论例如：

```text
merged_candidate_types
member_frames
member_summary = "C0002@56 GRIPPER_TRANSITION | C0003@57 DIRECTION_CHANGE"
```

或 Web 在渲染 Final 行时对 `member_candidate_ids` 做只读 join。这些都会改变展示或 schema，不属于本轮。
