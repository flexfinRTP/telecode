@echo off
REM ============================================
REM TeleCode TSCON Session Lock
REM ============================================
REM 
REM WHAT THIS DOES:
REM   Disconnects your screen while keeping your
REM   Windows session running in memory.
REM
REM WHY USE THIS:
REM   - Cursor IDE continues running
REM   - TeleCode can control Cursor via Telegram
REM   - GUI automation works in background
REM
REM SECURITY WARNING:
REM   - Only use on TRUSTED networks
REM   - Your session is technically "unlocked"
REM   - Physical access = potential access
REM   - Use BitLocker for disk encryption
REM
REM TO RECONNECT:
REM   - Press any key or move mouse
REM   - Enter your Windows password
REM
REM ============================================

echo.
echo ========================================
echo   TeleCode TSCON Session Lock
echo ========================================
echo.
echo This will disconnect your display while
echo keeping your Windows session ACTIVE.
echo.
echo AFTER RUNNING:
echo   [x] Screen goes BLACK (appears locked)
echo   [x] TeleCode continues running
echo   [x] Cursor IDE stays active
echo   [x] Control via Telegram works!
echo.
echo TO RECONNECT:
echo   1. Press any key or move mouse
echo   2. Enter your Windows password
echo.
echo ========================================
echo.
echo Press any key to disconnect session...
pause > nul

echo.
echo Disconnecting session...

REM Find tscon.exe - handle 32-bit/64-bit Windows correctly
set "TSCON_PATH="

REM Try multiple path variations
if exist "%SystemRoot%\Sysnative\tscon.exe" (
    set "TSCON_PATH=%SystemRoot%\Sysnative\tscon.exe"
    goto :tscon_found
)

if exist "%SystemRoot%\System32\tscon.exe" (
    set "TSCON_PATH=%SystemRoot%\System32\tscon.exe"
    goto :tscon_found
)

if exist "%windir%\System32\tscon.exe" (
    set "TSCON_PATH=%windir%\System32\tscon.exe"
    goto :tscon_found
)

REM Try using WHERE command
where tscon.exe >nul 2>&1
if %errorlevel% == 0 (
    for /f "delims=" %%i in ('where tscon.exe 2^>nul') do (
        set "TSCON_PATH=%%i"
        goto :tscon_found
    )
)

REM If still not found, show detailed error
echo.
echo ========================================
echo   ERROR: TSCON.EXE NOT FOUND
echo ========================================
echo.
echo Diagnostic information:
echo   SystemRoot: %SystemRoot%
echo   windir: %windir%
echo.
echo TSCON.exe is missing from Windows System32.
echo This may indicate:
echo   - Windows Home edition (TSCON may not be available)
echo   - Corrupted Windows installation
echo   - System files are missing
echo.
echo NOTE: TSCON is primarily available on Windows Pro/Enterprise/Server editions.
echo       Windows Home edition has limited or no TSCON support.
echo.
pause
exit /b 1

:tscon_found

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
"%TSCON_PATH%" %SESSION_ID% /dest:console

if errorlevel 1 (
    echo.
    echo ========================================
    echo   ERROR: TSCON FAILED
    echo ========================================
    echo.
    echo TSCON command failed with error code: %errorlevel%
    echo.
    echo Possible causes:
    echo   - Not running as Administrator
    echo   - Running in Remote Desktop session (TSCON won't work over RDP)
    echo   - Windows Home edition (limited support)
    echo   - Session ID not found or invalid
    echo.
    echo Diagnostic information:
    echo   TSCON path: %TSCON_PATH%
    echo   Session ID: %SESSION_ID%
    echo   Username: %USERNAME%
    echo.
    echo Current sessions:
    query session
    echo.
    echo HOW TO FIX:
    echo   1. Close this window
    echo   2. Right-click "tscon_lock_verbose.bat"
    echo   3. Select "Run as administrator"
    echo   4. Make sure you're not running over RDP
    echo.
    pause
    exit /b 1
)

