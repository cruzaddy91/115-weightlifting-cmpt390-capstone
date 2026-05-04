from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.programs.models import TrainingProgram


class Command(BaseCommand):
    help = (
        'Remove training programs whose name or description contains angle '
        'brackets (legacy XSS probe rows or bad imports). CASCADE deletes '
        'linked ProgramCompletion rows.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Perform deletes (default is a dry-run that only lists matches).',
        )

    def handle(self, *args, **options):
        qs = TrainingProgram.objects.filter(
            Q(name__contains='<')
            | Q(name__contains='>')
            | Q(description__contains='<')
            | Q(description__contains='>')
        ).order_by('id')
        n = qs.count()
        if n == 0:
            self.stdout.write(self.style.SUCCESS('No matching programs.'))
            return
        for p in qs:
            self.stdout.write(
                f'  id={p.id} athlete_id={p.athlete_id} name={p.name!r}',
            )
        if not options['apply']:
            self.stdout.write(
                self.style.WARNING(
                    f'Dry-run: {n} program(s) matched. Re-run with --apply to delete.',
                ),
            )
            return
        deleted, breakdown = qs.delete()
        self.stdout.write(
            self.style.SUCCESS(f'Deleted {deleted} row(s) total: {breakdown}'),
        )
