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
import atexit
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# ==========================================
# Single Instance Lock
# ==========================================
LOCK_FILE = Path.home() / ".telecode.lock"
_lock_file_handle = None


def acquire_single_instance_lock() -> bool:
    """
    Acquire a lock to ensure only one instance of TeleCode is running.
    
    Uses a file-based lock that works across platforms.
    
    Returns:
        True if lock acquired (no other instance running)
        False if another instance is already running
    """
    global _lock_file_handle
    
    try:
        if sys.platform == "win32":
            # Windows: Use exclusive file access
            import msvcrt
            
            # Try to open the lock file exclusively
            try:
                _lock_file_handle = open(LOCK_FILE, "w")
                # Try to lock the file exclusively (non-blocking)
                msvcrt.locking(_lock_file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                # Write our PID
                _lock_file_handle.write(str(os.getpid()))
                _lock_file_handle.flush()
                return True
            except (IOError, OSError):
                # Lock failed - another instance is running
                if _lock_file_handle:
                    _lock_file_handle.close()
                    _lock_file_handle = None
                return False
        else:
            # Unix/Mac: Use fcntl for file locking
            import fcntl
            
            _lock_file_handle = open(LOCK_FILE, "w")
            try:
                fcntl.flock(_lock_file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Write our PID
                _lock_file_handle.write(str(os.getpid()))
                _lock_file_handle.flush()
                return True
            except (IOError, OSError):
                # Lock failed - another instance is running
                _lock_file_handle.close()
                _lock_file_handle = None
                return False
                
    except Exception as e:
        logging.warning(f"Could not acquire instance lock: {e}")
        # If we can't lock, allow running (fail open)
        return True


def release_single_instance_lock():
    """Release the single instance lock."""
    global _lock_file_handle
    
    try:
        if _lock_file_handle:
            if sys.platform == "win32":
                import msvcrt
                try:
                    msvcrt.locking(_lock_file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
            else:
                import fcntl
                try:
                    fcntl.flock(_lock_file_handle.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
            
            _lock_file_handle.close()
            _lock_file_handle = None
        
        # Remove the lock file
        if LOCK_FILE.exists():
            try:
                LOCK_FILE.unlink()
            except Exception:
                pass
                
    except Exception as e:
        logging.warning(f"Could not release instance lock: {e}")


def get_running_instance_pid() -> int:
    """Get the PID of the running TeleCode instance, if any."""
    try:
        if LOCK_FILE.exists():
            with open(LOCK_FILE, "r") as f:
                pid_str = f.read().strip()
                if pid_str.isdigit():
                    return int(pid_str)
    except Exception:
        pass
    return 0

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
    
    # Ensure we have the instance lock (may need to reacquire after GUI)
    global _lock_file_handle
    if _lock_file_handle is None:
        if not acquire_single_instance_lock():
            logger.error("Could not acquire instance lock. Another TeleCode may have started.")
            print("\n❌ Another TeleCode instance started while configuring. Please try again.")
            sys.exit(1)
        # Register cleanup handler
        atexit.register(release_single_instance_lock)
    
    from dotenv import load_dotenv
    load_dotenv()
    
    from src.bot import create_bot_from_env
    
    bot = create_bot_from_env()
    if not bot:
        logger.error("Failed to create bot. Check your configuration.")
        release_single_instance_lock()
        sys.exit(1)
    
    # Run the bot
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise
    finally:
        release_single_instance_lock()


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
        version="TeleCode v0.1.5"
    )
    
    args = parser.parse_args()
    
    # Setup logging first
    setup_logging()
    
    # Print banner
    print_banner()
    
    # ==========================================
    # Single Instance Check
    # ==========================================
    if not acquire_single_instance_lock():
        existing_pid = get_running_instance_pid()
        
        print("\n" + "=" * 50)
        print("❌ TeleCode is already running!")
        print("=" * 50)
        
        if existing_pid:
            print(f"\nAnother instance is running (PID: {existing_pid})")
        else:
            print("\nAnother instance appears to be running.")
        
        print("\nTo start a new instance:")
        print("  1. Stop the existing TeleCode bot first")
        print("  2. Or check your system tray for the TeleCode icon")
        print("  3. Or kill the process manually:")
        if sys.platform == "win32":
            print(f"     taskkill /F /PID {existing_pid}" if existing_pid else "     taskkill /F /IM python.exe")
        else:
            print(f"     kill {existing_pid}" if existing_pid else "     pkill -f 'python.*main.py'")
        
        print("\n" + "=" * 50)
        sys.exit(1)
    
    # Register cleanup handler
    atexit.register(release_single_instance_lock)
    
    logger.info(f"TeleCode starting (PID: {os.getpid()})")
    
    # Handle arguments
    if args.config:
        # Force open GUI (config GUI doesn't need instance lock for the whole duration)
        release_single_instance_lock()  # Release so bot can start after config
        launch_gui()
    elif args.headless:
        # Headless mode - must have config
        if not check_config_exists():
            logger.error("No valid configuration found. Run without --headless first to configure.")
            release_single_instance_lock()
            sys.exit(1)
        run_bot()
    else:
        # Normal mode - check for config
        if check_config_exists():
            logger.info("Configuration found, starting bot...")
            run_bot()
        else:
            logger.info("No configuration found, launching setup GUI...")
            # Release lock for config, bot will reacquire when it starts
            release_single_instance_lock()
            launch_gui()


if __name__ == "__main__":
    main()

