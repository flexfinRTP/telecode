@echo off
REM ============================================
REM TeleCode Quick Lock
REM ============================================
REM Run as Administrator to disconnect display
REM while keeping TeleCode active!
REM ============================================

echo Disconnecting session for TeleCode...
tscon %sessionname% /dest:console

if errorlevel 1 (
    echo.
    echo ERROR: Run this as Administrator!
    echo Right-click ^> "Run as administrator"
    pause
)

