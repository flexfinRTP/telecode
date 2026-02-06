# Changelog

All notable changes to TeleCode will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Contributing**: For contributions, we increment `v0.2.x` (patch versions) for bug fixes 
> and minor improvements. Feature additions will increment to `v0.3.0`, etc.

---

## [0.2.5] - 2026-02-03

### 🐛 Fixed

#### AI Completion Detection
- **Fixed premature "Cursor AI Completed" messages**: Implemented robust poll history tracking to ensure completion is only shown when lines have truly stopped changing
- **Poll history verification**: Now requires at least 5 consecutive polls showing no changes before declaring completion
- **Improved change detection**: Tracks both immediate changes and ongoing changes via poll history comparison
- **Better stability verification**: Only shows "completed" when:
  - Lines have stopped changing (verified by poll history)
  - Stable count meets threshold (10 polls = 30 seconds)
  - Minimum processing time has passed (15 seconds)
  - Poll history confirms stability (at least 5 polls with no changes)
- **Enhanced logging**: Added detailed logging to track poll history and stability verification

### Technical Details

#### Implementation
- Added `poll_history` tracking to store last 5 poll results (files and diff size)
- Enhanced `lines_still_changing` detection by comparing all recent polls
- Only increment `stable_count` when poll history confirms no ongoing changes
- Clear poll history when changes are detected to start fresh tracking
- Improved status messages to show "verifying stability..." when building confidence

## [0.2.4] - 2026-02-03

### 📸 Screenshot Command with OCR Transcription

Added a new `/screenshot` command that captures the Cursor Composer chat window and performs OCR transcription of the entire AI prompt output.

### Added

#### Screenshot Command
- **`/screenshot`** - Capture Cursor Composer chat with full OCR transcription
- **Automatic fullscreen**: Ensures Cursor is focused and maximized before capture
- **Full text extraction**: Uses OCR to transcribe entire AI output (not filtered)
- **Dual output**: Sends both screenshot image and transcribed text
- **Smart formatting**: Long transcriptions sent as documents for better readability
- **Error handling**: Graceful fallback if OCR fails (still sends screenshot)

#### Security & Architecture
- **SEC-006**: New security standard for screenshot commands
- **Authenticated**: Uses `@require_auth` decorator for user validation
- **Rate limited**: Protected by CommandRateLimiter (30 commands/minute)
- **Audit logged**: All screenshot commands logged for security review
- **Output sanitization**: OCR text sanitized before sending (SEC-005 compliance)
- **Path validation**: Screenshot paths validated against security boundaries

### Changed

#### Help Menu
- Added `/screenshot` command to help menu under "AI Control" section
- Added to Telegram bot command list for autocomplete

### Technical Details

#### Implementation
- Reuses existing `capture_screenshot()` method from `CursorAgentBridge`
- Reuses existing `extract_text_from_screenshot()` method with `filter_code_blocks=False`
- Follows existing command handler patterns and error handling
- Uses `WindowManager.focus_cursor_window()` for optimal screenshot quality
- Leverages `_send_ocr_as_document()` for long transcriptions

#### Security Architecture
- ✅ User authentication via SecuritySentinel
- ✅ Rate limiting via CommandRateLimiter
- ✅ Command audit logging
- ✅ OCR output sanitization (tokens, paths, sensitive data)
- ✅ Error handling prevents information leakage
- ✅ No breaking changes to existing functionality

### Usage

```
# Capture screenshot and transcribe
/screenshot

# Command automatically:
# 1. Focuses and maximizes Cursor window
# 2. Captures screenshot of Composer chat
# 3. Extracts text via OCR
# 4. Sends screenshot image
# 5. Sends transcribed text (or document if long)
```

---

## [0.2.3] - 2026-02-03

### 📂 Enhanced /ls Command - Recursive Worktree Listing

Enhanced the `/ls` command to support recursive listing of the entire worktree, providing comprehensive file system visibility while maintaining security best practices.

### Added

#### Recursive Directory Listing
- **`/ls -R`** or **`/ls --recursive`** - Recursively list entire worktree
- **`/ls -R [path]`** - Recursively list from specific directory
- **Smart filtering**: Automatically skips common build/cache directories (node_modules, __pycache__, .venv, etc.)
- **File sizes**: Shows human-readable file sizes (B, KB, MB, GB)
- **Indented tree structure**: Clear visual hierarchy with indentation
- **Depth limiting**: Maximum recursion depth of 10 levels (security feature)
- **Hidden file handling**: Skips hidden files/directories except .git

#### Security Enhancements
- **Path validation**: Every path validated against sandbox boundaries during recursion
- **Permission handling**: Graceful handling of permission-denied directories
- **Output sanitization**: Maintains existing security sanitization for all outputs
- **Audit logging**: All recursive listings logged for security audit

### Changed

#### Enhanced `/ls` Command
- **Default behavior**: Unchanged - still lists current directory by default
- **Recursive mode**: New optional flag for full worktree listing
- **Better formatting**: Improved output with file sizes and tree structure
- **Error handling**: Enhanced error messages for permission issues

### Technical Details

#### Implementation
- Added `recursive` parameter to `CLIWrapper.list_directory()`
- Added `max_depth` parameter (default 10) to prevent infinite recursion
- Added `_format_size()` helper for human-readable file sizes
- Enhanced path validation during recursive traversal
- Maintains all existing security checks (sandbox validation, blocked file patterns)

#### Security Architecture
- ✅ All paths validated against sandbox boundaries
- ✅ Recursion depth limited to prevent DoS
- ✅ Permission errors handled gracefully
- ✅ Blocked file patterns still enforced
- ✅ Audit logging for all operations

### Usage Examples

```
# List current directory (unchanged)
/ls

# List specific directory
/ls src

# List entire worktree recursively
/ls -R

# List specific directory recursively
/ls -R src/components
```

