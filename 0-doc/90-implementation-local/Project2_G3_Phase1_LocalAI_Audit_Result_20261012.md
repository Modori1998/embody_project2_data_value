# Project 2 · G3 / Argus — Phase 0 + Phase 1 本地 AI 执行结果

```text
DATE              = 2026-10-12
DOCUMENT_STATUS   = LOCAL_EXECUTION_RESULT (DRAFT, 未冻结)
SCOPE             = SSOT 文档补齐核查 + G3 输入/可观测性只读审计 + 无 VLM 工程可行性检查
VLM_INVOKED       = NO
FORMAL_RETRIEVAL  = NOT_EXECUTED
FAISS_SIGLIP2     = NOT_EXECUTED
FROZEN_ARTIFACTS  = UNMODIFIED
RESULT            = PARTIAL (文档补齐阻塞；Git/网络已恢复并权威核验)
```

> **结论先行**：本轮**未**产生任何 VLM 调用、未执行正式检索、未改动任何冻结产物。
> 第 1 节（PR 文档补齐）因**输入缺失**（ZIP 不在本地）而**阻塞**；网络问题已排查并修复，PR #1 与 `origin/main` 已**权威核验**（见 A 节）。如实报告，未凭记忆重写文档。
> 第 2 节 Argus 侧**上游源码不可得**，故只完成 P2 侧能力盘点并给出映射骨架（Argus 侧标注 UNVERIFIED）。
> 第 3 节数据可观测性 Probe **完整执行成功**，是本轮唯一有实证产出的部分。

---

## A. Git / PR 同步状态 — **已恢复，权威确认**

### A.1 远端可达性诊断（先诊断，未臆测）

初次执行时网络**确实不可用**；随后（用户提示 VPN 后）重新诊断，**代理恢复**。

| 阶段 | 检查 | 结果 |
|---|---|---|
| 初次 | `git ls-remote` × 3 次退避 | **失败**：`CONNECT tunnel failed, response 502` / `schannel: server closed abruptly` / 直连 `Connection was reset` |
| 初次 | 代理端口 | 当时为 `127.0.0.1:4311`；历史端口 `14227` **已不再监听** |
| 恢复后 | 代理端口 | 变为 **`127.0.0.1:13931`**（另有 `127.0.0.1:10808` 监听） |
| 恢复后 | 公共仓库对照 | `git ls-remote https://github.com/octocat/Hello-World` → **成功** |
| 恢复后 | 目标仓库 | 无凭据时 `401`（私有）；**注入凭据后成功** |

**根因（两项，均已解决）**：
1. **代理端口漂移 + 间歇 502**：`ls-remote` 轻量可通，`fetch`（下载对象）易被重置 → 需**多后端 + 退避重试**。
2. **凭据助手失效**：`credential.helper=helper-selector` 在非交互环境路由失败（`could not read Username`）。
   Windows 凭据管理器**确实存有** `LegacyGeneric:target=git:https://github.com`（user `Modori1998`），
   直接调用 `git-credential-manager.exe get` **可取回**。

**可用组合（本轮验证）**：
```text
credential.helper=  （清空默认）
credential.helper=!f(){ echo username=Modori1998; echo password=$GH_PAT; }; f
http.sslBackend=openssl  （schannel 亦可，交替重试更稳）
+ 退避重试循环（每次 sleep 5–8s）
```
> 凭据**仅在进程内注入**，未写入磁盘、未进入命令行、未提交。

### A.2 `CURRENT_MAIN_SHA` — **已权威确认**

```text
CURRENT_MAIN_SHA = b5fd9b97d1b32ffa98d6facd95bf663be12ac63e
```
- 依据：`git ls-remote origin refs/heads/main` **成功返回**（权威通道，非缓存）。
- 交叉印证：PR 分支 `P2_G3_Retrieval_HOLD_Scope_Change_v1_20261012.md` 内
  `SRC_MAIN_HEAD_BEFORE = b5fd9b97d1b32ffa98d6facd95bf663be12ac63e` —— **完全一致**。
- 初次执行时的降级推断（本地 tracking `origin/main` = `b5fd9b9`）**被证实正确**。

### A.3 主工作树同步

```text
MAIN_WORKTREE       = C:/Users/95611/embody/4-Project2_data_value
BEFORE              = cc42b9b39d72f52f540485411f6d80ff3dd785ae
AFTER               = b5fd9b97d1b32ffa98d6facd95bf663be12ac63e
OPERATION           = git pull --ff-only origin main  →  Fast-forward
CHANGED             = 40 files, +7531 / -9
POST_STATE          = clean (git diff --numstat 空)
FORCE_CHECKOUT      = 未执行     RESET/CLEAN = 未执行     STASH = 未执行
```
> 同步内容即检索优先 MVP 的 24 个提交（M2、Core Retrieval 协议/清单、校准人审、Rubric Clarification）。
> 本机 `refs/remotes/*` 写入可能被静默丢弃（已知问题）—— 故 PR 分支需**显式指定 refspec** 拉取。

### A.4 本任务分支与 worktree

