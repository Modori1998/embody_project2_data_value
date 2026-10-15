# G3H-P0 视觉证据与语义映射失败审计（2026-10-15）

**范围：只读审计。** 没有新的 VLM 请求、训练、Prompt/Schema/Taxonomy/人工参考改动，也没有启动 G3E。基线是 G3G Development `development_20261015_schema_r1`（48/48 完成，决策 `8B_NO_CONFIRMED_GAIN`），Git SSOT 为 `663e096e169a1df64ee62063f3ea189e25fd90bf`。原始 4B/8B 请求、响应、QC 在本地 Git 忽略目录 `outputs/g3g/development_20261015_schema_r1/` 的 `{4B,8B}_{inputs,responses}.jsonl`；本审计逐条使用 `segment_id`、`task=A/B`、`attempt=1` 定位记录。20 列人工多事件参考 SHA256 为 `ecc716860eaf7617e00c1b23812fb1394a2719851346580a24e057a7e1ac938c`。下述 15 张原 PNG 经冻结 `sample_manifest.csv` SHA256 复核，且图像均为 128×128；完整 PNG SHA256、边界与帧身份保留在该 manifest。本地并排审查图在 `outputs/g3h/audit_20261015_r1/`，原 PNG 未改动。20 条审计响应的原始 `message.content` 均与保存的解析 JSON 一致，HTTP 200、`finish_reason=stop`、QC 结构有效。

**读图边界：**三帧给出离散位置，不展示帧间连续动作、抓握力或事件结果；红色目标部分被夹爪遮挡。图中位置移动、与夹爪同步移动、`object_motion` 事件，以及 `grasp_attempt`/`release_attempt` 是不同判断。以下“足够”仅指这些图片中的可见证据，不等同于已证明整段动作或任务成功。

## 逐帧图像与参考证据

| Segment；人工参考 | START | MIDDLE | END | 图像事实与参考可观测性 |
|---|---|---|---|---|
| `demo_2-S0003`；`transport`，`grasp_attempt`+`object_motion` | 63：红色目标在左侧夹爪下方。 | 84：红色目标和夹爪区域移到画面更右、靠近深色格。 | 106：两者在深色格上方更靠右。 | 对稳定桌面/格框，红色目标 **向右换位可辨**，尤其人工 `object_motion` 证据帧 84→106；与夹爪区域共同位移可见，但遮挡使夹持状态、开合过程不清。人工 `grasp_attempt` 证据 63→84 在输入范围内，是否可凭三张图确认闭合过程仍不确定。 |
| `demo_4-S0003`；`transport`，`grasp_attempt`+`object_motion` | 69：红色目标在左侧夹爪下。 | 102：目标与夹爪区域到中部。 | 136：目标与夹爪区域到右侧深色格。 | 相对格框 **向右换位清楚**；人工物体运动证据 102→136 落在输入内。夹爪姿态/角度变化明显，开合与夹持力难由这些像素可靠分离；人工抓取证据 69→102 有目标和夹爪就位，但闭合过程不清。 |
| `demo_159-S0003`；`transport`，`grasp_attempt`+`object_motion` | 81：红色目标在左侧夹爪下。 | 115：红色目标随夹爪区域到中右。 | 150：红色目标和夹爪区域更右。 | 位置变化可见，人工物体运动证据 115→150 落在输入内。人工抓取证据 81→115 落在输入内，但红色目标被遮挡、夹爪孔径不易区分；三图不足以独立确认一次新的闭合尝试。 |
| `demo_172-S0004`；`place`，`release_attempt` | 166：红色目标位于深色格、夹爪附近。 | 167：画面与 166 非常接近。 | 169：目标及夹爪仍在相近区域。 | 夹爪和目标可见；三帧中**无可辨的张开/放手序列**，也无足以确认放置结果的前后变化。人工释放证据 166→167 确实在输入内，但事件在 128×128 三张静帧中不足以可靠复核；这不构成人工标签错误的证明。 |
| `demo_169-S0002`；`approach`，无事件 | 4：红色目标在左侧桌格；夹爪在其右上方。 | 16：目标位置基本稳定，夹爪靠近。 | 28：目标仍基本稳定，夹爪更接近目标。 | 接近过程可见；没有明确的夹爪向闭合过渡或目标位移。姿态细节受分辨率限制，但三帧并不支持肯定的接触/抓取事件。人工无事件参考与可见证据相容。 |

