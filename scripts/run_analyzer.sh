#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_VENV_DIR="${REPO_ROOT}/.venv"
VENV_DIR="${VENV_DIR:-${DEFAULT_VENV_DIR}}"

VENV_ACTIVATE="${VENV_DIR}/bin/activate"

if [[ ! -f "${VENV_ACTIVATE}" ]]; then
  echo "Virtual environment not found at ${VENV_DIR}."
  echo "Run scripts/setup_env.sh first (optionally pass a custom path)."
  exit 1
fi

# shellcheck disable=SC1091
source "${VENV_ACTIVATE}"

cd "${REPO_ROOT}"
python analyze_missions.py "$@"
