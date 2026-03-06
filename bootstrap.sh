#!/usr/bin/env bash
# bootstrap.sh — KeroMDizer setup for Ubuntu 24.04
# Checks dependencies, installs missing packages, creates venv, installs dev requirements.

set -euo pipefail

VENV_DIR=".venv"
MIN_PYTHON_MINOR=11  # Requires Python 3.11+

# ── Colours ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}  ✔${RESET}  $*"; }
warn() { echo -e "${YELLOW}  !${RESET}  $*"; }
info() { echo -e "${CYAN}  →${RESET}  $*"; }
fail() { echo -e "${RED}  ✘${RESET}  $*" >&2; exit 1; }

echo ""
echo -e "${CYAN}KeroMDizer Bootstrap${RESET}"
echo "────────────────────────────────────"

# ── 1. Check we're on Ubuntu ───────────────────────────────────────────────────
if ! grep -qi ubuntu /etc/os-release 2>/dev/null; then
    warn "This script is designed for Ubuntu 24.04. Proceeding anyway — YMMV."
fi

# ── 2. Check for apt (needed to install system packages) ──────────────────────
if ! command -v apt-get &>/dev/null; then
    fail "apt-get not found. This script requires an Ubuntu/Debian system."
fi

# ── 3. Check Python 3.11+ ─────────────────────────────────────────────────────
PYTHON_BIN=""
for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" -c 'import sys; print(sys.version_info.minor)')
        major=$("$candidate" -c 'import sys; print(sys.version_info.major)')
        if [[ "$major" -eq 3 && "$version" -ge "$MIN_PYTHON_MINOR" ]]; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON_BIN" ]]; then
    info "Python 3.11+ not found — installing python3.12 via apt..."
    sudo apt-get update -qq
    sudo apt-get install -y python3.12
    PYTHON_BIN="python3.12"
fi

PY_VERSION=$("$PYTHON_BIN" --version)
ok "Python: $PY_VERSION ($PYTHON_BIN)"

# ── 4. Check python3-venv ──────────────────────────────────────────────────────
if ! "$PYTHON_BIN" -c 'import venv' &>/dev/null; then
    info "python3-venv not available — installing..."
    # Derive package name from binary (e.g. python3.12 -> python3.12-venv)
    PKG="${PYTHON_BIN}-venv"
    sudo apt-get install -y "$PKG" || sudo apt-get install -y python3-venv
fi
ok "venv module available"

# ── 5. Create virtual environment ─────────────────────────────────────────────
if [[ -d "$VENV_DIR" ]]; then
    warn "Virtual environment '$VENV_DIR' already exists — skipping creation."
else
    info "Creating virtual environment in '$VENV_DIR'..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    ok "Virtual environment created"
fi

# ── 6. Install dev requirements ────────────────────────────────────────────────
info "Installing dev requirements (pytest)..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r requirements-dev.txt
ok "Dev requirements installed"

# ── 7. Verify installation ─────────────────────────────────────────────────────
PYTEST_VERSION=$("$VENV_DIR/bin/pytest" --version 2>&1)
ok "pytest: $PYTEST_VERSION"

# ── 8. Quick test run ──────────────────────────────────────────────────────────
info "Running test suite to verify setup..."
if "$VENV_DIR/bin/pytest" tests/ -q 2>&1; then
    ok "All tests pass"
else
    fail "Tests failed — check output above."
fi

# ── Done — print usage instructions ───────────────────────────────────────────
echo ""
echo "────────────────────────────────────"
echo -e "${GREEN}Setup complete!${RESET}"
echo ""
echo "Activate the virtual environment:"
echo ""
echo -e "  ${CYAN}source ${VENV_DIR}/bin/activate${RESET}"
echo ""
echo "Then convert a ChatGPT export:"
echo ""
echo -e "  ${CYAN}python keromdizer.py /path/to/chatgpt-export/ --output ./output${RESET}"
echo ""
echo "Options:"
echo "  --output <dir>   Output directory for markdown files  (default: ./output)"
echo "  --dry-run        Preview what would be written without writing files"
echo ""
echo "Examples:"
echo -e "  ${CYAN}python keromdizer.py ~/Downloads/chatgpt-export/${RESET}"
echo -e "  ${CYAN}python keromdizer.py ~/Downloads/chatgpt-export/ --output ~/notes/chatgpt --dry-run${RESET}"
echo ""
echo "Run tests:"
echo -e "  ${CYAN}pytest tests/ -v${RESET}"
echo ""
echo "Or launch the interactive TUI:"
echo ""
echo -e "  ${CYAN}python tui.py${RESET}"
echo ""