图片直接支持 `demo_2/4/159` 的**物体画面坐标变化**；相对夹爪持续近邻支持“共同移动”的视觉判断，但不能从静帧推断施力或完整成功。`demo_172` 的 Release 缺关键开合证据是本审计最明确的输入可观测性问题。没有额外逐帧人工视觉事实表，因此更细的夹爪状态及事件边界仍可能有歧义。

## 原始 Task A / Task B 对照与归因

以下引号均为原始响应的短摘录；每条引用对应上述本地 `responses.jsonl` 中同一模型、Segment、任务、`attempt=1`。四项 Task A 顺序为 Can 可见/位置变化/随夹爪移动/夹爪开合；`Y/N/U` 为 yes/no/uncertain。所有 B 顶层证据帧合法；**帧号合法不保证解释正确**。

### `demo_2-S0003`

- **OBSERVED：**4B A 为 `Y/Y/Y/U`，位置变化理由是 “The robot segment's position changes”，并谈夹爪从红色物体到黑色物体；这个理由没有跟踪 Can。4B B 引用 63/84/106，输出 `grasp`、`grasp_attempt`、`gripper_contact_visible`，注释为“夹爪在三帧中保持闭合状态，无明显位移”。8B A 为 `Y/Y/N/U`，称 Can 从 63 到 84、106 “moved ... to the left”；图中红色目标相对固定格框实际向右。8B B 引用 63/84/106，也输出 `grasp`、`grasp_attempt`、`gripper_contact_visible`，并说“物体未发生明显位移”。人工抓取证据 63/84、物体运动证据 84/106。两模型 B 的 QC 都是 `NO_FINDING`。
- **INFERRED：**A 的 `yes` 不能当成两模型正确追踪 Can 的证明：4B 将机械臂换位当作问题答案，8B 报对“有变化”却报错方向。两模型 B 均未承认目标右移；8B B 明确否认物体位移，4B B 的“无明显位移”在语法上更可能指夹爪，不能强作物体判断。候选为 `VISUAL_PERCEPTION_ERROR` 和 `EVIDENCE_SELECTION_MISMATCH`。不能证明“已识别位移却映射失败”。
- **UNKNOWN：**模型为何在两任务切换关注对象；三帧之外抓取过程是否更明确。`SEMANTIC_MAPPING_ERROR` 目前证据不足。

### `demo_4-S0003`

- **OBSERVED：**4B A 为 `Y/Y/Y/Y`，但位置变化理由仍说 “The position of the robot segment changes”，并把帧 102/136 解释为放置/持有；4B B 引用 69/102/136，输出 `grasp`、`grasp_attempt`，注释“未见明显位移”。8B A 为 `Y/Y/Y/Y`，逐帧称 Can “from the left side ... to the right side ... bottom right compartment”；8B B 同样引用 69/102/136，却输出 `grasp`、`grasp_attempt`，称“物体在夹爪内未发生明显位移”。人工物体运动证据 102/136，图像里右移可辨；两模型 B QC 均为 `NO_FINDING`。
- **INFERRED：**8B A 与 B 对同一可见事实直接相反，是 `EVIDENCE_SELECTION_MISMATCH` 的较强证据；B 否认位移也构成候选 `VISUAL_PERCEPTION_ERROR`。4B A 的 `yes` 理由仍指机械臂，不能作为可靠 Can 感知。两模型都未在 B 正确描述位移，因此单独的 `SEMANTIC_MAPPING_ERROR` 尚未证实。
- **UNKNOWN：**8B A 的逐帧位置叙述有多少来自稳定的目标追踪、多少来自语言推断；夹爪是否发生可见闭合。

