"""Seed a coach + athlete roster against the 115 Weightlifting API.

This is the first of several simulation entry points. Later additions will
sit next to this file (build_programs.py, simulate_completion.py,
stress_test.py, etc.) and share the same client + theme infrastructure.

Examples:

    # Default: Coachone + 5 Game of Thrones athletes
    python seed.py

    # Second coach with a different roster
    python seed.py --coach Coachtwo --athletes 12 --theme lord-of-the-rings

    # Custom API target (real host / remote stage)
    python seed.py --api https://wl.example.com --coach-signup-code $CODE

The script is idempotent: running it twice won't create duplicate users.
Existing users are re-used (login happens with the same password), so
re-seeding after a reset or schema change is safe.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable

import requests

from character_sim_profiles import resolve_sim_profile
from client import ApiClient, DEFAULT_API
from themes import available_themes, roster


DEFAULT_COACH = "Coachone"
DEFAULT_ATHLETES = 5
DEFAULT_THEME = "game-of-thrones"
DEFAULT_PASSWORD = "Passw0rd!123"
DEFAULT_COACH_SIGNUP_CODE = "test123"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed a coach + athlete roster for 115 Weightlifting simulation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--coach", default=DEFAULT_COACH,
                        help=f"Coach username (default: {DEFAULT_COACH})")
    parser.add_argument("--athletes", type=int, default=DEFAULT_ATHLETES,
                        help=f"Number of athletes to seed (default: {DEFAULT_ATHLETES})")
    parser.add_argument("--theme", default=DEFAULT_THEME, choices=list(available_themes()),
                        help=f"Character name pool (default: {DEFAULT_THEME})")
    parser.add_argument("--password", default=DEFAULT_PASSWORD,
                        help=f"Password used for every seeded user (default: {DEFAULT_PASSWORD})")
    parser.add_argument("--api", default=os.environ.get("WL_API", DEFAULT_API),
                        help=f"API base URL (env WL_API; default: {DEFAULT_API})")
    parser.add_argument("--coach-signup-code",
                        default=os.environ.get("COACH_SIGNUP_CODE", DEFAULT_COACH_SIGNUP_CODE),
                        help=f"Coach signup code (env COACH_SIGNUP_CODE; default: {DEFAULT_COACH_SIGNUP_CODE})")
    return parser.parse_args()


def ensure_user(
    api: str,
    username: str,
    password: str,
    user_type: str,
    coach_signup_code: str | None = None,
) -> tuple[dict, bool]:
    """Register (or log in to) a single user with its own session.

    One client per user keeps cookies / access tokens isolated so we can later
    use the same clients in parallel when we build the stress-test harness.
    """
    client = ApiClient(api)
    try:
        user, created = client.register_or_login(
            username=username,
            password=password,
            user_type=user_type,
            coach_signup_code=coach_signup_code if user_type == "coach" else None,
        )
    except requests.HTTPError as exc:
        body = ""
        try:
            body = exc.response.text if exc.response is not None else ""
        except Exception:
            pass
        raise SystemExit(
            f"HTTP error seeding {user_type} '{username}': "
            f"{exc.response.status_code if exc.response is not None else '?'} {body[:200]}"
        ) from exc
    return user, created


def summarize(coach: str, password: str, athletes: Iterable[tuple[str, bool]]) -> None:
    print()
    print("=" * 62)
    print("  DEMO CREDENTIALS")
    print("=" * 62)
    print(f"  Password for every account below: {password}")
    print(f"  Login: http://localhost:3000/login")
    print()
    print(f"  Coach")
    print(f"    {coach}")
    print()
    print(f"  Athletes")
    for username, _created in athletes:
        print(f"    {username}")
    print("=" * 62)


def main() -> int:
    args = parse_args()

    print(f"> API:      {args.api}")
    print(f"> Coach:    {args.coach}")
    print(f"> Athletes: {args.athletes}")
    print(f"> Theme:    {args.theme}")
    print()

    # 1. Coach
    _, coach_created = ensure_user(
        api=args.api,
        username=args.coach,
        password=args.password,
        user_type="coach",
        coach_signup_code=args.coach_signup_code,
    )
    flag = "created" if coach_created else "already existed, logged in"
    print(f"  coach   {args.coach:<24} {flag}")

    # 2. Athletes
    roster_names = roster(args.theme, args.athletes)
    athletes_state: list[tuple[str, bool]] = []
    for index, name in enumerate(roster_names):
        _, created = ensure_user(
            api=args.api, username=name, password=args.password, user_type="athlete",
        )
        athletes_state.append((name, created))
        flag = "created" if created else "already existed"
        print(f"  athlete {name:<24} {flag}")
        bw, gender = resolve_sim_profile(name, index)
        client = ApiClient(args.api)
        try:
            client.login(name, args.password)
            client.patch_me({"bodyweight_kg": bw, "gender": gender})
            print(f"           {'':24} profile {bw} kg / {gender} → class set")
        except Exception as exc:
            print(f"           {'':24} WARN could not set profile: {exc}")

    created_count = sum(1 for _, c in athletes_state if c)
    existed_count = len(athletes_state) - created_count

    print()
    print(f"Done. {created_count} new athlete(s), {existed_count} already existed.")

    # Helpful reminder about the scope=mine vs scope=all distinction so the
    # coach doesn't wonder where their roster went when they log in.
    print()
    print("Note: these athletes are visible under scope=all (the coach editor's")
    print("default). They only move into scope=mine once the coach has programs")
    print("assigned to them. Run the program-simulation tool (coming next) to")
    print("populate programs.")

    summarize(args.coach, args.password, athletes_state)

    return 0


if __name__ == "__main__":
    sys.exit(main())
