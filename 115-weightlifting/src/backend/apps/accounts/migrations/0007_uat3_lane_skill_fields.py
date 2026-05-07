from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_user_recoverable_delete_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='date_of_birth',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='org_lane_prefix',
            field=models.CharField(blank=True, default='', max_length=3),
        ),
        migrations.AddField(
            model_name='user',
            name='skill_team',
            field=models.CharField(
                blank=True,
                choices=[
                    ('NOBLE', 'NOBLE'),
                    ('RED', 'RED'),
                    ('SILVER', 'SILVER'),
                    ('BLUE', 'BLUE'),
                ],
                default='',
                max_length=6,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='skill_team_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='skill_team_updated_by_role',
            field=models.CharField(
                blank=True,
                choices=[
                    ('GMHC', 'GMHC'),
                    ('AGMHC', 'AGMHC'),
                    ('LC', 'LC'),
                ],
                default='',
                max_length=5,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='skill_team_updated_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='skill_team_updates',
                to='accounts.user',
            ),
        ),
        migrations.CreateModel(
            name='OrgLaneAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prefix', models.CharField(max_length=3, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'head_coach',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='owned_org_lanes',
                        to='accounts.user',
                    ),
                ),
                (
                    'updated_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='updated_org_lanes',
                        to='accounts.user',
                    ),
                ),
            ],
            options={
                'ordering': ['prefix'],
            },
        ),
    ]
