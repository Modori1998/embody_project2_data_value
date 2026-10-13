# P2-G3 本地 VLM 部署说明（Qwen3-VL-4B-Instruct Q4_K_M + llama.cpp CUDA）

> **性质**：可复现的本地部署记录。仅用于 **本轮部署与多图推理可行性验证**。
> **不是**正式 G3 VLM Baseline，**不是** 8B 候选模型的替换，**不**冻结任何 taxonomy / 输入策略 / 评测集。
>
> **结论地位**：`Qwen/Qwen3-VL-4B-Instruct-GGUF:Q4_K_M` 只是**部署验证模型**，
> 正式候选 `Qwen3-VL-8B-Instruct` **未被替换、未被下载、未被运行**。

---

## 1. 本机环境（实际检查，非历史假设）

| 项 | 实际值 | 检查命令 |
|---|---|---|
| OS | Microsoft Windows 11 Home China，`10.0.26200`（64-bit） | `Get-CimInstance Win32_OperatingSystem` |
| CPU | 13th Gen Intel Core i9-13900HX，24C / 32T | `Get-CimInstance Win32_Processor` |
| RAM | 15.7 GiB 总量；preflight 时空闲 **仅 1.74 GiB** | `Win32_OperatingSystem.FreePhysicalMemory` |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU | `nvidia-smi` |
| 显存总量 | **8188 MiB（8 GiB）** | `nvidia-smi` |
| preflight 显存占用 | 488 MiB，空闲 7096 MiB | `nvidia-smi` |
| NVIDIA Driver | **592.82** | `nvidia-smi` |
| 驱动报告的 CUDA 版本 | **13.1**（= 驱动支持上限，**不是** 本机安装的 Toolkit） | `nvidia-smi` |
| 本机 CUDA Toolkit | **未安装**（`nvcc` 不存在，无 `CUDA_PATH`） | `Get-Command nvcc` |
| C 盘可用空间 | 171.6 GiB | `Get-PSDrive` |

**关键区分**：`nvidia-smi` 顶部的 `CUDA Version: 13.1` 是**驱动 API 支持上限**，
不等于本机装了 CUDA Toolkit 13.1。本机**没有** CUDA Toolkit，本轮**也无需安装**：
llama.cpp 官方 Windows 预编译包自带 CUDA runtime DLL。

---

## 2. 为什么选 CUDA 12.4 而不是 13.4

llama.cpp 官方 Windows 预编译发行同时提供 CUDA 12.4 与 13.4 两种构建：

- `llama-b11577-bin-win-cuda-12.4-x64.zip`
- `llama-b11577-bin-win-cuda-13.4-x64.zip`

驱动 592.82 报告的 CUDA 上限是 **13.1**，**低于 13.4**。选用 CUDA 13.4 构建有
驱动版本不满足的风险；CUDA 12.4 运行时对 13.1 驱动是向后兼容的。
因此选择 **CUDA 12.4** 构建（更保守、更可验证）。

实测 `llama-server --list-devices` 正确枚举：

```
Available devices:
  CUDA0: NVIDIA GeForce RTX 4060 Laptop GPU (8187 MiB, 7096 MiB free)
```

---

## 3. 已检查但未采用的路径

| 路径 | 结论 | 说明 |
|---|---|---|
| `winget install llama.cpp`（`ggml.llamacpp`，b11560） | **未采用** | winget 源可用，但为满足"必须确认 CUDA Backend 已加载"的要求，直接取官方 Windows CUDA Release 更可验证 |
| Ollama | **未安装、未采用** | 本机不存在；不引入第二套运行时 |
| 本地源码编译 llama.cpp | **未采用** | 预编译发行版已满足需求，避免不必要的本地编译 |
| 修改 NVIDIA Driver / 安装 CUDA Toolkit | **未执行** | 明确禁止；也不需要 |

---

## 4. 目录布局（全部在项目仓库之外）

