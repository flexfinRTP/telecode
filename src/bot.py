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
  /accept   - Stage and commit all changes
  /revert   - Discard all uncommitted changes
  /ai       - Execute AI prompt via Cursor CLI
    /ai <prompt>         - Send prompt to Cursor
    /ai accept [msg]     - Accept and commit all changes
    /ai revert           - Discard all changes
    /ai continue <prompt>- Follow-up prompt
    /ai stop             - Clear session
    /ai status           - Check agent status
  /cd       - Change current directory
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
import logging
import asyncio
import time
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
from .cursor_agent import CursorAgentBridge, get_agent_for_workspace, AgentState

logger = logging.getLogger("telecode.bot")

# Maximum message length for Telegram
MAX_MESSAGE_LENGTH = 4096

# Conversation states for /create command
CREATE_AWAITING_NAME, CREATE_AWAITING_CONFIRM = range(2)


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
                ],
                CREATE_AWAITING_CONFIRM: [
                    CallbackQueryHandler(self._cmd_create_confirm, pattern="^create_confirm$"),
                    CallbackQueryHandler(self._cmd_create_cancel_btn, pattern="^create_cancel$"),
                    CommandHandler("cancel", self._cmd_create_cancel),
                ],
            },
            fallbacks=[CommandHandler("cancel", self._cmd_create_cancel)],
            per_user=True,
            per_chat=True,
        )
        self.app.add_handler(create_conv_handler)
        
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
            CommandHandler("accept", self._cmd_accept),
            CommandHandler("revert", self._cmd_revert),
            CommandHandler("log", self._cmd_log),
            CommandHandler("branch", self._cmd_branch),
            
            # File/Navigation commands
            CommandHandler("cd", self._cmd_cd),
            CommandHandler("ls", self._cmd_ls),
            CommandHandler("read", self._cmd_read),
            CommandHandler("pwd", self._cmd_pwd),
            
            # AI commands
            CommandHandler("ai", self._cmd_ai),
            
            # Model selection commands
            CommandHandler("model", self._cmd_model),
            CommandHandler("models", self._cmd_models),
            
            # Model selection callback handler
            CallbackQueryHandler(self._cmd_model_callback, pattern="^model_"),
            
            # Diff expansion callback handler
            CallbackQueryHandler(self._cmd_diff_callback, pattern="^diff_"),
            
            # AI control callback handler
            CallbackQueryHandler(self._cmd_ai_callback, pattern="^ai_"),
            
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
            BotCommand("accept", "Commit all changes"),
            BotCommand("revert", "Discard changes"),
            BotCommand("ai", "Run AI prompt"),
            BotCommand("model", "Select AI model"),
            BotCommand("models", "List available models"),
            BotCommand("cd", "Change directory"),
            BotCommand("ls", "List files"),
            BotCommand("log", "Recent commits"),
            BotCommand("info", "System info"),
        ]
        await self.app.bot.set_my_commands(commands)
    
    def _truncate_message(self, text: str) -> str:
        """Truncate message to Telegram's limit."""
        if len(text) <= MAX_MESSAGE_LENGTH:
            return text
        return text[:MAX_MESSAGE_LENGTH - 100] + "\n\n... (truncated)"
    
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
        self.sentinel.log_command(update.effective_user.id, "/start")
        
        lock_status = "🔒 Locked" if ScreenLockDetector.is_locked() else "🔓 Unlocked"
        
        # Get user's selected model
        user_id = update.effective_user.id
        current_model = self.user_prefs.get_user_model(user_id)
        
        welcome = f"""
🚀 **Welcome to TeleCode v0.1**

Your secure Telegram-to-Terminal bridge is active!

📂 **Sandbox:** `{self.sentinel.dev_root.name}`
🖥️ **Screen:** {lock_status}
🎤 **Voice:** {"✅ Enabled" if self.voice.is_available else "❌ Disabled"}
🤖 **Model:** {current_model.emoji} {current_model.display_name}

Type /help to see available commands.
Use /model to change AI model.
"""
        await update.message.reply_text(welcome, parse_mode="Markdown")
    
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
  /accept [msg] - Commit all changes
  /revert - Discard all changes ⚠️
  /log - Recent commits
  /branch - List branches

**Navigation:**
  /cd [path] - Change directory
  /ls [path] - List files
  /read [file] - Read file contents
  /pwd - Show current path

