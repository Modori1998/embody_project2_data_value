# P2 Flora Video-only G3 v0.1 — 网页端开发及蓝耘云运行交接（2026-10-28）

> **STATUS = WEB_CODE_READY / SYNTHETIC_CPU_TEST_PASS / REAL_MP4_EXECUTION_NOT_RUN / QWEN_NOT_RUN**  
> 独立 Video-only 实验，非原 G1/Clean RGB 路线的替代证明。  
> 基线：PR #6 @ `c677c0b78a3a87ffe8ee7d9976ccc7ea4e59697e`；本方案建立堆叠开发分支，不能当作 PR #6 的 G1 Source Audit 已通过全部 Gate。

## 1. 做了什么

新增 `src/project2_g3/flora_video_evidence.py`、`scripts/build_flora_video_g3.py`、`tests/test_flora_video_evidence.py`、单独 GitHub Actions CPU 测试。

- 读取用户的 **原生 Flora JSON ZIP** 或包含 15 份 `demo_N.json` 的目录，**不修改原文件**；保留原字段，包括 `pipeline`，输出时只用原始文件成员路径/哈希进行关联。
- 用每条 JSON 的 `input_sha256.main` 验证实际 MP4 字节；不凭文件名假定来源。
- `ffprobe` 获取每个真实解码帧 PTS，扣除首帧原生 PTS 得相对时钟；`ffmpeg` 输出有序 RGB24 像素；核验帧数量、大小和单调 PTS。
- 按 Flora `[start_s,end_s)` 目标窗口选择属于该段的真实视频帧。每个 Segment 建 3、5、9 帧（短段不足时保留全部有效帧、显式报告实际数），起止帧不漏。
- 输出不带文字覆盖的、来自 MP4 解码的独立 PNG；**明确标记 `MP4_DECODED_RGB24_NOT_P2_CLEAN_RGB`**，不能当作原 P2 STATE Renderer 的像素证据。
- 为每个采样配置生成独立的证据包；可信 target ID 如 `flora/demo_2/S000`，可信 Episode Identity 为 `video/demo_2`，不是 `data/demo_2` 下的冻结 G1 Segment。
- 使用已有 `semantic_validation.check_manifest_integrity` / `validate_model_output_v0_2` 做输入来源/帧引用/八字段 Schema 校验，不另建同名语义 Schema。
- 另外生成 HTML 静态审计预览；仅供人工看，不给模型当作独立图片；生成 2 种模型请求候选：`vision_only` 和 `vision_plus_flora_caption`。**这只是候选描述，实际 Video-only Prompt 尚未冻结/渲染，未启动模型**。

### 不能误解的地方

- 原 G3 v0.2 Schema 里的 `motion_phase` 是**单个 target 的主要动作阶段**；一个 Flora 操作片段可能包含多个 phase。适配器不因此发明多阶段 GT 或重新分割时间。
- `Caption` 是 **未验证动作描述/意图**，在 `vision_only` 请求候选中不出现；未来给模型时必须分别锁定 Prompt 版本。
- `Validator VALID` 只说明结构与引用合法，不是事件语义正确。
- `ffmpeg/ffprobe` 的一致性校验、以及合成测试通过，不等于真实 15 条云端 MP4 已跑通过。

## 2. 已验证测试

GitHub Actions：`P2 Flora Video-only CPU tests` 在 Ubuntu Python 3.11 运行标准库 `unittest`、调用真实 ffmpeg 编码的**合成 MP4**。测试包括：抽帧与哈希、15 字段形状、半开时间段、3/5/9 采样、视频校验失败、缺失文件、PNG 篡改、目录输入、可配置文件名、确定性重跑、八字段 Validator 引用检查、短段。

截至提交本报告时：**12/12 测试通过**。GitHub Actions Run 日志可查；没有 GPU、没有真实用户 MP4、没有模型推理、没有数据训练。

## 3. 蓝耘云：准备环境与拉取代码

以下是 **Linux bash** 命令，假定已有 `/root/lanyun-tmp` 可用且磁盘保留。不要在保有未提交修改的旧仓库强制覆盖。

```bash
cd /root/lanyun-tmp

# 第一次：clone 到新目录（不触碰现有 Flora 模型/缓存）
git clone --single-branch --branch feat/p2-flora-video-g3-v0-1-20261028 \
  https://github.com/Modori1998/embody_project2_data_value.git p2_flora_video_code

cd /root/lanyun-tmp/p2_flora_video_code
git status --short
git rev-parse --short HEAD

# 以后更新：只有工作树干净、分支正确时才快进
git fetch origin
git pull --ff-only origin feat/p2-flora-video-g3-v0-1-20261028

# 确认依赖；ffmpeg/ffprobe 属于 CPU 工具，不需要 CUDA
python --version
ffmpeg -version | head -n 1
ffprobe -version | head -n 1
python -m unittest discover -s tests -p test_flora_video_evidence.py -v
```

如果云端 GitHub 连接失败，先排查现有 Cloudflare 通道/代理/VPN；不要改动主仓库或跳过版本核验。

