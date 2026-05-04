#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

ensure_backend_venv
ensure_backend_env
ensure_frontend_env

echo "Applying backend migrations..."
backend_manage migrate >/dev/null

echo "Starting Django development server..."
(
  cd "$BACKEND_DIR"
  backend_python manage.py runserver "$BACKEND_HOST:$BACKEND_PORT"
) &
BACKEND_PID=$!

echo "Starting Vite development server..."
(
  cd "$FRONTEND_DIR"
  npm run dev:host
) &
FRONTEND_PID=$!

echo
echo "Development stack is up."
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:$BACKEND_PORT"
echo
echo "Press Ctrl+C to stop both services."

wait "$BACKEND_PID" "$FRONTEND_PID"
