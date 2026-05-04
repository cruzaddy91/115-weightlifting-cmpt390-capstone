#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/src/backend"
FRONTEND_DIR="$ROOT_DIR/src/frontend"
DATA_SCIENCE_DIR="$ROOT_DIR/src/data-science"
BACKEND_ENV_FILE="$BACKEND_DIR/.env"
FRONTEND_ENV_FILE="$FRONTEND_DIR/.env"
BACKEND_VENV_DIR="$BACKEND_DIR/venv"
BACKEND_PYTHON="$BACKEND_VENV_DIR/bin/python"
VAR_DIR="$ROOT_DIR/var"
RUN_DIR="$VAR_DIR/run"
LOG_DIR="$VAR_DIR/log"
BACKUP_DIR="$VAR_DIR/backups"
RELEASE_DIR="$VAR_DIR/releases"
REPORT_DIR="$VAR_DIR/reports"
EVENT_DIR="$REPORT_DIR/events"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
BACKEND_LOG_FILE="$LOG_DIR/backend.log"
FRONTEND_LOG_FILE="$LOG_DIR/frontend.log"

ensure_backend_env() {
  if [[ ! -f "$BACKEND_ENV_FILE" ]]; then
    cp "$BACKEND_DIR/.env.example" "$BACKEND_ENV_FILE"
  fi
}

ensure_frontend_env() {
  if [[ ! -f "$FRONTEND_ENV_FILE" ]]; then
    cp "$FRONTEND_DIR/.env.example" "$FRONTEND_ENV_FILE"
  fi
}

ensure_backend_venv() {
  if [[ ! -x "$BACKEND_PYTHON" ]]; then
    python3 -m venv "$BACKEND_VENV_DIR"
  fi
}

backend_python() {
  "$BACKEND_PYTHON" "$@"
}

backend_manage() {
  (
    cd "$BACKEND_DIR"
    backend_python manage.py "$@"
  )
}

backend_pip() {
  backend_python -m pip "$@"
}

frontend_npm() {
  (
    cd "$FRONTEND_DIR"
    npm "$@"
  )
}

port_status() {
  local port="$1"
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "listening"
  else
    echo "not-listening"
  fi
}

ensure_runtime_dirs() {
  mkdir -p "$VAR_DIR" "$RUN_DIR" "$LOG_DIR" "$BACKUP_DIR" "$RELEASE_DIR" "$REPORT_DIR" "$EVENT_DIR"
}

is_pid_running() {
  local pid="$1"
  kill -0 "$pid" >/dev/null 2>&1
}

read_pid_file() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    cat "$pid_file"
  fi
}

cleanup_stale_pid_file() {
  local pid_file="$1"
  local pid
  pid="$(read_pid_file "$pid_file")"
  if [[ -n "${pid:-}" ]] && ! is_pid_running "$pid"; then
    rm -f "$pid_file"
  fi
}

wait_for_port() {
  local port="$1"
  local attempts="${2:-20}"
  for _ in $(seq 1 "$attempts"); do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

log_event() {
  local event_type="$1"
  local status="$2"
  local source="$3"
  local payload_json="${4-}"

  if [[ -z "$payload_json" ]]; then
    payload_json='{}'
  fi

  ensure_runtime_dirs
  python3 "$ROOT_DIR/scripts/lib/log_event.py" \
    --event-dir "$EVENT_DIR" \
    --event-type "$event_type" \
    --status "$status" \
    --source "$source" \
    --payload "$payload_json" >/dev/null
}
