#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

ensure_runtime_dirs

markdown_out="$REPORT_DIR/REPORT.md"
html_out="$REPORT_DIR/index.html"
snapshot_out="$REPORT_DIR/app_snapshot.json"

if [[ -x "$BACKEND_PYTHON" && -f "$BACKEND_ENV_FILE" ]]; then
  snapshot_json="$(backend_manage shell <<'PY'
import json
from django.contrib.auth import get_user_model

from apps.athletes.models import PersonalRecord, ProgramCompletion, WorkoutLog
from apps.programs.models import TrainingProgram

User = get_user_model()

completed_entries = 0
pending_entries = 0
for completion in ProgramCompletion.objects.all():
    entries = completion.completion_data.get('entries', {})
    for day_entries in entries.values():
        for exercise_entry in day_entries.values():
            if exercise_entry.get('completed'):
                completed_entries += 1
            else:
                pending_entries += 1

latest_program = TrainingProgram.objects.order_by('-created_at').values(
    'id',
    'name',
    'coach__username',
    'athlete__username',
    'created_at',
).first()
latest_workout = WorkoutLog.objects.order_by('-date', '-created_at').values(
    'id',
    'athlete__username',
    'date',
    'notes',
).first()
latest_pr = PersonalRecord.objects.order_by('-date', '-created_at').values(
    'id',
    'athlete__username',
    'lift_type',
    'weight',
    'date',
).first()

snapshot = {
    'available': True,
    'users': {
        'total': User.objects.count(),
        'coaches': User.objects.filter(user_type='coach').count(),
        'athletes': User.objects.filter(user_type='athlete').count(),
        'demo_users_present': list(
            User.objects.filter(username__in=['coach_smoke', 'athlete_smoke']).values_list('username', flat=True)
        ),
    },
    'programs': {
        'total': TrainingProgram.objects.count(),
        'with_completion_records': ProgramCompletion.objects.values('program_id').distinct().count(),
        'latest': latest_program,
    },
    'completion': {
        'records': ProgramCompletion.objects.count(),
        'completed_entries': completed_entries,
        'pending_entries': pending_entries,
    },
    'workouts': {
        'total': WorkoutLog.objects.count(),
        'latest': latest_workout,
    },
    'prs': {
        'total': PersonalRecord.objects.count(),
        'by_lift': {
            'snatch': PersonalRecord.objects.filter(lift_type='snatch').count(),
            'clean_jerk': PersonalRecord.objects.filter(lift_type='clean_jerk').count(),
            'total': PersonalRecord.objects.filter(lift_type='total').count(),
        },
        'latest': latest_pr,
    },
}

print(json.dumps(snapshot, default=str))
PY
)"
  snapshot_json="$(printf '%s\n' "$snapshot_json" | tail -n 1)"
else
  snapshot_json='{"available":false}'
fi

printf '%s\n' "$snapshot_json" > "$snapshot_out"

python3 "$ROOT_DIR/scripts/lib/render_report.py" \
  --event-dir "$EVENT_DIR" \
  --snapshot "$snapshot_out" \
  --markdown-out "$markdown_out" \
  --html-out "$html_out"

echo "Report generated:"
echo "  Markdown: $markdown_out"
echo "  HTML:     $html_out"
echo "  Snapshot: $snapshot_out"
