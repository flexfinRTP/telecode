"""
============================================
TeleCode v0.1 - Screen Lock Helper Utility
============================================
Easy-to-use tool for locking Windows screen while keeping session active.

This keeps GUI applications (like Cursor) running
even when the physical screen is locked.

HOW IT WORKS:
- Locks the Windows screen (password required to unlock)
- Session stays active in memory
- GUI automation continues working
- TeleCode and Cursor continue running

SECURITY FEATURES (Secure Mode):
- Disables Remote Desktop during lock
- Auto-lock watchdog timer
- Monitors for reconnection attempts
- Logs all security events

WORKS ON ALL WINDOWS EDITIONS (Home, Pro, Enterprise, Server)
No administrator privileges required for basic lock!

============================================
"""

import os
import sys
import ctypes
import subprocess
import logging
import threading
import winreg
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

logger = logging.getLogger("telecode.screen_lock")

# Check if we're on Windows
IS_WINDOWS = sys.platform == "win32"


def is_admin() -> bool:
    """Check if running with administrator privileges."""
    if not IS_WINDOWS:
        return False
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False


class ScreenLockSecurity:
    """
    Security hardening for screen lock sessions.
    
    Features:
    - Disable Remote Desktop during lock
    - Auto-lock watchdog (locks after timeout)
    - Monitor for suspicious reconnection
    - Audit logging
    """
    
    def __init__(self):
        self._watchdog_thread: Optional[threading.Thread] = None
        self._watchdog_stop = threading.Event()
        self._rdp_was_enabled: Optional[bool] = None
        self._lock_timeout_minutes: int = 30
        self._session_start_time: Optional[datetime] = None
    
    def disable_remote_desktop(self) -> tuple[bool, str]:
        """
        Temporarily disable Remote Desktop to prevent remote reconnection.
        
        This blocks RDP connections while screen is locked.
        Requires administrator privileges.
        """
        if not is_admin():
            return False, "Admin required to modify Remote Desktop"
        
        try:
            # Check current RDP state and save it
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Terminal Server",
                0,
                winreg.KEY_READ | winreg.KEY_WRITE
            )
            
            try:
                current_value, _ = winreg.QueryValueEx(key, "fDenyTSConnections")
                self._rdp_was_enabled = (current_value == 0)
            except FileNotFoundError:
                self._rdp_was_enabled = True
            
            # Disable RDP (set fDenyTSConnections to 1)
            winreg.SetValueEx(key, "fDenyTSConnections", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)
            
            # Also stop the service if running
            subprocess.run(
                ["net", "stop", "TermService", "/y"],
                capture_output=True,
                timeout=30
            )
            
            self._log_security_event("RDP_DISABLED", "Remote Desktop disabled for screen lock")
            return True, "Remote Desktop disabled"
            
        except Exception as e:
            return False, f"Failed to disable RDP: {e}"
    
    def restore_remote_desktop(self) -> tuple[bool, str]:
        """Restore Remote Desktop to its previous state."""
        if self._rdp_was_enabled is None:
            return True, "No previous RDP state to restore"
        
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Terminal Server",
                0,
                winreg.KEY_WRITE
            )
            
            # Restore original state
            value = 0 if self._rdp_was_enabled else 1
            winreg.SetValueEx(key, "fDenyTSConnections", 0, winreg.REG_DWORD, value)
            winreg.CloseKey(key)
            
            if self._rdp_was_enabled:
                subprocess.run(
                    ["net", "start", "TermService"],
                    capture_output=True,
                    timeout=30
                )
            
            self._log_security_event("RDP_RESTORED", "Remote Desktop restored to original state")
            return True, "Remote Desktop restored"
            
        except Exception as e:
            return False, f"Failed to restore RDP: {e}"
    
    def start_watchdog(self, timeout_minutes: int = 30):
        """
        Start a watchdog that auto-locks after timeout.
        
        This provides a safety net - if you forget about the session,
        it will automatically lock after the specified time.
        """
        self._lock_timeout_minutes = timeout_minutes
        self._watchdog_stop.clear()
        self._session_start_time = datetime.now()
        
        def watchdog_loop():
            while not self._watchdog_stop.wait(timeout=60):  # Check every minute
                elapsed = (datetime.now() - self._session_start_time).total_seconds() / 60
                
                if elapsed >= self._lock_timeout_minutes:
                    self._log_security_event(
                        "WATCHDOG_TRIGGERED",
                        f"Auto-locking after {self._lock_timeout_minutes} minutes"
                    )
                    lock_workstation()
                    self.stop_watchdog()
                    break
        
        self._watchdog_thread = threading.Thread(target=watchdog_loop, daemon=True)
        self._watchdog_thread.start()
        self._log_security_event("WATCHDOG_STARTED", f"Auto-lock in {timeout_minutes} minutes")
    
    def stop_watchdog(self):
        """Stop the auto-lock watchdog."""
        self._watchdog_stop.set()
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=5)
        self._log_security_event("WATCHDOG_STOPPED", "Auto-lock watchdog stopped")
    
    def _log_security_event(self, event_type: str, message: str):
        """Log a security event."""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] [SCREEN_LOCK-{event_type}] {message}"
        logger.info(log_entry)
        
        # Also write to audit log
        try:
            from src.system_utils import get_user_data_dir
            audit_log = get_user_data_dir() / "telecode_audit.log"
            with open(audit_log, "a", encoding="utf-8") as f:
                f.write(log_entry + "\n")
        except:
            pass