---

## [0.2.2] - 2026-02-03

### 🖥️ Fullscreen Cursor Focus for Screenshots & OCR

Enhanced screenshot and OCR functionality to ensure Cursor window is always maximized to fullscreen when processing screenshots, improving screenshot quality and OCR accuracy.

### Added

#### Photo/Image Handler for Telegram Screenshots
- **New photo handler**: Process screenshots sent directly to Telegram via photo messages
- **Automatic fullscreen**: Ensures Cursor is focused and fullscreen before OCR processing
- **OCR extraction**: Extracts text from uploaded screenshots using Tesseract OCR
- **Smart filtering**: Filters out code blocks and technical syntax, keeping only natural language summaries
- **User feedback**: Provides clear status messages during processing

### Changed

#### Fullscreen Focus on All Platforms
- **Windows**: `focus_cursor_window()` now maximizes window using `SW_MAXIMIZE` (Win32 API)
- **macOS**: Uses AppleScript to set `AXFullscreen` attribute or zoom window
- **Linux**: Uses `xdotool` or `wmctrl` to maximize window (MAXIMIZED_VERT + MAXIMIZED_HORZ)
- **All focus actions**: Every cursor focus operation now automatically makes window fullscreen

#### Screenshot Capture Improvements
- **Enhanced timing**: Increased wait time to 0.5s after fullscreen transition for better screenshot quality
- **Fullscreen before capture**: All screenshot operations now ensure Cursor is fullscreen first
- **Better OCR results**: Fullscreen screenshots provide more context and better text recognition

### Fixed

#### Consistent Fullscreen Behavior
- **All cursor focus actions**: Now consistently use fullscreen mode
  - Screenshot capture operations
  - OCR text extraction
  - Photo processing from Telegram
  - All AI prompt operations
  - Accept/Reject actions
  - Continue/Stop operations
  - All other cursor interactions

### Technical Details

#### Updated Methods
- `WindowManager._focus_cursor_window_windows()`: Added `SW_MAXIMIZE` after restore
- `WindowManager._focus_cursor_window_macos()`: Added fullscreen AppleScript commands
- `WindowManager._focus_cursor_window_linux()`: Added window maximization via xdotool/wmctrl
- `CursorAgentBridge.capture_screenshot()`: Enhanced with fullscreen focus and longer wait time
- `TeleCodeBot._handle_photo()`: New handler for processing Telegram photo messages

#### Cross-Platform Support
- Windows: Uses Win32 API `ShowWindow(hwnd, SW_MAXIMIZE)`
- macOS: Uses AppleScript `AXFullscreen` attribute or zoom button
- Linux: Uses `xdotool windowstate --add MAXIMIZED_VERT/MAXIMIZED_HORZ` or `wmctrl -b add,maximized_vert,maximized_horz`

### User Experience
- **Better screenshots**: Fullscreen captures show more context and are easier to read
- **Improved OCR**: Fullscreen screenshots provide better text recognition accuracy
- **Seamless workflow**: All cursor operations automatically use fullscreen without user intervention
- **Photo support**: Users can now send screenshots directly to Telegram for OCR processing

---

## [0.2.1] - 2026-02-03

### 🔍 Model Pricing Audit - Cursor 2026 Pricing Model

Comprehensive audit and update of model pricing information to reflect Cursor's current (2026) API-based pricing model.

### Removed
- **Gemini 2.0 Flash model**: Removed from available models list
  - Removed from `model_config.py` model registry
  - Removed from configuration GUI dropdown
  - Removed from documentation (USER_GUIDE.md, README.md)
  - Simplified Gemini Flash search patterns in cursor_agent.py

### Changed

#### Model Pricing Documentation
- **Updated model tier classification** to clarify practical vs. official distinction
- **Added comprehensive documentation** explaining Cursor's API-based pricing (as of June 2025)
- **Clarified FREE vs PAID tiers**:
  - FREE: Cost-effective models practical for free tier usage
  - PAID: Expensive models that require paid subscription for practical use
- **Updated all documentation** (USER_GUIDE.md, README.md, model_config.py) with accurate pricing information

#### Key Findings
- All frontier models are technically available on ALL Cursor plans (free and paid)
- The difference is in **usage allowances**, not model availability
- Free tier (Hobby) has very limited usage credits
- Paid plans include monthly usage credits ($20/month for Pro)

### Added

#### New Documentation
- **`docs/MODEL_PRICING_AUDIT_2026.md`**: Comprehensive audit report with findings and recommendations
- **Enhanced code comments** in `model_config.py` explaining the pricing model
- **Updated USER_GUIDE.md** with detailed explanation of Cursor's pricing structure

### Technical Details
- Model tier classification remains accurate from a practical usage standpoint
- All models correctly categorized based on cost-effectiveness for free tier
- Documentation now clearly explains that "FREE" means "practical for free tier" and "PAID" means "requires paid plan for practical use"

---

## [0.2.0] - 2026-02-03

### 🎉 Major Release - Production Ready

TeleCode v0.2.0 represents a major milestone with significant improvements in stability, features, and user experience. The application is now in excellent shape and ready for production use.

### ✨ Key Highlights

- **Virtual Display Support**: Complete replacement of screen lock with monitor power control for perfect pyautogui compatibility
- **OCR Text Extraction**: Extract readable text from Cursor screenshots with smart filtering
- **Progress Screenshots**: Real-time visual feedback while AI processes your prompts
- **Interactive Commits**: Enhanced commit workflow with file list preview
- **Git Push Improvements**: Automatic upstream branch detection and setup
- **Multi-Agent Support**: Better handling of multiple Cursor agent tabs
- **Cross-Platform**: Full support for Windows, macOS, and Linux with platform-specific optimizations

