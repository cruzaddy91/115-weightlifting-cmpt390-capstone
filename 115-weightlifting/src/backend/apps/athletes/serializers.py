from datetime import date as date_cls
from decimal import Decimal

from rest_framework import serializers
from .models import PersonalRecord, ProgramCompletion, WorkoutLog, default_completion_data

MIN_LOG_DATE = date_cls(2000, 1, 1)
MAX_LIFT_WEIGHT_KG = Decimal('500')


def _validate_event_date(value):
    if value is None:
        return value
    today = date_cls.today()
    if value > today:
        raise serializers.ValidationError('Date cannot be in the future.')
    if value < MIN_LOG_DATE:
        raise serializers.ValidationError('Date is before the supported logging window.')
    return value


class WorkoutLogSerializer(serializers.ModelSerializer):
    athlete_id = serializers.IntegerField(source='athlete.id', read_only=True)

    class Meta:
        model = WorkoutLog
        fields = ['id', 'athlete_id', 'date', 'notes', 'created_at', 'updated_at']

    def validate_date(self, value):
        return _validate_event_date(value)

    def create(self, validated_data):
        return WorkoutLog.objects.create(athlete=self.context['athlete'], **validated_data)


class PersonalRecordSerializer(serializers.ModelSerializer):
    athlete_id = serializers.IntegerField(source='athlete.id', read_only=True)

    class Meta:
        model = PersonalRecord
        fields = ['id', 'athlete_id', 'lift_type', 'weight', 'date', 'created_at']

    def validate_weight(self, value):
        if value <= 0:
            raise serializers.ValidationError('Weight must be greater than 0.')
        if value > MAX_LIFT_WEIGHT_KG:
            raise serializers.ValidationError(
                f'Weight cannot exceed {MAX_LIFT_WEIGHT_KG} kg.'
            )
        return value

    def validate_date(self, value):
        return _validate_event_date(value)

    def create(self, validated_data):
        return PersonalRecord.objects.create(athlete=self.context['athlete'], **validated_data)


def normalize_completion_data(value):
    if value in (None, ''):
        value = default_completion_data()

    if not isinstance(value, dict):
        raise serializers.ValidationError('completion_data must be an object.')

    entries = value.get('entries', {})
    if not isinstance(entries, dict):
        raise serializers.ValidationError('completion_data.entries must be an object.')

    normalized_entries = {}
    for day_index, exercises in entries.items():
        if not isinstance(exercises, dict):
            raise serializers.ValidationError('Each day entry must be an object keyed by exercise index.')

        normalized_day = {}
        for exercise_index, result in exercises.items():
            if not isinstance(result, dict):
                raise serializers.ValidationError('Each exercise entry must be an object.')

            normalized_day[str(exercise_index)] = {
                'completed': bool(result.get('completed', False)),
                'athlete_notes': str(result.get('athlete_notes', '')),
                'result': str(result.get('result', '')),
            }

        normalized_entries[str(day_index)] = normalized_day

    return {'entries': normalized_entries}


class ProgramCompletionSerializer(serializers.ModelSerializer):
    athlete_id = serializers.IntegerField(source='athlete.id', read_only=True)
    program_id = serializers.IntegerField(source='program.id', read_only=True)

    class Meta:
        model = ProgramCompletion
        fields = ['id', 'program_id', 'athlete_id', 'completion_data', 'created_at', 'updated_at']


class ProgramCompletionUpdateSerializer(serializers.ModelSerializer):
    completion_data = serializers.JSONField()

    class Meta:
        model = ProgramCompletion
        fields = ['completion_data']

    def validate_completion_data(self, value):
        return normalize_completion_data(value)
