# ⚡ TeleCode Quick Start Guide

Get TeleCode running in **30 seconds**.

> 🎤 **Voice-to-code** from your phone • 💰 **Uses your Cursor plan** (no API costs) • 🌍 **Works from anywhere**

---

## What You'll Get

- **Speak code changes** from your phone via Telegram
- **Remote Git control** — push, pull, commit from anywhere
- **Uses your existing Cursor subscription** — no extra API fees
- **Works even when laptop is locked**

---

## Prerequisites

- ✅ Python 3.10+
- ✅ Git
- ✅ Cursor IDE (with CLI installed) — *uses your existing subscription*
- ⚙️ FFmpeg (optional, for voice-to-code)

---

## Step 1: Get Telegram Credentials (2 minutes)

### 1.1 Create Your Bot
1. Open Telegram → Search **@BotFather**
2. Send `/newbot`
3. Choose a name: `My TeleCode`
4. Choose a username: `mytelecodeprivate_bot`
5. **Copy the token** (looks like `123456789:ABCdefGHI...`)

### 1.2 Get Your User ID
1. Open Telegram → Search **@userinfobot**
2. Send `/start`
3. **Copy your User ID** (a number like `123456789`)

---

## Step 2: Install TeleCode (1 minute)

### Windows
```batch
git clone https://github.com/yourusername/telecode.git
cd telecode
setup.bat
```

### Mac/Linux
```bash
git clone https://github.com/yourusername/telecode.git
cd telecode
chmod +x setup.sh start.sh
./setup.sh
```

---

## Step 3: Configure (30 seconds)

The setup GUI will open. Enter:

| Field | Value |
|-------|-------|
| Bot Token | `123456789:ABCdefGHI...` (from BotFather) |
| User ID | `123456789` (from userinfobot) |
| Dev Root | Click Browse → Select your projects folder |
| AI Model | Select your default model (Opus 4.5 recommended) |

Click **"Save & Start Bot"**.

> 💡 **Model Selection**: You can change your AI model anytime via `/model` command in Telegram.

---

## Step 4: Start Using! (0 seconds)

Open Telegram, find your bot, and try:

```
/start          → Welcome message
/help           → List commands
/status         → Git status
Hello world     → AI prompt!
```

---

## Quick Command Reference

| What | Command |
|------|---------|
| Git status | `/status` |
| See changes | `/diff` |
| Push code | `/push` |
| Pull code | `/pull` |
| Commit | `/commit Fix bug` |
| Undo changes | `/revert CONFIRM` ⚠️ |
| AI prompt | `/ai Refactor login` |
| Select model | `/model` |
| Quick model switch | `/model opus` or `/model haiku` |
| List models | `/models` |
| List files | `/ls` |
| Change folder | `/cd myproject` |

> **Note:** `/revert` requires `CONFIRM` argument to prevent accidents.

---

## 🤖 Model Selection (NEW!)

Choose which AI model powers your prompts:

| Command | Effect |
|---------|--------|
| `/model` | Show model menu with buttons |
| `/model opus` | Switch to Claude Opus 4.5 (best) |
| `/model sonnet` | Switch to Claude Sonnet 4.5 |
| `/model haiku` | Switch to Claude Haiku (free) |
| `/model gemini` | Switch to Gemini 3 Flash (free) |
| `/models` | List all available models |

**Available Models:**
- 💎 **Paid**: `opus` (best reasoning), `sonnet` (balanced), `gpt`
- ✨ **Free**: `haiku` (fast), `gemini` (large context)

---

## 📊 After AI Execution - Action Buttons

After every AI prompt, you'll see a **changes preview** with action buttons:

```
Bot: ✅ AI Execution Complete!

     📊 Changes Preview:
     src/login.py | 25 +++++++++++++
     1 file changed, 25 insertions(+)
     
     [📖 View Full Diff]
     [✅ Keep All] [🗑️ Undo All]
     [▶️ Continue]
```

| Button | Action |
|--------|--------|
| 📖 View Full Diff | Shows complete diff inline |
| ✅ Keep All | Commits all changes (like Cursor's "Keep All") |
| 🗑️ Undo All | Discards all changes (with confirmation) |
| ▶️ Continue | Prompts for follow-up AI command |

---

## Voice-to-Code (The Magic ✨)

Just **hold the microphone** in Telegram and speak:

> "Add a loading spinner to the dashboard component"

TeleCode will:
1. Transcribe your voice (free Google Speech API)
2. Send it to Cursor AI (uses your existing Cursor plan)
3. Show you the changes made

**No API costs** — uses your Cursor subscription!

---

## Starting TeleCode Later

### Windows
```batch
start.bat
```

### Mac/Linux
```bash
./start.sh
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Bot not responding | Check if terminal is running |
| "Unauthorized" | Verify User ID in .env |
| Voice not working | Install FFmpeg |
| Cursor CLI error | Run "Install cursor command" in Cursor |

---

## Next Steps

- 📖 Read the full [User Guide](USER_GUIDE.md)
- 🔒 Review [Security](SECURITY.md)
- 🐛 Report issues on GitHub

---

**Happy remote coding!** 🚀

*Voice-to-code from anywhere • Uses your Cursor plan • Zero API costs*

