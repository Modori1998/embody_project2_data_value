# Project 2 G1 Audit Web — Local Structure Audit

```text
DATE = 2026-09-16
MODE = READ / INSPECT / REPORT ONLY
DRAFT_FOUND = NO
AUTHORITY_ORDER = Engineering Master > Roadmap > Readable Design > Web Draft
```

本文件只记录本地真实结构。不修改 G1-P1 / G1-P2、CSV / JSON、Audit Package、M07 Web、schema、threshold。不生成新 run。

---

## 1. Fact Sources Read

### 1.1 Project 2 权威文档

| 优先级 | 文件 | 状态 |
| --- | --- | --- |
| 1 | `C:\Users\95611\embody\4-Project2_data_value\0-doc\Project_2_Engineering_Design_Master_v1_20260914.md` | READ |
| 2 | `C:\Users\95611\embody\4-Project2_data_value\0-doc\Project2_Development_Roadmap_and_Design_Gate_Plan_v1_20260914.md` | READ |
| 3 | `C:\Users\95611\embody\4-Project2_data_value\0-doc\02_robot_demonstration_mining_autolabel_design.md` | READ |
| 4 | `Project2_G1_Human_Audit_Web_Design_DRAFT_v0_1_20260916.md` | **DRAFT_FOUND = NO** |

本地 `0-doc\` 仅有上述三份权威 MD。全盘 `embody` 与 Google Drive `title contains 'Project2_G1'` 均未找到该 Draft。Drive 上同日存在的是 Project 1 文档 `M07_Detector_Iteration_Human_Audit_Web_Design_FROZEN_v1_20260916.md`，不是 G1 Web Draft。因此本审计不以任何 Web Draft 覆盖 Frozen G1 Design。

### 1.2 G1-P1 / G1-P2 输出与代码

读取了真实目录（含被 ignore 的 `video.mp4` / PNG）、全部 CSV / JSON、以及：

```text
scripts/run_g1_p1_signal_audit.py
scripts/run_g1_p2_boundary_audit.py
src/project2_g1/paths.py
src/project2_g1/boundary_io.py
src/project2_g1/boundary_engine.py
src/project2_g1/boundary_config.py
src/project2_g1/config.py
src/project2_g1/source.py
src/project2_g1/video.py
src/project2_g1/plot.py
src/project2_g1/report.py
configs/g1_p1_signal_contract.json
configs/g1_p2_exploratory_segmentation.json
```

媒体探针使用 Project 1 仓库内 `ffprobe.exe`（只读，未改视频）。

### 1.3 M07 Web 代码 / contract / registry / DB

```text
M07_WEB_ROOT = C:\Users\95611\embody\2-Project1_dataset\scr
BACKEND = FastAPI create_app in project1_benchmark/m07_audit_web_app.py
FRONTEND = Jinja2 HTML/CSS, no SPA JS bundle
DATABASE = result/m07_audit_web/m07_audit_web.sqlite
REGISTRY = result/m07_audit_web/audit_run_registry.json
CONTRACT = project1_benchmark/m07_audit_contract.py  CONTRACT_VERSION=M07_AUDIT_FOLDER_V1_1
```

本地 SQLite 已建表，但 `owner_run_paths` / `human_semantic_reviews` / `detector_run_reviews` 行数均为 0。Registry 有 1 条 `reversal_v2.1` Formal run。

---

## 2. G1-P1 Real Structure

### 2.1 真实目录树

```text
outputs/g1_p1_signal_audit/
  episode_manifest.csv                         (1097 B)
  g1_p1_run_summary.json                       (669 B)
  g1_p1_signal_contract_audit_report.md        (12420 B)
  demo_0/
    signal_plot.png                            (660134 B)
    video.mp4                                  (153545 B)
  demo_32/
    signal_plot.png                            (641606 B)
    video.mp4                                  (122452 B)
  demo_179/
    signal_plot.png                            (666217 B)
    video.mp4                                  (172110 B)
  demo_278/
    signal_plot.png                            (736573 B)
    video.mp4                                  (253609 B)
```

P1 smoke 仅 4 个 episode：`demo_0 / demo_32 / demo_179 / demo_278`。无 `demo_242` / `demo_230`。无 codebook、无 human review template、无 candidate/boundary CSV。

### 2.2 episode_manifest.csv

```text
absolute path =
C:\Users\95611\embody\4-Project2_data_value\outputs\g1_p1_signal_audit\episode_manifest.csv
n_rows = 4
storage = UTF-8 CSV text (无 typed schema 文件)
```

| column | logical dtype | nullable in this file | unique |
| --- | --- | --- | --- |
| `episode_id` | string | no | 4/4 |
| `native_episode_key` | string | no | 4/4 |
| `length` | int-as-text | no | 4/4 |
| `video_path` | absolute path string | no | 4/4 |
| `signal_plot_path` | absolute path string | no | 4/4 |
| `weak_reference` | enum-like {BETTER, OKAY} | no | 2/4 |
| `split` | enum-like {TRAIN} | no | 1/4 |
| `alignment` | enum-like {PASS} | no | 1/4 |
| `nan_inf` | enum-like {PASS} | no | 1/4 |
| `issues` | JSON-in-CSV string | no (`"[""none""]"`) | 1/4 |

Sample rows:

```text
data/demo_0,demo_0,118,<abs>\demo_0\video.mp4,<abs>\demo_0\signal_plot.png,BETTER,TRAIN,PASS,PASS,"[""none""]"
data/demo_32,demo_32,98,... BETTER,TRAIN,PASS,PASS
data/demo_278,demo_278,206,... OKAY,TRAIN,PASS,PASS
```

用户点名字段核对：

| 字段 | 现状 |
| --- | --- |
| `episode_id` | EXISTS = `data/demo_N` |
| `quality_group` | **MISSING**（P1 用 `weak_reference`） |
| `length` | EXISTS |
| `video_path` | EXISTS（绝对路径） |
| `signal_plot_path` | EXISTS（绝对路径） |
| `signal_contract_version` | **MISSING** |
| `signal_version` | **MISSING** |
| `code_hash` | **MISSING**（全 `src/project2_g1` 无 hashlib / code_hash） |
| dataset / source identity | **PARTIAL**：manifest 仅有 `split=TRAIN`；dataset 路径只在 report / `g1_p1_run_summary.json` 上游 discovery，不在 CSV |

Unique key candidate: `episode_id`（亦等价于 `native_episode_key`）。

### 2.3 Media structure

每个 episode 目录固定两件媒体：`video.mp4` + `signal_plot.png`。视频由 `src/project2_g1/video.py::render_episode_audit_video` 用 OpenCV `mp4v` 从 STATE_t 新渲染，不是上游预编码 RGB。Plot 由 `plot_episode_signals(..., candidate_boundaries=None, suppressed_boundaries=None, final_boundaries=None)` 生成，无 boundary overlay。

### 2.4 P1 stable identity / reuse

```text
P1_REVIEW_REUSE_READY = PARTIAL
```

事实依据：

1. `episode_id` 来自 P1 adapter `source_episode_id=f"data/{native_key}"`（`robomimic_adapter.py`），对同一 HDF5 demo 稳定。判定：**SOURCE_STABLE**。
2. Formal signal 由 `compute_formal_signals(episode, p1_config)` 计算；P2 runner 明确不改写 P1 formula（`run_g1_p2_boundary_audit.py` unknowns: `UPSTREAM_SIGNAL_ISSUE = NO`）。Signal 与 P2 segmentation config 代码路径分离。
3. **没有** `signal_contract_version`。`configs/g1_p1_signal_contract.json` 有 `phase/g1_design/...`，但无 version/hash 字段写入 manifest。
4. **没有** signal code hash。下一轮若改 `signals.py` 窗口/公式，Web 无法从当前 package 证明 P1 review 仍有效。
5. 当前也没有任何已保存的 P1 Human Signal Review；`G1_P1_HUMAN_VISUAL_REVIEW = DEFERRED`。可复用的是 identity + 媒体，不是已完成的 review 记录。

结论：同一 Episode 在下一轮只改 P2 threshold/config 时，P1 `episode_id` / 视频字节（若未重渲）可以概念上复用；但缺少 contract version / code hash，不能称为安全复用。

---

## 3. G1-P2 Real Structure

### 3.1 真实目录树

```text
outputs/g1_p2_boundary_audit/
  episode_manifest.csv                         (1767 B)
  exploratory_config.json                      (7672 B)
  g1_p2_boundary_engine_audit_report.md        (13956 B)
  g1_p2_run_summary.json                       (1142 B)
  human_boundary_review_codebook.json          (713 B)
  human_boundary_review_template.csv           (3048 B)
  demo_0/
    boundary_decisions.csv                     (752 B)
    candidate_boundaries.csv                   (1097 B)
    final_boundaries.csv                       (746 B)
    segment_manifest.csv                       (1181 B)
    signal_boundary_plot.png                   (770192 B)
    video.mp4                                  (153545 B)
  demo_32/   (same 6 files)
  demo_179/  (same 6 files)
  demo_230/  (same 6 files)
  demo_242/  (same 6 files)
  demo_278/  (same 6 files)
