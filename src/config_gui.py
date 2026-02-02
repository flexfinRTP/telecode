"""
============================================
TeleCode v0.1 - Configuration GUI
============================================
Windows XP "Luna" styled setup interface.

Style Guide:
- Background: #ECE9D8 (Classic XP Beige/Gray)
- Text: Tahoma, 8pt, Black
- Buttons: Beveled edges, standard gray
- Window Title: "TeleCode - Setup"

This provides a 30-second setup experience.
============================================
"""

import os
import sys
import webbrowser
import logging
from pathlib import Path
from typing import Optional, Callable
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger("telecode.gui")

# ==========================================
# Windows DPI Awareness (fixes blurry text)
# ==========================================
def enable_dpi_awareness():
    """Enable DPI awareness on Windows for crisp text rendering."""
    if sys.platform == "win32":
        try:
            from ctypes import windll
            # SetProcessDPIAware for Windows Vista+
            # SetProcessDpiAwareness for Windows 8.1+
            # SetProcessDpiAwarenessContext for Windows 10 1703+
            try:
                windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
            except Exception:
                try:
                    windll.user32.SetProcessDPIAware()
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Could not set DPI awareness: {e}")

# Call early, before any Tk windows are created
enable_dpi_awareness()

# Import model configuration
try:
    from .model_config import AVAILABLE_MODELS, DEFAULT_MODEL_ALIAS, ModelTier
    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False
    AVAILABLE_MODELS = {}
    DEFAULT_MODEL_ALIAS = "opus"

# ==========================================
# Windows XP Color Palette
# ==========================================
XP_COLORS = {
    "bg_main": "#ECE9D8",        # Classic XP Beige/Gray
    "bg_groupbox": "#F5F4EE",    # Slightly lighter for group boxes
    "bg_button": "#E1E1E1",      # Button gray
    "bg_button_hover": "#D4D0C8", # Button hover
    "text": "#000000",           # Black text
    "text_label": "#0046D5",     # Blue link color
    "border": "#919B9C",         # Border gray
    "success": "#008000",        # Green for success
    "error": "#C00000",          # Red for errors
}


class XPStyleButton(tk.Button):
    """Windows XP styled button with beveled edges."""
    
    def __init__(self, parent, **kwargs):
        # Default XP button styling
        defaults = {
            "bg": XP_COLORS["bg_button"],
            "fg": XP_COLORS["text"],
            "font": ("Tahoma", 8),
            "relief": "raised",
            "borderwidth": 2,
            "cursor": "hand2",
            "padx": 10,
            "pady": 5,
        }
        defaults.update(kwargs)
        super().__init__(parent, **defaults)
        
        # Hover effects
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
    
    def _on_enter(self, e):
        self["bg"] = XP_COLORS["bg_button_hover"]
    
    def _on_leave(self, e):
        self["bg"] = XP_COLORS["bg_button"]


class XPStyleEntry(tk.Entry):
    """Windows XP styled text entry."""
    
    def __init__(self, parent, **kwargs):
        defaults = {
            "bg": "white",
            "fg": XP_COLORS["text"],
            "font": ("Tahoma", 9),
            "relief": "sunken",
            "borderwidth": 2,
        }
        defaults.update(kwargs)
        super().__init__(parent, **defaults)


class XPStyleLabel(tk.Label):
    """Windows XP styled label."""
    
    def __init__(self, parent, **kwargs):
        defaults = {
            "bg": XP_COLORS["bg_main"],
            "fg": XP_COLORS["text"],
            "font": ("Tahoma", 8),
        }
        defaults.update(kwargs)
        super().__init__(parent, **defaults)


class XPStyleCheckbutton(tk.Checkbutton):
    """Windows XP styled checkbox."""
    
    def __init__(self, parent, **kwargs):
        defaults = {
            "bg": XP_COLORS["bg_main"],
            "fg": XP_COLORS["text"],
            "font": ("Tahoma", 8),
            "activebackground": XP_COLORS["bg_main"],
            "selectcolor": "white",
        }
        defaults.update(kwargs)
        super().__init__(parent, **defaults)


