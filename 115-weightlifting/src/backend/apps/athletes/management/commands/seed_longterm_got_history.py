from django.core.management.base import BaseCommand

from apps.athletes.long_history_seed import ATHLETE_PROFILES, seed_longterm_for_usernames


class Command(BaseCommand):
    help = (
        'Bulk-insert ~3 years of PersonalRecord + WorkoutLog demo history for '
        'athletes listed in long_history_seed.ATHLETE_PROFILES (GoT + LotR). '
        'Uses bulk_create in chunks; pass --replace to clear prior PR/workout '
        'rows for those users first.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Delete existing PRs and workout logs for selected athletes before insert.',
        )
        parser.add_argument(
            '--athletes',
            default='',
            help='Comma-separated usernames (default: all keys in ATHLETE_PROFILES).',
        )
        parser.add_argument(
            '--years',
            type=int,
            default=3,
            help='How many calendar years to simulate backward from today.',
        )

    def handle(self, *args, **options):
        raw = (options['athletes'] or '').strip()
        if raw:
            usernames = [u.strip() for u in raw.split(',') if u.strip()]
        else:
            usernames = list(ATHLETE_PROFILES.keys())

        summary = seed_longterm_for_usernames(
            usernames=usernames,
            replace=options['replace'],
            years=options['years'],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"athletes={summary.athletes} pr_rows={summary.pr_rows} "
                f"workout_rows={summary.workout_rows} "
                f"(deleted prs={summary.deleted_prs}, workouts={summary.deleted_workouts})",
            ),
        )
