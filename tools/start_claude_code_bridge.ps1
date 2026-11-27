param([switch]$Stop)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$envFile = Join-Path $repo '.env.v2'
$stateDir = Join-Path $env:LOCALAPPDATA 'QUADOS\claude-code-bridge'
$pidFile = Join-Path $stateDir 'bridge.pid'
$stdoutFile = Join-Path $stateDir 'bridge.out.log'
$stderrFile = Join-Path $stateDir 'bridge.err.log'
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null

if ($Stop) {
    if (Test-Path -LiteralPath $pidFile) {
        $oldPid = [int](Get-Content -LiteralPath $pidFile -Raw).Trim()
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $oldPid" -ErrorAction SilentlyContinue
        if ($proc -and $proc.CommandLine -match 'claude_code_bridge\.py') { Stop-Process -Id $oldPid -Force }
        Remove-Item -LiteralPath $pidFile -Force
    }
    Write-Output 'Claude Code bridge stopped.'
    exit 0
}

if (-not (Test-Path -LiteralPath $envFile)) { throw '.env.v2 is required for the local bridge token.' }
$lines = Get-Content -LiteralPath $envFile
$line = $lines | Where-Object { $_ -match '^\s*CLAUDE_CODE_BRIDGE_TOKEN\s*=' } | Select-Object -First 1
if ($line) { $token = ($line -split '=', 2)[1].Trim().Trim('"').Trim("'") }
else {
    $random = [byte[]]::new(48)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($random)
    $rng.Dispose()
    $token = [System.BitConverter]::ToString($random).Replace('-', '').ToLowerInvariant()
    Add-Content -LiteralPath $envFile -Value "CLAUDE_CODE_BRIDGE_TOKEN=$token" -Encoding UTF8
}
if ($token.Length -lt 64) { throw 'CLAUDE_CODE_BRIDGE_TOKEN must be at least 64 characters.' }
$env:CLAUDE_CODE_BRIDGE_TOKEN = $token
# Loopback only: Docker Desktop containers still reach it through host.docker.internal; the LAN and tailnet cannot.
$env:CLAUDE_CODE_BRIDGE_BIND = '127.0.0.1'
$env:CLAUDE_CODE_BRIDGE_PORT = '8127'

if (Test-Path -LiteralPath $pidFile) {
    $oldPid = [int](Get-Content -LiteralPath $pidFile -Raw).Trim()
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $oldPid" -ErrorAction SilentlyContinue
    if ($proc -and $proc.CommandLine -match 'claude_code_bridge\.py') {
        throw "Claude Code bridge is already running (PID $oldPid)."
    }
    Remove-Item -LiteralPath $pidFile -Force
}
$python = (Get-Command python -ErrorAction Stop).Source
$process = Start-Process -FilePath $python -ArgumentList @('tools/claude_code_bridge.py') `
    -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile
Set-Content -LiteralPath $pidFile -Value $process.Id -NoNewline
Start-Sleep -Milliseconds 700
if ($process.HasExited) {
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    throw "Claude Code bridge exited during startup. See local bridge error log."
}
Write-Output "Claude Code bridge started (PID $($process.Id), port 8127, read-only)."
