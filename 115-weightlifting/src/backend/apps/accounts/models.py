from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class User(AbstractUser):
    USER_TYPE_CHOICES = [
        ('head_coach', 'Head Coach'),
        ('coach', 'Coach'),
        ('athlete', 'Athlete'),
    ]

    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]

    user_type = models.CharField(max_length=12, choices=USER_TYPE_CHOICES)
    # Line coaches report to exactly one head coach; head coaches leave this null.
    reports_to = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='staff_coaches',
    )
    # Athletes have at most one accountable coach (synced from program assignment).
    primary_coach = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='primary_roster_athletes',
    )
    # Athlete competition profile (optional; coaches typically omit).
    bodyweight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.reports_to_id:
            if self.user_type != 'coach':
                raise ValidationError({'reports_to': 'Only line coaches may report to a head coach.'})
            if self.reports_to.user_type != 'head_coach':
                raise ValidationError({'reports_to': 'reports_to must be a head coach account.'})
            if self.reports_to_id == self.pk:
                raise ValidationError({'reports_to': 'A user cannot report to themselves.'})
        if self.primary_coach_id:
            if self.user_type != 'athlete':
                raise ValidationError({'primary_coach': 'Only athletes may have a primary coach.'})
            if self.primary_coach.user_type not in ('coach', 'head_coach'):
                raise ValidationError({'primary_coach': 'primary_coach must be a coach or head coach.'})

