# P2-G3 Phase 1B — 跨 Segment 上下文与视觉可观测性验证结果

- **任务**：`G3_CONTEXT_WINDOW_AND_VISUAL_OBSERVABILITY`
- **执行分支**：`p2-g3-phase1b-context-window-20261012`（基于 G3 审计分支 `21c9f9f9`，**未合并、未改 main**）
- **工作树**：`C:/Users/95611/embody/_p2_g3_phase1b_wt`
- **运行区间**：2026-10-12 23:47 → 2026-10-13 00:08（+08:00）
- **运行 ID**：`g3_phase1b_ab_20261012`
- **结论一句话**：在不改动任何冻结 G1 Segment 边界的前提下，跨 Segment 上下文可稳定、可复现地补上**紧邻边界的运动相位**（尤其是"释放/撤离"与"接近/闭合"），
  它**不是**万能补丁——对 4–6 帧的短段与"决定性转变本来就落在窗口之外"的段无增益；且**本轮未做人工打分**，
  因此"是否真的帮到人"目前只有**结构性证据 + 可审核材料**，没有人类读数。
- **本轮明确未做**：未调用任何 VLM；未冻结正式 taxonomy；未做 A/B VLM 推理；未开展 ACT 训练；未修改 G1 分段配置与冻结评测集。

---

## A. Git 与分支状态

| 项 | 值 |
|---|---|
| 仓库 | `Modori1998/embody_project2_data_value` |
| `main` 权威 HEAD（`git ls-remote`） | `b5fd9b97d1b32ffa98d6facd95bf663be12ac63e`（与上一轮一致，未变） |
| 设计分支 `design/p2-g3-argus-scope-20261012` | `bb711c0f9613da42e0a000695371826d2d7148e1`（Draft PR #1，**未合并**） |
| G3 审计分支 `p2-g3-local-ai-phase01-20261012` | `21c9f9f96f647a99af2d2824763e23c018ac1720` |
| 本任务分支 base | `21c9f9f96f647a99af2d2824763e23c018ac1720` |
| `merge-base(design, audit)` | `b5fd9b9` → 同源、历史兼容 |
| 本任务对 `main` 的改动 | **无** |
| 本任务对审计分支的改动 | **无**（新建独立分支，原分支原地不动） |
| 是否合并 PR | **否** |

执行动作：`git fetch origin` → `pull --ff-only origin main`（`Already up to date`）→
拉取两个既有分支 → 以审计分支 HEAD 为 base 新建 worktree + 独立分支。
因新 worktree 的 `outputs/` 为空（该目录被 gitignore），从主目录**只读复制**了 7 个历史清单，
否则 `build_development_pool` 会报 `FileNotFoundError`；**复制只读，未写入任何 Run 目录**。

> 说明：本轮**没有**把设计分支与开发分支做任何形式的合并，两者仅通过文档阅读建立上下文。

---

## B. Context Window 实现

### B.1 新增文件（全部独立于原 EvidencePack）

| 文件 | 作用 |
|---|---|
| `src/project2_g3/context_window.py` | Context Window 证据扩展 + 失败即停校验（核心交付） |
| `src/project2_g3/observability_ab.py` | A/B 可观测性对照材料构建（盲化面板 + 分析员面板） |
| `src/project2_g3/highres_probe.py` | 高分辨率渲染可行性只读探针 |
| `src/project2_g3/structural_delta.py` | 结构化证据增量（**明确标注为代理量，非人类真值**） |
| `scripts/run_g3_phase1b_ab.py` | A/B 构建只读 CLI |
| `scripts/run_g3_phase1b_highres.py` | 高分辨率探针只读 CLI |
| `tests/test_project2_g3_context_window.py` | 40 项测试 |

### B.2 证据策略（固定预算、确定性、无自适应）

```
CONTEXT_WINDOW_VERSION = "P2_G3_CONTEXT_WINDOW_V1"
CONTEXT_POLICY_NAME    = "PREV_END__TARGET_KEYFRAMES__NEXT_START_AND_MIDDLE"
MAX_PREV_CONTEXT_FRAMES = 1
MAX_NEXT_CONTEXT_FRAMES = 2
MAX_CONTEXT_FRAMES_TOTAL = 3
MIN_NEXT_FRAMES_FOR_MIDDLE = 4
```

