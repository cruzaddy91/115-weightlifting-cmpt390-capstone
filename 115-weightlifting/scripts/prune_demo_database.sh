#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

scrub_events=0
apply=0
for arg in "$@"; do
  case "$arg" in
    --yes)
      apply=1
      ;;
    --scrub-events)
      scrub_events=1
      ;;
    *)
      echo "Unknown option: $arg" >&2
      echo "Usage: $0 [--yes] [--scrub-events]" >&2
      exit 1
      ;;
  esac
done

ensure_backend_venv
ensure_backend_env
ensure_runtime_dirs

if [[ "$apply" -ne 1 ]]; then
  echo "Preview: canonical roster is Coachone+5 GoT and Coachtwo+5 LotR (see tools/sim/seed.py themes)."
  echo "All other coach/athlete accounts (smoke-*, extra sim users, etc.) would be removed."
  echo "Staff/superusers are preserved."
  echo
  backend_manage prune_demo_users --dry-run
  echo
  echo "Re-run with --yes to apply. Add --scrub-events to delete var/reports/events/*.json (removes old demo/smoke metadata)."
  exit 0
fi

echo "Creating safety backup before prune..."
"$ROOT_DIR/scripts/backup_data.sh"

backend_manage prune_demo_users --apply

if [[ "$scrub_events" -eq 1 ]]; then
  if compgen -G "$EVENT_DIR/*.json" > /dev/null; then
    rm -f "$EVENT_DIR"/*.json
    echo "Removed report event JSON files under $EVENT_DIR"
  else
    echo "No event JSON files to remove."
  fi
fi

log_event "demo_prune" "success" "prune_demo_database.sh" '{"kept":"Coachone+got5+Coachtwo+lotr5"}'
"$ROOT_DIR/scripts/report.sh" >/dev/null
echo "Prune complete."
