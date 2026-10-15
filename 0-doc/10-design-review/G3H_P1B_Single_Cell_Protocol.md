# G3H-P1B 单条事实抽取验证：推理前预注册

母协议：G3H-P1 冻结提交 `be8d4aa1860a9421006fb29a740d657321dfa028`。P1 的第一条事实抽取两次在 512 completion tokens 截断。本协议只把 Stage 1 `max_tokens` 改为 **1024**，重新测试 `demo_2-S0003` 一条；使用全新本地 Run ID。它不恢复原 Run ID，也不包含另外六条、单阶段 Baseline 或 Stage 2。

保持母协议的 8B Q4_K_M、FP16 mmproj、同一 llama.cpp 后端、`-ngl 32`、`ctx-size=4096`、`temperature=0`、`seed=1234`、三张原始 128×128 PNG、帧 63/84/106、Fact Prompt、Fact Schema、独立 Fact Validator 与资源停止线。一次请求，无重试。请求前核验图片和模型 SHA256、模型服务身份、Prompt/Schema SHA；保存完整请求、原始响应、资源采样和校验结果于 Git 忽略的本地目录。

预注册判定：加载后可用 RAM 若低于 1536 MiB，停止且不推理，报告 `HOLD_RESOURCE`。推理中若低于此线、OOM 或系统明显内存压力，停止并报告 `HOLD_RESOURCE`。如果 JSON 截断、非法，或完整事实经原图核验仍把同一个红色 Can 判为不动或方向不为向右，则 `FACT_EXTRACTION_GATE_FAIL`。只有 JSON 完整、Fact Validator 合法、证据帧合法且人工逐帧核验同一 Can 相对固定参照向右位移正确，才视为本单条事实抽取通过；这不放行其余六条或事件映射。

上下文容量检查：服务为 4096 context。前次相同三图和 Prompt 记录 prompt tokens 426，本次最大 completion tokens 1024，合计 1450，小于 4096；实际请求仍须核验服务返回无截断。此估算不替代实际 token 记录。
