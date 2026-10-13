# P2-G3 — Phase 1B/1C Context Window 与人工可观测性冻结记录（2026-10-13）

> **记录类别**：Owner 决定 + Development 证据快照（不可回填、不可静默改判）
>
> **状态**：`PHASE1B_ENGINEERING_EVIDENCE=FROZEN_SNAPSHOT`；`PHASE1C_OWNER_HUMAN_SCORES=FROZEN_10_OF_10`；`CONTEXT_POLICY_DECISION=KEEP_CONTEXT_OPTIONAL`。
>
> **冻结边界**：本文件冻结的是**此次开发阶段人工审核的原始评分、评分定义、证据口径和“上下文先作为可选输入”的暂定工程选择**；不构成 G3 正式语义 taxonomy、VLM 模型版本、正式视觉输入或 Held-out A/B 评测协议的冻结。
>
> **来源**：Owner 于 2026-10-13 提交人工审核 CSV，并要求将最近讨论的技术细节和评分冻结到 GitHub SSOT。下方 CSV 行是原始人工回答，不是 AI 补标。

## 1. 关联的 GitHub 证据（固定来源）

| 层次 | GitHub 来源 | 已证明/没有证明什么 |
| --- | --- | --- |
| G3 设计与治理 | `design/p2-g3-argus-scope-20261012`；`P2_G3_Argus_Design_v1_20261012.md`、`Plan`、`Output_Design` | G3 优先级；Retrieval v1 `HOLD_BY_OWNER`；正式 taxonomy 与推理配置尚待冻结 |
| Phase 1 工程审计 | `p2-g3-local-ai-phase01-20261012` @ `21c9f9f96f647a99af2d2824763e23c018ac1720` | 12 Episode / 59 Segment；对齐、字段泄漏与 RGB provenance 的小样本工程检查；18 项测试本地报告 PASS |
| Phase 1B 工程与对照材料 | `p2-g3-phase1b-context-window-20261012` @ `ad3f71121bdc35f27ee905ee3a693319ca536e4f` | 上下文取帧与独立证据结构；59 Segment、141 上下文帧、177 目标帧；58 项本地测试报告 PASS；**无人工评分** |
| Phase 1C 轻量审核工具/选样 | `p2-g3-phase1c-human-observability-20261013` @ `8989cf0f030374370ea15c2ad3b4974c8e4d0163` | 10 条结构化选样、轻量页面、初始 `UNSCORED` 模板；64 项相关测试本地报告 PASS；原分支文档 `PENDING_HUMAN_REVIEW` 是**评分前快照** |
| 此次 Owner 真正评分 | [原始人工 CSV](evidence/P2_G3_Phase1C_Simple10_Owner_Scored_Raw_20261013.csv) | 本次审核后的原始数据；10 行完成，且唯一；后续任何重评都应生成新版本，不能覆盖它 |

**原始 CSV 保真**：上传源文件 `csv.csv`，8 列、10 数据行、CRLF 换行；源文件 SHA-256 = `d70364f96fd8f582bd8280a817045b5b5957acdd2a9afc7b1bf9b7e1602ebbce`。GitHub 保存同内容的不可变证据副本；文件名改为有含义的证据名称。评分时间字段为 UTC（以原 CSV `Z` 时间保留）。

> 评分模板和打分前报告仍是历史证据，不得用新结果无痕覆盖 `UNSCORED` 模板。这里的 Owner 评分是后续 closeout 层，而不是宣称开发工具在提交时已存在人工结果。

## 2. Phase 1B 视觉输入协议与工程事实

