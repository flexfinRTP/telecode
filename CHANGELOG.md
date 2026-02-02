# Changelog

All notable changes to TeleCode will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Contributing**: For contributions, we increment `v0.1.x` (patch versions) for bug fixes 
> and minor improvements. Feature additions will increment to `v0.2.0`, etc.

---

## [0.1.8] - 2026-02-01

### 🔔 Cleaner Button Layout - Separate Approval Message

Simplified the main AI control buttons and moved Run/Continue to a separate follow-up message that only shows when relevant (when Cursor is waiting for approval).

### Changed

#### Button Layout Streamlined
- **Removed** from main keyboard:
  - 🌐 Search (redundant)
  - 🚫 Cancel (redundant)
  - ▶️ Run (moved to separate message)
  - ➡️ Continue (moved to separate message)

#### New Separate Approval Message
When a prompt is sent, a follow-up message now appears with:
- **▶️ Run** - Approve when Cursor asks to run a script
- **➡️ Continue** - Keep the AI going if it paused

This makes it clearer that Run/Continue are only for approval scenarios.

#### Updated Main Button Layout
```
[📊 Check] [📖 Diff] [✅ Keep]
[❌ Undo] [⚙️ Mode] [🧹 Cleanup]
```

#### Separate Approval Message
```
🔔 Waiting for Approval?

If Cursor is asking to run a script or needs approval:
• Run - Approve terminal command execution
• Continue - Keep the AI going if it paused

[▶️ Run] [➡️ Continue]
```

---

## [0.1.8] - 2026-02-01

### 📸 Smart AI Status + Screenshot on Completion

TeleCode now monitors Cursor AI in real-time and sends a screenshot when it's done!

### Added

#### Real-Time AI Status Polling
- **Live status updates** in Telegram as Cursor AI processes
- **Polls git status** every 2 seconds to detect file changes
- **Smart completion detection** - considers AI "done" after 3 stable polls
- Shows file count and elapsed time during processing

#### Screenshot on Completion
- **Captures screenshot** of Cursor when AI finishes
- **Sends photo to Telegram** with the completion message
- Shows current state of Cursor so you can see what happened
- Screenshots saved to `.telecode/screenshots/`

#### Improved Button Layout
All controls now in one unified button grid (no separate "Waiting for Approval" message):
```
Row 1: [📊 Check] [📖 Diff] [✅ Accept]
Row 2: [❌ Reject] [▶️ Run] [➡️ Continue]
Row 3: [⚙️ Mode] [🧹 Cleanup]
```

### Changed

#### New `CursorAgentBridge` Methods
```python
agent.capture_screenshot()       # Take screenshot of Cursor
await agent.send_prompt_and_wait(  # Send prompt + poll for completion
    prompt="...",
    status_callback=async_fn,
    timeout=90.0,
    poll_interval=2.0,
    stable_threshold=3
)
```

#### AI Processing Flow
1. User sends `/ai [prompt]`
2. Bot shows "📤 Sending to Cursor..."
3. Bot shows "🤖 Cursor AI is processing..."
4. Bot polls for file changes with live updates
5. When done: "✅ Cursor AI Completed!" + screenshot + all buttons

### Technical Details
- Uses `pyautogui.screenshot()` for screen capture
- Polls `git status --porcelain` to detect changes
- "Stable" = no new file changes for 3 consecutive polls
- 90 second timeout (configurable)
- Gracefully handles timeouts and errors

---

## [0.1.7] - 2026-02-01

### 🔄 Fixed Cursor Accept/Reject + Git Commit Rename

Fixed AI accept/reject to use correct Cursor keyboard shortcuts and renamed `/accept` to `/commit`.

### Fixed

#### Cursor Keyboard Shortcuts Now Working!
- **Accept** now uses **Ctrl+Enter** (was incorrectly using Ctrl+Shift+Enter)
- **Reject** now uses **Ctrl+Backspace** for Agent mode (was incorrectly using Ctrl+Z)
- **Reject** uses **Escape** for Chat mode (unchanged)

### Changed

#### Command Renames
- **`/accept`** → **`/commit`** - Now clearly indicates this is a git action
- Git operations are now separate from Cursor operations

