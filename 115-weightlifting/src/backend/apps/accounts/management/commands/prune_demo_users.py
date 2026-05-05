"""Archive or permanently remove local demo users outside the canonical roster.

Keeps canonical head coaches, canonical line coaches, **000_Athlete1**,
and the unassigned demo athlete pool.
Staff and superusers are never archived/deleted. Run with ``--dry-run`` first.

Default ``--apply`` behavior is non-destructive archive. Use ``--permanent-clean``
only for the Docker/UAT/demo cleanup path.
"""
from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.org_labels import (
    DEMO_ATHLETE_USERNAME,
    DEMO_COACH_USERNAME,
    DEMO_HEAD_COACH_USERNAMES,
    DEMO_LINE_COACH_USERNAMES,
    DEMO_UNASSIGNED_ATHLETE_USERNAMES,
    MASTER_HEAD_USERNAME,
)
from apps.programs.models import TrainingProgram

User = get_user_model()


def _assigned_head_variants(username: str) -> list[str]:
    suffix = username.split('_', 1)[1]
    return [f'{prefix}_{suffix}' for prefix in ('001', '002', '003', '004')]


def _migrate_user_identity(old_username: str, new_username: str) -> None:
    old_user = User.objects.filter(username=old_username).first()
    if old_user is None:
        return
    new_user = User.objects.filter(username=new_username).first()
    if new_user is None:
        old_user.username = new_username
        old_user.save(update_fields=['username'])
        return
    User.objects.filter(reports_to=old_user).update(reports_to=new_user)
    User.objects.filter(primary_coach=old_user).update(primary_coach=new_user)
    TrainingProgram.objects.filter(coach=old_user).update(
        coach=new_user,
        updated_at=timezone.now(),
    )
    old_user.email = f'archived_{old_user.pk}@example.invalid'
    old_user.is_active = False
    old_user.save(update_fields=['email', 'is_active'])


def _release_demo_email(email: str, except_user=None):
    blockers = User.objects.filter(email__iexact=email)
    if except_user is not None:
        blockers = blockers.exclude(pk=except_user.pk)
    for blocker in blockers:
        blocker.email = f'archived_{blocker.pk}@example.invalid'
        blocker.is_active = False
        blocker.save(update_fields=['email', 'is_active'])


def _canonical_usernames() -> tuple[str, ...]:
    return (
        *DEMO_HEAD_COACH_USERNAMES,
        *DEMO_LINE_COACH_USERNAMES,
        DEMO_ATHLETE_USERNAME,
        *DEMO_UNASSIGNED_ATHLETE_USERNAMES,
    )


def _cleanup_filter():
    legacy_names = [
        'Adminone',
        '117_MASTER_CHIEF',
        '117_Headcoachone',
        'Headcoachone',
        '001_Headcoachtwo',
        '001_Headcoachthree',
        '001_Headcoachfour',
        '001_Headcoachfive',
        '002_Headcoachone',
        '002_Headcoachtwo',
        '002_Headcoachthree',
        '002_Headcoachfour',
        '002_Headcoachfive',
        '003_Headcoachone',
        '003_Headcoachtwo',
        '003_Headcoachthree',
        '003_Headcoachfour',
        '003_Headcoachfive',
        '004_Headcoachone',
        '004_Headcoachtwo',
        '004_Headcoachthree',
        '004_Headcoachfour',
        '004_Headcoachfive',
        '121_Headcoachfive',
        'Coachone',
        '005_Coachone',
        '100_Coachone',
        '045_Coachone',
        '034_Coachtwo',
        '088_Coachthree',
        '013_Coachfour',
        '008_Athlete5',
        '009_Athlete6',
        '010_Athlete7',
        '011_Athlete8',
        '012_Athlete9',
        '014_Athlete10',
        '015_Athlete11',
        '016_Athlete12',
        '017_Athlete13',
        '018_Athlete14',
        '019_Athlete15',
        '020_Athlete16',
        '000_athelteone',
        'jon_snow',
        'arya_stark',
        'tyrion_lannister',
        'daenerys_targaryen',
        'sansa_stark',
        'frodo_baggins',
        'samwise_gamgee',
        'merry_brandybuck',
        'pippin_took',
        'gandalf_grey',
        'Coachtwo',
    ]
    return (
        Q(username__in=legacy_names)
        | Q(username__contains='docker_UAT')
        | Q(username__contains='dockerUAT')
    )


