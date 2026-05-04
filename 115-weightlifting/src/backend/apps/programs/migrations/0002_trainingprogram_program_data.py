# Generated manually for structured program support.

from django.db import migrations, models

import apps.programs.models


class Migration(migrations.Migration):

    dependencies = [
        ('programs', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='trainingprogram',
            name='program_data',
            field=models.JSONField(blank=True, default=apps.programs.models.default_program_data),
        ),
    ]

