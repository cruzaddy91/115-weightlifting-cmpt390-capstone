#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

echo "Setting up 115 Weightlifting..."

mkdir -p "$ROOT_DIR/logs"
mkdir -p "$ROOT_DIR/data/raw"
mkdir -p "$ROOT_DIR/data/processed"
mkdir -p "$ROOT_DIR/data/exports"

ensure_backend_venv
ensure_backend_env
ensure_frontend_env

echo "Installing backend dependencies..."
backend_pip install -r "$BACKEND_DIR/requirements.txt"

echo "Installing frontend dependencies..."
frontend_npm install

echo "Applying backend migrations..."
backend_manage migrate

echo
echo "Setup complete."
echo "Primary CLI:"
echo "  ./bin/zw help"
echo
echo "Useful commands:"
echo "  ./bin/zw dev"
echo "  ./bin/zw host-local"
echo "  ./bin/zw smoke"
echo "  ./bin/zw test"