### Added
- **Virtual Display (Windows)**: Turn off monitor while keeping session active - works on ALL Windows editions
- **OCR Integration**: Extract text from screenshots using Tesseract OCR with smart code block filtering
- **Progress Updates**: Periodic screenshots during AI processing (every 1 min for first 10 min, then every 5 min)
- **Interactive Commit**: Prompt for commit message with file list preview when no message provided
- **Git Push Auto-Detection**: Automatically detects and sets upstream branch when pushing
- **Agent Button Routing**: Continue and Stop buttons correctly target specific agent tabs
- **Model Selection**: Interactive model switching with support for Opus, Sonnet, Haiku, Gemini, and GPT-4.1
- **Project Creation Wizard**: Interactive `/create` command for new project scaffolding
- **Cursor Status Detection**: Smart detection of Cursor IDE status with launch capability

### Changed
- **Virtual Display Replaces Screen Lock**: Better pyautogui support, works on Windows Home
- **Screenshot Timing**: Initial screenshot at 8 seconds (was 10 seconds) for faster feedback
- **Commit Message Format**: Always includes timestamp suffix for consistency
- **Button Layout**: Streamlined action buttons with clearer separation of Cursor vs Git operations
- **Error Handling**: Improved error messages and diagnostics throughout

### Fixed
- **Git Push Without Upstream**: Fixed push failures when branch has no upstream configured
- **Conversation Handler State**: Fixed unresponsive commands after interruption
- **Agent Tab Navigation**: Fixed button routing to correct agent tabs
- **Permission Errors**: Fixed file access issues for installed applications (uses user data directory)
- **Markdown Parse Errors**: Fixed 400 Bad Request errors in commands with git status output

### Technical Improvements
- **User Data Directory**: Logs and config now stored in platform-specific user data directories
- **Cross-Platform Credentials**: Keychain/DPAPI/Secret Service support for all platforms
- **Enhanced Logging**: Better diagnostic information and error context
- **State Management**: Improved conversation handler state cleanup and recovery

### Documentation
- **Updated Guides**: Comprehensive updates to README, USER_GUIDE, and QUICK_START
- **Virtual Display Docs**: Complete documentation for Windows Virtual Display feature
- **Security Audit**: Full security audit documentation available

---

## [0.1.21] - 2026-02-03

### 🔄 Replaced LockWorkStation with Virtual Display (Turn Off Monitor)

### Changed
- **Replaced LockWorkStation with Virtual Display**: Complete replacement of screen lock with monitor power control
  - **Why**: `LockWorkStation()` locks the screen (password required), which **blocks ALL input including pyautogui**
  - **Solution**: Turn off monitor using `SC_MONITORPOWER` API - keeps session active, pyautogui works!
  - **Benefits**:
    - ✅ **pyautogui works perfectly!** (LockWorkStation blocks all input)
    - ✅ Works on Windows Home, Pro, Enterprise, Server
    - ✅ No administrator access required
    - ✅ Simpler and more reliable (single API call)
    - ✅ Better for GUI automation (session stays active, not locked)
  - **Files Changed**:
    - `src/screen_lock_helper.py` → `src/virtual_display_helper.py` (replaced with turn off monitor logic)
    - `screen_lock*.bat` → `turn_off_display.bat` (new batch file)
    - All imports and references updated throughout codebase
  - **Optional Component**:
    - Provides even better pyautogui support
    - Requires one-time admin approval (UAC prompt)
  - **Documentation Updated**:
    - `docs/ScreenLock.md` → `docs/VirtualDisplay.md` (rewritten)
    - All README, USER_GUIDE, CONTRIBUTING docs updated
    - All code comments updated

### Removed
- **Screen Lock Files**: Removed all LockWorkStation-related files
  - `src/screen_lock_helper.py` (replaced by `virtual_display_helper.py`)
  - `screen_lock.bat` (replaced by `turn_off_display.bat`)
  - `screen_lock_secure.bat` (no longer needed)
  - `screen_lock_verbose.bat` (no longer needed)

### Technical Details
- Uses `SendMessage` with `SC_MONITORPOWER` to turn off monitor
- No admin required for basic monitor control
- Session stays active (not locked) - pyautogui works!
- Monitor can be woken by mouse movement or key press

---

## [0.1.20] - 2026-02-03

### 🔄 Replaced TSCON with Screen Lock (LockWorkStation)

> **Note**: Screen Lock was later replaced with Virtual Display in v0.1.21. This entry is kept for historical reference.

### Changed
- **Replaced TSCON with Screen Lock**: Complete replacement of TSCON method with Windows LockWorkStation API
  - **Why**: TSCON only works on Windows Pro/Enterprise/Server, not Windows Home
  - **Solution**: Use `LockWorkStation()` API which works on ALL Windows editions
  - **Benefits**:
    - ✅ Works on Windows Home, Pro, Enterprise, Server
    - ✅ No administrator access required for basic lock
    - ✅ Simpler and more reliable (single API call vs complex TSCON logic)
    - ✅ Same functionality (lock screen, keep session active, GUI automation works)
    - ✅ Better user experience (no path detection issues, no session querying)
  - **Files Changed**:
    - `src/tscon_helper.py` → `src/screen_lock_helper.py` (renamed and rewritten)
    - `tscon_*.bat` → `screen_lock*.bat` (new batch files)
    - All imports and references updated throughout codebase
  - **Security Features Preserved**:
    - RDP disabling (secure mode) - still requires admin
    - Auto-lock watchdog timer - still works
    - Audit logging - still works
  - **Documentation Updated**:
    - `docs/TSCON.md` → `docs/ScreenLock.md` (rewritten)
    - All README, USER_GUIDE, CONTRIBUTING docs updated
    - All code comments updated

