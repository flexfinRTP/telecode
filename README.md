# 🚀 TeleCode v0.1.13

<div align="center">
  <img src="assets/telecode.png" alt="TeleCode Logo" width="200">
  
  **Voice-to-Code, From Anywhere**
</div>

[![Website](https://img.shields.io/badge/Website-telecodebot.com-39ff14.svg)](https://telecodebot.com)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Security: Hardened](https://img.shields.io/badge/Security-Hardened-brightgreen.svg)](#security)
[![OWASP: Compliant](https://img.shields.io/badge/OWASP-Compliant-blue.svg)](docs/SECURITY_AUDIT.md)
[![Download](https://img.shields.io/badge/Download-Latest%20Release-blue.svg)](https://github.com/flexfinRTP/telecode/releases/latest)
[![Cross-Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-blue.svg)](#-download--install)

**🌐 Website: [telecodebot.com](https://telecodebot.com)**

Control Cursor AI from your phone via Telegram. **Voice-to-code** that works from anywhere — uses your existing Cursor subscription with **zero API costs**.

> 🎤 **Speak your code changes** • 🌍 **Works from anywhere** • 💰 **No API fees** • 🔒 **Works even with laptop locked**

> 🔒 **Security Hardened**: [Full security audit](docs/SECURITY_AUDIT.md) with token encryption, prompt injection defense, and rate limiting.
> 🌍 **v0.1.13**: Agent button routing fixes, screenshot timing improvements, and enhanced multi-agent support!

---

## 📥 Download & Install

### One-Click Installers

| Platform | Download | Size |
|----------|----------|------|
| 🪟 **Windows** | [**TeleCode_Setup_Windows.exe**](https://github.com/flexfinRTP/telecode/releases/latest/download/TeleCode_Setup_v0.1.13_Windows.exe) | ~50 MB |
| 🍎 **macOS** | [**TeleCode_macOS.dmg**](https://github.com/flexfinRTP/telecode/releases/latest/download/TeleCode_v0.1.13_macOS.dmg) | ~45 MB |
| 🐧 **Linux** | [**TeleCode_Linux.tar.gz**](https://github.com/flexfinRTP/telecode/releases/latest/download/TeleCode_v0.1.13_Linux.tar.gz) | ~40 MB |

> 📦 **No Python required!** The installers include everything bundled.

### Installation Instructions

<details>
<summary><b>🪟 Windows</b></summary>

1. Download `TeleCode_Setup_v0.1.13_Windows.exe`
2. Run the installer (right-click → "Run as administrator" if needed)
3. Follow the setup wizard
4. Optional: Create TSCON shortcuts for screen lock while running (system tray → Secure Lock)
5. Launch TeleCode from Start Menu or Desktop

</details>

<details>
<summary><b>🍎 macOS</b></summary>

1. Download `TeleCode_v0.1.13_macOS.dmg`
2. Open the DMG file
3. Drag TeleCode to your Applications folder
4. First launch: Right-click → Open (to bypass Gatekeeper)
5. Grant microphone and accessibility permissions if prompted

</details>

<details>
<summary><b>🐧 Linux</b></summary>

```bash
# Download and extract
wget https://github.com/flexfinRTP/telecode/releases/latest/download/TeleCode_v0.1.13_Linux.tar.gz
tar -xzvf TeleCode_v0.1.13_Linux.tar.gz
cd TeleCode_v0.1.13_Linux

# Install (adds to ~/.local/bin and creates .desktop entry)
./install.sh

# Optional: Install headless mode dependencies
sudo apt install xvfb xdotool
pip install pyvirtualdisplay

# Run
telecode
```

</details>

---

## ✨ Why TeleCode?

| Benefit | Description |
|---------|-------------|
| 🎤 **Voice-to-Code** | Speak your prompts from your phone — they become Cursor AI commands |
| 💰 **Zero API Costs** | Uses your existing Cursor subscription. No OpenAI API key needed |
| 🌍 **Code From Anywhere** | On a train? At the gym? Control your code remotely via Telegram |
| 🔒 **Works Locked** | CLI-based — works even when your laptop screen is locked |
| 📱 **Just Use Telegram** | No custom app to install. Works on any device |

---

## ✨ Features

### 🎤 Voice-to-Code
Hold the mic button in Telegram and speak your coding request. TeleCode transcribes it using **free Google Speech Recognition** (no API key required) and sends it to Cursor AI.

### 💰 Uses Your Cursor Plan
TeleCode uses the **Cursor CLI** to execute AI prompts — meaning you use your existing Cursor subscription. No separate OpenAI API costs!

### 🌍 Remote Control From Anywhere
Control your development machine from anywhere in the world via Telegram:
- Git operations (status, push, pull, commit)
- AI-powered code changes
- File navigation and reading
- Project scaffolding

### 🔒 Lock-Proof Operation
Unlike GUI automation tools, TeleCode uses **Cursor CLI** and **subprocess** commands. Works perfectly even when your laptop is locked in your bag.

### 🛡️ Zero-Trust Security
- **Token Encryption**: Bot token stored in encrypted vault (DPAPI/Keychain)
- **Prompt Injection Defense**: Multi-layer protection against token extraction
- **Single-User Authentication**: Only your Telegram ID can control the bot
- **Filesystem Sandbox**: All operations restricted to your dev folder
- **Command Whitelist**: Only approved commands (git, cursor) can execute
- **Rate Limiting**: Prevents brute-force and DoS attacks
- **Audit Logging**: Every remote command is logged for review
- **No Open Ports**: Uses Telegram long-polling (outbound only)

See the [full security audit](docs/SECURITY_AUDIT.md) for details.

---

## 🏗️ Architecture

```
[Mobile User (Telegram)]
       |
       v
[Telegram Cloud]
       | (Long Polling - Outbound Only)
       v
[Your Laptop]
   +-- [Security Sentinel] (Auth + Sandbox)
   |
   +-- [Command Router]
          |
          +-- [Git Handler] (subprocess 'git')
          |
          +-- [AI Handler] (Cursor CLI)
```

---

## ⚡ Quick Start (30 Seconds)

### Option 1: Download Installer (Recommended)

See [Download & Install](#-download--install) above for one-click installers.

### Option 2: Run from Source

<details>
<summary><b>Prerequisites</b></summary>

- Python 3.10+
- Git
- Cursor IDE (with CLI installed)
- FFmpeg (optional, for voice features)

</details>

**Windows:**
```batch
git clone https://github.com/flexfinRTP/telecode.git
cd telecode
setup.bat
```

**macOS / Linux:**
```bash
git clone https://github.com/flexfinRTP/telecode.git
cd telecode
chmod +x setup.sh start.sh
./setup.sh
```

<details>
<summary><b>Manual Setup (Advanced)</b></summary>

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Unix/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run TeleCode
python main.py
```

</details>

---

## ⚙️ Configuration

TeleCode stores configuration in a `.env` file. You can configure via:

1. **GUI Setup** (Recommended): Run `python main.py --config`
2. **Manual**: Copy `env.example` to `.env` and edit

### Required Settings

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Your bot token from [@BotFather](https://t.me/BotFather) |
| `ALLOWED_USER_ID` | Your Telegram user ID from [@userinfobot](https://t.me/userinfobot) |
| `DEV_ROOT` | Root folder for all operations (the "sandbox") |

### Optional Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_VOICE` | `true` | Enable voice message transcription |
| `PREVENT_SLEEP` | `true` | Keep system awake while bot runs |
| `ENABLE_AUDIT_LOG` | `true` | Log all commands for security audit |

---

## 📱 Bot Commands

### Git Operations
| Command | Description |
|---------|-------------|
| `/status` | Show git status |
| `/diff` | Show uncommitted changes |
| `/push` | Push to remote |
| `/pull` | Pull from remote |
| `/commit [msg]` | Commit all changes |
| `/revert` | Discard all changes ⚠️ |
| `/log` | Show recent commits |
| `/branch` | List branches |

### Navigation
| Command | Description |
|---------|-------------|
| `/sandbox` | Switch sandbox directory |
| `/sandboxes` | List all sandbox directories |
| `/ls [path]` | List files |
| `/read [file]` | Read file contents |
| `/pwd` | Show current path |

### Project & IDE
| Command | Description |
|---------|-------------|
| `/create` | Create new project (interactive wizard) |
| `/cursor` | Check Cursor IDE status |
| `/cursor open` | Launch Cursor for current workspace |

### AI (Headless)
| Command | Description |
|---------|-------------|
| `/ai [prompt]` | Execute Cursor AI prompt |
| `/ai accept` | Accept AI changes in Cursor (Ctrl+Enter) |
| `/ai reject` | Reject AI changes in Cursor (Escape) |
| `/ai continue [prompt]` | Continue with follow-up prompt |
| `/ai stop` | Stop/clear current AI session |
| `/ai status` | Check agent state and pending changes |
| `/ai mode [agent\|chat]` | Switch prompt mode (Agent/Chat) |
| `/model` | Select AI model (interactive menu) |
| `/model [alias]` | Quick switch (`opus`, `sonnet`, `haiku`, `gemini`, `gpt`) |
| `/models` | List all available models |
| *(plain text)* | Treated as AI prompt |
| *(voice note)* | Transcribed and executed as prompt |

### After AI Execution - Action Buttons

After every AI prompt, inline action buttons appear:

| Button | Action |
|--------|--------|
| 📊 Check | See files modified |
| 📖 Diff | View changes |
| ✅ Accept | Accept changes in Cursor (Ctrl+Enter) |
| ❌ Reject | Reject changes in Cursor (Escape) |
| ➡️ Continue | Continue AI with follow-up |
| ⚙️ Mode | Switch Agent/Chat mode |
| 🧹 Cleanup | Close old agent tabs |

**Note:** Run button only appears when AI is waiting for approval (not on completion).

### System
| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | List commands |
| `/info` | System status |

---

## 🔐 Security

TeleCode is designed with security as the **#1 priority**. See [SECURITY.md](docs/SECURITY.md) for full details.

### Key Security Features

1. **Hard-Coded User ID**: Only your Telegram ID can interact with the bot
2. **Filesystem Sandbox**: Cannot escape the configured `DEV_ROOT` folder
3. **Path Traversal Prevention**: Blocks `..`, `~`, and absolute paths outside sandbox
4. **Command Whitelist**: Only `git`, `cursor`, `ls` commands allowed
5. **Blocked Files**: Cannot read `.env`, SSH keys, or credential files
6. **Shell Injection Prevention**: Blocks `&&`, `|`, `;`, `` ` `` and other shell operators
7. **No Open Ports**: Uses outbound-only Telegram long-polling
8. **Audit Logging**: Every command logged to `telecode_audit.log`

---

## 🎤 Voice Features

TeleCode can transcribe voice notes using the **free** Google Speech Recognition API.

### Requirements
- FFmpeg installed and in PATH
- `pydub` and `SpeechRecognition` packages (included in requirements.txt)

### How It Works
1. You send a voice note in Telegram
2. Bot downloads the `.ogg` file
3. Converts to `.wav` using FFmpeg
4. Transcribes using Google Speech API
5. Executes as an AI prompt

### Installing FFmpeg

**Windows:**
```batch
# Using Chocolatey
choco install ffmpeg

# Or download from https://ffmpeg.org/download.html
```

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt install ffmpeg
```

---

## 🖥️ The "Locked Screen" Solution

TeleCode solves the "locked laptop" problem using the **Cursor CLI** instead of GUI automation.

### Why This Works
- **GUI Automation (PyAutoGUI)**: Requires an active, unlocked screen
- **CLI/Subprocess**: Works in any terminal, locked or unlocked

### The CLI Approach
```
User sends: "/ai Refactor login.py to use JWT"
             ↓
Bot executes: cursor --folder /path/to/project --command "Refactor login.py to use JWT"
             ↓
Cursor CLI modifies files on disk
             ↓
Bot runs: git diff --stat
             ↓
User sees: "3 files changed, +50 insertions"
```

### GUI Automation Mode (Advanced)

For full Cursor Composer control (clickable AI buttons, visual feedback), TeleCode offers platform-specific headless modes:

| Platform | Headless Method | How It Works |
|----------|-----------------|--------------|
| 🪟 **Windows** | **TSCON** | Disconnects display while session stays active. GUI automation works perfectly. See [docs/TSCON.md](docs/TSCON.md) |
| 🐧 **Linux** | **Xvfb** | Virtual X framebuffer. Creates invisible display for GUI automation. Toggle from system tray. |
| 🍎 **macOS** | **Virtual Display** | Requires external setup (BetterDummy, VNC, or hardware adapter). `caffeinate` prevents sleep automatically. |

<details>
<summary><b>🪟 Windows TSCON (Recommended for Windows)</b></summary>

TSCON keeps your Windows session fully active while the display is disconnected:

```batch
# Quick Lock (from TeleCode tray icon)
Right-click TeleCode tray → Quick Lock

# Or run the batch file as Administrator
tscon_secure_lock.bat
```

See [docs/TSCON.md](docs/TSCON.md) for full details.

</details>

<details>
<summary><b>🐧 Linux Xvfb Setup</b></summary>

```bash
# Install Xvfb
sudo apt install xvfb

# Install Python wrapper
pip install pyvirtualdisplay

# Optional: Install xdotool for window management
sudo apt install xdotool
```

Toggle virtual display from the TeleCode system tray icon.

</details>

<details>
<summary><b>🍎 macOS Notes</b></summary>

macOS restricts accessibility APIs when the screen is locked. Options:
- **caffeinate** - TeleCode runs this automatically to prevent sleep
- **Virtual display adapter** - BetterDummy, Deskreen, or hardware HDMI adapter
- **VNC** - Screen sharing to a virtual display

</details>

---

## 📦 Distribution

### Pre-Built Installers

Download the installer **for your platform** from [GitHub Releases](https://github.com/flexfinRTP/telecode/releases/latest):

| Platform | File | Notes |
|----------|------|-------|
| 🪟 **Windows** | `TeleCode_Setup_v*.exe` | Full installer with TSCON shortcuts, system tray icon |
| 🍎 **macOS** | `TeleCode_v*_macOS.dmg` | Drag-and-drop .app bundle, caffeinate auto-enabled |
| 🐧 **Linux** | `TeleCode_v*_Linux.tar.gz` | Standalone executable, Xvfb headless mode support |

> **Each platform has its own installer** — download the one that matches your computer.

### Building From Source

```bash
cd build

# Windows
build_windows.bat

# macOS
./build_macos.sh

# Linux
./build_linux.sh
```

See [build/README.md](build/README.md) for detailed build instructions.

### Verifying Downloads

Always verify downloaded executables using SHA256 checksums:

```bash
# Windows (PowerShell)
Get-FileHash TeleCode.exe -Algorithm SHA256

# Mac/Linux
sha256sum TeleCode
```

---

## 🗺️ Roadmap

- [x] ~~OCR: Screenshot Cursor output and extract text~~ ✅ Done in v0.1.11
- [x] ~~Custom domain: telecodebot.com~~ ✅ Done in v0.1.12
- [ ] Multi-Repo: Switch between sandbox roots
- [ ] Scheduled Tasks: Queue prompts for later execution
- [ ] GitHub Actions: Trigger remote workflows
- [ ] Web Dashboard: Real-time status monitoring

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API wrapper
- [Cursor](https://cursor.com) - The AI-first code editor
- [SpeechRecognition](https://github.com/Uberi/speech_recognition) - Voice transcription

---

## 💬 Support

- **Issues**: [GitHub Issues](https://github.com/flexfinRTP/telecode/issues)
- **Discussions**: [GitHub Discussions](https://github.com/flexfinRTP/telecode/discussions)

---

**Made with ❤️ for developers who code from anywhere.**

*Voice-to-code • Uses your existing Cursor plan • Zero API costs*

🌐 **[telecodebot.com](https://telecodebot.com)**