```text
CURRENT_BRANCH = p2-g3-local-ai-phase01-20261012
WORKTREE       = C:/Users/95611/embody/_p2_g3_phase01_wt
BASE           = b5fd9b9  （= 权威 origin/main）
HEAD           = 7fa0e88  "Record P2-G3 Phase-1 local AI audit result (A-G deliverable)"
PUSHED         = NO（待 Owner 决定是否推送该审计分支）
```

### A.5 PR #1 状态 — **已核验（权威）**

```text
PR_NUMBER            = 1
PR_HEAD_BRANCH       = design/p2-g3-argus-scope-20261012
PR_HEAD_SHA          = dcad5c12818b73499ba11e43c0fd3a73b2e65cd7   (= refs/pull/1/head)
PR_MERGE_REF         = 3c423e5c4b401ac3f1b3b2a6c26318b064a029a9   (= refs/pull/1/merge)
MERGE_BASE_WITH_MAIN = b5fd9b9   （干净分支，无偏离）
COMMITS              = d8b0395 "Record Owner HOLD of Retrieval and reprioritize Argus-style G3"
                       dcad5c1 "Add non-destructive P2 Retrieval HOLD and G3 priority overlay"
MERGED               = NO（Draft，未合并）
```

**PR 实际改动（`git diff --numstat b5fd9b9 dcad5c12`，权威核验）**：

| 状态 | 文件 | 行数 |
|---|---|---|
| A | `0-doc/10-design-review/P2_G3_Retrieval_HOLD_Scope_Change_v1_20261012.md` | +30 |
| M | `0-doc/Project2_MVP_SSOT_20261008.md`（顶部 HOLD overlay） | +4 |

> **与任务书描述完全一致**："该 PR 当前仅有 SSOT 的 HOLD overlay 和
> `P2_G3_Retrieval_HOLD_Scope_Change_v1_20261012.md`，三份详细文档尚未同步。"

**SSOT overlay 内容（已读全文）**：声明 `P2_RETRIEVAL_V1_STATUS=HOLD_BY_OWNER`、
`P2_ACTIVE_PRIORITY=ARGUS_INSPIRED_G3_SEMANTIC_ANNOTATION`、`G3_DEPENDS_ON_RETRIEVAL_GATE=NO`，
并明确冻结检索清单/rubric/未执行的 18-query Final Retrieval **不得**被重解释为已完成或失败。

**Scope Change memo 内容（已读全文）**：`STATUS=OWNER_APPROVED_DIRECTION / REVIEW_BRANCH_PENDING_MERGE`；
5 条 Owner 决定（HOLD、G3 新主线、Argus 核心功能重实现 + Apache-2.0 归属、工业最小评测
**同一冻结 Qwen3-VL 模型** + A/B 对照、不训练 ACT/VLA、不自动 DROP/UPWEIGHT）。
其 "Next execution" 第 1 条明确要求**先把 Design / Plan / Output Design 三份文档纳入 PR 再合并**。

### A.6 三份文档补齐状态 — **仍阻塞（输入缺失）**

| 项 | 状态 |
|---|---|
| `P2_G3_Argus_Review_Package_v1.zip` | **缺失**（Downloads / Desktop / embody 全盘搜索 0 命中） |
| PR 分支内是否已有三份文档 | **无**（diff 权威核验：仅 2 个文件） |
| 三份目标文档 | **未创建、未提交** |
| 结论 | **明确报告：缺少文档。** 依指令**不凭模型记忆重写**、**不新建重复 PR**、**不 merge** |

> **术语/状态一致性核查（可执行部分）**：PR 内 SSOT overlay 与 Scope Change memo **互相一致**
> （HOLD 状态、G3 优先级、冻结保留、不训练 ACT/VLA、taxonomy 仍需单独冻结）。
> 三份文档到手后需再核对其与这两者的术语与状态一致性，并做**最小定向修复**。

---


## B. Argus 核心能力 → P2 功能映射与缺口

### B.0 前置声明（可信度分级，务必先读）

| 证据来源 | 可得性 | 本报告如何使用 |
|---|---|---|
| Argus 上游源码（`label/prompts.py`、`label/episode.py`、`label/frames.py`、`label/route.py`、`checks/label_consistency.py`、`review/`、`board/`） | **不可得**（无本地副本，无网络） | **无法**记录上游 commit SHA；**无法**核对 Apache-2.0 归属文本 |
| `P2_G3_Argus_Review_Package_v1.zip`（三份设计文档） | **不可得** | 同上 |
| P2 本仓代码与冻结文档 | **完全可得** | 作为映射矩阵的 P2 侧权威依据 |

> 因此 **B 节的 Argus 侧描述标记为 `UNVERIFIED_AGAINST_UPSTREAM`**：能力名取自本轮任务书列举的
> 功能域（采样 / 语义标签 / 任务结果 / 错误恢复 / QC / 审核 UI / 运行日志 / 导出），
> **不是**从 Argus 源码读出的接口事实。**不得**据此声称已完成 Argus 兼容性认证。
> 另：**`固定上游 commit SHA` 与 `Apache-2.0 归属要求` 本轮无法记录 —— 标记为 OPEN BLOCKER。**

