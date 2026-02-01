"""
============================================
TeleCode v0.1 - Security Tests
============================================
Tests for the Security Sentinel module.

Run with: pytest tests/test_security.py -v
============================================
"""

import os
import pytest
import tempfile
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.security import (
    SecuritySentinel,
    SecurityError,
    PathTraversalError,
    UnauthorizedUserError,
    ForbiddenCommandError
)


@pytest.fixture
def temp_sandbox():
    """Create a temporary sandbox directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some test files/directories
        sandbox = Path(tmpdir) / "sandbox"
        sandbox.mkdir()
        (sandbox / "project1").mkdir()
        (sandbox / "project1" / "main.py").write_text("print('hello')")
        (sandbox / "project1" / "secret.env").write_text("TOKEN=secret")
        yield sandbox


@pytest.fixture
def sentinel(temp_sandbox):
    """Create a SecuritySentinel for testing."""
    return SecuritySentinel(
        allowed_user_id=123456789,
        dev_root=str(temp_sandbox),
        enable_audit_log=False  # Disable logging for tests
    )


class TestUserValidation:
    """Tests for user authentication."""
    
    def test_valid_user(self, sentinel):
        """Valid user should be allowed."""
        assert sentinel.validate_user(123456789) is True
    
    def test_invalid_user(self, sentinel):
        """Invalid user should be rejected."""
        with pytest.raises(UnauthorizedUserError):
            sentinel.validate_user(999999999)
    
    def test_none_user(self, sentinel):
        """None user ID should be rejected."""
        with pytest.raises(UnauthorizedUserError):
            sentinel.validate_user(None)


class TestPathValidation:
    """Tests for filesystem sandboxing."""
    
    def test_valid_path_relative(self, sentinel, temp_sandbox):
        """Relative path within sandbox should be allowed."""
        result = sentinel.validate_path("project1")
        assert result == temp_sandbox / "project1"
    
    def test_valid_path_nested(self, sentinel, temp_sandbox):
        """Nested path within sandbox should be allowed."""
        result = sentinel.validate_path("project1/main.py")
        assert result == temp_sandbox / "project1" / "main.py"
    
    def test_path_traversal_attack(self, sentinel):
        """Path traversal attack should be blocked."""
        with pytest.raises(PathTraversalError):
            sentinel.validate_path("../../../etc/passwd")
    
    def test_path_traversal_double_dot(self, sentinel):
        """Double dot traversal should be blocked."""
        with pytest.raises(PathTraversalError):
            sentinel.validate_path("project1/../../outside")
    
    def test_absolute_path_outside(self, sentinel):
        """Absolute path outside sandbox should be blocked."""
        with pytest.raises(PathTraversalError):
            sentinel.validate_path("/etc/passwd")
    
    def test_blocked_env_file(self, sentinel):
        """Access to .env files should be blocked."""
        with pytest.raises(SecurityError):
            sentinel.validate_path("project1/secret.env")
    
    def test_blocked_ssh_key(self, sentinel, temp_sandbox):
        """Access to SSH keys should be blocked."""
        # Create a fake ssh key
        (temp_sandbox / "id_rsa").write_text("fake key")
        
        with pytest.raises(SecurityError):
            sentinel.validate_path("id_rsa")


class TestCommandValidation:
    """Tests for command whitelisting."""
    
    def test_allowed_command_git(self, sentinel):
        """Git command should be allowed."""
        binary, args = sentinel.validate_command("git", ["status"])
        assert binary == "git"
        assert args == ["status"]
    
    def test_allowed_command_cursor(self, sentinel):
        """Cursor command should be allowed."""
        binary, args = sentinel.validate_command("cursor", ["--help"])
        assert binary == "cursor"
    
    def test_forbidden_command_rm(self, sentinel):
        """rm command should be blocked."""
        with pytest.raises(ForbiddenCommandError):
            sentinel.validate_command("rm", ["-rf", "/"])
    
    def test_forbidden_command_curl(self, sentinel):
        """curl command should be blocked."""
        with pytest.raises(ForbiddenCommandError):
            sentinel.validate_command("curl", ["http://evil.com"])
    
    def test_shell_injection_semicolon(self, sentinel):
        """Semicolon injection should be blocked."""
        with pytest.raises(SecurityError):
            sentinel.validate_command("git", ["status; rm -rf /"])
    
    def test_shell_injection_pipe(self, sentinel):
        """Pipe injection should be blocked."""
        with pytest.raises(SecurityError):
            sentinel.validate_command("git", ["log | cat /etc/passwd"])
    
    def test_shell_injection_backtick(self, sentinel):
        """Backtick injection should be blocked."""
        with pytest.raises(SecurityError):
            sentinel.validate_command("git", ["`whoami`"])
    
    def test_shell_injection_dollar(self, sentinel):
        """Dollar substitution should be blocked."""
        with pytest.raises(SecurityError):
            sentinel.validate_command("git", ["$(whoami)"])


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_empty_path(self, sentinel, temp_sandbox):
        """Empty path should resolve to sandbox root."""
        result = sentinel.validate_path("")
        assert result == temp_sandbox
    
    def test_dot_path(self, sentinel, temp_sandbox):
        """Single dot should resolve to sandbox root."""
        result = sentinel.validate_path(".")
        assert result == temp_sandbox
    
    def test_case_sensitivity_windows(self, sentinel):
        """Command validation should be case-insensitive on Windows."""
        # This tests that 'GIT' is recognized as 'git'
        if os.name == 'nt':
            binary, args = sentinel.validate_command("GIT", ["status"])
            assert binary == "GIT"  # Original case preserved
    
    def test_exe_extension_windows(self, sentinel):
        """Command validation should handle .exe suffix."""
        binary, args = sentinel.validate_command("git.exe", ["status"])
        assert "git" in binary.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