对每个目标段，读取**同一 Episode 内**：
1. **前一段的 END**（`PREV_SEGMENT_END`，1 帧）；
2. **当前段的原始关键帧**（`TARGET_KEYFRAME`，沿用 `select_keyframes`，**原样复用，未改**）；
3. **后一段的 START**，以及**当后一段长度 ≥ 4 帧时**再取**后一段 MIDDLE**（`NEXT_SEGMENT_START` / `NEXT_SEGMENT_MIDDLE`）。

邻居不存在 → 记 `MISSING_NEIGHBOR`；**绝不跨 Episode 取帧**。

### B.3 关键契约：不污染原字段

原 `EvidencePack` 要求**关键帧必须落在目标段内**。本轮**没有**把跨段图像塞进原字段绕过该断言，而是：

- 新增**独立结构** `context_frames`（+ `context_frame_roles` / `segment_identity` / `neighbor_status` /
  `context_budget` / `target_keyframes`），**自带独立 allowlist** `ALLOWED_CONTEXT_FIELDS`；
- **保留**原"关键帧在段内"断言；
- **额外**校验跨段帧确实属于真实相邻段、方向正确、且**不得**被标记为段内帧。

每帧强制记录 8 个字段：
`source_episode_id` / `frame_index` / `pixel_sha256` / `target_segment_id` / `origin_segment_id` /
`evidence_role` / `is_target_segment_frame` / `renderer provenance`。

### B.4 校验器（失败即停，6 组）

(a) 目标段帧区间；(b) **段内断言仍然生效**；(c) 角色/来源/Episode/真假标志/方向/重复角色对；
(d) 证据预算；(e) `neighbor_status` 与实际帧一致；(f) 静态 + 动态 forbidden 字段审计。
另加 `audit_context_surfaces()` 对**实际输出面**做二次扫描。

**防"把后一段的行为错误归因到当前段"**：邻居帧一律 `is_target_segment_frame=False` + 独立 role + 独立颜色/标签，
且 `origin_segment_id != target_segment_id` 为硬校验；A 面板与 B 面板在视觉上明确区分（见 D 节图）。

---

## C. 59 Segment A/B 可观测性统计

样本：**12 个 Episode / 59 个 Segment**（沿用 Phase 1 的同一抽样，未重新抽）。

| 指标 | 值 |
|---|---|
| Episode / Segment | 12 / 59 |
| 目标段关键帧总数 | 177 |
| 上下文帧总数 | **141** |
| `PREV_SEGMENT_END` / `NEXT_SEGMENT_START` / `NEXT_SEGMENT_MIDDLE` | 47 / 47 / 47 |
| 缺前邻居（`MISSING_NEIGHBOR`） | 12（= 每 Episode 的首段） |
| 缺后邻居 | 12（= 每 Episode 的末段） |
| 两侧齐全 | **35** |
| 预算全部未超限 | ✅ `budget_within_limit_all = true` |
| 跨 Episode 取帧 | **0** |
| 邻居帧被误标为目标段帧 | **0** |
| 目标段帧被误标为邻居帧 | **0** |
| Clean RGB 契约违规 | **0** |
| 渲染失败 Episode | **0** |

**结构化证据增量（代理量，非人类真值）** —— `STRUCTURAL_PROXY_NOT_HUMAN_GT`：

| 指标 | 值 |
|---|---|
| 有夹爪行程增益的段 | 58 / 59 |
| 有末端轨迹增益的段 | 59 / 59 |
| **新增可判定的夹爪转变** | **0** |
| **丢失的夹爪转变** | **0** |
| 平均新增帧数 | 2.39 |
| 平均夹爪行程增益 | 0.0135 |
| 平均末端轨迹增益 | 0.1198 m |

> **必须如实说明**：夹爪"新增可判定转变 = 0"意味着——就**仪器量**而言，原段内关键帧已经足以覆盖夹爪状态变化；
> 上下文的价值**不在**"多出一个新的夹爪状态"，而在**把转变放进更长的运动语境**（前后相位）。
> 因此**不得**把上表当作"上下文提升了可观测性"的证明。

**人工读数**：`ab_review_sheet_UNSCORED.csv` 的 5 个维度
（`OBJECT_VISIBLE` / `MOTION_PHASE_DECIDABLE` / `GRIPPER_TRANSITION_VISIBLE` /
`OBJECT_FOLLOWING_DECIDABLE` / `RELEASE_DECIDABLE`）**全部为 `UNSCORED`（0 个已打分列）**，
`review_sheet_status = UNSCORED_PENDING_HUMAN`。**本轮不产出任何"通过率"**——因为没有人类读数，
任何比率都会是把启发式伪装成 Ground Truth。

