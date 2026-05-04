"""Create training programs for a coach's roster of athletes.

Runs after seed.py so the users already exist. Looks each athlete up by
username via the coach's athlete-list endpoint, then POSTs a fully-populated
program (5 days, ~15 exercises, proper intensity + tempo + rest) so the
coach dashboard has real data to exercise every surface:

  - scope=mine athlete roster (populates as programs get assigned)
  - program list-view rows with day/exercise counts + updated timestamps
  - editor round-trip (open -> edit -> save)
  - reassignment + preview

Usage:

  python build_programs.py                                 # Coachone, 5 athletes, 1 program each
  python build_programs.py --coach Coachtwo --theme lord-of-the-rings --athletes 10
  python build_programs.py --programs-per-athlete 2        # back-to-back 4-week blocks per athlete
  python build_programs.py --block-weeks 8                 # 8-week blocks instead of 4

Idempotency:
  This script creates new programs on every run -- it does not upsert. If
  you re-run you'll get duplicate programs per athlete. For clean state,
  use Django admin or the reset_demo.sh script to clear programs first.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

import requests

from client import ApiClient, DEFAULT_API
from program_generators import available_templates, build_program_payload
from themes import available_themes, roster


DEFAULT_COACH = "Coachone"
DEFAULT_COACH_PASSWORD = "Passw0rd!123"
DEFAULT_TEMPLATE = "classic-accumulation"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create training programs for a coach's roster of athletes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--coach", default=DEFAULT_COACH)
    parser.add_argument("--coach-password", default=DEFAULT_COACH_PASSWORD)
    parser.add_argument("--theme", default="game-of-thrones",
                        choices=list(available_themes()))
    parser.add_argument("--athletes", type=int, default=5,
                        help="How many athletes from the theme roster to program for")
    parser.add_argument("--programs-per-athlete", type=int, default=1,
                        help="Number of back-to-back blocks per athlete (each 'block-weeks' long)")
    parser.add_argument("--block-weeks", type=int, default=4,
                        help="Block length in weeks (default: 4)")
    parser.add_argument("--template", default=DEFAULT_TEMPLATE,
                        choices=available_templates())
    parser.add_argument("--api", default=os.environ.get("WL_API", DEFAULT_API))
    return parser.parse_args()


def find_athlete_id(coach_client: ApiClient, username: str) -> int:
    """Look up an athlete's numeric id by username via the coach's list endpoint."""
    result = coach_client.list_athletes(scope="all", q=username)
    for athlete in result.get("results", []):
        if athlete["username"] == username:
            return athlete["id"]
    raise SystemExit(
        f"Athlete '{username}' not found. Seed them first: "
        f"python seed.py --theme <theme> --athletes <N>"
    )


def main() -> int:
    args = parse_args()

    print(f"> API:                 {args.api}")
    print(f"> Coach:               {args.coach}")
    print(f"> Theme:               {args.theme}")
    print(f"> Roster size:         {args.athletes}")
    print(f"> Programs per athlete: {args.programs_per_athlete}")
    print(f"> Block length:        {args.block_weeks} weeks")
    print(f"> Template:            {args.template}")
    print()

    coach_client = ApiClient(args.api)
    try:
        coach_client.login(args.coach, args.coach_password)
    except requests.HTTPError as exc:
        raise SystemExit(
            f"Couldn't log in as {args.coach} ({exc}). "
            f"Seed the coach first: python seed.py --coach {args.coach}"
        )

    athlete_names = roster(args.theme, args.athletes)
    created = 0
    failed = 0

    for athlete_username in athlete_names:
        athlete_id = find_athlete_id(coach_client, athlete_username)
        for i in range(args.programs_per_athlete):
            # Stagger blocks backward in time when there's more than one per
            # athlete so the coach dashboard's 'updated' timestamps look
            # natural and nothing collides on start_date.
            start = date.today() - timedelta(weeks=args.block_weeks * i)
            if args.programs_per_athlete == 1:
                block_label = "Accumulation Block"
            elif i == 0:
                block_label = "Current Block"
            else:
                block_label = f"Prior Block #{i}"

            payload = build_program_payload(
                athlete_id=athlete_id,
                athlete_username=athlete_username,
                start_date=start,
                block_weeks=args.block_weeks,
                program_name=f"{block_label} — {athlete_username}",
                template=args.template,
            )
            try:
                result = coach_client.create_program(payload)
                created += 1
                print(f"  [{created:3d}]  {athlete_username:<26} \"{result['name']}\" "
                      f"(id {result['id']})")
            except requests.HTTPError as exc:
                failed += 1
                detail = ""
                if exc.response is not None:
                    try:
                        detail = exc.response.text[:200]
                    except Exception:
                        pass
                print(f"  FAIL {athlete_username}: {exc.response.status_code if exc.response is not None else '?'} {detail}")

    print()
    print(f"Done. {created} program(s) created, {failed} failed.")

    if created:
        print()
        print(f"Log in at http://localhost:3000/login as {args.coach} / {args.coach_password}")
        print("The programs list should now show every athlete above with day + exercise counts,")
        print("and scope=mine on the athlete dropdown will include them.")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
