from django.db import models
from django.conf import settings
from apps.programs.models import TrainingProgram


class WorkoutLog(models.Model):
    athlete = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workout_logs',
        db_index=True,
    )
    date = models.DateField(db_index=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['athlete', '-date'], name='workoutlog_athlete_date_idx'),
        ]


class PersonalRecord(models.Model):
    LIFT_CHOICES = [
        ('snatch', 'Snatch'),
        ('clean_jerk', 'Clean & Jerk'),
        ('total', 'Total'),
    ]

    athlete = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='personal_records',
        db_index=True,
    )
    lift_type = models.CharField(max_length=20, choices=LIFT_CHOICES)
    weight = models.DecimalField(max_digits=6, decimal_places=2)
    date = models.DateField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['athlete', 'lift_type', '-date'], name='pr_athlete_lift_date_idx'),
        ]


def default_completion_data():
    return {
        'entries': {},
    }


class ProgramCompletion(models.Model):
    program = models.ForeignKey(
        TrainingProgram,
        on_delete=models.CASCADE,
        related_name='completion_records',
        db_index=True,
    )
    athlete = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='program_completions',
        db_index=True,
    )
    completion_data = models.JSONField(default=default_completion_data, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['program', 'athlete'], name='unique_program_completion_per_athlete')
        ]
        indexes = [
            models.Index(fields=['athlete', '-updated_at'], name='completion_athlete_recent_idx'),
        ]
