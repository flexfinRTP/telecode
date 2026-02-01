#!/bin/bash
# ============================================
# TeleCode v0.1 - Unix/Mac Setup Script
# ============================================
# This script will:
# 1. Check for Python 3.10+
# 2. Check for Git
# 3. Check for FFmpeg (optional, for voice)
# 4. Create virtual environment
# 5. Install dependencies
# 6. Launch the configuration GUI
# ============================================

set -e

echo ""
echo "========================================"
echo "  TeleCode v0.1 Setup Script"
echo "  Remote Cursor Commander"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check for Python
echo "[1/5] Checking for Python..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    echo -e "      ${GREEN}Found Python $PYTHON_VERSION${NC}"
elif command -v python &> /dev/null; then
    PYTHON_CMD=python
    PYTHON_VERSION=$(python --version 2>&1 | cut -d' ' -f2)
    echo -e "      ${GREEN}Found Python $PYTHON_VERSION${NC}"
else
    echo -e "      ${RED}ERROR: Python is not installed${NC}"
    echo "      Please install Python 3.10+ from https://www.python.org/downloads/"
    exit 1
fi

# Check for Git
echo "[2/5] Checking for Git..."
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version | cut -d' ' -f3)
    echo -e "      ${GREEN}Found Git $GIT_VERSION${NC}"
else
    echo -e "      ${YELLOW}WARNING: Git is not installed. Git features will not work.${NC}"
fi

# Check for FFmpeg
echo "[3/5] Checking for FFmpeg (optional, for voice)..."
if command -v ffmpeg &> /dev/null; then
    echo -e "      ${GREEN}FFmpeg found - Voice features enabled!${NC}"
else
    echo -e "      ${YELLOW}FFmpeg not found. Voice features will be disabled.${NC}"
    echo "      Install with: brew install ffmpeg (Mac) or apt install ffmpeg (Linux)"
fi

# Create virtual environment
echo "[4/5] Setting up virtual environment..."
if [ ! -d "venv" ]; then
    $PYTHON_CMD -m venv venv
    echo "      Created new virtual environment"
else
    echo "      Using existing virtual environment"
fi

# Activate and install
echo "[5/5] Installing dependencies..."
source venv/bin/activate

pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Failed to install dependencies${NC}"
    exit 1
fi

echo ""
echo "========================================"
echo -e "  ${GREEN}Setup Complete!${NC}"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Get a Bot Token from @BotFather on Telegram"
echo "  2. Get your User ID from @userinfobot on Telegram"
echo "  3. Run './start.sh' to launch TeleCode"
echo ""
echo "Launching configuration GUI..."
echo ""

$PYTHON_CMD main.py --config

