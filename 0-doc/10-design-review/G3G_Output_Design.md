# G3G 输出与本地留存设计（2026-10-14）

## 每次运行

本地 `outputs/g3g/<run_id>/` 留存完整 `run_manifest.json`、`inputs.jsonl`、`responses.jsonl`、`per_segment.jsonl`、`summary.json`。私有 RGB、人工 CSV、权重及原始请求/响应仅本地保存，不提交 GitHub。公开证据只含 SHA256、版本、单元终态、脱敏聚合指标与逐条标签差异。

Manifest 记录：Git HEAD、官方模型仓库及 revision、4B/8B GGUF 和各自 mmproj SHA256、llama.cpp 版本和启动参数、ctx、图像尺寸与原 PNG SHA256、Prompt/Schema SHA256、Task A Prompt/Schema SHA256、12 条 Segment 身份、计划/实际顺序、seed、temperature、max_tokens、重试协议、Pilot 门槛和正式决策门槛。

每次请求记录模型、任务、Segment、attempt、帧号/哈希/顺序、模型可见文本哈希、请求哈希、HTTP 状态、finish reason、解析与 Schema/帧引用 QC、是否截断、tokens、wall time、显存快照和终态。不得将原图 base64 或原始响应写入公开目录。结构失败统一最多 2 次结构尝试；服务可恢复错误最多 3 次，两个模型相同。不可恢复身份、OOM、全局服务错误立即停。

Task A 独立表记录四项 yes/no/uncertain、支持帧、人工参考依据及 `SCORABLE`/`UNSCORABLE`。Task B 表逐 Segment 记录人工、4B、8B 的 phase 和 event set、两臂的 exact match、改正/退化、关键观察冲突。结果文档仅在真实实验后创建；未执行的单元不得填预测值或性能指标。
