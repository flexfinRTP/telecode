"""
============================================
TeleCode v0.1 - Cursor Agent Bridge
============================================
Automated integration layer for Cursor IDE AI control.

This module SENDS prompts directly to Cursor Composer via
keyboard automation. Works with TSCON locked sessions because
the Windows session remains active.

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
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("telecode.cursor_agent")

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

# Windows-specific imports for window management
if sys.platform == "win32":
    try:
        import ctypes
        from ctypes import wintypes
        WINDOWS_API_AVAILABLE = True
    except ImportError:
        WINDOWS_API_AVAILABLE = False
else:
    WINDOWS_API_AVAILABLE = False


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


class WindowManager:
    """
    Cross-platform window management for Cursor IDE.
    
    Handles finding, focusing, and interacting with Cursor windows.
    Works with TSCON locked sessions on Windows.
    """
    
    @staticmethod
    def find_cursor_window(workspace_name: Optional[str] = None) -> Optional[int]:
        """
        Find the Cursor IDE window handle.
        
        Args:
            workspace_name: Optional workspace name to match in window title
        
        Returns:
            Window handle (HWND on Windows) or None if not found
        """
        if sys.platform != "win32" or not WINDOWS_API_AVAILABLE:
            return None
        
        try:
            user32 = ctypes.windll.user32
            
            # Callback to enumerate windows
            EnumWindowsProc = ctypes.WINFUNCTYPE(
                wintypes.BOOL, 
                wintypes.HWND, 
                wintypes.LPARAM
            )
            
            found_hwnd = None
            
            def enum_callback(hwnd, lparam):
                nonlocal found_hwnd
                
                # Get window title
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buffer, length + 1)
                    title = buffer.value
                    
                    # Check if it's a Cursor window
                    # Cursor windows typically have "Cursor" in the title or end with "- Cursor"
                    if "Cursor" in title or title.endswith("- Cursor"):
                        # Check if window is visible
                        if user32.IsWindowVisible(hwnd):
                            # If workspace_name is provided, check if it matches
                            if workspace_name:
                                if workspace_name.lower() in title.lower():
                                    found_hwnd = hwnd
                                    return False  # Stop enumeration
                            else:
                                found_hwnd = hwnd
                                return False  # Stop enumeration
                
                return True  # Continue enumeration
            
            user32.EnumWindows(EnumWindowsProc(enum_callback), 0)
            
            return found_hwnd
            
        except Exception as e:
            logger.warning(f"Failed to find Cursor window: {e}")
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
            # Check if any Cursor process is running
            if not WindowManager.is_cursor_running():
                return CursorStatus.NOT_RUNNING
            
            # Check if Cursor window exists
            hwnd = WindowManager.find_cursor_window(workspace_name)
            if hwnd:
                return CursorStatus.READY
            elif WindowManager.find_cursor_window():
                # Cursor is open but maybe different workspace
                return CursorStatus.RUNNING
            else:
                # Process running but no window yet
                return CursorStatus.STARTING
                
        except Exception as e:
            logger.warning(f"Error checking Cursor status: {e}")
            return CursorStatus.ERROR
    
    @staticmethod
    def focus_cursor_window(hwnd: Optional[int] = None) -> bool:
        """
        Focus the Cursor window.
        
        Args:
            hwnd: Window handle (will search if not provided)
            
        Returns:
            True if window was focused successfully
        """
        if sys.platform != "win32" or not WINDOWS_API_AVAILABLE:
            # On non-Windows, just hope Cursor is focused
            return True
        
        try:
            user32 = ctypes.windll.user32
            
            if hwnd is None:
                hwnd = WindowManager.find_cursor_window()
            
            if hwnd is None:
                logger.warning("Cursor window not found")
                return False
            
            # Restore window if minimized
            SW_RESTORE = 9
            user32.ShowWindow(hwnd, SW_RESTORE)
            
            # Bring to foreground
            # First, attach to the thread of the foreground window
            foreground = user32.GetForegroundWindow()
            current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
            foreground_thread = user32.GetWindowThreadProcessId(foreground, None)
            
            # Attach input threads
            user32.AttachThreadInput(current_thread, foreground_thread, True)
            
            # Set foreground
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
            
            # Detach threads
            user32.AttachThreadInput(current_thread, foreground_thread, False)
            
            # Give it time to focus
            time.sleep(0.3)
            
            return True
            
        except Exception as e:
            logger.warning(f"Failed to focus Cursor window: {e}")
            return False
    
    @staticmethod
    def is_cursor_running() -> bool:
        """Check if Cursor is running."""
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
    Works with TSCON locked sessions on Windows.
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
                # Ctrl+1 to go to first tab, then Ctrl+W to close it
                pyautogui.hotkey('ctrl', '1')
                time.sleep(0.2)
                pyautogui.hotkey('ctrl', 'w')
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
            """Helper to call the status callback if provided."""
            if status_callback:
                try:
                    await status_callback(message, is_complete)
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
            if mode == "agent":
                # Agent mode: Ctrl+Shift+I - creates new agent, auto-saves files
                # This is the SAFEST mode - you won't lose work!
                logger.info("Opening new Agent with Ctrl+Shift+I (auto-save mode)...")
                pyautogui.hotkey('ctrl', 'shift', 'i')
                self.session.agent_count += 1
                time.sleep(1.0)  # Agent takes longer to initialize
            else:  # chat
                # Chat mode: Ctrl+L - opens chat panel
                # Changes are proposed but NOT saved until you click Keep All
                logger.info("Opening Chat with Ctrl+L (manual accept mode)...")
                pyautogui.hotkey('ctrl', 'l')
            time.sleep(self.COMPOSER_OPEN_WAIT)
            
            # Step 4: Clear any existing text and paste prompt
            logger.info("Pasting prompt...")
            pyautogui.hotkey('ctrl', 'a')  # Select all
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'v')  # Paste
            time.sleep(0.2)
            
            # Step 5: Send the prompt
            logger.info("Sending prompt...")
            # Use Ctrl+Enter for multi-line prompts, Enter for single line
            if '\n' in prompt:
                pyautogui.hotkey('ctrl', 'enter')
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
        
        Works with TSCON locked sessions on Windows!
        
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
    
    async def send_prompt_and_wait(
        self,
        prompt: str,
        status_callback: Optional[callable] = None,
        model: Optional[str] = None,
        mode: Optional[str] = None,
        timeout: float = 90.0,
        poll_interval: float = 2.0,
        stable_threshold: int = 3
    ) -> AgentResult:
        """
        Send a prompt to Cursor and wait for AI to complete processing.
        
        This async method:
        1. Sends the prompt to Cursor
        2. Polls for file changes to detect when AI is done
        3. Reports status via callback
        4. Takes a screenshot when complete
        
        Args:
            prompt: The AI prompt to send
            status_callback: Async callback(message: str, is_complete: bool, screenshot_path: Optional[Path])
            model: Optional model ID
            mode: One of "agent", "chat"
            timeout: Max time to wait for completion (seconds)
            poll_interval: Time between status checks (seconds)
            stable_threshold: Number of stable polls before considering done
            
        Returns:
            AgentResult with completion status and screenshot path
        """
        async def report_status(message: str, is_complete: bool = False, screenshot_path: Optional[Path] = None):
            """Helper to call the status callback if provided."""
            if status_callback:
                try:
                    await status_callback(message, is_complete, screenshot_path)
                except Exception as e:
                    logger.warning(f"Status callback error: {e}")
        
        # Step 1: Send the prompt
        await report_status("📤 Sending prompt to Cursor...")
        
        result = self.send_prompt(prompt, model=model, mode=mode)
        
        if not result.success:
            await report_status(f"❌ Failed: {result.message}", True, None)
            return result
        
        effective_mode = result.data.get("mode", "agent") if result.data else "agent"
        await report_status(f"🤖 Cursor AI is processing... ({effective_mode} mode)")
        
        # Update state to PROCESSING
        self.session.state = AgentState.PROCESSING
        self._save_session()
        
        # Step 2: Poll for completion
        start_time = time.time()
        last_file_count = 0
        stable_count = 0
        last_files = set()
        
        while time.time() - start_time < timeout:
            elapsed = int(time.time() - start_time)
            
            # Check for file changes via git
            try:
                git_result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=str(self.workspace),
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                current_files = set()
                if git_result.returncode == 0 and git_result.stdout.strip():
                    for line in git_result.stdout.strip().split("\n"):
                        if line.strip():
                            # Parse git status line (e.g., " M file.py" or "?? newfile.py")
                            parts = line.split(maxsplit=1)
                            if len(parts) >= 2:
                                current_files.add(parts[1].strip())
                
                current_count = len(current_files)
                
                # Check if files changed since last poll
                if current_files != last_files:
                    # New changes detected - AI is actively working
                    new_files = current_files - last_files
                    if new_files:
                        await report_status(f"📝 AI working... {current_count} files changed ({elapsed}s)")
                    last_files = current_files
                    last_file_count = current_count
                    stable_count = 0
                else:
                    # No new changes
                    stable_count += 1
                
                # If we have changes and they're stable for threshold polls, consider done
                if stable_count >= stable_threshold and current_count > 0:
                    # AI appears to be done!
                    self.session.state = AgentState.CHANGES_PENDING
                    self.session.changes_detected = True
                    self.session.pending_files = list(current_files)
                    self._save_session()
                    
                    # Take screenshot
                    screenshot_path = self.capture_screenshot()
                    
                    await report_status(
                        f"✅ Cursor AI completed! ({current_count} files changed in {elapsed}s)",
                        True,
                        screenshot_path
                    )
                    
                    return AgentResult(
                        success=True,
                        message="AI completed with changes!",
                        data={
                            "status": "completed",
                            "files_changed": current_count,
                            "files": list(current_files),
                            "elapsed_seconds": elapsed,
                            "screenshot": str(screenshot_path) if screenshot_path else None,
                            "mode": effective_mode
                        }
                    )
                
                # If no changes after a while, AI might be waiting or stuck
                if elapsed > 20 and current_count == 0 and stable_count >= 5:
                    # Take screenshot to show current state
                    screenshot_path = self.capture_screenshot()
                    
                    self.session.state = AgentState.AWAITING_CHANGES
                    self._save_session()
                    
                    await report_status(
                        f"⏳ Cursor AI may be waiting for input or still thinking... ({elapsed}s)",
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
                            "mode": effective_mode
                        }
                    )
                    
            except subprocess.TimeoutExpired:
                await report_status(f"⏳ Still processing... ({elapsed}s)")
            except Exception as e:
                logger.warning(f"Poll error: {e}")
            
            await asyncio.sleep(poll_interval)
        
        # Timeout reached
        self.session.state = AgentState.IDLE
        self._save_session()
        
        # Take final screenshot
        screenshot_path = self.capture_screenshot()
        
        await report_status(
            f"⏱️ Timeout after {int(timeout)}s - AI may still be working",
            True,
            screenshot_path
        )
        
        return AgentResult(
            success=True,
            message="Timeout reached - check Cursor manually",
            data={
                "status": "timeout",
                "files_changed": len(last_files),
                "files": list(last_files),
                "elapsed_seconds": int(timeout),
                "screenshot": str(screenshot_path) if screenshot_path else None,
                "mode": effective_mode
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
            
            # Cursor uses Ctrl+Enter to accept changes in diff view
            # This accepts all proposed changes from the AI
            logger.info("Sending Accept shortcut (Ctrl+Enter)...")
            pyautogui.hotkey('ctrl', 'enter')
            time.sleep(0.5)
            
            # Update session
            self.session.state = AgentState.IDLE
            self.session.changes_detected = False
            self.session.pending_files = []
            self.session.files_at_prompt_start = []  # Reset for next prompt
            self._save_session()
            
            self._add_to_history(self.session.current_prompt, "accept", "accepted via Cursor Ctrl+Enter")
            
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
        
        Uses Ctrl+Backspace to reject AI-generated changes in Cursor's diff view.
        For chat mode, Escape is used to dismiss the proposed changes.
        
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
            logger.info("Focusing Cursor for Reject...")
            if not WindowManager.focus_cursor_window():
                return AgentResult(
                    success=False,
                    message="Could not focus Cursor",
                    error="Cursor window not found"
                )
            
            time.sleep(0.3)
            
            current_mode = self.session.prompt_mode or "agent"
            
            if current_mode == "chat":
                # Chat mode: Press Escape to dismiss/reject proposed changes
                logger.info("Rejecting proposed changes (Escape)...")
                pyautogui.press('escape')
                time.sleep(0.2)
                pyautogui.press('escape')  # Press twice to be sure
                shortcut_used = "Escape"
            else:
                # Agent mode: Use Ctrl+Backspace to reject changes
                # This rejects all proposed changes in the diff view
                logger.info("Rejecting changes with Ctrl+Backspace...")
                pyautogui.hotkey('ctrl', 'backspace')
                time.sleep(0.3)
                shortcut_used = "Ctrl+Backspace"
            
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
            logger.error(f"Failed to Reject: {e}")
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
            logger.info("Focusing Cursor to cancel action...")
            if not WindowManager.focus_cursor_window():
                return AgentResult(
                    success=False,
                    message="Could not focus Cursor",
                    error="Cursor window not found"
                )
            
            time.sleep(0.3)
            
            # Press Escape to cancel the pending action
            logger.info("Cancelling action (Escape)...")
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
    
    def send_continue(self) -> AgentResult:
        """
        Send a continue signal to Cursor's AI agent.
        
        When the AI pauses or needs a nudge to continue, this sends
        a simple "continue" message to keep it going.
        
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
            logger.info("Focusing Cursor to send continue...")
            if not WindowManager.focus_cursor_window():
                return AgentResult(
                    success=False,
                    message="Could not focus Cursor",
                    error="Cursor window not found"
                )
            
            time.sleep(0.3)
            
            # Type "continue" and press Enter
            logger.info("Sending continue message...")
            pyperclip.copy("continue")
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.1)
            pyautogui.press('enter')
            time.sleep(0.2)
            
            self._add_to_history("continue", "continue_signal", "sent continue to agent")
            
            return AgentResult(
                success=True,
                message="▶️ Continue sent to AI!",
                data={
                    "action": "continue",
                    "method": "text_input"
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
