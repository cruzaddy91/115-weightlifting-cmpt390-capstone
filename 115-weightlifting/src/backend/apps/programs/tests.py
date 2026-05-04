from datetime import date

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

from apps.athletes.models import ProgramCompletion
from .models import TrainingProgram
from .serializers import canonical_program_name

User = get_user_model()


class ProgramAssignRosterGateTests(TestCase):
    def setUp(self):
        self.coach_a = User.objects.create_user(username='ca_gate', password='pw', user_type='coach')
        self.coach_b = User.objects.create_user(username='cb_gate', password='pw', user_type='coach')
        self.athlete_owned = User.objects.create_user(username='ath_owned', password='pw', user_type='athlete')
        self.athlete_owned.primary_coach = self.coach_b
        self.athlete_owned.save(update_fields=['primary_coach'])
        self.athlete_a = User.objects.create_user(username='ath_a0', password='pw', user_type='athlete')
        self.athlete_a.primary_coach = self.coach_a
        self.athlete_a.save(update_fields=['primary_coach'])
        self.program = TrainingProgram.objects.create(
            coach=self.coach_a,
            athlete=self.athlete_a,
            name='Gate block',
            start_date=date(2026, 1, 1),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.coach_a)

    def test_assign_rejects_other_coach_athlete(self):
        url = reverse('program-assign', kwargs={'program_id': self.program.id})
        response = self.client.patch(url, {'athlete_id': self.athlete_owned.id}, format='json')
        self.assertEqual(response.status_code, 403)


class ProgramAssignPreservesHistoryTests(TestCase):
    """Reassigning a program to a new athlete must not wipe the prior athlete's logs."""

    def setUp(self):
        self.coach = User.objects.create_user(
            username='coach1', password='pw', user_type='coach'
        )
        self.athlete_a = User.objects.create_user(
            username='athlete_a', password='pw', user_type='athlete'
        )
        self.athlete_b = User.objects.create_user(
            username='athlete_b', password='pw', user_type='athlete'
        )
        self.program = TrainingProgram.objects.create(
            coach=self.coach,
            athlete=self.athlete_a,
            name='Block 1',
            start_date=date(2026, 1, 1),
        )
        ProgramCompletion.objects.create(
            program=self.program,
            athlete=self.athlete_a,
            completion_data={'sessions': [{'day': 'Monday', 'done': True}]},
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.coach)

    def test_reassignment_preserves_prior_athletes_completion(self):
        url = reverse('program-assign', kwargs={'program_id': self.program.id})
        response = self.client.patch(url, {'athlete_id': self.athlete_b.id}, format='json')
        self.assertEqual(response.status_code, 200)

        self.program.refresh_from_db()
        self.assertEqual(self.program.athlete_id, self.athlete_b.id)

        prior_records = ProgramCompletion.objects.filter(
            program=self.program, athlete=self.athlete_a
        )
        self.assertEqual(prior_records.count(), 1, 'prior athletes history was destroyed')
        self.assertEqual(
            prior_records.first().completion_data['sessions'][0]['done'], True
        )

    def test_reassignment_allows_new_athlete_to_log_independently(self):
        url = reverse('program-assign', kwargs={'program_id': self.program.id})
        self.client.patch(url, {'athlete_id': self.athlete_b.id}, format='json')

        new_record = ProgramCompletion.objects.create(
            program=self.program,
            athlete=self.athlete_b,
            completion_data={'sessions': []},
        )
        self.assertEqual(
            ProgramCompletion.objects.filter(program=self.program).count(),
            2,
            'new athletes record should coexist with prior athletes history',
        )