### B.1 映射矩阵（P2 侧为实测，Argus 侧为 UNVERIFIED）

| # | 能力域 | P2 现有实现（实测） | 需要新增的 P2 模块 | 功能差距 | 依赖前置 | 复用/自主 | 风险 | 首版必需? |
|---|---|---|---|---|---|---|---|---|
| 1 | **采样 / Segment 构造** | Frozen G1 boundary engine（`project2_g1/boundary_engine.py`）+ Frozen 配置 `A1-007-C002` / τ_P12 / τ_C12 / window=8，**已实现、已 calibration、final config frozen** | 无（直接复用）；仅需 Development-pool 选择器（本轮已建） | **无**。注意：这是**运动分段**，**不是** VLM 语义分段 | 无 | 复用 | 低 | 是（已满足） |
| 2 | **Keyframe / 帧证据** | MVP-M2 `select_keyframes`：START/MIDDLE/END + GRIPPER_EVENT，去重、多角色保留 | 可选：更多 keyframe policy（当前固定 3–4 帧） | 粒度固定，不可按事件密度自适应 | M2 | 复用 | 中（见 C/D 节遮挡问题） | 是（已满足） |
| 3 | **语义标签（VLM）** | **不存在**。SSOT 明确 `G3_MVP_TAXONOMY = PENDING_MINIMAL_FREEZE` | G3 taxonomy freeze + prompt/schema/parser + provenance | **完全缺失** | P0B taxonomy freeze + RGB 运行时验证 | 自主（Argus 可参考） | **高** | **是（G3 本体）** |
| 4 | **任务结果（success/fail）** | 数据里**有** `rewards/dones` 但属 **forbidden**；Formal 侧**无**结果标签 | 若需要，只能作为**受限 evaluator namespace**（非模型输入） | 缺失；且**不得**把 reward/done 喂给 labeler | Owner 决策 | 自主 | 中（泄漏风险） | 否（首版可后置） |
| 5 | **错误恢复 / 失败检测** | **不存在**。G1 只切"状态变化"，不判失败 | 需 taxonomy 显式定义 + 可见正例 | **完全缺失**；且本轮 Probe 显示**可见性不足**（C 节） | taxonomy + 可见性结论 | 自主 | **高** | 否（首版建议后置） |
| 6 | **QC / 一致性检查** | 有：`assert_no_privileged_inputs`、M2 sanity gates、`checks` 风格断言；本轮新增 EvidencePack 四道 fail-closed 守卫 | 标签一致性检查（`label_consistency` 类） | 缺**标签层** QC（G1 层已有） | taxonomy | 复用+自主 | 中 | 是 |
| 7 | **审核 UI** | 有：G1 Audit Web（`src/project2_g1_audit_web`）、MVP Calibration Temporal Audit UI（含视频+帧轴同步） | G3 标签审核页（复用现有模板/媒体契约） | 缺 G3 侧 | 标签产出 | 复用为主 | 中（页面媒体是必需项） | 是 |
| 8 | **运行日志 / Provenance** | 强：`run_meta.json`、`rgb_provenance.json`、dataset SHA、frozen config SHA、`git_base` | G3 run log（prompt/模型 revision/输入来源） | 缺 G3 侧 | 模型接入 | 复用 | 低 | 是 |
| 9 | **导出 / Manifest** | 有：M2 manifests、retrieval manifest、Curation Manifest schema（SSOT §7，含 `candidate_tags[]` / `triage_action ∈ {KEEP,REVIEW}`） | G3 structured label 导出 | 缺标签列 | taxonomy | 复用 | 低 | 是 |

### B.2 关键边界（防止术语误用）

- **禁止**把 P2 G1 的运动分段称为"Argus 的 VLM 语义分段"。G1 输出是 `UnlabeledSegment`，
  其 `segment_label` / `semantic_phase` 字段当前恒为 `"NONE"`（源码实测）。
- SSOT 冻结：`approach / grasp / lift / transport / place / retract / idle / recovery / other`
  **只能作为候选最小集合**，Owner Freeze 前**不得**称 Formal Frozen Taxonomy。
- G3 语义**只能**来自 `RGB/keyframes + gripper/EEF/action-state summary`；
  `Can_pos / Can_to_EEF` **仅**用于独立评测与错误分析，**不得**作 hidden shortcut。

---

## C. Development-pool 审计清单（12 Episode / 59 Segment）

### C.1 采样规则（确定性、可复现、未触碰任何冻结集合）

```text
DEVELOPMENT_POOL =
    300 (dataset readable episodes)
  - 32  HISTORICAL_G1_USAGE           (exploratory + calibration + design diagnostic)
  - 24  FROZEN_G1_EVALUATION          (G1_P4_EVAL_MANIFEST_v1, 已延期独立评测)
  - 63  FROZEN_CORE_RETRIEVAL         (36 candidate bank + 9 calibration query + 18 final query)
  = 181
```
- 三段重叠审计：`historical∩frozen_eval = []`，`historical∩frozen_retrieval = []`，`frozen_eval∩frozen_retrieval = []`。
- 分层：对 181 条按 `(frame_count ASC, episode_id ASC)` 排序后取**时长三分位**（SHORT/MEDIUM/LONG）。
- 选样：层内按 `SHA256("P2_G3_PHASE1_PROBE_20261012|" + episode_id)` 升序，每层取前 4 → **12 条**。
- **未**使用任何冻结 formal 查询/候选/人审标签/embedding/检索分数。选择对输入顺序**不敏感**（有测试）。

