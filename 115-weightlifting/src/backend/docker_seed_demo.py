from datetime import date, timedelta
from decimal import Decimal
import os

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.athletes.long_history_seed import seed_longterm_for_usernames
from apps.athletes.models import ProgramCompletion
from apps.accounts.org_labels import (
    DEMO_ATHLETE_USERNAME,
    DEMO_COACH_USERNAME,
    DEMO_HEAD_COACH_USERNAMES,
    DEMO_LINE_COACH_USERNAMES,
    DEMO_UNASSIGNED_ATHLETE_USERNAMES,
    MASTER_HEAD_USERNAME,
)
from apps.programs.models import TrainingProgram

User = get_user_model()
PASSWORD = os.environ.get('DEMO_PASSWORD', 'Passw0rd!123')
DEMO_EMAIL_DOMAIN = os.environ.get('DEMO_EMAIL_DOMAIN', 'example.invalid')


def assigned_head_variants(username):
    suffix = username.split('_', 1)[1]
    return [f'{prefix}_{suffix}' for prefix in ('001', '002', '003', '004')]


def release_demo_email(email, except_user=None):
    blockers = User.objects.filter(email__iexact=email)
    if except_user is not None:
        blockers = blockers.exclude(pk=except_user.pk)
    for blocker in blockers:
        blocker.email = f'archived_{blocker.pk}@{DEMO_EMAIL_DOMAIN}'
        blocker.is_active = False
        blocker.save(update_fields=['email', 'is_active'])


athlete_usernames = [
    DEMO_ATHLETE_USERNAME,
]
legacy_demo_usernames = [
    '117_MASTER_CHIEF',
    'Headcoachone',
    '001_Headcoachtwo',
    '001_Headcoachthree',
    '001_Headcoachfour',
    '001_Headcoachfive',
    '002_Headcoachtwo',
    '002_Headcoachthree',
    '002_Headcoachfour',
    '002_Headcoachfive',
    '003_Headcoachtwo',
    '003_Headcoachthree',
    '003_Headcoachfour',
    '003_Headcoachfive',
    '004_Headcoachtwo',
    '004_Headcoachthree',
    '004_Headcoachfour',
    '004_Headcoachfive',
    'Coachone',
    '005_Coachone',
    '100_Coachone',
    '000_athelteone',
    'jon_snow',
    'arya_stark',
    'tyrion_lannister',
    'daenerys_targaryen',
    'sansa_stark',
    'frodo_baggins',
    'samwise_gamgee',
    'merry_brandybuck',
    'pippin_took',
    'gandalf_grey',
    'Coachtwo',
]

head, _ = User.objects.get_or_create(username=MASTER_HEAD_USERNAME, defaults={'user_type': 'head_coach'})
head.user_type = 'head_coach'
head.email = f'117_headcoachone@{DEMO_EMAIL_DOMAIN}'
head.is_active = True
head.set_password(PASSWORD)
head.save()

legacy_heads = User.objects.filter(username__in=['Headcoachone', '117_MASTER_CHIEF'])
for legacy_head in legacy_heads:
    User.objects.filter(reports_to=legacy_head).update(reports_to=head)
    User.objects.filter(primary_coach=legacy_head).update(primary_coach=head)
    TrainingProgram.objects.filter(coach=legacy_head).update(
        coach=head,
        updated_at=timezone.now(),
    )

for username in DEMO_HEAD_COACH_USERNAMES:
    if username == MASTER_HEAD_USERNAME:
        continue
    canonical_exists = User.objects.filter(username=username).exists()
    for assigned_variant in User.objects.filter(username__in=assigned_head_variants(username)):
        if not canonical_exists:
            assigned_variant.username = username
            assigned_variant.save(update_fields=['username'])
            canonical_exists = True
        else:
            assigned_variant.email = f'archived_{assigned_variant.id}@{DEMO_EMAIL_DOMAIN}'
            assigned_variant.is_active = False
            assigned_variant.save(update_fields=['email', 'is_active'])
    head_coach, _ = User.objects.get_or_create(username=username, defaults={'user_type': 'head_coach'})
    head_coach.user_type = 'head_coach'
    head_email = f'{username.lower()}@{DEMO_EMAIL_DOMAIN}'
    release_demo_email(head_email, except_user=head_coach)
    head_coach.email = head_email
    head_coach.is_active = True
    head_coach.reports_to = None
    head_coach.set_password(PASSWORD)
    head_coach.save()

line_coaches = {}
for username in DEMO_LINE_COACH_USERNAMES:
    coach, _ = User.objects.get_or_create(username=username, defaults={'user_type': 'coach'})
    coach.user_type = 'coach'
    coach.email = f'{username.lower()}@{DEMO_EMAIL_DOMAIN}'
    coach.is_active = True
    coach.reports_to = head
    coach.set_password(PASSWORD)
    coach.save()
    line_coaches[username] = coach
coach = line_coaches[DEMO_COACH_USERNAME]

legacy_coaches = User.objects.filter(username__in=['Coachone', '005_Coachone', '100_Coachone'])
for legacy_coach in legacy_coaches:
    User.objects.filter(primary_coach=legacy_coach).update(primary_coach=coach)
    TrainingProgram.objects.filter(coach=legacy_coach).update(
        coach=coach,
        updated_at=timezone.now(),
    )

