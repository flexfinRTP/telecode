"""
============================================
TeleCode v0.1 - Main Telegram Bot
============================================
The core bot that handles all Telegram commands.

Commands:
  /start    - Welcome message and status
  /help     - List available commands
  /status   - Git status of current directory
  /diff     - Show git diff of changes
  /push     - Push committed changes to remote
  /pull     - Pull latest changes from remote
  /commit   - Stage and commit all changes
  /revert   - Discard all uncommitted changes
  /ai       - Execute AI prompt via Cursor CLI
    /ai <prompt>         - Send prompt to Cursor
    /ai accept           - Accept AI changes (Ctrl+Enter)
    /ai reject           - Reject AI changes (Escape)
    /ai continue <prompt>- Follow-up prompt
    /ai stop             - Clear session
    /ai status           - Check agent status
  /ls       - List directory contents
  /read     - Read file contents
  /log      - Show recent git commits
  /info     - System and bot information

SECURITY: All commands are authenticated via Telegram User ID
          and sandboxed to DEV_ROOT directory.
          
AUDIT: Reviewed 2026-02 - Rate limiting added, input sanitization
============================================
"""

import os
import sys
import io
import logging
import asyncio
import time
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional
from collections import defaultdict

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    filters
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .security import (
    SecuritySentinel,
    create_sentinel_from_env,
    SecurityError
)
from .cli_wrapper import CLIWrapper
from .voice_processor import VoiceProcessor, download_telegram_voice
from .system_utils import (
    SleepPreventer,
    format_system_status,
    ScreenLockDetector
)
from .model_config import (
    get_preferences,
    validate_model,
    format_model_list,
    format_model_selection_message,
    AVAILABLE_MODELS,
    ModelTier
)
from .cursor_agent import CursorAgentBridge, get_agent_for_workspace, AgentState, CursorStatus

logger = logging.getLogger("telecode.bot")

# Maximum message length for Telegram
MAX_MESSAGE_LENGTH = 4096

# Conversation states for /create command
CREATE_AWAITING_NAME, CREATE_AWAITING_CONFIRM = range(2)

# Conversation states for /commit command
COMMIT_AWAITING_MESSAGE = 2


class CommandRateLimiter:
    """
    Rate limiter for bot commands.
    
    SEC-004: Prevents command spam and DoS attacks.
    """
    
    def __init__(self, max_commands_per_minute: int = 30):
        self.max_commands = max_commands_per_minute
        self.command_times: dict[int, list] = defaultdict(list)
    
    def is_allowed(self, user_id: int) -> bool:
        """Check if user can execute a command."""
        now = time.time()
        window = 60  # 1 minute window
        
        # Clean old entries
        self.command_times[user_id] = [
            t for t in self.command_times[user_id]
            if now - t < window
        ]
        
        # Check rate
        if len(self.command_times[user_id]) >= self.max_commands:
            logger.warning(f"Rate limit reached for user {user_id}")
            return False
        
        self.command_times[user_id].append(now)
        return True


def require_auth(func):
    """
    Auth decorator that enforces:
    1. User authentication via SecuritySentinel
    2. Command rate limiting
    3. Updates system tray with last command
    """
    async def wrapper(self, update, context, *args, **kwargs):
        user_id = update.effective_user.id if update.effective_user else None
        
        if user_id is None:
            logger.warning("Received update without user ID")
            return None
        
        try:
            # SEC: Authenticate user
            self.sentinel.validate_user(user_id)
            
            # SEC-004: Check rate limit
            if not self.rate_limiter.is_allowed(user_id):
                # Silently rate limit - don't inform attacker
                logger.warning(f"Rate limited user {user_id}")
                return None
            
            # Update system tray with command info
            if hasattr(self, '_update_tray_command'):
                cmd_text = update.message.text if update.message else "callback"
                self._update_tray_command(cmd_text[:50])
            
            return await func(self, update, context, *args, **kwargs)
        except Exception as e:
            # SEC-003: Don't log detailed exception info for security
            logger.warning(f"Auth failed for user {user_id}")
            return None
    
    return wrapper


class TeleCodeBot:
    """
    The TeleCode Telegram Bot.
    
    Provides secure remote access to Git and Cursor CLI operations.
    All operations are sandboxed and authenticated.
    """
    
    def __init__(self, token: str, sentinel: SecuritySentinel):
        """
        Initialize the bot.
        
        Args:
            token: Telegram Bot API token
            sentinel: SecuritySentinel for authentication and sandboxing
        """
        self.token = token
        self.sentinel = sentinel
        self.cli = CLIWrapper(sentinel)
        self.voice = VoiceProcessor()
        self.sleep_preventer = SleepPreventer()
        self.tray = None  # System tray icon
        self._stop_requested = False
        
        # SEC-004: Command rate limiter
        self.rate_limiter = CommandRateLimiter(max_commands_per_minute=30)
        
        # Model preferences (per-user)
        self.user_prefs = get_preferences()
        
        # Build the application
        self.app = Application.builder().token(token).build()
        
        # Register handlers
        self._register_handlers()
        
        logger.info("TeleCodeBot initialized")
    
    def _register_handlers(self):
        """Register all command and message handlers."""
        
        # Create project conversation handler (must be registered first)
        create_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("create", self._cmd_create_start)],
            states={
                CREATE_AWAITING_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self._cmd_create_name),
                    CommandHandler("cancel", self._cmd_create_cancel),
                    # Allow /create to restart the conversation if called again
                    CommandHandler("create", self._cmd_create_start),
                ],
                CREATE_AWAITING_CONFIRM: [
                    CallbackQueryHandler(self._cmd_create_confirm, pattern="^create_confirm$"),
                    CallbackQueryHandler(self._cmd_create_cancel_btn, pattern="^create_cancel$"),
                    CommandHandler("cancel", self._cmd_create_cancel),
                    # Allow /create to restart the conversation if called again
                    CommandHandler("create", self._cmd_create_start),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self._cmd_create_cancel),
                # Allow /create as fallback to restart conversation
                CommandHandler("create", self._cmd_create_start),
            ],
            per_user=True,
            per_chat=True,
        )
        self.app.add_handler(create_conv_handler)
        
        # Commit conversation handler (must be registered before text handler)
        commit_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("commit", self._cmd_commit)],
            states={
                COMMIT_AWAITING_MESSAGE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self._cmd_commit_message),
                    CommandHandler("cancel", self._cmd_commit_cancel),
                    # Allow /commit to restart the conversation if called again
                    CommandHandler("commit", self._cmd_commit),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self._cmd_commit_cancel),
                # Allow /commit as fallback to restart conversation
                CommandHandler("commit", self._cmd_commit),
            ],
            per_user=True,
            per_chat=True,
        )
        self.app.add_handler(commit_conv_handler)
        
        handlers = [
            # Core commands
            CommandHandler("start", self._cmd_start),
            CommandHandler("help", self._cmd_help),
            CommandHandler("info", self._cmd_info),
            
            # Git commands
            CommandHandler("status", self._cmd_status),
            CommandHandler("diff", self._cmd_diff),
            CommandHandler("push", self._cmd_push),
            CommandHandler("pull", self._cmd_pull),
            CommandHandler("revert", self._cmd_revert),
            CommandHandler("log", self._cmd_log),
            CommandHandler("branch", self._cmd_branch),
            
            # File/Navigation commands
            CommandHandler("ls", self._cmd_ls),
            CommandHandler("read", self._cmd_read),
            CommandHandler("pwd", self._cmd_pwd),
            
            # Sandbox management commands
            CommandHandler("sandbox", self._cmd_sandbox),
            CommandHandler("sandboxes", self._cmd_sandboxes),
            
            # AI commands
            CommandHandler("ai", self._cmd_ai),
            
            # Cursor control command
            CommandHandler("cursor", self._cmd_cursor),
            
            # Model selection commands
            CommandHandler("model", self._cmd_model),
            CommandHandler("models", self._cmd_models),
            
            # Lock PIN management commands
            CommandHandler("pin", self._cmd_pin),
            
            # Model selection callback handler
            CallbackQueryHandler(self._cmd_model_callback, pattern="^model_"),
            
            # Diff expansion callback handler
            CallbackQueryHandler(self._cmd_diff_callback, pattern="^diff_"),
            
            # AI control callback handler
            CallbackQueryHandler(self._cmd_ai_callback, pattern="^ai_"),
            
            # Cursor control callback handler (open/status)
            CallbackQueryHandler(self._cmd_cursor_callback, pattern="^cursor_"),
            
            # Sandbox switch callback handler
            CallbackQueryHandler(self._cmd_sandbox_callback, pattern="^sandbox_"),
            
            # Voice message handler
            MessageHandler(filters.VOICE, self._handle_voice),
            
            # Plain text as AI prompt
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text),
        ]
        
        for handler in handlers:
            self.app.add_handler(handler)
    
    async def _set_commands(self):
        """Set the bot commands visible in Telegram."""
        commands = [
            BotCommand("start", "Show welcome message"),
            BotCommand("help", "List available commands"),
            BotCommand("create", "Create new project"),
            BotCommand("status", "Git status"),
            BotCommand("diff", "Show changes (git diff)"),
            BotCommand("push", "Push to remote"),
            BotCommand("pull", "Pull from remote"),
            BotCommand("commit", "Commit all changes"),
            BotCommand("revert", "Discard changes"),
            BotCommand("ai", "Run AI prompt"),
            BotCommand("cursor", "Check/open Cursor IDE"),
            BotCommand("model", "Select AI model"),
            BotCommand("models", "List available models"),
            BotCommand("cd", "Change directory"),
            BotCommand("ls", "List files"),
            BotCommand("log", "Recent commits"),
            BotCommand("info", "System info"),
            BotCommand("pin", "View or set lock PIN"),
        ]
        await self.app.bot.set_my_commands(commands)
    
    def _truncate_message(self, text: str) -> str:
        """Truncate message to Telegram's limit."""
        if len(text) <= MAX_MESSAGE_LENGTH:
            return text
        return text[:MAX_MESSAGE_LENGTH - 100] + "\n\n... (truncated)"
    
    async def _send_ocr_as_document(
        self,
        message,
        text: str,
        filename: str = "cursor_output.txt",
        caption: str = "📝 **AI Output Text**"
    ):
        """
        Send OCR extracted text as a document file for full scrollability.
        
        Telegram messages are limited to 4096 chars, but document uploads
        allow unlimited text that users can scroll through.
        
        Args:
            message: The Telegram message to reply to
            text: The text content to send as document
            filename: Name for the document file
            caption: Caption for the document
        """
        try:
            # Create in-memory text file
            text_bytes = text.encode('utf-8')
            text_io = io.BytesIO(text_bytes)
            text_io.name = filename
            
            # Send as document
            await message.reply_document(
                document=text_io,
                filename=filename,
                caption=self._truncate_message(caption)[:1024],
                parse_mode="Markdown"
            )
            logger.info(f"Sent OCR text as document: {len(text)} chars")
            
        except Exception as e:
            logger.warning(f"Failed to send OCR document: {e}")
            # Fallback: send truncated message
            truncated = text[:3500] + "\n\n... (text too long, showing first 3500 chars)"
            await message.reply_text(
                f"📝 **Cursor AI Output:**\n\n{truncated}",
                parse_mode="Markdown"
            )
    
    def _format_result(self, title: str, result, show_command: bool = False) -> str:
        """Format a CLI result for display."""
        parts = [f"**{title}**"]
        
        if show_command:
            parts.append(f"```\n{result.command}\n```")
        
        if result.success:
            if result.stdout.strip():
                # SEC-005: Sanitize output to remove any leaked sensitive info
                sanitized_output = self._sanitize_output(result.stdout.strip())
                parts.append(f"```\n{sanitized_output}\n```")
            else:
                parts.append("_(no output)_")
        else:
            # SEC-005: Sanitize error messages
            sanitized_error = self._sanitize_output(result.stderr.strip())
            parts.append(f"❌ Error:\n```\n{sanitized_error}\n```")
        
        return "\n".join(parts)
    
    def _sanitize_output(self, text: str) -> str:
        """
        Sanitize output to remove sensitive information.
        
        SEC-005: Prevents accidental leakage of:
        - Tokens/API keys
        - Full file paths (show relative only)
        - System usernames
        - Internal error details
        """
        import re
        
        if not text:
            return text
        
        # Redact token-like patterns
        text = re.sub(r'\d{8,10}:[A-Za-z0-9_-]{35,40}', '[REDACTED_TOKEN]', text)
        
        # Redact API key patterns
        text = re.sub(r'[A-Za-z0-9]{32,64}', lambda m: m.group()[:4] + '***' + m.group()[-4:] if len(m.group()) > 20 else m.group(), text)
        
        # Redact full Windows paths with usernames
        text = re.sub(
            r'[A-Za-z]:\\Users\\[^\\]+\\',
            lambda m: m.group().split('\\')[0] + '\\Users\\[USER]\\',
            text
        )
        
        # Redact Unix home paths
        text = re.sub(r'/home/[^/]+/', '/home/[USER]/', text)
        text = re.sub(r'/Users/[^/]+/', '/Users/[USER]/', text)
        
        # Limit output length
        if len(text) > 3000:
            text = text[:3000] + "\n... (truncated)"
        
        return text
    
    # ==========================================
    # Core Commands
    # ==========================================
    
    @require_auth
    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome message and quick status."""
        try:
            user_id = update.effective_user.id if update.effective_user else None
            if not user_id:
                logger.warning("Received /start without user ID")
                await update.message.reply_text("❌ Error: Could not identify user.")
                return
            
            # Log command (this should always work)
            try:
                self.sentinel.log_command(user_id, "/start")
            except Exception as e:
                logger.warning(f"Failed to log /start command: {e}")
            
            # Virtual Display mode - monitor off, session active (not locked)
            lock_status = "🖥️ Display Off"
            
            # Get user's selected model (with fallback if it fails)
            try:
                current_model = self.user_prefs.get_user_model(user_id)
                model_display = f"{current_model.emoji} {current_model.display_name}"
            except Exception as e:
                logger.warning(f"Failed to get user model for /start: {e}")
                model_display = "🤖 Default"
            
            welcome = f"""
