from __future__ import annotations

from collections import defaultdict

from apps.accounts.weight_class import competitive_weight_class_label
from apps.athletes.models import ProgramCompletion
from apps.programs.models import TrainingProgram


def bodyweight_bucket(user):
    bw = user.bodyweight_kg
    if bw is None:
        return 'unknown'
    value = float(bw)
    if user.gender == 'F':
        if value < 59:
            return 'small'
        if value <= 71:
            return 'medium'
        return 'large'
    if user.gender == 'M':
        if value < 73:
            return 'small'
        if value <= 96:
            return 'medium'
        return 'large'
    return 'unknown'


def completion_ratio(completion_data):
    entries = (completion_data or {}).get('entries', {})
    total = 0
    done = 0
    for day_data in entries.values():
        if not isinstance(day_data, dict):
            continue
        for ex in day_data.values():
            if not isinstance(ex, dict):
                continue
            total += 1
            if ex.get('completed'):
                done += 1
    if total == 0:
        return 0.0
    return done / total


def estimate_program_volume(program_data):
    days = (program_data or {}).get('days', [])
    total_sets = 0
    total_reps = 0
    exercise_count = 0
    for day in days:
        exercises = day.get('exercises', []) if isinstance(day, dict) else []
        for ex in exercises:
            if not isinstance(ex, dict):
                continue
            exercise_count += 1
            sets = ex.get('sets')
            reps = ex.get('reps')
            try:
                total_sets += float(sets) if sets not in (None, '') else 0.0
            except (TypeError, ValueError):
                pass
            try:
                total_reps += float(reps) if reps not in (None, '') else 0.0
            except (TypeError, ValueError):
                pass
    return {
        'exercise_count': exercise_count,
        'total_sets': total_sets,
        'total_reps': total_reps,
    }


def build_training_rows_for_head(head, coach_ids, pr_delta_lookup):
    programs = (
        TrainingProgram.objects
        .select_related('athlete')
        .filter(coach_id__in=coach_ids)
        .order_by('-updated_at')
    )
    completion_by_program_athlete = {
        (row.program_id, row.athlete_id): row.completion_data
        for row in ProgramCompletion.objects.filter(program__coach_id__in=coach_ids)
    }
    rows = []
    for program in programs:
        athlete = program.athlete
        completion_data = completion_by_program_athlete.get((program.id, athlete.id), {})
        volume = estimate_program_volume(program.program_data)
        tags = program.style_tags or ['style:unclassified']
        style_tag = next((tag for tag in tags if str(tag).startswith('style:')), tags[0])
        rows.append({
            'program_id': program.id,
            'athlete_id': athlete.id,
            'style_tag': style_tag,
            'gender': athlete.gender or 'unknown',
            'bodyweight_bucket': bodyweight_bucket(athlete),
            'weight_class': competitive_weight_class_label(athlete.bodyweight_kg, athlete.gender) or 'unknown',
            'completion_ratio': completion_ratio(completion_data),
            'exercise_count': volume['exercise_count'],
            'total_sets': volume['total_sets'],
            'total_reps': volume['total_reps'],
            'pr_delta': pr_delta_lookup.get(program.id),
            'head_id': head.id,
        })
    return rows


def build_prediction_rows(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row['gender'], row['bodyweight_bucket'], row['weight_class'])].append(row)
    out = []
    for segment, items in grouped.items():
        out.append({
            'segment': {
                'gender': segment[0],
                'bodyweight_bucket': segment[1],
                'weight_class': segment[2],
            },
            'items': items,
        })
    return out