### Removed
- **TSCON Files**: Removed all TSCON-related files
  - `src/tscon_helper.py` (replaced by `screen_lock_helper.py`)
  - `tscon_lock.bat` (replaced by `screen_lock.bat`)
  - `tscon_lock_verbose.bat` (replaced by `screen_lock_verbose.bat`)
  - `tscon_secure_lock.bat` (replaced by `screen_lock_secure.bat`)
  - `tscon_restore.bat` (no longer needed)

### Technical Details
- LockWorkStation API is available on all Windows editions
- No admin required for basic screen lock
- Admin only needed for secure mode (RDP disabling)
- Session stays active for GUI automation (same as TSCON)
- Password required to unlock (same as TSCON)

---

## [0.1.19] - 2026-02-02

### 🔧 Fixed Git Push - No Upstream Branch Error

### Fixed
- **Git Push Without Upstream**: Fixed `/push` command failing when branch has no upstream branch configured
  - **Issue**: `git push` fails with "The current branch master has no upstream branch" error
  - **Root Cause**: Simple `git push` command doesn't work when upstream tracking isn't set
  - **Solution**: Enhanced `git_push()` to automatically detect current branch and remote, then push with explicit remote/branch
  - **Smart Detection**:
    1. First tries standard `git push` (works if upstream is configured)
    2. If that fails with "no upstream branch" error, detects:
       - Current branch name (via `git rev-parse --abbrev-ref HEAD`)
       - Available remotes (via `git remote`)
       - Default remote (prefers 'origin', falls back to first available)
    3. Pushes with explicit remote and branch: `git push -u <remote> <branch>`
    4. Sets upstream tracking for future pushes (`-u` flag)
  - **User-Friendly**: Works for all users regardless of:
    - Branch name (master, main, feature/xyz, etc.)
    - Remote name (origin, upstream, custom remotes)
    - Whether upstream is already configured or not
  - **Safe**: Branch and remote names are sanitized before use
  - **Error Handling**: Provides clear error messages if:
    - No remotes are configured
    - Branch name can't be determined
    - Push still fails after auto-detection

### Changed
- **`git_push()` method** in `src/cli_wrapper.py`:
  - Now handles branches without upstream automatically
  - Added helper methods:
    - `_get_current_branch()` - Detects current branch name
    - `_get_remotes()` - Lists available git remotes
    - `_get_default_remote()` - Selects default remote (origin preferred)
  - Enhanced error messages with context about what was tried

### Technical Details
- Uses `git push -u <remote> <branch>` to set upstream and push in one command
- Sanitizes branch names to prevent injection attacks
- Falls back gracefully if detection fails
- Maintains backward compatibility - works normally if upstream is already set

---

## [0.1.18] - 2026-02-02

### 🔧 Fixed

#### Conversation Handler State Management
- **Issue**: Multi-step commands (`/commit` and `/create`) would become unresponsive if called again after being interrupted (e.g., when user interacts with Cursor AI while waiting for input)
- **Root Cause**: Conversation handlers remained in their waiting states, preventing commands from being recognized as new entry points when called again
- **Fix Applied to Both Commands**:
  - **`/commit` command**: 
    - Added `/commit` command handler to `COMMIT_AWAITING_MESSAGE` state to allow restarting
    - Added `/commit` to fallback handlers for additional restart capability
    - Ensured `_cmd_commit` properly returns `ConversationHandler.END` when commit message is provided directly (immediate commit)
  - **`/create` command**:
    - Added `/create` command handler to both `CREATE_AWAITING_NAME` and `CREATE_AWAITING_CONFIRM` states
    - Added `/create` to fallback handlers
    - Added state cleanup in `_cmd_create_start` to clear any existing project name when restarting
- **Impact**: Users can now call `/commit` or `/create` again after interruption, and conversations will restart cleanly
- **Behavior**: 
  - When `/commit` is called while already in commit conversation state, it restarts the prompt flow (shows file list and asks for message again)
  - When `/create` is called while already in create conversation state, it restarts from the beginning (asks for project name again)

---

## [0.1.17] - 2026-02-02

### ✨ Added
- **Interactive Commit Message Prompt**: The `/commit` command now prompts users for a commit message when no message is provided
  - When `/commit` is used without arguments, the bot asks the user to enter a commit message
  - **Shows list of changed files** in the prompt to help users remember what they're committing
  - Displays up to 20 files with numbered list format
  - User's message is automatically combined with timestamp format: `"User message - TeleCode: YYYY-MM-DD HH:MM"`
  - Users can still provide a message directly: `/commit Fix bug` (timestamp still added)
  - Users can cancel the commit operation with `/cancel`
  - Improves commit message quality by encouraging descriptive messages

### Changed
- **Commit Message Format**: Commit messages now always include timestamp suffix
  - Format: `"User message - TeleCode: YYYY-MM-DD HH:MM"`
  - Timestamp is automatically appended to both direct and prompted commit messages
  - Maintains consistency with previous auto-commit format

---

## [0.1.16] - 2026-02-03

### 🔧 Fixed TSCON Path Detection and Session Handling

### Fixed
- **Enhanced TSCON Path Detection**: Added multiple path checks and diagnostics
  - Now checks `Sysnative`, `System32`, and `%windir%\System32` paths
  - Uses `where` command as fallback to locate tscon.exe
  - Provides detailed diagnostic information when tscon.exe is not found
  - Detects Windows edition to provide edition-specific error messages
- **Windows Home Edition Detection**: Improved error messages for Windows Home users
  - Clearly explains that TSCON is not available on Windows Home edition
  - Provides guidance on upgrading to Windows Pro if needed
  - Shows OS name and checked paths in diagnostic output
- **TSCON.exe Not Found Error**: Fixed "'tscon.exe' is not recognized" error on Windows
  - Added robust path detection that handles 32-bit/64-bit Windows correctly
  - Uses `Sysnative` path for 32-bit processes on 64-bit Windows (avoids System32 redirection)
  - Verifies tscon.exe exists before attempting to run it
  - Provides clear error messages when tscon.exe is missing
