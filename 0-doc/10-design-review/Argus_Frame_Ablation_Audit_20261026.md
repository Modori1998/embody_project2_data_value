# P2 Argus：3/6/12 帧实验现场审计（2026-10-26）

本报告保留首次只读审计时点。用户后来确认34格矩阵，输入准备及Pilot已执行；后续状态以 [Pilot结果](Argus_Frame_Ablation_Pilot_Results_20261026.md) 为准：工程门失败，正式集未运行。

状态：`AUDIT_COMPLETE / DESIGN_REVIEW_REQUIRED`。本轮模型调用 0、权重下载 0、新 RGB 渲染 0。本报告区分 GitHub 已跟踪证据、本地重新核验和仍未知项；不修改历史结论。实施方案见 [Argus_Frame_Ablation_Plan_20261026.md](Argus_Frame_Ablation_Plan_20261026.md)。

## 工作树与 SSOT

初始主工作树为 main@5b18a39，存在两个未跟踪条目：`.cindy-worktrees/`、`0-doc/Project2_G1_Audit_Web_Local_Structure_Audit_20260916.md`；无已跟踪文件修改。读取 WinINET 当前代理 `127.0.0.1:10808` 后，以命令级 `http.proxy` fetch origin main 成功，未改变全局网络配置。main 落后 11 commits、领先 0，以 `merge --ff-only origin/main` 同步到 `d561f98e9be6c6e7e4652e07e7839df40326a8d2`，两个未跟踪条目保留。

独立工作树 `.cindy-worktrees/argus-frame-ablation-20261026`，分支 `exp/argus-frame-ablation-20261026` 从该 origin/main 创建。用户本次明确要求隔离实验，故本分支只承载本轮交付，不改已有分支、M07/M11/P2 冻结文件。未连接蓝耘云、未访问 Flora 目录和缓存、未启动 GPU 服务。

## 精确模型与后端

GitHub 证据：`G3D2_R_Results.md`、`G3F_P1_Plan.md`、`G3F_P1_Results.md`、`scripts/run_g3f_p1_paired.py`。本地证据：主工作树 `outputs/g3f_p1/full_r1/{run_manifest.json,inputs.jsonl,responses.jsonl,per_segment.jsonl,scores.json,summary.json}`，仅只读访问，不提交原始请求和个人 CSV。

| 项目 | 恢复结果 |
|---|---|
| 官方 checkpoint | `Qwen/Qwen3-VL-4B-Instruct-GGUF@1cd86afb9a95c410a6038ab3b40d8b578c892266` |
| LLM | `Qwen3VL-4B-Instruct-Q4_K_M.gguf`，Q4_K_M |
| LLM SHA256 | `66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a` |
| 视觉投影 | `mmproj-Qwen3VL-4B-Instruct-F16.gguf`，F16 |
| mmproj SHA256 | `256f3a43bd4205ffef48d6b92715e1e70b5b0e9aef06522584967513a9985331` |
| 后端 | llama.cpp `0.6.0-dev`，build `11577`，commit `cbe28bb3c` |
| 历史配置 | ctx 4096、temperature 0、seed 1234、max_tokens 512、stream false |
| 输出模式 | G3F-P1：`response_format={"type":"json_object"}`；独立 Validator，非 schema-constrained decoding |
| 历史重试 | `fallback_json_object_retry_v1`；结构尝试上限 2、服务尝试上限 3 |

本轮逐字节重新计算 `_local_vlm_deploy/models/` 中上述两个文件的 SHA256，均匹配。历史 `logs/server_g3f_p1.log` 证实 build、37/37 层 GPU offload、n_ctx=4096、n_batch=2048。完整历史启动命令、所有未显式记录的后端默认值和当前可执行文件哈希尚未恢复；不得将部分日志冒充完整启动参数。后续启动前需记录 executable SHA256、完整 argv 和有效配置。

## Prompt、Schema、Validator 与输入

历史有多个三帧协议，不能混用：G3D2-R G0 使用 v0.2.1；G3F-P1 A/B/C 分别为 v0.2.1/v0.2.2/v0.2.3。最新 main 还有 G3G 的嵌入 Schema 解码及 G3H 两阶段实验；均不作为此次直接替代协议。

本次方案建议固定 G3F-P1 C 的 v0.2.3，不恢复已知错误语义，不在帧数臂之间改 Prompt。模板在 `src/project2_g3/semantic_prompt.py`，`prompt_version_info('v0_2_3')` 实测 SHA256 为 `cb9fa472a27332bb39ba37d373edfd7c3b361217137972a0553f9171ba7373c1`。Schema 在 `semantic_schema.py::json_schema_v0_2()`，以历史 `json.dumps(sort_keys=True, ensure_ascii=False)` 规则散列，实测为 `4cbec780693511c6e029a1fc005a7c523e5af7ea6a4ba127c7b9fc44253d0ad7`。Validator 在 `semantic_validation.py`，`FrameEntry` 记录实际 frame_index/来源/目标区间/pixel SHA，`ValidationResult` 分开返回 schema_ok 与 frame_evidence_ok；QC 不改模型答案。评分为 `g3d_paired.py::score_pairs` 的三类多标签事件集合，不使用旧单事件列替代。

冻结清单：`evidence/P2_G3_Taxonomy_v0_2_20261013/sample_manifest.csv` 的 `cohort=microset` 12 行。三帧为 START、floor((start+end)/2)、END；对应 `src/project2_mvp/m2.py::select_keyframes`。历史 `verified_frames` 仅接受三帧，后续须另写多帧输入检查，不修改旧函数。

