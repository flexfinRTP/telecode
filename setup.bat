@echo off
REM ============================================
REM TeleCode v0.1 - Windows Setup Script
REM ============================================
REM This script will:
REM 1. Check for Python 3.10+
REM 2. Check for Git
REM 3. Check for FFmpeg (optional, for voice)
REM 4. Create virtual environment
REM 5. Install dependencies
REM 6. Launch the configuration GUI
REM ============================================

echo.
echo ========================================
echo   TeleCode v0.1 Setup Script
echo   Remote Cursor Commander
echo ========================================
echo.

REM Check for Python
echo [1/5] Checking for Python...
python --version > nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%I in ('python --version 2^>^&1') do set PYTHON_VERSION=%%I
echo       Found Python %PYTHON_VERSION%

REM Check for Git
echo [2/5] Checking for Git...
git --version > nul 2>&1
if errorlevel 1 (
    echo WARNING: Git is not installed. Git features will not work.
    echo Install Git from https://git-scm.com/download/win
) else (
    for /f "tokens=3" %%I in ('git --version') do set GIT_VERSION=%%I
    echo       Found Git %GIT_VERSION%
)

REM Check for FFmpeg (optional)
echo [3/5] Checking for FFmpeg (optional, for voice)...
ffmpeg -version > nul 2>&1
if errorlevel 1 (
    echo       FFmpeg not found. Voice features will be disabled.
    echo       To enable voice, install FFmpeg: https://ffmpeg.org/download.html
) else (
    echo       FFmpeg found - Voice features enabled!
)

REM Create virtual environment
echo [4/5] Setting up virtual environment...
if not exist "venv" (
    python -m venv venv
    echo       Created new virtual environment
) else (
    echo       Using existing virtual environment
)

REM Activate venv and install dependencies
echo [5/5] Installing dependencies...
call venv\Scripts\activate.bat

python -m pip install --upgrade pip > nul 2>&1
pip install -r requirements.txt

if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo Next steps:
echo   1. Get a Bot Token from @BotFather on Telegram
echo   2. Get your User ID from @userinfobot on Telegram
echo   3. Run 'start.bat' to launch TeleCode
echo.
echo Launching configuration GUI...
echo.

python main.py --config

pause

