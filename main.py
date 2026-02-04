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
import signal
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


def is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is still running."""
    try:
        if sys.platform == "win32":
            import subprocess
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                timeout=2
            )
            return str(pid) in result.stdout.decode('utf-8', errors='ignore')
        else:
            # Unix/Mac: Use kill -0 to check if process exists
            import signal
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False
    except Exception:
        return False


def cleanup_stale_lock():
    """
    Clean up lock file if the process that created it is no longer running.
    
    This handles cases where TeleCode was killed forcefully and didn't clean up.
    """
    try:
        if not LOCK_FILE.exists():
            return
        
        pid = get_running_instance_pid()
        if pid > 0:
            if not is_process_running(pid):
                # Process is dead, remove stale lock
                try:
                    log = logging.getLogger("telecode")
                    log.info(f"Removing stale lock file (PID {pid} is not running)")
                except:
                    pass
                try:
                    LOCK_FILE.unlink()
                except Exception as e:
                    try:
                        log = logging.getLogger("telecode")
                        log.warning(f"Could not remove stale lock file: {e}")
                    except:
                        pass
    except Exception as e:
        try:
            log = logging.getLogger("telecode")
            log.warning(f"Error checking for stale lock: {e}")
        except:
            pass


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


def kill_all_telecode_processes():
    """
    Kill all TeleCode processes to ensure clean shutdown.
    
    This function:
    1. Kills processes by name (TeleCode.exe, python main.py, etc.)
    2. Kills child processes spawned by TeleCode
    3. Ensures lock file is released
    """
    try:
        current_pid = os.getpid()
        
        if sys.platform == "win32":
            # Windows: Use taskkill to kill TeleCode processes
            import subprocess
            
            # Kill by executable name
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", "TeleCode.exe"],
                    capture_output=True,
                    timeout=5
                )
            except Exception:
                pass
            
            # Kill Python processes running main.py
            try:
                # Get all Python processes and check command line
                import psutil
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if proc.info['name'] and 'python' in proc.info['name'].lower():
                            cmdline = proc.info.get('cmdline', [])
                            if cmdline and any('main.py' in str(arg) or 'telecode' in str(arg).lower() for arg in cmdline):
                                pid = proc.info['pid']
                                if pid != current_pid:  # Don't kill ourselves
                                    try:
                                        proc_obj = psutil.Process(pid)
                                        proc_obj.terminate()
                                        proc_obj.wait(timeout=3)
                                    except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                                        try:
                                            proc_obj.kill()
                                        except:
                                            pass
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
            except ImportError:
                # psutil not available, try alternative method
                try:
                    # Try to kill by finding processes with main.py in command line
                    result = subprocess.run(
                        ['wmic', 'process', 'where', 'commandline like "%main.py%"', 'get', 'processid'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    # Parse and kill PIDs (simplified - wmic output parsing is complex)
                except Exception:
                    pass
        else:
            # Unix/Mac: Use pkill or ps + kill
            import subprocess
            
            # Kill by process name
            try:
                subprocess.run(
                    ["pkill", "-f", "main.py"],
                    capture_output=True,
                    timeout=5
                )
            except Exception:
                pass
            
            try:
                subprocess.run(
                    ["pkill", "-f", "telecode"],
                    capture_output=True,
                    timeout=5
                )
            except Exception:
                pass
            
            # Also try psutil if available for more precise control
            try:
                import psutil
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        cmdline = proc.info.get('cmdline', [])
                        if cmdline and any('main.py' in str(arg) or 'telecode' in str(arg).lower() for arg in cmdline):
                            pid = proc.info['pid']
                            if pid != current_pid:  # Don't kill ourselves
                                try:
                                    proc_obj = psutil.Process(pid)
                                    proc_obj.terminate()
                                    proc_obj.wait(timeout=3)
                                except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                                    try:
                                        proc_obj.kill()
                                    except:
                                        pass
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
            except ImportError:
                pass
        
        try:
            log = logging.getLogger("telecode")
            log.info("Killed all TeleCode processes")
        except:
            pass
    except Exception as e:
        try:
            log = logging.getLogger("telecode")
            log.warning(f"Error killing TeleCode processes: {e}")
        except:
            pass


def cleanup_on_exit():
    """
    Comprehensive cleanup function called on exit.
    
    This ensures:
    1. Lock file is released
    2. Clean shutdown
    """
    try:
        # Get logger (may not be initialized yet)
        try:
            log = logging.getLogger("telecode")
            log.info("Performing cleanup on exit...")
        except:
            pass
        
        # Release lock file - this is the most important cleanup
        release_single_instance_lock()
        
        # Note: We don't kill all processes here because:
        # 1. The main process will exit naturally
        # 2. Child processes should be cleaned up by their parents
        # 3. Killing all processes could interfere with legitimate instances
        
    except Exception as e:
        try:
            log = logging.getLogger("telecode")
            log.error(f"Error during cleanup: {e}")
        except:
            pass

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
    from src.system_utils import get_user_data_dir
    
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Use user data directory for log file (works when installed in Program Files)
    user_data_dir = get_user_data_dir()
    log_file = user_data_dir / "telecode.log"
    
    # Create handlers
    console_handler = logging.StreamHandler(sys.stdout)
    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    
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


def get_env_path() -> Path:
    """
    Get the path to the .env configuration file.
    
    Checks user data directory first (for installed applications),
    then falls back to current directory (for development).
    """
    from src.system_utils import get_user_data_dir
    
    # Check user data directory first (for installed applications)
    user_data_dir = get_user_data_dir()
    env_path = user_data_dir / ".env"
    
    # Fallback to current directory (for development)
    if not env_path.exists():
        env_path = Path(".env")
    
    return env_path


def load_env_file():
    """
    Load .env file from user data directory or current directory.
    
    This ensures the application works both when installed and in development.
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