### `demo_159-S0003`

- **OBSERVED：**4B A 为 `Y/Y/Y/Y`，理由主要谈机械臂伸缩和开合，而非 Can 轨迹；4B B 引用 81/115/150，输出 `grasp`、`grasp_attempt`，说“未明确显示提起或搬运”。8B A 为 `Y/Y/U/U`，说明 Can 从左侧移到右侧，但称没有清楚看到夹爪持物；8B B 引用顶层 81/150，输出 `transport`、`object_motion`、`moving_with_gripper`，称“物体在夹爪闭合状态下随夹爪移动”，却没有人工 `grasp_attempt`。人工抓取证据为 81/115，物体运动为 115/150；8B B 的事件证据只有 81/150。QC 为 `NO_FINDING`。
- **INFERRED：**8B B 已识别并标注物体运动，说明更大的模型**在这一例**能把位移映射到事件；不能外推另外两例或认定模型规模解决映射。A 对“随夹爪移动”不确定、B 却肯定，提示跨任务证据选择变化。漏抓取可能是夹爪闭合证据不清、只关注持续搬运，或事件边界口径歧义；`TEMPORAL_EVIDENCE_INSUFFICIENT`、`EVIDENCE_SELECTION_MISMATCH`、`REFERENCE_AMBIGUITY` 均为候选。
- **UNKNOWN：**三张图是否足以独立确认 81→115 发生新的 `grasp_attempt`。冻结 Prompt 允许持续搬运时不重报既往抓取，但本段人工参考仍标抓取；当前证据不能判定模型是遵循此口径还是漏看闭合。

### `demo_172-S0004`

- **OBSERVED：**4B A 为 `Y/U/U/U`，称画面近静止、开合难辨；4B B 引用 166/167/169，却输出 `grasp`、`grasp_attempt` 和 `gripper_contact_visible`，说“夹爪闭合并接触物体”。8B A 为 `Y/N/N/N`，文字又称夹爪状态 “not visible ... to determine a change”，所以 `no` 比理由更确定；8B B 输出 `idle`、`events=[]`、`gripper_around`、`object_static`，说“无明显动作变化”。人工 `release_attempt` 的证据标在 166/167；两模型 QC 都是 `NO_FINDING`。
- **INFERRED：**三张高度相近的 128×128 静帧未清楚给出放手/开合，是 `TEMPORAL_EVIDENCE_INSUFFICIENT` 的强候选；4B 对静态“闭合接触”触发抓取，也可能是 `SEMANTIC_MAPPING_ERROR` 或视觉接触误判。8B 无事件与所见三图相容，却不等同于人工参考错误。
- **UNKNOWN：**高分辨率原帧或连续视频能否显示 166→167 的释放；人工标注依据的细微线索是否可由当前三图复核。记录 `INSUFFICIENT_EVIDENCE`，不把此例硬判为纯映射错误。

### `demo_169-S0002`

- **OBSERVED：**4B A 为 `Y/U/U/U`，4B B 引用 4/16/28，输出 `grasp`、`grasp_attempt`、`gripper_contact_visible`、`gripper_state=closed`，称“夹爪闭合并接触红色杯子”；图中夹爪靠近但未见明确接触或闭合。8B A 为 `Y/N/N/N`，两项理由却说 “There is no visible gripper”，与图中可见夹爪不符。8B B 引用 4/16/28，输出 `approach`、`grasp_attempt`、`gripper_around`、`gripper_state=open`，注释“夹爪保持 open 状态，未观察到闭合动作”。人工为 approach、无事件；两模型 QC 都是 `NO_FINDING`。
- **INFERRED：**4B 的“已闭合接触”和 8B A 的“看不到夹爪”分别是候选 `VISUAL_PERCEPTION_ERROR`。8B B 已写出“open、无闭合”，却仍给 `grasp_attempt`，符合 `SEMANTIC_MAPPING_ERROR`/触发阈值过宽的强候选。现有 Phase/Event QC 未标此条，是**已观察到的覆盖盲区**；冻结规则要求可见的、指向获取物体的行为，单纯 approach/open 不自动满足。
- **UNKNOWN：**夹爪是否有三帧之外的短暂闭合；模型内部是否另有未写出的抓取依据。不能用这一条证明所有抓取误报同源。