- Frozen G1 Segment 是 `[start_frame,end_frame]` **包含两端**的单位；`source_episode_id`、`segment_id`、边界及 G1 配置不可变。G1 是**运动分段**，不是 VLM 语义分段。
- **输入 A / Target-only**：当前 Segment 的 M2 `START/MIDDLE/END`，以及适用时的 `GRIPPER_EVENT` 去重关键帧。Phase 1B 统计：59 段共 177 张。
- **输入 B / Target + Neighbor**：A 加上同一 Episode 邻段帧 `PREV_SEGMENT_END`（至多 1）+`NEXT_SEGMENT_START`（至多 1）+`NEXT_SEGMENT_MIDDLE`（当后段长度满足条件；至多 1）；**额外上限 3 帧**。Phase 1B 统计 141 张（PREV_END / NEXT_START / NEXT_MIDDLE 各 47）；缺前邻 12 段、缺后邻 12 段、双侧有邻 35 段。
- 额外图像进入**独立 `context_frames`**，不改变原 EvidencePack 段内 Keyframe 契约；每帧记录源 Episode、Frame、像素 SHA、目标 Segment、来源 Segment、角色及 `is_target_segment_frame=false`。没有跨 Episode 取帧，也未把邻段帧冒充为目标段帧（按 Phase 1B 报告）。
- Clean RGB 仍是原有的 128×128、无文字/遮罩、直接基于渲染状态生成；不得将模拟器 `reward/done/object GT/states` 等特权字段作为 VLM 证据。渲染底层可以原生输出 256/512，但正式 P1/P2 RGB Contract 目前不支持直接替换，**高分辨率仅是技术可行性探针，未经批准不能修改冻结契约**。
- 短段风险：Phase 1B 的 59 段中 24 段 `duration<=10`（约 41%）；相邻帧可能恢复运动语境，但不能凭此证明物体接触/抓取成功/掉落/恢复事件可观察。
- 跨段规则：**邻段发生的行为不能计为目标 Segment 发生的行为**；上下文只用于解释目标段，不用于延展它的时间标签。
- Phase 1B 的 `STRUCTURAL_PROXY_NOT_HUMAN_GT`（夹爪行程、末端轨迹范围变化）只用于解释新增物理时间覆盖，不是人工可观察性改善率或模型准确率。

## 3. Phase 1C 极简人工审核协议（本次冻结）

抽样：Phase 1B 的 59 个 Segment 中，按 `P2_G3_PHASE1C_SIMPLE10_20261013_V1` 确定性选 10 个，每个来自不同 Episode；来源为 Phase 1C 分支 `0-doc/90-implementation-local/review_selection.csv`。覆盖：短段 4、普通段 6；首段 2、末段 2；双侧邻段完整 6、缺一侧 4。按结构字段选样，未按看到的 A/B 效果挑选。

**评分流程**：先展示 A，审核者回答后才展示 B，然后回答限制原因。复用 Phase 1B 本地图片，A/B 保持时间顺序并标明邻段的辅助身份；没有 VLM 调用。此次不是正式双盲人工 Ground Truth，也没有多人一致性检验。

三个通俗问题（不要求标注具体 grasp/release 标签）：
1. **A：只看目标 Segment 的原始图片，能看懂机器人在做什么吗？** `CAN/UNCERTAIN/CANNOT`（能/不确定/不能）。
2. **B：增加前后 Segment 图片之后，现在能看懂目标段动作吗？** 相同三档。
3. **主要限制**：`MISSING_ACTION_CONTEXT`（缺前后动作）、`LOW_RESOLUTION`（分辨率低）、`OCCLUSION_OR_OUT_OF_FRAME`（遮挡/出画）、`OTHER`（其他）、`NONE`（无明显问题）；以实际原始枚举为准。

提升的仅是**单人主观动作可理解性**，不得叫作语义标签正确率、VLM 提升或统计显著性。

## 4. Owner 10 行原始人工评分（与 CSV 逐行对应）

| Episode / Segment | A | B | 主要限制 | 变化 |
| --- | --- | --- | --- | --- |
| `demo_120-S0005` | CAN | CAN | NONE | 持平 |
| `demo_165-S0003` | CAN | CAN | NONE | 持平 |
| `demo_196-S0002` | CAN | CAN | NONE | 持平 |
| `demo_227-S0005` | CAN | CAN | NONE | 持平 |
| `demo_277-S0005` | CAN | CAN | NONE | 持平 |
| `demo_292-S0002` | CAN | CAN | NONE | 持平 |
| `demo_33-S0001` | CANNOT | CAN | MISSING_ACTION_CONTEXT | 改善 2 档 |
| `demo_47-S0003` | CAN | CAN | NONE | 持平 |
| `demo_74-S0003` | CANNOT | CAN | MISSING_ACTION_CONTEXT | 改善 2 档 |
| `demo_75-S0001` | CANNOT | UNCERTAIN | OTHER | 改善 1 档 |

原始结果没有附加 `review_notes` 文本；每行 `status=COMPLETE`。所有具体时间戳保留在原始 CSV，未另行补造时间。

## 5. 预先确定的评分规则与实际统计

