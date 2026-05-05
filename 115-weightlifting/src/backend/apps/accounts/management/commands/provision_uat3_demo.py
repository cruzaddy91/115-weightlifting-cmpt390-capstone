import json

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.demo_provisioning import provision_uat3_scenario


class Command(BaseCommand):
    help = 'Provision UAT3 demo deployment scenarios.'

    def add_arguments(self, parser):
        parser.add_argument(
            'scenario',
            nargs='?',
            default='preserve_current',
            choices=['preserve_current', 'fully_loaded', 'half_cock', 'bare_base', 'skeleton'],
            help='Demo scenario to provision.',
        )
        parser.add_argument(
            '--keep-history',
            action='store_true',
            help='Do not replace existing PR/workout/program history for provisioned athletes.',
        )

    def handle(self, *args, **options):
        try:
            result = provision_uat3_scenario(
                scenario=options['scenario'],
                replace_history=not options['keep_history'],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(json.dumps({
            'scenario': result.scenario,
            'heads': result.heads,
            'line_coaches': result.line_coaches,
            'athletes': result.athletes,
            'programs': result.programs,
            'prs': result.prs,
            'workouts': result.workouts,
        }, sort_keys=True)))
