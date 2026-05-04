"""Deterministic 3-year PR + workout simulation for demo athletes.

Used only by the seed_longterm_got_history management command. All randomness
is keyed per athlete username so re-seeding the same roster is stable.

Design goals:
  - Non-linear gains with occasional injury / deload plateaus.
  - ~6 block cycles per year (phase list repeats in days).
  - Bounded row counts: bulk_create friendly, no HTTP fan-out.
"""
from __future__ import annotations

import math
import random
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from django.contrib.auth import get_user_model

from .models import PersonalRecord, WorkoutLog

User = get_user_model()

# Mirrors tools/sim/populate_history.py so charts stay tier-distinct.
# bodyweight_kg + gender for these usernames must match tools/sim/character_sim_profiles.py
# (HTTP seed uses the same numbers for IWF class labels).
ATHLETE_PROFILES: dict[str, dict] = {
    'jon_snow': {
        'tier': 'world-class', 'bodyweight_kg': 85, 'gender': 'M',
        'snatch': (118, 172), 'clean_jerk': (148, 212),
    },
    'arya_stark': {
        'tier': 'pro', 'bodyweight_kg': 55, 'gender': 'F',
        'snatch': (62, 92), 'clean_jerk': (78, 116),
    },
    'tyrion_lannister': {
        'tier': 'advanced', 'bodyweight_kg': 67, 'gender': 'M',
        'snatch': (82, 118), 'clean_jerk': (102, 148),
    },
    'daenerys_targaryen': {
        'tier': 'pro', 'bodyweight_kg': 64, 'gender': 'F',
        'snatch': (68, 103), 'clean_jerk': (86, 129),
    },
    'sansa_stark': {
        'tier': 'advanced', 'bodyweight_kg': 71, 'gender': 'F',
        'snatch': (58, 86), 'clean_jerk': (72, 106),
    },
    # Coachtwo / lord-of-the-rings roster (first five names). bodyweight_kg + gender
    # must match tools/sim/character_sim_profiles.py.
    'frodo_baggins': {
        'tier': 'pro', 'bodyweight_kg': 58, 'gender': 'M',
        'snatch': (82, 98), 'clean_jerk': (100, 120),
    },
    'samwise_gamgee': {
        'tier': 'pro', 'bodyweight_kg': 72, 'gender': 'M',
        'snatch': (98, 118), 'clean_jerk': (122, 145),
    },
    'merry_brandybuck': {
        'tier': 'advanced', 'bodyweight_kg': 58, 'gender': 'M',
        'snatch': (70, 86), 'clean_jerk': (88, 106),
    },
    'pippin_took': {
        'tier': 'advanced', 'bodyweight_kg': 56, 'gender': 'M',
        'snatch': (68, 83), 'clean_jerk': (85, 102),
    },
    'gandalf_grey': {
        'tier': 'world-class', 'bodyweight_kg': 82, 'gender': 'M',
        'snatch': (115, 150), 'clean_jerk': (145, 185),
    },
}

# One full macrocycle (~33 weeks); repeats across the 3-year window.
PHASE_BLOCKS_WEEKS: tuple[tuple[str, int], ...] = (
    ('strength_conditioning', 6),
    ('progressive_overload', 8),
    ('strength', 6),
    ('taper', 2),
    ('deload', 2),
    ('peak', 2),
    ('off_season', 2),
)

SESSION_NOTES: tuple[str, ...] = (
    '', '', '', 'technical focus', 'felt strong', 'main lifts only',
    'accessory cut short', 'travel week — light', 'post-meet reset',
)


def _phase_at_day(day_index: int) -> str:
    """Map day offset from history start to a named phase (repeating cycle)."""
    cycle_days = sum(w * 7 for _, w in PHASE_BLOCKS_WEEKS)
    pos = day_index % cycle_days
    acc = 0
    for name, weeks in PHASE_BLOCKS_WEEKS:
        span = weeks * 7
        if pos < acc + span:
            return name
        acc += span
    return PHASE_BLOCKS_WEEKS[-1][0]


