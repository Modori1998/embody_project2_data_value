# P2-G3 本地 VLM 部署与多图推理可行性报告（2026-10-13）

> **任务**：`P2_G3_LOCAL_VLM_DEPLOYMENT_FEASIBILITY`
> **性质**：**可行性验证**。不是正式 G3 VLM Baseline，不冻结 taxonomy / 输入策略 / 评测集 / 成功率阈值。
> **模型地位**：`Qwen/Qwen3-VL-4B-Instruct-GGUF:Q4_K_M` 仅为**部署验证模型**，
> 正式候选 `Qwen3-VL-8B-Instruct` **未被替换、未被下载、未被运行**。
> **运行日期**：2026-10-13（本机时钟，UTC+08:00）；证据时间戳为 UTC。

---

## 0. 一句话结论

**这台笔记本能真跑视觉大模型**：RTX 4060 Laptop 8 GB 上，用 llama.cpp 把
Qwen3-VL-4B Q4_K_M **全部 37/37 层 + 视觉编码器卸载到 GPU**，单图约 2.0 s、
六图约 2.0 s（峰值显存 **4832 MiB / 8188 MiB**），**六图不 OOM**。
但**"能跑"不等于"能信"**：六图时模型会**把邻段帧当成目标段内帧**，
同一张图的夹爪状态在自由文本与 JSON 两种输出下**互相矛盾**。
本轮所有自由文本回答都撞到 128 token 上限被截断。
因此运行时状态为 `MULTIFRAME_FEASIBLE`，**语义可靠性未建立**。

---

## A. 本机硬件与软件 Preflight

```
LOCAL_VLM_PREFLIGHT = PASS
```

| 项 | 实际值 | 与历史参考的差异 |
|---|---|---|
| OS | **Windows 11 Home China `10.0.26200`** | ⚠️ 历史记录写 Windows 10，**实际是 Windows 11** |
| CPU | 13th Gen Intel Core i9-13900HX，24C/32T | 一致 |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU | 一致 |
| 显存总量 | **8188 MiB** | 一致（8 GB 级） |
| preflight 占用 / 空闲 | 488 MiB / **7096 MiB** | 空闲充足 |
| NVIDIA Driver | **592.82** | — |
| 驱动报告的 CUDA 版本 | **13.1**（驱动 API 上限） | — |
| 本机 CUDA Toolkit | **未安装**（`nvcc` 不存在） | ⚠️ 必须与上面的 13.1 区分 |
| 系统内存 | 15.7 GiB 总量，**空闲仅 1.74 GiB** | ⚠️ 内存偏紧（见下） |
| C 盘可用 | 171.6 GiB | 足够（模型合计 3.1 GiB） |
| Python（渲染器环境） | `project1_robomimic_audit` = **3.10.21** | 只读复用 |
| 已有 llama.cpp / Ollama | **均无** | 全新安装 |
| 已有 Qwen3-VL 权重 | **无**（HF cache 只有 siglip2 / clip-vit） | 全新下载 |

**关于 1.74 GiB 空闲内存的取舍**：可用物理内存偏低，但本轮瓶颈是 **VRAM 而非 RAM**
（模型全层在 GPU，KV cache 也在 GPU）。实测全程无内存压力、无 swap 抖动。
**不采取**关闭其他用户程序的激进做法；开始时的 GPU 占用进程只有 explorer / Listary / ChatGPT
等桌面程序，均非本轮启动，**未做强制结束**。

**Preflight Gate 判定**：磁盘充足、显存空闲 7096 MiB、模型 3.1 GiB，**放行下载**。

---

## B. 实际使用的模型、量化版本与推理引擎