### C.2 12 条 Episode 清单

| # | Episode | 层 | frames | segs | gripper-event segs | 边界类型 | 帧一致性 | 重复渲染 | 证据路径 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `data/demo_155` | SHORT | 133 | 5 | 3 | DIRECTION_CHANGE, GRIPPER_TRANSITION | PASS | 稳定 | `evidence_packs/data__demo_155.json` |
| 2 | `data/demo_33` | SHORT | 132 | 4 | 3 | GRIPPER_TRANSITION | PASS | 稳定 | `evidence_packs/data__demo_33.json` |
| 3 | `data/demo_24` | SHORT | 115 | 4 | 3 | GRIPPER_TRANSITION | PASS | 稳定 | `evidence_packs/data__demo_24.json` |
| 4 | `data/demo_47` | SHORT | 99 | 4 | 3 | GRIPPER_TRANSITION | PASS | 稳定 | `evidence_packs/data__demo_47.json` |
| 5 | `data/demo_120` | MEDIUM | 178 | 5 | 3 | GRIPPER_TRANSITION, MOVE_TO_IDLE | PASS | 稳定 | `evidence_packs/data__demo_120.json` |
| 6 | `data/demo_227` | MEDIUM | 150 | 6 | 3 | DIRECTION_CHANGE, GRIPPER_TRANSITION | PASS | 稳定 | `evidence_packs/data__demo_227.json` |
| 7 | `data/demo_196` | MEDIUM | 194 | 5 | 3 | DIRECTION_CHANGE, GRIPPER_TRANSITION | PASS | 稳定 | `evidence_packs/data__demo_196.json` |
| 8 | `data/demo_165` | MEDIUM | 169 | 4 | 3 | GRIPPER_TRANSITION | PASS | 稳定 | `evidence_packs/data__demo_165.json` |
| 9 | `data/demo_74` | LONG | 216 | 5 | 3 | GRIPPER_TRANSITION, IDLE_TO_MOVE | PASS | 稳定 | `evidence_packs/data__demo_74.json` |
| 10 | `data/demo_277` | LONG | 224 | 5 | 3 | GRIPPER_TRANSITION, MOVE_TO_IDLE | PASS | 稳定 | `evidence_packs/data__demo_277.json` |
| 11 | `data/demo_292` | LONG | 207 | 5 | 3 | DIRECTION_CHANGE, GRIPPER_TRANSITION | PASS | 稳定 | `evidence_packs/data__demo_292.json` |
| 12 | `data/demo_75` | LONG | 256 | 7 | 2 | DIRECTION_CHANGE, GRIPPER_TRANSITION, IDLE_TO_MOVE, MOVE_TO_IDLE | PASS | 稳定 | `evidence_packs/data__demo_75.json` |

接触表（人工目视复核用，每格标注 frame index + role）：
`outputs/g3_phase1_probe/_visual/data__<episode>_contact_sheet.png`（12 张，128×128 最近邻放大到 192×192）。

### C.3 逐段结构统计（59 段）

```text
SEGMENTS_TOTAL            = 59
DURATION <= 10 frames     = 24 (41%)      <-- 短段占比高
DURATION <=  4 frames     = 19 (32%)
L_BOUNDARY = EPISODE_START= 12 (20%)      <-- 每集开头固定 [0-3] 四帧前奏段
GRIPPER_EVENT segments    = 35 (59%)
NO GRIPPER_EVENT segments = 24 (41%)
MULTI_ROLE frames (START+GRIPPER_EVENT) = 35
RGB_INDEX_MISMATCH        = 0
KEYFRAME_OUT_OF_SEGMENT   = 0
FORBIDDEN_AUDIT_FAIL      = 0
```

**问题案例（重要）**：
1. **结构性短段**：每集固定出现 `[0-3]`（4 帧，L=EPISODE_START）与尾部 4–9 帧收尾段。
   这些段几乎不含可命名行为语义，41% 的段 ≤10 帧。→ taxonomy 必须显式处理，或引入最小段长/合并规则（**但 G1 边界已冻结，不得本轮修改**）。
2. **关键帧遮挡/出画**：`demo_75` 的 `S0003`(29–68, DIRECTION_CHANGE)、`S0004`(69–126, DIRECTION_CHANGE)
   以及 `demo_33` `S0002` 末帧（f69），目标蓝罐在 agentview 中**被机械臂遮挡或移出画面**。
   仅凭 START/MIDDLE/END 三帧**无法**判定"是否已抓取 / 是否已释放"。
3. **分辨率**：渲染固定 **128×128×3**（P1 renderer 实测）。蓝罐直径约 8–12 px，夹爪指宽约 3–5 px。
   **接触/滑脱/抓空**处于像素级极限，人工目视亦不稳定。

