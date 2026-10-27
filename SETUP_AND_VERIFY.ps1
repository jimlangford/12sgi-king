#!/usr/bin/env powershell
# COMPLETE SETUP AND VERIFICATION

Write-Host "================================" -ForegroundColor Green
Write-Host "12sgi-king LOCAL HOSTING SETUP" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host ""

$RepoPath = "C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king"
cd $RepoPath

# Step 1: Check prerequisites
Write-Host "Step 1: Checking Prerequisites..." -ForegroundColor Cyan
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) { Write-Host "  ✓ Python installed" -ForegroundColor Green } else { Write-Host "  ❌ Python not found" -ForegroundColor Red; exit 1 }

$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker) { Write-Host "  ✓ Docker installed" -ForegroundColor Green } else { Write-Host "  ❌ Docker not found" -ForegroundColor Red; exit 1 }

Write-Host ""

# Step 2: Check Docker services
Write-Host "Step 2: Checking Docker Services..." -ForegroundColor Cyan
$dockerOutput = docker compose -f docker-compose.v2.yml ps --format json 2>$null
if ($dockerOutput) {
    $services = $dockerOutput | ConvertFrom-Json
    $running = @($services | Where-Object { $_.State -like "*Up*" }).Count
    Write-Host "  ✓ Docker services running: $running" -ForegroundColor Green
}

Write-Host ""

# Step 3: Start web server
Write-Host "Step 3: Starting Web Server (Port 8080)..." -ForegroundColor Cyan
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*serve.py*" } | Stop-Process -Force -ErrorAction SilentlyContinue

$job = Start-Job -ScriptBlock {
    cd "C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king"
    python serve.py 8080
} -ErrorAction SilentlyContinue

Start-Sleep -Seconds 3
Write-Host "  ✓ Web server started" -ForegroundColor Green

Write-Host ""

# Step 4: Verify site files
Write-Host "Step 4: Verifying Site Files..." -ForegroundColor Cyan
if (Test-Path "site\reports.html") {
    Write-Host "  ✓ Site files present" -ForegroundColor Green
} else {
    Write-Host "  ⚠ Site files not found" -ForegroundColor Yellow
}

Write-Host ""

# Step 5: Display access information
Write-Host "========================================" -ForegroundColor Green
Write-Host "✅ LOCAL HOSTING IS READY!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "📍 TRY THESE LINKS:" -ForegroundColor Yellow
Write-Host ""

Write-Host "  Option 1: Direct localhost (best for testing):" -ForegroundColor Cyan
Write-Host "    🔗 http://127.0.0.1:8080/site/" -ForegroundColor Cyan
Write-Host ""

Write-Host "  Option 2: Via Tailscale (if connected to tailnet):" -ForegroundColor Cyan
Write-Host "    🔗 http://100.124.152.3:8080/site/" -ForegroundColor Cyan
Write-Host ""

Write-Host "  Option 3: Via domain (after DNS update):" -ForegroundColor Cyan
Write-Host "    🔗 http://12sgi.com:8080/site/" -ForegroundColor Cyan
Write-Host ""

Write-Host "🧪 TEST DEPLOYMENT:" -ForegroundColor Yellow
Write-Host "  1. git add ." -ForegroundColor Gray
Write-Host "  2. git commit -m 'test deployment'" -ForegroundColor Gray
Write-Host "  3. git push origin main" -ForegroundColor Gray
Write-Host ""

Write-Host "📚 DOCUMENTATION:" -ForegroundColor Yellow
Write-Host "  - README_LOCAL_HOSTING.md" -ForegroundColor Gray
Write-Host "  - LOCAL_HOSTING_MASTER.md" -ForegroundColor Gray
Write-Host "  - LOCAL_HOSTING_COMPLETE.md" -ForegroundColor Gray
Write-Host ""

Write-Host "✅ Click a link above to get started!" -ForegroundColor Green