def check_config_exists() -> bool:
    """Check if .env configuration file exists and is valid."""
    env_path = get_env_path()
    
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
            print("\n[ERROR] Another TeleCode instance started while configuring. Please try again.")
            sys.exit(1)
        # Register comprehensive cleanup handler
        atexit.register(cleanup_on_exit)
    
    load_env_file()
    
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
    # Ensure UTF-8 encoding for stdout on Windows
    if sys.platform == "win32":
        try:
            # Try to reconfigure stdout to use UTF-8
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            elif hasattr(sys.stdout, 'buffer'):
                # For older Python versions, wrap stdout
                import io
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        except Exception:
            # If reconfiguration fails, we'll handle it in the print statement
            pass
    
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
    try:
        print(banner)
    except UnicodeEncodeError:
        # Fallback to ASCII-safe banner if encoding fails
        ascii_banner = """
================================================
                                                
  TeleCode                                     
  Remote Cursor Commander v0.1                 
  Secure Telegram-to-Terminal Bridge           
                                                
================================================
"""
        print(ascii_banner)


def main():
    """Main entry point."""
    # Configure UTF-8 encoding for stdout on Windows to handle Unicode characters
    if sys.platform == "win32":
        try:
            # Try to reconfigure stdout to use UTF-8
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            elif hasattr(sys.stdout, 'buffer'):
                # For older Python versions, wrap stdout
                import io
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        except Exception:
            # If reconfiguration fails, continue with default encoding
            # print_banner will handle the fallback
            pass
    
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
        version="TeleCode v0.2.0"
    )
    
    parser.add_argument(
        "--settings-only", "-s",
        action="store_true",
        help="Open settings GUI only (no instance lock, no bot start - for tray menu)"
    )
    
    args = parser.parse_args()
    
    # Setup logging first
    setup_logging()
    
    # Print banner
    print_banner()
    
    # ==========================================
    # Settings-only mode (for system tray)
    # ==========================================
    # This mode opens the config GUI without checking instance lock
    # and without starting the bot afterward. Used when clicking
    # "Settings" from the system tray while bot is already running.
    if args.settings_only:
        logger.info("Opening settings GUI (settings-only mode)")
        from src.config_gui import show_config_gui
        # No callback - just edit and save, don't try to start bot
        show_config_gui(on_save_callback=None)
        logger.info("Settings GUI closed")
        sys.exit(0)
    
    # ==========================================
    # Single Instance Check
    # ==========================================
    # First, clean up any stale lock files
    cleanup_stale_lock()
    
    if not acquire_single_instance_lock():
        existing_pid = get_running_instance_pid()
        
        # Check if the existing process is actually running
        if existing_pid > 0 and not is_process_running(existing_pid):
            # Stale lock detected - remove it and try again
            logger.info(f"Found stale lock (PID {existing_pid} not running), removing...")
            try:
                if LOCK_FILE.exists():
                    LOCK_FILE.unlink()
            except Exception as e:
                logger.warning(f"Could not remove stale lock: {e}")
            
            # Try to acquire lock again
            if acquire_single_instance_lock():
                logger.info("Successfully acquired lock after cleaning stale lock")
                atexit.register(cleanup_on_exit)
            else:
                # Still can't acquire - another instance might have started
                existing_pid = get_running_instance_pid()
                if existing_pid > 0 and is_process_running(existing_pid):
                    print("\n" + "=" * 50)
                    print("[ERROR] TeleCode is already running!")
                    print("=" * 50)
                    print(f"\nAnother instance is running (PID: {existing_pid})")
                    print("\nTo start a new instance:")
                    print("  1. Stop the existing TeleCode bot first")
                    print("  2. Or check your system tray for the TeleCode icon")
                    print("  3. Or kill the process manually:")
                    if sys.platform == "win32":
                        print(f"     taskkill /F /PID {existing_pid}")
                    else:
                        print(f"     kill {existing_pid}")
                    print("\n" + "=" * 50)
                    sys.exit(1)
        else:
            # Lock is held by a running process
            print("\n" + "=" * 50)
            print("[ERROR] TeleCode is already running!")
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
                print(f"     taskkill /F /PID {existing_pid}" if existing_pid else "     taskkill /F /IM TeleCode.exe")
            else:
                print(f"     kill {existing_pid}" if existing_pid else "     pkill -f 'python.*main.py'")
            
            print("\n" + "=" * 50)
            sys.exit(1)
    
    # Register comprehensive cleanup handler
    atexit.register(cleanup_on_exit)
    
    # Also register signal handlers for graceful shutdown
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, lambda s, f: cleanup_on_exit())
        signal.signal(signal.SIGINT, lambda s, f: cleanup_on_exit())
    
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

