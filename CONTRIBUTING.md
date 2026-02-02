# Contributing to TeleCode

Thank you for your interest in contributing to TeleCode! This document provides guidelines for contributing.

---

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

---

## How to Contribute

### Reporting Bugs

1. **Check existing issues** to avoid duplicates
2. **Create a new issue** with:
   - Clear title describing the bug
   - Steps to reproduce
   - Expected vs actual behavior
   - Your environment (OS, Python version, etc.)
   - Relevant logs (redact any secrets!)

### Security Vulnerabilities

**Do NOT open public issues for security vulnerabilities.**

Instead, please email security@example.com with:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fixes

### Feature Requests

1. **Check existing issues/discussions**
2. **Create a discussion** in the Ideas category
3. Describe:
   - The problem you're trying to solve
   - Your proposed solution
   - Alternative approaches you've considered

### Pull Requests

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes** following our coding standards
4. **Add tests** if applicable
5. **Update documentation** if needed
6. **Commit with clear messages**: `git commit -m "Add amazing feature"`
7. **Push to your fork**: `git push origin feature/amazing-feature`
8. **Open a Pull Request**

---

## Development Setup

### Prerequisites

- Python 3.10+
- Git
- FFmpeg (for voice features)

### Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/telecode.git
cd telecode

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install pytest black flake8 mypy
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test
pytest tests/test_security.py
```

### Code Formatting

We use Black for formatting:

```bash
# Format all files
black src/ tests/

# Check formatting
black --check src/ tests/
```

### Linting

```bash
# Run flake8
flake8 src/ tests/

# Run mypy for type checking
mypy src/
```

### Update Checksum

```bash
# Run if main.py or requirements.txt is updated
(Get-FileHash main.py -Algorithm SHA256).Hash
```

---

## Coding Standards

### Python Style

- Follow PEP 8
- Use type hints where practical
- Write docstrings for public functions/classes
- Keep functions focused and small

### Security Considerations

**This is a security-focused project.** All contributions must:

1. **Validate all inputs** from Telegram
2. **Use the SecuritySentinel** for path validation
3. **Never execute arbitrary shell commands**
4. **Never log sensitive information** (tokens, user IDs in errors)
5. **Add security tests** for new features

### Documentation

- Update docstrings for changed functions
- Update README.md for new features
- Add entries to CHANGELOG.md

---

## Project Structure

```
telecode/
├── src/
│   ├── __init__.py        # Package info
│   ├── bot.py             # Main Telegram bot
│   ├── security.py        # Security layer
│   ├── cli_wrapper.py     # Git/Cursor CLI
│   ├── config_gui.py      # Setup GUI
│   ├── cursor_agent.py    # Cursor automation bridge
│   ├── model_config.py    # AI model configuration
│   ├── prompt_guard.py    # Prompt injection defense
│   ├── system_utils.py    # OS utilities
│   ├── token_vault.py     # Encrypted token storage
│   ├── tray_icon.py       # System tray icon
│   ├── tscon_helper.py    # Windows TSCON lock
│   └── voice_processor.py # Voice transcription
├── docs/
│   ├── COMMANDS.md        # Command reference
│   ├── SECURITY.md        # Security overview
│   ├── SECURITY_AUDIT.md  # Full security audit
│   └── TSCON.md           # Windows headless mode
├── build/                 # Build scripts for all platforms
├── tests/                 # Test files
├── main.py                # Entry point
├── requirements.txt
├── setup.bat / setup.sh
└── README.md
```

---

## Areas for Contribution

### Good First Issues

- Documentation improvements
- Adding more tests
- Fixing typos
- Improving error messages

### Wanted Features

- OCR for Cursor output screenshots
- Multi-repo support
- Inline keyboard confirmations
- Web status dashboard

### Performance

- Optimize voice processing
- Reduce memory usage
- Faster startup time

---

## Versioning

TeleCode follows [Semantic Versioning](https://semver.org/):

| Change Type | Version Increment | Example |
|-------------|-------------------|---------|
| Bug fixes, minor improvements | Patch | v0.1.0 → v0.1.1 |
| New features | Minor | v0.1.x → v0.2.0 |

Current version: **v0.1.10**

---

## Release Process

1. Update version in `src/__init__.py`
2. Update CHANGELOG.md with new version section
3. Create release commit: `git commit -m "Release vX.Y.Z"`
4. Tag release: `git tag vX.Y.Z`
5. Push: `git push origin main --tags`
6. Create GitHub Release with notes from CHANGELOG

---

## Questions?

- Open a Discussion on GitHub
- Check existing issues and docs first

Thank you for contributing to TeleCode! 🚀

