# 📱 TeleCode User Guide

<div align="center">
  <img src="assets/telecode.png" alt="TeleCode Logo" width="150">
</div>

Welcome to TeleCode! This guide will help you get started with **voice-to-code from anywhere**.

> 🎤 **Speak your prompts** • 💰 **Uses your Cursor plan** (no API costs) • 🌍 **Code from anywhere**

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Basic Commands](#basic-commands)
3. [Creating New Projects](#creating-new-projects)
4. [Git Workflow](#git-workflow)
5. [AI Coding](#ai-coding)
6. [Model Selection](#-model-selection)
7. [Voice Commands](#voice-commands)
8. [Navigation](#navigation)
9. [Headless Mode (Locked Screen)](#-headless-mode-locked-screen) ← **NEW!**
10. [Tips & Tricks](#tips--tricks)
11. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Step 1: Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g., "My TeleCode Bot")
4. Choose a username (must end in `bot`, e.g., `mytelecodeprivate_bot`)
5. **Save the token** - you'll need it for setup

### Step 2: Get Your User ID

1. Search for **@userinfobot** on Telegram
2. Send `/start`
3. **Save your User ID** (a number like `123456789`)

### Step 3: Configure TeleCode

#### Windows
```batch
# Run the setup script
setup.bat
```

#### Mac/Linux
```bash
# Make executable and run
chmod +x setup.sh
./setup.sh
```

The GUI will open. Enter:
- Your **Bot Token** from Step 1
- Your **User ID** from Step 2
- Your **Development Folder** (where your code lives)

Click **"Save & Start Bot"**.

### Step 4: Start Chatting!

Open Telegram and message your bot. Send `/start` to begin.

---

## Basic Commands

### Status & Help

| Command | What it does |
|---------|--------------|
| `/start` | Welcome message and current status |
| `/help` | List all available commands |
| `/info` | System info (CPU, memory, lock status) |
| `/pwd` | Show current working directory |

### Example Session

```
You: /start

Bot: 🚀 Welcome to TeleCode v0.1
     📂 Sandbox: Projects
     🖥️ Screen: 🔓 Unlocked
     🎤 Voice: ✅ Enabled
```

---

## Creating New Projects

Spin up new projects directly from Telegram! The `/create` command walks you through a secure project creation flow.

### How It Works

1. **Start the wizard**: Send `/create`
2. **Name your project**: Enter a name when prompted
3. **Confirm**: Press the button to create

TeleCode will then:
- 📁 Create the project directory (within your sandbox)
- 🔀 Initialize a git repository (`git init`)
- 💻 Open Cursor IDE with the new project

### Example Session

```
You: /create

Bot: 🆕 Create New Project

     📂 Projects will be created in:
     C:\Users\Dev\Projects

     📝 Enter your project name:

     Rules:
     • Use only letters, numbers, hyphens, underscores
     • No spaces or special characters
     • Example: my-awesome-app or webapp_v2

     (Type /cancel to abort)

You: my-new-api

Bot: 🔍 Confirm Project Creation

     📛 Name: my-new-api
     📂 Path: C:\Users\Dev\Projects\my-new-api

     This will:
     1. 📁 Create directory my-new-api
     2. 🔀 Initialize git repository
     3. 💻 Open Cursor IDE

     [✅ Create Project] [❌ Cancel]

You: [Clicks ✅ Create Project]

Bot: 🎉 Project Created Successfully!

     ✅ Project 'my-new-api' created successfully!

     📂 Location: C:\Users\Dev\Projects\my-new-api
     🔀 Git: Initialized
     💻 Cursor: Opening...

     Next steps:
     • Start coding in Cursor
     • Use /ai to run prompts
     • Use /status to check git
     • Use /commit to commit changes
```

### Project Naming Rules

| ✅ Allowed | ❌ Not Allowed |
|-----------|----------------|
| `my-project` | `my project` (spaces) |
| `webapp_v2` | `../escape` (path traversal) |
| `NewApp2026` | `C:\Windows` (absolute paths) |
| `api-server` | `project!@#` (special chars) |

### Security Features

- Projects are **always** created inside your DEV_ROOT sandbox
- Name sanitization blocks path traversal attempts (`../`, `..\\`)
- Confirmation step prevents accidental creation
- All actions are logged for audit

### Canceling

At any point, you can:
- Type `/cancel` to abort
- Press the ❌ Cancel button

---

## Git Workflow

TeleCode gives you full Git control from your phone.

### Checking Status

```
You: /status

Bot: 📊 Git Status
     ## main...origin/main [ahead 2]
      M src/app.py
     ?? new_file.txt
```

### Viewing Changes

```
You: /diff

Bot: 📝 Changes Summary
     src/app.py | 15 +++++++++------
     1 file changed, 9 insertions(+), 6 deletions(-)
```

### Committing Changes

```
You: /commit Fixed login bug

Bot: ✅ Changes Committed!
     📝 Message: Fixed login bug
```

### Pushing to Remote

```
You: /push

Bot: ⏳ Pushing to remote...
     ✅ Push Successful!
     To github.com:user/repo.git
        abc1234..def5678  main -> main
```

### Reverting Changes

⚠️ **Security Feature:** `/revert` now requires confirmation to prevent accidents.

```
You: /revert

Bot: ⚠️ DANGEROUS OPERATION

     This will permanently discard ALL uncommitted changes!

     📁 Affected directory: myproject

     This cannot be undone!

     To confirm, type:
     /revert CONFIRM

You: /revert CONFIRM

Bot: ⚠️ All uncommitted changes have been discarded!
```

**Warning:** `/revert CONFIRM` cannot be undone! It discards all uncommitted changes.

---

## AI Coding

Run Cursor AI from your phone — **using your existing Cursor subscription** (no extra API costs).

### Using /ai Command

```
You: /ai Add error handling to the login function

Bot: 🤖 Executing AI prompt...
     Add error handling to the login function

     ✅ AI Execution Complete!
     
     Changes Made:
     src/auth/login.py | 25 +++++++++++++++++++++++++
     1 file changed, 25 insertions(+)
     
     Use /commit to commit or /revert to undo
```

### Direct Text Prompts

You can also just type without `/ai`:

```
You: Refactor the database connection to use connection pooling

Bot: 🤖 Executing AI prompt...
     [continues as above]
```

### Review Before Accepting - Cursor Control Buttons

After every AI execution, you'll see **Cursor control buttons** (these do NOT touch git):

```
Bot: ✅ Prompt Sent to Cursor!

     🤖 Agent mode - Files auto-save (won't lose work)
     
     📝 Prompt: Create a login form with validation
     
     ⏳ AI is now processing...
     
     [📊 Check] [📖 Diff] [✅ Accept]
     [❌ Reject] [➡️ Continue]
     [⚙️ Mode] [🧹 Cleanup]
     
     _Note: Run button only appears when AI is waiting for approval (not on completion)_
```

### Cursor Buttons (AI control - no git!)

| Button | Action | What It Does |
|--------|--------|--------------|
| 📊 Check | See files modified | Read-only view of changes |
| 📖 Diff | Shows diff | Read-only diff view |
| ✅ Accept | Apply in Cursor | Uses Cursor automation to accept |
| ▶️ Run | **Approve command** | When AI wants to run a script, approve it |
| 🌐 Search | **Approve web search** | When AI wants to search the web, approve it |
| 🚫 Cancel | **Cancel action** | Cancel any pending AI action (Escape) |
| ➡️ Continue | **Continue AI** | Press Continue button (Enter) |
| 🛑 Stop | **Stop generation** | Stop current AI generation (Ctrl+Shift+Backspace) |
| ❌ Reject | Discard in Cursor | Uses Escape |
| ⚙️ Mode | Change prompt mode | Switch between Agent/Chat |
| 🧹 Cleanup | Close old agents | Closes oldest agent tabs when >5 |

### Approving AI Actions

When Cursor's AI wants to run a terminal command or search the web, it asks for permission. Use these buttons:

```
Bot: ⚠️ Cursor wants to run a command
     
     The AI is requesting to execute a terminal command.
     
     Do you want to approve this?
     
     [✅ Yes, Run It] [🚫 Cancel]

You: [clicks Yes, Run It]

Bot: ✅ Command Approved!
     The AI will now execute the command.
```

**Same for web search:**
```
Bot: 🌐 Cursor wants to search the web
     
     [🌐 Yes, Search] [🚫 Cancel]
```

### Cursor vs Git - Clear Separation

**Important:** AI buttons control **Cursor only**, git is **separate**!

| What You Want | Cursor (buttons) | Git (commands) |
|---------------|------------------|----------------|
| Apply changes | ✅ Accept | `/commit` |
| Discard changes | ❌ Reject | `/revert CONFIRM` |
| View changes | 📊 Check, 📖 Diff | `/status`, `/diff` |
| Save to repo | _(n/a)_ | `/commit` + `/push` |

**Workflow:**
1. Use **Accept** to apply AI changes in Cursor
2. Use `/commit` to git commit when ready
3. Use `/push` to push to remote

### Two-Step Undo Confirmation

When you click "🗑️ Undo All", a confirmation prompt appears:

```
Bot: ⚠️ Confirm Undo All

     This will permanently discard ALL uncommitted changes!
     
     This cannot be undone!
     
     [⚠️ Yes, Undo All Changes] [❌ Cancel]
```

### Manual Commands

You can also use text commands:

1. **Run AI prompt**: `/ai [your request]`
2. **Review changes**: `/diff`
3. **Accept or reject**:
   - `/commit [message]` - Commit with custom message
   - `/revert CONFIRM` - Discard all changes

---

## ⚙️ Prompt Modes

TeleCode supports two prompt modes that control how AI changes are handled:

### Agent Mode (Default - SAFEST)

```
You: /ai mode agent
Bot: ✅ Mode Changed! 🤖 Agent mode - Auto-saves files
     💡 Files auto-save, Reject uses Ctrl+Z
```

- Uses **Ctrl+Shift+I** to open a new Agent in Cursor
- **Files are saved immediately** to disk
- You **won't lose work** even if you forget to click Accept
- **Reject** uses Ctrl+Z to undo changes

### Chat Mode

```
You: /ai mode chat
Bot: ✅ Mode Changed! 💬 Chat mode
     ⚠️ Click Accept to apply, Reject uses Escape
```

- Uses **Ctrl+L** to open Chat panel in Cursor
- Changes are **proposed but not saved** until you click Accept
- More **control over what gets applied**
- **Reject** uses Escape to discard proposed changes

### Quick Mode Switch

```
/ai mode agent  - Switch to Agent mode (auto-save)
/ai mode chat   - Switch to Chat mode (manual accept)
/ai mode        - Show mode menu with buttons
```

### Mode Comparison

| Feature | 🤖 Agent Mode | 💬 Chat Mode |
|---------|---------------|--------------|
| Shortcut | Ctrl+Shift+I | Ctrl+L |
| Auto-saves | ✅ Yes | ❌ No |
| Risk of losing work | Low | Higher |
| Control | Less (auto-applies) | More (review first) |
| Reject method | Ctrl+Z | Escape |
| Best for | Quick tasks, safety | Careful review |

### Remember: No Git!

All these mode buttons only affect **Cursor**, not git. For git operations, use the separate commands (`/commit`, `/revert`, `/push`, etc.).

---

## 🤖 Model Selection

Choose which AI model powers your prompts. Different models have different strengths.

### Available Models

| Alias | Model | Tier | Context | Best For |
|-------|-------|------|---------|----------|
| `opus` | Claude Opus 4.5 | 💎 Paid | 200K | Complex reasoning, large refactors |
| `sonnet` | Claude Sonnet 4.5 | 💰 Paid | 1M | Daily coding, balanced |
| `haiku` | Claude Haiku 4.5 | ✨ Free | 200K | Quick tasks, simple edits |
| `gemini` | Gemini 3 Flash | ✨ Free | 1M | Large context, fast |
| `gpt` | GPT-4.1 | 💰 Paid | 128K | Alternative reasoning |

### Interactive Model Selection

```
You: /model

Bot: 🤖 Model Selection

     Current: claude-opus-4.5 (Claude Opus 4.5) 💎
     
     Select your AI model:
     
     [💎 Opus] [💰 Sonnet] [💰 GPT]
     [✨ Haiku] [⚡ Gemini]
     
     💎 = Paid  |  ✨ = Free

You: [Clicks Sonnet button]

Bot: ✅ Model Changed!

     💰 Now using: Claude Sonnet 4.5
     📊 Context: 1M
     💰 Tier: Paid

     Your next /ai command will use this model.
```

### Quick Model Switch

Switch models instantly without the menu:

```
You: /model haiku

Bot: ✅ Model changed to **Claude Haiku 4.5** ✨
```

### List All Models

```
You: /models

Bot: 📋 Available AI Models

     💎 Paid Models:
       opus - Claude Opus 4.5 (200K) ✅
         Best reasoning, complex tasks
       sonnet - Claude Sonnet 4.5 (1M)
         Balanced, cost-effective
       gpt - GPT-4.1 (128K)
         Alternative reasoning

     ✨ Free Models:
       haiku - Claude Haiku 4.5 (200K)
         Fast, simple tasks
       gemini - Gemini 3 Flash (1M)
         Large context, fast

     💡 Quick Switch: /model opus or /model haiku
     🔘 Menu: /model (interactive buttons)
```

### Model Persistence

- Your model choice is saved per Telegram user
- Persists across bot restarts
- Default model: **Claude Opus 4.5** (`opus`)
- Can be overridden in `.env` with `DEFAULT_MODEL=<alias>`

### Which Model Should I Use?

| Scenario | Recommended |
|----------|-------------|
| Complex refactoring | `opus` |
| Daily coding tasks | `sonnet` |
| Quick fixes, simple edits | `haiku` |
| Large file analysis | `gemini` (1M context) |
| Alternative reasoning | `gpt` |

---

## Voice-to-Code (The Core Feature)

This is what makes TeleCode special — **speak your code changes from anywhere** using just your phone.

### Why Voice-to-Code?
- 🚶 **Code while walking** — on your commute, at the gym, anywhere
- 💰 **No API costs** — uses free Google Speech + your existing Cursor plan
- ⚡ **Faster than typing** — especially for longer prompts

### How to Use

1. In Telegram, **hold the microphone button**
2. **Speak your prompt** (e.g., "Add a loading spinner to the dashboard")
3. **Release to send**

The bot will:
1. Download the audio
2. Transcribe it to text (free Google Speech API)
3. Show you what it heard
4. Execute it via Cursor AI (uses your existing subscription)

### Example

```
You: [Voice Message: "Create a new user registration form with email validation"]

Bot: 🎤 Processing voice message...
     📝 Transcribed: Create a new user registration form with email validation
     
     🤖 Executing AI prompt...
     [continues with AI execution]
```

### Tips for Voice

- Speak clearly and at a moderate pace
- Avoid background noise
- Keep prompts concise (under 30 seconds)
- English works best with Google Speech Recognition

---

## Navigation

Switch between sandbox directories and navigate files.

### Switching Sandboxes

```
You: /ls

Bot: 📂 Contents of myproject
     📁 src
     📁 tests
     📁 docs
     📄 README.md
     📄 requirements.txt
     📄 main.py
```

### Switching Sandboxes

```
You: /sandbox

Bot: 📂 Sandbox Directories (3)

     Current: Projects ✅
     
     Select a sandbox to switch to:
     [Projects ✅]
     [Work]
     [Personal]
```

```
You: /sandbox 2

Bot: ✅ Switched to sandbox: Work
     ⚠️ Restart TeleCode for full effect.
     
     Current sandbox: `Work`
```

**Note:** Use `/sandboxes` to see all available sandbox directories. Switch between them to work in different project folders.

### Opening Cursor from Telegram

```
You: /cursor

Bot: 💻 Cursor IDE Status

     Workspace: src
     Status: 🔴 Not Running
     
     Cursor is not running
     
     [🚀 Open in Cursor]

You: [clicks button]

Bot: 💻 Opening Cursor
     📂 Workspace: src
     ⏳ Launching... (3s)...

Bot: 💻 Cursor Status
     ✅ Cursor ready with src
     
     [🤖 Send AI Prompt] [🔄 Refresh Status]
```

### Reading Files

```
You: /read main.py

Bot: 📄 main.py

     from flask import Flask
     
     app = Flask(__name__)
     
     @app.route('/')
     def home():
         return "Hello, World!"
     
     if __name__ == '__main__':
         app.run()
```

### 🔒 Protected Files (Cannot Read)

For security, certain sensitive files are blocked:

```
You: /read .env

Bot: ⛔ Access denied: Access to .env files is blocked
```

| Blocked Pattern | Reason |
|-----------------|--------|
| `.env` | Contains your bot token |
| `id_rsa`, `id_ed25519` | SSH private keys |
| `.pem`, `.key` | Certificate files |
| `.ssh/` | SSH directory |
| `credentials`, `secrets.json` | Credential files |

### Navigation Rules

- You can only access files **within your current sandbox folder**
- Switch sandboxes using `/sandbox` to work in different project folders
- Absolute paths outside sandbox are blocked
- Sensitive files are always blocked even inside sandbox

---

## 🖥️ Headless Mode (Locked Screen)

TeleCode works even when your laptop screen is locked! Here's how each platform handles it:

### 🪟 Windows: TSCON

**TSCON** disconnects your display while keeping your session active. Perfect for GUI automation!

**Quick Start:**
1. Right-click the TeleCode tray icon (near the clock)
2. Click **"🛡️ Secure Lock"**
3. Screen goes black, but TeleCode keeps working!

**From Command Line (Admin required):**
```batch
tscon_secure_lock.bat
```

**Features:**
- ✅ Full GUI automation (Cursor Composer buttons work)
- ✅ Blocks remote desktop apps for security
- ✅ Auto-lock after 30 minutes
- ✅ Physical access only to reconnect

See [docs/TSCON.md](docs/TSCON.md) for full details.

### 🐧 Linux: Xvfb (Virtual Display)

**Xvfb** creates a virtual X server for headless GUI automation.

**Setup:**
```bash
# Install Xvfb
sudo apt install xvfb

# Install Python wrapper
pip install pyvirtualdisplay

# Optional: Window management
sudo apt install xdotool
```

**Usage:**
1. Right-click the TeleCode tray icon
2. Click **"🖥️ Start Virtual Display"**
3. Lock your screen normally — TeleCode keeps working!

**How it works:**
- Creates invisible display (e.g., `:99`)
- Cursor runs in the virtual display
- pyautogui works without physical monitor

### 🍎 macOS: caffeinate + Virtual Display

macOS is more restrictive with locked-screen automation.

**What TeleCode does automatically:**
- Runs `caffeinate -dims` to prevent sleep
- Keeps the system awake for remote commands

**For full headless GUI:**
macOS requires additional setup:
1. **Virtual Display Adapter** - BetterDummy, Deskreen, or hardware HDMI adapter
2. **VNC** - Screen sharing to a virtual display

**Without virtual display:**
- Git commands work ✅
- Voice transcription works ✅
- GUI automation (Accept/Reject buttons) may not work when screen is locked

### Quick Reference

| Platform | Headless Method | System Tray Option | Setup Required |
|----------|-----------------|-------------------|----------------|
| 🪟 Windows | TSCON | Secure Lock | None (built-in) |
| 🐧 Linux | Xvfb | Start Virtual Display | `apt install xvfb` |
| 🍎 macOS | caffeinate | Auto-enabled | Virtual adapter for full GUI |

---

## Tips & Tricks

### 1. Quick Status Check

The fastest way to see what's happening:

```
You: /status

Bot: ## main
      M app.py
```

### 2. Commit with Default Message

Just type `/commit` without a message:

```
You: /commit

Bot: ✅ Changes Committed!
     📝 Message: TeleCode auto-commit: 2026-02-01 14:30
```

### 3. View Recent Commits

```
You: /log 3

Bot: 📜 Recent Commits (last 3)
     abc1234 Add user authentication
     def5678 Fix database connection
     ghi9012 Initial commit
```

### 4. Quick Pull Before Working

Always pull latest changes first:

```
You: /pull
You: /ai [your prompt]
```

### 5. Branch Awareness

Check which branch you're on:

```
You: /branch

Bot: 🔀 Branches
     * main
       feature/login
       develop
```

---

## Troubleshooting

### Bot Not Responding

1. **Check if bot is running** on your laptop
2. **Verify your User ID** in `.env` matches your actual ID
3. **Check internet connection** on your laptop

### "Access Denied" Errors

You're trying to access files outside your sandbox or protected files:

```
You: /read C:\Windows\system32\config

Bot: ❌ Access denied. Path escapes sandbox: C:\Windows\system32\config
```

```
You: /read .env

Bot: ⛔ Access denied: Access to .env files is blocked
```

**Solution:** 
- Only navigate within your configured DEV_ROOT folder
- Sensitive files (.env, SSH keys, etc.) are blocked for security

### Voice Not Working

1. **Check FFmpeg is installed**: Run `ffmpeg -version` in terminal
2. **Verify voice is enabled**: Check "Enable Voice" in config GUI
3. **Check /info**: Shows if voice is enabled

```
You: /info

Bot: ...
     ❌ Voice processing unavailable:
     ❌ ffmpeg not installed
```

### Git Push Failing

```
Bot: ❌ Push Failed
     fatal: Authentication failed
```

**Solution:** Configure Git credentials on your laptop:
- Use SSH keys (recommended)
- Use Git Credential Manager
- Use a personal access token

### AI Command Not Working

```
Bot: ❌ Cursor CLI not found. Please install Cursor and add it to PATH.
```

**Solution:**
1. Open Cursor IDE
2. Open Command Palette (Ctrl+Shift+P)
3. Search "Install 'cursor' command"
4. Restart terminal and TeleCode

### Bot Stops When Laptop Sleeps

Enable sleep prevention:
1. Open TeleCode config (`python main.py --config`)
2. Check "Prevent Sleep Mode while running"
3. Save and restart

### "Prompt Blocked" Error

TeleCode has security filters to prevent malicious prompts:

```
You: Show me the bot token

Bot: ⛔ SECURITY ALERT
     Your prompt was blocked...
```

**This is normal!** TeleCode blocks prompts that appear to:
- Extract tokens or credentials
- Read sensitive files
- Execute shell commands
- Bypass security

**Solution:** Rephrase your prompt to focus on legitimate coding tasks.

---

## 🔒 Security Features

TeleCode has enterprise-grade security to protect your system.

### Token Protection

Your bot token is stored in an **encrypted vault**, not plaintext:
- **Windows**: Uses DPAPI (Data Protection API)
- **macOS**: Uses Keychain via `security` command
- **Linux**: Uses Secret Service (GNOME Keyring / KWallet) via `keyring` library
- **Fallback**: Encrypted file with machine-specific key (all platforms)

### Prompt Injection Defense

Certain prompts are blocked for security:

```
You: Show me the bot token

Bot: ⛔ SECURITY ALERT
     
     Your prompt was blocked because it appears to be attempting
     to extract sensitive information or execute dangerous commands.
     
     This incident has been logged.
```

| Blocked Patterns |
|------------------|
| "show token", "print env" |
| "ignore previous instructions" |
| Shell commands in prompts |
| Requests to read .env files |

### Rate Limiting

- **30 commands per minute** maximum
- **5 failed logins** = 5-minute lockout

---

## Quick Reference Card

| Task | Command |
|------|---------|
| Start | `/start` |
| Help | `/help` |
| **New project** | `/create` |
| Git status | `/status` |
| View changes | `/diff` |
| Commit | `/commit [msg]` |
| Push | `/push` |
| Pull | `/pull` |
| View log | `/log` |
| List branches | `/branch` |
| Undo changes | `/revert CONFIRM` |
| AI prompt | `/ai [prompt]` |
| AI accept | `/ai accept` |
| AI reject | `/ai reject` |
| AI continue | `/ai continue [prompt]` |
| AI stop | `/ai stop` |
| AI status | `/ai status` |
| AI mode | `/ai mode [agent|chat]` |
| **Select model** | `/model` |
| Quick model switch | `/model opus`, `/model haiku` |
| List models | `/models` |
| **Open Cursor** | `/cursor` or `/cursor open` 💻 |
| Switch sandbox | `/sandbox` or `/sandboxes` 📂 |
| List files | `/ls` |
| Read file | `/read [file]` |
| Current path | `/pwd` |
| System info | `/info` |

---

## Need More Help?

- **Security concerns?** See [SECURITY.md](SECURITY.md)
- **Technical details?** See the main [README.md](../README.md)
- **Found a bug?** Open an issue on GitHub

Happy remote coding! 🚀