| 项 | 值 |
|---|---|
| 模型仓库 | `Qwen/Qwen3-VL-4B-Instruct-GGUF` |
| **固定 revision** | `1cd86afb9a95c410a6038ab3b40d8b578c892266` |
| 量化 | **Q4_K_M**（LLM） |
| LLM 文件 | `Qwen3VL-4B-Instruct-Q4_K_M.gguf`，2497281664 B |
| **LLM SHA-256** | `66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a` |
| 视觉编码器 | `mmproj-Qwen3VL-4B-Instruct-F16.gguf`（**F16**），836180256 B |
| **mmproj SHA-256** | `256f3a43bd4205ffef48d6b92715e1e70b5b0e9aef06522584967513a9985331` |
| 推理引擎 | **llama.cpp**，构建 **b11577**，`0.6.0-dev (commit cbe28bb3c)` |
| 二进制 | `llama-b11577-bin-win-**cuda-12.4**-x64.zip`（sha256 `24f5885d…436c`） |
| CUDA runtime | `cudart-llama-bin-win-cuda-12.4-x64.zip`（sha256 `8c79a9b2…e1d6`） |

两个 GGUF 的 SHA-256 均**本地重算并与 HuggingFace 官方 listing 完全一致**。

**为什么 CUDA 12.4 而非 13.4**：驱动 592.82 的 CUDA 上限是 **13.1 < 13.4**，
用 13.4 构建有驱动不满足风险；12.4 对 13.1 驱动向后兼容。选保守项。

**未采用的替代路径**：`winget install llama.cpp`（源为 b11560，但不便于确认 CUDA 后端）；
Ollama（本机无）；本地源码编译（不必要）。

---

## C. 下载、安装与 CUDA 加载结果

| 步骤 | 结果 |
|---|---|
| 已有安装检查 | 无 llama.cpp / 无 Ollama / 无同款权重 → 全新部署 |
| 二进制下载 | ✅ 官方 Release b11577，CUDA 12.4 Windows x64 |
| 模型下载 | ✅ 3.1 GiB，**本地 SHA-256 双验证通过** |
| 设备枚举 | ✅ `CUDA0: NVIDIA GeForce RTX 4060 Laptop GPU (8187 MiB, 7096 MiB free)` |
| CUDA 后端加载 | ✅ `ggml-cuda.dll` + `cublas64_12.dll`；`CUDA : ARCHS = 500…900 | USE_GRAPHS = 1` |
| **GPU Offload** | ✅ **`offloaded 37/37 layers to GPU`**，**0 层在 CPU** |
| mmproj 加载 | ✅ `loaded multimodal model` |
| 冷加载耗时 | **3.46 s** 到 `/health` 就绪（页缓存已热） |
| `/v1/models` | ✅ 返回 `capabilities: ["completion","multimodal"]`，`input_modalities: ["text","image","video"]` |
| 显存变化 | 488 MiB → **4806 MiB**（+4.3 GiB，模型+mmproj 上卡） |
| 计算进程 | ✅ `llama-server.exe` 出现在 `nvidia-smi` 计算进程表（`Type=C`） |

**网络诊断（区分原因）**：直连 HF **被阻断**（`000` 超时）→ 判定为**网络可达性问题**，
非仓库权限或文件完整性问题；经代理 `127.0.0.1:10808` 可达 HF 与 GitHub。
GitHub API 返回 `403 API rate limit exceeded`（共享出口 IP 限流）→ 改解析 Release 页面。
最终走 `hf-mirror.com` **直连**（~2 MB/s，远快于经代理的 ~85 KB/s），
**并用本地重算哈希证明镜像内容与官方一致**。全程未使用任何访问凭据。

---

## D. 单图 / 三图 / 六图真实测试

**输入来源**：`data/demo_47` / 目标段 `demo_47-S0003`（**非 Held-out**；
与冻结 P4 评测集 24 个 Episode **零交集**）。
6 张图 = 目标段关键帧 `f50,f70,f90` + 邻段上下文 `f49(PREV_END), f91(NEXT_START), f94(NEXT_MID)`，
**逐帧与 Phase-1B 冻结帧清单的 `pixel_sha256` 比对：6/6 完全一致**。

**输入合法性**：128×128、无文字 Overlay、`overlay_applied=False`、`audit_mp4_used=False`、
`lossy_video_roundtrip=False`，由**原冻结 Renderer 按原帧索引重新渲染**
（`MODEL_RGB[t] = render(STATE_t)`），**未修改 RGB Contract**，
**未从含标注拼图中裁剪**，**未用审核 MP4**。

