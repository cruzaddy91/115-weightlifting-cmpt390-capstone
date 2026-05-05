from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models


class WeightliftingUserManager(UserManager):
    def _create_user(self, username, email, password, **extra_fields):
        if not email:
            email = f'{username}@example.invalid'
        return super()._create_user(username, email, password, **extra_fields)


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

    SKILL_TEAM_CHOICES = [
        ('NOBLE', 'NOBLE'),
        ('RED', 'RED'),
        ('SILVER', 'SILVER'),
        ('BLUE', 'BLUE'),
    ]

    SKILL_SETTER_ROLE_CHOICES = [
        ('GMHC', 'GMHC'),
        ('AGMHC', 'AGMHC'),
        ('LC', 'LC'),
    ]

    email = models.EmailField(unique=True)
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
    date_of_birth = models.DateField(null=True, blank=True)
    # Explicit org lane for UAT provisioning. This lets one AGMHC own multiple
    # lanes while line coaches and athletes still carry a single active lane.
    org_lane_prefix = models.CharField(max_length=3, blank=True, default='')
    skill_team = models.CharField(max_length=6, choices=SKILL_TEAM_CHOICES, blank=True, default='')
    skill_team_updated_by = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='skill_team_updates',
    )
    skill_team_updated_by_role = models.CharField(
        max_length=5,
        choices=SKILL_SETTER_ROLE_CHOICES,
        blank=True,
        default='',
    )
    skill_team_updated_at = models.DateTimeField(null=True, blank=True)
    # MVP recoverable delete: hide/block the account while retaining data for 30 days.
    deleted_at = models.DateTimeField(null=True, blank=True)
    recoverable_until = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='deleted_athlete_accounts',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = WeightliftingUserManager()

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
        if self.skill_team and self.user_type != 'athlete':
            raise ValidationError({'skill_team': 'Only athletes may have a skill team.'})


class OrgLaneAssignment(models.Model):
    prefix = models.CharField(max_length=3, unique=True)
    head_coach = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='owned_org_lanes',
    )
    updated_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='updated_org_lanes',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['prefix']

    def clean(self):
        super().clean()
        if self.prefix not in {'001', '002', '003', '004'}:
            raise ValidationError({'prefix': 'Lane prefix must be 001, 002, 003, or 004.'})
        if self.head_coach_id and self.head_coach.user_type != 'head_coach':
            raise ValidationError({'head_coach': 'Lane owner must be a head coach.'})

