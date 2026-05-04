#!/bin/bash
# HTTP: fill completion_data for programs the coach already has (no new programs).
# Fixes coach list 0/y when build_programs was used without populate_history.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"
API="${WL_API:-http://127.0.0.1:8000}"
PY=python3
DEMO_PASSWORD="${DEMO_PASSWORD:-Passw0rd!123}"
COACH="${1:-Coachtwo}"
( cd "$ROOT_DIR/tools/sim" && exec "$PY" backfill_completion_only.py --api "$API" --password "$DEMO_PASSWORD" --coach "$COACH" )
