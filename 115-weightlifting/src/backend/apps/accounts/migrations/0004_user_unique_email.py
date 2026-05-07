# Generated for Docker professor-facing auth hardening.

from django.db import migrations, models


def backfill_unique_emails(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    seen = set()
    for user in User.objects.order_by('pk'):
        current = (user.email or '').strip().lower()
        if current and current not in seen:
            user.email = current
            seen.add(current)
            user.save(update_fields=['email'])
            continue

        base = ''.join(ch if ch.isalnum() else '-' for ch in (user.username or f'user-{user.pk}').lower())
        base = '-'.join(part for part in base.split('-') if part) or f'user-{user.pk}'
        generated = f'{base}-{user.pk}@example.invalid'
        while generated in seen:
            generated = f'{base}-{user.pk}-{len(seen)}@example.invalid'
        user.email = generated
        seen.add(generated)
        user.save(update_fields=['email'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_head_coach_hierarchy'),
    ]

    operations = [
        migrations.RunPython(backfill_unique_emails, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='user',
            name='email',
            field=models.EmailField(max_length=254, unique=True),
        ),
    ]
