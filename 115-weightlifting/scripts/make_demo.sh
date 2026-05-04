#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

ensure_backend_venv
ensure_backend_env
ensure_runtime_dirs

echo "Resetting demo state first..."
"$ROOT_DIR/scripts/reset_demo.sh" --yes

echo "Seeding richer demo data..."
backend_manage shell <<'PY'
from datetime import date, timedelta

from django.contrib.auth import get_user_model

from apps.athletes.models import PersonalRecord, ProgramCompletion, WorkoutLog
from apps.programs.models import TrainingProgram

User = get_user_model()
coach = User.objects.get(username='coach_smoke')
athlete = User.objects.get(username='athlete_smoke')

today = date.today()
week_start = today - timedelta(days=today.weekday())

program = TrainingProgram.objects.create(
    coach=coach,
    athlete=athlete,
    name='Demo Peak Week',
    description='Sample competition-prep week seeded by make-demo.',
    start_date=week_start,
    end_date=week_start + timedelta(days=6),
    program_data={
        'week_start_date': str(week_start),
        'days': [
            {
                'day': 'Monday',
                'exercises': [
                    {'name': 'Snatch', 'sets': '5', 'reps': '2', 'intensity': '75%', 'notes': 'Fast finish'},
                    {'name': 'Back Squat', 'sets': '4', 'reps': '4', 'intensity': '78%', 'notes': 'Controlled tempo'},
                ],
            },
            {
                'day': 'Wednesday',
                'exercises': [
                    {'name': 'Clean & Jerk', 'sets': '6', 'reps': '1', 'intensity': '82%', 'notes': 'Own the jerk'},
                    {'name': 'Clean Pull', 'sets': '4', 'reps': '3', 'intensity': '95%', 'notes': 'Vertical finish'},
                ],
            },
            {
                'day': 'Friday',
                'exercises': [
                    {'name': 'Power Snatch', 'sets': '4', 'reps': '2', 'intensity': '70%', 'notes': 'Sharp turnover'},
                    {'name': 'Front Squat', 'sets': '3', 'reps': '3', 'intensity': '80%', 'notes': 'Strong rack'},
                ],
            },
        ],
    },
)

ProgramCompletion.objects.create(
    program=program,
    athlete=athlete,
    completion_data={
        'entries': {
            '0': {
                '0': {'completed': True, 'athlete_notes': 'Moved well.', 'result': '78x2'},
                '1': {'completed': True, 'athlete_notes': 'Last set hard.', 'result': '140x4'},
            },
            '1': {
                '0': {'completed': False, 'athlete_notes': 'Saved for tomorrow.', 'result': ''},
            },
        }
    },
)

workouts = [
    (week_start - timedelta(days=14), 'Volume session felt solid.'),
    (week_start - timedelta(days=9), 'Heavy clean day, bar speed improved.'),
    (week_start - timedelta(days=2), 'Taper session, low fatigue.'),
]
for workout_date, notes in workouts:
    WorkoutLog.objects.create(athlete=athlete, date=workout_date, notes=notes)

prs = [
    ('snatch', '79.00', week_start - timedelta(days=40)),
    ('snatch', '82.00', week_start - timedelta(days=10)),
    ('clean_jerk', '101.00', week_start - timedelta(days=35)),
    ('clean_jerk', '105.00', week_start - timedelta(days=7)),
    ('total', '184.00', week_start - timedelta(days=7)),
]
for lift_type, weight, pr_date in prs:
    PersonalRecord.objects.create(athlete=athlete, lift_type=lift_type, weight=weight, date=pr_date)

print({
    'coach': coach.username,
    'athlete': athlete.username,
    'program_id': program.id,
    'workout_logs': WorkoutLog.objects.filter(athlete=athlete).count(),
    'prs': PersonalRecord.objects.filter(athlete=athlete).count(),
})
PY

log_event "demo" "success" "make_demo.sh" '{"scenario":"rich-demo"}'
"$ROOT_DIR/scripts/report.sh" >/dev/null
echo "Demo scenario ready."