def _ensure_canonical_users(password: str) -> dict:
    created_or_updated = []

    _migrate_user_identity('117_Headcoachone', MASTER_HEAD_USERNAME)
    _migrate_user_identity('121_Headcoachfive', '121_Headcoachone')
    _migrate_user_identity('001_Headcoachfive', '001_Headcoachone')
    _migrate_user_identity('045_Coachone', '008_Coachone')
    _migrate_user_identity('034_Coachtwo', '013_Coachtwo')
    _migrate_user_identity('088_Coachthree', '048_Coachthree')
    _migrate_user_identity('013_Coachfour', '088_Coachtfour')

    head_org, _ = User.objects.get_or_create(
        username=MASTER_HEAD_USERNAME,
        defaults={'user_type': 'head_coach'},
    )
    head_org.user_type = 'head_coach'
    head_org.email = '117_headcoachgm@example.invalid'
    head_org.reports_to = None
    head_org.is_active = True
    head_org.set_password(password)
    head_org.save()
    created_or_updated.append(MASTER_HEAD_USERNAME)

    for legacy_head in User.objects.filter(username__in=['Headcoachone', '117_MASTER_CHIEF', '117_Headcoachone']):
        User.objects.filter(reports_to=legacy_head).update(reports_to=head_org)
        User.objects.filter(primary_coach=legacy_head).update(primary_coach=head_org)
        TrainingProgram.objects.filter(coach=legacy_head).update(
            coach=head_org,
            updated_at=timezone.now(),
        )

    for username in DEMO_HEAD_COACH_USERNAMES:
        if username == MASTER_HEAD_USERNAME:
            continue
        canonical_exists = User.objects.filter(username=username).exists()
        for assigned_variant in User.objects.filter(username__in=_assigned_head_variants(username)):
            if not canonical_exists:
                assigned_variant.username = username
                assigned_variant.save(update_fields=['username'])
                canonical_exists = True
            else:
                assigned_variant.email = f'archived_{assigned_variant.id}@example.invalid'
                assigned_variant.is_active = False
                assigned_variant.save(update_fields=['email', 'is_active'])
        head_coach, _ = User.objects.get_or_create(
            username=username,
            defaults={'user_type': 'head_coach'},
        )
        head_coach.user_type = 'head_coach'
        head_email = f'{username.lower()}@example.invalid'
        _release_demo_email(head_email, except_user=head_coach)
        head_coach.email = head_email
        head_coach.reports_to = None
        head_coach.is_active = True
        head_coach.set_password(password)
        head_coach.save()
        created_or_updated.append(username)

    line_coaches = {}
    for username in DEMO_LINE_COACH_USERNAMES:
        coach, _ = User.objects.get_or_create(
            username=username,
            defaults={'user_type': 'coach'},
        )
        coach.user_type = 'coach'
        coach.email = f'{username.lower()}@example.invalid'
        coach.reports_to = head_org
        coach.is_active = True
        coach.set_password(password)
        coach.save()
        line_coaches[username] = coach
        created_or_updated.append(username)
    coach = line_coaches[DEMO_COACH_USERNAME]

    legacy_coaches = User.objects.filter(username__in=['Coachone', '005_Coachone', '100_Coachone', '045_Coachone'])
    for legacy_coach in legacy_coaches:
        User.objects.filter(primary_coach=legacy_coach).update(primary_coach=coach)
        TrainingProgram.objects.filter(coach=legacy_coach).update(
            coach=coach,
            updated_at=timezone.now(),
        )

    athlete, _ = User.objects.get_or_create(
        username=DEMO_ATHLETE_USERNAME,
        defaults={'user_type': 'athlete'},
    )
    athlete.user_type = 'athlete'
    athlete.email = '000_athlete1@example.invalid'
    athlete.primary_coach = coach
    athlete.is_active = True
    athlete.set_password(password)
    athlete.save()
    created_or_updated.append(DEMO_ATHLETE_USERNAME)

    for username in DEMO_UNASSIGNED_ATHLETE_USERNAMES:
        athlete, _ = User.objects.get_or_create(
            username=username,
            defaults={'user_type': 'athlete'},
        )
        athlete.user_type = 'athlete'
        athlete.email = f'{username.lower()}@example.invalid'
        athlete.primary_coach = None
        athlete.is_active = True
        athlete.set_password(password)
        athlete.save()
        created_or_updated.append(username)

    return {'users_refreshed': created_or_updated}


