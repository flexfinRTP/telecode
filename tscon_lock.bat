@echo off
REM ============================================
REM TeleCode Quick Lock
REM ============================================
REM Run as Administrator to disconnect display
REM while keeping TeleCode active!
REM ============================================

echo Disconnecting session for TeleCode...

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

REM If still not found, show error
echo.
echo ERROR: TSCON.EXE NOT FOUND
echo.
echo TSCON.exe is missing from Windows System32.
echo This may indicate:
echo   - Windows Home edition (TSCON may not be available)
echo   - Corrupted Windows installation
echo   - System files are missing
echo.
echo NOTE: TSCON is primarily available on Windows Pro/Enterprise/Server.
echo.
pause
exit /b 1

:tscon_found

REM Query current session to get session ID
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
echo Session ID: %SESSION_ID%
"%TSCON_PATH%" %SESSION_ID% /dest:console

if errorlevel 1 (
    echo.
    echo ERROR: TSCON failed!
    echo.
    echo Possible causes:
    echo   - Not running as Administrator (right-click ^> Run as administrator)
    echo   - Running in Remote Desktop session (TSCON won't work over RDP)
    echo   - Windows Home edition has limited TSCON support
    echo   - Session ID not found
    echo.
    echo Diagnostic information:
    echo   TSCON path: %TSCON_PATH%
    echo   Session ID: %SESSION_ID%
    echo.
    echo Current sessions:
    query session
    echo.
    pause
    exit /b 1
)