**AI Control:** 🤖
  /ai [prompt] - Send prompt to Cursor
  /ai accept [msg] - Commit AI changes
  /ai revert - Discard AI changes
  /ai continue [prompt] - Follow-up
  /ai stop - Clear session
  /ai status - Check state
  /model - Select AI model
  /models - List available models
  _(or just send text/voice)_

**System:**
  /info - System status
  /help - This message

📂 **Sandbox:** `{self.sentinel.dev_root.name}`
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
        info += f"\n\n📂 **Workspace**\n{self.cli.get_current_info()}"
        info += f"\n\n🤖 **AI Model**\n"
        info += f"  {current_model.emoji} {current_model.display_name}\n"
        info += f"  Context: {current_model.context_window}\n"
        info += f"  Tier: {'💎 Paid' if current_model.tier == ModelTier.PAID else '✨ Free'}"
        info += f"\n\n{self.voice.get_status()}"
        
        await update.message.reply_text(info, parse_mode="Markdown")
    
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
            
            # Build inline keyboard with expand and action buttons
            keyboard = [
                [InlineKeyboardButton("📖 View Full Diff", callback_data="diff_full")],
                [
                    InlineKeyboardButton("✅ Keep All", callback_data="diff_keep"),
                    InlineKeyboardButton("🗑️ Undo All", callback_data="diff_undo"),
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
    async def _cmd_accept(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stage and commit all changes."""
        self.sentinel.log_command(update.effective_user.id, "/accept")
        
        # Get commit message from args or generate default
        args = context.args
        if args:
            commit_msg = " ".join(args)
        else:
            commit_msg = f"TeleCode auto-commit: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Stage all changes
        add_result = self.cli.git_add_all()
        if not add_result.success:
            message = self._format_result("❌ Failed to stage changes", add_result)
            await update.message.reply_text(message, parse_mode="Markdown")
            return
        
        # Commit
        commit_result = self.cli.git_commit(commit_msg)
        if commit_result.success:
            message = f"✅ **Changes Committed!**\n\n📝 Message: _{commit_msg}_"
        else:
            message = self._format_result("❌ Commit Failed", commit_result)
        
        await update.message.reply_text(self._truncate_message(message), parse_mode="Markdown")
    
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
    async def _cmd_cd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Change current directory."""
        if not context.args:
            await update.message.reply_text(
                "Usage: /cd [path]\n\nExample: /cd myproject",
                parse_mode="Markdown"
            )
            return
        
        path = " ".join(context.args)
        self.sentinel.log_command(update.effective_user.id, f"/cd {path}")
        
        success, message = self.cli.set_working_directory(path)
        
        if success:
            # Show new location with git status
            info = self.cli.get_current_info()
            await update.message.reply_text(f"✅ {message}\n\n{info}", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ {message}", parse_mode="Markdown")
    
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
    async def _cmd_pwd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current working directory."""
        self.sentinel.log_command(update.effective_user.id, "/pwd")
        
        info = self.cli.get_current_info()
        await update.message.reply_text(info, parse_mode="Markdown")
    
    # ==========================================
    # Project Creation Commands (Conversation)
    # ==========================================
    
    @require_auth
    async def _cmd_create_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Start the project creation conversation.
        
        Step 1: Ask for project name.
        """
        self.sentinel.log_command(update.effective_user.id, "/create")
        
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
💻 **Cursor:** Opening...

**Next steps:**
• Start coding in Cursor
• Use /ai to run prompts
• Use /status to check git
• Use /accept to commit changes
"""
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
            /ai accept [message]   - Accept and commit all changes
            /ai revert             - Discard all changes
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
            await self._cmd_ai_accept(update, remaining_args)
        elif subcommand == "revert":
            await self._cmd_ai_revert(update)
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
        
        state_emoji = {
            "idle": "⚪",
            "prompt_sent": "🟡",
            "awaiting_changes": "🟡", 
            "changes_pending": "🟢",
            "processing": "🔵"
        }
        
        state = status.data.get("state", "idle") if status.data else "idle"
        
        help_text = f"""
🤖 **AI Commands** (Cursor Integration)

**Send Prompt:**
  `/ai <prompt>` - Send to Cursor AI

**Control Changes:**
  `/ai accept [msg]` - Commit all changes
  `/ai revert` - Discard all changes
  `/ai continue <prompt>` - Follow-up prompt
  `/ai stop` - Clear session

**Status:**
  `/ai status` - Check current state

**Current State:** {state_emoji.get(state, "⚪")} `{state}`
**Model:** {current_model.emoji} {current_model.display_name}
**Workspace:** `{self.cli.current_dir.name}`

💡 _You can also just send text as AI prompt!_
"""
        await update.message.reply_text(help_text, parse_mode="Markdown")
    
    async def _execute_ai_prompt(self, update: Update, prompt: str):
        """Execute an AI prompt via Cursor Agent Bridge - sends directly to Composer!"""
        user_id = update.effective_user.id
        self.sentinel.log_command(user_id, f"/ai {prompt[:50]}...")
        
        # Get user's selected model
        current_model = self.user_prefs.get_user_model(user_id)
        
        # Show "sending" message
        status_msg = await update.message.reply_text(
            f"🤖 Sending to Cursor with **{current_model.display_name}**...\n\n_{prompt}_", 
            parse_mode="Markdown"
        )
        
        # Get the Cursor Agent
        agent = self._get_cursor_agent()
        
        # Send prompt DIRECTLY to Cursor Composer
        result = agent.send_prompt(prompt, model=current_model.id)
        
        if result.success:
            # Build response
            message = f"""✅ **Prompt Sent to Cursor!**

🚀 Your prompt was sent directly to Cursor Composer via keyboard automation.

📝 **Prompt:** _{prompt[:100]}{'...' if len(prompt) > 100 else ''}_

⏳ **AI is now processing...**

When the AI finishes making changes, use:
• `/ai status` - Check for changes
• `/ai accept` - Commit the changes
• `/ai revert` - Discard the changes
• `/ai continue` - Send follow-up"""
            
            # Build inline keyboard for quick actions
            keyboard = [
                [
                    InlineKeyboardButton("📊 Check Changes", callback_data="ai_check"),
                    InlineKeyboardButton("📖 View Diff", callback_data="diff_full"),
                ],
                [
                    InlineKeyboardButton("✅ Accept All", callback_data="ai_accept"),
                    InlineKeyboardButton("🗑️ Revert All", callback_data="ai_revert"),
                ],
                [InlineKeyboardButton("▶️ Continue", callback_data="ai_continue_prompt")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
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
            
            await update.message.reply_text(self._truncate_message(message), parse_mode="Markdown")
    
    async def _cmd_ai_accept(self, update: Update, args: list):
        """Accept and commit all AI changes."""
        user_id = update.effective_user.id
        self.sentinel.log_command(user_id, "/ai accept")
        
        agent = self._get_cursor_agent()
        
        # Custom commit message if provided
        message = " ".join(args) if args else None
        
        result = agent.accept_changes(message)
        
        if result.success:
            data = result.data or {}
            response = f"""✅ **Changes Accepted!**

📝 **Commit:** {data.get('commit_message', 'TeleCode AI commit')}
📁 **Files:** {data.get('files_committed', 0)} committed

Use `/push` to push to remote."""
        else:
            response = f"❌ **Accept Failed**\n\n{result.message}\n\n{result.error or ''}"
        
        await update.message.reply_text(response, parse_mode="Markdown")
    
    async def _cmd_ai_revert(self, update: Update):
        """Revert all AI changes with confirmation."""
        user_id = update.effective_user.id
        self.sentinel.log_command(user_id, "/ai revert")
        
        agent = self._get_cursor_agent()
        
        # First check what we're reverting
        check = agent.check_changes()
        
        if check.data and check.data.get("has_changes"):
            file_count = check.data.get("file_count", 0)
            
            # Show confirmation
            keyboard = [[
                InlineKeyboardButton(f"⚠️ Yes, Revert {file_count} files", callback_data="ai_revert_confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="ai_revert_cancel"),
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"⚠️ **Confirm Revert**\n\n"
                f"This will **permanently discard** {file_count} file(s)!\n\n"
                f"**This cannot be undone!**",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("✅ No changes to revert.", parse_mode="Markdown")
    
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
            
            response = f"""📊 **AI Agent Status**

**State:** {state_emoji.get(state, state)}
**Workspace:** `{Path(data.get('workspace', '')).name}`
**Model:** {current_model.emoji} {current_model.display_name}

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
            
            # Add action buttons if there are pending changes
            if data.get('changes_detected'):
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Accept All", callback_data="ai_accept"),
                        InlineKeyboardButton("🗑️ Revert All", callback_data="ai_revert"),
                    ],
                    [InlineKeyboardButton("📖 View Diff", callback_data="diff_full")],
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
                await update.message.reply_text(f"✅ {message}", parse_mode="Markdown")
            else:
                await update.message.reply_text(f"❌ {message}", parse_mode="Markdown")
            return
        
        # Show interactive model selection menu
        current_model = self.user_prefs.get_user_model(user_id)
        
        # Build inline keyboard with model buttons
        keyboard = []
        
        # First row: Paid models
        paid_row = []
        for alias, model in AVAILABLE_MODELS.items():
            if model.tier == ModelTier.PAID:
                label = f"{model.emoji} {model.alias.title()}"
                if model.alias == current_model.alias:
                    label = f"✓ {label}"
                paid_row.append(InlineKeyboardButton(label, callback_data=f"model_{alias}"))
        keyboard.append(paid_row)
        
        # Second row: Free models
        free_row = []
        for alias, model in AVAILABLE_MODELS.items():
            if model.tier == ModelTier.FREE:
                label = f"{model.emoji} {model.alias.title()}"
                if model.alias == current_model.alias:
                    label = f"✓ {label}"
                free_row.append(InlineKeyboardButton(label, callback_data=f"model_{alias}"))
        keyboard.append(free_row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = format_model_selection_message(current_model)
        message += "\n💎 = Paid  |  ✨ = Free"
        
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
        lines.append("💎 **Paid Models:**")
        for alias, model in AVAILABLE_MODELS.items():
            if model.tier == ModelTier.PAID:
                current_marker = " ✅" if model.alias == current_model.alias else ""
                lines.append(
                    f"  `{model.alias}` - {model.display_name} "
                    f"({model.context_window}){current_marker}"
                )
                lines.append(f"      _{model.description}_")
        
        lines.append("")
        
        # Free models
        lines.append("✨ **Free Models:**")
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
            # Keep All - stage and commit all changes (equivalent to Cursor's "Keep All")
            self.sentinel.log_command(user_id, "/accept (Keep All)")
            
            # Stage all changes
            add_result = self.cli.git_add_all()
            if not add_result.success:
                await query.message.reply_text(
                    f"❌ Failed to stage changes: {add_result.stderr}",
                    parse_mode="Markdown"
                )
                return
            
            # Commit with auto message
            commit_msg = f"TeleCode: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            commit_result = self.cli.git_commit(commit_msg)
            
            if commit_result.success:
                # Update original message to show kept
                try:
                    await query.edit_message_text(
                        query.message.text + "\n\n✅ **Changes kept and committed!**",
                        parse_mode="Markdown"
                    )
                except Exception:
                    await query.message.reply_text("✅ **Changes kept and committed!**", parse_mode="Markdown")
            else:
                await query.message.reply_text(
                    f"❌ Commit failed: {commit_result.stderr}",
                    parse_mode="Markdown"
                )
        
        elif callback_data == "diff_undo":
            # Undo All - show confirmation button (two-step for safety)
            self.sentinel.log_command(user_id, "/revert (Undo All - step 1)")
            
            # Show confirmation with a confirm button
            keyboard = [[
                InlineKeyboardButton("⚠️ Yes, Undo All Changes", callback_data="diff_undo_confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="diff_undo_cancel"),
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                "⚠️ **Confirm Undo All**\n\n"
                "This will **permanently discard** ALL uncommitted changes!\n\n"
                "**This cannot be undone!**",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        
        elif callback_data == "diff_undo_confirm":
            # Actually undo/revert all changes
            self.sentinel.log_command(user_id, "/revert (Undo All - confirmed)")
            
            result = self.cli.git_restore()
            
            if result.success:
                try:
                    await query.edit_message_text(
                        "🗑️ **All changes have been undone!**\n\n"
                        "Your working directory is now clean.",
                        parse_mode="Markdown"
                    )
                except Exception:
                    await query.message.reply_text(
                        "🗑️ **All changes have been undone!**",
                        parse_mode="Markdown"
                    )
            else:
                await query.message.reply_text(
                    f"❌ Undo failed: {result.stderr}",
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
            # Check for changes
            self.sentinel.log_command(user_id, "/ai status (button)")
            
            result = agent.check_changes()
            
            if result.success and result.data:
                data = result.data
                if data.get("has_changes"):
                    diff_stat = data.get("diff_stat", "")
                    message = f"📊 **Changes Detected!**\n\n**{data.get('file_count', 0)} files modified**\n\n```\n{diff_stat}\n```"
                else:
                    message = "✅ No changes detected yet.\n\nMake sure to run AI in Cursor first!"
            else:
                message = f"❌ Check failed: {result.error or 'Unknown error'}"
            
            await query.message.reply_text(message, parse_mode="Markdown")
        
        elif callback_data == "ai_accept":
            # Accept all changes
            self.sentinel.log_command(user_id, "/ai accept (button)")
            
            result = agent.accept_changes()
            
            if result.success:
                data = result.data or {}
                message = f"""✅ **Changes Accepted!**

📝 **Commit:** {data.get('commit_message', 'TeleCode AI commit')}
📁 **Files:** {data.get('files_committed', 0)} committed

Use `/push` to push to remote."""
            else:
                message = f"❌ Accept failed: {result.error or result.message}"
            
            try:
                await query.edit_message_text(
                    query.message.text + f"\n\n{message}",
                    parse_mode="Markdown"
                )
            except Exception:
                await query.message.reply_text(message, parse_mode="Markdown")
        
        elif callback_data == "ai_revert":
            # Show revert confirmation
            self.sentinel.log_command(user_id, "/ai revert (button)")
            
            check = agent.check_changes()
            
            if check.data and check.data.get("has_changes"):
                file_count = check.data.get("file_count", 0)
                
                keyboard = [[
                    InlineKeyboardButton(f"⚠️ Yes, Revert {file_count} files", callback_data="ai_revert_confirm"),
                    InlineKeyboardButton("❌ Cancel", callback_data="ai_revert_cancel"),
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.message.reply_text(
                    f"⚠️ **Confirm Revert**\n\n"
                    f"This will **permanently discard** {file_count} file(s)!\n\n"
                    f"**This cannot be undone!**",
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
            else:
                await query.message.reply_text("✅ No changes to revert.", parse_mode="Markdown")
        
        elif callback_data == "ai_revert_confirm":
            # Actually revert
            self.sentinel.log_command(user_id, "/ai revert (confirmed)")
            
            result = agent.revert_changes()
            
            if result.success:
                data = result.data or {}
                message = f"""🗑️ **All Changes Reverted!**

📁 **Files reverted:** {data.get('files_reverted', 0)}

Working directory is now clean."""
            else:
                message = f"❌ Revert failed: {result.error or result.message}"
            
            try:
                await query.edit_message_text(message, parse_mode="Markdown")
            except Exception:
                await query.message.reply_text(message, parse_mode="Markdown")
        
        elif callback_data == "ai_revert_cancel":
            # Cancel revert
            try:
                await query.edit_message_text(
                    "✅ Revert cancelled. Your changes are still intact.",
                    parse_mode="Markdown"
                )
            except Exception:
                await query.message.reply_text(
                    "✅ Revert cancelled. Your changes are still intact.",
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
        
        # Start sleep prevention if enabled
        prevent_sleep = os.getenv("PREVENT_SLEEP", "true").lower() == "true"
        if prevent_sleep:
            self.sleep_preventer.start()
        
        # Start system tray icon
        try:
            from .tray_icon import start_tray, get_tray
            self.tray = start_tray(
                on_stop=self._request_stop
            )
            if self.tray:
                self.tray.set_connected()
        except Exception as e:
            logger.debug(f"Tray icon not available: {e}")
            self.tray = None
        
        # Start polling
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)
        
        logger.info("TeleCode bot is running!")
        
        # Update tray status
        if self.tray:
            self.tray.update_status("Connected")
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(3600)  # Sleep for an hour, repeat
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
        
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
        logger.info("TeleCode bot stopped")


def create_bot_from_env() -> Optional[TeleCodeBot]:
    """
    Create a TeleCodeBot instance from environment variables.
    
    SECURITY: Token is loaded from secure vault first, .env as fallback.
    
    Returns:
        TeleCodeBot instance or None if configuration is invalid.
    """
    from dotenv import load_dotenv
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