- **Session Detection**: Improved session ID detection for TSCON commands
  - Now queries active sessions using `query session` command before calling tscon
  - Falls back to SESSIONNAME environment variable if query fails
  - Defaults to "console" as last resort
  - Provides diagnostic information showing current sessions on failure
- **Error Diagnostics**: Enhanced error messages with comprehensive diagnostics
  - Shows TSCON path, session ID, and current sessions on failure
  - Better guidance for troubleshooting (RDP, Windows Home, permissions)
  - All batch files now provide consistent error reporting

### Changed
- **Batch Files**: Updated all TSCON batch files with improved path detection
  - `tscon_secure_lock.bat`: Now handles 32-bit/64-bit Windows correctly
  - `tscon_lock.bat`: Added session querying and better error handling
  - `tscon_lock_verbose.bat`: Enhanced diagnostics and path detection
- **Python Helper**: Updated `src/tscon_helper.py` with robust TSCON support
  - New `get_tscon_path()` function handles 32-bit/64-bit path resolution
  - Enhanced `get_session_name()` function queries sessions before using environment variable
  - Improved error messages with diagnostic information
  - All generated batch files now use the same robust path detection

### Technical Details
- On 64-bit Windows, 32-bit processes see System32 redirected to SysWOW64
- Using `Sysnative` allows 32-bit processes to access the real System32 directory
- Session ID must be queried dynamically as SESSIONNAME environment variable may not be set correctly
- TSCON requires administrator privileges and cannot work over RDP connections

---

## [0.1.15] - 2026-02-02

### 🎨 Fixed Icon Sizes for Production and Installer

### Fixed
- **Icon Sizes**: Fixed Windows ICO file to include all required sizes for proper display
  - Updated `icon.ico` to include: 16x16, 32x32, 48x48, 64x64, 128x128, 256x256 pixels
  - Icons now display correctly at all DPI levels and in all Windows contexts (taskbar, desktop, file explorer, installer)
  - Regenerated all icon files using updated `generate_icons.py` script
- **Wizard Images**: Added validation check for Inno Setup wizard images (wizard_large.bmp should be 164x314, wizard_small.bmp should be 55x55)

### Changed
- **`generate_icons.py`**: Updated `WINDOWS_SIZES` to include all standard Windows icon sizes (16, 32, 48, 64, 128, 256)
- **`assets/README.md`**: Updated documentation to reflect correct icon size requirements

### Technical Details
- Windows ICO files require multiple resolutions for optimal display at different DPI settings
- Missing sizes (64x64, 128x128) caused icons to appear blurry or pixelated in some contexts
- All icon files regenerated with proper multi-resolution support
- Icon generator script now validates wizard image sizes for Inno Setup installer

---

## [0.1.14] - 2026-02-02

### 🔧 Fixed Permission Errors for Installed Applications

### Fixed
- **Permission Denied Error**: Fixed `PermissionError` when running TeleCode installed in `Program Files` directory
  - Log files (`telecode.log`, `telecode_audit.log`) now write to user data directory instead of installation directory
  - Configuration file (`.env`) now stored in user data directory for installed applications
  - User preferences now stored in user data directory
  - Cross-platform support: Windows (`%APPDATA%\TeleCode`), macOS (`~/Library/Application Support/TeleCode`), Linux (`~/.config/TeleCode`)

### Changed
- **`setup_logging()`**: Now uses `get_user_data_dir()` for log file location
- **`_audit_log()`**: Now writes audit logs to user data directory
- **`UserPreferences`**: Now stores preferences in user data directory by default
- **`.env` file handling**: Now checks user data directory first, falls back to current directory for development
- **`load_dotenv()` calls**: Updated throughout codebase to use user data directory

### Added
- **`get_user_data_dir()`**: New function in `src/system_utils.py` for cross-platform user data directory
- **`get_env_path()`**: New helper function to get `.env` file path (user data dir or current dir)
- **`load_env_file()`**: New helper function to load `.env` from appropriate location

### Security
- ✅ All file operations now use user-writable directories
- ✅ No changes to security model or sandboxing
- ✅ Maintains backward compatibility with development mode

---

## [0.1.13] - 2026-02-02

### 🎯 Agent Button Routing & Screenshot Timing

### Fixed
- **Initial Screenshot Timing**: Changed from 10 seconds to 8 seconds for faster feedback
- **Button Routing**: Continue and Stop buttons now correctly target the specific agent chat when multiple are open
  - Buttons store `agent_id` in callback_data to identify which agent tab to target
  - Uses keyboard navigation (`Ctrl+{tab_number}`) to switch to the correct agent tab before executing actions
  - Falls back gracefully to current tab behavior if navigation fails

### Changed
- **`send_continue()`**: Now accepts optional `agent_id` parameter to target specific agent tab
- **`stop_generation()`**: Now accepts optional `agent_id` parameter to target specific agent tab
- **Button Callbacks**: Parse `agent_id` from callback_data format `ai_send_continue:{agent_id}` or `ai_stop:{agent_id}`
- **Result Data**: `send_prompt_and_wait()` now includes `agent_id` in result data for button routing

### Added
- **`_navigate_to_agent_tab()`**: New method to navigate to specific agent tabs using keyboard shortcuts
- **Agent Tab Navigation**: Automatic navigation to correct agent tab before executing continue/stop actions
- **Audit Document**: Created `docs/AGENT_BUTTON_ROUTING_AUDIT.md` with architecture analysis and implementation plan

### Security
- ✅ All operations remain within Cursor IDE (no external calls)
- ✅ Agent IDs are workspace-scoped and validated
- ✅ Graceful fallback if navigation fails

### Performance
- ✅ Fast keyboard shortcuts (< 1s total)
- ✅ No network calls required
- ✅ Minimal state overhead (single integer per button)

---

## [0.1.12] - 2026-02-02

