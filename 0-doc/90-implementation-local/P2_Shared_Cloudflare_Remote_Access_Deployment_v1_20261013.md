# 共用 Cloudflare 远程访问部署方案 v1（G1 / G3 / M07 / Retrieval 审核 Web 通用）

> **目的**：把"本地审核 Web → 公网 HTTPS"这条链路固定下来，避免每次新 Web 都重新找远程接口。
> **性质**：运维方案 + 可复用脚本。**不含**任何凭据、Token、Cloudflare 账号信息。
> **适用**：本机（Windows）上任何绑定 `127.0.0.1:<port>` 的只读审核页。

---

## 1. 本机现状（2026-10-13 实测）

| 项 | 值 |
|---|---|
| 方法 | **Quick Tunnel**（`trycloudflare.com`，无需 Cloudflare 账号） |
| 历史依据 | M07 审核记录里公网地址即 `https://<random>.trycloudflare.com/audit/...`；**本机不存在 `.cloudflared` 凭据目录、无 `cert.pem`、无 `config.yml`** → 从未使用 Named Tunnel |
| 推荐二进制 | `%USERPROFILE%\embody\_tools\cloudflared\cloudflared.exe` — **2026.10.0** |
| 旧持久安装 | `%LOCALAPPDATA%\cloudflared\cloudflared.exe` — 2026.9.1（**不支持** `--allowed-mail`） |
| 辅助脚本 | `scripts/cf_quick_tunnel.ps1`（start / stop / status） |
| 日志与 PID | `%USERPROFILE%\embody\_local_vlm_deploy\cflogs\cf_<port>_{stdout,stderr}.log`、`cf_<port>.pid`、`cf_<port>.url` |

**为什么优先 `_tools/cloudflared`**：`--allowed-mail` 邮箱验证码保护**只有 2026.10.0+ 支持**；
2026.9.1 上该参数不存在，脚本会**拒绝**在请求保护时启动，避免误开无认证公网链接。
升级现有安装（`AppData\Local\cloudflared`）属于可选动作，本方案不改动它。

---

## 2. 端口约定（避免多个审核 Web 互相顶掉）

| Web | 端口 |
|---|---|
| G3 / G1 / Retrieval（Project2） | `8765` `8766` `8767` `8770` |
| M07 / M11（Project1） | `8791` `8796` |

新 Web 请在此表登记一个新端口，**不要复用正在运行的端口**。

---

## 3. 一次性使用（三条命令）

```powershell
# 0) 先让审核 Web 跑起来（示例：G3 盲审包）
Start-Process python -ArgumentList '-m','http.server','8767','--bind','127.0.0.1','--directory','<审核包目录>' -WindowStyle Hidden

# 1) 开公网隧道，并读取真实 URL
.\scripts\cf_quick_tunnel.ps1 -Action start -Port 8767
#    -> REMOTE_HTTPS_URL = https://<random>.trycloudflare.com

# 2) 查看 / 停止
.\scripts\cf_quick_tunnel.ps1 -Action status -Port 8767
.\scripts\cf_quick_tunnel.ps1 -Action stop   -Port 8767
```

### 带邮箱验证码保护（**含机器人图像时必须用**）

```powershell
.\scripts\cf_quick_tunnel.ps1 -Action start -Port 8767 -AllowedMail owner@example.com
# 支持多个，逗号分隔；也支持通配符域，例如 *@example.com
```

脚本会先检查本机 cloudflared 是否真的支持 `--allowed-mail`，
**不支持就直接报 `STOP_ALLOWED_MAIL_UNSUPPORTED` 退出**，绝不静默降级成无认证。

### 等价的原生命令（脚本不可用时）

```powershell
$cf = "$env:USERPROFILE\embody\_tools\cloudflared\cloudflared.exe"
& $cf tunnel --url http://127.0.0.1:8767 --no-autoupdate
# 受保护版本：
& $cf tunnel --url http://127.0.0.1:8767 --no-autoupdate --allowed-mail owner@example.com
# 真实 URL 打印在 stderr，形如 https://<random>.trycloudflare.com
```

---

## 4. 安全底线（**强制**）

1. 审核 Web 一律 `--bind 127.0.0.1`，**不得**绑 `0.0.0.0`。脚本在 start 前会检查并拒绝。
2. **含机器人实验图像 / 未公开数据** 的页面，**必须**启用 `--allowed-mail` 或已配置的 Cloudflare Access。
3. 只有**非敏感**内容才可开无认证 Quick Tunnel，且需 Owner 明确知情同意。
4. 不要把公网 URL 贴到公开渠道；URL 本身就是访问凭据（无认证时）。
5. 不要把 Cloudflare 凭据 / `cert.pem` / Token 提交到 Git。

