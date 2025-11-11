#!/usr/bin/env bash
# Coordinated entrypoint for Railway deployments.
# Usage examples:
#   ./start.sh backend        # Run the FastAPI backend (default)
#   ./start.sh frontend       # Serve the Next.js frontend
#   SERVICE_ROLE=frontend ./start.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"

is_railway_env() {
  if [[ -n "${RAILWAY_PROJECT_ID:-}" || -n "${RAILWAY_ENVIRONMENT_ID:-}" || -n "${RAILWAY_ENVIRONMENT:-}" || -n "${RAILWAY_SERVICE_NAME:-}" || -n "${RAILWAY_SERVICE_SLUG:-}" || -n "${RAILPACK_SERVICE_TYPE:-}" ]]; then
    return 0
  fi
  return 1
}

normalize_role_label() {
  local raw="${1:-}"
  if [[ -z "${raw}" ]]; then
    return 1
  fi
  local lower
  lower="$(echo "${raw}" | tr '[:upper:]' '[:lower:]')"
  lower="${lower// /}"
  case "${lower}" in
    backend|api|server|fastapi|python)
      echo "backend"
      return 0
      ;;
    frontend|front-end|next|nextjs|web|ui|client)
      echo "frontend"
      return 0
      ;;
  esac
  if [[ "${lower}" == *"backend"* || "${lower}" == *"api"* ]]; then
    echo "backend"
    return 0
  fi
  if [[ "${lower}" == *"frontend"* || "${lower}" == *"next"* || "${lower}" == *"web"* || "${lower}" == *"client"* ]]; then
    echo "frontend"
    return 0
  fi
  return 1
}

resolve_role() {
  local candidate
  if candidate="$(normalize_role_label "${1:-}")"; then
    echo "${candidate}"
    return 0
  fi
  if candidate="$(normalize_role_label "${SERVICE_ROLE:-}")"; then
    echo "${candidate}"
    return 0
  fi
  if candidate="$(normalize_role_label "${APP_ROLE:-}")"; then
    echo "${candidate}"
    return 0
  fi
  if candidate="$(normalize_role_label "${RAILPACK_SERVICE_TYPE:-}")"; then
    echo "${candidate}"
    return 0
  fi
  if candidate="$(normalize_role_label "${RAILWAY_SERVICE_NAME:-}")"; then
    echo "${candidate}"
    return 0
  fi
  if candidate="$(normalize_role_label "${RAILWAY_SERVICE_SLUG:-}")"; then
    echo "${candidate}"
    return 0
  fi
  if candidate="$(normalize_role_label "${DEFAULT_SERVICE_ROLE:-}")"; then
    echo "${candidate}"
    return 0
  fi
  echo ""
}

ROLE="$(resolve_role "${1:-}")"
if [[ -z "${ROLE}" ]]; then
  fallback_raw="${DEFAULT_SERVICE_ROLE:-backend}"
  if ! fallback_normalized="$(normalize_role_label "${fallback_raw}")"; then
    fallback_normalized="backend"
  fi
  ROLE="${fallback_normalized}"
  echo "Warning: SERVICE_ROLE not set. Defaulting to \"${ROLE}\". Set SERVICE_ROLE to backend or frontend for deterministic deployments." >&2
  if is_railway_env; then
    echo >&2 "Tip: add SERVICE_ROLE to your Railpack service env vars (see README.md - Railway / Railpack Deployment)." 
  fi
fi

export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"

detect_python_bin() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    echo "${PYTHON_BIN}"
    return
  fi
  if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    echo "${REPO_ROOT}/.venv/bin/python"
    return
  fi
  if [[ -x "${REPO_ROOT}/venv/bin/python" ]]; then
    echo "${REPO_ROOT}/venv/bin/python"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return
  fi
  if command -v python >/dev/null 2>&1; then
    echo "python"
    return
  fi
  echo ""
}

