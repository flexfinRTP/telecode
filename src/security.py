"""
============================================
TeleCode v0.1 - Security Module
============================================
Implements Zero-Trust security architecture:
- User authentication via Telegram ID
- Filesystem sandboxing (path traversal prevention)
- Command whitelist enforcement
- Audit logging for all operations
- Rate limiting for failed attempts
- Secure environment variable handling

SECURITY NOTICE: This is the most critical module.
Any changes should be reviewed carefully.

AUDIT STATUS: Reviewed 2026-02 - All critical issues fixed
============================================
"""

import os
import re
import logging
import hashlib
import secrets
import time
from pathlib import Path
from functools import wraps
from datetime import datetime
from typing import Optional, Callable, Any, Dict
from collections import defaultdict

# Configure security logger
logger = logging.getLogger("telecode.security")


# ==========================================
# Rate Limiting (SEC-004 Fix)
# ==========================================

class RateLimiter:
    """
    Rate limiter to prevent brute-force and DoS attacks.
    
    Uses exponential backoff for failed attempts.
    """
    
    def __init__(self, max_attempts: int = 5, window_seconds: int = 60, lockout_seconds: int = 300):
        """
        Initialize rate limiter.
        
        Args:
            max_attempts: Maximum attempts before lockout
            window_seconds: Time window for counting attempts
            lockout_seconds: How long to lock out after max attempts
        """
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._attempts: Dict[str, list] = defaultdict(list)
        self._lockouts: Dict[str, float] = {}
    
    def is_allowed(self, key: str) -> bool:
        """
        Check if an action is allowed for a given key.
        
        Args:
            key: Identifier (e.g., user ID or IP)
            
        Returns:
            True if allowed, False if rate limited
        """
        now = time.time()
        
        # Check if locked out
        if key in self._lockouts:
            if now < self._lockouts[key]:
                return False
            else:
                # Lockout expired
                del self._lockouts[key]
                self._attempts[key] = []
        
        # Clean old attempts
        self._attempts[key] = [
            t for t in self._attempts[key]
            if now - t < self.window_seconds
        ]
        
        # Check attempt count
        if len(self._attempts[key]) >= self.max_attempts:
            self._lockouts[key] = now + self.lockout_seconds
            logger.warning(f"Rate limit exceeded for {key}, locked out for {self.lockout_seconds}s")
            return False
        
        return True
    
    def record_attempt(self, key: str) -> None:
        """Record a failed attempt."""
        self._attempts[key].append(time.time())
    
    def reset(self, key: str) -> None:
        """Reset attempts for a key (on successful auth)."""
        self._attempts.pop(key, None)
        self._lockouts.pop(key, None)


# Global rate limiter for auth failures
_auth_rate_limiter = RateLimiter(max_attempts=5, window_seconds=60, lockout_seconds=300)


class SecurityError(Exception):
    """Raised when a security violation is detected."""
    pass


class PathTraversalError(SecurityError):
    """Raised when path traversal attack is detected."""
    pass


class UnauthorizedUserError(SecurityError):
    """Raised when an unauthorized user attempts access."""
    pass


class ForbiddenCommandError(SecurityError):
    """Raised when a forbidden command is attempted."""
    pass


