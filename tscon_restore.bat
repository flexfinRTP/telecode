@echo off
REM ============================================
REM TeleCode TSCON - Restore Security Settings
REM ============================================
REM Run this after using SECURE lock to restore
REM Remote Desktop functionality.
REM ============================================

echo.
echo ================================================
echo   TeleCode - Restore Security Settings
echo ================================================
echo.
echo This will restore Remote Desktop functionality
echo after using the SECURE lock mode.
echo.
pause

echo.
echo [1/2] Enabling Remote Desktop...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 0 /f > nul 2>&1
if errorlevel 1 (
    echo       ERROR: Could not enable RDP
    echo       Make sure to run as Administrator!
    pause
    exit /b 1
)
echo       Remote Desktop: ENABLED

echo.
echo [2/2] Starting Remote Desktop service...
net start TermService > nul 2>&1
echo       TermService: Started

echo.
echo ================================================
echo   Settings Restored Successfully
echo ================================================
echo.
echo Remote Desktop is now enabled again.
echo.
pause