### C.4 可见性判定（对应任务书第 6 项）

| 阶段 | 可见性结论 | 依据 |
|---|---|---|
| 接近（approach） | **通常可见** | 多段 START→MIDDLE 可见夹爪与罐相对接近（demo_33/155/227） |
| 抓取（grasp） | `CANDIDATE_ONLY` | 可见夹爪闭合并靠近罐，但**接触瞬间**在 128×128 下不可靠确认 |
| 移动（transport） | **通常可见** | EEF 位移显著，罐随动在部分帧可见 |
| 释放（release） | `INSUFFICIENT` | 释放后罐常已出画/被遮挡；无稳定可见正例 |
| 接触 / 掉落 / 抓空 / 恢复 | **`INSUFFICIENT`** | 本轮 12 集 59 段中**未发现足够可见的真实正例** |

> **依指令，不凭空制造案例。** 上述判定基于接触表目视 + 帧统计，标注为 **DRAFT / 需 Owner 复核**。

### C.5 跨 Segment 事件（只记录问题，不改冻结边界）

- G1 边界为 gripper transition / direction change / idle↔move。若一个物理行为（如"抓取-抬升"）
  横跨两个 G1 段，则**单段 EvidencePack 无法表达完整事件**。
- 本轮观察到：抓取段与其后 transport 段相邻（如 `demo_33` S0002→S0003），
  释放语义落在**段边界附近**。
- **需要跨段上下文**：建议下一阶段评估"邻接段 ±1 的 keyframe 拼接"或"段间过渡帧"作为可选证据，
  **但本轮不修改任何冻结 G1 边界**，仅登记为待决问题。

---

## D. 字段契约 / 时间对齐 / Renderer / 任务文本 结论

### D.1 允许字段（模型可见，allowlist）

```text
EVIDENCE_PACK_ALLOWED = { keyframe_rgb, keyframe_roles, segment_identity, robot_motion_summary, task_text }
FORMAL_SOURCE_FIELDS  = { eef_pos, gripper_qpos, actions }      # MVP-M2 ALLOWED_FORMAL_INPUT_FIELDS
MOTION_SUMMARY_FIELDS = duration_frames, duration_sec, eef_net_displacement_m, eef_path_length_m,
                        eef_displacement_xyz, eef_main_direction_xyz, coarse_direction_change_rad,
                        gripper_{start,end}_aperture, gripper_{start,end}_state,
                        gripper_transition_present, action_magnitude_{mean,max,std}, action_semantic
```

### D.2 Forbidden 字段明细（实测存在于原始数据，但**未**进入 Formal 输入）

原始 HDF5 **确实含有**以下字段（`demo_0` 实测 schema）：

| 位置 | 字段 | 性质 | 本轮验证 |
|---|---|---|---|
| `data/<ep>` | `rewards` | 模拟器 reward | **未**被 `load_formal_episode` 读取 |
| `data/<ep>` | `dones` | 模拟器 done | **未**读取 |
| `data/<ep>` | `states` | 原始 MuJoCo 71D 特权状态 | **未**直接进入模型输入（**仅**被 renderer 用作 `render(STATE_t)` 的中间量，见 D.4） |
| `data/<ep>/next_obs/*` | 全部 | `obs[t+1]` 转移结果 | **未**读取 |
| `data/<ep>/obs/object` | `object` | 物体 GT 14D | **未**读取 |

Forbidden token 集合（`project2_mvp/m2.py`，实测）：`{object, can_pos, can_quat, reward, done, success, next_obs, states}`。

**本轮显式检验（双层）**：
1. **静态 allowlist**：`audit_forbidden_field_names(ALLOWED_EVIDENCE_FIELDS)` → PASS。
2. **动态表面扫描**：对**实际发出**的 `motion_summary` keys + keyframe roles + 面名重新扫描 forbidden token → PASS。
3. 结果：59/59 段 `forbidden_audit_passed = True`；`forbidden_audit_fail = 0`。

> 未发现禁止字段漏入。**注意**：本轮验证的是**字段名层面**的 allowlist + 发出面扫描，
> **未**做数值层面的"语义泄漏"证明（如 RGB 像素本身是否间接编码了特权信息）。该点列入 G 节。

### D.3 时间对齐结论

```text
MODEL_RGB[t] = render(STATE_t)  ↔  PROPRIO[t]  ↔  ACTION[t]      # 同一规范索引 t
```
- 实测：`len(eef_pos) == len(actions) == len(gripper_qpos) == frame_count`，12/12 集全相等。
- `RGB_INDEX_MISMATCH = 0`、`KEYFRAME_OUT_OF_SEGMENT = 0`（59 段全通过）。
- 对齐为**索引保持型（index-preserving）**，无重采样、无插值。

### D.4 Renderer 结论

