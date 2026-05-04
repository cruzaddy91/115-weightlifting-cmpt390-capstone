from datetime import date, timedelta
from decimal import Decimal
import os

from django.contrib.auth import get_user_model

from apps.athletes.long_history_seed import seed_longterm_for_usernames
from apps.athletes.models import ProgramCompletion
from apps.programs.models import TrainingProgram

User = get_user_model()
PASSWORD = os.environ.get('DEMO_PASSWORD', 'Passw0rd!123')
athlete_usernames = [
    'jon_snow',
    'arya_stark',
    'tyrion_lannister',
    'daenerys_targaryen',
    'sansa_stark',
]

head, _ = User.objects.get_or_create(username='Headcoachone', defaults={'user_type': 'head_coach'})
head.user_type = 'head_coach'
head.is_active = True
head.set_password(PASSWORD)
head.save()

coach, _ = User.objects.get_or_create(username='Coachone', defaults={'user_type': 'coach'})
coach.user_type = 'coach'
coach.is_active = True
coach.reports_to = head
coach.set_password(PASSWORD)
coach.save()

for username in athlete_usernames:
    athlete, _ = User.objects.get_or_create(username=username, defaults={'user_type': 'athlete'})
    athlete.user_type = 'athlete'
    athlete.is_active = True
    athlete.primary_coach = coach
    athlete.set_password(PASSWORD)
    athlete.save()

# Keep repeated container starts deterministic for the demo cohort.
TrainingProgram.objects.filter(coach=coach, athlete__username__in=athlete_usernames).delete()
seed_longterm_for_usernames(usernames=athlete_usernames, replace=True, years=3)

jon = User.objects.get(username='jon_snow')
today = date.today()
week_start = today - timedelta(days=today.weekday())
program_specs = [
    ('Accumulation Block 1 -- jon_snow', week_start - timedelta(days=28), 0.72),
    ('Accumulation Block 2 -- jon_snow', week_start - timedelta(days=21), 0.76),
    ('Accumulation Block 3 -- jon_snow', week_start - timedelta(days=14), 0.80),
    ('Current Block -- jon_snow', week_start, 0.84),
]

for idx, (name, start, intensity) in enumerate(program_specs):
    program = TrainingProgram.objects.create(
        coach=coach,
        athlete=jon,
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
    ProgramCompletion.objects.create(program=program, athlete=jon, completion_data={'entries': completion_entries})

print({
    'head_coach': head.username,
    'coach': coach.username,
    'athletes': athlete_usernames,
    'jon_snow_programs': TrainingProgram.objects.filter(athlete=jon).count(),
})
