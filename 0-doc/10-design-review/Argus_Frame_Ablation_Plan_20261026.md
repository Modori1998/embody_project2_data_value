# P2 Argus：3/6/12 帧实施方案（待确认，2026-10-26）

此文保留最初提交的设计草案。用户随后确认推荐的34格方案；执行前修订与事件见 [Execution](Argus_Frame_Ablation_Execution_20261026.md)，实际Pilot及停止结论见 [Pilot Results](Argus_Frame_Ablation_Pilot_Results_20261026.md)。未选择的方案均未执行。

状态：`DRAFT / NO_INFERENCE_AUTHORIZED_THIS_STAGE`。已完成工作见 [现场审计](Argus_Frame_Ablation_Audit_20261026.md)。先提交本方案供审阅；本轮不下载权重、不加载模型、不跑 Pilot 或正式集。CPU 草案不是可执行授权或实验结果。

## 唯一干预与固定项

检验同一模型在同一冻结 Segment 内增加时间采样点，是否减少 object_motion FN。固定 Qwen3-VL-4B 官方 revision、Q4_K_M GGUF、F16 mmproj（精确 SHA 见审计）、llama.cpp build 11577、同一 GPU/offload/ctx4096 和全部有效服务参数；固定 v0.2.3 Prompt 模板、v0.2 Schema、Validator、temperature=0、seed=1234、max_tokens=512、stream=false、json_object 及既有重试协议。选择 v0.2.3 是保留历史最小语义修复，G3D2-R v0.2.1 仅作历史背景；三个新臂不能混用版本。历史响应不拼入新实验。

所有臂使用按时间排列的独立 image_url 多图输入；图像均为同一相机、128×128 Clean RGB，沿用历史 PNG/data URI 路径，不增加裁剪、分辨率、视觉 token 最小值或原生视频输入。Prompt 语义模板和 task_text 不变，仅按实际输入更新其原有 frame identity 表；三帧臂与旧 C 的对应请求做逐字段 diff。原始三帧角色保持 START/MIDDLE/END，新增中间帧采用既有 MIDDLE 角色；不得因此改变 Validator 或证据定义。每条请求保存完整渲染后 Prompt 和 hash，以便识别输入列表导致的必然文本长度变化。

## 必须先裁定的短片段问题

冻结集 demo_180-S0001、demo_172-S0004 只有 4 帧。以下是待选择的明确方案，尚未应用任何一个：

| 方案 | 实际实验 | 可以回答的问题与限制 |
|---|---|---|
| 推荐：10 条严格配对 + 2 条边界对照 | 长段 10×3=30 次；短段各 3/4 帧=4 次，正式共34格；Pilot另6格 | 10 条为独立时间采样的 3/6/12 对比；两短段单列。必须得到允许变更“12条36次”的确认；release 正例在短段，不能把10条的release指标冒充12条 |
| 保留12条36格，短段显式重复帧 | 长段照常；短段在6/12张中按预注册规则重复已有帧 | 改变的是输入张数，短段不是新增时间证据；需要确认允许重复，并事先冻结重复次数/顺序/角色及Validator兼容性；分层报告，不能宣称所有12条都增加了时间点 |
| 严格保留全部原要求 | 不运行正式实验 | 不扩范围、不重复、不删换样本时无法完成；等待其他合法原始时间采样来源，不能靠插值补齐 |

不推荐扩大短片段边界、换样本、使用相邻段帧或改人工标签。若用户选择另一方案，须在任何推理前修订此文和草案、冻结 hash；不能在看结果后决定。

## 确定性抽帧（可行长段）

从冻结三帧集合开始；每次选择相邻已选帧之间最大的整数帧间隔，等长时取左端更早的一段，添加 floor((left+right)/2)，直至 6 或 12 帧；最后按 frame ID 升序排列。3 ⊂ 6 ⊂ 12，所有新增帧在原始 start/end 内，不使用标签、物体位置、模型输出或人工证据帧来挑选。不足 count 个唯一时间点时停止，禁止重复。草案准备脚本 `scripts/prepare_argus_frame_ablation.py` 无模型、网络或渲染入口，以 exclusive-create 写输出，拒绝覆盖。

已产出 `evidence/Argus_Frame_Ablation_20261026/frame_schedule_draft.json`：12条身份、36格计划、4格不可行。名义秒数为 frame_index/20，并明确注明非视频 PTS。后续实际 provenance 需区分 source timestamp（存在则使用）与 nominal control timestamp，不能猜测视频帧率。

## 准备、Pilot 与正式执行

