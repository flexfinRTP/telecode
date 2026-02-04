"""
============================================
TeleCode v0.1 - Virtual Display Helper
============================================
Turns off monitor while keeping session active for GUI automation.

This allows pyautogui to work even when the screen appears "off".
Perfect for headless GUI automation on Windows.

HOW IT WORKS:
- Turns off physical monitor (screen goes black)
- Session stays ACTIVE (not locked)
- GUI automation (pyautogui) works perfectly
- TeleCode and Cursor continue running
- Works on ALL Windows editions!

WHY NOT LockWorkStation?
- LockWorkStation() locks the screen (password required)
- Locked screens block ALL input including pyautogui
- This solution turns off monitor WITHOUT locking
- Session stays active, pyautogui works!

VIRTUAL DISPLAY OPTION:
- If Indigo Virtual Display is installed, can switch to virtual display
- Virtual display allows pyautogui even when physical monitor is off
- Optional: Install via TeleCode installer (one-time, admin approval)

============================================
"""

import os
import sys
import ctypes
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple, Callable

logger = logging.getLogger("telecode.virtual_display")

# Check if we're on Windows
IS_WINDOWS = sys.platform == "win32"

# Windows constants
WM_SYSCOMMAND = 0x0112
SC_MONITORPOWER = 0xF170
MONITOR_OFF = 2
MONITOR_ON = -1
MONITOR_STANDBY = 1


def is_admin() -> bool:
    """Check if running with administrator privileges."""
    if not IS_WINDOWS:
        return False
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False


def turn_off_display() -> bool:
    """
    Turn off the physical monitor while keeping session active.
    
    This is different from LockWorkStation():
    - LockWorkStation() LOCKS the screen (blocks pyautogui)
    - This turns OFF the monitor (pyautogui still works!)
    
    Works on ALL Windows editions (Home, Pro, Enterprise, Server).
    No administrator privileges required!
    
    Returns:
        True if monitor turned off successfully, False otherwise
    """
    if not IS_WINDOWS:
        logger.warning("Display control is only available on Windows")
        return False
    
    try:
        # Get desktop window handle
        desktop_hwnd = ctypes.windll.user32.GetDesktopWindow()
        
        # Send message to turn off monitor
        result = ctypes.windll.user32.SendMessageW(
            desktop_hwnd,
            WM_SYSCOMMAND,
            SC_MONITORPOWER,
            MONITOR_OFF
        )
        
        if result == 0:
            logger.info("Monitor turned off successfully")
            return True
        else:
            logger.warning(f"SendMessage returned {result}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to turn off monitor: {e}")
        return False


def turn_on_display() -> bool:
    """
    Turn on the physical monitor.
    
    Returns:
        True if monitor turned on successfully, False otherwise
    """
    if not IS_WINDOWS:
        return False
    
    try:
        # Get desktop window handle
        desktop_hwnd = ctypes.windll.user32.GetDesktopWindow()
        
        # Send message to turn on monitor
        result = ctypes.windll.user32.SendMessageW(
            desktop_hwnd,
            WM_SYSCOMMAND,
            SC_MONITORPOWER,
            MONITOR_ON
        )
        
        if result == 0:
            logger.info("Monitor turned on successfully")
            return True
        else:
            # Alternative: Simulate mouse movement to wake monitor
            ctypes.windll.user32.mouse_event(0x0001, 0, 0, 0, 0)
            return True
            
    except Exception as e:
        logger.error(f"Failed to turn on monitor: {e}")
        return False


