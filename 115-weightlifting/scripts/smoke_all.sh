#!/bin/bash
# Runs every smoke in sequence. Fails fast on first smoke that fails.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== backend smoke (API + reassign history + refresh rotation) ==="
"$SCRIPT_DIR/smoke_test.sh"

echo
echo "=== settings smoke (SECRET_KEY guard) ==="
"$SCRIPT_DIR/smoke_settings.sh"

echo
echo "=== frontend smoke (vitest + vite build) ==="
"$SCRIPT_DIR/smoke_frontend.sh"

echo
echo "ok all smokes passed"