class ProgramsListNPlusOneTests(TestCase):
    """Listing N programs must not issue O(N) SELECTs for completion records."""

    def setUp(self):
        self.coach = User.objects.create_user(
            username='np1_coach', password='pw', user_type='coach'
        )
        self.athletes = [
            User.objects.create_user(
                username=f'np1_athlete_{i}', password='pw', user_type='athlete'
            )
            for i in range(8)
        ]
        for i, athlete in enumerate(self.athletes):
            program = TrainingProgram.objects.create(
                coach=self.coach, athlete=athlete,
                name=f'Week {i}', start_date=date(2026, 1, 1),
            )
            ProgramCompletion.objects.create(
                program=program, athlete=athlete,
                completion_data={'entries': {'0': {'0': {'completed': True}}}},
            )
        self.client = APIClient()
        self.client.force_authenticate(user=self.coach)

    def test_programs_list_issues_constant_completion_queries(self):
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(reverse('program-list-create'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 8)
        self.assertTrue(
            all('completion_data' in item for item in response.data),
            'programs list response is missing completion_data',
        )
        queries_touching_completion = [
            q for q in ctx.captured_queries if 'programcompletion' in q['sql'].lower()
        ]
        self.assertLessEqual(
            len(queries_touching_completion),
            1,
            f'expected <=1 completion query via prefetch, got {len(queries_touching_completion)}',
        )


class ProgramDataDayIdTests(TestCase):
    """normalize_program_data preserves stable day ids so completion records
    survive day reorder/rename on the coach side."""

    def setUp(self):
        self.coach = User.objects.create_user(
            username='didcoach', password='pw', user_type='coach'
        )
        self.athlete = User.objects.create_user(
            username='didathlete', password='pw', user_type='athlete'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.coach)

    def test_day_id_round_trips_on_create(self):
        program_data = {
            'week_start_date': '2026-04-21',
            'days': [
                {'id': 'dabc123', 'day': 'Monday', 'exercises': []},
                {'id': 'dxyz789', 'day': 'Tuesday', 'exercises': []},
            ],
        }
        response = self.client.post(
            reverse('program-list-create'),
            {
                'name': 'Block 1',
                'description': '',
                'athlete_id': self.athlete.id,
                'start_date': '2026-04-21',
                'end_date': None,
                'program_data': program_data,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.content)
        days = response.data['program_data']['days']
        self.assertEqual([d['id'] for d in days], ['dabc123', 'dxyz789'])

    def test_intensity_mode_round_trips_on_program_data(self):
        """Coach preference for % 1RM / RPE / Weight survives save + reload."""
        program_data = {
            'week_start_date': '2026-04-21',
            'intensity_mode': 'rpe',
            'days': [{'id': 'd0', 'day': 'Monday', 'exercises': []}],
        }
        response = self.client.post(
            reverse('program-list-create'),
            {
                'name': 'RPE block',
                'description': '',
                'athlete_id': self.athlete.id,
                'start_date': '2026-04-21',
                'end_date': None,
                'program_data': program_data,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data['program_data'].get('intensity_mode'), 'rpe')

    def test_invalid_intensity_mode_is_dropped(self):
        program_data = {
            'week_start_date': '2026-04-21',
            'intensity_mode': 'not-a-real-mode',
            'days': [{'id': 'd0', 'day': 'Monday', 'exercises': []}],
        }
        response = self.client.post(
            reverse('program-list-create'),
            {
                'name': 'Garbage mode block',
                'description': '',
                'athlete_id': self.athlete.id,
                'start_date': '2026-04-21',
                'end_date': None,
                'program_data': program_data,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertNotIn('intensity_mode', response.data['program_data'])

    def test_backfills_deterministic_id_for_days_without_one(self):
        program_data = {
            'week_start_date': '2026-04-21',
            'days': [
                {'day': 'Monday', 'exercises': []},
                {'day': 'Tuesday', 'exercises': []},
            ],
        }
        response = self.client.post(
            reverse('program-list-create'),
            {
                'name': 'Legacy block',
                'description': '',
                'athlete_id': self.athlete.id,
                'start_date': '2026-04-21',
                'end_date': None,
                'program_data': program_data,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.content)
        days = response.data['program_data']['days']
        self.assertEqual([d['id'] for d in days], ['d0', 'd1'])


class ProgramNameMarkupRejectedTests(TestCase):
    """Program name/description must stay plain text at the API boundary."""

    def setUp(self):
        self.coach = User.objects.create_user(
            username='xss_coach', password='pw', user_type='coach'
        )
        self.athlete = User.objects.create_user(
            username='xss_athlete', password='pw', user_type='athlete'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.coach)

    def _minimal_create_body(self, **overrides):
        base = {
            'name': 'Clean block',
            'description': '',
            'athlete_id': self.athlete.id,
            'start_date': '2026-04-21',
            'end_date': None,
            'program_data': {
                'week_start_date': '2026-04-21',
                'days': [{'id': 'd0', 'day': 'Monday', 'exercises': []}],
            },
        }
        base.update(overrides)
        return base

    def test_create_rejects_angle_brackets_in_name(self):
        response = self.client.post(
            reverse('program-list-create'),
            self._minimal_create_body(name="<script>alert(1)</script>"),
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_create_rejects_angle_brackets_in_description(self):
        response = self.client.post(
            reverse('program-list-create'),
            self._minimal_create_body(description='<img onerror=1>'),
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_patch_rejects_markup_in_name(self):
        program = TrainingProgram.objects.create(
            coach=self.coach,
            athlete=self.athlete,
            name='Legit',
            start_date=date(2026, 1, 1),
        )
        response = self.client.patch(
            reverse('program-detail', kwargs={'program_id': program.id}),
            {'name': '</style><script>1</script>'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)


class PurgeMarkupProgramNamesCommandTests(TestCase):
    """Management command removes legacy probe rows that bypassed validation."""

    def setUp(self):
        self.coach = User.objects.create_user(
            username='purge_coach', password='pw', user_type='coach'
        )
        self.athlete = User.objects.create_user(
            username='purge_athlete', password='pw', user_type='athlete'
        )

    def test_purge_apply_deletes_only_markup_rows(self):
        bad = TrainingProgram.objects.create(
            coach=self.coach,
            athlete=self.athlete,
            name="<script>x</script>",
            start_date=date(2026, 1, 1),
        )
        good = TrainingProgram.objects.create(
            coach=self.coach,
            athlete=self.athlete,
            name='Clean block',
            start_date=date(2026, 2, 1),
        )
        call_command('purge_markup_program_names', '--apply', verbosity=0)
        self.assertFalse(TrainingProgram.objects.filter(pk=bad.pk).exists())
        self.assertTrue(TrainingProgram.objects.filter(pk=good.pk).exists())


class ProgramNormalizationTests(TestCase):
    def setUp(self):
        self.coach = User.objects.create_user(username='norm_coach', password='pw', user_type='coach')
        self.athlete = User.objects.create_user(username='norm_athlete', password='pw', user_type='athlete')
        self.client = APIClient()
        self.client.force_authenticate(user=self.coach)

    def test_create_sets_normalized_name_and_style_tags(self):
        payload = {
            'name': ' Peak / Strength Block  ',
            'description': '',
            'athlete_id': self.athlete.id,
            'start_date': '2026-04-21',
            'end_date': '2026-06-21',
            'program_data': {
                'week_start_date': '2026-04-21',
                'intensity_mode': 'percent_1rm',
                'days': [
                    {'id': 'd0', 'day': 'Monday', 'exercises': [{'name': 'Snatch', 'sets': '5', 'reps': '2', 'percent_1rm': '85%'}]},
                ],
            },
        }
        r = self.client.post(reverse('program-list-create'), payload, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        program = TrainingProgram.objects.get(pk=r.data['id'])
        self.assertEqual(program.normalized_name, canonical_program_name(payload['name']))
        self.assertIn('style:olympic', program.style_tags)
        self.assertIn('intensity_mode:percent_1rm', program.style_tags)

    def test_update_recomputes_normalized_name(self):
        program = TrainingProgram.objects.create(
            coach=self.coach,
            athlete=self.athlete,
            name='Old',
            normalized_name='old',
            style_tags=[],
            start_date=date(2026, 1, 1),
        )
        r = self.client.patch(
            reverse('program-detail', kwargs={'program_id': program.id}),
            {'name': 'New Name!!!'},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        program.refresh_from_db()
        self.assertEqual(program.normalized_name, 'new name')


class BackfillProgramNormalizationCommandTests(TestCase):
    def setUp(self):
        coach = User.objects.create_user(username='bf_coach', password='pw', user_type='coach')
        athlete = User.objects.create_user(username='bf_ath', password='pw', user_type='athlete')
        self.program = TrainingProgram.objects.create(
            coach=coach,
            athlete=athlete,
            name='  Taper+Peak ',
            normalized_name='',
            style_tags=[],
            start_date=date(2026, 1, 1),
        )

    def test_backfill_apply_populates_new_fields(self):
        call_command('backfill_program_normalization', '--apply', verbosity=0)
        self.program.refresh_from_db()
        self.assertEqual(self.program.normalized_name, 'taper peak')


class SettingsHardeningTests(TestCase):
    """Prod boot should refuse insecure SECRET_KEY defaults."""

    def test_debug_parsing_case_insensitive(self):
        import importlib
        import os

        original_debug = os.environ.get('DEBUG')
        original_key = os.environ.get('SECRET_KEY')
        try:
            os.environ['DEBUG'] = 'TRUE'
            os.environ['SECRET_KEY'] = 'test-ok-key'
            from config import settings as s
            importlib.reload(s)
            self.assertTrue(s.DEBUG)

            os.environ['DEBUG'] = 'false'
            importlib.reload(s)
            self.assertFalse(s.DEBUG)
        finally:
            if original_debug is None:
                os.environ.pop('DEBUG', None)
            else:
                os.environ['DEBUG'] = original_debug
            if original_key is None:
                os.environ.pop('SECRET_KEY', None)
            else:
                os.environ['SECRET_KEY'] = original_key
            from config import settings as s
            importlib.reload(s)

    def test_insecure_key_refused_when_debug_false(self):
        import importlib
        import os

        original_debug = os.environ.get('DEBUG')
        original_key = os.environ.get('SECRET_KEY')
        try:
            os.environ['DEBUG'] = 'False'
            os.environ['SECRET_KEY'] = 'django-insecure-change-this-in-production'
            with self.assertRaises(RuntimeError):
                from config import settings as s
                importlib.reload(s)
        finally:
            if original_debug is None:
                os.environ.pop('DEBUG', None)
            else:
                os.environ['DEBUG'] = original_debug
            if original_key is None:
                os.environ.pop('SECRET_KEY', None)
            else:
                os.environ['SECRET_KEY'] = original_key
            from config import settings as s
            importlib.reload(s)