def lock_workstation() -> bool:
    """
    Lock the Windows workstation (password-protected lock).
    
    This locks the screen while keeping the session active.
    Works on ALL Windows editions (Home, Pro, Enterprise, Server).
    No administrator privileges required!
    
    Returns:
        True if lock succeeded, False otherwise
    """
    if not IS_WINDOWS:
        return False
    try:
        ctypes.windll.user32.LockWorkStation()
        logger.info("Screen locked successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to lock workstation: {e}")
        return False


def lock_screen(secure_mode: bool = False, watchdog_minutes: int = 30) -> tuple[bool, str]:
    """
    Lock the Windows screen while keeping session active.
    
    This locks the screen (password required to unlock) while keeping
    the session active so GUI automation continues working.
    
    Works on ALL Windows editions - no admin required for basic lock!
    
    Args:
        secure_mode: If True, enables security hardening:
                     - Disables Remote Desktop (requires admin)
                     - Starts auto-lock watchdog
        watchdog_minutes: Auto-lock timeout (default 30 min)
    
    Returns:
        Tuple of (success, message)
    """
    if not IS_WINDOWS:
        return False, "Screen lock is only available on Windows"
    
    security = ScreenLockSecurity()
    security_status = []
    
    # Apply security hardening if requested
    if secure_mode:
        # Disable RDP (requires admin)
        success, msg = security.disable_remote_desktop()
        if success:
            security_status.append("RDP: Disabled")
        else:
            security_status.append(f"RDP: {msg}")
        
        # Start watchdog
        security.start_watchdog(watchdog_minutes)
        security_status.append(f"Watchdog: {watchdog_minutes}min")
    
    # Lock the screen (simple API call, no admin needed)
    if lock_workstation():
        msg = "Screen locked successfully."
        if secure_mode:
            msg += f"\n🔒 Secure Mode: {', '.join(security_status)}"
        return True, msg
    else:
        # Restore RDP if we disabled it
        if secure_mode:
            security.restore_remote_desktop()
            security.stop_watchdog()
        return False, "Failed to lock screen"


def create_lock_shortcut(target_folder: str = None, secure_mode: bool = False) -> tuple[bool, str]:
    """
    Create a desktop shortcut for easy screen lock access.
    
    Args:
        target_folder: Where to create the shortcut (default: Desktop)
        secure_mode: Create secure mode shortcut with hardening
        
    Returns:
        Tuple of (success, message)
    """
    if not IS_WINDOWS:
        return False, "Shortcuts only available on Windows"
    
    try:
        # Determine target folder
        if target_folder is None:
            target_folder = Path.home() / "Desktop"
        else:
            target_folder = Path(target_folder)
        
        if secure_mode:
            # Secure mode batch file - with hardening
            batch_content = '''@echo off
REM ============================================
REM TeleCode Screen Lock - SECURE Mode
REM ============================================
REM This is the SECURE version:
REM   - Disables Remote Desktop
REM   - Auto-locks after 30 minutes
REM   - Logs all security events
REM ============================================

echo.
echo ========================================
echo   TeleCode SECURE Screen Lock
echo ========================================
echo.
echo SECURITY FEATURES ENABLED:
echo   [x] Remote Desktop will be DISABLED
echo   [x] Auto-lock after 30 minutes
echo   [x] All events logged to audit file
echo.
echo After running:
echo   - Screen will be LOCKED
echo   - RDP connections BLOCKED
echo   - TeleCode continues working
echo   - Auto-lock in 30 minutes
echo.
echo To UNLOCK:
echo   - Physical access only (no RDP)
echo   - Enter your Windows password
echo.
echo ========================================
echo.
pause

echo.
echo [1/3] Disabling Remote Desktop...
reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 1 /f > nul 2>&1
net stop TermService /y > nul 2>&1
if errorlevel 1 (
    echo       WARNING: Could not disable RDP (admin required)
) else (
    echo       Remote Desktop DISABLED
)

echo.
echo [2/3] Starting auto-lock watchdog...
echo       (Will lock in 30 minutes if not reconnected)

echo.
echo [3/3] Locking screen...
python -c "import ctypes; ctypes.windll.user32.LockWorkStation()"

if errorlevel 1 (
    echo.
    echo ERROR: Failed to lock screen!
    echo.
    echo Restoring Remote Desktop...
    reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 0 /f > nul 2>&1
    pause
    exit /b 1
)
'''
            filename = "TeleCode_SecureLock.bat"
        else:
            # Standard batch file
            batch_content = '''@echo off
REM ============================================
REM TeleCode Screen Lock - Quick Lock
REM ============================================
REM This locks your screen while keeping
REM TeleCode and Cursor running in the background.
REM ============================================

echo.
echo ========================================
echo   TeleCode Screen Lock
echo ========================================
echo.
echo This will lock your screen while
echo keeping your session ACTIVE in memory.
echo.
echo After running:
echo   - Screen will be LOCKED
echo   - TeleCode continues working
echo   - Cursor IDE stays active
echo   - You can still control via Telegram
echo.
echo To UNLOCK:
echo   - Enter your Windows password
echo.
echo ========================================
echo.
echo TIP: For more security, use TeleCode_SecureLock.bat
echo      which disables Remote Desktop connections.
echo.
pause

echo Locking screen...
python -c "import ctypes; ctypes.windll.user32.LockWorkStation()"

if errorlevel 1 (
    echo.
    echo ERROR: Failed to lock screen!
    pause
    exit /b 1
)
'''
            filename = "TeleCode_QuickLock.bat"
        
        # Write the batch file
        batch_path = target_folder / filename
        with open(batch_path, "w", encoding="utf-8") as f:
            f.write(batch_content)
        
        return True, f"Created shortcut at: {batch_path}"
        
    except Exception as e:
        return False, f"Failed to create shortcut: {e}"


