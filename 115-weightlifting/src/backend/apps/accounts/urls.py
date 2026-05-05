from django.urls import path
from .head_views import (
    HeadAthletePrimaryCoachView,
    HeadCoachAssignmentView,
    HeadOrgRosterView,
    HeadOrgSummaryView,
    HeadStaffInviteView,
    HeadStaffLinkView,
)
from .views import (
    AthleteListView,
    CurrentUserView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    TokenObtainPairViewAllowAny,
    TokenRefreshViewAllowAny,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('token/', TokenObtainPairViewAllowAny.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshViewAllowAny.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path('athletes/', AthleteListView.as_view(), name='athlete-list'),
    path('head/org-summary/', HeadOrgSummaryView.as_view(), name='head-org-summary'),
    path('head/roster/', HeadOrgRosterView.as_view(), name='head-org-roster'),
    path('head/staff/', HeadStaffInviteView.as_view(), name='head-staff-invite'),
    path('head/staff/<int:user_id>/', HeadStaffLinkView.as_view(), name='head-staff-link'),
    path('head/head-coaches/<int:user_id>/', HeadCoachAssignmentView.as_view(), name='head-coach-assignment'),
    path('head/athletes/<int:user_id>/', HeadAthletePrimaryCoachView.as_view(), name='head-athlete-primary-coach'),
]
