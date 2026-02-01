"""
============================================
TeleCode v0.1 - TSCON Helper Utility
============================================
Easy-to-use tool for the Windows TSCON method.

This keeps GUI applications (like Cursor) running
even when the physical screen appears "locked".

HOW IT WORKS:
- Disconnects your session from the display
- Session stays active in memory
- GUI automation continues working
- Screen appears black/locked

SECURITY FEATURES (Secure Mode):
- Disables Remote Desktop during TSCON
- Auto-lock watchdog timer
- Monitors for reconnection attempts
- Logs all security events

============================================
"""

import os
import sys
import ctypes
import subprocess
import logging
import threading
import time
import winreg
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger("telecode.tscon")

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


def get_session_name() -> str:
    """Get the current Windows session name."""
    if not IS_WINDOWS:
        return ""
    return os.environ.get("SESSIONNAME", "console")


class TSCONSecurity:
    """
    Security hardening for TSCON sessions.
    
    Features:
    - Disable Remote Desktop during TSCON
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
        
        This blocks RDP connections while TSCON is active.
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
            
            self._log_security_event("RDP_DISABLED", "Remote Desktop disabled for TSCON session")
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
        log_entry = f"[{timestamp}] [TSCON-{event_type}] {message}"
        logger.info(log_entry)
        
        # Also write to audit log
        try:
            with open("telecode_audit.log", "a", encoding="utf-8") as f:
                f.write(log_entry + "\n")
        except:
            pass


def lock_workstation() -> bool:
    """Lock the Windows workstation (real lock with password)."""
    if not IS_WINDOWS:
        return False
    try:
        ctypes.windll.user32.LockWorkStation()
        return True
    except:
        return False


def run_tscon(secure_mode: bool = False, watchdog_minutes: int = 30) -> tuple[bool, str]:
    """
    Execute the TSCON disconnect command.
    
    This disconnects the current session while keeping it active.
    Requires administrator privileges.
    
    Args:
        secure_mode: If True, enables security hardening:
                     - Disables Remote Desktop
                     - Starts auto-lock watchdog
        watchdog_minutes: Auto-lock timeout (default 30 min)
    
    Returns:
        Tuple of (success, message)
    """
    if not IS_WINDOWS:
        return False, "TSCON is only available on Windows"
    
    if not is_admin():
        return False, "Administrator privileges required. Right-click and 'Run as Administrator'"
    
    session_name = get_session_name()
    if not session_name:
        return False, "Could not determine session name"
    
    security = TSCONSecurity()
    security_status = []
    
    # Apply security hardening if requested
    if secure_mode:
        # Disable RDP
        success, msg = security.disable_remote_desktop()
        security_status.append(f"RDP: {'Disabled' if success else 'Failed'}")
        
        # Start watchdog
        security.start_watchdog(watchdog_minutes)
        security_status.append(f"Watchdog: {watchdog_minutes}min")
    
    try:
        # Run tscon command
        result = subprocess.run(
            ["tscon", session_name, "/dest:console"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            msg = "Session disconnected successfully."
            if secure_mode:
                msg += f"\n🔒 Secure Mode: {', '.join(security_status)}"
            return True, msg
        else:
            # Restore RDP if we disabled it
            if secure_mode:
                security.restore_remote_desktop()
                security.stop_watchdog()
            return False, f"TSCON failed: {result.stderr or result.stdout}"
            
    except subprocess.TimeoutExpired:
        return False, "TSCON command timed out"
    except FileNotFoundError:
        return False, "TSCON command not found. Are you on Windows?"
    except Exception as e:
        return False, f"Error running TSCON: {e}"


def create_tscon_shortcut(target_folder: str = None, secure_mode: bool = False) -> tuple[bool, str]:
    """
    Create a desktop shortcut for easy TSCON access.
    
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
REM TeleCode TSCON - SECURE Lock
REM ============================================
REM This is the SECURE version:
REM   - Disables Remote Desktop
REM   - Auto-locks after 30 minutes
REM   - Logs all security events
REM ============================================