```

6 个 smoke episode：`demo_0, demo_32, demo_179, demo_278, demo_242, demo_230`。每个 episode 都有用户点名的 4 个 CSV + `video.mp4` + `signal_boundary_plot.png`。根目录另有 codebook / template / exploratory_config / report / summary。

`g1_p2_run_summary.json` 关键字段：

```text
G1_P2_STATUS = PASS_READY_FOR_HUMAN_BOUNDARY_REVIEW
G1_P2_SEGMENTATION_STATUS = EXPLORATORY_ONLY
threshold_frozen = false
human_gt_calibration = false
g1_p3_started = false
```

### 3.2 全量 CSV schema（storage = UTF-8 text）

下列 dtype 是从单元格推断的逻辑类型，不是独立 schema 文件。

#### A. `episode_manifest.csv`

```text
path = ...\outputs\g1_p2_boundary_audit\episode_manifest.csv
n_rows = 6
unique key candidate = episode_id
path columns = video_path, plot_path (均为绝对路径)
```

| column | logical dtype | nullable here |
| --- | --- | --- |
| `episode_id` | string `data/demo_N` | no |
| `native_episode_key` | string `demo_N` | no |
| `quality_group` | enum-like {BETTER, OKAY, WORSE} | no |
| `length` | int | no |
| `candidate_count` | int | no |
| `suppressed_count` | int | no |
| `final_boundary_count` | int | no |
| `segment_count` | int | no |
| `video_path` | abs path | no |
| `plot_path` | abs path | no |
| `review_required` | bool-as-text {True} | no（本包 6/6 True） |
| `short_segment_count` | int | no |
| `long_segment_count` | int | no（本包全 0） |
| `alignment` | {PASS} | no |
| `nan_inf` | {PASS} | no |

Sample:

```text
data/demo_0,demo_0,BETTER,118,5,2,3,4,...\demo_0\video.mp4,...\signal_boundary_plot.png,True,2,0,PASS,PASS
data/demo_278,demo_278,OKAY,206,9,0,9,10,...,True,2,0,PASS,PASS
data/demo_242,demo_242,WORSE,232,15,5,10,11,...,True,1,0,PASS,PASS
```

P1 有而 P2 没有：`weak_reference`, `split`, `signal_plot_path`, `issues`。  
P2 有而 P1 没有：`quality_group` 及全部 boundary/segment 计数。

#### B. `candidate_boundaries.csv`（每 episode 一份）

Smoke 合计 48 rows。列与 `boundary_io.write_episode_audit_tables` 完全一致。

| 用户点名 | 真实列名 | 现状 |
| --- | --- | --- |
| `candidate_id` | `candidate_id` | EXISTS |
| `episode_id` | `episode_id` | EXISTS |
| `frame` | `frame` | EXISTS int |
| `candidate_type` | `candidate_type` | EXISTS |
| `primary_reason` | `primary_reason` | EXISTS |
| `supporting_reasons` | `supporting_reasons` | EXISTS；`\|` 拼接；常空 |
| `evidence` | `evidence_value` | EXISTS（列名不是 `evidence`） |
| persistence status | `persistence_status` | EXISTS；本包全部 `PERSISTENT` |
| `config_version` | `config_version` | EXISTS = `g1_p2_exploratory_segmentation.v0` |

额外列：`source_signal`, `polarity`。无 `run_id`。

Unique key candidate: `candidate_id`（本包全局唯一；生成规则见 §5）。

本包实际 `candidate_type`：

```text
DIRECTION_CHANGE = 27
GRIPPER_TRANSITION = 18
IDLE_TO_MOVE = 2
MOVE_TO_IDLE = 1
```

`primary_reason`：

```text
PERSISTENT_DIRECTION_CHANGE
PERSISTENT_GRIPPER_CLOSE_TO_OPEN
PERSISTENT_GRIPPER_OPEN_TO_CLOSE
PERSISTENT_IDLE_TO_MOVE
PERSISTENT_MOVE_TO_IDLE
```

`supporting_reasons` 出现过：`ACTION_SUPPORT`, `ROTATION_SUPPORT`, 及其 `\|` 组合。空字符串常见。

`polarity`：`CLOSE_TO_OPEN / OPEN_TO_CLOSE / DIRECTION_CHANGE / IDLE_TO_MOVE / MOVE_TO_IDLE`。

Sample `demo_0`：

```text
data/demo_0,demo_0-C0001,4,GRIPPER_TRANSITION,PERSISTENT_GRIPPER_CLOSE_TO_OPEN,,0.00806...,PERSISTENT,gripper_aperture,g1_p2_exploratory_segmentation.v0,CLOSE_TO_OPEN
data/demo_0,demo_0-C0003,57,DIRECTION_CHANGE,PERSISTENT_DIRECTION_CHANGE,ACTION_SUPPORT,2.356...,PERSISTENT,direction_change_evidence,...,DIRECTION_CHANGE
```

Sample `demo_242` 含全部四类 candidate，见该文件 C0001–C0015。

#### C. `boundary_decisions.csv`

列：

```text
episode_id, candidate_id, frame, candidate_type, decision, reason, target_boundary_id
```

Unique key candidate: `candidate_id`。`target_boundary_id` 本包无空值。

**代码 taxonomy**（`boundary_engine.py` / `boundary_io.DECISION_ORDER`）：

```text
KEEP
RETAIN_HARD
SUPPRESS_DEBOUNCE
MERGE_CONSOLIDATION
SUPPRESS_SHORT_PAUSE
MERGE_LEFT
MERGE_RIGHT
REVIEW_REQUIRED
```

**本 smoke 实际出现过的 decision（不是设计枚举）**：

```text
KEEP                 = 21
MERGE_CONSOLIDATION  = 15
RETAIN_HARD          = 10
MERGE_LEFT           = 1    (demo_230-C0006 → demo_230-B0004)
MERGE_RIGHT          = 1    (demo_242-C0014 → demo_242-B0010)
```

未在本包出现：`SUPPRESS_DEBOUNCE`, `SUPPRESS_SHORT_PAUSE`, `REVIEW_REQUIRED`。  
P2 report 也写明：pause bridging 未在 6-episode smoke 触发。

`reason` 是自由文本，不是 enum。本包见过：

```text
hard boundary protected from ordinary length-guard deletion
hard boundary anchored as cluster representative
cluster representative
consolidated into {B} anchored at {TYPE}@{frame}
short segment {S} merged toward more compatible left/right neighbor
```

关系字段：

- consolidation / merge 关系 = `decision` + `target_boundary_id`
- 无单独 `suppression_reason` 列；抑制/合并原因写在 `reason`
- 无 `suppressed` boolean 列

重要事实：`target_boundary_id` 可以指向**不在** `final_boundaries.csv` 的 ID。

```text
demo_242-C0014 MERGE_RIGHT → demo_242-B0010   (B0010 不在 final_boundaries)
demo_230-C0006 MERGE_LEFT  → demo_230-B0004   (B0004 不在 final_boundaries)
```

原因：`boundary_id` 在 consolidation 时按 cluster 顺序分配；随后 length-guard merge 把该 event `active=False`，`final_events` 过滤掉它。Template 只写 active final events，因此 `demo_242` 从 B0009 跳到 B0011。

#### D. `final_boundaries.csv`

真实列名是 `boundary_id`，**不是** `final_boundary_id`。

| 用户点名 | 真实列 | 现状 |
| --- | --- | --- |
| `final_boundary_id` | `boundary_id` | EXISTS under different name |
| `frame` | `frame` | EXISTS |
| `reason` | `reason` | EXISTS（= representative primary_reason） |
| supporting evidence | `supporting_reasons` | EXISTS；可空 |
| source candidate ids | `member_candidate_ids` | EXISTS；`\|` 拼接 |
| `review_required` | **MISSING as boolean**；近似字段 = `review_flags` | 本包值为空或 `REVIEW_REQUIRED` |

额外列：`episode_id, candidate_type, polarity, config_version, segmentation_version`。

Smoke 合计 31 条 final boundaries。Unique key candidate: `boundary_id`（本 run 内唯一；跨 config **不稳定**，见 §5）。

Sample `demo_0`：

```text
demo_0-B0001,data/demo_0,4,GRIPPER_TRANSITION,PERSISTENT_GRIPPER_CLOSE_TO_OPEN,demo_0-C0001,,REVIEW_REQUIRED,CLOSE_TO_OPEN,g1_p2_exploratory_segmentation.v0,G1-P2-EXPLORATORY-v0
demo_0-B0002,...,56,...,demo_0-C0002|demo_0-C0003,ACTION_SUPPORT,,OPEN_TO_CLOSE,...
```

`review_flags` 本包仅见 `REVIEW_REQUIRED`（10 次）。空字符串 = 无 flag。

#### E. `segment_manifest.csv`

| 用户点名 | 真实列 | 现状 |
| --- | --- | --- |
| `segment_id` | `segment_id` | EXISTS |
| `start_frame` | `start_frame` | EXISTS inclusive |
| `end_frame` | `end_frame` | EXISTS inclusive |
| boundary relation | `left_boundary_id` / `right_boundary_id` + `*_reason` | EXISTS |
| flags | `short_segment_flag`, `long_segment_flag`, `review_required`, `review_flags` | EXISTS |
| `segmentation_version` | `segmentation_version` | EXISTS = `G1-P2-EXPLORATORY-v0` |
| `config_version` | `config_version` | EXISTS = `g1_p2_exploratory_segmentation.v0` |

额外：`source_episode_id, duration_frames, duration_sec, segment_label=NONE, semantic_phase=NONE`。

Smoke 合计 37 segments。`review_flags` 本包仅见 `SHORT_SEGMENT_CANDIDATE`（10 次）。`long_segment_flag` 全 False。`left/right_boundary_id` 可取 `EPISODE_START` / `EPISODE_END`。

Sample `demo_0-S0001`：`start=0,end=3,duration=4, left=EPISODE_START, right=demo_0-B0001, short=True`。

#### F. `human_boundary_review_template.csv`

见 §4。

### 3.3 JSON

`exploratory_config.json`：P2 runner 把 `p2_config.raw` dump 到固定路径。含 `config_version`, `segmentation_version`, 全部 exploratory parameters。无 `run_id` / `config_hash` / `created_at` / `parent_run_id`。

`human_boundary_review_codebook.json`：见 §4。

---

## 4. Human Review Contract

### 4.1 Template schema

```text
path = ...\outputs\g1_p2_boundary_audit\human_boundary_review_template.csv
n_rows = 49
fields (boundary_io.REVIEW_TEMPLATE_FIELDS) =
  episode_id
  predicted_boundary_id
  predicted_frame
  human_review
  corrected_frame
  human_added_frame
  reason_code
  note
  reviewer
  review_version
