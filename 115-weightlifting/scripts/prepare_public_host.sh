#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

ensure_backend_venv
ensure_backend_env
ensure_frontend_env

echo "Preparing backend environment..."
backend_pip install -r "$BACKEND_DIR/requirements.txt"
backend_manage migrate

echo "Building frontend..."
frontend_npm install
frontend_npm run build

echo
echo "Public-host artifacts are ready."
echo "Frontend build output: $FRONTEND_DIR/dist"
echo "Backend app root:      $BACKEND_DIR"
echo
echo "Next:"
echo "1. Copy config/self_hosting/backend.env.production.example to your host env path and fill secrets."
echo "2. Copy config/self_hosting/Caddyfile.example into your Caddy config and set the real domain."
echo "3. Copy config/self_hosting/weightlifting-backend.service to /etc/systemd/system/ and adjust paths if needed."
