#!/usr/bin/env python3
"""Docker-first UAT for the 115 Weightlifting stack.

Uses only the HTTP surface exposed by docker-compose so the test matches a
professor's clone/build/run workflow instead of local virtualenv assumptions.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import date


DEFAULT_PASSWORD = os.getenv("DEMO_PASSWORD", "Passw0rd!123")
MASTER_HEAD_USERNAME = "117_HeadcoachGM"
SEEDED_COACH_USERNAME = "008_Coachone"
SEEDED_ATHLETE_USERNAME = "000_Athlete1"
SEEDED_UNASSIGNED_ATHLETE_USERNAMES = [
    "005_Athlete2",
    "006_Athlete3",
    "007_Athlete4",
    "009_Athlete5",
    "010_Athlete6",
    "011_Athlete7",
    "012_Athlete8",
    "014_Athlete9",
    "015_Athlete10",
    "016_Athlete11",
    "017_Athlete12",
    "018_Athlete13",
    "019_Athlete14",
    "020_Athlete15",
    "021_Athlete16",
]


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


def _fetch_url_text(url: str, timeout: float, max_bytes: int | None = 2_500_000) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        chunk = response.read(max_bytes) if max_bytes else response.read()
        return response.status, chunk.decode("utf-8", errors="replace")


def verify_head_dashboard_bundle(frontend_url: str, timeout: float) -> tuple[bool, dict]:
    """Catch stale Docker `dist` / wrong tree: skill-roster athletes must not reuse `head-athlete-table`.

    Served bundle must include the UI stamp and the `head-skill-roster-table` class string, and must
    not concatenate `head-athlete-table` with `head-skill-roster-table` (mobile card-layout bug).
    """
    base = frontend_url.rstrip("/")
    detail: dict = {"edge_case": "head_dashboard_stale_or_wrong_bundle"}
    try:
        status, html = _fetch_url_text(f"{base}/", timeout, max_bytes=65536)
        detail["index_http_status"] = status
        if status != 200:
            return False, {**detail, "error": "index not 200"}

        # Production Vite: <script type="module" crossorigin src="/assets/index-*.js">
        script_paths = re.findall(r'(?:src)=["\'](/assets/[^"\']+\.js)["\']', html, flags=re.I)
        detail["asset_script_tags"] = len(script_paths)
        if not script_paths:
            has_dev_main = "/src/main.jsx" in html or 'src="/src/' in html
            return False, {
                **detail,
                "error": "index has no /assets/*.js (need vite build / docker preview, not raw dev index)",
                "dev_main_detected": has_dev_main,
            }

        # Prefer entry chunk name
        main_js = next((p for p in script_paths if "index-" in p), script_paths[0])
        js_url = f"{base}{main_js}"
        detail["bundle_url"] = js_url
        jstatus, js_body = _fetch_url_text(js_url, timeout, max_bytes=2_500_000)
        detail["bundle_http_status"] = jstatus
        detail["bundle_chars_sampled"] = len(js_body)
        if jstatus != 200:
            return False, {**detail, "error": "bundle not 200"}

        stamp = "skill-roster-2026-05-05"
        class_skill = "head-skill-roster-table"
        stale_combo = "head-athlete-table head-skill-roster-table"
        has_stamp = stamp in js_body
        has_skill_class = class_skill in js_body
        has_stale_combo = stale_combo in js_body
        detail["has_ui_stamp"] = has_stamp
        detail["has_skill_roster_class"] = has_skill_class
        detail["has_stale_class_combo"] = has_stale_combo

        passed = has_stamp and has_skill_class and not has_stale_combo
        return passed, detail
    except Exception as exc:  # noqa: BLE001
        return False, {**detail, "error": str(exc)}


def login(client: HttpClient, username: str, password: str = DEFAULT_PASSWORD) -> dict:
    status, payload = client.request(
        "POST",
        "/api/auth/token/",
        {"username": username, "password": password},
    )
    if status != 200 or not isinstance(payload, dict) or "access" not in payload:
        raise RuntimeError(f"Login failed for {username}: status={status}, payload={payload}")
    return payload


def email_for(username: str) -> str:
    return f"{username}@uat.example.invalid"


def register_user(
    client: HttpClient,
    username: str,
    email: str,
    user_type: str,
    password: str,
    coach_signup_code: str | None = None,
) -> dict:
    payload = {"username": username, "email": email, "password": password, "user_type": user_type}
    if coach_signup_code:
        payload["coach_signup_code"] = coach_signup_code
    status, body = client.request("POST", "/api/auth/register/", payload)
    if status != 201:
        raise RuntimeError(f"Registration failed for {username}: status={status}, payload={body}")
    time.sleep(0.25)  # avoid THROTTLE_REGISTER bursts during Docker UAT / SSVC
    return body if isinstance(body, dict) else {}


def canonical_uat_athlete_registration_shape(registration: dict, base_suffix: str) -> tuple[bool, str | None]:
    """Return (ok, numeric_prefix) for finalized usernames like 022_Athlete17."""
    username = registration.get("username") if isinstance(registration, dict) else None
    if not isinstance(username, str):
        return False, None
    match = re.fullmatch(r"(\d{3})_(Athlete\d+)", username)
    if not match or match.group(2) != base_suffix:
        return False, None
    return True, match.group(1)


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


def create_program(client: HttpClient, token: str, athlete_id: int, unique_name: str):
    return client.request(
        "POST",
        "/api/programs/",
        {
            "name": unique_name,
            "description": "Created by Docker UAT harness.",
            "start_date": str(date.today()),
            "end_date": None,
            "athlete_id": athlete_id,
            "program_data": sample_program_data(),
        },
        token=token,
    )


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
    run_tag = uuid.uuid4().hex[:10]
    # Line-coach registration requires PREFIX_rest where the numeric prefix is not yet used
    # by any username in the DB — fixed 090/091/… fails on repeat UAT runs.
    _coach_prefix_pool = list(range(60, 90))
    random.shuffle(_coach_prefix_pool)
    _cp = _coach_prefix_pool[:4]
    temp_coach = f"{_cp[0]:03d}_dockerUATc_{run_tag}"
    rbac_coach_b = f"{_cp[1]:03d}_dockerUATb_{run_tag}"
    staff_reassign_coach = f"{_cp[2]:03d}_dockerUATsr_{run_tag}"
    staff_delete_coach = f"{_cp[3]:03d}_dockerUATsd_{run_tag}"
    unique = run_tag
    # Match demo-style canonical handles (NNN_Athlete#); numeric prefix is still auto-assigned.
    temp_athlete_base = "Athlete32"
    rbac_athlete_b_base = "Athlete33"
    unassign_athlete_base = "Athlete34"
    delete_athlete_base = "Athlete35"

    ok, detail = frontend_is_html(args.frontend_url, args.timeout)
    check(results, "frontend root returns HTML", ok, detail)

    fb_ok, fb_detail = verify_head_dashboard_bundle(args.frontend_url, args.timeout)
    check(
        results,
        "frontend bundle includes head skill-roster stamp and not stale athlete-table combo",
        fb_ok,
        fb_detail,
    )

    try:
        seeded_tokens = {}
        seeded_users = {}
        for username, expected_type in (
            (MASTER_HEAD_USERNAME, "head_coach"),
            (SEEDED_COACH_USERNAME, "coach"),
            (SEEDED_ATHLETE_USERNAME, "athlete"),
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

        status, prefix_payload = client.request("GET", "/api/auth/register/coach-prefixes/")
        expect_status(results, "GET /api/auth/register/coach-prefixes/ returns 200", status, 200, prefix_payload)
        avail = prefix_payload.get("available_numeric_prefixes") if isinstance(prefix_payload, dict) else None
        check(
            results,
            "coach-prefixes returns a non-empty available_numeric_prefixes list",
            isinstance(avail, list) and len(avail) > 0,
            prefix_payload,
        )

        status, demo_athlete_programs = client.request("GET", "/api/programs/", token=seeded_tokens[SEEDED_ATHLETE_USERNAME]["access"])
        expect_status(results, f"{SEEDED_ATHLETE_USERNAME} can retrieve assigned programs", status, 200, demo_athlete_programs)
        check(
            results,
            f"{SEEDED_ATHLETE_USERNAME} has at least one assigned program",
            isinstance(demo_athlete_programs, list) and len(demo_athlete_programs) > 0,
            {"program_count": len(demo_athlete_programs) if isinstance(demo_athlete_programs, list) else None},
        )

        for path in (
            "/api/auth/head/org-summary/",
            "/api/auth/head/roster/",
            "/api/analytics/head/model-status/",
        ):
            status, payload = client.request("GET", path, token=seeded_tokens[MASTER_HEAD_USERNAME]["access"])
            expect_status(results, f"{MASTER_HEAD_USERNAME} can access {path}", status, 200, payload)
            status, payload = client.request("GET", path, token=seeded_tokens[SEEDED_COACH_USERNAME]["access"])
            expect_status(results, f"{SEEDED_COACH_USERNAME} is blocked from {path}", status, 403, payload)

        register_user(client, temp_coach, email_for(temp_coach), "coach", args.password, args.coach_signup_code)
        register_user(client, staff_reassign_coach, email_for(staff_reassign_coach), "coach", args.password, args.coach_signup_code)
        register_user(client, staff_delete_coach, email_for(staff_delete_coach), "coach", args.password, args.coach_signup_code)
        batch_bases = [f"Athlete{16 + idx}" for idx in range(1, 16)]
        batch_athletes = []
        batch_prefixes: list[str] = []
        for idx, base_username in enumerate(batch_bases, start=1):
            registration = register_user(
                client, base_username, email_for(base_username), "athlete", args.password,
            )
            batch_athletes.append(registration.get("username"))
            ok_shape, prefix = canonical_uat_athlete_registration_shape(registration, base_username)
            check(
                results,
                f"batch athlete {idx} username is canonical ({base_username})",
                ok_shape,
                registration,
            )
            if prefix:
                batch_prefixes.append(prefix)
        batch_order_ok = (
            len(batch_prefixes) == len(batch_bases)
            and len(batch_prefixes) == len(set(batch_prefixes))
            and batch_prefixes == sorted(batch_prefixes)
        )
        check(
            results,
            "batch athlete numeric prefixes are unique and strictly increasing (smallest-free order)",
            batch_order_ok,
            {"prefixes": batch_prefixes},
        )
        temp_athlete_registration = register_user(
            client, temp_athlete_base, email_for(temp_athlete_base), "athlete", args.password,
        )
        temp_athlete = temp_athlete_registration.get("username")
        register_user(client, rbac_coach_b, email_for(rbac_coach_b), "coach", args.password, args.coach_signup_code)
        rbac_athlete_b_registration = register_user(
            client, rbac_athlete_b_base, email_for(rbac_athlete_b_base), "athlete", args.password,
        )
        rbac_athlete_b = rbac_athlete_b_registration.get("username")
        unassign_athlete_registration = register_user(
            client, unassign_athlete_base, email_for(unassign_athlete_base), "athlete", args.password,
        )
        unassign_athlete = unassign_athlete_registration.get("username")
        delete_athlete_registration = register_user(
            client, delete_athlete_base, email_for(delete_athlete_base), "athlete", args.password,
        )
        delete_athlete = delete_athlete_registration.get("username")
        ok_temp, _ = canonical_uat_athlete_registration_shape(temp_athlete_registration, temp_athlete_base)
        check(
            results,
            "temporary athlete username is canonical UAT shape (NNN_Athlete#)",
            ok_temp,
            temp_athlete_registration,
        )
        reserved_prefixes = {"001", "002", "003", "004", "117"}
        normal_prefixes = {"000"} | {f"{prefix:03d}" for prefix in range(5, 100)}
        check(
            results,
            "temporary athlete prefix skips reserved org labels",
            isinstance(temp_athlete, str) and temp_athlete[:3] not in reserved_prefixes,
            temp_athlete_registration,
        )
        check(
            results,
            "temporary athlete prefix stays in normal member pool",
            isinstance(temp_athlete, str) and temp_athlete[:3] in normal_prefixes,
            temp_athlete_registration,
        )
        ok_rb, _ = canonical_uat_athlete_registration_shape(rbac_athlete_b_registration, rbac_athlete_b_base)
        check(
            results,
            "RBAC athlete B username is canonical UAT shape",
            ok_rb,
            rbac_athlete_b_registration,
        )
        ok_un, _ = canonical_uat_athlete_registration_shape(unassign_athlete_registration, unassign_athlete_base)
        check(
            results,
            "unassign athlete username is canonical UAT shape",
            ok_un,
            unassign_athlete_registration,
        )
        ok_del, _ = canonical_uat_athlete_registration_shape(delete_athlete_registration, delete_athlete_base)
        check(
            results,
            "delete athlete username is canonical UAT shape",
            ok_del,
            delete_athlete_registration,
        )
        status, payload = client.request(
            "POST",
            "/api/auth/register/",
            {
                "username": f"001_docker_UAT_reserved_coach_{unique}",
                "email": email_for(f"001_docker_UAT_reserved_coach_{unique}"),
                "password": args.password,
                "user_type": "coach",
                "coach_signup_code": args.coach_signup_code,
            },
        )
        expect_status(results, "coach registration rejects reserved org prefix", status, 400, payload)
        status, payload = client.request(
            "POST",
            "/api/auth/register/",
            {
                "username": f"100_docker_UAT_out_of_pool_coach_{unique}",
                "email": email_for(f"100_docker_UAT_out_of_pool_coach_{unique}"),
                "password": args.password,
                "user_type": "coach",
                "coach_signup_code": args.coach_signup_code,
            },
        )
        expect_status(results, "coach registration rejects out-of-pool prefix", status, 400, payload)
        status, payload = client.request(
            "POST",
            "/api/auth/register/",
            {
                "username": f"docker_UAT_bad_athlete_{unique}",
                "email": email_for(f"docker_UAT_bad_athlete_{unique}"),
                "password": args.password,
                "user_type": "athlete",
            },
        )
        expect_status(results, "athlete registration rejects underscores in selected username", status, 400, payload)

        status, head_roster = client.request(
            "GET",
            "/api/auth/head/roster/",
            token=seeded_tokens[MASTER_HEAD_USERNAME]["access"],
        )
        expect_status(results, f"{MASTER_HEAD_USERNAME} can refresh roster after new registrations", status, 200, head_roster)
        staff_names = {row.get("username") for row in head_roster.get("staff", [])} if isinstance(head_roster, dict) else set()
        athlete_names = {row.get("username") for row in head_roster.get("athletes", [])} if isinstance(head_roster, dict) else set()
        roster_head_rows = head_roster.get("head_coaches", []) if isinstance(head_roster, dict) else []
        roster_staff_rows = head_roster.get("staff", []) if isinstance(head_roster, dict) else []
        roster_athlete_rows = head_roster.get("athletes", []) if isinstance(head_roster, dict) else []
        check(results, f"{MASTER_HEAD_USERNAME} sees newly registered unassigned coach", temp_coach in staff_names, head_roster)
        check(results, f"{MASTER_HEAD_USERNAME} sees newly registered unassigned athlete", temp_athlete in athlete_names, head_roster)
        seeded_unassigned_rows = [
            row for row in roster_athlete_rows if row.get("username") in SEEDED_UNASSIGNED_ATHLETE_USERNAMES
        ]
        check(
            results,
            "15 seeded demo athletes show XXX_UNASSIGNED metadata",
            len(seeded_unassigned_rows) == 15
            and all(
                row.get("primary_coach_id") is None
                and row.get("org_label") == "XXX_UNASSIGNED"
                and row.get("org_color_key") == "graphite"
                for row in seeded_unassigned_rows
            ),
            seeded_unassigned_rows,
        )
        registered_batch_rows = [
            row for row in roster_athlete_rows if row.get("username") in set(batch_athletes)
        ]
        check(
            results,
            "15 registered batch athletes show XXX_UNASSIGNED metadata",
            len(registered_batch_rows) == 15
            and all(
                row.get("primary_coach_id") is None
                and row.get("org_label") == "XXX_UNASSIGNED"
                and row.get("org_color_key") == "graphite"
                for row in registered_batch_rows
            ),
            registered_batch_rows,
        )
        check(
            results,
            "head roster staff rows include reports_to_username",
            any(row.get("username") == SEEDED_COACH_USERNAME and row.get("reports_to_username") for row in roster_staff_rows),
            head_roster,
        )
        check(
            results,
            "head roster athlete rows include primary_coach_username",
            any(row.get("username") == SEEDED_ATHLETE_USERNAME and row.get("primary_coach_username") == SEEDED_COACH_USERNAME for row in roster_athlete_rows),
            head_roster,
        )
        check(
            results,
            "head roster rows inherit organization color metadata",
            any(
                row.get("username") == SEEDED_COACH_USERNAME
                and row.get("org_label") != "XXX_UNASSIGNED"
                and row.get("org_color_key") != "graphite"
                for row in roster_staff_rows
            ),
            head_roster,
        )
        expected_head_pool = {
            "118_Headcoachtwo",
            "119_Headcoachthree",
            "120_Headcoachfour",
            "121_Headcoachone",
            "001_Headcoachone",
            "002_Headcoachtwo",
            "003_Headcoachthree",
            "004_Headcoachfour",
        }
        check(
            results,
            "head coach roster includes UAT3 assigned or standalone category pool",
            len(expected_head_pool.intersection({row.get("username") for row in roster_head_rows})) >= 4,
            head_roster,
        )
        head_to_assign = (
            next((row for row in roster_head_rows if row.get("org_prefix") == "001"), None)
            or next((row for row in roster_head_rows if row.get("username") == "121_Headcoachone"), None)
        )
        head_to_delete = next((row for row in roster_head_rows if row.get("username") == "120_Headcoachfour"), None)
        matrix_athlete = next((row for row in roster_athlete_rows if row.get("username") == batch_athletes[0]), None)
        line_under_gm = next((row for row in roster_staff_rows if row.get("username") == SEEDED_COACH_USERNAME), None)
        line_to_move_under_agm = next((row for row in roster_staff_rows if row.get("username") == staff_reassign_coach), None)
        headcoach_id = seeded_users[MASTER_HEAD_USERNAME].get("id") if isinstance(seeded_users.get(MASTER_HEAD_USERNAME), dict) else None
        status, payload = client.request(
            "PATCH",
            f"/api/auth/head/head-coaches/{head_to_assign.get('id') if isinstance(head_to_assign, dict) else 'missing'}/",
            {"category_prefix": "001"},
            token=seeded_tokens[MASTER_HEAD_USERNAME]["access"],
        )
        expect_status(results, f"{MASTER_HEAD_USERNAME} can assign standalone head coach to AGM slot", status, 200, payload)
        check(
            results,
            "assigned standalone head coach receives AGM metadata",
            isinstance(payload, dict)
            and payload.get("username") == "001_Headcoachone"
            and payload.get("org_label") == "001_INFINITY",
            payload,
        )
        assigned_head_id = payload.get("id") if isinstance(payload, dict) else None
        matrix_athlete_id = matrix_athlete.get("id") if isinstance(matrix_athlete, dict) else None
        line_under_gm_id = line_under_gm.get("id") if isinstance(line_under_gm, dict) else None
        line_to_move_under_agm_id = line_to_move_under_agm.get("id") if isinstance(line_to_move_under_agm, dict) else None
        status, payload = client.request(
            "PATCH",
            f"/api/auth/head/athletes/{matrix_athlete_id if matrix_athlete_id is not None else 'missing'}/",
            {"primary_coach_id": headcoach_id},
            token=seeded_tokens[MASTER_HEAD_USERNAME]["access"],
        )
        expect_status(results, f"{MASTER_HEAD_USERNAME} can assign athlete directly to GM", status, 200, payload)
        status, payload = client.request(
            "PATCH",
            f"/api/auth/head/athletes/{matrix_athlete_id if matrix_athlete_id is not None else 'missing'}/",
            {"primary_coach_id": assigned_head_id},
            token=seeded_tokens[MASTER_HEAD_USERNAME]["access"],
        )
        expect_status(results, f"{MASTER_HEAD_USERNAME} can assign athlete directly to AGM head coach", status, 200, payload)
        status, payload = client.request(
            "PATCH",
            f"/api/auth/head/athletes/{matrix_athlete_id if matrix_athlete_id is not None else 'missing'}/",
            {"primary_coach_id": line_under_gm_id},
            token=seeded_tokens[MASTER_HEAD_USERNAME]["access"],
        )
        expect_status(results, f"{MASTER_HEAD_USERNAME} can assign athlete to line coach under GM", status, 200, payload)
        status, payload = client.request(
            "PATCH",
            f"/api/auth/head/staff/{line_to_move_under_agm_id if line_to_move_under_agm_id is not None else 'missing'}/",
            {"reports_to_id": assigned_head_id},
            token=seeded_tokens[MASTER_HEAD_USERNAME]["access"],
        )
        expect_status(results, f"{MASTER_HEAD_USERNAME} can assign line coach under AGM for athlete matrix", status, 200, payload)
        status, payload = client.request(
            "PATCH",
            f"/api/auth/head/athletes/{matrix_athlete_id if matrix_athlete_id is not None else 'missing'}/",
            {"primary_coach_id": line_to_move_under_agm_id},
            token=seeded_tokens[MASTER_HEAD_USERNAME]["access"],
        )
        expect_status(results, f"{MASTER_HEAD_USERNAME} can assign athlete to line coach under AGM", status, 200, payload)
        status, payload = client.request(
            "PATCH",
            f"/api/auth/head/athletes/{matrix_athlete_id if matrix_athlete_id is not None else 'missing'}/",
            {"primary_coach_id": None},
            token=seeded_tokens[MASTER_HEAD_USERNAME]["access"],
        )
        expect_status(results, f"{MASTER_HEAD_USERNAME} can return matrix athlete to XXX_UNASSIGNED", status, 200, payload)
        status, payload = client.request(
            "PATCH",
            f"/api/auth/head/head-coaches/{assigned_head_id if assigned_head_id is not None else 'missing'}/",
            {"category_prefix": "XXX_UNASSIGNED"},
            token=seeded_tokens[MASTER_HEAD_USERNAME]["access"],
        )
        expect_status(results, f"{MASTER_HEAD_USERNAME} can move AGM head coach to XXX_UNASSIGNED", status, 200, payload)
        check(
            results,
            "unassigned AGM head coach receives XXX metadata",
            isinstance(payload, dict)
            and payload.get("org_label") == "XXX_UNASSIGNED",
            payload,
        )
        if not isinstance(head_to_delete, dict) and isinstance(payload, dict):
            head_to_delete = payload
        status, payload = client.request(
            "DELETE",
            f"/api/auth/head/head-coaches/{head_to_delete.get('id') if isinstance(head_to_delete, dict) else 'missing'}/",
            token=seeded_tokens[MASTER_HEAD_USERNAME]["access"],
        )
        expect_status(results, f"{MASTER_HEAD_USERNAME} can soft-delete standalone head coach", status, 200, payload)
        archived_demo_names = {
            "jon_snow",
            "arya_stark",
            "tyrion_lannister",
            "daenerys_targaryen",
            "sansa_stark",
            "frodo_baggins",
            "samwise_gamgee",
            "merry_brandybuck",
            "pippin_took",
            "gandalf_grey",
        }
        check(
            results,
            "archived themed demo athletes are hidden from head roster",
            athlete_names.isdisjoint(archived_demo_names),
            sorted(athlete_names & archived_demo_names),
        )
        status, payload = client.request(
            "POST",
            "/api/auth/token/",
            {"username": "jon_snow", "password": args.password},
        )
        expect_status(results, "archived jon_snow login is disabled", status, 401, payload)

        staff_reassign_tokens = login(client, staff_reassign_coach, args.password)
        status, staff_reassign_me = client.request("GET", "/api/auth/me/", token=staff_reassign_tokens["access"])
        expect_status(results, "staff reassign coach /api/auth/me/", status, 200, staff_reassign_me)
        staff_reassign_id = staff_reassign_me.get("id") if isinstance(staff_reassign_me, dict) else None
        check(results, "staff reassign coach has id", isinstance(staff_reassign_id, int), staff_reassign_me)
        status, payload = client.request(
            "PATCH",
            f"/api/auth/head/staff/{staff_reassign_id}/",
            {"reports_to_id": headcoach_id},
            token=seeded_tokens[MASTER_HEAD_USERNAME]["access"],
        )
        expect_status(results, f"{MASTER_HEAD_USERNAME} can assign coach to head coach", status, 200, payload)
        status, payload = client.request(
            "PATCH",
            f"/api/auth/head/staff/{staff_reassign_id}/",
            {"reports_to_id": None},
            token=seeded_tokens[MASTER_HEAD_USERNAME]["access"],
        )
        expect_status(results, f"{MASTER_HEAD_USERNAME} can move coach to unaffiliated", status, 200, payload)

        staff_delete_tokens = login(client, staff_delete_coach, args.password)
        status, staff_delete_me = client.request("GET", "/api/auth/me/", token=staff_delete_tokens["access"])
        expect_status(results, "staff delete coach /api/auth/me/ before delete", status, 200, staff_delete_me)
        staff_delete_id = staff_delete_me.get("id") if isinstance(staff_delete_me, dict) else None
        check(results, "staff delete coach has id", isinstance(staff_delete_id, int), staff_delete_me)
        status, deleted_staff_payload = client.request(
            "DELETE",
            f"/api/auth/head/staff/{staff_delete_id}/",
            token=seeded_tokens[MASTER_HEAD_USERNAME]["access"],
        )
        expect_status(results, f"{MASTER_HEAD_USERNAME} can soft-delete active coach", status, 200, deleted_staff_payload)
        check(
            results,
            "soft-deleted coach has recovery window",
            isinstance(deleted_staff_payload, dict) and bool(deleted_staff_payload.get("deleted_at")) and bool(deleted_staff_payload.get("recoverable_until")),
            deleted_staff_payload,
        )
        status, payload = client.request(
            "POST",
            "/api/auth/token/",
            {"username": staff_delete_coach, "password": args.password},
        )
        expect_status(results, "soft-deleted coach login is blocked", status, 401, payload)
        status, staff_roster_after_delete = client.request(
            "GET",
            "/api/auth/head/roster/",
            token=seeded_tokens[MASTER_HEAD_USERNAME]["access"],
        )
        expect_status(results, f"{MASTER_HEAD_USERNAME} can refresh roster after coach delete", status, 200, staff_roster_after_delete)
        post_delete_staff_names = {
            row.get("username") for row in staff_roster_after_delete.get("staff", [])
        } if isinstance(staff_roster_after_delete, dict) else set()
        check(
            results,
            "soft-deleted coach hidden from active roster",
            staff_delete_coach not in post_delete_staff_names,
            staff_roster_after_delete,
        )

        status, payload = client.request(
            "POST",
            "/api/auth/register/",
            {
                "username": f"dockerUATDuplicateEmail{unique}",
                "email": email_for(temp_athlete_base),
                "password": args.password,
                "user_type": "athlete",
            },
        )
        expect_status(results, "registration rejects duplicate email", status, 400, payload)

        temp_coach_tokens = login(client, temp_coach, args.password)
        temp_athlete_tokens = login(client, temp_athlete, args.password)
        rbac_coach_b_tokens = login(client, rbac_coach_b, args.password)
        rbac_athlete_b_tokens = login(client, rbac_athlete_b, args.password)

        status, temp_athlete_me = client.request("GET", "/api/auth/me/", token=temp_athlete_tokens["access"])
        expect_status(results, "temporary athlete /api/auth/me/", status, 200, temp_athlete_me)
        athlete_id = temp_athlete_me.get("id") if isinstance(temp_athlete_me, dict) else None
        check(results, "temporary athlete has id", isinstance(athlete_id, int), temp_athlete_me)

        status, rbac_athlete_b_me = client.request("GET", "/api/auth/me/", token=rbac_athlete_b_tokens["access"])
        expect_status(results, "RBAC athlete B /api/auth/me/", status, 200, rbac_athlete_b_me)
        athlete_b_id = rbac_athlete_b_me.get("id") if isinstance(rbac_athlete_b_me, dict) else None
        check(results, "RBAC athlete B has id", isinstance(athlete_b_id, int), rbac_athlete_b_me)

        unassign_athlete_tokens = login(client, unassign_athlete, args.password)
        status, unassign_athlete_me = client.request("GET", "/api/auth/me/", token=unassign_athlete_tokens["access"])
        expect_status(results, "unassign athlete /api/auth/me/", status, 200, unassign_athlete_me)
        unassign_athlete_id = unassign_athlete_me.get("id") if isinstance(unassign_athlete_me, dict) else None
        check(results, "unassign athlete has id", isinstance(unassign_athlete_id, int), unassign_athlete_me)
        status, payload = client.request(
            "PATCH",
            f"/api/auth/head/athletes/{unassign_athlete_id}/",
            {"primary_coach_id": None},
            token=seeded_tokens[MASTER_HEAD_USERNAME]["access"],
        )
        expect_status(results, f"{MASTER_HEAD_USERNAME} can unassign active athlete without deleting", status, 200, payload)
        status, still_active = client.request("GET", "/api/auth/me/", token=unassign_athlete_tokens["access"])
        expect_status(results, "unassigned athlete account remains active", status, 200, still_active)

        delete_athlete_tokens = login(client, delete_athlete, args.password)
        status, delete_athlete_me = client.request("GET", "/api/auth/me/", token=delete_athlete_tokens["access"])
        expect_status(results, "delete athlete /api/auth/me/ before delete", status, 200, delete_athlete_me)
        delete_athlete_id = delete_athlete_me.get("id") if isinstance(delete_athlete_me, dict) else None
        check(results, "delete athlete has id", isinstance(delete_athlete_id, int), delete_athlete_me)
        status, deleted_payload = client.request(
            "DELETE",
            f"/api/auth/head/athletes/{delete_athlete_id}/",
            token=seeded_tokens[MASTER_HEAD_USERNAME]["access"],
        )
        expect_status(results, f"{MASTER_HEAD_USERNAME} can soft-delete active athlete", status, 200, deleted_payload)
        check(
            results,
            "soft-deleted athlete has recovery window",
            isinstance(deleted_payload, dict) and bool(deleted_payload.get("deleted_at")) and bool(deleted_payload.get("recoverable_until")),
            deleted_payload,
        )
        status, payload = client.request(
            "POST",
            "/api/auth/token/",
            {"username": delete_athlete, "password": args.password},
        )
        expect_status(results, "soft-deleted athlete login is blocked", status, 401, payload)
        status, head_roster_after_delete = client.request(
            "GET",
            "/api/auth/head/roster/",
            token=seeded_tokens[MASTER_HEAD_USERNAME]["access"],
        )
        expect_status(results, f"{MASTER_HEAD_USERNAME} can refresh roster after athlete delete", status, 200, head_roster_after_delete)
        post_delete_athlete_names = {
            row.get("username") for row in head_roster_after_delete.get("athletes", [])
        } if isinstance(head_roster_after_delete, dict) else set()
        check(
            results,
            "soft-deleted athlete hidden from active roster",
            delete_athlete not in post_delete_athlete_names,
            head_roster_after_delete,
        )

        status, created_program = create_program(
            client,
            temp_coach_tokens["access"],
            athlete_id,
            f"Docker UAT Program A {unique}",
        )
        expect_status(results, "temporary coach creates program", status, 201, created_program)
        program_id = created_program.get("id") if isinstance(created_program, dict) else None
        check(results, "created program has id", isinstance(program_id, int), created_program)

        status, created_program_b = create_program(
            client,
            rbac_coach_b_tokens["access"],
            athlete_b_id,
            f"Docker UAT Program B {unique}",
        )
        expect_status(results, "RBAC coach B creates program for athlete B", status, 201, created_program_b)
        program_b_id = created_program_b.get("id") if isinstance(created_program_b, dict) else None
        check(results, "RBAC program B has id", isinstance(program_b_id, int), created_program_b)

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

        status, payload = client.request(
            "GET",
            f"/api/athletes/prs/?athlete_id={athlete_b_id}",
            token=temp_coach_tokens["access"],
        )
        expect_status(results, "RBAC coach A cannot read athlete B PRs", status, 403, payload)

        status, payload = client.request(
            "GET",
            f"/api/athletes/workouts/?athlete_id={athlete_b_id}",
            token=temp_coach_tokens["access"],
        )
        expect_status(results, "RBAC coach A cannot read athlete B workouts", status, 403, payload)

        status, payload = client.request(
            "PATCH",
            f"/api/programs/{program_id}/assign/",
            {"athlete_id": athlete_b_id},
            token=temp_coach_tokens["access"],
        )
        expect_status(results, "RBAC coach A cannot assign program to athlete B", status, 403, payload)

        status, payload = client.request(
            "POST",
            "/api/programs/",
            {
                "name": f"Forbidden Cross Coach Program {unique}",
                "description": "Should be blocked by RBAC.",
                "start_date": str(date.today()),
                "end_date": None,
                "athlete_id": athlete_id,
                "program_data": sample_program_data(),
            },
            token=rbac_coach_b_tokens["access"],
        )
        expect_status(results, "RBAC coach B cannot create program for athlete A", status, 400, payload)

        status, payload = client.request(
            "PATCH",
            f"/api/programs/{program_id}/",
            {"description": "Cross-coach update should fail."},
            token=rbac_coach_b_tokens["access"],
        )
        expect_status(results, "RBAC coach B cannot patch coach A program", status, 404, payload)

        status, payload = client.request(
            "GET",
            f"/api/athletes/program-completion/{program_b_id}/",
            token=temp_athlete_tokens["access"],
        )
        expect_status(results, "RBAC athlete A cannot read athlete B completion", status, 403, payload)

        status, payload = client.request(
            "PATCH",
            f"/api/athletes/program-completion/{program_b_id}/",
            completion_payload,
            token=temp_athlete_tokens["access"],
        )
        expect_status(results, "RBAC athlete A cannot patch athlete B completion", status, 404, payload)

        status, reset_payload = client.request(
            "POST",
            "/api/auth/password-reset/",
            {"email": email_for(temp_athlete_base)},
        )
        expect_status(results, "password reset request accepts known email", status, 200, reset_payload)
        reset_url = reset_payload.get("debug_reset_url") if isinstance(reset_payload, dict) else None
        parsed_reset = urllib.parse.urlparse(reset_url or "")
        reset_query = urllib.parse.parse_qs(parsed_reset.query)
        reset_uid = reset_query.get("uid", [None])[0]
        reset_token = reset_query.get("token", [None])[0]
        check(
            results,
            "password reset returns Docker debug reset URL",
            bool(reset_uid and reset_token),
            {"reset_url_present": bool(reset_url)},
        )

        new_password = f"ResetPassw0rd!{unique[-6:]}"
        status, payload = client.request(
            "POST",
            "/api/auth/password-reset/confirm/",
            {"uid": reset_uid, "token": reset_token, "password": new_password},
        )
        expect_status(results, "password reset confirmation changes password", status, 200, payload)

        status, payload = client.request(
            "POST",
            "/api/auth/token/",
            {"username": temp_athlete, "password": args.password},
        )
        expect_status(results, "old password rejected after reset", status, 401, payload)
        status, payload = client.request(
            "POST",
            "/api/auth/token/",
            {"username": temp_athlete, "password": new_password},
        )
        expect_status(results, "new password accepted after reset", status, 200, payload)
    except Exception as exc:  # noqa: BLE001 - converted to structured report
        check(results, "UAT raised unexpected exception", False, {"error": str(exc)})

    total_ct = len(results)
    passed_n = sum(1 for item in results if item["passed"])
    failed_n = sum(1 for item in results if not item["passed"])
    summary = {
        "started_at": started_at,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "backend_url": args.backend_url,
        "frontend_url": args.frontend_url,
        "total": total_ct,
        "passed": passed_n,
        "failed": failed_n,
        "pass_rate": round(passed_n / total_ct, 6) if total_ct else 0.0,
        "ssvc_metrics": {
            "checks_total": total_ct,
            "checks_passed": passed_n,
            "checks_failed": failed_n,
            "pass_rate": round(passed_n / total_ct, 6) if total_ct else 0.0,
            "frontend_head_dashboard_bundle": next(
                (
                    r.get("detail")
                    for r in results
                    if r.get("name")
                    == "frontend bundle includes head skill-roster stamp and not stale athlete-table combo"
                ),
                None,
            ),
        },
        "results": results,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
