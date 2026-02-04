"""
============================================
TeleCode v0.1 - System Tray Icon
============================================
Shows TeleCode status in the system tray.

Features:
- Green icon when running
- Right-click menu for actions
- Tooltip shows status
- Cross-platform support (Windows/macOS/Linux)

Platform-specific features:
- Windows: Screen lock options
- Linux: Virtual display (Xvfb) options
- macOS: Standard menu (no headless lock)
============================================
"""

import sys
import threading
import logging
from typing import Optional, Callable
from pathlib import Path

logger = logging.getLogger("telecode.tray")

# Platform detection
IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

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
    Cross-platform support with platform-specific options.
    """
    
    def __init__(
        self,
        on_settings: Optional[Callable] = None,
        on_lock_screen: Optional[Callable] = None,
        on_virtual_display: Optional[Callable] = None,
        on_stop: Optional[Callable] = None,
    ):
        """
        Initialize the tray icon.
        
        Args:
            on_settings: Callback when Settings is clicked
            on_lock_screen: Callback when Turn Off Display is clicked (Windows only)
            on_virtual_display: Callback when Virtual Display is clicked (Linux only)
            on_stop: Callback when Stop is clicked
        """
        self.on_settings = on_settings
        self.on_lock_screen = on_lock_screen
        self.on_virtual_display = on_virtual_display
        self.on_stop = on_stop
        
        self.icon: Optional[pystray.Icon] = None
        self.status = "Starting..."
        self.last_command = "None"
        self.command_count = 0
        self._running = False
        self._virtual_display_active = False
        self._screen_locked = False
        
    def _create_icon_image(self, color: str = "#1B5E20") -> 'Image':
        """Create a simple colored icon with brand colors."""
        # Create a 64x64 image with the TeleCode "T" logo
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Draw smooth circle with white outline and dark green fill
        # Outer circle (white outline) - slightly larger
        outline_width = 2
        padding = 2
        draw.ellipse(
            [padding, padding, size - padding, size - padding],
            fill="#FFFFFF",  # White outline
            outline=None
        )
        
        # Inner circle (dark green fill) - creates the white outline effect
        inner_padding = padding + outline_width
        draw.ellipse(
            [inner_padding, inner_padding, size - inner_padding, size - inner_padding],
            fill=color  # Dark green brand color
        )
        
        # "T" letter in the center (white)
        t_color = "#FFFFFF"
        # Horizontal bar of T
        draw.rectangle([16, 18, 48, 26], fill=t_color)
        # Vertical bar of T
        draw.rectangle([27, 18, 37, 50], fill=t_color)
        
        return image
    
    def _get_menu(self) -> 'pystray.Menu':
        """Create the right-click menu with platform-specific options."""
        # Build menu items list
        items = [
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
        ]
        
        # Platform-specific headless/display options
        if IS_WINDOWS:
            # Windows: Turn off display (always available - unlock happens via PIN entry)
            # Note: Display is turned on via unlock (entering PIN), not via tray
            items.extend([
                pystray.MenuItem(
                    "🖥️ Turn Off Display",
                    self._on_lock_screen_click
                ),
                pystray.Menu.SEPARATOR,
            ])
        elif IS_LINUX:
            # Linux: Virtual display options
            display_label = "🖥️ Stop Virtual Display" if self._virtual_display_active else "🖥️ Start Virtual Display"
            items.extend([
                pystray.MenuItem(
                    display_label,
                    self._on_virtual_display_click
                ),
                pystray.Menu.SEPARATOR,
            ])
        # macOS: No special headless options (requires external setup)
        
        # Common stop option
        items.append(
            pystray.MenuItem(
                "❌ Stop TeleCode",
                self._on_stop_click
            )
        )
        
        return pystray.Menu(*items)
    
    def _on_settings_click(self, icon, item):
        """Handle Settings click."""
        if self.on_settings:
            self.on_settings()
    
    def _on_lock_screen_click(self, icon, item):
        """Handle Turn Off Display click."""
        # Always just call the callback - no state toggling
        # The callback will handle turning off display and locking
        # Unlock happens via PIN entry, which will reset state via set_screen_locked(False)
        if self.on_lock_screen:
            self.on_lock_screen()
    
    def set_screen_locked(self, locked: bool):
        """
        Update the display lock status.
        
        Args:
            locked: True when display is off and locked, False when unlocked
                   When False, tray is ready for next "Turn Off Display" action
        """
        self._screen_locked = locked
        # Menu always shows "Turn Off Display" - no need to refresh
        # But refresh anyway to ensure menu is up to date
        self._refresh_menu()
    
    def _on_virtual_display_click(self, icon, item):
        """Handle Virtual Display toggle click (Linux)."""
        if self.on_virtual_display:
            self._virtual_display_active = not self._virtual_display_active
            self.on_virtual_display(self._virtual_display_active)
            self._refresh_menu()
    
    def set_virtual_display_status(self, active: bool):
        """Update the virtual display status for menu display."""
        self._virtual_display_active = active
        self._refresh_menu()
    
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
        """Set icon to connected state (dark green brand color)."""
        self.status = "Running"
        if self.icon:
            self.icon.icon = self._create_icon_image("#1B5E20")  # Dark green brand color
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
    on_lock_screen: Optional[Callable] = None,
    on_virtual_display: Optional[Callable] = None,
    on_stop: Optional[Callable] = None,
) -> Optional[TrayIcon]:
    """
    Start the system tray icon.
    
    Args:
        on_settings: Callback when Settings is clicked
        on_lock_screen: Callback when Turn Off Display is clicked (Windows only)
        on_virtual_display: Callback when Virtual Display is toggled (Linux only)
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
            on_lock_screen=on_lock_screen,
            on_virtual_display=on_virtual_display,
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

