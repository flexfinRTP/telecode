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
REM Use full path to tscon.exe (required when PATH may not include System32)
%SystemRoot%\System32\tscon.exe %sessionname% /dest:console

if errorlevel 1 (
    echo.
    echo ========================================
    echo   ERROR: TSCON FAILED
    echo ========================================
    echo.
    echo Possible causes:
    echo   - Not running as Administrator
    echo   - Running in Remote Desktop session
    echo   - Windows Home edition (limited support)
    echo.
    echo Current session: %sessionname%
    echo.
    echo HOW TO FIX:
    echo   1. Close this window
    echo   2. Right-click "tscon_lock_verbose.bat"
    echo   3. Select "Run as administrator"
    echo.
    pause
)