```
C:/Users/95611/embody/_local_vlm_deploy/
├── llama_cpp/
│   ├── llama-b11577-bin-win-cuda-12.4-x64.zip      # sha256 24f5885d…436c
│   ├── cudart-llama-bin-win-cuda-12.4-x64.zip      # sha256 8c79a9b2…e1d6
│   └── bin/                                        # 解压后的运行时
├── models/
│   ├── Qwen3VL-4B-Instruct-Q4_K_M.gguf             # sha256 66358cb1…0a0a
│   └── mmproj-Qwen3VL-4B-Instruct-F16.gguf         # sha256 256f3a43…5331
├── rgb/                                            # 由冻结 Renderer 重新生成的 Clean RGB
├── logs/                                           # 启动日志、CUDA offload 证据
├── pget.py                                         # 并发分块下载器（stdlib）
└── serve.sh / serve_alt.sh                         # 启动脚本
```

**模型权重、缓存、原始机器人 PNG 一律不进 Git。** 仓库内只提交脚本、测试、文档和小型哈希清单。

---

## 5. 模型文件固定（不可回填）

| 项 | 值 |
|---|---|
| 仓库 | `Qwen/Qwen3-VL-4B-Instruct-GGUF` |
| **revision（commit）** | `1cd86afb9a95c410a6038ab3b40d8b578c892266` |
| LLM 文件 | `Qwen3VL-4B-Instruct-Q4_K_M.gguf` |
| LLM 字节 | 2497281664（2.33 GiB） |
| **LLM SHA-256** | `66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a` |
| mmproj 文件 | `mmproj-Qwen3VL-4B-Instruct-F16.gguf` |
| mmproj 字节 | 836180256（0.78 GiB） |
| **mmproj SHA-256** | `256f3a43bd4205ffef48d6b92715e1e70b5b0e9aef06522584967513a9985331` |

两个 SHA-256 均在本地**重新计算并与 HuggingFace 官方 listing 逐一比对，完全一致**。

> mmproj 另有 Q8_0 版本（453974304 B，sha256 `30ba2c7d…b06d`）可作为**有记录的显存降级替代**；
> 本轮未使用，主配置用 F16。

---

## 6. 运行时固定

| 项 | 值 |
|---|---|
| 引擎 | llama.cpp |
| 构建 | **b11577** |
| 版本串 | `0.6.0-dev (build 11577, commit cbe28bb3c)`，Clang 20.1.8，Windows x86_64 |
| 二进制包 | `llama-b11577-bin-win-cuda-12.4-x64.zip`（sha256 `24f5885d2d67b9a61da5f9dcde93d74ae3820b4bb4fcaa738f29f7ab4ba7436c`） |
| CUDA runtime 包 | `cudart-llama-bin-win-cuda-12.4-x64.zip`（sha256 `8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6`） |
| CUDA backend | `ggml-cuda.dll` + `cublas64_12.dll`（含于上述包内） |

---

## 7. 启动命令（主配置）

```bash
BIN=D:/<DEPLOY_ROOT>/llama_cpp/bin          # 本机实际为 C:/Users/95611/embody/_local_vlm_deploy/llama_cpp/bin
M=D:/<DEPLOY_ROOT>/models

"$BIN/llama-server.exe" \
  -m "$M/Qwen3VL-4B-Instruct-Q4_K_M.gguf" \
  --mmproj "$M/mmproj-Qwen3VL-4B-Instruct-F16.gguf" \
  -ngl 99 -c 4096 -np 1 \
  --host 127.0.0.1 --port 8080 \
  --no-webui --jinja --temp 0 --seed 1234
```

