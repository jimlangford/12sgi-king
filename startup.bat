@echo off
REM startup.bat - boot all 12sgi-king services with health checks (Windows)
REM
REM Usage: startup.bat
REM        startup.bat --daemon (run watchdog in background)
REM
REM Features:
REM   - Starts docker-compose stack
REM   - Launches king-watchdog (Node.js)
REM   - Health checks for all services
REM   - Auto-compact configuration
REM
REM Fixed 2026-07-14: file previously contained literal \n escape sequences instead of
REM real newlines (unrunnable), and the :log subroutine sat inline in the execution path
REM (top-down flow fell into it and hit goto :EOF, exiting before any work). Subroutine
REM now lives at the end, past the exit. Kept pure ASCII (the .bat ASCII gotcha).

setlocal enabledelayedexpansion

set "HERE=%~dp0"
set "LOG=%HERE%startup.log"
set "WATCHDOG_PID_FILE=%HERE%.watchdog.pid"

REM --- Initialize -------------------------------------------------------------
REM Check if Docker is installed
where docker >nul 2>&1
if %errorlevel% neq 0 (
  echo Error: Docker not found. Install Docker Desktop and try again.
  exit /b 1
)

REM Check if Node.js is installed
where node >nul 2>&1
if %errorlevel% neq 0 (
  echo Error: Node.js not found. Install Node.js 18+ and try again.
  exit /b 1
)

echo.
echo === 12sgi-king STARTUP SEQUENCE ===
echo.
call :log "Starting 12sgi-king services (13 tenants, 25 characters)"

REM --- Phase 1: Docker Services -----------------------------------------------
echo.
echo Phase 1: Starting Docker services...
call :log "Phase 1: Starting Docker services"

REM Check if docker daemon is running
docker ps >nul 2>&1
if %errorlevel% neq 0 (
  echo Error: Docker daemon not running. Start Docker Desktop and try again.
  call :log "ERROR: Docker daemon not running"
  exit /b 1
)
echo OK: Docker daemon is running
call :log "OK: Docker daemon is running"

REM Start docker-compose stack
if exist "%HERE%docker-compose.v2.yml" (
  echo Bringing up docker-compose stack...
  call :log "Bringing up docker-compose stack"
  cd /d "%HERE%"
  call docker-compose -f docker-compose.v2.yml up -d
  if !errorlevel! neq 0 (
    call :log "WARNING: docker-compose up returned non-zero"
  )
  timeout /t 5 /nobreak >nul
) else (
  call :log "WARNING: docker-compose.v2.yml not found - skipping Docker stack"
)

REM --- Phase 2: Process Services ------------------------------------------------
echo.
echo Phase 2: Starting managed processes...
call :log "Phase 2: Starting managed processes (king-bridge, static server)"

echo Starting king-watchdog (Node.js)...
call :log "Starting king-watchdog"

if "%~1"=="--daemon" (
  REM Run in background
  start "king-watchdog" /B node "%HERE%king-watchdog.js" >> "%LOG%" 2>&1
  echo watchdog started in background (check %LOG%)
  call :log "Watchdog started in background"
) else (
  REM Run in foreground
  node "%HERE%king-watchdog.js"
  call :log "Watchdog exited"
  exit /b !errorlevel!
)

timeout /t 3 /nobreak >nul

REM Health check for king-bridge
echo Checking king-bridge API health...
call :log "Checking king-bridge API health"
for /L %%i in (1,1,12) do (
  for /f "tokens=*" %%A in ('powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://localhost:8109/api/v2/ready' -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch { $false }" 2^>nul') do set "READY=%%A"
  if "!READY!"=="True" (
    echo OK: king-bridge API is ready
    call :log "OK: king-bridge API ready on :8109"
    goto :skip_kingbridge
  )
  if %%i lss 12 timeout /t 2 /nobreak >nul
)
echo WARNING: king-bridge not responding yet (watchdog will retry)
call :log "WARNING: king-bridge not responding yet"
:skip_kingbridge

REM Health check for static server
echo Checking static server health...
call :log "Checking static server health"
for /L %%i in (1,1,6) do (
  for /f "tokens=*" %%A in ('powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://localhost:8888/' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { $false }" 2^>nul') do set "READY=%%A"
  if "!READY!"=="True" (
    echo OK: Static server is ready
    call :log "OK: Static server ready on :8888"
    goto :skip_static
  )
  if %%i lss 6 timeout /t 1 /nobreak >nul
)
echo WARNING: Static server not responding yet
call :log "WARNING: Static server not responding yet"
:skip_static

REM --- Phase 3: Optional Checks -------------------------------------------------
echo.
echo Phase 3: Checking optional services...
call :log "Phase 3: Checking optional services"

where ollama >nul 2>&1
if %errorlevel% equ 0 (
  echo Checking Ollama...
  for /L %%i in (1,1,3) do (
    for /f "tokens=*" %%A in ('powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { $false }" 2^>nul') do set "READY=%%A"
    if "!READY!"=="True" (
      echo OK: Ollama is ready
      call :log "OK: Ollama ready on :11434 (inference available)"
      goto :skip_ollama
    )
    if %%i lss 3 timeout /t 1 /nobreak >nul
  )
  echo WARNING: Ollama not responding
  call :log "WARNING: Ollama not responding - inference unavailable"
) else (
  call :log "NOTE: Ollama not installed - skip if you don't need local inference"
)
:skip_ollama

REM --- Phase 4: Auto-Compact Configuration --------------------------------------
echo.
echo Phase 4: Configuring auto-compact and best features...
call :log "Phase 4: Configuring auto-compact"

if exist "%HERE%services\king_bridge\app\main.py" (
  echo Conversation auto-compaction ready:
  echo   Set NEO4J_CONV_TTL_DAYS=30 to auto-compact after 30 days
  echo   Set NEO4J_CONV_BATCH_SIZE=1000 for batch processing
  call :log "Auto-compact settings available via environment variables"
)

REM --- Summary -------------------------------------------------------------------
echo.
echo ===================================================================
echo STARTUP COMPLETE
echo ===================================================================
echo.
echo Dashboard:        http://localhost:8888/king_landing.html
echo king-bridge API:  http://localhost:8109/api/v2/
echo Studio Assets:    http://localhost:8108/api/v2/
echo Neo4j Browser:    http://localhost:7474/
echo Watchdog log:     %HERE%watchdog.log
echo Startup log:      %LOG%
echo.
echo Services:
echo   13 Tenants (9 films, 1 game, 2 music videos, 1 civic studio)
echo   25 Named characters across all tenants
echo   6 Lipsync skills (dialogue, ceremony, rhythm, song, 3D, etc.)
echo   5 Render registers (photoreal, cartoon-3d, animated, etc.)
echo   12 Civic divisions (HI state, counties, NY, etc.)
echo.
echo Tailscale integration (optional):
echo   tailscale serve --bg http://8109  (expose king-bridge)
echo   tailscale serve --bg http://8888  (expose dashboard)
echo.
call :log "Startup sequence complete"
echo.
exit /b 0

REM --- Logging subroutine (must live past the exit so top-down flow never falls in)
:log
echo [%date% %time%] %~1 >> "%LOG%"
echo [%date% %time%] %~1
goto :EOF