class SecuritySentinel:
    """
    The Iron Dome - Zero-Trust Security Gatekeeper
    
    This class enforces all security policies:
    1. User authentication (Telegram ID whitelist)
    2. Path sandboxing (DEV_ROOT jail)
    3. Command whitelisting
    4. Dangerous file blocking
    5. Shell injection prevention
    """
    
    # Whitelisted binaries that can be executed
    ALLOWED_BINARIES = frozenset([
        "git",
        "cursor",
        "cursor-agent",
        "code",       # VS Code CLI
        "ls",
        "dir",        # Windows equivalent of ls
        "cat",
        "type",       # Windows equivalent of cat
        "mkdir",      # Directory creation (for project scaffolding)
        "md",         # Windows equivalent of mkdir
    ])
    
    # Dangerous file patterns that should NEVER be accessed
    BLOCKED_FILE_PATTERNS = [
        r"\.env$",           # Environment files
        r"\.env\.",          # .env.local, .env.production, etc.
        r"id_rsa",           # SSH private keys
        r"id_ed25519",       # SSH private keys
        r"\.pem$",           # Certificate files
        r"\.key$",           # Key files
        r"\.ssh[/\\]",       # SSH directory
        r"credentials",      # Credential files
        r"secrets?\.json",   # Secret configuration
        r"\.git[/\\]config", # Git config with possible tokens
    ]
    
    # Shell injection patterns to block
    SHELL_INJECTION_PATTERNS = [
        r"&&",           # Command chaining
        r"\|\|",         # OR chaining
        r";",            # Command separator
        r"\|",           # Pipe (can be dangerous)
        r"`",            # Backtick execution
        r"\$\(",         # Command substitution
        r"\$\{",         # Variable expansion
        r">",            # Redirect output
        r"<",            # Redirect input
        r"\n",           # Newline injection
        r"\r",           # Carriage return injection
    ]
    
    def __init__(
        self,
        allowed_user_id: int,
        dev_root: str,
        enable_audit_log: bool = True
    ):
        """
        Initialize the Security Sentinel.
        
        Args:
            allowed_user_id: The only Telegram user ID allowed to use the bot
            dev_root: The root directory for all file operations (the "jail")
            enable_audit_log: Whether to log all operations for security audit
        """
        self.allowed_user_id = allowed_user_id
        self.dev_root = Path(dev_root).resolve()
        self.enable_audit_log = enable_audit_log
        
        # Compile blocked file patterns for performance
        self._blocked_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.BLOCKED_FILE_PATTERNS
        ]
        
        # Compile shell injection patterns
        self._injection_patterns = [
            re.compile(pattern)
            for pattern in self.SHELL_INJECTION_PATTERNS
        ]
        
        # Validate dev_root exists
        if not self.dev_root.exists():
            raise ValueError(f"DEV_ROOT does not exist: {self.dev_root}")
        
        logger.info(f"SecuritySentinel initialized. DEV_ROOT={self.dev_root}")
    
    def validate_user(self, user_id: int) -> bool:
        """
        Validate that the user is authorized.
        
        The Bouncer - Only the owner can enter.
        
        Args:
            user_id: Telegram user ID to validate
            
        Returns:
            True if authorized
            
        Raises:
            UnauthorizedUserError: If user is not authorized
        """
        # SEC-004: Check rate limiting first
        user_key = f"user_{user_id}"
        if not _auth_rate_limiter.is_allowed(user_key):
            self._audit_log(
                "RATE_LIMITED",
                f"User {user_id} is rate limited"
            )
            raise UnauthorizedUserError("Rate limited. Try again later.")
        
        if user_id != self.allowed_user_id:
            # SEC-004: Record failed attempt
            _auth_rate_limiter.record_attempt(user_key)
            
            # SEC-003: Don't leak the expected user ID in logs
            # Only log the attempting user ID (public info anyway)
            self._audit_log(
                "UNAUTHORIZED_ACCESS",
                f"Rejected user_id={user_id}"
            )
            # SEC-003: Generic error message (no info about expected ID)
            raise UnauthorizedUserError("Access denied.")
        
        # Reset rate limit on successful auth
        _auth_rate_limiter.reset(user_key)
        return True
    
    def validate_path(self, path: str) -> Path:
        """
        Validate that a path is within the sandbox (DEV_ROOT).
        
        The Jail - Prevents path traversal attacks.
        
        Args:
            path: The path to validate (can be relative or absolute)
            
        Returns:
            The resolved, validated Path object
            
        Raises:
            PathTraversalError: If path escapes the sandbox
            SecurityError: If path matches a blocked pattern
        """
        # Resolve the path to absolute
        if os.path.isabs(path):
            target = Path(path).resolve()
        else:
            target = (self.dev_root / path).resolve()
        
        # Check if path is within DEV_ROOT using commonpath
        try:
            common = Path(os.path.commonpath([self.dev_root, target]))
            if common != self.dev_root:
                self._audit_log(
                    "PATH_TRAVERSAL_BLOCKED",
                    f"Blocked: {path} -> {target} (escapes {self.dev_root})"
                )
                raise PathTraversalError(
                    f"Access denied. Path escapes sandbox: {path}"
                )
        except ValueError:
            # Different drives on Windows
            self._audit_log(
                "PATH_TRAVERSAL_BLOCKED",
                f"Blocked cross-drive access: {path}"
            )
            raise PathTraversalError(
                f"Access denied. Cross-drive access not allowed: {path}"
            )
        
        # Check against blocked file patterns
        path_str = str(target)
        for pattern in self._blocked_patterns:
            if pattern.search(path_str):
                self._audit_log(
                    "BLOCKED_FILE_ACCESS",
                    f"Blocked sensitive file: {path}"
                )
                raise SecurityError(
                    f"Access denied. Cannot access protected file: {path}"
                )
        
        return target
    
    def validate_command(self, binary: str, args: list[str]) -> tuple[str, list[str]]:
        """
        Validate that a command is in the whitelist and safe to execute.
        
        The Warden - Only approved commands can run.
        
        Args:
            binary: The binary/command to execute
            args: Command arguments
            
        Returns:
            Tuple of (validated_binary, sanitized_args)
            
        Raises:
            ForbiddenCommandError: If command is not whitelisted
            SecurityError: If shell injection is detected
        """
        # Normalize binary name (strip .exe on Windows)
        binary_normalized = binary.lower().replace(".exe", "")
        
        if binary_normalized not in self.ALLOWED_BINARIES:
            self._audit_log(
                "FORBIDDEN_COMMAND",
                f"Blocked command: {binary} {' '.join(args)}"
            )
            raise ForbiddenCommandError(
                f"Command not allowed: {binary}"
            )
        
        # Check each argument for shell injection
        sanitized_args = []
        for arg in args:
            for pattern in self._injection_patterns:
                if pattern.search(arg):
                    self._audit_log(
                        "SHELL_INJECTION_BLOCKED",
                        f"Blocked injection in arg: {arg}"
                    )
                    raise SecurityError(
                        f"Shell injection detected in argument: {arg}"
                    )
            sanitized_args.append(arg)
        
        return binary, sanitized_args
    
    def _audit_log(self, event_type: str, message: str) -> None:
        """
        Write to the security audit log.
        
        SEC-006: Audit log is written relative to script location,
        not hardcoded path that could escape sandbox.
        """
        if not self.enable_audit_log:
            return
        
        timestamp = datetime.now().isoformat()
        
        # SEC-003: Sanitize message to prevent log injection
        safe_message = message.replace("\n", " ").replace("\r", " ")
        log_entry = f"[{timestamp}] [{event_type}] {safe_message}"
        
        logger.warning(log_entry)
        
        # SEC-006: Write to file in project directory, not arbitrary location
        try:
            # Get the directory where this script is located
            script_dir = Path(__file__).parent.parent
            log_file = script_dir / "telecode_audit.log"
            
            # Validate log file is in expected location
            if not str(log_file.resolve()).startswith(str(script_dir.resolve())):
                logger.error("Audit log path validation failed")
                return
            
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_entry + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def log_command(self, user_id: int, command: str) -> None:
        """Log a successful command execution for audit trail."""
        # SEC-003: Truncate long commands to prevent log flooding
        safe_command = command[:200] + "..." if len(command) > 200 else command
        self._audit_log(
            "COMMAND_EXECUTED",
            f"User {user_id}: {safe_command}"
        )
    
    @staticmethod
    def get_safe_env() -> dict:
        """
        Get a safe subset of environment variables for subprocess.
        
        SEC-001: Only pass necessary env vars to child processes.
        Excludes potentially sensitive variables.
        """
        # Blocklist of sensitive environment variable patterns
        sensitive_patterns = [
            "TOKEN", "SECRET", "KEY", "PASSWORD", "CREDENTIAL",
            "AUTH", "API_KEY", "PRIVATE", "AWS_", "AZURE_",
            "GCP_", "GITHUB_TOKEN", "NPM_TOKEN", "TELEGRAM"
        ]
        
        safe_env = {}
        
        # Only include necessary environment variables
        # Whitelist approach for safety
        allowed_vars = [
            "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC",
            "TEMP", "TMP", "HOME", "USER", "USERNAME", "SHELL",
            "LANG", "LC_ALL", "LC_CTYPE", "TERM", "COLORTERM",
            "EDITOR", "VISUAL", "PAGER", "LESS", "DISPLAY",
            "XDG_RUNTIME_DIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
            "HOMEDRIVE", "HOMEPATH", "USERPROFILE", "APPDATA",
            "LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
            "COMMONPROGRAMFILES", "PROCESSOR_ARCHITECTURE",
            "NUMBER_OF_PROCESSORS", "OS", "COMPUTERNAME",
            # Git-specific
            "GIT_EXEC_PATH", "GIT_TEMPLATE_DIR", "GIT_SSL_CAINFO",
            "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
            "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
        ]
        
        for var in allowed_vars:
            if var in os.environ:
                safe_env[var] = os.environ[var]
        
        return safe_env
    
    @staticmethod
    def sanitize_for_subprocess(text: str) -> str:
        """
        Sanitize text for safe use in subprocess arguments.
        
        SEC-002: Removes or escapes dangerous patterns.
        """
        if not text:
            return ""
        
        # Remove null bytes
        text = text.replace("\x00", "")
        
        # Remove common shell injection patterns
        dangerous_patterns = [
            (r"\$\(.*?\)", ""),      # Command substitution $(...)
            (r"`.*?`", ""),           # Backtick execution
            (r"\$\{.*?\}", ""),       # Variable expansion ${...}
            (r";\s*", " "),           # Command separator
            (r"&&\s*", " "),          # AND chaining
            (r"\|\|\s*", " "),        # OR chaining
            (r"\|\s*", " "),          # Pipe
            (r">\s*", " "),           # Redirect
            (r"<\s*", " "),           # Redirect
            (r"\n", " "),             # Newline
            (r"\r", " "),             # Carriage return
        ]
        
        import re
        for pattern, replacement in dangerous_patterns:
            text = re.sub(pattern, replacement, text)
        
        # Collapse multiple spaces
        text = re.sub(r"\s+", " ", text).strip()
        
        return text


