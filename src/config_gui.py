"""
============================================
TeleCode v0.2 - Configuration GUI
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
        self.pending_pin = None  # Store PIN in memory until Save is pressed
        self.root = tk.Tk()
        self._setup_window()
        self._create_widgets()
        self._load_existing_config()
    
    def _setup_window(self):
        """Configure the main window."""
        self.root.title("TeleCode - Setup")
        self.root.configure(bg=XP_COLORS["bg_main"])
        self.root.resizable(True, True)  # Allow resizing
        
        # Center window on screen (850x800 for good aspect ratio, scrollable for longer content)
        window_width = 850
        window_height = 800
        
        # Set minimum size so UI doesn't break when resized too small
        self.root.minsize(700, 600)
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Adjust window height if screen is smaller
        if screen_height < window_height + 100:
            window_height = screen_height - 100
        
        x = (screen_width - window_width) // 2
        y = max(20, (screen_height - window_height) // 2)  # Ensure not off-screen
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Set window icon
        try:
            icon_path = Path(__file__).parent.parent / "assets" / "icon.ico"
            if icon_path.exists() and sys.platform == "win32":
                self.root.iconbitmap(str(icon_path))
        except Exception as e:
            logger.debug(f"Could not set window icon: {e}")
    
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
        
        self.main_canvas = tk.Canvas(canvas_frame, bg=XP_COLORS["bg_main"], highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=self.main_canvas.yview)
        
        # Main container inside canvas
        main_frame = tk.Frame(self.main_canvas, bg=XP_COLORS["bg_main"], padx=15, pady=15)
        
        # Configure canvas scrolling
        self.main_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.main_canvas.pack(side="left", fill="both", expand=True)
        
        # Create window inside canvas
        canvas_window = self.main_canvas.create_window((0, 0), window=main_frame, anchor="nw")
        
        # Update scroll region when content changes
        def on_frame_configure(event):
            # Update the scroll region to match the size of the frame
            self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        main_frame.bind("<Configure>", on_frame_configure)
        
        # Make canvas width follow window width
        def on_canvas_configure(event):
            canvas_width = event.width
            self.main_canvas.itemconfig(canvas_window, width=canvas_width)
        self.main_canvas.bind("<Configure>", on_canvas_configure)
        
        # Enable mousewheel scrolling - bind to canvas and frame
        def on_mousewheel(event):
            # Windows uses delta, Linux/Mac use different values
            if sys.platform == "win32":
                delta = int(-1 * (event.delta / 120))
            else:
                delta = -1 if event.num == 4 else 1
            self.main_canvas.yview_scroll(delta, "units")
        
        # Bind mousewheel to canvas and frame for better coverage
        self.main_canvas.bind("<MouseWheel>", on_mousewheel)
        canvas_frame.bind("<MouseWheel>", on_mousewheel)
        main_frame.bind("<MouseWheel>", on_mousewheel)
        
        # Also bind to Linux/Mac mouse buttons
        if sys.platform != "win32":
            self.main_canvas.bind("<Button-4>", on_mousewheel)
            self.main_canvas.bind("<Button-5>", on_mousewheel)
            canvas_frame.bind("<Button-4>", on_mousewheel)
            canvas_frame.bind("<Button-5>", on_mousewheel)
            main_frame.bind("<Button-4>", on_mousewheel)
            main_frame.bind("<Button-5>", on_mousewheel)
        
        # Make canvas focusable for keyboard scrolling
        self.main_canvas.focus_set()
        
        # ==========================================
        # Header with Logo
        # ==========================================
        header_frame = tk.Frame(main_frame, bg=XP_COLORS["bg_main"])
        header_frame.pack(fill="x", pady=(0, 15))
        
        # Logo and title container
        logo_title_frame = tk.Frame(header_frame, bg=XP_COLORS["bg_main"])
        logo_title_frame.pack(fill="x", pady=(0, 5))
        
        # Try to load and display logo
        logo_path = Path(__file__).parent.parent / "assets" / "telecode.png"
        if logo_path.exists():
            try:
                from PIL import Image, ImageTk
                logo_img = Image.open(logo_path)
                # Resize logo to fit nicely (max 120px height)
                logo_img.thumbnail((180, 120), Image.Resampling.LANCZOS)
                logo_photo = ImageTk.PhotoImage(logo_img)
                logo_label = tk.Label(
                    logo_title_frame,
                    image=logo_photo,
                    bg=XP_COLORS["bg_main"]
                )
                logo_label.image = logo_photo  # Keep a reference
                logo_label.pack(side="left", padx=(0, 15))
            except Exception as e:
                logger.debug(f"Could not load logo: {e}")
        
        # Title and subtitle in a frame
        title_frame = tk.Frame(logo_title_frame, bg=XP_COLORS["bg_main"])
        title_frame.pack(side="left", fill="x", expand=True)
        
        title_label = tk.Label(
            title_frame,
            text="🚀 TeleCode Configuration",
            font=("Tahoma", 14, "bold"),
            bg=XP_COLORS["bg_main"],
            fg=XP_COLORS["text"]
        )
        title_label.pack(anchor="w")
        
        subtitle_label = tk.Label(
            title_frame,
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
        
        # Multi-sandbox list with scrollable frame
        sandbox_list_frame = tk.Frame(sandbox_group, bg="#FFF8DC")
        sandbox_list_frame.pack(fill="both", expand=True, pady=(5, 5))
        
        # Scrollable canvas for sandbox list
        canvas = tk.Canvas(sandbox_list_frame, bg="#FFF8DC", highlightthickness=0, height=150)
        scrollbar = tk.Scrollbar(sandbox_list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#FFF8DC")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.sandbox_list_frame = scrollable_frame
        self.sandbox_canvas = canvas
        self.sandbox_vars = []  # List of StringVar for each sandbox
        
        # Add button
        add_btn_frame = tk.Frame(sandbox_group, bg="#FFF8DC")
        add_btn_frame.pack(fill="x", pady=(5, 0))
        
        add_btn = XPStyleButton(
            add_btn_frame,
            text="➕ Add Sandbox Directory",
            command=self._add_sandbox_folder
        )
        add_btn.pack(side="left")
        
        # Info label
        info_label = tk.Label(
            add_btn_frame,
            text="(Up to 10 directories allowed)",
            font=("Tahoma", 7),
            fg="#666666",
            bg="#FFF8DC"
        )
        info_label.pack(side="left", padx=(10, 0))
        
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
                "🚀 Gemini 3 Pro ⭐",
                "🧠 GPT-5.2 ⭐",
                "💻 GPT-5.2 Codex ⭐",
                "🦙 Meta Llama 3.1 🆓",
                "🤖 xAI Grok ⭐",
            ]
            self.model_aliases = [
                "opus",
                "sonnet",
                "haiku",
                "gemini",
                "geminipro",
                "gpt",
                "codex",
                "llama",
                "grok",
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
        # Lock PIN Section (Windows Only)
        # ==========================================
        if sys.platform == "win32":
            lockpin_group = tk.LabelFrame(
                main_frame,
                text=" 🔒 Lock PIN (Windows) ",
                font=("Tahoma", 8, "bold"),
                bg=XP_COLORS["bg_groupbox"],
                fg=XP_COLORS["text"],
                padx=10,
                pady=8
            )
            lockpin_group.pack(fill="x", pady=(0, 10))
            
            lockpin_info = tk.Label(
                lockpin_group,
                text="Set a PIN for secure display lock.\n"
                     "When display turns off, PIN will be required on wake.\n"
                     "💡 Tip: You can use your Windows password as the PIN!\n"
                     "💡 Forgot PIN? Reset via Telegram: /pin set",
                font=("Tahoma", 7),
                fg="#666666",
                bg=XP_COLORS["bg_groupbox"],
                justify="left"
            )
            lockpin_info.pack(anchor="w", pady=(0, 10))
            
            # PIN status
            status_frame = tk.Frame(lockpin_group, bg=XP_COLORS["bg_groupbox"])
            status_frame.pack(fill="x", pady=(0, 10))
            
            tk.Label(
                status_frame,
                text="Status:",
                font=("Tahoma", 8),
                bg=XP_COLORS["bg_groupbox"],
                fg=XP_COLORS["text"]
            ).pack(side="left")
            
            self.pin_status_label = tk.Label(
                status_frame,
                text="⚠️ Not set",
                font=("Tahoma", 8, "bold"),
                bg=XP_COLORS["bg_groupbox"],
                fg="#CC6600"
            )
            self.pin_status_label.pack(side="left", padx=(5, 0))
            
            # Update PIN status display
            self._update_pin_status()
            
            # PIN input frame
            pin_frame = tk.Frame(lockpin_group, bg=XP_COLORS["bg_groupbox"])
            pin_frame.pack(fill="x", pady=(0, 5))
            
            tk.Label(
                pin_frame,
                text="PIN:",
                font=("Tahoma", 8),
                bg=XP_COLORS["bg_groupbox"],
                fg=XP_COLORS["text"],
                width=8,
                anchor="w"
            ).pack(side="left")
            
            self.pin_var = tk.StringVar()
            self.pin_visible = False  # Track PIN visibility state
            
            pin_entry = XPStyleEntry(
                pin_frame,
                textvariable=self.pin_var,
                width=20,
                show="*"
            )
            pin_entry.pack(side="left", padx=(5, 5))
            
            def set_pin():
                """Store PIN in memory (not saved until user clicks Save)."""
                pin = self.pin_var.get().strip()
                if not pin:
                    self._set_status("❌ Please enter a PIN", "error")
                    return
                if len(pin) < 4:
                    self._set_status("❌ PIN must be at least 4 characters", "error")
                    return
                
                # Store in memory - will be saved when user clicks Save
                self.pending_pin = pin
                self._set_status(f"✅ PIN ready to save (click 'Save Config' to persist)", "success")
                self.pin_var.set("")
                # Update status display
                self._update_pin_status()
            
            set_pin_btn = XPStyleButton(
                pin_frame,
                text="Set PIN",
                command=set_pin,
                width=10
            )
            set_pin_btn.pack(side="left", padx=(0, 5))
            
            def toggle_pin_visibility():
                """Toggle PIN visibility (mask/unmask)."""
                self.pin_visible = not self.pin_visible
                if self.pin_visible:
                    pin_entry.configure(show="")
                    eye_btn.configure(text="🙈")
                else:
                    pin_entry.configure(show="*")
                    eye_btn.configure(text="👁")
            
            eye_btn = XPStyleButton(
                pin_frame,
                text="👁",
                command=toggle_pin_visibility,
                width=4
            )
            eye_btn.pack(side="left")
        
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
                text="Run TeleCode headless with a virtual display (Xvfb). This allows GUI automation\neven without a physical monitor — the Linux equivalent of Windows Screen Lock.",
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
        
        # Update scroll region after all widgets are created
        self.root.update_idletasks()
        self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        
    def _load_existing_config(self):
        """Load existing configuration from .env if present."""
        try:
            from dotenv import dotenv_values
            from src.system_utils import get_user_data_dir
            
            # Check user data directory first (for installed applications)
            user_data_dir = get_user_data_dir()
            env_path = user_data_dir / ".env"
            
            # Fallback to current directory (for development)
            if not env_path.exists():
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
                
                # Load sandboxes from config (multi-sandbox support)
                from src.sandbox_config import get_sandbox_config
                sandbox_config = get_sandbox_config()
                
                if sandbox_config.sandboxes:
                    # Load from sandbox config
                    for sandbox_path in sandbox_config.sandboxes:
                        self._add_sandbox_to_ui(sandbox_path)
                elif config.get("DEV_ROOT"):
                    # Backward compatibility: load single DEV_ROOT
                    self._add_sandbox_to_ui(config["DEV_ROOT"])
                
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
    
    def _update_pin_status(self):
        """Update the PIN status label display."""
        if not hasattr(self, 'pin_status_label'):
            return
        
        try:
            # Check if there's a pending PIN (not yet saved)
            if self.pending_pin:
                status_text = f"✅ PIN ready to save ({'*' * (len(self.pending_pin) - 2) + self.pending_pin[-2:] if len(self.pending_pin) > 2 else '****'})"
                status_color = XP_COLORS["success"]
            else:
                # Check stored PIN
                from .lock_pin_storage import get_lock_pin_storage
                storage = get_lock_pin_storage()
                pin = storage.retrieve_pin()
                # Check for legacy password (backward compatibility)
                password = storage.retrieve_password()
                
                if pin:
                    status_text = f"✅ PIN set ({'*' * (len(pin) - 2) + pin[-2:] if len(pin) > 2 else '****'})"
                    status_color = XP_COLORS["success"]
                elif password:
                    # Legacy password found - show as PIN (they work the same way)
                    status_text = "✅ PIN set (legacy password)"
                    status_color = XP_COLORS["success"]
                else:
                    status_text = "⚠️ Not set"
                    status_color = "#CC6600"
        except:
            status_text = "❌ Error loading status"
            status_color = "#CC0000"
        
        self.pin_status_label.configure(text=status_text, fg=status_color)
    
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
    
    def _add_sandbox_folder(self):
        """Open folder dialog to add a new sandbox directory."""
        folder = filedialog.askdirectory(
            title="Select Sandbox Directory",
            mustexist=True
        )
        
        if folder:
            folder_path = Path(folder).resolve()
            folder_str = str(folder_path)
            
            # Check if already in list
            existing_paths = [var.get().strip() for var in self.sandbox_vars]
            if folder_str in existing_paths:
                messagebox.showwarning(
                    "Already Added",
                    f"This directory is already in the sandbox list:\n{folder_str}"
                )
                return
            
            # Check limit
            if len(self.sandbox_vars) >= 10:
                messagebox.showwarning(
                    "Limit Reached",
                    "Maximum 10 sandbox directories allowed."
                )
                return
            
            # Check if dangerous
            danger_msg = self._check_dangerous_folder(folder_str)
            if danger_msg:
                messagebox.showwarning("⚠️ Dangerous Folder", danger_msg)
                return
            
            # Add to UI
            self._add_sandbox_to_ui(folder_str)
            self._set_status(f"✅ Added sandbox: {folder_path.name}", "success")
    
    def _add_sandbox_to_ui(self, path: str):
        """Add a sandbox path to the UI list."""
        # Create entry frame
        entry_frame = tk.Frame(self.sandbox_list_frame, bg="#FFF8DC")
        entry_frame.pack(fill="x", padx=5, pady=2)
        
        # Create StringVar for this sandbox
        var = tk.StringVar(value=path)
        self.sandbox_vars.append(var)
        
        # Entry field
        entry = tk.Entry(
            entry_frame,
            textvariable=var,
            font=("Tahoma", 8),
            bg="white",
            relief="sunken",
            bd=1
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        # Remove button
        remove_btn = XPStyleButton(
            entry_frame,
            text="✖",
            command=lambda: self._remove_sandbox_from_ui(entry_frame, var),
            width=3
        )
        remove_btn.pack(side="right")
        
        # Update canvas scroll region
        self.sandbox_list_frame.update_idletasks()
        self.sandbox_canvas.configure(scrollregion=self.sandbox_canvas.bbox("all"))
    
    def _remove_sandbox_from_ui(self, frame: tk.Frame, var: tk.StringVar):
        """Remove a sandbox entry from the UI."""
        if var in self.sandbox_vars:
            self.sandbox_vars.remove(var)
        frame.destroy()
        
        # Update canvas scroll region
        self.sandbox_list_frame.update_idletasks()
        self.sandbox_canvas.configure(scrollregion=self.sandbox_canvas.bbox("all"))
        
        self._set_status("Removed sandbox directory", "info")
    
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
        
        # Validate sandboxes
        if not self.sandbox_vars:
            self._set_status("❌ At least one sandbox directory is required", "error")
            return False
        
        # Check each sandbox
        for var in self.sandbox_vars:
            path = var.get().strip()
            if not path:
                self._set_status("❌ All sandbox directories must be set", "error")
                return False
            
            if not Path(path).exists():
                self._set_status(f"❌ Directory does not exist: {path}", "error")
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
            
            # Collect sandbox directories
            sandbox_paths = []
            for var in self.sandbox_vars:
                path = var.get().strip()
                if path:
                    try:
                        # Validate path exists
                        path_obj = Path(path).resolve()
                        if path_obj.exists() and path_obj.is_dir():
                            sandbox_paths.append(str(path_obj))
                        else:
                            self._set_status(f"⚠️ Warning: Directory does not exist: {path}", "error")
                    except Exception as e:
                        self._set_status(f"⚠️ Warning: Invalid path: {path} - {e}", "error")
            
            if not sandbox_paths:
                messagebox.showerror(
                    "No Sandboxes",
                    "Please add at least one sandbox directory."
                )
                return False
            
            # Save sandbox configuration
            from src.sandbox_config import get_sandbox_config
            sandbox_config = get_sandbox_config()
            
            # Clear existing and add new ones
            sandbox_config.sandboxes = []
            for path in sandbox_paths:
                success, msg = sandbox_config.add_sandbox(path)
                if not success:
                    self._set_status(f"⚠️ Failed to add sandbox: {msg}", "error")
            
            # Set first as current if none set
            if sandbox_config.current_index >= len(sandbox_config.sandboxes):
                sandbox_config.current_index = 0
            
            if not sandbox_config.save():
                messagebox.showerror("Error", "Failed to save sandbox configuration")
                return False
            
            # Get current sandbox for DEV_ROOT (backward compatibility)
            current_sandbox = sandbox_config.get_current() or sandbox_paths[0]
            
            # Write .env with other settings (token may be in vault)
            env_content = f"""# TeleCode Configuration
