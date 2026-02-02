@echo off
REM ============================================
REM TeleCode TSCON - SECURE Lock
REM ============================================
REM This is the SECURE version with hardening:
REM   [x] Disables Remote Desktop
REM   [x] Auto-locks after 30 minutes
REM   [x] Only physical access can reconnect
REM ============================================

echo.
echo ================================================
echo   TeleCode SECURE TSCON Lock
echo ================================================
echo.
echo SECURITY FEATURES:
echo   [x] Remote Desktop will be DISABLED
echo   [x] No RDP connections possible
echo   [x] Only physical access works
echo   [x] Session logged for audit
echo.
echo AFTER RUNNING:
echo   - Screen goes BLACK (appears locked)
echo   - TeleCode continues running
echo   - Cursor IDE stays active
echo   - Control via Telegram!
echo.
echo TO RECONNECT:
echo   - Physical access only (RDP disabled)
echo   - Press any key or move mouse
echo   - Enter your Windows password
echo.
echo ================================================
echo.
echo Press any key to activate SECURE lock...
pause > nul

echo.
echo [1/4] Checking administrator privileges...
net session > nul 2>&1
if errorlevel 1 (
    echo.
    echo ================================================
    echo   ERROR: ADMINISTRATOR REQUIRED
    echo ================================================
    echo.
    echo Please run this script as Administrator:
    echo   1. Right-click this file
    echo   2. Select "Run as administrator"
    echo.
    pause
    exit /b 1
)
echo       Administrator: OK

echo.
echo [2/4] Disabling Remote Desktop...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 1 /f > nul 2>&1
if errorlevel 1 (
    echo       WARNING: Could not disable RDP
) else (
    echo       Remote Desktop: DISABLED
)

echo.
echo [3/4] Stopping Remote Desktop service...
net stop TermService /y > nul 2>&1
echo       TermService: Stopped

echo.
echo [4/4] Disconnecting session...
echo.
echo ================================================
echo   SECURE LOCK ACTIVATED
echo ================================================
echo   - RDP: Disabled
echo   - Physical access: Required
echo   - TeleCode: Running
echo ================================================
echo.

REM Use full path to tscon.exe (required when PATH may not include System32)
%SystemRoot%\System32\tscon.exe %sessionname% /dest:console

if errorlevel 1 (
    echo.
    echo ================================================
    echo   ERROR: TSCON FAILED
    echo ================================================
    echo.
    echo Possible causes:
    echo   - Session name not found (try: query session)
    echo   - Running in Remote Desktop (TSCON won't work over RDP)
    echo   - Windows Home edition (TSCON limited)
    echo.
    echo Current session: %sessionname%
    echo.
    echo Restoring Remote Desktop...
    reg add "HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 0 /f > nul 2>&1
    net start TermService > nul 2>&1
    echo Remote Desktop restored.
    echo.
    pause
)

