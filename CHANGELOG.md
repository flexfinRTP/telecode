# Changelog

All notable changes to TeleCode will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Contributing**: For contributions, we increment `v0.1.x` (patch versions) for bug fixes 
> and minor improvements. Feature additions will increment to `v0.2.0`, etc.

---

## [0.1.2] - 2026-02-01

### 🤖 AI Control Commands - Full Automated Cursor Integration

Complete rewrite of Cursor integration with **automated keyboard control**.
Prompts are now SENT DIRECTLY to Cursor Composer - no manual paste needed!

### Added

#### Automated Prompt Delivery
- **Direct Composer Integration**: Prompts sent via keyboard automation
- **Zero Manual Steps**: TeleCode opens Cursor → focuses window → types prompt → sends
- **Works When Locked**: Compatible with TSCON locked sessions on Windows

#### AI Subcommands
| Command | Description |
|---------|-------------|
| `/ai <prompt>` | **Sends prompt directly to Cursor Composer** |
| `/ai accept [msg]` | Accept and commit all AI changes |
| `/ai revert` | Discard all AI changes (with confirmation) |
| `/ai continue <prompt>` | Send follow-up prompt |
| `/ai stop` | Clear current AI session |
| `/ai status` | Check agent state and pending changes |

#### Cursor Agent Bridge (`src/cursor_agent.py`)
- **Keyboard automation** via pyautogui + pyperclip
- **Window management** to find and focus Cursor
- Session state persistence
- Prompt history logging
- Git-based change tracking

#### New Dependencies
```
pyautogui>=0.9.54   # Keyboard automation
pyperclip>=1.8.2    # Clipboard handling
```

#### Inline Button Actions
- **Check Changes** - Quickly see pending modifications
- **Accept All** - One-click commit
- **Revert All** - Discard with 2-step confirmation
- **Continue** - Prompt for follow-up

### Fixed
- **Cursor CLI**: No longer uses non-existent `cursor agent` command
- **Manual workflow eliminated**: No need to copy/paste prompts
- **TSCON compatibility**: Works with locked Windows sessions

### How It Works Now
```
1. You send: /ai create a login form
   ↓
2. TeleCode:
   - Opens Cursor (if not running)
   - Focuses Cursor window
   - Opens Composer (Ctrl+L)
   - Pastes your prompt
   - Presses Enter to send
   ↓
3. Cursor AI processes the prompt
   ↓
4. You: /ai status → See changes
5. You: /ai accept → Commit
6. You: /push → Push to remote
```

### Security
- All prompts scanned by PromptGuard before sending
- Workspace must be in DEV_ROOT sandbox
- Full audit logging to `.telecode/history.json`
- Clipboard cleared after use (optional)

---

## [0.1.1] - 2026-02-01

### 🔧 Cursor CLI Compatibility Fix + Professional Installers

Fixed Cursor CLI integration and added cross-platform installers.

### Added
- **System Tray Icon**: TeleCode now shows in your system tray (near clock)
  - Green icon when running
  - Right-click menu: Status, Settings, Quick Lock, Secure Lock, Stop
  - Shows last command and command count
  - Updates in real-time as you send Telegram commands
- **Startup Confirmation**: Modal popup when bot starts, pointing to system tray
- **Professional Installers**: One-click installers for all platforms
  - Windows: Inno Setup installer (`TeleCode_Setup_v0.1.1_Windows.exe`)
  - macOS: DMG with drag-and-drop app bundle (`TeleCode_v0.1.1_macOS.dmg`)
  - Linux: tar.gz with install script (`TeleCode_v0.1.1_Linux.tar.gz`)
- **GitHub Actions**: Automated CI/CD builds on every release tag
- **Build System**: Complete PyInstaller specs and build scripts for all platforms
- **Eye button**: Token visibility toggle in setup GUI
- **TSCON UI improvements**: Separate Quick Lock and Secure Lock buttons with info dialogs
- **Options info buttons**: Info icons next to Voice, Sleep, and Audit options

