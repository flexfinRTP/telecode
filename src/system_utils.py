"""
============================================
TeleCode v0.1 - System Utilities Module
============================================
Cross-platform utilities for:
- Screen lock detection
- Sleep prevention ("Insomnia" protocol)
- System information

Works on Windows, macOS, and Linux.
============================================
"""

import os
import sys
import logging
import platform
import ctypes
from threading import Thread, Event
from typing import Optional

logger = logging.getLogger("telecode.system")

# Platform detection
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"


class ScreenLockDetector:
    """
    Detect if the screen is locked.
    
    Note: On Windows, this uses User32 API.
    On macOS, this uses Quartz.
    On Linux, this is more complex (depends on DE).
    """
    
    @staticmethod
    def is_locked() -> bool:
        """
        Check if the screen is currently locked.
        
        Returns:
            True if screen is locked, False otherwise.
            Returns False if detection fails (assume unlocked).
        """
        try:
            if IS_WINDOWS:
                return ScreenLockDetector._is_locked_windows()
            elif IS_MACOS:
                return ScreenLockDetector._is_locked_macos()
            elif IS_LINUX:
                return ScreenLockDetector._is_locked_linux()
            else:
                logger.warning(f"Unknown platform: {platform.system()}")
                return False
        except Exception as e:
            logger.error(f"Failed to detect screen lock: {e}")
            return False
    
    @staticmethod
    def _is_locked_windows() -> bool:
        """Windows lock detection using User32 API."""
        try:
            user32 = ctypes.windll.user32
            # Check if workstation is locked
            # This is an approximation - checks for foreground window
            hwnd = user32.GetForegroundWindow()
            if hwnd == 0:
                return True
            
            # Alternative: Check for lock screen
            # OpenInputDesktop returns None if locked
            try:
                desktop = user32.OpenInputDesktop(0, False, 0x0100)
                if desktop:
                    user32.CloseDesktop(desktop)
                    return False
                return True
            except:
                return False
                
        except Exception as e:
            logger.error(f"Windows lock detection failed: {e}")
            return False
    
    @staticmethod
    def _is_locked_macos() -> bool:
        """macOS lock detection using Quartz."""
        try:
            # Try using Quartz
            from Quartz import CGSessionCopyCurrentDictionary
            session = CGSessionCopyCurrentDictionary()
            if session:
                locked = session.get("CGSSessionScreenIsLocked", 0)
                return bool(locked)
            return False
        except ImportError:
            logger.warning("Quartz not available on macOS")
            return False
        except Exception as e:
            logger.error(f"macOS lock detection failed: {e}")
            return False
    
    @staticmethod
    def _is_locked_linux() -> bool:
        """
        Linux lock detection (desktop environment dependent).
        
        This is complex because different DEs have different lock mechanisms.
        We check for common patterns.
        """
        try:
            import subprocess
            
            # Try GNOME screensaver
            result = subprocess.run(
                ["gnome-screensaver-command", "-q"],
                capture_output=True,
                text=True
            )
            if "is active" in result.stdout.lower():
                return True
            
            # Try xdg-screensaver
            result = subprocess.run(
                ["xdg-screensaver", "status"],
                capture_output=True,
                text=True
            )
            if "enabled" in result.stdout.lower():
                return True
            
            return False
            
        except FileNotFoundError:
            logger.warning("No screensaver command found on Linux")
            return False
        except Exception as e:
            logger.error(f"Linux lock detection failed: {e}")
            return False


