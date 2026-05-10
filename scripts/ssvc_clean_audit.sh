#!/usr/bin/env bash
# CLEAN (audit): list deprecation markers and obvious cruft targets. Does not delete files.
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="$ROOT/validation-reports/ssvc_clean_audit_latest.txt"
mkdir -p "$(dirname "$OUT")"

{
  echo "# SSVC clean audit generated $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo
  echo "## Markers (deprecated / obsolete / remove hints)"
  echo
  if command -v git >/dev/null 2>&1 && git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "$ROOT" grep -n -i -E 'deprecated|obsolete|legacy code|todo[[:space:]]*:.remove|remove.before|FIXME[[:space:]]*:.remove' \
      -- ':!.git' ':!validation-reports' ':!node_modules' ':!*.lock' 2>/dev/null || true
  else
    find "$ROOT/115-weightlifting/src" -type f \( -name '*.py' -o -name '*.js' -o -name '*.jsx' \) \
      ! -path '*/node_modules/*' -print0 2>/dev/null \
      | xargs -0 grep -n -i -E 'deprecated|obsolete|todo.*remove' 2>/dev/null || true
  fi
  echo
  echo "## Empty stub bodies (sample)"
  echo
  find "$ROOT/115-weightlifting/src/backend" -name '*.py' ! -path '*/migrations/*' -print0 2>/dev/null \
    | xargs -0 grep -n '^\s*pass\s*$' 2>/dev/null | head -40 || true
} > "$OUT"

echo "Wrote $OUT"