| 项 | 值 |
|---|---|
| 渲染器 | `project1_benchmark.robomimic_rgb_materializer.RoboMimicStateRenderer`（P1 权威实现，**未复制**） |
| 输入 | `STATE_t`（源状态序列） |
| 输出 | `128×128×3 uint8`，`RGB` 色彩空间 |
| 后处理 | 无叠加、无 resize、无 crop；PNG 无损导出（compression=3） |
| `overlay_applied` / `audit_mp4_used` / `lossy_video_roundtrip` | 全为 `False`（逐帧断言） |
| **重复渲染一致性** | **12/12 集**：同一 frame index 渲染两次 `pixel_sha256` **完全相同** |
| 交叉核对 | `demo_0` frame 0 哈希 `b1083e13d4ec2747…` 与既存 `mvp_rgb_contract_smoke` 产物**一致** |

**须登记的语义事实（非缺陷，但影响 claim）**：RGB 由**模拟器状态重渲染**得到，属 `renderer-derived RGB`，
**不是**真实相机采集。任何"视觉真实性"类结论不得越过此边界。

### D.5 任务文本来源结论（关键）

| 项 | 结论 |
|---|---|
| 数据中是否存在**逐 episode 自然语言指令** | **不存在**（raw / low_dim HDF5 均无 instruction/language 字段） |
| 唯一可得 task 字符串 | `"PickPlaceCan"`（来源：`adapter.get_provenance()["task"]`，即**环境/任务 ID**） |
| 12 集 59 段取值 | `task_text_distinct = ["PickPlaceCan"]`（全同） |
| 是否可当"实录 instruction" | **否**。`recorded_instruction = false`（硬编码于 `TaskTextEvidence`） |
| 后果 | 若 VLM 提示词需要 task text，**只能**用环境 ID，且**必须**在 provenance 标注为环境 ID，**不得**升级为自然语言指令 |

### D.6 Action 语义结论

```text
ACTION_SEMANTIC = NORMALIZED_CONTROLLER_INPUT      # 59/59 段实测一致
```
Action 是 **7D OSC_POSE 归一化控制器输入**（`translation_delta_xyz` + `rotation_delta_xyz` + `gripper_command`），
**不等于**实际物理速度或位移。`eef_net_displacement_m` / `eef_path_length_m` 来自 **realized proprio**，
才是运动学证据。二者**不得**互相替代。

---

## E. 已实现的无模型调用代码路径 + 测试

### E.1 代码路径（全部位于独立分支 / 独立目录，未触碰 G1/M2/Frozen Retrieval）

| 文件 | 职责 | blob sha256(前16) |
|---|---|---|
| `src/project2_g3/__init__.py` | 包声明与范围说明 | — |
| `src/project2_g3/development_pool.py` | 确定性 Development-pool 构造 + 分层选样 | `97ac216585be244c` |
| `src/project2_g3/evidence_pack.py` | 无 VLM EvidencePack 适配器（4 道 fail-closed 守卫） | `49596cf8a6f17213` |
| `src/project2_g3/probe.py` | Probe 编排 + 产物落地 | `37af50cb09edf62b` |
| `scripts/run_g3_phase1_probe.py` | 只读 CLI | `0eae18daf8b948ae` |
| `tests/test_project2_g3_probe.py` | 18 项测试 | `4f601ddbb4370162` |

四道 fail-closed 守卫：①段范围/episode 长度 ②`MODEL_RGB[t]`↔keyframe↔段范围 ③RGB provenance（无叠加/无 MP4/无损视频往返）④禁止字段（静态 allowlist + 动态发出面扫描）。

### E.2 测试清单与结果

```text
PYTHON = C:\Users\95611\miniconda3\envs\project1_robomimic_audit\python.exe  (3.10.21)
CMD    = python -m unittest tests.test_project2_g3_probe
RESULT = OK  (18 tests, 0 failures, 0 errors)
```

| 测试 | 覆盖目标 | 结果 |
|---|---|---|
| `test_inclusive_range_and_middle` | 段范围/中点 | PASS |
| `test_off_by_one_single_frame_segment` | **off-by-one**（start==end） | PASS |
| `test_middle_uses_floor_division` | 中点向下取整 | PASS |
| `test_no_gripper_event_when_left_boundary_not_gripper` | **无 gripper 事件** | PASS |
| `test_gripper_event_attached_to_start_frame` | gripper 事件挂 START | PASS |
| `test_build_pack_without_render_uses_cache` | 帧缓存路径 | PASS |
| `test_out_of_segment_frame_fails` | 帧越段 fail-closed | PASS |
| `test_frame_index_beyond_episode_fails` | **缺帧/越界** fail-closed | PASS |
| `test_alignment_detects_index_mismatch` | 对齐不一致检测 | PASS |
| `test_provenance_reference_preserved` | **来源引用**保全 | PASS |
| `test_allowlist_passes` / `test_forbidden_tokens_detected` / `test_unapproved_field_detected` | **禁止字段漏入** | PASS |
| `test_task_text_not_upgraded_to_instruction` / `test_missing_task_field` | 任务文本诚实性 | PASS |
| `test_probe_digest_is_deterministic` / `test_selection_is_stratified_and_unique` / `test_selection_is_order_independent` | 选样确定性 | PASS |

### E.3 本轮 Probe 运行摘要