若仓库已经在别处克隆，优先在干净 worktree/独立 clone 中安全 fetch 当前开发分支，不要在已有工作树上强制 switch。部署请以 `git rev-parse HEAD` 输出为版本事实。

## 4. 蓝耘云：定位真实 15 视频及 15 JSON

**不能凭本地 Windows 路径猜测云端位置。** 先运行：

```bash
find /root/lanyun-tmp/flora_mvp -maxdepth 8 -type f \
  \( -name 'demo_2_agentview_20fps.mp4' -o -name 'demo_2.mp4' \
     -o -name 'demo_2.json' -o -name 'flora_native_all15_export.zip' \) \
  -print
```

从返回的真实位置设置：

- `FLORA_SOURCE`：含 15 个 `raw_json/demo_N.json` 的目录、直接放 `demo_N.json` 的目录，**或** `flora_native_all15_export.zip` 文件。
- `VIDEO_DIR`：直接包含 MP4，或下一级 `videos/` 包含 MP4 的目录。
- 如果文件名是 `demo_2.mp4`，追加 `--video-pattern '{episode}.mp4'`；默认寻找 `demo_2_agentview_20fps.mp4`。

如果找不到这些 JSON/MP4，不要凭路径假设继续。把 find 结果发回核对。

## 5. 蓝耘云：先跑 1 条，再跑全部

按第 4 节的真实目录填入环境变量；**下面的路径示意值不能原样使用**：

```bash
export FLORA_SOURCE="/实际位置/raw_json"
export VIDEO_DIR="/实际位置/含视频的目录"
export OUT_BASE="/root/lanyun-tmp/flora_mvp/outputs"

cd /root/lanyun-tmp/p2_flora_video_code

# Smoke Test：只读 demo_2 的 JSON 和 MP4，CPU 抽帧
python scripts/build_flora_video_g3.py \
  --flora-source "$FLORA_SOURCE" \
  --video-dir "$VIDEO_DIR" \
  --output-dir "$OUT_BASE/flora_video_g3_smoke_demo2_v01" \
  --episode demo_2

# 成功后：单独输出目录，全 15 条
python scripts/build_flora_video_g3.py \
  --flora-source "$FLORA_SOURCE" \
  --video-dir "$VIDEO_DIR" \
  --output-dir "$OUT_BASE/flora_video_g3_all15_v01"
```

若使用 `demo_N.mp4` 命名，两次命令均加 `--video-pattern '{episode}.mp4'`。

**输出目录必须为空**。重复运行请换新目录，而不是删除旧结果；发生异常时程序退出码 `2`，不得当作通过。Linux `df -h /root/lanyun-tmp` 可以检查落盘空间。整个过程只调用 CPU 解码和标准库处理，不加载 Qwen/Flora GPU 权重。

## 6. 云端预期输出

```text
<output_dir>/
  video_frame_manifest.jsonl     # 每个实际解码帧的 ordinal/PTS/RGB 像素 SHA
  episode_inventory.jsonl        # MP4/原生 JSON 来源、时长、分辨率、数量
  evidence_packs.jsonl           # 每 Flora 段 × 3/5/9 帧采样配置
  sampling_comparison.jsonl      # 请求帧数与实际索引
  model_input_candidates.jsonl   # 纯视觉 vs Caption 提示候选；NOT_RUN
  contact_sheets/                # 本地浏览器打开的 HTML 审计视图，不是模型输入
  images/                        # 被采样的独立 PNG，来自 MP4 解码
  summary.json                   # 成功与范围；明确标记 Qwen NOT_RUN
```

如果 15 条、31 段都成功且每段拥有 3 个配置，理论上是 **93 个证据包、186 条请求候选**；实际以运行的 `summary.json` 为准，不要事先声称已实现这些数量。

结果文件与 PNG 不提交到 GitHub。将 `summary.json`、运行退出码、测试结果，以及实际错误日志发回 ChatGPT；**不要把模型缓存、API 密钥或大文件直接粘贴到聊天**。

## 7. 下一阶段 Gate

```text
VIDEO_ONLY_CODE_AND_SYNTHETIC_TESTS = PASS
CLOUD_REAL_15_MP4_HASH_AND_PTS = NOT_RUN
CLOUD_REAL_31_SEGMENT_EVIDENCE = NOT_RUN
VIDEO_ONLY_PROMPT_V0_1_FREEZE = NOT_DONE
QWEN_SMALL_BASELINE = NOT_RUN
G3_SEMANTIC_QUALITY = NOT_ESTIMABLE
FORMAL_P2_G1_CLEAN_RGB_GATE = NOT_APPLICABLE
```

后续仅在云端证据包通过后，另行冻结 **Video-only v0.1 Prompt**，选择 3–5 个开发片段、做小 Baseline；再考虑视觉 3/5/9 帧与是否加入 Flora Caption 的逐变量对照。禁止拿这些探索结果替换原冻结 G1/Clean RGB 的正式指标或独立测试。
