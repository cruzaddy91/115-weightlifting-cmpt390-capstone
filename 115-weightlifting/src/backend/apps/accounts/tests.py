import os
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.weight_class import competitive_weight_class_label
from apps.athletes.models import PersonalRecord, ProgramCompletion
from apps.programs.models import TrainingProgram

User = get_user_model()


class CoachRegistrationGateTests(TestCase):
    url = reverse('register')

    def setUp(self):
        self.client = APIClient()

    def test_coach_signup_rejected_without_env_configured(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('COACH_SIGNUP_CODE', None)
            response = self.client.post(
                self.url,
                {'username': 'u1', 'password': 'longenoughpw1', 'user_type': 'coach'},
                format='json',
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn('user_type', response.json())

    def test_coach_signup_rejected_with_wrong_code(self):
        with mock.patch.dict(os.environ, {'COACH_SIGNUP_CODE': 'secret-2026'}):
            response = self.client.post(
                self.url,
                {
                    'username': 'u2',
                    'password': 'longenoughpw1',
                    'user_type': 'coach',
                    'coach_signup_code': 'nope',
                },
                format='json',
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn('coach_signup_code', response.json())
        self.assertFalse(User.objects.filter(username='u2').exists())

    def test_coach_signup_succeeds_with_correct_code(self):
        with mock.patch.dict(os.environ, {'COACH_SIGNUP_CODE': 'secret-2026'}):
            response = self.client.post(
                self.url,
                {
                    'username': 'u3',
                    'password': 'longenoughpw1',
                    'user_type': 'coach',
                    'coach_signup_code': 'secret-2026',
                },
                format='json',
            )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username='u3', user_type='coach').exists())

    def test_athlete_signup_never_requires_code(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('COACH_SIGNUP_CODE', None)
            response = self.client.post(
                self.url,
                {'username': 'a1', 'password': 'longenoughpw1', 'user_type': 'athlete'},
                format='json',
            )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username='a1', user_type='athlete').exists())

    def test_head_coach_signup_rejected(self):
        response = self.client.post(
            self.url,
            {'username': 'hc1', 'password': 'longenoughpw1', 'user_type': 'head_coach'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('user_type', response.json())
        self.assertFalse(User.objects.filter(username='hc1').exists())


class RefreshTokenBlacklistTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='blacklist_user', password='longenoughpw1', user_type='athlete'
        )
        self.client = APIClient()

    def test_old_refresh_token_rejected_after_rotation(self):
        login = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'blacklist_user', 'password': 'longenoughpw1'},
            format='json',
        )
        self.assertEqual(login.status_code, 200)
        original_refresh = login.json()['refresh']

        first = self.client.post(
            reverse('token_refresh'), {'refresh': original_refresh}, format='json'
        )
        self.assertEqual(first.status_code, 200)

        replay = self.client.post(
            reverse('token_refresh'), {'refresh': original_refresh}, format='json'
        )
        self.assertEqual(
            replay.status_code,
            401,
            f'expected 401 on blacklisted refresh, got {replay.status_code}: {replay.content}',
        )


class LogoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='logout_user', password='longenoughpw1', user_type='athlete'
        )
        self.client = APIClient()
        tokens = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'logout_user', 'password': 'longenoughpw1'},
            format='json',
        ).json()
        self.access = tokens['access']
        self.refresh = tokens['refresh']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')

    def test_logout_blacklists_refresh(self):
        response = self.client.post(reverse('logout'), {'refresh': self.refresh}, format='json')
        self.assertEqual(response.status_code, 205)

        replay = APIClient().post(
            reverse('token_refresh'), {'refresh': self.refresh}, format='json'
        )
        self.assertEqual(replay.status_code, 401)

    def test_logout_without_refresh_returns_400(self):
        self.client.cookies.clear()
        response = self.client.post(reverse('logout'), {}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_logout_with_garbage_refresh_returns_400(self):
        self.client.cookies.clear()
        response = self.client.post(reverse('logout'), {'refresh': 'not-a-jwt'}, format='json')
        self.assertEqual(response.status_code, 400)


class RefreshCookieTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='cookie_user', password='longenoughpw1', user_type='athlete'
        )
        self.client = APIClient()

    def test_login_sets_httponly_refresh_cookie(self):
        response = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'cookie_user', 'password': 'longenoughpw1'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        cookie = response.cookies.get('wl_refresh')
        self.assertIsNotNone(cookie, 'expected wl_refresh cookie on login')
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['path'], '/api/auth/')

    def test_refresh_endpoint_accepts_cookie_only(self):
        login = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'cookie_user', 'password': 'longenoughpw1'},
            format='json',
        )
        self.client.cookies['wl_refresh'] = login.cookies['wl_refresh'].value

        response = self.client.post(reverse('token_refresh'), {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIsNotNone(response.cookies.get('wl_refresh'))

    def test_logout_accepts_cookie_only_and_clears_it(self):
        login = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'cookie_user', 'password': 'longenoughpw1'},
            format='json',
        )
        cookie_value = login.cookies['wl_refresh'].value
        self.client.cookies['wl_refresh'] = cookie_value
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        response = self.client.post(reverse('logout'), {}, format='json')
        self.assertEqual(response.status_code, 205)
        cleared = response.cookies.get('wl_refresh')
        self.assertIsNotNone(cleared)
        self.assertEqual(cleared.value, '')