## Failure Matrix 与跨案例判断

| Segment | 4B 错误 | 8B 错误 | A/B 是否矛盾 | 视觉证据充分性 | 候选原因 | 证据强度 |
|---|---|---|---|---|---|---|
| `demo_2` | A 以机械臂代 Can；B 漏运动 | A 位移方向错、随夹爪判断可疑；B 漏运动 | 答案层面是；A 理由本身也有错 | 物体横移可见；抓取开合不清 | `VISUAL_PERCEPTION_ERROR`, `EVIDENCE_SELECTION_MISMATCH` | 高：图像/B 否认；中：内部原因 |
| `demo_4` | A 以机械臂代 Can；B 漏运动 | A 描述 Can 换位，B 否认并漏运动 | **是，8B 有直接文本冲突** | 物体横移可见；开合不清 | `EVIDENCE_SELECTION_MISMATCH`, `VISUAL_PERCEPTION_ERROR` | 高：直接任务间矛盾 |
| `demo_159` | B 漏运动 | B 找回运动但漏抓取 | 8B 同步移动 A 不确定、B 肯定 | 物体横移可见；新抓取开合不清 | `EVIDENCE_SELECTION_MISMATCH`, `TEMPORAL_EVIDENCE_INSUFFICIENT`, `REFERENCE_AMBIGUITY` | 高：标签差异；低：抓取归因 |
| `demo_172` | 静帧推抓取，漏释放 | 无事件，漏释放 | 4B A 不确定/B 肯定接触；8B A 理由与 no 不完全一致 | **释放序列不足** | `TEMPORAL_EVIDENCE_INSUFFICIENT`, `REFERENCE_AMBIGUITY`; 4B 映射亦可疑 | 高：图像缺明显释放；低：标签边界原因 |
| `demo_169` | 幻想闭合接触、误报抓取 | B 文字 open/无闭合却误报抓取 | 8B A 说夹爪不可见/B 明说可见；B 自身矛盾 | 接近可见；抓取证据不足 | `VISUAL_PERCEPTION_ERROR`, `SEMANTIC_MAPPING_ERROR` | 高：8B B 标签–文字矛盾及 QC 漏检 |

**`demo_2` 与 `demo_4` 不是完全同型。** 两者均有可见物体横移，而 B 均未标出该运动；`demo_2` 的 8B A 把方向说反、同步移动答 no，A 本身不可靠。`demo_4` 的 8B A 则具体描述了 Can 换位，任务间证据不一致更直接。

**`demo_159` 只证明单例可正确映射 Object Motion。** 8B 在该例的 B 写出物体随夹爪移动并标了 `object_motion`，同时漏了人工抓取；不能据此宣称增大模型普遍修复映射。

**Release 与 Object Motion 漏检的直接图像条件不同。** `demo_2/4` 的位置变化在三帧中可见；`demo_172` 的开合/放手不明显。两者都可能受三帧采样影响，但 172 更像可观测性不足，2/4 更像视觉证据未被 B 稳定使用。三帧 128×128 足以支持部分物体位移事实，不足以保证识别抓取/释放过程；不能概括成“所有事件都需补帧”。

**尚未证实：**纯粹的 `SEMANTIC_MAPPING_ERROR` 是物体运动漏报的主因；A 的 `yes` 常伴随错误对象、方向或依据。对 `demo_169` 的抓取误报，映射/触发规则使用错误的证据较强；对 `demo_172`，当前三图不足，标记 `INSUFFICIENT_EVIDENCE`。缺少独立的逐帧视觉事实参考、模型内部注意力证据及受控干预，无法把视觉提取、注意/证据选择和映射完全拆开。

## 最多两个后续实验候选（仅设计，未执行）

