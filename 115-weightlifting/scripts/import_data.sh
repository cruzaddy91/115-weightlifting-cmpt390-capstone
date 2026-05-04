#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

usage() {
  echo "Usage: $0 <fixture.json> --yes" >&2
  exit 1
}

fixture_path="${1:-}"
confirm="${2:-}"

[[ -n "$fixture_path" ]] || usage
[[ -f "$fixture_path" ]] || { echo "Fixture not found: $fixture_path" >&2; exit 1; }
[[ "$confirm" == "--yes" ]] || { echo "Refusing to import without --yes" >&2; usage; }

ensure_backend_venv
ensure_backend_env
ensure_runtime_dirs

backend_manage loaddata "$fixture_path"
echo "Import complete: $fixture_path"

log_event "import" "success" "import_data.sh" "$(printf '{"fixture_file":"%s"}' "$fixture_path")"
"$ROOT_DIR/scripts/report.sh" >/dev/null