def _phase_pr_multiplier(phase: str) -> float:
    if phase in ('peak', 'progressive_overload'):
        return 1.06
    if phase == 'strength':
        return 1.02
    if phase == 'strength_conditioning':
        return 1.0
    if phase == 'taper':
        return 0.98
    if phase == 'deload':
        return 0.94
    if phase == 'off_season':
        return 0.88
    return 1.0


def _phase_workout_sessions_per_week(phase: str, rng: random.Random) -> int:
    base = {
        'strength_conditioning': (3, 5),
        'progressive_overload': (4, 6),
        'strength': (4, 5),
        'taper': (2, 4),
        'deload': (2, 3),
        'peak': (3, 5),
        'off_season': (0, 2),
    }.get(phase, (2, 4))
    lo, hi = base
    return rng.randint(lo, hi)


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _add_months(d: date, n: int) -> date:
    y, m = d.year, d.month + n
    while m > 12:
        m -= 12
        y += 1
    while m < 1:
        m += 12
        y -= 1
    last = monthrange(y, m)[1]
    return date(y, m, min(d.day, last))


def _pick_day_in_month(rng: random.Random, y: int, month: int) -> date:
    last = monthrange(y, month)[1]
    return date(y, month, rng.randint(8, last))


@dataclass
class SeedSummary:
    athletes: int
    pr_rows: int
    workout_rows: int
    deleted_prs: int
    deleted_workouts: int


def _iter_month_starts(start: date, end: date) -> Iterable[tuple[int, int]]:
    cur = _month_start(start)
    while cur <= end:
        yield cur.year, cur.month
        cur = _add_months(cur, 1)


def build_pr_and_workout_rows(
    *,
    athlete: User,
    profile: dict,
    history_start: date,
    history_end: date,
    rng: random.Random,
) -> tuple[list[PersonalRecord], list[WorkoutLog]]:
    """Synthesize PersonalRecord and WorkoutLog rows for one athlete."""
    sn0, sn1 = profile['snatch']
    cj0, cj1 = profile['clean_jerk']
    total_days = (history_end - history_start).days + 1

    pr_rows: list[PersonalRecord] = []
    workout_rows: list[WorkoutLog] = []

    prev_sn = float(sn0)
    prev_cj = float(cj0)
    prev_tot = float(sn0 + cj0)

    for year, month in _iter_month_starts(history_start, history_end):
        month_mid = date(year, month, 15)
        if month_mid < history_start or month_mid > history_end:
            continue
        day_index = (month_mid - history_start).days
        phase = _phase_at_day(max(0, day_index))
        pr_mul = _phase_pr_multiplier(phase)

        # Long-horizon trend with diminishing returns at the top.
        elapsed = (month_mid - history_start).days / max(1.0, float(total_days))
        curve = 1.0 - math.exp(-3.2 * elapsed)
        injury = rng.random() < 0.07
        injury_pen = rng.uniform(3, 12) if injury else 0.0

        target_sn = sn0 + (sn1 - sn0) * (curve ** 0.82) * pr_mul - injury_pen * (0.4 + 0.6 * curve)
        target_cj = cj0 + (cj1 - cj0) * (curve ** 0.82) * pr_mul - injury_pen * (0.35 + 0.55 * curve)

        noise_sn = rng.gauss(0, 1.1)
        noise_cj = rng.gauss(0, 1.4)
        sn = max(25.0, round(target_sn + noise_sn, 1))
        cj = max(35.0, round(target_cj + noise_cj, 1))

        # Monotonic-ish: allow tiny noise dips, never collapse.
        sn = max(prev_sn - 1.5, min(sn, sn1 + 3.0))
        cj = max(prev_cj - 1.5, min(cj, cj1 + 3.0))
        tot = max(80.0, round(sn + cj + rng.gauss(0, 1.8), 1))
        tot = max(prev_tot - 2.0, min(tot, sn1 + cj1 + 8.0))

        pr_date = _pick_day_in_month(rng, year, month)
        if pr_date < history_start:
            pr_date = history_start + timedelta(days=rng.randint(0, min(6, total_days - 1)))
        if pr_date > history_end:
            pr_date = history_end

        pr_rows.append(
            PersonalRecord(athlete=athlete, lift_type='snatch', weight=Decimal(str(sn)), date=pr_date),
        )
        pr_rows.append(
            PersonalRecord(athlete=athlete, lift_type='clean_jerk', weight=Decimal(str(cj)), date=pr_date),
        )
        pr_rows.append(
            PersonalRecord(athlete=athlete, lift_type='total', weight=Decimal(str(tot)), date=pr_date),
        )

        prev_sn, prev_cj, prev_tot = sn, cj, tot

    # Workouts: weekly buckets, volume follows phase; keeps row count modest.
    week_start = history_start - timedelta(days=history_start.weekday())
    while week_start <= history_end:
        day_index = max(0, (week_start - history_start).days)
        phase = _phase_at_day(day_index)
        sessions = _phase_workout_sessions_per_week(phase, rng)
        used_offsets: set[int] = set()
        for _ in range(sessions):
            for _try in range(14):
                off = rng.randint(0, 6)
                if off in used_offsets:
                    continue
                used_offsets.add(off)
                wdate = week_start + timedelta(days=off)
                if wdate < history_start or wdate > history_end:
                    continue
                workout_rows.append(
                    WorkoutLog(
                        athlete=athlete,
                        date=wdate,
                        notes=rng.choice(SESSION_NOTES),
                    ),
                )
                break
        week_start += timedelta(days=7)

    return pr_rows, workout_rows


