from rest_framework import status
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings as dj_settings
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .serializers import AthleteProfileUpdateSerializer, CurrentUserSerializer, RegisterSerializer
from .weight_class import competitive_weight_class_label


REFRESH_COOKIE_NAME = 'wl_refresh'
REFRESH_COOKIE_PATH = '/api/auth/'


def _refresh_cookie_kwargs():
    secure = not dj_settings.DEBUG
    return {
        'httponly': True,
        'secure': secure,
        'samesite': 'Lax',
        'path': REFRESH_COOKIE_PATH,
        'max_age': int(dj_settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()),
    }


def _set_refresh_cookie(response, refresh_token):
    response.set_cookie(REFRESH_COOKIE_NAME, refresh_token, **_refresh_cookie_kwargs())


def _clear_refresh_cookie(response):
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


class LoginRateThrottle(AnonRateThrottle):
    scope = 'login'


class RegisterRateThrottle(AnonRateThrottle):
    scope = 'register'

User = get_user_model()


class TokenObtainPairViewAllowAny(TokenObtainPairView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200 and 'refresh' in response.data:
            _set_refresh_cookie(response, response.data['refresh'])
        return response


class TokenRefreshViewAllowAny(TokenRefreshView):
    """Accepts the refresh token from request body OR from the httpOnly cookie.

    On successful rotation the new refresh token is written back to the cookie,
    so clients that use cookie-only auth never expose the refresh token to JS.
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        if not request.data.get('refresh'):
            cookie_refresh = request.COOKIES.get(REFRESH_COOKIE_NAME)
            if cookie_refresh:
                mutable = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
                mutable['refresh'] = cookie_refresh
                request._full_data = mutable
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200 and 'refresh' in response.data:
            _set_refresh_cookie(response, response.data['refresh'])
        return response


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {'message': 'User created. Use /api/auth/token/ to log in.'},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CurrentUserView(APIView):
    def get(self, request):
        serializer = CurrentUserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        """Athletes may update bodyweight + gender (drives competitive weight class)."""
        if request.user.user_type != 'athlete':
            return Response(
                {'detail': 'Only athletes can update these profile fields.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = AthleteProfileUpdateSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(CurrentUserSerializer(request.user).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        """Delete the current user's own account.

        Cascade policy (enforced here explicitly; the DB cascade would otherwise
        fire without the safety net):

          - ATHLETES: straight delete. DB CASCADE removes the athlete's
            PersonalRecord / WorkoutLog / ProgramCompletion rows AND any
            TrainingProgram assigned to them (a program without an athlete is
            meaningless). Other coaches' programs for other athletes are
            untouched because each program has its own coach FK.
          - COACHES: REFUSED if the coach still has programs. A bulk cascade
            would vaporize every assigned athlete's training history. Coach
            must reassign their programs away (or delete them) first. This
            is a capstone-grade safeguard; a production system would offer
            bulk-transfer UI before deletion.

        Requires the account password in the request body as a confirmation
        step so a stolen access token alone cannot erase an account.
        """
        user = request.user
        password = request.data.get('password')
        if not password or not user.check_password(password):
            return Response(
                {'password': ['Password confirmation is required to delete an account.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user.user_type in ('coach', 'head_coach'):
            from apps.programs.models import TrainingProgram
            active = TrainingProgram.objects.filter(coach=user).count()
            if active > 0:
                return Response(
                    {'detail': f'You still have {active} program(s). Reassign or delete them before closing your coach account.'},
                    status=status.HTTP_409_CONFLICT,
                )
        user.delete()
        response = Response(status=status.HTTP_204_NO_CONTENT)
        # Best-effort clear any refresh cookie the user still holds.
        _clear_refresh_cookie(response)
        return response


class LogoutView(APIView):
    """Blacklist the supplied refresh token so it cannot be reused.

    Accepts the refresh token in the request body OR the httpOnly cookie.
    Always clears the cookie on exit, even on failure, so a stale cookie
    cannot keep trying to resurrect a session.
    """

    def post(self, request):
        refresh = request.data.get('refresh') or request.COOKIES.get(REFRESH_COOKIE_NAME)
        if not refresh:
            response = Response(
                {'refresh': ['This field is required.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
            _clear_refresh_cookie(response)
            return response
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            response = Response(
                {'refresh': ['Invalid or already-expired refresh token.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
            _clear_refresh_cookie(response)
            return response
        response = Response(status=status.HTTP_205_RESET_CONTENT)
        _clear_refresh_cookie(response)
        return response


class AthleteListView(APIView):
    """List athlete users for coach program UI.

    Line coaches: only ``scope=mine`` (athletes they manage via ``primary_coach``).
    Head coaches: ``scope=mine`` is org roster; ``scope=all`` is the same org pool
    plus any athlete who already appears on staff programs (for edge cases).
    """

    PAGE_SIZE = 50

    def get(self, request):
        from django.db.models import Q

        from apps.accounts.roles import is_head_coach, is_line_coach, staff_coach_queryset
        from apps.programs.models import TrainingProgram

        if not is_line_coach(request.user):
            return Response({'detail': 'Only coaches can list athletes.'}, status=status.HTTP_403_FORBIDDEN)

        scope = request.query_params.get('scope', 'mine').lower()
        query = (request.query_params.get('q') or '').strip()
        try:
            page = max(1, int(request.query_params.get('page', '1')))
        except ValueError:
            page = 1

        if scope == 'all' and not is_head_coach(request.user):
            return Response(
                {
                    'detail': (
                        'Line coaches may only use scope=mine (athletes you manage). '
                        'Head coaches may use scope=all to browse the organization roster.'
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        base = User.objects.filter(user_type='athlete')
        if is_head_coach(request.user):
            staff_ids = list(staff_coach_queryset(request.user).values_list('id', flat=True))
            org_ids = [request.user.id, *staff_ids]
            if scope == 'all':
                id_primary = set(
                    User.objects.filter(user_type='athlete', primary_coach_id__in=org_ids).values_list(
                        'pk', flat=True
                    )
                )
                id_prog = set(
                    TrainingProgram.objects.filter(Q(coach=request.user) | Q(coach_id__in=staff_ids))
                    .values_list('athlete_id', flat=True)
                    .distinct()
                )
                base = base.filter(pk__in=(id_primary | id_prog))
            else:
                base = base.filter(primary_coach_id__in=org_ids)
        else:
            base = base.filter(primary_coach=request.user)

        if query:
            base = base.filter(username__icontains=query)

        total = base.count()
        offset = (page - 1) * self.PAGE_SIZE
        rows = list(
            base.order_by('username').values(
                'id', 'username', 'bodyweight_kg', 'gender',
            )[offset:offset + self.PAGE_SIZE]
        )
        athletes = []
        for row in rows:
            bw = row.get('bodyweight_kg')
            athletes.append({
                'id': row['id'],
                'username': row['username'],
                'bodyweight_kg': float(bw) if bw is not None else None,
                'gender': row.get('gender'),
                'competitive_weight_class': competitive_weight_class_label(
                    row.get('bodyweight_kg'), row.get('gender'),
                ),
            })
        return Response(
            {
                'results': athletes,
                'count': total,
                'page': page,
                'page_size': self.PAGE_SIZE,
                'scope': scope if is_head_coach(request.user) else 'mine',
            },
            status=status.HTTP_200_OK,
        )
