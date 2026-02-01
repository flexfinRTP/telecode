@echo off
REM ============================================
REM TeleCode v0.1 - Quick Start Script (Windows)
REM ============================================

echo Starting TeleCode...
echo.

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Start the bot
python main.py

pause