### 🌐 Custom Domain - telecodebot.com

TeleCode is now available at **https://telecodebot.com**!

### Added

#### GitHub Pages Custom Domain
- **Custom domain**: Site now accessible at `telecodebot.com`
- **CNAME file**: Added for GitHub Pages custom domain configuration
- **SEO improvements**: Added Open Graph, Twitter cards, and meta tags
- **Canonical URL**: All pages now reference `telecodebot.com`
- **Favicon**: Added SVG favicon support

#### Updated `_config.yml`
- Added `url: "https://telecodebot.com"` for Jekyll
- Added social/SEO configuration
- Added more exclusions for cleaner builds

#### Updated `index.html`
- Added full SEO meta tags (description, keywords, author)
- Added Open Graph tags for social sharing
- Added Twitter Card meta tags
- Added canonical link
- Updated footer with User Guide link and copyright

### DNS Setup (for reference)
Custom domain requires these DNS records at registrar:
- A records pointing to GitHub Pages IPs
- CNAME record for `www` subdomain

---

## [0.1.11] - 2026-02-02

### 🎨 Website Redesign - Brand Identity & Modern UI

Complete redesign of the landing page with brand-aligned aesthetics and modern web design.

### Changed

#### New Landing Page Design
- **Brand Colors**: Emerald green palette matching the horse logo
- **Typography**: Crimson Pro (serif headlines), Instrument Sans (body), Space Mono (code)
- **Animations**: Floating gradient orbs, rising code particles, scroll reveal effects
- **Layout**: Full one-pager with smooth scroll navigation
- **Responsive**: Mobile-optimized with clean breakpoints

#### Visual Enhancements
- **Hero Section**: Large logo with gradient text, animated entry
- **Feature Cards**: Hover effects with animated top border
- **Terminal Demo**: Realistic terminal with blinking cursor
- **Step-by-Step**: Numbered circles with rotating dashed borders
- **Security Grid**: Icon cards with hover highlights
- **Open Source Card**: Dark gradient with GitHub CTA

#### Updated Content
- **Version**: Updated to v0.1.11
- **Checksums**: Updated SHA-256 hashes for main.py and requirements.txt
- **Download Links**: Platform-specific installers with OS icons
- **Features**: Highlighted OCR extraction as "NEW!"

### Technical
- Pure CSS animations (no JavaScript libraries)
- CSS custom properties for brand colors
- Intersection Observer for scroll reveals
- Dynamic particle generation via vanilla JS

---

## [0.1.11] - 2026-02-01

### 📸 OCR Text Extraction from Cursor Screenshots

TeleCode now uses OCR to extract the AI's text output from Cursor screenshots! When you click "📊 Check", you get both the screenshot AND the actual text summary - filtere to show only the explanation text (no code blocks).

### Added

#### OCR Text Extraction
- **Screenshot → Text**: Extracts readable text from Cursor screenshots using Tesseract OCR
- **Smart Filtering**: Automatically removes code blocks, file paths, diff markers, and technical syntax
- **Natural Language Only**: Keeps only the AI's explanations, summaries, and bullet points
- **Full Scrollability**: Long outputs sent as `.txt` document files that you can scroll through in Telegram

#### New `CursorAgentBridge` Methods
```python
agent.extract_text_from_screenshot(path, filter_code_blocks=True)  # OCR extraction
agent.capture_and_extract_text()  # Screenshot + OCR in one call
```

#### Smart Text Filtering
The OCR filter removes:
- Code blocks (indented code, syntax highlighted)
- File paths (`src/file.py`, `C:\path\to\file`)
- Diff markers (`+++`, `---`, `@@`, `+`, `-`)
- Line numbers (`1:`, `12:`, etc.)
- Import/export statements
- Function/class definitions
- HTML/XML tags
- UI elements and menu items

And keeps:
- Natural language explanations
- Bullet points and numbered lists
- Summary paragraphs
- Status messages

### Changed

#### "📊 Check" Button Enhanced
1. Shows git diff summary (file changes)
2. Captures screenshot of Cursor
3. Extracts text via OCR
4. Sends both screenshot AND extracted text separately
5. Long text (>3800 chars) sent as downloadable `.txt` file

### New Dependencies
- `pytesseract>=0.3.10` - Python wrapper for Tesseract OCR

### Setup Requirements
Tesseract OCR engine must be installed:
- **Windows**: Download from https://github.com/UB-Mannheim/tesseract/wiki
- **macOS**: `brew install tesseract`
- **Linux**: `sudo apt install tesseract-ocr`

---

## [0.1.10] - 2026-02-01

### 📸 Progress Screenshots While AI is Working

Added periodic screenshot updates so you can see what Cursor is doing while AI processes your prompt.

### Added

#### Initial Screenshot at 10 Seconds
- **Quick confirmation** that Cursor received and started processing your prompt
- Shows "AI Started!" with initial screenshot at 10 seconds
- Tells user updates will come every 1 minute

#### Progress Screenshot Updates
- **Every 1 minute** for the first 10 minutes of processing
- **Every 5 minutes** after 10 minutes until completion
- Screenshots sent as photo messages showing current Cursor state
- Includes file change count and elapsed time

#### Control Buttons on Progress Screenshots
Each progress screenshot now includes action buttons:
- **➡️ Continue** - Press the Continue button in Cursor (presses Enter)
- **🛑 Stop** - Stop the current generation (Ctrl+Shift+Backspace)

This allows users to:
- Approve Continue prompts when AI asks to proceed
- Stop long-running generations remotely
- Control AI workflow without switching to laptop

#### New `stop_generation()` Method
- Uses correct Cursor shortcut: **Ctrl+Shift+Backspace** (Cmd+Shift+Backspace on macOS)
- Separate from `cancel_action()` which uses Escape for dialogs
- Properly stops AI while it's actively generating

