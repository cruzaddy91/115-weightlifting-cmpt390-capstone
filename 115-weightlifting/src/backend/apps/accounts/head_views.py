"""Head-coach-only org overview and assignment APIs."""

from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from apps.accounts.roles import is_head_coach, staff_coach_queryset
from apps.accounts.org_labels import (
    AGM_PREFIXES,
    DEMO_HEAD_COACH_USERNAMES,
    GM_PREFIX,
    is_master_head_user,
    org_meta_for_user,
    username_prefix,
)
from apps.athletes.models import PersonalRecord, WorkoutLog
from apps.programs.models import TrainingProgram

User = get_user_model()


def _org_coach_ids(head):
    return [head.id, *list(staff_coach_queryset(head).values_list('pk', flat=True))]


def _is_master_head(user):
    return is_master_head_user(user)


def _soft_delete_user(user, deleted_by, now):
    user.is_active = False
    user.deleted_at = now
    user.deleted_by = deleted_by
    user.recoverable_until = now + timedelta(days=30)


def _username_with_prefix(username, prefix):
    suffix = (username or '').split('_', 1)[1] if '_' in (username or '') else username
    return f'{prefix}_{suffix}'


def _next_unassigned_head_username(username):
    suffix = (username or '').split('_', 1)[1] if '_' in (username or '') else username
    for demo_username in DEMO_HEAD_COACH_USERNAMES:
        if demo_username.endswith(f'_{suffix}') and not User.objects.filter(username__iexact=demo_username).exists():
            return demo_username
    for prefix in range(118, 1000):
        candidate = f'{prefix:03d}_{suffix}'
        if not User.objects.filter(username__iexact=candidate).exists():
            return candidate
    return None