```text
RUN = outputs/g3_phase1_probe/g3_phase1_probe_20261012
episodes_probed = 12   segments_probed = 59
rgb_index_match_all = True      keyframes_in_segment_all = True
forbidden_audit_passed_all = True
duplicate_render_stable_episodes = 12 / 12      episodes_with_render_error = 0
vlm_invoked = false   formal_retrieval_executed = false   faiss_executed = false   siglip2_executed = false
```

### E.4 未实现项（诚实清单）

- G3 taxonomy freeze、prompt、schema、parser —— **未实现**（本轮禁止自行冻结）。
- VLM 调用链路、SigLIP2 编码、FAISS 检索 —— **未实现**（本轮禁止）。
- 标签层一致性检查（`label_consistency` 类）—— **未实现**（依赖 taxonomy）。
- 数值层特权泄漏证明（RGB 像素是否间接编码 GT）—— **未做**。
- Argus 上游源码审计、commit SHA 记录、Apache-2.0 归属文本 —— **阻塞**（源码不可得）。

---

## F. `PROPOSED_MINIMAL_TAXONOMY` — **DRAFT，未冻结，禁止引用为 Formal**

> **状态：DRAFT / PROPOSAL_ONLY。** 本轮**无权**冻结 taxonomy。以下仅为供 Owner 下一轮评审的候选最小集合，
> 依据 SSOT §4（P0B 候选集合）+ 冻结 G1→G3 语义边界 + 本轮 59 段可见性实证。
> **未做**任何 VLM 试验，**未**预设 failed_grasp / slip / recovery 数量或可识别准确率。

### F.1 候选标签（单标签 + 可选结构化字段）

```text
motion_phase ∈ {
  APPROACH,           # EEF 向目标物体净接近
  GRASP_CONTACT,      # 夹爪闭合并与物体接触（含 candidate 语义）
  TRANSPORT,          # 物体随 EEF 移动
  RELEASE_PLACE,      # 夹爪张开、物体脱离
  RETRACT,            # EEF 离开物体区域
  IDLE_SETTLE,        # 无显著运动 / 段首尾静置
  UNCERTAIN,          # 证据不足（强制显式，禁止强行归类）
  OTHER               # 不属于以上受控集合
}

可选结构化字段（非首版必需）：
  object_relation ∈ { APPROACHING, AROUND, MOVING_WITH, RESTING_AFTER_RELEASE, MOVING_AWAY, UNKNOWN }
  gripper_semantic_state ∈ { OPEN, CLOSING, CLOSED_ON_OBJECT, OPENING, UNKNOWN }
  evidence_quality ∈ { CLEAR, OCCLUDED, OUT_OF_FRAME, LOW_RESOLUTION }
```

### F.2 不确定条件（何时**必须**判 `UNCERTAIN`）

1. 关键帧中目标物体**被遮挡**或**移出画面**（本轮实测：`demo_75` S0003/S0004 等）。
2. 段长 ≤4 帧且无 gripper 事件（本轮 19/59 段属此类）。
3. 只有"夹爪闭合"证据但**无可见接触**（不足以区分 GRASP_CONTACT 与空抓）。
4. 段边界附近发生释放，释放时刻不在段内（跨段问题，见 C.5）。
5. 分辨率不足以判定接触（128×128 下夹爪指宽 3–5 px）。

### F.3 典型正/负例（**均为候选，待 Owner 复核**）

| 标签 | 候选正例（本轮可见） | 候选负例 / 反例 |
|---|---|---|
| APPROACH | `demo_227` S0002 f4→f19（夹爪向罐接近，罐可见） | `demo_75` S0003（罐不可见）→ 不成立 |
| GRASP_CONTACT | `demo_33` S0002 f36（夹爪绕罐、闭合）→ **CANDIDATE_ONLY** | 无可见接触的闭合段 → 不可判 GRASP |
| TRANSPORT | `demo_33` S0003（EEF 位移显著） | 仅 `DIRECTION_CHANGE` 但 EEF 净位移≈0 → 应为 RETRACT/UNCERTAIN |
| RELEASE_PLACE | **未找到足够可见正例** → `INSUFFICIENT` | — |
| IDLE_SETTLE | 各集 `[0-3]` 前奏段、`MOVE_TO_IDLE` 段 | — |
| 失败/恢复（failed_grasp/slip/recovery） | **`INSUFFICIENT`，无正例** | **禁止**在无证据下预设计数 |

### F.4 DRAFT 状态标记

```text
PROPOSED_MINIMAL_TAXONOMY = DRAFT
OWNER_FREEZE              = NOT_REQUESTED_THIS_ROUND
G3_MVP_TAXONOMY           = PENDING_MINIMAL_FREEZE   (不变)
```

---

## G. 需 Owner 拍板事项 与 就绪判定

### G.1 需 Owner 决策（5 项，按优先级）

1. **PR 文档补齐的输入通道**：`P2_G3_Argus_Review_Package_v1.zip` 缺失且网络不可用。
   Owner 需决定：(a) 提供本地 ZIP；(b) 授权恢复网络后由执行侧 fetch；(c) 暂缓 PR #1 文档补齐。
