# P2-G3C — Multi-Event Blind Audit Web v2（2026-10-13）

> Status: `G3C_CODE_COMMITTED / CI_GATE_REQUIRED / REAL_LOCAL_RGB_BROWSER_PENDING`。G3 v0.2.1 原始推理、已采集的人工 v1 CSV、冻结 G1/M2/RGB、PR #4 均保持原样。本文件不是完成新盲审或正式语义准确率的声明。
>
> Branch: `feat/p2-g3c-multievent-blind-audit-20261013`，从 PR #4 分支的真实远端提交 `880aa78c23ac0c46ea36b68fe7f390ec6c69affb` 派生。建议叠加 PR 以 PR #4 分支为 base；原 PR #4 尚未合并 main。不要覆盖它，也不要先在 main 开发。

## 1. 目的与口径

- G1 Segment **主阶段** `phase_ref` 仍然单选。一个 Segment 可能包含多个不同的局部事件；不要因片段开始有抓取迹象，就强行把主要搬运阶段改为抓取。
- `event_assessment_ref`：`event_visible`/ `no_event_visible` / `insufficient_evidence`，保留原定义。
- `event_type_ref`：**主要事件**，保留旧列以兼容已导出的 v1 CSV/既有分析。
- **新增 `event_types_ref` 多选**：分号分隔的已观察事件集合，仅 `grasp_attempt`、`release_attempt`、`object_motion`。若观察到多个事件，应都记录。主要事件必须属于该集合。
- **新增逐事件证据帧**：
  - `grasp_attempt_frames_ref`
  - `release_attempt_frames_ref`
  - `object_motion_frames_ref`
  均为原冻结 START/MIDDLE/END 目标帧索引，分号分隔。每个已选择事件需要 **至少两张**可比目标帧以支持它的时序变化；具体的发生时刻只可限定区间，不应臆断为精确接触点。
- 本次补审仅为人类标签协议修订，没有改变 G3 v0.2 模型 schema（模型的 `events[]` 本来就允许多个实质事件）。
- 仅“靠近物体”并不足以成为 `grasp_attempt`；仅“后续已在搬运”也不足以凭空证明一段不可见的抓取启动。无事件与证据不足应分开判断。
- 多事件的 `evidence_quality_ref` 仍 **只评估主要 `motion_phase` 的可观察性**；逐事件的证据充分性由每个事件是否有可比目标帧和人工解释单独表达。

## 2. 兼容与数据保护

- 旧 16 列 CSV 原文件不得编辑或覆盖；新版导出 **20 列**，在旧列尾部加上述 4 列。新下载名称为 `G3C_12_Segment_Human_MultiEvent_Reference_v2.csv`。
- 新页面支持导入严格匹配 12 个 Segment 身份与冻结元数据的 16 列 **v1** CSV，或 20 列 **v2** CSV；拒绝未知表头、不同 source 或顺序、篡改 frame manifest、错误 enum、非法帧号。
- 迁移旧 CSV 时：只将原来已有的正向主要事件列入 `event_types_ref`，各事件证据帧 **全部留空**。**不猜测其它事件或隐含证据**；需要人工重新核对/补证据方可算完成。
- 旧版已经存在的自相矛盾记录，例如 `no_event_visible + grasp_attempt`，迁移时保留原值、醒目提示，**禁止导出 v2 直到修正**。禁止悄悄变为无事件或把矛盾当成有效正例。
- 如果用户在同一浏览器源上已经有旧版 localStorage，且 v2 没有新记录，新页面仅拷贝旧状态到独立 `p2_g3_blind_audit_v2_<sha>` 存储 key，不修改 v1 key。Cloudflare Quick Tunnel 更换域名可能导致浏览器源变化，因此 **CSV 导入是跨域/跨设备恢复的可靠路径**。
- 新 Builder 的输出目录是 `outputs/p2_g3_semantic_blind_audit/g3c_v02_microset_12_multi_event`，不会覆盖已存在的 `g3_v02_microset_12`。已有目标输出存在时默认拒绝覆盖，防止误删离线资产。
- 原始 12 行来源 CSV 仍严格 16 列、空的人类标签字段，且 PNG SHA256 逐张检查 36/36；绝不注入旧 VLM 预测，保持盲审。

## 3. 浏览器与校验逻辑