**盲化设计**：每段按 `SHA256(salt|segment_id)` 的奇偶决定 A/B 呈现顺序（确定性、可复现、不显然），
盲化面板 `_visual/blinded/*__panel{1,2}.png` **无标题、无角色标签、无帧号**；
对照键 `ab_blinding_key_SEALED.csv` **单独封存**。若同一人先后看 A/B，仍存在记忆偏差，
建议独立评审或至少打乱段序——本轮**未**做，留作待冻结项。

---

## D. 典型成功与失败案例

### D.1 成功：`demo_33-S0003` [70–125] —— 释放/撤离只靠上下文才可见

- **A 面板（仅目标段）**：`START f70 +GRIPPER`（夹爪已夹住罐子）→ `MIDDLE f97`（抬升/横移）→ `END f125`（下降到料箱上方）。
  三段**都在"持物"状态内**，**看不到释放**。
- **B 面板（+邻居）**：前置 `<PREV END f69`（从上方接近罐子）+ 后置 `NEXT START f126>` / `NEXT MID f128>`
  （夹爪张开并撤离，罐子已落入箱内）。
- **增益**：`RELEASE_DECIDABLE` 从"不可判"变为"可判"；运动相位由"片段"变成"接近→抓取→搬运→释放"的完整闭环。
- **风险控制**：后置两帧以橙色边框 + `NEXT START/NEXT MID` 标签明确标注为**邻居段证据**，
  不进入目标段字段，不会被当作 `demo_33-S0003` 自身的行为。

### D.2 部分增益：`demo_75-S0003` [29–68] —— 抓取闭合落在边界上

- **A 面板**：机械臂高抬 → 下降 → 抵达罐子上方；闭合瞬间不在段内。
- **B 面板**：`<PREV END f28`（高抬）确认起点相位；`NEXT START f69>` / `NEXT MID f97>` 显示**接近并闭合**。
- **增益**：`GRIPPER_TRANSITION_VISIBLE` 由"不确定"变为"有邻证"。
- **残留问题**：128×128 下罐子仅占极小像素面积，**即使加了邻居帧，目标物体的可见性仍受分辨率限制**——
  这正是 E 节高分辨率动因。

### D.3 无增益（失败案例）：`demo_33-S0004` [126–131] —— 短末段 + 单侧邻居

- 段长仅 **6 帧**，`next_status = MISSING_NEIGHBOR`，只有 1 帧上下文（`<PREV END f125`）。
- **A 与 B 几乎无法区分**：夹爪已在箱内、罐子早已释放，决定性转变发生在**段开始之前**。
- **结论**：上下文窗口**不能**修复"证据缺口位于窗口之外"的段；也不应被当作短段策略的替代品。
  同理，`demo_33-S0001` 等 19 个 4 帧前奏段（`[0-3]`，`MISSING_NEIGHBOR`）属于同类。
- **这一条必须写进下一轮设计**：对 `duration ≤ 4` 或单侧缺邻居的段，应单独标注为
  `CONTEXT_INSUFFICIENT_BY_CONSTRUCTION`，而**不是**记成"上下文无效"。

---

## E. 高分辨率方案可行性

### E.1 只读核查结论

| 项 | 结论 |
|---|---|
| P1 Renderer 是否支持指定输出宽高 | **否** |
| 依据 | `RoboMimicStateRenderer.__init__(self, adapter)` 与 `.render(self, model_file, state)` 均**无** width/height 参数；`FORMAL_RGB_RESOLUTION = (128,128)` 是 `robomimic_adapter.py` 的模块常量 |
| 底层仿真器能否直接出更高分辨率 | **能** |
| 冻结 RGB 契约是否被改动 | **否**（`formal_rgb_contract_modified = false`） |
| 是否进入正式管线 | **否**（`fed_into_formal_pipeline = false`） |

关键约束：`canonicalize_raw_mujoco_rgb` 对任何非 128×128 的原生形状**直接 raise `RGBContractError`**（"resize is forbidden"）。
→ 因此**不能**用本地改常量绕过；高分辨率需要 **Owner 明确批准的契约变更**。

### E.2 实测（3 个样本帧，原生渲染，非插值放大）

| 分辨率 | 平均唯一颜色数 |
|---|---|
| 128×128 | 3957.7 |
| 256×256 | 8553.3 |
| 512×512 | **16713.3** |

`errors: []`；`resized_from_formal = false`（每张均为原生渲染）。
目视对照 `_compare_demo75_f97.png` 确认：512×512 下**夹爪两指、罐体标签、料箱分格边缘**均可分辨，
而 128×128 下这些结构糊成一团 —— 这是**真实新增信息**，不是 Resize 冒充。

