#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

ensure_runtime_dirs

timestamp="$(date +%Y%m%d_%H%M%S)"
manifest_file="$RELEASE_DIR/release_${timestamp}.txt"
export_file="$BACKUP_DIR/release_export_${timestamp}.json"

echo "Starting release flow at $timestamp"

echo "1/5 Backup"
"$ROOT_DIR/scripts/backup_data.sh"

echo "2/5 Full test suite"
"$ROOT_DIR/scripts/test_all.sh"

echo "3/5 Smoke test"
smoke_output="$("$ROOT_DIR/scripts/smoke_test.sh")"
echo "$smoke_output"

echo "4/5 Export release fixture"
"$ROOT_DIR/scripts/export_data.sh" "$export_file"

echo "5/5 Write release manifest"
{
  echo "created_at=$timestamp"
  echo "root=$ROOT_DIR"
  echo "export_file=$export_file"
  echo "backup_dir=$BACKUP_DIR"
  echo "release_type=local-predeploy"
} > "$manifest_file"

log_event "release" "success" "release.sh" "$(printf '{"manifest_file":"%s","export_file":"%s"}' "$manifest_file" "$export_file")"
"$ROOT_DIR/scripts/report.sh" >/dev/null

echo
echo "Release flow complete."
echo "Manifest: $manifest_file"
echo "Export:   $export_file"
echo
echo "Next:"
echo "1. Review './bin/zw doctor'"
echo "2. Run './bin/zw prepare-public' when you want public-host artifacts refreshed"
