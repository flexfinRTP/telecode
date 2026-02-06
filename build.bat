@echo off
REM ============================================
REM TeleCode v0.1 - Build Executable (Windows)
REM ============================================
REM Packages TeleCode as a standalone .exe file
REM Requires PyInstaller: pip install pyinstaller
REM ============================================

echo.
echo ========================================
echo   TeleCode Build Script
echo ========================================
echo.

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Check for PyInstaller
pip show pyinstaller > nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

echo Building TeleCode executable...
echo.

REM Use the spec file which includes all necessary imports
pyinstaller --clean --noconfirm build\telecode_windows.spec

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Build Complete!
echo ========================================
echo.
echo Executable: dist\TeleCode.exe
echo.

REM Generate SHA256 checksum
echo Generating SHA256 checksum...
certutil -hashfile dist\TeleCode.exe SHA256 > dist\TeleCode.exe.sha256

echo Checksum saved to dist\TeleCode.exe.sha256
echo.
echo Done!
pause