1. 用户确认方案后，补齐完整启动参数、二进制 hash 和输入数据 provenance。只读复用现有模型文件与 renderer 环境，不安装包、不并发下载，不使用 Flora 的目录或缓存。默认本机独占空闲 GPU 串行推理；不因本机资源不足自动转占 A100。若有其他计算任务，停止等待，不终止对方进程。
2. 在全新输出目录渲染新增 Clean RGB，先重渲染原36张并核对 PNG/pixel hash，确认 renderer 一致；任何差异阻塞，不能静默替换历史三帧。逐张记录 frame ID、来源、时间戳及类型、PNG/pixel SHA、尺寸、相机、渲染契约；再冻结输入 manifest、Prompt/Schema/代码/模型/backend hashes。未渲染图像不得标记为已输入。
3. Pilot 固定正例 `demo_2-S0003`、真实无事件负例 `demo_169-S0002`，各3/6/12，共6格。选择169是因它有25帧且人工事件集合为空；不用只有4帧的180充当可扩帧负例。Pilot只验工程，不依赖预测是否命中金标来放行或改Prompt。
4. 每个 Pilot 请求在发出前确认实际image_url数、解析PNG哈希和manifest顺序相符，原始三帧仍在列表；发出后保存HTTP、原始bytes、finish_reason、parse/schema/frame validation。全部6格合法、未截断、无OOM、无身份漂移、视觉token及资源日志可归属请求后通过。失败则停在Pilot，分别记录模型结构错误与实现错误，不通过调词或挑帧救工程门。
5. 用户确认后的正式集才运行新鲜完整配对。按原冻结sample_order排列；对第i条循环轮转3/6/12臂顺序以减轻缓存/温度偏差，Pilot响应不复用。严格原方案名义36格（另加Pilot6格）；推荐短段方案为34格（另加Pilot6格），须先获确认。继承历史bounded retry，每一次HTTP尝试均记成本，不能把计划格数说成总调用次数。
6. 实现错误单独 incident 记录代码diff、影响格和版本。保留错误结果，修复后以新Run ID重新跑完整可比矩阵（含Pilot门）；不混用修复前后结果。不因低分改Prompt、策略、标签或重试规则。

## 可观测性与成本

每请求记录 request_id、segment/arm、attempt、输入顺序/张数/hash、模板及完整Prompt hash、模型/backend/argv身份、发送/接收UTC及单调时钟时长、usage prompt/completion tokens、HTTP/finish_reason、Validator/QC 和原始输出。

实际视觉token从build11577后端多模态编码日志/可核验计数接口逐图提取，串行单并发并以请求起止offset关联，分别汇总image count、per-image tokens与sum。历史18 tokens/图仅作排查参考；不能用N×18或总prompt_tokens伪装实测。如果该build不能暴露可归属的视觉token，先报 `VISUAL_TOKENS_UNAVAILABLE` 并停在工程门，提交最小日志观测方案；不偷偷升级后端。

GPU采样拟100ms轮询 `nvidia-smi`，保存原始时间序列、GPU ID、进程和显存（Windows进程项不可用则标明），每格报告基线、采样峰值/增量和采样间隔。称为“采样峰值”，不冒充捕获到瞬时真实峰值；存在其他GPU进程时不能归因于本请求。记录端到端请求耗时、服务器prefill/decode耗时（可得时）、模型加载/预热时间，统计每臂中位数、p95、总GPU占用时间与全部attempt成本。预热如需模型调用，必须事前规定并单列成本；不计入正式成绩。未获取云计费不得编造货币成本。

## 评分与输出

沿用冻结三事件多标签集合及 `score_pairs` 的TP/FP/FN、zero-division=0规则，event_assessment不足证据不额外改写标签。原始人工CSV不进入Prompt；评分阶段按segment_id唯一连接，不更改人工frame证据。法定引用只检查是否实际提供、同episode/目标段内；引用合法不代表视觉判断正确。

- 每臂 object_motion Precision/Recall/F1 和TP/FP/FN；全部事件Micro P/R/F1，grasp_attempt/object_motion/release_attempt逐类FN/FP，event-set exact与phase correctness作辅助。
- JSON parse率、Schema合法率、证据引用合法率分别报告首尝试及最终值，分母为计划格数；证据合法率另报schema-valid条件分母，防止不可解析输出被忽略。空events合法时不当作引用失败。
- 沿用历史 own-valid/common-valid 评分并列，披露共同有效集合和排除偏差；另报全部计划格的失败/未完成/拒答及end-to-end exact。失败格不伪造成合法空预测，也不隐藏在分母外。
- 逐Episode（准确到冻结Segment）3/6/12对照：金标、frame IDs/timestamps/hashes、事件集合与原始说明、FN/FP变化、Schema/evidence状态、tokens、显存、延迟。短段按确认方案独立列出，不静默加入同质比较。
- demo_2/4/159分别检查新帧是否新增可见位移过程、注释是否承认位移、事件是否发出、引用是否落在支持变化的时间点、是否只混淆夹爪运动；区分观察与归因假设。额外人工视觉复核仅作诊断，不能回填或改金标。

三个长臂为Development探索性对比，无独立泛化或显著性声明。预先规定：某增加帧臂相对同run 3帧，object_motion F1和Recall均提高、全事件Micro-F1不下降、object_motion FP不增加，记为“增加帧数有效（本Development集）”；若Micro-F1或object_motion F1下降，记“退化/存在退化权衡”；否则“无明显作用/证据混合”，完整呈现TP/FP/FN，不强行判成功。6、12分别判定，不能只展示最好臂。合法性不足或覆盖不全时先判 `INCONCLUSIVE_ENGINEERING`，不能把工程失败当作帧数的语义效果。

最终交付：冻结输入manifest、运行identity、原始输入/输出与成本日志（本地）、逐格QC/评分表、三历史漏检诊断及汇总报告（脱敏入Git）。本方案确认前没有新实验分数、GPU成本或结论。
