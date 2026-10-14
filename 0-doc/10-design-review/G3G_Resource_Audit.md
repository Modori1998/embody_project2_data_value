# G3G 本地资源与身份审计（2026-10-14）

状态：`HOLD_RESOURCE`。已完成只读审计与实验预注册；未运行 8B、Pilot 或正式 Development，因此没有 G3G 成绩或逐 Segment 配对预测，也不创建 `G3G_Results.md`。

## SSOT 与历史输入

`origin/main` 在使用现有 `socks5h://127.0.0.1:10808` 抓取后为 `5b18a39c95639d2cb36fae56e9163070f99657c2`；本工作树起点相同且干净。直连 GitHub 曾报 `Recv failure: Connection was reset`。历史 G3F-P1 `full_r1` 的 4B 权重记录为 Qwen 官方 revision `1cd86afb9a95c410a6038ab3b40d8b578c892266`，GGUF SHA256 `66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a`，FP16 mmproj SHA256 `256f3a43bd4205ffef48d6b92715e1e70b5b0e9aef06522584967513a9985331`。冻结 v0.2.3 Prompt SHA256 `cb9fa472a27332bb39ba37d373edfd7c3b361217137972a0553f9171ba7373c1`，Schema SHA256 `4cbec780693511c6e029a1fc005a7c523e5af7ea6a4ba127c7b9fc44253d0ad7`。这些是历史 manifest 的已记录值，本轮尚未重新散列本地 4B 文件。

三帧 PNG 缓存在本机 `_local_vlm_deploy/rgb_g3_v02/g3_taxonomy_v02_20261013`；12 条冻结身份与 PNG SHA256 在仓库的 `sample_manifest.csv`。G3C 人工参考的填充版保留本机 `_local_vlm_deploy/g3c_csv_backup_20261013`，不进入 Git。历史 G3F-P1 原始运行结果保留在主工作树 `outputs/g3f_p1/full_r1`。历史 Runner 对 4B 身份硬编码；G3G 必须另建独立 Runner。

## 8B 来源、下载与内存

[Qwen 官方 8B GGUF 仓库](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF/tree/main)，2026-10-14 API revision `f982a07559d4a2f6c8744d840bf6fccab30eea96`。官方 `Qwen3VL-8B-Instruct-Q4_K_M.gguf` 长度 5,027,784,800 bytes、X-Linked-ETag SHA256 `67d1659bfe71b89d50b45a4ad1a9e5b997e5bb16ce5da66a6a6167abd569e9e2`；配套 `mmproj-Qwen3VL-8B-Instruct-F16.gguf` 长度 1,159,029,824 bytes、X-Linked-ETag SHA256 `ca524100ebf825c9a870db1c580d03879e0da0ab2541697e2458e64891cf9d38`。这些是官方远端声明值，不能代替完整本地文件的 SHA256 验证。

`nvidia-smi` 报 RTX 4060 Laptop 8188 MiB、检查时 0 MiB 使用、无 GPU 进程。llama.cpp 为 `0.6.0-dev` build `11577` commit `cbe28bb3c`。两份 8B 文件合计 6,186,814,624 bytes（约 5.76 GiB）；4096 context 的 KV cache、图像编码、计算缓冲和 WDDM 余量尚未计入。预计需要部分 CPU offload，不能证明全 GPU offload 安全。未更改图片尺寸或上下文。

经 SOCKS5 对官方文件试下，FP16 mmproj 约 0.77 MB/s，权重约 0.17 MB/s，按当时速率分别尚需约 21 分钟和 8 小时；`hf-mirror.com` 同文件 HEAD 返回 HTTP 429。下载已中止，可续传的局部文件仅在 gitignored `outputs/g3g/models/`，**不是已验证模型**。没有执行任何推理，也没有占用 GPU。后续应先完成两文件下载和本地 SHA256 校验，再测试单模型 CPU/GPU 分层加载；未达到这些前置条件不得宣称 8B 效果。
