"""
============================================
TeleCode v0.1 - Lock PIN Storage
============================================
Secure storage for lock PIN/password.

Uses same encryption as token vault for consistency.
============================================
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("telecode.lock_pin")

IS_WINDOWS = sys.platform == "win32"

# Try to use token vault's storage methods
try:
    from .token_vault import TokenVault
    
    class LockPINStorage:
        """Secure storage for lock PIN/password."""
        
        KEY_SERVICE = "TeleCode"
        KEY_ACCOUNT = "lock_pin"
        KEY_ACCOUNT_PASSWORD = "lock_password"
        
        def __init__(self):
            self.vault = TokenVault()
        
        def store_pin(self, pin: str) -> Tuple[bool, str]:
            """Store lock PIN securely."""
            if not pin or len(pin) < 4:
                return False, "PIN must be at least 4 characters"
            
            try:
                # Use vault's encrypted file storage
                vault_path = Path.home() / ".telecode_vault"
                pin_data = f"PIN:{pin}"
                
                # Store using same method as token vault
                if IS_WINDOWS:
                    success, msg = self._store_windows(pin_data)
                else:
                    success, msg = self._store_encrypted_file(pin_data)
                
                if success:
                    logger.info("Lock PIN stored securely")
                    return True, "PIN stored securely"
                else:
                    return False, msg
                    
            except Exception as e:
                logger.error(f"Failed to store PIN: {e}")
                return False, f"Failed to store PIN: {e}"
        
        def store_password(self, password: str) -> Tuple[bool, str]:
            """Store lock password securely."""
            if not password or len(password) < 4:
                return False, "Password must be at least 4 characters"
            
            try:
                password_data = f"PASSWORD:{password}"
                
                if IS_WINDOWS:
                    success, msg = self._store_windows(password_data, is_password=True)
                else:
                    success, msg = self._store_encrypted_file(password_data)
                
                if success:
                    logger.info("Lock password stored securely")
                    return True, "Password stored securely"
                else:
                    return False, msg
                    
            except Exception as e:
                logger.error(f"Failed to store password: {e}")
                return False, f"Failed to store password: {e}"
        
        def retrieve_pin(self) -> Optional[str]:
            """Retrieve lock PIN."""
            try:
                if IS_WINDOWS:
                    data = self._retrieve_windows()
                else:
                    data = self._retrieve_encrypted_file()
                
                if data and data.startswith("PIN:"):
                    return data[4:]  # Remove "PIN:" prefix
                return None
                
            except Exception as e:
                logger.error(f"Failed to retrieve PIN: {e}")
                return None
        
        def retrieve_password(self) -> Optional[str]:
            """Retrieve lock password."""
            try:
                if IS_WINDOWS:
                    data = self._retrieve_windows(is_password=True)
                else:
                    data = self._retrieve_encrypted_file()
                
                if data and data.startswith("PASSWORD:"):
                    return data[9:]  # Remove "PASSWORD:" prefix
                return None
                
            except Exception as e:
                logger.error(f"Failed to retrieve password: {e}")
                return None
        
        def has_pin(self) -> bool:
            """Check if PIN is set."""
            return self.retrieve_pin() is not None
        
        def has_password(self) -> bool:
            """Check if password is set."""
            return self.retrieve_password() is not None
        
        def _store_windows(self, data: str, is_password: bool = False) -> Tuple[bool, str]:
            """Store using Windows DPAPI."""
            try:
                import ctypes
                from ctypes import wintypes
                
                class DATA_BLOB(ctypes.Structure):
                    _fields_ = [("cbData", wintypes.DWORD),
                               ("pbData", ctypes.POINTER(ctypes.c_byte))]
                
                crypt32 = ctypes.windll.crypt32
                
                blob_in = DATA_BLOB()
                blob_in.pbData = ctypes.c_char_p(data.encode('utf-8'))
                blob_in.cbData = len(data.encode('utf-8'))
                
                blob_out = DATA_BLOB()
                
                account = self.KEY_ACCOUNT_PASSWORD if is_password else self.KEY_ACCOUNT
                
                if crypt32.CryptProtectData(
                    ctypes.byref(blob_in),
                    f"TeleCode Lock {account}",
                    None, None, None, 0x01,
                    ctypes.byref(blob_out)
                ):
                    encrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
                    vault_path = Path.home() / f".telecode_lock_{account}"
                    vault_path.write_bytes(encrypted)
                    kernel32 = ctypes.windll.kernel32
                    kernel32.LocalFree(blob_out.pbData)
                    return True, "Stored securely"
                return False, "Encryption failed"
            except Exception as e:
                logger.warning(f"DPAPI failed: {e}")
                return self._store_encrypted_file(data)
        
        def _retrieve_windows(self, is_password: bool = False) -> Optional[str]:
            """Retrieve from Windows DPAPI."""
            try:
                import ctypes
                from ctypes import wintypes
                
                class DATA_BLOB(ctypes.Structure):
                    _fields_ = [("cbData", wintypes.DWORD),
                               ("pbData", ctypes.POINTER(ctypes.c_byte))]
                
                account = self.KEY_ACCOUNT_PASSWORD if is_password else self.KEY_ACCOUNT
                vault_path = Path.home() / f".telecode_lock_{account}"
                
                if not vault_path.exists():
                    return None
                
                encrypted = vault_path.read_bytes()
                
                blob_in = DATA_BLOB()
                blob_in.pbData = ctypes.cast(encrypted, ctypes.POINTER(ctypes.c_byte))
                blob_in.cbData = len(encrypted)
                
                blob_out = DATA_BLOB()
                
                crypt32 = ctypes.windll.crypt32
                if crypt32.CryptUnprotectData(
                    ctypes.byref(blob_in),
                    None, None, None, None, 0,
                    ctypes.byref(blob_out)
                ):
                    data = ctypes.string_at(blob_out.pbData, blob_out.cbData).decode('utf-8')
                    kernel32 = ctypes.windll.kernel32
                    kernel32.LocalFree(blob_out.pbData)
                    return data
                return None
            except Exception as e:
                logger.warning(f"DPAPI retrieve failed: {e}")
                return self._retrieve_encrypted_file()
        
        def _store_encrypted_file(self, data: str) -> Tuple[bool, str]:
            """Store in encrypted file (fallback)."""
            try:
                import hashlib
                import secrets
                import base64
                
                # Simple encryption using machine key
                machine_key = self.vault._get_machine_key()
                nonce = secrets.token_bytes(16)
                key = hashlib.pbkdf2_hmac('sha256', machine_key, nonce, 100000)
                
                encrypted = bytes(a ^ b for a, b in zip(
                    data.encode('utf-8'),
                    (key * ((len(data) // 32) + 1))[:len(data)]
                ))
                
                vault_path = Path.home() / ".telecode_lock_pin"
                vault_path.write_bytes(nonce + encrypted)
                return True, "Stored securely"
            except Exception as e:
                return False, f"Storage failed: {e}"
        
        def _retrieve_encrypted_file(self) -> Optional[str]:
            """Retrieve from encrypted file."""
            try:
                import hashlib
                
                vault_path = Path.home() / ".telecode_lock_pin"
                if not vault_path.exists():
                    return None
                
                data = vault_path.read_bytes()
                if len(data) < 17:
                    return None
                
                nonce = data[:16]
                encrypted = data[16:]
                
                machine_key = self.vault._get_machine_key()
                key = hashlib.pbkdf2_hmac('sha256', machine_key, nonce, 100000)
                
                decrypted = bytes(a ^ b for a, b in zip(
                    encrypted,
                    (key * ((len(encrypted) // 32) + 1))[:len(encrypted)]
                ))
                
                return decrypted.decode('utf-8')
            except Exception as e:
                logger.error(f"Retrieve failed: {e}")
                return None

except ImportError:
    # Fallback if token_vault not available
    class LockPINStorage:
        def store_pin(self, pin: str) -> Tuple[bool, str]:
            return False, "PIN storage not available"
        
        def retrieve_pin(self) -> Optional[str]:
            return None


def get_lock_pin_storage() -> LockPINStorage:
    """Get lock PIN storage instance."""
    return LockPINStorage()

