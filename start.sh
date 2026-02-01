#!/bin/bash
# ============================================
# TeleCode v0.1 - Quick Start Script (Unix/Mac)
# ============================================

echo "Starting TeleCode..."
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Determine Python command
if command -v python3 &> /dev/null; then
    python3 main.py
else
    python main.py
fi

