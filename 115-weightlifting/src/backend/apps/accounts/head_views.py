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

from apps.accounts.models import OrgLaneAssignment
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


def _owned_lane_prefixes(head):
    prefixes = set(
        OrgLaneAssignment.objects.filter(head_coach=head).values_list('prefix', flat=True)
    )
    prefix = username_prefix(getattr(head, 'username', ''))
    if prefix in AGM_PREFIXES:
        prefixes.add(prefix)
    return prefixes


def _actor_role(user):
    if _is_master_head(user):
        return 'GMHC'
    if getattr(user, 'user_type', None) == 'head_coach':
        return 'AGMHC'
    if getattr(user, 'user_type', None) == 'coach':
        return 'LC'
    return ''


def _summary_row(coach, athlete_ids):
    athlete_set = set(athlete_ids)
    pr_qs = PersonalRecord.objects.filter(athlete_id__in=athlete_ids) if athlete_ids else PersonalRecord.objects.none()
    wl_qs = WorkoutLog.objects.filter(athlete_id__in=athlete_ids) if athlete_ids else WorkoutLog.objects.none()
    return {
        'id': coach.id,
        'username': coach.username,
        'user_type': coach.user_type,
        'athlete_count': len(athlete_set),
        'program_count': TrainingProgram.objects.filter(coach=coach, athlete__is_active=True).count(),
        'personal_record_count': pr_qs.count(),
        'workout_log_count': wl_qs.count(),
    }


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
        if _is_master_head(head):
            coaches = list(
                User.objects.filter(user_type__in=('head_coach', 'coach'), is_active=True, is_staff=False, is_superuser=False)
                .order_by('user_type', 'username')
            )
        else:
            lane_prefixes = _owned_lane_prefixes(head)
            staff_qs = staff_coach_queryset(head)
            if lane_prefixes:
                staff_qs = User.objects.filter(
                    Q(reports_to=head) | Q(org_lane_prefix__in=lane_prefixes),
                    user_type='coach',
                    is_active=True,
                    is_staff=False,
                    is_superuser=False,
                ).distinct()
            coaches = [head, *list(staff_qs.order_by('username'))]
        out = []
        for coach in coaches:
            # Roster = athletes whose accountable coach is this user (line or head), not program joins alone.
            athlete_ids = list(
                User.objects.filter(user_type='athlete', is_active=True, primary_coach=coach).values_list('pk', flat=True)
            )
            out.append(_summary_row(coach, athlete_ids))
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
        master_head = _is_master_head(head)
        staff_qs = User.objects.filter(user_type='coach', is_active=True, is_staff=False, is_superuser=False)
        head_qs = User.objects.filter(user_type='head_coach', is_active=True, is_staff=False, is_superuser=False)
        athlete_qs = User.objects.filter(user_type='athlete', is_active=True, is_staff=False, is_superuser=False)
        if not master_head:
            lane_prefixes = _owned_lane_prefixes(head)
            staff_qs = staff_qs.filter(Q(reports_to=head) | Q(org_lane_prefix__in=lane_prefixes)).distinct()
            head_qs = head_qs.filter(pk=head.pk)
            athlete_filter = Q(primary_coach=head) | Q(primary_coach__reports_to=head)
            if lane_prefixes:
                athlete_filter |= Q(org_lane_prefix__in=lane_prefixes) | Q(primary_coach__org_lane_prefix__in=lane_prefixes)
            athlete_qs = athlete_qs.filter(athlete_filter).distinct()
        staff_users = list(
            staff_qs
            .select_related('reports_to')
            .order_by('username')
        )
        staff = [
            {
                'id': coach.id,
                'username': coach.username,
                'reports_to_id': coach.reports_to_id,
                'reports_to_username': coach.reports_to.username if coach.reports_to else None,
                'org_lane_prefix': coach.org_lane_prefix,
                **org_meta_for_user(coach),
            }
            for coach in staff_users
        ]
        head_users = list(head_qs.order_by('username'))
        head_coaches = [
            {
                'id': head_coach.id,
                'username': head_coach.username,
                'owned_lane_prefixes': list(
                    OrgLaneAssignment.objects.filter(head_coach=head_coach).values_list('prefix', flat=True)
                ),
                **org_meta_for_user(head_coach),
            }
            for head_coach in head_users
        ]
        athlete_users = list(
            athlete_qs
            .select_related('primary_coach', 'primary_coach__reports_to')
            .order_by('username')
        )
        athletes = [
            {
                'id': athlete.id,
                'username': athlete.username,
                'primary_coach_id': athlete.primary_coach_id,
                'primary_coach_username': athlete.primary_coach.username if athlete.primary_coach else None,
                'org_lane_prefix': athlete.org_lane_prefix,
                'date_of_birth': athlete.date_of_birth,
                'skill_team': athlete.skill_team,
                'skill_team_updated_by_id': athlete.skill_team_updated_by_id,
                'skill_team_updated_by_username': athlete.skill_team_updated_by.username if athlete.skill_team_updated_by else None,
                'skill_team_updated_by_role': athlete.skill_team_updated_by_role,
                'skill_team_updated_at': athlete.skill_team_updated_at,
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
        coach.org_lane_prefix = head.org_lane_prefix or username_prefix(head.username) or ''
        coach.full_clean()
        coach.save(update_fields=['reports_to', 'org_lane_prefix'])
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
                        primary_coach=None,
                        org_lane_prefix='',
                    )
                    TrainingProgram.objects.filter(coach=coach).update(
                        coach=head,
                        updated_at=timezone.now(),
                    )
                    coach.reports_to = None
                    coach.org_lane_prefix = ''
                else:
                    coach.reports_to = target_head
                    target_prefix = target_head.org_lane_prefix or username_prefix(target_head.username) or ''
                    coach.org_lane_prefix = target_prefix if target_prefix in AGM_PREFIXES else ''
                coach.full_clean()
                coach.save(update_fields=['reports_to', 'org_lane_prefix'])
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
            coach.org_lane_prefix = head.org_lane_prefix or username_prefix(head.username) or ''
            coach.full_clean()
            coach.save(update_fields=['reports_to', 'org_lane_prefix'])
        else:
            if coach.reports_to_id != head.id:
                return Response(
                    {'detail': 'You can only remove coaches who report to you.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # Line coach leaving: head temporarily owns their roster + programs until reassigned.
            with transaction.atomic():
                User.objects.filter(user_type='athlete', primary_coach_id=coach.id).update(
                    primary_coach=head,
                    org_lane_prefix=head.org_lane_prefix or username_prefix(head.username) or '',
                )
                TrainingProgram.objects.filter(coach=coach).update(
                    coach=head,
                    updated_at=timezone.now(),
                )
                coach.reports_to = None
                coach.org_lane_prefix = ''
                coach.save(update_fields=['reports_to', 'org_lane_prefix'])
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
                primary_coach=None,
                org_lane_prefix='',
            )
            TrainingProgram.objects.filter(coach=coach).update(
                coach=head,
                updated_at=now,
            )
            coach.reports_to = None
            coach.org_lane_prefix = ''
            _soft_delete_user(coach, head, now)
            coach.full_clean()
            coach.save(
                update_fields=[
                    'is_active',
                    'reports_to',
                    'org_lane_prefix',
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
            head_coach.org_lane_prefix = ''
            head_coach.full_clean()
            head_coach.save(update_fields=['username', 'org_lane_prefix'])
            OrgLaneAssignment.objects.filter(head_coach=head_coach).update(head_coach=None, updated_by=request.user)
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
        head_coach.org_lane_prefix = category_prefix
        head_coach.full_clean()
        head_coach.save(update_fields=['username', 'org_lane_prefix'])
        OrgLaneAssignment.objects.update_or_create(
            prefix=category_prefix,
            defaults={'head_coach': head_coach, 'updated_by': request.user},
        )
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
        master_head = _is_master_head(head)
        allowed = set(_org_coach_ids(head))
        prev = athlete.primary_coach_id
        if prev is not None and prev not in allowed and not master_head:
            return Response(
                {'detail': 'Athlete is assigned outside your organization.'},
                status=status.HTTP_403_FORBIDDEN,
            )
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
        if coach.id not in allowed and not master_head:
            return Response(
                {'primary_coach_id': ['Coach is not in your organization.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            athlete.primary_coach = coach
            if coach.user_type == 'coach' and coach.org_lane_prefix:
                athlete.org_lane_prefix = coach.org_lane_prefix
            elif coach.user_type == 'head_coach':
                coach_prefix = username_prefix(coach.username)
                athlete.org_lane_prefix = coach_prefix if coach_prefix in AGM_PREFIXES or coach_prefix == GM_PREFIX else ''
            athlete.full_clean()
            athlete.save(update_fields=['primary_coach', 'org_lane_prefix'])
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


class HeadAthleteSkillTeamView(APIView):
    """Assign athlete skill teams with GMHC/AGMHC/LC downflow controls."""

    def patch(self, request, user_id):
        actor = request.user
        actor_role = _actor_role(actor)
        if actor_role not in {'GMHC', 'AGMHC', 'LC'}:
            return Response(
                {'detail': 'Only coaches can assign athlete skill teams.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        athlete = get_object_or_404(User, pk=user_id, user_type='athlete', is_active=True)
        skill_team = str(request.data.get('skill_team') or '').strip().upper()
        allowed_teams = {choice for choice, _label in User.SKILL_TEAM_CHOICES}
        if skill_team not in allowed_teams:
            return Response(
                {'skill_team': ['Choose NOBLE, RED, SILVER, or BLUE.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        previous_role = athlete.skill_team_updated_by_role or ''
        permitted = False
        if actor_role == 'GMHC':
            permitted = True
        elif actor_role == 'AGMHC':
            lane_prefixes = _owned_lane_prefixes(actor)
            athlete_lane = athlete.org_lane_prefix or org_meta_for_user(athlete).get('org_prefix')
            permitted = athlete_lane in lane_prefixes and previous_role in {'', 'AGMHC', 'LC'}
        elif actor_role == 'LC':
            permitted = athlete.primary_coach_id == actor.id and previous_role in {'', 'LC'}

        if not permitted:
            return Response(
                {
                    'detail': (
                        'Skill-team change requires a request because the last assignment '
                        'came from a higher access level or outside your lane.'
                    ),
                    'request_required': True,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        athlete.skill_team = skill_team
        athlete.skill_team_updated_by = actor
        athlete.skill_team_updated_by_role = actor_role
        athlete.skill_team_updated_at = timezone.now()
        athlete.full_clean()
        athlete.save(
            update_fields=[
                'skill_team',
                'skill_team_updated_by',
                'skill_team_updated_by_role',
                'skill_team_updated_at',
            ],
        )
        return Response(
            {
                'id': athlete.id,
                'username': athlete.username,
                'skill_team': athlete.skill_team,
                'skill_team_updated_by_id': athlete.skill_team_updated_by_id,
                'skill_team_updated_by_username': actor.username,
                'skill_team_updated_by_role': athlete.skill_team_updated_by_role,
                'skill_team_updated_at': athlete.skill_team_updated_at,
            },
            status=status.HTTP_200_OK,
        )
