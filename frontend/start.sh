#!/usr/bin/env bash
set -euo pipefail

# Frontend-specific start script for Railway deployment
# This runs from the /frontend directory when Root Directory is set

echo "Starting frontend service..."

HOST="${FRONTEND_HOST:-0.0.0.0}"
PORT="${PORT:-3000}"

# Ensure build artifacts exist
if [[ ! -d .next || ! -f .next/BUILD_ID ]]; then
  echo "ERROR: .next/ build artifacts missing."
  echo "Ensure 'npm run build' completed successfully during the build phase."
  exit 1
fi

echo "Starting Next.js production server on ${HOST}:${PORT}"
exec npm run start -- --hostname "${HOST}" --port "${PORT}"
