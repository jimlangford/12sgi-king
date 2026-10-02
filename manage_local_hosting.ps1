#!/usr/bin/env powershell
<#
.SYNOPSIS
12sgi-king Local Hosting Management Script
Starts both the deployment system and auto-recovery monitor

.DESCRIPTION
This script simplifies starting your complete local hosting system:
- Deployment system (port 9000)
- Auto-recovery monitor
- Status dashboard

.EXAMPLE
.\manage_local_hosting.ps1

#>

param(
    [ValidateSet("start", "stop", "status", "logs", "dashboard")]
    [string]$Action = "start",
    
    [string]$LogLines = 10
)

$RepoPath = "C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king"
$DeploymentScript = "$RepoPath\local_deployment_complete.py"
$AutoRecoveryScript = "$RepoPath\service_auto_recovery.py"
$StatusScript = "$RepoPath\status_dashboard.py"
$LogDir = "$RepoPath\logs\local-deployment"

function Start-Systems {
    Write-Host "🚀 Starting 12sgi-king Local Hosting System" -ForegroundColor Green
    Write-Host ""
    
    # Check prerequisites
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        Write-Host "❌ Python not found. Please install Python 3.11+" -ForegroundColor Red
        exit 1
    }
    
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $docker) {
        Write-Host "❌ Docker not found. Please install Docker Desktop" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "✓ Prerequisites check passed" -ForegroundColor Green
    Write-Host ""
    
    # Start deployment system in new window
    Write-Host "▶ Starting Local Deployment System..." -ForegroundColor Cyan
    Write-Host "  Command: python $DeploymentScript" -ForegroundColor Gray
    
    try {
        $deploymentJob = Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd '$RepoPath'; python local_deployment_complete.py" -PassThru
        Write-Host "  ✓ Deployment system started (PID: $($deploymentJob.Id))" -ForegroundColor Green
    } catch {
        Write-Host "  ❌ Failed to start deployment system: $_" -ForegroundColor Red
        exit 1
    }
    
    Start-Sleep -Seconds 2
    
    # Start auto-recovery in new window
    Write-Host "▶ Starting Auto-Recovery Monitor..." -ForegroundColor Cyan
    Write-Host "  Command: python $AutoRecoveryScript" -ForegroundColor Gray
    
    try {
        $recoveryJob = Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd '$RepoPath'; python service_auto_recovery.py" -PassThru
        Write-Host "  ✓ Auto-recovery started (PID: $($recoveryJob.Id))" -ForegroundColor Green
    } catch {
        Write-Host "  ❌ Failed to start auto-recovery: $_" -ForegroundColor Red
        exit 1
    }
    
    Write-Host ""
    Write-Host "✅ All systems started!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📝 Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Push code: git push origin main" -ForegroundColor Gray
    Write-Host "  2. Watch Terminal 1: Full deployment automatic" -ForegroundColor Gray
    Write-Host "  3. Access locally: http://12sgi.local:8080/site/" -ForegroundColor Gray
    Write-Host ""
    Write-Host "📚 Read documentation:" -ForegroundColor Yellow
    Write-Host "  1. LOCAL_HOSTING_MASTER.md" -ForegroundColor Gray
    Write-Host "  2. LOCAL_HOSTING_COMPLETE.md" -ForegroundColor Gray
    Write-Host ""
}

function Stop-Systems {
    Write-Host "🛑 Stopping Local Hosting Systems" -ForegroundColor Yellow
    
    $deploymentProcess = Get-Process python -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -like "*local_deployment*"}
    $recoveryProcess = Get-Process python -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -like "*service_auto_recovery*"}
    
    if ($deploymentProcess) {
        Write-Host "Stopping deployment system..." -ForegroundColor Cyan
        Stop-Process -InputObject $deploymentProcess -Force
        Write-Host "✓ Deployment system stopped" -ForegroundColor Green
    }
    
    if ($recoveryProcess) {
        Write-Host "Stopping auto-recovery monitor..." -ForegroundColor Cyan
        Stop-Process -InputObject $recoveryProcess -Force
        Write-Host "✓ Auto-recovery stopped" -ForegroundColor Green
    }
    
    if (-not $deploymentProcess -and -not $recoveryProcess) {
        Write-Host "✓ No systems running" -ForegroundColor Green
    }
}

function Show-Status {
    Write-Host "📊 System Status" -ForegroundColor Green
    Write-Host ""
    
    # Check webhook port
    Write-Host "🔍 Checking services..." -ForegroundColor Cyan
    
    $webhook = netstat -ano | findstr :9000
    if ($webhook) {
        Write-Host "  ✓ Webhook server: LISTENING (port 9000)" -ForegroundColor Green
    } else {
        Write-Host "  ❌ Webhook server: NOT LISTENING (port 9000)" -ForegroundColor Red
    }
    
    # Check docker services
    try {
        $containers = docker compose -f "$RepoPath\docker-compose.v2.yml" ps --quiet 2>$null
        $count = @($containers).Count
        Write-Host "  ✓ Docker containers: $count running" -ForegroundColor Green
    } catch {
        Write-Host "  ⚠ Docker: Cannot connect" -ForegroundColor Yellow
    }
    
    # Check deployment logs
    if (Test-Path "$LogDir\deployments.jsonl") {
        $lastDeploy = Get-Content "$LogDir\deployments.jsonl" -Tail 1 | ConvertFrom-Json
        Write-Host "  ✓ Last deployment: $($lastDeploy.status) ($($lastDeploy.elapsed_seconds)s)" -ForegroundColor Green
    } else {
        Write-Host "  ℹ No deployments yet" -ForegroundColor Cyan
    }
    
    Write-Host ""
}

function Show-Logs {
    Write-Host "📋 Recent Deployment Logs" -ForegroundColor Green
    Write-Host ""
    
    if (Test-Path "$LogDir\deployments.jsonl") {
        $logs = Get-Content "$LogDir\deployments.jsonl" -Tail $LogLines
        foreach ($log in $logs) {
            $entry = $log | ConvertFrom-Json
            $color = if ($entry.status -eq "success") { "Green" } else { "Red" }
            Write-Host "[$($entry.status.ToUpper())] $($entry.timestamp) - $($entry.commit_sha.Substring(0,7))" -ForegroundColor $color
        }
    } else {
        Write-Host "No deployment logs found" -ForegroundColor Yellow
    }
    
    Write-Host ""
}

function Show-Dashboard {
    Write-Host "📊 Opening Status Dashboard..." -ForegroundColor Cyan
    
    cd $RepoPath
    python $StatusScript
}

# Execute action
switch ($Action.ToLower()) {
    "start" { Start-Systems }
    "stop" { Stop-Systems }
    "status" { Show-Status }
    "logs" { Show-Logs }
    "dashboard" { Show-Dashboard }
    default { Start-Systems }
}
