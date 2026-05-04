from django.db import models
from django.conf import settings


class Competition(models.Model):
    name = models.CharField(max_length=200)
    date = models.DateField()
    location = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CompetitionAttempt(models.Model):
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='attempts')
    athlete = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='competition_attempts')
    lift_type = models.CharField(max_length=20, choices=[('snatch', 'Snatch'), ('clean_jerk', 'Clean & Jerk')])
    attempt_number = models.IntegerField()
    weight = models.DecimalField(max_digits=6, decimal_places=2)
    success = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