#### Button Labels
- **✅ Accept** - Accept AI changes in Cursor (Ctrl+Enter)
- **❌ Reject** - Reject AI changes in Cursor (Ctrl+Backspace)

#### New Commands
- `/ai accept` - Accept AI changes via Ctrl+Enter
- `/ai reject` - Reject AI changes via Ctrl+Backspace

### Migration
| Old Command | New Command | Action |
|-------------|-------------|--------|
| `/accept` | `/commit` | Git commit |
| `/ai accept` | `/ai accept` | Accept in Cursor (Ctrl+Enter) |
| `/ai revert` | `/ai reject` | Reject in Cursor (Ctrl+Backspace) |

---

## [0.1.6] - 2026-02-01

### ▶️ AI Action Approval - Run, Search & Continue Buttons

When Cursor's AI wants to run a terminal command or search the web, you now get a confirmation prompt in Telegram before it executes. Plus, a new "Continue" button keeps the AI working!

### Added

#### New AI Control Buttons
- **▶️ Run** - Approve when AI wants to run a terminal command
  - Shows confirmation dialog: "Yes, Run It" or "Cancel"
  - Sends approval to Cursor via keyboard automation
- **🌐 Search** - Approve when AI wants to do a web search
  - Shows confirmation dialog: "Yes, Search" or "Cancel"
  - Lets AI search for context without automatic execution
- **🚫 Cancel** - Cancel any pending AI action
  - Presses Escape in Cursor to cancel the pending action
- **➡️ Continue** - Send "continue" to keep AI working
  - Useful when AI pauses or needs a nudge to continue
  - Types "continue" and presses Enter in Cursor

#### New `CursorAgentBridge` Methods
```python
agent.approve_run()        # Approve terminal command (Enter key)
agent.cancel_action()      # Cancel pending action (Escape key)
agent.approve_web_search() # Approve web search (Enter key)
agent.send_continue()      # Send "continue" to AI (text + Enter)
```

### Changed

#### Button Layout Updated
- Compact button layout with 3 buttons per row
- Renamed buttons for clarity:
  - "📊 Check Changes" → "📊 Check"
  - "📖 View Diff" → "📖 Diff"
  - "🧹 Cleanup Agents" → "🧹 Cleanup"
- New buttons row: [▶️ Run] [🌐 Search] [🚫 Cancel]
- Continue button moved to new row with Reject

### UI Flow Example

```
User: /ai Create a script that runs npm install

Bot: ✅ Prompt Sent to Cursor!
     [📊 Check] [📖 Diff] [✅ Accept]
     [▶️ Run] [🌐 Search] [🚫 Cancel]
     [➡️ Continue] [❌ Reject]
     [⚙️ Mode] [🧹 Cleanup]

[AI wants to run: npm install]

User: [clicks ▶️ Run]

Bot: ⚠️ Cursor wants to run a command
     The AI is requesting to execute a terminal command.
     [✅ Yes, Run It] [🚫 Cancel]

User: [clicks Yes, Run It]

Bot: ✅ Command Approved!
     The AI will now execute the command.
```

### Documentation
- Updated `docs/COMMANDS.md` with new buttons and approval flow
- Updated `USER_GUIDE.md` with new buttons table and examples

---

## [0.1.5] - 2026-02-01

### 💻 Smart Cursor Detection + AI Thinking Status + Tray Fix

TeleCode now intelligently detects if Cursor is open for your selected workspace and offers to launch it if needed, with live status updates in Telegram. Plus, AI prompts now show clever "thinking" messages while processing!

### Fixed

#### System Tray Icon Now Works! 🔧
- **Fixed missing tray callbacks** - `_on_tray_settings`, `_on_tray_quick_lock`, `_on_tray_secure_lock` were referenced but not defined
- Added proper UAC elevation for Quick Lock and Secure Lock from tray icon
- Settings button now opens the config GUI
- Tray icon should now appear and stay visible while bot is running

#### Token Loading from Vault Fixed 🔒
- **Fixed token not loading properly** when stored in secure vault
- Config GUI now retrieves token from vault when `.env` contains `[STORED_IN_SECURE_VAULT]`
- Shows proper status message when token is loaded from vault
- Shows warning if vault token can't be retrieved

