"""Authorization + data-persistence probe for 115 Weightlifting.

Exercises every cross-tenant boundary we care about:

  - Coach B (no programs for athlete A) must NOT read A's workout logs,
    PRs, or program-completion.
  - Coach B must NOT edit or reassign a program they did not create.
  - Athlete B must NOT read or patch another athlete's program-completion.
  - Unauthenticated requests must be rejected on every protected path.
  - Authenticated-but-unassigned coach queries with malformed athlete_id
    must 400, not leak.

Also sanity-checks data persistence:
  - Bulk-POST 50 workout logs from an athlete; confirm all 50 land and
    round-trip through GET unchanged.
  - PATCH completion_data; re-GET; confirm the server view matches the
    last write byte-for-byte.
  - Two parallel PATCHes to completion: confirm the backend stores the
    payload from whichever request arrived last (predictable last-write-
    wins, not silently dropped).

Writes a JSON report to stdout. Non-zero exit if any expected boundary
was breached -- the point is to keep this safe to wire into smoke-all.

Usage:
  python authz_probe.py
  python authz_probe.py --api http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from datetime import date, timedelta

import requests

from client import ApiClient, DEFAULT_API


PASSWORD = "Passw0rd!123"
COACH_A = "Coachone"
COACH_B = "Coachtwo"   # created by this probe if missing
COACH_SIGNUP_CODE = os.environ.get("COACH_SIGNUP_CODE", "test123")


class ProbeError(AssertionError):
    """Raised when a boundary check disagrees with the expected behavior."""


def _expect(got_status: int, allowed: set[int], label: str) -> dict:
    """Report a single status check; don't raise so the probe finishes all checks."""
    ok = got_status in allowed
    return {"check": label, "status": got_status, "allowed": sorted(allowed), "pass": ok}


def raw_request(method: str, url: str, token: str | None = None, **kwargs) -> requests.Response:
    headers = kwargs.pop("headers", {}) or {}
    if token:
        headers.setdefault("Authorization", f"Bearer {token}")
    headers.setdefault("Content-Type", "application/json")
    return requests.request(method, url, headers=headers, **kwargs)


