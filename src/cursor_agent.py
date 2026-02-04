"""
============================================
TeleCode v0.1 - Cursor Agent Bridge
============================================
Automated integration layer for Cursor IDE AI control.

This module SENDS prompts directly to Cursor Composer via
keyboard automation. Works cross-platform:
- Windows: Virtual display (monitor off, session active)
- macOS: Virtual display or caffeinate
- Linux: Xvfb virtual framebuffer

ARCHITECTURE:
1. Opens Cursor with workspace (if not already open)
2. Focuses Cursor window
3. Opens Composer (Ctrl+L for chat, Ctrl+I for inline)
4. Pastes the prompt via clipboard
5. Sends Enter to execute
6. Monitors git for changes
7. Provides accept/revert controls

SECURITY:
- All prompts are scanned by PromptGuard before sending
- Workspace must be in DEV_ROOT sandbox
- Full audit logging

CROSS-PLATFORM SUPPORT:
- Windows: Win32 API for window management
- macOS: AppleScript for window management, Cmd instead of Ctrl
- Linux: xdotool/wmctrl for window management, Xvfb for headless

============================================
"""

import os
import sys
import json
import logging
import shutil
import subprocess
import time
import threading
import asyncio
import platform
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("telecode.cursor_agent")

# Platform detection
IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# Keyboard modifier for shortcuts (Cmd on macOS, Ctrl elsewhere)
MODIFIER_KEY = "command" if IS_MACOS else "ctrl"

# Keyboard automation imports (with fallbacks)
AUTOMATION_AVAILABLE = False
try:
    import pyautogui
    import pyperclip
    pyautogui.FAILSAFE = False  # Disable fail-safe for headless operation
    pyautogui.PAUSE = 0.1  # Small pause between actions
    AUTOMATION_AVAILABLE = True
    logger.info("Keyboard automation available (pyautogui + pyperclip)")
except ImportError as e:
    logger.warning(f"Keyboard automation not available: {e}")
    logger.warning("Install with: pip install pyautogui pyperclip")

# OCR Support for text extraction from screenshots
OCR_AVAILABLE = False
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
    logger.info("OCR support available (pytesseract)")
except ImportError:
    logger.info("pytesseract not installed - OCR text extraction unavailable")
    logger.info("Install with: pip install pytesseract pillow")
    logger.info("Also requires Tesseract OCR engine: https://github.com/tesseract-ocr/tesseract")

# Virtual display support for Linux headless operation
VIRTUAL_DISPLAY_AVAILABLE = False
_virtual_display = None
if IS_LINUX:
    try:
        from pyvirtualdisplay import Display
        VIRTUAL_DISPLAY_AVAILABLE = True
        logger.info("Virtual display support available (pyvirtualdisplay)")
    except ImportError:
        logger.info("pyvirtualdisplay not installed - headless mode unavailable on Linux")
        logger.info("Install with: pip install pyvirtualdisplay")

# Windows-specific imports for window management
if IS_WINDOWS:
    try:
        import ctypes
        from ctypes import wintypes
        WINDOWS_API_AVAILABLE = True
    except ImportError:
        WINDOWS_API_AVAILABLE = False
else:
    WINDOWS_API_AVAILABLE = False

# Linux window management tools detection
XDOTOOL_AVAILABLE = False
WMCTRL_AVAILABLE = False
if IS_LINUX:
    XDOTOOL_AVAILABLE = shutil.which("xdotool") is not None
    WMCTRL_AVAILABLE = shutil.which("wmctrl") is not None
    if XDOTOOL_AVAILABLE:
        logger.info("xdotool available for Linux window management")
    if WMCTRL_AVAILABLE:
        logger.info("wmctrl available for Linux window management")


class AgentState(Enum):
    """Current state of the AI agent workflow."""
    IDLE = "idle"
    PROMPT_SENT = "prompt_sent"
    AWAITING_CHANGES = "awaiting_changes"
    CHANGES_PENDING = "changes_pending"
    PROCESSING = "processing"
    ERROR = "error"


class PromptMode(Enum):
    """Mode for sending prompts to Cursor."""
    CHAT = "chat"       # Ctrl+L - Chat panel, changes need Keep All button
    AGENT = "agent"     # Ctrl+Shift+I - Agent mode, auto-saves files (SAFEST)


@dataclass
class AgentSession:
    """Tracks an AI agent session."""
    state: AgentState = AgentState.IDLE
    current_prompt: str = ""
    workspace: str = ""
    started_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    changes_detected: bool = False
    pending_files: list = field(default_factory=list)
    last_error: str = ""
    # Track files at prompt start to detect changes from latest prompt only
    files_at_prompt_start: list = field(default_factory=list)
    # Track agent count for cleanup
    agent_count: int = 0
    # User's preferred mode for sending prompts
    prompt_mode: str = "agent"  # Default to agent (safer - auto-saves)