**固定推理配置**：`temperature=0`，`seed=1234`，`max_tokens=128`，单请求无并发，
模型与运行时版本固定。

### D.1 主配置结果

| 测试 | 图数 | prompt tok | 完成 tok | 总耗时 | 生成耗时 | 显存峰值 | OOM | JSON 可解析 | 完成推理 |
|---|---|---|---|---|---|---|---|---|---|
| `test_1img_A`（单图） | 1 | 51 | 128 | **2.00 s** | 1668 ms | 4824 MiB | 否 | — | ✅ |
| `test_1img_A_json`（单图+JSON） | 1 | 96 | 73 | **1.09 s** | 950 ms | 4824 MiB | 否 | ✅ **是** | ✅ |
| `test_3img_B`（三图） | 3 | 89 | 128 | **1.88 s** | 1665 ms | 4830 MiB | 否 | — | ✅ |
| `test_6img_C`（六图） | 6 | 228 | 128 | **2.05 s** | 1699 ms | **4832 MiB** | **否** | — | ✅ |
| `test_6img_C_repeat`（六图复跑） | 6 | 228 | 128 | **1.80 s** | 1705 ms | 4832 MiB | 否 | — | ✅ |
| `diag_6img_long`（六图，512 tok） | 6 | 228 | 212 | 2.92 s | 2812 ms | 4832 MiB | 否 | — | ✅ |

**生成速率约 75 token/s**（128 tok / 1.70 s），三档图数**几乎不变**——
因为图像 token 极少（见 D.3），瓶颈在解码而非视觉编码。

**确定性**：相同 Prompt / 参数（`temp=0, seed=1234`）重复请求，输出**逐字完全一致**。

### D.2 六种问题的实际回答（原始，未修饰）

**单图（`test_1img_A`）**：机械臂白色、悬停工作台上方；夹爪银灰色金属、**张开、尚未夹紧**；
目标物体为**红色圆柱**，位于工作台中央，**尚未被夹取**。→ **基本正确**。

**单图 JSON（`test_1img_A_json`）**：同一张图，输出
`{"arm_visible": true, "gripper_state": "closed", "target_object_visible": true, "uncertain": false,
"notes": "...holding a red object..."}`
→ **和上一行直接矛盾**：自由文本说"张开/未夹紧"，JSON 说 `closed` + 已"holding"。
⚠️ **同一张图、同一模型、同一 seed，只因输出格式不同就给出相反的夹爪状态判断。**

**三图（`test_3img_B`）**：描述"夹持红色圆柱 → 放置到右侧黑色托盘 → 夹爪已松开移开"。
运动叙述连贯，但**断言了"已放置/已松开"这类接触与结果**，
与 Prompt 的"不要推断看不见的接触或任务成功"**相冲突**。

**六图（`test_6img_C`）**：出现**明显的证据越界**——把邻段上下文当成目标段行为叙述，
并在结尾声称"图2、图3、图4、图5、图6 是目标段内连续关键帧"，
**而图5、图6 实际是 `NEXT_SEGMENT_START` / `NEXT_SEGMENT_MIDDLE`**。
同时自相矛盾：前半句刚说"图1和图5、图6 是邻段上下文，不计入目标段内行为"。
⚠️ **这正是 Phase-1B 冻结文档反复警告、必须防住的错误**。

**关于 128 token 截断**：`test_1img_A` / `test_3img_B` / `test_6img_C` 的 `finish_reason` 全为
`length`，即**回答在句中被截断**。把六图放宽到 512 token 后答案完整（212 tok，`stop`），
越界问题**依然存在**——说明它不是截断造成的假象。

**证据限制遵守情况**：4 次主配置运行中，**没有任何一次输出"无法判断"**
（`states_uncertainty` 全为 `false`），即模型**从不主动声明证据不足**。

### D.3 视觉编码器确实参与推理（非纯文本冒充）

同一 Prompt 下，图像带来的 prompt token 增量**严格线性**：