# Generated by TeleCode Setup GUI
# SECURITY: Token may be stored in encrypted vault (check .telecode_vault)
# NOTE: Multiple sandboxes are stored in sandboxes.json
# DEV_ROOT here is the current active sandbox (for backward compatibility)

TELEGRAM_BOT_TOKEN={token_for_env}
ALLOWED_USER_ID={self.userid_var.get().strip()}
DEV_ROOT={current_sandbox}
ENABLE_VOICE={str(self.voice_var.get()).lower()}
PREVENT_SLEEP={str(self.sleep_var.get()).lower()}
ENABLE_AUDIT_LOG={str(self.audit_var.get()).lower()}

# AI Model Configuration (use alias: opus, sonnet, haiku, gemini, gpt)
DEFAULT_MODEL={selected_model_alias}
"""
            
            # Save .env to user data directory (works when installed in Program Files)
            from src.system_utils import get_user_data_dir
            user_data_dir = get_user_data_dir()
            env_path = user_data_dir / ".env"
            
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(env_content)
            
            # Set restrictive permissions on .env
            try:
                if sys.platform != "win32":
                    import os
                    os.chmod(env_path, 0o600)
            except Exception:
                pass
            
            # Save PIN if there's a pending one
            if self.pending_pin:
                try:
                    from .lock_pin_storage import get_lock_pin_storage
                    from .custom_lock import set_lock_pin
                    storage = get_lock_pin_storage()
                    success, msg = storage.store_pin(self.pending_pin)
                    if success:
                        set_lock_pin(self.pending_pin)
                        self._set_status(f"✅ Configuration saved! PIN saved. {len(sandbox_paths)} sandbox(es) configured.", "success")
                        self.pending_pin = None  # Clear pending PIN
                        self._update_pin_status()  # Update status display
                    else:
                        self._set_status(f"⚠️ Config saved but PIN failed: {msg}", "error")
                except Exception as e:
                    logger.error(f"Failed to save PIN: {e}")
                    self._set_status(f"⚠️ Config saved but PIN failed: {e}", "error")
            else:
                self._set_status(f"✅ Configuration saved! {len(sandbox_paths)} sandbox(es) configured.", "success")
            
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
                    "• Turn off display\n"
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
    
    def run(self):
        """Start the GUI event loop."""
        try:
            # Bring window to front and focus
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.after_idle(lambda: self.root.attributes('-topmost', False))
            self.root.focus_force()
            
            # Update scroll region after window is fully rendered
            def update_scroll_region():
                self.root.update_idletasks()
                self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
            self.root.after(100, update_scroll_region)
            
            # Start main loop
            self.root.mainloop()
        except Exception as e:
            logger.error(f"GUI error: {e}", exc_info=True)
            # Try to show error in messagebox if possible
            try:
                messagebox.showerror("TeleCode Error", f"Failed to start configuration GUI:\n\n{e}")
            except:
                pass
            raise


def show_config_gui(on_save_callback: Optional[Callable] = None):
    """
    Display the configuration GUI.
    
    Args:
        on_save_callback: Function to call when config is saved
    """
    try:
        gui = ConfigurationGUI(on_save_callback)
        gui.run()
    except Exception as e:
        logger.error(f"Failed to show config GUI: {e}", exc_info=True)
        # Try to show error dialog
        try:
            import tkinter.messagebox as mb
            mb.showerror("TeleCode Error", f"Failed to open configuration:\n\n{e}\n\nPlease check the logs for details.")
        except:
            pass
        raise


if __name__ == "__main__":
    # Allow running GUI standalone for testing
    show_config_gui()

