# P2 Argus 3/6/12 帧：Pilot 未通过，正式实验未运行

**决策：`INCONCLUSIVE_ENGINEERING / STOP_PILOT_GATE_FAILED`。** 确认后的矩阵为10条长段3/6/12帧、2条短段3/4帧，正式34格；但完整6格Pilot中，12帧正例输出两次违反冻结Schema，因此按方案停止，正式执行0/34。不能将本报告表述为完整帧数消融结论，也不能声称已解决三例历史漏检。

本轮无权重下载、无模型规模比较、无训练、无Flora目录/缓存或A100操作；本机自有llama-server已在退出时关闭。M07/M11/P2历史冻结结果未改。审计和准备见 [Audit](Argus_Frame_Ablation_Audit_20261026.md)、[Plan](Argus_Frame_Ablation_Plan_20261026.md)、[执行前冻结与实施事件](Argus_Frame_Ablation_Execution_20261026.md)。

## 输入与运行身份

- 代码在推理前提交：`9ae8426`（完整Pilot），前一观测错误运行为`001ee4d`。固定v0.2.3、原v0.2 Schema/Validator、Qwen3-VL-4B Q4_K_M与F16 mmproj、llama.cpp build11577、ctx4096、temperature0、seed1234、max_tokens512、json_object、单槽多图image_url输入。无原生视频、额外状态或Prompt搜索。
- 已生成128张不同原始时间点Clean RGB；新增原始时间点92张，原36张PNG/pixel hashes均匹配历史；128×128、原相机/渲染器。34个payload检查通过，全部12个三帧payload与历史G3F-P1 C完全一致。输入manifest SHA256 `2499a63834474e1c51f6bae7d8a7be7ca3b148a448cc91eb7b793f35f0d03449`。图像身份见 `evidence/Argus_Frame_Ablation_20261026/input_identity_verified.json`。
- 正式使用的本地运行目录：`outputs/argus_frame_ablation/run_r3`；其中只有pilot目录，无full目录。完整Pilot6格达到终态，共7次请求（一次结构重试）。原始HTTP、请求、逐图后端日志和GPU时间序列保留本地；脱敏汇总见同级evidence中的`pilot_summary_verified.json`。
- 较早`run_r2`在12帧重试命中KV缓存时被观测逻辑误停，4次请求全部计入成本，不混作run_r3成绩。修复只处理观测：同一payload之前已有实测值且缓存几乎完整时，保留其输入视觉token实测来源，本次新增编码计0。run_r3从全新模型会话重跑全部Pilot，不修改模型请求。
- 两次实际推理之外有两次准备期错误（清理Adapter及Path类型），均发生在推理前，详见实施记录；没有借此选择Prompt、标签或抽帧策略。

## Pilot实际输入与逐条结果

时间戳为控制时钟名义值 `frame_id/20` 秒，非真实视频PTS。完整timestamp、PNG/pixel SHA已记录；真实采集时间戳未恢复，值为null，不伪造。

| Segment | 帧数 | 实际frame ID（按输入顺序） | 输入视觉embedding tokens |
|---|---:|---|---:|
| demo_2-S0003 | 3 | 63,84,106 | 48 |
| demo_2-S0003 | 6 | 63,73,78,84,95,106 | 96 |
| demo_2-S0003 | 12 | 63,68,73,78,81,84,89,92,95,100,103,106 | 192 |
| demo_169-S0002 | 3 | 4,16,28 | 48 |
| demo_169-S0002 | 6 | 4,7,10,16,22,28 | 96 |
| demo_169-S0002 | 12 | 4,5,7,8,10,11,13,16,19,22,25,28 | 192 |

逐请求日志实测每图16个embedding tokens，上表总数来自实际计数汇总，不是拿总prompt_tokens替代。另有image delimiters，未计入embedding口径；此前18/图的历史口径不能直接与此混比。12帧重试完整缓存复用，其输入仍为192个实测embedding tokens，本次新增视觉编码0。

| Segment / 人工真值 | 3帧 | 6帧 | 12帧 |
|---|---|---|---|
| demo_2：transport；grasp_attempt + object_motion | grasp；grasp_attempt；OM漏检。注释“未见明显位移” | grasp；grasp_attempt；OM仍漏检。注释“无明显位移” | place；**非法event_type=place**，两次一致；注释称“物体被移动至目标盒子区域”。不得映射成合法object_motion或release_attempt |
| demo_169：approach；无事件 | grasp；grasp_attempt误报，称闭合接触 | approach；grasp_attempt误报，注释称夹爪保持打开、罐子静止 | approach；grasp_attempt误报，注释明确无可见物体运动或接触 |

12帧正例JSON可解析，所有引用都在实际输入帧内；失败是事件枚举`place`不合法，不是图像少传、跨段引用、上下文溢出或max_tokens截断。首次finish_reason=stop，生成254 tokens，小于512上限；schema-only结构重试仍为同一非法事件，未恢复。保留原始结果，不自动纠错。3/6帧正例的REVIEW_REQUIRED属于一致性审阅候选，结构和帧引用均合法，符合既有工程门口径。

## 合法率与诊断评分（仅Pilot）

