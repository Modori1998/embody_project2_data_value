# Argus 帧数消融：执行前冻结与实施记录（2026-10-26）

## 执行前资源门调整（模型调用0）

首次run_r1在创建输出目录/加载模型之前被资源门阻止：当前桌面另有OMENCommandCenterBackground和Codex/ChatGPT界面GPU进程。只读核实为桌面/OEM管理程序，无其他模型计算进程。将二者纳入桌面基线白名单，和dwm/Listary一起逐请求记录，未知/计算进程仍阻塞。不结束对方进程、不声称GPU零使用。整卡显存采样含这些桌面开销，不能归因于模型独占；所有臂沿用同一规则。修改发生在任何推理之前。

用户已在审阅审计与方案后选择“10 条严格配对，2 条单列”：正式10×3+2×2=34格，Pilot另6格；允许Pilot通过后运行正式集。短段3/4帧单列，不纳入10条3/6/12主比较。原方案其他固定项、抽帧算法、合法性门、重试和评分规则不变。

确认后的输入时间点见 `evidence/Argus_Frame_Ablation_20261026/frame_schedule_approved.json`。最初36格草案保留作为审计，不执行其中STOP格。模型和Prompt固定4B Q4_K_M + F16 mmproj、v0.2.3、build11577、ctx4096、temperature0、seed1234、max_tokens512、json_object。

## 实施事件：INPUT_PREPARATION_CLEANUP_ERROR

首次准备目录 `outputs/argus_frame_ablation/inputs_v1`：12段渲染完成，128张不同帧，原36张PNG/pixel哈希全部匹配。退出时直接调用既有Adapter不存在的close方法，抛出AttributeError，阻止最终manifest落盘。模型调用0；不含任何效果结果。

修复仅将清理改为检查close是否可调用，与既有renderer脚本一致。失败目录保留，不复用不完整manifest；以新目录inputs_v2重新完成相同冻结抽帧与原帧哈希校验。无Prompt、策略、标签调整。

## 后端与成本记录口径补充

只读恢复 `_local_vlm_deploy/serve.sh` 的历史启动项：-ngl99、-c4096、-np1、--jinja、--temp0、--seed1234、-lv5；实验换用独立loopback端口8097，避免接管其他服务。`serve_alt.sh` 含8192 context与image-min-tokens1024，不采用。

实际视觉token报告为后端逐图 `decoding image batch ..., n_tokens_batch = ...` 的image embedding数量，不含image delimiters；总prompt_tokens另报。不能把历史18（含包装token口径）与实测embedding token混作同一个数。单槽串行，日志offset关联每次请求；无法记录时工程门停止。显存为100ms目标周期的GPU整体采样峰值，另记真实query时长/采样间隔，不声称瞬时峰值；桌面dwm/Listary基线保留，其他未知或计算进程阻塞。
