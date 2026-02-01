"""
============================================
TeleCode v0.1 - Token Vault (Secure Storage)
============================================
Provides encrypted token storage to prevent:
- Token leakage from .env files
- Memory scraping attacks
- Log/debug output exposure

Uses DPAPI on Windows, Keychain on macOS, or
encrypted file fallback with machine-specific key.

SECURITY NOTICE:
- Token is NEVER stored in plaintext
- Token is obfuscated in memory
- All access is logged for audit
============================================
"""

import os
import sys
import base64
import hashlib
import logging
import secrets
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("telecode.vault")

# Platform detection
IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"


class TokenVault:
    """
    Secure token storage with encryption.
    
    Features:
    - DPAPI encryption on Windows
    - Keychain on macOS (if available)
    - Encrypted file fallback
    - Memory obfuscation
    - Access logging
    """
    
    VAULT_FILE = ".telecode_vault"
    KEY_SERVICE = "TeleCode"
    KEY_ACCOUNT = "bot_token"
    
    def __init__(self):
        self._obfuscated_token: Optional[bytes] = None
        self._obfuscation_key: bytes = secrets.token_bytes(32)
        self._access_count = 0
    
    def store_token(self, token: str) -> Tuple[bool, str]:
        """
        Securely store the bot token.
        
        Args:
            token: The Telegram bot token
            
        Returns:
            Tuple of (success, message)
        """
        if not self._validate_token_format(token):
            return False, "Invalid token format"
        
        try:
            if IS_WINDOWS:
                return self._store_windows(token)
            elif IS_MACOS:
                return self._store_macos(token)
            else:
                return self._store_encrypted_file(token)
        except Exception as e:
            logger.error(f"Failed to store token: {type(e).__name__}")
            return False, "Failed to store token securely"
    
    def retrieve_token(self) -> Optional[str]:
        """
        Retrieve the bot token from secure storage.
        
        Returns:
            The token or None if not found/error
        """
        self._access_count += 1
        logger.info(f"Token access #{self._access_count}")
        
        # Check memory cache first (obfuscated)
        if self._obfuscated_token:
            return self._deobfuscate(self._obfuscated_token)
        
        try:
            if IS_WINDOWS:
                token = self._retrieve_windows()
            elif IS_MACOS:
                token = self._retrieve_macos()
            else:
                token = self._retrieve_encrypted_file()
            
            if token:
                # Cache in obfuscated form
                self._obfuscated_token = self._obfuscate(token)
            
            return token
        except Exception as e:
            logger.error(f"Failed to retrieve token: {type(e).__name__}")
            return None
    
    def clear_token(self) -> bool:
        """
        Remove the stored token.
        """
        self._obfuscated_token = None
        self._obfuscation_key = secrets.token_bytes(32)
        
        try:
            if IS_WINDOWS:
                return self._clear_windows()
            elif IS_MACOS:
                return self._clear_macos()
            else:
                return self._clear_encrypted_file()
        except Exception:
            return False
    
    def _validate_token_format(self, token: str) -> bool:
        """Validate token matches Telegram format."""
        import re
        pattern = r'^\d{8,10}:[A-Za-z0-9_-]{35,40}$'
        return bool(re.match(pattern, token))
    
    def _obfuscate(self, token: str) -> bytes:
        """
        Obfuscate token in memory.
        
        This prevents simple memory scanning attacks.
        """
        token_bytes = token.encode('utf-8')
        # XOR with key
        obfuscated = bytes(a ^ b for a, b in zip(
            token_bytes, 
            (self._obfuscation_key * ((len(token_bytes) // 32) + 1))[:len(token_bytes)]
        ))
        return obfuscated
    
    def _deobfuscate(self, obfuscated: bytes) -> str:
        """Deobfuscate token from memory."""
        token_bytes = bytes(a ^ b for a, b in zip(
            obfuscated,
            (self._obfuscation_key * ((len(obfuscated) // 32) + 1))[:len(obfuscated)]
        ))
        return token_bytes.decode('utf-8')
    
    def _get_machine_key(self) -> bytes:
        """
        Generate a machine-specific encryption key.
        
        Uses hardware identifiers to create a key unique to this machine.
        """
        # Combine machine-specific values
        factors = []
        
        # Machine name
        factors.append(os.environ.get("COMPUTERNAME", ""))
        factors.append(os.environ.get("HOSTNAME", ""))
        
        # User info
        factors.append(os.environ.get("USERNAME", ""))
        factors.append(os.environ.get("USER", ""))
        
        # Home directory (unique per user/machine)
        factors.append(str(Path.home()))
        
        # Combine and hash
        combined = "|".join(factors).encode('utf-8')
        return hashlib.sha256(combined).digest()
    
    # ==========================================
    # Windows DPAPI Implementation
    # ==========================================
    
    def _store_windows(self, token: str) -> Tuple[bool, str]:
        """Store token using Windows DPAPI."""
        try:
            import ctypes
            from ctypes import wintypes
            
            crypt32 = ctypes.windll.crypt32
            kernel32 = ctypes.windll.kernel32
            
            class DATA_BLOB(ctypes.Structure):
                _fields_ = [
                    ("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_byte))
                ]
            
            # Prepare input
            token_bytes = token.encode('utf-8')
            blob_in = DATA_BLOB()
            blob_in.cbData = len(token_bytes)
            blob_in.pbData = ctypes.cast(
                ctypes.create_string_buffer(token_bytes, len(token_bytes)),
                ctypes.POINTER(ctypes.c_byte)
            )
            
            blob_out = DATA_BLOB()
            
            # Encrypt with DPAPI
            if crypt32.CryptProtectData(
                ctypes.byref(blob_in),
                "TeleCode",  # Description
                None,        # Optional entropy
                None,        # Reserved
                None,        # Prompt struct
                0x01,        # CRYPTPROTECT_LOCAL_MACHINE flag
                ctypes.byref(blob_out)
            ):
                # Save encrypted blob to file
                encrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
                vault_path = Path.home() / self.VAULT_FILE
                vault_path.write_bytes(encrypted)
                
                # Free memory
                kernel32.LocalFree(blob_out.pbData)
                
                logger.info("Token stored with Windows DPAPI")
                return True, "Token stored securely (DPAPI)"
            else:
                return False, "DPAPI encryption failed"
                
        except Exception as e:
            logger.warning(f"DPAPI failed, using fallback: {e}")
            return self._store_encrypted_file(token)
    
    def _retrieve_windows(self) -> Optional[str]:
        """Retrieve token from Windows DPAPI."""
        try:
            import ctypes
            from ctypes import wintypes
            
            vault_path = Path.home() / self.VAULT_FILE
            if not vault_path.exists():
                return None
            
            encrypted = vault_path.read_bytes()
            
            crypt32 = ctypes.windll.crypt32
            kernel32 = ctypes.windll.kernel32
            
            class DATA_BLOB(ctypes.Structure):
                _fields_ = [
                    ("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_byte))
                ]
            
            blob_in = DATA_BLOB()
            blob_in.cbData = len(encrypted)
            blob_in.pbData = ctypes.cast(
                ctypes.create_string_buffer(encrypted, len(encrypted)),
                ctypes.POINTER(ctypes.c_byte)
            )
            
            blob_out = DATA_BLOB()
            
            if crypt32.CryptUnprotectData(
                ctypes.byref(blob_in),
                None, None, None, None,
                0x01,
                ctypes.byref(blob_out)
            ):
                token = ctypes.string_at(blob_out.pbData, blob_out.cbData).decode('utf-8')
                kernel32.LocalFree(blob_out.pbData)
                return token
            
            return None
            
        except Exception as e:
            logger.warning(f"DPAPI retrieval failed, trying fallback: {e}")
            return self._retrieve_encrypted_file()
    
    def _clear_windows(self) -> bool:
        """Clear Windows vault."""
        vault_path = Path.home() / self.VAULT_FILE
        if vault_path.exists():
            # Secure delete
            vault_path.write_bytes(secrets.token_bytes(100))
            vault_path.unlink()
        return True
    
    # ==========================================
    # macOS Keychain Implementation
    # ==========================================
    
    def _store_macos(self, token: str) -> Tuple[bool, str]:
        """Store token using macOS Keychain."""
        try:
            import subprocess
            
            # Delete existing entry first
            subprocess.run(
                ["security", "delete-generic-password", 
                 "-s", self.KEY_SERVICE, "-a", self.KEY_ACCOUNT],
                capture_output=True
            )
            
            # Add new entry
            result = subprocess.run(
                ["security", "add-generic-password",
                 "-s", self.KEY_SERVICE, "-a", self.KEY_ACCOUNT,
                 "-w", token, "-U"],
                capture_output=True
            )
            
            if result.returncode == 0:
                logger.info("Token stored in macOS Keychain")
                return True, "Token stored securely (Keychain)"
            else:
                return self._store_encrypted_file(token)
                
        except Exception as e:
            logger.warning(f"Keychain failed, using fallback: {e}")
            return self._store_encrypted_file(token)
    
    def _retrieve_macos(self) -> Optional[str]:
        """Retrieve token from macOS Keychain."""
        try:
            import subprocess
            
            result = subprocess.run(
                ["security", "find-generic-password",
                 "-s", self.KEY_SERVICE, "-a", self.KEY_ACCOUNT, "-w"],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            
            return self._retrieve_encrypted_file()
            
        except Exception:
            return self._retrieve_encrypted_file()
    
    def _clear_macos(self) -> bool:
        """Clear macOS Keychain entry."""
        try:
            import subprocess
            subprocess.run(
                ["security", "delete-generic-password",
                 "-s", self.KEY_SERVICE, "-a", self.KEY_ACCOUNT],
                capture_output=True
            )
        except Exception:
            pass
        return self._clear_encrypted_file()
    
    # ==========================================
    # Encrypted File Fallback
    # ==========================================
    
    def _store_encrypted_file(self, token: str) -> Tuple[bool, str]:
        """Store token in encrypted file (fallback)."""
        try:
            key = self._get_machine_key()
            
            # Simple XOR encryption with key stretching
            token_bytes = token.encode('utf-8')
            nonce = secrets.token_bytes(16)
            
            # Key derivation
            derived_key = hashlib.pbkdf2_hmac('sha256', key, nonce, 100000)
            
            # Encrypt
            encrypted = bytes(a ^ b for a, b in zip(
                token_bytes,
                (derived_key * ((len(token_bytes) // 32) + 1))[:len(token_bytes)]
            ))
            
            # Store nonce + encrypted
            vault_path = Path.home() / self.VAULT_FILE
            vault_path.write_bytes(nonce + encrypted)
            
            # Set restrictive permissions
            if not IS_WINDOWS:
                os.chmod(vault_path, 0o600)
            
            logger.info("Token stored with encrypted file")
            return True, "Token stored securely (encrypted file)"
            
        except Exception as e:
            logger.error(f"Failed to store encrypted file: {e}")
            return False, "Failed to store token"
    
    def _retrieve_encrypted_file(self) -> Optional[str]:
        """Retrieve token from encrypted file."""
        try:
            vault_path = Path.home() / self.VAULT_FILE
            if not vault_path.exists():
                return None
            
            data = vault_path.read_bytes()
            if len(data) < 17:
                return None
            
            nonce = data[:16]
            encrypted = data[16:]
            
            key = self._get_machine_key()
            derived_key = hashlib.pbkdf2_hmac('sha256', key, nonce, 100000)
            
            # Decrypt
            decrypted = bytes(a ^ b for a, b in zip(
                encrypted,
                (derived_key * ((len(encrypted) // 32) + 1))[:len(encrypted)]
            ))
            
            return decrypted.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Failed to retrieve encrypted file: {e}")
            return None
    
    def _clear_encrypted_file(self) -> bool:
        """Clear encrypted file."""
        vault_path = Path.home() / self.VAULT_FILE
        if vault_path.exists():
            # Secure delete - overwrite before unlinking
            vault_path.write_bytes(secrets.token_bytes(100))
            vault_path.unlink()
        return True


def mask_token(token: str) -> str:
    """
    Mask a token for display/logging.
    
    Shows only format validation without revealing content.
    Example: "123***:***ABC"
    """
    if not token or len(token) < 10:
        return "[INVALID]"
    
    parts = token.split(":")
    if len(parts) != 2:
        return "[INVALID]"
    
    bot_id = parts[0]
    secret = parts[1]
    
    # Show first 3 and last 3 chars only
    masked_id = bot_id[:3] + "*" * (len(bot_id) - 3)
    masked_secret = secret[:3] + "*" * (len(secret) - 6) + secret[-3:]
    
    return f"{masked_id}:{masked_secret}"


# Singleton vault instance
_vault: Optional[TokenVault] = None


def get_vault() -> TokenVault:
    """Get the singleton TokenVault instance."""
    global _vault
    if _vault is None:
        _vault = TokenVault()
    return _vault

