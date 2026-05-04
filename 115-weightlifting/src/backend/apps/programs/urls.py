from django.urls import path
from .views import ProgramAssign, ProgramDetail, ProgramListCreate

urlpatterns = [
    path('', ProgramListCreate.as_view(), name='program-list-create'),
    path('<int:program_id>/', ProgramDetail.as_view(), name='program-detail'),
    path('<int:program_id>/assign/', ProgramAssign.as_view(), name='program-assign'),
]