for legacy in User.objects.filter(username__in=legacy_demo_usernames):
    legacy.is_active = False
    if legacy.user_type == 'athlete':
        legacy.primary_coach = None
        legacy.save(update_fields=['is_active', 'primary_coach'])
    elif legacy.user_type == 'coach':
        legacy.reports_to = None
        legacy.save(update_fields=['is_active', 'reports_to'])
    else:
        legacy.save(update_fields=['is_active'])

for username in athlete_usernames:
    athlete, _ = User.objects.get_or_create(username=username, defaults={'user_type': 'athlete'})
    athlete.user_type = 'athlete'
    athlete.email = f'{username}@{DEMO_EMAIL_DOMAIN}'
    athlete.is_active = True
    athlete.primary_coach = coach
    athlete.set_password(PASSWORD)
    athlete.save()

for username in DEMO_UNASSIGNED_ATHLETE_USERNAMES:
    athlete, _ = User.objects.get_or_create(username=username, defaults={'user_type': 'athlete'})
    athlete.user_type = 'athlete'
    athlete.email = f'{username.lower()}@{DEMO_EMAIL_DOMAIN}'
    athlete.is_active = True
    athlete.primary_coach = None
    athlete.set_password(PASSWORD)
    athlete.save()

# Keep repeated container starts deterministic for the demo cohort.
TrainingProgram.objects.filter(coach=coach, athlete__username__in=athlete_usernames).delete()
seed_longterm_for_usernames(usernames=athlete_usernames, replace=True, years=3)

demo_athlete = User.objects.get(username=DEMO_ATHLETE_USERNAME)
today = date.today()
week_start = today - timedelta(days=today.weekday())
program_specs = [
    (f'Accumulation Block 1 -- {DEMO_ATHLETE_USERNAME}', week_start - timedelta(days=28), 0.72),
    (f'Accumulation Block 2 -- {DEMO_ATHLETE_USERNAME}', week_start - timedelta(days=21), 0.76),
    (f'Accumulation Block 3 -- {DEMO_ATHLETE_USERNAME}', week_start - timedelta(days=14), 0.80),
    (f'Current Block -- {DEMO_ATHLETE_USERNAME}', week_start, 0.84),
]

for idx, (name, start, intensity) in enumerate(program_specs):
    program = TrainingProgram.objects.create(
        coach=coach,
        athlete=demo_athlete,
        name=name,
        description='Seeded Docker demo training block for professor review.',
        start_date=start,
        end_date=start + timedelta(days=6),
        style_tags=['demo', 'weightlifting'],
        program_data={
            'week_start_date': str(start),
            'days': [
                {
                    'day': 'Monday',
                    'exercises': [
                        {'name': 'Snatch', 'sets': '5', 'reps': '2', 'intensity': f'{int(intensity * 100)}%', 'notes': 'Speed under the bar'},
                        {'name': 'Back Squat', 'sets': '4', 'reps': '4', 'intensity': f'{int((intensity + 0.04) * 100)}%', 'notes': 'Controlled descent'},
                    ],
                },
                {
                    'day': 'Wednesday',
                    'exercises': [
                        {'name': 'Clean & Jerk', 'sets': '6', 'reps': '1', 'intensity': f'{int((intensity + 0.02) * 100)}%', 'notes': 'Own the jerk recovery'},
                        {'name': 'Clean Pull', 'sets': '4', 'reps': '3', 'intensity': f'{int((intensity + 0.12) * 100)}%', 'notes': 'Vertical finish'},
                    ],
                },
                {
                    'day': 'Friday',
                    'exercises': [
                        {'name': 'Power Snatch', 'sets': '4', 'reps': '2', 'intensity': f'{int((intensity - 0.05) * 100)}%', 'notes': 'Sharp turnover'},
                        {'name': 'Front Squat', 'sets': '3', 'reps': '3', 'intensity': f'{int((intensity + 0.03) * 100)}%', 'notes': 'Tall torso'},
                    ],
                },
            ],
        },
    )
    completion_entries = {}
    if idx < 3:
        completion_entries = {
            '0': {'0': {'completed': True, 'result': 'done', 'athlete_notes': 'Moved well'}, '1': {'completed': True, 'result': 'done', 'athlete_notes': 'Solid squats'}},
            '1': {'0': {'completed': True, 'result': 'done', 'athlete_notes': 'Good timing'}, '1': {'completed': True, 'result': 'done', 'athlete_notes': 'Pulls felt strong'}},
            '2': {'0': {'completed': True, 'result': 'done', 'athlete_notes': 'Fast'}, '1': {'completed': True, 'result': 'done', 'athlete_notes': 'No misses'}},
        }
    else:
        completion_entries = {
            '0': {'0': {'completed': True, 'result': 'completed', 'athlete_notes': 'Ready for demo'}, '1': {'completed': False, 'result': '', 'athlete_notes': ''}},
        }
    ProgramCompletion.objects.create(program=program, athlete=demo_athlete, completion_data={'entries': completion_entries})

print({
    'head_coach': head.username,
    'coach': coach.username,
    'athletes': athlete_usernames,
    'demo_athlete_programs': TrainingProgram.objects.filter(athlete=demo_athlete).count(),
    'archived_legacy_demo_users': list(
        User.objects.filter(username__in=legacy_demo_usernames, is_active=False)
        .order_by('username')
        .values_list('username', flat=True)
    ),
})
