#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

ensure_runtime_dirs
cleanup_stale_pid_file "$BACKEND_PID_FILE"
cleanup_stale_pid_file "$FRONTEND_PID_FILE"

echo "root=$ROOT_DIR"
echo "backend_env=$(test -f "$BACKEND_ENV_FILE" && echo present || echo missing)"
echo "frontend_env=$(test -f "$FRONTEND_ENV_FILE" && echo present || echo missing)"
echo "backend_venv=$(test -x "$BACKEND_PYTHON" && echo present || echo missing)"
echo "frontend_node_modules=$(test -d "$FRONTEND_DIR/node_modules" && echo present || echo missing)"
echo "backend_8000=$(port_status 8000)"
echo "frontend_3000=$(port_status 3000)"
echo "frontend_4173=$(port_status 4173)"
echo "managed_backend_pid=$(read_pid_file "$BACKEND_PID_FILE" || true)"
echo "managed_frontend_pid=$(read_pid_file "$FRONTEND_PID_FILE" || true)"
echo "log_dir=$LOG_DIR"
echo "backup_dir=$BACKUP_DIR"

if test -x "$BACKEND_PYTHON"; then
  (
    cd "$BACKEND_DIR"
    "$BACKEND_PYTHON" manage.py shell -c "from django.contrib.auth import get_user_model; User=get_user_model(); print('users=%s coaches=%s athletes=%s' % (User.objects.count(), User.objects.filter(user_type='coach').count(), User.objects.filter(user_type='athlete').count()))"
  )
fi
