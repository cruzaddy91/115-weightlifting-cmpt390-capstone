#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

usage() {
  cat >&2 <<'EOF'
Usage:
  restore_data.sh --sqlite <backup.sqlite3> --yes
  restore_data.sh --fixture <backup.json> --yes
EOF
  exit 1
}

mode="${1:-}"
input_path="${2:-}"
confirm="${3:-}"

[[ -n "$mode" && -n "$input_path" ]] || usage
[[ -f "$input_path" ]] || { echo "Backup not found: $input_path" >&2; exit 1; }
[[ "$confirm" == "--yes" ]] || { echo "Refusing to restore without --yes" >&2; usage; }

ensure_backend_venv
ensure_backend_env
ensure_runtime_dirs

case "$mode" in
  --sqlite)
    cp "$input_path" "$BACKEND_DIR/db.sqlite3"
    echo "SQLite database restored from $input_path"
    restore_mode="sqlite"
    ;;
  --fixture)
    backend_manage flush --no-input
    backend_manage loaddata "$input_path"
    echo "Fixture restored from $input_path"
    restore_mode="fixture"
    ;;
  *)
    usage
    ;;
esac

backend_manage migrate >/dev/null
echo "Restore complete."

log_event "restore" "success" "restore_data.sh" "$(printf '{"mode":"%s","input_path":"%s"}' "$restore_mode" "$input_path")"
"$ROOT_DIR/scripts/report.sh" >/dev/null