2. **Argus 上游 commit 固定与许可**：需 Owner 指定 Argus 仓库 URL + 目标 commit SHA，
   并确认 Apache-2.0 归属/NOTICE 的落地方式（本轮**无法**记录，属 OPEN BLOCKER）。
3. **taxonomy 粒度与短段策略**：41% 段 ≤10 帧、20% 段为 `EPISODE_START` 前奏段。
   需决定：是否为短段设 `IDLE_SETTLE/UNCERTAIN` 兜底，或引入**段合并/最小段长**规则
   （后者会触及**已冻结 G1 边界**，须 Owner 明确授权方可讨论）。
4. **可见性不足的处置**：接触/释放/失败/恢复在 128×128 + 3–4 keyframe 下**不可靠**。
   需决定：是否 (a) 接受 `UNCERTAIN` 高占比；(b) 增设**更多 keyframe / 更高分辨率渲染**（须评估是否改动 RGB 契约）；
   (c) 引入**跨段上下文**（邻接段证据拼接）。
5. **首版范围裁剪**：建议首版 taxonomy **只做** `APPROACH / GRASP_CONTACT / TRANSPORT / RELEASE_PLACE / RETRACT / IDLE_SETTLE / UNCERTAIN / OTHER`，
   将 **任务结果**、**错误恢复**、**失败检测**后置（本轮无可见正例支撑）。需 Owner 确认。

### G.2 就绪判定

```text
READY_FOR_TAXONOMY_REVIEW = PARTIAL
```
- **可以**进入 taxonomy review 的部分：字段契约、时间对齐、renderer provenance、禁止字段边界、
  Development-pool 选样规则、EvidencePack 结构（均已实证）。
- **尚不足以**冻结 taxonomy 的部分：接触/释放/失败/恢复的**可见正例不足**；
  Argus 上游对照缺失；PR 文档缺失。
- 因此建议 Owner 先就 **G.1 的第 1、2、4 项**给出裁决，再进入 taxonomy freeze。

---

## 附：产物路径与哈希

```text
RUN_DIR = <worktree>/outputs/g3_phase1_probe/g3_phase1_probe_20261012/
  probe_selection_manifest.csv   sha256(前16) = 2aeb1ae1fd88cb36
  segment_audit_summary.csv      sha256(前16) = 4e39b45f4e4abfb7
  episode_audit_summary.csv      sha256(前16) = 58f66137e1e207d0
  phase1_probe_summary.json      sha256(前16) = 0cda32415da67d84
  development_pool.csv           sha256(前16) = 58b5cac7c4c67546
  evidence_packs/data__demo_*.json  (12 个)
VISUAL = <worktree>/outputs/g3_phase1_probe/_visual/data__demo_*_contact_sheet.png  (12 张)
CODE_COMMIT = 9bb28de  (branch p2-g3-local-ai-phase01-20261012)
```

---

## 人话总结

P2 的检索之所以暂停，是因为 18-query 的正式 Final Retrieval 还没跑，状态是 `HOLD_BY_OWNER`——既不是通过也不是失败，
而是等 Owner 对 G3/Argus 这条新支线拍板；这一轮我**没有**去动检索。

这一轮我**复用**了已经冻结的东西：G1 运动分段（A1-007-C002 那套配置）、MVP-M2 的关键帧与运动摘要、
以及 P1 的 RoboMimicStateRenderer 渲染栈，另加 63 条正式检索集和 32/24 条历史集的排除清单，
拼出了一个 181 条干净可用的 Development pool。

我**实际检查**了 12 条 episode、59 个 segment：帧对齐、RGB 来源、禁止字段、任务文本来源、动作语义，
并且把每个关键帧渲染出来做了接触表人工目视。好消息是对齐和来源全都干净——12 条 episode 重复渲染像素哈希完全一致，
0 个禁止字段漏入，Action 确实只是归一化控制器输入而不是物理速度。

**遇到的阻碍**有三个，都很硬：GitHub 完全连不上（代理 502、直连被重置），所以远端 main 的真实 SHA
无法权威确认、PR 分支也拉不下来；`P2_G3_Argus_Review_Package_v1.zip` 根本不在本地，
所以三份设计文档我**没有**写、也**拒绝**凭记忆补；Argus 上游源码同样不可得，
所以固定 commit SHA 和 Apache-2.0 归属要求这一轮**记录不了**。

**还不能对外宣称**的是：接触、释放、掉落、抓空、恢复这些细粒度事件，在 128×128 的 agentview 加
每段只有 3–4 个关键帧的条件下，**根本没有足够可见的真实正例**——很多帧里目标罐子被机械臂挡住或者已经出画，
所以我只能把它们标成 `INSUFFICIENT / CANDIDATE_ONLY`，不能假装看得见。

**下一步需要 Owner 决定**的主要是三件事：Argus 文档和源码怎么给我；短段（41% 的段不到 10 帧）
要不要合并或兜底；以及可见性不足要怎么处理（接受高 UNCERTAIN，还是加关键帧/提分辨率/加跨段上下文）。
本轮到此**停止**，等 Owner 审阅。
