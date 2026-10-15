# G3H-P1 两阶段视觉事实与事件映射设计（推理前冻结）

## 问题与范围

检验把视觉事实提取与事件映射拆开，是否能减少 G3G 中已观察到的漏报/误报。只做 7 条已反复使用的 Development 机制 Pilot，不作为独立泛化证据。不改 v0.2.3 Task B Prompt、v0.2 Schema、事件定义、人工多事件参考、边界或原始 128×128 三帧。G3H-P0 审计为设计依据，并非 Stage 1 的人工视觉真值。

固定七条及顺序：`demo_2-S0003`, `demo_4-S0003`, `demo_159-S0003`, `demo_169-S0002`, `demo_180-S0001`, `demo_232-S0002`, `demo_172-S0004`。Segment/episode、三帧与 PNG SHA256 一律从 G3C 冻结 manifest 核对。无事件参考不自动成为“Can 静止”的 Stage 1 负标签。

## 两组协议

**Arm A：新运行单阶段 8B Baseline。** 原三图 → 原 v0.2.3 Task B → 原 v0.2 Schema 结构约束与独立 Validator；与 G3G 相同的 8B Q4_K_M + FP16 mmproj、llama.cpp b11577、`-ngl 32`、ctx 4096、temperature 0、seed 1234、max_tokens 512。不复用 G3G 的模型预测。

**Arm B：两阶段。** 原三图 → 同一 8B Stage 1 事实抽取（1 次调用）→ 纯 CPU Stage 2 确定性映射（0 次 VLM 调用）。Stage 1 输入没有任务文本、人工参考、GT、历史输出、Robot State 或额外 RGB。输出逐帧 Can 可见性、同一物体身份、相对固定参照的位置、Can 位移/方向、随夹爪移动、夹爪靠近、近物体闭合/张开过渡、遮挡及证据帧；允许 `uncertain`/`not_observable`。事实 Schema 不含任何动作阶段或事件字段。Stage 1 模型原始 JSON 原样保留；独立事实 Validator 检查字段、类型、枚举、重复键、帧号、方向与证据至少两帧。结构非法统一最多一次重试。

Stage 2 只读已验证 Stage 1 JSON、对应 Segment 身份及允许帧号和冻结 v0.2 定义；不得读取 RGB、人工参考、单阶段输出或其他模型响应。仅当**同一 Can**、**固定参照可比**、**可辨位移**均为 yes 且方向/证据有效时触发 `object_motion`。仅在此基础上且共同移动 yes 时选择 `transport`。只有可见的近物体闭合过渡触发 `grasp_attempt`；只有可见张开过渡触发 `release_attempt`。靠近或静态 closed/open 不触发事件。不确定事实不提升为肯定，也不自动当作已证明无事件。主阶段按放手、同步搬运、闭合抓取、接近、其他物体运动、静止、无法判断的顺序选取；**事件集合独立保留全部触发项**，`transport` 不删除同时存在的抓取。无结果证据时事件 outcome 为 `unclear`。映射必须构造完整 v0.2 八字段并通过原 Validator；失败记录原因，不补写或修改 Stage 1 事实。

Stage 1 Prompt/Schema SHA256、映射源文件 SHA256、Runner SHA256、Baseline Prompt/Schema SHA256、模型/mmproj 身份均由新 Runner 写入本地 run manifest。冻结提交 SHA 在推理前单独提交并记录。不得看到七条输出后修改这些对象、门槛或样本。

冻结候选哈希（提交前复核；运行 manifest 必须完全匹配）：Stage 1 Prompt `96277a004c6e7b9314ce556ec2f105370cfa234a84f6c0b5253893eeae948bfe`，Stage 1 Schema `767e292660dbe30e32ce4b58bfa6278c0735c83d546140687b1ab18ea9e3982f`，Stage 2 映射源文件 `5ddb16f0888bffcb5a5539fac84e8ae2fbbf8209e2424eaa4aeb265c8dabcb0d`，Runner 源文件 `63b48c6f3b07ded08ebacadbaba0cbe54dd4c2c8472369a101148f998d32ac8c`。Baseline v0.2.3 Prompt `cb9fa472a27332bb39ba37d373edfd7c3b361217137972a0553f9171ba7373c1`，v0.2 Schema `4cbec780693511c6e029a1fc005a7c523e5af7ea6a4ba127c7b9fc44253d0ad7`。

## 事实放行门槛

先只运行 7 条 Stage 1 并保存所有首次/重试结果，再人工看**原始三帧与事实**；审核者承认已经知道 G3H-P0 的历史人工事件标签，因此这不是完全盲审。审核不得以“事件标签有/无”替代逐帧视觉事实。

必须全部满足：7/7 有结构、帧引用合法的事实终态；`demo_2/4/159` 的同一红色目标身份为 yes、固定参照可比为 yes、位移为 yes、方向为 **right**，逐帧位置叙述与原图一致且引用至少两张真实帧；尤其 `demo_2/4` 不得把机械臂换位冒充 Can 换位。其余 4 条逐图检查：若报告肯定运动，必须能指认相同目标在固定参照下的对应变化；无遮蔽的静止图不可虚构位移；开合/同步移动不得无依据肯定。`demo_232` 不因人工无事件标签自动判定为 Stage 1 假阳性。若任一强制项目失败，记录 `FACT_EXTRACTION_GATE_FAIL`，不运行新 Baseline 或 Stage 2 效果验证。结构整体无法稳定生成也走同一门槛失败。资源危险另标 `HOLD_RESOURCE`。

## 效果门槛（仅事实放行后）

新 Arm A 与 Arm B 在同 7 条逐条对照，使用原 `truth()` / `score_pairs()` 事件集合口径；统计事件 micro P/R/F1、TP/FP/FN、各类事件 TP/FP/FN、exact match、phase accuracy、结构及帧证据、时延和资源。全部满足才称 `TWO_STAGE_MECHANISM_CANDIDATE`：3 个 `object_motion` 正例 Arm B ≥2 TP；3 条人工无事件参考中的 `object_motion` FP ≤1；事件集合 exact match 比新 Arm A ≥1；`grasp_attempt` TP 不下降；事实门槛与工程有效性通过。否则 `TWO_STAGE_NO_CONFIRMED_GAIN`。这只是机制筛选，正式性能须用 Episode-disjoint 独立样本。
