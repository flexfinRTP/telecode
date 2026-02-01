"""
============================================
TeleCode v0.1 - System Tray Icon
============================================
Shows TeleCode status in the system tray.

Features:
- Green icon when running
- Right-click menu for actions
- Tooltip shows status
============================================
"""

import sys
import threading
import logging
from typing import Optional, Callable
from pathlib import Path

logger = logging.getLogger("telecode.tray")

# Try to import pystray (optional dependency)
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    logger.info("pystray/PIL not installed - tray icon disabled. Install with: pip install pystray pillow")


class TrayIcon:
    """
    System tray icon for TeleCode.
    
    Shows status and provides quick actions via right-click menu.
    """
    
    def __init__(
        self,
        on_settings: Optional[Callable] = None,
        on_quick_lock: Optional[Callable] = None,
        on_secure_lock: Optional[Callable] = None,
        on_stop: Optional[Callable] = None,
    ):
        """
        Initialize the tray icon.
        
        Args:
            on_settings: Callback when Settings is clicked
            on_quick_lock: Callback when Quick Lock is clicked
            on_secure_lock: Callback when Secure Lock is clicked
            on_stop: Callback when Stop is clicked
        """
        self.on_settings = on_settings
        self.on_quick_lock = on_quick_lock
        self.on_secure_lock = on_secure_lock
        self.on_stop = on_stop
        
        self.icon: Optional[pystray.Icon] = None
        self.status = "Starting..."
        self.last_command = "None"
        self.command_count = 0
        self._running = False
        
    def _create_icon_image(self, color: str = "#39ff14") -> 'Image':
        """Create a simple colored icon."""
        # Create a 64x64 image with the TeleCode "T" logo
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Background circle
        padding = 4
        draw.ellipse(
            [padding, padding, size - padding, size - padding],
            fill=color
        )
        
        # "T" letter in the center (dark)
        t_color = "#0a0e14"
        # Horizontal bar of T
        draw.rectangle([16, 18, 48, 26], fill=t_color)
        # Vertical bar of T
        draw.rectangle([27, 18, 37, 50], fill=t_color)
        
        return image
    
    def _get_menu(self) -> 'pystray.Menu':
        """Create the right-click menu."""
        return pystray.Menu(
            pystray.MenuItem(
                f"✅ {self.status}",
                None,
                enabled=False
            ),
            pystray.MenuItem(
                f"📝 Last: {self.last_command[:30]}...",
                None,
                enabled=False
            ) if len(self.last_command) > 30 else pystray.MenuItem(
                f"📝 Last: {self.last_command}",
                None,
                enabled=False
            ),
            pystray.MenuItem(
                f"📊 Commands: {self.command_count}",
                None,
                enabled=False
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "⚙️ Settings",
                self._on_settings_click
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "⚡ Quick Lock",
                self._on_quick_lock_click
            ) if sys.platform == "win32" else None,
            pystray.MenuItem(
                "🛡️ Secure Lock",
                self._on_secure_lock_click
            ) if sys.platform == "win32" else None,
            pystray.Menu.SEPARATOR if sys.platform == "win32" else None,
            pystray.MenuItem(
                "❌ Stop TeleCode",
                self._on_stop_click
            ),
        )
    
    def _on_settings_click(self, icon, item):
        """Handle Settings click."""
        if self.on_settings:
            self.on_settings()
    
    def _on_quick_lock_click(self, icon, item):
        """Handle Quick Lock click."""
        if self.on_quick_lock:
            self.on_quick_lock()
    
    def _on_secure_lock_click(self, icon, item):
        """Handle Secure Lock click."""
        if self.on_secure_lock:
            self.on_secure_lock()
    
    def _on_stop_click(self, icon, item):
        """Handle Stop click."""
        self.stop()
        if self.on_stop:
            self.on_stop()
    
    def update_status(self, status: str):
        """Update the status text."""
        self.status = status
        self._refresh_menu()
    
    def update_last_command(self, command: str):
        """Update the last command text."""
        self.last_command = command
        self.command_count += 1
        self._refresh_menu()
    
    def _refresh_menu(self):
        """Refresh the menu to show updated values."""
        if self.icon:
            self.icon.menu = self._get_menu()
            self.icon.update_menu()
    
    def set_connected(self):
        """Set icon to connected state (green)."""
        self.status = "Running"
        if self.icon:
            self.icon.icon = self._create_icon_image("#39ff14")  # Green
            self._refresh_menu()
    
    def set_error(self, message: str = "Error"):
        """Set icon to error state (red)."""
        self.status = message
        if self.icon:
            self.icon.icon = self._create_icon_image("#ff5f56")  # Red
            self._refresh_menu()
    
    def start(self):
        """Start the tray icon in a background thread."""
        if not TRAY_AVAILABLE:
            logger.warning("Tray icon not available (install pystray pillow)")
            return
        
        if self._running:
            return
        
        def run_tray():
            try:
                self.icon = pystray.Icon(
                    "TeleCode",
                    self._create_icon_image(),
                    "TeleCode - Running",
                    menu=self._get_menu()
                )
                self._running = True
                logger.info("System tray icon started")
                self.icon.run()
            except Exception as e:
                logger.error(f"Tray icon error: {e}")
                self._running = False
        
        # Run in background thread
        tray_thread = threading.Thread(target=run_tray, daemon=True)
        tray_thread.start()
    
    def stop(self):
        """Stop the tray icon."""
        self._running = False
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
            logger.info("System tray icon stopped")


# Singleton instance
_tray_instance: Optional[TrayIcon] = None


def get_tray() -> Optional[TrayIcon]:
    """Get the global tray icon instance."""
    global _tray_instance
    return _tray_instance


def start_tray(
    on_settings: Optional[Callable] = None,
    on_stop: Optional[Callable] = None,
) -> Optional[TrayIcon]:
    """
    Start the system tray icon.
    
    Args:
        on_settings: Callback when Settings is clicked
        on_stop: Callback when Stop is clicked
    
    Returns:
        TrayIcon instance or None if not available
    """
    global _tray_instance
    
    if not TRAY_AVAILABLE:
        return None
    
    if _tray_instance is None:
        _tray_instance = TrayIcon(
            on_settings=on_settings,
            on_stop=on_stop,
        )
    
    _tray_instance.start()
    return _tray_instance


def stop_tray():
    """Stop the system tray icon."""
    global _tray_instance
    if _tray_instance:
        _tray_instance.stop()
        _tray_instance = None

