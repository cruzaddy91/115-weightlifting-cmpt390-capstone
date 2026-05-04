from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from apps.accounts.roles import is_head_coach, staff_coach_queryset
from apps.programs.models import TrainingProgram

User = get_user_model()
from .models import PersonalRecord, ProgramCompletion, WorkoutLog
from .serializers import (
    PersonalRecordSerializer,
    ProgramCompletionSerializer,
    ProgramCompletionUpdateSerializer,
    WorkoutLogSerializer,
)


_COACHED_IDS_CACHE_ATTR = '_coached_athlete_ids_cache'


def _coached_athlete_ids(user, request=None):
    """Return athlete ids coached by *user*, cached for the lifetime of *request*.

    Every authZ check on this view set calls the helper, and without caching
    it re-queries TrainingProgram per call. The cache is attached to the
    incoming request object so each HTTP request pays at most one query.
    """
    if request is not None:
        cached = getattr(request, _COACHED_IDS_CACHE_ATTR, None)
        if cached is not None:
            return cached

    if is_head_coach(user):
        staff_ids = list(staff_coach_queryset(user).values_list('id', flat=True))
        org_ids = [user.id, *staff_ids]
        from_programs = set(
            TrainingProgram.objects.filter(Q(coach=user) | Q(coach_id__in=staff_ids))
            .values_list('athlete_id', flat=True)
            .distinct()
        )
        from_primary = set(
            User.objects.filter(user_type='athlete', primary_coach_id__in=org_ids).values_list(
                'id', flat=True
            )
        )
        athlete_ids = from_programs | from_primary
    else:
        from_programs = set(
            TrainingProgram.objects.filter(coach=user).values_list('athlete_id', flat=True).distinct()
        )
        from_primary = set(
            User.objects.filter(user_type='athlete', primary_coach=user).values_list('id', flat=True)
        )
        athlete_ids = from_programs | from_primary
    if request is not None:
        setattr(request, _COACHED_IDS_CACHE_ATTR, athlete_ids)
    return athlete_ids


class WorkoutLogListCreate(APIView):
    def get(self, request):
        user = request.user
        if user.user_type == 'athlete':
            logs = WorkoutLog.objects.filter(athlete=user).order_by('-date', '-created_at')
        elif user.user_type in ('coach', 'head_coach'):
            athlete_id = request.query_params.get('athlete_id')
            if not athlete_id:
                return Response({'detail': 'athlete_id is required for coach queries.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                athlete_id_int = int(athlete_id)
            except ValueError:
                return Response({'detail': 'athlete_id must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)
            if athlete_id_int not in _coached_athlete_ids(user, request=request):
                return Response({'detail': 'You can only view logs for your assigned athletes.'}, status=status.HTTP_403_FORBIDDEN)
            logs = WorkoutLog.objects.filter(athlete_id=athlete_id_int).order_by('-date', '-created_at')
        else:
            return Response({'detail': 'Unsupported user type.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = WorkoutLogSerializer(logs, many=True)
        return Response(serializer.data)

    def post(self, request):
        user = request.user
        if user.user_type != 'athlete':
            return Response({'detail': 'Only athletes can create workout logs.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = WorkoutLogSerializer(data=request.data, context={'athlete': user})
        if serializer.is_valid():
            workout_log = serializer.save()
            return Response(WorkoutLogSerializer(workout_log).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PersonalRecordListCreate(APIView):
    def get(self, request):
        user = request.user
        if user.user_type == 'athlete':
            prs = PersonalRecord.objects.filter(athlete=user).order_by('-date', '-created_at')
        elif user.user_type in ('coach', 'head_coach'):
            athlete_id = request.query_params.get('athlete_id')
            if not athlete_id:
                return Response({'detail': 'athlete_id is required for coach queries.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                athlete_id_int = int(athlete_id)
            except ValueError:
                return Response({'detail': 'athlete_id must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)
            if athlete_id_int not in _coached_athlete_ids(user, request=request):
                return Response({'detail': 'You can only view PRs for your assigned athletes.'}, status=status.HTTP_403_FORBIDDEN)
            prs = PersonalRecord.objects.filter(athlete_id=athlete_id_int).order_by('-date', '-created_at')
        else:
            return Response({'detail': 'Unsupported user type.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = PersonalRecordSerializer(prs, many=True)
        return Response(serializer.data)

    def post(self, request):
        user = request.user
        if user.user_type != 'athlete':
            return Response({'detail': 'Only athletes can create personal records.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = PersonalRecordSerializer(data=request.data, context={'athlete': user})
        if serializer.is_valid():
            pr = serializer.save()
            return Response(PersonalRecordSerializer(pr).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProgramCompletionDetail(APIView):
    def get(self, request, program_id):
        program = get_object_or_404(TrainingProgram, id=program_id)

        if request.user.user_type == 'athlete':
            if program.athlete_id != request.user.id:
                return Response(
                    {'detail': 'You can only view completion for your assigned programs.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            athlete = request.user
        elif request.user.user_type == 'coach':
            if program.coach_id != request.user.id:
                return Response(
                    {'detail': 'You can only view completion for your own programs.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            athlete = program.athlete
        elif is_head_coach(request.user):
            staff_ids = set(staff_coach_queryset(request.user).values_list('id', flat=True))
            if program.coach_id != request.user.id and program.coach_id not in staff_ids:
                return Response(
                    {'detail': 'You can only view completion for programs in your organization.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            athlete = program.athlete
        else:
            return Response({'detail': 'Unsupported user type.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            completion = ProgramCompletion.objects.get(program=program, athlete=athlete)
        except ProgramCompletion.DoesNotExist:
            return Response(
                {'detail': 'No completion record yet.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ProgramCompletionSerializer(completion).data, status=status.HTTP_200_OK)

    def patch(self, request, program_id):
        if request.user.user_type != 'athlete':
            return Response(
                {'detail': 'Only athletes can update program completion.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        program = get_object_or_404(TrainingProgram, id=program_id, athlete=request.user)
        completion, _ = ProgramCompletion.objects.get_or_create(program=program, athlete=request.user)
        serializer = ProgramCompletionUpdateSerializer(completion, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(ProgramCompletionSerializer(completion).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