历史 PNG 缓存：`C:/Users/95611/embody/_local_vlm_deploy/rgb_g3_v02/g3_taxonomy_v02_20261013`。本轮 36/36 PNG SHA256 与冻结清单匹配，读取 PNG header 确认 128×128。模型输入为同一 user content 中的 text + 多个 `image_url` data URI，无视频、拼图、Overlay、额外 Robot State 或 Can Position。新增帧应复用 `materialize_g3_vlm_rgb_frames.py` 和 `project2_mvp/rgb_input.py` 的 Clean RGB 路径，`MODEL_RGB[t]=render(STATE_t)`，不从审计视频裁图。

## 冻结样本与人工真值

正确人工文件已定位：`C:/Users/95611/Downloads/G3C_12_Segment_Human_MultiEvent_Reference_v2.csv`，20 列、12 行，SHA256 `ecc716860eaf7617e00c1b23812fb1394a2719851346580a24e057a7e1ac938c`。本轮逐行核对 episode、segment、区间、原始 frame ID、PNG hashes，并比对历史 G3F-P1 `per_segment.jsonl` 的 phase 和多事件真值，12/12 一致。备份目录中的两份 16 列旧版 CSV 不是本实验金标，不应误用。个人姓名、解释、完整 CSV 留在本机。

| Segment | 区间（含端点） | 原始 frame ID | 人工 phase | 人工事件集合 |
|---|---|---|---|---|
| demo_2-S0003 | 63–106 | 63;84;106 | transport | grasp_attempt;object_motion |
| demo_4-S0003 | 69–136 | 69;102;136 | transport | grasp_attempt;object_motion |
| demo_28-S0003 | 14–62 | 14;38;62 | approach | grasp_attempt |
| demo_180-S0001 | 0–3 | 0;1;3 | idle | 空 |
| demo_159-S0003 | 81–150 | 81;115;150 | transport | grasp_attempt;object_motion |
| demo_169-S0002 | 4–28 | 4;16;28 | approach | 空 |
| demo_172-S0004 | 166–169 | 166;167;169 | place | release_attempt |
| demo_232-S0002 | 4–49 | 4;26;49 | approach | 空 |
| demo_71-S0003 | 34–106 | 34;70;106 | approach | grasp_attempt |
| demo_72-S0002 | 4–88 | 4;46;88 | approach | 空 |
| demo_183-S0003 | 67–104 | 67;85;104 | grasp | grasp_attempt |
| demo_216-S0002 | 4–70 | 4;37;70 | approach | grasp_attempt |

**设计阻塞：demo_180 与 demo_172 各只有 4 个原始时间点。** 保持冻结范围且使用不同原始帧时，6/12 帧数学上不可实现。不能静默复制、插值、扩区间、换样本或删两条后仍报告 12 条结果。CPU 草案 `evidence/Argus_Frame_Ablation_20261026/frame_schedule_draft.json` 的 36 格有 4 格显式 `STOP_INSUFFICIENT_UNIQUE_FRAMES`；它只是时间点计划，不是实际图像输入清单。

## 三个历史漏检的证据与原因边界

G3D2-R 五臂的三例 object_motion 均 FN；G3F-P1 A/C 同样 0/3 TP，B 找回 demo_2、demo_159 但增加 FP，不能当成视觉证据不存在的证明。本轮读取历史逐条记录，C 的三例都只预测 grasp_attempt，说明分别是桌面/桌面/托盘上“未见明显位移”。历史 C 总计 object_motion TP=0、FP=2、FN=3；这是历史数据，不是此次消融结果。

最新 GitHub `G3G_Development_Results.md` 和 `G3H_P0_Failure_Audit.md` 已提供更强限定：demo_2/4 的物体横移可见，demo_159 也有位移；Task A 与 Task B 出现判断不一致。该审计的 OBSERVED 为既有报告证据，本轮未重新做独立图像盲审。demo_2 存在对象/方向混淆候选；demo_4 的跨任务证据选择不一致更直接；demo_159 有任务间判断变化且抓取边界可能含歧义。视觉注意、证据提取、语义映射和时间采样仍未被因果分离。新增中间帧是否改善是受控假设，不能预先认定“原三帧无运动信息”。

## 已知缺口与执行前门槛

- 新增帧尚未渲染，故其 PNG/pixel hashes、图像合法性及真实维度尚无数值；不得填写为已验证。
- 原始 raw/low_dim HDF5 和只读 renderer Python 路径存在，但本轮未打开 HDF5 核验内部状态/时间轴，未运行 renderer。复用渲染前须核验来源冻结身份、相机和尺寸，保留 provenance。
- G1 配置为 20 Hz、nominal_dt=0.05 s。草案 timestamp=i/20 是控制时钟的名义秒数，不是视频 PTS；采集真实时间戳未恢复，不能冒充实际视频时间。
- 每请求实际视觉 token 数、6/12 帧显存峰值及延迟均未知。总 prompt_tokens 不能当视觉 token。历史约 18 token/128×128 图的记录不代替本轮测量。
- 完整启动 argv、当前 backend 二进制哈希、GPU 空闲状态与 Flora 当前运行状态未核实。未触碰云资源；不能声称已确认 A100 空闲。
- 新 worktree 不自动包含 gitignored outputs。后续尽量直接消费已冻结清单与只读数据源；若依赖历史 G1 构造清单，须显式核对所需文件并只读复制到新的输出区域，不能通过重跑冻结流程补齐。

本阶段可交付审计和设计；目前不能执行严格的 12×3 个独立原始帧对比，需用户先裁定短片段处理方式。
