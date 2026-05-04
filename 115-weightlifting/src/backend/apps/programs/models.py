from django.db import models
from django.conf import settings


def default_program_data():
    return {
        'week_start_date': '',
        'days': [
            {'day': 'Monday', 'exercises': []},
            {'day': 'Tuesday', 'exercises': []},
            {'day': 'Wednesday', 'exercises': []},
            {'day': 'Thursday', 'exercises': []},
            {'day': 'Friday', 'exercises': []},
        ],
    }


class TrainingProgram(models.Model):
    coach = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='programs')
    athlete = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assigned_programs')
    name = models.CharField(max_length=200)
    normalized_name = models.CharField(max_length=200, blank=True, default='', db_index=True)
    style_tags = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    program_data = models.JSONField(default=default_program_data, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
