#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-4173}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
WORKERS="${GUNICORN_WORKERS:-2}"
USE_GUNICORN="${USE_GUNICORN:-1}"
subcommand="${1:-start}"
shift || true

cleanup_foreground() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup_foreground EXIT INT TERM

ensure_backend_venv
ensure_backend_env
ensure_frontend_env
ensure_runtime_dirs
cleanup_stale_pid_file "$BACKEND_PID_FILE"
cleanup_stale_pid_file "$FRONTEND_PID_FILE"

detach_command() {
  if command -v setsid >/dev/null 2>&1; then
    setsid "$@"
  else
    "$@"
  fi
}

start_managed() {
  if [[ -f "$BACKEND_PID_FILE" ]] || [[ -f "$FRONTEND_PID_FILE" ]]; then
    echo "Managed local host stack already appears to be running." >&2
    exit 1
  fi

  if [[ "$(port_status "$BACKEND_PORT")" == "listening" ]] || [[ "$(port_status "$FRONTEND_PORT")" == "listening" ]]; then
    echo "Port conflict detected. Stop the existing stack first." >&2
    exit 1
  fi

  echo "Preparing frontend build..."
  frontend_npm run build >/dev/null

  echo "Applying backend migrations..."
  backend_manage migrate >/dev/null

  : > "$BACKEND_LOG_FILE"
  : > "$FRONTEND_LOG_FILE"

  echo "Starting backend..."
  if [[ "$USE_GUNICORN" == "1" ]]; then
    detach_command nohup "$BACKEND_PYTHON" -m gunicorn config.wsgi:application \
      --bind "$BACKEND_HOST:$BACKEND_PORT" \
      --workers "$WORKERS" \
      --chdir "$BACKEND_DIR" >>"$BACKEND_LOG_FILE" 2>&1 </dev/null &
  else
    detach_command nohup bash -lc "cd \"$BACKEND_DIR\" && \"$BACKEND_PYTHON\" manage.py runserver \"$BACKEND_HOST:$BACKEND_PORT\"" \
      >>"$BACKEND_LOG_FILE" 2>&1 </dev/null &
  fi
  echo $! > "$BACKEND_PID_FILE"

  echo "Starting frontend preview server..."
  detach_command nohup bash -lc "cd \"$FRONTEND_DIR\" && npm run preview -- --host \"$FRONTEND_HOST\" --port \"$FRONTEND_PORT\"" \
    >>"$FRONTEND_LOG_FILE" 2>&1 </dev/null &
  echo $! > "$FRONTEND_PID_FILE"

  wait_for_port "$BACKEND_PORT" 20 || {
    echo "Backend failed to start. Check $BACKEND_LOG_FILE" >&2
    exit 1
  }
  wait_for_port "$FRONTEND_PORT" 20 || {
    echo "Frontend failed to start. Check $FRONTEND_LOG_FILE" >&2
    exit 1
  }

  echo
  echo "Local host stack started in managed mode."
  echo "Frontend: http://localhost:$FRONTEND_PORT"
  echo "Backend:  http://localhost:$BACKEND_PORT"
  echo "Logs:     $LOG_DIR"
}

stop_managed() {
  local pid

  pid="$(read_pid_file "$FRONTEND_PID_FILE")"
  if [[ -n "${pid:-}" ]] && is_pid_running "$pid"; then
    kill "$pid" >/dev/null 2>&1 || true
  fi
  rm -f "$FRONTEND_PID_FILE"

  pid="$(read_pid_file "$BACKEND_PID_FILE")"
  if [[ -n "${pid:-}" ]] && is_pid_running "$pid"; then
    kill "$pid" >/dev/null 2>&1 || true
  fi
  rm -f "$BACKEND_PID_FILE"

  echo "Managed local host stack stopped."
}

status_managed() {
  echo "backend_pid=$(read_pid_file "$BACKEND_PID_FILE" || true)"
  echo "frontend_pid=$(read_pid_file "$FRONTEND_PID_FILE" || true)"
  echo "backend_port_$BACKEND_PORT=$(port_status "$BACKEND_PORT")"
  echo "frontend_port_$FRONTEND_PORT=$(port_status "$FRONTEND_PORT")"
  echo "backend_log=$BACKEND_LOG_FILE"
  echo "frontend_log=$FRONTEND_LOG_FILE"
}

logs_managed() {
  touch "$BACKEND_LOG_FILE" "$FRONTEND_LOG_FILE"
  tail -n 80 -f "$BACKEND_LOG_FILE" "$FRONTEND_LOG_FILE"
}

foreground_managed() {
  echo "Preparing frontend build..."
  frontend_npm run build >/dev/null

  echo "Applying backend migrations..."
  backend_manage migrate >/dev/null

  echo "Starting backend..."
  if [[ "$USE_GUNICORN" == "1" ]]; then
    "$BACKEND_PYTHON" -m gunicorn config.wsgi:application \
      --bind "$BACKEND_HOST:$BACKEND_PORT" \
      --workers "$WORKERS" \
      --chdir "$BACKEND_DIR" &
  else
    backend_manage runserver "$BACKEND_HOST:$BACKEND_PORT" &
  fi
  BACKEND_PID=$!

  echo "Starting frontend preview server..."
  (
    cd "$FRONTEND_DIR"
    npm run preview -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
  ) &
  FRONTEND_PID=$!

  echo
  echo "Local host stack is up."
  echo "Frontend: http://localhost:$FRONTEND_PORT"
  echo "Backend:  http://localhost:$BACKEND_PORT"
  echo
  echo "Press Ctrl+C to stop both services."

  wait "$BACKEND_PID" "$FRONTEND_PID"
}

case "$subcommand" in
  start)
    trap - EXIT INT TERM
    start_managed
    ;;
  stop)
    trap - EXIT INT TERM
    stop_managed
    ;;
  restart)
    trap - EXIT INT TERM
    stop_managed || true
    start_managed
    ;;
  status)
    trap - EXIT INT TERM
    status_managed
    ;;
  logs)
    trap - EXIT INT TERM
    logs_managed
    ;;
  foreground)
    foreground_managed
    ;;
  *)
    echo "Usage: $0 [start|stop|restart|status|logs|foreground]" >&2
    exit 1
    ;;
esac
