# Project 2 G1 Final Boundary Semantic Materialization Result

```text
DATE = 2026-09-17
CONTRACT = P2_G1_AUDIT_FOLDER_V1
FINAL_BOUNDARY_SEMANTICS = MATERIALIZED_V1
CHILD_RUN_ID = g1_exploratory_audit_20260917_141541_fe251439
PARENT_RUN_ID = g1_exploratory_audit_20260916_214523_1ba11d9d
DETECTOR_LOGIC_MODIFIED = NO
CONTRACT_VERSION_BUMPED = NO
OLD_RUN_FILES_MODIFIED = NO
HUMAN_REVIEW_MIGRATED = NO
```

目标状态：

```text
PRESERVED_BY_LINEAGE_ONLY
↓
PRESERVED_AND_MATERIALIZED
```

---

## PHASE A — Persisted Schema

### 权威读取

- Google Drive Frozen：`Project2_G1_Human_Audit_Web_Design_FROZEN_v1_20260916.md`
  - `run_meta.json` 是 **至少包含** 字段清单；允许 additive metadata。
  - 禁止 bump `P2_G1_AUDIT_FOLDER_V1` → V2。
- 本地审计：`0-doc/80-audit-local/Project2_G1_Final_Boundary_Merged_Semantics_Audit_20260917.md`
  - 进入本轮前：`SEMANTIC_STATE = PRESERVED_BY_LINEAGE_ONLY`
- 真实代码：
  - `src/project2_g1/boundary_engine.py`
  - `src/project2_g1/boundary_io.py`
  - `src/project2_g1/final_semantics.py`（本轮新增）
  - `src/project2_g1_audit_web/contract.py`
  - `src/project2_g1_audit_web/materialize_final_semantics.py`
  - writer：`write_episode_audit_tables()` 写出 `final_boundaries.csv`

### 语义分层

Representative Boundary（切分点，含义不变）：

```text
boundary_id / frame / candidate_type / reason / polarity
```

Merged Evidence（新增物化字段）：

```text
representative_candidate_id
member_candidate_ids
member_candidate_types
member_candidate_frames
member_candidate_count
```

`candidate_type` 仍只表示 Representative Type。`frame` 仍只表示唯一切分 frame。

`supporting_reasons` 仍是 evidence tag，不把 member type 塞进去。

### 排序规则

```text
frame ASC, then candidate_id ASC
```

`representative_candidate_id` 来自真实 `_pick_representative()` 返回对象，不是 sorted list[0]。

### 一致性校验（fail-fast，禁止 silent repair）

- member ID ∈ Candidate 表
- materialized type/frame == Candidate 表
- `len(ids) == len(types) == len(frames) == member_candidate_count`
- representative ∈ members
- representative.frame == final.frame
- representative.type == final.candidate_type

Validator 区分：

```text
LEGACY / PRE-MATERIALIZATION  → FINAL_MEMBER_SEMANTICS = LINEAGE_ONLY
MATERIALIZED FINAL SCHEMA     → FINAL_MEMBER_SEMANTICS = MATERIALIZED
```

旧 Run 可读，不补列。

`run_meta` additive：

```text
final_boundary_semantics = MATERIALIZED_V1
schema_materialization = FINAL_BOUNDARY_MEMBER_SEMANTICS_V1
```

`contract_version` 仍为 `P2_G1_AUDIT_FOLDER_V1`。

### Child Run

从 parent copy 重建 immutable folder：Candidate / Decision / Segment / Video / Plot 不重算。只改 `final_boundaries.csv` 列与 additive metadata。随后 `validate` + `register`。Parent 未 disable。

---

## PHASE B — Web Integration

P2 Final 行直接显示：

```text
Primary｜代表事件
<code> @<final frame>

Merged Evidence｜合并证据   （仅 member_count > 1）
• type @frame
```

- MATERIALIZED Run：读 Final 物化字段，不再为了基础语义 join Candidate。
- LINEAGE_ONLY Run：view 层临时 join Candidate（方案 A），并标注 `Legacy Run｜成员语义由 Candidate 表 join 展示`。
- Merged Evidence 只读；人工审核仍只有 VALID / REDUNDANT / MISALIGNED。
- P1 layout、Diagnostics 表、Review SQLite schema、Review key `(run_id, episode_id, boundary_id)` 均未改。
- 未迁移 parent Human Review 到 child。

中文展示沿用 `vocab.py`：`CODE｜中文`。未知类型：`UNKNOWN_CODE::<raw>`，不静默隐藏。

---

## Real verification

### demo_0-B0002（child）

```text
frame = 56
candidate_type = GRIPPER_TRANSITION
representative_candidate_id = demo_0-C0002
member_candidate_ids = demo_0-C0002|demo_0-C0003
member_candidate_types = GRIPPER_TRANSITION|DIRECTION_CHANGE
member_candidate_frames = 56|57
member_candidate_count = 2
supporting_reasons = ACTION_SUPPORT
```

### 3-member 真实组合

```text
demo_179-B0002 @71 GRIPPER_TRANSITION
members = GRIPPER_TRANSITION@71 | DIRECTION_CHANGE@73 | IDLE_TO_MOVE@78

demo_242-B0009 @146 GRIPPER_TRANSITION
members = GRIPPER_TRANSITION@146 | MOVE_TO_IDLE@147 | DIRECTION_CHANGE@152
```

### representative ≠ first member（真实）

```text
demo_179-B0003
members = C0006 DIRECTION_CHANGE @141 | C0007 GRIPPER_TRANSITION @144
representative_candidate_id = demo_179-C0007
frame = 144
```

### Immutability fingerprints

```text
Legacy  before = 9f22745ca60b6840d6a1844f35cfb3a93dbd229b72d5b4d5ee141312ed16d067
Legacy  after  = 9f22745ca60b6840d6a1844f35cfb3a93dbd229b72d5b4d5ee141312ed16d067

Parent  before = da1bc0abee824c0ae63b053fbceea53996373ba87e2d063fd8e223cac2e3c4d6
Parent  after  = da1bc0abee824c0ae63b053fbceea53996373ba87e2d063fd8e223cac2e3c4d6
```

Smoke GET 后 SQLite：

```text
signal_review_history = 6
predicted_boundary_review_history = 3  (全部属于 parent run)
human_added_boundary_history = 0
episode_note_history = 0
child run predicted reviews = 0
```

---

## Tests

```text
test_g1_final_semantics.py     13 PASS
test_g1_p2_boundary_engine.py  15 PASS
test_g1_audit_web*.py          42 PASS
```

---

## Browser / live HTTP trial

服务：`http://127.0.0.1:8766/`

无独立浏览器自动化工具；对已重启的 8766 进程做了真实 HTTP GET：

- Home：parent 与 child 同时可见
- Child `demo_0` P2：B0002 Primary GRIPPER_TRANSITION @56 + Merged @56/@57；B0001 无 Merged Evidence
- Child `demo_179` P2：B0002 三成员 GRIPPER / DIRECTION / IDLE_TO_MOVE
- Child `demo_242` P2：B0009 三成员 GRIPPER / MOVE_TO_IDLE / DIRECTION
- Parent `demo_0` P2：仍可打开，join 展示 DIRECTION_CHANGE @57，并显示 Legacy 说明
- P1 layout / Save / Save & Next / Diagnostics 仍在
- 未 POST Review

---

## Explicit stop

未调整 threshold、未重新 Calibration、未进入 G1-P3、未改 Review labels、未导出 Human Calibration。

等待 Design Owner 打开 child run 确认展示。