#### Fixed `send_continue()` Method
- **Old (wrong)**: Was typing "continue" as text
- **New (correct)**: Just presses Enter to activate the Continue button

#### Fixed AI Completion Detection - Now Tracks Content Changes
- **Old (wrong)**: Only checked if file LIST changed - missed content growing in same file
- **New (correct)**: Tracks `git diff --shortstat` to detect content changes
- Now monitors **total lines changed** (insertions + deletions)
- Single file being written over several minutes will NOT trigger false "completed"
- Logs now show: `[AI_PROMPT] Diff size changed: 500 -> 750 lines`
- Only declares complete when CONTENT stops changing for stable_threshold polls

### Fixed

#### Reject Button Now Uses Correct Undo Shortcut
- **Issue**: Reject button was using `Ctrl+Backspace` which doesn't undo in Cursor
- **Fix**: Now uses `Ctrl+Z` (or `Cmd+Z` on macOS) pressed 3 times to undo changes
- Added detailed `[REJECT]` logging for debugging
- Increased focus wait time to 0.5s for reliability
- Chat mode still uses Escape to dismiss proposals

#### How It Works
```
1 min:  📸 Progress Update (0 files)
2 min:  📸 Progress Update (2 files changed)
3 min:  📸 Progress Update (3 files changed)
...
10 min: 📸 Progress Update (5 files changed)
15 min: 📸 Progress Update (5 files changed)  ← 5 min interval now
20 min: 📸 Progress Update (6 files changed)
...
✅ Cursor AI completed! (6 files changed in 22min)
```

---

### 🤖 Fixed AI Prompt Completion Detection - Triggering Too Early

Fixed major issue where "Cursor AI Completed" message was sent prematurely while AI was still working.

### Fixed

#### AI Completion Detection Logic Overhaul
- **Issue**: AI was declared "completed" after only 6 seconds of stable file changes (3 polls × 2s)
- **Root cause**: `stable_threshold=3` and `poll_interval=2.0` was way too aggressive
- **Impact**: User would see "Completed" while Cursor was still actively processing

#### New Detection Parameters
| Parameter | Old Value | New Value | Effect |
|-----------|-----------|-----------|--------|
| `timeout` | 90s | 300s (5 min) | More time for complex prompts |
| `poll_interval` | 2s | 3s | Less aggressive polling |
| `stable_threshold` | 3 polls | 10 polls | Need 30s of stability, not 6s |
| `min_processing_time` | ❌ None | 15s | Won't complete before 15s elapsed |

#### Improved "Waiting" State Detection
- Old: Triggered after 20s with no changes
- New: Triggers after 120s with no changes (gives AI much more time)
- Added periodic status updates every 30 seconds while working

#### Better Logging
- Added `[AI_PROMPT]` prefixed logs throughout the flow:
  - When prompt is sent to Cursor
  - When new files are detected
  - Stability progress (every 5 polls)
  - When completion is declared
  - Timeout and error conditions

### Technical Details
```python
# Old (too aggressive):
stable_threshold=3, poll_interval=2.0  # 6 seconds = "done"

# New (proper detection):
stable_threshold=10, poll_interval=3.0, min_processing_time=15.0
# Requires: 30s of file stability AND at least 15s elapsed
```

---

### 🐛 Fixed Commands - Markdown Parse Error (400 Bad Request)

Fixed `/pwd`, `/info`, and `/cd` commands failing with 400 Bad Request error.

### Fixed

#### Markdown Parsing Issues in Multiple Commands
- **Issue**: Commands failed when git status contained `## main` (Telegram interpreted it as Markdown header)
- **Affected**: `/pwd`, `/info`, `/cd` - all commands using `get_current_info()` with Markdown parse mode
- **Fix**: 
  - `/pwd`: Removed `parse_mode="Markdown"` (no formatting needed)
  - `/info`: Wrapped workspace info in code block
  - `/cd`: Wrapped workspace info in code block
- This also fixes paths with underscores (like `my_project`) being incorrectly parsed as italic

---

### 📚 Documentation Audit & Update

Comprehensive documentation audit to ensure all public-facing docs are up to date with latest features and commands.

### Documentation Updates

#### All Docs
- Updated version references from v0.1.8/v0.1.9 to v0.1.10
- Added missing `/create` command (project creation wizard)
- Added missing `/cursor` command (IDE status and launch)

#### README.md
- Updated all download links to v0.1.10
- Added new "Project & IDE" commands section
- Fixed version badge and references

#### QUICK_START.md  
- Added `/create` and `/cursor open` to command reference

#### USER_GUIDE.md
- Added `/model`, `/models` to Quick Reference Card
- Added `/log`, `/branch`, `/pwd` to Quick Reference Card
- Now lists all 20+ available commands

#### CONTRIBUTING.md
- Updated project structure with all new source files
- Added: `cursor_agent.py`, `model_config.py`, `prompt_guard.py`, `token_vault.py`, `tray_icon.py`, `tscon_helper.py`
- Added docs folder files: `COMMANDS.md`, `SECURITY_AUDIT.md`
- Updated current version to v0.1.10

#### docs/COMMANDS.md
- Updated version footer to v0.1.10

---

### 🐛 Fixed System Tray Settings - Instance Lock Issue

Fixed a bug where clicking "Settings" from the system tray would show "TeleCode is already running!" instead of opening the config GUI.

### Fixed

#### System Tray Settings Now Works!
- **Fixed: Settings menu from tray** - Was trying to launch a new instance with `--config`, which triggered the single-instance lock check and failed
- **New `--settings-only` flag** - Opens config GUI without instance lock or starting the bot afterward
- **Proper stop flag handling** - Bot now properly checks `_stop_requested` flag and exits gracefully
- **Better settings message** - Shows "Settings Updated" message when editing from tray (not "TeleCode is Starting")

### Changed

