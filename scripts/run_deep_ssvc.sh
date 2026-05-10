#!/usr/bin/env bash
# Deep SSVC: Smoke -> Stack UAT + stress -> Validate (unit/UI tests) -> Manifest gate -> Clean audit.
# Requires Docker Compose from repo root. Destructive only to demo DB via prune_demo_users (same as validate_docker_stack).
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

export STRESS_CYCLES="${STRESS_CYCLES:-60}"
export SSVC_ALLOW_GROWTH="${SSVC_ALLOW_GROWTH:-}"

echo "=== SMOKE: compose parse + security gate ==="
docker compose config >/dev/null
python3 "$ROOT/scripts/security_gate.py" --mode tracked

echo "=== STACK: validate_docker_stack (STRESS_CYCLES=$STRESS_CYCLES) ==="
"$ROOT/scripts/validate_docker_stack.sh"

echo "=== VALIDATE: Django test suite (running stack) ==="
docker compose exec -T backend python manage.py test -v 1

echo "=== VALIDATE: Vitest (frontend container) ==="
docker compose exec -T frontend sh -c "cd /app && npm test"

echo "=== MANIFEST: UAT floor + required check names ==="
python3 "$ROOT/scripts/ssvc_verify_manifest.py" \
  "$ROOT/validation-reports/docker_uat_latest.json"

echo "=== CLEAN: deprecation / stub audit (report only) ==="
"$ROOT/scripts/ssvc_clean_audit.sh"

echo "Deep SSVC finished OK."