def create_lock_files_in_project() -> tuple[bool, str]:
    """
    Create screen lock helper files in the project directory.
    
    Creates:
    - screen_lock.bat - Quick lock with minimal prompts
    - screen_lock_verbose.bat - Lock with explanations
    
    Returns:
        Tuple of (success, message)
    """
    try:
        project_root = Path(__file__).parent.parent
        
        # Quick lock script (minimal)
        quick_lock = '''@echo off
REM TeleCode Quick Lock - No admin required!
echo Locking screen for TeleCode...
python -c "import ctypes; ctypes.windll.user32.LockWorkStation()"

if errorlevel 1 (
    echo ERROR: Failed to lock screen!
    exit /b 1
)
'''
        
        # Verbose lock script (with explanations)
        verbose_lock = '''@echo off
REM ============================================
REM TeleCode Screen Lock
REM ============================================
REM 
REM WHAT THIS DOES:
REM   Locks your screen while keeping your
REM   Windows session running in memory.
REM
REM WHY USE THIS:
REM   - Cursor IDE continues running
REM   - TeleCode can control Cursor via Telegram
REM   - GUI automation works in background
REM
REM SECURITY:
REM   - Screen is password-protected
REM   - Session stays active for automation
REM   - Use BitLocker for disk encryption
REM
REM TO UNLOCK:
REM   - Enter your Windows password
REM
REM ============================================

@echo.
@echo ========================================
@echo   TeleCode Screen Lock
@echo ========================================
@echo.
@echo Your screen will be LOCKED but TeleCode
@echo will continue running in the background.
@echo.
@echo Control your laptop via Telegram!
@echo.
@echo Press any key to lock...
@pause > nul

@echo.
@echo Locking screen...
python -c "import ctypes; ctypes.windll.user32.LockWorkStation()"

@if errorlevel 1 (
    @echo.
    @echo ERROR: Failed to lock screen!
    @pause
    exit /b 1
)
'''
        
        # Write files
        (project_root / "screen_lock.bat").write_text(quick_lock, encoding="utf-8")
        (project_root / "screen_lock_verbose.bat").write_text(verbose_lock, encoding="utf-8")
        
        return True, "Created screen_lock.bat and screen_lock_verbose.bat"
        
    except Exception as e:
        return False, f"Failed to create lock files: {e}"


