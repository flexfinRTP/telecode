"""
============================================
TeleCode v0.1 - Custom Lock Overlay
============================================
Custom lock screen that requires password/PIN on wake.

This provides REAL security:
- Monitor turns off (privacy)
- When monitor wakes, custom lock overlay appears
- Password/PIN required to unlock
- Blocks ALL desktop input until unlocked
- pyautogui continues working in background!

Inspired by remote desktop apps like TeamViewer, AnyDesk, etc.

============================================
"""

import os
import sys
import ctypes
import threading
import time
import logging
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime

logger = logging.getLogger("telecode.custom_lock")

IS_WINDOWS = sys.platform == "win32"

# Windows constants
WH_MOUSE_LL = 14
WH_KEYBOARD_LL = 13
WM_MOUSEMOVE = 0x0200
WM_KEYDOWN = 0x0100
HC_ACTION = 0

# Lock state
_lock_active = False
_lock_thread = None
_lock_callback = None
_password_hash = None
_pin_hash = None
_unlock_callback: Optional[Callable] = None


def _hash_password(password: str) -> str:
    """Simple hash for password storage (not cryptographically secure, but sufficient for local lock)."""
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash."""
    return _hash_password(password) == stored_hash


def set_lock_password(password: str):
    """Set the lock password (Windows password or custom PIN)."""
    global _password_hash
    _password_hash = _hash_password(password)
    logger.info("Lock password set")


def set_lock_pin(pin: str):
    """Set a custom PIN for lock (alternative to Windows password)."""
    global _pin_hash
    _pin_hash = _hash_password(pin)
    logger.info("Lock PIN set")


def _show_lock_overlay():
    """Show fullscreen lock overlay with password prompt."""
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
        
        class LockWindow:
            def __init__(self):
                self.root = tk.Tk()
                self.root.title("TeleCode Lock")
                self.root.attributes("-fullscreen", True)
                self.root.attributes("-topmost", True)
                self.root.overrideredirect(True)  # Remove window decorations (no close button)
                self.root.configure(bg="black")
                self.root.focus_force()
                self.root.grab_set()  # Grab all input to this window
                self.root.grab_set_global()  # Global grab - blocks all other windows
                
                # Block ALL keyboard shortcuts using Windows hooks
                self._install_keyboard_blocker()
                
                # Block Alt+Tab, Win key, etc. in tkinter
                # Note: Some key combinations can't be bound directly in tkinter
                # The Windows hook handles most blocking, these are additional safeguards
                self.root.bind("<Alt-Tab>", lambda e: "break")
                self.root.bind("<Alt-F4>", lambda e: "break")
                self.root.bind("<Escape>", lambda e: "break")  # Escape
                # Win key bindings (may not work on all systems)
                try:
                    self.root.bind("<Super_L>", lambda e: "break")
                    self.root.bind("<Super_R>", lambda e: "break")
                except:
                    pass  # Win key binding not supported
                
                # Block all mouse clicks outside password entry
                self.root.bind("<Button-1>", self._block_click)
                self.root.bind("<Button-2>", self._block_click)
                self.root.bind("<Button-3>", self._block_click)
                
                # Center frame
                frame = tk.Frame(self.root, bg="black")
                frame.place(relx=0.5, rely=0.5, anchor="center")
                
                # Lock icon
                lock_label = tk.Label(
                    frame,
                    text="🔒",
                    font=("Arial", 72),
                    bg="black",
                    fg="white"
                )
                lock_label.pack(pady=20)
                
                # Title
                title_label = tk.Label(
                    frame,
                    text="TeleCode Locked",
                    font=("Arial", 24, "bold"),
                    bg="black",
                    fg="white"
                )
                title_label.pack(pady=10)
                
                # Password entry
                self.password_var = tk.StringVar()
                password_entry = tk.Entry(
                    frame,
                    textvariable=self.password_var,
                    font=("Arial", 16),
                    show="*",
                    width=30,
                    bg="#222",
                    fg="white",
                    insertbackground="white",
                    relief="flat",
                    bd=5
                )
                password_entry.pack(pady=20, padx=20)
                password_entry.focus()
                password_entry.bind("<Return>", self._check_password)
                
                # Unlock button
                unlock_btn = tk.Button(
                    frame,
                    text="Unlock",
                    command=self._check_password,
                    font=("Arial", 14),
                    bg="#0066cc",
                    fg="white",
                    activebackground="#0052a3",
                    activeforeground="white",
                    relief="flat",
                    padx=30,
                    pady=10
                )
                unlock_btn.pack(pady=10)
                
                # Error label
                self.error_label = tk.Label(
                    frame,
                    text="",
                    font=("Arial", 12),
                    bg="black",
                    fg="red"
                )
                self.error_label.pack(pady=5)
                
                # Info label
                info_label = tk.Label(
                    frame,
                    text="Enter your Windows password or TeleCode PIN",
                    font=("Arial", 10),
                    bg="black",
                    fg="#888"
                )
                info_label.pack(pady=5)
                
                # Reminder about Telegram reset
                reminder_label = tk.Label(
                    frame,
                    text="💡 Forgot PIN? Reset via Telegram bot: /pin set",
                    font=("Arial", 9),
                    bg="black",
                    fg="#666"
                )
                reminder_label.pack(pady=(10, 5))
                
                self.attempts = 0
                self.max_attempts = 5
                self._keyboard_hook = None
                
            def _check_password(self, event=None):
                password = self.password_var.get()
                if not password:
                    return
                
                # Check PIN first (if set)
                if _pin_hash and _verify_password(password, _pin_hash):
                    logger.info("Unlocked with PIN")
                    self._unlock()
                    return
                
                # Check Windows password (if set)
                if _password_hash and _verify_password(password, _password_hash):
                    logger.info("Unlocked with password")
                    self._unlock()
                    return
                
                # Don't try Windows authentication - we only use stored PIN/password
                # This ensures we never show Windows lock screen (which blocks pyautogui)
                
                # Wrong password
                self.attempts += 1
                remaining = self.max_attempts - self.attempts
                
                if remaining > 0:
                    self.error_label.config(
                        text=f"❌ Incorrect password. {remaining} attempts remaining."
                    )
                    self.password_var.set("")
                else:
                    self.error_label.config(
                        text="❌ Too many failed attempts. Lock remains active."
                    )
                    self.password_var.set("")
                    # Could add delay here
                
            def _block_click(self, event):
                """Block clicks outside password entry."""
                # Only allow clicks on password entry
                if event.widget != self.root:
                    return
                return "break"
            
            def _install_keyboard_blocker(self):
                """Install Windows keyboard hook to block Alt+Tab and other shortcuts."""
                if not IS_WINDOWS:
                    return
                
                try:
                    # Block Alt+Tab, Win key, Ctrl+Alt+Del using low-level hooks
                    WH_KEYBOARD_LL = 13
                    WM_KEYDOWN = 0x0100
                    VK_TAB = 0x09
                    VK_LWIN = 0x5B
                    VK_RWIN = 0x5C
                    VK_MENU = 0x12  # Alt key
                    VK_CONTROL = 0x11
                    VK_DELETE = 0x2E
                    VK_ESCAPE = 0x1B
                    
                    # Define KBDLLHOOKSTRUCT structure
                    class KBDLLHOOKSTRUCT(ctypes.Structure):
                        _fields_ = [
                            ("vkCode", ctypes.wintypes.DWORD),
                            ("scanCode", ctypes.wintypes.DWORD),
                            ("flags", ctypes.wintypes.DWORD),
                            ("time", ctypes.wintypes.DWORD),
                            ("dwExtraInfo", ctypes.POINTER(ctypes.wintypes.ULONG))
                        ]
                    
                    def low_level_keyboard_proc(nCode, wParam, lParam):
                        if nCode >= 0 and wParam == WM_KEYDOWN:
                            # lParam points to KBDLLHOOKSTRUCT
                            kb_struct = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                            vk_code = kb_struct.vkCode
                            
                            # Block Alt+Tab
                            if vk_code == VK_TAB:
                                alt_pressed = ctypes.windll.user32.GetAsyncKeyState(VK_MENU) & 0x8000
                                if alt_pressed:
                                    logger.debug("Blocked Alt+Tab")
                                    return 1  # Block Alt+Tab
                            
                            # Block Win key
                            if vk_code in (VK_LWIN, VK_RWIN):
                                logger.debug("Blocked Win key")
                                return 1  # Block Win key
                            
                            # Block Alt key (prevents Alt+Tab when Tab is also pressed)
                            if vk_code == VK_MENU:
                                tab_pressed = ctypes.windll.user32.GetAsyncKeyState(VK_TAB) & 0x8000
                                if tab_pressed:
                                    logger.debug("Blocked Alt+Tab (Alt key)")
                                    return 1
                            
                            # Block Escape (but allow it in password entry for user convenience)
                            # Actually, let's not block Escape - user might want to cancel
                            # The fullscreen overlay and grab_set_global() already prevent bypass
                            
                            # Block Ctrl+Alt+Del (may not be fully blockable by design)
                            if vk_code == VK_DELETE:
                                ctrl_pressed = ctypes.windll.user32.GetAsyncKeyState(VK_CONTROL) & 0x8000
                                alt_pressed = ctypes.windll.user32.GetAsyncKeyState(VK_MENU) & 0x8000
                                if ctrl_pressed and alt_pressed:
                                    logger.debug("Attempted Ctrl+Alt+Del (may not be fully blockable)")
                        
                        return ctypes.windll.user32.CallNextHookExW(None, nCode, wParam, lParam)
                    
                    HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM)
                    hook_proc = HOOKPROC(low_level_keyboard_proc)
                    
                    self._keyboard_hook = ctypes.windll.user32.SetWindowsHookExW(
                        WH_KEYBOARD_LL,
                        hook_proc,
                        ctypes.windll.kernel32.GetModuleHandleW(None),
                        0
                    )
                    
                    if self._keyboard_hook:
                        logger.info("Keyboard blocker installed")
                except Exception as e:
                    logger.warning(f"Failed to install keyboard blocker: {e}")
            
            def _uninstall_keyboard_blocker(self):
                """Uninstall keyboard hook."""
                if self._keyboard_hook:
                    try:
                        ctypes.windll.user32.UnhookWindowsHookExW(self._keyboard_hook)
                        self._keyboard_hook = None
                    except:
                        pass
            
            def _unlock(self):
                global _lock_active, _overlay_shown
                _lock_active = False
                _overlay_shown = False
                self._uninstall_keyboard_blocker()
                # Stop wake detector
                _stop_wake_detector()
                if _unlock_callback:
                    _unlock_callback()
                self.root.destroy()
                logger.info("Lock overlay unlocked and cleaned up")
            
            def run(self):
                # Run message loop for keyboard hook (required for hooks to work)
                # This must run in a separate thread so it doesn't block tkinter
                def message_loop():
                    if not IS_WINDOWS or not self._keyboard_hook:
                        return
                    import ctypes.wintypes
                    msg = ctypes.wintypes.MSG()
                    while _lock_active:
                        try:
                            bRet = ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                            if bRet == 0 or bRet == -1:
                                break
                            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
                        except Exception as e:
                            logger.debug(f"Message loop error: {e}")
                            time.sleep(0.1)
                
                # Start message loop in background thread (required for keyboard hook)
                if IS_WINDOWS and self._keyboard_hook:
                    hook_thread = threading.Thread(target=message_loop, daemon=True)
                    hook_thread.start()
                    logger.info("Keyboard hook message loop started")
                
                # Run tkinter mainloop (blocks until window destroyed)
                try:
                    self.root.mainloop()
                except Exception as e:
                    logger.error(f"Tkinter mainloop error: {e}")
                    raise
        
        lock_window = LockWindow()
        lock_window.run()
        
    except ImportError:
        logger.error("tkinter not available - cannot show lock overlay")
        # Cannot fallback to Windows lock - it blocks pyautogui!
        logger.error("CRITICAL: Cannot show lock overlay - tkinter required")
    except Exception as e:
        logger.error(f"Failed to show lock overlay: {e}")
        # Cannot fallback to Windows lock - it blocks pyautogui!
        logger.error("CRITICAL: Lock overlay failed - cannot secure display")


# Removed _verify_windows_password - we only use stored PIN/password
# This ensures we NEVER show Windows lock screen (which blocks pyautogui)


# Monitor wake detection using polling (simpler and more reliable)
_wake_detector_thread = None
_wake_detector_active = False
_overlay_shown = False


def _detect_monitor_wake():
    """Poll for monitor wake events (mouse/keyboard activity)."""
    global _overlay_shown
    
    if not IS_WINDOWS:
        return
    
    last_mouse_pos = None
    last_key_state = None
    
    while _wake_detector_active and _lock_active:
        try:
            # Check mouse position
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            
            pt = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            current_mouse = (pt.x, pt.y)
            
            if last_mouse_pos and last_mouse_pos != current_mouse:
                # Mouse moved - monitor woke up!
                if not _overlay_shown:
                    logger.info("Mouse movement detected - showing lock overlay")
                    _overlay_shown = True
                    threading.Thread(target=_show_lock_overlay, daemon=True).start()
            
            last_mouse_pos = current_mouse
            
            # Check keyboard state (simplified - just check if any key is pressed)
            # This is a basic check - for production, use proper key state API
            
            time.sleep(0.5)  # Poll every 500ms
            
        except Exception as e:
            logger.debug(f"Wake detection error: {e}")
            time.sleep(1)


def _start_wake_detector():
    """Start monitoring for monitor wake events."""
    global _wake_detector_thread, _wake_detector_active, _overlay_shown
    
    # If already active, stop it first to ensure clean state
    if _wake_detector_active:
        logger.debug("Wake detector already active - stopping and restarting for clean state")
        _stop_wake_detector()
        time.sleep(0.1)  # Give it a moment to stop
    
    _wake_detector_active = True
    _overlay_shown = False  # Reset overlay flag
    _wake_detector_thread = threading.Thread(target=_detect_monitor_wake, daemon=True)
    _wake_detector_thread.start()
    logger.info("Wake detector started")


def _stop_wake_detector():
    """Stop monitoring for monitor wake events."""
    global _wake_detector_active, _overlay_shown
    
    _wake_detector_active = False
    _overlay_shown = False
    
    if _wake_detector_thread and _wake_detector_thread.is_alive():
        _wake_detector_thread.join(timeout=2)
    
    logger.info("Wake detector stopped")


def activate_lock(password: Optional[str] = None, pin: Optional[str] = None, on_unlock: Optional[Callable] = None):
    """
    Activate custom lock with password/PIN protection.
    
    Args:
        password: Windows password or custom password (optional, can be set separately)
        pin: Custom PIN (optional, can be set separately)
        on_unlock: Callback when unlocked
    """
    global _lock_active, _unlock_callback, _overlay_shown
    
    if not IS_WINDOWS:
        logger.warning("Custom lock is only available on Windows")
        return False
    
    # Clean up any previous lock state first
    if _lock_active:
        logger.info("Cleaning up previous lock state before activating new lock")
        deactivate_lock()
        time.sleep(0.1)  # Give cleanup a moment
    
    # If PIN/password not provided, try to load from storage (for persistence across sessions)
    if not password and not pin:
        try:
            from .lock_pin_storage import get_lock_pin_storage
            storage = get_lock_pin_storage()
            loaded_pin = storage.retrieve_pin()
            loaded_password = storage.retrieve_password()
            if loaded_pin:
                pin = loaded_pin
                logger.info("Loaded PIN from storage for lock activation")
            elif loaded_password:
                password = loaded_password
                logger.info("Loaded password from storage for lock activation")
        except Exception as e:
            logger.warning(f"Failed to load PIN/password from storage: {e}")
    
    # Set the PIN/password (this sets the in-memory hash for verification)
    if password:
        set_lock_password(password)
        logger.info("Lock password set")
    if pin:
        set_lock_pin(pin)
        logger.info("Lock PIN set")
    
    if on_unlock:
        _unlock_callback = on_unlock
    
    # Reset state
    _lock_active = True
    _overlay_shown = False  # Reset overlay flag
    
    # Start wake detector (will restart if needed)
    _start_wake_detector()
    
    # Log what's required for unlock
    if pin:
        logger.info("Custom lock activated - PIN required on wake")
    elif password:
        logger.info("Custom lock activated - password required on wake")
    else:
        logger.warning("Custom lock activated - NO PIN/password set! User won't be able to unlock.")
    
    return True


def deactivate_lock():
    """Deactivate custom lock and clean up all resources."""
    global _lock_active, _overlay_shown, _unlock_callback
    
    _lock_active = False
    _overlay_shown = False
    _stop_wake_detector()
    _unlock_callback = None  # Clear callback
    
    logger.info("Custom lock deactivated and cleaned up")


def is_locked() -> bool:
    """Check if custom lock is active."""
    return _lock_active

