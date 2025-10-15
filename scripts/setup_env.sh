#!/usr/bin/env bash
# Bootstraps a Python virtual environment for the analytics stack.
# Usage:
#   ./scripts/setup_env.sh [custom_venv_path]
# Environment overrides:
#   VENV_DIR, PYTHON_BIN
set -euo pipefail

# Determine repository root even if script is called via symlink.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Allow overriding venv location via first argument or VENV_DIR env var.
DEFAULT_VENV_DIR="${REPO_ROOT}/.venv"
VENV_DIR="${VENV_DIR:-${1:-${DEFAULT_VENV_DIR}}}"

PYTHON_BIN="${PYTHON_BIN:-python3}"

# Fall back to `python` if `python3` is unavailable, otherwise abort with guidance.
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "Error: could not find python interpreter. Set PYTHON_BIN to your Python executable." >&2
    exit 1
  fi
fi

echo "Using Python interpreter: ${PYTHON_BIN}"
echo "Creating virtual environment at: ${VENV_DIR}"
"${PYTHON_BIN}" -m venv "${VENV_DIR}"

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

echo "Upgrading pip..."
pip install --upgrade pip

# Install project dependencies. Prefer repository root requirements if present;
# otherwise fallback to the minimal runtime required by legacy scripts.
if [[ -f "${REPO_ROOT}/requirements.txt" ]]; then
  echo "Installing dependencies from requirements.txt..."
  pip install -r "${REPO_ROOT}/requirements.txt"
else
  echo "Installing required packages..."
  pip install requests
fi

echo
echo "Virtual environment ready."
echo "To activate it later, run: source \"${VENV_DIR}/bin/activate\""