| 指标 | 3帧（2格） | 6帧（2格） | 12帧（2格） |
|---|---:|---:|---:|
| 首次/最终Schema合法 | 2/2；2/2 | 2/2；2/2 | 1/2；1/2 |
| 首次/最终JSON可解析 | 2/2；2/2 | 2/2；2/2 | 2/2；2/2 |
| 首次/最终帧引用合法 | 2/2；2/2 | 2/2；2/2 | 2/2；2/2 |
| 合法输出数 | 2 | 2 | 1（只有负例） |
| OM TP/FP/FN（own-valid） | 0/0/1 | 0/0/1 | 0/0/0；正例非法，未评分 |
| OM Precision/Recall/F1 | 0/0/0 | 0/0/0 | 不可比较：合法集合无正例 |
| 全事件Micro P/R/F1（own-valid） | .500/.500/.500 | .500/.500/.500 | 0/0/0；仅负例，不能与两条集合比较 |
| grasp_attempt TP/FP/FN | 1/1/0 | 1/1/0 | 0/1/0；仅负例 |
| release_attempt TP/FP/FN | 0/0/0 | 0/0/0 | 0/0/0 |
| end-to-end event-set exact（非法计不正确） | 0/2 | 0/2 | 0/2 |

zero-division沿用历史实现记0。尤其12帧合法集合的OM Recall数学分母为0，底层返回0不代表测得了召回率；上表明确不作比较。三臂共同合法集合只有demo_169，三者均grasp FP=1、事件Micro-F1=0，没有OM正例，不能支持补帧有效/无效判断。Pilot无release真值，不能用0/0/0证明release表现良好。

总体6格：首次与最终Schema合法率均5/6=83.3%，JSON可解析6/6、帧引用合法6/6；在schema-valid条件下帧引用合法5/5。按全部7次请求计：Schema合法5/7=71.4%，JSON和引用均7/7。合法引用不代表视觉事实或标签正确。正式34格及全部12条的OM P/R/F1、Micro-F1与逐类FN/FP均为 **NOT_RUN**，不从Pilot填充。

## 延迟和GPU成本

GPU为RTX4060 Laptop 8188 MiB；模型一次加载2.68s；run_r3整个自有服务会话30.82s。桌面基线约386 MiB，整卡采样峰值4736 MiB（约4.63GiB，相对初始基线增4350 MiB）。不能将这视为纯模型分配或瞬时峰值；包含dwm、Listary、OMEN和Codex桌面占用。283个GPU采样，实际间隔中位109.1ms、最大118.3ms。

| 帧数 | 首次请求平均/中位耗时 | 首次p95（nearest-rank，n=2） | 含重试总耗时 | 请求数 | prompt/completion tokens |
|---|---:|---:|---:|---:|---:|
| 3 | 3.107s | 3.176s | 6.213s | 2 | 4716 / 297 |
| 6 | 3.512s | 3.615s | 7.024s | 2 | 4997 / 350 |
| 12 | 5.001s | 5.008s | 13.787s | 3 | 8329 / 758 |

相对3帧，两例首次延迟均值6帧约+13.0%，12帧约+61.0%。这些是两个已知样本、热模型串行且共享前缀缓存的端到端请求时间，不是稳定吞吐benchmark；n=2的p95只是最大观测值。各臂整卡采样峰值均4736MiB，不足以证明多帧没有更高瞬时/激活显存开销。

run_r3合计7次请求27.024s，18042 prompt + 1405 completion tokens，实际新编码672个视觉embedding tokens。包含run_r2观测错误后的真实总成本为11次请求43.359s、28405 prompt + 2247 completion tokens、1008个新编码视觉embedding tokens；两批成本都未隐去。渲染CPU/GPU时间、GPU kernel执行时间和货币费用没有独立计量；不能拿请求耗时冒充GPU kernel秒数，也未产生可报告的A100计费。

## 三个历史object_motion漏检样本：本轮能说到哪里

| 样本 | 已观察 | 可支持的判断 | 仍未知 |
|---|---|---|---|
| demo_2 | 3/6帧合法输出均否认可见位移并漏OM；12帧注释承认移动，却输出非法place事件 | 6帧未在该例恢复OM；12帧引起描述/阶段变化且出现结构退化。视觉证据选择与事件编码/映射均可能参与 | 12帧所述“目标盒子区域”是否准确、内部注意与映射的因果贡献；未将这条非法输出强算为TP |
| demo_4 | 历史G3F-P1 C漏OM；最新G3H审计指出原三帧存在可见物体横移及跨任务证据不一致 | 不能再笼统断言三帧没有位移信息；时间采样与任务条件下证据使用是竞争解释 | 本轮6/12帧没有推理，无法判断增益或退化 |
| demo_159 | 历史C漏OM；历史其他Prompt/任务可改变运动判断 | 识别与事件输出依赖任务条件，补帧尚待验证 | 本轮6/12帧未运行；不能用其他模型/Prompt的历史恢复替代本轮成绩 |

本轮未额外修改人工事实真值或做新一轮独立视觉盲审；历史分析引用的是GitHub审计证据，与本轮观测分开。demo_169在6/12帧注释“open/静止”却发出grasp_attempt，提示既有触发/映射或视觉证据使用问题，增加帧数没有在该负例消除误报。

## 结论与停止边界

**增加帧数有效：本轮未建立。6帧：两个Pilot样本上事件评分无改善。12帧：正例出现Schema可靠性退化。整体：工程门失败，帧数对完整Development集的效果仍不可判定。** 不将该结论命名为全量NO_GAIN，不从单例泛化，也不在看过结果后改Prompt、事件枚举、抽帧策略或重试预算。

34格正式集、两条短段3/4帧对照均未运行。若后续要在原json_object协议下继续正式集，须明确修订“Pilot必须全合法”的门并接受无效格，作为新协议预注册；若要加入Schema约束解码，也属于新的固定协议，须三臂重新Pilot/正式运行，不能与本次或历史结果拼接。本轮不擅自执行任何一种改变。

验证：34个输入payload检查、12个历史三帧payload等值检查、128个图像身份检查、缓存观测和嵌套抽帧3项pytest均通过。输入和代码实现已可复查，Pilot因真实模型非法输出失败，正式集停止是冻结门的预期行为。
