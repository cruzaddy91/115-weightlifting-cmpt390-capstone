from __future__ import annotations

from collections import defaultdict
import random
import os
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import OrgLaneAssignment
from apps.accounts.canonical_usernames import (
    ALL_DEMO_RESERVED_MEMBER_PREFIXES,
    CANONICAL_ATHLETE_PREFIXES_32,
    DEMO_STANDALONE_HEAD_COACH_USERNAMES,
    LEGACY_USERNAME_TO_CANONICAL,
    agm_head_username,
    athlete_username,
)
from apps.accounts.org_labels import (
    AGM_PREFIXES,
    DEMO_ATHLETE_USERNAME,
    DEMO_COACH_USERNAME,
    DEMO_HEAD_COACH_USERNAMES,
    DEMO_LINE_COACH_SLOT_B_USERNAMES,
    DEMO_LINE_COACH_USERNAMES,
    DEMO_UNASSIGNED_ATHLETE_USERNAMES,
    GM_PREFIX,
    MASTER_HEAD_USERNAME,
)
from apps.athletes.long_history_seed import build_pr_and_workout_rows, profile_for_skill_team
from apps.athletes.models import PersonalRecord, ProgramCompletion, WorkoutLog
from apps.programs.models import TrainingProgram

User = get_user_model()

PASSWORD = os.environ.get('DEMO_PASSWORD', 'Passw0rd!123')
DEMO_EMAIL_DOMAIN = 'example.invalid'
LANES = ('001', '002', '003', '004')
SKILL_TEAMS = ('NOBLE', 'RED', 'SILVER', 'BLUE')
STYLE_ROTATION = (
    'strength_conditioning',
    'strength',
    'maintenance',
    'taper',
    'backoff',
    'peak',
)


@dataclass(frozen=True)
class ScenarioResult:
    scenario: str
    heads: int
    line_coaches: int
    athletes: int
    programs: int
    prs: int
    workouts: int


def _rng_for(*parts) -> random.Random:
    return random.Random(hash(':'.join(str(part) for part in parts)) & 0xFFFFFFFF)


def _email_for(username: str) -> str:
    return f'{username.lower()}@{DEMO_EMAIL_DOMAIN}'


def _ensure_user(username: str, user_type: str, *, password: str = PASSWORD) -> User:
    user, _created = User.objects.get_or_create(username=username, defaults={'user_type': user_type})
    blocker_qs = User.objects.filter(email__iexact=_email_for(username)).exclude(pk=user.pk)
    for blocker in blocker_qs:
        blocker.email = f'archived_{blocker.pk}@{DEMO_EMAIL_DOMAIN}'
        blocker.is_active = False
        blocker.save(update_fields=['email', 'is_active'])
    user.user_type = user_type
    user.email = _email_for(username)
    user.is_active = True
    user.deleted_at = None
    user.deleted_by = None
    user.recoverable_until = None
    user.set_password(password)
    return user


_CANONICAL_LINE_COACH_SLOTS = 8


def _migrate_demo_username(old_username: str, new_username: str) -> None:
    """Rename or merge a demo user into canonical handles (same rules as ``prune_demo_users``)."""
    old_user = User.objects.filter(username=old_username).first()
    if old_user is None:
        return
    new_user = User.objects.filter(username=new_username).first()
    if new_user is None:
        old_user.username = new_username
        old_user.save(update_fields=['username'])
        return
    User.objects.filter(reports_to=old_user).update(reports_to=new_user)
    User.objects.filter(primary_coach=old_user).update(primary_coach=new_user)
    TrainingProgram.objects.filter(coach=old_user).update(
        coach=new_user,
        updated_at=timezone.now(),
    )
    old_user.email = f'archived_{old_user.pk}@{DEMO_EMAIL_DOMAIN}'
    old_user.is_active = False
    old_user.save(update_fields=['email', 'is_active'])


def _coach_username(index: int) -> str:
    """Lanes 001–004: slot-A/B alternate; extra coaches use prefix ``026+`` with verbal suffix."""
    if index < _CANONICAL_LINE_COACH_SLOTS:
        lane_slot = index // 2
        if index % 2 == 0:
            return DEMO_LINE_COACH_USERNAMES[lane_slot]
        return DEMO_LINE_COACH_SLOT_B_USERNAMES[lane_slot]
    from apps.accounts.canonical_usernames import coach_username

    extra = index - _CANONICAL_LINE_COACH_SLOTS
    candidate = 26 + extra
    return coach_username(f'{candidate:03d}')


