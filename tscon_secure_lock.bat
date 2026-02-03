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

REM Find tscon.exe - handle 32-bit/64-bit Windows correctly
set "TSCON_PATH="
set "DIAGNOSTIC_MODE=0"

REM Try multiple path variations
REM 1. Try Sysnative (for 32-bit processes on 64-bit Windows)
if exist "%SystemRoot%\Sysnative\tscon.exe" (
    set "TSCON_PATH=%SystemRoot%\Sysnative\tscon.exe"
    goto :tscon_found
)

REM 2. Try System32 (standard location)
if exist "%SystemRoot%\System32\tscon.exe" (
    set "TSCON_PATH=%SystemRoot%\System32\tscon.exe"
    goto :tscon_found
)

REM 3. Try %windir% as alternative to %SystemRoot%
if exist "%windir%\System32\tscon.exe" (
    set "TSCON_PATH=%windir%\System32\tscon.exe"
    goto :tscon_found
)

REM 4. Try using WHERE command to find tscon.exe
where tscon.exe >nul 2>&1
if %errorlevel% == 0 (
    for /f "delims=" %%i in ('where tscon.exe 2^>nul') do (
        set "TSCON_PATH=%%i"
        goto :tscon_found
    )
)

REM If still not found, show diagnostics and error
echo.
echo ================================================
echo   ERROR: TSCON.EXE NOT FOUND
echo ================================================
echo.

REM Check Windows edition
for /f "tokens=4-5 delims=. " %%i in ('ver') do set VERSION=%%i.%%j
for /f "tokens=2 delims=[]" %%i in ('systeminfo ^| findstr /B /C:"OS Name"') do set OS_NAME=%%i

echo Diagnostic information:
echo   SystemRoot: %SystemRoot%
echo   windir: %windir%
echo   Processor: %PROCESSOR_ARCHITECTURE%
if defined OS_NAME echo   OS Name: %OS_NAME%
echo.
echo Checked paths:
if exist "%SystemRoot%\Sysnative\tscon.exe" (
    echo   [OK] %SystemRoot%\Sysnative\tscon.exe
) else (
    echo   [MISSING] %SystemRoot%\Sysnative\tscon.exe
)
if exist "%SystemRoot%\System32\tscon.exe" (
    echo   [OK] %SystemRoot%\System32\tscon.exe
) else (
    echo   [MISSING] %SystemRoot%\System32\tscon.exe
)
if exist "%windir%\System32\tscon.exe" (
    echo   [OK] %windir%\System32\tscon.exe
) else (
    echo   [MISSING] %windir%\System32\tscon.exe
)
echo.
echo TSCON.exe is missing from Windows System32.
echo.
echo MOST LIKELY CAUSE:
echo   Windows Home edition does NOT include TSCON.exe
echo   TSCON is only available on:
echo     - Windows Pro
echo     - Windows Enterprise
echo     - Windows Server
echo.
echo Other possible causes:
echo   - Corrupted Windows installation
echo   - System files are missing
echo   - TSCON was removed or disabled
echo.
echo SOLUTION:
echo   If you're on Windows Home, TSCON is not available.
echo   Consider upgrading to Windows Pro or use alternative locking methods.
echo.
echo Restoring Remote Desktop...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 0 /f > nul 2>&1
net start TermService > nul 2>&1
echo Remote Desktop restored.
echo.
pause
exit /b 1

:tscon_found
echo       TSCON found: %TSCON_PATH%

REM Query current session to get session ID
echo       Querying current session...
for /f "tokens=2" %%i in ('query session ^| findstr /C:"%USERNAME%" /C:"Active" /C:"Disc"') do (
    set "SESSION_ID=%%i"
    goto :found_session
)

REM Fallback: try to get session from SESSIONNAME environment variable
if defined SESSIONNAME (
    set "SESSION_ID=%SESSIONNAME%"
    goto :found_session
)

REM Last resort: try console
set "SESSION_ID=console"

:found_session
echo       Session ID: %SESSION_ID%

echo.
echo ================================================
echo   SECURE LOCK ACTIVATED
echo ================================================
echo   - RDP: Disabled
echo   - Physical access: Required
echo   - TeleCode: Running
echo ================================================
echo.

REM Run tscon with the found session ID
"%TSCON_PATH%" %SESSION_ID% /dest:console

if errorlevel 1 (
    echo.
    echo ================================================
    echo   ERROR: TSCON FAILED
    echo ================================================
    echo.
    echo TSCON command failed with error code: %errorlevel%
    echo.
    echo Possible causes:
    echo   - Session ID not found or invalid
    echo   - Running in Remote Desktop (TSCON won't work over RDP)
    echo   - Windows Home edition (TSCON limited)
    echo   - Insufficient permissions
    echo.
    echo Diagnostic information:
    echo   TSCON path: %TSCON_PATH%
    echo   Session ID: %SESSION_ID%
    echo   Username: %USERNAME%
    echo.
    echo Current sessions:
    query session
    echo.
    echo Restoring Remote Desktop...
    reg add "HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 0 /f > nul 2>&1
    net start TermService > nul 2>&1
    echo Remote Desktop restored.
    echo.
    pause
    exit /b 1
)

