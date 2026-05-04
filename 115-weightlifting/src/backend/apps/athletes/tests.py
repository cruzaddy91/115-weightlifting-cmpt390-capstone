from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.athletes.models import PersonalRecord, ProgramCompletion, WorkoutLog
from apps.programs.models import TrainingProgram

User = get_user_model()


class ProgramCompletionGetIsReadOnlyTests(TestCase):
    """GET must not upsert rows; only PATCH should."""

    def setUp(self):
        self.coach = User.objects.create_user(
            username='c_ro', password='longenoughpw1', user_type='coach'
        )
        self.athlete = User.objects.create_user(
            username='a_ro', password='longenoughpw1', user_type='athlete'
        )
        self.program = TrainingProgram.objects.create(
            coach=self.coach, athlete=self.athlete,
            name='RO Block', start_date=date(2026, 1, 1),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.athlete)
        self.url = reverse('program-completion-detail', kwargs={'program_id': self.program.id})

    def test_get_without_existing_record_returns_404_and_does_not_create(self):
        self.assertEqual(
            ProgramCompletion.objects.filter(program=self.program).count(), 0
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            ProgramCompletion.objects.filter(program=self.program).count(),
            0,
            'GET silently created a ProgramCompletion row',
        )

    def test_patch_upserts_and_get_then_returns_200(self):
        patch_response = self.client.patch(
            self.url,
            {'completion_data': {'entries': {'0': {'0': {'completed': True}}}}},
            format='json',
        )
        self.assertEqual(patch_response.status_code, 200)

        get_response = self.client.get(self.url)
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(
            get_response.json()['completion_data']['entries']['0']['0']['completed'],
            True,
        )
        self.assertEqual(
            ProgramCompletion.objects.filter(program=self.program).count(), 1
        )

    def test_repeated_gets_do_not_mutate_row_count(self):
        self.client.patch(
            self.url,
            {'completion_data': {'entries': {}}},
            format='json',
        )
        for _ in range(5):
            self.client.get(self.url)
        self.assertEqual(
            ProgramCompletion.objects.filter(program=self.program).count(), 1
        )


