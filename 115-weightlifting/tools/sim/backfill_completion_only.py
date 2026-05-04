"""Write completion_data for every program a coach already owns (no new programs).

Use when the coach dashboard shows 0/y done: ``build_programs`` creates
structure but athletes never PATCH completion. This logs in as each
athlete once and updates completion for that coach's programs using the
same synthetic completion as ``populate_history`` (_build_completion).

  python backfill_completion_only.py --coach Coachtwo
  python backfill_completion_only.py --coach Coachone --api http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from copy import deepcopy
from typing import Any

import requests

from client import ApiClient, DEFAULT_API

# Reuse the completion construction + athlete strength profiles
import populate_history as ph  # noqa: WPS301

DEFAULT_PROFILE: dict[str, Any] = {
    "tier": "pro",
    "bodyweight_kg": 70,
    "gender": "M",
    "snatch": (85, 100),
    "clean_jerk": (110, 125),
}


def _ensure_day_ids(program_data: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(program_data) if program_data else {}
    days = out.get("days") or []
    for i, day in enumerate(days):
        if not isinstance(day, dict):
            continue
        if not day.get("id"):
            day["id"] = f"d{i}"
    out["days"] = days
    return out


def _profile_for(username: str) -> dict[str, Any]:
    if username in ph.ATHLETE_PROFILES:
        return ph.ATHLETE_PROFILES[username]
    return DEFAULT_PROFILE


def _done_ratio_for_program(program_id: int, seed: int) -> float:
    """Tweak per program so not every ring is identical (still non-zero if >0.05)."""
    rng = random.Random(seed)
    return 0.40 + rng.random() * 0.5  # ~40%–90% of exercises marked done


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill program completion_data for a coach's existing programs.",
    )
    parser.add_argument("--api", default=os.environ.get("WL_API", DEFAULT_API))
    parser.add_argument("--coach", required=True, help="Coach username (e.g. Coachtwo, Coachone)")
    parser.add_argument(
        "--password",
        default=os.environ.get("DEMO_PASSWORD", ph.PASSWORD),
    )
    args = parser.parse_args()
    base = str(args.api).rstrip("/")

    coach = ApiClient(base)
    try:
        coach.login(args.coach, args.password)
    except requests.HTTPError as exc:
        raise SystemExit(
            f"Coach login failed: {exc!s} {getattr(getattr(exc, 'response', None), 'text', '')[:200]}",
        ) from exc

    progs = coach.list_programs()
    if not progs:
        print("No programs for this coach. Create some with build_programs.py or the editor first.")
        return 0

    by_athlete: dict[str, list[dict]] = {}
    for p in progs:
        u = p.get("athlete_username")
        if not u:
            continue
        by_athlete.setdefault(u, []).append(p)

    if not by_athlete:
        print("No programs with athlete_username in list. Nothing to do.")
        return 0

    print(f"> API: {base}")
    print(f"> Coach: {args.coach}  — {len(progs)} program(s) on wire, {len(by_athlete)} athlete(s)")
    print()

    for athlete_username, programs in by_athlete.items():
        profile = _profile_for(athlete_username)
        s_end = float(profile["snatch"][1])
        cj_end = float(profile["clean_jerk"][1])
        squat_1rm = cj_end + 30.0
        ac = ApiClient(base)
        ac.login(athlete_username, args.password)
        for p in programs:
            pid = p.get("id")
            pd = _ensure_day_ids(p.get("program_data") or {})
            if not (pd.get("days")):
                print(f"  skip id={pid} ({p.get('name')}) — no days")
                continue
            dr = _done_ratio_for_program(int(pid) if pid else 0, int(pid or 0))
            rng = random.Random((hash(athlete_username) ^ (pid or 0)) & 0xFFFFFFFF)
            comp = ph._build_completion(
                pd,
                snatch_1rm=s_end,
                clean_jerk_1rm=cj_end,
                squat_1rm=squat_1rm,
                rng=rng,
                done_ratio=dr,
            )
            ac.update_program_completion(int(pid), comp)
            n_cells = sum(len((d or {}).get("exercises") or []) for d in (pd.get("days") or []))
            n_done = sum(
                1
                for day in comp.get("entries", {}).values()
                for ex in (day or {}).values()
                if (ex or {}).get("completed")
            )
            print(
                f"  ok  id={pid}  @{athlete_username}  {p.get('name', '')[:48]!r}  "
                f"~{n_done}/{n_cells} completed ({int(dr * 100)}% plan slice)",
            )

    print()
    print("Done. Refresh the coach dashboard: rings should be non-zero.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