def seed_longterm_for_usernames(
    *,
    usernames: list[str],
    replace: bool,
    years: int = 3,
    batch_size: int = 2500,
) -> SeedSummary:
    """Insert long-range demo history for known GoT-style athletes."""
    history_end = date.today()
    history_start = history_end - timedelta(days=365 * years + 1)

    deleted_prs = 0
    deleted_workouts = 0
    users: list[User] = []
    for uname in usernames:
        u = User.objects.filter(username=uname).first()
        if u is None:
            continue
        users.append(u)

    if replace and users:
        uid_list = [u.id for u in users]
        deleted_workouts, _ = WorkoutLog.objects.filter(athlete_id__in=uid_list).delete()
        deleted_prs, _ = PersonalRecord.objects.filter(athlete_id__in=uid_list).delete()

    all_prs: list[PersonalRecord] = []
    all_w: list[WorkoutLog] = []

    for athlete in users:
        profile = ATHLETE_PROFILES.get(athlete.username)
        if not profile:
            continue
        rng = random.Random(hash(athlete.username) & 0xFFFFFFFF)
        prs, ws = build_pr_and_workout_rows(
            athlete=athlete,
            profile=profile,
            history_start=history_start,
            history_end=history_end,
            rng=rng,
        )
        all_prs.extend(prs)
        all_w.extend(ws)

    for i in range(0, len(all_prs), batch_size):
        PersonalRecord.objects.bulk_create(all_prs[i : i + batch_size], batch_size=batch_size)
    for i in range(0, len(all_w), batch_size):
        WorkoutLog.objects.bulk_create(all_w[i : i + batch_size], batch_size=batch_size)

    # Align User.bodyweight_kg / gender with demo tiers so UI can show IWF class.
    for uname in usernames:
        prof = ATHLETE_PROFILES.get(uname)
        if not prof:
            continue
        User.objects.filter(username=uname, user_type='athlete').update(
            bodyweight_kg=prof['bodyweight_kg'],
            gender=prof['gender'],
        )

    return SeedSummary(
        athletes=len(users),
        pr_rows=len(all_prs),
        workout_rows=len(all_w),
        deleted_prs=deleted_prs,
        deleted_workouts=deleted_workouts,
    )
