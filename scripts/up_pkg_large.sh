#!/usr/bin/env sh
# Bring up the pkg_large Docker stack: multi-worker Gunicorn, no demo seed,
# DEBUG=False, isolated Compose project (default name pkg_large) so volumes
# do not collide with a demo stack using the default project name.
#
# Prerequisites: Docker Compose v2, ports 5432/8000/4173 free (stop demo stack first).
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

echo "Compose project: $COMPOSE_PROJECT_NAME"
echo "Env file: $PKG_ENV"
echo "If this fails with 'port is already allocated', run: docker compose down (demo stack) first."

exec docker compose --env-file "$PKG_ENV" \
  -f docker-compose.yml \
  -f docker-compose.large.yml \
  -f docker-compose.pkg_large.yml \
  up --build "$@"
