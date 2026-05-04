#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

json_mode=0
if [[ "${1:-}" == "--json" ]]; then
  json_mode=1
fi

pass_count=0
warn_count=0
fail_count=0
json_entries=()

pass() {
  if [[ "$json_mode" -eq 0 ]]; then
    echo "PASS  $1"
  fi
  pass_count=$((pass_count + 1))
  json_entries+=("{\"level\":\"pass\",\"message\":\"$1\"}")
}

warn() {
  if [[ "$json_mode" -eq 0 ]]; then
    echo "WARN  $1"
  fi
  warn_count=$((warn_count + 1))
  json_entries+=("{\"level\":\"warn\",\"message\":\"$1\"}")
}

fail() {
  if [[ "$json_mode" -eq 0 ]]; then
    echo "FAIL  $1"
  fi
  fail_count=$((fail_count + 1))
  json_entries+=("{\"level\":\"fail\",\"message\":\"$1\"}")
}

check_file() {
  local path="$1"
  local label="$2"
  if [[ -f "$path" ]]; then
    pass "$label present"
  else
    fail "$label missing ($path)"
  fi
}

check_dir() {
  local path="$1"
  local label="$2"
  if [[ -d "$path" ]]; then
    pass "$label present"
  else
    fail "$label missing ($path)"
  fi
}

ensure_runtime_dirs
cleanup_stale_pid_file "$BACKEND_PID_FILE"
cleanup_stale_pid_file "$FRONTEND_PID_FILE"

if [[ "$json_mode" -eq 0 ]]; then
  echo "Weightlifting doctor"
  echo "root=$ROOT_DIR"
  echo
fi

check_file "$BACKEND_ENV_FILE" "backend env"
check_file "$FRONTEND_ENV_FILE" "frontend env"
check_dir "$BACKEND_VENV_DIR" "backend virtualenv"
check_dir "$FRONTEND_DIR/node_modules" "frontend node_modules"

if command -v node >/dev/null 2>&1; then
  pass "node available ($(node -v))"
else
  fail "node is not available"
fi

if command -v npm >/dev/null 2>&1; then
  pass "npm available ($(npm -v))"
else
  fail "npm is not available"
fi

if [[ -x "$BACKEND_PYTHON" ]]; then
  pass "backend python available"
else
  fail "backend python missing"
fi

if "$BACKEND_PYTHON" -m gunicorn --version >/dev/null 2>&1; then
  pass "gunicorn available in backend venv"
else
  warn "gunicorn missing in backend venv"
fi

if backend_manage check >/dev/null 2>&1; then
  pass "django system check passed"
else
  fail "django system check failed"
fi

if backend_manage makemigrations --check >/dev/null 2>&1; then
  pass "migration state clean"
else
  fail "pending model changes detected"
fi

if backend_manage shell -c "from django.contrib.auth import get_user_model; from apps.programs.models import TrainingProgram; print({'users': get_user_model().objects.count(), 'programs': TrainingProgram.objects.count()})" >/dev/null 2>&1; then
  pass "database query succeeded"
else
  fail "database query failed"
fi

if frontend_npm run build >/dev/null 2>&1; then
  pass "frontend production build passed"
else
  fail "frontend production build failed"
fi

if [[ "$(port_status 8000)" == "listening" ]]; then
  pass "backend port 8000 is listening"
else
  warn "backend port 8000 is not listening"
fi

if [[ "$(port_status 4173)" == "listening" ]]; then
  pass "frontend port 4173 is listening"
else
  warn "frontend port 4173 is not listening"
fi

if [[ -n "$(read_pid_file "$BACKEND_PID_FILE")" || -n "$(read_pid_file "$FRONTEND_PID_FILE")" ]]; then
  pass "managed host PID files present"
else
  warn "managed host PID files not present"
fi

if [[ "$json_mode" -eq 0 ]]; then
  echo
  echo "Summary: pass=$pass_count warn=$warn_count fail=$fail_count"
else
  printf '{"root":"%s","summary":{"pass":%s,"warn":%s,"fail":%s},"checks":[%s]}\n' \
    "$ROOT_DIR" \
    "$pass_count" \
    "$warn_count" \
    "$fail_count" \
    "$(IFS=,; echo "${json_entries[*]}")"
fi

report_json="$(printf '{"summary":{"pass":%s,"warn":%s,"fail":%s}}' \
  "$pass_count" \
  "$warn_count" \
  "$fail_count")"
log_event "doctor" "$([[ "$fail_count" -gt 0 ]] && echo fail || echo success)" "doctor.sh" "$report_json"
"$ROOT_DIR/scripts/report.sh" >/dev/null

if [[ "$fail_count" -gt 0 ]]; then
  exit 1
fi
