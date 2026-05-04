#!/bin/bash
# Creates multi-week programs and PATCHes completion_data as each athlete so
# the coach list shows non-zero "x/y done" and % rings. Runs populate_history
# for Coachone (5 GoT) and Coachtwo (5 LotR) — same tier logic, different rosters.
#
# Requires: Django API reachable (e.g. ./bin/zw dev) and users seeded (e.g. prune-demo).
# Each run ADDS new programs (4/athlete). For a clean slate, prune or delete
# TrainingProgram rows in admin for those coaches first.
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

ensure_runtime_dirs

API="${WL_API:-http://127.0.0.1:8000}"
DEMO_PASSWORD="${DEMO_PASSWORD:-Passw0rd!123}"
TOOLS="$ROOT_DIR/tools/sim"
PY=python3
if [[ ! -d "$TOOLS" ]]; then
  echo "Expected $TOOLS" >&2
  exit 1
fi

DRY_RUN=()
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=(--dry-run)
fi

echo "API: $API"
echo "This will run populate_history.py twice (Coachone+GoT, Coachtwo+LotR)."
echo "Password: from DEMO_PASSWORD (default Passw0rd!123 unless set)."
if [[ ${#DRY_RUN[@]} -gt 0 ]]; then
  echo "DRY RUN only — no writes."
fi
echo

run_pop() {
  local coach="$1" theme="$2" size="${3:-5}"
  ( cd "$TOOLS" && "$PY" populate_history.py --api "$API" --password "$DEMO_PASSWORD" --coach "$coach" \
    --roster-theme "$theme" --roster-size "$size" ${DRY_RUN[@]+"${DRY_RUN[@]}"} )
}

echo "== Coachone + game-of-thrones (first 5) =="
run_pop "Coachone" "game-of-thrones" 5
echo
echo "== Coachtwo + lord-of-the-rings (first 5) =="
run_pop "Coachtwo" "lord-of-the-rings" 5
echo
echo "Done. Log in as Coachone or Coachtwo: coach program rows should show partial/full completion, not 0% everywhere."
