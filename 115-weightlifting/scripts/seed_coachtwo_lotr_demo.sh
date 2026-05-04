#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

ensure_backend_venv
ensure_backend_env
ensure_runtime_dirs

# --replace + 3y history by default; forward e.g. --with-programs --api http://127.0.0.1:8000
backend_manage seed_coachtwo_lotr_demo --replace --years 3 "$@"

log_event "coachtwo_lotr_seed" "success" "seed_coachtwo_lotr_demo.sh" '{"coach":"Coachtwo","theme":"lord-of-the-rings","athletes":5}'
"$ROOT_DIR/scripts/report.sh" >/dev/null

echo
echo "Coachtwo + LotR roster and long history are ready."
echo "Optional: create programs via HTTP with API up —"
echo "  ./bin/zw seed-coachtwo-lotr --with-programs"
echo "or: cd tools/sim && python build_programs.py --coach Coachtwo --theme lord-of-the-rings --athletes 5"
