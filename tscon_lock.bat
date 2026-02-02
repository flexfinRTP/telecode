@echo off
REM ============================================
REM TeleCode Quick Lock
REM ============================================
REM Run as Administrator to disconnect display
REM while keeping TeleCode active!
REM ============================================

echo Disconnecting session for TeleCode...
REM Use full path to tscon.exe (required when PATH may not include System32)
%SystemRoot%\System32\tscon.exe %sessionname% /dest:console

if errorlevel 1 (
    echo.
    echo ERROR: TSCON failed!
    echo.
    echo Possible causes:
    echo   - Not running as Administrator (right-click ^> Run as administrator)
    echo   - Running in Remote Desktop session (TSCON won't work over RDP)
    echo   - Windows Home edition has limited TSCON support
    echo.
    echo Current session: %sessionname%
    pause
)

