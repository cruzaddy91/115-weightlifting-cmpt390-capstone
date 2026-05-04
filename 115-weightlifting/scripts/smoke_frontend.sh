#!/bin/bash
# Smoke: frontend compiles, interceptor/ProtectedRoute unit tests pass, login bundle ships.
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  frontend_npm install --silent >/dev/null
fi

frontend_npm run -s test

frontend_npm run -s build >/dev/null

dist_index="$FRONTEND_DIR/dist/index.html"
if [[ ! -f "$dist_index" ]]; then
  echo "FAIL: build did not produce dist/index.html" >&2
  exit 1
fi

if ! grep -q '<div id="root"></div>' "$dist_index"; then
  echo "FAIL: built index.html missing React root mount point" >&2
  exit 1
fi

echo "ok frontend smoke: vitest passed, build emitted $(du -sh "$FRONTEND_DIR/dist" | awk '{print $1}'), login bundle linked"
