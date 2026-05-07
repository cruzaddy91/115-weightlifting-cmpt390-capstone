# Security Gate

This repository includes a dependency-free security gate to reduce the chance of committing sensitive data.

It checks for:

- Accidental `.env` files
- Private key and certificate material
- Live-looking API tokens
- Credential assignments with non-placeholder values
- Non-demo email addresses

The scanner intentionally allows documented Docker/demo-only values such as `Passw0rd!123`, `docker-uat-coach`, and `example.invalid` addresses.

## Run Manually

```sh
python3 scripts/security_gate.py --mode tracked
```

For maximum local paranoia:

```sh
python3 scripts/security_gate.py --mode all
```

## Install Local Git Hooks

Run this once per clone:

```sh
scripts/install_git_hooks.sh
```

This installs:

- `pre-commit`: scans staged files
- `pre-push`: scans tracked files

Git hooks live in `.git/hooks`, so they are local to each clone and are not pushed. The GitHub Actions workflow in `.github/workflows/security-gate.yml` runs the same scanner on every push and pull request.
