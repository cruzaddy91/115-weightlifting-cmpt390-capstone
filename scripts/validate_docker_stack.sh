#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/validation-reports"
ENV_FILE="$ROOT_DIR/.env"
ENV_EXAMPLE="$ROOT_DIR/.env.example"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:4173}"
DEMO_PASSWORD="${DEMO_PASSWORD:-Passw0rd!123}"
UAT_COACH_SIGNUP_CODE="${UAT_COACH_SIGNUP_CODE:-docker-uat-coach}"
STRESS_CYCLES="${STRESS_CYCLES:-25}"

mkdir -p "$REPORT_DIR"

ensure_env_file() {
  if [ ! -f "$ENV_FILE" ]; then
    if [ ! -f "$ENV_EXAMPLE" ]; then
      echo "Missing .env and .env.example; cannot bootstrap Docker environment." >&2
      exit 1
    fi
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    echo "Created .env from .env.example"
  fi
}

ensure_env_key() {
  key="$1"
  value="$2"
  if ! grep -q "^${key}=" "$ENV_FILE"; then
    printf '\n%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

env_value() {
  key="$1"
  value="$(grep "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true)"
  printf '%s' "$value"
}

wait_for_url() {
  name="$1"
  url="$2"
  expected="$3"
  attempts="${4:-60}"
  delay="${5:-2}"
  count=1
  while [ "$count" -le "$attempts" ]; do
    code="$(curl -sS -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || true)"
    if [ "$code" = "$expected" ]; then
      echo "$name reachable at $url ($code)"
      return 0
    fi
    echo "Waiting for $name at $url; attempt $count/$attempts returned ${code:-no response}"
    sleep "$delay"
    count=$((count + 1))
  done
  echo "$name did not become reachable at $url with expected status $expected" >&2
  return 1
}

write_summary() {
  status="$1"
  cat > "$REPORT_DIR/docker_validation_summary_latest.md" <<EOF
# Docker Validation Summary

- Status: $status
- Backend URL: $BACKEND_URL
- Frontend URL: $FRONTEND_URL
- Stress cycles per account: $STRESS_CYCLES
- Generated at UTC: $(date -u +"%Y-%m-%dT%H:%M:%SZ")

## Artifacts

- docker_uat_latest.json
- auth_stress_coachone_latest.json
- auth_stress_jonsnow_latest.json
- compose_config_latest.txt
- compose_ps_latest.txt
- backend_logs_latest.txt
- frontend_logs_latest.txt
- postgres_logs_latest.txt
EOF
}

ensure_env_file
ensure_env_key "COACH_SIGNUP_CODE" "$UAT_COACH_SIGNUP_CODE"
ensure_env_key "THROTTLE_LOGIN" "120/min"
ensure_env_key "THROTTLE_REGISTER" "60/min"

DEMO_PASSWORD_FROM_ENV="$(env_value DEMO_PASSWORD)"
if [ -n "$DEMO_PASSWORD_FROM_ENV" ]; then
  DEMO_PASSWORD="$DEMO_PASSWORD_FROM_ENV"
fi
COACH_SIGNUP_CODE_FROM_ENV="$(env_value COACH_SIGNUP_CODE)"
if [ -n "$COACH_SIGNUP_CODE_FROM_ENV" ]; then
  UAT_COACH_SIGNUP_CODE="$COACH_SIGNUP_CODE_FROM_ENV"
fi

cd "$ROOT_DIR"

echo "Validating Compose config..."
docker compose config > "$REPORT_DIR/compose_config_latest.txt"

echo "Starting Docker stack..."
docker compose up --build -d
docker compose ps > "$REPORT_DIR/compose_ps_latest.txt" || true

wait_for_url "backend auth endpoint" "$BACKEND_URL/api/auth/me/" "401"
wait_for_url "frontend" "$FRONTEND_URL/" "200"

export BACKEND_URL FRONTEND_URL DEMO_PASSWORD UAT_COACH_SIGNUP_CODE

echo "Running Docker API UAT..."
python3 "$ROOT_DIR/scripts/docker_uat.py" \
  --backend-url "$BACKEND_URL" \
  --frontend-url "$FRONTEND_URL" \
  --password "$DEMO_PASSWORD" \
  --coach-signup-code "$UAT_COACH_SIGNUP_CODE" \
  > "$REPORT_DIR/docker_uat_latest.json"

echo "Running auth stress for Coachone..."
python3 "$ROOT_DIR/scripts/docker_auth_stress.py" \
  --backend-url "$BACKEND_URL" \
  --username "Coachone" \
  --password "$DEMO_PASSWORD" \
  --cycles "$STRESS_CYCLES" \
  > "$REPORT_DIR/auth_stress_coachone_latest.json"

echo "Running auth stress for jon_snow..."
python3 "$ROOT_DIR/scripts/docker_auth_stress.py" \
  --backend-url "$BACKEND_URL" \
  --username "jon_snow" \
  --password "$DEMO_PASSWORD" \
  --cycles "$STRESS_CYCLES" \
  > "$REPORT_DIR/auth_stress_jonsnow_latest.json"

docker compose ps > "$REPORT_DIR/compose_ps_latest.txt" || true
docker compose logs --no-color --tail=300 backend > "$REPORT_DIR/backend_logs_latest.txt" 2>&1 || true
docker compose logs --no-color --tail=300 frontend > "$REPORT_DIR/frontend_logs_latest.txt" 2>&1 || true
docker compose logs --no-color --tail=300 postgres > "$REPORT_DIR/postgres_logs_latest.txt" 2>&1 || true

write_summary "PASS"
echo "Docker validation passed. Reports written to $REPORT_DIR"
