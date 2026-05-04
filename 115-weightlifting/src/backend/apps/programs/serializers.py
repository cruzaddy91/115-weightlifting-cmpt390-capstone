import re

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.roles import coach_may_bind_athlete, is_head_coach, staff_coach_queryset
from apps.accounts.weight_class import competitive_weight_class_label

from .models import TrainingProgram, default_program_data

User = get_user_model()


def _plain_text_no_markup(value, field_label):
    """Reject angle brackets in user-facing text fields (XSS / UI confusion)."""
    if value in (None, ''):
        return value
    text = str(value)
    if '<' in text or '>' in text:
        raise serializers.ValidationError(
            f'{field_label} cannot contain "<" or ">".'
        )
    return text


def canonical_program_name(value):
    text = str(value or '').strip().lower()
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def derive_program_style_tags(program_data):
    tags = set()
    days = program_data.get('days') if isinstance(program_data, dict) else []
    if not isinstance(days, list):
        return []

    intensity_mode = str(program_data.get('intensity_mode') or '').strip()
    if intensity_mode in ('percent_1rm', 'rpe', 'weight'):
        tags.add(f'intensity_mode:{intensity_mode}')

    max_week = 1
    total_volume = 0
    lift_rows = 0
    pct_sum = 0.0
    pct_rows = 0
    low_rep_rows = 0
    olympic_hits = 0
    strength_hits = 0
    conditioning_hits = 0

    for day in days:
        exercises = day.get('exercises') if isinstance(day, dict) else []
        if not isinstance(exercises, list):
            continue
        for exercise in exercises:
            if not isinstance(exercise, dict):
                continue
            raw_week = str(exercise.get('week') or '').strip()
            try:
                if raw_week:
                    max_week = max(max_week, int(raw_week))
            except ValueError:
                pass

            name = str(exercise.get('name') or '').lower()
            if any(k in name for k in ('snatch', 'clean', 'jerk')):
                olympic_hits += 1
            if any(k in name for k in ('squat', 'deadlift', 'press', 'pull')):
                strength_hits += 1
            if any(k in name for k in ('run', 'row', 'bike', 'burpee', 'conditioning', 'emom', 'amrap')):
                conditioning_hits += 1

            sets = str(exercise.get('sets') or '').strip()
            reps = str(exercise.get('reps') or '').strip()
            try:
                sets_n = float(sets)
                reps_n = float(reps.split('+')[0]) if '+' in reps else float(reps)
                total_volume += sets_n * reps_n
                lift_rows += 1
                if reps_n <= 2:
                    low_rep_rows += 1
            except ValueError:
                pass

            pct = str(exercise.get('percent_1rm') or '').strip().replace('%', '')
            try:
                pct_sum += float(pct)
                pct_rows += 1
            except ValueError:
                pass

    tags.add(f'block:{max_week}wk')
    if olympic_hits > 0:
        tags.add('style:olympic')
    if strength_hits > 0:
        tags.add('style:strength')
    if conditioning_hits > 0:
        tags.add('style:conditioning')
    if lift_rows > 0:
        avg_volume = total_volume / lift_rows
        if avg_volume >= 20:
            tags.add('volume:high')
        elif avg_volume <= 8:
            tags.add('volume:low')
    if pct_rows > 0 and (pct_sum / pct_rows) >= 85 and low_rep_rows >= max(1, lift_rows // 3):
        tags.add('phase:peak')
    elif low_rep_rows >= max(1, lift_rows // 3):
        tags.add('phase:taper')
    return sorted(tags)


def normalize_program_data(value):
    if value in (None, ''):
        value = default_program_data()

    if not isinstance(value, dict):
        raise serializers.ValidationError('program_data must be an object.')

    # Coach display preference for intensity columns (% 1RM / RPE / weight).
    # Persisted so reopening a program restores the mode; frontend-only signal,
    # doesn't affect stored prescription data.
    intensity_mode = value.get('intensity_mode')
    if intensity_mode not in ('percent_1rm', 'rpe', 'weight'):
        intensity_mode = None

    normalized = {
        'week_start_date': str(value.get('week_start_date', '')),
        'days': [],
    }
    if intensity_mode:
        normalized['intensity_mode'] = intensity_mode

    days = value.get('days', [])
    if not isinstance(days, list):
        raise serializers.ValidationError('program_data.days must be a list.')

    for index, day in enumerate(days):
        if not isinstance(day, dict):
            raise serializers.ValidationError(f'program_data.days[{index}] must be an object.')

        exercises = day.get('exercises', [])
        if not isinstance(exercises, list):
            raise serializers.ValidationError(f'program_data.days[{index}].exercises must be a list.')

        # Preserve stable per-day id so athlete completion records survive day
        # reorder / rename. Frontend provides the id; fall back to a
        # position-based default so legacy programs still get a usable id.
        day_id = day.get('id')
        if not isinstance(day_id, str) or not day_id:
            day_id = f'd{index}'

        normalized_day = {
            'id': day_id,
            'day': str(day.get('day') or f'Day {index + 1}'),
            'exercises': [],
        }

        for exercise_index, exercise in enumerate(exercises):
            if not isinstance(exercise, dict):
                raise serializers.ValidationError(
                    f'program_data.days[{index}].exercises[{exercise_index}] must be an object.'
                )
            normalized_day['exercises'].append(
                {
                    'name': str(exercise.get('name', '')),
                    'sets': str(exercise.get('sets', '')),
                    'reps': str(exercise.get('reps', '')),
                    # Legacy combined intensity kept for backwards-compat with
                    # older frontends / consumers; new clients should prefer
                    # the explicit percent_1rm / rpe / weight fields below.
                    'intensity': str(exercise.get('intensity', '')),
                    'percent_1rm': str(exercise.get('percent_1rm', '')),
                    'rpe': str(exercise.get('rpe', '')),
                    'weight': str(exercise.get('weight', '')),
                    'tempo': str(exercise.get('tempo', '')),
                    'rest': str(exercise.get('rest', '')),
                    'week': str(exercise.get('week', '')),
                    'notes': str(exercise.get('notes', '')),
                }
            )

        normalized['days'].append(normalized_day)

    return normalized


class TrainingProgramSerializer(serializers.ModelSerializer):
    coach_id = serializers.IntegerField(source='coach.id', read_only=True)
    coach_username = serializers.CharField(source='coach.username', read_only=True)
    athlete_id = serializers.IntegerField(source='athlete.id', read_only=True)
    athlete_username = serializers.CharField(source='athlete.username', read_only=True)
    athlete_bodyweight_kg = serializers.DecimalField(
        source='athlete.bodyweight_kg',
        read_only=True,
        max_digits=6,
        decimal_places=2,
        allow_null=True,
    )
    athlete_gender = serializers.CharField(source='athlete.gender', read_only=True, allow_null=True)
    athlete_competitive_weight_class = serializers.SerializerMethodField()
    completion_data = serializers.SerializerMethodField()

    class Meta:
        model = TrainingProgram
        fields = [
            'id',
            'name',
            'normalized_name',
            'style_tags',
            'description',
            'start_date',
            'end_date',
            'program_data',
            'completion_data',
            'coach_id',
            'coach_username',
            'athlete_id',
            'athlete_username',
            'athlete_bodyweight_kg',
            'athlete_gender',
            'athlete_competitive_weight_class',
            'created_at',
            'updated_at',
        ]

    def get_athlete_competitive_weight_class(self, obj):
        a = obj.athlete
        return competitive_weight_class_label(a.bodyweight_kg, a.gender)

    def get_completion_data(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        user = request.user
        if user.user_type == 'athlete':
            if obj.athlete_id != user.id:
                return None
            target_athlete = user.id
        elif user.user_type == 'coach':
            if obj.coach_id != user.id:
                return None
            target_athlete = obj.athlete_id
        elif is_head_coach(user):
            staff_ids = set(staff_coach_queryset(user).values_list('id', flat=True))
            if obj.coach_id != user.id and obj.coach_id not in staff_ids:
                return None
            target_athlete = obj.athlete_id
        else:
            return None
        for record in getattr(obj, 'completion_records').all() if hasattr(obj, 'completion_records') else []:
            if record.athlete_id == target_athlete:
                return record.completion_data
        return None


class ProgramCreateSerializer(serializers.ModelSerializer):
    athlete_id = serializers.IntegerField(write_only=True)
    program_data = serializers.JSONField(required=False)

    class Meta:
        model = TrainingProgram
        fields = ['id', 'name', 'description', 'start_date', 'end_date', 'athlete_id', 'program_data']

    def validate_athlete_id(self, value):
        try:
            athlete = User.objects.get(id=value, user_type='athlete')
        except User.DoesNotExist:
            raise serializers.ValidationError('Selected athlete does not exist.')
        coach = self.context['request'].user
        if not coach_may_bind_athlete(coach, athlete):
            raise serializers.ValidationError('You can only select athletes you manage.')
        return athlete.id

    def validate_program_data(self, value):
        return normalize_program_data(value)

    def validate_name(self, value):
        return _plain_text_no_markup(value, 'Program name')

    def validate_description(self, value):
        return _plain_text_no_markup(value, 'Description')

    def create(self, validated_data):
        athlete_id = validated_data.pop('athlete_id')
        athlete = User.objects.get(id=athlete_id, user_type='athlete')
        coach = self.context['request'].user
        name = validated_data.get('name', '')
        program_data = validated_data.get('program_data', default_program_data())
        validated_data['normalized_name'] = canonical_program_name(name)
        validated_data['style_tags'] = derive_program_style_tags(program_data)
        program = TrainingProgram.objects.create(coach=coach, athlete=athlete, **validated_data)
        User.objects.filter(pk=athlete.id, user_type='athlete').update(primary_coach_id=coach.id)
        return program


class ProgramUpdateSerializer(serializers.ModelSerializer):
    athlete_id = serializers.IntegerField(write_only=True, required=False)
    program_data = serializers.JSONField(required=False)

    class Meta:
        model = TrainingProgram
        fields = ['name', 'description', 'start_date', 'end_date', 'athlete_id', 'program_data']
        extra_kwargs = {
            'name': {'required': False},
            'description': {'required': False},
            'start_date': {'required': False},
            'end_date': {'required': False, 'allow_null': True},
        }

    def validate_athlete_id(self, value):
        try:
            athlete = User.objects.get(id=value, user_type='athlete')
        except User.DoesNotExist:
            raise serializers.ValidationError('Selected athlete does not exist.')
        coach = self.context['request'].user
        if not coach_may_bind_athlete(coach, athlete):
            raise serializers.ValidationError('You can only select athletes you manage.')
        return athlete.id

    def validate_program_data(self, value):
        return normalize_program_data(value)

    def validate_name(self, value):
        return _plain_text_no_markup(value, 'Program name')

    def validate_description(self, value):
        return _plain_text_no_markup(value, 'Description')

    def update(self, instance, validated_data):
        athlete_id = validated_data.pop('athlete_id', None)
        if athlete_id is not None:
            instance.athlete = User.objects.get(id=athlete_id, user_type='athlete')

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.normalized_name = canonical_program_name(instance.name)
        instance.style_tags = derive_program_style_tags(instance.program_data or default_program_data())

        instance.save()
        if athlete_id is not None:
            User.objects.filter(pk=instance.athlete_id, user_type='athlete').update(
                primary_coach_id=instance.coach_id,
            )
        return instance