class AthleteListScopingTests(TestCase):
    def setUp(self):
        self.coach = User.objects.create_user(
            username='scope_coach', password='longenoughpw1', user_type='coach'
        )
        self.my_athlete = User.objects.create_user(
            username='my_athlete', password='longenoughpw1', user_type='athlete'
        )
        self.stranger = User.objects.create_user(
            username='stranger_athlete', password='longenoughpw1', user_type='athlete'
        )
        from datetime import date
        from apps.programs.models import TrainingProgram
        TrainingProgram.objects.create(
            coach=self.coach, athlete=self.my_athlete,
            name='scope block', start_date=date(2026, 1, 1),
        )
        self.my_athlete.primary_coach = self.coach
        self.my_athlete.save(update_fields=['primary_coach'])
        self.client = APIClient()
        self.client.force_authenticate(user=self.coach)

    def test_default_scope_mine_hides_unassigned_athletes(self):
        response = self.client.get(reverse('athlete-list'))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        usernames = {a['username'] for a in payload['results']}
        self.assertIn('my_athlete', usernames)
        self.assertNotIn('stranger_athlete', usernames)
        self.assertEqual(payload['scope'], 'mine')
        self.assertEqual(payload['page_size'], 50)

    def test_scope_all_forbidden_for_line_coach(self):
        response = self.client.get(reverse('athlete-list'), {'scope': 'all'})
        self.assertEqual(response.status_code, 403)

    def test_head_scope_all_is_org_pool_only(self):
        head = User.objects.create_user(
            username='head_list', password='longenoughpw1', user_type='head_coach',
        )
        line = User.objects.create_user(
            username='line_list', password='longenoughpw1', user_type='coach',
        )
        line.reports_to = head
        line.save(update_fields=['reports_to'])
        mine = User.objects.create_user(
            username='org_athlete', password='longenoughpw1', user_type='athlete',
        )
        mine.primary_coach = line
        mine.save(update_fields=['primary_coach'])
        stranger = User.objects.create_user(
            username='stranger_outside', password='longenoughpw1', user_type='athlete',
        )
        stranger.save()
        self.client.force_authenticate(user=head)
        r = self.client.get(reverse('athlete-list'), {'scope': 'all'})
        self.assertEqual(r.status_code, 200)
        names = {a['username'] for a in r.json()['results']}
        self.assertIn('org_athlete', names)
        self.assertNotIn('stranger_outside', names)

    def test_q_filter_narrows_results(self):
        response = self.client.get(reverse('athlete-list'), {'scope': 'mine', 'q': 'my_ath'})
        payload = response.json()
        self.assertEqual([a['username'] for a in payload['results']], ['my_athlete'])

    def test_athlete_cannot_list(self):
        self.client.force_authenticate(user=self.my_athlete)
        response = self.client.get(reverse('athlete-list'))
        self.assertEqual(response.status_code, 403)

    def test_athlete_list_includes_weight_class_fields(self):
        self.my_athlete.bodyweight_kg = Decimal('64.0')
        self.my_athlete.gender = 'F'
        self.my_athlete.save(update_fields=['bodyweight_kg', 'gender'])
        response = self.client.get(reverse('athlete-list'))
        self.assertEqual(response.status_code, 200)
        hit = next(a for a in response.json()['results'] if a['username'] == 'my_athlete')
        self.assertEqual(hit['bodyweight_kg'], 64.0)
        self.assertEqual(hit['gender'], 'F')
        self.assertEqual(hit['competitive_weight_class'], '71 kg')


class WeightClassLabelTests(TestCase):
    def test_men_superheavy(self):
        self.assertEqual(competitive_weight_class_label(Decimal('120'), 'M'), '+109 kg')

    def test_women_mid(self):
        self.assertEqual(competitive_weight_class_label(59, 'F'), '59 kg')

    def test_missing_gender(self):
        self.assertIsNone(competitive_weight_class_label(80, None))


