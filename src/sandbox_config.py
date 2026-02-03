"""
============================================
TeleCode Sandbox Configuration Manager
============================================
Manages multiple sandbox directories with persistence.

Supports:
- Multiple sandbox directories (up to 10)
- Current active sandbox tracking
- JSON-based persistence
- Backward compatibility with single DEV_ROOT
============================================
"""

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict
from .system_utils import get_user_data_dir

logger = logging.getLogger(__name__)

SANDBOX_CONFIG_FILE = "sandboxes.json"
MAX_SANDBOXES = 10


class SandboxConfig:
    """Manages multiple sandbox directory configuration."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize sandbox configuration manager.
        
        Args:
            config_path: Optional path to config file (defaults to user data dir)
        """
        if config_path is None:
            config_path = get_user_data_dir() / SANDBOX_CONFIG_FILE
        
        self.config_path = config_path
        self.sandboxes: List[str] = []
        self.current_index: int = 0
        
        # Load existing configuration
        self.load()
    
    def load(self) -> bool:
        """
        Load sandbox configuration from JSON file.
        
        Also checks .env for backward compatibility.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        # Try loading from JSON first
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.sandboxes = data.get('sandboxes', [])
                self.current_index = data.get('current_index', 0)
                
                # Validate
                if not self.sandboxes:
                    logger.warning("Sandbox config has no directories")
                    return False
                
                # Ensure current_index is valid
                if self.current_index >= len(self.sandboxes):
                    self.current_index = 0
                
                # Validate all directories exist
                valid_sandboxes = []
                for idx, sandbox in enumerate(self.sandboxes):
                    path = Path(sandbox)
                    if path.exists() and path.is_dir():
                        valid_sandboxes.append(sandbox)
                    else:
                        logger.warning(f"Sandbox directory does not exist: {sandbox}")
                        if idx == self.current_index:
                            self.current_index = 0
                
                if not valid_sandboxes:
                    logger.error("No valid sandbox directories found")
                    return False
                
                self.sandboxes = valid_sandboxes
                logger.info(f"Loaded {len(self.sandboxes)} sandbox directories")
                return True
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse sandbox config: {e}")
            except Exception as e:
                logger.error(f"Failed to load sandbox config: {e}")
        
        # Fallback: Try loading from .env (backward compatibility)
        return self._load_from_env()
    
    def _load_from_env(self) -> bool:
        """
        Load single DEV_ROOT from .env file (backward compatibility).
        
        Returns:
            True if loaded, False otherwise
        """
        from dotenv import load_dotenv
        import os
        
        # Try user data directory first
        user_data_dir = get_user_data_dir()
        env_path = user_data_dir / ".env"
        if not env_path.exists():
            env_path = Path(".env")
        
        if env_path.exists():
            load_dotenv(env_path)
            dev_root = os.getenv("DEV_ROOT")
            
            if dev_root:
                path = Path(dev_root)
                if path.exists() and path.is_dir():
                    self.sandboxes = [str(path.resolve())]
                    self.current_index = 0
                    logger.info(f"Loaded DEV_ROOT from .env: {dev_root}")
                    # Save to JSON for future use
                    self.save()
                    return True
        
        return False
    
    def save(self) -> bool:
        """
        Save sandbox configuration to JSON file.
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'sandboxes': self.sandboxes,
                'current_index': self.current_index,
                'version': '1.0'
            }
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {len(self.sandboxes)} sandbox directories to {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save sandbox config: {e}")
            return False
    
    def add_sandbox(self, path: str) -> tuple[bool, str]:
        """
        Add a new sandbox directory.
        
        Args:
            path: Directory path to add
            
        Returns:
            Tuple of (success, message)
        """
        # Validate path
        try:
            path_obj = Path(path).resolve()
        except Exception as e:
            return False, f"Invalid path: {e}"
        
        if not path_obj.exists():
            return False, f"Directory does not exist: {path}"
        
        if not path_obj.is_dir():
            return False, f"Path is not a directory: {path}"
        
        path_str = str(path_obj)
        
        # Check if already exists
        if path_str in self.sandboxes:
            return False, f"Sandbox already exists: {path_obj.name}"
        
        # Check limit
        if len(self.sandboxes) >= MAX_SANDBOXES:
            return False, f"Maximum {MAX_SANDBOXES} sandboxes allowed"
        
        # Add to list
        self.sandboxes.append(path_str)
        
        # If this is the first sandbox, set it as current
        if len(self.sandboxes) == 1:
            self.current_index = 0
        
        # Save
        if self.save():
            return True, f"Added sandbox: {path_obj.name}"
        else:
            # Rollback
            self.sandboxes.pop()
            return False, "Failed to save configuration"
    
    def remove_sandbox(self, index: int) -> tuple[bool, str]:
        """
        Remove a sandbox directory by index.
        
        Args:
            index: Index of sandbox to remove
            
        Returns:
            Tuple of (success, message)
        """
        if index < 0 or index >= len(self.sandboxes):
            return False, f"Invalid index: {index}"
        
        if len(self.sandboxes) <= 1:
            return False, "Cannot remove the last sandbox. Add another first."
        
        removed_path = Path(self.sandboxes[index]).name
        self.sandboxes.pop(index)
        
        # Adjust current_index if needed
        if self.current_index >= len(self.sandboxes):
            self.current_index = len(self.sandboxes) - 1
        elif self.current_index > index:
            self.current_index -= 1
        
        # Save
        if self.save():
            return True, f"Removed sandbox: {removed_path}"
        else:
            # Rollback (would need to restore, but for simplicity just return error)
            return False, "Failed to save configuration"
    
    def set_current(self, index: int) -> tuple[bool, str]:
        """
        Set the current active sandbox by index.
        
        Args:
            index: Index of sandbox to activate
            
        Returns:
            Tuple of (success, message)
        """
        if index < 0 or index >= len(self.sandboxes):
            return False, f"Invalid index: {index}"
        
        old_index = self.current_index
        self.current_index = index
        
        if self.save():
            path = Path(self.sandboxes[index])
            return True, f"Switched to sandbox: {path.name}"
        else:
            # Rollback
            self.current_index = old_index
            return False, "Failed to save configuration"
    
    def get_current(self) -> Optional[str]:
        """Get the current active sandbox path."""
        if not self.sandboxes:
            return None
        
        if self.current_index >= len(self.sandboxes):
            self.current_index = 0
        
        return self.sandboxes[self.current_index]
    
    def get_all(self) -> List[str]:
        """Get all sandbox paths."""
        return self.sandboxes.copy()
    
    def get_info(self) -> Dict:
        """Get configuration info for display."""
        current_path = self.get_current()
        current_name = Path(current_path).name if current_path else "None"
        
        return {
            'total': len(self.sandboxes),
            'current_index': self.current_index,
            'current_path': current_path,
            'current_name': current_name,
            'sandboxes': [
                {
                    'index': idx,
                    'path': path,
                    'name': Path(path).name,
                    'is_current': idx == self.current_index
                }
                for idx, path in enumerate(self.sandboxes)
            ]
        }


def get_sandbox_config() -> SandboxConfig:
    """Get the global sandbox configuration instance."""
    return SandboxConfig()