def is_virtual_display_available() -> bool:
    """
    Check if Indigo Virtual Display (or similar) is installed.
    
    Returns:
        True if virtual display driver is available, False otherwise
    """
    if not IS_WINDOWS:
        return False
    
    try:
        # Check for virtual display in device manager
        # Look for common virtual display driver names
        result = subprocess.run(
            ['powershell', '-Command', 
             'Get-PnpDevice | Where-Object {$_.FriendlyName -like "*Virtual*Display*" -or $_.FriendlyName -like "*Indigo*"}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and result.stdout:
            logger.info("Virtual display detected")
            return True
        
        return False
        
    except Exception as e:
        logger.debug(f"Could not check for virtual display: {e}")
        return False


def get_display_count() -> int:
    """
    Get the number of displays connected.
    
    Returns:
        Number of displays (including virtual displays)
    """
    if not IS_WINDOWS:
        return 0
    
    try:
        # Use Windows API to count displays
        def enum_callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            if dwData:
                dwData[0] += 1
            return True
        
        MonitorEnumProc = ctypes.WINFUNCTYPE(
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.wintypes.RECT),
            ctypes.POINTER(ctypes.c_int)
        )
        
        count = [0]
        ctypes.windll.user32.EnumDisplayMonitors(
            None,
            None,
            MonitorEnumProc(enum_callback),
            ctypes.byref(ctypes.c_int(count[0]))
        )
        
        return count[0] if count else 1
        
    except Exception as e:
        logger.debug(f"Could not count displays: {e}")
        return 1  # Assume at least one display


def turn_off_display_safe(secure: bool = True, password: Optional[str] = None, pin: Optional[str] = None, on_unlock: Optional[Callable] = None) -> Tuple[bool, str]:
    """
    Turn off display with safety checks and status message.
    
    Args:
        secure: If True, activate custom lock (password required on wake)
        password: Windows password or custom password for lock
        pin: Custom PIN for lock (alternative to password)
    
    Returns:
        Tuple of (success, message)
    """
    if not IS_WINDOWS:
        return False, "Display control is only available on Windows"
    
    # Check if virtual display is available (optional)
    has_virtual = is_virtual_display_available()
    display_count = get_display_count()
    
    # Turn off monitor
    if turn_off_display():
        # IMPORTANT: Keep computer awake - prevent sleep/lock
        # This ensures pyautogui continues working
        # Note: SleepPreventer is typically already started by bot.py
        # This is just a safety check - if not active, try to start it
        try:
            from .system_utils import SleepPreventer
            # Create instance and start (start() handles already-active case)
            sleep_preventer = SleepPreventer()
            if sleep_preventer.start():
                logger.info("Sleep prevention activated to keep computer awake")
        except Exception as e:
            logger.warning(f"Failed to activate sleep prevention: {e}")
        
        # Activate custom lock if secure mode
        if secure:
            try:
                from .custom_lock import activate_lock
                
                # NEVER use Windows LockWorkStation - it blocks pyautogui!
                # Only use our custom lock overlay
                # Note: activate_lock() will automatically load PIN/password from storage if not provided
                activate_lock(password=password, pin=pin, on_unlock=on_unlock)
                msg = "✅ Monitor turned off + SECURE LOCK activated!"
                if pin:
                    msg += f"\n🔒 PIN required when monitor wakes"
                elif password:
                    msg += f"\n🔒 Password required when monitor wakes"
                else:
                    msg += "\n⚠️ No PIN/password set - set one with /pin set"
            except Exception as e:
                logger.warning(f"Failed to activate custom lock: {e}")
                msg = "Monitor turned off (lock activation failed)"
        else:
            msg = "Monitor turned off. TeleCode continues working!"
        
        if has_virtual:
            msg += "\n💡 Virtual display detected - pyautogui works perfectly!"
        elif display_count > 1:
            msg += f"\n💡 {display_count} displays - pyautogui works on other displays"
        else:
            msg += "\n💡 pyautogui works - session is active"
        
        return True, msg
    else:
        return False, "Failed to turn off monitor. Try moving mouse to wake it first."


# Backward compatibility - keep old function name
def lock_workstation() -> bool:
    """
    DEPRECATED: Use turn_off_display() instead.
    
    This function name is kept for backward compatibility.
    It now turns off the monitor instead of locking.
    """
    logger.warning("lock_workstation() is deprecated. Use turn_off_display() instead.")
    return turn_off_display()


class VirtualDisplayManager:
    """
    Manager for virtual display operations.
    
    Provides high-level interface for display control.
    """
    
    def __init__(self):
        self._display_off = False
        self._virtual_display_available = is_virtual_display_available()
    
    @property
    def is_admin(self) -> bool:
        """Check if running with admin privileges."""
        return is_admin()
    
    @property
    def virtual_display_available(self) -> bool:
        """Check if virtual display is available."""
        return self._virtual_display_available
    
    def turn_off_display(self, secure: bool = True, password: Optional[str] = None, pin: Optional[str] = None) -> Tuple[bool, str]:
        """
        Turn off physical monitor with optional secure lock.
        
        Args:
            secure: If True, activate custom lock (password required on wake)
            password: Windows password or custom password for lock
            pin: Custom PIN for lock (alternative to password)
        
        Returns:
            Tuple of (success, message)
        """
        success, message = turn_off_display_safe(secure=secure, password=password, pin=pin)
        if success:
            self._display_off = True
        return success, message
    
    def turn_on_display(self) -> Tuple[bool, str]:
        """
        Turn on physical monitor and deactivate lock.
        
        Returns:
            Tuple of (success, message)
        """
        # Deactivate custom lock if active
        try:
            from .custom_lock import deactivate_lock, is_locked
            if is_locked():
                deactivate_lock()
        except Exception as e:
            logger.debug(f"Could not deactivate lock: {e}")
        
        if turn_on_display():
            self._display_off = False
            return True, "Monitor turned on"
        else:
            return False, "Failed to turn on monitor"
    
    def is_display_off(self) -> bool:
        """Check if display is currently off."""
        return self._display_off
    
    def get_status(self) -> dict:
        """
        Get current virtual display status.
        
        Returns:
            Dictionary with status information
        """
        return {
            "display_off": self._display_off,
            "virtual_display_available": self._virtual_display_available,
            "display_count": get_display_count(),
            "platform": "Windows" if IS_WINDOWS else "Other",
            "admin": self.is_admin
        }


# CLI interface for batch files
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="TeleCode Virtual Display Helper")
    parser.add_argument("--off", action="store_true", help="Turn off monitor")
    parser.add_argument("--secure", action="store_true", help="Activate secure lock (password required on wake)")
    parser.add_argument("--password", type=str, help="Set lock password")
    parser.add_argument("--pin", type=str, help="Set lock PIN")
    parser.add_argument("--on", action="store_true", help="Turn on monitor")
    parser.add_argument("--status", action="store_true", help="Show status")
    
    args = parser.parse_args()
    
    if args.off:
        success, msg = turn_off_display_safe(
            secure=args.secure,
            password=args.password,
            pin=args.pin
        )
        if success:
            print(f"✅ {msg}")
            sys.exit(0)
        else:
            print(f"❌ {msg}")
            sys.exit(1)
    elif args.on:
        if turn_on_display():
            print("✅ Monitor turned on")
            sys.exit(0)
        else:
            print("❌ Failed to turn on monitor")
            sys.exit(1)
    elif args.status:
        manager = VirtualDisplayManager()
        status = manager.get_status()
        print(f"Display Status:")
        print(f"  Off: {status['display_off']}")
        print(f"  Virtual Display Available: {status['virtual_display_available']}")
        print(f"  Display Count: {status['display_count']}")
        print(f"  Platform: {status['platform']}")
        print(f"  Admin: {status['admin']}")
    else:
        parser.print_help()