def _athlete_username(index: int) -> str:
    prefix_pool = ['000', *[f'{p:03d}' for p in range(5, 100)]]
    reserved = ALL_DEMO_RESERVED_MEMBER_PREFIXES
    available = [prefix for prefix in prefix_pool if prefix not in reserved]
    prefix = available[index] if index < len(available) else f'{200 + index:03d}'
    return athlete_username(prefix)


def _apply_demographics(athlete: User, *, scenario: str, skill_team: str, index: int) -> None:
    rng = _rng_for(scenario, athlete.username, 'demo')
    gender = rng.choice(['M', 'F'])
    bodyweight = Decimal(str(round(rng.uniform(53, 118) if gender == 'M' else rng.uniform(45, 89), 2)))
    age = rng.randint(16, 43)
    athlete.gender = gender
    athlete.bodyweight_kg = bodyweight
    athlete.date_of_birth = date.today().replace(year=date.today().year - age) - timedelta(days=rng.randint(0, 360))
    if skill_team:
        athlete.skill_team = skill_team
        athlete.skill_team_updated_by_role = 'GMHC'
        athlete.skill_team_updated_at = timezone.now()


def _program_data(week_start: date, intensity: float) -> dict:
    return {
        'week_start_date': str(week_start),
        'days': [
            {
                'day': 'Monday',
                'exercises': [
                    {'name': 'Snatch', 'sets': '5', 'reps': '2', 'intensity': f'{int(intensity * 100)}%', 'notes': 'UAT skill-team block'},
                    {'name': 'Back Squat', 'sets': '4', 'reps': '4', 'intensity': f'{int((intensity + 0.05) * 100)}%', 'notes': 'Posture first'},
                ],
            },
            {
                'day': 'Wednesday',
                'exercises': [
                    {'name': 'Clean & Jerk', 'sets': '6', 'reps': '1', 'intensity': f'{int((intensity + 0.02) * 100)}%', 'notes': 'Stable catch'},
                    {'name': 'Clean Pull', 'sets': '4', 'reps': '3', 'intensity': f'{int((intensity + 0.12) * 100)}%', 'notes': 'Vertical finish'},
                ],
            },
            {
                'day': 'Friday',
                'exercises': [
                    {'name': 'Power Snatch', 'sets': '4', 'reps': '2', 'intensity': f'{int((intensity - 0.04) * 100)}%', 'notes': 'Fast turnover'},
                    {'name': 'Front Squat', 'sets': '3', 'reps': '3', 'intensity': f'{int((intensity + 0.04) * 100)}%', 'notes': 'Meet positions'},
                ],
            },
        ],
    }


def _parse_intensity_pct(exercise: dict) -> float:
    raw = str(exercise.get('intensity') or '70%').replace('%', '').strip()
    try:
        return max(35.0, min(105.0, float(raw)))
    except ValueError:
        return 70.0


def tier_simulated_result(exercise: dict, profile: dict, rng: random.Random) -> str:
    """Human-readable load line from prescription intensity × tier-scaled profile."""
    pct = _parse_intensity_pct(exercise)
    sn_lo, sn_hi = profile['snatch']
    cj_lo, cj_hi = profile['clean_jerk']
    sn_mid = (float(sn_lo) + float(sn_hi)) / 2.0
    cj_mid = (float(cj_lo) + float(cj_hi)) / 2.0
    name = (exercise.get('name') or '').lower()
    if 'snatch' in name:
        base = sn_mid
    elif 'clean' in name and 'pull' in name:
        base = cj_mid * 1.08
    elif 'clean' in name or 'jerk' in name:
        base = cj_mid * 0.92
    elif 'squat' in name:
        base = max(sn_mid, cj_mid * 0.55) * 1.35
    else:
        base = sn_mid
    kg = base * (pct / 100.0) * rng.uniform(0.96, 1.04)
    kg = max(15.0, round(kg, 1))
    sets = exercise.get('sets', '?')
    reps = exercise.get('reps', '?')
    return f'{kg} kg × {sets}×{reps} @ ~{int(pct)}% prescription'