> **本轮实例的例外记录**：2026-10-13 的 G3 盲审页，Owner 在**已知悉图片将公开可见且不可撤回**的前提下，
> **明确指示使用无认证 Quick Tunnel**。该决定属 Owner 授权，已在当轮报告中留痕，
> **不构成本方案的默认策略**。后续含敏感图像的 Web 默认走 `--allowed-mail`。

---

## 5. 持久性与 URL 轮换（重要）

| 问题 | 事实 |
|---|---|
| 电脑重启后还能访问吗？ | **不能。**本地 Web 与 cloudflared 都是普通进程；重启即中断 |
| URL 会变吗？ | **会。**Quick Tunnel 每次启动都分配**新的随机** `trycloudflare.com` 域名 |
| 有无 SLA？ | **无。**cloudflared 明确提示 account-less Tunnel 无可用性保证 |
| 需要固定 URL 怎么办？ | 需改用 **Named Tunnel**（要 Cloudflare 账号 + 自有域名 + `cloudflared tunnel login`），本方案不含该步骤 |

因此：**每次重启后必须重新执行 §3.1，并重新把新 URL 发给审核者。**

### 一键恢复（重启后）

```powershell
# 1) 起本地 Web（如已配置计划任务可跳过）
Start-Process python -ArgumentList '-m','http.server','8767','--bind','127.0.0.1','--directory','<审核包目录>' -WindowStyle Hidden
# 2) 起隧道并取新 URL
.\scripts\cf_quick_tunnel.ps1 -Action start -Port 8767
```

> 如需开机自动恢复，可自行注册计划任务（本方案不含，属可选运维动作）。
> Quick Tunnel URL 仍会变，**自动化也无法免除"重启后重发新 URL"这一步**。

---

## 6. 自检清单（每次开完隧道跑一遍）

```powershell
# a) 本地是否只绑回环
Get-NetTCPConnection -LocalPort 8767 -State Listen | Select-Object LocalAddress,OwningProcess

# b) 隧道与 URL
.\scripts\cf_quick_tunnel.ps1 -Action status -Port 8767

# c) 公网可达 + 确实经过 Cloudflare 边缘（应看到 Server: cloudflare / CF-Ray）
curl.exe -sI https://<random>.trycloudflare.com/ | Select-String "HTTP/|server:|cf-ray"

# d) 关键资源哈希与冻结源一致（审核页尤其重要）
$h = (Get-FileHash <本地PNG> -Algorithm SHA256).Hash
# 与冻结清单逐张比对，勿只看"能打开"

# e) 边界：不应暴露的样本必须 404
curl.exe -s -o NUL -w "%{http_code}`n" https://<random>.trycloudflare.com/images/<不该有的文件>.png
```

---

## 7. 故障排查

| 现象 | 处理 |
|---|---|
| `STOP_LOCAL_WEB_NOT_LISTENING` | 先启动本地 Web；确认端口与 `--bind 127.0.0.1` 一致 |
| `STOP_LOCAL_WEB_PUBLICLY_BOUND` | 端口绑到了 `0.0.0.0`，改为 `127.0.0.1` 再起隧道 |
| `STOP_ALLOWED_MAIL_UNSUPPORTED` | 用的 cloudflared < 2026.10.0；换 `_tools\cloudflared` 那个，或升级安装 |
| 隧道起来了但 URL 打不开 | 等 10–30 秒（DNS 传播）；查 `cflogs\cf_<port>_stderr.log` |
| 连不上 Cloudflare 边缘 | 看日志里的 `CONNECTIVITY PRE-CHECKS`；必要时加 `--protocol http2` |
| 想确认走的是 QUIC 还是 HTTP/2 | 日志 `Initial protocol quic` / pre-check 段 |
| 隧道进程残留 | `cf_quick_tunnel.ps1 -Action stop -Port <port>`（会按端口清理） |

---

## 8. 脚本接口速查

```
cf_quick_tunnel.ps1
  -Action      start | stop | status        (默认 start)
  -Port        本地回环端口                  (默认 8767)
  -AllowedMail 逗号分隔的邮箱/通配符域        (可选；含敏感图像时必填)
  -TunnelExe   显式指定 cloudflared.exe      (可选)
  -LogRoot     日志与 pid 目录
```

`stop` **只停隧道，不停本地 Web**（本地服务保持运行，便于继续本地审核）。
