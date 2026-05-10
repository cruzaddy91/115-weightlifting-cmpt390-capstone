#!/usr/bin/env python3
"""Gate Docker UAT evidence against a fixed floor and required check substrings.

When you add new HTTP acceptance rows in docker_uat.py, bump scripts/ssvc_uat_floor.txt
to the new total on the same commit so the suite cannot shrink silently.

Usage:
  python3 scripts/ssvc_verify_manifest.py [path/to/docker_uat_latest.json]

Default policy:
  - failed != 0  -> exit 1
  - total < floor -> exit 1 (suite shrunk versus the floor file)
  - total > floor -> pass with stderr NOTE (bump scripts/ssvc_uat_floor.txt when you want to lock new coverage)

Environment:
  SSVC_UAT_STRICT=1 -> require total == floor
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOOR_FILE = ROOT / "scripts" / "ssvc_uat_floor.txt"
REQ_NAMES_FILE = ROOT / "scripts" / "ssvc_uat_required_names.txt"


def _load_names(data: dict) -> list[str]:
    return [str(item.get("name", "")) for item in data.get("results", [])]


def main() -> int:
    default_json = ROOT / "validation-reports" / "docker_uat_latest.json"
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_json
    if not path.is_file():
        print(f"Missing UAT JSON: {path}", file=sys.stderr)
        return 1

    data = json.loads(path.read_text(encoding="utf-8"))
    failed_n = int(data.get("failed", 1))
    if failed_n != 0:
        print("UAT report shows failures; fix docker_uat before manifest passes.", file=sys.stderr)
        return 1

    total = int(data.get("total", 0))
    if not FLOOR_FILE.is_file():
        print(f"Missing floor file: {FLOOR_FILE}", file=sys.stderr)
        return 1
    floor = int(FLOOR_FILE.read_text(encoding="utf-8").strip())
    if floor < 0:
        print("Invalid floor", file=sys.stderr)
        return 1

    strict = os.environ.get("SSVC_UAT_STRICT", "") == "1"

    if floor > 0 and total < floor:
        print(
            f"UAT suite shrunk: total {total} < floor {floor}. "
            "Restore checks or intentionally lower scripts/ssvc_uat_floor.txt.",
            file=sys.stderr,
        )
        return 1

    if floor > 0 and strict and total != floor:
        print(
            f"SSVC_UAT_STRICT: total {total} must equal floor {floor}.",
            file=sys.stderr,
        )
        return 1

    if floor > 0 and total > floor:
        print(
            f"NOTE: UAT now has {total} checks (floor {floor}). "
            f"Bump scripts/ssvc_uat_floor.txt to {total} when you want CI to reject regressions below that count.",
            file=sys.stderr,
        )

    names = _load_names(data)
    if REQ_NAMES_FILE.is_file():
        for line in REQ_NAMES_FILE.read_text(encoding="utf-8").splitlines():
            needle = line.strip()
            if not needle or needle.startswith("#"):
                continue
            if not any(needle in n for n in names):
                print(f"Missing UAT check containing substring: {needle!r}", file=sys.stderr)
                return 1

    print(f"UAT manifest OK: total={total}, floor={floor}, failed=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