| 请求 | prompt tokens | 图像贡献 | 每图 |
|---|---|---|---|
| 纯文本 0 图 | 33 | — | — |
| 1 图 | 51 | +18 | **18** |
| 3 图 | 87 | +54 | **18** |
| 6 图 | 141 | +108 | **18** |

每张 128×128 图 = **18 个视觉 token**。这说明**图像真的进入了视觉编码器**，
也**解释了细粒度判断（夹爪开合）为何不可靠**：18 token 对 128×128 的机械臂细节是极低预算。

---

## E. 显存峰值、耗时与性能瓶颈

### E.1 资源表（主配置 `-c 4096`）

| 状态 | 显存占用 | 说明 |
|---|---|---|
| 桌面基线 | 488 MiB | preflight |
| 模型+mmproj 加载后 | 4806 MiB | +4.3 GiB（LLM 2.33 GiB + mmproj 0.78 GiB + KV/compute） |
| 单图推理峰值 | 4824 MiB | +18 MiB |
| 三图推理峰值 | 4830 MiB | |
| **六图推理峰值** | **4832 MiB** | **剩余空闲 ~3.35 GiB** |

**六图没有触及显存上限**，无需任何降级。

### E.2 是否需要 CPU Offload

**不需要。** 37/37 层与视觉编码器全部在 GPU，`-ngl 99` 无裁剪，无 CPU 回退。

### E.3 瓶颈诊断

| 环节 | 观测 | 判定 |
|---|---|---|
| 冷加载 | 3.46 s | 快，非瓶颈 |
| 视觉编码 | 6 图 prompt 处理 238 ms | **非瓶颈**（图像 token 太少） |
| **自回归解码** | **~75 tok/s，与图数无关** | **真瓶颈**：耗时几乎全部来自输出 token |
| 显存 | 峰值 4832/8188 MiB | 非瓶颈，余量 41% |

**结论**：本机瓶颈**不是显存、不是视觉编码，而是解码吞吐**（4B Q4_K_M 在 4060 Laptop 上 ~75 tok/s）。
3 图与 6 图的总耗时与单图几乎相同（1.8–2.05 s），因为主成本是 128 个**输出** token。

### E.4 分辨率/token 预算对照实验（诊断，非主配置）

针对服务器关于 `--image-min-tokens 1024` 的警告，做了一次**有记录**的对照
（`-c 8192 --image-min-tokens 1024`，**与主配置结果严格分开，不混用**）：

| 项 | 主配置（默认 18 tok/图） | 诊断（1024 tok/图） | 变化 |
|---|---|---|---|
| 1 图 prompt tok | 51 | 1059 | ×20.8 |
| 6 图 prompt tok | 228 | 6272 | ×27.5 |
| 6 图总耗时 | 2.05 s | **6.41 s** | **×3.1 更慢** |
| 6 图显存峰值 | 4832 MiB | 5514 MiB | +682 MiB |
| 单图回答质量 | 正确识别红色圆柱 | ⚠️ **反而说"未显示任何明确的目标物体"** | **变差** |
| 六图越界问题 | 存在 | **依然存在** | 未解决 |

**判定**：提高图像 token 预算**没有修复**细粒度判断与证据越界，却带来 **3 倍延迟**与更高显存。
**不作为主配置**，仅记录为已测负结果。

---

## F. GitHub 提交与复现命令

### F.1 分支与基线

| 项 | 值 |
|---|---|
| 仓库 | `Modori1998/embody_project2_data_value` |
| 前置同步 | `git fetch origin` → 主工作树 `git pull --ff-only origin main` |
| `origin/main` 同步后 SHA | **`41a5da37b057bc0daa27ef38b1302a8096253ce0`**（与任务给定参考一致） |
| 任务分支 | `p2-g3-local-vlm-deploy-20261013`（基于 `41a5da3`） |
| 对 `main` 的改动 | **无**（未 merge、未 force push、未 reset/clean/stash） |
| 未触碰 | 冻结 G1/M2/RGB Contract、Phase 1B/1C Owner 评分、Retrieval、P1/P2 venv |

