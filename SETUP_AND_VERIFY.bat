@echo off
REM 12sgi-king Complete Setup and Verify

setlocal enabledelayedexpansion

echo.
echo ================================================================================
echo 12sgi-king LOCAL HOSTING - SETUP AND VERIFY
echo ================================================================================
echo.

cd /d "C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king"

REM Kill any existing serve.py
taskkill /IM python.exe /F /FI "WINDOWTITLE eq *serve.py*" >nul 2>&1

echo Step 1: Starting Web Server on Port 8080...
start /B python serve.py 8080 >nul 2>&1

REM Wait for server to start
timeout /t 2 /nobreak >nul

echo Step 2: Checking Docker Services...
docker compose -f docker-compose.v2.yml ps >nul 2>&1
if %errorlevel% equ 0 (
    echo  - Docker services OK
) else (
    echo  - Starting Docker services...
    docker compose -f docker-compose.v2.yml up -d >nul 2>&1
)

echo.
echo ================================================================================
echo SUCCESS! LOCAL HOSTING IS READY
echo ================================================================================
echo.

echo ACCESS YOUR SYSTEM:
echo.
echo 1. BEST FOR TESTING (localhost, no DNS needed):
echo    http://127.0.0.1:8080/site/
echo.
echo 2. VIA TAILSCALE (if connected to tailnet):
echo    http://100.124.152.3:8080/site/
echo.
echo 3. VIA DOMAIN (after DNS update in Wix):
echo    http://12sgi.com:8080/site/
echo.

echo TEST AUTOMATIC DEPLOYMENT:
echo   1. Make a change
echo   2. git add .
echo   3. git commit -m "test"
echo   4. git push origin main
echo.

echo DOCUMENTATION:
echo   - README_LOCAL_HOSTING.md
echo   - LOCAL_HOSTING_MASTER.md
echo.

echo Opening default browser with localhost...
timeout /t 2 /nobreak >nul
start http://127.0.0.1:8080/site/

echo.
echo Ready! Check your browser.
pause
