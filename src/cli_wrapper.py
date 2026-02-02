"""
============================================
TeleCode v0.1 - CLI Wrapper Module
============================================
Handles subprocess execution for:
- Git commands (status, diff, push, pull, etc.)
- Cursor CLI/Agent (AI code generation)

IMPORTANT: All commands are sandboxed via SecuritySentinel.
This module ONLY executes pre-validated commands.

SECURITY: Uses PromptGuard for AI prompt injection defense.
============================================
"""

import os
import subprocess
import logging
import shutil
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

from .security import SecuritySentinel, SecurityError
from .prompt_guard import get_prompt_guard, ThreatLevel

logger = logging.getLogger("telecode.cli")


@dataclass
class CommandResult:
    """Result of a CLI command execution."""
    success: bool
    stdout: str
    stderr: str
    return_code: int
    command: str  # The command that was executed (for logging)


class CLIWrapper:
    """
    Secure CLI wrapper for Git and Cursor operations.
    
    All commands are:
    1. Validated against the security whitelist
    2. Executed within the sandbox directory
    3. Logged for audit trail
    """
    
    # Maximum output size to prevent memory issues
    MAX_OUTPUT_SIZE = 50000  # 50KB
    
    # Command timeout (seconds)
    DEFAULT_TIMEOUT = 120  # 2 minutes
    AI_TIMEOUT = 600       # 10 minutes for AI operations
    
    def __init__(self, sentinel: SecuritySentinel):
        """
        Initialize CLI wrapper with security sentinel.
        
        Args:
            sentinel: SecuritySentinel instance for validation
        """
        self.sentinel = sentinel
        self.current_dir = sentinel.dev_root
        
        # Detect available CLI tools
        self.git_path = self._find_executable("git")
        self.cursor_path = self._find_executable("cursor")
        
        logger.info(f"CLIWrapper initialized. Git: {self.git_path}, Cursor: {self.cursor_path}")
    
    def _find_executable(self, name: str) -> Optional[str]:
        """Find executable in PATH."""
        return shutil.which(name)
    
    def _run_command(
        self,
        args: list[str],
        cwd: Optional[Path] = None,
        timeout: int = DEFAULT_TIMEOUT,
        shell: bool = False
    ) -> CommandResult:
        """
        Execute a command and capture output.
        
        Args:
            args: Command arguments (first element is the binary)
            cwd: Working directory (defaults to current_dir)
            timeout: Command timeout in seconds
            shell: Whether to run in shell (DANGEROUS - use sparingly)
            
        Returns:
            CommandResult with output and status
        """
        if cwd is None:
            cwd = self.current_dir
        
        # Validate the path
        cwd = self.sentinel.validate_path(str(cwd))
        
        # Validate the command
        if args:
            binary, validated_args = self.sentinel.validate_command(args[0], args[1:])
            args = [binary] + validated_args
        
        command_str = " ".join(args)
        logger.info(f"Executing: {command_str} in {cwd}")
        
        try:
            # SEC-001: Use safe environment variables only
            safe_env = self.sentinel.get_safe_env()
            
            result = subprocess.run(
                args,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=shell,
                env=safe_env,
                encoding='utf-8',
                errors='replace'  # Handle encoding errors gracefully
            )
            
            # Truncate output if too large
            stdout = result.stdout[:self.MAX_OUTPUT_SIZE]
            stderr = result.stderr[:self.MAX_OUTPUT_SIZE]
            
            if len(result.stdout) > self.MAX_OUTPUT_SIZE:
                stdout += "\n... (output truncated)"
            
            return CommandResult(
                success=result.returncode == 0,
                stdout=stdout,
                stderr=stderr,
                return_code=result.returncode,
                command=command_str
            )
            
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {command_str}")
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                return_code=-1,
                command=command_str
            )
        except FileNotFoundError as e:
            logger.error(f"Command not found: {args[0]}")
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"Command not found: {args[0]}",
                return_code=-1,
                command=command_str
            )
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return CommandResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=-1,
                command=command_str
            )
    
    def set_working_directory(self, path: str) -> Tuple[bool, str]:
        """
        Change the current working directory (within sandbox).
        
        Args:
            path: New directory path (relative or absolute)
            
        Returns:
            Tuple of (success, message)
        """
        try:
            new_dir = self.sentinel.validate_path(path)
            
            if not new_dir.is_dir():
                return False, f"Not a directory: {path}"
            
            self.current_dir = new_dir
            return True, f"Changed directory to: {new_dir}"
            
        except SecurityError as e:
            return False, str(e)
    
    # ==========================================
    # Git Operations
    # ==========================================
    
    def git_status(self) -> CommandResult:
        """Get git status of current directory."""
        return self._run_command(["git", "status", "--short", "--branch"])
    
    def git_diff(self, stat_only: bool = True) -> CommandResult:
        """
        Get git diff of current changes.
        
        Args:
            stat_only: If True, only show stats. If False, show full diff.
        """
        if stat_only:
            return self._run_command(["git", "diff", "--stat"])
        return self._run_command(["git", "diff"])
    
    def git_diff_staged(self) -> CommandResult:
        """Get diff of staged changes."""
        return self._run_command(["git", "diff", "--staged", "--stat"])
    
    def git_log(self, count: int = 5) -> CommandResult:
        """Get recent git log entries."""
        return self._run_command([
            "git", "log",
            f"--oneline",
            f"-{min(count, 20)}"  # Cap at 20 for safety
        ])
    
    def git_pull(self) -> CommandResult:
        """Pull latest changes from remote."""
        return self._run_command(["git", "pull"])
    
    def git_push(self) -> CommandResult:
        """Push committed changes to remote."""
        return self._run_command(["git", "push"])
    
    def git_add_all(self) -> CommandResult:
        """Stage all changes."""
        return self._run_command(["git", "add", "."])
    
    def git_commit(self, message: str) -> CommandResult:
        """
        Commit staged changes.
        
        Args:
            message: Commit message (will be sanitized)
        """
        # SEC-002: Use proper sanitization for commit message
        safe_message = self.sentinel.sanitize_for_subprocess(message)
        
        # Additional git-specific sanitization
        # Remove any remaining quotes that could break the command
        safe_message = safe_message.replace('"', "'")
        
        # Limit message length
        MAX_COMMIT_MSG_LENGTH = 500
        if len(safe_message) > MAX_COMMIT_MSG_LENGTH:
            safe_message = safe_message[:MAX_COMMIT_MSG_LENGTH] + "..."
        
        if not safe_message:
            safe_message = "TeleCode commit"
        
        return self._run_command(["git", "commit", "-m", safe_message])
    
    def git_restore(self) -> CommandResult:
        """Discard all uncommitted changes (DANGEROUS - revert)."""
        return self._run_command(["git", "restore", "."])
    
    def git_branch(self) -> CommandResult:
        """List branches."""
        return self._run_command(["git", "branch", "-a"])
    
    def git_init(self, path: Optional[Path] = None) -> CommandResult:
        """
        Initialize a new git repository.
        
        Args:
            path: Directory to initialize (defaults to current_dir)
        """
        cwd = path or self.current_dir
        return self._run_command(["git", "init"], cwd=cwd)
    
    def git_checkout(self, branch: str) -> CommandResult:
        """
        Switch to a branch.
        
        Args:
            branch: Branch name (sanitized)
        """
        # Sanitize branch name
        safe_branch = "".join(c for c in branch if c.isalnum() or c in "-_/.")
        return self._run_command(["git", "checkout", safe_branch])
    
    # ==========================================
    # Cursor AI Operations
    # ==========================================
    
    def run_cursor_ai(
        self, 
        prompt: str, 
        workspace: Optional[str] = None,
        model: Optional[str] = None
    ) -> CommandResult:
        """
        Execute an AI prompt via Cursor Agent Bridge.
        
        This opens Cursor with the workspace and saves the prompt
        to .telecode/prompt.md for the user to execute manually.
        
        NOTE: Cursor CLI doesn't have a true headless AI mode.
        The user must trigger AI manually in Cursor (Ctrl+I).
        Use CursorAgentBridge directly for full control.
        
        Args:
            prompt: The AI prompt to execute
            workspace: Optional workspace path (defaults to current_dir)
            model: Optional model ID to use (for display only)
            
        Returns:
            CommandResult with operation output
        """
        from .cursor_agent import get_agent_for_workspace
        
        if not self.cursor_path:
            return CommandResult(
                success=False,
                stdout="",
                stderr="Cursor CLI not found. Please install Cursor and add it to PATH.",
                return_code=-1,
                command="cursor"
            )
        
        workspace_path = Path(workspace) if workspace else self.current_dir
        
        # Validate workspace path
        try:
            self.sentinel.validate_path(str(workspace_path))
        except SecurityError as e:
            return CommandResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=-1,
                command="cursor"
            )
        
        # =============================================
        # SECURITY: Multi-layer prompt injection defense
        # =============================================
        
        # Layer 1: PromptGuard scan (token extraction, jailbreak, etc.)
        prompt_guard = get_prompt_guard(strict_mode=True)
        scan_result = prompt_guard.scan(prompt)
        
        if not scan_result.is_safe:
            logger.warning(f"Prompt blocked by PromptGuard: {scan_result.threat_level.name}")
            
            return CommandResult(
                success=False,
                stdout="",
                stderr=scan_result.warning_message or "Prompt blocked for security reasons.",
                return_code=-2,
                command="cursor (BLOCKED)"
            )
        
        # Layer 2: Additional sanitization
        safe_prompt = self.sentinel.sanitize_for_subprocess(prompt)
        
        if not safe_prompt:
            return CommandResult(
                success=False,
                stdout="",
                stderr="Prompt was empty after security sanitization.",
                return_code=-1,
                command="cursor"
            )
        
        # Layer 3: Limit prompt length
        MAX_PROMPT_LENGTH = 10000
        if len(safe_prompt) > MAX_PROMPT_LENGTH:
            safe_prompt = safe_prompt[:MAX_PROMPT_LENGTH]
            logger.warning(f"Prompt truncated to {MAX_PROMPT_LENGTH} characters")
        
        # =============================================
        # USE CURSOR AGENT BRIDGE
        # =============================================
        
        try:
            agent = get_agent_for_workspace(workspace_path)
            result = agent.send_prompt(safe_prompt, model=model)
            
            if result.success:
                instructions = result.data.get("instructions", []) if result.data else []
                instr_text = "\n".join(instructions)
                
                return CommandResult(
                    success=True,
                    stdout=f"{result.message}\n\n{instr_text}",
                    stderr="",
                    return_code=0,
                    command="cursor (CursorAgentBridge)"
                )
            else:
                return CommandResult(
                    success=False,
                    stdout="",
                    stderr=result.error or result.message,
                    return_code=-1,
                    command="cursor"
                )
                
        except Exception as e:
            logger.error(f"Cursor agent bridge failed: {e}")
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"Cursor execution failed: {str(e)}",
                return_code=-1,
                command="cursor"
            )
    
    def open_cursor(self, path: Optional[str] = None) -> CommandResult:
        """
        Open a directory in Cursor IDE.
        
        Args:
            path: Directory path to open (defaults to current_dir)
            
        Returns:
            CommandResult indicating success/failure
        """
        if not self.cursor_path:
            return CommandResult(
                success=False,
                stdout="",
                stderr="Cursor CLI not found. Please install Cursor and add it to PATH.",
                return_code=-1,
                command="cursor"
            )
        
        target = path or str(self.current_dir)
        
        # Validate path is in sandbox
        try:
            validated_path = self.sentinel.validate_path(target)
        except SecurityError as e:
            return CommandResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=-1,
                command=f"cursor {target}"
            )
        
        # Open Cursor with the directory
        args = [self.cursor_path, str(validated_path)]
        
        return self._run_command(args, timeout=30)
    
    # ==========================================
    # Project Scaffolding Operations
    # ==========================================
    
    def create_directory(self, name: str) -> Tuple[bool, str, Optional[Path]]:
        """
        Create a new directory within the sandbox.
        
        Security: Directory is ALWAYS created within DEV_ROOT.
        Name is sanitized to prevent path traversal.
        
        Args:
            name: Project/directory name (will be sanitized)
            
        Returns:
            Tuple of (success, message, path_if_created)
        """
        # Sanitize project name - only allow safe characters
        # Remove any path separators and suspicious patterns
        safe_name = self._sanitize_project_name(name)
        
        if not safe_name:
            return False, "Invalid project name. Use only letters, numbers, hyphens, and underscores.", None
        
        if len(safe_name) > 100:
            return False, "Project name too long. Maximum 100 characters.", None
        
        # Build the target path (always relative to DEV_ROOT)
        target_path = self.sentinel.dev_root / safe_name
        
        # Check if already exists
        if target_path.exists():
            return False, f"Directory already exists: {safe_name}", None
        
        try:
            # Create the directory
            target_path.mkdir(parents=False, exist_ok=False)
            
            logger.info(f"Created project directory: {target_path}")
            
            return True, f"Created directory: {safe_name}", target_path
            
        except PermissionError:
            return False, f"Permission denied. Cannot create directory: {safe_name}", None
        except Exception as e:
            logger.error(f"Failed to create directory: {e}")
            return False, f"Failed to create directory: {e}", None
    
    def _sanitize_project_name(self, name: str) -> str:
        """
        Sanitize a project name to prevent path traversal and injection.
        
        Only allows: a-z, A-Z, 0-9, hyphen (-), underscore (_), period (.)
        Strips leading/trailing whitespace and periods.
        
        Args:
            name: Raw project name input
            
        Returns:
            Sanitized name or empty string if invalid
        """
        import re
        
        # Strip whitespace
        name = name.strip()
        
        # Block path traversal patterns
        if ".." in name or "/" in name or "\\" in name:
            logger.warning(f"Path traversal attempt blocked in project name: {name}")
            return ""
        
        # Only allow safe characters
        sanitized = re.sub(r'[^a-zA-Z0-9\-_.]', '', name)
        
        # Remove leading/trailing periods (hidden files)
        sanitized = sanitized.strip('.')
        
        # Ensure it's not empty and doesn't start with special chars
        if not sanitized or sanitized[0] in '-_':
            return ""
        
        return sanitized
    
    def scaffold_project(self, name: str) -> Tuple[bool, str, Optional[Path]]:
        """
        Complete project scaffolding: create dir, init git, open Cursor.
        
        This is a convenience method that combines:
        1. create_directory()
        2. git_init()
        3. open_cursor()
        
        Args:
            name: Project name
            
        Returns:
            Tuple of (success, message, project_path)
        """
        # Step 1: Create directory
        success, message, project_path = self.create_directory(name)
        if not success:
            return False, f"❌ {message}", None
        
        # Step 2: Initialize git
        git_result = self.git_init(project_path)
        if not git_result.success:
            return False, f"❌ Directory created but git init failed: {git_result.stderr}", project_path
        
        # Step 3: Open in Cursor
        cursor_result = self.open_cursor(str(project_path))
        if not cursor_result.success:
            # Still success - project was created, just Cursor didn't open
            return True, f"✅ Project created and git initialized!\n⚠️ Could not open Cursor: {cursor_result.stderr}", project_path
        
        return True, f"✅ Project '{name}' created successfully!", project_path
    
    # ==========================================
    # File Operations
    # ==========================================
    
    def list_directory(self, path: Optional[str] = None) -> CommandResult:
        """
        List contents of a directory.
        
        Args:
            path: Directory path (defaults to current_dir)
        """
        target = path or str(self.current_dir)
        
        try:
            target_path = self.sentinel.validate_path(target)
        except SecurityError as e:
            return CommandResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=-1,
                command=f"ls {target}"
            )
        
        if not target_path.is_dir():
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"Not a directory: {target}",
                return_code=-1,
                command=f"ls {target}"
            )
        
        # List directory contents
        try:
            entries = []
            for item in sorted(target_path.iterdir()):
                prefix = "📁 " if item.is_dir() else "📄 "
                entries.append(f"{prefix}{item.name}")
            
            output = "\n".join(entries) if entries else "(empty directory)"
            
            return CommandResult(
                success=True,
                stdout=output,
                stderr="",
                return_code=0,
                command=f"ls {target}"
            )
        except PermissionError:
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"Permission denied: {target}",
                return_code=-1,
                command=f"ls {target}"
            )
    
    def read_file(self, path: str, max_lines: int = 100) -> CommandResult:
        """
        Read contents of a file.
        
        Args:
            path: File path
            max_lines: Maximum lines to read (for safety)
        """
        # SECURITY: Check if file is safe to read
        prompt_guard = get_prompt_guard()
        is_safe, reason = prompt_guard.is_safe_file_path(path)
        
        if not is_safe:
            logger.warning(f"Blocked file read: {path} - {reason}")
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"⛔ Access denied: {reason}",
                return_code=-2,
                command=f"cat {path} (BLOCKED)"
            )
        
        try:
            file_path = self.sentinel.validate_path(path)
        except SecurityError as e:
            return CommandResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=-1,
                command=f"cat {path}"
            )
        
        if not file_path.is_file():
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"Not a file: {path}",
                return_code=-1,
                command=f"cat {path}"
            )
        
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append(f"\n... (truncated at {max_lines} lines)")
                        break
                    lines.append(line.rstrip())
                
                return CommandResult(
                    success=True,
                    stdout="\n".join(lines),
                    stderr="",
                    return_code=0,
                    command=f"cat {path}"
                )
        except Exception as e:
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"Failed to read file: {e}",
                return_code=-1,
                command=f"cat {path}"
            )
    
    def append_to_file(self, path: str, content: str) -> CommandResult:
        """
        Append content to a file (for quick notes/TODOs).
        
        Args:
            path: File path
            content: Content to append
        """
        # SEC-002: Limit content size to prevent disk filling attacks
        MAX_APPEND_SIZE = 10000  # 10KB max per append
        if len(content) > MAX_APPEND_SIZE:
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"Content too large. Maximum {MAX_APPEND_SIZE} characters.",
                return_code=-1,
                command=f"append {path}"
            )
        
        try:
            file_path = self.sentinel.validate_path(path)
        except SecurityError as e:
            return CommandResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=-1,
                command=f"append {path}"
            )
        
        # SEC-006: Check file size before appending
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB max file size
        if file_path.exists() and file_path.stat().st_size > MAX_FILE_SIZE:
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"File too large to append (max {MAX_FILE_SIZE // 1024 // 1024}MB).",
                return_code=-1,
                command=f"append {path}"
            )
        
        try:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(content + "\n")
            
            return CommandResult(
                success=True,
                stdout=f"Appended to {file_path.name}",
                stderr="",
                return_code=0,
                command=f"append {path}"
            )
        except Exception as e:
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"Failed to append: {e}",
                return_code=-1,
                command=f"append {path}"
            )
    
    def get_current_info(self) -> str:
        """Get information about current working directory and git status."""
        info_parts = [
            f"📂 Current: {self.current_dir.name}",
            f"📍 Path: {self.current_dir}"
        ]
        
        # Add git info if in a repo
        git_result = self.git_status()
        if git_result.success:
            info_parts.append(f"🔀 Git: {git_result.stdout.strip()}")
        
        return "\n".join(info_parts)

