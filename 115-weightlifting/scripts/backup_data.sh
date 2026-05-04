#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

ensure_backend_venv
ensure_backend_env
ensure_runtime_dirs

timestamp="$(date +%Y%m%d_%H%M%S)"
sqlite_backup="$BACKUP_DIR/db_${timestamp}.sqlite3"
fixture_backup="$BACKUP_DIR/data_${timestamp}.json"
manifest_file="$BACKUP_DIR/backup_${timestamp}.txt"

echo "Creating data backup at $timestamp"

if [[ -f "$BACKEND_DIR/db.sqlite3" ]]; then
  cp "$BACKEND_DIR/db.sqlite3" "$sqlite_backup"
  echo "sqlite_backup=$(basename "$sqlite_backup")" >> "$manifest_file"
fi

backend_manage dumpdata --exclude contenttypes --exclude auth.permission > "$fixture_backup"
echo "fixture_backup=$(basename "$fixture_backup")" >> "$manifest_file"
echo "created_at=$timestamp" >> "$manifest_file"

echo "Backup complete:"
[[ -f "$sqlite_backup" ]] && echo "  SQLite copy:   $sqlite_backup"
echo "  Fixture dump:  $fixture_backup"
echo "  Manifest:      $manifest_file"

log_event "backup" "success" "backup_data.sh" "$(printf '{"sqlite_backup":"%s","fixture_backup":"%s","manifest_file":"%s"}' "$sqlite_backup" "$fixture_backup" "$manifest_file")"
"$ROOT_DIR/scripts/report.sh" >/dev/null
