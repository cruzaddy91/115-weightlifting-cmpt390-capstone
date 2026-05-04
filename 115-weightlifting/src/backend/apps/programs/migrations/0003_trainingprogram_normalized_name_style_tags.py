from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('programs', '0002_trainingprogram_program_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='trainingprogram',
            name='normalized_name',
            field=models.CharField(blank=True, db_index=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='trainingprogram',
            name='style_tags',
            field=models.JSONField(blank=True, default=list),
        ),
    ]

