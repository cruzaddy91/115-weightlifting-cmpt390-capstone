#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

ensure_backend_venv
ensure_backend_env
ensure_frontend_env

echo "Running Django checks..."
backend_manage check

echo "Checking migrations..."
backend_manage makemigrations --check

echo "Running Django tests..."
# Explicit app test modules (bare `test` discovers 0 tests in this repo layout).
backend_manage test \
  apps.accounts.tests \
  apps.programs.tests \
  apps.athletes.tests \
  apps.analytics.tests

echo "Running frontend unit tests (Vitest)..."
frontend_npm test

echo "Building frontend..."
frontend_npm run build

log_event "test" "success" "test_all.sh" '{"backend_checks":"passed","vitest":"passed","frontend_build":"passed"}'
"$ROOT_DIR/scripts/report.sh" >/dev/null