class AthleteProfilePatchTests(TestCase):
    def setUp(self):
        self.athlete = User.objects.create_user(
            username='patch_athlete', password='longenoughpw1', user_type='athlete',
        )
        self.coach = User.objects.create_user(
            username='patch_coach', password='longenoughpw1', user_type='coach',
        )
        self.client = APIClient()

    def test_patch_me_updates_bodyweight(self):
        login = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'patch_athlete', 'password': 'longenoughpw1'},
            format='json',
        )
        self.assertEqual(login.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")
        r = self.client.patch(
            reverse('current-user'),
            {'bodyweight_kg': '81.2', 'gender': 'M'},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertEqual(float(data['bodyweight_kg']), 81.2)
        self.assertEqual(data['gender'], 'M')
        self.assertEqual(data['competitive_weight_class'], '89 kg')

    def test_coach_patch_me_forbidden(self):
        login = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'patch_coach', 'password': 'longenoughpw1'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")
        r = self.client.patch(reverse('current-user'), {'bodyweight_kg': '80'}, format='json')
        self.assertEqual(r.status_code, 403)


class HeadOrgSummaryTests(TestCase):
    def setUp(self):
        self.head = User.objects.create_user(
            username='head_org', password='longenoughpw1', user_type='head_coach',
        )
        self.line = User.objects.create_user(
            username='line_org', password='longenoughpw1', user_type='coach',
        )
        self.line.reports_to = self.head
        self.line.save(update_fields=['reports_to'])
        self.client = APIClient()

    def test_coach_forbidden(self):
        login = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'line_org', 'password': 'longenoughpw1'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")
        r = self.client.get(reverse('head-org-summary'))
        self.assertEqual(r.status_code, 403)

    def test_head_sees_staff_row(self):
        login = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'head_org', 'password': 'longenoughpw1'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")
        r = self.client.get(reverse('head-org-summary'))
        self.assertEqual(r.status_code, 200)
        coaches = r.json()['coaches']
        usernames = {c['username'] for c in coaches}
        self.assertIn('head_org', usernames)
        self.assertIn('line_org', usernames)

    def test_counts_use_primary_coach_roster(self):
        a_head = User.objects.create_user(
            username='ath_head', password='longenoughpw1', user_type='athlete',
        )
        a_head.primary_coach = self.head
        a_head.save(update_fields=['primary_coach'])
        a_line = User.objects.create_user(
            username='ath_line', password='longenoughpw1', user_type='athlete',
        )
        a_line.primary_coach = self.line
        a_line.save(update_fields=['primary_coach'])
        login = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'head_org', 'password': 'longenoughpw1'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")
        r = self.client.get(reverse('head-org-summary'))
        self.assertEqual(r.status_code, 200)
        by_user = {c['username']: c for c in r.json()['coaches']}
        self.assertEqual(by_user['head_org']['athlete_count'], 1)
        self.assertEqual(by_user['line_org']['athlete_count'], 1)


class HeadRosterAssignmentTests(TestCase):
    def setUp(self):
        self.head = User.objects.create_user(
            username='head_ra', password='longenoughpw1', user_type='head_coach',
        )
        self.line = User.objects.create_user(
            username='line_ra', password='longenoughpw1', user_type='coach',
        )
        self.line.reports_to = self.head
        self.line.save(update_fields=['reports_to'])
        self.ath = User.objects.create_user(
            username='ath_ra', password='longenoughpw1', user_type='athlete',
        )
        self.ath.primary_coach = self.line
        self.ath.save(update_fields=['primary_coach'])
        self.solo_coach = User.objects.create_user(
            username='solo_coach', password='longenoughpw1', user_type='coach',
        )
        self.client = APIClient()

    def _auth_head(self):
        t = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'head_ra', 'password': 'longenoughpw1'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {t.json()['access']}")

    def test_roster(self):
        self._auth_head()
        r = self.client.get(reverse('head-org-roster'))
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertEqual(len(j['staff']), 1)
        self.assertEqual(j['staff'][0]['username'], 'line_ra')
        self.assertEqual(len(j['athletes']), 1)

    def test_invite_staff_by_username(self):
        self._auth_head()
        r = self.client.post(reverse('head-staff-invite'), {'username': 'solo_coach'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.solo_coach.refresh_from_db()
        self.assertEqual(self.solo_coach.reports_to_id, self.head.id)

    def test_unlink_staff(self):
        from datetime import date

        from apps.programs.models import TrainingProgram

        prog = TrainingProgram.objects.create(
            coach=self.line,
            athlete=self.ath,
            name='unlink_prog',
            start_date=date(2026, 4, 1),
        )
        self._auth_head()
        r = self.client.patch(
            reverse('head-staff-link', kwargs={'user_id': self.line.id}),
            {'linked': False},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.line.refresh_from_db()
        self.assertIsNone(self.line.reports_to_id)
        self.ath.refresh_from_db()
        prog.refresh_from_db()
        self.assertEqual(self.ath.primary_coach_id, self.head.id)
        self.assertEqual(prog.coach_id, self.head.id)

    def test_link_staff_patch(self):
        self.line.reports_to = None
        self.line.save(update_fields=['reports_to'])
        self._auth_head()
        r = self.client.patch(
            reverse('head-staff-link', kwargs={'user_id': self.line.id}),
            {'linked': True},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.line.refresh_from_db()
        self.assertEqual(self.line.reports_to_id, self.head.id)

    def test_reassign_athlete_to_head(self):
        self._auth_head()
        r = self.client.patch(
            reverse('head-athlete-primary-coach', kwargs={'user_id': self.ath.id}),
            {'primary_coach_id': self.head.id},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.ath.refresh_from_db()
        self.assertEqual(self.ath.primary_coach_id, self.head.id)

    def test_reassign_moves_program_coach(self):
        from datetime import date

        from apps.programs.models import TrainingProgram

        prog = TrainingProgram.objects.create(
            coach=self.line,
            athlete=self.ath,
            name='handoff_prog',
            start_date=date(2026, 4, 1),
        )
        other = User.objects.create_user(
            username='line_b_ra', password='longenoughpw1', user_type='coach',
        )
        other.reports_to = self.head
        other.save(update_fields=['reports_to'])
        self._auth_head()
        r = self.client.patch(
            reverse('head-athlete-primary-coach', kwargs={'user_id': self.ath.id}),
            {'primary_coach_id': other.id},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        prog.refresh_from_db()
        self.ath.refresh_from_db()
        self.assertEqual(self.ath.primary_coach_id, other.id)
        self.assertEqual(prog.coach_id, other.id)

    def test_coach_forbidden_roster(self):
        t = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'line_ra', 'password': 'longenoughpw1'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {t.json()['access']}")
        r = self.client.get(reverse('head-org-roster'))
        self.assertEqual(r.status_code, 403)


class HeadAnalyticsEndpointTests(TestCase):
    def setUp(self):
        self.head = User.objects.create_user(username='head_ana', password='pw', user_type='head_coach')
        self.line = User.objects.create_user(username='line_ana', password='pw', user_type='coach')
        self.line.reports_to = self.head
        self.line.save(update_fields=['reports_to'])
        self.client = APIClient()

        # Create a cohort >= minimum sample size (3).
        for i in range(3):
            athlete = User.objects.create_user(
                username=f'ana_ath_{i}',
                password='pw',
                user_type='athlete',
                gender='F',
                bodyweight_kg=Decimal('58.0'),
            )
            athlete.primary_coach = self.line
            athlete.save(update_fields=['primary_coach'])
            program = TrainingProgram.objects.create(
                coach=self.line,
                athlete=athlete,
                name='Peak Strength',
                normalized_name='peak strength',
                style_tags=['style:strength', 'phase:peak'],
                start_date='2026-01-01',
                end_date='2026-02-01',
            )
            ProgramCompletion.objects.create(
                program=program,
                athlete=athlete,
                completion_data={'entries': {'d0': {'0': {'completed': True}, '1': {'completed': False}}}},
            )
            PersonalRecord.objects.create(athlete=athlete, lift_type='total', weight=Decimal('180.0'), date='2025-12-31')
            PersonalRecord.objects.create(athlete=athlete, lift_type='total', weight=Decimal('185.0'), date='2026-02-10')

    def _auth(self, username='head_ana'):
        t = self.client.post(
            reverse('token_obtain_pair'),
            {'username': username, 'password': 'pw'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {t.json()['access']}")

    def test_head_style_outcomes_returns_deidentified_aggregates(self):
        self._auth()
        r = self.client.get(reverse('head-program-style-outcomes'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('groups', r.json())
        self.assertNotIn('username', str(r.json()).lower())
        self.assertGreaterEqual(len(r.json()['groups']), 1)

    def test_head_name_outcomes_returns_grouped_rows(self):
        self._auth()
        r = self.client.get(reverse('head-program-name-outcomes'))
        self.assertEqual(r.status_code, 200)
        groups = r.json()['groups']
        self.assertTrue(any(g['normalized_name'] == 'peak strength' for g in groups))

    def test_head_recommendations_returns_rule_based_cards(self):
        self._auth()
        r = self.client.get(reverse('head-recommendations'))
        self.assertEqual(r.status_code, 200)
        recs = r.json()['recommendations']
        self.assertGreaterEqual(len(recs), 1)
        self.assertIn('recommended_style_tag', recs[0])

    def test_line_coach_forbidden_from_head_analytics(self):
        self._auth('line_ana')
        r = self.client.get(reverse('head-program-style-outcomes'))
        self.assertEqual(r.status_code, 403)
