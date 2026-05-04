from django.urls import path
from .views import PersonalRecordListCreate, ProgramCompletionDetail, WorkoutLogListCreate

urlpatterns = [
    path('workouts/', WorkoutLogListCreate.as_view(), name='workout-log-list-create'),
    path('prs/', PersonalRecordListCreate.as_view(), name='personal-record-list-create'),
    path('program-completion/<int:program_id>/', ProgramCompletionDetail.as_view(), name='program-completion-detail'),
]
