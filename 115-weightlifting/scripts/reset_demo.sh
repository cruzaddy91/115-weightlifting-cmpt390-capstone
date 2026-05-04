#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

apply=0
for arg in "$@"; do
  case "$arg" in
    --yes)
      apply=1
      ;;
    *)
      echo "Unknown option: $arg" >&2
      echo "Usage: $0 [--yes]" >&2
      exit 1
      ;;
  esac
done

ensure_backend_venv
ensure_backend_env
ensure_runtime_dirs

echo "Reset scope:"
echo "  users: coach_smoke, athlete_smoke"
echo "  data: programs, completions, workout logs, PRs, and related rows cascading from those users"

backend_manage shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
targets = list(User.objects.filter(username__in=['coach_smoke', 'athlete_smoke']).values('id', 'username', 'user_type'))
print({'matching_demo_users': targets, 'count': len(targets)})
"

if [[ "$apply" -ne 1 ]]; then
  echo
  echo "Preview only. Re-run with --yes to back up and reset demo data."
  exit 0
fi

echo "Creating safety backup first..."
"$ROOT_DIR/scripts/backup_data.sh"

backend_manage shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
User.objects.filter(username__in=['coach_smoke', 'athlete_smoke']).delete()
print('Deleted existing demo users and cascading demo-owned data.')
"

"$ROOT_DIR/scripts/seed_demo_users.sh"

echo
echo "Demo reset complete."

log_event "demo_reset" "success" "reset_demo.sh" '{"users":["coach_smoke","athlete_smoke"]}'
"$ROOT_DIR/scripts/report.sh" >/dev/null
