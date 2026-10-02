@echo off
REM 12sgi-king Local Hosting - One Click Start

cd /d "C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king"

REM Open the HTML dashboard
start LOCAL_HOSTING_INDEX.html

REM Wait a moment for browser to open
timeout /t 2 /nobreak

REM Show simple menu
echo.
echo ================================================================================
echo 12sgi-king LOCAL HOSTING SYSTEM
echo ================================================================================
echo.
echo This will start your complete local hosting system.
echo.
echo What would you like to do?
echo.
echo 1. Start both systems (deployment + auto-recovery)
echo 2. Just check status
echo 3. View recent logs
echo 4. Open dashboard in browser
echo 5. Exit
echo.

set /p choice="Enter choice (1-5): "

if "%choice%"=="1" (
    echo.
    echo Starting systems...
    echo.
    powershell -ExecutionPolicy Bypass -Command "& '.\manage_local_hosting.ps1' -Action start"
    pause
) else if "%choice%"=="2" (
    echo.
    powershell -ExecutionPolicy Bypass -Command "& '.\manage_local_hosting.ps1' -Action status"
    pause
) else if "%choice%"=="3" (
    echo.
    powershell -ExecutionPolicy Bypass -Command "& '.\manage_local_hosting.ps1' -Action logs"
    pause
) else if "%choice%"=="4" (
    start LOCAL_HOSTING_INDEX.html
) else (
    echo Exiting...
)
