from django.core.management.base import BaseCommand

from apps.programs.models import TrainingProgram
from apps.programs.serializers import canonical_program_name, derive_program_style_tags


class Command(BaseCommand):
    help = 'Backfill normalized_name and style_tags for TrainingProgram rows.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Persist updates. Without this flag, runs as a dry-run.')

    def handle(self, *args, **options):
        apply_changes = bool(options.get('apply'))
        updated = 0
        total = 0
        for program in TrainingProgram.objects.all().iterator():
            total += 1
            normalized_name = canonical_program_name(program.name)
            style_tags = derive_program_style_tags(program.program_data or {})
            if program.normalized_name == normalized_name and program.style_tags == style_tags:
                continue
            updated += 1
            if apply_changes:
                program.normalized_name = normalized_name
                program.style_tags = style_tags
                program.save(update_fields=['normalized_name', 'style_tags'])
        mode = 'apply' if apply_changes else 'dry-run'
        self.stdout.write(f'backfill_program_normalization mode={mode} total={total} updated={updated}')