```

逻辑类型：全部 string。`predicted_frame` 在 predicted 行是 int-as-text。

Empty counts（本文件）：

```text
predicted_boundary_id = 18   (每 episode 3 条 MISSED 空行)
predicted_frame       = 18
human_review          = 49   (全部未填)
corrected_frame       = 49
human_added_frame     = 49
reason_code           = 49
note                  = 31   (18 条空行带固定英文提示)
reviewer              = 49
review_version        = 49
```

Unique key：**NOT_DEFINED**。Predicted 行可用 `(episode_id, predicted_boundary_id)`。空 MISSED 行同一 `episode_id` 重复 3 次，无 row_id。

无 `episode_note` / `blocking_issue` 列。注释列名是 `note`，不是 `comment`。

### 4.2 Review 主枚举

Codebook 与 `boundary_io.HUMAN_REVIEW_VALUES`：

```text
VALID
REDUNDANT
MISALIGNED
MISSED_BOUNDARY
```

无其他值。Template 当前全部为空，所以**没有真实填过的 human_review**。

### 4.3 reason_code（真实 codebook，按前缀分类）

REDUNDANT 可选值：

```text
REDUNDANT_SHORT_PAUSE
REDUNDANT_DIRECTION_JITTER
REDUNDANT_ROTATION
REDUNDANT_ACTION_JITTER
```

MISALIGNED 可选值：

```text
MISALIGNED_GRIPPER
MISALIGNED_MOTION_CHANGE
```

MISSED_BOUNDARY 可选值：

```text
MISSED_GRIPPER_TRANSITION
MISSED_MOVE_STOP
MISSED_STOP_MOVE
MISSED_DIRECTION_CHANGE
```

其他通用值：

```text
OTHER
```

Codebook 是否包含：

| 项 | 现状 |
| --- | --- |
| 中文解释 | **NO**（只有 code list） |
| 英文解释 | **PARTIAL**：仅一条总 `note`，无 per-code 英文 |
| required / optional 条件 | **PARTIAL**：总 note 写 “MISALIGNED requires corrected_frame”；无 JSON required schema |

### 4.4 Conditional fields

| 规则 | 现状 |
| --- | --- |
| MISALIGNED → `corrected_frame` | 仅 codebook `note` 自然语言；**NOT_DEFINED** as schema/enforced required |
| MISSED_BOUNDARY → `human_added_frame` | 提供 3 条空行；**NOT_DEFINED** 何时必填 |
| REDUNDANT → `reason_code` required | **NOT_DEFINED** |
| `note` / comment optional | 字段存在；required 逻辑 **NOT_DEFINED** |
| `human_review` required to save | **NOT_DEFINED**（无 Web / 无 validator） |
| `reviewer` / `review_version` | 列存在，全空，规则 **NOT_DEFINED** |

Master G1-D 设计要求 MISALIGNED 必须记 `corrected_frame`，且所有人工标签记 `reason_code`。那是 Frozen Design，不是当前 template 的机器可执行 required 逻辑。本审计不自行补规则。

### 4.5 固定标签中文（仅 display 建议；未改 codebook）

当前 codebook / CSV **没有任何中文字段**。下列是网页 display text 建议，stored code 保持英文。

| Code | 当前是否有中文 | 建议网页中文 |
| --- | --- | --- |
| VALID | NO | 有效边界 |
| REDUNDANT | NO | 冗余边界 |
| MISALIGNED | NO | 边界位置偏移 |
| MISSED_BOUNDARY | NO | 漏检边界 |
| REDUNDANT_SHORT_PAUSE | NO | 短暂停造成的冗余切分 |
| REDUNDANT_DIRECTION_JITTER | NO | 方向抖动造成的冗余切分 |
| REDUNDANT_ROTATION | NO | 旋转证据造成的冗余切分 |
| REDUNDANT_ACTION_JITTER | NO | 动作指令抖动造成的冗余切分 |
| MISALIGNED_GRIPPER | NO | 夹爪边界位置偏移 |
| MISALIGNED_MOTION_CHANGE | NO | 运动变化边界位置偏移 |
| MISSED_GRIPPER_TRANSITION | NO | 漏检夹爪切换 |
| MISSED_MOVE_STOP | NO | 漏检运动→静止 |
| MISSED_STOP_MOVE | NO | 漏检静止→运动 |
| MISSED_DIRECTION_CHANGE | NO | 漏检主方向变化 |
| OTHER | NO | 其他 |
| GRIPPER_TRANSITION | NO | 夹爪切换 |
| MOVE_TO_IDLE | NO | 运动→静止 |
| IDLE_TO_MOVE | NO | 静止→运动 |
| DIRECTION_CHANGE | NO | 主方向变化 |
| KEEP | NO | 保留 |
| RETAIN_HARD | NO | 强边界保护保留 |
| MERGE_CONSOLIDATION | NO | 合并为同一边界事件 |
| MERGE_LEFT | NO | 向左邻合并 |
| MERGE_RIGHT | NO | 向右邻合并 |
| SUPPRESS_DEBOUNCE | NO | 去抖抑制 |
| SUPPRESS_SHORT_PAUSE | NO | 短暂停桥接抑制 |
| REVIEW_REQUIRED | NO | 需要人工复核 |
| PERSISTENT | NO | 已持续确认 |
| SHORT_SEGMENT_CANDIDATE | NO | 短片段候选 |
| EPISODE_START | NO | 片段开始（Episode 起点） |
| EPISODE_END | NO | 片段结束（Episode 终点） |

---

## 5. Identity / Version Audit

### 5.1 Identity 判定

| identity | 判定 | 生成位置 | 规则 |
| --- | --- | --- | --- |
| `episode_id` | **SOURCE_STABLE** | P1 `RoboMimicHDF5SourceAdapter` → `data/{demo_N}` | HDF5 native key；与 config/threshold 无关 |
| `native_episode_key` | **SOURCE_STABLE** | 同上 `demo_N` | 目录名 / ID 前缀 |
| `candidate_id` | **RUN_STABLE_ONLY** | `boundary_engine._assign_ids` | `{native}-C{index:04d}`；index = 按 `(frame, TYPE_PRIORITY)` 排序后的 1-based 序号 |
| `boundary_id`（即 predicted / final id） | **RUN_STABLE_ONLY** | `consolidate_candidates` | `{native}-B{index:04d}`；index = consolidation cluster 顺序。随后 deactivate 不回收编号 → 出现 B0010 缺口 |
| `segment_id` | **RUN_STABLE_ONLY** | `build` segments 循环 | `{native}-S{index:04d}`；index = 切分后 segment 顺序 |
| `predicted_boundary_id` in template | 复制 `event.boundary_id` | `boundary_io.build_human_review_rows` | 只含 `final_events`（active） |

不是 RANDOM。也不是单纯 DERIVED_FROM_FRAME：同一 frame 可有多个 candidate；ID 依赖检测集合与排序，不是 `episode+frame` 函数。

同一 Episode 用不同 threshold/config rerun：

```text
KEEP     = episode_id, native_episode_key
CHANGE   = candidate_id, boundary_id, segment_id
          （候选增减会平移后续 C/B/S 序号）