class Command(BaseCommand):
    help = (
        'Archive coach/athlete users outside the canonical demo roster '
        '(canonical head coaches -> canonical line coaches -> assigned/unassigned demo athletes). '
        'Staff/superusers kept.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List who would be deleted without changing the database.',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Archive matching users by marking them inactive.',
        )
        parser.add_argument(
            '--permanent-clean',
            action='store_true',
            help='With --apply, permanently delete known Docker/UAT/demo leftovers after canonical migration.',
        )
        parser.add_argument(
            '--no-ensure-canonical',
            action='store_true',
            help='After --apply, skip recreating/refreshed passwords on kept users.',
        )
        parser.add_argument(
            '--demo-password',
            default=os.environ.get('DEMO_PASSWORD', 'Passw0rd!123'),
            help='Password set on canonical users when ensuring they exist (default: env DEMO_PASSWORD or Passw0rd!123).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        apply = options['apply']
        permanent_clean = options['permanent_clean']
        demo_password = options['demo_password']

        if dry_run and apply:
            self.stderr.write('Use only one of --dry-run or --apply.')
            raise SystemExit(2)
        if not dry_run and not apply:
            self.stderr.write('Specify --dry-run to preview or --apply to execute.')
            raise SystemExit(2)
        if permanent_clean and not apply and not dry_run:
            self.stderr.write('--permanent-clean requires --apply.')
            raise SystemExit(2)

        keep = frozenset(_canonical_usernames())

        protected = User.objects.filter(is_superuser=True) | User.objects.filter(is_staff=True)
        protected_ids = set(protected.values_list('id', flat=True))

        if apply and not options['no_ensure_canonical']:
            info = _ensure_canonical_users(demo_password)
            self.stdout.write(self.style.SUCCESS(f'Canonical users refreshed: {info["users_refreshed"]}'))

        candidates = User.objects.filter(
            user_type__in=('coach', 'athlete', 'head_coach'),
        ).exclude(id__in=protected_ids).exclude(username__in=keep)
        if permanent_clean:
            candidates = candidates.filter(_cleanup_filter())
        to_archive = candidates.order_by('username')

        archive_list = list(to_archive.values_list('username', flat=True))
        self.stdout.write(f'Canonical keep set ({len(keep)}): {", ".join(sorted(keep))}')
        action = 'permanently delete' if permanent_clean else 'archive'
        self.stdout.write(f'Would {action} {len(archive_list)} user(s).')
        if archive_list:
            preview = archive_list[:40]
            self.stdout.write('Sample: ' + ', '.join(preview) + (' ...' if len(archive_list) > 40 else ''))

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run only; no changes made.'))
            return

        with transaction.atomic():
            if permanent_clean:
                deleted_count, _ = to_archive.delete()
                self.stdout.write(self.style.SUCCESS(f'Permanently deleted rows: {deleted_count}'))
            else:
                archived = 0
                for user in to_archive:
                    user.is_active = False
                    if user.user_type == 'coach':
                        user.reports_to = None
                        user.save(update_fields=['is_active', 'reports_to'])
                    elif user.user_type == 'athlete':
                        user.primary_coach = None
                        user.save(update_fields=['is_active', 'primary_coach'])
                    else:
                        user.save(update_fields=['is_active'])
                    archived += 1
                self.stdout.write(self.style.SUCCESS(f'Archived users: {archived}'))
        self.stdout.write(
            self.style.WARNING(
                'Demo password is not printed. Set DEMO_PASSWORD in the environment '
                'or use the default documented in tools/sim/seed.py and README.',
            ),
        )
