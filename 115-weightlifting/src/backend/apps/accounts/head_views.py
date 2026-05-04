"""Head-coach-only org overview and assignment APIs."""

from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from apps.accounts.roles import is_head_coach, staff_coach_queryset
from apps.athletes.models import PersonalRecord, WorkoutLog
from apps.programs.models import TrainingProgram

User = get_user_model()


def _org_coach_ids(head):
    return [head.id, *list(staff_coach_queryset(head).values_list('pk', flat=True))]


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
                User.objects.filter(user_type='athlete', primary_coach=coach).values_list('pk', flat=True)
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
                    'program_count': TrainingProgram.objects.filter(coach=coach).count(),
                    'personal_record_count': pr_qs.count(),
                    'workout_log_count': wl_qs.count(),
                }
            )
        return Response({'coaches': out}, status=status.HTTP_200_OK)


class HeadOrgRosterView(APIView):
    """Staff line coaches under this head + org athletes (primary_coach in org)."""

    def get(self, request):
        if not is_head_coach(request.user):
            return Response(
                {'detail': 'Only head coaches can view org roster.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        head = request.user
        staff = list(
            staff_coach_queryset(head)
            .order_by('username')
            .values('id', 'username', 'reports_to_id')
        )
        coach_ids = _org_coach_ids(head)
        athletes = list(
            User.objects.filter(user_type='athlete', primary_coach_id__in=coach_ids)
            .order_by('username')
            .values('id', 'username', 'primary_coach_id')
        )
        return Response({'staff': staff, 'athletes': athletes}, status=status.HTTP_200_OK)


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
        coach = get_object_or_404(User, username__iexact=username, user_type='coach')
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
        coach = get_object_or_404(User, pk=user_id, user_type='coach')
        linked = request.data.get('linked')
        if not isinstance(linked, bool):
            return Response({'linked': ['Must be a boolean.']}, status=status.HTTP_400_BAD_REQUEST)
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


class HeadAthletePrimaryCoachView(APIView):
    """Set an org athlete's primary_coach to this head or a line coach under this head."""

    def patch(self, request, user_id):
        if not is_head_coach(request.user):
            return Response(
                {'detail': 'Only head coaches can assign athletes.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        head = request.user
        athlete = get_object_or_404(User, pk=user_id, user_type='athlete')
        coach_id = request.data.get('primary_coach_id')
        try:
            coach_id = int(coach_id)
        except (TypeError, ValueError):
            return Response(
                {'primary_coach_id': ['Must be an integer user id.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        coach = get_object_or_404(User, pk=coach_id)
        if coach.user_type not in ('coach', 'head_coach'):
            return Response(
                {'primary_coach_id': ['Target must be a coach or head coach.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if coach.user_type == 'head_coach' and coach.id != head.id:
            return Response(
                {'primary_coach_id': ['Athletes may only report to your account as head coach.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if coach.user_type == 'coach':
            if coach.reports_to_id != head.id:
                return Response(
                    {'primary_coach_id': ['Line coach must report to you before they can own an athlete.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        allowed = set(_org_coach_ids(head))
        if coach.id not in allowed:
            return Response(
                {'primary_coach_id': ['Coach is not in your organization.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        prev = athlete.primary_coach_id
        if prev is not None and prev not in allowed:
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