UNKNOWN  = 若恰好候选集合与顺序不变，C/B/S 会碰巧相同；代码不保证
```

因此 **predicted boundary 不能当作跨 Config 的 stable case identity**。Web 必须用 run-specific key，例如：

```text
(run_id, episode_id, boundary_id)
或 (run_id, episode_id, predicted_frame, candidate_type, member_candidate_ids)
```

`episode_id` **可以**直接映射 M07 `case_id` 的“源稳定、禁止掺 run_id”模式。

### 5.2 Config / version / run identity

| 字段 | 判定 | 来源 |
| --- | --- | --- |
| `run_id` | **MISSING** | G1 全树无此字段 |
| `run_stage` | **MISSING** | |
| `config_version` | **EXISTS** | P2 config JSON / `G1P2Config.config_version` / 写入 candidate、final、segment CSV。当前字面量 `g1_p2_exploratory_segmentation.v0`。改 threshold 若不改这个字符串，version 不会变 |
| `config_hash` | **MISSING** | |
| `segmentation_version` | **EXISTS** | `G1-P2-EXPLORATORY-v0`；同样是常量，不随参数自动变 |
| `signal_contract_version` | **MISSING** | P1 config 无 version 键 |
| `created_at` | **MISSING** | 无 run_meta；不可用 mtime |
| `parent_run_id` | **MISSING** | |

`g1_p2_run_summary.json` 也没有 run_id / hash / created_at。

---

## 6. Rerun Behavior

```text
CURRENT_RERUN_BEHAVIOR = A. 覆盖 outputs\g1_p2_boundary_audit
```

代码证据（`scripts/run_g1_p2_boundary_audit.py`）：

1. `--output-dir` 默认 `paths.G1_P2_OUTPUT_ROOT` = `PROJECT2_ROOT/outputs/g1_p2_boundary_audit`。
2. `output_dir.mkdir(parents=True, exist_ok=True)` — 不 fail-if-exists。
3. 直接写 `exploratory_config.json`、`episode_manifest.csv`、`human_boundary_review_template.csv`、`human_boundary_review_codebook.json`、`g1_p2_boundary_engine_audit_report.md`、`g1_p2_run_summary.json`。
4. `write_episode_audit_tables` / `plot_episode_signals` / `_ensure_video` 写入同一 `output_dir / native_episode_key`。
5. 无版本子目录、无 run_id 目录、无 backup。
6. `_ensure_video`：若目标已存在且 `--skip-video` → 复用；否则若 P1 有 video → `shutil.copy2` 覆盖 P2 video；否则重新 render 覆盖。

P1 runner 同样覆盖 `outputs/g1_p1_signal_audit`（`exist_ok=True` + 写同名文件）。

第二次执行：

```text
scripts\run_g1_p2_boundary_audit.py
```

会静默覆盖当前 Audit Package。若 Web 已绑定该路径上的 human review，旧预测表会消失；当前也没有 versioned root 可保留。

---

## 7. Media Audit

### 7.1 Video（ffprobe，未改文件）

三件样本与 P1 对应件（若存在）均为：

```text
container     = MP4 (mov,mp4,...)
codec_name    = mpeg4
codec_tag     = mp4v
profile       = Simple Profile
pix_fmt       = yuv420p
resolution    = 128 x 128
fps           = 20/1
encoder path  = cv2.VideoWriter_fourcc(*"mp4v")
```

| episode | frames | duration s | size B | SHA256 |
| --- | --- | --- | --- | --- |
| demo_0 | 118 | 5.9 | 153545 | `cc088f97...229052` |
| demo_278 | 206 | 10.3 | 253609 | `f5a439d3...337502` |
| demo_242 | 232 | 11.6 | 291702 | `4108e1b4...d2cb2b` |

帧数与 manifest `length` 一致。

```text
Chromium / Edge native playback likely = NO
```

依据：与 M07 同源 `mp4v` / MPEG-4 Part 2。M07 `classify_needs_proxy()` 对 `mpeg4`/`mp4v` 返回 True，走 `H264_BROWSER_V1` proxy。本审计未在浏览器播放 G1 文件；判定来自 codec 事实 + 已有 M07 proxy 证据。

### 7.2 PNG

| file | width | height | mode | size B |
| --- | --- | --- | --- | --- |
| P1 `demo_0/signal_plot.png` | 2520 | 3528 | RGBA | 660134 |
| P2 `demo_0/signal_boundary_plot.png` | 2520 | 3843 | RGBA | 770192 |
| P1 `demo_278/signal_plot.png` | 2520 | 3528 | RGBA | 736573 |
| P2 `demo_278/signal_boundary_plot.png` | 2520 | 3843 | RGBA | 828319 |
| P2 `demo_242/signal_boundary_plot.png` | 2520 | 3843 | RGBA | 996754 |

P2 图更高：同一套 signal axes 上叠加 candidate / suppressed / final overlay（`plot.py::_draw_boundaries`）。

### 7.3 P1 vs P2 媒体是否重复

Video：

| episode | same bytes / SHA256? | 机制 |
| --- | --- | --- |
| demo_0 / 32 / 179 / 278 | **YES** 完全相同 | P2 `_ensure_video` `shutil.copy2` 自 P1 |
| demo_242 / demo_230 | P1 不存在；P2 独有 | P2 自己 render，不是 copy |

不是 shared path：P1 与 P2 各有一份文件。重叠 4 个 episode 是 duplicated copy，不是 symlink。

Plot：

```text
不是同一张图。
P2 = P1 Formal Signal Set + Candidate/Suppressed/Final overlay。
SHA256 不同，高度不同。
```

Web 含义：视频可做 shared-by-hash（4 个 smoke 已是相同 SHA256）；plot 必须 per-run diagnostic。

---

## 8. M07 Web Current Implementation

### 8.1 技术栈定位

```text
M07_WEB_ROOT        = C:\Users\95611\embody\2-Project1_dataset\scr
BACKEND             = FastAPI + uvicorn (python scr/run_m07_audit_web.py)
FRONTEND            = Jinja2 templates + audit.css；无独立 JS bundle / React
DATABASE            = SQLite result/m07_audit_web/m07_audit_web.sqlite
REGISTRY            = result/m07_audit_web/audit_run_registry.json
CONTRACT_VALIDATOR  = project1_benchmark/m07_audit_contract.py :: validate_m07_audit_folder
MEDIA_SERVER        = m07_audit_web_media.py :: /media/{run_id}/{case_id}/{media_key}
VIDEO_PROXY         = m07_audit_web_video_proxy.py :: /proxy/video/{source_sha256}/{profile}.mp4
DEFAULT_BIND        = 127.0.0.1:8765
```

依赖：`scr/m07_audit_web_requirements.txt` = fastapi, uvicorn, jinja2, python-multipart。另需本机/仓库 ffmpeg。

### 8.2 主要文件树

```text
scr/run_m07_audit_web.py
scr/M07_AUDIT_WEB_README.md
scr/m07_audit_web_requirements.txt
scr/project1_benchmark/
  m07_audit_contract.py
  m07_audit_run_registry.py
  m07_audit_web_app.py
  m07_audit_web_input.py
  m07_audit_web_view.py
  m07_audit_web_media.py
  m07_audit_web_video_proxy.py
  m07_audit_web_reviews.py
  m07_audit_web_ui_vocab.py
  m07_audit_web_templates/
    index.html
    audit.html
    error.html
    audit.css