| 参数 | 作用 | 理由 |
|---|---|---|
| `--mmproj` | 加载视觉编码器 | **必须**；只加载 LLM GGUF 不能处理图像 |
| `-ngl 99` | 全部层卸载到 GPU | 实测 `offloaded 37/37 layers to GPU` |
| `-c 4096` | 上下文 4096 | 6 张 128×128 图仅需 ~228 prompt token，4096 充足且省显存 |
| `-np 1` | 单 slot | 无并发，符合"单请求、无并行" |
| `--host 127.0.0.1` | 仅监听回环 | **不暴露公网** |
| `--no-webui` | 关闭 Web UI | 减少无关开销 |
| `--jinja` | 用模型自带 chat template | Qwen3-VL 需要正确的多模态 template |
| `--temp 0 --seed 1234` | 确定性 | 实测两次同参请求输出逐字一致 |

### 可选诊断配置（**非主配置，不可与主配置结果混用**）

```bash
  ... -c 8192 --image-min-tokens 1024
```

服务器启动时会对 Qwen-VL 打印如下提示，`--image-min-tokens 1024` 即为响应它：

```
W load_hparams: Qwen-VL models require at minimum 1024 image tokens to function
                correctly on grounding tasks
W load_hparams: if you encounter problems with accuracy, try adding
                --image-min-tokens 1024
```

实测该配置**未改善**结果且明显更慢/更占显存（见可行性报告 E/F 节），因此**不作为主配置**。

---

## 8. CUDA Backend 与 GPU Offload 的实际证据

**不能把"程序启动了"当成"GPU 推理成功"。** 本轮从**实际日志 + 系统监控**两侧确认：

`llama-server -lv 5` 启动日志（原文）：

```
I common_param:   - CUDA0   : NVIDIA GeForce RTX 4060 Laptop GPU (8187 MiB, 7096 MiB free)
I llama_prepare_model_devices: using device CUDA0 (NVIDIA GeForce RTX 4060 Laptop GPU) (0000:01:00.0) - 7096 MiB free
I load_tensors: offloading output layer to GPU
I load_tensors: offloading 35 repeating layers to GPU
I load_tensors: offloaded 37/37 layers to GPU
I cmn system_info: ... CUDA : ARCHS = 500,610,700,750,800,860,890,900 | USE_GRAPHS = 1 | FA_QUANTS = q4_0-q4_0,q8_0-q8_0,f16-f16,bf16-bf16
```

- **`offloaded 37/37 layers to GPU`，无任何 `assigned to device CPU` 行** → 全部层在 GPU。
- 系统监控：显存 **488 MiB → 4806 MiB**（+4.3 GiB），`llama-server.exe` 出现在
  `nvidia-smi --query-compute-apps` 的 `Type=C`（CUDA Compute）进程中。
- 推理期间 `nvidia-smi` 采样到 GPU Util **93%**。
- **视觉编码器确实参与推理**（不是纯文本冒充图像推理）：以同一 Prompt 做定量对照，
  每张 128×128 图贡献**恰好 18 个 prompt token**，且随图数线性增长：

| 请求 | prompt tokens | 图像贡献 |
|---|---|---|
| 纯文本（0 图） | 33 | — |
| 1 图 | 51 | **+18** |
| 3 图 | 87 | **+54 = 18×3** |
| 6 图 | 141 | **+108 = 18×6** |

---

## 9. 冷启动与资源基线

| 指标 | 主配置（`-c 4096`） | 诊断配置（`-c 8192 --image-min-tokens 1024`） |
|---|---|---|
| 冷加载到 `/health` 就绪 | **3.46 s**（页缓存已热） | 3.14 s |
| 加载后显存 | 4806 MiB | 5386 MiB |
| 6 图推理峰值 | **4832 MiB** | 5514 MiB |
| 剩余空闲显存（峰值时） | ~3.35 GiB | ~2.67 GiB |

---

## 10. 网络与代理（端口会漂移，以实测为准）

- **直连 HuggingFace 不可用**（`curl https://huggingface.co` → `000`，超时）。
- Windows WinINET 代理 `ProxyServer = 127.0.0.1:10808`（**本轮实测端口，非历史写死值**）
  可访问 HF（HTTP 200）与 GitHub Release。