class SleepPreventer:
    """
    The "Insomnia" Protocol - Prevents system from sleeping.
    
    This keeps the system awake while the bot is running,
    ensuring it's always responsive to commands.
    
    IMPORTANT: Use responsibly - this will drain battery on laptops.
    """
    
    def __init__(self):
        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        self._active = False
    
    def start(self) -> bool:
        """
        Start preventing sleep.
        
        Returns:
            True if successfully started, False otherwise.
        """
        if self._active:
            logger.warning("SleepPreventer already active")
            return True
        
        try:
            if IS_WINDOWS:
                return self._start_windows()
            elif IS_MACOS:
                return self._start_macos()
            elif IS_LINUX:
                return self._start_linux()
            else:
                logger.warning(f"Sleep prevention not supported on {platform.system()}")
                return False
        except Exception as e:
            logger.error(f"Failed to start sleep prevention: {e}")
            return False
    
    def stop(self):
        """Stop preventing sleep."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._active = False
        self._clear_sleep_prevention()
        logger.info("Sleep prevention stopped")
    
    def _start_windows(self) -> bool:
        """Windows sleep prevention using SetThreadExecutionState."""
        try:
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ES_DISPLAY_REQUIRED = 0x00000002
            
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            )
            self._active = True
            logger.info("Windows sleep prevention active")
            return True
        except Exception as e:
            logger.error(f"Windows sleep prevention failed: {e}")
            return False
    
    def _start_macos(self) -> bool:
        """macOS sleep prevention using caffeinate."""
        try:
            import subprocess
            
            def run_caffeinate():
                # Run caffeinate until stop event
                self._caffeinate_proc = subprocess.Popen(
                    ["caffeinate", "-dims"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self._stop_event.wait()
                self._caffeinate_proc.terminate()
            
            self._thread = Thread(target=run_caffeinate, daemon=True)
            self._thread.start()
            self._active = True
            logger.info("macOS sleep prevention active (caffeinate)")
            return True
        except Exception as e:
            logger.error(f"macOS sleep prevention failed: {e}")
            return False
    
    def _start_linux(self) -> bool:
        """Linux sleep prevention using systemd-inhibit or xdg-screensaver."""
        try:
            import subprocess
            
            def run_inhibit():
                # Try systemd-inhibit first
                self._inhibit_proc = subprocess.Popen(
                    [
                        "systemd-inhibit",
                        "--what=idle:sleep",
                        "--why=TeleCode Bot Active",
                        "--mode=block",
                        "sleep", "infinity"
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self._stop_event.wait()
                self._inhibit_proc.terminate()
            
            self._thread = Thread(target=run_inhibit, daemon=True)
            self._thread.start()
            self._active = True
            logger.info("Linux sleep prevention active (systemd-inhibit)")
            return True
        except Exception as e:
            logger.error(f"Linux sleep prevention failed: {e}")
            return False
    
    def _clear_sleep_prevention(self):
        """Clear sleep prevention state."""
        if IS_WINDOWS:
            try:
                ES_CONTINUOUS = 0x80000000
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            except:
                pass
        elif IS_MACOS and hasattr(self, '_caffeinate_proc'):
            try:
                self._caffeinate_proc.terminate()
            except:
                pass
        elif IS_LINUX and hasattr(self, '_inhibit_proc'):
            try:
                self._inhibit_proc.terminate()
            except:
                pass


def get_system_info() -> dict:
    """
    Get system information for status display.
    
    Returns:
        Dictionary with system info.
    """
    try:
        import psutil
        
        return {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python_version": sys.version.split()[0],
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent if not IS_WINDOWS else psutil.disk_usage("C:\\").percent,
        }
    except ImportError:
        return {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python_version": sys.version.split()[0],
        }
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        return {"error": str(e)}


def format_system_status() -> str:
    """Format system status for display in Telegram."""
    info = get_system_info()
    
    lines = [
        "🖥️ **System Status**",
        f"  Platform: {info.get('platform', 'Unknown')}",
        f"  Python: {info.get('python_version', 'Unknown')}",
    ]
    
    if "cpu_percent" in info:
        lines.append(f"  CPU: {info['cpu_percent']:.1f}%")
    if "memory_percent" in info:
        lines.append(f"  Memory: {info['memory_percent']:.1f}%")
    if "disk_percent" in info:
        lines.append(f"  Disk: {info['disk_percent']:.1f}%")
    
    lock_status = "🔒 Locked" if ScreenLockDetector.is_locked() else "🔓 Unlocked"
    lines.append(f"  Screen: {lock_status}")
    
    return "\n".join(lines)

