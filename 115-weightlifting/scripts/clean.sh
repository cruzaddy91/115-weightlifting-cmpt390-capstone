#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

apply=0
deep=0

for arg in "$@"; do
  case "$arg" in
    --yes)
      apply=1
      ;;
    --deep)
      deep=1
      ;;
    *)
      echo "Unknown option: $arg" >&2
      echo "Usage: $0 [--yes] [--deep]" >&2
      exit 1
      ;;
  esac
done

targets=(
  "$ROOT_DIR/var/log"
  "$ROOT_DIR/var/run"
  "$FRONTEND_DIR/dist"
  "$BACKEND_DIR/__pycache__"
  "$BACKEND_DIR/staticfiles"
  "$BACKEND_DIR/media"
)

while IFS= read -r ds_store; do
  [[ -n "$ds_store" ]] && targets+=("$ds_store")
done < <(find "$ROOT_DIR" -name '.DS_Store' -print 2>/dev/null || true)

if [[ "$deep" -eq 1 ]]; then
  targets+=(
    "$FRONTEND_DIR/node_modules"
  )
fi

echo "Clean targets:"
for target in "${targets[@]}"; do
  echo "  $target"
done

if [[ "$apply" -ne 1 ]]; then
  echo
  echo "Preview only. Re-run with --yes to remove these artifacts."
  exit 0
fi

for target in "${targets[@]}"; do
  rm -rf "$target"
done

echo
echo "Clean complete."
