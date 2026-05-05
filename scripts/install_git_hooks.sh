#!/usr/bin/env sh
set -eu

root="$(git rev-parse --show-toplevel)"
hooks_dir="$root/.git/hooks"
mkdir -p "$hooks_dir"

cat > "$hooks_dir/pre-commit" <<'HOOK'
#!/usr/bin/env sh
set -eu
python3 scripts/security_gate.py --mode staged
HOOK

cat > "$hooks_dir/pre-push" <<'HOOK'
#!/usr/bin/env sh
set -eu
python3 scripts/security_gate.py --mode tracked
HOOK

chmod +x "$hooks_dir/pre-commit" "$hooks_dir/pre-push"
echo "Installed security pre-commit and pre-push hooks."
