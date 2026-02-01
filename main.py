#!/usr/bin/env python3
"""
============================================
TeleCode v0.1 - Remote Cursor Commander
============================================
Main Entry Point

This script:
1. Checks if .env configuration exists
2. If not, launches the GUI setup
3. If yes, starts the Telegram bot

Usage:
    python main.py           # Normal startup
    python main.py --config  # Force open config GUI
    python main.py --help    # Show help

============================================
"""

import os
import sys
import asyncio
import logging
import argparse
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Setup logging
class SensitiveDataFilter(logging.Filter):
    """
    Filter to redact sensitive data from logs.
    
    SEC: Prevents accidental logging of tokens, secrets, etc.
    """
    
    SENSITIVE_PATTERNS = [
        (r'\d{8,10}:[A-Za-z0-9_-]{35,40}', '[REDACTED_TOKEN]'),  # Telegram bot token
        (r'[A-Za-z0-9]{32,}', '[REDACTED_KEY]'),  # Generic API keys
    ]
    
    def filter(self, record):
        import re
        message = str(record.msg)
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            message = re.sub(pattern, replacement, message)
        record.msg = message
        return True


def setup_logging():
    """Configure logging for the application."""
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Create handlers
    console_handler = logging.StreamHandler(sys.stdout)
    file_handler = logging.FileHandler("telecode.log", encoding="utf-8")
    
    # Add sensitive data filter to both handlers
    sensitive_filter = SensitiveDataFilter()
    console_handler.addFilter(sensitive_filter)
    file_handler.addFilter(sensitive_filter)
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            console_handler,
            file_handler
        ]
    )

logger = logging.getLogger("telecode")


def check_config_exists() -> bool:
    """Check if .env configuration file exists and is valid."""
    env_path = Path(".env")
    
    if not env_path.exists():
        return False
    
    # Check if required fields are present
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        required = ["TELEGRAM_BOT_TOKEN", "ALLOWED_USER_ID", "DEV_ROOT"]
        for field in required:
            if field not in content or f"{field}=your_" in content.lower():
                return False
        
        return True
    except Exception:
        return False


def launch_gui():
    """Launch the configuration GUI."""
    logger.info("Launching configuration GUI...")
    
    from src.config_gui import show_config_gui
    
    def on_config_saved():
        """Callback when config is saved - start the bot."""
        logger.info("Configuration saved, starting bot...")
        run_bot()
    
    show_config_gui(on_save_callback=on_config_saved)


def run_bot():
    """Run the Telegram bot."""
    logger.info("Starting TeleCode bot...")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    from src.bot import create_bot_from_env
    
    bot = create_bot_from_env()
    if not bot:
        logger.error("Failed to create bot. Check your configuration.")
        sys.exit(1)
    
    # Run the bot
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise


def print_banner():
    """Print the TeleCode banner."""
    banner = """
╔════════════════════════════════════════════╗
║                                            ║
║  ▀█▀ ██▀ █   ██▀ ▄▀▀ ▄▀▄ █▀▄ ██▀          ║
║   █  █▄▄ █▄▄ █▄▄ ▀▄▄ ▀▄▀ █▄▀ █▄▄          ║
║                                            ║
║      Remote Cursor Commander v0.1          ║
║    Secure Telegram-to-Terminal Bridge      ║
║                                            ║
╚════════════════════════════════════════════╝
"""
    print(banner)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="TeleCode - Remote Cursor Commander",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py              Start TeleCode (shows GUI if not configured)
    python main.py --config     Open configuration GUI
    python main.py --headless   Run without GUI (requires existing .env)
    
For more information, see the README.md file.
"""
    )
    
    parser.add_argument(
        "--config", "-c",
        action="store_true",
        help="Force open the configuration GUI"
    )
    
    parser.add_argument(
        "--headless", "-H",
        action="store_true",
        help="Run in headless mode (no GUI, requires existing .env)"
    )
    
    parser.add_argument(
        "--version", "-v",
        action="version",
        version="TeleCode v0.1.0"
    )
    
    args = parser.parse_args()
    
    # Setup logging first
    setup_logging()
    
    # Print banner
    print_banner()
    
    # Handle arguments
    if args.config:
        # Force open GUI
        launch_gui()
    elif args.headless:
        # Headless mode - must have config
        if not check_config_exists():
            logger.error("No valid configuration found. Run without --headless first to configure.")
            sys.exit(1)
        run_bot()
    else:
        # Normal mode - check for config
        if check_config_exists():
            logger.info("Configuration found, starting bot...")
            run_bot()
        else:
            logger.info("No configuration found, launching setup GUI...")
            launch_gui()


if __name__ == "__main__":
    main()

