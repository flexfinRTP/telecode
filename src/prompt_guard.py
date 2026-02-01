"""
============================================
TeleCode v0.1 - Prompt Guard (Injection Defense)
============================================
Multi-layer defense against prompt injection attacks.

Attack Vectors Blocked:
- Token extraction attempts
- System prompt leakage
- Jailbreak attempts
- Command injection via prompts
- Data exfiltration patterns

Based on OWASP AI Agent Security Guidelines.
============================================
"""

import re
import logging
from typing import Tuple, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("telecode.prompt_guard")


class ThreatLevel(Enum):
    """Threat classification levels."""
    SAFE = 0
    SUSPICIOUS = 1
    BLOCKED = 2
    CRITICAL = 3


@dataclass
class ScanResult:
    """Result of a prompt security scan."""
    is_safe: bool
    threat_level: ThreatLevel
    blocked_patterns: List[str]
    sanitized_prompt: str
    warning_message: Optional[str] = None


class PromptGuard:
    """
    Multi-layer prompt injection defense.
    
    Layers:
    1. Token/Secret Extraction Detection
    2. System Prompt Leakage Detection
    3. Jailbreak Pattern Detection
    4. Command Injection Detection
    5. Data Exfiltration Detection
    """
    
    # ===========================================
    # LAYER 1: Token/Secret Extraction Patterns
    # ===========================================
    TOKEN_EXTRACTION_PATTERNS = [
        # Direct token requests
        r"(?i)show\s*(me\s*)?(the\s*)?token",
        r"(?i)what\s*is\s*(the\s*)?(your\s*)?token",
        r"(?i)reveal\s*(the\s*)?token",
        r"(?i)print\s*(the\s*)?token",
        r"(?i)display\s*(the\s*)?token",
        r"(?i)output\s*(the\s*)?token",
        r"(?i)give\s*(me\s*)?(the\s*)?token",
        r"(?i)tell\s*(me\s*)?(the\s*)?token",
        r"(?i)leak\s*(the\s*)?token",
        r"(?i)expose\s*(the\s*)?token",
        
        # Environment variable extraction
        r"(?i)print\s*env",
        r"(?i)echo\s*\$",
        r"(?i)printenv",
        r"(?i)show\s*environment",
        r"(?i)list\s*env",
        r"(?i)get\s*env",
        r"(?i)os\.environ",
        r"(?i)process\.env",
        r"(?i)getenv\s*\(",
        
        # Config file extraction
        r"(?i)read\s*\.env",
        r"(?i)cat\s*\.env",
        r"(?i)show\s*\.env",
        r"(?i)print\s*\.env",
        r"(?i)type\s*\.env",
        r"(?i)display\s*config",
        
        # API key extraction
        r"(?i)api\s*key",
        r"(?i)secret\s*key",
        r"(?i)bot\s*token",
        r"(?i)telegram.*token",
        r"(?i)access\s*token",
        
        # Credential patterns
        r"(?i)password",
        r"(?i)credential",
        r"(?i)ssh\s*key",
        r"(?i)private\s*key",
    ]
    
    # ===========================================
    # LAYER 2: System Prompt Leakage Patterns
    # ===========================================
    SYSTEM_PROMPT_LEAKAGE_PATTERNS = [
        r"(?i)ignore\s*(previous|all|prior)\s*instructions",
        r"(?i)disregard\s*(previous|all|prior)\s*instructions",
        r"(?i)forget\s*(previous|all|prior)\s*instructions",
        r"(?i)what\s*(are|were)\s*(your|the)\s*instructions",
        r"(?i)show\s*(me\s*)?(your\s*)?system\s*prompt",
        r"(?i)reveal\s*(your\s*)?system\s*prompt",
        r"(?i)print\s*(your\s*)?system\s*prompt",
        r"(?i)what\s*is\s*your\s*system\s*prompt",
        r"(?i)repeat\s*(your\s*)?initial\s*instructions",
        r"(?i)first\s*instruction",
        r"(?i)original\s*instructions",
        r"(?i)tell\s*me\s*your\s*rules",
        r"(?i)bypass\s*restrictions",
        r"(?i)override\s*safety",
    ]
    
    # ===========================================
    # LAYER 3: Jailbreak Patterns
    # ===========================================
    JAILBREAK_PATTERNS = [
        r"(?i)pretend\s*(you\s*are|to\s*be)",
        r"(?i)act\s*as\s*if",
        r"(?i)roleplay\s*as",
        r"(?i)you\s*are\s*now\s*(?!going)",  # "you are now X" but not "you are now going to"
        r"(?i)dan\s*mode",
        r"(?i)developer\s*mode",
        r"(?i)unrestricted\s*mode",
        r"(?i)no\s*restrictions",
        r"(?i)no\s*limits",
        r"(?i)without\s*safety",
        r"(?i)disable\s*filters",
        r"(?i)turn\s*off\s*safety",
        r"(?i)hypothetically",
        r"(?i)in\s*fiction",
        r"(?i)for\s*educational\s*purposes",
        r"(?i)as\s*a\s*thought\s*experiment",
    ]
    
    # ===========================================
    # LAYER 4: Command Injection Patterns
    # ===========================================
    COMMAND_INJECTION_PATTERNS = [
        # Shell commands
        r"(?i);\s*rm\s",
        r"(?i);\s*del\s",
        r"(?i);\s*format\s",
        r"(?i);\s*shutdown",
        r"(?i);\s*reboot",
        r"(?i)\|\s*rm\s",
        r"(?i)&&\s*rm\s",
        r"(?i)\$\(.*\)",  # Command substitution
        r"`[^`]+`",        # Backtick execution
        
        # Dangerous file operations
        r"(?i)delete\s*(all|every|\*)",
        r"(?i)remove\s*(all|every|\*)",
        r"(?i)erase\s*(all|every|\*)",
        r"(?i)destroy\s*(all|every|\*)",
        r"(?i)format\s*(drive|disk|c:)",
        r"(?i)wipe\s*(drive|disk|system)",
        
        # Network exfiltration
        r"(?i)curl\s+.*\s+[-d]",
        r"(?i)wget\s+",
        r"(?i)nc\s+-",
        r"(?i)netcat",
        r"(?i)socket\s*\(",
        r"(?i)requests\.(post|get)\s*\(",
        r"(?i)urllib",
        r"(?i)http\s*request",
        
        # Code execution
        r"(?i)exec\s*\(",
        r"(?i)eval\s*\(",
        r"(?i)compile\s*\(",
        r"(?i)__import__",
        r"(?i)subprocess",
        r"(?i)os\.system",
        r"(?i)popen\s*\(",
    ]
    
    # ===========================================
    # LAYER 5: Data Exfiltration Patterns
    # ===========================================
    DATA_EXFILTRATION_PATTERNS = [
        # File type patterns
        r"(?i)\.env",
        r"(?i)\.pem$",
        r"(?i)\.key$",
        r"(?i)id_rsa",
        r"(?i)id_ed25519",
        r"(?i)\.ssh/",
        r"(?i)known_hosts",
        r"(?i)authorized_keys",
        r"(?i)\.aws/",
        r"(?i)credentials",
        r"(?i)secrets?\.(json|yaml|yml|xml)",
        r"(?i)\.git/config",
        r"(?i)\.gitconfig",
        r"(?i)\.npmrc",
        r"(?i)\.pypirc",
        
        # Database patterns
        r"(?i)\.sqlite",
        r"(?i)\.db$",
        r"(?i)dump\s*database",
        r"(?i)export\s*database",
        
        # Send/upload patterns
        r"(?i)send\s*(to|via)\s*(http|email|server|webhook)",
        r"(?i)upload\s*(to|via)",
        r"(?i)post\s*(to|via)\s*(http|api|server)",
        r"(?i)exfiltrate",
        r"(?i)transfer\s*(out|to\s*external)",
    ]
    
    def __init__(self, strict_mode: bool = True):
        """
        Initialize PromptGuard.
        
        Args:
            strict_mode: If True, blocks suspicious patterns. If False, only warns.
        """
        self.strict_mode = strict_mode
        
        # Compile all patterns for performance
        self._compiled_patterns = {
            "token_extraction": [re.compile(p) for p in self.TOKEN_EXTRACTION_PATTERNS],
            "system_leakage": [re.compile(p) for p in self.SYSTEM_PROMPT_LEAKAGE_PATTERNS],
            "jailbreak": [re.compile(p) for p in self.JAILBREAK_PATTERNS],
            "command_injection": [re.compile(p) for p in self.COMMAND_INJECTION_PATTERNS],
            "data_exfiltration": [re.compile(p) for p in self.DATA_EXFILTRATION_PATTERNS],
        }
    
    def scan(self, prompt: str) -> ScanResult:
        """
        Scan a prompt for injection attempts.
        
        Args:
            prompt: The user's prompt to scan
            
        Returns:
            ScanResult with threat analysis
        """
        if not prompt or not prompt.strip():
            return ScanResult(
                is_safe=True,
                threat_level=ThreatLevel.SAFE,
                blocked_patterns=[],
                sanitized_prompt=""
            )
        
        blocked_patterns = []
        threat_level = ThreatLevel.SAFE
        
        # Layer 1: Token extraction (CRITICAL)
        for pattern in self._compiled_patterns["token_extraction"]:
            if pattern.search(prompt):
                blocked_patterns.append(f"TOKEN_EXTRACTION: {pattern.pattern[:30]}...")
                threat_level = ThreatLevel.CRITICAL
        
        # Layer 2: System prompt leakage (BLOCKED)
        for pattern in self._compiled_patterns["system_leakage"]:
            if pattern.search(prompt):
                blocked_patterns.append(f"SYSTEM_LEAKAGE: {pattern.pattern[:30]}...")
                if threat_level.value < ThreatLevel.BLOCKED.value:
                    threat_level = ThreatLevel.BLOCKED
        
        # Layer 3: Jailbreak attempts (BLOCKED)
        for pattern in self._compiled_patterns["jailbreak"]:
            if pattern.search(prompt):
                blocked_patterns.append(f"JAILBREAK: {pattern.pattern[:30]}...")
                if threat_level.value < ThreatLevel.BLOCKED.value:
                    threat_level = ThreatLevel.BLOCKED
        
        # Layer 4: Command injection (CRITICAL)
        for pattern in self._compiled_patterns["command_injection"]:
            if pattern.search(prompt):
                blocked_patterns.append(f"COMMAND_INJECTION: {pattern.pattern[:30]}...")
                threat_level = ThreatLevel.CRITICAL
        
        # Layer 5: Data exfiltration (BLOCKED)
        for pattern in self._compiled_patterns["data_exfiltration"]:
            if pattern.search(prompt):
                blocked_patterns.append(f"DATA_EXFILTRATION: {pattern.pattern[:30]}...")
                if threat_level.value < ThreatLevel.BLOCKED.value:
                    threat_level = ThreatLevel.BLOCKED
        
        # Determine safety
        is_safe = threat_level == ThreatLevel.SAFE
        
        if not is_safe and self.strict_mode:
            # In strict mode, block the prompt entirely
            sanitized_prompt = ""
            warning_message = self._get_warning_message(threat_level, blocked_patterns)
        else:
            # Try to sanitize the prompt
            sanitized_prompt = self._sanitize_prompt(prompt)
            warning_message = None if is_safe else self._get_warning_message(threat_level, blocked_patterns)
        
        # Log security event
        if blocked_patterns:
            logger.warning(f"Prompt injection detected: {threat_level.name}, patterns: {len(blocked_patterns)}")
        
        return ScanResult(
            is_safe=is_safe,
            threat_level=threat_level,
            blocked_patterns=blocked_patterns,
            sanitized_prompt=sanitized_prompt if is_safe else "",
            warning_message=warning_message
        )
    
    def _sanitize_prompt(self, prompt: str) -> str:
        """
        Sanitize a prompt by removing dangerous patterns.
        
        Note: This is a best-effort sanitization. In strict mode,
        dangerous prompts are blocked entirely.
        """
        sanitized = prompt
        
        # Remove shell injection patterns
        sanitized = re.sub(r'[;&|`$]', '', sanitized)
        sanitized = re.sub(r'\$\([^)]*\)', '', sanitized)
        sanitized = re.sub(r'`[^`]*`', '', sanitized)
        
        # Remove redirect operators
        sanitized = re.sub(r'[<>]', '', sanitized)
        
        # Remove newlines (can be used for injection)
        sanitized = sanitized.replace('\n', ' ').replace('\r', ' ')
        
        # Collapse multiple spaces
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        return sanitized
    
    def _get_warning_message(self, threat_level: ThreatLevel, patterns: List[str]) -> str:
        """Generate a user-facing warning message."""
        if threat_level == ThreatLevel.CRITICAL:
            return (
                "⛔ **SECURITY ALERT**\n\n"
                "Your prompt was blocked because it appears to be attempting "
                "to extract sensitive information or execute dangerous commands.\n\n"
                "This incident has been logged."
            )
        elif threat_level == ThreatLevel.BLOCKED:
            return (
                "🚫 **Prompt Blocked**\n\n"
                "Your prompt contains patterns that are not allowed for security reasons.\n\n"
                "Please rephrase your request."
            )
        else:
            return (
                "⚠️ **Warning**\n\n"
                "Your prompt contains suspicious patterns and has been sanitized."
            )
    
    def is_safe_file_path(self, path: str) -> Tuple[bool, str]:
        """
        Check if a file path is safe to access.
        
        Args:
            path: The file path to check
            
        Returns:
            Tuple of (is_safe, reason)
        """
        path_lower = path.lower()
        
        # Check against data exfiltration patterns
        for pattern in self._compiled_patterns["data_exfiltration"]:
            if pattern.search(path):
                return False, "Access to this file type is blocked for security"
        
        # Additional file-specific checks
        dangerous_files = [
            ".env", "env.local", ".env.production",
            "id_rsa", "id_ed25519", "id_ecdsa",
            ".pem", ".key", ".p12", ".pfx",
            "credentials", "secrets.json", "secrets.yaml",
            ".git/config", ".gitconfig",
            ".aws/credentials", ".azure/credentials",
            ".npmrc", ".pypirc", ".docker/config.json",
        ]
        
        for dangerous in dangerous_files:
            if dangerous in path_lower:
                return False, f"Access to {dangerous} files is blocked"
        
        return True, ""


# Singleton instance
_guard: Optional[PromptGuard] = None


def get_prompt_guard(strict_mode: bool = True) -> PromptGuard:
    """Get the singleton PromptGuard instance."""
    global _guard
    if _guard is None:
        _guard = PromptGuard(strict_mode=strict_mode)
    return _guard


def scan_prompt(prompt: str) -> ScanResult:
    """Convenience function to scan a prompt."""
    return get_prompt_guard().scan(prompt)


def is_safe_file(path: str) -> Tuple[bool, str]:
    """Convenience function to check file safety."""
    return get_prompt_guard().is_safe_file_path(path)

