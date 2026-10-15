# G3H-P1B 单条事实抽取：资源线覆盖后的结果

**最终状态：`FACT_EXTRACTION_GATE_FAIL`。** Owner 在 2026-10-15 明确允许本次尝试忽略原 1536 MiB 可用 RAM 停止线。本次执行与预注册 P1B 协议的偏离仅为**不以该线自动停止**；仍只运行 `demo_2-S0003` 一次，Stage 1 `max_tokens=1024`，其余模型、Prompt、Fact Schema、图片、上下文及采样参数未变。使用新的本地 Run ID `outputs/g3h/p1b_20261015_override_r1/`，没有覆盖之前的截断或资源停止记录。

## 执行与资源

- Git 协议提交：`b5e63ec3b491f8cf56a9388d7a0e3c9f07648d2e`。8B Q4_K_M + FP16 mmproj；同一 llama.cpp 后端，`-ngl 32`、`ctx-size=4096`。
- 启动前可用 RAM 约 5.15 GiB，GPU 已用 435 MiB。加载中采样可用 RAM 最低 **390 MiB**，随后回升；服务最终健康。加载采样显存最高 6599 MiB。
- 一次三图请求：HTTP 200，`finish_reason=stop`；prompt tokens 426，completion tokens 531，总计 957；耗时 18.90 秒。请求阶段采样的最低可用 RAM **4967 MiB**、峰值已用 VRAM **6627 MiB**。资源采样存在阶段差异，不能把请求阶段 4967 MiB 当作加载阶段最低值。未观察到 OOM；服务在请求后关闭，未影响其他进程。
- 完整 JSON 解析成功，Fact Schema、帧引用和独立 Fact Validator 均通过。三张原始 PNG 为帧 63、84、106，Runner 在请求前校验 manifest 图片及模型哈希。

## 视觉事实核验

Stage 1 对 `same_can`、固定参照可比性均回答 `yes`，但对 `can_motion` 回答 **`no` / `none`**，并在观察文字中称红色 Can 在三帧里保持静止、位于桌面中央。对原始三帧并排图逐帧核验：红色 Can 在 START 帧位于托盘中部上方，MIDDLE 帧靠近右侧格框，END 帧位于更右侧格框上方；相对固定托盘/格框呈可辨认的**向右移动**。模型逐帧均填写笼统的 `center of table`，未利用可比的格框位置，故结论与可见证据冲突。

本次仅证明在这一条样本上，增加输出预算解决了 JSON 截断，却**没有解决红色 Can 的位置跟踪和方向判断**。由于事实抽取门槛失败，不运行其余六条、单阶段 Baseline 或 Stage 2；不修改映射规则补救视觉事实。原始图片、完整事实 JSON、请求/响应及服务日志仅留在本地忽略目录。
