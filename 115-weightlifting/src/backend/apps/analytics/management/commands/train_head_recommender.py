from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.roles import is_head_coach, staff_coach_queryset
from apps.athletes.models import PersonalRecord
from apps.analytics.ml.features import build_training_rows_for_head
from apps.analytics.ml.trainer import train_recommender_model
from apps.programs.models import TrainingProgram

User = get_user_model()


def _pr_delta_for_program(program):
    if not program.end_date:
        return None
    baseline = (
        PersonalRecord.objects
        .filter(athlete_id=program.athlete_id, lift_type='total', date__lte=program.start_date)
        .order_by('-date')
        .values_list('weight', flat=True)
        .first()
    )
    outcome = (
        PersonalRecord.objects
        .filter(athlete_id=program.athlete_id, lift_type='total', date__gte=program.end_date)
        .order_by('-weight', '-date')
        .values_list('weight', flat=True)
        .first()
    )
    if baseline is None or outcome is None:
        return None
    return float(outcome - baseline)


class Command(BaseCommand):
    help = 'Train and persist head-coach recommendation model artifacts.'

    def add_arguments(self, parser):
        parser.add_argument('--head-id', type=int, required=True, help='Head coach user id')

    def handle(self, *args, **options):
        head_id = options['head_id']
        try:
            head = User.objects.get(pk=head_id)
        except User.DoesNotExist as exc:
            raise CommandError(f'Head coach not found: {head_id}') from exc
        if not is_head_coach(head):
            raise CommandError(f'User {head_id} is not a head coach.')

        coach_ids = [head.id, *list(staff_coach_queryset(head).values_list('pk', flat=True))]
        programs = TrainingProgram.objects.filter(coach_id__in=coach_ids)
        pr_delta_lookup = {program.id: _pr_delta_for_program(program) for program in programs}
        rows = build_training_rows_for_head(head, coach_ids, pr_delta_lookup)
        if len(rows) < 12:
            raise CommandError('Need at least 12 rows to train the recommender model.')

        result = train_recommender_model(rows)
        artifact = result['artifact']
        metrics = result['metrics']
        self.stdout.write(self.style.SUCCESS(
            f"Trained {artifact['version']} accuracy={metrics['accuracy']} auc={metrics['roc_auc']} rows={metrics['rows']}"
        ))

