$ErrorActionPreference = 'Continue'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$logDir = Join-Path $env:LOCALAPPDATA 'QUADOS\startup'
$logPath = Join-Path $logDir 'startup_system.log'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
"[$(Get-Date -Format o)] Starting QUAD OS Docker stack." | Add-Content -LiteralPath $logPath
Push-Location $repo
try {
    & python -u (Join-Path $repo 'startup_system.py') *>> $logPath
    "[$(Get-Date -Format o)] startup_system.py exit code: $LASTEXITCODE" | Add-Content -LiteralPath $logPath
} finally {
    Pop-Location
}
