"""Role helpers for coach / head coach / athlete authorization."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


def is_head_coach(user: AbstractUser) -> bool:
    return getattr(user, 'user_type', None) == 'head_coach'


def is_line_coach(user: AbstractUser) -> bool:
    """Coach or head coach — may own training programs."""
    return getattr(user, 'user_type', None) in ('coach', 'head_coach')


def is_athlete(user: AbstractUser) -> bool:
    return getattr(user, 'user_type', None) == 'athlete'


def staff_coach_queryset(head):
    """Line coaches reporting to this head coach (not including the head)."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.filter(reports_to=head, user_type='coach')


def coach_may_bind_athlete(coach_user, athlete) -> bool:
    """Whether coach/head may attach a program to this athlete (roster / org rule).

    Line coach: athlete is unassigned or already lists this coach as primary.
    Head coach: primary is unset or points to the head or any line coach under them.
    """
    if getattr(athlete, 'user_type', None) != 'athlete':
        return False
    pid = getattr(athlete, 'primary_coach_id', None)
    if getattr(coach_user, 'user_type', None) == 'coach':
        return pid in (None, coach_user.id)
    if is_head_coach(coach_user):
        org_ids = {coach_user.id, *staff_coach_queryset(coach_user).values_list('pk', flat=True)}
        return pid is None or pid in org_ids
    return False