#### New Startup Flag
- `--settings-only` / `-s` - Opens settings GUI only, for use from system tray
  - No instance lock check (safe when bot is already running)
  - No bot start after saving (bot is already running)
  - Proper message: "Some changes may require restart"

#### Improved Shutdown Flow
- Main loop now checks `_stop_requested` every second (was 1 hour!)
- "Stop TeleCode" from tray now actually stops the bot promptly
- Lock file properly released on all exit paths

#### Windows Improvements
- Settings GUI now launches with `pythonw.exe` when available (no console flash)
- Uses `CREATE_NO_WINDOW` flag to prevent console window

### Technical Details
- `main.py`: Added `--settings-only` argument that bypasses instance lock
- `bot.py`: Updated `_on_tray_settings` to use `--settings-only` instead of `--config`
- `bot.py`: Changed main loop from 3600s sleep to 1s with stop flag check
- `config_gui.py`: Different message for settings-only mode vs first-time setup

---

## [0.1.9] - 2026-02-01

### 🌍 Full Cross-Platform Support (Windows, macOS, Linux)

TeleCode now works on **all major platforms** with platform-specific optimizations for headless GUI automation!

### Added

#### Cross-Platform Window Management
- **Windows**: Win32 API (unchanged, works with TSCON)
- **macOS**: AppleScript integration for Cursor window focus/detection
- **Linux**: xdotool/wmctrl support for window management

#### Cross-Platform Credential Storage
- **Windows**: DPAPI (unchanged)
- **macOS**: Keychain via `security` command
- **Linux**: Secret Service (GNOME Keyring / KWallet) via `keyring` library
- **Fallback**: Encrypted file with machine-specific key (all platforms)

#### Linux Virtual Display Support (Headless Mode)
- **Xvfb integration** via `pyvirtualdisplay` for headless GUI automation
- Linux equivalent of Windows TSCON - run Cursor without a physical monitor
- System tray toggle to start/stop virtual display
- Automatic detection of Xvfb and pyvirtualdisplay availability
- Configuration GUI shows setup instructions if dependencies missing

#### Platform-Aware Keyboard Shortcuts
- Automatic detection: `Cmd` on macOS, `Ctrl` on Windows/Linux
- All keyboard automation now uses platform-appropriate modifiers
- Works correctly for: prompt sending, accept, reject, continue

#### Updated System Tray Menus
- **Windows**: TSCON Quick Lock & Secure Lock options
- **Linux**: Virtual Display toggle option
- **macOS**: Standard menu (caffeinate runs automatically)

#### New Dependencies
- `keyring>=24.0.0` - Cross-platform credential storage
- `pyvirtualdisplay>=3.0` - Linux virtual display (Xvfb wrapper)

### Changed

#### Configuration GUI
- Platform-specific sections:
  - Windows: TSCON Session Lock options
  - Linux: Virtual Display setup and status
  - macOS: Headless mode info (caffeinate, virtual display adapters)

#### System Status (`/status`)
- Now shows headless mode availability and status
- Platform-specific information displayed

### Platform Support Matrix

| Feature | Windows | macOS | Linux |
|---------|---------|-------|-------|
| Sleep Prevention | ✅ SetThreadExecutionState | ✅ caffeinate | ✅ systemd-inhibit |
| Lock Detection | ✅ User32 API | ✅ Quartz | ✅ DE-specific |
| Window Focus | ✅ Win32 API | ✅ AppleScript | ✅ xdotool/wmctrl |
| Headless GUI | ✅ TSCON | ⚠️ VNC/Adapter | ✅ Xvfb |
| Credential Storage | ✅ DPAPI | ✅ Keychain | ✅ Secret Service |

### Linux Setup

```bash
# Install Xvfb for headless mode
sudo apt install xvfb

# Install Python dependencies
pip install pyvirtualdisplay keyring

# Optional: Install xdotool for window management
sudo apt install xdotool
```

### macOS Notes

- Headless GUI automation requires external setup (VNC or virtual display adapter)
- `caffeinate` prevents sleep automatically (TeleCode handles this)
- For true headless: use BetterDummy, Deskreen, or hardware HDMI adapter

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
- **Reject** now uses **Ctrl+Z** (undo) for Agent mode
- **Reject** uses **Escape** for Chat mode (unchanged)

### Changed

#### Command Renames
- **`/accept`** → **`/commit`** - Now clearly indicates this is a git action
- Git operations are now separate from Cursor operations

#### Button Labels
- **✅ Accept** - Accept AI changes in Cursor (Ctrl+Enter)
- **❌ Reject** - Reject AI changes in Cursor (Ctrl+Z / Escape)

#### New Commands
- `/ai accept` - Accept AI changes via Ctrl+Enter
- `/ai reject` - Reject AI changes via Ctrl+Z (agent) or Escape (chat)

### Migration
| Old Command | New Command | Action |
|-------------|-------------|--------|
| `/accept` | `/commit` | Git commit |
| `/ai accept` | `/ai accept` | Accept in Cursor (Ctrl+Enter) |
| `/ai revert` | `/ai reject` | Reject in Cursor (Ctrl+Z / Escape) |

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
- **➡️ Continue** - Press the Continue button when AI pauses
  - Useful when AI pauses or asks to continue
  - Presses Enter in Cursor to activate Continue button

#### New `CursorAgentBridge` Methods
```python
agent.approve_run()        # Approve terminal command (Enter key)
agent.cancel_action()      # Cancel pending action (Escape key)
agent.approve_web_search() # Approve web search (Enter key)
agent.send_continue()      # Press Continue button (Enter key)
agent.stop_generation()    # Stop generation (Ctrl+Shift+Backspace)
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
| `/ai reject` | Reject AI changes in Cursor (Ctrl+Z / Escape) |
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

- [x] ~~OCR: Screenshot Cursor output and extract text~~ ✅ Done in v0.1.11
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