### A. 先试：事实抽取与事件映射分离

- **假设与唯一干预：**在固定 8B、同一三张原 PNG、后端及采样参数下，把单次 Task B 改成“视觉事实 JSON → 预先固定的事件映射”两阶段流程。阶段一必须记录**同一物体的逐帧位置与可见性、稳定参照、与夹爪的相对关系、开合变化、遮挡及不确定性**；阶段二只消费这些事实、原冻结事件定义和 Segment 身份。`can_position_change=yes` **不能直接推出** `object_motion`：须核对目标身份和可比参照；`transport` 另需随夹爪一致移动的证据；`grasp/release` 需可见过渡。冻结映射规则后才推理；这是一个整体流程干预，不能把其效果归因于某一句新 Prompt。
- **防泄漏与最小 Pilot：**先用当前 Development 中 7 条作**机制 Pilot**：物体运动正例 `demo_2/4/159`，无事件反例 `demo_169/180/232`，释放例 `demo_172`。模型输入不含人工标签、参考帧、GT 或 Task B 旧输出；阶段一的视觉事实由盲审人员在看标签前核对。7 条只作开发诊断，绝不包装为独立测试。需重新运行同协议的 7 条单阶段 8B Baseline，再跑 7 条两阶段视觉调用；映射可在 CPU 确定性执行，约 **14 次 VLM 调用**，按本轮均值约 `7×(7.36+9.46)≈118 s` 的纯请求耗时，另计模型加载和映射；实际资源另测。
- **成功/停止：**先过工程门：所有事实有原图可追溯引用，结构/帧合法，无 OOM，RAM 保持预设安全余量。若阶段一在 `demo_2/4` 仍错认对象/方向或在无事件样本虚构位移，停止并记录视觉事实瓶颈，不靠映射补救。候选效果门：3 个物体运动正例 ≥2 TP、三个无事件样本中 `object_motion` FP ≤1、全 7 条事件集合完全匹配数比新 Baseline ≥1，且 `grasp_attempt` 真阳性不下降。分别记录 TP/FP/FN、Release、逐条 exact match 和阶段一事实准确性。正式性能仍需新 Episode-disjoint 集。

### B. 条件候选：增强同三帧的原生空间分辨率

- **触发依据与唯一变量：**仅针对 `demo_172` 等夹爪孔径/释放细节在 128×128 不可辨的例子，若原始采集确有更高分辨率，保持**相同三个时间点和顺序**，只把输入改为原生 256×256 RGB；不得对 128×128 上采样后冒充新证据。先只用 4B 控制显存，Prompt/Schema/解码规则、边界和参考全部固定。该方案主要检验抓取/释放可见性，不能预设会解决 `demo_2/4` 的物体运动漏报。
- **防泄漏与最小 Pilot：**同 7 条组成，在新的配对 Run 中各跑 7 条原 128×128 与 7 条原生 256×256 Task B，共 **14 次 4B 请求**；不依据参考帧挑选额外时间点。按本轮 4B Task B 均值，128 臂约 22 s，256 臂耗时未知、估计总请求时间约 **45–90 s**，必须先验证原生源图、上下文与显存预算。成功候选门：`demo_172` Release 有可核对的新增视觉证据并从 FN 变 TP，事件集合 exact match 至少 +1，三条无事件样本新增事件 FP=0，且任何正例的原有 TP 不丢失。若原生高分辨率不存在、出现裁剪/截断/OOM/低 RAM，或增加像素仍无法显示开合，立即停止并报告输入不足；不反复调参挑结果。正式比较仍须 Episode-disjoint 独立集。

**推荐顺序：先做 A 的事实可靠性门，再决定是否做 B。** `demo_2/4` 已有可见位移，盲目增加像素或帧未针对当前最强证据；A 能直接区分“事实抽取仍错”与“事实正确但事件触发错”。若 A 事实阶段也不稳，优先回到输入证据；B 仅对确实缺少抓取/释放细节的案例成立。两方案都只是下一轮设计，本轮没有执行。