#### Single Instance Lock 🔐
- **Only one TeleCode instance can run at a time** - prevents duplicate bots
- Uses file-based locking (`~/.telecode.lock`) for cross-platform compatibility
- Shows helpful message if another instance is already running
- Displays PID of running instance and how to stop it
- Lock is properly released on exit (normal, crash, or Ctrl+C)

### Added

#### New `/cursor` Command
- **`/cursor`** - Check Cursor IDE status and show open button if not running
- **`/cursor open`** - Launch Cursor for current workspace with live status
- **`/cursor status`** - Just check status without opening

#### Smart Cursor Detection on `/cd`
- When changing directories with `/cd`, TeleCode now checks if Cursor is open
- Shows Cursor status: 🟢 Ready, 🟠 Different workspace, 🟡 Starting, 🔴 Not running
- **"🚀 Open in Cursor"** button appears if workspace isn't open in Cursor

#### Live Pending Status in Telegram
- Real-time status updates while Cursor is launching
- Animated progress messages: "⏳ Launching... (5s)..."
- Success message with action buttons when Cursor is ready
- Timeout handling with retry option if Cursor doesn't open in 30s

#### Enhanced Project Creation
- After `/create` completes, automatically opens Cursor with pending status
- Shows live progress while Cursor launches for new project
- Ready message with "🤖 Send AI Prompt" button when Cursor is ready

#### AI Thinking/Working Status 🧠
- When sending `/ai` prompts, shows clever "thinking" messages:
  - "🧠 Thinking..."
  - "🔮 Consulting the code oracle..."
  - "✨ Crafting the perfect response..."
  - "🎨 Preparing to create..."
  - And more random phrases!
- Automatically detects if Cursor isn't open and shows opening progress
- Updates to "working" status while sending to Cursor:
  - "⏳ Working on it..."
  - "💫 Magic happening..."
  - "🛠️ Building your code..."
- Single message updates (no spam) - edits the same message throughout
- Final success/error message replaces the status message

### Technical Details

#### New `CursorStatus` Enum
```python
class CursorStatus(Enum):
    NOT_RUNNING = "not_running"
    STARTING = "starting"
    RUNNING = "running"      # Open but different workspace
    READY = "ready"          # Open with correct workspace
    ERROR = "error"
```

#### New Methods in `CursorAgentBridge`
- `check_cursor_status()` - Returns dict with detailed Cursor status
- `open_cursor_and_wait(status_callback, timeout, poll_interval)` - Async method that waits for Cursor to open with progress callbacks

#### Window Detection Enhancement
- `WindowManager.find_cursor_window()` now accepts optional `workspace_name` parameter
- Can detect if specific workspace is open vs any Cursor window

### UI Flow Example

```
User: /cd myproject
Bot: ✅ Changed to myproject
     💻 Cursor: 🔴 Not Running
     [🚀 Open in Cursor]

User: [clicks button]
Bot: 💻 Opening Cursor
     📂 Workspace: myproject
     ⏳ Launching... (3s)...

Bot: 💻 Cursor Status
     ✅ Cursor ready with myproject
     [🤖 Send AI Prompt] [📊 Check Status]
```

---

## [0.1.4] - 2026-02-01

### 🔒 System Tray Lock Improvements - UAC Elevation & Simplified Setup

Streamlined TSCON lock functionality with automatic UAC elevation prompts and removal of redundant desktop shortcut creation.

### Changed

#### System Tray Lock Now Works!
- **Fixed: Quick Lock & Secure Lock tray options** - Were not connected to handlers, now fully functional
- **UAC Elevation Prompt** - Lock options now automatically request administrator privileges via Windows UAC
- **No more manual shortcuts needed** - Removed "Create Desktop Shortcuts" button from Setup GUI
- Tray icon right-click menu is now the primary way to lock screen

#### Setup GUI Cleanup
- Removed redundant "Create Lock Shortcuts" button (shortcuts no longer needed)
- Added helpful tip pointing users to the system tray icon
- Lock buttons in Setup GUI now also request UAC elevation automatically

### Fixed
- **System tray lock callbacks** were not connected in `bot.py` - now properly wired up
- **Settings button** now opens the config GUI from tray icon
- All tray menu options now functional: Settings, Quick Lock, Secure Lock, Stop

