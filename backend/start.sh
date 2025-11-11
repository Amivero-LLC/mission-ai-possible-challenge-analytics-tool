#!/usr/bin/env bash
set -euo pipefail

# Backend-specific start script for Railway deployment
# This runs from the /backend directory when Root Directory is set

echo "Starting backend service..."

# Run Alembic migrations
if [[ "${SKIP_DB_MIGRATIONS:-0}" != "1" ]]; then
  if command -v alembic >/dev/null 2>&1; then
    echo "Running Alembic migrations..."
    alembic upgrade head
  else
    echo "Alembic not found, skipping migrations"
  fi
fi

# Start Uvicorn
HOST="${BACKEND_HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "Starting Uvicorn on ${HOST}:${PORT}"
exec uvicorn app.main:app --host "${HOST}" --port "${PORT}"