🚀 **Welcome to TeleCode v0.1**

Your secure Telegram-to-Terminal bridge is active!

📂 **Sandbox:** `{self.sentinel.dev_root.name}`
🖥️ **Screen:** {lock_status}
🎤 **Voice:** {"✅ Enabled" if self.voice.is_available else "❌ Disabled"}
🤖 **Model:** {model_display}

Type /help to see available commands.
Use /model to change AI model.
"""
            await update.message.reply_text(welcome, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error in /start command: {e}", exc_info=True)
            try:
                await update.message.reply_text(
                    "🚀 **Welcome to TeleCode!**\n\n"
                    "Type /help to see available commands.",
                    parse_mode="Markdown"
                )
            except Exception:
                logger.error("Failed to send error fallback message")
    
    @require_auth
    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available commands."""
        self.sentinel.log_command(update.effective_user.id, "/help")
        
        # Get current model for display
        user_id = update.effective_user.id
        current_model = self.user_prefs.get_user_model(user_id)
        
        help_text = f"""
📋 **TeleCode Commands**

**Project:**
  /create - Create new project 🆕
    _(Interactive: mkdir → git init → open Cursor)_

**Git Operations:**
  /status - Current git status
  /diff - Show uncommitted changes
  /push - Push to remote
  /pull - Pull from remote
  /commit [msg] - Commit all changes
  /revert - Discard all changes ⚠️
  /log - Recent commits
  /branch - List branches

**Navigation:**
  /ls [path] - List files
  /read [file] - Read file contents
  /pwd - Show current path

**Sandbox Management:** 📂
  /sandbox - Switch sandbox directory
  /sandboxes - List all sandbox directories
  _(Switch sandboxes to work in different project folders)_

**AI Control:** 🤖
  /ai [prompt] - Send prompt to Cursor
  /ai accept - Accept AI changes (Ctrl+Enter)
  /ai reject - Reject AI changes (Escape)
  /ai continue [prompt] - Follow-up
  /ai stop - Clear session
  /ai status - Check state
  /model - Select AI model
  /models - List available models
  /cursor - Check Cursor status/open 💻
  _(or just send text/voice)_

**System:**
  /info - System status
  /help - This message

**Lock PIN (Windows):** 🔒
  /pin - View current PIN
  /pin set <pin> - Set PIN (can use Windows password)
  💡 Tip: Use Windows password for easy remembering!

📂 **Current Sandbox:** `{self.sentinel.dev_root.name}`
🤖 **Model:** `{current_model.alias}` ({current_model.display_name})
"""
        await update.message.reply_text(help_text, parse_mode="Markdown")
    
    @require_auth
    async def _cmd_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show system and bot information."""
        self.sentinel.log_command(update.effective_user.id, "/info")
        
        # Get user's selected model
        user_id = update.effective_user.id
        current_model = self.user_prefs.get_user_model(user_id)
        
        info = format_system_status()
        # Wrap workspace info in code block to avoid Markdown parsing issues with git status (## main)
        workspace_info = self.cli.get_current_info()
        info += f"\n\n📂 **Workspace**\n```\n{workspace_info}\n```"
        info += f"\n\n🤖 **AI Model**\n"
        info += f"  {current_model.emoji} {current_model.display_name}\n"
        info += f"  Context: {current_model.context_window}\n"
        info += f"  Tier: {'💎 Paid' if current_model.tier == ModelTier.PAID else '✨ Free'}"
        info += f"\n\n{self.voice.get_status()}"
        
        await update.message.reply_text(info, parse_mode="Markdown")
    
    @require_auth
    async def _cmd_pin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pin command - view or set lock PIN."""
        if not sys.platform == "win32":
            await update.message.reply_text(
                "❌ Lock PIN is only available on Windows.\n\n"
                "Use `/pin` to view current PIN\n"
                "Use `/pin set <pin>` to set a new PIN"
            )
            return
        
        try:
            from .lock_pin_storage import get_lock_pin_storage
            from .custom_lock import set_lock_pin
            
            storage = get_lock_pin_storage()
            args = context.args or []
            
            if not args:
                # View PIN - show masked
                pin = storage.retrieve_pin()
                password = storage.retrieve_password()
                
                if pin:
                    masked = "*" * (len(pin) - 2) + pin[-2:] if len(pin) > 2 else "****"
                    msg = f"🔒 **Current PIN:** `{masked}`"
                elif password:
                    msg = "🔒 **Password set** (Windows password)\n\n"
                    msg += "💡 Password is stored securely and cannot be displayed."
                else:
                    msg = "🔒 **No PIN set**\n\n"
                    msg += "Set one with: `/pin set <pin>`\n\n"
                    msg += "💡 **Tip:** Use your Windows password for easy remembering!"
                
                await update.message.reply_text(msg, parse_mode="Markdown")
                return
            
            command = args[0].lower()
            
            if command == "set":
                if len(args) < 2:
                    await update.message.reply_text(
                        "❌ Usage: `/pin set <pin>`\n\n"
                        "Example: `/pin set 1234`\n\n"
                        "💡 **Tip:** Use your Windows password for easy remembering!"
                    )
                    return
                
                # Set PIN (can be password too)
                pin = args[1]
                
                if len(pin) < 4:
                    await update.message.reply_text(
                        "❌ PIN must be at least 4 characters.\n\n"
                        "Example: `/pin set 1234`"
                    )
                    return
                
                # Store as PIN (user can use Windows password as PIN)
                success, message = storage.store_pin(pin)
                
                if success:
                    set_lock_pin(pin)
                    await update.message.reply_text(
                        f"✅ **PIN set successfully!**\n\n"
                        f"Your PIN is now stored securely.\n"
                        f"It will be required when unlocking the display.\n\n"
                        f"💡 **Tip:** You can use your Windows password as the PIN!"
                    )
                else:
                    await update.message.reply_text(f"❌ Failed to set PIN: {message}")
            else:
                await update.message.reply_text(
                    "❌ Unknown command. Use:\n"
                    "• `/pin` - View current PIN\n"
                    "• `/pin set <pin>` - Set PIN"
                )
                
        except Exception as e:
            logger.error(f"PIN command failed: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Error: {e}")
    
    # ==========================================
    # Git Commands
    # ==========================================
    
    @require_auth
    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Git status command."""
        self.sentinel.log_command(update.effective_user.id, "/status")
        
        result = self.cli.git_status()
        message = self._format_result("📊 Git Status", result)
        await update.message.reply_text(self._truncate_message(message), parse_mode="Markdown")
    
    @require_auth
    async def _cmd_diff(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Git diff command with expandable preview."""
        self.sentinel.log_command(update.effective_user.id, "/diff")
        
        # Check if "full" argument was provided
        show_full = context.args and context.args[0].lower() == "full"
        
        if show_full:
            # Show full diff directly
            diff_result = self.cli.git_diff(stat_only=False)
            if diff_result.success and diff_result.stdout.strip():
                content = diff_result.stdout.strip()
                if len(content) > 3500:
                    content = content[:3500] + "\n\n... (truncated)"
                message = f"📖 **Full Diff:**\n\n```diff\n{content}\n```"
            else:
                message = "✅ No uncommitted changes"
            await update.message.reply_text(self._truncate_message(message), parse_mode="Markdown")
            return
        
        # Show stat summary with expand button
        stat_result = self.cli.git_diff(stat_only=True)
        
        if stat_result.success and stat_result.stdout.strip():
            message = f"📊 **Changes Summary:**\n```\n{stat_result.stdout.strip()}\n```"
            
            # Build inline keyboard with expand and git action buttons
            keyboard = [
                [InlineKeyboardButton("📖 View Full Diff", callback_data="diff_full")],
                [
                    InlineKeyboardButton("💾 Git Commit", callback_data="diff_keep"),
                    InlineKeyboardButton("🗑️ Git Restore", callback_data="diff_undo"),
                ],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                self._truncate_message(message), 
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        elif stat_result.success:
            await update.message.reply_text("✅ No uncommitted changes", parse_mode="Markdown")
        else:
            message = self._format_result("📝 Git Diff", stat_result)
            await update.message.reply_text(self._truncate_message(message), parse_mode="Markdown")
    
    @require_auth
    async def _cmd_push(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Git push command."""
        self.sentinel.log_command(update.effective_user.id, "/push")
        
        await update.message.reply_text("⏳ Pushing to remote...")
        result = self.cli.git_push()
        
        if result.success:
            message = "✅ **Push Successful!**\n"
            if result.stdout.strip():
                message += f"```\n{result.stdout.strip()}\n```"
        else:
            message = self._format_result("❌ Push Failed", result)
        
        await update.message.reply_text(self._truncate_message(message), parse_mode="Markdown")
    
    @require_auth
    async def _cmd_pull(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Git pull command."""
        self.sentinel.log_command(update.effective_user.id, "/pull")
        
        await update.message.reply_text("⏳ Pulling from remote...")
        result = self.cli.git_pull()
        message = self._format_result("📥 Git Pull", result)
        await update.message.reply_text(self._truncate_message(message), parse_mode="Markdown")
    
    @require_auth
    async def _cmd_commit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stage and commit all changes."""
        self.sentinel.log_command(update.effective_user.id, "/commit")
        
        # Get commit message from args
        args = context.args
        if args:
            # User provided message in command - use it directly with timestamp
            user_msg = " ".join(args)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            commit_msg = f"{user_msg} - TeleCode: {timestamp}"
            
            # Stage all changes
            add_result = self.cli.git_add_all()
            if not add_result.success:
                message = self._format_result("❌ Failed to stage changes", add_result)
                await update.message.reply_text(message, parse_mode="Markdown")
                return ConversationHandler.END
            
            # Commit
            commit_result = self.cli.git_commit(commit_msg)
            if commit_result.success:
                message = f"✅ **Changes Committed!**\n\n📝 Message: _{commit_msg}_"
            else:
                message = self._format_result("❌ Commit Failed", commit_result)
            
            await update.message.reply_text(self._truncate_message(message), parse_mode="Markdown")
            return ConversationHandler.END
        else:
            # No message provided - prompt user with list of changed files
            # Get list of changed files
            status_result = self.cli.git_status()
            changed_files = []
            
            if status_result.success and status_result.stdout:
                # Parse git status --short output
                # Format: " M file.py" or "A  newfile.py" or "?? untracked.txt"
                # Status is 2 chars, then space(s), then filename
                for line in status_result.stdout.strip().split('\n'):
                    line = line.strip()
                    if not line or line.startswith('##'):
                        continue  # Skip branch info line
                    # Extract filename (everything after the status code and space)
                    # Status codes are 2 characters, then space(s)
                    if len(line) >= 4:
                        # Find first space after status code (position 2)
                        parts = line.split(None, 1)  # Split on whitespace, max 1 split
                        if len(parts) >= 2:
                            filename = parts[1].strip()
                            # Handle renamed files (old -> new)
                            if ' -> ' in filename:
                                filename = filename.split(' -> ')[1]
                            changed_files.append(filename)
            
            # Build message with file list
            files_text = ""
            if changed_files:
                files_text = "\n\n**Changed files:**\n"
                for i, filename in enumerate(changed_files[:20], 1):  # Limit to 20 files
                    files_text += f"  {i}. `{filename}`\n"
                if len(changed_files) > 20:
                    files_text += f"  ... and {len(changed_files) - 20} more files\n"
            else:
                files_text = "\n\n_No changes detected._\n"
            
            message = (
                "📝 **Enter Commit Message**\n\n"
                "Please type your commit message:"
                f"{files_text}\n"
                "_The timestamp will be added automatically._\n"
                "_(Type /cancel to abort)_"
            )
            await update.message.reply_text(message, parse_mode="Markdown")
            return COMMIT_AWAITING_MESSAGE
    
    @require_auth
    async def _cmd_commit_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle commit message input from user."""
        user_msg = update.message.text.strip()
        
        if not user_msg:
            await update.message.reply_text(
                "❌ **Empty message!**\n\n"
                "Please enter a commit message or /cancel:",
                parse_mode="Markdown"
            )
            return COMMIT_AWAITING_MESSAGE
        
        # Combine user message with timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        commit_msg = f"{user_msg} - TeleCode: {timestamp}"
        
        self.sentinel.log_command(update.effective_user.id, f"/commit {user_msg}")
        
        # Stage all changes
        await update.message.reply_text("⏳ Staging changes...")
        add_result = self.cli.git_add_all()
        if not add_result.success:
            message = self._format_result("❌ Failed to stage changes", add_result)
            await update.message.reply_text(message, parse_mode="Markdown")
            return ConversationHandler.END
        
        # Commit
        await update.message.reply_text("⏳ Committing changes...")
        commit_result = self.cli.git_commit(commit_msg)
        if commit_result.success:
            message = f"✅ **Changes Committed!**\n\n📝 Message: _{commit_msg}_"
        else:
            message = self._format_result("❌ Commit Failed", commit_result)
        
        await update.message.reply_text(self._truncate_message(message), parse_mode="Markdown")
        return ConversationHandler.END
    
    @require_auth
    async def _cmd_commit_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel commit operation."""
        await update.message.reply_text("❌ Commit cancelled.", parse_mode="Markdown")
        return ConversationHandler.END
    
    @require_auth
    async def _cmd_revert(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Discard all uncommitted changes (DANGEROUS - requires confirmation)."""
        self.sentinel.log_command(update.effective_user.id, "/revert")
        
        # SEC-004: Dangerous operation confirmation
        # Check if this is a confirmed revert
        if context.args and context.args[0].upper() == "CONFIRM":
            # User confirmed - execute revert
            result = self.cli.git_restore()
            if result.success:
                message = "⚠️ **All uncommitted changes have been discarded!**"
            else:
                message = self._format_result("❌ Revert Failed", result)
            
            await update.message.reply_text(message, parse_mode="Markdown")
        else:
            # Show confirmation warning
            warning = (
                "⚠️ **DANGEROUS OPERATION**\n\n"
                "This will **permanently discard** ALL uncommitted changes!\n\n"
                "📁 Affected directory: `{}`\n\n"
                "**This cannot be undone!**\n\n"
                "To confirm, type:\n"
                "`/revert CONFIRM`"
            ).format(self.cli.current_dir.name)
            
            await update.message.reply_text(warning, parse_mode="Markdown")
    
    @require_auth
    async def _cmd_log(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show recent git commits."""
        self.sentinel.log_command(update.effective_user.id, "/log")
        
        count = 5
        if context.args:
            try:
                count = int(context.args[0])
            except ValueError:
                pass
        
        result = self.cli.git_log(count)
        message = self._format_result(f"📜 Recent Commits (last {count})", result)
        await update.message.reply_text(self._truncate_message(message), parse_mode="Markdown")
    
    @require_auth
    async def _cmd_branch(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List git branches."""
        self.sentinel.log_command(update.effective_user.id, "/branch")
        
        result = self.cli.git_branch()
        message = self._format_result("🔀 Branches", result)
        await update.message.reply_text(self._truncate_message(message), parse_mode="Markdown")
    
    # ==========================================
    # Navigation Commands
    # ==========================================
    
    @require_auth
    async def _cmd_ls(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List directory contents."""
        path = " ".join(context.args) if context.args else None
        self.sentinel.log_command(update.effective_user.id, f"/ls {path or ''}")
        
        result = self.cli.list_directory(path)
        
        header = f"📂 Contents of `{path or self.cli.current_dir.name}`"
        if result.success:
            message = f"{header}\n\n{result.stdout}"
        else:
            message = f"❌ {result.stderr}"
        
        await update.message.reply_text(self._truncate_message(message), parse_mode="Markdown")
    
    @require_auth
    async def _cmd_read(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Read file contents."""
        if not context.args:
            await update.message.reply_text(
                "Usage: /read [filepath]\n\nExample: /read README.md",
                parse_mode="Markdown"
            )
            return
        
        path = " ".join(context.args)
        self.sentinel.log_command(update.effective_user.id, f"/read {path}")
        
        result = self.cli.read_file(path)
        
        if result.success:
            message = f"📄 **{path}**\n\n```\n{result.stdout}\n```"
        else:
            message = f"❌ {result.stderr}"
        
        await update.message.reply_text(self._truncate_message(message), parse_mode="Markdown")
    
    @require_auth
    @require_auth
    async def _cmd_sandbox(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Switch to a different sandbox directory."""
        from src.sandbox_config import get_sandbox_config
        
        sandbox_config = get_sandbox_config()
        info = sandbox_config.get_info()
        
        if not context.args:
            # Show list of sandboxes with current marked
            message = f"📂 **Sandbox Directories** ({info['total']})\n\n"
            
            buttons = []
            for sandbox in info['sandboxes']:
                current_marker = " ✅" if sandbox['is_current'] else ""
                label = f"{sandbox['name']}{current_marker}"
                buttons.append([InlineKeyboardButton(
                    label,
                    callback_data=f"sandbox_switch_{sandbox['index']}"
                )])
            
            keyboard = InlineKeyboardMarkup(buttons)
            
            message += f"**Current:** {info['current_name']}\n\n"
            message += "Select a sandbox to switch to:"
            
            await update.message.reply_text(message, parse_mode="Markdown", reply_markup=keyboard)
            return
        
        # Switch by index or name
        arg = " ".join(context.args)
        
        # Try as index first
        try:
            index = int(arg)
            success, msg = sandbox_config.set_current(index)
            if success:
                # Reload sentinel with new current sandbox
                # Note: This requires restart for full effect, but we can update CLI
                new_path = sandbox_config.get_current()
                if new_path:
                    self.cli.current_dir = Path(new_path)
                    self.sentinel.dev_root = Path(new_path)
                    self.sentinel.log_command(update.effective_user.id, f"/sandbox switch to {Path(new_path).name}")
                    await update.message.reply_text(f"✅ {msg}\n\n⚠️ Restart TeleCode for full effect.")
                else:
                    await update.message.reply_text(f"❌ {msg}")
            else:
                await update.message.reply_text(f"❌ {msg}")
        except ValueError:
            # Try as name
            found = False
            for idx, sandbox in enumerate(info['sandboxes']):
                if sandbox['name'].lower() == arg.lower():
                    success, msg = sandbox_config.set_current(idx)
                    if success:
                        new_path = sandbox_config.get_current()
                        if new_path:
                            self.cli.current_dir = Path(new_path)
                            self.sentinel.dev_root = Path(new_path)
                            self.sentinel.log_command(update.effective_user.id, f"/sandbox switch to {Path(new_path).name}")
                            await update.message.reply_text(f"✅ {msg}\n\n⚠️ Restart TeleCode for full effect.")
                        found = True
                        break
            
            if not found:
                await update.message.reply_text(f"❌ Sandbox not found: {arg}\n\nUse /sandboxes to see available sandboxes.")
    
    @require_auth
    async def _cmd_sandboxes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all sandbox directories."""
        from src.sandbox_config import get_sandbox_config
        
        sandbox_config = get_sandbox_config()
        info = sandbox_config.get_info()
        
        message = f"📂 **Sandbox Directories** ({info['total']}/10)\n\n"
        
        for sandbox in info['sandboxes']:
            current_marker = " ✅ **CURRENT**" if sandbox['is_current'] else ""
            message += f"{sandbox['index'] + 1}. **{sandbox['name']}**{current_marker}\n"
            message += f"   `{sandbox['path']}`\n\n"
        
        message += "Use `/sandbox [index]` or `/sandbox [name]` to switch.\n"
        message += "Example: `/sandbox 2` or `/sandbox Projects`"
        
        await update.message.reply_text(message, parse_mode="Markdown")
    
    async def _cmd_sandbox_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle sandbox switch button callbacks."""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        callback_data = query.data
        
        from src.sandbox_config import get_sandbox_config
        sandbox_config = get_sandbox_config()
        
        if callback_data.startswith("sandbox_switch_"):
            index_str = callback_data.replace("sandbox_switch_", "")
            try:
                index = int(index_str)
                success, msg = sandbox_config.set_current(index)
                if success:
                    new_path = sandbox_config.get_current()
                    if new_path:
                        self.cli.current_dir = Path(new_path)
                        self.sentinel.dev_root = Path(new_path)
                        self.sentinel.log_command(user_id, f"/sandbox switch to {Path(new_path).name}")
                        await query.message.reply_text(
                            f"✅ {msg}\n\n"
                            f"⚠️ **Restart TeleCode** for full effect.\n\n"
                            f"Current sandbox: `{Path(new_path).name}`",
                            parse_mode="Markdown"
                        )
                    else:
                        await query.message.reply_text(f"❌ Failed to switch sandbox")
                else:
                    await query.message.reply_text(f"❌ {msg}")
            except ValueError:
                await query.message.reply_text("❌ Invalid sandbox index")
    
    async def _cmd_pwd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current working directory."""
        self.sentinel.log_command(update.effective_user.id, "/pwd")
        
        info = self.cli.get_current_info()
        # Don't use Markdown parse_mode - git status contains ## which breaks it
        await update.message.reply_text(info)
    
    # ==========================================
    # Project Creation Commands (Conversation)
    # ==========================================
    
    @require_auth
    async def _cmd_create_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Start the project creation conversation.
        
        Step 1: Ask for project name.
        Can be called to restart the conversation if interrupted.
        """
        self.sentinel.log_command(update.effective_user.id, "/create")
        
        # Clear any existing state when restarting
        context.user_data.pop('create_project_name', None)
        
        message = f"""
🆕 **Create New Project**

📂 Projects will be created in:
`{self.sentinel.dev_root}`

📝 **Enter your project name:**

_Rules:_
• Use only letters, numbers, hyphens, underscores
• No spaces or special characters
• Example: `my-awesome-app` or `webapp_v2`

_(Type /cancel to abort)_
"""
        await update.message.reply_text(message, parse_mode="Markdown")
        return CREATE_AWAITING_NAME
    
    @require_auth
    async def _cmd_create_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle project name input.
        
        Step 2: Validate name and ask for confirmation.
        """
        name = update.message.text.strip()
        
        # Validate the name using CLI wrapper's sanitizer
        safe_name = self.cli._sanitize_project_name(name)
        
        if not safe_name:
            await update.message.reply_text(
                "❌ **Invalid project name!**\n\n"
                "Use only letters, numbers, hyphens (-), and underscores (_).\n"
                "Cannot start with - or _ and no path characters allowed.\n\n"
                "Please try again or /cancel:",
                parse_mode="Markdown"
            )
            return CREATE_AWAITING_NAME
        
        # Check if name was sanitized differently
        if safe_name != name:
            await update.message.reply_text(
                f"⚠️ Name was sanitized to: `{safe_name}`",
                parse_mode="Markdown"
            )
        
        # Check if directory already exists
        target_path = self.sentinel.dev_root / safe_name
        if target_path.exists():
            await update.message.reply_text(
                f"❌ **Directory already exists!**\n\n"
                f"A folder named `{safe_name}` already exists.\n"
                f"Please choose a different name or /cancel:",
                parse_mode="Markdown"
            )
            return CREATE_AWAITING_NAME
        
        # Store the name for confirmation
        context.user_data['create_project_name'] = safe_name
        
        # Ask for confirmation with inline buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Create Project", callback_data="create_confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="create_cancel"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        confirm_message = f"""
🔍 **Confirm Project Creation**

📛 **Name:** `{safe_name}`
📂 **Path:** `{target_path}`

**This will:**
1. 📁 Create directory `{safe_name}`
2. 🔀 Initialize git repository
3. 💻 Open Cursor IDE

_Press a button to confirm or cancel:_
"""
        await update.message.reply_text(
            confirm_message,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return CREATE_AWAITING_CONFIRM
    
    @require_auth
    async def _cmd_create_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle confirmation button press.
        
        Step 3: Actually create the project.
        """
        query = update.callback_query
        await query.answer()
        
        project_name = context.user_data.get('create_project_name')
        
        if not project_name:
            await query.edit_message_text("❌ Session expired. Please start again with /create")
            return ConversationHandler.END
        
        self.sentinel.log_command(update.effective_user.id, f"/create {project_name} (confirmed)")
        
        # Show progress
        await query.edit_message_text(
            f"⏳ Creating project `{project_name}`...",
            parse_mode="Markdown"
        )
        
        # Create the project using scaffold_project
        success, message, project_path = self.cli.scaffold_project(project_name)
        
        if success:
            # Switch to the new project directory
            self.cli.current_dir = project_path
            
            result_message = f"""
🎉 **Project Created Successfully!**

{message}

📂 **Location:** `{project_path}`
🔀 **Git:** Initialized
"""
            await query.edit_message_text(result_message, parse_mode="Markdown")
            
            # Now open Cursor with status updates
            agent = self._get_cursor_agent()
            
            pending_msg = await query.message.reply_text(
                f"💻 **Opening Cursor...**\n\n"
                f"📂 Workspace: `{project_name}`\n"
                f"⏳ Status: Launching...",
                parse_mode="Markdown"
            )
            
            last_message = {"text": ""}
            
            async def status_callback(msg: str, is_complete: bool):
                """Update the Telegram message with current status."""
                if msg != last_message["text"]:
                    last_message["text"] = msg
                    try:
                        if is_complete:
                            if "✅" in msg:
                                keyboard = [[
                                    InlineKeyboardButton("🤖 Send AI Prompt", callback_data="ai_prompt_start"),
                                ]]
                                reply_markup = InlineKeyboardMarkup(keyboard)
                                await pending_msg.edit_text(
                                    f"💻 **Cursor Ready!**\n\n{msg}\n\n"
                                    f"**Next steps:**\n"
                                    f"• Start coding in Cursor\n"
                                    f"• Use /ai to run prompts\n"
                                    f"• Use /status to check git",
                                    parse_mode="Markdown",
                                    reply_markup=reply_markup
                                )
                            else:
                                keyboard = [[
                                    InlineKeyboardButton("🔄 Retry", callback_data="cursor_open"),
                                ]]
                                reply_markup = InlineKeyboardMarkup(keyboard)
                                await pending_msg.edit_text(
                                    f"💻 **Cursor Status**\n\n{msg}",
                                    parse_mode="Markdown",
                                    reply_markup=reply_markup
                                )
                        else:
                            await pending_msg.edit_text(
                                f"💻 **Opening Cursor**\n\n"
                                f"📂 Workspace: `{project_name}`\n"
                                f"{msg}",
                                parse_mode="Markdown"
                            )
                    except Exception as e:
                        logger.debug(f"Failed to update status message: {e}")
            
            # Open Cursor and wait
            await agent.open_cursor_and_wait(
                status_callback=status_callback,
                timeout=30.0,
                poll_interval=1.5
            )
        else:
            result_message = f"""
❌ **Project Creation Failed**

{message}

Please try again with /create
"""
            await query.edit_message_text(result_message, parse_mode="Markdown")
        
        # Clear user data
        context.user_data.pop('create_project_name', None)
        
        return ConversationHandler.END
    
    @require_auth
    async def _cmd_create_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel command during project creation."""
        self.sentinel.log_command(update.effective_user.id, "/create (cancelled)")
        
        # Clear user data
        context.user_data.pop('create_project_name', None)
        
        await update.message.reply_text(
            "❌ Project creation cancelled.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    @require_auth
    async def _cmd_create_cancel_btn(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle cancel button press during project creation."""
        query = update.callback_query
        await query.answer()
        
        self.sentinel.log_command(update.effective_user.id, "/create (cancelled via button)")
        
        # Clear user data
        context.user_data.pop('create_project_name', None)
        
        await query.edit_message_text(
            "❌ Project creation cancelled.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    # ==========================================
    # Cursor Commands
    # ==========================================
    
    @require_auth
    async def _cmd_cursor(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Check Cursor IDE status and open if needed.
        
        Usage:
            /cursor         - Check status and show open button if needed
            /cursor open    - Open Cursor with current workspace
            /cursor status  - Just show status
        """
        self.sentinel.log_command(update.effective_user.id, "/cursor")
        
        agent = self._get_cursor_agent()
        workspace_name = self.cli.current_dir.name
        
        # Check for subcommands
        subcommand = context.args[0].lower() if context.args else None
        
        if subcommand == "open":
            # Open Cursor for the current workspace with live status updates
            pending_msg = await update.message.reply_text(
                f"🚀 **Opening Cursor...**\n\n"
                f"📂 Workspace: `{workspace_name}`\n"
                f"⏳ Status: Launching...",
                parse_mode="Markdown"
            )
            
            last_message = {"text": ""}
            
            async def status_callback(message: str, is_complete: bool):
                """Update the Telegram message with current status."""
                if message != last_message["text"]:
                    last_message["text"] = message
                    try:
                        if is_complete:
                            if "✅" in message:
                                keyboard = [[
                                    InlineKeyboardButton("🤖 Send AI Prompt", callback_data="ai_prompt_start"),
                                ]]
                                reply_markup = InlineKeyboardMarkup(keyboard)
                            else:
                                keyboard = [[
                                    InlineKeyboardButton("🔄 Retry", callback_data="cursor_open"),
                                ]]
                                reply_markup = InlineKeyboardMarkup(keyboard)
                            
                            await pending_msg.edit_text(
                                f"💻 **Cursor Status**\n\n{message}",
                                parse_mode="Markdown",
                                reply_markup=reply_markup
                            )
                        else:
                            await pending_msg.edit_text(
                                f"💻 **Opening Cursor**\n\n"
                                f"📂 Workspace: `{workspace_name}`\n"
                                f"{message}",
                                parse_mode="Markdown"
                            )
                    except Exception as e:
                        logger.debug(f"Failed to update status message: {e}")
            
            result = await agent.open_cursor_and_wait(
                status_callback=status_callback,
                timeout=30.0,
                poll_interval=1.5
            )
            return
        
        # Default: show status with options
        status = agent.check_cursor_status()
        
        status_emoji = {
            "not_running": "🔴 Not Running",
            "starting": "🟡 Starting...",
            "running": "🟠 Running (different workspace)",
            "ready": "🟢 Ready",
        }
        
        status_text = status_emoji.get(status.get("status", ""), "⚪ Unknown")
        message_text = status.get("message", "Unable to determine status")
        
        response = f"""💻 **Cursor IDE Status**

**Workspace:** `{workspace_name}`
**Status:** {status_text}

{message_text}

**Commands:**
• `/cursor open` - Open workspace in Cursor
• `/cursor status` - Check status"""
        
        # Add action buttons based on status
        if not status.get("workspace_open"):
            keyboard = [[InlineKeyboardButton("🚀 Open in Cursor", callback_data="cursor_open")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(response, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            keyboard = [[
                InlineKeyboardButton("🤖 Send AI Prompt", callback_data="ai_prompt_start"),
                InlineKeyboardButton("🔄 Refresh Status", callback_data="cursor_status"),
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(response, parse_mode="Markdown", reply_markup=reply_markup)
    
    # ==========================================
    # AI Commands
    # ==========================================
    
    def _get_cursor_agent(self) -> CursorAgentBridge:
        """Get or create the Cursor Agent for current workspace."""
        return get_agent_for_workspace(self.cli.current_dir)
    
    @require_auth
    async def _cmd_ai(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        AI command with subcommands for Cursor control.
        
        Usage:
            /ai <prompt>           - Send prompt to Cursor
            /ai accept             - Accept AI changes (Ctrl+Enter)
            /ai reject             - Reject AI changes (Escape)
            /ai continue <prompt>  - Continue with follow-up prompt
            /ai stop               - Stop/clear current session
            /ai status             - Check agent status
        """
        if not context.args:
            await self._show_ai_help(update)
            return
        
        # Check for subcommands
        subcommand = context.args[0].lower()
        remaining_args = context.args[1:] if len(context.args) > 1 else []
        
        if subcommand == "accept":
            await self._cmd_ai_accept(update)
        elif subcommand == "reject":
            await self._cmd_ai_reject(update)
        elif subcommand == "continue":
            if remaining_args:
                prompt = " ".join(remaining_args)
                await self._cmd_ai_continue(update, prompt)
            else:
                await update.message.reply_text(
                    "❌ Please provide a follow-up prompt:\n\n"
                    "`/ai continue <your follow-up prompt>`",
                    parse_mode="Markdown"
                )
        elif subcommand == "stop":
            await self._cmd_ai_stop(update)
        elif subcommand == "status":
            await self._cmd_ai_status(update)
        elif subcommand == "mode":
            if remaining_args:
                mode = remaining_args[0].lower()
                await self._cmd_ai_mode(update, mode)
            else:
                await self._cmd_ai_mode(update, None)
        else:
            # Not a subcommand - treat entire args as prompt
            prompt = " ".join(context.args)
            await self._execute_ai_prompt(update, prompt)
    
    async def _show_ai_help(self, update: Update):
        """Show AI command help."""
        user_id = update.effective_user.id
        current_model = self.user_prefs.get_user_model(user_id)
        
        # Check current status
        agent = self._get_cursor_agent()
        status = agent.get_status()
        current_mode = agent.get_prompt_mode()
        
        state_emoji = {
            "idle": "⚪",
            "prompt_sent": "🟡",
            "awaiting_changes": "🟡", 
            "changes_pending": "🟢",
            "processing": "🔵"
        }
        mode_emoji = {"agent": "🤖", "chat": "💬", "inline": "✏️"}.get(current_mode, "❓")
        
        state = status.data.get("state", "idle") if status.data else "idle"
        
        help_text = f"""
🤖 **AI Commands** (Cursor only - no git)

**Send Prompt:**
  `/ai <prompt>` - Send to Cursor

**Cursor Controls:** (buttons OR commands)
  `/ai accept` (✅) - Accept changes (Ctrl+Enter)
  `/ai reject` (❌) - Reject changes (Escape)
  📊 Check - See changed files
  📖 Diff - View changes

**AI Commands:**
  `/ai continue <prompt>` - Follow-up
  `/ai stop` - Clear session
  `/ai status` - Check state
  `/ai mode [agent|chat]` - Set mode

**Git Commands:** (separate)
  `/commit` - Git commit
  `/revert` - Git restore
  `/push` - Git push

**Mode:** {mode_emoji} `{current_mode}` {'(auto-save)' if current_mode == 'agent' else '(manual)'}
**Model:** {current_model.emoji} {current_model.display_name}

💡 _Just send text as AI prompt!_
"""
        await update.message.reply_text(help_text, parse_mode="Markdown")
    
    async def _execute_ai_prompt(self, update: Update, prompt: str):
        """Execute an AI prompt via Cursor Agent Bridge with live status updates and screenshot."""
        from pathlib import Path
        import random
        
        user_id = update.effective_user.id
        self.sentinel.log_command(user_id, f"/ai {prompt[:50]}...")
        
        # Get user's selected model
        current_model = self.user_prefs.get_user_model(user_id)
        workspace_name = self.cli.current_dir.name
        
        # Show initial status message
        status_msg = await update.message.reply_text(
            f"📤 **Sending to Cursor...**\n\n"
            f"🤖 **{current_model.display_name}**\n"
            f"📂 `{workspace_name}`\n\n"
            f"📝 _{prompt[:100]}{'...' if len(prompt) > 100 else ''}_\n\n"
            f"💡 **Note:** Make sure '{current_model.display_name}' is enabled in Cursor Settings > Models", 
            parse_mode="Markdown"
        )
        
        # Get the Cursor Agent
        agent = self._get_cursor_agent()
        
        # Track completion state
        final_screenshot_path = None
        final_status = None
        final_files = []
        
        # Define status callback to update Telegram message
        async def status_callback(message: str, is_complete: bool, screenshot_path=None):
            nonlocal final_screenshot_path, final_status, final_files
            
            if screenshot_path:
                final_screenshot_path = screenshot_path
            
            if not is_complete:
                # Check if this is a progress screenshot update
                if screenshot_path and "📸" in message:
                    # Send progress screenshot as a new photo message with control buttons
                    try:
                        from pathlib import Path
                        screenshot_file = Path(screenshot_path)
                        if screenshot_file.exists():
                            # Add control buttons for stuck agent scenarios
                            keyboard = [[
                                InlineKeyboardButton("➡️ Continue", callback_data="ai_send_continue"),
                                InlineKeyboardButton("🛑 Stop", callback_data="ai_stop"),
                            ]]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            
                            with open(screenshot_file, 'rb') as photo:
                                await update.message.reply_photo(
                                    photo=photo,
                                    caption=f"{message}\n\n📝 _{prompt[:60]}{'...' if len(prompt) > 60 else ''}_",
                                    parse_mode="Markdown",
                                    reply_markup=reply_markup
                                )
                            logger.info(f"[AI_PROMPT] Sent progress screenshot with controls: {screenshot_path}")
                    except Exception as e:
                        logger.warning(f"Failed to send progress screenshot: {e}")
                        # Fall back to text update
                        try:
                            await status_msg.edit_text(
                                f"{message}\n\n"
                                f"🤖 **{current_model.display_name}**\n"
                                f"📂 `{workspace_name}`\n\n"
                                f"📝 _{prompt[:80]}{'...' if len(prompt) > 80 else ''}_",
                                parse_mode="Markdown"
                            )
                        except Exception:
                            pass
                else:
                    # Regular text status update
                    try:
                        await status_msg.edit_text(
                            f"{message}\n\n"
                            f"🤖 **{current_model.display_name}**\n"
                            f"📂 `{workspace_name}`\n\n"
                            f"📝 _{prompt[:80]}{'...' if len(prompt) > 80 else ''}_",
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass
        
        # Check if Cursor is open - if not, open it first
        cursor_status = agent.check_cursor_status()
        
        if not cursor_status.get("workspace_open"):
            # Update message to show we're opening Cursor
            try:
                await status_msg.edit_text(
                    f"🚀 **Opening Cursor...**\n\n"
                    f"📂 `{workspace_name}`\n"
                    f"⏳ Please wait...\n\n"
                    f"📝 _{prompt[:80]}{'...' if len(prompt) > 80 else ''}_",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            
            # Define callback to update status
            async def cursor_open_callback(msg: str, is_complete: bool):
                if not is_complete:
                    try:
                        await status_msg.edit_text(
                            f"🚀 **Opening Cursor...**\n\n"
                            f"📂 `{workspace_name}`\n"
                            f"{msg}\n\n"
                            f"📝 _{prompt[:80]}{'...' if len(prompt) > 80 else ''}_",
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass
            
            # Wait for Cursor to open
            open_result = await agent.open_cursor_and_wait(
                status_callback=cursor_open_callback,
                timeout=30.0,
                poll_interval=1.5
            )
            
            if not open_result.success:
                await status_msg.edit_text(
                    f"❌ **Failed to open Cursor**\n\n{open_result.message}\n\n{open_result.error or ''}",
                    parse_mode="Markdown"
                )
                return
        
        # CRITICAL: Run AI work in background task to avoid blocking button callbacks
        # This allows the handler to return immediately so button presses can be processed
        async def run_ai_work():
            """Run AI work in background - allows button callbacks to be processed independently."""
            try:
                # Only change model if user just selected a new one (within last 5 minutes)
                # Otherwise use normal flow (Cursor will use its current/default model)
                model_to_use = None
                should_clear_flag = False
                if self.user_prefs.was_model_recently_changed(user_id, max_age_minutes=5):
                    model_to_use = current_model.id
                    should_clear_flag = True  # Clear flag after attempting change
                    logger.info(f"Model was recently changed, will attempt to change to: {current_model.display_name}")
                else:
                    logger.info(f"Using normal flow - model not recently changed, Cursor will use current/default model")
                
                # Send prompt and wait for completion with live status updates
                # Increased timeouts: 5 min max, 3s polls, 10 stable polls (30s), 15s min processing
                result = await agent.send_prompt_and_wait(
                    prompt=prompt,
                    status_callback=status_callback,
                    model=model_to_use,  # Only set if model was recently changed
                    timeout=300.0,           # 5 minutes max for complex prompts
                    poll_interval=3.0,       # Check every 3 seconds
                    stable_threshold=10,     # Need 10 stable polls (30s of no changes)
                    min_processing_time=15.0 # At least 15s before declaring done
                )
                
                # Clear the "recently changed" flag after attempting model change
                # This ensures we only try to change model once, not on every subsequent prompt
                if should_clear_flag:
                    self.user_prefs.clear_model_changed_flag(user_id)
                    logger.info("Cleared model_changed_at flag - subsequent prompts will use normal flow")
                
                if result.success:
                    data = result.data or {}
                    status = data.get("status", "completed")
                    mode = data.get("mode", "agent")
                    files_changed = data.get("files_changed", 0)
                    elapsed = data.get("elapsed_seconds", 0)
                    files = data.get("files", [])
                    screenshot_path = data.get("screenshot")
                    agent_id = data.get("agent_id")  # Agent ID for routing buttons to correct chat
                    
                    # Build status emoji and message based on result
                    # files_changed already contains only changes from this prompt (from cursor_agent.py)
                    lines_changed = data.get("lines_changed", 0)  # Get lines changed if available
                    if status == "completed":
                        status_emoji = "✅"
                        if lines_changed > 0:
                            status_text = f"**Cursor AI Completed!** ({files_changed} files, ~{lines_changed} lines, {elapsed}s)"
                        else:
                            status_text = f"**Cursor AI Completed!** ({files_changed} files, {elapsed}s)"
                    elif status == "waiting":
                        status_emoji = "⏳"
                        status_text = f"**Cursor AI may be waiting...** ({elapsed}s)"
                    else:  # timeout
                        status_emoji = "⏱️"
                        status_text = f"**Timeout** - Check Cursor ({elapsed}s)"
                    
                    # Mode info
                    auto_save = mode == "agent"
                    if auto_save:
                        mode_info = "🤖 Agent mode - Files auto-saved"
                    else:
                        mode_info = "💬 Chat mode - Click Accept to apply"
                    
                    # Files list (truncated)
                    files_preview = ""
                    if files:
                        files_list = files[:5]
                        files_preview = "\n📁 " + ", ".join(f"`{f}`" for f in files_list)
                        if len(files) > 5:
                            files_preview += f" _+{len(files)-5} more_"
                    
                    # Build final message
                    message = f"""{status_emoji} {status_text}

{mode_info}
{files_preview}

📝 _{prompt[:80]}{'...' if len(prompt) > 80 else ''}_"""
                    
                    # Build inline keyboard with ALL controls in one grid
                    # Include agent_id in callback_data for continue/stop buttons to route to correct chat
                    continue_callback = f"ai_send_continue:{agent_id}" if agent_id is not None else "ai_send_continue"
                    stop_callback = f"ai_stop:{agent_id}" if agent_id is not None else "ai_stop"
                    
                    # For completed status, remove Run button since it uses same command (Enter) as Continue
                    if status == "completed":
                        keyboard = [
                            [
                                InlineKeyboardButton("📊 Check", callback_data="ai_check"),
                                InlineKeyboardButton("📖 Diff", callback_data="ai_view_diff"),
                                InlineKeyboardButton("✅ Accept", callback_data="ai_accept"),
                            ],
                            [
                                InlineKeyboardButton("❌ Reject", callback_data="ai_reject"),
                                InlineKeyboardButton("➡️ Continue", callback_data=continue_callback),
                            ],
                            [
                                InlineKeyboardButton("⚙️ Mode", callback_data="ai_mode"),
                                InlineKeyboardButton("🧹 Cleanup", callback_data="ai_cleanup"),
                            ],
                        ]
                    else:
                        # For waiting/timeout status, keep Run button
                        keyboard = [
                            [
                                InlineKeyboardButton("📊 Check", callback_data="ai_check"),
                                InlineKeyboardButton("📖 Diff", callback_data="ai_view_diff"),
                                InlineKeyboardButton("✅ Accept", callback_data="ai_accept"),
                            ],
                            [
                                InlineKeyboardButton("❌ Reject", callback_data="ai_reject"),
                                InlineKeyboardButton("▶️ Run", callback_data="ai_run"),
                                InlineKeyboardButton("➡️ Continue", callback_data=continue_callback),
                            ],
                            [
                                InlineKeyboardButton("⚙️ Mode", callback_data="ai_mode"),
                                InlineKeyboardButton("🧹 Cleanup", callback_data="ai_cleanup"),
                            ],
                        ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    # Send screenshot with the completion message
                    if screenshot_path and Path(screenshot_path).exists():
                        try:
                            # Delete the old status message
                            await status_msg.delete()
                        except Exception:
                            pass
                        
                        # Send photo with caption and buttons
                        try:
                            with open(screenshot_path, 'rb') as photo:
                                await update.message.reply_photo(
                                    photo=photo,
                                    caption=self._truncate_message(message)[:1024],  # Photo captions max 1024 chars
                                    parse_mode="Markdown",
                                    reply_markup=reply_markup
                                )
                        except Exception as e:
                            logger.warning(f"Failed to send screenshot: {e}")
                            # Fallback to text message
                            await update.message.reply_text(
                                self._truncate_message(message),
                                parse_mode="Markdown",
                                reply_markup=reply_markup
                            )
                    else:
                        # No screenshot - just update the message
                        try:
                            await status_msg.edit_text(
                                self._truncate_message(message), 
                                parse_mode="Markdown",
                                reply_markup=reply_markup
                            )
                        except Exception:
                            await update.message.reply_text(
                                self._truncate_message(message), 
                                parse_mode="Markdown",
                                reply_markup=reply_markup
                            )
                else:
                    error = result.error or "Unknown error"
                    message = f"❌ **Failed to Send Prompt**\n\n{result.message}\n\n```\n{error}\n```"
                    
                    # Add troubleshooting tips
                    if "automation" in error.lower() or "pyautogui" in error.lower():
                        message += "\n\n💡 **Tip:** Make sure `pyautogui` and `pyperclip` are installed:\n`pip install pyautogui pyperclip`"
                    elif "cursor" in error.lower():
                        message += "\n\n💡 **Tip:** Make sure Cursor is installed and `cursor` is in your PATH."
                    
                    # Update the status message with the error
                    try:
                        await status_msg.edit_text(self._truncate_message(message), parse_mode="Markdown")
                    except Exception:
                        await update.message.reply_text(self._truncate_message(message), parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Error in background AI work: {e}", exc_info=True)
                try:
                    await status_msg.edit_text(
                        f"❌ **Error during AI execution**\n\n{str(e)}",
                        parse_mode="Markdown"
                    )
                except Exception:
                    await update.message.reply_text(
                        f"❌ **Error during AI execution**\n\n{str(e)}",
                        parse_mode="Markdown"
                    )
        
        # CRITICAL: Run AI work in background task and return immediately
        # This allows button callbacks to be processed independently
        asyncio.create_task(run_ai_work())
        # Handler returns immediately - button callbacks can now be processed!
    
    async def _cmd_ai_accept(self, update: Update):
        """Accept all AI changes in Cursor (uses Ctrl+Enter)."""
        user_id = update.effective_user.id
        self.sentinel.log_command(user_id, "/ai accept")
        
        agent = self._get_cursor_agent()
        
        # Use Cursor's Accept (Ctrl+Enter)
        result = agent.accept_changes_via_cursor()
        
        if result.success:
            response = """✅ **Changes Accepted in Cursor!**

The AI changes have been applied via Ctrl+Enter.

📌 _This only affects Cursor, not git._
💡 _Use `/commit` to git commit, `/push` to push._"""
        else:
            response = f"❌ **Accept Failed**\n\n{result.message}\n\n{result.error or ''}"
        
        await update.message.reply_text(response, parse_mode="Markdown")
    
    async def _cmd_ai_reject(self, update: Update):
        """Reject AI changes in Cursor (uses Escape)."""
        user_id = update.effective_user.id
        self.sentinel.log_command(user_id, "/ai reject")
        
        agent = self._get_cursor_agent()
        
        # Show confirmation for Cursor-only reject
        keyboard = [[
            InlineKeyboardButton("⚠️ Yes, Reject in Cursor", callback_data="ai_reject_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="ai_reject_cancel"),
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Both modes use Escape to reject changes
        method = "Escape"
        
        await update.message.reply_text(
            f"⚠️ **Confirm Reject**\n\n"
            f"This will reject AI changes **in Cursor only**.\n\n"
            f"🔄 Method: {method}\n\n"
            f"📌 _This does NOT affect git._\n"
            f"💡 _For git restore, use `/revert CONFIRM` instead._",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    
    async def _cmd_ai_continue(self, update: Update, prompt: str):
        """Continue with a follow-up prompt."""
        user_id = update.effective_user.id
        self.sentinel.log_command(user_id, f"/ai continue {prompt[:30]}...")
        
        agent = self._get_cursor_agent()
        current_model = self.user_prefs.get_user_model(user_id)
        
        result = agent.continue_session(prompt, model=current_model.id)
        
        if result.success:
            await update.message.reply_text(
                f"▶️ **Continuing...**\n\n"
                f"📝 Follow-up: _{prompt}_\n\n"
                f"Open Cursor and use `Ctrl+I` to continue.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ **Cannot Continue**\n\n{result.message}\n\n{result.error or ''}",
                parse_mode="Markdown"
            )
    
    async def _cmd_ai_stop(self, update: Update):
        """Stop/clear the current AI session."""
        user_id = update.effective_user.id
        self.sentinel.log_command(user_id, "/ai stop")
        
        agent = self._get_cursor_agent()
        result = agent.stop_session()
        
        await update.message.reply_text(
            f"🛑 **Session Stopped**\n\n"
            f"Previous state: `{result.data.get('previous_state', 'unknown') if result.data else 'unknown'}`\n"
            f"Session cleared. Ready for new prompts.",
            parse_mode="Markdown"
        )
    
    async def _cmd_ai_mode(self, update: Update, mode: Optional[str]):
        """Set or show the AI prompt mode."""
        user_id = update.effective_user.id
        agent = self._get_cursor_agent()
        
        if mode:
            # Set mode
            self.sentinel.log_command(user_id, f"/ai mode {mode}")
            result = agent.set_prompt_mode(mode)
            
            if result.success:
                data = result.data or {}
                description = data.get("description", "")
                auto_save = data.get("auto_save", False)
                
                message = f"✅ **Mode Changed!**\n\n{description}"
                if auto_save:
                    message += "\n\n💡 _Files auto-save, Reject uses Escape_"
                else:
                    message += "\n\n⚠️ _Click Accept to apply, Reject uses Escape_"
                
                await update.message.reply_text(message, parse_mode="Markdown")
            else:
                await update.message.reply_text(
                    f"❌ {result.error}\n\nValid modes: `agent`, `chat`",
                    parse_mode="Markdown"
                )
        else:
            # Show current mode with selection buttons
            self.sentinel.log_command(user_id, "/ai mode")
            current_mode = agent.get_prompt_mode()
            
            keyboard = [
                [InlineKeyboardButton(
                    f"{'✓ ' if current_mode == 'agent' else ''}🤖 Agent (auto-save)", 
                    callback_data="ai_mode_agent"
                )],
                [InlineKeyboardButton(
                    f"{'✓ ' if current_mode == 'chat' else ''}💬 Chat (manual keep)", 
                    callback_data="ai_mode_chat"
                )],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            mode_emoji = {"agent": "🤖", "chat": "💬"}.get(current_mode, "❓")
            
            await update.message.reply_text(
                f"⚙️ **Prompt Mode**\n\n"
                f"Current: {mode_emoji} **{current_mode.title()}**\n\n"
                f"🤖 **Agent** - Auto-saves files to disk (SAFEST)\n"
                f"   _Files saved immediately - won't lose work_\n"
                f"   _Reject uses Escape_\n\n"
                f"💬 **Chat** - Proposed changes need Accept\n"
                f"   _More control, review before accepting_\n"
                f"   _Reject uses Escape to discard_\n\n"
                f"Quick switch: `/ai mode agent` or `/ai mode chat`",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
    
    async def _cmd_ai_status(self, update: Update):
        """Show current AI agent status."""
        user_id = update.effective_user.id
        self.sentinel.log_command(user_id, "/ai status")
        
        agent = self._get_cursor_agent()
        status = agent.get_status()
        current_model = self.user_prefs.get_user_model(user_id)
        
        if status.success and status.data:
            data = status.data
            
            state_emoji = {
                "idle": "⚪ Idle",
                "prompt_sent": "🟡 Prompt Sent",
                "awaiting_changes": "🟡 Awaiting Changes", 
                "changes_pending": "🟢 Changes Pending",
                "processing": "🔵 Processing"
            }
            
            state = data.get("state", "idle")
            agent_count = data.get("agent_count", 0)
            
            # Get current mode from agent
            current_prompt_mode = agent.get_prompt_mode()
            mode_emoji = {"agent": "🤖", "chat": "💬"}.get(current_prompt_mode, "❓")
            
            response = f"""📊 **AI Agent Status**

**State:** {state_emoji.get(state, state)}
**Workspace:** `{Path(data.get('workspace', '')).name}`
**Model:** {current_model.emoji} {current_model.display_name}
**Mode:** {mode_emoji} {current_prompt_mode.title()} {'(auto-save)' if current_prompt_mode == 'agent' else '(manual keep)'}
**Agents Open:** {agent_count}

**Changes:**
  • Detected: {'✅ Yes' if data.get('changes_detected') else '❌ No'}
  • Pending files: {data.get('file_count', 0)}
"""
            
            if data.get('prompt_preview'):
                response += f"\n**Last Prompt:** _{data['prompt_preview']}..._"
            
            if data.get('pending_files'):
                files_list = "\n".join(f"  • `{f}`" for f in data['pending_files'][:5])
                if len(data['pending_files']) > 5:
                    files_list += f"\n  _...and {len(data['pending_files']) - 5} more_"
                response += f"\n\n**Pending Files:**\n{files_list}"
            
            # Add action buttons if there are pending changes (Cursor controls only, no git)
            if data.get('changes_detected'):
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Accept", callback_data="ai_accept"),
                        InlineKeyboardButton("❌ Reject", callback_data="ai_reject"),
                    ],
                    [InlineKeyboardButton("📖 View Diff", callback_data="ai_view_diff")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(response, parse_mode="Markdown", reply_markup=reply_markup)
            else:
                await update.message.reply_text(response, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                f"❌ Failed to get status: {status.error or 'Unknown error'}",
                parse_mode="Markdown"
            )
    
    # ==========================================
    # Model Selection Commands
    # ==========================================
    
    @require_auth
    async def _cmd_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Select AI model - interactive menu or quick switch.
        
        Usage:
            /model        - Show model selection menu
            /model opus   - Quick switch to Opus
            /model sonnet - Quick switch to Sonnet
        """
        user_id = update.effective_user.id
        self.sentinel.log_command(user_id, "/model")
        
        # Check if a model alias was provided
        if context.args:
            alias = context.args[0].lower()
            success, message = self.user_prefs.set_user_model(user_id, alias)
            
            if success:
                # Get the model to check if it's paid
                model = self.user_prefs.get_user_model(user_id)
                response = f"✅ {message}"
                
                # Add warning for paid models
                if model.tier == ModelTier.PAID:
                    response += f"\n\n⚠️ **Note:** {model.display_name} is a paid model."
                    response += "\n💡 Make sure your Cursor subscription includes access to this model."
                    response += "\n📝 If you see errors, try a free model: `/model haiku` or `/model gemini`"
                
                await update.message.reply_text(response, parse_mode="Markdown")
            else:
                await update.message.reply_text(f"❌ {message}", parse_mode="Markdown")
            return
        
        # Show interactive model selection menu
        current_model = self.user_prefs.get_user_model(user_id)
        
        # Build inline keyboard with model buttons (2-3 buttons per row)
        keyboard = []
        
        # Collect paid and free models separately
        paid_models = []
        free_models = []
        for alias, model in AVAILABLE_MODELS.items():
            label = f"{model.emoji} {model.alias.title()}"
            if model.alias == current_model.alias:
                label = f"✓ {label}"
            button = InlineKeyboardButton(label, callback_data=f"model_{alias}")
            if model.tier == ModelTier.PAID:
                paid_models.append(button)
            else:
                free_models.append(button)
        
        # Add paid models in rows of 2-3 buttons
        for i in range(0, len(paid_models), 3):
            keyboard.append(paid_models[i:i+3])
        
        # Add free models in rows of 2-3 buttons
        for i in range(0, len(free_models), 3):
            keyboard.append(free_models[i:i+3])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = format_model_selection_message(current_model)
        message += "\n\n💎 = Paid (requires Cursor subscription)"
        message += "\n✨ = Free (available to all)"
        message += "\n\n⚠️ **Important:**"
        message += "\n• Paid models require a Cursor subscription with access to that model."
        message += "\n• **Your selected model must be enabled in Cursor Settings > Models**"
        message += "\n• If a model isn't working, check Cursor Settings and toggle it ON"
        message += "\n💡 If you see errors, try switching to a free model."
        
        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    
    @require_auth
    async def _cmd_model_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle model selection button callback."""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Extract model alias from callback data (format: "model_opus")
        callback_data = query.data
        if not callback_data.startswith("model_"):
            return
        
        alias = callback_data.replace("model_", "")
        
        self.sentinel.log_command(user_id, f"/model {alias} (button)")
        
        success, message = self.user_prefs.set_user_model(user_id, alias)
        
        if success:
            # Get the new model for display
            new_model = self.user_prefs.get_user_model(user_id)
            
            result_message = f"""
✅ **Model Changed!**

{new_model.emoji} Now using: **{new_model.display_name}**
📊 Context: {new_model.context_window}
💰 Tier: {'Paid' if new_model.tier == ModelTier.PAID else 'Free'}

Your next /ai command will use this model.
"""
            
            # Add important notes
            result_message += "\n\n⚠️ **Important:**"
            result_message += f"\n• Make sure '{new_model.display_name}' is **enabled** in Cursor Settings > Models"
            result_message += "\n• If the model isn't working, check Cursor Settings and toggle it ON"
            
            # Add warning for paid models
            if new_model.tier == ModelTier.PAID:
                result_message += "\n• This is a paid model - ensure your Cursor subscription includes access"
                result_message += "\n💡 If you see errors, try: `/model haiku` or `/model gemini`"
            
            await query.edit_message_text(result_message, parse_mode="Markdown")
        else:
            await query.edit_message_text(f"❌ {message}", parse_mode="Markdown")
    
    @require_auth
    async def _cmd_models(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all available AI models."""
        user_id = update.effective_user.id
        self.sentinel.log_command(user_id, "/models")
        
        current_model = self.user_prefs.get_user_model(user_id)
        
        # Build detailed model list
        lines = ["📋 **Available AI Models**\n"]
        
        # Paid models
        lines.append("💎 **Paid Models:** *(Requires Cursor subscription with access)*")
        for alias, model in AVAILABLE_MODELS.items():
            if model.tier == ModelTier.PAID:
                current_marker = " ✅" if model.alias == current_model.alias else ""
                lines.append(
                    f"  `{model.alias}` - {model.display_name} "
                    f"({model.context_window}){current_marker}"
                )
                lines.append(f"      _{model.description}_")
        
        lines.append("")
        lines.append("⚠️ **Note:** Paid models require a Cursor subscription that includes access to that specific model.")
        lines.append("💡 If you select a paid model you don't have access to, Cursor will show an error.")
        lines.append("")
        
        # Free models
        lines.append("✨ **Free Models:** *(Available to all users)*")
        for alias, model in AVAILABLE_MODELS.items():
            if model.tier == ModelTier.FREE:
                current_marker = " ✅" if model.alias == current_model.alias else ""
                lines.append(
                    f"  `{model.alias}` - {model.display_name} "
                    f"({model.context_window}){current_marker}"
                )
                lines.append(f"      _{model.description}_")
        
        lines.append("")
        lines.append("💡 **Quick Switch:** `/model opus` or `/model haiku`")
        lines.append("🔘 **Menu:** `/model` (interactive buttons)")
        lines.append("")
        lines.append("📚 **Need Help?** Check your Cursor subscription settings to see which models you have access to.")
        
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    
    # ==========================================
    # Diff Expansion Callbacks
    # ==========================================
    
    @require_auth
    async def _cmd_diff_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle diff expansion button callbacks."""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        callback_data = query.data
        
        if callback_data == "diff_full":
            # Show full diff
            self.sentinel.log_command(user_id, "/diff (expanded)")
            
            diff_result = self.cli.git_diff(stat_only=False)
            
            if diff_result.success and diff_result.stdout.strip():
                # Truncate if too long for Telegram
                diff_content = diff_result.stdout.strip()
                if len(diff_content) > 3500:
                    diff_content = diff_content[:3500] + "\n\n... (truncated, use terminal for full diff)"
                
                message = f"📖 **Full Diff:**\n\n```diff\n{diff_content}\n```"
            else:
                message = "_(No changes to display)_"
            
            # Send as new message (don't edit, as the diff might be long)
            await query.message.reply_text(
                self._truncate_message(message), 
                parse_mode="Markdown"
            )
        
        elif callback_data == "diff_keep":
            # Git Commit - stage and commit all changes
            self.sentinel.log_command(user_id, "/commit (git commit)")
            
            # Stage all changes
            add_result = self.cli.git_add_all()
            if not add_result.success:
                await query.message.reply_text(
                    f"❌ Git stage failed: {add_result.stderr}",
                    parse_mode="Markdown"
                )
                return
            
            # Commit with auto message
            commit_msg = f"TeleCode: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            commit_result = self.cli.git_commit(commit_msg)
            
            if commit_result.success:
                try:
                    await query.edit_message_text(
                        query.message.text + "\n\n💾 **Git committed!**\n_Use /push to push to remote._",
                        parse_mode="Markdown"
                    )
                except Exception:
                    await query.message.reply_text("💾 **Git committed!**\n_Use /push to push._", parse_mode="Markdown")
            else:
                await query.message.reply_text(
                    f"❌ Git commit failed: {commit_result.stderr}",
                    parse_mode="Markdown"
                )
        
        elif callback_data == "diff_undo":
            # Git Restore - show confirmation button (two-step for safety)
            self.sentinel.log_command(user_id, "/revert (git restore - step 1)")
            
            # Show confirmation with a confirm button
            keyboard = [[
                InlineKeyboardButton("⚠️ Yes, Git Restore", callback_data="diff_undo_confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="diff_undo_cancel"),
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                "⚠️ **Confirm Git Restore**\n\n"
                "This will run `git restore .` + `git clean -fd`\n"
                "**Permanently discards** ALL uncommitted changes!\n\n"
                "⚠️ **This cannot be undone!**",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        
        elif callback_data == "diff_undo_confirm":
            # Actually git restore all changes
            self.sentinel.log_command(user_id, "/revert (git restore - confirmed)")
            
            result = self.cli.git_restore()
            
            if result.success:
                try:
                    await query.edit_message_text(
                        "🗑️ **Git restore complete!**\n\n"
                        "All uncommitted changes have been discarded.",
                        parse_mode="Markdown"
                    )
                except Exception:
                    await query.message.reply_text(
                        "🗑️ **Git restore complete!**",
                        parse_mode="Markdown"
                    )
            else:
                await query.message.reply_text(
                    f"❌ Git restore failed: {result.stderr}",
                    parse_mode="Markdown"
                )
        
        elif callback_data == "diff_undo_cancel":
            # Cancel the undo operation
            try:
                await query.edit_message_text(
                    "✅ Undo cancelled. Your changes are still intact.",
                    parse_mode="Markdown"
                )
            except Exception:
                await query.message.reply_text(
                    "✅ Undo cancelled. Your changes are still intact.",
                    parse_mode="Markdown"
                )
        
        elif callback_data == "diff_continue":
            # Continue - prompt user to send follow-up
            self.sentinel.log_command(user_id, "/ai (Continue)")
            
            await query.message.reply_text(
                "▶️ **Continue with AI**\n\n"
                "Send your next prompt as a message.\n\n"
                "_Example: \"Now add unit tests for the changes\"_",
                parse_mode="Markdown"
            )
    
    # ==========================================
    # AI Control Callbacks
    # ==========================================
    
    @require_auth
    async def _cmd_ai_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle AI control button callbacks."""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        callback_data = query.data
        
        agent = self._get_cursor_agent()
        
        if callback_data == "ai_check":
            # Check for changes - show diff summary + OCR text from latest prompt
            self.sentinel.log_command(user_id, "/ai status (button)")
            
            # First, get the git diff summary
            result = agent.get_diff_summary()
            
            if result.success and result.data:
                data = result.data
                git_summary = data.get("summary", "No summary available")
                has_changes = data.get("has_changes", False)
                
                # Capture screenshot and extract text via OCR
                ocr_result = agent.capture_and_extract_text()
                ocr_summary = ""
                screenshot_path = None
                
                if ocr_result.success and ocr_result.data:
                    ocr_summary = ocr_result.data.get("summary", "")
                    screenshot_path = ocr_result.data.get("screenshot_path")
                
                # Build the combined message with git summary and OCR summary
                combined_message = git_summary
                if ocr_summary and len(ocr_summary.strip()) > 10:
                    combined_message += f"\n\n📝 **AI Summary:**\n\n{ocr_summary}"
                
                # Add buttons (Cursor controls only, no git)
                keyboard = []
                if has_changes:
                    keyboard = [
                        [
                            InlineKeyboardButton("✅ Accept", callback_data="ai_accept"),
                            InlineKeyboardButton("❌ Reject", callback_data="ai_reject"),
                        ],
                        [InlineKeyboardButton("📖 View Full Diff", callback_data="diff_full")],
                    ]
                
                reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
                
                # Send screenshot with combined message (git summary + OCR summary)
                if screenshot_path and Path(screenshot_path).exists():
                    try:
                        with open(screenshot_path, 'rb') as photo:
                            # Send photo with caption (truncated to 1024 chars for Telegram limit)
                            caption = self._truncate_message(combined_message)[:1024]
                            await query.message.reply_photo(
                                photo=photo,
                                caption=caption,
                                parse_mode="Markdown",
                                reply_markup=reply_markup
                            )
                        
                        # If combined message is longer than caption limit, send full text as separate message
                        if len(combined_message) > 1024:
                            # Check if full message is too long for text message (Telegram limit ~4096 chars)
                            if len(combined_message) > 3800:
                                # Send as a text document for full scrollability
                                await self._send_ocr_as_document(
                                    query.message,
                                    combined_message,
                                    "check_summary.txt",
                                    "📊 **Full Check Summary** (git diff + AI summary)"
                                )
                            else:
                                # Send as formatted text message
                                await query.message.reply_text(
                                    self._truncate_message(combined_message),
                                    parse_mode="Markdown"
                                )
                    except Exception as e:
                        logger.warning(f"Failed to send screenshot: {e}")
                        # Fallback: send text message only
                        if len(combined_message) > 3800:
                            await self._send_ocr_as_document(
                                query.message,
                                combined_message,
                                "check_summary.txt",
                                "📊 **Check Summary**"
                            )
                        else:
                            await query.message.reply_text(
                                self._truncate_message(combined_message),
                                parse_mode="Markdown",
                                reply_markup=reply_markup
                            )
                else:
                    # No screenshot - send text message only
                    if len(combined_message) > 3800:
                        await self._send_ocr_as_document(
                            query.message,
                            combined_message,
                            "check_summary.txt",
                            "📊 **Check Summary**"
                        )
                    else:
                        await query.message.reply_text(
                            self._truncate_message(combined_message),
                            parse_mode="Markdown",
                            reply_markup=reply_markup
                        )
            else:
                message = f"❌ Check failed: {result.error or 'Unknown error'}"
                await query.message.reply_text(message, parse_mode="Markdown")
        
        elif callback_data == "ai_accept":
            # Accept changes via Cursor automation (Ctrl+Enter)
            self.sentinel.log_command(user_id, "/ai accept (button)")
            
            result = agent.accept_changes_via_cursor()
            
            if result.success:
                shortcut = result.data.get("shortcut", "Ctrl+Enter") if result.data else "Ctrl+Enter"
                message = f"""✅ **Changes Accepted in Cursor!**

The AI changes have been applied via {shortcut}.

📌 _This only affects Cursor, not git._
💡 _Use `/commit` to git commit, `/push` to push._"""
            else:
                message = f"❌ Accept failed: {result.error or result.message}"
            
            try:
                await query.edit_message_text(
                    query.message.text + f"\n\n{message}",
                    parse_mode="Markdown"
                )
            except Exception:
                await query.message.reply_text(message, parse_mode="Markdown")
        
        elif callback_data == "ai_reject":
            # Show reject confirmation (Cursor only, no git)
            self.sentinel.log_command(user_id, "/ai reject (button)")
            
            # Both modes use Escape to reject changes
            method = "Escape"
            
            keyboard = [[
                InlineKeyboardButton("⚠️ Yes, Reject Changes", callback_data="ai_reject_confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="ai_reject_cancel"),
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                f"⚠️ **Confirm Reject**\n\n"
                f"This will reject the AI changes **in Cursor**.\n\n"
                f"🔄 Method: {method}\n\n"
                f"📌 _This uses Cursor automation, not git._\n"
                f"💡 _For git revert, use `/revert CONFIRM` instead._",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        
        elif callback_data == "ai_reject_confirm":
            # Actually reject using Cursor automation (Escape)
            self.sentinel.log_command(user_id, "/ai reject (confirmed)")
            
            result = agent.revert_changes_via_cursor()
            
            if result.success:
                data = result.data or {}
                shortcut = data.get("shortcut", "Escape")
                message = f"""❌ **Changes Rejected in Cursor!**

🔄 Method: {shortcut}

📌 _This only affected Cursor, not git._
💡 _Use `/revert CONFIRM` for git restore._"""
                
                # Capture screenshot after rejection
                screenshot_path = agent.capture_screenshot()
                
                # Send screenshot with message if available
                if screenshot_path and Path(screenshot_path).exists():
                    try:
                        # Delete the confirmation message first
                        try:
                            await query.message.delete()
                        except Exception:
                            pass
                        
                        # Send photo with caption to the chat
                        with open(screenshot_path, 'rb') as photo:
                            await query.message.chat.send_photo(
                                photo=photo,
                                caption=self._truncate_message(message)[:1024],  # Photo captions max 1024 chars
                                parse_mode="Markdown"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to send rejection screenshot: {e}")
                        # Fallback to text message
                        try:
                            await query.edit_message_text(message, parse_mode="Markdown")
                        except Exception:
                            await query.message.reply_text(message, parse_mode="Markdown")
                else:
                    # No screenshot - just send text message
                    try:
                        await query.edit_message_text(message, parse_mode="Markdown")
                    except Exception:
                        await query.message.reply_text(message, parse_mode="Markdown")
            else:
                message = f"❌ Reject failed: {result.error or result.message}"
                try:
                    await query.edit_message_text(message, parse_mode="Markdown")
                except Exception:
                    await query.message.reply_text(message, parse_mode="Markdown")
        
        elif callback_data == "ai_reject_cancel":
            # Cancel reject
            try:
                await query.edit_message_text(
                    "✅ Reject cancelled. Your changes are still intact.",
                    parse_mode="Markdown"
                )
            except Exception:
                await query.message.reply_text(
                    "✅ Reject cancelled. Your changes are still intact.",
                    parse_mode="Markdown"
                )
        
        elif callback_data == "ai_continue_prompt":
            # Prompt user to send follow-up
            self.sentinel.log_command(user_id, "/ai continue (button)")
            
            await query.message.reply_text(
                "▶️ **Continue with AI**\n\n"
                "Send your next prompt as a message, or use:\n"
                "`/ai continue <your follow-up prompt>`\n\n"
                "_Example: \"Now add unit tests for the changes\"_",
                parse_mode="Markdown"
            )
        
        elif callback_data == "ai_view_diff":
            # View diff from latest prompt only
            self.sentinel.log_command(user_id, "/ai diff (button)")
            
            result = agent.get_diff(full=True, latest_only=True)
            
            if result.success and result.data:
                diff_content = result.data.get("diff", "")
                if diff_content:
                    # Truncate if too long
                    if len(diff_content) > 3500:
                        diff_content = diff_content[:3500] + "\n\n... (truncated)"
                    message = f"📖 **Diff from Latest Prompt:**\n\n```diff\n{diff_content}\n```"
                else:
                    message = "_(No diff available - files may be new/untracked)_"
                
                await query.message.reply_text(
                    self._truncate_message(message),
                    parse_mode="Markdown"
                )
            else:
                await query.message.reply_text(
                    f"❌ Failed to get diff: {result.error or 'Unknown error'}",
                    parse_mode="Markdown"
                )
        
        elif callback_data == "ai_cleanup":
            # Cleanup old agent tabs
            self.sentinel.log_command(user_id, "/ai cleanup (button)")
            
            # Check if cleanup is needed and send status message
            max_agents = 5
            if agent.session.agent_count > max_agents:
                agents_to_close = agent.session.agent_count - max_agents
                await query.message.reply_text(
                    f"🔄 Closing {agents_to_close} old agent tabs...",
                    parse_mode="Markdown"
                )
            
            result = agent.cleanup_agents(max_agents=max_agents)
            
            if result.success:
                data = result.data or {}
                agents_closed = data.get("agents_closed", 0)
                agent_count = data.get("agent_count", 0)
                
                if agents_closed > 0:
                    message = f"🧹 **Cleaned up {agents_closed} agent tab(s)**\n\nRemaining agents: {agent_count}"
                else:
                    message = f"✅ No cleanup needed.\n\nCurrent agent count: {agent_count}"
                
                await query.message.reply_text(message, parse_mode="Markdown")
            else:
                await query.message.reply_text(
                    f"❌ Cleanup failed: {result.error or 'Unknown error'}",
                    parse_mode="Markdown"
                )
        
        elif callback_data == "ai_mode":
            # Show mode selection
            self.sentinel.log_command(user_id, "/ai mode (button)")
            
            current_mode = agent.get_prompt_mode()
            
            keyboard = [
                [InlineKeyboardButton(
                    f"{'✓ ' if current_mode == 'agent' else ''}🤖 Agent (auto-save)", 
                    callback_data="ai_mode_agent"
                )],
                [InlineKeyboardButton(
                    f"{'✓ ' if current_mode == 'chat' else ''}💬 Chat (manual keep)", 
                    callback_data="ai_mode_chat"
                )],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                f"⚙️ **Select Prompt Mode**\n\n"
                f"Current: **{current_mode}**\n\n"
                f"🤖 **Agent** - Auto-saves files to disk (SAFEST)\n"
                f"   _Won't lose work, Reject uses Escape_\n\n"
                f"💬 **Chat** - Proposed changes need Accept\n"
                f"   _More control, Reject uses Escape_",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        
        elif callback_data.startswith("ai_mode_"):
            # Set mode
            new_mode = callback_data.replace("ai_mode_", "")
            self.sentinel.log_command(user_id, f"/ai mode {new_mode}")
            
            result = agent.set_prompt_mode(new_mode)
            
            if result.success:
                data = result.data or {}
                description = data.get("description", "")
                auto_save = data.get("auto_save", False)
                
                message = f"✅ **Mode Changed!**\n\n{description}"
                if auto_save:
                    message += "\n\n💡 _Files auto-save, Reject uses Escape_"
                else:
                    message += "\n\n⚠️ _Click Accept to apply, Reject uses Escape_"
                
                try:
                    await query.edit_message_text(message, parse_mode="Markdown")
                except Exception:
                    await query.message.reply_text(message, parse_mode="Markdown")
            else:
                await query.message.reply_text(
                    f"❌ Failed: {result.error or 'Unknown error'}",
                    parse_mode="Markdown"
                )
        
        elif callback_data == "ai_run":
            # Approve a pending terminal command in Cursor
            self.sentinel.log_command(user_id, "/ai run (button)")
            
            # Show confirmation first
            keyboard = [
                [
                    InlineKeyboardButton("✅ Yes, Run It", callback_data="ai_run_confirm"),
                    InlineKeyboardButton("🚫 Cancel", callback_data="ai_cancel"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                "⚠️ **Cursor wants to run a command**\n\n"
                "The AI is requesting to execute a terminal command.\n\n"
                "**Do you want to approve this?**\n\n"
                "_This will press Enter in Cursor to confirm._",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        
        elif callback_data == "ai_run_confirm":
            # Confirmed - approve the run command
            self.sentinel.log_command(user_id, "/ai run confirm")
            
            result = agent.approve_run()
            
            if result.success:
                message = f"✅ **Command Approved!**\n\n{result.message}\n\n_The AI will now execute the command._"
            else:
                message = f"❌ **Failed to approve:** {result.error or result.message}"
            
            try:
                await query.edit_message_text(message, parse_mode="Markdown")
            except Exception:
                await query.message.reply_text(message, parse_mode="Markdown")
        
        elif callback_data == "ai_web_search":
            # Approve a pending web search in Cursor
            self.sentinel.log_command(user_id, "/ai web_search (button)")
            
            # Show confirmation first
            keyboard = [
                [
                    InlineKeyboardButton("🌐 Yes, Search", callback_data="ai_web_search_confirm"),
                    InlineKeyboardButton("🚫 Cancel", callback_data="ai_cancel"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                "🌐 **Cursor wants to search the web**\n\n"
                "The AI is requesting to perform a web search for context.\n\n"
                "**Do you want to approve this?**\n\n"
                "_This will press Enter in Cursor to confirm._",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        
        elif callback_data == "ai_web_search_confirm":
            # Confirmed - approve the web search
            self.sentinel.log_command(user_id, "/ai web_search confirm")
            
            result = agent.approve_web_search()
            
            if result.success:
                message = f"🌐 **Web Search Approved!**\n\n{result.message}\n\n_The AI will now search the web._"
            else:
                message = f"❌ **Failed to approve:** {result.error or result.message}"
            
            try:
                await query.edit_message_text(message, parse_mode="Markdown")
            except Exception:
                await query.message.reply_text(message, parse_mode="Markdown")
        
        elif callback_data == "ai_cancel":
            # Cancel a pending action in Cursor (Escape for dialogs)
            self.sentinel.log_command(user_id, "/ai cancel (button)")
            
            result = agent.cancel_action()
            
            if result.success:
                message = f"🚫 **Action Cancelled!**\n\n{result.message}\n\n_Pressed Escape in Cursor._"
            else:
                message = f"❌ **Failed to cancel:** {result.error or result.message}"
            
            try:
                await query.edit_message_text(message, parse_mode="Markdown")
            except Exception:
                await query.message.reply_text(message, parse_mode="Markdown")
        
        elif callback_data == "ai_stop" or callback_data.startswith("ai_stop:"):
            # Stop the current AI generation (Ctrl+Shift+Backspace)
            # Parse agent_id from callback_data if present (format: "ai_stop:{agent_id}")
            agent_id = None
            if ":" in callback_data:
                try:
                    agent_id = int(callback_data.split(":")[1])
                    self.sentinel.log_command(user_id, f"/ai stop (button, agent_id={agent_id})")
                except (ValueError, IndexError):
                    self.sentinel.log_command(user_id, "/ai stop (button)")
            else:
                self.sentinel.log_command(user_id, "/ai stop (button)")
            
            result = agent.stop_generation(agent_id=agent_id)
            
            if result.success:
                agent_info = f" (agent tab {agent_id + 1})" if agent_id is not None else ""
                message = f"🛑 **Generation Stopped!**{agent_info}\n\n⏳ Please wait for the **AI Completed** message to see the final results of this prompt."
            else:
                message = f"❌ **Failed to stop:** {result.error or result.message}"
            
            try:
                await query.edit_message_text(message, parse_mode="Markdown")
            except Exception:
                await query.message.reply_text(message, parse_mode="Markdown")
        
        elif callback_data == "ai_send_continue" or callback_data.startswith("ai_send_continue:"):
            # Press Enter to click the Continue button in Cursor
            # Parse agent_id from callback_data if present (format: "ai_send_continue:{agent_id}")
            agent_id = None
            if ":" in callback_data:
                try:
                    agent_id = int(callback_data.split(":")[1])
                    self.sentinel.log_command(user_id, f"/ai continue (button, agent_id={agent_id})")
                except (ValueError, IndexError):
                    self.sentinel.log_command(user_id, "/ai continue (button)")
            else:
                self.sentinel.log_command(user_id, "/ai continue (button)")
            
            result = agent.send_continue(agent_id=agent_id)
            
            if result.success:
                agent_info = f" (agent tab {agent_id + 1})" if agent_id is not None else ""
                message = f"➡️ **Continue Pressed!**{agent_info}\n\n{result.message}\n\n_Pressed Enter to activate Continue button._"
            else:
                message = f"❌ **Failed to continue:** {result.error or result.message}"
            
            try:
                await query.edit_message_text(message, parse_mode="Markdown")
            except Exception:
                await query.message.reply_text(message, parse_mode="Markdown")
    
    # ==========================================
    # Cursor Control Callbacks
    # ==========================================
    
    @require_auth
    async def _cmd_cursor_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Cursor control button callbacks (open, status, etc.)."""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        callback_data = query.data
        
        agent = self._get_cursor_agent()
        
        if callback_data == "cursor_open":
            # Open Cursor for the current workspace with live status updates
            self.sentinel.log_command(user_id, "cursor open (button)")
            
            workspace_name = self.cli.current_dir.name
            
            # Send initial pending message
            pending_msg = await query.message.reply_text(
                f"🚀 **Opening Cursor...**\n\n"
                f"📂 Workspace: `{workspace_name}`\n"
                f"⏳ Status: Launching...",
                parse_mode="Markdown"
            )
            
            # Create a callback to update the message
            last_message = {"text": ""}  # Use dict to allow mutation in closure
            
            async def status_callback(message: str, is_complete: bool):
                """Update the Telegram message with current status."""
                # Only update if message changed (to avoid rate limiting)
                if message != last_message["text"]:
                    last_message["text"] = message
                    try:
                        if is_complete:
                            # Add buttons based on final status
                            if "✅" in message:
                                # Success - offer to send a prompt
                                keyboard = [[
                                    InlineKeyboardButton("🤖 Send AI Prompt", callback_data="ai_prompt_start"),
                                    InlineKeyboardButton("📊 Check Status", callback_data="cursor_status"),
                                ]]
                                reply_markup = InlineKeyboardMarkup(keyboard)
                            else:
                                # Error or warning - offer retry
                                keyboard = [[
                                    InlineKeyboardButton("🔄 Retry", callback_data="cursor_open"),
                                    InlineKeyboardButton("📊 Check Status", callback_data="cursor_status"),
                                ]]
                                reply_markup = InlineKeyboardMarkup(keyboard)
                            
                            await pending_msg.edit_text(
                                f"💻 **Cursor Status**\n\n{message}",
                                parse_mode="Markdown",
                                reply_markup=reply_markup
                            )
                        else:
                            # In progress - show animated status
                            await pending_msg.edit_text(
                                f"💻 **Opening Cursor**\n\n"
                                f"📂 Workspace: `{workspace_name}`\n"
                                f"{message}",
                                parse_mode="Markdown"
                            )
                    except Exception as e:
                        logger.debug(f"Failed to update status message: {e}")
            
            # Open Cursor and wait for it to be ready
            result = await agent.open_cursor_and_wait(
                status_callback=status_callback,
                timeout=30.0,
                poll_interval=1.5
            )
            
            # Log result
            if result.success:
                logger.info(f"Cursor opened successfully for {workspace_name}")
            else:
                logger.warning(f"Cursor open failed: {result.message}")
        
        elif callback_data == "cursor_status":
            # Check Cursor status
            self.sentinel.log_command(user_id, "cursor status (button)")
            
            status = agent.check_cursor_status()
            
            status_emoji = {
                "not_running": "🔴 Not Running",
                "starting": "🟡 Starting...",
                "running": "🟠 Running (different workspace)",
                "ready": "🟢 Ready",
            }
            
            status_text = status_emoji.get(status.get("status", ""), "⚪ Unknown")
            message = status.get("message", "Unable to determine status")
            
            response = f"💻 **Cursor Status**\n\n{status_text}\n\n{message}"
            
            # Add action buttons based on status
            if not status.get("workspace_open"):
                keyboard = [[InlineKeyboardButton("🚀 Open in Cursor", callback_data="cursor_open")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.reply_text(response, parse_mode="Markdown", reply_markup=reply_markup)
            else:
                keyboard = [[InlineKeyboardButton("🤖 Send AI Prompt", callback_data="ai_prompt_start")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.reply_text(response, parse_mode="Markdown", reply_markup=reply_markup)
        
        elif callback_data == "ai_prompt_start":
            # Prompt user to send an AI message
            self.sentinel.log_command(user_id, "ai prompt start (button)")
            
            await query.message.reply_text(
                "🤖 **Ready for AI Prompt**\n\n"
                "Send your coding request as a message.\n\n"
                "_Example: \"Create a login form with validation\"_\n\n"
                "Or use: `/ai <your prompt>`",
                parse_mode="Markdown"
            )
    
    # ==========================================
    # Message Handlers
    # ==========================================
    
    @require_auth
    async def _handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle voice messages - transcribe and execute as AI prompt."""
        if not self.voice.is_available:
            await update.message.reply_text(
                "❌ Voice processing is not available.\n\n" + self.voice.get_status(),
                parse_mode="Markdown"
            )
            return
        
        await update.message.reply_text("🎤 Processing voice message...")
        
        # Download and process voice
        voice_path = await download_telegram_voice(update.message.voice, context.bot)
        
        if not voice_path:
            await update.message.reply_text("❌ Failed to download voice message")
            return
        
        # Transcribe
        success, text = await self.voice.process_voice_file(voice_path)
        
        if success:
            await update.message.reply_text(f"📝 Transcribed: _{text}_", parse_mode="Markdown")
            # Execute as AI prompt
            await self._execute_ai_prompt(update, text)
        else:
            await update.message.reply_text(f"❌ Transcription failed: {text}")
    
    @require_auth
    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle plain text messages as AI prompts."""
        text = update.message.text.strip()
        
        if not text:
            return
        
        # Treat as AI prompt
        await self._execute_ai_prompt(update, text)
    
    # ==========================================
    # Bot Lifecycle
    # ==========================================
    
    async def start(self):
        """Start the bot."""
        logger.info("Starting TeleCode bot...")
        
        # Set bot commands
        await self._set_commands()
        
        # Load PIN/password from storage on startup (for persistence across sessions)
        try:
            from .lock_pin_storage import get_lock_pin_storage
            from .custom_lock import set_lock_pin, set_lock_password
            storage = get_lock_pin_storage()
            loaded_pin = storage.retrieve_pin()
            loaded_password = storage.retrieve_password()
            if loaded_pin:
                set_lock_pin(loaded_pin)
                logger.info("PIN loaded from storage on startup")
            elif loaded_password:
                set_lock_password(loaded_password)
                logger.info("Password loaded from storage on startup")
        except Exception as e:
            logger.debug(f"Could not load PIN/password on startup (may not be set): {e}")
        
        # Start sleep prevention if enabled
        prevent_sleep = os.getenv("PREVENT_SLEEP", "true").lower() == "true"
        if prevent_sleep:
            self.sleep_preventer.start()
        
        # Start system tray icon
        try:
            from .tray_icon import start_tray, get_tray
            self.tray = start_tray(
                on_settings=self._on_tray_settings,
                on_lock_screen=self._on_tray_lock_screen,
                on_virtual_display=self._on_tray_virtual_display,
                on_stop=self._request_stop
            )
            if self.tray:
                self.tray.set_connected()
        except Exception as e:
            logger.warning(f"Tray icon not available: {e}")
            self.tray = None
        
        # Start polling
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)
        
        logger.info("TeleCode bot is running!")
        
        # Update tray status
        if self.tray:
            self.tray.update_status("Connected")
        
        # Keep running - check for stop request periodically
        try:
            while not self._stop_requested:
                await asyncio.sleep(1)  # Check stop flag every second
            # Stop was requested (e.g., from system tray)
            logger.info("Stop flag detected, shutting down...")
            await self.stop()
        except (KeyboardInterrupt, SystemExit):
            await self.stop()
    
    def _request_stop(self):
        """Request the bot to stop (called from tray icon)."""
        self._stop_requested = True
        logger.info("Stop requested from system tray")
    
    def _update_tray_command(self, command: str):
        """Update the tray icon with the last command."""
        if self.tray:
            self.tray.update_last_command(command)
    
    def _on_tray_settings(self):
        """Handle Settings click from tray icon."""
        logger.info("Settings requested from system tray")
        try:
            import subprocess
            import threading
            
            # Check if running as frozen EXE (PyInstaller)
            is_frozen = getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS')
            
            if is_frozen:
                # Running as EXE - launch the EXE itself with --settings-only
                exe_path = sys.executable
                logger.info(f"Launching settings from EXE: {exe_path}")
                
                subprocess.Popen(
                    [exe_path, "--settings-only"],
                    # On Windows, use CREATE_NO_WINDOW to avoid console flash
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                # Running from source - launch main.py
                project_root = Path(__file__).parent.parent
                main_py = project_root / "main.py"
                
                # Use pythonw on Windows to avoid console window
                if sys.platform == "win32":
                    pythonw = Path(sys.executable).parent / "pythonw.exe"
                    python_exe = str(pythonw) if pythonw.exists() else sys.executable
                else:
                    python_exe = sys.executable
                
                subprocess.Popen(
                    [python_exe, str(main_py), "--settings-only"],
                    cwd=str(project_root),
                    # On Windows, use CREATE_NO_WINDOW to avoid console flash
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            
            logger.info("Settings GUI launched successfully")
        except Exception as e:
            logger.error(f"Failed to open settings: {e}", exc_info=True)
    
    def _on_tray_lock_screen(self):
        """Handle Turn Off Display click from tray icon (Windows only)."""
        logger.info("Turn Off Display requested from system tray")
        try:
            from .virtual_display_helper import turn_off_display_safe
            from .custom_lock import is_locked
            
            # Check if already locked - if so, do nothing (unlock happens via PIN entry)
            if is_locked():
                logger.info("Display is already locked - unlock via PIN entry")
                return
            
            # Define unlock callback to reset tray state when user unlocks via PIN
            def on_unlock():
                """Called when user unlocks via PIN entry - reset tray state."""
                if self.tray:
                    self.tray.set_screen_locked(False)
                logger.info("Lock unlocked via PIN - tray state reset, ready for next Turn Off Display")
            
            # Use secure mode by default (password required on wake)
            # Pass unlock callback so tray icon resets when user unlocks via PIN
            success, message = turn_off_display_safe(secure=True, on_unlock=on_unlock)
            if success:
                logger.info(f"Display turned off with secure lock: {message}")
                # Update tray icon state to locked (but menu still shows "Turn Off Display")
                if self.tray:
                    self.tray.set_screen_locked(True)
            else:
                logger.error(f"Failed to turn off display: {message}")
        except Exception as e:
            logger.error(f"Failed to turn off display: {e}", exc_info=True)
    
    def _on_tray_virtual_display(self, start: bool):
        """Handle Virtual Display toggle from tray icon (Linux only)."""
        if sys.platform.startswith("linux"):
            try:
                from .cursor_agent import start_virtual_display, stop_virtual_display, VirtualDisplayManager
                
                if start:
                    logger.info("Starting virtual display from system tray")
                    success = start_virtual_display()
                    if success:
                        logger.info("Virtual display started successfully")
                        if self.tray:
                            self.tray.set_virtual_display_status(True)
                    else:
                        logger.warning("Failed to start virtual display")
                        if self.tray:
                            self.tray.set_virtual_display_status(False)
                else:
                    logger.info("Stopping virtual display from system tray")
                    stop_virtual_display()
                    if self.tray:
                        self.tray.set_virtual_display_status(False)
            except Exception as e:
                logger.error(f"Virtual display toggle failed: {e}")
                if self.tray:
                    self.tray.set_virtual_display_status(False)
        else:
            logger.warning("Virtual display is only available on Linux")
    
    async def stop(self):
        """Stop the bot gracefully."""
        logger.info("Stopping TeleCode bot...")
        self.sleep_preventer.stop()
        
        # Stop tray icon
        if self.tray:
            try:
                from .tray_icon import stop_tray
                stop_tray()
            except Exception:
                pass
        
        # Stop Telegram bot
        try:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
        except Exception as e:
            logger.warning(f"Error stopping bot app: {e}")
        
        # Ensure lock file is released
        try:
            import sys
            from pathlib import Path
            # Import the release function from main
            # Since we're in a different module, we'll handle it via atexit
            # which should already be registered
        except Exception:
            pass
        
        logger.info("TeleCode bot stopped")


def create_bot_from_env() -> Optional[TeleCodeBot]:
    """
    Create a TeleCodeBot instance from environment variables.
    
    SECURITY: Token is loaded from secure vault first, .env as fallback.
    
    Returns:
        TeleCodeBot instance or None if configuration is invalid.
    """
    from dotenv import load_dotenv
    from src.system_utils import get_user_data_dir
    
    # Load .env from user data directory first (for installed applications)
    user_data_dir = get_user_data_dir()
    env_path = user_data_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Fallback to current directory (for development)
        load_dotenv()
    
    token = None
    
    # SEC-006: Try to load token from secure vault first
    try:
        from .token_vault import get_vault, mask_token
        vault = get_vault()
        token = vault.retrieve_token()
        
        if token:
            logger.info(f"Token loaded from secure vault: {mask_token(token)}")
    except ImportError:
        logger.warning("Token vault not available, using .env")
    except Exception as e:
        logger.warning(f"Failed to load from vault: {type(e).__name__}")
    
    # Fallback to .env if vault didn't work
    if not token:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        
        # Check if it's the placeholder
        if token == "[STORED_IN_SECURE_VAULT]":
            logger.error("Token marked as in vault but vault retrieval failed")
            return None
        
        if token:
            logger.info("Token loaded from .env (consider using vault for better security)")
    
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found in vault or .env")
        return None
    
    sentinel = create_sentinel_from_env()
    if not sentinel:
        logger.error("Failed to create SecuritySentinel")
        return None
    
    return TeleCodeBot(token, sentinel)



