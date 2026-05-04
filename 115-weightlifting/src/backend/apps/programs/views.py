from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404

from apps.accounts.roles import coach_may_bind_athlete, is_head_coach, is_line_coach, staff_coach_queryset
from apps.athletes.models import ProgramCompletion
from .models import TrainingProgram
from .serializers import ProgramCreateSerializer, ProgramUpdateSerializer, TrainingProgramSerializer

User = get_user_model()


class ProgramListCreate(APIView):
    """List programs for the current user (as coach or athlete)."""

    def get(self, request):
        user = request.user
        # Single-query version of coach-or-athlete filter, with prefetched
        # completion records so TrainingProgramSerializer.get_completion_data
        # does not issue a SELECT per program (N+1 kill).
        if is_head_coach(user):
            staff_ids = list(staff_coach_queryset(user).values_list('id', flat=True))
            visibility = Q(coach=user) | Q(coach_id__in=staff_ids) | Q(athlete=user)
        else:
            visibility = Q(coach=user) | Q(athlete=user)
        programs = (
            TrainingProgram.objects
            .filter(visibility)
            .select_related('coach', 'athlete')
            .prefetch_related(Prefetch('completion_records', queryset=ProgramCompletion.objects.all()))
            .distinct()
            .order_by('-created_at')
        )
        serializer = TrainingProgramSerializer(programs, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        if not is_line_coach(request.user):
            return Response({'detail': 'Only coaches can create programs.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = ProgramCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            program = serializer.save()
            response_serializer = TrainingProgramSerializer(program)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProgramDetail(APIView):
    """Update an existing structured training program."""

    def patch(self, request, program_id):
        if not is_line_coach(request.user):
            return Response({'detail': 'Only coaches can edit programs.'}, status=status.HTTP_403_FORBIDDEN)

        program = get_object_or_404(TrainingProgram, id=program_id, coach=request.user)
        serializer = ProgramUpdateSerializer(program, data=request.data, partial=True)
        if serializer.is_valid():
            updated_program = serializer.save()
            return Response(TrainingProgramSerializer(updated_program).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProgramAssign(APIView):
    """Reassign an existing program to a different athlete."""

    def patch(self, request, program_id):
        if not is_line_coach(request.user):
            return Response({'detail': 'Only coaches can assign programs.'}, status=status.HTTP_403_FORBIDDEN)

        program = get_object_or_404(TrainingProgram, id=program_id, coach=request.user)
        athlete_id = request.data.get('athlete_id')
        if not athlete_id:
            return Response({'athlete_id': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)

        try:
            athlete = User.objects.get(id=athlete_id, user_type='athlete')
        except User.DoesNotExist:
            return Response({'athlete_id': ['Selected athlete does not exist.']}, status=status.HTTP_400_BAD_REQUEST)

        if not coach_may_bind_athlete(request.user, athlete):
            return Response(
                {'athlete_id': ['You can only assign this program to athletes you manage.']},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Preserve prior athlete's completion history. The (program, athlete)
        # unique constraint means the new athlete gets a fresh record on first log;
        # wiping all records would silently destroy the prior athlete's work.
        with transaction.atomic():
            program.athlete = athlete
            program.save(update_fields=['athlete', 'updated_at'])
            User.objects.filter(pk=athlete.id, user_type='athlete').update(primary_coach_id=program.coach_id)
        serializer = TrainingProgramSerializer(program)
        return Response(serializer.data, status=status.HTTP_200_OK)