tests/test_m07_audit_web_*.py
tests/browser_m07_audit_web_g4.py
result/m07_audit_web/
  audit_run_registry.json     (1 reversal run)
  m07_audit_web.sqlite        (schema only, 0 review rows)
```

无 `components/` 目录。UI 是 server-rendered HTML form POST。

### 8.3 Run layer

- **Registry reader**：`M07AuditWebInput.list_effective_runs()` 读 JSON registry，不扫描磁盘树。
- **Manual override**：`add_manual_run` / `override_run_path` / `disable_run` / `restore_run`；path_source ∈ `{AUTO_REGISTERED, MANUAL_ADDED, MANUAL_OVERRIDE}`，持久化在 SQLite `owner_run_paths`。
- **Run validator**：`load_validated_run()` 必须先 `validate_m07_audit_folder()`；失败 → `VALIDATION_FAILED`，UI 不可打开。

Registry 写入由 Detector Audit Folder generator 调用 `register_run()`（atomic `os.replace`）。只允许 `run_scope=FORMAL_SCENARIO_RUN`。`run_id` 由 `allocate_run_id(detector_name, detector_version, created_at, salt)` 生成。

本地 registry 样本：

```text
run_id = reversal_v2_1_20260916_155358_38327c38
detector_name = reversal
detector_version = v2.1
run_scope = FORMAL_SCENARIO_RUN
```

### 8.4 Backend routes

```text
GET  /
GET  /audit/{run_id}
GET  /audit/{run_id}/case/{case_id}
POST /audit/{run_id}/case/{case_id}/review     action=save | save_next
GET  /media/{run_id}/{case_id}/{media_key}
GET  /proxy/video/{source_sha256}/{profile_file}
GET  /static/audit.css
```

`docs_url=None`。无 REST JSON API schema 文件；页面模型是 `ValidatedRun` + `CaseView`。

### 8.5 Frontend

`index.html`：Available Runs 表。  
`audit.html`：Run Header + filter (ALL/PENDING/FN/FP/TP/TN) + Case Queue + 6 路媒体 + case 只读字段 + Human Semantic Review + Detector Run Review + Save / Save & Next。  
中文 display 由 `m07_audit_web_ui_vocab.py` 映射，stored code 不变。

### 8.6 Persistence

SQLite 表（真实 CREATE）：

```text
owner_run_paths(
  run_id PK, registry_path, effective_path, path_source, enabled, created_at, updated_at, note)

