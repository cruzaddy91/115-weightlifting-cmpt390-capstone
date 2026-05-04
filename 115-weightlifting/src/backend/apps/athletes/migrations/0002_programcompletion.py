# Generated manually for athlete program completion tracking.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

import apps.athletes.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('programs', '0002_trainingprogram_program_data'),
        ('athletes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProgramCompletion',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('completion_data', models.JSONField(blank=True, default=apps.athletes.models.default_completion_data)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'athlete',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='program_completions',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'program',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='completion_records',
                        to='programs.trainingprogram',
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name='programcompletion',
            constraint=models.UniqueConstraint(
                fields=('program', 'athlete'),
                name='unique_program_completion_per_athlete',
            ),
        ),
    ]

