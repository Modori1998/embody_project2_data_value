# G3H-P1 两阶段机制 Pilot：事实抽取门槛未通过

**状态：`FACT_EXTRACTION_GATE_FAIL`。** 本轮按预注册条件停止；没有运行单阶段 Baseline、确定性事件映射或后续六条 Stage 1 请求。因此没有可计算的两臂事件指标，也不能判断两阶段流程是否提升事件质量。

## 冻结协议和运行范围

- 预注册提交：`be8d4aa1860a9421006fb29a740d657321dfa028`，已先于推理推送至 GitHub `main`。Prompt、事实 Schema、Mapper、Runner 和七条样本顺序均在该提交冻结。
- 本地 Run ID：`outputs/g3h/p1_20261015_r1/`。运行使用冻结的 8B Q4_K_M / FP16 mmproj、同一 llama.cpp 服务、`-ngl 32`、`ctx-size=4096`、`temperature=0`、`seed=1234`、`max_tokens=512`，以及 manifest 中 `demo_2-S0003` 的三张 128×128 原始 PNG（帧 63、84、106）。Runner 在请求前核验模型和图片哈希。
- 结构化事实输出使用 `json_object` 加事实 Schema，另行用独立 Fact Validator 检查。每条最多两次请求，所有原始请求和响应仅保存在本地忽略目录。

## 实际执行与停止证据

| Segment | 阶段 | 尝试 | HTTP | finish_reason | 输出 token | 耗时 | 校验结果 |
| --- | --- | ---: | ---: | --- | ---: | ---: | --- |
| demo_2-S0003 | Stage 1 | 1 | 200 | `length` | 512 | 16.76 秒 | JSON 在 `observation_note` 内截断，无法解析 |
| demo_2-S0003 | Stage 1 | 2 | 200 | `length` | 512 | 15.53 秒 | 同处截断，无法解析 |

两次请求的 prompt tokens 均为 426；均在 512 个 completion tokens 用尽时停止。响应已输出大部分事实字段，但尾部字符串没有结束，不能把它当作合法事实对象，也不能修补后继续映射。两次输出中途曾给出 `can_motion=no`，但该字段来自不完整响应，且未通过独立逐帧审计，**不得作为已核实视觉结论**。

两个请求采样的显存峰值均为 6193 MiB；最低可用系统 RAM 分别约 4906、4738 MiB，均高于预注册的 1536 MiB 停止阈值。未观察到 OOM、HTTP 服务错误或资源竞争。服务已停止。失败发生在输出长度和结构完整性，当前证据不支持归因于 RAM 或 GPU 不足。

## 七条样本执行状态

| Segment | Stage 1 | 单阶段 Baseline | Stage 2 |
| --- | --- | --- | --- |
| demo_2-S0003 | 两次请求，均截断且非法 | 未执行 | 未执行 |
| demo_4-S0003 | 未执行 | 未执行 | 未执行 |
| demo_159-S0003 | 未执行 | 未执行 | 未执行 |
| demo_169-S0002 | 未执行 | 未执行 | 未执行 |
| demo_180-S0001 | 未执行 | 未执行 | 未执行 |
| demo_232-S0002 | 未执行 | 未执行 | 未执行 |
| demo_172-S0004 | 未执行 | 未执行 | 未执行 |

预注册的事实门槛要求七条均有合法事实，并逐帧检查目标跟踪、固定参照和运动方向。首条在有界重试后仍无合法事实，故门槛未通过。无法给出七条事实质量表、事件 TP/FP/FN、F1 或 Exact Match；更不能声称 `demo_2` 的目标跟踪问题已解决。`demo_169` 的抓取误报及 `demo_172` 的释放证据问题也尚未得到本轮检验。

## 结论与后续

本轮没有证据表明 Stage 1 已能可靠抽取 Can 运动，也没有检验 Stage 2 能否改进事件映射。若继续此方向，须先**新建并预注册**一个能在输出预算内完整生成事实 JSON 的协议，再独立验证事实质量与停止门槛；不得把本次不完整输出补字段或提高 token 上限后混入本 Run ID。前述建议不是本轮实验结果。

证据：本地 `run_manifest.json`、`stage1_inputs.jsonl`、`stage1_responses.jsonl`、`stage1_summary.json`、`fact_gate.json`、服务日志。原始 RGB、完整响应和请求均未提交。
