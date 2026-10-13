<#
.SYNOPSIS
  Shared Cloudflare Quick Tunnel helper for local audit/review web servers.

.DESCRIPTION
  One reusable entry point for every local review Web (G1 / G3 / M07 / Retrieval),
  so a new Web never has to hunt for the remote-access path again.

  It starts a Cloudflare *Quick Tunnel* (no Cloudflare account required) that
  maps  http://127.0.0.1:<Port>  to a public  https://<random>.trycloudflare.com
  URL, optionally gated by Cloudflare's e-mail one-time-code protection.

  IMPORTANT LIMITS (by design of Quick Tunnels):
    * the public hostname is RANDOM and CHANGES on every start -> always re-read it;
    * there is no uptime guarantee and no persistence across reboot;
    * `--allowed-mail` needs cloudflared >= 2026.10.0. On older builds the flag is
      silently unavailable, so the script refuses to start an unprotected tunnel
      when -AllowedMail is requested but unsupported.

.PARAMETER Action
  start | stop | status

.PARAMETER Port
  Local loopback port already serving the review Web (default 8767).

.PARAMETER AllowedMail
  Optional. Comma-separated e-mail addresses and/or wildcard domains allowed to
  open the tunnel (requires cloudflared >= 2026.10.0). Omit only for
  non-sensitive content -- never for robot imagery.

.PARAMETER TunnelExe
  Optional explicit path to cloudflared.exe.

.EXAMPLE
  # protected tunnel for the G3 blind audit page
  .\scripts\cf_quick_tunnel.ps1 -Action start -Port 8767 -AllowedMail you@example.com

.EXAMPLE
  .\scripts\cf_quick_tunnel.ps1 -Action status -Port 8767
  .\scripts\cf_quick_tunnel.ps1 -Action stop   -Port 8767
#>
[CmdletBinding()]
param(
  [ValidateSet('start', 'stop', 'status')]
  [string]$Action = 'start',
  [int]$Port = 8767,
  [string]$AllowedMail = '',
  [string]$LogRoot = (Join-Path $env:USERPROFILE 'embody\_local_vlm_deploy\cflogs'),
  [string]$TunnelExe = ''
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null

$pidFile   = Join-Path $LogRoot "cf_$Port.pid"
$urlFile   = Join-Path $LogRoot "cf_$Port.url"
$outLog    = Join-Path $LogRoot "cf_${Port}_stdout.log"
$errLog    = Join-Path $LogRoot "cf_${Port}_stderr.log"

function Resolve-Cloudflared {
  param([string]$Explicit)
  $candidates = @()
  if ($Explicit) { $candidates += $Explicit }
  $candidates += (Join-Path $env:USERPROFILE 'embody\_tools\cloudflared\cloudflared.exe')
  $candidates += (Join-Path $env:LOCALAPPDATA 'cloudflared\cloudflared.exe')
  foreach ($c in $candidates) { if (Test-Path $c) { return (Resolve-Path $c).Path } }
  $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  throw "cloudflared.exe not found. Checked: $($candidates -join ', ') and PATH."
}

function Get-RunningTunnel {
  param([int]$LocalPort)
  Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -match "--url\s+http://127\.0\.0\.1:$LocalPort\b" }
}

function Get-TunnelUrl {
  param([string]$ErrLog)
  if (-not (Test-Path $ErrLog)) { return $null }
  $m = Select-String -Path $ErrLog -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -AllMatches -ErrorAction SilentlyContinue
  if (-not $m) { return $null }
  return ($m.Matches[-1].Value)
}

switch ($Action) {

  'status' {
    $t = Get-RunningTunnel -LocalPort $Port
    if (-not $t) { "STATUS: no cloudflared tunnel for port $Port"; exit 1 }
    foreach ($proc in $t) { "STATUS: running pid=$($proc.ProcessId) port=$Port" }
    $u = Get-TunnelUrl -ErrLog $errLog
    if ($u) { "URL: $u" } else { "URL: not found in $errLog yet" }
    $local = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($local) { "LOCAL: listening on 127.0.0.1:$Port" } else { "LOCAL: NOT listening on $Port" }
  }

  'stop' {
    $stopped = 0
    if (Test-Path $pidFile) {
      $old = Get-Content $pidFile -ErrorAction SilentlyContinue
      if ($old -and (Get-Process -Id $old -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $old -Force; $stopped++
      }
      Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
    foreach ($proc in (Get-RunningTunnel -LocalPort $Port)) {
      if (Get-Process -Id $proc.ProcessId -ErrorAction SilentlyContinue) {
        Stop-Process -Id $proc.ProcessId -Force; $stopped++
      }
    }
    "STOPPED: $stopped cloudflared process(es) for port $Port"
    "NOTE: the local web server on port $Port was left running."
  }

  'start' {
    # -- fail closed: the local site must actually be up ----------------
    $local = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $local) {
      throw "STOP_LOCAL_WEB_NOT_LISTENING: nothing is listening on 127.0.0.1:$Port. Start the review web first."
    }
    if ($local.LocalAddress -contains '0.0.0.0') {
      throw "STOP_LOCAL_WEB_PUBLICLY_BOUND: port $Port is bound to 0.0.0.0. Bind 127.0.0.1 instead."
    }

    $exe = Resolve-Cloudflared -Explicit $TunnelExe
    $version = (& $exe --version 2>&1 | Select-Object -First 1)
    "cloudflared: $exe"
    "version    : $version"

    $cfArgs = @('tunnel', '--url', "http://127.0.0.1:$Port", '--no-autoupdate')
    if ($AllowedMail) {
      $supports = (& $exe tunnel --help 2>&1 | Select-String -Pattern '--allowed-mail' -Quiet)
      if (-not $supports) {
        throw "STOP_ALLOWED_MAIL_UNSUPPORTED: this cloudflared build has no --allowed-mail. Upgrade to >= 2026.10.0, or omit -AllowedMail for non-sensitive content only."
      }
      $cfArgs += @('--allowed-mail', $AllowedMail)
      "protection : --allowed-mail $AllowedMail"
    } else {
      "protection : NONE (publicly reachable by anyone with the URL)"
    }

    $existing = Get-RunningTunnel -LocalPort $Port
    if ($existing) {
      foreach ($proc in $existing) { "stop       : killing previous pid=$($proc.ProcessId)" ; Stop-Process -Id $proc.ProcessId -Force }
      Start-Sleep -Seconds 2
    }

    Remove-Item $outLog, $errLog, $urlFile -ErrorAction SilentlyContinue
    $p = Start-Process -FilePath $exe -ArgumentList $cfArgs -WindowStyle Hidden -PassThru `
         -RedirectStandardOutput $outLog -RedirectStandardError $errLog
    Set-Content -Path $pidFile -Value $p.Id
    "pid        : $($p.Id)"

    $url = $null
    for ($i = 0; $i -lt 60; $i++) {
      Start-Sleep -Seconds 1
      if ($p.HasExited) { break }
      $url = Get-TunnelUrl -ErrLog $errLog
      if ($url) { break }
    }
    if (-not $url) {
      "FAILED to obtain a tunnel URL. See $errLog"
      Get-Content $errLog -Tail 20 -ErrorAction SilentlyContinue
      exit 2
    }
    Set-Content -Path $urlFile -Value $url
    ""
    "REMOTE_HTTPS_URL = $url"
    "logs             = $errLog"
  }
}
