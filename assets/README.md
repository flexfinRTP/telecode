# TeleCode Assets

This folder contains icons and branding assets for TeleCode.

## Required Icons

Before building installers, you need to create these icon files:

### icon.ico (Windows)
- Size: Multi-resolution ICO containing 16x16, 32x32, 48x48, 64x64, 128x128, 256x256
- Format: ICO (multi-resolution)
- Used by: Windows EXE and installer
- **Note**: All sizes are required for proper display at different DPI levels and contexts

### icon.icns (macOS)
- Size: Multi-resolution ICNS containing 16x16 to 1024x1024
- Format: ICNS
- Used by: macOS .app bundle

### icon.png (Linux/General)
- Size: 512x512 or 1024x1024
- Format: PNG with transparency
- Used by: Linux desktop entries, GitHub, documentation

## Creating Icons

### Option 1: Online Tool
1. Create a 1024x1024 PNG logo
2. Use https://icoconvert.com/ for ICO
3. Use https://cloudconvert.com/png-to-icns for ICNS

### Option 2: ImageMagick (CLI)
```bash
# From a 1024x1024 source.png:
convert source.png -resize 256x256 icon.ico
# For macOS, use iconutil or online converter
```

## Logo Design Guidelines

The TeleCode logo should convey:
- 📡 Remote connectivity (Telegram)
- 💻 Code/Terminal (Cursor IDE)
- 🔒 Security (sandboxed access)
- 🚀 Speed and automation

Suggested design: A stylized "T" or terminal cursor icon with a Telegram-style paper plane integrated.