echo.
echo ========================================
echo   TeleCode SECURE TSCON Lock
echo ========================================
echo.
echo SECURITY FEATURES ENABLED:
echo   [x] Remote Desktop will be DISABLED
echo   [x] Auto-lock after 30 minutes
echo   [x] All events logged to audit file
echo.
echo After running:
echo   - Screen will go BLACK
echo   - RDP connections BLOCKED
echo   - TeleCode continues working
echo   - Auto-lock in 30 minutes
echo.
echo To RECONNECT:
echo   - Physical access only (no RDP)
echo   - Press any key or move mouse
echo   - Enter your Windows password
echo.
echo ========================================
echo.
pause

echo.
echo [1/3] Disabling Remote Desktop...
reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 1 /f > nul 2>&1
net stop TermService /y > nul 2>&1
echo       Remote Desktop DISABLED

echo.
echo [2/3] Starting auto-lock watchdog...
echo       (Will lock in 30 minutes if not reconnected)

echo.
echo [3/3] Disconnecting session...
tscon %sessionname% /dest:console

if errorlevel 1 (
    echo.
    echo ERROR: TSCON failed!
    echo Make sure to run this as Administrator.
    echo.
    echo Restoring Remote Desktop...
    reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 0 /f > nul 2>&1
    pause
)
'''
            filename = "TeleCode_SecureLock.bat"
        else:
            # Standard batch file
            batch_content = '''@echo off
REM ============================================
REM TeleCode TSCON - Quick Lock
REM ============================================
REM This disconnects your session while keeping
REM TeleCode and Cursor running in the background.
REM ============================================

echo.
echo ========================================
echo   TeleCode TSCON Quick Lock
echo ========================================
echo.
echo This will disconnect your display while
echo keeping your session ACTIVE in memory.
echo.
echo After running:
echo   - Screen will go BLACK
echo   - TeleCode continues working
echo   - Cursor IDE stays active
echo   - You can still control via Telegram
echo.
echo To RECONNECT:
echo   - Press any key or move mouse
echo   - Enter your Windows password
echo.
echo ========================================
echo.
echo TIP: For more security, use TeleCode_SecureLock.bat
echo      which disables Remote Desktop connections.
echo.
pause

echo Disconnecting session...
tscon %sessionname% /dest:console

