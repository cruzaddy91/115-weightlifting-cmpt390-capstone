#!/usr/bin/env bash
# After a green validate_docker_stack, set the UAT floor to the current total (lock coverage bar).
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
JSON="${1:-$ROOT/validation-reports/docker_uat_latest.json}"
export ROOT JSON
python3 - <<'PY'
import json, os, pathlib, sys
root = os.environ["ROOT"]
json_path = pathlib.Path(os.environ["JSON"])
if not json_path.is_file():
    sys.exit(f"missing {json_path}")
d = json.loads(json_path.read_text(encoding="utf-8"))
if d.get("failed"):
    sys.exit("UAT has failures; fix before syncing floor")
n = int(d["total"])
path = pathlib.Path(root) / "scripts" / "ssvc_uat_floor.txt"
path.write_text(str(n) + "\n", encoding="utf-8")
print(f"Wrote {path} = {n}")
PY
