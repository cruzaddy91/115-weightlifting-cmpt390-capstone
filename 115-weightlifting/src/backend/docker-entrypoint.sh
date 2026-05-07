#!/bin/sh
set -e

if [ -n "${DATABASE_URL:-}" ]; then
  echo "Waiting for PostgreSQL..."
  python - <<'PY'
import os
import socket
import time
from urllib.parse import urlparse

url = os.environ.get('DATABASE_URL', '')
parsed = urlparse(url)
host = parsed.hostname or 'postgres'
port = parsed.port or 5432

for attempt in range(60):
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f'PostgreSQL is available at {host}:{port}')
            break
    except OSError:
        if attempt == 59:
            raise
        time.sleep(1)
PY
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput

if [ "$(printf '%s' "${SEED_DEMO:-false}" | tr '[:upper:]' '[:lower:]')" = "true" ]; then
  echo "Seeding demo data..."
  python manage.py provision_uat3_demo "${UAT3_DEMO_SCENARIO:-preserve_current}"
fi

exec "$@"
