@echo off
REM ============================================
REM TeleCode - Turn Off Display
REM ============================================
REM This turns off your monitor while keeping
REM TeleCode and Cursor running in the background.
REM Works on ALL Windows editions - no admin required!
REM pyautogui works perfectly!
REM ============================================

echo.
echo ========================================
echo   TeleCode - Turn Off Display
echo ========================================
echo.
echo This will turn off your monitor while
echo keeping your session ACTIVE.
echo.
echo After running:
echo   - Monitor will turn OFF (screen goes black)
echo   - SECURE LOCK activated (password/PIN required on wake)
echo   - TeleCode continues working
echo   - Cursor IDE stays active
echo   - pyautogui works perfectly!
echo   - You can still control via Telegram
echo.
echo SECURITY:
echo   - When monitor wakes, password/PIN prompt appears
echo   - Blocks ALL desktop input until unlocked
echo   - Protects your computer from physical access
echo.
echo To UNLOCK:
echo   - Move mouse or press any key (wakes monitor)
echo   - Enter your Windows password or TeleCode PIN
echo   - Or use system tray: Turn On Display
echo.
echo ========================================
echo.
pause

echo.
echo Turning off display with SECURE LOCK...
echo Password/PIN will be required when monitor wakes.
echo.
python -m src.virtual_display_helper --off --secure

if errorlevel 1 (
    echo.
    echo ERROR: Failed to turn off display!
    pause
    exit /b 1
)

echo.
echo Display turned off successfully!
echo TeleCode continues working in the background.
timeout /t 2 > nul

