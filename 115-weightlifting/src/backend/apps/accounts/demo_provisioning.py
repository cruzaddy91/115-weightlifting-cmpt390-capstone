from __future__ import annotations

import random
import os
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import OrgLaneAssignment
from apps.accounts.org_labels import (
    AGM_PREFIXES,
    DEMO_ATHLETE_USERNAME,
    DEMO_COACH_USERNAME,
    DEMO_HEAD_COACH_USERNAMES,
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


def _head_suffix(index: int) -> str:
    return ('Headcoachone', 'Headcoachtwo', 'Headcoachthree', 'Headcoachfour')[index]


def _coach_username(index: int) -> str:
    if index < len(DEMO_LINE_COACH_USERNAMES):
        return DEMO_LINE_COACH_USERNAMES[index]
    prefix = f'{22 + index:03d}'
    return f'{prefix}_Coach{index + 1}'


def _athlete_username(index: int) -> str:
    prefix_pool = ['000', *[f'{prefix:03d}' for prefix in range(5, 100)]]
    reserved = {username.split('_', 1)[0] for username in DEMO_LINE_COACH_USERNAMES}
    available = [prefix for prefix in prefix_pool if prefix not in reserved]
    prefix = available[index] if index < len(available) else f'{200 + index:03d}'
    return f'{prefix}_UAT3Athlete{index + 1:03d}'


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
    completions = []
    prs = []
    workouts = []
    for athlete in athletes:
        rng = _rng_for(scenario, athlete.username, 'history')
        coach = athlete.primary_coach or User.objects.get(username=MASTER_HEAD_USERNAME)
        program_count = rng.randint(3, 12)
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
    for program in TrainingProgram.objects.filter(athlete_id__in=athlete_ids, name__contains='--').order_by('id'):
        completions.append(
            ProgramCompletion(
                program=program,
                athlete=program.athlete,
                completion_data={'entries': {'0': {'0': {'completed': True, 'result': 'done', 'athlete_notes': 'Seeded UAT completion'}}}},
            )
        )
    ProgramCompletion.objects.bulk_create(completions, batch_size=500, ignore_conflicts=True)
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


def _preserve_current(gm: User, *, password: str = PASSWORD) -> list[User]:
    lane_heads = {}
    for idx, lane in enumerate(LANES):
        head = _ensure_user(f'{lane}_{_head_suffix(idx)}', 'head_coach', password=password)
        head.org_lane_prefix = lane
        head.save()
        lane_heads[lane] = head

    for idx, username in enumerate(DEMO_LINE_COACH_USERNAMES):
        lane = LANES[idx % len(LANES)]
        coach = _ensure_user(username, 'coach', password=password)
        coach.reports_to = lane_heads[lane]
        coach.org_lane_prefix = lane
        coach.save()
    existing_athletes = User.objects.filter(user_type='athlete', is_active=True)
    if not existing_athletes.exists():
        coaches = list(User.objects.filter(user_type='coach', is_active=True).order_by('username'))
        for idx, username in enumerate([DEMO_ATHLETE_USERNAME, *DEMO_UNASSIGNED_ATHLETE_USERNAMES]):
            coach = coaches[idx % len(coaches)] if coaches else gm
            athlete = _ensure_user(username, 'athlete', password=password)
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
    # Docker UAT / SSVC expect this exact pool: one athlete on DEMO_COACH, fifteen unassigned
    # (XXX_UNASSIGNED roster metadata). Do not skip when other athletes already exist — partial UAT
    # runs leave the DB inconsistent otherwise.
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
    aliases = {'fully_loaded': 'fully_loaded', 'half_cock': 'half_cock', 'bare_base': 'bare_base', 'skeleton': 'skeleton', 'preserve_current': 'preserve_current'}
    if scenario not in aliases:
        raise ValueError('Unknown scenario. Choose fully_loaded, half_cock, bare_base, skeleton, or preserve_current.')

    with transaction.atomic():
        gm = _ensure_user(MASTER_HEAD_USERNAME, 'head_coach', password=password)
        gm.org_lane_prefix = GM_PREFIX
        gm.save()
        if scenario == 'preserve_current':
            athletes = _preserve_current(gm, password=password)
        else:
            _reset_active_assignments()
            lane_heads: dict[str, User] = {}
            if scenario == 'bare_base':
                head_plan: list[tuple[str, str]] = []
            elif scenario == 'half_cock':
                head_plan = [('001', 'Headcoachone'), ('003', 'Headcoachtwo')]
            elif scenario == 'skeleton':
                head_plan = []
            else:
                head_plan = [(lane, _head_suffix(idx)) for idx, lane in enumerate(LANES)]

            for lane, suffix in head_plan:
                username = f'{lane}_{suffix}'
                head = _ensure_user(username, 'head_coach', password=password)
                head.org_lane_prefix = lane
                head.save()
                lane_heads[lane] = head

            if scenario == 'half_cock':
                lane_heads['002'] = lane_heads['001']
                lane_heads['004'] = lane_heads['003']

            if scenario == 'skeleton':
                for username in DEMO_HEAD_COACH_USERNAMES:
                    if username == MASTER_HEAD_USERNAME:
                        continue
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
                                _apply_demographics(athlete, scenario=scenario, skill_team='' if scenario == 'skeleton' else skill_team, index=athlete_index)
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
