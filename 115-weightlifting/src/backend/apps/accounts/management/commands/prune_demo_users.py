"""Trim local databases down to the canonical capstone demo roster.

Keeps **Headcoachone** (org head) with **Coachone** + first five ``game-of-thrones``
athletes and **Coachtwo** + first five ``lord-of-the-rings`` athletes (same rosters
as ``tools/sim/seed.py`` defaults). **Adminone** remains as an extra head-coach
account for legacy checks. Removes every other non-staff coach/athlete user.

Staff and superusers are never deleted. Run with ``--dry-run`` first.
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

User = get_user_model()

_REPO_ROOT = Path(__file__).resolve().parents[6]
_TOOLS_SIM = _REPO_ROOT / 'tools' / 'sim'
_ROSTER_SIZE = 5


def _import_tools_sim():
    p = str(_TOOLS_SIM)
    if p not in sys.path:
        sys.path.insert(0, p)
    from character_sim_profiles import resolve_sim_profile  # noqa: WPS433
    from themes import roster  # noqa: WPS433

    return roster, resolve_sim_profile


def _canonical_usernames() -> tuple[str, ...]:
    roster, _ = _import_tools_sim()
    got = roster('game-of-thrones', _ROSTER_SIZE)
    lotr = roster('lord-of-the-rings', _ROSTER_SIZE)
    return ('Adminone', 'Headcoachone', 'Coachone', 'Coachtwo', *got, *lotr)


def _ensure_canonical_users(password: str) -> dict:
    roster, resolve_sim_profile = _import_tools_sim()
    created_or_updated = []

    admin_head, _ = User.objects.get_or_create(
        username='Adminone',
        defaults={'user_type': 'head_coach'},
    )
    admin_head.user_type = 'head_coach'
    admin_head.reports_to = None
    admin_head.set_password(password)
    admin_head.save()
    created_or_updated.append('Adminone')

    head_org, _ = User.objects.get_or_create(
        username='Headcoachone',
        defaults={'user_type': 'head_coach'},
    )
    head_org.user_type = 'head_coach'
    head_org.reports_to = None
    head_org.set_password(password)
    head_org.save()
    created_or_updated.append('Headcoachone')

    for coach_username, theme in (
        ('Coachone', 'game-of-thrones'),
        ('Coachtwo', 'lord-of-the-rings'),
    ):
        coach, _ = User.objects.get_or_create(
            username=coach_username,
            defaults={'user_type': 'coach'},
        )
        coach.user_type = 'coach'
        coach.reports_to = head_org
        coach.set_password(password)
        coach.save()
        created_or_updated.append(coach_username)

        for index, username in enumerate(roster(theme, _ROSTER_SIZE)):
            bw, gender = resolve_sim_profile(username, index)
            athlete, _ = User.objects.get_or_create(
                username=username,
                defaults={'user_type': 'athlete'},
            )
            athlete.user_type = 'athlete'
            athlete.set_password(password)
            athlete.bodyweight_kg = Decimal(str(bw)).quantize(Decimal('0.01'))
            athlete.gender = gender
            athlete.primary_coach = coach
            athlete.save()
            created_or_updated.append(username)

    return {'users_refreshed': created_or_updated}


class Command(BaseCommand):
    help = (
        'Delete coach/athlete users outside the canonical demo roster '
        '(Headcoachone org head → Coachone+5 GoT, Coachtwo+5 LotR; Adminone kept). Staff/superusers kept.'
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
            help='Perform deletions (irreversible except via backup/restore).',
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
        demo_password = options['demo_password']

        if dry_run and apply:
            self.stderr.write('Use only one of --dry-run or --apply.')
            raise SystemExit(2)
        if not dry_run and not apply:
            self.stderr.write('Specify --dry-run to preview or --apply to execute.')
            raise SystemExit(2)

        keep = frozenset(_canonical_usernames())

        protected = User.objects.filter(is_superuser=True) | User.objects.filter(is_staff=True)
        protected_ids = set(protected.values_list('id', flat=True))

        candidates = User.objects.filter(
            user_type__in=('coach', 'athlete', 'head_coach'),
        ).exclude(id__in=protected_ids)
        to_remove = candidates.exclude(username__in=keep).order_by('username')

        remove_list = list(to_remove.values_list('username', flat=True))
        self.stdout.write(f'Canonical keep set ({len(keep)}): {", ".join(sorted(keep))}')
        self.stdout.write(f'Would delete {len(remove_list)} user(s).')
        if remove_list:
            preview = remove_list[:40]
            self.stdout.write('Sample: ' + ', '.join(preview) + (' …' if len(remove_list) > 40 else ''))

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run only; no changes made.'))
            return

        with transaction.atomic():
            deleted, _ = to_remove.delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted rows (including cascades): {deleted}'))

        if not options['no_ensure_canonical']:
            info = _ensure_canonical_users(demo_password)
            self.stdout.write(self.style.SUCCESS(f'Canonical users refreshed: {info["users_refreshed"]}'))
        self.stdout.write(
            self.style.WARNING(
                'Demo password is not printed. Set DEMO_PASSWORD in the environment '
                'or use the default documented in tools/sim/seed.py and README.',
            ),
        )
