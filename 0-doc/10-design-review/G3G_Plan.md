# G3G 执行计划与预注册门槛（2026-10-14）

本文件在正式 12 条推理前冻结。GitHub `origin/main` 为 SSOT；当前恢复基线 `5b18a39c95639d2cb36fae56e9163070f99657c2`。

1. 校验官方 Qwen 8B Q4_K_M 与相应 FP16 mmproj 的 revision、文件 SHA256；检查 4B 身份、llama.cpp 版本、原 RGB 缓存、人工参考、GPU 进程与空闲显存。8B 与 4B 如需新后端，则两臂均用新后端重新推理。
2. Pilot 固定 `demo_2-S0003`、`demo_159-S0003`、`demo_169-S0002`、`demo_180-S0001`。2 模型 × 4 Segment × 2 独立任务 = 16 单元。逐模型串行，所有单元记录请求、终态、重试、耗时、GPU 峰值。放行条件：权重及 mmproj 正确、三张原图与帧序正确、无截断或静默裁剪、结构及帧引用合法、无 OOM/资源竞争、所有单元有终态、耗时与显存可接受。准确率不参与 Pilot 放行。
3. Pilot 通过后，以新 Run ID 对 12 条全部重新跑 A/B 两任务和 4B/8B 两臂，共 48 个计划单元。首次及重试分别计数；不拼接历史响应。A 与 B 分别统计，A 的缺失人工参考记 `UNSCORABLE`。
4. B 统计 motion phase accuracy、event presence F1、multi-event micro P/R/F1、event set exact match、三类事件 TP/FP/FN、evidence-label conflict、结构首次/最终合法率、tokens 与 wall time。逐条列出人工、4B、8B 和错对变化。A 统计 Can motion TP/FP/FN、P/R/F1、同步移动、开合、uncertain 与支持帧；仅对可评分参考计算。

## 正式运行前冻结的 Development 门槛

全部满足才输出 `8B_DEVELOPMENT_CANDIDATE`：8B B 事件 micro-F1 比本轮 4B 至少 +0.10；3 个 `object_motion` 正例至少 2 个 TP；该事件 FP ≤1；event set exact match 至少 +1 条；motion phase 正确数下降 ≤1；工程有效性无明显退化。否则 `8B_NO_CONFIRMED_GAIN`。8B 无法安全运行则 `HOLD_RESOURCE`。A 明显改善而 B 未改善，另标记 `PERCEPTION_GAIN_MAPPING_BOTTLENECK`。这些是开发筛选条件，不是显著性或泛化证明；候选须进入 Episode-disjoint 独立集。

解释时分别检查感知与事件映射、召回与误报。若两者均无增益，仍需列明三帧采样、量化和小样本限制。若 8B 不能观察 Can 位移，后续才考虑 G3E 关键帧、分辨率、RGB 派生位置特征或更强 VLM，不预言补帧有效。
