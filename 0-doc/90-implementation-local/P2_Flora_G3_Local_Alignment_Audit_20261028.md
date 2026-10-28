# P2 Flora–G3 本地来源与局部 G1 对齐审计

日期：2026-10-28。开发数据诊断，不是独立测试或语义准确率评测。

## 结果

- PR #6 基线：`7c1bac1c27df7e57e8d0f8c67e6214230db7184c`，仍为 Draft；远端 main 为 `d416c02`。原 main 工作区有未跟踪文件，未修改；新建隔离 worktree，快进同步后在 `codex/flora-g1-local-audit` 开发。
- 找回 Downloads 中完整 Flora ZIP，15 JSON / 31 Segment，全部 Caption complete；不提取、不重写原 JSON。
- ZIP 前后 SHA256 均为 `b7a04298f69cd94dd2d0152a61e199631f42d52c70e54df396910233936f6cd7`。每份原 JSON 的哈希见 native_inventory.csv。
- 找回 Can/MH raw / low_dim HDF5，实际重算哈希分别为 `6f5a0e96fc375468ae19ccac86a6dee3b4d3862ef0fe37ca2d02e93d9046fe6b` / `c4a34c837913446d295c6ca38f2b31888d69812198478af470ecb84a99e9f7d7`，与历史审计及导出记录一致。
- 15/15 MP4 实际哈希与 Flora input_sha256.main、逐视频 metadata 一致。不是仅凭 demo 名称匹配。
- 在原 HDF5 中只访问指定 15 个开发 Episode 的 states/actions 形状；未读取其他 Episode 轨迹或独立测试集内容。
- 通过 CPU ffmpeg showinfo 实际解码 3,004 帧，逐帧取得 PTS；各视频从 0 开始、数量与对应状态及 action 数一致，均符合历史导出时间序列。没有以 time×20 推导来源身份。
- 导出脚本记录整段 STATE_t 按序渲染/读取 lossless RGB，再 raw RGB24 编码；相机 agentview、128×128、20Hz，无裁剪/变速步骤；main 角色通过匹配视频哈希绑定。14 条曾用 P1 lossless RGB HDF5，demo_2 曾走 P1 renderer fallback。历史 metadata 有冻结帧像素核验 PASS。本轮不重新渲染，也不将有损 MP4 当正式 Clean RGB。

## G1 覆盖边界

找到已提交的 `0-doc/10-design-review/evidence/P2_G3_Taxonomy_v0_2_20261013/sample_manifest.csv`，含每个指定 Demo 的一个既有 G1 target，共 15 个；边界原样使用。未为缺失部分计算新边界。

- 15/15 Demo 来源链核验完成；15/15 有可信局部 target 关联，**0/15 完成全轨迹 G1 对齐**。
- 31 Flora Segment 中 19 个与这些既有目标有真实映射帧交集，12 个在现有部分清单中无交集，标记未对齐；不能解释为真实不存在 G1 Segment。
- 已知目标覆盖 622/3,004 源帧；其余 2,382 帧不在已恢复 target 清单中。不能把缺失目标当成背景或空事件。
- Adapter 原候选状态保留；独立 `local_source_audit` 字段记录已核验的局部关联及清单哈希。全局 source_alignment_verified=false / alignment_blocked=true，避免误报完整 gate 通过。
- 本轮真实数据只证明局部映射；1:N、N:1 和半开时间边界的合成测试用于工程验证，不算真实全量对齐证据。

## 资产位置与重复执行

原数据目录：`C:/Users/95611/embody/1-dataset/robomimic/`。

视频与 metadata：主仓库 `.cindy-worktrees/p2-video-recovery-20261026/outputs/p2_video_recovery_20261026/`。

原导出代码：该 worktree 的 `scripts/recover_p2_argus_videos.py`（原代码只读，未运行）。

在本 PR 隔离工作区运行：

```powershell
& 'C:/Users/95611/miniconda3/envs/project1_robomimic_audit/python.exe' scripts/audit_flora_local_sources.py --flora-zip C:/Users/95611/Downloads/flora_native_all15_export.zip --recovery-dir C:/Users/95611/embody/4-Project2_data_value/.cindy-worktrees/p2-video-recovery-20261026/outputs/p2_video_recovery_20261026 --g1-targets 0-doc/10-design-review/evidence/P2_G3_Taxonomy_v0_2_20261013/sample_manifest.csv --export-script C:/Users/95611/embody/4-Project2_data_value/.cindy-worktrees/p2-video-recovery-20261026/scripts/recover_p2_argus_videos.py --output-dir outputs/flora_local_alignment_20261028
```

返回码 3 表示部分 G1 覆盖导致 gate 阻塞，不是对齐通过。完整本地证据保存在忽略目录 `outputs/flora_local_alignment_20261028/`：native_inventory.csv、alignment_audit.csv、flora_g1_links.jsonl、adapter_summary.json、action_taxonomy_gap_candidates.csv、recovered_source_mapping.json、local_evidence_audit.json。不提交 ZIP、MP4、RGB、HDF5 或完整运行输出。

## 分类只读审计

31 条 Caption 以 pick up / put 等意图描述为主，可提出 approach/grasp/lift/transport/place/retract 等多阶段候选，不能自动指定单一 G1 phase。候选 CSV 保留原 Caption，全部为 UNVERIFIED_CAPTION_ONLY。未检出 align/regrasp/rotate/push/handover/recovery 的直接词面证据；这不证明视觉中不存在这些动作，也不确认 taxonomy 缺口。没有用 Caption 生成视觉真值、成功结论或新枚举。other 表示清楚可见但不属于已有 phase，uncertain 表示证据不足；本轮未对其赋值，不存在已证实的混用结论。

## 工程修复与下一步

修复已有 Adapter 的门禁不一致：清单内部自洽时 source_alignment_verified 仍为 false，但原 alignment_blocked 可为 false、CLI 可返回 0；现改为保守阻塞。没有改动 G3 Schema/Validator、G1 边界或九类标签。

优先恢复这 15 条开发轨迹的完整历史 G1 Segment 清单，以及每个待推理 target 的 Clean RGB 与帧证据 manifest。已找到的 M2 final 清单属于历史其他 Episode，不可混用；不读取独立测试运行。可低成本从旧开发 worktree/备份找回相应输出。若确实未曾保存完整清单，应另行明确记录是否允许使用冻结 G1 函数确定性重放；本轮没有擅自以新分段替代已有资产。现有 HDF5 和 P1 lossless RGB/renderer 路径使恢复无需重新下载模型或大型数据。

正式 Qwen G3 推理准备停止，不改用 MP4 证据。没有 GPU、模型调用、训练或 main 合并。

P1_SOURCE_RECOVERY = COMPLETE

P1_G1_ALIGNMENT = PARTIAL

P2_ADAPTER_INTEGRATION = PARTIAL

G3_INFERENCE_READINESS = BLOCKED

## 最终验证

Adapter 8/8；包含 G3 v0.1/v0.2 合同和 G1 边界引擎的定向回归共 185 passed、1 skipped。真实审计重跑的 7 个输出文件逐字节一致；JSON 仍仅以 ZIP 原始成员和 SHA 引用。跳过项来自既有测试，不作为通过项。上述测试不替代真实 G1 全覆盖证明。
