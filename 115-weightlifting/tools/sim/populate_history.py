"""Populate each seeded athlete with advanced / pro / world-class historical data.

For every athlete in the roster this script generates:

  - 3 back-dated COMPLETED programs (16 -> 4 weeks ago, 4 weeks each) plus one
    CURRENT program (started 4 weeks ago, not yet fully finished). Every
    exercise in the past programs is marked completed with a realistic
    percent-of-1RM result, so the coach's per-program completion ring reads
    100% and the athlete's lifetime lift count is real.
  - A daily workout log for the last 60 calendar days so the streak pill and
    workout history list look lived-in.
  - A PR progression for snatch, clean & jerk, and total spanning the same
    16-week window, shaped as a tier-appropriate linear climb with realistic
    noise. These feed the PR history line chart on the athlete dashboard and
    populate both roles' Sinclair calculator with a current total + bodyweight.

Tiers are hard-coded so different athletes in the demo show different
progressions -- one world-class lifter, two pros, two advanced -- and charts
look different when the coach clicks between athletes.

The script is idempotent on the PR/workout side in the sense that re-running
it appends more rows (not strictly idempotent because POSTs don't dedupe).
Programs are always created fresh; a second run stacks another 4 programs
per athlete. If you want a clean slate, wipe ProgramCompletion / PersonalRecord
/ WorkoutLog / TrainingProgram in Django admin first.

Run after ``seed.py`` has created the coach + athletes:

    python populate_history.py

**Coach dashboard completion %** (per-program ring, “x/y done”) is driven by
``completion_data`` that this script writes (as each athlete). ``build_programs.py``
only creates programs with no completion, so those rings stay at 0% until
``populate_history.py`` (or the athlete checks boxes) runs.

**Same logic for Coachtwo as for Coachone**: limit the roster to one theme
so you only backfill the athletes for that coach, e.g. first five LotR
(after those users exist — ``seed.py`` / ``seed-coachtwo-lotr``):

    python populate_history.py --coach Coachtwo --roster-theme lord-of-the-rings --roster-size 5

For **Coachone + first five GoT** (default ``seed.py`` roster):

    python populate_history.py --coach Coachone --roster-theme game-of-thrones --roster-size 5

Without ``--roster-theme``, the script uses **every** username in
``ATHLETE_PROFILES``; users missing from the API will cause a hard error.
Each run **creates** new programs; delete older duplicates in admin if
re-running.

For ~3 years of PR + workout rows (bulk ORM, coach dashboard charts) from the
Django repo root:

    ./bin/zw seed-long-history --replace
    # (from repo root; wraps manage.py seed_longterm_got_history)

Credentials default to the seed-script defaults (Passw0rd!123, Coachone).
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import date, timedelta
from typing import Any

import requests

from client import ApiClient, DEFAULT_API
from program_generators import build_program_payload
from themes import available_themes, roster


COACH_USERNAME = "Coachone"
PASSWORD = "Passw0rd!123"

# Athlete profiles. Ranges are (start_1RM_16_weeks_ago, current_1RM_today) in kg.
# Picked to span tiers so the PR charts look visually distinct:
#   - world-class: 400+ Sinclair, competitive international lifters
#   - pro:         national-level performers
#   - advanced:    strong regional lifters
ATHLETE_PROFILES: dict[str, dict[str, Any]] = {
    "jon_snow": {
        "tier": "world-class", "bodyweight_kg": 85, "gender": "M",
        "snatch": (150, 172), "clean_jerk": (185, 212),
    },
    "arya_stark": {
        "tier": "pro", "bodyweight_kg": 55, "gender": "F",
        "snatch": (78, 92), "clean_jerk": (96, 116),
    },
    "tyrion_lannister": {
        "tier": "advanced", "bodyweight_kg": 67, "gender": "M",
        "snatch": (103, 118), "clean_jerk": (128, 148),
    },
    "daenerys_targaryen": {
        "tier": "pro", "bodyweight_kg": 64, "gender": "F",
        "snatch": (86, 103), "clean_jerk": (108, 129),
    },
    "sansa_stark": {
        "tier": "advanced", "bodyweight_kg": 71, "gender": "F",
        "snatch": (74, 86), "clean_jerk": (92, 106),
    },
    "frodo_baggins": {
        "tier": "pro", "bodyweight_kg": 58, "gender": "M",
        "snatch": (88, 98), "clean_jerk": (108, 120),
    },
    "samwise_gamgee": {
        "tier": "pro", "bodyweight_kg": 72, "gender": "M",
        "snatch": (105, 118), "clean_jerk": (130, 145),
    },
    "merry_brandybuck": {
        "tier": "advanced", "bodyweight_kg": 58, "gender": "M",
        "snatch": (76, 86), "clean_jerk": (94, 106),
    },
    "pippin_took": {
        "tier": "advanced", "bodyweight_kg": 56, "gender": "M",
        "snatch": (74, 83), "clean_jerk": (92, 102),
    },
    "gandalf_grey": {
        "tier": "world-class", "bodyweight_kg": 82, "gender": "M",
        "snatch": (125, 150), "clean_jerk": (158, 185),
    },
}

# Timeline knobs. 4 programs x 4 weeks = 16 weeks of history.
PAST_PROGRAM_COUNT = 3
PROGRAM_WEEKS = 4
CURRENT_PROGRAM_WEEKS = 4
WORKOUT_LOG_DAYS = 60
PR_POINTS_PER_LIFT = 8
# Portion of the CURRENT program that's already done by 'today'.
CURRENT_PROGRAM_DONE_RATIO = 0.45


FEEL_WEIGHTS = [("hard", 0.25), ("solid", 0.55), ("easy", 0.20)]
SESSION_NOTE_POOL = [
    "", "", "", "technical focus", "felt strong",
    "bar speed off the floor", "good lockouts",
    "a bit heavy -- stopped early",
    "main-lift only, cut accessory",
]


def _linspace(a: float, b: float, n: int) -> list[float]:
    if n <= 1:
        return [float(b)]
    step = (b - a) / (n - 1)
    return [a + step * i for i in range(n)]


def _weighted_choice(rng: random.Random, options: list[tuple[str, float]]) -> str:
    r = rng.random()
    cum = 0.0
    for value, weight in options:
        cum += weight
        if r <= cum:
            return value
    return options[-1][0]


def _result_weight_for_exercise(
    exercise: dict[str, str],
    *,
    snatch_1rm: float,
    clean_jerk_1rm: float,
    squat_1rm: float,
    rng: random.Random,
) -> str:
    """Turn a prescription row into a realistic 'what the athlete lifted' string.

    Priority: percent_1rm mapped to the matching lift family (snatch / CJ /
    squat-family), then RPE-style rough estimation, then the coach's explicit
    weight field, then a blank result for pure technique drills.
    """
    name = exercise.get("name", "").lower()
    pct_raw = exercise.get("percent_1rm", "")
    rpe_raw = exercise.get("rpe", "")
    weight_raw = exercise.get("weight", "")

    # Movement family -> which 1RM to base off of.
    if "snatch" in name:
        base = snatch_1rm
    elif "clean" in name or "jerk" in name:
        base = clean_jerk_1rm
    elif "squat" in name or "deadlift" in name or "good morning" in name or "press" in name:
        base = squat_1rm
    elif "row" in name or "overhead" in name or "balance" in name:
        base = snatch_1rm * 0.6
    else:
        base = snatch_1rm * 0.7

    if pct_raw.endswith("%"):
        try:
            pct = int(pct_raw.rstrip("%")) / 100
            kg = round(base * pct + rng.uniform(-1.5, 1.5))
            return f"{max(10, kg)}kg"
        except ValueError:
            pass
    if rpe_raw:
        # RPE 7 -> roughly 80%, RPE 9 -> 93%. Rough mapping, good enough for demo.
        try:
            rpe = float(rpe_raw)
            pct = 0.60 + (rpe / 10) * 0.35
            return f"{round(base * pct)}kg"
        except ValueError:
            pass
    if weight_raw:
        return weight_raw
    return ""


def _build_completion(
    program_data: dict,
    *,
    snatch_1rm: float,
    clean_jerk_1rm: float,
    squat_1rm: float,
    rng: random.Random,
    done_ratio: float = 1.0,
) -> dict:
    """Produce a completion_data dict for one program.

    done_ratio<1 leaves the tail of the program untouched so the coach ring
    reads < 100% and the athlete sees remaining work on the current block.
    """
    all_cells: list[tuple[str, str]] = []
    for day in program_data.get("days", []):
        for idx in range(len(day.get("exercises", []))):
            all_cells.append((day["id"], str(idx)))

    cutoff = int(round(len(all_cells) * done_ratio))
    done_cells = set(all_cells[:cutoff])

    entries: dict[str, dict] = {}
    for day in program_data.get("days", []):
        bag: dict[str, dict] = {}
        for idx, exercise in enumerate(day.get("exercises", [])):
            key = str(idx)
            result = _result_weight_for_exercise(
                exercise,
                snatch_1rm=snatch_1rm,
                clean_jerk_1rm=clean_jerk_1rm,
                squat_1rm=squat_1rm,
                rng=rng,
            )
            feel = _weighted_choice(rng, FEEL_WEIGHTS)
            bag[key] = {
                "completed": (day["id"], key) in done_cells,
                "result": result,
                "athlete_notes": f"felt: {feel}",
            }
        entries[day["id"]] = bag
    return {"entries": entries}


def _tier_label(tier: str) -> str:
    return tier.replace("-", " ").title()


def _generate_pr_points(
    *,
    lift_type: str,
    start_weight: float,
    end_weight: float,
    start_date: date,
    end_date: date,
    n_points: int,
    rng: random.Random,
) -> list[tuple[date, float]]:
    """Generate a tier-appropriate PR progression with realistic noise.

    Weights are rounded to 1kg; a small forward-biased noise term keeps the
    line from being a perfect linear staircase. An occasional soft dip
    simulates a missed attempt / retested PR at a lower weight.
    """
    weights = _linspace(start_weight, end_weight, n_points)
    total_days = (end_date - start_date).days
    step_days = max(1, total_days // max(1, n_points - 1))
    out: list[tuple[date, float]] = []
    for i, w in enumerate(weights):
        d = start_date + timedelta(days=step_days * i + rng.randint(-2, 2))
        if d > end_date:
            d = end_date
        if d < start_date:
            d = start_date
        noise = rng.gauss(0, 1.5)
        # Every ~4th entry dips slightly under trend to feel real.
        if i > 0 and rng.random() < 0.2:
            noise -= rng.uniform(1.0, 3.0)
        kg = max(10.0, round(w + noise))
        out.append((d, kg))
    # Always make the FINAL point the clean end_weight so the 'current 1RM'
    # used elsewhere in this script agrees with the last PR the chart shows.
    out[-1] = (end_date, float(round(end_weight)))
    return out


# ---------------------------------------------------------------------------
# Top-level per-athlete pipeline
# ---------------------------------------------------------------------------


def populate_athlete(
    *,
    coach: ApiClient,
    athlete_username: str,
    profile: dict,
    api_base: str,
    today: date,
    dry_run: bool = False,
) -> dict:
    """Create 4 programs for the athlete and fill their log / PR history.

    Returns a small dict summarizing what was written so the CLI can print a
    receipt.
    """
    rng = random.Random(f"populate:{athlete_username}")

    # Seeded randomness specific to this athlete so the fake data stays stable
    # on re-runs even if we re-seed programs (e.g. after a Django migration).
    snatch_start, snatch_end = profile["snatch"]
    cj_start, cj_end = profile["clean_jerk"]
    # Squat family ceiling ~ CJ + 30 kg for a realistic Olympic lifter.
    squat_end = cj_end + 30

    # Find the athlete's id via the coach's athlete list.
    athletes_page = coach.list_athletes(scope="all", q=athlete_username, page=1)
    matches = [a for a in athletes_page.get("results", []) if a["username"] == athlete_username]
    if not matches:
        raise SystemExit(
            f"Athlete '{athlete_username}' not found via coach's athlete list. "
            "Run seed.py first to create the roster."
        )
    athlete_id = matches[0]["id"]

    # Build the 4 (past + current) program windows on the calendar.
    total_programs = PAST_PROGRAM_COUNT + 1
    windows: list[tuple[date, date, bool]] = []
    # Past programs are adjacent, each PROGRAM_WEEKS long, ending at 'today - CURRENT_PROGRAM_WEEKS'.
    current_start = today - timedelta(days=CURRENT_PROGRAM_WEEKS * 7 - 1)
    past_end = current_start - timedelta(days=1)
    for i in range(PAST_PROGRAM_COUNT, 0, -1):
        window_end = past_end - timedelta(days=(i - 1) * PROGRAM_WEEKS * 7)
        window_start = window_end - timedelta(days=PROGRAM_WEEKS * 7 - 1)
        windows.append((window_start, window_end, False))  # is_current = False
    windows.append((current_start, today + timedelta(days=(CURRENT_PROGRAM_WEEKS * 7) - (today - current_start).days - 1), True))

    # Linear 1RM progression across the 4 programs. Past programs ride a ramp
    # from start_weight to one step below end_weight; current program finishes
    # at end_weight.
    snatch_program_1rms = _linspace(snatch_start, snatch_end, total_programs)
    cj_program_1rms = _linspace(cj_start, cj_end, total_programs)
    squat_program_1rms = [cj + 30 for cj in cj_program_1rms]

    created_programs: list[dict] = []
    print(f"\n-- {athlete_username} ({_tier_label(profile['tier'])}, {profile['bodyweight_kg']}kg) --")

    for i, (win_start, win_end, is_current) in enumerate(windows):
        block_snatch = snatch_program_1rms[i]
        block_cj = cj_program_1rms[i]
        block_squat = squat_program_1rms[i]
        block_num = i + 1
        name = (
            f"Accumulation Block {block_num} — {athlete_username}"
            if not is_current
            else f"Current Block — {athlete_username}"
        )
        description = (
            f"Back-dated {'completed' if not is_current else 'in-progress'} block. "
            f"{_tier_label(profile['tier'])} level; snatch ~{round(block_snatch)}kg, "
            f"clean & jerk ~{round(block_cj)}kg 1RMs."
        )
        payload = build_program_payload(
            athlete_id=athlete_id,
            athlete_username=athlete_username,
            start_date=win_start,
            block_weeks=PROGRAM_WEEKS,
            program_name=name,
            description=description,
            seed=hash((athlete_username, i)) & 0xFFFFFFFF,
        )
        # Force the end_date to our computed window (build_program_payload
        # derives end_date from start_date + block_weeks; we already set that).
        payload["end_date"] = win_end.isoformat()

        if dry_run:
            print(f"  [dry-run] would create: {name}  [{win_start} -> {win_end}]")
            continue
        program = coach.create_program(payload)
        print(f"  created program  id={program['id']:<5} {name}")
        done_ratio = CURRENT_PROGRAM_DONE_RATIO if is_current else 1.0
        completion = _build_completion(
            payload["program_data"],
            snatch_1rm=block_snatch,
            clean_jerk_1rm=block_cj,
            squat_1rm=block_squat,
            rng=rng,
            done_ratio=done_ratio,
        )
        created_programs.append({
            "id": program["id"],
            "completion": completion,
            "is_current": is_current,
        })

    if dry_run:
        return {"athlete": athlete_username, "programs": 0, "workout_logs": 0, "prs": 0}

    # Now login as the athlete to PATCH their completion_data and POST logs/PRs.
    athlete = ApiClient(api_base)
    athlete.login(athlete_username, PASSWORD)

    for prog in created_programs:
        athlete.update_program_completion(prog["id"], prog["completion"])

    log_count = 0
    start_log_date = today - timedelta(days=WORKOUT_LOG_DAYS - 1)
    for offset in range(WORKOUT_LOG_DAYS):
        log_date = start_log_date + timedelta(days=offset)
        note = rng.choice(SESSION_NOTE_POOL)
        try:
            athlete.create_workout_log(date=log_date.isoformat(), notes=note)
            log_count += 1
        except requests.HTTPError as exc:
            # Don't let a stray duplicate/date-validation failure kill the run.
            body = exc.response.text[:120] if exc.response is not None else ""
            print(f"  [warn] workout log {log_date} failed: {body}")

    pr_count = 0
    # Full PR history spans the entire 16-week window (first past program start
    # -> today) so the chart doesn't look truncated to the current block.
    history_start = windows[0][0]
    for lift_type, start_w, end_w in [
        ("snatch", snatch_start, snatch_end),
        ("clean_jerk", cj_start, cj_end),
    ]:
        points = _generate_pr_points(
            lift_type=lift_type,
            start_weight=start_w,
            end_weight=end_w,
            start_date=history_start,
            end_date=today,
            n_points=PR_POINTS_PER_LIFT,
            rng=rng,
        )
        for d, w in points:
            try:
                athlete.create_personal_record(lift_type=lift_type, weight=str(w), date=d.isoformat())
                pr_count += 1
            except requests.HTTPError as exc:
                body = exc.response.text[:120] if exc.response is not None else ""
                print(f"  [warn] PR {lift_type}@{w}kg on {d} failed: {body}")

    # Total PRs sampled from the same timeline so the three lines move together.
    total_points = _generate_pr_points(
        lift_type="total",
        start_weight=snatch_start + cj_start,
        end_weight=snatch_end + cj_end,
        start_date=history_start,
        end_date=today,
        n_points=PR_POINTS_PER_LIFT,
        rng=rng,
    )
    for d, w in total_points:
        try:
            athlete.create_personal_record(lift_type="total", weight=str(w), date=d.isoformat())
            pr_count += 1
        except requests.HTTPError as exc:
            body = exc.response.text[:120] if exc.response is not None else ""
            print(f"  [warn] PR total@{w}kg on {d} failed: {body}")

    print(f"  wrote {len(created_programs)} programs, {log_count} workout logs, {pr_count} PRs")
    return {
        "athlete": athlete_username,
        "programs": len(created_programs),
        "workout_logs": log_count,
        "prs": pr_count,
    }


def _profiles_for_args(args) -> dict[str, dict[str, Any]]:
    """Select which ATHLETE_PROFILES entries to run. Same logic as main()."""
    if not getattr(args, "roster_theme", None):
        return dict(ATHLETE_PROFILES)
    size = int(getattr(args, "roster_size", 5) or 5)
    names = roster(args.roster_theme, size)
    out: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for n in names:
        if n in ATHLETE_PROFILES:
            out[n] = ATHLETE_PROFILES[n]
        else:
            missing.append(n)
    if missing:
        raise SystemExit(
            f"No ATHLETE_PROFILES entry for: {missing!r}. "
            "Add profiles in populate_history.py (tiers, snatch, clean_jerk)."
        )
    if not out:
        raise SystemExit("No athletes to populate after --roster-theme filter.")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Populate each seeded athlete with realistic training history."
    )
    parser.add_argument("--api", default=os.environ.get("WL_API", DEFAULT_API))
    parser.add_argument("--coach", default=COACH_USERNAME)
    parser.add_argument("--password", default=PASSWORD)
    parser.add_argument("--dry-run", action="store_true",
                        help="Plan the program windows without writing anything.")
    parser.add_argument(
        "--roster-theme",
        default=None,
        choices=list(available_themes()),
        help=(
            "Only populate the first N names from this theme (see themes.roster). "
            "Use with --coach and --roster-size so e.g. Coachtwo + lord-of-the-rings "
            "mirrors Coachone + game-of-thrones without mixing rosters."
        ),
    )
    parser.add_argument(
        "--roster-size",
        type=int,
        default=5,
        help="With --roster-theme, how many usernames to take (default: 5).",
    )
    args = parser.parse_args()

    profiles_to_run = _profiles_for_args(args)

    print(f"> API:      {args.api}")
    print(f"> Coach:    {args.coach}")
    print(
        f"> Athletes: {len(profiles_to_run)}"
        + (f"  (roster: {args.roster_theme!r} x{args.roster_size})" if args.roster_theme else "  (all ATHLETE_PROFILES)"),
    )
    print(f"> Window:   {PAST_PROGRAM_COUNT + 1} programs x {PROGRAM_WEEKS} weeks (~16 weeks)")
    if args.dry_run:
        print("> DRY RUN — nothing will be written.")

    coach = ApiClient(args.api)
    try:
        coach.login(args.coach, args.password)
    except requests.HTTPError as exc:
        raise SystemExit(
            f"Coach login failed ({exc.response.status_code if exc.response else '?'}): "
            f"{exc.response.text[:200] if exc.response else ''}"
        ) from exc

    today = date.today()
    totals = {"programs": 0, "workout_logs": 0, "prs": 0}
    for athlete_username, profile in profiles_to_run.items():
        result = populate_athlete(
            coach=coach,
            athlete_username=athlete_username,
            profile=profile,
            api_base=args.api,
            today=today,
            dry_run=args.dry_run,
        )
        totals["programs"] += result["programs"]
        totals["workout_logs"] += result["workout_logs"]
        totals["prs"] += result["prs"]

    print()
    print("=" * 62)
    print(
        f"Wrote {totals['programs']} programs, "
        f"{totals['workout_logs']} workout logs, "
        f"{totals['prs']} PRs across {len(profiles_to_run)} athletes."
    )
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
