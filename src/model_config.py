"""
============================================
TeleCode v0.1 - Model Configuration Module
============================================
Handles AI model selection and per-user preferences.

IMPORTANT: Cursor Pricing Model (2026)
--------------------------------------
As of June 2025, Cursor switched to API-based pricing:
- ALL frontier models are available on ALL plans (free and paid)
- Free tier (Hobby) has very limited usage credits
- Paid plans include monthly usage credits ($20/month for Pro)

Model Tier Classification:
- FREE: Models that are cost-effective enough to use within free tier limits
- PAID: Models that typically require a paid subscription for practical use

This is a PRACTICAL distinction based on usage costs, not official Cursor categorization.

Available Models:
- Claude Opus 4.5 (paid tier - expensive, requires paid plan)
- Claude Sonnet 4.5 (paid tier - moderate cost, requires paid plan)
- Claude Haiku 4.5 (free tier - lower cost, practical for free tier)
- Gemini 3 Flash (free tier - lower cost, large context)
- Gemini 3 Pro (paid tier - higher cost, requires paid plan)
- GPT models (paid tier - requires paid plan)
- Meta Llama 3.1 (free tier - open-source, typically free)
- xAI Grok (paid tier - requires paid plan)

Security: Model names are validated against whitelist.
============================================
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger("telecode.model_config")


class ModelTier(Enum):
    """
    Model pricing tier.
    
    Note: This is a PRACTICAL classification based on usage costs:
    - FREE: Cost-effective enough to use within Cursor's free tier limits
    - PAID: Typically requires a paid Cursor subscription for practical use
    
    All models are technically available on all Cursor plans, but free tier
    has very limited usage credits, making expensive models impractical.
    """
    FREE = "free"
    PAID = "paid"


@dataclass
class AIModel:
    """Definition of an AI model."""
    id: str                      # Internal identifier (e.g., "claude-opus-4.5")
    alias: str                   # Short alias (e.g., "opus")
    display_name: str            # Human-readable name (e.g., "Claude Opus 4.5")
    tier: ModelTier              # FREE or PAID
    context_window: str          # Context window size (e.g., "200K")
    description: str             # Brief description
    emoji: str                   # Display emoji


# ==========================================
# Available Models Registry
# ==========================================

AVAILABLE_MODELS: Dict[str, AIModel] = {
    "opus": AIModel(
        id="claude-opus-4.5",
        alias="opus",
        display_name="Claude Opus 4.5",
        tier=ModelTier.PAID,
        context_window="200K",
        description="Best reasoning, complex tasks",
        emoji="💎"
    ),
    "sonnet": AIModel(
        id="claude-sonnet-4.5",
        alias="sonnet",
        display_name="Claude Sonnet 4.5",
        tier=ModelTier.PAID,
        context_window="1M",
        description="Balanced, cost-effective",
        emoji="💰"
    ),
    "haiku": AIModel(
        id="claude-haiku-4.5",
        alias="haiku",
        display_name="Claude Haiku 4.5",
        tier=ModelTier.FREE,
        context_window="200K",
        description="Fast, simple tasks",
        emoji="✨"
    ),
    "gemini": AIModel(
        id="gemini-3-flash",
        alias="gemini",
        display_name="Gemini 3 Flash",
        tier=ModelTier.FREE,
        context_window="1M",
        description="Large context, fast",
        emoji="⚡"
    ),
    "geminipro": AIModel(
        id="gemini-3-pro",
        alias="geminipro",
        display_name="Gemini 3 Pro",
        tier=ModelTier.PAID,
        context_window="1M",
        description="Advanced reasoning, powerful",
        emoji="🚀"
    ),
    "gpt": AIModel(
        id="gpt-5.2",
        alias="gpt",
        display_name="GPT-5.2",
        tier=ModelTier.PAID,
        context_window="128K",
        description="Latest OpenAI, best reasoning",
        emoji="🧠"
    ),
    "codex": AIModel(
        id="gpt-5.2-codex",
        alias="codex",
        display_name="GPT-5.2 Codex",
        tier=ModelTier.PAID,
        context_window="128K",
        description="Code-optimized, specialized",
        emoji="💻"
    ),
    "llama": AIModel(
        id="llama-3.1",
        alias="llama",
        display_name="Meta Llama 3.1",
        tier=ModelTier.FREE,
        context_window="128K",
        description="Open-source, privacy-focused",
        emoji="🦙"
    ),
    "grok": AIModel(
        id="grok-beta",
        alias="grok",
        display_name="xAI Grok",
        tier=ModelTier.PAID,
        context_window="128K",
        description="Alternative reasoning model",
        emoji="🤖"
    ),
}

# Default model (Opus 4.5 as requested)
DEFAULT_MODEL_ALIAS = "opus"


def get_model_by_alias(alias: str) -> Optional[AIModel]:
    """
    Get a model by its alias.
    
    Args:
        alias: Model alias (e.g., "opus", "sonnet")
        
    Returns:
        AIModel or None if not found
    """
    return AVAILABLE_MODELS.get(alias.lower())


def get_model_by_id(model_id: str) -> Optional[AIModel]:
    """
    Get a model by its full ID.
    
    Args:
        model_id: Full model ID (e.g., "claude-opus-4.5")
        
    Returns:
        AIModel or None if not found
    """
    for model in AVAILABLE_MODELS.values():
        if model.id == model_id:
            return model
    return None


def validate_model(alias_or_id: str) -> Optional[AIModel]:
    """
    Validate and return a model by alias or ID.
    
    Security: Only returns models from the whitelist.
    
    Args:
        alias_or_id: Model alias or full ID
        
    Returns:
        AIModel or None if invalid
    """
    # Try alias first
    model = get_model_by_alias(alias_or_id)
    if model:
        return model
    
    # Try full ID
    return get_model_by_id(alias_or_id)


def get_all_models() -> List[AIModel]:
    """Get all available models."""
    return list(AVAILABLE_MODELS.values())


def get_models_by_tier(tier: ModelTier) -> List[AIModel]:
    """Get models filtered by tier."""
    return [m for m in AVAILABLE_MODELS.values() if m.tier == tier]


def get_default_model() -> AIModel:
    """
    Get the default model.
    
    Checks:
    1. Environment variable DEFAULT_MODEL
    2. Falls back to DEFAULT_MODEL_ALIAS (opus)
    """
    env_model = os.getenv("DEFAULT_MODEL", "").strip().lower()
    
    if env_model:
        model = validate_model(env_model)
        if model:
            return model
        logger.warning(f"Invalid DEFAULT_MODEL in env: {env_model}, using default")
    
    return AVAILABLE_MODELS[DEFAULT_MODEL_ALIAS]


# ==========================================
# User Preferences Storage
# ==========================================

class UserPreferences:
    """
    Per-user preferences storage.
    
    Stores preferences in JSON file within the project directory.
    Security: File is stored relative to script, not user-controlled path.
    """
    
    def __init__(self, storage_dir: Optional[Path] = None):
        """
        Initialize user preferences.
        
        Args:
            storage_dir: Directory to store preferences (defaults to user data directory)
        """
        if storage_dir is None:
            # Store in user data directory (works when installed in Program Files)
            from src.system_utils import get_user_data_dir
            storage_dir = get_user_data_dir()
        
        self.storage_dir = Path(storage_dir)
        self.prefs_file = self.storage_dir / "user_prefs.json"
        
        # Create directory if needed
        self.storage_dir.mkdir(exist_ok=True)
        
        # Load existing preferences
        self._prefs: Dict[str, Dict[str, Any]] = self._load()
    
    def _load(self) -> Dict[str, Dict[str, Any]]:
        """Load preferences from disk."""
        if not self.prefs_file.exists():
            return {}
        
        try:
            with open(self.prefs_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # Validate structure
            if not isinstance(data, dict):
                logger.warning("Invalid prefs file structure, resetting")
                return {}
            
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse prefs file: {e}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load prefs: {e}")
            return {}
    
    def _save(self) -> bool:
        """Save preferences to disk."""
        try:
            with open(self.prefs_file, "w", encoding="utf-8") as f:
                json.dump(self._prefs, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save prefs: {e}")
            return False
    
    def get_user_model(self, user_id: int) -> AIModel:
        """
        Get the selected model for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            User's selected model or default
        """
        user_key = str(user_id)
        
        if user_key not in self._prefs:
            return get_default_model()
        
        user_data = self._prefs[user_key]
        model_alias = user_data.get("model")
        
        if not model_alias:
            return get_default_model()
        
        model = validate_model(model_alias)
        if not model:
            logger.warning(f"Invalid stored model for user {user_id}: {model_alias}")
            return get_default_model()
        
        return model
    
    def set_user_model(self, user_id: int, model_alias: str) -> tuple[bool, str]:
        """
        Set the model for a user.
        
        Args:
            user_id: Telegram user ID
            model_alias: Model alias to set
            
        Returns:
            Tuple of (success, message)
        """
        # Validate model
        model = validate_model(model_alias)
        if not model:
            valid_aliases = ", ".join(AVAILABLE_MODELS.keys())
            return False, f"Invalid model. Available: {valid_aliases}"
        
        user_key = str(user_id)
        
        # Initialize user data if needed
        if user_key not in self._prefs:
            self._prefs[user_key] = {}
        
        # Check if model is actually changing
        old_model = self._prefs[user_key].get("model")
        model_changed = (old_model != model.alias)
        
        # Update model
        self._prefs[user_key]["model"] = model.alias
        
        # Track when model was changed (only if it actually changed)
        if model_changed:
            from datetime import datetime
            self._prefs[user_key]["model_changed_at"] = datetime.now().isoformat()
            logger.info(f"User {user_id} switched to model: {model.alias} (was: {old_model})")
        else:
            logger.info(f"User {user_id} model unchanged: {model.alias}")
        
        # Save to disk
        if not self._save():
            return False, "Failed to save preference"
        
        return True, f"Model changed to **{model.display_name}** {model.emoji}"
    
    def was_model_recently_changed(self, user_id: int, max_age_minutes: int = 5) -> bool:
        """
        Check if the user's model was recently changed.
        
        Args:
            user_id: Telegram user ID
            max_age_minutes: Maximum age in minutes to consider "recent" (default: 5)
            
        Returns:
            True if model was changed within the last max_age_minutes
        """
        user_key = str(user_id)
        
        if user_key not in self._prefs:
            return False
        
        user_data = self._prefs[user_key]
        model_changed_at_str = user_data.get("model_changed_at")
        
        if not model_changed_at_str:
            return False
        
        try:
            from datetime import datetime, timedelta
            model_changed_at = datetime.fromisoformat(model_changed_at_str)
            age = datetime.now() - model_changed_at
            return age <= timedelta(minutes=max_age_minutes)
        except (ValueError, TypeError) as e:
            logger.debug(f"Failed to parse model_changed_at timestamp: {e}")
            return False
    
    def get_user_data(self, user_id: int) -> Dict[str, Any]:
        """Get all preferences for a user."""
        return self._prefs.get(str(user_id), {})
    
    def clear_model_changed_flag(self, user_id: int) -> bool:
        """
        Clear the model_changed_at timestamp after model has been changed in Cursor.
        
        This prevents the system from trying to change the model again on subsequent prompts.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if flag was cleared, False if it didn't exist
        """
        user_key = str(user_id)
        
        if user_key not in self._prefs:
            return False
        
        if "model_changed_at" in self._prefs[user_key]:
            del self._prefs[user_key]["model_changed_at"]
            self._save()
            logger.info(f"Cleared model_changed_at flag for user {user_id}")
            return True
        
        return False


# ==========================================
# Singleton Instance
# ==========================================

_preferences: Optional[UserPreferences] = None


def get_preferences() -> UserPreferences:
    """Get the singleton UserPreferences instance."""
    global _preferences
    if _preferences is None:
        _preferences = UserPreferences()
    return _preferences


# ==========================================
# Formatting Helpers
# ==========================================

def format_model_list() -> str:
    """
    Format all available models for display.
    
    Returns:
        Formatted string listing all models
    """
    lines = ["📋 **Available Models**\n"]
    
    # Paid models
    paid_models = get_models_by_tier(ModelTier.PAID)
    if paid_models:
        lines.append("💎 **Paid Models:**")
        for model in paid_models:
            lines.append(
                f"  • `{model.alias}` - {model.display_name} "
                f"({model.context_window} context)"
            )
        lines.append("")
    
    # Free models
    free_models = get_models_by_tier(ModelTier.FREE)
    if free_models:
        lines.append("✨ **Free Models:**")
        for model in free_models:
            lines.append(
                f"  • `{model.alias}` - {model.display_name} "
                f"({model.context_window} context)"
            )
    
    return "\n".join(lines)


def format_model_status(model: AIModel, is_current: bool = False) -> str:
    """
    Format a single model for display.
    
    Args:
        model: The model to format
        is_current: Whether this is the current model
        
    Returns:
        Formatted string
    """
    current_marker = " ✅ CURRENT" if is_current else ""
    tier_emoji = "💎" if model.tier == ModelTier.PAID else "✨"
    
    return (
        f"{tier_emoji} **{model.display_name}** (`{model.alias}`){current_marker}\n"
        f"   {model.description}\n"
        f"   Context: {model.context_window}"
    )


def format_model_selection_message(current_model: AIModel) -> str:
    """
    Format the model selection menu message.
    
    Args:
        current_model: The user's current model
        
    Returns:
        Formatted message for /model command
    """
    lines = [
        "🤖 **Model Selection**\n",
        f"**Current:** `{current_model.id}` ({current_model.display_name}) {current_model.emoji}\n",
        "Select your AI model:\n",
    ]
    
    return "\n".join(lines)