**保留的冻结决定（未改动）**：`CONTEXT_POLICY_DECISION = KEEP_CONTEXT_OPTIONAL`
**本轮仍未冻结**：G3 taxonomy、正式 VLM revision、正式 A/B 输入策略、Held-out 评测集、成功率阈值。

### F.2 提交内容

**代码 / 测试**
- `scripts/probe_g3_local_vlm.py` — 本地单图/多图推理探针（纯 stdlib，可复用）
- `scripts/materialize_g3_vlm_rgb_frames.py` — 用冻结 Renderer 按原帧索引重建 Clean RGB + 与冻结清单比对
- `tests/test_g3_local_vlm_probe.py` — **31 项**输入契约与解析测试

**文档**
- `0-doc/90-implementation-local/P2_G3_Local_VLM_Deployment_Notes_20261013.md`（部署说明）
- 本文件（可行性报告）

**小型证据（可提交，不含图片与凭据）**
- `0-doc/10-design-review/evidence/P2_G3_Local_VLM_Probe_Runs_20261013.json`
- `0-doc/10-design-review/evidence/P2_G3_Local_VLM_Resource_Latency_20261013.csv`
- `0-doc/10-design-review/evidence/P2_G3_Local_VLM_Frame_Provenance_20261013.csv`
- `0-doc/10-design-review/evidence/P2_G3_Local_VLM_Environment_Provenance_20261013.json`

**明确不提交**：GGUF 权重、模型缓存、原始机器人 PNG、`llama.cpp` 二进制、`outputs/` 运行目录、
HF token（全程未使用、未落盘）、含敏感绝对路径的运行日志。

### F.3 复现命令

```bash
# 主配置启动（详见部署说明 §7）
llama-server.exe -m Qwen3VL-4B-Instruct-Q4_K_M.gguf \
  --mmproj mmproj-Qwen3VL-4B-Instruct-F16.gguf \
  -ngl 99 -c 4096 -np 1 --host 127.0.0.1 --port 8080 \
  --no-webui --jinja --temp 0 --seed 1234

# 单图 / 三图 / 六图
python scripts/probe_g3_local_vlm.py --images f50.png --label t1 \
  --prompt "请根据图像描述机械臂、夹爪和目标物体的可见状态。如果无法判断，明确说明无法判断。" \
  --max-tokens 128 --temperature 0 --seed 1234 --json-out t1.json --csv-out metrics.csv

# 重建 Clean RGB 并核对冻结哈希
PY=.../project1_robomimic_audit/python.exe
$PY scripts/materialize_g3_vlm_rgb_frames.py --episode-id data/demo_47 \
  --target-segment-id demo_47-S0003 --frames 50 70 90 \
  --context-frames 49 91 94 \
  --context-roles PREV_SEGMENT_END NEXT_SEGMENT_START NEXT_SEGMENT_MIDDLE \
  --output-dir <LOCAL_DEPLOY_ROOT>/rgb --provenance-out <...>/rgb_provenance.csv \
  --summary-out <...>/rgb_provenance_summary.json \
  --expect-csv <phase1b>/G3_Context_Window_Frame_Provenance_20261012.csv

# 测试
python -m pytest tests/test_g3_local_vlm_probe.py -q      # 31 passed
```

---

## G. 三种成功的分级判定

| 层级 | 判定 | 依据 |
|---|---|---|
| **A. `LOAD_SUCCESS`** | ✅ **YES** | 37/37 层 + mmproj 全部加载；`/v1/models` 报 multimodal；冷加载 3.46 s |
| **B. `INFERENCE_SUCCESS`** | ✅ **YES** | CUDA0 实际计算（显存 +4.3 GiB、GPU util 93%、计算进程在列）；真实 RGB 经视觉编码器（+18 tok/图）；返回自然语言与可解析 JSON |
| **C. `P2_MULTIFRAME_READY`** | ⚠️ **运行时 = YES，语义 = NO** | 能稳定处理 3/6 图且不 OOM（峰值 4832/8188 MiB）、可重复、响应与 Provenance 可保存；**但**六图出现证据越界、单图出现自相矛盾、从不声明不确定 |

