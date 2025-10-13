#!/usr/bin/env bash
# Launches both the FastAPI backend and Next.js frontend for local development.
# Usage:
#   ./scripts/run_analyzer.sh
# Environment overrides:
#   BACKEND_HOST, BACKEND_PORT, FRONTEND_HOST, FRONTEND_PORT,
#   NEXT_PUBLIC_API_BASE_URL, API_BASE_URL, VENV_DIR
set -euo pipefail

# Resolve important paths relative to repository root so the script works from anywhere.
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

# Check that required tooling is installed before proceeding.
if ! command -v uvicorn >/dev/null 2>&1; then
  echo "uvicorn is not installed in the active virtual environment."
  echo "Run: pip install -r backend/requirements.txt"
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to start the frontend. Please install Node.js/npm."
  exit 1
fi

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# Trap handler ensures both child processes exit cleanly on exit or Ctrl+C.
cleanup() {
  local exit_code=$?
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "${BACKEND_PID}" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "${FRONTEND_PID}" 2>/dev/null || true
  fi
  exit "${exit_code}"
}
trap cleanup EXIT INT TERM

cd "${REPO_ROOT}"

echo "Starting FastAPI backend on http://${BACKEND_HOST}:${BACKEND_PORT}"
# Background the server so the script can continue launching the frontend.
uvicorn backend.app.main:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}" --reload &
BACKEND_PID=$!

cd "${REPO_ROOT}/frontend"

export NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://${BACKEND_HOST}:${BACKEND_PORT}}"
export API_BASE_URL="${API_BASE_URL:-${NEXT_PUBLIC_API_BASE_URL}}"

if [[ ! -d node_modules ]]; then
  echo "Installing frontend dependencies..."
  npm install
fi

# Next.js dev server runs in watch mode and proxies API calls to the backend.
echo "Starting Next.js frontend on http://${FRONTEND_HOST}:${FRONTEND_PORT}"
npm run dev -- --hostname "${FRONTEND_HOST}" --port "${FRONTEND_PORT}" &
FRONTEND_PID=$!

cd "${REPO_ROOT}"

echo
echo "Frontend available at http://${FRONTEND_HOST}:${FRONTEND_PORT}"
echo "Backend API available at http://${BACKEND_HOST}:${BACKEND_PORT}"
echo "Press Ctrl+C to stop both services."
echo

wait "${BACKEND_PID}" "${FRONTEND_PID}"
