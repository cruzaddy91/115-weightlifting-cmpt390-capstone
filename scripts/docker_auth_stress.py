#!/usr/bin/env python3
"""Small auth-flow stress test against the Docker backend."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request


DEFAULT_PASSWORD = os.getenv("DEMO_PASSWORD", "Passw0rd!123")


def request_json(method: str, url: str, payload=None, token: str | None = None, timeout: float = 10.0):
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, decode(response)
    except urllib.error.HTTPError as exc:
        return exc.code, decode(exc)


def decode(response):
    raw = response.read().decode("utf-8", errors="replace")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def run_cycle(base_url: str, username: str, password: str, timeout: float) -> tuple[bool, dict]:
    status, token_payload = request_json(
        "POST",
        f"{base_url}/api/auth/token/",
        {"username": username, "password": password},
        timeout=timeout,
    )
    if status != 200 or not isinstance(token_payload, dict):
        return False, {"step": "login", "status": status, "payload": token_payload}

    access = token_payload.get("access")
    refresh = token_payload.get("refresh")
    if not access or not refresh:
        return False, {"step": "token-shape", "payload": token_payload}

    status, me_payload = request_json(
        "GET",
        f"{base_url}/api/auth/me/",
        token=access,
        timeout=timeout,
    )
    if status != 200 or not isinstance(me_payload, dict) or me_payload.get("username") != username:
        return False, {"step": "me", "status": status, "payload": me_payload}

    status, logout_payload = request_json(
        "POST",
        f"{base_url}/api/auth/logout/",
        {"refresh": refresh},
        token=access,
        timeout=timeout,
    )
    if status != 205:
        return False, {"step": "logout", "status": status, "payload": logout_payload}

    return True, {"step": "complete"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Docker auth stress test.")
    parser.add_argument("--backend-url", default=os.getenv("BACKEND_URL", "http://localhost:8000"))
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--cycles", type=int, default=25)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--sleep", type=float, default=0.05)
    args = parser.parse_args()

    base_url = args.backend_url.rstrip("/")
    results = []
    started = time.time()
    for index in range(1, args.cycles + 1):
        ok, detail = run_cycle(base_url, args.username, args.password, args.timeout)
        results.append({"cycle": index, "passed": ok, "detail": detail})
        marker = "PASS" if ok else "FAIL"
        print(f"[{marker}] {args.username} cycle {index}/{args.cycles}", file=sys.stderr)
        if args.sleep:
            time.sleep(args.sleep)

    passed = sum(1 for item in results if item["passed"])
    failed = len(results) - passed
    summary = {
        "username": args.username,
        "backend_url": base_url,
        "cycles": args.cycles,
        "passed": passed,
        "failed": failed,
        "pass_rate": passed / args.cycles if args.cycles else 0,
        "elapsed_seconds": round(time.time() - started, 3),
        "results": results,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