- 未观察到事件：`event_assessment_ref=no_event_visible`、`event_type_ref=none`、多事件集合和帧证据均为空。
- 无法确认发生与否：`insufficient_evidence`、`uncertain`、集合和帧证据为空。
- 有可见事件：`event_visible`，至少 1 个合法事件，主要事件属于多选集合，**每个**事件至少选择 2 张目标证据帧；旧数据尚未补证据只能处于未完成。
- 页面拒绝导出互相矛盾的记录，但允许导出 **合法但尚未完成** 的记录作备份，未完成不计入完成率。导入 v2 时严格拒绝无效组合；导入 v1 发现已有冲突时保留并提示人工修正。
- Node 无第三方依赖的模拟 DOM 测试覆盖：双事件、逐项选帧、CSV v2 导出、v1 导入不臆造证据、旧数据冲突拒导。
- 自动化测试不能代替 36 张真实 RGB 的 Chromium 实测，也不能代替一次真实人工补审。

## 4. 本地部署：先更新 GitHub SSOT，使用独立工作树

执行前：在**干净健康的 main worktree** 中运行：

```powershell
git status --short --branch
git worktree list
git fetch origin --prune
git pull --ff-only origin main
git rev-parse HEAD
git rev-parse origin/main
```

如果 main 不干净或现有工作树损坏，不得 `stash/reset/clean`；使用健康的 clone 并 fetch。GitHub 超时优先复用本机 SOCKS5 `127.0.0.1:10808`。

在 P2 仓库中创建新任务工作树，不改变当前 PR #4 的工作树：

```powershell
git fetch origin --prune
git worktree add C:\Users\95611\embody\_p2_g3c_auditweb_wt -b local/p2-g3c-auditweb origin/feat/p2-g3c-multievent-blind-audit-20261013
cd C:\Users\95611\embody\_p2_g3c_auditweb_wt
python -m pytest -q tests/test_g3_semantic_blind_audit_web.py
node tests/g3c_multi_event_dom_smoke.cjs
python scripts/build_g3_semantic_blind_audit.py
```

Builder 必须返回 `BUILT_HASH_VERIFIED`、`segment_count=12`、`png_verified_count=36`。如果 SHA 不符 STOP，绝不自行修改 frozen hash。缺缓存时才在既有 Renderer 环境尝试 `--render-missing`。

**先同时保留旧 Web**：新版本在 8768 启动测试，不改变旧版 8767：

```powershell
python -m http.server 8768 --bind 127.0.0.1 --directory outputs/p2_g3_semantic_blind_audit/g3c_v02_microset_12_multi_event
```

在 Chromium 打开 `http://127.0.0.1:8768/`；检查 36 张图片自然宽度、无控制台 JS 错误；用备份旧 CSV 导入后，核验 `demo_2-S0003` 同时选择抓取尝试和物体移动、两事件分别勾选合法帧、导出新 20 列 CSV 后再导入。**不要将示例勾选视为该样本真实发生了抓取，必须目视复核。**

Cloudflare 远程访问：复用仓库已存在的 `scripts/cf_quick_tunnel.ps1` 和 `P2_Shared_Cloudflare_Remote_Access_Deployment_v1_20261013.md`，先检查旧通道，按已获授权的身份保护方式将其指向 8768，或在准备切换正式 Web 时改 8767 的本地服务目录。不得安装 Tailscale、生成/编造 URL、无认证公开原始数据。Quick Tunnel 地址可能变化；远端实际访问必须验证后再报告真实 HTTPS URL。

## 5. 运行边界及下一步

1. 先将 v1 12 条审核数据备份；**只能导入补审**，不覆盖 v1。
2. 优先补 `demo_2-S0003` 和 `demo_159-S0003` 等可能存在多事件的片段；只在三帧能支持抓取启动时才多选 `grasp_attempt`。
3. 导出 v2 CSV，复核所有必需事件帧及冲突零、完成 12/12；再用于多标签事件集合的 Precision/Recall。先前“主要事件类型一致率”与完整集合指标不可混淆。
4. 12 条 Development 已用于诊断，不可直接充当后续调整后的 Held-out 最终性能。进入后续 G3D A/B 前单独冻结 Episode 隔离评估数据。
5. G1、M2、模型预测、v0.1/v0.2.1 已保存响应、GitHub main 和 PR #4 不变；本轮没有运行 VLM、更无训练或训练数据处置。