### Technical Details
- Uses `ShellExecuteW` with `runas` verb for UAC elevation
- Falls back to running tscon_helper.py directly if BAT files not found
- Lock operations run in separate elevated process for security

---

## [0.1.3] - 2026-02-01

### 🎯 Enhanced Cursor Integration - Clear AI vs Git Separation

Major improvements to Cursor integration with better change tracking and automation.

### Added

#### Keep All via Cursor Automation
- **Keep All button** now uses Cursor's native "Keep All" shortcut (Ctrl+Shift+Enter)
- No longer does git commit - uses Cursor's UI automation instead
- More reliable acceptance of AI-generated changes

#### Check Changes - Latest Prompt Only
- **📊 Check Changes** now shows only files changed since the latest prompt
- Tracks file state snapshot before each prompt
- Shows concise diff summary with new/modified file counts
- Filters out pre-existing changes for clarity

#### View Diff - Latest Prompt
- **📖 View Diff** shows diff for files from latest prompt only
- Includes info about new untracked files
- Fixed encoding issues (UTF-8 with error handling)

#### Agent Cleanup
- **🧹 Cleanup Agents** button to close old agent tabs
- Closes oldest agents when count exceeds 5
- Tracks agent count across sessions

#### Improved Composer Handling
- Closes existing panels before opening new composer
- Handles case where composer is already open
- Option to use Agent mode (Ctrl+Shift+I) instead of Chat (Ctrl+L)

### Fixed
- **UnicodeDecodeError** on Windows with git diff (cp1252 encoding issue)
- **"Working directory is clean"** error when files were actually created
- Git commands now use `git add -A` to include new untracked files
- Improved subprocess encoding: `encoding='utf-8', errors='replace'`

### Changed
- **Clear AI vs Git separation** - AI buttons ONLY control Cursor, git is separate
- Renamed buttons for clarity:
  - "Keep All" → "✅ Accept" (Cursor automation)
  - "Undo All" → "❌ Reject" (Cursor automation)
- `/diff` buttons renamed:
  - "Keep All" → "💾 Git Commit"
  - "Undo All" → "🗑️ Git Restore"
- Accept button now ONLY uses Cursor automation (no git)
- Reject button now ONLY uses Cursor automation (Escape/Ctrl+Z)
- Git operations are clearly separate commands

### Clear Separation: Cursor vs Git
| Operation | Cursor (AI buttons) | Git (commands) |
|-----------|---------------------|----------------|
| Apply | ✅ Accept | `/commit` |
| Discard | ❌ Reject | `/revert CONFIRM` |
| View | 📊 Check, 📖 Diff | `/status`, `/diff` |

### Prompt Mode Selection
Added user-selectable prompt modes:

| Mode | Shortcut | Behavior |
|------|----------|----------|
| 🤖 Agent | Ctrl+Shift+I | Auto-saves files (SAFEST - won't lose work) |
| 💬 Chat | Ctrl+L | Changes need Keep All button to apply |

**Default: Agent mode** - Files are auto-saved to disk, so you won't lose work even if you forget to click Keep All.

Commands:
- `/ai mode` - Show mode selection menu
- `/ai mode agent` - Switch to Agent mode
- `/ai mode chat` - Switch to Chat mode
- ⚙️ Mode button after prompts

### AI Revert for Both Modes
- **Agent mode**: Uses git restore (files are already saved)
- **Chat mode**: Uses Escape to reject proposed changes

### Button Layout
After sending a prompt (Cursor controls only):
```
[📊 Check Changes] [📖 View Diff]
[✅ Accept] [❌ Reject]
[▶️ Continue] [⚙️ Mode]
[🧹 Cleanup Agents]
```

After /diff (Git controls):
```
[📖 View Full Diff]
[💾 Git Commit] [🗑️ Git Restore]
```

### Updated Documentation
- Updated COMMANDS.md with clear AI vs Git separation
- Updated USER_GUIDE.md with Cursor vs Git table
- All docs now clearly distinguish Cursor buttons from git commands

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
| `/ai accept` | Accept AI changes in Cursor (Ctrl+Enter) |
| `/ai reject` | Reject AI changes in Cursor (Ctrl+Backspace) |
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
5. You: /ai accept → Accept changes (or /commit for git)
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
| `/commit` | Commit changes |
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