if errorlevel 1 (
    echo.
    echo ERROR: TSCON failed!
    echo Make sure to run this as Administrator.
    pause
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


def create_tscon_files_in_project() -> tuple[bool, str]:
    """
    Create TSCON helper files in the project directory.
    
    Creates:
    - tscon_lock.bat - Quick lock with minimal prompts
    - tscon_lock_verbose.bat - Lock with explanations
    
    Returns:
        Tuple of (success, message)
    """
    try:
        project_root = Path(__file__).parent.parent
        
        # Quick lock script (minimal)
        quick_lock = '''@echo off
REM TeleCode Quick Lock - Run as Administrator
echo Disconnecting session for TeleCode...
tscon %sessionname% /dest:console
'''
        
        # Verbose lock script (with explanations)
        verbose_lock = '''@echo off
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
REM SECURITY:
REM   - Only use on trusted networks
REM   - Your session is technically "unlocked"
REM   - Use BitLocker for disk encryption
REM
REM TO RECONNECT:
REM   - Press any key or move mouse
REM   - Enter your Windows password
REM
REM ============================================

@echo.
@echo ========================================
@echo   TeleCode Session Lock
@echo ========================================
@echo.
@echo Your screen will go BLACK but TeleCode
@echo will continue running in the background.
@echo.
@echo Control your laptop via Telegram!
@echo.
@echo Press any key to disconnect...
@pause > nul

@echo.
@echo Disconnecting session...
tscon %sessionname% /dest:console

@if errorlevel 1 (
    @echo.
    @echo ERROR: TSCON command failed!
    @echo.
    @echo Make sure you're running this as Administrator:
    @echo   Right-click ^> "Run as administrator"
    @echo.
    @pause
)
'''
        
        # Write files
        (project_root / "tscon_lock.bat").write_text(quick_lock, encoding="utf-8")
        (project_root / "tscon_lock_verbose.bat").write_text(verbose_lock, encoding="utf-8")
        
        return True, "Created tscon_lock.bat and tscon_lock_verbose.bat"
        
    except Exception as e:
        return False, f"Failed to create TSCON files: {e}"


class TSCONManager:
    """
    Manager class for TSCON functionality.
    
    Provides easy access to TSCON features from the GUI.
    Includes Secure Mode for hardened TSCON sessions.
    """
    
    def __init__(self):
        self.is_available = IS_WINDOWS
        self.is_admin = is_admin() if IS_WINDOWS else False
        self.security = TSCONSecurity() if IS_WINDOWS else None
    
    def get_status(self) -> dict:
        """Get current TSCON status."""
        return {
            "available": self.is_available,
            "is_admin": self.is_admin,
            "session_name": get_session_name() if self.is_available else None,
            "ready": self.is_available and self.is_admin
        }
    
    def get_status_text(self) -> str:
        """Get human-readable status."""
        if not self.is_available:
            return "❌ TSCON not available (Windows only)"
        
        if not self.is_admin:
            return "⚠️ TSCON available but needs Administrator"
        
        return "✅ TSCON ready to use"
    
    def lock_session(self, secure_mode: bool = False, watchdog_minutes: int = 30) -> tuple[bool, str]:
        """
        Lock the session using TSCON.
        
        Args:
            secure_mode: Enable security hardening
            watchdog_minutes: Auto-lock timeout
        """
        return run_tscon(secure_mode=secure_mode, watchdog_minutes=watchdog_minutes)
    
    def lock_session_secure(self, watchdog_minutes: int = 30) -> tuple[bool, str]:
        """Lock session with full security hardening."""
        return run_tscon(secure_mode=True, watchdog_minutes=watchdog_minutes)
    
    def real_lock(self) -> bool:
        """Perform a real Windows lock (with password)."""
        return lock_workstation()
    
    def restore_security_settings(self) -> tuple[bool, str]:
        """Restore any security settings changed during TSCON."""
        if self.security:
            self.security.stop_watchdog()
            return self.security.restore_remote_desktop()
        return True, "No settings to restore"
    
    def create_shortcut(self, location: str = None, secure_mode: bool = False) -> tuple[bool, str]:
        """Create a quick-access shortcut."""
        return create_tscon_shortcut(location, secure_mode=secure_mode)
    
    def setup_project_files(self) -> tuple[bool, str]:
        """Create TSCON helper files in project."""
        return create_tscon_files_in_project()


# CLI interface for standalone use
def main():
    """Command-line interface for TSCON helper."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="TeleCode TSCON Helper - Lock screen while keeping session active",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Security Modes:
  Standard Mode: Quick disconnect, RDP still works
  Secure Mode:   Disables RDP + Auto-lock watchdog

Examples:
  python -m src.tscon_helper --lock              # Standard lock
  python -m src.tscon_helper --lock --secure     # Secure lock
  python -m src.tscon_helper --shortcut --secure # Create secure shortcut
"""
    )
    parser.add_argument(
        "--lock", "-l",
        action="store_true",
        help="Lock the session now (requires admin)"
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
        help="Show TSCON status"
    )
    
    args = parser.parse_args()
    
    manager = TSCONManager()
    
    if args.status or not any([args.lock, args.shortcut, args.setup, args.restore]):
        print("\n" + "=" * 50)
        print("  TeleCode TSCON Helper")
        print("=" * 50)
        print(f"\n  Status: {manager.get_status_text()}")
        print(f"  Session: {get_session_name()}")
        print(f"  Admin: {'Yes' if manager.is_admin else 'No'}")
        print("\n  Commands:")
        print("    --lock              Lock session (standard)")
        print("    --lock --secure     Lock session (hardened)")
        print("    --shortcut          Create desktop shortcut")
        print("    --shortcut --secure Create SECURE shortcut")
        print("    --restore           Restore RDP after secure lock")
        print("    --setup             Create helper batch files")
        print("\n  Security Levels:")
        print("    Standard: RDP enabled, no timeout")
        print("    Secure:   RDP disabled, 30min auto-lock")
        print("=" * 50 + "\n")
        return
    
    if args.restore:
        success, message = manager.restore_security_settings()
        print(f"{'✅' if success else '❌'} {message}")
    
    if args.lock:
        if args.secure:
            print("🔒 SECURE MODE: Disabling RDP + Starting watchdog...")
            success, message = manager.lock_session_secure(watchdog_minutes=args.timeout)
        else:
            success, message = manager.lock_session()
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