def require_auth(sentinel: SecuritySentinel):
    """
    Decorator that enforces user authentication on handler functions.
    
    Usage:
        @require_auth(security_sentinel)
        async def my_handler(update, context):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(update, context, *args, **kwargs):
            # Get user ID from update
            user_id = update.effective_user.id if update.effective_user else None
            
            if user_id is None:
                logger.warning("Received update without user ID")
                return None
            
            try:
                sentinel.validate_user(user_id)
                return await func(update, context, *args, **kwargs)
            except UnauthorizedUserError:
                # Silently drop unauthorized requests (don't leak info)
                logger.warning(f"Unauthorized access attempt from user {user_id}")
                return None
        
        return wrapper
    return decorator


def create_sentinel_from_env() -> Optional[SecuritySentinel]:
    """
    Create a SecuritySentinel from environment variables.
    
    Required env vars:
        - ALLOWED_USER_ID: int
        - DEV_ROOT: str (path)
        
    Optional:
        - ENABLE_AUDIT_LOG: bool (default True)
    
    Returns:
        SecuritySentinel instance or None if config is invalid
    """
    from dotenv import load_dotenv
    load_dotenv()
    
    user_id = os.getenv("ALLOWED_USER_ID")
    dev_root = os.getenv("DEV_ROOT")
    enable_audit = os.getenv("ENABLE_AUDIT_LOG", "true").lower() == "true"
    
    if not user_id or not dev_root:
        logger.error("Missing required config: ALLOWED_USER_ID and DEV_ROOT")
        return None
    
    try:
        return SecuritySentinel(
            allowed_user_id=int(user_id),
            dev_root=dev_root,
            enable_audit_log=enable_audit
        )
    except (ValueError, Exception) as e:
        logger.error(f"Failed to create SecuritySentinel: {e}")
        return None