class ConfigurationGUI:
    """
    TeleCode Configuration Window (XP Style)
    
    Provides easy setup with fields for:
    - Telegram Bot Token
    - User ID
    - Sandbox Directory
    - Voice Toggle
    - Sleep Prevention Toggle
    """
    
    def __init__(self, on_save_callback: Optional[Callable] = None):
        """
        Initialize the configuration GUI.
        
        Args:
            on_save_callback: Function to call when config is saved and bot should start
        """
        self.on_save_callback = on_save_callback
        self.root = tk.Tk()
        self._setup_window()
        self._create_widgets()
        self._load_existing_config()
    
    def _setup_window(self):
        """Configure the main window."""
        self.root.title("TeleCode - Setup")
        self.root.configure(bg=XP_COLORS["bg_main"])
        self.root.resizable(True, True)  # Allow resizing
        
        # Center window on screen (850x1150 for comfortable layout with all buttons visible)
        window_width = 850
        window_height = 1150
        
        # Set minimum size so UI doesn't break when resized too small
        self.root.minsize(700, 650)
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Adjust window height if screen is smaller
        if screen_height < window_height + 100:
            window_height = screen_height - 100
        
        x = (screen_width - window_width) // 2
        y = max(20, (screen_height - window_height) // 2)  # Ensure not off-screen
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Set icon (would be custom in production)
        try:
            if sys.platform == "win32":
                self.root.iconbitmap(default="")
        except:
            pass
    
    def _create_widgets(self):
        """Create all GUI widgets."""
        # ==========================================
        # Button bar at bottom (pack FIRST so it's always visible)
        # ==========================================
        button_bar = tk.Frame(self.root, bg=XP_COLORS["bg_main"], padx=15, pady=10)
        button_bar.pack(side="bottom", fill="x")
        
        # Separator line above buttons
        separator = tk.Frame(self.root, bg=XP_COLORS["border"], height=1)
        separator.pack(side="bottom", fill="x")
        
        self.start_btn = XPStyleButton(
            button_bar,
            text="💾 Save & Start Bot",
            command=self._save_and_start,
            font=("Tahoma", 9, "bold"),
            padx=15
        )
        self.start_btn.pack(side="right")
        
        save_only_btn = XPStyleButton(
            button_bar,
            text="Save Config",
            command=self._save_config
        )
        save_only_btn.pack(side="right", padx=(0, 10))
        
        cancel_btn = XPStyleButton(
            button_bar,
            text="Cancel",
            command=self.root.destroy
        )
        cancel_btn.pack(side="left")
        
        # ==========================================
        # Scrollable content area
        # ==========================================
        # Create canvas with scrollbar for content
        canvas_frame = tk.Frame(self.root, bg=XP_COLORS["bg_main"])
        canvas_frame.pack(fill="both", expand=True)
        
        canvas = tk.Canvas(canvas_frame, bg=XP_COLORS["bg_main"], highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        
        # Main container inside canvas
        main_frame = tk.Frame(canvas, bg=XP_COLORS["bg_main"], padx=15, pady=15)
        
        # Configure canvas scrolling
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        # Create window inside canvas
        canvas_window = canvas.create_window((0, 0), window=main_frame, anchor="nw")
        
        # Update scroll region when content changes
        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        main_frame.bind("<Configure>", on_frame_configure)
        
        # Make canvas width follow window width
        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", on_canvas_configure)
        
        # Enable mousewheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # ==========================================
        # Header
        # ==========================================
        header_frame = tk.Frame(main_frame, bg=XP_COLORS["bg_main"])
        header_frame.pack(fill="x", pady=(0, 15))
        
        title_label = tk.Label(
            header_frame,
            text="🚀 TeleCode Configuration",
            font=("Tahoma", 14, "bold"),
            bg=XP_COLORS["bg_main"],
            fg=XP_COLORS["text"]
        )
        title_label.pack(anchor="w")
        
        subtitle_label = tk.Label(
            header_frame,
            text="Configure your secure Telegram-to-Terminal bridge",
            font=("Tahoma", 8),
            bg=XP_COLORS["bg_main"],
            fg="#666666"
        )
        subtitle_label.pack(anchor="w")
        
        # ==========================================
        # Telegram Settings Group
        # ==========================================
        telegram_group = tk.LabelFrame(
            main_frame,
            text=" Telegram Settings ",
            font=("Tahoma", 8, "bold"),
            bg=XP_COLORS["bg_groupbox"],
            fg=XP_COLORS["text"],
            padx=10,
            pady=10
        )
        telegram_group.pack(fill="x", pady=(0, 10))
        
        # Bot Token
        token_frame = tk.Frame(telegram_group, bg=XP_COLORS["bg_groupbox"])
        token_frame.pack(fill="x", pady=(0, 8))
        
        XPStyleLabel(token_frame, text="Bot Token:", bg=XP_COLORS["bg_groupbox"]).pack(anchor="w")
        
        token_input_frame = tk.Frame(token_frame, bg=XP_COLORS["bg_groupbox"])
        token_input_frame.pack(fill="x")
        
        self.token_var = tk.StringVar()
        self.token_entry = XPStyleEntry(token_input_frame, textvariable=self.token_var, show="•", width=45)
        self.token_entry.pack(side="left", fill="x", expand=True)
        
        # Eye button to reveal/hide token
        self.token_visible = False
        self.eye_btn = XPStyleButton(token_input_frame, text="👁", command=self._toggle_token_visibility)
        self.eye_btn.pack(side="right", padx=(5, 0))
        
        help_btn = XPStyleButton(token_input_frame, text="?", command=self._open_botfather_help)
        help_btn.pack(side="right", padx=(5, 0))
        
        # User ID
        userid_frame = tk.Frame(telegram_group, bg=XP_COLORS["bg_groupbox"])
        userid_frame.pack(fill="x")
        
        XPStyleLabel(userid_frame, text="Your User ID:", bg=XP_COLORS["bg_groupbox"]).pack(anchor="w")
        
        userid_input_frame = tk.Frame(userid_frame, bg=XP_COLORS["bg_groupbox"])
        userid_input_frame.pack(fill="x")
        
        self.userid_var = tk.StringVar()
        self.userid_entry = XPStyleEntry(userid_input_frame, textvariable=self.userid_var, width=45)
        self.userid_entry.pack(side="left", fill="x", expand=True)
        
        get_id_btn = XPStyleButton(userid_input_frame, text="Get ID", command=self._open_userinfobot)
        get_id_btn.pack(side="right", padx=(5, 0))
        
        # ==========================================
        # Sandbox Settings Group (CRITICAL SECURITY)
        # ==========================================
        sandbox_group = tk.LabelFrame(
            main_frame,
            text=" ⚠️ SECURITY SANDBOX (READ CAREFULLY) ",
            font=("Tahoma", 8, "bold"),
            bg="#FFF8DC",  # Light yellow warning background
            fg=XP_COLORS["error"],
            padx=10,
            pady=10
        )
        sandbox_group.pack(fill="x", pady=(0, 10))
        
        # Main label
        XPStyleLabel(
            sandbox_group, 
            text="Allowed Folder (THE JAIL):", 
            bg="#FFF8DC",
            font=("Tahoma", 8, "bold")
        ).pack(anchor="w")
        
        # Warning explanation
        warning_text = tk.Label(
            sandbox_group,
            text="⚠️ TeleCode can READ, WRITE, and DELETE files in this folder!\n"
                 "The bot will have FULL ACCESS to everything inside.",
            font=("Tahoma", 8),
            fg=XP_COLORS["error"],
            bg="#FFF8DC",
            justify="left"
        )
        warning_text.pack(anchor="w", pady=(2, 5))
        
        # What to select
        good_label = tk.Label(
            sandbox_group,
            text="✅ GOOD: A dedicated projects folder (e.g., C:\\Dev\\Projects)",
            font=("Tahoma", 7),
            fg=XP_COLORS["success"],
            bg="#FFF8DC"
        )
        good_label.pack(anchor="w")
        
        # What NOT to select
        bad_label = tk.Label(
            sandbox_group,
            text="❌ BAD: Desktop, Documents, C:\\, Home folder, or system folders",
            font=("Tahoma", 7),
            fg=XP_COLORS["error"],
            bg="#FFF8DC"
        )
        bad_label.pack(anchor="w", pady=(0, 5))
        
        path_frame = tk.Frame(sandbox_group, bg="#FFF8DC")
        path_frame.pack(fill="x", pady=(5, 0))
        
        self.path_var = tk.StringVar()
        self.path_entry = XPStyleEntry(path_frame, textvariable=self.path_var, width=45)
        self.path_entry.pack(side="left", fill="x", expand=True)
        
        browse_btn = XPStyleButton(path_frame, text="Browse...", command=self._browse_folder)
        browse_btn.pack(side="right", padx=(5, 0))
        
        # ==========================================
        # AI Model Selection Group
        # ==========================================
        model_group = tk.LabelFrame(
            main_frame,
            text=" 🤖 AI Model Selection ",
            font=("Tahoma", 8, "bold"),
            bg=XP_COLORS["bg_groupbox"],
            fg=XP_COLORS["text"],
            padx=10,
            pady=10
        )
        model_group.pack(fill="x", pady=(0, 10))
        
        XPStyleLabel(
            model_group, 
            text="Default AI Model:", 
            bg=XP_COLORS["bg_groupbox"]
        ).pack(anchor="w")
        
        model_hint = tk.Label(
            model_group,
            text="Select the AI model for Cursor prompts (can be changed via /model command)",
            font=("Tahoma", 7),
            fg="#666666",
            bg=XP_COLORS["bg_groupbox"]
        )
        model_hint.pack(anchor="w", pady=(0, 5))
        
        model_frame = tk.Frame(model_group, bg=XP_COLORS["bg_groupbox"])
        model_frame.pack(fill="x")
        
        # Build model choices (using aliases as IDs for consistency)
        self.model_choices = []
        self.model_aliases = []  # Store aliases for .env
        if MODELS_AVAILABLE and AVAILABLE_MODELS:
            for alias, model in AVAILABLE_MODELS.items():
                tier_icon = "⭐" if model.tier == ModelTier.PAID else "🆓"
                display = f"{model.emoji} {model.display_name} {tier_icon}"
                self.model_choices.append(display)
                self.model_aliases.append(alias)
        else:
            # Fallback if model_config not available
            self.model_choices = [
                "💎 Claude Opus 4.5 ⭐",
                "💰 Claude Sonnet 4.5 ⭐", 
                "✨ Claude Haiku 4.5 🆓",
                "⚡ Gemini 3 Flash 🆓",
                "🧠 GPT-4.1 ⭐",
            ]
            self.model_aliases = [
                "opus",
                "sonnet",
                "haiku",
                "gemini",
                "gpt",
            ]
        
        self.model_var = tk.StringVar(value=self.model_choices[0] if self.model_choices else "")
        self.model_dropdown = ttk.Combobox(
            model_frame,
            textvariable=self.model_var,
            values=self.model_choices,
            state="readonly",
            width=42,
            font=("Tahoma", 9)
        )
        self.model_dropdown.pack(side="left", fill="x", expand=True)
        
        # Style the combobox
        style = ttk.Style()
        style.configure("TCombobox", font=("Tahoma", 9))
        
        # ==========================================
        # Options Group
        # ==========================================
        options_group = tk.LabelFrame(
            main_frame,
            text=" Options ",
            font=("Tahoma", 8, "bold"),
            bg=XP_COLORS["bg_groupbox"],
            fg=XP_COLORS["text"],
            padx=10,
            pady=10
        )
        options_group.pack(fill="x", pady=(0, 10))
        
        # Voice option row
        voice_frame = tk.Frame(options_group, bg=XP_COLORS["bg_groupbox"])
        voice_frame.pack(fill="x", pady=2)
        self.voice_var = tk.BooleanVar(value=True)
        voice_check = XPStyleCheckbutton(
            voice_frame,
            text="Enable Voice Transcription",
            variable=self.voice_var,
            bg=XP_COLORS["bg_groupbox"]
        )
        voice_check.pack(side="left")
        voice_info_btn = XPStyleButton(voice_frame, text=" i ", command=self._show_voice_info, width=2)
        voice_info_btn.pack(side="left", padx=(5, 0))
        
        # Sleep option row
        sleep_frame = tk.Frame(options_group, bg=XP_COLORS["bg_groupbox"])
        sleep_frame.pack(fill="x", pady=2)
        self.sleep_var = tk.BooleanVar(value=True)
        sleep_check = XPStyleCheckbutton(
            sleep_frame,
            text="Prevent Sleep Mode",
            variable=self.sleep_var,
            bg=XP_COLORS["bg_groupbox"]
        )
        sleep_check.pack(side="left")
        sleep_info_btn = XPStyleButton(sleep_frame, text=" i ", command=self._show_sleep_info, width=2)
        sleep_info_btn.pack(side="left", padx=(5, 0))
        
        # Audit option row
        audit_frame = tk.Frame(options_group, bg=XP_COLORS["bg_groupbox"])
        audit_frame.pack(fill="x", pady=2)
        self.audit_var = tk.BooleanVar(value=True)
        audit_check = XPStyleCheckbutton(
            audit_frame,
            text="Enable Security Logging",
            variable=self.audit_var,
            bg=XP_COLORS["bg_groupbox"]
        )
        audit_check.pack(side="left")
        audit_info_btn = XPStyleButton(audit_frame, text=" i ", command=self._show_audit_info, width=2)
        audit_info_btn.pack(side="left", padx=(5, 0))
        
        # ==========================================
        # TSCON Section (Windows Only)
        # ==========================================
        if sys.platform == "win32":
            tscon_group = tk.LabelFrame(
                main_frame,
                text=" 🔒 TSCON Session Lock (Advanced) ",
                font=("Tahoma", 8, "bold"),
                bg=XP_COLORS["bg_groupbox"],
                fg=XP_COLORS["text"],
                padx=10,
                pady=8
            )
            tscon_group.pack(fill="x", pady=(0, 10))
            
            tscon_info = tk.Label(
                tscon_group,
                text="Lock your screen and code on the go! Your session stays active so you can\ncontrol Cursor via Telegram from anywhere. Use the System Tray icon for quick access!",
                font=("Tahoma", 7),
                fg="#666666",
                bg=XP_COLORS["bg_groupbox"],
                justify="left"
            )
            tscon_info.pack(anchor="w")
            
            # Note about system tray
            tray_note = tk.Label(
                tscon_group,
                text="💡 TIP: Right-click the TeleCode tray icon (near clock) for Quick Lock & Secure Lock!",
                font=("Tahoma", 7, "bold"),
                fg=XP_COLORS["success"],
                bg=XP_COLORS["bg_groupbox"]
            )
            tray_note.pack(anchor="w", pady=(5, 5))
            
            # ---- Quick Lock ----
            quick_frame = tk.Frame(tscon_group, bg=XP_COLORS["bg_groupbox"])
            quick_frame.pack(fill="x", pady=(3, 3))
            
            quick_lock_btn = XPStyleButton(
                quick_frame,
                text="⚡ Quick Lock Now",
                command=self._run_quick_lock
            )
            quick_lock_btn.pack(side="left")
            
            quick_info_btn = XPStyleButton(quick_frame, text=" i ", command=self._show_quick_lock_info, width=2)
            quick_info_btn.pack(side="left", padx=(5, 0))
            
            tk.Label(
                quick_frame,
                text="Remote Desktop apps still work",
                font=("Tahoma", 7),
                fg="#666666",
                bg=XP_COLORS["bg_groupbox"]
            ).pack(side="left", padx=(10, 0))
            
            # ---- Option 3: Secure Lock ----
            secure_frame = tk.Frame(tscon_group, bg=XP_COLORS["bg_groupbox"])
            secure_frame.pack(fill="x", pady=(3, 3))
            
            secure_lock_btn = XPStyleButton(
                secure_frame,
                text="🛡️ Secure Lock Now",
                command=self._run_secure_lock
            )
            secure_lock_btn.pack(side="left")
            
            secure_info_btn = XPStyleButton(secure_frame, text=" i ", command=self._show_secure_lock_info, width=2)
            secure_info_btn.pack(side="left", padx=(5, 0))
            
            tk.Label(
                secure_frame,
                text="⭐ Best — blocks Remote Desktop apps, 30min auto-lock",
                font=("Tahoma", 7, "bold"),
                fg=XP_COLORS["success"],
                bg=XP_COLORS["bg_groupbox"]
            ).pack(side="left", padx=(10, 0))
        
        # ==========================================
        # Virtual Display Section (Linux Only)
        # ==========================================
        elif sys.platform.startswith("linux"):
            vdisplay_group = tk.LabelFrame(
                main_frame,
                text=" 🖥️ Virtual Display (Headless Mode) ",
                font=("Tahoma", 8, "bold"),
                bg=XP_COLORS["bg_groupbox"],
                fg=XP_COLORS["text"],
                padx=10,
                pady=8
            )
            vdisplay_group.pack(fill="x", pady=(0, 10))
            
            vdisplay_info = tk.Label(
                vdisplay_group,
                text="Run TeleCode headless with a virtual display (Xvfb). This allows GUI automation\neven without a physical monitor — the Linux equivalent of Windows TSCON.",
                font=("Tahoma", 7),
                fg="#666666",
                bg=XP_COLORS["bg_groupbox"],
                justify="left"
            )
            vdisplay_info.pack(anchor="w")
            
            # Check if Xvfb is available
            import shutil
            xvfb_available = shutil.which("Xvfb") is not None
            pyvd_available = False
            try:
                import pyvirtualdisplay
                pyvd_available = True
            except ImportError:
                pass
            
            status_text = "✅ Ready" if (xvfb_available and pyvd_available) else "⚠️ Setup Required"
            status_color = XP_COLORS["success"] if (xvfb_available and pyvd_available) else "#CC6600"
            
            status_frame = tk.Frame(vdisplay_group, bg=XP_COLORS["bg_groupbox"])
            status_frame.pack(fill="x", pady=(5, 5))
            
            tk.Label(
                status_frame,
                text=f"Status: {status_text}",
                font=("Tahoma", 8, "bold"),
                fg=status_color,
                bg=XP_COLORS["bg_groupbox"]
            ).pack(side="left")
            
            if not xvfb_available:
                tk.Label(
                    vdisplay_group,
                    text="📦 Install Xvfb: sudo apt install xvfb",
                    font=("Tahoma", 7),
                    fg="#666666",
                    bg=XP_COLORS["bg_groupbox"]
                ).pack(anchor="w")
            
            if not pyvd_available:
                tk.Label(
                    vdisplay_group,
                    text="📦 Install pyvirtualdisplay: pip install pyvirtualdisplay",
                    font=("Tahoma", 7),
                    fg="#666666",
                    bg=XP_COLORS["bg_groupbox"]
                ).pack(anchor="w")
            
            if xvfb_available and pyvd_available:
                tray_note = tk.Label(
                    vdisplay_group,
                    text="💡 TIP: Use the system tray icon to toggle virtual display mode!",
                    font=("Tahoma", 7, "bold"),
                    fg=XP_COLORS["success"],
                    bg=XP_COLORS["bg_groupbox"]
                )
                tray_note.pack(anchor="w", pady=(5, 0))
        
        # ==========================================
        # macOS Info Section (macOS Only)
        # ==========================================
        elif sys.platform == "darwin":
            macos_group = tk.LabelFrame(
                main_frame,
                text=" 🍎 Headless Mode (macOS) ",
                font=("Tahoma", 8, "bold"),
                bg=XP_COLORS["bg_groupbox"],
                fg=XP_COLORS["text"],
                padx=10,
                pady=8
            )
            macos_group.pack(fill="x", pady=(0, 10))
            
            macos_info = tk.Label(
                macos_group,
                text="macOS requires external setup for headless GUI automation.\nOptions: virtual display adapter, VNC, or 'caffeinate' to prevent sleep.",
                font=("Tahoma", 7),
                fg="#666666",
                bg=XP_COLORS["bg_groupbox"],
                justify="left"
            )
            macos_info.pack(anchor="w")
            
            tk.Label(
                macos_group,
                text="💡 caffeinate -dims — prevents sleep (TeleCode does this automatically)",
                font=("Tahoma", 7),
                fg=XP_COLORS["success"],
                bg=XP_COLORS["bg_groupbox"]
            ).pack(anchor="w", pady=(5, 0))
            
            tk.Label(
                macos_group,
                text="🔌 For true headless: use a virtual display adapter (BetterDummy, Deskreen)",
                font=("Tahoma", 7),
                fg="#666666",
                bg=XP_COLORS["bg_groupbox"]
            ).pack(anchor="w")
        
        # ==========================================
        # Status Label
        # ==========================================
        self.status_var = tk.StringVar()
        self.status_label = tk.Label(
            main_frame,
            textvariable=self.status_var,
            font=("Tahoma", 8),
            bg=XP_COLORS["bg_main"],
            fg="#666666"
        )
        self.status_label.pack(pady=(0, 10))
        
    def _load_existing_config(self):
        """Load existing configuration from .env if present."""
        try:
            from dotenv import dotenv_values
            
            env_path = Path(".env")
            if env_path.exists():
                config = dotenv_values(env_path)
                
                # Load token - try vault first if placeholder is in .env
                token_in_env = config.get("TELEGRAM_BOT_TOKEN", "")
                if token_in_env == "[STORED_IN_SECURE_VAULT]":
                    # Token is in vault, try to retrieve it
                    try:
                        from .token_vault import get_vault
                        vault = get_vault()
                        vault_token = vault.retrieve_token()
                        if vault_token:
                            self.token_var.set(vault_token)
                            self._set_status("🔒 Token loaded from secure vault", "success")
                        else:
                            # Vault retrieval failed - show placeholder so user knows to re-enter
                            self.token_var.set("")
                            self._set_status("⚠️ Token in vault but couldn't retrieve - please re-enter", "error")
                    except Exception as e:
                        logger.warning(f"Could not load token from vault: {e}")
                        self.token_var.set("")
                        self._set_status("⚠️ Token vault error - please re-enter token", "error")
                elif token_in_env:
                    self.token_var.set(token_in_env)
                
                if config.get("ALLOWED_USER_ID"):
                    self.userid_var.set(config["ALLOWED_USER_ID"])
                if config.get("DEV_ROOT"):
                    self.path_var.set(config["DEV_ROOT"])
                
                self.voice_var.set(config.get("ENABLE_VOICE", "true").lower() == "true")
                self.sleep_var.set(config.get("PREVENT_SLEEP", "true").lower() == "true")
                self.audit_var.set(config.get("ENABLE_AUDIT_LOG", "true").lower() == "true")
                
                # Load saved model selection
                saved_model = config.get("DEFAULT_MODEL", "").lower()
                if saved_model and saved_model in self.model_aliases:
                    idx = self.model_aliases.index(saved_model)
                    if idx < len(self.model_choices):
                        self.model_var.set(self.model_choices[idx])
                
                if not self.status_var.get().startswith("🔒") and not self.status_var.get().startswith("⚠️"):
                    self._set_status("Loaded existing configuration", "info")
        except Exception as e:
            logger.warning(f"Could not load existing config: {e}")
    
    def _set_status(self, message: str, level: str = "info"):
        """Update status message."""
        colors = {
            "info": "#666666",
            "success": XP_COLORS["success"],
            "error": XP_COLORS["error"]
        }
        self.status_label.configure(fg=colors.get(level, colors["info"]))
        self.status_var.set(message)
    
    def _browse_folder(self):
        """Open folder browser dialog with security warnings."""
        folder = filedialog.askdirectory(
            title="⚠️ SELECT YOUR ALLOWED FOLDER - TeleCode Will Have Full Access!",
            initialdir=self.path_var.get() or str(Path.home())
        )
        if folder:
            # Check for dangerous folder selections
            danger_result = self._check_dangerous_folder(folder)
            if danger_result:
                messagebox.showerror(
                    "🚫 DANGEROUS FOLDER BLOCKED",
                    f"You cannot select this folder:\n\n"
                    f"📁 {folder}\n\n"
                    f"Reason: {danger_result}\n\n"
                    f"Please select a dedicated development folder instead.\n"
                    f"Example: C:\\Dev\\Projects or ~/code"
                )
                return
            
            # Show confirmation for any folder
            confirm = messagebox.askyesno(
                "⚠️ CONFIRM FOLDER ACCESS",
                f"You are granting TeleCode FULL ACCESS to:\n\n"
                f"📁 {folder}\n\n"
                f"TeleCode will be able to:\n"
                f"  • READ all files in this folder\n"
                f"  • WRITE and MODIFY files\n"
                f"  • DELETE files (via git commands)\n"
                f"  • Execute Cursor AI on these files\n\n"
                f"Are you SURE this is the correct folder?\n\n"
                f"Only click 'Yes' if this is a dedicated development folder.",
                icon="warning"
            )
            
            if confirm:
                self.path_var.set(folder)
                self._set_status(f"✅ Folder selected: {Path(folder).name}", "success")
            else:
                self._set_status("Folder selection cancelled", "info")
    
    def _check_dangerous_folder(self, folder: str) -> str:
        """
        Check if a folder is dangerous to use as sandbox.
        
        Returns:
            Error message if dangerous, empty string if safe.
        """
        folder_path = Path(folder).resolve()
        folder_str = str(folder_path).lower()
        
        # Get system paths
        home = Path.home()
        
        # List of dangerous patterns
        dangerous_checks = [
            # Root drives
            (len(folder_path.parts) <= 1, "This is a root drive. Select a subfolder."),
            (folder_str in ["c:\\", "d:\\", "e:\\", "/"], "This is a root drive. Select a subfolder."),
            
            # User home folder itself
            (folder_path == home, "This is your entire home folder. Select a subfolder."),
            
            # Common system folders (Windows)
            ("\\windows" in folder_str, "This is a Windows system folder."),
            ("\\system32" in folder_str, "This is a Windows system folder."),
            ("\\program files" in folder_str, "This is a Program Files folder."),
            ("\\programdata" in folder_str, "This is a system data folder."),
            
            # Common system folders (Unix)
            (folder_str == "/etc", "This is a system configuration folder."),
            (folder_str == "/usr", "This is a system folder."),
            (folder_str == "/bin", "This is a system folder."),
            (folder_str == "/var", "This is a system folder."),
            
            # Common user folders that are too broad
            (folder_path == home / "Desktop", "Desktop contains personal files. Use a subfolder."),
            (folder_path == home / "Documents", "Documents is too broad. Create a Dev subfolder."),
            (folder_path == home / "Downloads", "Downloads is too risky. Use a dedicated dev folder."),
            (folder_path == home / "OneDrive", "OneDrive root is too broad. Use a subfolder."),
            (folder_path == home / "Dropbox", "Dropbox root is too broad. Use a subfolder."),
            (folder_path == home / "Google Drive", "Google Drive root is too broad. Use a subfolder."),
            
            # SSH and secrets
            (".ssh" in folder_str, "This folder may contain SSH keys and secrets."),
            (".gnupg" in folder_str, "This folder contains encryption keys."),
            (".aws" in folder_str, "This folder contains AWS credentials."),
        ]
        
        for condition, message in dangerous_checks:
            if condition:
                return message
        
        return ""  # Safe
    
    def _toggle_token_visibility(self):
        """Toggle bot token visibility (show/hide)."""
        self.token_visible = not self.token_visible
        if self.token_visible:
            self.token_entry.configure(show="")
            self.eye_btn.configure(text="🙈")
        else:
            self.token_entry.configure(show="•")
            self.eye_btn.configure(text="👁")
    
    def _open_botfather_help(self):
        """Open BotFather help in browser."""
        webbrowser.open("https://t.me/BotFather")
        self._set_status("Opened @BotFather - Create a new bot to get your token", "info")
    
    def _open_userinfobot(self):
        """Open userinfobot in browser."""
        webbrowser.open("https://t.me/userinfobot")
        self._set_status("Opened @userinfobot - Send /start to get your User ID", "info")
    
    def _validate_config(self) -> bool:
        """Validate the configuration values."""
        token = self.token_var.get().strip()
        userid = self.userid_var.get().strip()
        path = self.path_var.get().strip()
        
        if not token:
            self._set_status("❌ Bot Token is required", "error")
            return False
        
        # SEC: Validate token format more strictly
        # Format: 123456789:ABCdefGHI_JKLmno-pqrSTU
        import re
        token_pattern = r'^\d{8,10}:[A-Za-z0-9_-]{35,40}$'
        if not re.match(token_pattern, token):
            self._set_status("❌ Bot Token format appears invalid", "error")
            return False
        
        if not userid:
            self._set_status("❌ User ID is required", "error")
            return False
        
        try:
            int(userid)
        except ValueError:
            self._set_status("❌ User ID must be a number", "error")
            return False
        
        if not path:
            self._set_status("❌ Development Root folder is required", "error")
            return False
        
        if not Path(path).exists():
            self._set_status("❌ Selected folder does not exist", "error")
            return False
        
        # Check for dangerous folder selections
        danger_result = self._check_dangerous_folder(path)
        if danger_result:
            self._set_status(f"❌ Unsafe folder: {danger_result}", "error")
            messagebox.showerror(
                "🚫 DANGEROUS FOLDER",
                f"Cannot use this folder:\n\n"
                f"📁 {path}\n\n"
                f"Reason: {danger_result}\n\n"
                f"Please select a dedicated development folder."
            )
            return False
        
        return True
    
    def _save_config(self) -> bool:
        """Save configuration securely."""
        if not self._validate_config():
            return False
        
        try:
            token = self.token_var.get().strip()
            
            # SECURITY: Store token in encrypted vault instead of plaintext .env
            try:
                from .token_vault import get_vault, mask_token
                vault = get_vault()
                success, vault_msg = vault.store_token(token)
                
                if success:
                    # Token stored securely - don't write to .env
                    token_for_env = "[STORED_IN_SECURE_VAULT]"
                    self._set_status(f"🔒 Token secured: {mask_token(token)}", "success")
                else:
                    # Fallback to .env (with warning)
                    token_for_env = token
                    logger.warning(f"Vault storage failed: {vault_msg}, using .env fallback")
            except ImportError:
                # Token vault not available, use .env
                token_for_env = token
            
            # Get selected model alias from dropdown
            selected_model_display = self.model_var.get()
            selected_model_alias = "opus"  # Fallback
            if selected_model_display in self.model_choices:
                idx = self.model_choices.index(selected_model_display)
                if idx < len(self.model_aliases):
                    selected_model_alias = self.model_aliases[idx]
            
            # Write .env with other settings (token may be in vault)
            env_content = f"""# TeleCode Configuration
# Generated by TeleCode Setup GUI
# SECURITY: Token may be stored in encrypted vault (check .telecode_vault)

TELEGRAM_BOT_TOKEN={token_for_env}
ALLOWED_USER_ID={self.userid_var.get().strip()}
DEV_ROOT={self.path_var.get().strip()}
ENABLE_VOICE={str(self.voice_var.get()).lower()}
PREVENT_SLEEP={str(self.sleep_var.get()).lower()}
ENABLE_AUDIT_LOG={str(self.audit_var.get()).lower()}

# AI Model Configuration (use alias: opus, sonnet, haiku, gemini, gpt)
DEFAULT_MODEL={selected_model_alias}
"""
            
            env_path = Path(".env")
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(env_content)
            
            # Set restrictive permissions on .env
            try:
                if sys.platform != "win32":
                    import os
                    os.chmod(env_path, 0o600)
            except Exception:
                pass
            
            self._set_status("✅ Configuration saved securely!", "success")
            return True
            
        except Exception as e:
            self._set_status(f"❌ Failed to save: {e}", "error")
            return False
    
    def _save_and_start(self):
        """Save configuration and start the bot."""
        if self._save_config():
            if self.on_save_callback:
                # Show confirmation splash for new bot start
                messagebox.showinfo(
                    "🚀 TeleCode is Starting!",
                    "✅ Configuration saved!\n\n"
                    "TeleCode is now running in the background.\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "📱 CONTROL VIA TELEGRAM\n"
                    "   Open your bot and send /help\n\n"
                    "🖥️ SYSTEM TRAY\n"
                    "   Look for the green TeleCode icon\n"
                    "   near your clock (bottom right)\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "Right-click the tray icon to:\n"
                    "• View status\n"
                    "• Open settings\n"
                    "• Lock screen (TSCON)\n"
                    "• Stop TeleCode"
                )
                self.root.destroy()
                self.on_save_callback()
            else:
                # Settings-only mode - bot is already running
                messagebox.showinfo(
                    "✅ Settings Updated",
                    "✅ Configuration saved!\n\n"
                    "Your settings have been updated.\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "⚠️ NOTE: Some changes may require\n"
                    "   restarting TeleCode to take effect.\n\n"
                    "To restart:\n"
                    "1. Right-click TeleCode tray icon\n"
                    "2. Click 'Stop TeleCode'\n"
                    "3. Run TeleCode again"
                )
                self.root.destroy()
    
    
    def _show_voice_info(self):
        """Show info about voice transcription."""
        messagebox.showinfo(
            "Voice Transcription",
            "🎤 VOICE TRANSCRIPTION\n\n"
            "Send voice messages in Telegram and TeleCode\n"
            "will transcribe them to text commands.\n\n"
            "REQUIRES:\n"
            "• FFmpeg installed on your system\n"
            "• Internet connection (uses Google Speech API)\n\n"
            "EXAMPLE:\n"
            "1. Hold mic button in Telegram\n"
            "2. Say: 'Add a login button to the header'\n"
            "3. TeleCode transcribes → sends to Cursor AI\n\n"
            "FREE: Uses Google's free speech API."
        )
    
    def _show_sleep_info(self):
        """Show info about prevent sleep."""
        messagebox.showinfo(
            "Prevent Sleep Mode",
            "💤 PREVENT SLEEP MODE\n\n"
            "Keeps your computer awake while TeleCode runs.\n\n"
            "WHY:\n"
            "• Your PC won't go to sleep mid-task\n"
            "• Telegram commands always work\n"
            "• Long AI tasks won't be interrupted\n\n"
            "WHAT IT DOES:\n"
            "• Prevents screen saver\n"
            "• Prevents automatic sleep\n"
            "• Stops after TeleCode closes\n\n"
            "Your screen can still turn off to save power."
        )
    
    def _show_audit_info(self):
        """Show info about security logging."""
        messagebox.showinfo(
            "Security Logging",
            "📝 SECURITY AUDIT LOGGING\n\n"
            "Logs every command you run via Telegram.\n\n"
            "LOG FILE: telecode_audit.log\n\n"
            "WHAT'S LOGGED:\n"
            "• Every /command you send\n"
            "• AI prompts you execute\n"
            "• Git operations\n"
            "• File access attempts\n"
            "• Timestamps for everything\n\n"
            "WHY:\n"
            "• Review what you did remotely\n"
            "• Detect if someone else used your bot\n"
            "• Debug issues"
        )
    
    def _show_quick_lock_info(self):
        """Show info about Quick Lock mode."""
        messagebox.showinfo(
            "Quick Lock",
            "⚡ QUICK LOCK\n\n"
            "Screen goes black but TeleCode keeps running.\n\n"
            "STILL WORKS:\n"
            "✓ TeleCode (all Telegram commands)\n"
            "✓ Cursor AI (code changes)\n"
            "✓ Voice messages\n"
            "✓ Remote Desktop apps (RDP, TeamViewer, AnyDesk)\n\n"
            "USE WHEN:\n"
            "• At home on trusted network\n"
            "• You want to use a Remote Desktop app later\n\n"
            "TO UNLOCK: Press any key → enter password"
        )
    
    def _show_secure_lock_info(self):
        """Show info about Secure Lock mode."""
        messagebox.showinfo(
            "Secure Lock",
            "🛡️ SECURE LOCK (Recommended)\n\n"
            "Screen goes black. Remote Desktop apps blocked.\n\n"
            "STILL WORKS:\n"
            "✓ TeleCode (all Telegram commands)\n"
            "✓ Cursor AI (code changes)\n"
            "✓ Voice messages\n\n"
            "BLOCKED:\n"
            "✗ Remote Desktop apps (RDP, TeamViewer, AnyDesk)\n"
            "✗ Must be physically at PC to unlock\n\n"
            "EXTRA SAFETY:\n"
            "• Auto-locks after 30 minutes\n"
            "• All actions logged\n\n"
            "USE WHEN:\n"
            "• In public (cafe, office, coworking)\n"
            "• You don't need Remote Desktop apps\n\n"
            "TO UNLOCK: Press any key → enter password"
        )
    
    def _run_quick_lock(self):
        """Run Quick Lock (standard TSCON) - requests UAC elevation if needed."""
        try:
            from .tscon_helper import TSCONManager
            manager = TSCONManager()
            
            confirm = messagebox.askyesno(
                "⚡ Quick Lock",
                "This will disconnect your display.\n\n"
                "⚠️ Note: Remote Desktop stays ENABLED.\n"
                "Someone could still connect to your PC remotely.\n\n"
                "You will be prompted for Administrator access.\n\n"
                "Proceed with Quick Lock?",
                icon="warning"
            )
            
            if confirm:
                if manager.is_admin:
                    # Already admin, run directly
                    success, message = manager.lock_session()
                    if not success:
                        messagebox.showerror("Error", message)
                else:
                    # Request UAC elevation
                    self._run_elevated_lock(secure_mode=False)
        except Exception as e:
            messagebox.showerror("Error", f"Quick Lock failed: {e}")
    
    def _run_secure_lock(self):
        """Run Secure Lock (TSCON with remote access blocked + timeout) - requests UAC elevation if needed."""
        try:
            from .tscon_helper import TSCONManager
            manager = TSCONManager()
            
            confirm = messagebox.askyesno(
                "🛡️ Secure Lock",
                "This will:\n"
                "• Disconnect your display\n"
                "• DISABLE Remote Desktop\n"
                "• Auto-lock after 30 minutes\n\n"
                "Security features enabled:\n"
                "✓ Remote connections blocked\n"
                "✓ Physical access required to reconnect\n"
                "✓ Automatic timeout protection\n\n"
                "You will be prompted for Administrator access.\n\n"
                "Proceed with Secure Lock?",
                icon="warning"
            )
            
            if confirm:
                if manager.is_admin:
                    # Already admin, run directly
                    success, message = manager.lock_session_secure(watchdog_minutes=30)
                    if not success:
                        messagebox.showerror("Error", message)
                else:
                    # Request UAC elevation
                    self._run_elevated_lock(secure_mode=True)
        except Exception as e:
            messagebox.showerror("Error", f"Secure Lock failed: {e}")
    
    def _run_elevated_lock(self, secure_mode: bool = False):
        """
        Run TSCON lock with UAC elevation prompt.
        
        Uses ShellExecuteW with 'runas' verb to request elevation.
        """
        import ctypes
        from pathlib import Path
        
        if sys.platform != "win32":
            messagebox.showwarning("Not Available", "This feature is only available on Windows.")
            return
        
        try:
            # Find the appropriate BAT file
            project_root = Path(__file__).parent.parent
            
            if secure_mode:
                script_path = project_root / "tscon_secure_lock.bat"
            else:
                script_path = project_root / "tscon_lock.bat"
            
            if script_path.exists():
                # Run the BAT file with elevation
                result = ctypes.windll.shell32.ShellExecuteW(
                    None,          # hwnd
                    "runas",       # verb (run as admin)
                    str(script_path),  # file
                    None,          # parameters
                    str(project_root),  # directory
                    1              # show command (SW_SHOWNORMAL)
                )
                
                if result <= 32:
                    messagebox.showerror("Error", f"Failed to request administrator access (code: {result})")
            else:
                # Fallback: run Python with tscon_helper directly
                python_exe = sys.executable
                tscon_module = str(project_root / "src" / "tscon_helper.py")
                
                params = f'"{tscon_module}" --lock'
                if secure_mode:
                    params += " --secure"
                
                result = ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "runas",
                    python_exe,
                    params,
                    str(project_root),
                    1
                )
                
                if result <= 32:
                    messagebox.showerror("Error", f"Failed to request administrator access (code: {result})")
                    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run elevated lock: {e}")
    
    def _show_tscon_help(self):
        """Show TSCON help dialog."""
        help_text = """🔒 TSCON - Keep Session Active While "Locked"

WHAT IT DOES:
Disconnects your screen from Windows while keeping
everything running in memory.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🛡️ SECURE MODE (Recommended)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Disables Remote Desktop
✓ Auto-locks after 30 minutes
✓ Only physical access can reconnect
✓ All events logged to audit file

⚡ STANDARD MODE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Quick disconnect
• Remote access stays enabled
• No timeout protection
• Less secure but simpler

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HOW TO USE:
1. Click "Create Shortcuts"
2. When leaving your laptop:
   - Right-click TeleCode_SecureLock.bat
   - Select "Run as administrator"
3. Screen goes black
4. Control via Telegram!

TO RECONNECT:
• Press any key or move mouse
• Enter your Windows password

💡 TIP: Use Secure Mode unless you specifically
need Remote Desktop access while away.
"""
        messagebox.showinfo("TSCON Help", help_text)
    
    def run(self):
        """Start the GUI event loop."""
        self.root.mainloop()


def show_config_gui(on_save_callback: Optional[Callable] = None):
    """
    Display the configuration GUI.
    
    Args:
        on_save_callback: Function to call when config is saved
    """
    gui = ConfigurationGUI(on_save_callback)
    gui.run()


if __name__ == "__main__":
    # Allow running GUI standalone for testing
    show_config_gui()

