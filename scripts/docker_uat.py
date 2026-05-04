#!/usr/bin/env python3
"""Docker-first UAT for the 115 Weightlifting stack.

Uses only the HTTP surface exposed by docker-compose so the test matches a
professor's clone/build/run workflow instead of local virtualenv assumptions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date


DEFAULT_PASSWORD = os.getenv("DEMO_PASSWORD", "Passw0rd!123")


class HttpClient:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(self, method: str, path: str, payload=None, token: str | None = None):
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.status, _decode_response(response)
        except urllib.error.HTTPError as exc:
            return exc.code, _decode_response(exc)


def _decode_response(response):
    raw = response.read().decode("utf-8", errors="replace")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def check(results, name: str, passed: bool, detail=None) -> None:
    results.append({"name": name, "passed": bool(passed), "detail": detail})
    marker = "PASS" if passed else "FAIL"
    print(f"[{marker}] {name}", file=sys.stderr)
    if detail is not None and not passed:
        print(f"  {detail}", file=sys.stderr)


def expect_status(results, name: str, actual: int, expected: int, payload=None) -> bool:
    passed = actual == expected
    check(results, name, passed, {"expected": expected, "actual": actual, "payload": payload})
    return passed


def frontend_is_html(frontend_url: str, timeout: float) -> tuple[bool, dict]:
    req = urllib.request.Request(frontend_url.rstrip("/") + "/", headers={"Accept": "text/html"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read(4096).decode("utf-8", errors="replace").lower()
            content_type = response.headers.get("content-type", "")
            return response.status == 200 and "<html" in body, {
                "status": response.status,
                "content_type": content_type,
            }
    except Exception as exc:  # noqa: BLE001 - surfaced in report
        return False, {"error": str(exc)}


def login(client: HttpClient, username: str, password: str = DEFAULT_PASSWORD) -> dict:
    status, payload = client.request(
        "POST",
        "/api/auth/token/",
        {"username": username, "password": password},
    )
    if status != 200 or not isinstance(payload, dict) or "access" not in payload:
        raise RuntimeError(f"Login failed for {username}: status={status}, payload={payload}")
    return payload


def register_user(
    client: HttpClient,
    username: str,
    user_type: str,
    password: str,
    coach_signup_code: str | None = None,
) -> None:
    payload = {"username": username, "password": password, "user_type": user_type}
    if coach_signup_code:
        payload["coach_signup_code"] = coach_signup_code
    status, body = client.request("POST", "/api/auth/register/", payload)
    if status != 201:
        raise RuntimeError(f"Registration failed for {username}: status={status}, payload={body}")


def sample_program_data() -> dict:
    return {
        "week_start_date": str(date.today()),
        "intensity_mode": "percent_1rm",
        "days": [
            {
                "id": "d0",
                "day": "Docker UAT Day 1",
                "exercises": [
                    {
                        "name": "Back Squat",
                        "sets": "5",
                        "reps": "3",
                        "percent_1rm": "80",
                        "rpe": "7",
                        "weight": "120",
                        "tempo": "controlled",
                        "rest": "2 min",
                        "week": "1",
                        "notes": "Docker UAT validation row",
                    }
                ],
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Docker API UAT.")
    parser.add_argument("--backend-url", default=os.getenv("BACKEND_URL", "http://localhost:8000"))
    parser.add_argument("--frontend-url", default=os.getenv("FRONTEND_URL", "http://localhost:4173"))
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--coach-signup-code", default=os.getenv("UAT_COACH_SIGNUP_CODE", "docker-uat-coach"))
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    client = HttpClient(args.backend_url, timeout=args.timeout)
    results: list[dict] = []
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    unique = str(int(time.time()))
    temp_coach = f"uat_coach_{unique}"
    temp_athlete = f"uat_athlete_{unique}"

    ok, detail = frontend_is_html(args.frontend_url, args.timeout)
    check(results, "frontend root returns HTML", ok, detail)

    try:
        seeded_tokens = {}
        seeded_users = {}
        for username, expected_type in (
            ("Headcoachone", "head_coach"),
            ("Coachone", "coach"),
            ("jon_snow", "athlete"),
        ):
            tokens = login(client, username, args.password)
            status, payload = client.request("GET", "/api/auth/me/", token=tokens["access"])
            seeded_tokens[username] = tokens
            seeded_users[username] = payload
            expect_status(results, f"{username} /api/auth/me/", status, 200, payload)
            check(
                results,
                f"{username} has expected role",
                isinstance(payload, dict) and payload.get("user_type") == expected_type,
                payload,
            )

        status, jon_programs = client.request("GET", "/api/programs/", token=seeded_tokens["jon_snow"]["access"])
        expect_status(results, "jon_snow can retrieve assigned programs", status, 200, jon_programs)
        check(
            results,
            "jon_snow has at least one assigned program",
            isinstance(jon_programs, list) and len(jon_programs) > 0,
            {"program_count": len(jon_programs) if isinstance(jon_programs, list) else None},
        )

        register_user(client, temp_coach, "coach", args.password, args.coach_signup_code)
        register_user(client, temp_athlete, "athlete", args.password)
        temp_coach_tokens = login(client, temp_coach, args.password)
        temp_athlete_tokens = login(client, temp_athlete, args.password)

        status, temp_athlete_me = client.request("GET", "/api/auth/me/", token=temp_athlete_tokens["access"])
        expect_status(results, "temporary athlete /api/auth/me/", status, 200, temp_athlete_me)
        athlete_id = temp_athlete_me.get("id") if isinstance(temp_athlete_me, dict) else None
        check(results, "temporary athlete has id", isinstance(athlete_id, int), temp_athlete_me)

        program_payload = {
            "name": f"Docker UAT Program {unique}",
            "description": "Created by Docker UAT harness.",
            "start_date": str(date.today()),
            "end_date": None,
            "athlete_id": athlete_id,
            "program_data": sample_program_data(),
        }
        status, created_program = client.request(
            "POST",
            "/api/programs/",
            program_payload,
            token=temp_coach_tokens["access"],
        )
        expect_status(results, "temporary coach creates program", status, 201, created_program)
        program_id = created_program.get("id") if isinstance(created_program, dict) else None
        check(results, "created program has id", isinstance(program_id, int), created_program)

        status, updated_program = client.request(
            "PATCH",
            f"/api/programs/{program_id}/",
            {"description": "Updated by Docker UAT harness."},
            token=temp_coach_tokens["access"],
        )
        expect_status(results, "temporary coach updates program", status, 200, updated_program)

        status, assigned_program = client.request(
            "PATCH",
            f"/api/programs/{program_id}/assign/",
            {"athlete_id": athlete_id},
            token=temp_coach_tokens["access"],
        )
        expect_status(results, "temporary coach assigns program", status, 200, assigned_program)

        status, athlete_programs = client.request("GET", "/api/programs/", token=temp_athlete_tokens["access"])
        expect_status(results, "temporary athlete retrieves programs", status, 200, athlete_programs)
        check(
            results,
            "temporary athlete sees UAT program",
            isinstance(athlete_programs, list) and any(p.get("id") == program_id for p in athlete_programs),
            athlete_programs,
        )

        completion_payload = {
            "completion_data": {
                "entries": {
                    "d0": {
                        "0": {
                            "completed": True,
                            "athlete_notes": "Completed during Docker UAT.",
                            "result": "5x3 @ 120kg",
                        }
                    }
                }
            }
        }
        status, completion = client.request(
            "PATCH",
            f"/api/athletes/program-completion/{program_id}/",
            completion_payload,
            token=temp_athlete_tokens["access"],
        )
        expect_status(results, "temporary athlete saves completion data", status, 200, completion)

        status, workout = client.request(
            "POST",
            "/api/athletes/workouts/",
            {"date": str(date.today()), "notes": "Docker UAT workout log."},
            token=temp_athlete_tokens["access"],
        )
        expect_status(results, "temporary athlete creates workout log", status, 201, workout)

        status, workouts = client.request("GET", "/api/athletes/workouts/", token=temp_athlete_tokens["access"])
        expect_status(results, "temporary athlete retrieves workout logs", status, 200, workouts)

        status, pr = client.request(
            "POST",
            "/api/athletes/prs/",
            {"lift_type": "total", "weight": "250.0", "date": str(date.today())},
            token=temp_athlete_tokens["access"],
        )
        expect_status(results, "temporary athlete creates PR", status, 201, pr)

        status, prs = client.request("GET", "/api/athletes/prs/", token=temp_athlete_tokens["access"])
        expect_status(results, "temporary athlete retrieves PRs", status, 200, prs)

        status, sinclair = client.request(
            "POST",
            "/api/analytics/sinclair/",
            {"bodyweight_kg": 85, "total_kg": 300, "gender": "M"},
            token=temp_athlete_tokens["access"],
        )
        expect_status(results, "Sinclair analytics endpoint responds", status, 200, sinclair)
        check(
            results,
            "Sinclair response has calculated total",
            isinstance(sinclair, dict) and "sinclair_total" in sinclair,
            sinclair,
        )
    except Exception as exc:  # noqa: BLE001 - converted to structured report
        check(results, "UAT raised unexpected exception", False, {"error": str(exc)})

    summary = {
        "started_at": started_at,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "backend_url": args.backend_url,
        "frontend_url": args.frontend_url,
        "total": len(results),
        "passed": sum(1 for item in results if item["passed"]),
        "failed": sum(1 for item in results if not item["passed"]),
        "results": results,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
