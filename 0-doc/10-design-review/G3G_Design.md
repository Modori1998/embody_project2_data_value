# G3G — 4B / 8B 模型能力对照设计（2026-10-14）

## 问题与范围

检验现有三帧 RGB 条件下，Qwen3-VL-8B-Instruct Q4_K_M 是否比同系列 4B Q4_K_M 更能观察 Can 运动，并提高完整 G3 语义标注。只比较模型；不训练、不修改人工标签、历史结果、v0.2.3 Prompt 或 v0.2 Schema。历史 v0.2.1 分数仅作背景，不能充当本轮 4B 臂。

## 两个独立任务

**A：Visual Motion Probe。** 相同的三张 Clean RGB、Segment 身份和帧序；询问 Can 可见、Can 有无可辨位置变化、Can 是否随 Gripper 移动、Gripper 有无开合变化。每项用 `yes`、`no`、`uncertain`，列出支持帧号和简短可见证据。固定模型可见 Prompt：

> You are inspecting three clean RGB frames of one robot segment, in chronological order. Use only visible evidence in these images. Return one JSON object with exactly the fields segment_id, can_visible, can_position_change, can_moves_with_gripper, gripper_open_close_change. Each of the four judgments is an object with fields answer, evidence_frame_indices, observation. answer must be yes, no, or uncertain. evidence_frame_indices must contain only supplied frame indices, or be empty when no frame supports the judgment. If the images do not establish a judgment, use uncertain. Do not infer hidden motion between frames. Do not output action or event labels.

运行时只附加固定格式的 `segment_id`、三个帧号及按序排列的图像；不得附加参考答案。Task A 的 JSON 独立于语义 v0.2 Schema，不反馈给 Task B。A 指标中，仅能从已有人工可见证据明确确认的项目计分；其余 `UNSCORABLE`，禁止把缺失答案当负例。

**B：Full Semantic Annotation。** 使用 `semantic_prompt.py` 中冻结 v0.2.3、`semantic_schema.py` v0.2、原三帧和原验证规则；输出 `motion_phase`、`object_relation`、`gripper_state`、`event_assessment`、`events`、`evidence_frame_indices`、`evidence_quality`、`observation_note`。不使用 Robot State、Can GT 或 A 的输出。

## 配对身份

12 条 G3C Development Segment、边界、帧序、原 PNG SHA256、人工多事件参考以冻结 manifest 为准。两模型必须使用相同的模型可见文本、三张 PNG 字节、temperature=0、seed=1234、max_tokens=512、context_length=4096、`json_object` 首次请求和统一有限重试。模型身份、对应 FP16 mmproj、后端版本及每次请求摘要入 manifest；实际内容保留本地。若 chat template、图像预处理或截断方式不同，先记录并解决可比性问题；无法解决则不宣称规模效应。

## 安全边界

RTX 4060 Laptop 8188 MiB。官方 8B Q4 文件约 5.03 GB，FP16 mmproj 约 1.16 GB；仅权重已约 6.19 GB，还需 KV cache、计算缓冲、三图视觉 token 与系统余量，不能预设全 GPU offload 可行。逐模型串行加载，先检查 `nvidia-smi` 和训练进程；必要时降低 GPU 层数，以 CPU offload 保持原图及 4096 context。OOM、资源竞争、模型身份漂移或静默图像裁剪即停。
