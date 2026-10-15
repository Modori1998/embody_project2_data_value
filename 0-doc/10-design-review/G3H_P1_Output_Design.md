# G3H-P1 输出与本地留存设计（推理前冻结）

## 本地私有 Run

`outputs/g3h/p1_20261015_r1/` 在 Git 忽略范围内。`run_manifest.json` 留存冻结 Git SHA、后端/模型/mmproj 身份、Stage 1 Prompt/Schema SHA、映射与 Runner 源码 SHA、Baseline Prompt/Schema SHA、七条身份和帧号/PNG SHA、ctx/GPU 层数、采样、重试与 RAM 停止门槛。`stage1_inputs.jsonl`、`stage1_responses.jsonl`、`stage1_summary.json` 分别保存完整原始三图请求、逐尝试 HTTP 原文与解析/QC/资源记录、每条终态。事实门槛结果单存 `fact_gate.json`，包括 Stage 1 响应文件 SHA 和逐条审核；它不是模型输入。

只有事实门槛通过，才生成 `baseline_inputs.jsonl`、`baseline_responses.jsonl`、`baseline_summary.json` 及纯 CPU 的 `mapped_results.jsonl`。每个映射结果带 Stage 1 事实 SHA、完整八字段、独立 Validator 结果或明确错误。不覆盖任何 G3G、G3H-P0 原始产物；中断后已存在的阶段输出默认拒绝重跑，以免静默重复调用。

## GitHub 脱敏报告

`G3H_P1_Pilot_Results.md` 仅包含冻结提交 SHA、协议哈希、七条 Stage 1 事实摘要/图像核对结果、事实门槛、若执行则七条配对阶段/事件、TP/FP/FN、F1、exact match、结构合法率、重试、显存/RAM/耗时及最终判定。私有原图、完整事实 JSON、人工 CSV、base64 请求和原始响应不入 Git。若事实门槛失败，未执行的 Arm A/Stage 2 全部标记 **NOT_RUN**，绝不填历史预测或推测值。