class HeadOrgSummaryView(APIView):
    """Per-coach rollups for this head coach's org (staff + self)."""

    def get(self, request):
        if not is_head_coach(request.user):
            return Response(
                {'detail': 'Only head coaches can view org summary.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        head = request.user
        coaches = [head, *list(staff_coach_queryset(head).order_by('username'))]
        out = []
        for coach in coaches:
            # Roster = athletes whose accountable coach is this user (line or head), not program joins alone.
            athlete_ids = list(
                User.objects.filter(user_type='athlete', is_active=True, primary_coach=coach).values_list('pk', flat=True)
            )
            athlete_set = set(athlete_ids)
            pr_qs = PersonalRecord.objects.filter(athlete_id__in=athlete_ids) if athlete_ids else PersonalRecord.objects.none()
            wl_qs = WorkoutLog.objects.filter(athlete_id__in=athlete_ids) if athlete_ids else WorkoutLog.objects.none()
            out.append(
                {
                    'id': coach.id,
                    'username': coach.username,
                    'user_type': coach.user_type,
                    'athlete_count': len(athlete_set),
                    'program_count': TrainingProgram.objects.filter(coach=coach, athlete__is_active=True).count(),
                    'personal_record_count': pr_qs.count(),
                    'workout_log_count': wl_qs.count(),
                }
            )
        return Response({'coaches': out}, status=status.HTTP_200_OK)


class HeadOrgRosterView(APIView):
    """Staff/available line coaches + org/available athletes.

    In the single-organization Docker review build, the head coach is the
    business owner. They need to see unassigned accounts so newly registered
    coaches/athletes can be brought into the org from the dashboard.
    """

    def get(self, request):
        if not is_head_coach(request.user):
            return Response(
                {'detail': 'Only head coaches can view org roster.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        head = request.user
        staff_users = list(
            User.objects.filter(user_type='coach', is_active=True, is_staff=False, is_superuser=False)
            .select_related('reports_to')
            .order_by('username')
        )
        staff = [
            {
                'id': coach.id,
                'username': coach.username,
                'reports_to_id': coach.reports_to_id,
                'reports_to_username': coach.reports_to.username if coach.reports_to else None,
                **org_meta_for_user(coach),
            }
            for coach in staff_users
        ]
        head_users = list(
            User.objects.filter(user_type='head_coach', is_active=True, is_staff=False, is_superuser=False)
            .order_by('username')
        )
        head_coaches = [
            {
                'id': head_coach.id,
                'username': head_coach.username,
                **org_meta_for_user(head_coach),
            }
            for head_coach in head_users
        ]
        athlete_users = list(
            User.objects.filter(user_type='athlete', is_active=True, is_staff=False, is_superuser=False)
            .select_related('primary_coach', 'primary_coach__reports_to')
            .order_by('username')
        )
        athletes = [
            {
                'id': athlete.id,
                'username': athlete.username,
                'primary_coach_id': athlete.primary_coach_id,
                'primary_coach_username': athlete.primary_coach.username if athlete.primary_coach else None,
                **org_meta_for_user(athlete),
            }
            for athlete in athlete_users
        ]
        return Response(
            {'staff': staff, 'head_coaches': head_coaches, 'athletes': athletes},
            status=status.HTTP_200_OK,
        )


class HeadStaffInviteView(APIView):
    """Add a line coach to this head's org by username (sets reports_to)."""

    def post(self, request):
        if not is_head_coach(request.user):
            return Response(
                {'detail': 'Only head coaches can manage staff.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        username = (request.data.get('username') or '').strip()
        if not username:
            return Response({'username': ['Required.']}, status=status.HTTP_400_BAD_REQUEST)
        coach = get_object_or_404(User, username__iexact=username, user_type='coach', is_active=True)
        head = request.user
        if coach.reports_to_id and coach.reports_to_id != head.id:
            return Response(
                {'detail': 'That coach already reports to another head coach.'},
                status=status.HTTP_409_CONFLICT,
            )
        coach.reports_to = head
        coach.full_clean()
        coach.save(update_fields=['reports_to'])
        return Response(
            {'id': coach.id, 'username': coach.username, 'reports_to_id': head.id},
            status=status.HTTP_200_OK,
        )


class HeadStaffLinkView(APIView):
    """Link or unlink a line coach by id (reports_to this head)."""

    def patch(self, request, user_id):
        if not is_head_coach(request.user):
            return Response(
                {'detail': 'Only head coaches can manage staff.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        head = request.user
        coach = get_object_or_404(User, pk=user_id, user_type='coach', is_active=True)
        if 'reports_to_id' in request.data:
            reports_to_id = request.data.get('reports_to_id')
            unassign_requested = reports_to_id is None or reports_to_id == ''
            target_head = None
            if not unassign_requested:
                try:
                    reports_to_id = int(reports_to_id)
                except (TypeError, ValueError):
                    return Response(
                        {'reports_to_id': ['Must be an integer user id or null.']},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                target_head = get_object_or_404(User, pk=reports_to_id, user_type='head_coach', is_active=True)
            with transaction.atomic():
                if unassign_requested:
                    User.objects.filter(user_type='athlete', primary_coach_id=coach.id).update(
                        primary_coach=None
                    )
                    TrainingProgram.objects.filter(coach=coach).update(
                        coach=head,
                        updated_at=timezone.now(),
                    )
                    coach.reports_to = None
                else:
                    coach.reports_to = target_head
                coach.full_clean()
                coach.save(update_fields=['reports_to'])
            return Response(
                {'id': coach.id, 'username': coach.username, 'reports_to_id': coach.reports_to_id},
                status=status.HTTP_200_OK,
            )

        linked = request.data.get('linked')
        if not isinstance(linked, bool):
            return Response(
                {'linked': ['Must be a boolean, or provide reports_to_id.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if linked:
            if coach.reports_to_id and coach.reports_to_id != head.id:
                return Response(
                    {'detail': 'That coach already reports to another head coach.'},
                    status=status.HTTP_409_CONFLICT,
                )
            coach.reports_to = head
            coach.full_clean()
            coach.save(update_fields=['reports_to'])
        else:
            if coach.reports_to_id != head.id:
                return Response(
                    {'detail': 'You can only remove coaches who report to you.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # Line coach leaving: head temporarily owns their roster + programs until reassigned.
            with transaction.atomic():
                User.objects.filter(user_type='athlete', primary_coach_id=coach.id).update(
                    primary_coach=head
                )
                TrainingProgram.objects.filter(coach=coach).update(
                    coach=head,
                    updated_at=timezone.now(),
                )
                coach.reports_to = None
                coach.save(update_fields=['reports_to'])
        return Response(
            {'id': coach.id, 'username': coach.username, 'reports_to_id': coach.reports_to_id},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, user_id):
        if not is_head_coach(request.user):
            return Response(
                {'detail': 'Only head coaches can delete coaches.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        head = request.user
        coach = get_object_or_404(User, pk=user_id, user_type='coach', is_active=True)
        now = timezone.now()
        with transaction.atomic():
            User.objects.filter(user_type='athlete', primary_coach_id=coach.id).update(
                primary_coach=None
            )
            TrainingProgram.objects.filter(coach=coach).update(
                coach=head,
                updated_at=now,
            )
            coach.reports_to = None
            _soft_delete_user(coach, head, now)
            coach.full_clean()
            coach.save(
                update_fields=[
                    'is_active',
                    'reports_to',
                    'deleted_at',
                    'deleted_by',
                    'recoverable_until',
                ],
            )
        return Response(
            {
                'id': coach.id,
                'username': coach.username,
                'is_active': coach.is_active,
                'deleted_at': coach.deleted_at,
                'recoverable_until': coach.recoverable_until,
            },
            status=status.HTTP_200_OK,
        )


class HeadCoachAssignmentView(APIView):
    """GM-only management for standalone/AGM head coach accounts."""

    def patch(self, request, user_id):
        if not is_head_coach(request.user):
            return Response(
                {'detail': 'Only head coaches can manage head-coach categories.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _is_master_head(request.user):
            return Response(
                {'detail': 'Only the GM head coach can manage head-coach categories.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        head_coach = get_object_or_404(User, pk=user_id, user_type='head_coach', is_active=True)
        if head_coach.id == request.user.id or username_prefix(head_coach.username) == GM_PREFIX:
            return Response(
                {'detail': 'The GM head coach cannot be reassigned.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        category_prefix = str(request.data.get('category_prefix') or '').strip()
        unassign_requested = category_prefix in ('', 'XXX', 'XXX_UNASSIGNED')
        if unassign_requested:
            if username_prefix(head_coach.username) not in AGM_PREFIXES:
                return Response(
                    {
                        'id': head_coach.id,
                        'username': head_coach.username,
                        **org_meta_for_user(head_coach),
                    },
                    status=status.HTTP_200_OK,
                )
            next_username = _next_unassigned_head_username(head_coach.username)
            if next_username is None:
                return Response(
                    {'username': ['No unassigned head-coach prefixes are available.']},
                    status=status.HTTP_409_CONFLICT,
                )
            head_coach.username = next_username
            head_coach.full_clean()
            head_coach.save(update_fields=['username'])
            return Response(
                {
                    'id': head_coach.id,
                    'username': head_coach.username,
                    **org_meta_for_user(head_coach),
                },
                status=status.HTTP_200_OK,
            )
        if category_prefix not in AGM_PREFIXES:
            return Response(
                {'category_prefix': ['Choose XXX_UNASSIGNED or one of the AGM prefixes: 001, 002, 003, or 004.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        existing = User.objects.filter(
            username__istartswith=f'{category_prefix}_',
            user_type='head_coach',
            is_active=True,
        ).exclude(pk=head_coach.pk).first()
        if existing:
            return Response(
                {'category_prefix': [f'{category_prefix} is already assigned to @{existing.username}.']},
                status=status.HTTP_409_CONFLICT,
            )
        next_username = _username_with_prefix(head_coach.username, category_prefix)
        if User.objects.filter(username__iexact=next_username).exclude(pk=head_coach.pk).exists():
            return Response(
                {'username': [f'Cannot assign because @{next_username} already exists.']},
                status=status.HTTP_409_CONFLICT,
            )
        head_coach.username = next_username
        head_coach.full_clean()
        head_coach.save(update_fields=['username'])
        return Response(
            {
                'id': head_coach.id,
                'username': head_coach.username,
                **org_meta_for_user(head_coach),
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, user_id):
        if not is_head_coach(request.user):
            return Response(
                {'detail': 'Only head coaches can delete head-coach accounts.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _is_master_head(request.user):
            return Response(
                {'detail': 'Only the GM head coach can delete head-coach accounts.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        head_coach = get_object_or_404(User, pk=user_id, user_type='head_coach', is_active=True)
        if head_coach.id == request.user.id or username_prefix(head_coach.username) == GM_PREFIX:
            return Response(
                {'detail': 'The GM head coach cannot be deleted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        now = timezone.now()
        _soft_delete_user(head_coach, request.user, now)
        head_coach.full_clean()
        head_coach.save(update_fields=['is_active', 'deleted_at', 'deleted_by', 'recoverable_until'])
        return Response(
            {
                'id': head_coach.id,
                'username': head_coach.username,
                'is_active': head_coach.is_active,
                'deleted_at': head_coach.deleted_at,
                'recoverable_until': head_coach.recoverable_until,
            },
            status=status.HTTP_200_OK,
        )


class HeadAthletePrimaryCoachView(APIView):
    """Set an org athlete's primary_coach to this head or a line coach under this head."""

    def patch(self, request, user_id):
        if not is_head_coach(request.user):
            return Response(
                {'detail': 'Only head coaches can assign athletes.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        head = request.user
        athlete = get_object_or_404(User, pk=user_id, user_type='athlete', is_active=True)
        coach_id = request.data.get('primary_coach_id')
        unassign_requested = coach_id is None or coach_id == ''
        if not unassign_requested:
            try:
                coach_id = int(coach_id)
            except (TypeError, ValueError):
                return Response(
                    {'primary_coach_id': ['Must be an integer user id or null.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if unassign_requested:
            with transaction.atomic():
                athlete.primary_coach = None
                athlete.full_clean()
                athlete.save(update_fields=['primary_coach'])
                # Head coach becomes the temporary custodian of existing work so
                # the prior line coach loses active program access without data loss.
                TrainingProgram.objects.filter(athlete=athlete).update(
                    coach=head,
                    updated_at=timezone.now(),
                )
            return Response(
                {
                    'id': athlete.id,
                    'username': athlete.username,
                    'primary_coach_id': athlete.primary_coach_id,
                },
                status=status.HTTP_200_OK,
            )

        coach = get_object_or_404(User, pk=coach_id, is_active=True)
        if coach.user_type not in ('coach', 'head_coach'):
            return Response(
                {'primary_coach_id': ['Target must be a coach or head coach.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        master_head = _is_master_head(head)
        if coach.user_type == 'head_coach' and coach.id != head.id and not master_head:
            return Response(
                {'primary_coach_id': ['Athletes may only report to your account as head coach.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if coach.user_type == 'coach':
            if coach.reports_to_id != head.id and not master_head:
                return Response(
                    {'primary_coach_id': ['Line coach must report to you before they can own an athlete.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        allowed = set(_org_coach_ids(head))
        if coach.id not in allowed and not master_head:
            return Response(
                {'primary_coach_id': ['Coach is not in your organization.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        prev = athlete.primary_coach_id
        if prev is not None and prev not in allowed and not master_head:
            return Response(
                {'detail': 'Athlete is assigned outside your organization.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        with transaction.atomic():
            athlete.primary_coach = coach
            athlete.full_clean()
            athlete.save(update_fields=['primary_coach'])
            # Keep program ownership + log/PR auth in sync: all this athlete's programs
            # belong to the accountable coach so the previous coach loses edit/list access.
            TrainingProgram.objects.filter(athlete=athlete).update(
                coach=coach,
                updated_at=timezone.now(),
            )
        return Response(
            {
                'id': athlete.id,
                'username': athlete.username,
                'primary_coach_id': athlete.primary_coach_id,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, user_id):
        if not is_head_coach(request.user):
            return Response(
                {'detail': 'Only head coaches can delete athletes.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        head = request.user
        athlete = get_object_or_404(User, pk=user_id, user_type='athlete', is_active=True)
        now = timezone.now()
        with transaction.atomic():
            _soft_delete_user(athlete, head, now)
            athlete.primary_coach = None
            athlete.full_clean()
            athlete.save(
                update_fields=[
                    'is_active',
                    'primary_coach',
                    'deleted_at',
                    'deleted_by',
                    'recoverable_until',
                ],
            )
            TrainingProgram.objects.filter(athlete=athlete).update(
                coach=head,
                updated_at=now,
            )
        return Response(
            {
                'id': athlete.id,
                'username': athlete.username,
                'is_active': athlete.is_active,
                'deleted_at': athlete.deleted_at,
                'recoverable_until': athlete.recoverable_until,
            },
            status=status.HTTP_200_OK,
        )