class PersonalRecordValidationTests(TestCase):
    def setUp(self):
        self.athlete = User.objects.create_user(
            username='pr_athlete', password='longenoughpw1', user_type='athlete'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.athlete)
        self.url = reverse('personal-record-list-create')

    def _payload(self, **overrides):
        base = {'lift_type': 'snatch', 'weight': '120.0', 'date': str(date.today())}
        base.update(overrides)
        return base

    def test_valid_pr_accepted(self):
        response = self.client.post(self.url, self._payload(), format='json')
        self.assertEqual(response.status_code, 201)

    def test_future_date_rejected(self):
        future = (date.today() + timedelta(days=1)).isoformat()
        response = self.client.post(self.url, self._payload(date=future), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('date', response.json())
        self.assertEqual(PersonalRecord.objects.count(), 0)

    def test_zero_weight_rejected(self):
        response = self.client.post(self.url, self._payload(weight='0'), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('weight', response.json())

    def test_absurd_weight_rejected(self):
        response = self.client.post(self.url, self._payload(weight='999'), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('weight', response.json())
        self.assertEqual(PersonalRecord.objects.count(), 0)

    def test_ancient_date_rejected(self):
        response = self.client.post(
            self.url, self._payload(date='1999-12-31'), format='json'
        )
        self.assertEqual(response.status_code, 400)


class WorkoutLogValidationTests(TestCase):
    def setUp(self):
        self.athlete = User.objects.create_user(
            username='wl_athlete', password='longenoughpw1', user_type='athlete'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.athlete)
        self.url = reverse('workout-log-list-create')

    def test_future_dated_workout_rejected(self):
        future = (date.today() + timedelta(days=2)).isoformat()
        response = self.client.post(
            self.url, {'date': future, 'notes': 'bad date'}, format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(WorkoutLog.objects.count(), 0)


class CrossTenantAuthorizationTests(TestCase):
    """Every boundary the authz-probe tool exercises, pinned as a unit test.

    The probe runs against a live server; these tests keep the same
    invariants locked in CI so a regression on any of them fails the
    backend smoke rather than waiting for a manual probe run.
    """

    @classmethod
    def setUpTestData(cls):
        cls.coach_a = User.objects.create_user(
            username='coach_a', password='longenoughpw1', user_type='coach',
        )
        cls.coach_b = User.objects.create_user(
            username='coach_b', password='longenoughpw1', user_type='coach',
        )
        cls.athlete_x = User.objects.create_user(
            username='athlete_x', password='longenoughpw1', user_type='athlete',
        )
        cls.athlete_y = User.objects.create_user(
            username='athlete_y', password='longenoughpw1', user_type='athlete',
        )
        # coach_a coaches athlete_x via at least one program; coach_b has none.
        cls.program_ax = TrainingProgram.objects.create(
            coach=cls.coach_a, athlete=cls.athlete_x,
            name='Block AX', start_date=date(2026, 1, 1),
        )
        # Seed one workout log + one PR for athlete_x so GETs have content.
        WorkoutLog.objects.create(athlete=cls.athlete_x, date=date(2026, 4, 1), notes='')
        PersonalRecord.objects.create(
            athlete=cls.athlete_x, lift_type='snatch', weight=170, date=date(2026, 4, 1),
        )

    def _as(self, user):
        c = APIClient()
        c.force_authenticate(user=user)
        return c

    # -- Anonymous access ---------------------------------------------------

    def test_unauthenticated_requests_are_rejected(self):
        anon = APIClient()
        for path in [
            '/api/programs/',
            '/api/athletes/prs/',
            '/api/athletes/workouts/',
            f'/api/athletes/program-completion/{self.program_ax.id}/',
            '/api/auth/athletes/?scope=mine',
        ]:
            self.assertEqual(anon.get(path).status_code, 401, msg=path)

    # -- Cross-coach boundary ----------------------------------------------

    def test_coach_b_cannot_read_athlete_x_workouts(self):
        resp = self._as(self.coach_b).get(f'/api/athletes/workouts/?athlete_id={self.athlete_x.id}')
        self.assertEqual(resp.status_code, 403)

    def test_coach_b_cannot_read_athlete_x_prs(self):
        resp = self._as(self.coach_b).get(f'/api/athletes/prs/?athlete_id={self.athlete_x.id}')
        self.assertEqual(resp.status_code, 403)

    def test_coach_b_cannot_read_program_completion(self):
        resp = self._as(self.coach_b).get(f'/api/athletes/program-completion/{self.program_ax.id}/')
        self.assertEqual(resp.status_code, 403)

    def test_coach_b_cannot_patch_coach_a_program(self):
        resp = self._as(self.coach_b).patch(
            f'/api/programs/{self.program_ax.id}/',
            {'name': 'hijacked'}, format='json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_coach_b_cannot_reassign_coach_a_program(self):
        resp = self._as(self.coach_b).patch(
            f'/api/programs/{self.program_ax.id}/assign/',
            {'athlete_id': self.athlete_y.id}, format='json',
        )
        self.assertEqual(resp.status_code, 404)

    # -- Cross-athlete boundary --------------------------------------------

    def test_athlete_y_cannot_read_athlete_x_completion(self):
        resp = self._as(self.athlete_y).get(f'/api/athletes/program-completion/{self.program_ax.id}/')
        self.assertEqual(resp.status_code, 403)

    def test_athlete_y_cannot_patch_athlete_x_completion(self):
        resp = self._as(self.athlete_y).patch(
            f'/api/athletes/program-completion/{self.program_ax.id}/',
            {'completion_data': {'entries': {'d0': {'0': {'completed': True}}}}},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_athlete_y_get_prs_does_not_leak_other_athletes_data(self):
        # The ?athlete_id= param is a coach affordance; if an athlete sends it,
        # the endpoint must still scope to the requester only.
        resp = self._as(self.athlete_y).get(f'/api/athletes/prs/?athlete_id={self.athlete_x.id}')
        self.assertEqual(resp.status_code, 200)
        for pr in resp.json():
            self.assertEqual(pr['athlete'], self.athlete_y.id)

    # -- Coach input validation --------------------------------------------

    def test_coach_missing_athlete_id_rejected(self):
        resp = self._as(self.coach_a).get('/api/athletes/workouts/')
        self.assertEqual(resp.status_code, 400)
        resp = self._as(self.coach_a).get('/api/athletes/prs/')
        self.assertEqual(resp.status_code, 400)

    def test_coach_malformed_athlete_id_rejected(self):
        resp = self._as(self.coach_a).get('/api/athletes/workouts/?athlete_id=notanumber')
        self.assertEqual(resp.status_code, 400)

    # -- Coach-a happy path (sanity check, not a boundary) -----------------

    def test_coach_a_can_read_their_own_athletes_data(self):
        c = self._as(self.coach_a)
        self.assertEqual(c.get(f'/api/athletes/workouts/?athlete_id={self.athlete_x.id}').status_code, 200)
        self.assertEqual(c.get(f'/api/athletes/prs/?athlete_id={self.athlete_x.id}').status_code, 200)
        self.assertEqual(c.get(f'/api/athletes/program-completion/{self.program_ax.id}/').status_code, 404)  # no completion yet
        # After the athlete logs one entry, the coach's GET succeeds.
        self._as(self.athlete_x).patch(
            f'/api/athletes/program-completion/{self.program_ax.id}/',
            {'completion_data': {'entries': {'d0': {'0': {'completed': True}}}}},
            format='json',
        )
        self.assertEqual(c.get(f'/api/athletes/program-completion/{self.program_ax.id}/').status_code, 200)

    # -- UAT #2: Coach demoted mid-session ---------------------------------

    def test_demoted_coach_is_immediately_denied_coach_endpoints(self):
        """Flipping user_type -> 'athlete' must take effect on the very next
        request, without needing to invalidate the access token. The backend
        reads user_type off request.user each call; this test guards against
        any future caching that would let a demoted coach keep reading data.
        """
        c = self._as(self.coach_a)
        # Happy path first: coach can view their athlete's data.
        self.assertEqual(c.get(f'/api/athletes/prs/?athlete_id={self.athlete_x.id}').status_code, 200)
        # Demotion: flip user_type in the DB.
        self.coach_a.user_type = 'athlete'
        self.coach_a.save(update_fields=['user_type'])
        # Same session, same client: coach endpoints should now 403 / 400.
        # prs: athletes do not send athlete_id (endpoint treats request as
        # athlete-self-scoped) -- 200 is allowed because the response is
        # scoped to the demoted user, with zero records leaked.
        resp = c.get(f'/api/athletes/prs/?athlete_id={self.athlete_x.id}')
        self.assertIn(resp.status_code, (200, 403))
        if resp.status_code == 200:
            for pr in resp.json():
                self.assertEqual(pr['athlete'], self.coach_a.id,
                                 'demoted coach leaked another user\'s PR')
        # Program edit: coach-only path, must now be denied.
        resp = c.patch(f'/api/programs/{self.program_ax.id}/', {'name': 'x'}, format='json')
        self.assertEqual(resp.status_code, 403)
        # Program create: also denied.
        resp = c.post('/api/programs/', {
            'name': 'new', 'athlete_id': self.athlete_x.id,
            'start_date': '2026-04-01', 'program_data': {},
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    # -- UAT #5: Past-athlete retention ------------------------------------

    def test_coach_loses_access_after_reassigning_away_all_programs(self):
        """Data is scoped to *current* coaching relationship. A coach who
        reassigns their last program for an athlete must no longer be able
        to read that athlete's workout logs / PRs via the athlete_id scope.
        """
        c = self._as(self.coach_a)
        # With the program in place, access is granted.
        self.assertEqual(c.get(f'/api/athletes/prs/?athlete_id={self.athlete_x.id}').status_code, 200)
        # Reassign the program to athlete_y so coach_a no longer coaches x.
        self.program_ax.athlete = self.athlete_y
        self.program_ax.save(update_fields=['athlete'])
        # Access to x's data is now revoked.
        self.assertEqual(c.get(f'/api/athletes/prs/?athlete_id={self.athlete_x.id}').status_code, 403)
        self.assertEqual(c.get(f'/api/athletes/workouts/?athlete_id={self.athlete_x.id}').status_code, 403)
        # But access to y's data -- the athlete now on the coach's roster --
        # must now be granted.
        self.assertEqual(c.get(f'/api/athletes/prs/?athlete_id={self.athlete_y.id}').status_code, 200)

    # -- UAT #9: Reassign mid-save race ------------------------------------

    def test_reassign_then_athlete_patch_returns_404_not_silent_success(self):
        """If the coach reassigns a program away from an athlete while that
        athlete has a PATCH in flight, the backend must reject with 404 --
        never silently write to the new athlete's completion row.
        """
        # Coach reassigns the program from X to Y.
        self.program_ax.athlete = self.athlete_y
        self.program_ax.save(update_fields=['athlete'])
        # X's late PATCH must be refused.
        resp = self._as(self.athlete_x).patch(
            f'/api/athletes/program-completion/{self.program_ax.id}/',
            {'completion_data': {'entries': {'d0': {'0': {'completed': True, 'result': 'racegap'}}}}},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)
        # And athlete_y (the new owner) gets a clean slate -- no leaked row.
        completion_rows = ProgramCompletion.objects.filter(program=self.program_ax)
        for row in completion_rows:
            self.assertNotIn('racegap', str(row.completion_data))


class AccountDeletionTests(TestCase):
    """Deleting your own account: password-confirmed; coach-with-programs blocked."""

    def setUp(self):
        self.athlete = User.objects.create_user(
            username='del_athlete', password='longenoughpw1', user_type='athlete',
        )
        # One PR + one workout log so we can confirm cascade.
        PersonalRecord.objects.create(
            athlete=self.athlete, lift_type='snatch', weight=120, date=date(2026, 4, 1),
        )
        WorkoutLog.objects.create(athlete=self.athlete, date=date(2026, 4, 1), notes='')
        self.coach_empty = User.objects.create_user(
            username='del_coach_empty', password='longenoughpw1', user_type='coach',
        )
        self.coach_full = User.objects.create_user(
            username='del_coach_full', password='longenoughpw1', user_type='coach',
        )
        TrainingProgram.objects.create(
            coach=self.coach_full, athlete=self.athlete,
            name='held block', start_date=date(2026, 1, 1),
        )

    def _as(self, user):
        c = APIClient()
        c.force_authenticate(user=user)
        return c

    def test_delete_without_password_is_rejected(self):
        resp = self._as(self.athlete).delete('/api/auth/me/')
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(User.objects.filter(id=self.athlete.id).exists())

    def test_delete_with_wrong_password_is_rejected(self):
        resp = self._as(self.athlete).delete('/api/auth/me/', {'password': 'wrong'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(User.objects.filter(id=self.athlete.id).exists())

    def test_athlete_delete_cascades_prs_and_logs(self):
        athlete_id = self.athlete.id
        resp = self._as(self.athlete).delete(
            '/api/auth/me/', {'password': 'longenoughpw1'}, format='json',
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(User.objects.filter(id=athlete_id).exists())
        self.assertEqual(PersonalRecord.objects.filter(athlete_id=athlete_id).count(), 0)
        self.assertEqual(WorkoutLog.objects.filter(athlete_id=athlete_id).count(), 0)
        # Programs assigned to the athlete are also cascade-deleted.
        self.assertEqual(TrainingProgram.objects.filter(athlete_id=athlete_id).count(), 0)
        # The coach who had a program for this athlete still exists.
        self.assertTrue(User.objects.filter(id=self.coach_full.id).exists())

    def test_coach_with_active_programs_cannot_delete(self):
        resp = self._as(self.coach_full).delete(
            '/api/auth/me/', {'password': 'longenoughpw1'}, format='json',
        )
        self.assertEqual(resp.status_code, 409)
        self.assertTrue(User.objects.filter(id=self.coach_full.id).exists())

    def test_coach_without_programs_can_delete(self):
        resp = self._as(self.coach_empty).delete(
            '/api/auth/me/', {'password': 'longenoughpw1'}, format='json',
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(User.objects.filter(id=self.coach_empty.id).exists())


class LongHistorySeedTests(TestCase):
    """Bulk long-range demo PR/workout synthesis stays bounded and importable."""

    def setUp(self):
        # Username must match ATHLETE_PROFILES in long_history_seed for the command path.
        self.athlete = User.objects.create_user(
            username='arya_stark', password='longenoughpw1', user_type='athlete',
        )

    def test_build_pr_and_workout_rows_reasonable_volume(self):
        import random

        from apps.athletes.long_history_seed import ATHLETE_PROFILES, build_pr_and_workout_rows

        rng = random.Random(42)
        end = date(2026, 6, 1)
        start = end - timedelta(days=365)
        profile = ATHLETE_PROFILES['arya_stark']
        prs, logs = build_pr_and_workout_rows(
            athlete=self.athlete,
            profile=profile,
            history_start=start,
            history_end=end,
            rng=rng,
        )
        self.assertGreaterEqual(len(prs), 30)
        self.assertLessEqual(len(prs), 200)
        self.assertGreater(len(logs), 40)

    def test_seed_longterm_command_runs_one_year(self):
        from django.core.management import call_command

        call_command('seed_longterm_got_history', '--replace', '--years', '1', '--athletes', 'arya_stark')
        self.assertGreater(PersonalRecord.objects.filter(athlete=self.athlete).count(), 20)
        self.assertGreater(WorkoutLog.objects.filter(athlete=self.athlete).count(), 30)
