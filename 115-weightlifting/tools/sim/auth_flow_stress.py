"""Stress-test the full login -> logout -> login cycle.

Exists because a user reports the 'Log in' button stops firing after a
logout in their live browser. Headless Chromium never reproduces, so we
need to: (a) confirm the backend itself cannot fail this flow, and
(b) capture rich structured data for every cycle that we can compare
against a browser trace when the user runs the sibling auth-probe.html.

Each cycle:
  1. Clear session cookies from the HTTP client (simulates fresh browser)
  2. POST /api/auth/token/      -- login
  3. GET  /api/auth/me/         -- verify access token works
  4. POST /api/auth/logout/     -- blacklist refresh token
  5. POST /api/auth/token/      -- login again (the step under suspicion)
  6. GET  /api/auth/me/         -- verify second login
  Also records cookie jar state after every step.

Usage:
  python auth_flow_stress.py                     # 10 cycles, Coachone
  python auth_flow_stress.py --cycles 50         # heavier run
  python auth_flow_stress.py --user jon_snow     # different account
  python auth_flow_stress.py --out report.json   # custom output path
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

from client import DEFAULT_API


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cookie_snapshot(session: requests.Session) -> dict:
    return {c.name: {"value_len": len(c.value or ""), "path": c.path, "domain": c.domain, "secure": c.secure} for c in session.cookies}


def _record_request(session: requests.Session, method: str, url: str, **kwargs) -> dict:
    t0 = time.perf_counter()
    error = None
    status = None
    body_preview = None
    set_cookie = None
    try:
        resp = session.request(method, url, **kwargs)
        status = resp.status_code
        text = resp.text
        try:
            body_preview = json.loads(text) if text else None
        except json.JSONDecodeError:
            body_preview = (text[:300] + "…") if len(text) > 300 else text
        set_cookie = resp.headers.get("set-cookie")
    except requests.RequestException as exc:
        error = repr(exc)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "at": _ts(),
        "method": method,
        "url": url,
        "status": status,
        "elapsed_ms": elapsed_ms,
        "error": error,
        "body_preview": body_preview,
        "set_cookie": set_cookie,
    }


def run_cycle(api: str, user: str, password: str, cycle_num: int) -> dict:
    session = requests.Session()
    cycle: dict = {
        "cycle_num": cycle_num,
        "user": user,
        "steps": [],
        "cookies_timeline": {},
        "pass": False,
    }

    def step(label: str, response: dict) -> None:
        cycle["steps"].append({"label": label, **response})
        cycle["cookies_timeline"][label] = _cookie_snapshot(session)

    # Pre-login: no cookies
    cycle["cookies_timeline"]["initial"] = _cookie_snapshot(session)

    # 1. First login
    step(
        "login_1",
        _record_request(session, "POST", f"{api}/api/auth/token/",
                        json={"username": user, "password": password},
                        headers={"Content-Type": "application/json"}),
    )
    first = cycle["steps"][-1]
    if first["status"] != 200 or not isinstance(first["body_preview"], dict):
        cycle["pass"] = False
        return cycle
    access_1 = first["body_preview"].get("access")

    # 2. /me with first access token
    step(
        "me_1",
        _record_request(session, "GET", f"{api}/api/auth/me/",
                        headers={"Authorization": f"Bearer {access_1}"}),
    )
    if cycle["steps"][-1]["status"] != 200:
        cycle["pass"] = False
        return cycle

    # 3. Logout (cookie-based refresh is already in session.cookies from login_1)
    step(
        "logout",
        _record_request(session, "POST", f"{api}/api/auth/logout/",
                        headers={"Authorization": f"Bearer {access_1}", "Content-Type": "application/json"},
                        json={}),
    )

    # 4. Second login (the suspicious one)
    step(
        "login_2",
        _record_request(session, "POST", f"{api}/api/auth/token/",
                        json={"username": user, "password": password},
                        headers={"Content-Type": "application/json"}),
    )
    second = cycle["steps"][-1]
    if second["status"] != 200 or not isinstance(second["body_preview"], dict):
        cycle["pass"] = False
        return cycle
    access_2 = second["body_preview"].get("access")

    # 5. /me with second access token
    step(
        "me_2",
        _record_request(session, "GET", f"{api}/api/auth/me/",
                        headers={"Authorization": f"Bearer {access_2}"}),
    )
    cycle["pass"] = cycle["steps"][-1]["status"] == 200
    return cycle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stress-test the login->logout->login cycle.")
    parser.add_argument("--api", default=os.environ.get("WL_API", DEFAULT_API))
    parser.add_argument("--user", default="Coachone")
    parser.add_argument("--password", default="Passw0rd!123")
    parser.add_argument("--cycles", type=int, default=10)
    parser.add_argument("--out", default="auth_flow_report.json",
                        help="JSON report output path (default: auth_flow_report.json in cwd)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(f"> API:      {args.api}")
    print(f"> User:     {args.user}")
    print(f"> Cycles:   {args.cycles}")
    print()

    report: dict = {
        "started_at": _ts(),
        "finished_at": None,
        "api": args.api,
        "user": args.user,
        "cycle_count": args.cycles,
        "cycles": [],
        "summary": {},
    }

    for i in range(1, args.cycles + 1):
        cycle = run_cycle(args.api, args.user, args.password, i)
        status_tag = "PASS" if cycle["pass"] else "FAIL"
        statuses = " / ".join(
            f"{s['label']}={s['status']}" for s in cycle["steps"]
        )
        print(f"  [{i:3d}]  {status_tag}  {statuses}")
        report["cycles"].append(cycle)

    report["finished_at"] = _ts()
    passed = sum(1 for c in report["cycles"] if c["pass"])
    failed = args.cycles - passed
    report["summary"] = {
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / args.cycles, 3),
    }

    with open(args.out, "w") as f:
        json.dump(report, f, indent=2)

    print()
    print(f"Done. {passed}/{args.cycles} cycles passed ({report['summary']['pass_rate'] * 100:.0f}%).")
    print(f"Full structured report written to: {args.out}")
    if failed:
        print("  Inspect the failing cycle's 'steps' + 'cookies_timeline' for the exact break point.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
