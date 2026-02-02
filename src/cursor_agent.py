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


@dataclass
class AgentResult:
    """Result of an agent operation."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class WindowManager:
    """
    Cross-platform window management for Cursor IDE.
    
    Handles finding, focusing, and interacting with Cursor windows.
    Works with TSCON locked sessions on Windows.
    """
    
    @staticmethod
    def find_cursor_window() -> Optional[int]:
        """
        Find the Cursor IDE window handle.
        
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
                            found_hwnd = hwnd
                            return False  # Stop enumeration
                
                return True  # Continue enumeration
            
            user32.EnumWindows(EnumWindowsProc(enum_callback), 0)
            
            return found_hwnd
            
        except Exception as e:
            logger.warning(f"Failed to find Cursor window: {e}")
            return None
    
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
                    last_error=data.get("last_error", "")
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
                "last_error": self.session.last_error
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
    
    def _send_to_composer(self, prompt: str, use_chat: bool = True) -> bool:
        """
        Send prompt to Cursor Composer via keyboard automation.
        
        Args:
            prompt: The prompt to send
            use_chat: If True, use Ctrl+L (chat). If False, use Ctrl+I (inline)
            
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
            
            # Step 2: Copy prompt to clipboard
            logger.info("Copying prompt to clipboard...")
            pyperclip.copy(prompt)
            
            # Step 3: Open Composer
            # Ctrl+L = Chat mode (recommended for prompts)
            # Ctrl+I = Inline/Composer mode
            hotkey = 'l' if use_chat else 'i'
            logger.info(f"Opening Composer with Ctrl+{hotkey.upper()}...")
            pyautogui.hotkey('ctrl', hotkey)
            time.sleep(self.COMPOSER_OPEN_WAIT)
            
            # Step 4: Clear any existing text and paste prompt
            logger.info("Pasting prompt...")
            pyautogui.hotkey('ctrl', 'a')  # Select all
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'v')  # Paste
            time.sleep(0.2)
            
            # Step 5: Send the prompt (Enter or Ctrl+Enter)
            logger.info("Sending prompt...")
            # Use Ctrl+Enter for multi-line prompts, Enter for single line
            if '\n' in prompt:
                pyautogui.hotkey('ctrl', 'enter')
            else:
                pyautogui.press('enter')
            
            logger.info("Prompt sent to Cursor Composer!")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send to Composer: {e}")
            return False
    
    def send_prompt(self, prompt: str, model: Optional[str] = None) -> AgentResult:
        """
        Send a prompt directly to Cursor Composer.
        
        This:
        1. Opens Cursor with the workspace (if not open)
        2. Focuses the Cursor window
        3. Opens Composer (Ctrl+L for chat)
        4. Pastes and sends the prompt
        5. Updates session state
        
        Works with TSCON locked sessions on Windows!
        
        Args:
            prompt: The AI prompt to send
            model: Optional model ID (for logging only)
            
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
        
        # Save prompt to file for logging
        self._save_prompt_file(prompt, model)
        
        # Step 1: Make sure Cursor is open with workspace
        logger.info("Opening Cursor workspace...")
        if not self._open_cursor_workspace():
            return AgentResult(
                success=False,
                message="Failed to open Cursor",
                error="Could not launch Cursor IDE"
            )
        
        # Step 2: Send prompt to Composer
        logger.info("Sending prompt to Composer...")
        if not self._send_to_composer(prompt, use_chat=True):
            # Update session with error
            self.session.state = AgentState.ERROR
            self.session.last_error = "Failed to send prompt to Composer"
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
        self._save_session()
        
        # Add to history
        self._add_to_history(prompt, "send", "success - sent to Composer")
        
        return AgentResult(
            success=True,
            message="Prompt sent to Cursor!",
            data={
                "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt,
                "workspace": str(self.workspace),
                "method": "keyboard_automation",
                "composer": "chat",
                "instructions": [
                    "✅ Prompt sent to Cursor Composer",
                    "⏳ AI is processing...",
                    "📊 Use /ai status to check for changes",
                    "✅ Use /ai accept to commit changes",
                    "🗑️ Use /ai revert to discard changes"
                ]
            }
        )
    
    def check_changes(self) -> AgentResult:
        """
        Check for uncommitted changes in the workspace.
        
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
            changed_files = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    status = line[:2]
                    filename = line[3:]
                    
                    # Skip .telecode files
                    if ".telecode" in filename:
                        continue
                    
                    changed_files.append({
                        "status": status.strip(),
                        "file": filename
                    })
            
            has_changes = len(changed_files) > 0
            
            # Update session
            self.session.changes_detected = has_changes
            self.session.pending_files = [f["file"] for f in changed_files]
            if has_changes:
                self.session.state = AgentState.CHANGES_PENDING
            self.session.last_activity = datetime.now()
            self._save_session()
            
            # Get diff stats
            diff_result = subprocess.run(
                ["git", "diff", "--stat"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return AgentResult(
                success=True,
                message=f"{'Changes detected!' if has_changes else 'No changes yet'}",
                data={
                    "has_changes": has_changes,
                    "file_count": len(changed_files),
                    "files": changed_files,
                    "diff_stat": diff_result.stdout.strip() if diff_result.returncode == 0 else ""
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
    
    def get_diff(self, full: bool = False) -> AgentResult:
        """Get the current diff."""
        try:
            args = ["git", "diff"]
            if not full:
                args.append("--stat")
            
            result = subprocess.run(
                args,
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return AgentResult(
                success=True,
                message="Diff retrieved",
                data={
                    "diff": result.stdout.strip(),
                    "full": full
                }
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                message="Failed to get diff",
                error=str(e)
            )
    
    def accept_changes(self, message: Optional[str] = None) -> AgentResult:
        """Accept all changes: git add + commit."""
        check = self.check_changes()
        if not check.success:
            return check
        
        if not check.data.get("has_changes"):
            return AgentResult(
                success=False,
                message="No changes to accept",
                error="Working directory is clean"
            )
        
        try:
            # Stage all changes
            add_result = subprocess.run(
                ["git", "add", "."],
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
            self._save_session()
            
            self._add_to_history(self.session.current_prompt, "accept", commit_msg)
            
            return AgentResult(
                success=True,
                message="Changes accepted and committed!",
                data={
                    "commit_message": commit_msg,
                    "files_committed": check.data.get("file_count", 0),
                    "output": commit_result.stdout.strip()
                }
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                message="Failed to accept changes",
                error=str(e)
            )
    
    def revert_changes(self) -> AgentResult:
        """Revert all uncommitted changes."""
        check = self.check_changes()
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
            self._save_session()
            
            self._add_to_history(self.session.current_prompt, "revert", f"reverted {files_to_revert} files")
            
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
    
    def continue_session(self, prompt: str, model: Optional[str] = None) -> AgentResult:
        """Continue with a follow-up prompt."""
        # Check for pending changes first
        check = self.check_changes()
        
        if check.data and check.data.get("has_changes"):
            return AgentResult(
                success=False,
                message="Pending changes detected!",
                error=(
                    f"You have {check.data.get('file_count', 0)} uncommitted files.\n"
                    "Use `/ai accept` to commit or `/ai revert` to discard first."
                )
            )
        
        return self.send_prompt(prompt, model)
    
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
        check = self.check_changes()
        
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
                "last_error": self.session.last_error
            }
        )


def get_agent_for_workspace(workspace: Path) -> CursorAgentBridge:
    """Factory function to get an agent bridge for a workspace."""
    return CursorAgentBridge(workspace)
