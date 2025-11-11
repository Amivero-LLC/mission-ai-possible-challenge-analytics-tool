#!/usr/bin/env bash
# Coordinated entrypoint for Railway deployments.
# Usage examples:
#   ./start.sh backend        # Run the FastAPI backend (default)
#   ./start.sh frontend       # Serve the Next.js frontend
#   SERVICE_ROLE=frontend ./start.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"

choose_role() {
  if [[ -n "${1:-}" ]]; then
    echo "${1}"
  elif [[ -n "${SERVICE_ROLE:-}" ]]; then
    echo "${SERVICE_ROLE}"
  elif [[ -n "${APP_ROLE:-}" ]]; then
    echo "${APP_ROLE}"
  elif [[ -n "${RAILWAY_SERVICE_NAME:-}" ]]; then
    echo "${RAILWAY_SERVICE_NAME}"
  else
    echo "backend"
  fi
}

ROLE_RAW="$(choose_role "${1:-}")"
ROLE_LOWER="$(echo "${ROLE_RAW}" | tr '[:upper:]' '[:lower:]')"

# Allow Railpack/Railway service names that don't literally include backend/frontend.
normalize_role() {
  local value="${1}"
  if [[ "${value}" == *frontend* ]]; then
    echo "frontend"
    return
  fi
  if [[ "${value}" == *backend* ]]; then
    echo "backend"
    return
  fi
  if [[ -n "${RAILPACK_SERVICE_TYPE:-}" ]]; then
    local pack_type
    pack_type="$(echo "${RAILPACK_SERVICE_TYPE}" | tr '[:upper:]' '[:lower:]')"
    if [[ "${pack_type}" == *frontend* ]]; then
      echo "frontend"
      return
    fi
    if [[ "${pack_type}" == *backend* ]]; then
      echo "backend"
      return
    fi
  fi
  if [[ -n "${DEFAULT_SERVICE_ROLE:-}" ]]; then
    echo "${DEFAULT_SERVICE_ROLE}"
    return
  fi
  echo "backend"
}

ROLE="$(normalize_role "${ROLE_LOWER}")"
if [[ "${ROLE}" == "backend" && "${ROLE_LOWER}" != *backend* && "${ROLE_LOWER}" != *frontend* ]]; then
  echo "Detected unrecognized role \"${ROLE_RAW}\" – defaulting to backend. Set SERVICE_ROLE to backend or frontend to override." >&2
fi

export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"

detect_python_bin() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    echo "${PYTHON_BIN}"
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

  if [[ ! -d node_modules ]]; then
    echo "Installing frontend dependencies"
    if [[ -f package-lock.json ]]; then
      npm ci
    else
      npm install
    fi
  fi

  local needs_build=0
  if [[ ! -d .next ]]; then
    needs_build=1
  fi
  if [[ "${FORCE_FRONTEND_BUILD:-0}" == "1" ]]; then
    needs_build=1
  fi

  if [[ "${SKIP_FRONTEND_BUILD:-0}" != "1" && "${needs_build}" -eq 1 ]]; then
    echo "Building Next.js app"
    npm run build
  fi

  exec npm run start -- --hostname "${host}" --port "${port}"
}

if [[ "${ROLE}" == *frontend* ]]; then
  start_frontend
elif [[ "${ROLE}" == *backend* ]]; then
  start_backend
else
  echo "Unsupported role \"${ROLE_RAW}\". Set SERVICE_ROLE to backend or frontend." >&2
  exit 1
fi
