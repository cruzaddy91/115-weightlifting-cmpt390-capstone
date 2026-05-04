"""Create Coachtwo + five LotR athletes and bulk-seed ~3y PR/workout history.

Reuses ``seed_longterm_for_usernames`` with profiles defined in
``long_history_seed.ATHLETE_PROFILES`` (frodo_baggins … gandalf_grey). Body mass
and sex category are taken from ``tools/sim/character_sim_profiles.py``.

Optional HTTP programs: run with API up::

    cd tools/sim && python build_programs.py --coach Coachtwo --theme lord-of-the-rings --athletes 5

or pass ``--with-programs`` to the shell wrapper ``scripts/seed_coachtwo_lotr_demo.sh``.
"""
from __future__ import annotations

import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import shutil

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.athletes.long_history_seed import seed_longterm_for_usernames

_REPO_ROOT = Path(__file__).resolve().parents[6]
_TOOLS_SIM = _REPO_ROOT / 'tools' / 'sim'


def _tools_sim_imports():
    p = str(_TOOLS_SIM)
    if p not in sys.path:
        sys.path.insert(0, p)
    from character_sim_profiles import resolve_sim_profile  # noqa: WPS433
    from themes import roster  # noqa: WPS433

    return roster, resolve_sim_profile


class Command(BaseCommand):
    help = 'Create Coachtwo + 5 LotR athletes and seed multi-year PR/workout demo rows.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Clear existing PR + workout rows for these athletes before insert.',
        )
        parser.add_argument(
            '--years',
            type=int,
            default=3,
            help='Years of simulated history (default: 3).',
        )
        parser.add_argument(
            '--demo-password',
            default=os.environ.get('DEMO_PASSWORD', 'Passw0rd!123'),
            help='Password for Coachtwo and all LotR athletes.',
        )
        parser.add_argument(
            '--with-programs',
            action='store_true',
            help='After ORM seed, run tools/sim/build_programs.py (needs Django API on WL_API).',
        )
        parser.add_argument(
            '--api',
            default=os.environ.get('WL_API', 'http://127.0.0.1:8000'),
            help='API base URL for --with-programs (default: env WL_API or http://127.0.0.1:8000).',
        )

    def handle(self, *args, **options):
        roster, resolve_sim_profile = _tools_sim_imports()
        names = list(roster('lord-of-the-rings', 5))
        password = options['demo_password']
        User = get_user_model()

        coach, _ = User.objects.get_or_create(
            username='Coachtwo',
            defaults={'user_type': 'coach'},
        )
        coach.user_type = 'coach'
        coach.set_password(password)
        coach.save()

        for index, username in enumerate(names):
            bw, gender = resolve_sim_profile(username, index)
            athlete, _ = User.objects.get_or_create(
                username=username,
                defaults={'user_type': 'athlete'},
            )
            athlete.user_type = 'athlete'
            athlete.set_password(password)
            athlete.bodyweight_kg = Decimal(str(bw)).quantize(Decimal('0.01'))
            athlete.gender = gender
            athlete.save()

        summary = seed_longterm_for_usernames(
            usernames=names,
            replace=options['replace'],
            years=options['years'],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Coachtwo + {len(names)} athletes ready. History: athletes={summary.athletes} '
                f'pr_rows={summary.pr_rows} workout_rows={summary.workout_rows} '
                f'(deleted prs={summary.deleted_prs}, workouts={summary.deleted_workouts})',
            ),
        )
        self.stdout.write(f'Athletes: {", ".join(names)}')
        self.stdout.write(
            self.style.WARNING(
                'Password not printed; use DEMO_PASSWORD or default Passw0rd!123 (see tools/sim/seed.py).',
            ),
        )

        if options['with_programs']:
            build_script = _REPO_ROOT / 'tools' / 'sim' / 'build_programs.py'
            sim_venv_py = _REPO_ROOT / 'tools' / 'sim' / '.venv' / 'bin' / 'python'
            runner = str(sim_venv_py) if sim_venv_py.is_file() else shutil.which('python3') or sys.executable
            cmd = [
                runner,
                str(build_script),
                '--coach',
                'Coachtwo',
                '--coach-password',
                password,
                '--theme',
                'lord-of-the-rings',
                '--athletes',
                '5',
                '--api',
                options['api'],
            ]
            self.stdout.write(self.style.NOTICE(f'Running: {" ".join(cmd)}'))
            proc = subprocess.run(cmd, cwd=str(_TOOLS_SIM), check=False)
            if proc.returncode != 0:
                self.stderr.write(
                    self.style.ERROR(
                        f'build_programs.py exited {proc.returncode}. '
                        'Ensure the API is up and Coachtwo can log in.',
                    ),
                )
                raise SystemExit(proc.returncode)
