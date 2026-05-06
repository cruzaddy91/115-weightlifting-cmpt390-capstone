#!/usr/bin/env sh
# Bring up the pkg_large Docker stack: multi-worker Gunicorn, no demo seed,
# DEBUG=False, isolated Compose project (pkg_large). Uses alternate host
# ports so the demo stack can stay on 5432 / 8000 / 4173 at the same time.
#
# Frontend http://localhost:4174  API http://localhost:8001  Postgres host 5433
set -eu

ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PKG_ENV="${PKG_LARGE_ENV_FILE:-$ROOT/.env.pkg_large}"
TEMPLATE="$ROOT/env.large.local.example"

if [ ! -f "$TEMPLATE" ]; then
  echo "Missing $TEMPLATE" >&2
  exit 1
fi

if [ ! -f "$PKG_ENV" ]; then
  cp "$TEMPLATE" "$PKG_ENV"
  echo "Created $PKG_ENV from env.large.local.example"
fi

# One-time migration: older templates used demo ports (8000/4173) and lacked PKG_LARGE_HOST_*.
if [ -f "$PKG_ENV" ] && ! grep -q '^PKG_LARGE_HOST_POSTGRES_PORT=' "$PKG_ENV" 2>/dev/null; then
  echo "Migrating $PKG_ENV to pkg_large host ports (5433 / 8001 / 4174)..."
  perl -i -pe 's/^VITE_API_BASE_URL=http:\/\/localhost:8000$/VITE_API_BASE_URL=http:\/\/localhost:8001/' "$PKG_ENV"
  perl -i -pe 's#http://localhost:4173#http://localhost:4174#g; s#http://127.0.0.1:4173#http://127.0.0.1:4174#g' "$PKG_ENV"
  printf '%s\n' '' '# Host-published ports (must match docker-compose.pkg_large.yml)' \
    'PKG_LARGE_HOST_POSTGRES_PORT=5433' \
    'PKG_LARGE_HOST_BACKEND_PORT=8001' \
    'PKG_LARGE_HOST_FRONTEND_PORT=4174' >>"$PKG_ENV"
fi

# Replace placeholder secret key once OpenSSL is available (Django rejects django-insecure defaults).
if grep -q '^SECRET_KEY=pkg-large-local-placeholder-REPLACE-OR-RUN-up_pkg_large-sh' "$PKG_ENV" 2>/dev/null; then
  if command -v openssl >/dev/null 2>&1; then
    NEWKEY="$(openssl rand -hex 32)"
    awk -v k="$NEWKEY" 'BEGIN{done=0} /^SECRET_KEY=pkg-large-local-placeholder/{print "SECRET_KEY=" k; done=1; next} {print}' "$PKG_ENV" >"$PKG_ENV.tmp" && mv "$PKG_ENV.tmp" "$PKG_ENV"
    echo "Set SECRET_KEY in $PKG_ENV (openssl rand -hex 32)."
  else
    echo "Install openssl or edit SECRET_KEY in $PKG_ENV manually." >&2
    exit 1
  fi
fi

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-pkg_large}"

PORT_UI="$(grep '^PKG_LARGE_HOST_FRONTEND_PORT=' "$PKG_ENV" 2>/dev/null | tail -1 | cut -d= -f2-)"
PORT_API="$(grep '^PKG_LARGE_HOST_BACKEND_PORT=' "$PKG_ENV" 2>/dev/null | tail -1 | cut -d= -f2-)"
PORT_UI="${PORT_UI:-4174}"
PORT_API="${PORT_API:-8001}"

echo "Compose project: $COMPOSE_PROJECT_NAME"
echo "Env file: $PKG_ENV"
echo "pkg_large URLs:  UI http://localhost:${PORT_UI}  API http://localhost:${PORT_API}"
echo "(Demo stack may continue using :4173 / :8000 / :5432.)"

exec docker compose --env-file "$PKG_ENV" \
  -f docker-compose.yml \
  -f docker-compose.large.yml \
  -f docker-compose.pkg_large.yml \
  up --build "$@"
