from django.urls import path
from .views import (
    HeadModelStatusView,
    HeadProgramNameOutcomesView,
    HeadProgramStyleOutcomesView,
    HeadRecommendationsView,
    RobiView,
    SinclairView,
)

urlpatterns = [
    path('sinclair/', SinclairView.as_view(), name='sinclair'),
    path('robi/', RobiView.as_view(), name='robi'),
    path('head/program-style-outcomes/', HeadProgramStyleOutcomesView.as_view(), name='head-program-style-outcomes'),
    path('head/program-name-outcomes/', HeadProgramNameOutcomesView.as_view(), name='head-program-name-outcomes'),
    path('head/recommendations/', HeadRecommendationsView.as_view(), name='head-recommendations'),
    path('head/model-status/', HeadModelStatusView.as_view(), name='head-model-status'),
]