```
LOCAL_VLM_STATUS = MULTIFRAME_FEASIBLE      # 仅代表运行时能力
```

> **必须强调**：`MULTIFRAME_FEASIBLE` **只说明这台机器跑得动 3–6 张图**，
> **不代表**语义标签正确、**不代表**正式实验就绪、**不代表**可用于 G3 评测。
> 本轮**未**评价动作标签准确率，也**未**产出任何准确率数字。

---

## 人话总结

**这台电脑到底能不能运行视觉大模型？**
能。RTX 4060 Laptop 8 GB + llama.cpp，把 Qwen3-VL-4B 的**全部 37 层和视觉编码器都放进了显存**，
加载后占 4.8 GB，还剩 3.3 GB 空闲。冷启动约 3.5 秒。这是**真的 GPU 推理**，不是 CPU 硬撑，
也不是"程序起来了"就算数——日志里明确写了 `offloaded 37/37 layers to GPU`。

**单张机器人图片能不能处理？**
能，而且**基本看懂了**：它认出白色机械臂、银灰色夹爪、还有那个红色小圆柱，说得大体没错。
但**细节不可靠**：同一张图，让它用自由文字答，它说夹爪"张开、还没夹"；
让它用 JSON 答，它说 `closed`、"正夹着"——**同一张图两个相反答案**。
所以"能看图"是真的，"看得准"还不是。

**多张图片是否会爆显存？**
**不会。** 1 张、3 张、6 张的显存峰值分别是 4824 / 4830 / 4832 MiB，
6 张也只用掉 8 GB 里的 4.8 GB，还剩 3.3 GB。**不需要降级、不需要 CPU offload**。
而且 6 张图跟 1 张图耗时几乎一样（约 2 秒）——因为慢的是"往外写字"（约 75 字/秒），
不是"看图"。我们也试过把每张图的视觉 token 从 18 提到 1024，
结果**慢 3 倍、更占显存、答得反而更差**，所以没采用。

**但有一个必须说清的问题**：图给多了，模型反而**开始编**。
六张图那一轮，它把"邻段的图片"（实际上是下一段的第一帧和中间帧）
当成"目标段自己的画面"来讲，还白纸黑字说"图 5、图 6 是目标段内关键帧"——
这正是 Phase 1B 文档反复警告、最怕发生的那种错误。
而且不管给几张图，它**从来不主动说"我看不出来"**。

**后续正式 G3 应该采用什么部署方式？**
1. **算力不是障碍，别为了省显存去砍配置。** 8 GB 够跑 4B Q4_K_M 的多图。
2. **4B + 128×128 的语义可靠性不够**，不能拿现在这套直接去做正式标注或评测。
   每张 128×128 图只有 18 个视觉 token，这是**细粒度判断不准的根因之一**——
   与 Phase 1B 早就指出的"128×128 是真实瓶颈"一致。
3. **顺序建议**：先在**远程/更大显存 GPU** 上试 **8B** 正式候选
   （4B 已证明本地能跑，8B Q4 在 8 GB 上会非常紧张），
   同时把**分辨率**（256×256 起，需 Owner 批准契约变更）和**输出格式**（JSON-only 可减少自相矛盾）
   作为独立变量先做小样本消融；
   **不要**在没有可观测性 rubric 和证据边界检查的情况下直接开正式 A/B。
4. **无论走哪条路，都必须先解决"邻段帧不得记为目标段事件"的硬约束**——
   本轮证明单纯在 Prompt 里写规则**不足以**约束 4B 模型，需要**结构性**的
   输入隔离（例如目标段与上下文分次请求，或对输出做强校验拒绝）。

---

## 本轮停止点

**Local VLM 可行性测试已完成，立即停止。** 未进入：
G3 Taxonomy Freeze、正式 8B Baseline、A/B 语义评测、Held-out 评测、
任何 ACT/VLA 训练、任何 `main` 合并。

**遗留未冻结项**（需 Owner 另行决策）：正式 VLM 模型与 revision、正式输入策略（A/B/B+C）、
分辨率实验版本、证据边界校验机制、taxonomy 取值、成功率阈值。
