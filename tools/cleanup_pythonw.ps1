param(
    [int]$ProcessId = 0,
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$processes = @(Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'")
$processes | Select-Object ProcessId, ExecutablePath, CommandLine,
    @{Name='MemoryMiB'; Expression={[math]::Round($_.WorkingSetSize / 1MB, 1)}} |
    Format-List

if (-not $Execute) {
    Write-Output 'Preview only. Identify a stale repo-owned process, then use -ProcessId <PID> -Execute.'
    exit 0
}
if ($ProcessId -le 0) {
    throw 'An explicit -ProcessId is required. Never terminate all pythonw processes.'
}
$target = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId"
if (-not $target -or $target.Name -ne 'pythonw.exe' -or
    -not $target.CommandLine -or
    $target.CommandLine.IndexOf($repo + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase) -lt 0) {
    throw 'Refusing: selected PID is not an identifiable pythonw process for this repository.'
}
$answer = Read-Host "Stop only PID $ProcessId after reviewing its command line? Type the PID to confirm"
if ($answer -ne "$ProcessId") {
    throw 'Cancelled'
}
# Recheck process identity after confirmation to avoid killing a reused PID.
$current = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId"
if (-not $current -or $current.CreationDate -ne $target.CreationDate -or
    $current.CommandLine -ne $target.CommandLine) {
    throw 'Process changed; inspect again'
}
Stop-Process -Id $ProcessId -ErrorAction Stop
Write-Output "Stopped PID $ProcessId only. Restart the intended service through its normal supervisor."