@dataclass
class AgentResult:
    """Result of an agent operation."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class CursorStatus(Enum):
    """Status of Cursor IDE."""
    NOT_RUNNING = "not_running"
    STARTING = "starting"
    RUNNING = "running"
    READY = "ready"
    ERROR = "error"


class WindowCapture:
    """
    Windows API-based window capture for screenshots behind lock overlay.
    
    Uses PrintWindow API to capture window content even when obscured by overlay.
    This allows screenshots to show actual Cursor window content instead of the lock screen.
    """
    
    @staticmethod
    def capture_window_by_handle(hwnd: int) -> Optional[Image.Image]:
        """
        Capture window content using Windows API (works even when obscured).
        
        Args:
            hwnd: Window handle (HWND)
            
        Returns:
            PIL Image object, or None if failed
        """
        if not IS_WINDOWS or not WINDOWS_API_AVAILABLE:
            return None
        
        try:
            from PIL import Image
            import ctypes
            from ctypes import wintypes
            
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            
            # Get window dimensions
            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long),
                           ("top", ctypes.c_long),
                           ("right", ctypes.c_long),
                           ("bottom", ctypes.c_long)]
            
            rect = RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                logger.warning("Failed to get window rect")
                return None
            
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            
            if width <= 0 or height <= 0:
                logger.warning(f"Invalid window dimensions: {width}x{height}")
                return None
            
            # Get window device context
            hwnd_dc = user32.GetWindowDC(hwnd)
            if not hwnd_dc:
                logger.warning("Failed to get window DC")
                return None
            
            try:
                # Create compatible device context
                mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
                if not mem_dc:
                    logger.warning("Failed to create compatible DC")
                    return None
                
                try:
                    # Create compatible bitmap
                    bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
                    if not bitmap:
                        logger.warning("Failed to create compatible bitmap")
                        return None
                    
                    try:
                        # Select bitmap into device context
                        old_bitmap = gdi32.SelectObject(mem_dc, bitmap)
                        
                        # Use PrintWindow to capture window content (works even when obscured)
                        # PW_RENDERFULLCONTENT = 0x00000002
                        PW_RENDERFULLCONTENT = 0x2
                        success = user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)
                        
                        if not success:
                            # Fallback: Try BitBlt if PrintWindow fails
                            logger.debug("PrintWindow failed, trying BitBlt")
                            success = gdi32.BitBlt(mem_dc, 0, 0, width, height, hwnd_dc, 0, 0, 0x00CC0020)  # SRCCOPY
                        
                        gdi32.SelectObject(mem_dc, old_bitmap)
                        
                        if not success:
                            logger.warning("Failed to capture window content")
                            return None
                        
                        # Convert bitmap to PIL Image
                        # Define BITMAPINFOHEADER structure
                        class BITMAPINFOHEADER(ctypes.Structure):
                            _fields_ = [
                                ("biSize", wintypes.DWORD),
                                ("biWidth", ctypes.c_long),
                                ("biHeight", ctypes.c_long),
                                ("biPlanes", wintypes.WORD),
                                ("biBitCount", wintypes.WORD),
                                ("biCompression", wintypes.DWORD),
                                ("biSizeImage", wintypes.DWORD),
                                ("biXPelsPerMeter", ctypes.c_long),
                                ("biYPelsPerMeter", ctypes.c_long),
                                ("biClrUsed", wintypes.DWORD),
                                ("biClrImportant", wintypes.DWORD),
                            ]
                        
                        class BITMAPINFO(ctypes.Structure):
                            _fields_ = [("bmiHeader", BITMAPINFOHEADER),
                                       ("bmiColors", wintypes.DWORD * 3)]
                        
                        bmp_info = BITMAPINFO()
                        bmp_info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
                        bmp_info.bmiHeader.biWidth = width
                        bmp_info.bmiHeader.biHeight = -height  # Negative for top-down DIB
                        bmp_info.bmiHeader.biPlanes = 1
                        bmp_info.bmiHeader.biBitCount = 32
                        bmp_info.bmiHeader.biCompression = 0  # BI_RGB
                        
                        # Allocate buffer for image data
                        buffer_size = width * height * 4  # 32-bit RGBA
                        buffer = (ctypes.c_byte * buffer_size)()
                        
                        # Get bitmap bits
                        if not gdi32.GetDIBits(mem_dc, bitmap, 0, height, buffer, ctypes.byref(bmp_info), 0):
                            logger.warning("Failed to get bitmap bits")
                            return None
                        
                        # Create PIL Image from buffer
                        # Note: Windows bitmap is BGR, PIL expects RGB
                        img = Image.frombuffer('RGBA', (width, height), buffer, 'raw', 'BGRA', 0, 1)
                        
                        logger.info(f"Successfully captured window {hwnd} ({width}x{height})")
                        return img
                        
                    finally:
                        gdi32.DeleteObject(bitmap)
                        
                finally:
                    gdi32.DeleteDC(mem_dc)
                    
            finally:
                user32.ReleaseDC(hwnd, hwnd_dc)
                
        except Exception as e:
            logger.error(f"Failed to capture window by handle: {e}", exc_info=True)
            return None
    
    @staticmethod
    def capture_cursor_window() -> Optional[Image.Image]:
        """
        Capture Cursor window using Windows API.
        
        Returns:
            PIL Image object, or None if failed
        """
        if not IS_WINDOWS:
            return None
        
        try:
            # Find Cursor window (call at runtime to avoid forward reference)
            # Use the public method which will call the Windows-specific implementation
            hwnd = WindowManager.find_cursor_window()
            if hwnd is None:
                logger.warning("Cursor window not found for capture")
                return None
            
            # Capture window content
            return WindowCapture.capture_window_by_handle(hwnd)
            
        except Exception as e:
            logger.error(f"Failed to capture Cursor window: {e}")
            return None


class WindowManager:
    """
    Cross-platform window management for Cursor IDE.
    
    Handles finding, focusing, and interacting with Cursor windows.
    Platform support:
    - Windows: Win32 API (works with virtual display - monitor off, session active)
    - macOS: AppleScript
    - Linux: xdotool/wmctrl
    """
    
    @staticmethod
    def find_cursor_window(workspace_name: Optional[str] = None) -> Optional[Any]:
        """
        Find the Cursor IDE window.
        
        Args:
            workspace_name: Optional workspace name to match in window title
        
        Returns:
            Window identifier (HWND on Windows, window ID on Linux, app name on macOS)
            or None if not found
        """
        if IS_WINDOWS:
            return WindowManager._find_cursor_window_windows(workspace_name)
        elif IS_MACOS:
            return WindowManager._find_cursor_window_macos(workspace_name)
        elif IS_LINUX:
            return WindowManager._find_cursor_window_linux(workspace_name)
        return None
    
    @staticmethod
    def _find_cursor_window_windows(workspace_name: Optional[str] = None) -> Optional[int]:
        """Windows: Find Cursor window using Win32 API."""
        if not WINDOWS_API_AVAILABLE:
            return None
        
        try:
            user32 = ctypes.windll.user32
            
            EnumWindowsProc = ctypes.WINFUNCTYPE(
                wintypes.BOOL, 
                wintypes.HWND, 
                wintypes.LPARAM
            )
            
            found_hwnd = None
            
            def enum_callback(hwnd, lparam):
                nonlocal found_hwnd
                
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buffer, length + 1)
                    title = buffer.value
                    
                    if "Cursor" in title or title.endswith("- Cursor"):
                        if user32.IsWindowVisible(hwnd):
                            if workspace_name:
                                if workspace_name.lower() in title.lower():
                                    found_hwnd = hwnd
                                    return False
                            else:
                                found_hwnd = hwnd
                                return False
                
                return True
            
            user32.EnumWindows(EnumWindowsProc(enum_callback), 0)
            return found_hwnd
            
        except Exception as e:
            logger.warning(f"Failed to find Cursor window (Windows): {e}")
            return None
    
    @staticmethod
    def _find_cursor_window_macos(workspace_name: Optional[str] = None) -> Optional[str]:
        """macOS: Check if Cursor is running using AppleScript."""
        try:
            # Check if Cursor app is running
            script = '''
            tell application "System Events"
                set cursorRunning to (name of processes) contains "Cursor"
            end tell
            return cursorRunning
            '''
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0 and 'true' in result.stdout.lower():
                # If workspace_name provided, check window title
                if workspace_name:
                    title_script = '''
                    tell application "System Events"
                        tell process "Cursor"
                            set windowNames to name of every window
                        end tell
                    end tell
                    return windowNames
                    '''
                    title_result = subprocess.run(
                        ['osascript', '-e', title_script],
                        capture_output=True, text=True, timeout=5
                    )
                    if workspace_name.lower() in title_result.stdout.lower():
                        return "Cursor"
                    return None
                return "Cursor"
            return None
            
        except Exception as e:
            logger.warning(f"Failed to find Cursor window (macOS): {e}")
            return None
    
    @staticmethod
    def _find_cursor_window_linux(workspace_name: Optional[str] = None) -> Optional[str]:
        """Linux: Find Cursor window using xdotool or wmctrl."""
        try:
            if XDOTOOL_AVAILABLE:
                # Use xdotool to search for window
                search_name = workspace_name if workspace_name else "Cursor"
                result = subprocess.run(
                    ['xdotool', 'search', '--name', search_name],
                    capture_output=True, text=True, timeout=5
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    # Return first matching window ID
                    window_ids = result.stdout.strip().split('\n')
                    for wid in window_ids:
                        # Verify it's a Cursor window
                        name_result = subprocess.run(
                            ['xdotool', 'getwindowname', wid],
                            capture_output=True, text=True, timeout=5
                        )
                        if 'cursor' in name_result.stdout.lower():
                            return wid
                    return window_ids[0] if window_ids else None
                    
            elif WMCTRL_AVAILABLE:
                # Use wmctrl to list windows
                result = subprocess.run(
                    ['wmctrl', '-l'],
                    capture_output=True, text=True, timeout=5
                )
                
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'cursor' in line.lower():
                            if workspace_name and workspace_name.lower() not in line.lower():
                                continue
                            # Extract window ID (first column)
                            parts = line.split()
                            if parts:
                                return parts[0]
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to find Cursor window (Linux): {e}")
            return None
    
    @staticmethod
    def get_cursor_status(workspace_name: Optional[str] = None) -> CursorStatus:
        """
        Get the current status of Cursor IDE.
        
        Args:
            workspace_name: Optional workspace name to check if specific workspace is open
            
        Returns:
            CursorStatus enum value
        """
        try:
            if not WindowManager.is_cursor_running():
                return CursorStatus.NOT_RUNNING
            
            window = WindowManager.find_cursor_window(workspace_name)
            if window:
                return CursorStatus.READY
            elif WindowManager.find_cursor_window():
                return CursorStatus.RUNNING
            else:
                return CursorStatus.STARTING
                
        except Exception as e:
            logger.warning(f"Error checking Cursor status: {e}")
            return CursorStatus.ERROR
    
    @staticmethod
    def focus_cursor_window(window_id: Optional[Any] = None) -> bool:
        """
        Focus the Cursor window.
        
        Args:
            window_id: Window identifier (will search if not provided)
            
        Returns:
            True if window was focused successfully
        """
        if IS_WINDOWS:
            return WindowManager._focus_cursor_window_windows(window_id)
        elif IS_MACOS:
            return WindowManager._focus_cursor_window_macos()
        elif IS_LINUX:
            return WindowManager._focus_cursor_window_linux(window_id)
        return False
    
    @staticmethod
    def _focus_cursor_window_windows(hwnd: Optional[int] = None) -> bool:
        """Windows: Focus Cursor window using Win32 API."""
        if not WINDOWS_API_AVAILABLE:
            return True  # Assume focused
        
        try:
            user32 = ctypes.windll.user32
            
            if hwnd is None:
                hwnd = WindowManager._find_cursor_window_windows()
            
            if hwnd is None:
                logger.warning("Cursor window not found")
                return False
            
            SW_RESTORE = 9
            user32.ShowWindow(hwnd, SW_RESTORE)
            
            foreground = user32.GetForegroundWindow()
            current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
            foreground_thread = user32.GetWindowThreadProcessId(foreground, None)
            
            user32.AttachThreadInput(current_thread, foreground_thread, True)
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
            user32.AttachThreadInput(current_thread, foreground_thread, False)
            
            time.sleep(0.3)
            return True
            
        except Exception as e:
            logger.warning(f"Failed to focus Cursor window (Windows): {e}")
            return False
    
    @staticmethod
    def _focus_cursor_window_macos() -> bool:
        """macOS: Focus Cursor window using AppleScript."""
        try:
            script = '''
            tell application "Cursor"
                activate
            end tell
            tell application "System Events"
                tell process "Cursor"
                    set frontmost to true
                end tell
            end tell
            '''
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True, text=True, timeout=5
            )
            
            time.sleep(0.3)
            return result.returncode == 0
            
        except Exception as e:
            logger.warning(f"Failed to focus Cursor window (macOS): {e}")
            return False
    
    @staticmethod
    def _focus_cursor_window_linux(window_id: Optional[str] = None) -> bool:
        """Linux: Focus Cursor window using xdotool or wmctrl."""
        try:
            if window_id is None:
                window_id = WindowManager._find_cursor_window_linux()
            
            if window_id is None:
                logger.warning("Cursor window not found")
                return False
            
            if XDOTOOL_AVAILABLE:
                result = subprocess.run(
                    ['xdotool', 'windowactivate', '--sync', window_id],
                    capture_output=True, text=True, timeout=5
                )
                time.sleep(0.3)
                return result.returncode == 0
                
            elif WMCTRL_AVAILABLE:
                result = subprocess.run(
                    ['wmctrl', '-i', '-a', window_id],
                    capture_output=True, text=True, timeout=5
                )
                time.sleep(0.3)
                return result.returncode == 0
            
            return False
            
        except Exception as e:
            logger.warning(f"Failed to focus Cursor window (Linux): {e}")
            return False
    
    @staticmethod
    def is_cursor_running() -> bool:
        """Check if Cursor is running (cross-platform)."""
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                name = proc.info['name'].lower()
                if 'cursor' in name:
                    return True
            return False
        except Exception:
            return False


class CursorAgentBridge:
    """
    Bridge between TeleCode and Cursor IDE.
    
    SENDS prompts directly to Cursor Composer via keyboard automation.
    Cross-platform support:
    - Windows: Works with virtual display (monitor off, session active)
    - macOS: Works with caffeinate or virtual display
    - Linux: Works with Xvfb virtual display
    """
    
    # TeleCode working directory name
    TELECODE_DIR = ".telecode"
    
    # Files
    PROMPT_FILE = "prompt.md"
    SESSION_FILE = "session.json"
    HISTORY_FILE = "history.json"
    
    # Timing constants (seconds)
    CURSOR_LAUNCH_WAIT = 3.0      # Wait for Cursor to launch
    CURSOR_FOCUS_WAIT = 0.5       # Wait after focusing
    COMPOSER_OPEN_WAIT = 0.8      # Wait for Composer to open
    TYPING_INTERVAL = 0.02        # Interval between keystrokes
    
    def __init__(self, workspace: Path, cursor_path: Optional[str] = None):
        """
        Initialize the Cursor Agent Bridge.
        
        Args:
            workspace: The workspace directory
            cursor_path: Path to cursor executable (auto-detected if None)
        """
        self.workspace = Path(workspace)
        self.cursor_path = cursor_path or shutil.which("cursor")
        self.telecode_dir = self.workspace / self.TELECODE_DIR
        self.session = AgentSession(workspace=str(workspace))
        self.window_manager = WindowManager()
        
        # Ensure .telecode directory exists
        self._ensure_telecode_dir()
        
        # Load existing session if any
        self._load_session()
        
        logger.info(f"CursorAgentBridge initialized for {workspace}")
        logger.info(f"Automation available: {AUTOMATION_AVAILABLE}")
    
    def _ensure_telecode_dir(self):
        """Create .telecode directory if it doesn't exist."""
        self.telecode_dir.mkdir(exist_ok=True)
        
        # Add to .gitignore if not already there
        gitignore = self.workspace / ".gitignore"
        if gitignore.exists():
            content = gitignore.read_text()
            if ".telecode/" not in content:
                with open(gitignore, "a") as f:
                    f.write("\n# TeleCode working directory\n.telecode/\n")
        else:
            with open(gitignore, "w") as f:
                f.write("# TeleCode working directory\n.telecode/\n")
    
    def _load_session(self):
        """Load session from disk."""
        session_file = self.telecode_dir / self.SESSION_FILE
        if session_file.exists():
            try:
                data = json.loads(session_file.read_text())
                self.session = AgentSession(
                    state=AgentState(data.get("state", "idle")),
                    current_prompt=data.get("current_prompt", ""),
                    workspace=data.get("workspace", str(self.workspace)),
                    started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
                    last_activity=datetime.fromisoformat(data["last_activity"]) if data.get("last_activity") else None,
                    changes_detected=data.get("changes_detected", False),
                    pending_files=data.get("pending_files", []),
                    last_error=data.get("last_error", ""),
                    files_at_prompt_start=data.get("files_at_prompt_start", []),
                    agent_count=data.get("agent_count", 0),
                    prompt_mode=data.get("prompt_mode", "agent")
                )
            except Exception as e:
                logger.warning(f"Failed to load session: {e}")
    
    def _save_session(self):
        """Save session to disk."""
        session_file = self.telecode_dir / self.SESSION_FILE
        try:
            data = {
                "state": self.session.state.value,
                "current_prompt": self.session.current_prompt,
                "workspace": self.session.workspace,
                "started_at": self.session.started_at.isoformat() if self.session.started_at else None,
                "last_activity": self.session.last_activity.isoformat() if self.session.last_activity else None,
                "changes_detected": self.session.changes_detected,
                "pending_files": self.session.pending_files,
                "last_error": self.session.last_error,
                "files_at_prompt_start": self.session.files_at_prompt_start,
                "agent_count": self.session.agent_count,
                "prompt_mode": self.session.prompt_mode
            }
            session_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save session: {e}")
    
    def _add_to_history(self, prompt: str, action: str, result: str):
        """Add an entry to prompt history."""
        history_file = self.telecode_dir / self.HISTORY_FILE
        
        history = []
        if history_file.exists():
            try:
                history = json.loads(history_file.read_text())
            except:
                pass
        
        history.append({
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt[:500],
            "action": action,
            "result": result
        })
        
        # Keep last 100 entries
        history = history[-100:]
        
        try:
            history_file.write_text(json.dumps(history, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save history: {e}")
    
    def _get_current_files_snapshot(self) -> List[str]:
        """Get a snapshot of all files currently in git status (modified/new/staged)."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return []
            
            files = []
            for line in result.stdout.strip().split("\n"):
                if line.strip() and ".telecode" not in line:
                    # Extract filename (skip status prefix)
                    filename = line[3:].strip()
                    files.append(filename)
            return files
        except Exception as e:
            logger.warning(f"Failed to get files snapshot: {e}")
            return []
    
    def _close_existing_panels(self) -> None:
        """Close any existing composer/chat panels to start fresh."""
        if not AUTOMATION_AVAILABLE:
            return
        
        try:
            # Press Escape a few times to close any open panels/dialogs
            for _ in range(2):
                pyautogui.press('escape')
                time.sleep(0.1)
        except Exception as e:
            logger.warning(f"Failed to close panels: {e}")
    
    def _navigate_to_agent_tab(self, agent_id: int) -> bool:
        """
        Navigate to a specific agent tab using keyboard shortcuts.
        
        Agent tabs in Cursor are accessed via Ctrl+1, Ctrl+2, etc.
        The agent_id is 0-indexed (first agent = 0), but tabs are 1-indexed.
        
        Args:
            agent_id: The agent tab index (0 = first agent, 1 = second, etc.)
            
        Returns:
            True if navigation succeeded, False otherwise
        """
        if not AUTOMATION_AVAILABLE:
            return False
        
        try:
            # Focus Cursor window first
            if not WindowManager.focus_cursor_window():
                logger.warning(f"[NAVIGATE] Could not focus Cursor window")
                return False
            
            time.sleep(0.3)
            
            # Agent tabs are 1-indexed, so agent_id 0 = tab 1, agent_id 1 = tab 2, etc.
            tab_number = agent_id + 1
            
            # Navigate to the specific agent tab using Ctrl+{tab_number}
            logger.info(f"[NAVIGATE] Switching to agent tab {tab_number} (agent_id={agent_id})...")
            pyautogui.hotkey(MODIFIER_KEY, str(tab_number))
            time.sleep(0.3)  # Wait for tab switch to complete
            
            logger.info(f"[NAVIGATE] Successfully navigated to agent tab {tab_number}")
            return True
            
        except Exception as e:
            logger.warning(f"[NAVIGATE] Failed to navigate to agent tab {agent_id}: {e}")
            return False
    
    def _cleanup_old_agents(self, max_agents: int = 5) -> bool:
        """
        Close oldest agent tabs if we have too many open.
        Uses Ctrl+W to close tabs.
        
        Args:
            max_agents: Maximum number of agent tabs to keep
            
        Returns:
            True if cleanup was performed
        """
        if not AUTOMATION_AVAILABLE:
            return False
        
        if self.session.agent_count <= max_agents:
            return False
        
        try:
            agents_to_close = self.session.agent_count - max_agents
            logger.info(f"Closing {agents_to_close} old agent tabs...")
            
            # Focus Cursor first
            WindowManager.focus_cursor_window()
            time.sleep(0.3)
            
            # Close oldest tabs (they should be leftmost)
            for i in range(agents_to_close):
                # Ctrl+1 (Cmd+1 on macOS) to go to first tab, then Ctrl+W to close it
                pyautogui.hotkey(MODIFIER_KEY, '1')
                time.sleep(0.2)
                pyautogui.hotkey(MODIFIER_KEY, 'w')
                time.sleep(0.2)
            
            self.session.agent_count = max_agents
            self._save_session()
            
            logger.info(f"Cleaned up {agents_to_close} agent tabs")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to cleanup agents: {e}")
            return False
    
    def _save_prompt_file(self, prompt: str, model: Optional[str] = None):
        """Save prompt to file for logging/backup."""
        prompt_file = self.telecode_dir / self.PROMPT_FILE
        
        model_info = f"\n**Model:** {model}" if model else ""
        
        prompt_content = f"""# 🤖 TeleCode AI Prompt

**Sent at:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Workspace:** `{self.workspace.name}`{model_info}
**Status:** Sent to Cursor Composer

---

## Prompt

{prompt}

---
*This prompt was automatically sent to Cursor Composer by TeleCode.*
"""
        
        try:
            prompt_file.write_text(prompt_content, encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save prompt file: {e}")
    
    def _open_cursor_workspace(self) -> bool:
        """
        Open Cursor with the workspace.
        
        Returns:
            True if Cursor was opened/is running
        """
        if not self.cursor_path:
            logger.error("Cursor CLI not found")
            return False
        
        try:
            # Check if Cursor is already running with this workspace
            if WindowManager.is_cursor_running():
                logger.info("Cursor is already running")
                return True
            
            # Open Cursor with the workspace
            subprocess.Popen(
                [self.cursor_path, str(self.workspace)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(self.workspace)
            )
            
            logger.info(f"Opened Cursor with workspace: {self.workspace}")
            
            # Wait for Cursor to launch
            time.sleep(self.CURSOR_LAUNCH_WAIT)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to open Cursor: {e}")
            return False
    
    def check_cursor_status(self) -> Dict[str, Any]:
        """
        Check the current status of Cursor for this workspace.
        
        Returns:
            Dict with status information:
            - is_running: bool - Is Cursor process running
            - has_window: bool - Is Cursor window visible
            - workspace_open: bool - Is this specific workspace open
            - status: str - Human readable status
        """
        workspace_name = self.workspace.name
        
        is_running = WindowManager.is_cursor_running()
        
        if not is_running:
            return {
                "is_running": False,
                "has_window": False,
                "workspace_open": False,
                "status": CursorStatus.NOT_RUNNING.value,
                "message": "Cursor is not running"
            }
        
        # Check for any Cursor window
        any_window = WindowManager.find_cursor_window()
        if not any_window:
            return {
                "is_running": True,
                "has_window": False,
                "workspace_open": False,
                "status": CursorStatus.STARTING.value,
                "message": "Cursor is starting..."
            }
        
        # Check for this workspace specifically
        workspace_window = WindowManager.find_cursor_window(workspace_name)
        if workspace_window:
            return {
                "is_running": True,
                "has_window": True,
                "workspace_open": True,
                "status": CursorStatus.READY.value,
                "message": f"Cursor is open with {workspace_name}"
            }
        
        return {
            "is_running": True,
            "has_window": True,
            "workspace_open": False,
            "status": CursorStatus.RUNNING.value,
            "message": "Cursor is open (different workspace)"
        }
    
    async def open_cursor_and_wait(
        self,
        status_callback: Optional[callable] = None,
        timeout: float = 30.0,
        poll_interval: float = 1.0
    ) -> AgentResult:
        """
        Open Cursor for this workspace and wait for it to be ready.
        
        This method is async and can report progress via callback.
        
        Args:
            status_callback: Optional async callback function(message: str, is_complete: bool)
                            Called periodically with status updates
            timeout: Maximum time to wait for Cursor (seconds)
            poll_interval: Time between status checks (seconds)
            
        Returns:
            AgentResult indicating success/failure
        """
        workspace_name = self.workspace.name
        
        async def report_status(message: str, is_complete: bool = False):
            """Helper to call the status callback if provided.
            
            For non-complete updates, we use create_task to avoid blocking the event loop.
            This allows button callbacks to be processed while Cursor is opening.
            For complete updates, we await to ensure they're sent before returning.
            """
            if status_callback:
                try:
                    if is_complete:
                        # Critical updates: await to ensure they're sent
                        await status_callback(message, is_complete)
                    else:
                        # Non-critical updates: fire-and-forget to avoid blocking event loop
                        # This allows button callbacks to be processed during Cursor opening
                        asyncio.create_task(status_callback(message, is_complete))
                except Exception as e:
                    logger.warning(f"Status callback error: {e}")
        
        # Step 1: Check current status
        status = self.check_cursor_status()
        
        if status["workspace_open"]:
            await report_status(f"✅ Cursor already open with `{workspace_name}`", True)
            return AgentResult(
                success=True,
                message="Cursor is already open",
                data=status
            )
        
        # Step 2: If Cursor is not running, start it
        if not status["is_running"]:
            await report_status(f"🚀 Launching Cursor for `{workspace_name}`...")
            
            if not self.cursor_path:
                await report_status("❌ Cursor CLI not found", True)
                return AgentResult(
                    success=False,
                    message="Cursor CLI not found",
                    error="Please install Cursor and ensure 'cursor' is in your PATH"
                )
            
            try:
                subprocess.Popen(
                    [self.cursor_path, str(self.workspace)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    cwd=str(self.workspace)
                )
                logger.info(f"Launched Cursor for workspace: {self.workspace}")
            except Exception as e:
                await report_status(f"❌ Failed to launch Cursor: {e}", True)
                return AgentResult(
                    success=False,
                    message="Failed to launch Cursor",
                    error=str(e)
                )
        elif not status["workspace_open"]:
            # Cursor running but different workspace - open this workspace
            await report_status(f"📂 Opening `{workspace_name}` in Cursor...")
            
            try:
                subprocess.Popen(
                    [self.cursor_path, str(self.workspace)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    cwd=str(self.workspace)
                )
            except Exception as e:
                await report_status(f"❌ Failed to open workspace: {e}", True)
                return AgentResult(
                    success=False,
                    message="Failed to open workspace in Cursor",
                    error=str(e)
                )
        
        # Step 3: Wait for Cursor to be ready
        await report_status(f"⏳ Waiting for Cursor to open `{workspace_name}`...")
        
        start_time = time.time()
        dots = 0
        last_status = ""
        
        while time.time() - start_time < timeout:
            # Check status
            status = self.check_cursor_status()
            
            if status["workspace_open"]:
                await report_status(f"✅ Cursor ready with `{workspace_name}`", True)
                return AgentResult(
                    success=True,
                    message="Cursor is ready!",
                    data=status
                )
            
            # Show progress with animated dots
            dots = (dots % 3) + 1
            elapsed = int(time.time() - start_time)
            
            current_status = status.get("message", "Loading...")
            if current_status != last_status:
                await report_status(f"⏳ {current_status} ({elapsed}s){'.' * dots}")
                last_status = current_status
            
            # Small sleep to avoid hammering CPU
            await asyncio.sleep(poll_interval)
        
        # Timeout reached
        final_status = self.check_cursor_status()
        
        if final_status["has_window"]:
            # Cursor is open but maybe different workspace
            await report_status(
                f"⚠️ Cursor is open but workspace `{workspace_name}` may not be active. "
                f"Please switch to it manually.",
                True
            )
            return AgentResult(
                success=True,
                message="Cursor opened (please verify workspace)",
                data=final_status
            )
        
        await report_status(f"❌ Timeout waiting for Cursor to open", True)
        return AgentResult(
            success=False,
            message=f"Timeout after {timeout}s",
            error="Cursor did not open in time. Please try again or open manually."
        )
    
    def _send_to_composer(self, prompt: str, mode: str = "agent") -> bool:
        """
        Send prompt to Cursor via keyboard automation.
        
        Args:
            prompt: The prompt to send
            mode: One of "agent" or "chat"
                - agent: Ctrl+Shift+I - Opens new agent, auto-saves files (SAFEST)
                - chat: Ctrl+L - Chat panel, changes need Keep All to apply
            
        Returns:
            True if prompt was sent successfully
        """
        if not AUTOMATION_AVAILABLE:
            logger.error("Keyboard automation not available")
            return False
        
        try:
            # Step 1: Focus Cursor window
            logger.info("Focusing Cursor window...")
            if not WindowManager.focus_cursor_window():
                # Try to open Cursor if not running
                if not self._open_cursor_workspace():
                    return False
                time.sleep(self.CURSOR_LAUNCH_WAIT)
                if not WindowManager.focus_cursor_window():
                    logger.warning("Could not focus Cursor window, proceeding anyway...")
            
            time.sleep(self.CURSOR_FOCUS_WAIT)
            
            # Step 1.5: Close any existing panels/dialogs first (only for chat mode)
            if mode == "chat":
                logger.info("Closing any existing panels...")
                self._close_existing_panels()
                time.sleep(0.2)
            
            # Step 2: Copy prompt to clipboard
            logger.info("Copying prompt to clipboard...")
            pyperclip.copy(prompt)
            
            # Step 3: Open the appropriate mode
            # Note: On macOS, Cmd is used instead of Ctrl
            if mode == "agent":
                # Agent mode: Ctrl+Shift+I (Cmd+Shift+I on macOS) - creates new agent, auto-saves files
                # This is the SAFEST mode - you won't lose work!
                logger.info(f"Opening new Agent with {MODIFIER_KEY.title()}+Shift+I (auto-save mode)...")
                pyautogui.hotkey(MODIFIER_KEY, 'shift', 'i')
                self.session.agent_count += 1
                time.sleep(1.0)  # Agent takes longer to initialize
            else:  # chat
                # Chat mode: Ctrl+L (Cmd+L on macOS) - opens chat panel
                # Changes are proposed but NOT saved until you click Keep All
                logger.info(f"Opening Chat with {MODIFIER_KEY.title()}+L (manual accept mode)...")
                pyautogui.hotkey(MODIFIER_KEY, 'l')
            time.sleep(self.COMPOSER_OPEN_WAIT)
            
            # Step 4: Clear any existing text and paste prompt
            logger.info("Pasting prompt...")
            pyautogui.hotkey(MODIFIER_KEY, 'a')  # Select all
            time.sleep(0.1)
            pyautogui.hotkey(MODIFIER_KEY, 'v')  # Paste
            time.sleep(0.2)
            
            # Step 5: Send the prompt
            logger.info("Sending prompt...")
            # Use Ctrl+Enter (Cmd+Enter on macOS) for multi-line prompts, Enter for single line
            if '\n' in prompt:
                pyautogui.hotkey(MODIFIER_KEY, 'enter')
            else:
                pyautogui.press('enter')
            
            logger.info(f"Prompt sent to Cursor ({mode} mode)!")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send to Composer: {e}")
            return False
    
    def send_prompt(self, prompt: str, model: Optional[str] = None, mode: Optional[str] = None) -> AgentResult:
        """
        Send a prompt directly to Cursor.
        
        This:
        1. Opens Cursor with the workspace (if not open)
        2. Focuses the Cursor window
        3. Opens the appropriate mode (Agent/Chat/Inline)
        4. Pastes and sends the prompt
        5. Updates session state
        
        Works with virtual display on Windows (monitor off, pyautogui works)!
        
        MODES:
        - agent: Auto-saves files to disk (SAFEST - won't lose work)
        - chat: Changes need Keep All button to apply (more control)
        - inline: Quick edit in current file
        
        Args:
            prompt: The AI prompt to send
            model: Optional model ID (for logging only)
            mode: One of "agent", "chat", "inline" (defaults to session preference)
            
        Returns:
            AgentResult with success status
        """
        if not self.cursor_path:
            return AgentResult(
                success=False,
                message="Cursor CLI not found",
                error="Please install Cursor and ensure 'cursor' is in your PATH"
            )
        
        if not AUTOMATION_AVAILABLE:
            return AgentResult(
                success=False,
                message="Keyboard automation not available",
                error="Install dependencies: pip install pyautogui pyperclip"
            )
        
        # Determine which mode to use
        effective_mode = mode or self.session.prompt_mode or "agent"
        
        # Save prompt to file for logging
        self._save_prompt_file(prompt, model)
        
        # Snapshot current files BEFORE sending prompt (to detect changes later)
        files_before = self._get_current_files_snapshot()
        
        # Step 1: Make sure Cursor is open with workspace
        logger.info("Opening Cursor workspace...")
        if not self._open_cursor_workspace():
            return AgentResult(
                success=False,
                message="Failed to open Cursor",
                error="Could not launch Cursor IDE"
            )
        
        # Step 2: Send prompt using the selected mode
        logger.info(f"Sending prompt in {effective_mode} mode...")
        if not self._send_to_composer(prompt, mode=effective_mode):
            # Update session with error
            self.session.state = AgentState.ERROR
            self.session.last_error = "Failed to send prompt to Cursor"
            self._save_session()
            
            return AgentResult(
                success=False,
                message="Failed to send prompt to Cursor",
                error="Keyboard automation failed - is Cursor window accessible?"
            )
        
        # Step 3: Update session
        self.session.state = AgentState.PROMPT_SENT
        self.session.current_prompt = prompt
        self.session.started_at = datetime.now()
        self.session.last_activity = datetime.now()
        self.session.changes_detected = False
        self.session.last_error = ""
        self.session.files_at_prompt_start = files_before  # Track for later diff
        self._save_session()
        
        # Add to history
        self._add_to_history(prompt, "send", f"success - sent via {effective_mode} mode")
        
        # Mode-specific instructions
        if effective_mode == "agent":
            instructions = [
                "✅ Prompt sent to Cursor Agent",
                "💾 Agent mode auto-saves files (won't lose work)",
                "⏳ AI is processing...",
                "✅ Accept to confirm | ❌ Reject to undo (Ctrl+Z)"
            ]
        else:
            instructions = [
                "✅ Prompt sent to Cursor Chat",
                "⚠️ Chat mode - changes are proposed only",
                "⏳ AI is processing...",
                "✅ Accept to apply | ❌ Reject to discard (Escape)"
            ]
        
        return AgentResult(
            success=True,
            message=f"Prompt sent to Cursor ({effective_mode} mode)!",
            data={
                "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt,
                "workspace": str(self.workspace),
                "method": "keyboard_automation",
                "mode": effective_mode,
                "agent_count": self.session.agent_count,
                "auto_save": effective_mode == "agent",
                "instructions": instructions
            }
        )
    
    def capture_screenshot(self, filename: Optional[str] = None) -> Optional[Path]:
        """
        Capture a screenshot of the current screen (Cursor window).
        
        When lock overlay is active, uses Windows API to capture window directly
        (bypassing the overlay). Otherwise uses standard pyautogui screenshot.
        
        Args:
            filename: Optional filename. If None, uses timestamp.
            
        Returns:
            Path to the screenshot file, or None if failed
        """
        if not AUTOMATION_AVAILABLE:
            logger.warning("Screenshot not available - pyautogui not installed")
            return None
        
        try:
            # Create screenshots directory in .telecode
            screenshots_dir = self.telecode_dir / "screenshots"
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"cursor_{timestamp}.png"
            
            screenshot_path = screenshots_dir / filename
            
            # Check if lock overlay is active
            is_locked = False
            if IS_WINDOWS:
                try:
                    from .custom_lock import is_locked as check_lock
                    is_locked = check_lock()
                except Exception as e:
                    logger.debug(f"Could not check lock state: {e}")
            
            # If locked, use Windows API to capture window directly (bypasses overlay)
            if is_locked and IS_WINDOWS and WINDOWS_API_AVAILABLE:
                logger.info("Lock overlay detected - using Windows API window capture")
                try:
                    from PIL import Image
                    window_image = WindowCapture.capture_cursor_window()
                    
                    if window_image:
                        window_image.save(str(screenshot_path))
                        logger.info(f"Window capture screenshot saved: {screenshot_path}")
                        return screenshot_path
                    else:
                        logger.warning("Window capture failed, falling back to standard screenshot")
                        # Fall through to standard method
                except ImportError:
                    logger.warning("PIL not available for window capture, using standard method")
                    # Fall through to standard method
                except Exception as e:
                    logger.warning(f"Window capture error: {e}, falling back to standard screenshot")
                    # Fall through to standard method
            
            # Standard screenshot method (when not locked or as fallback)
            # Focus Cursor window first for better screenshot
            WindowManager.focus_cursor_window()
            time.sleep(0.3)
            
            # Take screenshot
            screenshot = pyautogui.screenshot()
            screenshot.save(str(screenshot_path))
            
            logger.info(f"Screenshot saved: {screenshot_path}")
            return screenshot_path
            
        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            return None
    
    def extract_text_from_screenshot(
        self,
        screenshot_path: Optional[Path] = None,
        filter_code_blocks: bool = True
    ) -> AgentResult:
        """
        Extract text from a screenshot using OCR.
        
        Filters out code block formatted text (file changes) and returns
        only the summary/explanation text that Cursor outputs.
        
        Args:
            screenshot_path: Path to screenshot. If None, takes a new one.
            filter_code_blocks: If True, filters out code-like text
            
        Returns:
            AgentResult with extracted text in data["text"] and data["summary"]
        """
        if not OCR_AVAILABLE:
            return AgentResult(
                success=False,
                message="OCR not available",
                error="Install pytesseract and Tesseract OCR engine. See: https://github.com/tesseract-ocr/tesseract"
            )
        
        try:
            # Take screenshot if not provided
            if screenshot_path is None:
                screenshot_path = self.capture_screenshot()
            
            if screenshot_path is None or not Path(screenshot_path).exists():
                return AgentResult(
                    success=False,
                    message="No screenshot available",
                    error="Could not capture or find screenshot"
                )
            
            # Open the image
            image = Image.open(screenshot_path)
            
            # Run OCR with optimal settings for IDE text
            # Use --psm 6 for uniform block of text, -l eng for English
            custom_config = r'--oem 3 --psm 6 -l eng'
            raw_text = pytesseract.image_to_string(image, config=custom_config)
            
            if not raw_text.strip():
                return AgentResult(
                    success=True,
                    message="No text detected in screenshot",
                    data={
                        "raw_text": "",
                        "summary": "",
                        "line_count": 0
                    }
                )
            
            # Filter and clean the text
            if filter_code_blocks:
                summary_text = self._filter_cursor_output(raw_text)
            else:
                summary_text = raw_text.strip()
            
            line_count = len(summary_text.split('\n'))
            
            logger.info(f"OCR extracted {line_count} lines of text")
            
            return AgentResult(
                success=True,
                message=f"Extracted {line_count} lines of text",
                data={
                    "raw_text": raw_text,
                    "summary": summary_text,
                    "line_count": line_count,
                    "screenshot_path": str(screenshot_path)
                }
            )
            
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return AgentResult(
                success=False,
                message="OCR extraction failed",
                error=str(e)
            )
    
    def _filter_cursor_output(self, raw_text: str) -> str:
        """
        Filter Cursor IDE output to extract only summary/explanation text.
        
        Removes:
        - Code blocks (indented code, syntax highlighted blocks)
        - File path headers (like "src/file.py")
        - Diff-style lines (starting with +, -, @@)
        - Line numbers
        - Import statements
        - Function/class definitions (standalone technical lines)
        
        Keeps:
        - Natural language explanations
        - Bullet points and numbered lists
        - Summary paragraphs from AI
        
        Args:
            raw_text: Raw OCR output
            
        Returns:
            Filtered text with only summary content
        """
        import re
        
        lines = raw_text.split('\n')
        filtered_lines = []
        in_code_block = False
        consecutive_code_lines = 0
        
        for line in lines:
            stripped = line.strip()
            
            # Skip empty lines (but track them for spacing)
            if not stripped:
                if filtered_lines and filtered_lines[-1] != '':
                    filtered_lines.append('')
                continue
            
            # Detect code block markers
            if stripped.startswith('```') or stripped.startswith('~~~'):
                in_code_block = not in_code_block
                continue
            
            # Skip if inside explicit code block
            if in_code_block:
                continue
            
            # Skip patterns that indicate code/technical content
            skip_patterns = [
                # Diff markers
                r'^[\+\-]{2,}',  # --- or +++
                r'^@@',  # @@ diff markers
                r'^\+\s',  # + added line
                r'^-\s',  # - removed line
                
                # File paths (like src/file.py, ./path/to, C:\path)
                r'^[a-zA-Z]:\\',  # Windows paths
                r'^\.?/[a-zA-Z]',  # Unix paths starting with / or ./
                r'^\w+/\w+.*\.\w{1,5}$',  # file/path.ext pattern
                r'^\w+\.\w{2,5}:?\s*$',  # filename.ext alone
                
                # Line numbers (1:, 12:, 123:)
                r'^\d+[:\|]',
                
                # Code indicators
                r'^import\s+\w',  # import statements
                r'^from\s+\w+\s+import',  # from x import y
                r'^(def|class|function|const|let|var|public|private)\s+\w',  # definitions
                r'^\s*[{}()\[\]]+\s*$',  # lone brackets
                r'^[a-zA-Z_]\w*\s*[=:]\s*[{(\[]',  # variable assignments to objects/arrays
                r'^\s*return\s',  # return statements
                r'^\s*(if|else|elif|for|while|switch|case)\s*[\(\{:]',  # control flow
                r'^\/\*|\*\/|^\/\/',  # comment markers
                r'^#\s*\w+',  # preprocessor or comment headers (not natural text)
                r'^\s*@\w+',  # decorators
                r'^<\/?[a-zA-Z]',  # HTML/XML tags
                
                # OCR artifacts / UI elements
                r'^[\u2500-\u257F]+$',  # box drawing characters
                r'^[─│┌┐└┘├┤┬┴┼]+$',  # more box drawing
                r'^\d+\s*(files?|insertions?|deletions?)',  # git stat lines
                r'^Cursor|^File|^Edit|^View|^Go|^Run|^Terminal|^Help',  # menu items
            ]
            
            should_skip = False
            for pattern in skip_patterns:
                if re.match(pattern, stripped, re.IGNORECASE):
                    should_skip = True
                    consecutive_code_lines += 1
                    break
            
            if should_skip:
                # Skip code-like lines
                continue
            
            # Check for heavily indented lines (likely code)
            leading_spaces = len(line) - len(line.lstrip())
            if leading_spaces >= 4 and not stripped.startswith(('•', '-', '*', '>', '1', '2', '3', '4', '5', '6', '7', '8', '9')):
                consecutive_code_lines += 1
                if consecutive_code_lines > 2:
                    continue
            else:
                consecutive_code_lines = 0
            
            # Check if line looks like natural language
            # Natural text has spaces, common words, punctuation
            word_count = len(stripped.split())
            has_common_words = any(word.lower() in stripped.lower() for word in 
                ['the', 'a', 'an', 'is', 'are', 'was', 'were', 'will', 'would', 'can', 'could',
                 'this', 'that', 'these', 'those', 'here', 'there', 'have', 'has', 'been',
                 'i', "i've", "i'm", 'you', 'we', 'they', 'it', 'and', 'or', 'but', 'so',
                 'because', 'if', 'when', 'while', 'for', 'to', 'of', 'in', 'on', 'at',
                 'created', 'added', 'updated', 'changed', 'modified', 'fixed', 'removed',
                 'now', 'should', 'need', 'make', 'made', 'also', 'with', 'from',
                 'file', 'function', 'method', 'class', 'component', 'module'])
            
            # Likely natural language if:
            # - Has 3+ words
            # - Contains common English words
            # - Ends with punctuation
            # - Starts with bullet/number
            is_likely_text = (
                word_count >= 3 and has_common_words or
                stripped.endswith(('.', '!', '?', ':')) or
                stripped.startswith(('•', '-', '*', '>', '1.', '2.', '3.', '4.', '5.', 
                                     '6.', '7.', '8.', '9.', '✓', '✅', '❌', '⚠️', '📝'))
            )
            
            if is_likely_text or (word_count >= 4 and not stripped.endswith(('(', '{', '[', ';', ','))):
                filtered_lines.append(stripped)
        
        # Clean up result
        result = '\n'.join(filtered_lines)
        
        # Remove consecutive empty lines
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        return result.strip()
    
    def capture_and_extract_text(self) -> AgentResult:
        """
        Capture a screenshot and extract summary text via OCR.
        
        Convenience method that combines capture_screenshot and extract_text_from_screenshot.
        
        Returns:
            AgentResult with screenshot path and extracted summary text
        """
        # Capture screenshot
        screenshot_path = self.capture_screenshot()
        
        if not screenshot_path:
            return AgentResult(
                success=False,
                message="Failed to capture screenshot",
                error="Screenshot capture failed"
            )
        
        # Extract text
        ocr_result = self.extract_text_from_screenshot(screenshot_path, filter_code_blocks=True)
        
        if not ocr_result.success:
            # Return partial success with screenshot but no text
            return AgentResult(
                success=True,
                message="Screenshot captured but OCR failed",
                data={
                    "screenshot_path": str(screenshot_path),
                    "summary": "",
                    "ocr_error": ocr_result.error
                }
            )
        
        # Combine results
        return AgentResult(
            success=True,
            message=f"Captured screenshot and extracted {ocr_result.data.get('line_count', 0)} lines",
            data={
                "screenshot_path": str(screenshot_path),
                "summary": ocr_result.data.get("summary", ""),
                "raw_text": ocr_result.data.get("raw_text", ""),
                "line_count": ocr_result.data.get("line_count", 0)
            }
        )
    
    async def send_prompt_and_wait(
        self,
        prompt: str,
        status_callback: Optional[callable] = None,
        model: Optional[str] = None,
        mode: Optional[str] = None,
        timeout: float = 300.0,
        poll_interval: float = 3.0,
        stable_threshold: int = 10,
        min_processing_time: float = 15.0
    ) -> AgentResult:
        """
        Send a prompt to Cursor and wait for AI to complete processing.
        
        This async method:
        1. Sends the prompt to Cursor
        2. Polls for file changes to detect when AI is done
        3. Reports status via callback
        4. Takes a screenshot when complete
        
        IMPORTANT: AI completion detection is based on stable file changes.
        We require a minimum processing time AND stable file count before
        declaring completion to avoid false positives.
        
        Args:
            prompt: The AI prompt to send
            status_callback: Async callback(message: str, is_complete: bool, screenshot_path: Optional[Path])
            model: Optional model ID
            mode: One of "agent", "chat"
            timeout: Max time to wait for completion (seconds) - default 5 mins
            poll_interval: Time between status checks (seconds)
            stable_threshold: Number of stable polls before considering done (10 = 30s of stability)
            min_processing_time: Minimum seconds before allowing completion detection
            
        Returns:
            AgentResult with completion status and screenshot path
        """
        async def report_status(message: str, is_complete: bool = False, screenshot_path: Optional[Path] = None):
            """Helper to call the status callback if provided.
            
            For non-complete updates, we use create_task to avoid blocking the event loop.
            This allows button callbacks to be processed while AI is running.
            For complete updates, we await to ensure they're sent before returning.
            """
            if status_callback:
                try:
                    if is_complete:
                        # Critical updates: await to ensure they're sent
                        await status_callback(message, is_complete, screenshot_path)
                    else:
                        # Non-critical updates: fire-and-forget to avoid blocking event loop
                        # This allows button callbacks to be processed during AI execution
                        asyncio.create_task(status_callback(message, is_complete, screenshot_path))
                except Exception as e:
                    logger.warning(f"Status callback error: {e}")
        
        # Step 1: Send the prompt
        logger.info(f"[AI_PROMPT] Sending prompt to Cursor: {prompt[:100]}...")
        await report_status("📤 Sending prompt to Cursor...")
        
        result = self.send_prompt(prompt, model=model, mode=mode)
        
        if not result.success:
            logger.error(f"[AI_PROMPT] Failed to send prompt: {result.message}")
            await report_status(f"❌ Failed: {result.message}", True, None)
            return result
        
        effective_mode = result.data.get("mode", "agent") if result.data else "agent"
        # Capture agent_id for this prompt (agent_count - 1, since count was incremented after opening)
        # Only relevant for agent mode
        agent_id = None
        if effective_mode == "agent" and result.data:
            agent_count = result.data.get("agent_count", 0)
            if agent_count > 0:
                agent_id = agent_count - 1  # 0-indexed: first agent = 0, second = 1, etc.
                logger.info(f"[AI_PROMPT] Agent ID for this prompt: {agent_id} (agent_count={agent_count})")
        
        logger.info(f"[AI_PROMPT] Prompt sent successfully. Mode: {effective_mode}. Waiting for AI to process...")
        await report_status(f"🤖 Cursor AI is processing... ({effective_mode} mode)")
        
        # Update state to PROCESSING
        self.session.state = AgentState.PROCESSING
        self._save_session()
        
        # Step 2: Capture baseline state BEFORE polling (to track changes from this prompt only)
        # This ensures we only count changes made by this specific prompt, not cumulative changes
        baseline_files = set()
        baseline_diff_size = 0
        
        try:
            # Capture baseline git status and diff size
            async def run_git_status_baseline():
                return await asyncio.to_thread(
                    subprocess.run,
                    ["git", "status", "--porcelain"],
                    cwd=str(self.workspace),
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            
            async def run_git_diff_baseline():
                return await asyncio.to_thread(
                    subprocess.run,
                    ["git", "diff", "--shortstat"],
                    cwd=str(self.workspace),
                    capture_output=True,
                    text=True,
                    timeout=10,
                    encoding='utf-8',
                    errors='replace'
                )
            
            git_status_baseline, git_diff_baseline = await asyncio.gather(
                run_git_status_baseline(),
                run_git_diff_baseline(),
                return_exceptions=True
            )
            
            # Parse baseline files
            if not isinstance(git_status_baseline, Exception) and git_status_baseline.returncode == 0:
                if git_status_baseline.stdout.strip():
                    for line in git_status_baseline.stdout.strip().split("\n"):
                        if line.strip():
                            parts = line.split(maxsplit=1)
                            if len(parts) >= 2:
                                baseline_files.add(parts[1].strip())
            
            # Parse baseline diff size
            if not isinstance(git_diff_baseline, Exception) and git_diff_baseline.returncode == 0:
                if git_diff_baseline.stdout.strip():
                    import re
                    diff_output = git_diff_baseline.stdout.strip()
                    insertions = re.search(r'(\d+) insertion', diff_output)
                    deletions = re.search(r'(\d+) deletion', diff_output)
                    if insertions:
                        baseline_diff_size += int(insertions.group(1))
                    if deletions:
                        baseline_diff_size += int(deletions.group(1))
            
            # Also check baseline untracked file sizes
            async def get_file_size_baseline(file_path_str):
                try:
                    file_path = self.workspace / file_path_str.strip('"')
                    def check_and_stat():
                        if file_path.exists() and file_path.is_file():
                            return file_path.stat().st_size
                        return 0
                    return await asyncio.to_thread(check_and_stat)
                except Exception:
                    return 0
            
            file_size_tasks = [get_file_size_baseline(f) for f in baseline_files]
            file_sizes = await asyncio.gather(*file_size_tasks, return_exceptions=True)
            for size in file_sizes:
                if isinstance(size, int):
                    baseline_diff_size += size // 50  # Rough line estimate
            
            logger.info(f"[AI_PROMPT] Baseline captured: {len(baseline_files)} files, ~{baseline_diff_size} lines")
        except Exception as e:
            logger.warning(f"[AI_PROMPT] Failed to capture baseline state: {e}, using empty baseline")
            # Continue with empty baseline - will show all changes (fallback behavior)
        
        # Step 3: Poll for completion
        start_time = time.time()
        stable_count = 0
        last_files = set()
        last_diff_size = 0         # Track total lines changed (insertions + deletions)
        last_screenshot_time = 0   # Track when we last sent a screenshot
        screenshot_count = 0       # Track total screenshots sent
        sent_initial_screenshot = False  # Track if we sent the first quick screenshot
        
        # Screenshot intervals: every 60s for first 10 min, then every 300s (5 min)
        INITIAL_SCREENSHOT_TIME = 8        # Send first screenshot at 8 seconds
        SCREENSHOT_INTERVAL_INITIAL = 60   # 1 minute for first 10 min
        SCREENSHOT_INTERVAL_LATER = 300    # 5 minutes after 10 min
        INITIAL_PERIOD = 600               # First 10 minutes
        
        while time.time() - start_time < timeout:
            elapsed = int(time.time() - start_time)
            
            # Check for file changes via git - track CONTENT changes, not just file list
            try:
                # Helper function to run subprocess in thread pool (non-blocking)
                async def run_git_status():
                    return await asyncio.to_thread(
                        subprocess.run,
                        ["git", "status", "--porcelain"],
                        cwd=str(self.workspace),
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                
                async def run_git_diff():
                    return await asyncio.to_thread(
                        subprocess.run,
                        ["git", "diff", "--shortstat"],
                        cwd=str(self.workspace),
                        capture_output=True,
                        text=True,
                        timeout=10,
                        encoding='utf-8',
                        errors='replace'
                    )
                
                # Run git commands in parallel (non-blocking)
                git_status, git_diff = await asyncio.gather(
                    run_git_status(),
                    run_git_diff(),
                    return_exceptions=True
                )
                
                # Handle exceptions
                if isinstance(git_status, Exception):
                    logger.warning(f"[AI_PROMPT] Git status error: {git_status}")
                    git_status = type('obj', (object,), {'returncode': 1, 'stdout': ''})()
                if isinstance(git_diff, Exception):
                    logger.warning(f"[AI_PROMPT] Git diff error: {git_diff}")
                    git_diff = type('obj', (object,), {'returncode': 1, 'stdout': ''})()
                
                current_files = set()
                if git_status.returncode == 0 and git_status.stdout.strip():
                    for line in git_status.stdout.strip().split("\n"):
                        if line.strip():
                            parts = line.split(maxsplit=1)
                            if len(parts) >= 2:
                                current_files.add(parts[1].strip())
                
                current_count = len(current_files)
                
                # Parse diff size (e.g., "1 file changed, 500 insertions(+), 10 deletions(-)")
                current_diff_size = 0
                if git_diff.returncode == 0 and git_diff.stdout.strip():
                    diff_output = git_diff.stdout.strip()
                    # Extract numbers for insertions and deletions
                    import re
                    insertions = re.search(r'(\d+) insertion', diff_output)
                    deletions = re.search(r'(\d+) deletion', diff_output)
                    if insertions:
                        current_diff_size += int(insertions.group(1))
                    if deletions:
                        current_diff_size += int(deletions.group(1))
                
                # Also check untracked file sizes (for new files not yet staged)
                # Run file stat operations in thread pool to avoid blocking
                async def get_file_size(file_path_str):
                    try:
                        file_path = self.workspace / file_path_str.strip('"')
                        # Check existence and get size in thread pool
                        def check_and_stat():
                            if file_path.exists() and file_path.is_file():
                                return file_path.stat().st_size
                            return 0
                        return await asyncio.to_thread(check_and_stat)
                    except Exception:
                        pass
                    return 0
                
                file_size_tasks = [get_file_size(f) for f in current_files]
                file_sizes = await asyncio.gather(*file_size_tasks, return_exceptions=True)
                for size in file_sizes:
                    if isinstance(size, int):
                        current_diff_size += size // 50  # Rough line estimate
                
                # Calculate DELTA changes from this prompt only (current - baseline)
                # This ensures we only show changes made by this specific prompt
                # Count all files that are different from baseline (new, modified, or deleted)
                # For files: count files that are in current but not in baseline (new/modified)
                # Note: We can't easily detect deletions without more complex logic, so we focus on additions/modifications
                files_changed_from_prompt = current_files - baseline_files
                files_changed_count = len(files_changed_from_prompt)
                lines_changed_count = max(0, current_diff_size - baseline_diff_size)
                
                # Check if CONTENT changed (diff size grew) OR new files appeared
                content_changed = (current_diff_size != last_diff_size) or (current_files != last_files)
                
                if content_changed:
                    # Content is still changing - AI is actively working
                    if current_files != last_files:
                        new_files = current_files - last_files
                        if new_files:
                            logger.info(f"[AI_PROMPT] New files: {new_files}")
                    if current_diff_size != last_diff_size:
                        logger.info(f"[AI_PROMPT] Diff size changed: {last_diff_size} -> {current_diff_size} lines")
                    
                    await report_status(f"📝 AI working... {files_changed_count} files, ~{lines_changed_count} lines ({elapsed}s)")
                    last_files = current_files
                    last_diff_size = current_diff_size
                    stable_count = 0
                else:
                    # No content changes - increment stable count
                    stable_count += 1
                    if stable_count % 5 == 0:  # Log every 5 stable polls
                        logger.info(f"[AI_PROMPT] Content stable: {stable_count}/{stable_threshold} polls, {current_diff_size} lines, {elapsed}s")
                
                # Calculate stability time in seconds
                stability_time = stable_count * poll_interval
                
                # If we have changes and CONTENT is stable for threshold polls AND minimum time passed
                # We need BOTH: enough stable polls AND minimum processing time
                # Use delta values (changes from this prompt only) for completion check
                if (stable_count >= stable_threshold and 
                    (files_changed_count > 0 or lines_changed_count > 0) and 
                    elapsed >= min_processing_time):
                    # AI appears to be done! Content hasn't changed for stability_time seconds
                    logger.info(f"[AI_PROMPT] ✅ AI COMPLETED! Content stable for {stability_time}s")
                    logger.info(f"[AI_PROMPT]    Files: {files_changed_count} (from this prompt), Lines: ~{lines_changed_count}, Elapsed: {elapsed}s")
                    self.session.state = AgentState.CHANGES_PENDING
                    self.session.changes_detected = True
                    # Store only files changed from this prompt
                    self.session.pending_files = list(files_changed_from_prompt) if files_changed_from_prompt else list(current_files)
                    self._save_session()
                    
                    # Take screenshot (non-blocking)
                    screenshot_path = await asyncio.to_thread(self.capture_screenshot)
                    
                    await report_status(
                        f"✅ Cursor AI completed! ({files_changed_count} files, ~{lines_changed_count} lines in {elapsed}s)",
                        True,
                        screenshot_path
                    )
                    
                    return AgentResult(
                        success=True,
                        message="AI completed with changes!",
                        data={
                            "status": "completed",
                            "files_changed": files_changed_count,  # Only files from this prompt
                            "lines_changed": lines_changed_count,  # Only lines from this prompt
                            "files": list(files_changed_from_prompt) if files_changed_from_prompt else list(current_files),
                            "elapsed_seconds": elapsed,
                            "screenshot": str(screenshot_path) if screenshot_path else None,
                            "mode": effective_mode,
                            "agent_id": agent_id  # Include agent_id for button routing
                        }
                    )
                elif stable_count >= stable_threshold and files_changed_count > 0:
                    # Files are stable but haven't hit min processing time yet
                    remaining = int(min_processing_time - elapsed)
                    if remaining > 0:
                        await report_status(f"📝 AI working... {files_changed_count} files ({elapsed}s, verifying...)")
                
                # If no changes after a long while, AI might be waiting or stuck
                # Only trigger this after 120s with absolutely no file changes
                # This avoids false "waiting" state when AI is just thinking
                if elapsed > 120 and current_count == 0 and stable_count >= 30:
                    logger.info(f"[AI_PROMPT] No file changes after {elapsed}s - AI may be waiting for input")
                    
                    # Take screenshot to show current state (non-blocking)
                    screenshot_path = await asyncio.to_thread(self.capture_screenshot)
                    
                    self.session.state = AgentState.AWAITING_CHANGES
                    self._save_session()
                    
                    await report_status(
                        f"⏳ Cursor AI may be waiting for input... ({elapsed}s)\nNo file changes detected. Check Cursor directly.",
                        True,
                        screenshot_path
                    )
                    
                    return AgentResult(
                        success=True,
                        message="AI may be waiting or still processing",
                        data={
                            "status": "waiting",
                            "files_changed": 0,
                            "elapsed_seconds": elapsed,
                            "screenshot": str(screenshot_path) if screenshot_path else None,
                            "mode": effective_mode,
                            "agent_id": agent_id  # Include agent_id for button routing
                        }
                    )
                
                # Send initial screenshot at 10 seconds to confirm AI is working
                if not sent_initial_screenshot and elapsed >= INITIAL_SCREENSHOT_TIME:
                    sent_initial_screenshot = True
                    screenshot_count += 1
                    last_screenshot_time = elapsed
                    
                    initial_screenshot = await asyncio.to_thread(self.capture_screenshot)
                    files_info = f"{files_changed_count} files changed" if files_changed_count > 0 else "No file changes yet"
                    
                    logger.info(f"[AI_PROMPT] Initial screenshot at {elapsed}s - {files_info}")
                    
                    await report_status(
                        f"📸 **AI Started!** ({elapsed}s)\n\n"
                        f"✅ Cursor received your prompt\n"
                        f"🔄 AI is now working...\n"
                        f"📁 {files_info}\n"
                        f"⏱️ Updates every 1 min",
                        False,
                        initial_screenshot
                    )
                
                # Periodic screenshot updates while AI is working
                # Every 1 minute for first 10 min, then every 5 min after that
                elif elapsed > INITIAL_SCREENSHOT_TIME:
                    # Determine current screenshot interval
                    if elapsed <= INITIAL_PERIOD:
                        current_interval = SCREENSHOT_INTERVAL_INITIAL
                    else:
                        current_interval = SCREENSHOT_INTERVAL_LATER
                    
                    # Check if it's time for a screenshot update
                    time_since_last_screenshot = elapsed - last_screenshot_time
                    if time_since_last_screenshot >= current_interval:
                        screenshot_count += 1
                        last_screenshot_time = elapsed
                        
                        # Take screenshot to show current state (non-blocking)
                        progress_screenshot = await asyncio.to_thread(self.capture_screenshot)
                        
                        # Build status message (show only changes from this prompt)
                        files_info = f"{files_changed_count} files changed" if files_changed_count > 0 else "No file changes yet"
                        if files_changed_count > 0 and lines_changed_count > 0:
                            files_info += f", ~{lines_changed_count} lines"
                        interval_info = "1 min updates" if elapsed <= INITIAL_PERIOD else "5 min updates"
                        
                        logger.info(f"[AI_PROMPT] Progress screenshot #{screenshot_count} at {elapsed}s - {files_info}")
                        
                        await report_status(
                            f"📸 **Progress Update** ({elapsed}s)\n\n"
                            f"🔄 AI still working...\n"
                            f"📁 {files_info}\n"
                            f"⏱️ {interval_info}",
                            False,  # Not complete yet
                            progress_screenshot
                        )
                    
            except Exception as e:
                logger.warning(f"[AI_PROMPT] Poll error at {elapsed}s: {e}")
                # Continue polling even if there's an error
            
            await asyncio.sleep(poll_interval)
        
        # Timeout reached - calculate final delta values
        timeout_files_changed = len(last_files - baseline_files)
        timeout_lines_changed = max(0, last_diff_size - baseline_diff_size)
        
        logger.info(f"[AI_PROMPT] Timeout after {int(timeout)}s. Files changed from this prompt: {timeout_files_changed}")
        self.session.state = AgentState.IDLE
        self._save_session()
        
        # Take final screenshot (non-blocking)
        screenshot_path = await asyncio.to_thread(self.capture_screenshot)
        
        timeout_info = f" ({timeout_files_changed} files, ~{timeout_lines_changed} lines)" if timeout_files_changed > 0 else ""
        await report_status(
            f"⏱️ Timeout after {int(timeout)}s - AI may still be working{timeout_info}. Check Cursor directly.",
            True,
            screenshot_path
        )
        
        return AgentResult(
            success=True,
            message="Timeout reached - check Cursor manually",
            data={
                "status": "timeout",
                "files_changed": timeout_files_changed,  # Only files from this prompt
                "lines_changed": timeout_lines_changed,  # Only lines from this prompt
                "files": list(last_files - baseline_files) if (last_files - baseline_files) else list(last_files),
                "elapsed_seconds": int(timeout),
                "screenshot": str(screenshot_path) if screenshot_path else None,
                "mode": effective_mode,
                "agent_id": agent_id  # Include agent_id for button routing
            }
        )
    
    def check_changes(self, latest_only: bool = True) -> AgentResult:
        """
        Check for uncommitted changes in the workspace.
        
        Args:
            latest_only: If True, only show files changed since last prompt
        
        Returns:
            AgentResult with change information
        """
        try:
            # Run git status
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return AgentResult(
                    success=False,
                    message="Git status failed",
                    error=result.stderr
                )
            
            # Parse changed files
            all_changed_files = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    status = line[:2]
                    filename = line[3:]
                    
                    # Skip .telecode files
                    if ".telecode" in filename:
                        continue
                    
                    all_changed_files.append({
                        "status": status.strip(),
                        "file": filename
                    })
            
            # Filter to only files changed since last prompt (new files)
            changed_files = all_changed_files
            new_files_from_prompt = []
            
            if latest_only and self.session.files_at_prompt_start:
                files_before = set(self.session.files_at_prompt_start)
                for f in all_changed_files:
                    if f["file"] not in files_before:
                        new_files_from_prompt.append(f)
                # Show new files from latest prompt, but include all for status
                if new_files_from_prompt:
                    changed_files = new_files_from_prompt
            
            has_changes = len(changed_files) > 0
            
            # Update session
            self.session.changes_detected = has_changes
            self.session.pending_files = [f["file"] for f in changed_files]
            if has_changes:
                self.session.state = AgentState.CHANGES_PENDING
            self.session.last_activity = datetime.now()
            self._save_session()
            
            # Get diff stats for only the changed files
            diff_stat = ""
            if changed_files:
                file_list = [f["file"] for f in changed_files]
                diff_result = subprocess.run(
                    ["git", "diff", "--stat", "--"] + file_list,
                    cwd=str(self.workspace),
                    capture_output=True,
                    text=True,
                    timeout=30,
                    encoding='utf-8',
                    errors='replace'
                )
                diff_stat = diff_result.stdout.strip() if diff_result.returncode == 0 else ""
            
            # Also get untracked files stats
            untracked_info = ""
            untracked_files = [f for f in changed_files if f["status"] in ["?", "??", "A"]]
            if untracked_files:
                untracked_info = f"\n📄 New files: {len(untracked_files)}"
            
            return AgentResult(
                success=True,
                message=f"{'Changes detected!' if has_changes else 'No changes yet'}",
                data={
                    "has_changes": has_changes,
                    "file_count": len(changed_files),
                    "files": changed_files,
                    "all_files_count": len(all_changed_files),
                    "diff_stat": diff_stat + untracked_info,
                    "latest_only": latest_only and bool(self.session.files_at_prompt_start)
                }
            )
            
        except subprocess.TimeoutExpired:
            return AgentResult(
                success=False,
                message="Git command timed out",
                error="Operation took too long"
            )
        except Exception as e:
            return AgentResult(
                success=False,
                message="Failed to check changes",
                error=str(e)
            )
    
    def get_diff(self, full: bool = False, latest_only: bool = True) -> AgentResult:
        """
        Get the current diff.
        
        Args:
            full: If True, get full diff content. If False, get stat summary.
            latest_only: If True, only show diff for files changed since last prompt.
        
        Returns:
            AgentResult with diff data
        """
        try:
            args = ["git", "diff"]
            if not full:
                args.append("--stat")
            
            # If latest_only, only diff files changed since prompt start
            if latest_only and self.session.files_at_prompt_start:
                current_files = self._get_current_files_snapshot()
                files_before = set(self.session.files_at_prompt_start)
                new_files = [f for f in current_files if f not in files_before]
                
                if new_files:
                    args.append("--")
                    args.extend(new_files)
            
            result = subprocess.run(
                args,
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=60,
                encoding='utf-8',
                errors='replace'
            )
            
            diff_content = result.stdout.strip()
            
            # Also include info about new untracked files
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            new_files_info = ""
            if status_result.returncode == 0:
                untracked = []
                for line in status_result.stdout.strip().split("\n"):
                    if line.startswith("?? ") or line.startswith("A "):
                        filename = line[3:].strip()
                        if ".telecode" not in filename:
                            untracked.append(filename)
                
                if untracked:
                    new_files_info = "\n\n📄 New files:\n" + "\n".join(f"  + {f}" for f in untracked[:10])
                    if len(untracked) > 10:
                        new_files_info += f"\n  ... and {len(untracked) - 10} more"
            
            return AgentResult(
                success=True,
                message="Diff retrieved",
                data={
                    "diff": diff_content + new_files_info,
                    "full": full,
                    "latest_only": latest_only
                }
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                message="Failed to get diff",
                error=str(e)
            )
    
    def get_diff_summary(self) -> AgentResult:
        """
        Get a concise text summary of changes from the latest prompt.
        
        This is designed to be sent via Telegram when "Check Changes" is pressed.
        
        Returns:
            AgentResult with a formatted text summary
        """
        try:
            # Get the diff stat
            diff_result = self.get_diff(full=False, latest_only=True)
            
            if not diff_result.success:
                return diff_result
            
            diff_stat = diff_result.data.get("diff", "") if diff_result.data else ""
            
            # Get changed files list
            check = self.check_changes(latest_only=True)
            
            if not check.success:
                return check
            
            files = check.data.get("files", []) if check.data else []
            file_count = len(files)
            
            # Build summary text
            summary_parts = []
            
            if file_count > 0:
                summary_parts.append(f"📊 **{file_count} file(s) changed from latest prompt:**\n")
                
                # List files with their status
                for f in files[:10]:
                    status_icon = "📝" if f["status"] in ["M", "MM"] else "➕" if f["status"] in ["?", "??", "A"] else "📄"
                    summary_parts.append(f"{status_icon} `{f['file']}`")
                
                if file_count > 10:
                    summary_parts.append(f"\n_...and {file_count - 10} more files_")
                
                # Add diff stat
                if diff_stat:
                    summary_parts.append(f"\n```\n{diff_stat}\n```")
            else:
                summary_parts.append("✅ No new changes detected from the latest prompt.")
                summary_parts.append("\n_Wait for AI to finish processing, then check again._")
            
            return AgentResult(
                success=True,
                message="Summary generated",
                data={
                    "summary": "\n".join(summary_parts),
                    "file_count": file_count,
                    "has_changes": file_count > 0
                }
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                message="Failed to generate summary",
                error=str(e)
            )
    
    def accept_changes_via_cursor(self) -> AgentResult:
        """
        Accept all changes by triggering Cursor's "Accept" action via automation.
        
        Uses Ctrl+Enter to accept AI-generated changes in Cursor's diff view.
        This is the keyboard shortcut for accepting/keeping proposed changes.
        
        Returns:
            AgentResult with success status
        """
        if not AUTOMATION_AVAILABLE:
            return AgentResult(
                success=False,
                message="Keyboard automation not available",
                error="Install dependencies: pip install pyautogui pyperclip"
            )
        
        try:
            # Focus Cursor window
            logger.info("Focusing Cursor for Accept...")
            if not WindowManager.focus_cursor_window():
                return AgentResult(
                    success=False,
                    message="Could not focus Cursor",
                    error="Cursor window not found"
                )
            
            time.sleep(0.3)
            
            # Cursor uses Ctrl+Enter (Cmd+Enter on macOS) to accept changes in diff view
            # This accepts all proposed changes from the AI
            shortcut_display = f"{MODIFIER_KEY.title()}+Enter"
            logger.info(f"Sending Accept shortcut ({shortcut_display})...")
            pyautogui.hotkey(MODIFIER_KEY, 'enter')
            time.sleep(0.5)
            
            # Update session
            self.session.state = AgentState.IDLE
            self.session.changes_detected = False
            self.session.pending_files = []
            self.session.files_at_prompt_start = []  # Reset for next prompt
            self._save_session()
            
            self._add_to_history(self.session.current_prompt, "accept", f"accepted via Cursor {shortcut_display}")
            
            return AgentResult(
                success=True,
                message="Changes accepted in Cursor!",
                data={
                    "method": "cursor_automation",
                    "action": "accept",
                    "shortcut": "Ctrl+Enter"
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to Accept: {e}")
            return AgentResult(
                success=False,
                message="Failed to Accept",
                error=str(e)
            )
    
    def accept_changes(self, message: Optional[str] = None, use_cursor_button: bool = True) -> AgentResult:
        """
        Accept all changes.
        
        Args:
            message: Optional commit message (only used if use_cursor_button=False)
            use_cursor_button: If True, use Cursor's Keep All button. If False, use git commit.
        
        Returns:
            AgentResult with success status
        """
        # If using Cursor button, delegate to that method
        if use_cursor_button and AUTOMATION_AVAILABLE:
            return self.accept_changes_via_cursor()
        
        # Fallback: use git add + commit
        check = self.check_changes(latest_only=False)
        if not check.success:
            return check
        
        if not check.data.get("has_changes"):
            # Check if there are untracked new files that git status might miss
            try:
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=str(self.workspace),
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if not result.stdout.strip():
                    return AgentResult(
                        success=False,
                        message="No changes to accept",
                        error="Working directory is clean"
                    )
            except:
                pass
        
        try:
            # Stage all changes (including new/untracked files)
            add_result = subprocess.run(
                ["git", "add", "-A"],  # -A stages all including new files
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if add_result.returncode != 0:
                return AgentResult(
                    success=False,
                    message="Failed to stage changes",
                    error=add_result.stderr
                )
            
            # Check if there's anything staged now
            staged_result = subprocess.run(
                ["git", "diff", "--cached", "--stat"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if not staged_result.stdout.strip():
                return AgentResult(
                    success=False,
                    message="No changes to commit",
                    error="Nothing staged for commit"
                )
            
            # Commit
            commit_msg = message or f"TeleCode AI: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if commit_result.returncode != 0:
                return AgentResult(
                    success=False,
                    message="Failed to commit",
                    error=commit_result.stderr
                )
            
            # Update session
            self.session.state = AgentState.IDLE
            self.session.changes_detected = False
            self.session.pending_files = []
            self.session.files_at_prompt_start = []
            self._save_session()
            
            self._add_to_history(self.session.current_prompt, "accept", commit_msg)
            
            return AgentResult(
                success=True,
                message="Changes accepted and committed!",
                data={
                    "commit_message": commit_msg,
                    "files_committed": check.data.get("file_count", 0) if check.data else 0,
                    "output": commit_result.stdout.strip()
                }
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                message="Failed to accept changes",
                error=str(e)
            )
    
    def revert_changes_via_cursor(self) -> AgentResult:
        """
        Reject/Undo changes using Cursor's UI automation.
        
        Uses Escape key to dismiss/reject proposed changes in both agent and chat modes.
        This is the standard way to reject changes in Cursor's interface.
        
        Returns:
            AgentResult with success status
        """
        if not AUTOMATION_AVAILABLE:
            return AgentResult(
                success=False,
                message="Automation not available",
                error="Install pyautogui and pyperclip"
            )
        
        try:
            # Focus Cursor window first
            logger.info("[REJECT] Focusing Cursor window...")
            if not WindowManager.focus_cursor_window():
                logger.error("[REJECT] Could not focus Cursor window")
                return AgentResult(
                    success=False,
                    message="Could not focus Cursor",
                    error="Cursor window not found"
                )
            
            # Wait for focus to take effect
            time.sleep(0.5)
            logger.info("[REJECT] Cursor window focused")
            
            current_mode = self.session.prompt_mode or "agent"
            logger.info(f"[REJECT] Current mode: {current_mode}")
            
            # Both chat and agent mode: Press Escape to dismiss/reject proposed changes
            # Escape is the standard way to reject/cancel changes in Cursor
            logger.info("[REJECT] Pressing Escape to reject changes...")
            pyautogui.press('escape')
            time.sleep(0.3)
            pyautogui.press('escape')  # Press twice to be sure
            time.sleep(0.2)
            shortcut_used = "Escape"
            
            logger.info(f"[REJECT] Completed: {shortcut_used}")
            
            # Update session
            self.session.state = AgentState.IDLE
            self.session.changes_detected = False
            self._save_session()
            
            self._add_to_history(self.session.current_prompt, "reject", f"rejected via {shortcut_used}")
            
            return AgentResult(
                success=True,
                message=f"Changes rejected in Cursor ({shortcut_used})!",
                data={
                    "method": "cursor_automation",
                    "mode": current_mode,
                    "shortcut": shortcut_used
                }
            )
            
        except Exception as e:
            logger.error(f"[REJECT] Failed: {e}")
            return AgentResult(
                success=False,
                message="Failed to Reject",
                error=str(e)
            )
    
    def approve_run(self) -> AgentResult:
        """
        Approve a pending terminal command that Cursor's AI wants to run.
        
        When Cursor's agent wants to execute a script or command, it shows a 
        "Run" button that requires user approval. This method simulates clicking
        that button by pressing Enter (which typically confirms the action).
        
        Returns:
            AgentResult with success status
        """
        if not AUTOMATION_AVAILABLE:
            return AgentResult(
                success=False,
                message="Automation not available",
                error="Install pyautogui and pyperclip"
            )
        
        try:
            # Focus Cursor window
            logger.info("Focusing Cursor to approve Run...")
            if not WindowManager.focus_cursor_window():
                return AgentResult(
                    success=False,
                    message="Could not focus Cursor",
                    error="Cursor window not found"
                )
            
            time.sleep(0.3)
            
            # Press Enter to approve the pending run command
            # In Cursor, the Run button is typically focused, so Enter confirms it
            logger.info("Approving run command (Enter)...")
            pyautogui.press('enter')
            time.sleep(0.2)
            
            self._add_to_history("", "approve_run", "approved terminal command")
            
            return AgentResult(
                success=True,
                message="✅ Run command approved!",
                data={
                    "action": "approve_run",
                    "method": "enter_key"
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to approve run: {e}")
            return AgentResult(
                success=False,
                message="Failed to approve run",
                error=str(e)
            )
    
    def stop_generation(self, agent_id: Optional[int] = None) -> AgentResult:
        """
        Stop the current AI generation in Cursor.
        
        Uses Ctrl+Shift+Backspace (Cmd+Shift+Backspace on macOS) to stop
        the AI while it's generating/working.
        
        Args:
            agent_id: Optional agent tab ID to target. If provided, navigates
                     to that specific agent tab before stopping.
                     If None, uses current active tab (backward compatible).
        
        Returns:
            AgentResult with success status
        """
        if not AUTOMATION_AVAILABLE:
            return AgentResult(
                success=False,
                message="Automation not available",
                error="Install pyautogui and pyperclip"
            )
        
        try:
            # Navigate to specific agent tab if agent_id is provided
            if agent_id is not None:
                logger.info(f"[STOP] Targeting agent tab {agent_id + 1} (agent_id={agent_id})...")
                if not self._navigate_to_agent_tab(agent_id):
                    # Fallback: still try to stop on current tab
                    logger.warning(f"[STOP] Failed to navigate to agent {agent_id}, stopping on current tab")
                    if not WindowManager.focus_cursor_window():
                        return AgentResult(
                            success=False,
                            message="Could not focus Cursor",
                            error="Cursor window not found"
                        )
                    time.sleep(0.5)
                else:
                    # Navigation succeeded, already focused
                    time.sleep(0.2)  # Small delay after navigation
            else:
                # Backward compatible: focus window normally
                logger.info("[STOP] Focusing Cursor window...")
                if not WindowManager.focus_cursor_window():
                    return AgentResult(
                        success=False,
                        message="Could not focus Cursor",
                        error="Cursor window not found"
                    )
                time.sleep(0.5)
            
            # Press Ctrl+Shift+Backspace to stop generation
            shortcut_display = f"{MODIFIER_KEY.title()}+Shift+Backspace"
            logger.info(f"[STOP] Pressing {shortcut_display} to stop generation...")
            pyautogui.hotkey(MODIFIER_KEY, 'shift', 'backspace')
            time.sleep(0.3)
            
            # Update session state
            self.session.state = AgentState.IDLE
            self._save_session()
            
            action_desc = f"stopped via {shortcut_display} (agent_id={agent_id})" if agent_id is not None else f"stopped via {shortcut_display}"
            self._add_to_history("stop", "stop_generation", action_desc)
            
            return AgentResult(
                success=True,
                message=f"Stopped via {shortcut_display}",
                data={
                    "action": "stop",
                    "method": shortcut_display,
                    "agent_id": agent_id
                }
            )
            
        except Exception as e:
            logger.error(f"[STOP] Failed: {e}")
            return AgentResult(
                success=False,
                message="Failed to stop generation",
                error=str(e)
            )
    
    def cancel_action(self) -> AgentResult:
        """
        Cancel a pending action in Cursor (run command, web search, etc).
        
        When Cursor's agent is asking for approval (run a script, web search, etc),
        this cancels/rejects that action by pressing Escape.
        
        Returns:
            AgentResult with success status
        """
        if not AUTOMATION_AVAILABLE:
            return AgentResult(
                success=False,
                message="Automation not available",
                error="Install pyautogui and pyperclip"
            )
        
        try:
            # Focus Cursor window
            logger.info("[CANCEL] Focusing Cursor window...")
            if not WindowManager.focus_cursor_window():
                return AgentResult(
                    success=False,
                    message="Could not focus Cursor",
                    error="Cursor window not found"
                )
            
            time.sleep(0.5)
            
            # Press Escape to cancel the pending action
            logger.info("[CANCEL] Pressing Escape to cancel action...")
            pyautogui.press('escape')
            time.sleep(0.2)
            
            self._add_to_history("", "cancel_action", "cancelled pending action")
            
            return AgentResult(
                success=True,
                message="❌ Action cancelled!",
                data={
                    "action": "cancel",
                    "method": "escape_key"
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to cancel action: {e}")
            return AgentResult(
                success=False,
                message="Failed to cancel action",
                error=str(e)
            )
    
    def approve_web_search(self) -> AgentResult:
        """
        Approve a pending web search that Cursor's AI wants to perform.
        
        When Cursor's agent wants to do a web search for context, it may ask
        for user approval. This approves it by pressing Enter.
        
        Returns:
            AgentResult with success status
        """
        if not AUTOMATION_AVAILABLE:
            return AgentResult(
                success=False,
                message="Automation not available",
                error="Install pyautogui and pyperclip"
            )
        
        try:
            # Focus Cursor window
            logger.info("Focusing Cursor to approve web search...")
            if not WindowManager.focus_cursor_window():
                return AgentResult(
                    success=False,
                    message="Could not focus Cursor",
                    error="Cursor window not found"
                )
            
            time.sleep(0.3)
            
            # Press Enter to approve the web search
            logger.info("Approving web search (Enter)...")
            pyautogui.press('enter')
            time.sleep(0.2)
            
            self._add_to_history("", "approve_web_search", "approved web search")
            
            return AgentResult(
                success=True,
                message="🌐 Web search approved!",
                data={
                    "action": "approve_web_search",
                    "method": "enter_key"
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to approve web search: {e}")
            return AgentResult(
                success=False,
                message="Failed to approve web search",
                error=str(e)
            )
    
    def send_continue(self, agent_id: Optional[int] = None) -> AgentResult:
        """
        Press the Continue button in Cursor's AI agent.
        
        When the AI is waiting for approval or showing a Continue button,
        this presses Enter to activate it.
        
        Args:
            agent_id: Optional agent tab ID to target. If provided, navigates
                     to that specific agent tab before pressing Continue.
                     If None, uses current active tab (backward compatible).
        
        Returns:
            AgentResult with success status
        """
        if not AUTOMATION_AVAILABLE:
            return AgentResult(
                success=False,
                message="Automation not available",
                error="Install pyautogui and pyperclip"
            )
        
        try:
            # Navigate to specific agent tab if agent_id is provided
            if agent_id is not None:
                logger.info(f"[CONTINUE] Targeting agent tab {agent_id + 1} (agent_id={agent_id})...")
                if not self._navigate_to_agent_tab(agent_id):
                    # Fallback: still try to continue on current tab
                    logger.warning(f"[CONTINUE] Failed to navigate to agent {agent_id}, continuing on current tab")
                    if not WindowManager.focus_cursor_window():
                        return AgentResult(
                            success=False,
                            message="Could not focus Cursor",
                            error="Cursor window not found"
                        )
                    time.sleep(0.5)
                else:
                    # Navigation succeeded, already focused
                    time.sleep(0.2)  # Small delay after navigation
            else:
                # Backward compatible: focus window normally
                logger.info("[CONTINUE] Focusing Cursor window...")
                if not WindowManager.focus_cursor_window():
                    return AgentResult(
                        success=False,
                        message="Could not focus Cursor",
                        error="Cursor window not found"
                    )
                time.sleep(0.5)
            
            # Press Enter to click the Continue button
            logger.info("[CONTINUE] Pressing Enter to activate Continue button...")
            pyautogui.press('enter')
            time.sleep(0.3)
            
            action_desc = f"pressed Enter for Continue (agent_id={agent_id})" if agent_id is not None else "pressed Enter for Continue"
            self._add_to_history("continue", "continue_button", action_desc)
            
            return AgentResult(
                success=True,
                message="➡️ Continue button pressed!",
                data={
                    "action": "continue",
                    "method": "enter_key",
                    "agent_id": agent_id
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to send continue: {e}")
            return AgentResult(
                success=False,
                message="Failed to send continue",
                error=str(e)
            )
    
    def revert_changes(self, use_git: bool = True) -> AgentResult:
        """
        Revert all uncommitted changes.
        
        Args:
            use_git: If True, use git restore. If False, use Cursor automation.
        
        For Agent mode: Files are saved to disk, so git restore is effective.
        For Chat mode: Can use Cursor's Escape to reject proposed changes.
        
        Returns:
            AgentResult with success status
        """
        # If not using git, delegate to Cursor automation
        if not use_git and AUTOMATION_AVAILABLE:
            return self.revert_changes_via_cursor()
        
        check = self.check_changes(latest_only=False)
        if not check.success:
            return check
        
        if not check.data.get("has_changes"):
            return AgentResult(
                success=True,
                message="No changes to revert",
                data={"files_reverted": 0}
            )
        
        files_to_revert = check.data.get("file_count", 0)
        
        try:
            # Restore tracked files
            subprocess.run(
                ["git", "restore", "."],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Clean untracked files (except .telecode)
            subprocess.run(
                ["git", "clean", "-fd", "--exclude=.telecode"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Update session
            self.session.state = AgentState.IDLE
            self.session.changes_detected = False
            self.session.pending_files = []
            self.session.files_at_prompt_start = []
            self._save_session()
            
            self._add_to_history(self.session.current_prompt, "revert", f"reverted {files_to_revert} files via git")
            
            return AgentResult(
                success=True,
                message="All changes reverted!",
                data={"files_reverted": files_to_revert}
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                message="Failed to revert changes",
                error=str(e)
            )
    
    def set_prompt_mode(self, mode: str) -> AgentResult:
        """
        Set the preferred mode for sending prompts.
        
        Args:
            mode: One of "agent", "chat", "inline"
            
        Returns:
            AgentResult with success status
        """
        valid_modes = ["agent", "chat"]
        if mode not in valid_modes:
            return AgentResult(
                success=False,
                message="Invalid mode",
                error=f"Mode must be one of: {', '.join(valid_modes)}"
            )
        
        self.session.prompt_mode = mode
        self._save_session()
        
        mode_descriptions = {
            "agent": "🤖 Agent mode - Auto-saves files (safest, won't lose work)",
            "chat": "💬 Chat mode - Changes need Accept button to apply"
        }
        
        return AgentResult(
            success=True,
            message=f"Mode set to: {mode}",
            data={
                "mode": mode,
                "description": mode_descriptions.get(mode, ""),
                "auto_save": mode == "agent"
            }
        )
    
    def get_prompt_mode(self) -> str:
        """Get the current prompt mode."""
        return self.session.prompt_mode or "agent"
    
    def continue_session(self, prompt: str, model: Optional[str] = None, mode: Optional[str] = None) -> AgentResult:
        """Continue with a follow-up prompt."""
        # In agent mode, changes are auto-saved so we don't need to check
        # In chat mode, warn if there are pending proposed changes
        current_mode = mode or self.session.prompt_mode or "agent"
        
        if current_mode != "agent":
            # Check for pending changes first
            check = self.check_changes()
            
            if check.data and check.data.get("has_changes"):
                return AgentResult(
                    success=False,
                    message="Pending changes detected!",
                    error=(
                        f"You have {check.data.get('file_count', 0)} uncommitted files.\n"
                        "Use Accept to apply or Reject to discard first."
                    )
                )
        
        return self.send_prompt(prompt, model, mode=mode)
    
    def stop_session(self) -> AgentResult:
        """Stop/clear the current AI session."""
        # Clear prompt file
        prompt_file = self.telecode_dir / self.PROMPT_FILE
        if prompt_file.exists():
            try:
                prompt_file.unlink()
            except:
                pass
        
        old_state = self.session.state
        self.session.state = AgentState.IDLE
        self.session.current_prompt = ""
        self.session.last_error = ""
        self._save_session()
        
        self._add_to_history("", "stop", "session cleared")
        
        return AgentResult(
            success=True,
            message="AI session stopped",
            data={
                "previous_state": old_state.value,
                "current_state": "idle"
            }
        )
    
    def get_status(self) -> AgentResult:
        """Get current agent status."""
        check = self.check_changes(latest_only=True)
        
        return AgentResult(
            success=True,
            message="Agent status",
            data={
                "state": self.session.state.value,
                "workspace": str(self.workspace),
                "has_prompt": bool(self.session.current_prompt),
                "prompt_preview": self.session.current_prompt[:100] if self.session.current_prompt else None,
                "started_at": self.session.started_at.isoformat() if self.session.started_at else None,
                "changes_detected": self.session.changes_detected,
                "pending_files": self.session.pending_files,
                "file_count": len(self.session.pending_files),
                "automation_available": AUTOMATION_AVAILABLE,
                "last_error": self.session.last_error,
                "agent_count": self.session.agent_count,
                "files_at_start": len(self.session.files_at_prompt_start)
            }
        )
    
    def cleanup_agents(self, max_agents: int = 5) -> AgentResult:
        """
        Close oldest agent tabs if we have too many open.
        
        Args:
            max_agents: Maximum number of agent tabs to keep
            
        Returns:
            AgentResult with cleanup status
        """
        if not AUTOMATION_AVAILABLE:
            return AgentResult(
                success=False,
                message="Automation not available",
                error="Install pyautogui and pyperclip"
            )
        
        if self.session.agent_count <= max_agents:
            return AgentResult(
                success=True,
                message=f"No cleanup needed ({self.session.agent_count} agents)",
                data={"agents_closed": 0, "agent_count": self.session.agent_count}
            )
        
        agents_to_close = self.session.agent_count - max_agents
        
        if self._cleanup_old_agents(max_agents):
            return AgentResult(
                success=True,
                message=f"Closed {agents_to_close} old agent tab(s)",
                data={"agents_closed": agents_to_close, "agent_count": self.session.agent_count}
            )
        else:
            return AgentResult(
                success=False,
                message="Failed to cleanup agents",
                error="Automation failed"
        )


def get_agent_for_workspace(workspace: Path) -> CursorAgentBridge:
    """Factory function to get an agent bridge for a workspace."""
    return CursorAgentBridge(workspace)


# ============================================
# Virtual Display Support (Linux Headless Mode)
# ============================================

class VirtualDisplayManager:
    """
    Manages virtual display for headless GUI automation on Linux.
    
    Uses pyvirtualdisplay (Xvfb wrapper) to create a virtual X server
    that allows pyautogui to work even when no physical display is attached.
    
    Similar to Windows Virtual Display - keeps GUI applications running without
    a physical monitor.
    """
    
    _instance = None
    _display = None
    _is_running = False
    
    @classmethod
    def get_instance(cls) -> 'VirtualDisplayManager':
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = VirtualDisplayManager()
        return cls._instance
    
    @staticmethod
    def is_available() -> bool:
        """Check if virtual display is available."""
        return VIRTUAL_DISPLAY_AVAILABLE and IS_LINUX
    
    @classmethod
    def start(cls, width: int = 1920, height: int = 1080, color_depth: int = 24) -> bool:
        """
        Start a virtual display.
        
        Args:
            width: Display width in pixels
            height: Display height in pixels
            color_depth: Color depth (16, 24, or 32)
            
        Returns:
            True if started successfully
        """
        if not cls.is_available():
            logger.warning("Virtual display not available (Linux + pyvirtualdisplay required)")
            return False
        
        if cls._is_running:
            logger.info("Virtual display already running")
            return True
        
        try:
            from pyvirtualdisplay import Display
            
            cls._display = Display(
                visible=False,
                size=(width, height),
                color_depth=color_depth
            )
            cls._display.start()
            cls._is_running = True
            
            logger.info(f"Virtual display started: {width}x{height}x{color_depth}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start virtual display: {e}")
            return False
    
    @classmethod
    def stop(cls) -> bool:
        """
        Stop the virtual display.
        
        Returns:
            True if stopped successfully
        """
        if not cls._is_running or cls._display is None:
            return True
        
        try:
            cls._display.stop()
            cls._display = None
            cls._is_running = False
            logger.info("Virtual display stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop virtual display: {e}")
            return False
    
    @classmethod
    def is_running(cls) -> bool:
        """Check if virtual display is currently running."""
        return cls._is_running
    
    @classmethod
    def get_display_info(cls) -> Optional[Dict[str, Any]]:
        """
        Get information about the virtual display.
        
        Returns:
            Dictionary with display info or None if not running
        """
        if not cls._is_running or cls._display is None:
            return None
        
        try:
            return {
                "running": True,
                "display": cls._display.display,
                "size": cls._display.size,
                "backend": "Xvfb",
                "platform": "Linux"
            }
        except Exception:
            return {"running": True, "platform": "Linux"}


def start_virtual_display() -> bool:
    """
    Start virtual display for headless operation.
    
    This is the Linux equivalent of Windows Virtual Display - allows GUI automation
    to work without a physical monitor.
    
    Returns:
        True if started successfully (or already running/not needed)
    """
    if IS_WINDOWS:
        # Windows uses Virtual Display (turn off monitor), not Xvfb
        logger.info("Windows detected - use Virtual Display for headless operation")
        return True
    
    if IS_MACOS:
        # macOS has limited headless support, virtual display not available
        logger.warning("macOS detected - virtual display not supported")
        logger.warning("Consider using a virtual display adapter or VNC")
        return False
    
    if IS_LINUX:
        return VirtualDisplayManager.start()
    
    return False


def stop_virtual_display() -> bool:
    """Stop the virtual display if running."""
    return VirtualDisplayManager.stop()


def get_platform_info() -> Dict[str, Any]:
    """
    Get information about the current platform and its capabilities.
    
    Returns:
        Dictionary with platform information
    """
    info = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "python_version": platform.python_version(),
        "automation_available": AUTOMATION_AVAILABLE,
        "modifier_key": MODIFIER_KEY,
    }
    
    if IS_WINDOWS:
        info.update({
            "headless_method": "Virtual Display",
            "windows_api_available": WINDOWS_API_AVAILABLE,
            "headless_available": True,
        })
    elif IS_MACOS:
        info.update({
            "headless_method": "Virtual Display Adapter / VNC",
            "headless_available": False,
            "note": "macOS requires hardware/software display adapter for true headless",
        })
    elif IS_LINUX:
        info.update({
            "headless_method": "Xvfb (pyvirtualdisplay)",
            "virtual_display_available": VIRTUAL_DISPLAY_AVAILABLE,
            "xdotool_available": XDOTOOL_AVAILABLE,
            "wmctrl_available": WMCTRL_AVAILABLE,
            "headless_available": VIRTUAL_DISPLAY_AVAILABLE,
        })
    
    return info