### Fixed
- **Cursor CLI syntax**: Updated `cli_wrapper.py` to use correct Cursor v2.2+ CLI
  - Old (broken): `cursor --folder <path> --command <prompt>` (flags don't exist)
  - New (working): `cursor agent` with stdin piping for prompts
  - Fallback: Opens Cursor GUI with workspace + saves prompt to `.telecode_prompt.md`
- **Setup GUI banner**: Made ASCII art banner smaller to fit properly in the setup window
- **Setup GUI blurry text**: Added Windows DPI awareness for crisp text rendering at high DPI
- **Setup GUI buttons cut off**: Fixed button bar to always be visible at bottom, added scrollable content area
- **Setup GUI resizable**: Window is now resizable and draggable (850x1150 default)

### Technical Details
- `cursor agent` mode reads prompts from stdin for headless operation
- If agent returns empty, falls back to GUI mode with prompt file
- Prompt file allows user to copy/paste into Cursor Composer (Ctrl+I)
- Works with screen locked via TSCON method
- Build artifacts uploaded to GitHub Releases automatically

### Notes
- All existing functionality preserved
- Users don't need to do anything - the fix is automatic
- Download installers from GitHub Releases page

---

## [0.1.0] - 2026-02-01

### 🚀 Initial Public Release

First open source release of TeleCode - Remote Cursor Commander via Telegram.

### Features

#### 🎤 Voice-to-Code
- Speak coding prompts via Telegram voice messages
- Free Google Speech Recognition (no API key required)
- Automatic transcription and execution via Cursor AI

#### 🤖 AI Model Selection
- **`/model`** - Interactive model selection with inline keyboard buttons
- **`/model <alias>`** - Quick switch (e.g., `/model opus`, `/model haiku`)
- **`/models`** - List all available models with descriptions
- Per-user preferences stored in `.telecode/user_prefs.json`
- Default model: `opus` (Claude Opus 4.5)

#### 📋 Available Models
| Alias | Model | Tier | Context |
|-------|-------|------|---------|
| `opus` | Claude Opus 4.5 | 💎 Paid | 200K |
| `sonnet` | Claude Sonnet 4.5 | 💰 Paid | 1M |
| `haiku` | Claude Haiku 4.5 | ✨ Free | 200K |
| `gemini` | Gemini 3 Flash | ✨ Free | 1M |
| `gpt` | GPT-4.1 | 💰 Paid | 128K |

#### 📊 Expandable Diff Preview with Cursor-Style Actions
- **Preview mode**: Shows `git diff --stat` summary after AI execution
- **"View Full Diff" button**: Expands to show complete diff inline
- **Cursor-compatible action buttons**:
  - ✅ **Keep All** - Stage and commit all changes
  - 🗑️ **Undo All** - Discard all changes with 2-step confirmation
  - ▶️ **Continue** - Prompt for follow-up AI command
- Two-step confirmation for "Undo All" to prevent accidents

#### 🛡️ Security
- **Token Encryption**: Bot token stored in encrypted vault (DPAPI/Keychain)
- **Prompt Injection Defense**: Pattern detection + LLM boundary markers
- **Rate Limiting**: 30 requests/minute, 500/day per user
- **Sandbox**: File operations restricted to configured DEV_ROOT
- **Audit Logging**: All commands logged with timestamps

#### 🔒 TSCON Lock-Proof Operation (Windows)
- Works with laptop screen locked
- Secure mode: Disables RDP + 30-minute auto-lock
- Desktop shortcuts for quick locking

#### 🖥️ Setup GUI
- Beautiful 800x600 Windows XP-style interface
- AI model selection dropdown during setup
- Dangerous folder detection and blocking
- Token validation and secure storage

### Commands
| Command | Description |
|---------|-------------|
| `/start` | Welcome message with current model |
| `/help` | List all available commands |
| `/status` | Git status of current project |
| `/diff` | Show diff with action buttons |
| `/commit <msg>` | Commit changes |
| `/push`, `/pull` | Git push/pull |
| `/model` | Select AI model |
| `/models` | List available models |
| `/cd <path>` | Change project directory |
| `/lock` | TSCON lock (Windows) |

### Technical
- Python 3.10+ required
- `python-telegram-bot` async framework
- Cursor CLI integration for AI prompts
- Cross-platform: Windows, macOS, Linux

---

## [Unreleased]

### Planned
- Multi-workspace support
- Custom model configurations
- Webhook mode for production deployments

---

## Development History

*The following entries document the internal development history prior to public release.*

---

## [Internal 4.2.0] - 2026-02-01

### 🔒 Security Audit Release - "Fort Knox Edition"

Comprehensive security audit and hardening of the entire codebase based on OWASP AI Agent Security Guidelines.

### Security Fixes

| ID | Severity | Issue | Resolution |
|----|----------|-------|------------|
| SEC-001 | 🔴 Critical | Environment variable exposure | Filtered env vars in subprocess |
| SEC-002 | 🔴 Critical | Insufficient prompt sanitization | Multi-layer PromptGuard system |
| SEC-003 | 🟠 High | Information leakage in logs | Redacted sensitive data in logs |
| SEC-004 | 🟠 High | No rate limiting | Added rate limiting (auth + commands) |
| SEC-005 | 🟡 Medium | Insecure temp file handling | Secure file deletion with overwrite |
| SEC-006 | 🟡 Medium | Token stored in plaintext | Encrypted vault with DPAPI/Keychain |

### New Security Modules

#### 🔐 Token Vault (`src/token_vault.py`)
- **Encrypted storage**: DPAPI on Windows, Keychain on macOS, encrypted file fallback
- **Memory obfuscation**: Tokens XOR'd in memory to prevent scanning
- **Machine-specific keys**: Token can only be decrypted on the same machine
- **Access logging**: Every token access is logged

#### 🛡️ Prompt Guard (`src/prompt_guard.py`)
Multi-layer defense against prompt injection attacks:
- **Layer 1**: Token extraction detection (blocks "show me the token")
- **Layer 2**: System prompt leakage (blocks "ignore previous instructions")
- **Layer 3**: Jailbreak patterns (blocks "pretend you are...")
- **Layer 4**: Command injection (blocks shell commands in prompts)
- **Layer 5**: Data exfiltration (blocks reading .env, SSH keys, etc.)

### Added
- **Rate Limiting System**: Prevents brute-force and DoS attacks
  - Auth failures: 5 attempts per minute, 5-minute lockout
  - Commands: 30 per minute per user
- **Sensitive Data Filter**: Automatically redacts tokens from logs
- **Safe Environment Handling**: Only whitelisted env vars passed to subprocess
- **Output Sanitization**: Removes usernames, paths, tokens from all outputs
- **Dangerous Operation Confirmation**: `/revert` now requires `CONFIRM` argument
- **File Access Blocking**: Prevents reading sensitive files (.env, .ssh, etc.)

### Documentation
- New `docs/SECURITY_AUDIT.md` with full audit report
- Penetration test results for common attack vectors
- Security recommendations for users

---

## [4.1.0] - 2026-02-01

### Added
- **Project Creation via Telegram**: New `/create` command with interactive CLI prompts
  - Secure conversation flow: prompts for name → confirmation → creation
  - Creates project directory within sandbox (DEV_ROOT)
  - Automatically initializes git repository (`git init`)
  - Opens Cursor IDE with the new project
  - Name sanitization prevents path traversal and injection attacks
  - Inline keyboard buttons for confirm/cancel
  - Audit logging of all project creation attempts
  - Blocked characters: `/`, `\`, `..`, spaces, special chars
  - Allowed characters: `a-z`, `A-Z`, `0-9`, `-`, `_`, `.`

### Security
- Added `mkdir` and `md` (Windows) to allowed binaries whitelist
- Project names are strictly sanitized before directory creation
- All projects created within DEV_ROOT sandbox only
- Conversation state prevents injection via mid-flow attacks

### Technical
- New `CLIWrapper` methods:
  - `git_init()` - Initialize git repository
  - `create_directory()` - Safe directory creation with sanitization
  - `open_cursor()` - Open directory in Cursor IDE
  - `scaffold_project()` - Combined create + init + open
  - `_sanitize_project_name()` - Security sanitizer for names
- Uses Telegram's `ConversationHandler` for multi-step prompts
- Inline keyboard buttons for user confirmation

---

## [4.0.2] - 2026-02-01

### Security
- **Strict Sandbox Folder Warnings**: Enhanced GUI with explicit security warnings
  - Yellow warning box explaining folder access implications
  - Clear "GOOD" and "BAD" folder examples
  - Confirmation dialog when selecting a folder
  - Automatic blocking of dangerous folders:
    - Root drives (C:\, /)
    - Home folder (entire user directory)
    - System folders (Windows, System32, Program Files)
    - Sensitive directories (.ssh, .aws, .gnupg)
    - Common user folders (Desktop, Documents, Downloads)
    - Cloud sync roots (OneDrive, Dropbox, Google Drive)
  - Detailed error messages explaining why a folder is blocked

### Added
- **TSCON Quick Lock Tool**: Integrated TSCON helper for Windows users
  - New "🔒 TSCON Quick Lock" section in setup GUI
  - **Secure Mode** checkbox (recommended) with:
    - Automatic Remote Desktop disable
    - 30-minute auto-lock watchdog
    - Physical-access-only reconnection
    - Full audit logging
  - One-click "Create Shortcuts" button (creates both modes)
  - "Lock Now" button with mode selection
  - Help dialog explaining security modes
  - Ready-to-use batch files:
    - `tscon_secure_lock.bat` - Hardened mode (disables RDP)
    - `tscon_lock_verbose.bat` - Standard with explanations
    - `tscon_lock.bat` - Quick standard lock
    - `tscon_restore.bat` - Restore RDP after secure lock
  - Python module: `src/tscon_helper.py` with CLI interface
  - Comprehensive documentation in `docs/TSCON.md`

---

## [4.0.1] - 2026-02-01

### Added
- **GitHub Pages Landing Page**: Beautiful installation page with one-click download
  - Modern terminal/hacker aesthetic design
  - "Open Source - Verify the code" section with GitHub link
  - SHA-256 checksums for `main.py` and `requirements.txt` with plain English explanation
  - Responsive design for mobile devices

---

## [4.0.0] - 2026-02-01

### 🎉 The "Headless" Edition

This is a complete rewrite focused on **lock-proof operation**. TeleCode now works even when your laptop screen is locked, using CLI-based execution instead of GUI automation.

### Added

- **Cursor CLI Integration**: Execute AI prompts via `cursor` command line
- **Zero-Trust Security**: Multi-layered security architecture
  - User ID authentication
  - Filesystem sandboxing
  - Command whitelisting
  - Shell injection prevention
  - Audit logging
- **Voice Transcription**: Send voice notes that get transcribed and executed
- **Windows XP Style GUI**: Nostalgic setup interface for easy configuration
- **Cross-Platform Support**: Works on Windows, macOS, and Linux
- **Sleep Prevention**: Keep laptop awake while bot is running

### Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | List commands |
| `/status` | Git status |
| `/diff` | Show changes |
| `/push` | Push to remote |
| `/pull` | Pull from remote |
| `/accept` | Commit changes |
| `/revert` | Discard changes |
| `/ai` | Execute AI prompt |
| `/cd` | Change directory |
| `/ls` | List files |
| `/read` | Read file contents |
| `/log` | Recent commits |
| `/branch` | List branches |
| `/info` | System info |

### Security Features

- Hard-coded Telegram User ID authentication
- Path traversal prevention with `os.path.commonpath()`
- Blocked access to sensitive files (`.env`, SSH keys, etc.)
- Shell injection pattern detection and blocking
- Full audit logging of all commands
- No open ports (outbound-only long polling)

### Technical Stack

- Python 3.10+
- python-telegram-bot 22.0
- SpeechRecognition (Google API)
- pydub + FFmpeg
- tkinter (GUI)

---

## [3.0.0] - 2026-01-15 (Unreleased)

### The "Omni-Lock" Edition (Concept)

- Lock detection with mode switching
- Queue system for locked screen prompts
- Keep-alive service

*Note: This version was conceptual and led to v4.0's CLI-first approach.*

---

## [2.0.0] - 2026-01-01 (Unreleased)

### The "XP Edition" (Concept)

- Windows XP styling
- Git-first workflow
- Voice-to-code pipeline

*Note: This version was conceptual and merged into v4.0.*

---

## [1.0.0] - 2025-12-15 (Unreleased)

### Initial Concept

- Basic Telegram bot
- PyAutoGUI-based GUI automation
- Simple git commands

*Note: This approach was abandoned due to locked screen limitations.*

---

## Roadmap

### [0.2.0] - Planned

- [ ] OCR: Screenshot Cursor output and extract text
- [ ] Multi-Repo: Switch between sandbox roots via commands

### [0.3.0] - Planned

- [ ] Scheduled Tasks: Queue prompts for later execution
- [ ] GitHub Actions: Trigger remote workflows
- [ ] Webhook mode (alternative to long polling)

### [1.0.0] - Future

- [ ] Web Dashboard: Real-time status monitoring
- [ ] Multiple user support (team mode)
- [ ] Plugin system for custom commands

---

## Contributing

For version increments:
- **Bug fixes / minor improvements**: Increment patch version (v0.1.x → v0.1.1, v0.1.2, etc.)
- **New features**: Increment minor version (v0.1.x → v0.2.0)
4. Configure via GUI

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute to TeleCode.

---

## Support

- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Security**: See [SECURITY.md](docs/SECURITY.md)