human_semantic_reviews(          # append-only; current = MAX(review_id) per case_id
  review_id PK, case_id, detector_name, semantic_namespace, semantic_label,
  decision, comment, reviewed_at, source_run_id)

detector_run_reviews(            # append-only; current = MAX(review_id) per (run_id, case_id)
  review_id PK, run_id, case_id, review_decision, failure_reason, comment, reviewed_at)
```

语义：Human Semantic Gold 按 **stable case_id** 跨 run 保留；Detector Run Review 按 **(run_id, case_id)**。Evaluation GT 不会自动写成 Human Gold。

当前本地这三张业务表均为 0 行。

### 8.7 Media / proxy

- 只解析 manifest 相对路径；禁止 `..` / 绝对路径 / 逃出 run root。
- HTTP Range 显式实现；全文件 Range → 200 以便 Chromium 缓存；切片 → 206。
- `Cache-Control: public, max-age=86400, immutable` + ETag。
- Proxy identity = `source_sha256:H264_BROWSER_V1`；cache 路径 `{cache_root}/H264_BROWSER_V1/{sha256}.mp4`。
- `bind_case_media` 在渲染 case 时把 `mp4v` 的 `<video src>` 换成 proxy URL；proxy 文件 lazy generate，不在 page render 时转码。
- 本机 `video_proxy_cache/` 目录当前不存在（尚未为 G1/M07 生成 proxy 文件）。

M07 `case_id` 来源（reversal audit generator）：`row["new_clip_id"]`，并由 `assert_stable_case_id` 禁止包含 `run_id` 或 `rank`。

---

## 9. Reuse Matrix

### CAN_REUSE_AS_IS

仅列当前代码已实现、G1 不改业务语义即可调用的能力：

```text
HTTP Range + ETag + Cache-Control media_file_response
path-isolation media resolver 模式
H264_BROWSER_V1 Video Proxy（content-addressed SHA256 cache）
classify_needs_proxy(mpeg4/mp4v) → needs_proxy=True   # G1 视频正好是这种
FastAPI + uvicorn localhost bind 模式
Jinja2 template/static 挂载
ui_vocab：stored code 不变、页面显示中文
SQLite 文件 + append-only current=MAX(id) 基础设施（不是 M07 那两张业务表本身）
atomic JSON registry write (write_json_atomic)
```

### REUSE_WITH_ADAPTER

换 G1 schema / 路径 / 枚举即可，不必重写框架：

```text
Run Registry reader（JSON entries；禁止扫目录猜最新）
Owner Path Set + MANUAL_OVERRIDE / disable
load_validated_run 门禁（需换 G1 folder contract）
Single Run page shell：header / queue / media / detail
Prev / Next / Save / Save & Next
filter tabs（G1 不能照搬 FN/FP/TP/TN）
ReviewStore 双层 identity 思想：
  source-stable review vs run-specific review