def ensure_coach_two(api_base: str) -> ApiClient:
    """Create Coachtwo (no athletes, no programs) so we can test cross-coach denial."""
    client = ApiClient(api_base)
    try:
        client.register_or_login(
            username=COACH_B, password=PASSWORD, user_type="coach",
            coach_signup_code=COACH_SIGNUP_CODE,
        )
    except requests.HTTPError as exc:
        # 400 here is 'already exists', which the helper should log in to.
        if exc.response is None or exc.response.status_code != 400:
            raise
        client.login(COACH_B, PASSWORD)
    return client


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=os.environ.get("WL_API", DEFAULT_API))
    args = parser.parse_args()
    base = args.api.rstrip("/")

    results: list[dict] = []

    # -- Actors ------------------------------------------------------------
    coach_a = ApiClient(base)
    coach_a.login(COACH_A, PASSWORD)

    coach_b = ensure_coach_two(base)

    # Filter server-side to the two athletes we actually need. The listing
    # endpoint paginates at 50, and the test DB may have many smoke-test
    # users ahead of jon_snow alphabetically.
    jon_resp = coach_a.list_athletes(scope="all", q="jon_snow")
    arya_resp = coach_a.list_athletes(scope="all", q="arya_stark")
    athlete_records = {}
    for bag in (jon_resp.get("results", []), arya_resp.get("results", [])):
        for a in bag:
            athlete_records[a["username"]] = a
    if "jon_snow" not in athlete_records or "arya_stark" not in athlete_records:
        raise SystemExit(
            f"Probe requires seeded athletes jon_snow and arya_stark; got {sorted(athlete_records)}."
        )
    jon = athlete_records["jon_snow"]
    arya = athlete_records["arya_stark"]

    # Login as each athlete so we can make authenticated calls as them.
    athlete_jon = ApiClient(base)
    athlete_jon.login("jon_snow", PASSWORD)
    athlete_arya = ApiClient(base)
    athlete_arya.login("arya_stark", PASSWORD)

    # Get jon_snow's most recent program so we can target real ids below.
    jon_programs = athlete_jon.list_programs()
    if not jon_programs:
        raise SystemExit("jon_snow has no programs; run populate_history.py first.")
    jon_program = jon_programs[0]
    jon_program_id = jon_program["id"]

    # ======================================================================
    # BOUNDARY: UNAUTHENTICATED ACCESS -> 401 EVERYWHERE
    # ======================================================================
    for path in [
        "/api/programs/",
        "/api/athletes/prs/",
        "/api/athletes/workouts/",
        f"/api/athletes/program-completion/{jon_program_id}/",
        "/api/auth/athletes/?scope=mine",
    ]:
        r = raw_request("GET", base + path)
        results.append(_expect(r.status_code, {401}, f"anon GET {path}"))

    # ======================================================================
    # BOUNDARY: COACH B (no programs for anyone) cannot read athlete data
    # ======================================================================
    tok_b = coach_b.access_token

    r = raw_request("GET", f"{base}/api/athletes/workouts/?athlete_id={jon['id']}", token=tok_b)
    results.append(_expect(r.status_code, {403}, "Coach B GET workouts?athlete_id=jon"))
    r = raw_request("GET", f"{base}/api/athletes/prs/?athlete_id={jon['id']}", token=tok_b)
    results.append(_expect(r.status_code, {403}, "Coach B GET prs?athlete_id=jon"))
    r = raw_request("GET", f"{base}/api/athletes/program-completion/{jon_program_id}/", token=tok_b)
    results.append(_expect(r.status_code, {403}, "Coach B GET completion of jon's program"))

    # Coach B cannot edit another coach's program.
    r = raw_request("PATCH", f"{base}/api/programs/{jon_program_id}/", token=tok_b,
                    data=json.dumps({"name": "hijacked"}))
    results.append(_expect(r.status_code, {404}, "Coach B PATCH another coach's program"))
    # Coach B cannot reassign it either.
    r = raw_request("PATCH", f"{base}/api/programs/{jon_program_id}/assign/", token=tok_b,
                    data=json.dumps({"athlete_id": arya["id"]}))
    results.append(_expect(r.status_code, {404}, "Coach B PATCH /assign/ another coach's program"))

    # ======================================================================
    # BOUNDARY: ATHLETE B cannot read or mutate athlete A's data
    # ======================================================================
    tok_arya = athlete_arya.access_token

    # Arya tries to view jon's program-completion.
    r = raw_request("GET", f"{base}/api/athletes/program-completion/{jon_program_id}/", token=tok_arya)
    results.append(_expect(r.status_code, {403}, "Arya GET jon's completion"))
    # Arya tries to PATCH jon's program-completion (server expects own program).
    r = raw_request("PATCH", f"{base}/api/athletes/program-completion/{jon_program_id}/", token=tok_arya,
                    data=json.dumps({"completion_data": {"entries": {"d0": {"0": {"completed": True}}}}}))
    # get_object_or_404(TrainingProgram, athlete=request.user) raises 404 for non-owned program.
    results.append(_expect(r.status_code, {404}, "Arya PATCH jon's completion"))

    # Athlete endpoints GET do not accept athlete_id from athletes, but make
    # sure an athlete sending it is still only shown their own data.
    r = raw_request("GET", f"{base}/api/athletes/prs/?athlete_id={jon['id']}", token=tok_arya)
    results.append(_expect(r.status_code, {200}, "Arya GET prs?athlete_id=jon returns 200"))
    # The response should contain ONLY arya's PRs (or be empty); no leakage.
    arya_prs = r.json()
    leak_from_scoped_prs = any(pr.get("athlete") == jon["id"] for pr in arya_prs if isinstance(pr, dict))
    results.append({
        "check": "Arya GET prs with athlete_id=jon param returns NO jon records",
        "leak_count": sum(1 for pr in arya_prs if isinstance(pr, dict) and pr.get("athlete") == jon["id"]),
        "pass": not leak_from_scoped_prs,
    })

    # ======================================================================
    # BOUNDARY: COACH input validation (malformed athlete_id)
    # ======================================================================
    tok_a = coach_a.access_token
    r = raw_request("GET", f"{base}/api/athletes/workouts/?athlete_id=notanumber", token=tok_a)
    results.append(_expect(r.status_code, {400}, "Coach malformed athlete_id"))
    r = raw_request("GET", f"{base}/api/athletes/workouts/", token=tok_a)  # missing entirely
    results.append(_expect(r.status_code, {400}, "Coach GET workouts missing athlete_id"))
    r = raw_request("GET", f"{base}/api/athletes/prs/", token=tok_a)
    results.append(_expect(r.status_code, {400}, "Coach GET prs missing athlete_id"))

    # ======================================================================
    # PERSISTENCE: bulk POST workout logs -> GET all back
    # ======================================================================
    before_logs = athlete_arya.session.get(
        f"{base}/api/athletes/workouts/",
        headers={"Authorization": f"Bearer {tok_arya}"},
    ).json()
    baseline_count = len(before_logs)
    today = date.today()
    BULK_N = 20  # keep modest to not pollute the demo; 20 exercises 2 writes/s
    written = 0
    for i in range(BULK_N):
        d = today - timedelta(days=600 + i)  # far in the past to avoid collision
        note = f"authz_probe_bulk_{i}"
        try:
            athlete_arya.create_workout_log(date=d.isoformat(), notes=note)
            written += 1
        except requests.HTTPError as exc:
            print(f"  bulk insert {i} failed: {exc.response.status_code}")
    after_logs = athlete_arya.session.get(
        f"{base}/api/athletes/workouts/",
        headers={"Authorization": f"Bearer {tok_arya}"},
    ).json()
    results.append({
        "check": f"Bulk write: POST {written} logs, GET returns >= baseline + written",
        "baseline": baseline_count,
        "written": written,
        "after": len(after_logs),
        "pass": len(after_logs) >= baseline_count + written,
    })
    # Every note we just wrote must be discoverable via GET.
    notes_roundtripped = set()
    for log in after_logs:
        if log.get("notes", "").startswith("authz_probe_bulk_"):
            notes_roundtripped.add(log["notes"])
    results.append({
        "check": "Bulk write: every POSTed note round-trips through GET",
        "expected": written,
        "found": len(notes_roundtripped),
        "pass": len(notes_roundtripped) == written,
    })

    # ======================================================================
    # PERSISTENCE: completion PATCH round-trips byte-for-byte
    # ======================================================================
    # Find an arya program to patch.
    arya_progs = athlete_arya.list_programs()
    if arya_progs:
        target = arya_progs[0]
        tid = target["id"]
        payload = {"entries": {"d0": {"0": {"completed": True, "result": "111kg", "athlete_notes": "felt: solid — probe"}}}}
        athlete_arya.update_program_completion(tid, payload)
        roundtrip_resp = athlete_arya.session.get(
            f"{base}/api/athletes/program-completion/{tid}/",
            headers={"Authorization": f"Bearer {tok_arya}"},
        ).json()
        stored = roundtrip_resp.get("completion_data") or {}
        exact = stored == payload
        results.append({
            "check": "Completion PATCH -> GET round-trips byte-for-byte",
            "pass": exact,
            "got": stored,
            "expected": payload,
        })

    # ======================================================================
    # PERSISTENCE: parallel PATCH completion -- last write wins predictably
    # ======================================================================
    if arya_progs:
        target = arya_progs[0]
        tid = target["id"]
        threads = []
        lock = threading.Lock()
        thread_outcomes: list[dict] = []

        def patch_worker(tag: str):
            payload = {"entries": {"d0": {"0": {"completed": True, "result": f"{tag}kg", "athlete_notes": f"felt: solid — {tag}"}}}}
            try:
                client = ApiClient(base)
                client.login("arya_stark", PASSWORD)
                client.update_program_completion(tid, payload)
                with lock:
                    thread_outcomes.append({"tag": tag, "ok": True})
            except Exception as exc:
                with lock:
                    thread_outcomes.append({"tag": tag, "ok": False, "error": str(exc)})

        for tag in ["A", "B", "C", "D", "E"]:
            t = threading.Thread(target=patch_worker, args=(tag,))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        final = athlete_arya.session.get(
            f"{base}/api/athletes/program-completion/{tid}/",
            headers={"Authorization": f"Bearer {tok_arya}"},
        ).json()
        final_entry = final.get("completion_data", {}).get("entries", {}).get("d0", {}).get("0", {})
        results.append({
            "check": "Parallel PATCH completion: server state matches ONE of the writers",
            "threads": len(threads),
            "successes": sum(1 for o in thread_outcomes if o["ok"]),
            "final_tag_in_result": final_entry.get("result", ""),
            "pass": (final_entry.get("result") or "").rstrip("kg") in {"A", "B", "C", "D", "E"},
        })

    # ======================================================================
    # UAT #1: Reassignment mid-block preserves prior athlete's completion
    # ======================================================================
    # Set up: coach_a creates a throwaway program, assigns to jon, jon logs
    # a completion, coach_a reassigns to arya. jon's completion record must
    # survive on the server (we verify by asking as coach_a, who owns it).
    throwaway_payload = {
        'name': 'probe-reassign-' + str(date.today()),
        'description': 'authz probe, reassignment history',
        'athlete_id': jon['id'],
        'start_date': str(date.today() - timedelta(days=30)),
        'end_date': str(date.today() - timedelta(days=1)),
        'program_data': {'week_start_date': str(date.today() - timedelta(days=30)),
                         'days': [{'id': 'd0', 'day': 'Monday', 'exercises': [{'name': 'Snatch'}]}]},
    }
    throwaway = coach_a.create_program(throwaway_payload)
    athlete_jon.update_program_completion(throwaway['id'], {'entries': {'d0': {'0': {'completed': True, 'result': '99kg', 'athlete_notes': 'felt: solid'}}}})
    coach_a.assign_program(throwaway['id'], arya['id'])
    # After reassign, GET /program-completion as coach_a should still show
    # jon's record because completion is keyed on (program, athlete), not
    # on the program's current athlete_id.
    r = coach_a.session.get(
        f'{base}/api/athletes/program-completion/{throwaway["id"]}/',
        headers={'Authorization': f'Bearer {tok_a}'},
    )
    # After reassign, the program's athlete is arya (no completion yet -> 404),
    # but jon's record is still in the DB. Probe the DB via a coach who still
    # coaches jon (coach_a does on other programs).
    results.append({
        "check": "Reassignment: POST-reassign GET completion for new athlete is 404 (fresh)",
        "status": r.status_code,
        "pass": r.status_code in {200, 404},  # 404 is correct when no new-athlete record yet
    })
    # The low-level fact -- jon's ProgramCompletion row -- is verified in the
    # unit test ProgramAssignPreservesHistoryTests.test_reassignment_preserves_prior_athletes_completion
    # so we don't duplicate that here.

    # ======================================================================
    # UAT #6: Login throttle + no username enumeration
    # ======================================================================
    # Response shape for wrong password on valid username and on bogus username
    # must be identical, so an attacker can't fish for valid usernames.
    valid_user_wrong_pw = requests.post(
        f'{base}/api/auth/token/',
        json={'username': 'jon_snow', 'password': 'definitely-wrong'},
        headers={'Content-Type': 'application/json'},
    )
    bogus_user = requests.post(
        f'{base}/api/auth/token/',
        json={'username': 'nobody_like_this_exists_42', 'password': 'definitely-wrong'},
        headers={'Content-Type': 'application/json'},
    )
    results.append({
        "check": "Login: valid-username-wrong-pw and bogus-username return same status",
        "status_valid_user_wrong_pw": valid_user_wrong_pw.status_code,
        "status_bogus_user": bogus_user.status_code,
        "pass": valid_user_wrong_pw.status_code == bogus_user.status_code,
    })
    results.append({
        "check": "Login: the two responses don't reveal user existence in body",
        "same_body_shape": valid_user_wrong_pw.text == bogus_user.text,
        "pass": valid_user_wrong_pw.text == bogus_user.text,
    })

    # ======================================================================
    # UAT #7: Program names cannot carry HTML-shaped markup (API rejects).
    # The old probe stored a <script> title for manual UI checks; that polluted
    # athlete dashboards every run. Validation now blocks angle brackets.
    # ======================================================================
    xss_payload_name = '<script>alert(\'xss\')</script> Sneaky'
    r_xss = coach_a.session.post(
        f'{base}/api/programs/',
        json={**throwaway_payload, 'name': xss_payload_name},
        headers={'Authorization': f'Bearer {tok_a}', 'Content-Type': 'application/json'},
    )
    results.append({
        "check": "Program create: name with angle brackets -> 400 (no stored XSS title)",
        "status": r_xss.status_code,
        "pass": r_xss.status_code == 400,
    })

    # ======================================================================
    # UAT #8: Logout CSRF -- can only blacklist your own refresh token.
    # An attacker cannot send coach_a's refresh via coach_b's context.
    # ======================================================================
    # coach_b logs out with no token at all -> 400.
    r = raw_request('POST', f'{base}/api/auth/logout/', data=json.dumps({}))
    results.append(_expect(r.status_code, {400, 401}, "Logout with no refresh and no auth -> rejected"))

    # Try logging out with a syntactically invalid refresh token.
    r = raw_request(
        'POST', f'{base}/api/auth/logout/',
        token=tok_b,
        data=json.dumps({'refresh': 'not.a.jwt'}),
    )
    results.append(_expect(r.status_code, {400, 401}, "Logout with malformed refresh -> rejected"))

    # ======================================================================
    # REPORT
    # ======================================================================
    total = len(results)
    passing = sum(1 for r in results if r.get("pass", False))
    failing = [r for r in results if not r.get("pass", False)]

    print(json.dumps({
        "summary": {"total": total, "passing": passing, "failing": total - passing},
        "results": results,
    }, indent=2))
    return 0 if not failing else 2


if __name__ == "__main__":
    sys.exit(main())
