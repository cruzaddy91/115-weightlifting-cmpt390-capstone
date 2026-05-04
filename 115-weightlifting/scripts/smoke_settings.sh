#!/bin/bash
# Smoke: settings.py must refuse to boot with DEBUG=False + insecure SECRET_KEY.
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

ensure_backend_venv
ensure_backend_env

# Run in a clean env so the developer's real .env does not mask the guard.
output="$(
  env -i \
    PATH="$PATH" \
    HOME="$HOME" \
    PYTHONPATH="$BACKEND_DIR" \
    DJANGO_SETTINGS_MODULE=config.settings \
    DEBUG=False \
    SECRET_KEY='django-insecure-change-this-in-production' \
    "$BACKEND_PYTHON" -c "import django; django.setup()" 2>&1 || true
)"

if ! printf '%s\n' "$output" | grep -q 'Refusing to start'; then
  echo "FAIL: insecure SECRET_KEY guard did not fire under DEBUG=False" >&2
  printf '%s\n' "$output" >&2
  exit 1
fi

good_output="$(
  env -i \
    PATH="$PATH" \
    HOME="$HOME" \
    PYTHONPATH="$BACKEND_DIR" \
    DJANGO_SETTINGS_MODULE=config.settings \
    DEBUG=TRUE \
    SECRET_KEY='django-insecure-change-this-in-production' \
    "$BACKEND_PYTHON" -c "import django; django.setup(); print('DEBUG_BOOT_OK')" 2>&1
)"
if ! printf '%s\n' "$good_output" | grep -q 'DEBUG_BOOT_OK'; then
  echo "FAIL: DEBUG=True boot with insecure key should succeed but did not" >&2
  printf '%s\n' "$good_output" >&2
  exit 1
fi

prod_output="$(
  env -i \
    PATH="$PATH" \
    HOME="$HOME" \
    PYTHONPATH="$BACKEND_DIR" \
    DJANGO_SETTINGS_MODULE=config.settings \
    DEBUG=False \
    SECRET_KEY='prod-grade-random-$'"$(date +%s%N)"'-key' \
    "$BACKEND_PYTHON" -c "import django; django.setup(); print('PROD_BOOT_OK')" 2>&1
)"
if ! printf '%s\n' "$prod_output" | grep -q 'PROD_BOOT_OK'; then
  echo "FAIL: DEBUG=False boot with strong key should succeed but did not" >&2
  printf '%s\n' "$prod_output" >&2
  exit 1
fi

prod_hardening="$(
  env -i \
    PATH="$PATH" \
    HOME="$HOME" \
    PYTHONPATH="$BACKEND_DIR" \
    DJANGO_SETTINGS_MODULE=config.settings \
    DEBUG=False \
    SECRET_KEY='prod-grade-random-another-'"$(date +%s%N)"'-key' \
    "$BACKEND_PYTHON" -c "
import django
django.setup()
from django.conf import settings as s
assert s.SECURE_PROXY_SSL_HEADER == ('HTTP_X_FORWARDED_PROTO', 'https'), s.SECURE_PROXY_SSL_HEADER
assert s.SESSION_COOKIE_SECURE is True, 'SESSION_COOKIE_SECURE'
assert s.CSRF_COOKIE_SECURE is True, 'CSRF_COOKIE_SECURE'
assert s.SECURE_HSTS_SECONDS >= 0, 'SECURE_HSTS_SECONDS'
assert s.SECURE_HSTS_INCLUDE_SUBDOMAINS is True, 'SECURE_HSTS_INCLUDE_SUBDOMAINS'
assert s.SECURE_CONTENT_TYPE_NOSNIFF is True, 'SECURE_CONTENT_TYPE_NOSNIFF'
assert s.X_FRAME_OPTIONS == 'DENY', s.X_FRAME_OPTIONS
print('PROD_HARDENING_OK')
" 2>&1
)"
if ! printf '%s\n' "$prod_hardening" | grep -q 'PROD_HARDENING_OK'; then
  echo "FAIL: prod TLS/security settings not applied correctly under DEBUG=False" >&2
  printf '%s\n' "$prod_hardening" >&2
  exit 1
fi

dev_no_hsts="$(
  env -i \
    PATH="$PATH" \
    HOME="$HOME" \
    PYTHONPATH="$BACKEND_DIR" \
    DJANGO_SETTINGS_MODULE=config.settings \
    DEBUG=True \
    "$BACKEND_PYTHON" -c "
import django
django.setup()
from django.conf import settings as s
assert not getattr(s, 'SECURE_SSL_REDIRECT', False), 'DEBUG build should not redirect to HTTPS'
print('DEV_NO_HSTS_OK')
" 2>&1
)"
if ! printf '%s\n' "$dev_no_hsts" | grep -q 'DEV_NO_HSTS_OK'; then
  echo "FAIL: DEBUG=True build leaked prod TLS enforcement" >&2
  printf '%s\n' "$dev_no_hsts" >&2
  exit 1
fi

echo 'ok settings.py hardening: insecure-key-refused, dev-boot-ok, prod-boot-ok, prod-tls-hardened, dev-no-hsts'