start_backend() {
  local python_bin
  python_bin="$(detect_python_bin)"
  if [[ -z "${python_bin}" ]]; then
    echo "Error: python interpreter not found. Set PYTHON_BIN to the appropriate executable." >&2
    exit 1
  fi
  if ! "${python_bin}" -c "import uvicorn" >/dev/null 2>&1; then
    echo "uvicorn is not installed in ${python_bin}. Install backend dependencies during the Railpack build phase." >&2
    exit 1
  fi
  local host="${BACKEND_HOST:-0.0.0.0}"
  local port="${BACKEND_PORT:-8000}"

  if [[ -n "${PORT:-}" ]]; then
    port="${PORT}"
  fi
  export BACKEND_PORT="${port}"

  echo "Starting backend on ${host}:${port}"

  if [[ "${SKIP_DB_MIGRATIONS:-0}" != "1" ]]; then
    cd "${REPO_ROOT}/backend"
    if command -v alembic >/dev/null 2>&1; then
      echo "Running Alembic migrations"
      alembic upgrade head
    elif "${python_bin}" -m alembic --help >/dev/null 2>&1; then
      echo "Running Alembic migrations through python -m"
      "${python_bin}" -m alembic upgrade head
    else
      echo "Alembic not available; skipping migrations" >&2
    fi
    cd "${REPO_ROOT}" || exit 1
  fi

  exec "${python_bin}" -m uvicorn backend.app.main:app --host "${host}" --port "${port}"
}

start_frontend() {
  local host="${FRONTEND_HOST:-0.0.0.0}"
  local port_override="${PORT:-}"
  local port="${FRONTEND_PORT:-3000}"

  if [[ -n "${port_override}" ]]; then
    port="${port_override}"
  fi
  export FRONTEND_PORT="${port}"
  export PORT="${port}"

  echo "Starting frontend on ${host}:${port}"

  cd "${REPO_ROOT}/frontend"

  if ! command -v npm >/dev/null 2>&1; then
    echo "npm is not available in PATH. Install Node.js during the Railpack build phase." >&2
    exit 1
  fi

  export NODE_ENV="${NODE_ENV:-production}"
  export NEXT_TELEMETRY_DISABLED="${NEXT_TELEMETRY_DISABLED:-1}"

  local allow_install="${ALLOW_RUNTIME_NPM_INSTALL:-}"
  if [[ -z "${allow_install}" ]]; then
    if is_railway_env; then
      allow_install=0
    else
      allow_install=1
    fi
  fi

  if [[ ! -d node_modules ]]; then
    if [[ "${allow_install}" != "1" ]]; then
      echo "node_modules/ is missing. Install dependencies during the Railpack build phase or set ALLOW_RUNTIME_NPM_INSTALL=1 if you intentionally want runtime installs." >&2
      exit 1
    fi
    echo "Installing frontend dependencies"
    if [[ -f package-lock.json ]]; then
      npm ci --omit=dev
    else
      npm install --omit=dev
    fi
  fi

  local needs_build=0
  if [[ ! -d .next || ! -f .next/BUILD_ID ]]; then
    needs_build=1
  fi
  if [[ "${FORCE_FRONTEND_BUILD:-0}" == "1" ]]; then
    needs_build=1
  fi

  if [[ "${SKIP_FRONTEND_BUILD:-0}" != "1" && "${needs_build}" -eq 1 ]]; then
    local allow_build="${ALLOW_RUNTIME_NEXT_BUILD:-}"
    if [[ -z "${allow_build}" ]]; then
      if is_railway_env; then
        allow_build=0
      else
        allow_build=1
      fi
    fi
    if [[ "${allow_build}" != "1" ]]; then
      echo ".next/ build artifacts missing. Build the frontend during the Railpack build phase or set ALLOW_RUNTIME_NEXT_BUILD=1 to compile at startup." >&2
      exit 1
    fi
    echo "Building Next.js app"
    npm run build
  fi

  exec npm run start -- --hostname "${host}" --port "${port}"
}

if [[ "${ROLE}" == "frontend" ]]; then
  start_frontend
elif [[ "${ROLE}" == "backend" ]]; then
  start_backend
else
  echo "Unsupported role \"${ROLE}\". Set SERVICE_ROLE to backend or frontend." >&2
  exit 1
fi