- 顺序：`CANNOT < UNCERTAIN < CAN`，每个 Segment A/B 成对比较。
- 样本数量 = 10；已完成 = 10；跳过/缺失 = 0；不同 Episode = 10。
- A：`CAN=7, UNCERTAIN=0, CANNOT=3`。
- B：`CAN=9, UNCERTAIN=1, CANNOT=0`。
- **改善 = 3/10（30%）**；其中 `CANNOT→CAN=2/10`、`CANNOT→UNCERTAIN=1/10`。持平 `7/10`；退化 `0/10`。
- 如果只数从“弱判断”升到明确 `CAN`：`2/10`，不要和 3/10 全部改善混为一谈。
- 局限类别（Owner 原始作答）：`NONE=7`、`MISSING_ACTION_CONTEXT=2`、`OTHER=1`。没有任何评分将本轮失败归因为 `LOW_RESOLUTION`，不代表 128×128 没有分辨率瓶颈；Phase 1B 的高分辨率探针是独立工程观察。
- **4 条短段中 2 条改善**（`demo_33-S0001`、`demo_75-S0001`，均 4 帧的 Episode 首段）；**6 条非短段中 1 条改善**（`demo_74-S0003`，17 帧）；两条末尾短段保持 CAN→CAN。
- 样本非概率外推的小型 Development 审核，不能推出整 181 Episode、正式 G3、VLM 的真实提升率或统计显著性。

## 6. Owner 决策与执行边界（冻结）

```text
OWNER_REVIEW_COMPLETED = YES
PHASE1C_REVIEW_STATUS = CLOSED_WITH_OWNER_SCORES_10_OF_10
CONTEXT_POLICY_DECISION = KEEP_CONTEXT_OPTIONAL
CONTEXT_DEFAULT_FOR_FORMAL_VLM = NOT_YET_FROZEN
G3_MINIMAL_TAXONOMY = PENDING_FREEZE
VLM_CHECKPOINT_REVISION = PENDING_RUNTIME_PIN
FORMAL_AB_HUMAN_GT_AND_HELDOUT = NOT_STARTED
RETRIEVAL_V1 = HOLD_BY_OWNER
ACT_VLA_TRAINING = OUT_OF_SCOPE_G3_V1
```

**解释**：Context Window 在部分 Segment 上确实让 Owner 更容易理解动作，但 7/10 个案例 A 已可理解且 B 不改变结果。因此**保留上下文能力，暂作为可选额外证据，不强制所有段默认使用**。不批准“上下文提高 VLM 语义准确率”的结论，也不在这里创造未经验证的自动触发阈值。

**不能把`邻段看到了 release`误标成`目标段发生了 release`。** B 帮助理解并不自动改变目标标签的时序边界。

正式多模态消融必须单独设计：正式 **A/B（Vision-only / Vision+Robot State/Action）** 与本轮**可观测性 A/B（Target-only / Target+Neighbor）** 是两种不同对照，不能混淆。

## 7. 下一步冻结顺序与停止条件

1. **Phase 1C 已结束**：不再为了输入可行性无限扩大人工审核、不追加事后挑选“改善案例”改写本结果。
2. **最小 Taxonomy Freeze（待 Owner 另行批准）**：优先提案 `approach`（接近）、`grasp_attempt`（尝试抓取）、`transport`（搬运）、`place`（放置）、`retract`（撤离）、`idle`（空闲）、`uncertain`（无法确定）；这些是候选值，不是本文件冻结的正式标签。细粒度 `failed_grasp/slip/recovery/task_completed` 不作为默认必达主指标。
3. **Tiny VLM Baseline（待正式配置）**：先固定模型的精确 checkpoint/revision、Prompt/Schema、可用 RGB 与状态证据、输入预算和约 8–12 条探索性样本；评估模型输出解析和人能否核验的基本能力。小样本推理是可行性基线而非正式 Held-out。
4. **正式实验另行冻结**：Episode-disjoint human reference 与 Calibration/Held-out、指标、停止条件、潜在高分辨率实验和 A/B 模态差异都应在正式评测前独立冻结。未测到足够可观察的失败正例，不得宣称失败/恢复检测性能。
5. **工程保护**：主仓库 `main` 合并的只能是设计与历史审核证据；Phase 1/1B/1C 开发代码仍在独立分支，未经单独审阅不得以“文档冻结”为名一并合入。Frozen G1/M2/Retrieval 保持不变。

## 8. 可复现实验与诚实边界

- Phase 1B 代码：`src/project2_g3/context_window.py`、`observability_ab.py`、`structural_delta.py`、`highres_probe.py`（在 Phase 1B 开发分支）；测试：`tests/test_project2_g3_context_window.py`。
- Phase 1C 页面与结果工具：`scripts/run_g3_phase1c_simple.py`、`scripts/report_g3_phase1c.py`（在 Phase 1C 开发分支）。小型选样 Manifest 已提交；图片/视频/盲化钥匙及原始机器人大文件未提交 GitHub。
- 此次上传的人工 CSV 是 Owner 提供的原始评分记录；本文件只做可检查的确定性计数和决策登记，没有重新评分任何图片。
- 如果以后有额外审核者或新模型评估，请写 `v2` / 新文件，并保留本次 v1 原始证据。