### E.3 技术判断（建议，非决定）

1. **128×128 是当前可观测性的真实瓶颈之一**，尤其对"小目标 + 遮挡"场景；
2. 若 Owner 批准，**推荐 256×256 起步**（信息量约 ×2.16，算力/存储可控），
   512×512 仅在需要读罐体标签/细粒度夹爪姿态时按需启用；
3. 变更方式必须是**新增实验版本 + 独立输出目录**，`MODEL_RGB[t] = render(STATE_t)` 与索引对齐语义**保持不变**；
4. **不建议**用后处理放大替代原生渲染；
5. 本轮**未**提出正式变更提案，**未**修改任何冻结配置。

---

## F. 测试与远端提交

### F.1 测试

| 套件 | 数量 | 结果 |
|---|---|---|
| `tests/test_project2_g3_context_window.py`（新增） | 40 | ✅ 全通过 |
| `tests/test_project2_g3_probe.py`（Phase 1 原 18 项） | 18 | ✅ 全通过 |
| **合计** | **58** | ✅ |

覆盖 §5 全部要求：冻结 G1 段身份不变 / 邻居边界与方向正确 / 不跨 Episode 取帧 /
缺前段或后段正常处理 / 错误帧索引与重复角色不得污染输出 / 上下文帧不得被误标为段内帧 /
预算不超限 / 不引入 Privileged Fields / RGB 仍满足 Clean RGB Source Contract / 原 18 项继续通过。

**本轮新修的 2 个真实缺陷**（均已加回归测试）：
1. **A 面板为空**：早期版本用 `context_frames`（按设计**只装邻居帧**）构建 A 面板，导致 A 面板全空、
   B 面板却把邻居帧当段内帧展示。修复为按 `target_keyframe_indices` 构建，并抽成纯函数
   `build_panel_cells()` 便于直接断言。
2. **角色标签被裁掉**：标签文字画在 `_HEADER + _PAD + _CELL + 4`，而画布高仅 `_HEADER + _CELL + 2*_PAD`，
   文字落在画布外 → 分析员面板**看不见角色与帧号**。修复为新增 `_FOOTER` 带，
   并加测试断言页脚带内确实存在非背景像素。

### F.2 产物与提交范围

**允许提交（代码 / 测试 / 文档 / 小型非敏感 Manifest）**：
`src/project2_g3/{context_window,observability_ab,highres_probe,structural_delta}.py`、
`scripts/run_g3_phase1b_{ab,highres}.py`、`tests/test_project2_g3_context_window.py`、
本报告、`G3_Context_Window_Observability_Manifest_20261012.csv`（59 行逐段审计）、
`G3_Context_Window_Frame_Provenance_20261012.csv`（141 行逐帧来源）、
`G3_Context_Window_Structural_Delta_20261012.csv`（59 行结构化代理量）。

**不提交（保持本地）**：`_visual/analyst/*.png`（59）、`_visual/blinded/*.png`（118）、
高分辨率 PNG（9）、`_compare_*.png`、`ab_blinding_key_SEALED.csv`（盲化对照键单独封存）。

**本地保留路径**：
```
outputs/g3_phase1b_ab/g3_phase1b_ab_20261012/           # A/B 全量产物
outputs/g3_phase1b_ab/_superseded_buggy_panel_A_20261012/   # 缺陷版留档（未删）
outputs/g3_phase1b_ab/_superseded_label_clipped_20261012/   # 缺陷版留档（未删）
outputs/g3_phase1b_highres/g3_phase1b_highres_20261012/     # 高分辨率探针
```

**复现命令**：
```bash
PY=C:/Users/95611/miniconda3/envs/project1_robomimic_audit/python.exe
$PY scripts/run_g3_phase1b_ab.py --output-root outputs/g3_phase1b_ab --run-id <RUN_ID>
$PY scripts/run_g3_phase1b_highres.py --output-root outputs/g3_phase1b_highres --run-id <RUN_ID>
$PY -c "import sys;sys.path.insert(0,'src');from project2_g3.structural_delta import compute_structural_delta as f;print(f('outputs/g3_phase1b_ab/<RUN_ID>'))"
$PY -m unittest tests.test_project2_g3_context_window tests.test_project2_g3_probe
```

---

## G. Owner 下一步需要冻结的决策

1. **Context Window 是否作为正式 G3 VLM 输入**（本轮结论：**建议作为可选输入，但不建议无条件默认开启**，
   见下方人话总结）。