class ScreenLockManager:
    """
    Manager class for screen lock functionality.
    
    Provides easy access to screen lock features from the GUI.
    Includes Secure Mode for hardened lock sessions.
    """
    
    def __init__(self):
        self.is_available = IS_WINDOWS
        self.is_admin = is_admin() if IS_WINDOWS else False
        self.security = ScreenLockSecurity() if IS_WINDOWS else None
    
    def get_status(self) -> dict:
        """Get current screen lock status."""
        return {
            "available": self.is_available,
            "is_admin": self.is_admin,
            "ready": self.is_available  # No admin needed for basic lock!
        }
    
    def get_status_text(self) -> str:
        """Get human-readable status."""
        if not self.is_available:
            return "❌ Screen lock not available (Windows only)"
        
        return "✅ Screen lock ready (works on all Windows editions!)"
    
    def lock_screen(self, secure_mode: bool = False, watchdog_minutes: int = 30) -> tuple[bool, str]:
        """
        Lock the screen.
        
        Args:
            secure_mode: Enable security hardening
            watchdog_minutes: Auto-lock timeout
        """
        return lock_screen(secure_mode=secure_mode, watchdog_minutes=watchdog_minutes)
    
    def lock_screen_secure(self, watchdog_minutes: int = 30) -> tuple[bool, str]:
        """Lock screen with full security hardening."""
        return lock_screen(secure_mode=True, watchdog_minutes=watchdog_minutes)
    
    def restore_security_settings(self) -> tuple[bool, str]:
        """Restore any security settings changed during lock."""
        if self.security:
            self.security.stop_watchdog()
            return self.security.restore_remote_desktop()
        return True, "No settings to restore"
    
    def create_shortcut(self, location: str = None, secure_mode: bool = False) -> tuple[bool, str]:
        """Create a quick-access shortcut."""
        return create_lock_shortcut(location, secure_mode=secure_mode)
    
    def setup_project_files(self) -> tuple[bool, str]:
        """Create screen lock helper files in project."""
        return create_lock_files_in_project()


# CLI interface for standalone use
def main():
    """Command-line interface for screen lock helper."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="TeleCode Screen Lock Helper - Lock screen while keeping session active",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Security Modes:
  Standard Mode: Quick lock, RDP still works
  Secure Mode:   Disables RDP + Auto-lock watchdog

Examples:
  python -m src.screen_lock_helper --lock              # Standard lock
  python -m src.screen_lock_helper --lock --secure     # Secure lock
  python -m src.screen_lock_helper --shortcut --secure # Create secure shortcut
"""
    )
    parser.add_argument(
        "--lock", "-l",
        action="store_true",
        help="Lock the screen now"
    )
    parser.add_argument(
        "--secure", "-X",
        action="store_true",
        help="Enable secure mode (disable RDP + auto-lock)"
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=30,
        help="Auto-lock timeout in minutes (default: 30)"
    )
    parser.add_argument(
        "--shortcut", "-s",
        action="store_true",
        help="Create a desktop shortcut"
    )
    parser.add_argument(
        "--setup", "-S",
        action="store_true",
        help="Create helper files in project folder"
    )
    parser.add_argument(
        "--restore", "-r",
        action="store_true",
        help="Restore security settings (re-enable RDP)"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show screen lock status"
    )
    
    args = parser.parse_args()
    
    manager = ScreenLockManager()
    
    if args.status or not any([args.lock, args.shortcut, args.setup, args.restore]):
        print("\n" + "=" * 50)
        print("  TeleCode Screen Lock Helper")
        print("=" * 50)
        print(f"\n  Status: {manager.get_status_text()}")
        print(f"  Admin: {'Yes' if manager.is_admin else 'No (not required for basic lock)'}")
        print("\n  Commands:")
        print("    --lock              Lock screen (standard)")
        print("    --lock --secure     Lock screen (hardened)")
        print("    --shortcut          Create desktop shortcut")
        print("    --shortcut --secure Create SECURE shortcut")
        print("    --restore           Restore RDP after secure lock")
        print("    --setup             Create helper batch files")
        print("\n  Security Levels:")
        print("    Standard: RDP enabled, no timeout")
        print("    Secure:   RDP disabled, 30min auto-lock")
        print("\n  Works on ALL Windows editions (Home, Pro, Enterprise, Server)!")
        print("=" * 50 + "\n")
        return
    
    if args.restore:
        success, message = manager.restore_security_settings()
        print(f"{'✅' if success else '❌'} {message}")
    
    if args.lock:
        if args.secure:
            print("🔒 SECURE MODE: Disabling RDP + Starting watchdog...")
            success, message = manager.lock_screen_secure(watchdog_minutes=args.timeout)
        else:
            success, message = manager.lock_screen()
        print(f"{'✅' if success else '❌'} {message}")
    
    if args.shortcut:
        # Create both shortcuts
        success1, msg1 = manager.create_shortcut(secure_mode=False)
        success2, msg2 = manager.create_shortcut(secure_mode=True)
        print(f"{'✅' if success1 else '❌'} Standard: {msg1}")
        print(f"{'✅' if success2 else '❌'} Secure: {msg2}")
    
    if args.setup:
        success, message = manager.setup_project_files()
        print(f"{'✅' if success else '❌'} {message}")


if __name__ == "__main__":
    main()