def full_completion_entries(program_data: dict, profile: dict, rng: random.Random) -> dict:
    entries: dict[str, dict] = {}
    days = program_data.get('days') or []
    for di, day in enumerate(days):
        day_entries: dict[str, dict] = {}
        for ei, ex in enumerate(day.get('exercises') or []):
            day_entries[str(ei)] = {
                'completed': True,
                'result': tier_simulated_result(ex, profile, rng),
                'athlete_notes': 'Demo seed — simulated prescription.',
            }
        entries[str(di)] = day_entries
    return {'entries': entries}


def partial_completion_entries(program_data: dict, profile: dict, rng: random.Random) -> dict:
    """Leave roughly half of day×exercise cells incomplete for dashboard contrast."""
    entries: dict[str, dict] = {}
    days = program_data.get('days') or []
    positions = [(di, ei) for di, day in enumerate(days) for ei, _ in enumerate(day.get('exercises') or [])]
    complete_positions: set[tuple[int, int]] = set()
    if positions:
        complete_positions = set(rng.sample(positions, k=max(1, len(positions) // 2)))
    for di, day in enumerate(days):
        exercises = day.get('exercises') or []
        day_entries: dict[str, dict] = {}
        for ei, ex in enumerate(exercises):
            if (di, ei) in complete_positions:
                day_entries[str(ei)] = {
                    'completed': True,
                    'result': tier_simulated_result(ex, profile, rng),
                    'athlete_notes': 'Demo seed — partial week.',
                }
            else:
                day_entries[str(ei)] = {'completed': False, 'result': '', 'athlete_notes': ''}
        entries[str(di)] = day_entries
    return {'entries': entries}


def _seed_programs_and_history(athletes: list[User], *, scenario: str, replace: bool) -> tuple[int, int, int]:
    if not athletes:
        return (0, 0, 0)
    athlete_ids = [athlete.id for athlete in athletes]
    if replace:
        TrainingProgram.objects.filter(athlete_id__in=athlete_ids).delete()
        PersonalRecord.objects.filter(athlete_id__in=athlete_ids).delete()
        WorkoutLog.objects.filter(athlete_id__in=athlete_ids).delete()

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    programs = []
    programs_this_run: dict[int, list[TrainingProgram]] = defaultdict(list)
    prs = []
    workouts = []
    for athlete in athletes:
        rng = _rng_for(scenario, athlete.username, 'history')
        coach = athlete.primary_coach or User.objects.get(username=MASTER_HEAD_USERNAME)
        program_count = rng.randint(3, 13)
        for idx in range(program_count):
            start = week_start - timedelta(days=7 * (program_count - idx))
            style = STYLE_ROTATION[idx % len(STYLE_ROTATION)]
            program = TrainingProgram(
                coach=coach,
                athlete=athlete,
                name=f'{style.replace("_", " ").title()} Block {idx + 1} -- {athlete.username}',
                normalized_name=f'{style}_uat3',
                style_tags=['uat3', style, (athlete.skill_team or 'unassigned').lower()],
                description='Deterministic UAT3 provisioning block.',
                start_date=start,
                end_date=start + timedelta(days=6),
                program_data=_program_data(start, 0.66 + min(idx, 6) * 0.025),
            )
            programs.append(program)
            programs_this_run[athlete.id].append(program)
        profile = profile_for_skill_team(
            username=athlete.username,
            skill_team=athlete.skill_team,
            gender=athlete.gender,
            bodyweight_kg=athlete.bodyweight_kg,
        )
        athlete_prs, athlete_workouts = build_pr_and_workout_rows(
            athlete=athlete,
            profile=profile,
            history_start=today - timedelta(days=365),
            history_end=today,
            rng=rng,
        )
        prs.extend(athlete_prs)
        workouts.extend(athlete_workouts)

    TrainingProgram.objects.bulk_create(programs, batch_size=500)
    completions = []
    for athlete in athletes:
        plist = programs_this_run.get(athlete.id, [])
        if not plist:
            continue
        profile = profile_for_skill_team(
            username=athlete.username,
            skill_team=athlete.skill_team,
            gender=athlete.gender,
            bodyweight_kg=athlete.bodyweight_kg,
        )
        inc_rng = _rng_for(scenario, athlete.username, 'incomplete_program_idx')
        incomplete_idx = inc_rng.randint(0, len(plist) - 1)
        for idx, program in enumerate(plist):
            pdata = program.program_data if isinstance(program.program_data, dict) else {}
            crng = _rng_for(scenario, athlete.username, 'completion', program.pk)
            if idx == incomplete_idx:
                completion_payload = partial_completion_entries(pdata, profile, crng)
            else:
                completion_payload = full_completion_entries(pdata, profile, crng)
            completions.append(
                ProgramCompletion(program=program, athlete=athlete, completion_data=completion_payload),
            )
    ProgramCompletion.objects.bulk_create(completions, batch_size=500)
    PersonalRecord.objects.bulk_create(prs, batch_size=2500)
    WorkoutLog.objects.bulk_create(workouts, batch_size=2500)
    return (len(programs), len(prs), len(workouts))


def _reset_active_assignments() -> None:
    User.objects.filter(user_type='coach').update(reports_to=None, org_lane_prefix='')
    User.objects.filter(user_type='athlete').update(
        primary_coach=None,
        org_lane_prefix='',
        skill_team='',
        skill_team_updated_by=None,
        skill_team_updated_by_role='',
        skill_team_updated_at=None,
    )
    OrgLaneAssignment.objects.all().delete()


def _provision_pkg_large(gm: User, *, password: str = PASSWORD) -> list[User]:
    """Baseline LARGE roster: 4 AGM heads, 8 line coaches, 32 canonically named athletes."""
    lane_heads: dict[str, User] = {}
    for lane in LANES:
        head = _ensure_user(agm_head_username(lane), 'head_coach', password=password)
        head.org_lane_prefix = lane
        head.save()
        lane_heads[lane] = head

    coaches_flat: list[User] = []
    for idx, lane in enumerate(LANES):
        head = lane_heads[lane]
        for username in (DEMO_LINE_COACH_USERNAMES[idx], DEMO_LINE_COACH_SLOT_B_USERNAMES[idx]):
            coach = _ensure_user(username, 'coach', password=password)
            coach.reports_to = head
            coach.org_lane_prefix = lane
            coach.save()
            coaches_flat.append(coach)

    athletes_out: list[User] = []
    for i, pfx in enumerate(CANONICAL_ATHLETE_PREFIXES_32):
        uname = athlete_username(pfx)
        athlete = _ensure_user(uname, 'athlete', password=password)
        athlete.primary_coach = coaches_flat[i % len(coaches_flat)]
        athlete.org_lane_prefix = athlete.primary_coach.org_lane_prefix or ''
        _apply_demographics(athlete, scenario='pkg_large', skill_team=SKILL_TEAMS[i % len(SKILL_TEAMS)], index=i)
        athlete.skill_team_updated_by = gm
        athlete.save()
        athletes_out.append(athlete)

    for lane, head in lane_heads.items():
        OrgLaneAssignment.objects.update_or_create(prefix=lane, defaults={'head_coach': head, 'updated_by': gm})

    demo_coach = User.objects.filter(username=DEMO_COACH_USERNAME, user_type='coach', is_active=True).first()
    if demo_coach:
        primary_demo = User.objects.filter(username=DEMO_ATHLETE_USERNAME, user_type='athlete').first()
        if primary_demo:
            primary_demo.primary_coach = demo_coach
            primary_demo.org_lane_prefix = ''
            primary_demo.save(update_fields=['primary_coach', 'org_lane_prefix'])
        for username in DEMO_UNASSIGNED_ATHLETE_USERNAMES:
            row = User.objects.filter(username=username, user_type='athlete').first()
            if row:
                row.primary_coach = None
                row.org_lane_prefix = ''
                row.save(update_fields=['primary_coach', 'org_lane_prefix'])

    return athletes_out


def _preserve_current(gm: User, *, password: str = PASSWORD) -> list[User]:
    _migrate_demo_username('121_Headcoachfive', '121_Headcoachone')
    _migrate_demo_username('001_Headcoachfive', '001_Headcoachone')
    for old_name, new_name in LEGACY_USERNAME_TO_CANONICAL:
        _migrate_demo_username(old_name, new_name)

    lane_heads = {}
    for lane in LANES:
        head = _ensure_user(agm_head_username(lane), 'head_coach', password=password)
        head.org_lane_prefix = lane
        head.save()
        lane_heads[lane] = head

    for idx, lane in enumerate(LANES):
        head = lane_heads[lane]
        for username in (DEMO_LINE_COACH_USERNAMES[idx], DEMO_LINE_COACH_SLOT_B_USERNAMES[idx]):
            coach = _ensure_user(username, 'coach', password=password)
            coach.reports_to = head
            coach.org_lane_prefix = lane
            coach.save()
    coaches = list(User.objects.filter(user_type='coach', is_active=True).order_by('username'))
    canon_athlete_list = [DEMO_ATHLETE_USERNAME, *DEMO_UNASSIGNED_ATHLETE_USERNAMES]
    for idx, username in enumerate(canon_athlete_list):
        existed_before = User.objects.filter(username=username).exists()
        athlete = _ensure_user(username, 'athlete', password=password)
        if not existed_before:
            coach = coaches[idx % len(coaches)] if coaches else gm
            athlete.primary_coach = coach
            athlete.org_lane_prefix = coach.org_lane_prefix or GM_PREFIX
            _apply_demographics(athlete, scenario='preserve_current', skill_team=SKILL_TEAMS[idx % len(SKILL_TEAMS)], index=idx)
            athlete.skill_team_updated_by = gm
            athlete.save()

    heads = list(User.objects.filter(user_type='head_coach', is_active=True).exclude(username=MASTER_HEAD_USERNAME))
    for head in heads:
        prefix = (head.org_lane_prefix or head.username.split('_', 1)[0])
        if prefix in AGM_PREFIXES:
            OrgLaneAssignment.objects.update_or_create(prefix=prefix, defaults={'head_coach': head, 'updated_by': gm})
    for coach in User.objects.filter(user_type='coach', is_active=True).select_related('reports_to'):
        if coach.org_lane_prefix:
            continue
        head = coach.reports_to
        prefix = head.org_lane_prefix if head else ''
        prefix = prefix or (head.username.split('_', 1)[0] if head and '_' in head.username else '')
        if prefix in AGM_PREFIXES:
            coach.org_lane_prefix = prefix
            coach.save(update_fields=['org_lane_prefix'])
    athletes = list(User.objects.filter(user_type='athlete', is_active=True).select_related('primary_coach', 'primary_coach__reports_to'))
    for idx, athlete in enumerate(athletes):
        if not athlete.org_lane_prefix and athlete.primary_coach_id:
            coach = athlete.primary_coach
            athlete.org_lane_prefix = coach.org_lane_prefix or ''
            if not athlete.org_lane_prefix and coach.reports_to_id:
                athlete.org_lane_prefix = coach.reports_to.org_lane_prefix or coach.reports_to.username.split('_', 1)[0]
        if athlete.org_lane_prefix == GM_PREFIX:
            athlete.org_lane_prefix = ''
        if not athlete.skill_team:
            skill_team = SKILL_TEAMS[idx % len(SKILL_TEAMS)]
            athlete.skill_team = skill_team
            athlete.skill_team_updated_by = gm
            athlete.skill_team_updated_by_role = 'GMHC'
            athlete.skill_team_updated_at = timezone.now()
        athlete.save(
            update_fields=[
                'org_lane_prefix',
                'skill_team',
                'skill_team_updated_by',
                'skill_team_updated_by_role',
                'skill_team_updated_at',
            ]
        )
    # Docker UAT / SSVC: primary athlete on DEMO_COACH; remaining canon athletes XXX_UNASSIGNED.
    demo_coach = User.objects.filter(username=DEMO_COACH_USERNAME, user_type='coach', is_active=True).first()
    if demo_coach:
        primary_demo = User.objects.filter(username=DEMO_ATHLETE_USERNAME, user_type='athlete').first()
        if primary_demo:
            primary_demo.primary_coach = demo_coach
            primary_demo.org_lane_prefix = ''
            primary_demo.save(update_fields=['primary_coach', 'org_lane_prefix'])
        for username in DEMO_UNASSIGNED_ATHLETE_USERNAMES:
            row = User.objects.filter(username=username, user_type='athlete').first()
            if not row:
                continue
            row.primary_coach = None
            row.org_lane_prefix = ''
            row.save(update_fields=['primary_coach', 'org_lane_prefix'])
    return athletes


def provision_uat3_scenario(*, scenario: str, replace_history: bool = True, password: str = PASSWORD) -> ScenarioResult:
    scenario = scenario.replace('-', '_').lower()
    aliases = {
        'fully_loaded': 'fully_loaded',
        'half_cock': 'half_cock',
        'bare_base': 'bare_base',
        'skeleton': 'skeleton',
        'preserve_current': 'preserve_current',
        'pkg_large': 'pkg_large',
    }
    if scenario not in aliases:
        raise ValueError(
            'Unknown scenario. Choose preserve_current, pkg_large, fully_loaded, half_cock, bare_base, or skeleton.',
        )

    with transaction.atomic():
        gm = _ensure_user(MASTER_HEAD_USERNAME, 'head_coach', password=password)
        gm.org_lane_prefix = GM_PREFIX
        gm.save()
        if scenario == 'preserve_current':
            athletes = _preserve_current(gm, password=password)
        elif scenario == 'pkg_large':
            _reset_active_assignments()
            athletes = _provision_pkg_large(gm, password=password)
        else:
            _reset_active_assignments()
            lane_heads: dict[str, User] = {}
            if scenario == 'bare_base':
                heads_to_create: list[tuple[str, str]] = []
            elif scenario == 'half_cock':
                heads_to_create = [('001', agm_head_username('001')), ('003', agm_head_username('003'))]
            elif scenario == 'skeleton':
                heads_to_create = []
            else:
                heads_to_create = [(lane, agm_head_username(lane)) for lane in LANES]

            for lane, username in heads_to_create:
                head = _ensure_user(username, 'head_coach', password=password)
                head.org_lane_prefix = lane
                head.save()
                lane_heads[lane] = head

            if scenario == 'half_cock':
                lane_heads['002'] = lane_heads['001']
                lane_heads['004'] = lane_heads['003']

            if scenario == 'skeleton':
                for username in DEMO_STANDALONE_HEAD_COACH_USERNAMES:
                    skeleton_head = _ensure_user(username, 'head_coach', password=password)
                    skeleton_head.org_lane_prefix = ''
                    skeleton_head.save()

            for lane in LANES:
                OrgLaneAssignment.objects.update_or_create(
                    prefix=lane,
                    defaults={'head_coach': None if scenario == 'skeleton' else lane_heads.get(lane), 'updated_by': gm},
                )

            athletes = []
            coach_index = 0
            athlete_index = 0
            if scenario == 'bare_base':
                for _idx in range(10):
                    athlete = _ensure_user(_athlete_username(athlete_index), 'athlete', password=password)
                    skill_team = SKILL_TEAMS[athlete_index % len(SKILL_TEAMS)]
                    athlete.primary_coach = gm
                    athlete.org_lane_prefix = GM_PREFIX
                    _apply_demographics(athlete, scenario=scenario, skill_team=skill_team, index=athlete_index)
                    athlete.skill_team_updated_by = gm
                    athlete.save()
                    athletes.append(athlete)
                    athlete_index += 1
            else:
                per_lc_counts = {
                    'fully_loaded': {'NOBLE': 2, 'RED': 4, 'SILVER': 1, 'BLUE': 8},
                    'skeleton': {'NOBLE': 2, 'RED': 4, 'SILVER': 1, 'BLUE': 8},
                    'half_cock': {'NOBLE': 1, 'RED': 2, 'SILVER': 1, 'BLUE': 4},
                }[scenario]
                lane_order = LANES if scenario != 'half_cock' else ('001', '002', '003', '004')
                for lane in lane_order:
                    head = lane_heads.get(lane)
                    for _coach_slot in range(2 if scenario != 'half_cock' else 1):
                        coach = _ensure_user(_coach_username(coach_index), 'coach', password=password)
                        coach.reports_to = None if scenario == 'skeleton' else head
                        coach.org_lane_prefix = '' if scenario == 'skeleton' else lane
                        coach.save()
                        coach_index += 1
                        for skill_team, count in per_lc_counts.items():
                            for _ in range(count):
                                athlete = _ensure_user(_athlete_username(athlete_index), 'athlete', password=password)
                                athlete.primary_coach = None if scenario == 'skeleton' else coach
                                athlete.org_lane_prefix = '' if scenario == 'skeleton' else lane
                                _apply_demographics(
                                    athlete,
                                    scenario=scenario,
                                    skill_team='' if scenario == 'skeleton' else skill_team,
                                    index=athlete_index,
                                )
                                if scenario != 'skeleton':
                                    athlete.skill_team_updated_by = gm
                                athlete.save()
                                athletes.append(athlete)
                                athlete_index += 1

        programs, prs, workouts = _seed_programs_and_history(athletes, scenario=scenario, replace=replace_history)

    return ScenarioResult(
        scenario=scenario,
        heads=User.objects.filter(user_type='head_coach', is_active=True).count(),
        line_coaches=User.objects.filter(user_type='coach', is_active=True).count(),
        athletes=len(athletes),
        programs=programs,
        prs=prs,
        workouts=workouts,
    )