- **发现并采用更快路径**：`hf-mirror.com` **直连（不走代理）** 实测约 2 MB/s，
  而原站经代理仅 ~85 KB/s。模型最终由镜像下载，**并以本地重算 SHA-256 与官方值比对通过**。
- GitHub API 在共享代理出口 IP 上被限流（403 `API rate limit exceeded`），
  改为解析 Release 页面获取资产列表，未使用任何凭据。
- 下载器为本轮自建的 `pget.py`（纯 stdlib，8 并发 Range 分块，可断点续传）。
- **未向任何云端 API 上传机器人图片**：所有推理仅发往 `127.0.0.1:8080`。
- 未写入、未提交任何访问凭据；模型下载全程使用公开镜像，不需要 token。

---

## 11. 复现步骤

```bash
# 0) 前置：确认 GPU 与显存
nvidia-smi

# 1) 取官方 CUDA 12.4 预编译发行（经代理）
PGET_PROXY=http://127.0.0.1:10808 python pget.py \
  https://github.com/ggml-org/llama.cpp/releases/download/b11577/llama-b11577-bin-win-cuda-12.4-x64.zip \
  llama_cpp/llama-b11577-bin-win-cuda-12.4-x64.zip 6
PGET_PROXY=http://127.0.0.1:10808 python pget.py \
  https://github.com/ggml-org/llama.cpp/releases/download/b11577/cudart-llama-bin-win-cuda-12.4-x64.zip \
  llama_cpp/cudart-llama-bin-win-cuda-12.4-x64.zip 4
# 解压两个 zip 到 llama_cpp/bin

# 2) 下载并**校验**模型（走镜像直连）
REV=1cd86afb9a95c410a6038ab3b40d8b578c892266
python pget.py "https://hf-mirror.com/Qwen/Qwen3-VL-4B-Instruct-GGUF/resolve/$REV/Qwen3VL-4B-Instruct-Q4_K_M.gguf" \
  models/Qwen3VL-4B-Instruct-Q4_K_M.gguf 8
python pget.py "https://hf-mirror.com/Qwen/Qwen3-VL-4B-Instruct-GGUF/resolve/$REV/mmproj-Qwen3VL-4B-Instruct-F16.gguf" \
  models/mmproj-Qwen3VL-4B-Instruct-F16.gguf 6
sha256sum models/*.gguf   # 必须等于 §5 表中两个值

# 3) 确认 CUDA 设备可见
llama_cpp/bin/llama-server.exe --list-devices

# 4) 启动（见 §7）
./serve.sh

# 5) 单图 smoke test
python scripts/probe_g3_local_vlm.py --base-url http://127.0.0.1:8080 \
  --images <frame.png> --prompt "请根据图像描述机械臂、夹爪和目标物体的可见状态。如果无法判断，明确说明无法判断。" \
  --label smoke --max-tokens 128 --temperature 0 --seed 1234 \
  --json-out out.json --csv-out metrics.csv
```

---

## 12. 与既有环境隔离的保证

- 未修改 P1/P2 Python venv（渲染器环境 `project1_robomimic_audit` 仅**只读使用**）。
- 未升级 RoboMimic / MuJoCo / PyTorch。
- 未修改 NVIDIA Driver，未安装 CUDA Toolkit。
- 未关闭任何非本轮启动的 GPU 进程（开始时仅 explorer / Listary / ChatGPT 等桌面进程）。
- 未使用第三方非官方量化权重。
- 未修改冻结 G1/M2/Phase 1C Owner 评分、RGB Contract、Retrieval。
- 未执行任何 ACT/VLA 训练，未执行正式 8B 推理。
- server 结束前已用 `taskkill` 停止本轮启动的 `llama-server.exe`，显存回到 488 MiB。
