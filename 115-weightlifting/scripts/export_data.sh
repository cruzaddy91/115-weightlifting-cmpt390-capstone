#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

ensure_backend_venv
ensure_backend_env
ensure_runtime_dirs

timestamp="$(date +%Y%m%d_%H%M%S)"
output_path="${1:-$BACKUP_DIR/export_${timestamp}.json}"

mkdir -p "$(dirname "$output_path")"
backend_manage dumpdata --exclude contenttypes --exclude auth.permission > "$output_path"

echo "Export complete: $output_path"
log_event "export" "success" "export_data.sh" "$(printf '{"export_file":"%s"}' "$output_path")"
"$ROOT_DIR/scripts/report.sh" >/dev/null