```

### MUST_BUILD_NEW

以当前代码事实为准，不是猜测：

```text
G1 Audit Folder Contract（M07_AUDIT_FOLDER_V1_1 字段全是 case_id/detector/error_type/6 路媒体）
G1 run_meta.json / run_id allocator / versioned audit root
G1-P1 Signal Review UI 与 persistence
G1-P2 Boundary-level Review UI（每条 predicted boundary 一行）
Add Missed Boundary（空行 / human_added_frame）
Conditional form: MISALIGNED→corrected_frame, reason_code 级联
Human Calibration Export → G1-P3 输入文件
Candidate / Suppressed / Final / Segment 表的只读展示
Signal plot 作为一等媒体（M07 MEDIA_KEYS 无 signal_plot）
CALIBRATION_SET / EVALUATION_SET 身份（M07 与 G1 都未在 G1 manifest 出现）
P1/P2 双阶段 queue（M07 是单 detector case queue）
Episode note / blocking issue（template 无此列）
```

不可直接复用的 M07 业务表：`human_semantic_reviews` / `detector_run_reviews` 的 decision 枚举与 G1 VALID/REDUNDANT/... 不同。

---

## 10. UI Field Mapping

控件类型仅基于实际字段。

| UI 区域 | UI 字段 | 来源文件 | 来源 column | 控件类型 |
| --- | --- | --- | --- | --- |
| Run Header | 输出根路径 | 当前固定 `outputs/g1_p2_boundary_audit` | 无 run_id | READ_ONLY |
| Run Header | P2 status | `g1_p2_run_summary.json` | `G1_P2_STATUS` | READ_ONLY |
| Run Header | segmentation status | 同上 | `G1_P2_SEGMENTATION_STATUS` | READ_ONLY |
| Run Header | config_version | `exploratory_config.json` / CSV | `config_version` | READ_ONLY |
| Run Header | segmentation_version | 同上 | `segmentation_version` | READ_ONLY |
| Run Header | threshold_frozen | `g1_p2_run_summary.json` | `threshold_frozen` | READ_ONLY |
| Run Header | episode count | manifest | row count | READ_ONLY |
| Episode Queue | episode_id | P2 `episode_manifest.csv` | `episode_id` | READ_ONLY / queue link |
| Episode Queue | native key | 同上 | `native_episode_key` | READ_ONLY |
| Episode Queue | quality_group | 同上 | `quality_group` | READ_ONLY |
| Episode Queue | length | 同上 | `length` | READ_ONLY |
| Episode Queue | candidate/final/segment counts | 同上 | `candidate_count` 等 | READ_ONLY |
| Episode Queue | review_required | 同上 | `review_required` | READ_ONLY |
| Video | 播放器 | `{demo}/video.mp4` via manifest `video_path` | abs path → 需改相对/受控 route | MEDIA |
| Signal Plot | 图 | `{demo}/signal_boundary_plot.png` | `plot_path` | IMAGE |
| Signal Plot (P1) | 无 overlay 图 | P1 `signal_plot.png` | `signal_plot_path` | IMAGE |
| Final Boundary rows | id | `{demo}/final_boundaries.csv` | `boundary_id` | READ_ONLY |
| Final Boundary rows | frame | 同上 | `frame` | READ_ONLY |
| Final Boundary rows | type / reason | 同上 | `candidate_type`, `reason` | READ_ONLY |
| Final Boundary rows | members | 同上 | `member_candidate_ids` | READ_ONLY |
| Final Boundary rows | flags | 同上 | `review_flags` | READ_ONLY |
| Candidate detail | 全列 | `{demo}/candidate_boundaries.csv` | 见 §3.2.B | READ_ONLY |
| Suppressed detail | 非 KEEP/RETAIN 的 candidate | `{demo}/boundary_decisions.csv` | `decision`, `reason`, `target_boundary_id` | READ_ONLY |
| Review dropdown | human_review | template + codebook | `human_review` | SELECT |
| Reason dropdown | reason_code | codebook | `reason_code` | SELECT |
| Corrected frame | 校正帧 | template | `corrected_frame` | NUMBER_INPUT |
| Add Missed Boundary | 空行 / 新行 | template 空 `predicted_boundary_id` 行 | `human_added_frame` | NUMBER_INPUT + BUTTON |
| Comment | 备注 | template | `note`（不是 comment） | TEXTAREA |
| Episode note | — | **当前 schema 无此列** | MISSING | 不可映射；若 UI 要做须先补 contract |
| Reviewer | reviewer | template | `reviewer` | READ_ONLY or TEXT；规则 NOT_DEFINED |
| Segment table | 可选只读 | `{demo}/segment_manifest.csv` | `segment_id`, start/end, flags | READ_ONLY |

P1 Signal Review 若作为独立阶段：当前没有 review 列可映射，只有 media + `weak_reference` / `alignment` / `nan_inf`。那是 MUST_BUILD_NEW 的 persistence，不是现成 CSV 字段。

---

## 11. Iteration Run Contract Gaps

目标：`Config vN → Audit Run vN → Human Review → Config vN+1 → Audit Run vN+1 → same Web`。Web 不允许扫目录或用 mtime 猜最新。

| 项 | 判定 | 事实 |
| --- | --- | --- |
| `run_meta.json` | **REQUIRED** | 当前不存在；M07 靠它提供 `run_id` 给 registry |
| run registry | **REQUIRED** | G1 无；M07 有独立 JSON registry |
| versioned audit root | **REQUIRED** | 当前固定覆盖 `outputs/g1_p2_boundary_audit` |
| config snapshot | **PARTIAL / ALREADY_EXISTS 弱形式** | `exploratory_config.json` 存在但与输出根同路径，rerun 覆盖 |
| config hash | **REQUIRED** | `config_version` 字符串不会随 threshold 自动变 |
| `parent_run_id` | **REQUIRED**（calibration loop） | 缺失则无法声明 vN+1 继承哪次 review |
| contract validator | **REQUIRED** | G1 无 folder self-validation；Web 不能直接套 `M07_AUDIT_FOLDER_V1_1` |
| `signal_contract_version` / code hash | **REQUIRED** 若要复用 P1 review | 当前 MISSING |
| `created_at` | **REQUIRED** | MISSING |
| CALIBRATION/EVALUATION 标记 | **REQUIRED** 进入 P3/P4 前 | 见 §12 前的 §20 结论 |

```text
NOT_NEEDED = 无。当前缺口都挡住 “same Web continuously register new detector/segmentation runs”。
```

---

## 12. Human GT → G1-P3 Contract

```text
P3_HUMAN_GT_INPUT_CONTRACT = PARTIAL
CALIBRATION_EVALUATION_IDENTITY_READY = NO
```

### 12.1 已定义（文档 + 空 template）

Frozen Master G1-D / Roadmap P2-S1C 规定人工标签：

```text
VALID | REDUNDANT | MISALIGNED + corrected_frame | MISSED_BOUNDARY + human_frame
reason_code
optional_note
```

落地文件现状：

```text
human_boundary_review_template.csv   # 空标签，schema 存在
human_boundary_review_codebook.json  # enum 存在，无中英解释表
```

没有已填写的 Human Boundary Reference 文件。`g1_p3_started = false`。无 `src` G1-P3 reader。

### 12.2 未定义（不要假装有）

G1-P3 最终读取哪个路径 / 哪个文件名 / 哪次 run：

```text
NOT_DEFINED
```

Roadmap 只说 Calibration Review Package 必须提供 template，以及人工 GT 进入 Numeric Threshold Search。没有冻结例如：

```text
outputs/<run_id>/human_boundary_gt.csv
或 Web SQLite export
```

也没有：filled vs template 的区分、row_id、如何把 3 条空 MISSED 行变成正式 GT、如何处理 `boundary_id` 跨 run 不稳定、tolerance window 数值。

### 12.3 Calibration / Evaluation 字段

代码与两份 manifest **都没有** `CALIBRATION_SET` / `EVALUATION_SET`。

P1 `split=TRAIN` 是 RoboMimic train/valid，不是 P2 Calibration/Evaluation。  
P2 `quality_group` 是 BETTER/OKAY/WORSE，不是 set identity。

Web / Run Contract 最终需要（只列缺口，不发明 schema）：

```text
episode 属于 CALIBRATION_SET 还是 EVALUATION_SET
该身份绑定到哪一次 frozen manifest / run_id
禁止用 Evaluation 行去调 threshold
```

### 12.4 Web Design Freeze 前必须补齐的接口字段

不是一套假设计，只是当前空缺：

```text
1. P3 读取的 GT 文件名与是否 Web-owned export
2. 每行稳定键：不能只靠 boundary_id
3. human_review / reason_code / corrected_frame / human_added_frame 的 required 逻辑
4. MISSED_BOUNDARY 行身份（新 GT 点 vs 空 template 行）
5. CALIBRATION_SET episode 列表的权威位置
6. run_id + parent_run_id + config_hash 如何随 GT 一起被 P3 消费
```

---

## 13. Blocking Decisions Before Web Design Freeze

| ID | 问题 | 级别 |
| --- | --- | --- |
| B1 | G1 Audit 根目录是继续覆盖 `outputs/g1_p2_boundary_audit`，还是必须 versioned `{run_id}` 目录？当前 runner = 覆盖。 | **BLOCKER** |
| B2 | Predicted boundary 的 Web/SQLite 主键：承认 `boundary_id` 仅 RUN_STABLE，强制 `(run_id, episode_id, boundary_id)`？还是改生成规则做跨 run 稳定（会改 Frozen 实现，超出本轮）？ | **BLOCKER** |
| B3 | Human Review 权威存储：填写/导出 CSV template，还是 Web SQLite 为 SSOT 再 export 给 P3？P3 读谁？ | **BLOCKER** |
| B4 | P1 Signal Review 是否作为 Web 一等阶段？当前无 review schema，且 HUMAN_VISUAL_REVIEW=DEFERRED。 | **BLOCKER** |
| B5 | CALIBRATION_SET / EVALUATION_SET 的 episode 名单与字段在 Freeze 前是否写入 Run Contract？ | **BLOCKER** |
| B6 | 视频策略：强制复用 M07 H264 proxy（G1 已是 mp4v），还是改 encoder（本轮禁止改视频/threshold，只能在 Design 里拍板）？ | **NON_BLOCKER**（播放必需，但不阻塞字段 Freeze；默认可跟 M07） |
| B7 | 中文 display 是 Web vocab 层（M07 模式）还是改 codebook？后者本轮明确不改 source。 | **NON_BLOCKER** |
| B8 | Template 3 条空 MISSED 行 vs UI “Add Missed Boundary” 按钮；B 编号缺口是否对审核员可见。 | **NON_BLOCKER** |
| B9 | P1/P2 视频 duplicate copy 是否改为 hash-shared media。 | **IMPLEMENTATION_DETAIL** |
| B10 | FastAPI/Jinja 复制 vs 新包名；端口；是否保留 FN/FP filters。 | **IMPLEMENTATION_DETAIL** |
| B11 | `note` vs UI 文案「备注」；`episode_note` 是否新增列。新增列 = Design/schema 变更。 | **BLOCKER** 若 UI 要 Episode note；否则 NON_BLOCKER |
| B12 | `config_version` 字面量在改 threshold 时是否必须 bump / 是否必须上 hash。 | **BLOCKER**（否则 vN 与 vN+1 无法区分） |

---

## 14. Recommended Design Patch

```text
DRAFT_FOUND = NO
```

无法对 `Project2_G1_Human_Audit_Web_Design_DRAFT_v0_1_20260916.md` 做章节级 freeze/修改/TBD 对照，因为本地与 Drive 均无该文件。

任何后续 Draft 若要 Freeze，必须吸收本审计，否则会与真实 package 冲突：

### 可以按 Frozen G1 Design 写入 Draft 且与真实 enum 对齐的部分

```text
Review 主枚举 VALID / REDUNDANT / MISALIGNED / MISSED_BOUNDARY
reason_code 列表（与 codebook / Master G1-D 一致）
P1 = Signal Review, P2 = Boundary Review 的阶段划分
M07 框架复用：Registry → Validator → Queue → Media → Human Review → SQLite → 新 run 注册
中文 display 放 Web vocab 层，不改 codebook
视频走 H264 proxy（源 codec=mp4v）
episode_id 作为 source-stable queue key
```

### Draft 若已按“稳定 final_boundary_id / 扫描最新目录 / 直接套 M07 case_id”来写，则必须改

```text
列名是 boundary_id 不是 final_boundary_id
candidate evidence 列名是 evidence_value
comment 列名是 note
P1 无 quality_group，有 weak_reference
无 run_id；rerun 覆盖同一目录
C/B/S ID 都是 run-local 序号，跨 config 会漂
human required 逻辑未机器化
无 CALIBRATION_SET 字段
P3 输入文件未定义
P1/P2 plot 不是同一张图
```

### 在 B1–B5 / B12 拍板前必须保持 TBD

```text
versioned run root 布局
SQLite vs CSV 作为 Human GT SSOT
P3 读取契约
P1 Signal Review persistence
config hash / parent_run_id
episode_note 是否入 schema
```

本轮 **不修改** 任何 Design MD。

---

## 15. Explicit Stop

```text
NO_SOURCE_MODIFICATION = YES
NO_AUDIT_OUTPUT_MODIFICATION = YES
NO_WEB_CODE_MODIFICATION = YES
NO_NEW_RUN_GENERATED = YES
NO_THRESHOLD_CHANGE = YES
```

本轮唯一写入：本报告文件

```text
C:\Users\95611\embody\4-Project2_data_value\0-doc\80-audit-local\Project2_G1_Audit_Web_Local_Structure_Audit_20260916.md
```

执行到这里停止。