2. **跨段上下文规则**：是否接受 `PREV_END(1) + NEXT_START(1) + NEXT_MID(≤1)` 这一固定预算；
   是否需要双向对称（如 `PREV_MID`）；总预算上限是否维持 3。
3. **短段/单侧缺邻居的处置**：是否新增 `CONTEXT_INSUFFICIENT_BY_CONSTRUCTION` 标记，
   并在统计中**从"上下文有效/无效"分母中剔除**（否则会系统性低估上下文价值）。
4. **高分辨率**：是否批准新增实验渲染版本；起步取 256×256 还是 512×512；
   契约变更范围（仅新增实验版本 vs 修改 `FORMAL_RGB_RESOLUTION`）。
5. **可观测性 rubric**：5 个维度的 `SUFFICIENT/PARTIAL/INSUFFICIENT` 判据文字定义、
   失败原因码（`OCCLUSION`/`OUT_OF_FRAME`/`TEMPORAL_GAP`/`OTHER`）的判定标准。
6. **人工评审协议**：是否强制独立评审（本轮仅做了盲化顺序 + 封存键）；
   样本量（本轮 59 段为可行性样本，**不构成统计显著性**）；是否需要在 A/B 之外加"仅上下文"对照 C 臂。
7. **标签范围**：下一轮允许冻结的标签集合 —— 建议**先冻结** `MOTION_PHASE` 与
   `GRIPPER_TRANSITION`（本轮证据最充分），**暂缓** `OBJECT_FOLLOWING` / `RELEASE`
   （受 128×128 分辨率限制，需先定高分辨率方案），**不冻结** `success/goal_reached` 一类需要真值的字段。
8. **taxonomy 取值**：Argus 的 `state_changes` / `recovery[]` / `DATA_ISSUE_TAGS`(11) /
   `OPERATOR_MISTAKE_TAGS`(9) 在 P2 Can/MH 上**具体保留哪些**——Argus 是通用任务设计，
   P2 只有单一 `PickPlaceCan`，需裁剪。
9. **Qwen3-VL 精确 revision** 与 A/B 队列样本量、C/D 启动判据、Gate 数值阈值。

---

## 人话总结

原来的"3–4 张关键帧"只覆盖**目标段自己**，而 G1 的分段边界是机械切出来的：
一段常常在"刚夹住"或"刚松手"的那一刻**就结束了**。于是审核者看到的三张图往往全在"持物"状态里，
**看不见它是怎么抓起来的、又是什么时候放下的**——不是没拍，是切在窗口外面了。
这一轮我们**没有动任何已有的分段边界**，只是给每一段额外配了几张"邻居的边界帧"：
前一段的最后一帧、后一段的第一帧（后一段够长时再加一帧中段），
并把它们和目标段的关键帧**分开放**（独立的 `context_frames` 结构 + 独立校验 + 面板上橙色边框与
`<PREV END / NEXT START / NEXT MID>` 标签），从机制上避免把"下一段的行为"算到"当前段"头上。
59 个段跑下来：**141 张上下文帧、0 跨 Episode、0 误标、0 预算超限、0 RGB 契约违规**，
58/59 段拿到更大的夹爪行程、59/59 段拿到更长的末端轨迹；
在 `demo_33-S0003` 这类段上，**"释放"这个动作确实只有加上后一段的两帧才看得出来**。
但它**不是万能药**：仪器量上"新增可判定的夹爪转变 = 0"，说明它补的是**运动语境**而不是新的状态；
对 4–6 帧的短段、或者决定性转变本来就落在窗口之外的段（`demo_33-S0004`），它基本无效。
另外必须诚实地说：**这一轮没有任何人类打分**，审核表 5 个维度全是 `UNSCORED`，
所以"是否真的帮到人判断"目前只有结构性证据和一份可直接看的盲化材料，**没有人类读数**。
因此建议：**把 Context Window 作为 G3 的可选输入而不是默认输入**，
优先在"中等长度段 + 双侧邻居齐全"上启用；同时把 128×128 视为另一个真实瓶颈——
实测原生渲染 256/512 能多出一倍以上的颜色信息，夹爪两指和罐体标签才开始可分辨，
但这需要 Owner 批准契约变更，不能本地改常量绕过。

---

## 本轮停止点

以上为 Phase 1B 全部产出。**未进入下一阶段**：
未调用 VLM、未冻结 taxonomy、未做 A/B VLM 推理、未启动 ACT 训练、未合并任何 PR、未修改 `main`。
