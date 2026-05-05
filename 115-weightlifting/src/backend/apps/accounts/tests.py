import os
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.org_labels import DEMO_UNASSIGNED_ATHLETE_USERNAMES
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
                {
                    'username': '005_u1',
                    'email': 'u1@example.invalid',
                    'password': 'longenoughpw1',
                    'user_type': 'coach',
                },
                format='json',
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn('user_type', response.json())

    def test_coach_signup_rejected_with_wrong_code(self):
        with mock.patch.dict(os.environ, {'COACH_SIGNUP_CODE': 'secret-2026'}):
            response = self.client.post(
                self.url,
                {
                    'username': '006_u2',
                    'email': 'u2@example.invalid',
                    'password': 'longenoughpw1',
                    'user_type': 'coach',
                    'coach_signup_code': 'nope',
                },
                format='json',
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn('coach_signup_code', response.json())
        self.assertFalse(User.objects.filter(username='006_u2').exists())

    def test_coach_signup_succeeds_with_correct_code(self):
        with mock.patch.dict(os.environ, {'COACH_SIGNUP_CODE': 'secret-2026'}):
            response = self.client.post(
                self.url,
                {
                    'username': '005_u3',
                    'email': 'u3@example.invalid',
                    'password': 'longenoughpw1',
                    'user_type': 'coach',
                    'coach_signup_code': 'secret-2026',
                },
                format='json',
            )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username='005_u3', user_type='coach').exists())

    def test_athlete_signup_never_requires_code(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('COACH_SIGNUP_CODE', None)
            response = self.client.post(
                self.url,
                {
                    'username': 'a1',
                    'email': 'a1@example.invalid',
                    'password': 'longenoughpw1',
                    'user_type': 'athlete',
                },
                format='json',
            )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username='000_a1', user_type='athlete').exists())
        self.assertEqual(response.json()['username'], '000_a1')

    def test_athlete_signup_rejects_underscore_in_selected_username(self):
        response = self.client.post(
            self.url,
            {
                'username': 'bad_name',
                'email': 'badname@example.invalid',
                'password': 'longenoughpw1',
                'user_type': 'athlete',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('username', response.json())

    def test_athlete_signup_uses_next_numeric_prefix(self):
        User.objects.create_user(
            username='000_existing', password='longenoughpw1', user_type='athlete',
        )
        response = self.client.post(
            self.url,
            {
                'username': 'nextathlete',
                'email': 'nextathlete@example.invalid',
                'password': 'longenoughpw1',
                'user_type': 'athlete',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['username'], '005_nextathlete')

    def test_athlete_signup_skips_reserved_numeric_prefixes(self):
        for prefix in ('000', '005'):
            User.objects.create_user(
                username=f'{prefix}_existing', password='longenoughpw1', user_type='athlete',
            )
        response = self.client.post(
            self.url,
            {
                'username': 'reservedskip',
                'email': 'reservedskip@example.invalid',
                'password': 'longenoughpw1',
                'user_type': 'athlete',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['username'], '006_reservedskip')

    def test_athlete_signup_assigns_first_15_available_prefixes(self):
        for prefix in ('013', '034', '045', '088'):
            User.objects.create_user(
                username=f'{prefix}_coach', password='longenoughpw1', user_type='coach',
            )
        expected_prefixes = [
            '000', '005', '006', '007', '008',
            '009', '010', '011', '012', '014',
            '015', '016', '017', '018', '019',
        ]

        actual_usernames = []
        for idx in range(15):
            response = self.client.post(
                self.url,
                {
                    'username': f'batchathlete{idx + 1}',
                    'email': f'batchathlete{idx + 1}@example.invalid',
                    'password': 'longenoughpw1',
                    'user_type': 'athlete',
                },
                format='json',
            )
            self.assertEqual(response.status_code, 201)
            actual_usernames.append(response.json()['username'])

        self.assertEqual(
            actual_usernames,
            [f'{prefix}_batchathlete{idx + 1}' for idx, prefix in enumerate(expected_prefixes)],
        )

    def test_coach_signup_rejects_reserved_numeric_prefix(self):
        with mock.patch.dict(os.environ, {'COACH_SIGNUP_CODE': 'secret-2026'}):
            response = self.client.post(
                self.url,
                {
                    'username': '001_reservedcoach',
                    'email': 'reservedcoach@example.invalid',
                    'password': 'longenoughpw1',
                    'user_type': 'coach',
                    'coach_signup_code': 'secret-2026',
                },
                format='json',
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn('username', response.json())
        self.assertFalse(User.objects.filter(username='001_reservedcoach').exists())

    def test_coach_signup_rejects_out_of_pool_numeric_prefix(self):
        with mock.patch.dict(os.environ, {'COACH_SIGNUP_CODE': 'secret-2026'}):
            response = self.client.post(
                self.url,
                {
                    'username': '100_outofpoolcoach',
                    'email': 'outofpoolcoach@example.invalid',
                    'password': 'longenoughpw1',
                    'user_type': 'coach',
                    'coach_signup_code': 'secret-2026',
                },
                format='json',
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn('username', response.json())
        self.assertFalse(User.objects.filter(username='100_outofpoolcoach').exists())

    def test_coach_signup_rejects_prefix_already_used_by_athlete(self):
        User.objects.create_user(
            username='005_existingathlete', password='longenoughpw1', user_type='athlete',
        )
        with mock.patch.dict(os.environ, {'COACH_SIGNUP_CODE': 'secret-2026'}):
            response = self.client.post(
                self.url,
                {
                    'username': '005_newcoach',
                    'email': 'newcoach@example.invalid',
                    'password': 'longenoughpw1',
                    'user_type': 'coach',
                    'coach_signup_code': 'secret-2026',
                },
                format='json',
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn('username', response.json())
        self.assertFalse(User.objects.filter(username='005_newcoach').exists())

    def test_coach_signup_accepts_available_normal_member_prefix(self):
        with mock.patch.dict(os.environ, {'COACH_SIGNUP_CODE': 'secret-2026'}):
            response = self.client.post(
                self.url,
                {
                    'username': '005_newcoach',
                    'email': 'availablecoach@example.invalid',
                    'password': 'longenoughpw1',
                    'user_type': 'coach',
                    'coach_signup_code': 'secret-2026',
                },
                format='json',
            )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username='005_newcoach').exists())

    def test_head_coach_signup_rejected(self):
        response = self.client.post(
            self.url,
            {
                'username': 'hc1',
                'email': 'hc1@example.invalid',
                'password': 'longenoughpw1',
                'user_type': 'head_coach',
            },
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

    def test_head_scope_all_includes_all_active_athletes(self):
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
        outside_head = User.objects.create_user(
            username='outside_head', password='longenoughpw1', user_type='head_coach',
        )
        outside_athlete = User.objects.create_user(
            username='outside_athlete', password='longenoughpw1', user_type='athlete',
        )
        outside_athlete.primary_coach = outside_head
        outside_athlete.save(update_fields=['primary_coach'])
        self.client.force_authenticate(user=head)
        r = self.client.get(reverse('athlete-list'), {'scope': 'all'})
        self.assertEqual(r.status_code, 200)
        names = {a['username'] for a in r.json()['results']}
        self.assertIn('org_athlete', names)
        self.assertIn('stranger_outside', names)
        self.assertIn('outside_athlete', names)

    def test_head_scope_all_hides_inactive_archived_athletes(self):
        head = User.objects.create_user(
            username='head_archive_list', password='longenoughpw1', user_type='head_coach',
        )
        archived = User.objects.create_user(
            username='archived_athlete', password='longenoughpw1', user_type='athlete',
        )
        archived.is_active = False
        archived.save(update_fields=['is_active'])
        self.client.force_authenticate(user=head)
        r = self.client.get(reverse('athlete-list'), {'scope': 'all'})
        self.assertEqual(r.status_code, 200)
        names = {a['username'] for a in r.json()['results']}
        self.assertNotIn('archived_athlete', names)

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

    def test_master_head_summary_includes_all_active_head_and_line_coaches(self):
        master = User.objects.create_user(
            username='117_HeadcoachGM', password='longenoughpw1', user_type='head_coach',
        )
        agm = User.objects.create_user(
            username='001_Headcoachone', password='longenoughpw1', user_type='head_coach',
        )
        line_under_agm = User.objects.create_user(
            username='005_Lineagm', password='longenoughpw1', user_type='coach',
        )
        line_under_agm.reports_to = agm
        line_under_agm.save(update_fields=['reports_to'])
        line_under_gm = User.objects.create_user(
            username='006_Linegm', password='longenoughpw1', user_type='coach',
        )
        line_under_gm.reports_to = master
        line_under_gm.save(update_fields=['reports_to'])
        athlete = User.objects.create_user(
            username='007_Athleteagm', password='longenoughpw1', user_type='athlete',
        )
        athlete.primary_coach = line_under_agm
        athlete.save(update_fields=['primary_coach'])

        self.client.force_authenticate(user=master)
        r = self.client.get(reverse('head-org-summary'))
        self.assertEqual(r.status_code, 200)
        by_user = {row['username']: row for row in r.json()['coaches']}
        self.assertIn('117_HeadcoachGM', by_user)
        self.assertIn('001_Headcoachone', by_user)
        self.assertIn('005_Lineagm', by_user)
        self.assertIn('006_Linegm', by_user)
        self.assertEqual(by_user['005_Lineagm']['athlete_count'], 1)


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
        staff_names = {row['username'] for row in j['staff']}
        athlete_names = {row['username'] for row in j['athletes']}
        self.assertIn('line_ra', staff_names)
        self.assertIn('solo_coach', staff_names)
        self.assertIn('ath_ra', athlete_names)
        line_row = next(row for row in j['staff'] if row['username'] == 'line_ra')
        athlete_row = next(row for row in j['athletes'] if row['username'] == 'ath_ra')
        self.assertEqual(line_row['reports_to_username'], 'head_ra')
        self.assertEqual(athlete_row['primary_coach_username'], 'line_ra')
        self.assertIn('org_label', line_row)
        self.assertIn('org_color_key', athlete_row)

    def test_roster_includes_inherited_org_color_metadata(self):
        prefixed_head = User.objects.create_user(
            username='117_HeadcoachGM', password='longenoughpw1', user_type='head_coach',
        )
        unassigned_head = User.objects.create_user(
            username='118_Headcoachtwo', password='longenoughpw1', user_type='head_coach',
        )
        prefixed_line = User.objects.create_user(
            username='045_Coachone', password='longenoughpw1', user_type='coach',
        )
        prefixed_line.reports_to = prefixed_head
        prefixed_line.save(update_fields=['reports_to'])
        prefixed_athlete = User.objects.create_user(
            username='000_Athlete1', password='longenoughpw1', user_type='athlete',
        )
        prefixed_athlete.primary_coach = prefixed_line
        prefixed_athlete.save(update_fields=['primary_coach'])
        self.client.force_authenticate(user=prefixed_head)
        r = self.client.get(reverse('head-org-roster'))
        self.assertEqual(r.status_code, 200)
        j = r.json()
        head_row = next(row for row in j['head_coaches'] if row['username'] == '117_HeadcoachGM')
        unassigned_head_row = next(row for row in j['head_coaches'] if row['username'] == unassigned_head.username)
        line_row = next(row for row in j['staff'] if row['username'] == '045_Coachone')
        athlete_row = next(row for row in j['athletes'] if row['username'] == '000_Athlete1')
        for row in (head_row, line_row, athlete_row):
            self.assertEqual(row['org_prefix'], '117')
            self.assertEqual(row['org_label'], '117_MASTER_CHIEF')
            self.assertEqual(row['org_color_key'], 'sage-green')
        self.assertIsNone(unassigned_head_row['org_prefix'])
        self.assertEqual(unassigned_head_row['org_label'], 'XXX_UNASSIGNED')
        self.assertEqual(unassigned_head_row['org_color_key'], 'graphite')

    def test_roster_marks_demo_unassigned_athlete_pool_as_xxx_unassigned(self):
        prefixed_head = User.objects.create_user(
            username='117_HeadcoachGM', password='longenoughpw1', user_type='head_coach',
        )
        for username in DEMO_UNASSIGNED_ATHLETE_USERNAMES:
            User.objects.create_user(
                username=username, password='longenoughpw1', user_type='athlete',
            )
        self.client.force_authenticate(user=prefixed_head)
        r = self.client.get(reverse('head-org-roster'))
        self.assertEqual(r.status_code, 200)
        rows_by_username = {row['username']: row for row in r.json()['athletes']}

        for username in DEMO_UNASSIGNED_ATHLETE_USERNAMES:
            self.assertIn(username, rows_by_username)
            self.assertIsNone(rows_by_username[username]['primary_coach_id'])
            self.assertIsNone(rows_by_username[username]['org_prefix'])
            self.assertEqual(rows_by_username[username]['org_label'], 'XXX_UNASSIGNED')
            self.assertEqual(rows_by_username[username]['org_color_key'], 'graphite')

    def test_master_head_can_assign_standalone_head_to_agm_category(self):
        master = User.objects.create_user(
            username='117_HeadcoachGM', password='longenoughpw1', user_type='head_coach',
        )
        standalone = User.objects.create_user(
            username='118_Headcoachtwo', password='longenoughpw1', user_type='head_coach',
        )
        self.client.force_authenticate(user=master)
        r = self.client.patch(
            reverse('head-coach-assignment', args=[standalone.id]),
            {'category_prefix': '001'},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        standalone.refresh_from_db()
        self.assertEqual(standalone.username, '001_Headcoachtwo')
        self.assertEqual(r.json()['org_label'], '001_INFINITY')

    def test_master_head_can_move_agm_head_to_unassigned_category(self):
        master = User.objects.create_user(
            username='117_HeadcoachGM', password='longenoughpw1', user_type='head_coach',
        )
        agm = User.objects.create_user(
            username='001_Headcoachtwo', password='longenoughpw1', user_type='head_coach',
        )
        self.client.force_authenticate(user=master)
        r = self.client.patch(
            reverse('head-coach-assignment', args=[agm.id]),
            {'category_prefix': 'XXX_UNASSIGNED'},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        agm.refresh_from_db()
        self.assertEqual(agm.username, '118_Headcoachtwo')
        self.assertEqual(r.json()['org_label'], 'XXX_UNASSIGNED')

    def test_master_head_cannot_assign_occupied_agm_category(self):
        master = User.objects.create_user(
            username='117_HeadcoachGM', password='longenoughpw1', user_type='head_coach',
        )
        User.objects.create_user(
            username='001_Existingagm', password='longenoughpw1', user_type='head_coach',
        )
        standalone = User.objects.create_user(
            username='118_Headcoachtwo', password='longenoughpw1', user_type='head_coach',
        )
        self.client.force_authenticate(user=master)
        r = self.client.patch(
            reverse('head-coach-assignment', args=[standalone.id]),
            {'category_prefix': '001'},
            format='json',
        )
        self.assertEqual(r.status_code, 409)
        standalone.refresh_from_db()
        self.assertEqual(standalone.username, '118_Headcoachtwo')

    def test_master_head_can_soft_delete_standalone_head(self):
        master = User.objects.create_user(
            username='117_HeadcoachGM', password='longenoughpw1', user_type='head_coach',
        )
        standalone = User.objects.create_user(
            username='118_Headcoachtwo', password='longenoughpw1', user_type='head_coach',
        )
        self.client.force_authenticate(user=master)
        r = self.client.delete(reverse('head-coach-assignment', args=[standalone.id]))
        self.assertEqual(r.status_code, 200)
        standalone.refresh_from_db()
        self.assertFalse(standalone.is_active)
        self.assertEqual(standalone.deleted_by, master)
        self.assertIsNotNone(standalone.recoverable_until)

    def test_non_master_head_cannot_manage_head_categories(self):
        non_master = User.objects.create_user(
            username='118_Headcoachtwo', password='longenoughpw1', user_type='head_coach',
        )
        standalone = User.objects.create_user(
            username='119_Headcoachthree', password='longenoughpw1', user_type='head_coach',
        )
        self.client.force_authenticate(user=non_master)
        r = self.client.patch(
            reverse('head-coach-assignment', args=[standalone.id]),
            {'category_prefix': '001'},
            format='json',
        )
        self.assertEqual(r.status_code, 403)

    def test_roster_includes_unassigned_athletes(self):
        unassigned = User.objects.create_user(
            username='ath_unassigned_ra', password='longenoughpw1', user_type='athlete',
        )
        other_head = User.objects.create_user(
            username='other_head_ra', password='longenoughpw1', user_type='head_coach',
        )
        outside = User.objects.create_user(
            username='ath_outside_ra', password='longenoughpw1', user_type='athlete',
        )
        outside.primary_coach = other_head
        outside.save(update_fields=['primary_coach'])

        self._auth_head()
        r = self.client.get(reverse('head-org-roster'))
        self.assertEqual(r.status_code, 200)
        names = {row['username'] for row in r.json()['athletes']}
        self.assertIn(unassigned.username, names)
        self.assertIn(outside.username, names)

    def test_roster_hides_inactive_archived_users(self):
        archived_coach = User.objects.create_user(
            username='archived_coach_ra', password='longenoughpw1', user_type='coach',
        )
        archived_coach.is_active = False
        archived_coach.save(update_fields=['is_active'])
        archived_athlete = User.objects.create_user(
            username='archived_athlete_ra', password='longenoughpw1', user_type='athlete',
        )
        archived_athlete.is_active = False
        archived_athlete.save(update_fields=['is_active'])

        self._auth_head()
        r = self.client.get(reverse('head-org-roster'))
        self.assertEqual(r.status_code, 200)
        staff_names = {row['username'] for row in r.json()['staff']}
        athlete_names = {row['username'] for row in r.json()['athletes']}
        self.assertNotIn(archived_coach.username, staff_names)
        self.assertNotIn(archived_athlete.username, athlete_names)

    def test_roster_hides_django_admin_accounts(self):
        admin_head = User.objects.create_user(
            username='Adminone', password='longenoughpw1', user_type='head_coach',
        )
        admin_head.is_staff = True
        admin_head.is_superuser = True
        admin_head.save(update_fields=['is_staff', 'is_superuser'])

        self._auth_head()
        r = self.client.get(reverse('head-org-roster'))
        self.assertEqual(r.status_code, 200)
        head_names = {row['username'] for row in r.json()['head_coaches']}
        self.assertNotIn('Adminone', head_names)

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

    def test_reassign_staff_to_head_by_id(self):
        other_head = User.objects.create_user(
            username='other_head_staff', password='longenoughpw1', user_type='head_coach',
        )
        self._auth_head()
        r = self.client.patch(
            reverse('head-staff-link', kwargs={'user_id': self.line.id}),
            {'reports_to_id': other_head.id},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.line.refresh_from_db()
        self.assertEqual(self.line.reports_to_id, other_head.id)

    def test_unassign_staff_by_reports_to_null_makes_roster_unaffiliated(self):
        from datetime import date

        from apps.programs.models import TrainingProgram

        prog = TrainingProgram.objects.create(
            coach=self.line,
            athlete=self.ath,
            name='staff_unassign_prog',
            start_date=date(2026, 4, 1),
        )
        self._auth_head()
        r = self.client.patch(
            reverse('head-staff-link', kwargs={'user_id': self.line.id}),
            {'reports_to_id': None},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.line.refresh_from_db()
        self.ath.refresh_from_db()
        prog.refresh_from_db()
        self.assertIsNone(self.line.reports_to_id)
        self.assertIsNone(self.ath.primary_coach_id)
        self.assertEqual(prog.coach_id, self.head.id)

    def test_delete_staff_soft_deletes_and_unassigns_roster(self):
        from datetime import date

        from django.utils import timezone
        from apps.programs.models import TrainingProgram

        prog = TrainingProgram.objects.create(
            coach=self.line,
            athlete=self.ath,
            name='staff_delete_prog',
            start_date=date(2026, 4, 1),
        )
        self._auth_head()
        before = timezone.now()
        r = self.client.delete(
            reverse('head-staff-link', kwargs={'user_id': self.line.id}),
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.line.refresh_from_db()
        self.ath.refresh_from_db()
        prog.refresh_from_db()
        self.assertFalse(self.line.is_active)
        self.assertIsNone(self.line.reports_to_id)
        self.assertEqual(self.line.deleted_by_id, self.head.id)
        self.assertGreaterEqual(self.line.deleted_at, before)
        self.assertIsNotNone(self.line.recoverable_until)
        self.assertIsNone(self.ath.primary_coach_id)
        self.assertEqual(prog.coach_id, self.head.id)

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

    def test_unassign_athlete_keeps_account_and_moves_programs_to_head(self):
        from datetime import date

        from apps.programs.models import TrainingProgram

        prog = TrainingProgram.objects.create(
            coach=self.line,
            athlete=self.ath,
            name='unassign_prog',
            start_date=date(2026, 4, 1),
        )
        self._auth_head()
        r = self.client.patch(
            reverse('head-athlete-primary-coach', kwargs={'user_id': self.ath.id}),
            {'primary_coach_id': None},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.ath.refresh_from_db()
        prog.refresh_from_db()
        self.assertIsNone(self.ath.primary_coach_id)
        self.assertTrue(self.ath.is_active)
        self.assertEqual(prog.coach_id, self.head.id)

    def test_non_master_head_cannot_unassign_active_athlete_outside_org(self):
        other_head = User.objects.create_user(
            username='outside_head_unassign', password='longenoughpw1', user_type='head_coach',
        )
        outside = User.objects.create_user(
            username='outside_ath_unassign', password='longenoughpw1', user_type='athlete',
        )
        outside.primary_coach = other_head
        outside.save(update_fields=['primary_coach'])

        self._auth_head()
        r = self.client.patch(
            reverse('head-athlete-primary-coach', kwargs={'user_id': outside.id}),
            {'primary_coach_id': None},
            format='json',
        )
        self.assertEqual(r.status_code, 403)
        outside.refresh_from_db()
        self.assertEqual(outside.primary_coach_id, other_head.id)

    def test_master_head_can_reassign_active_athlete_outside_org(self):
        master = User.objects.create_user(
            username='117_HeadcoachGM', password='longenoughpw1', user_type='head_coach',
        )
        outside_head = User.objects.create_user(
            username='outside_head_reassign', password='longenoughpw1', user_type='head_coach',
        )
        outside = User.objects.create_user(
            username='outside_ath_reassign', password='longenoughpw1', user_type='athlete',
        )
        outside.primary_coach = outside_head
        outside.save(update_fields=['primary_coach'])
        t = self.client.post(
            reverse('token_obtain_pair'),
            {'username': '117_HeadcoachGM', 'password': 'longenoughpw1'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {t.json()['access']}")
        r = self.client.patch(
            reverse('head-athlete-primary-coach', kwargs={'user_id': outside.id}),
            {'primary_coach_id': master.id},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        outside.refresh_from_db()
        self.assertEqual(outside.primary_coach_id, master.id)

    def test_master_head_can_assign_athlete_to_agm_head(self):
        master = User.objects.create_user(
            username='117_HeadcoachGM', password='longenoughpw1', user_type='head_coach',
        )
        agm = User.objects.create_user(
            username='001_Headcoachone', password='longenoughpw1', user_type='head_coach',
        )
        athlete = User.objects.create_user(
            username='021_agm_target', password='longenoughpw1', user_type='athlete',
        )
        self.client.force_authenticate(user=master)
        r = self.client.patch(
            reverse('head-athlete-primary-coach', kwargs={'user_id': athlete.id}),
            {'primary_coach_id': agm.id},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        athlete.refresh_from_db()
        self.assertEqual(athlete.primary_coach_id, agm.id)

    def test_master_head_can_assign_athlete_to_line_coach_under_gm(self):
        master = User.objects.create_user(
            username='117_HeadcoachGM', password='longenoughpw1', user_type='head_coach',
        )
        line = User.objects.create_user(
            username='022_linegm', password='longenoughpw1', user_type='coach',
        )
        line.reports_to = master
        line.save(update_fields=['reports_to'])
        athlete = User.objects.create_user(
            username='023_linegm_target', password='longenoughpw1', user_type='athlete',
        )
        self.client.force_authenticate(user=master)
        r = self.client.patch(
            reverse('head-athlete-primary-coach', kwargs={'user_id': athlete.id}),
            {'primary_coach_id': line.id},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        athlete.refresh_from_db()
        self.assertEqual(athlete.primary_coach_id, line.id)

    def test_master_head_can_assign_athlete_to_line_coach_under_agm(self):
        master = User.objects.create_user(
            username='117_HeadcoachGM', password='longenoughpw1', user_type='head_coach',
        )
        agm = User.objects.create_user(
            username='001_Headcoachone', password='longenoughpw1', user_type='head_coach',
        )
        line = User.objects.create_user(
            username='024_lineagm', password='longenoughpw1', user_type='coach',
        )
        line.reports_to = agm
        line.save(update_fields=['reports_to'])
        athlete = User.objects.create_user(
            username='025_lineagm_target', password='longenoughpw1', user_type='athlete',
        )
        self.client.force_authenticate(user=master)
        r = self.client.patch(
            reverse('head-athlete-primary-coach', kwargs={'user_id': athlete.id}),
            {'primary_coach_id': line.id},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        athlete.refresh_from_db()
        self.assertEqual(athlete.primary_coach_id, line.id)

    def test_master_head_can_unassign_active_athlete_outside_org(self):
        master = User.objects.create_user(
            username='117_HeadcoachGM', password='longenoughpw1', user_type='head_coach',
        )
        outside_head = User.objects.create_user(
            username='outside_head_master_unassign', password='longenoughpw1', user_type='head_coach',
        )
        outside = User.objects.create_user(
            username='outside_ath_master_unassign', password='longenoughpw1', user_type='athlete',
        )
        outside.primary_coach = outside_head
        outside.save(update_fields=['primary_coach'])
        self.client.force_authenticate(user=master)
        r = self.client.patch(
            reverse('head-athlete-primary-coach', kwargs={'user_id': outside.id}),
            {'primary_coach_id': None},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        outside.refresh_from_db()
        self.assertIsNone(outside.primary_coach_id)

    def test_delete_athlete_soft_deletes_with_30_day_recovery_window(self):
        from datetime import date

        from django.utils import timezone
        from apps.programs.models import TrainingProgram

        prog = TrainingProgram.objects.create(
            coach=self.line,
            athlete=self.ath,
            name='delete_prog',
            start_date=date(2026, 4, 1),
        )
        self._auth_head()
        before = timezone.now()
        r = self.client.delete(
            reverse('head-athlete-primary-coach', kwargs={'user_id': self.ath.id}),
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.ath.refresh_from_db()
        prog.refresh_from_db()
        self.assertFalse(self.ath.is_active)
        self.assertIsNone(self.ath.primary_coach_id)
        self.assertEqual(self.ath.deleted_by_id, self.head.id)
        self.assertIsNotNone(self.ath.deleted_at)
        self.assertGreaterEqual(self.ath.deleted_at, before)
        self.assertIsNotNone(self.ath.recoverable_until)
        self.assertEqual((self.ath.recoverable_until.date() - self.ath.deleted_at.date()).days, 30)
        self.assertEqual(prog.coach_id, self.head.id)

    def test_line_coach_cannot_delete_athlete(self):
        t = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'line_ra', 'password': 'longenoughpw1'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {t.json()['access']}")
        r = self.client.delete(
            reverse('head-athlete-primary-coach', kwargs={'user_id': self.ath.id}),
            format='json',
        )
        self.assertEqual(r.status_code, 403)

    def test_coach_forbidden_roster(self):
        t = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'line_ra', 'password': 'longenoughpw1'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {t.json()['access']}")
        r = self.client.get(reverse('head-org-roster'))
        self.assertEqual(r.status_code, 403)


class DemoPruneCommandTests(TestCase):
    def test_permanent_clean_removes_demo_uat_leftovers_only(self):
        from io import StringIO

        from django.core.management import call_command

        canonical_head = User.objects.create_user(
            username='117_HeadcoachGM', password='pw', user_type='head_coach',
        )
        for username in ('118_Headcoachtwo', '119_Headcoachthree', '120_Headcoachfour', '121_Headcoachone'):
            User.objects.create_user(username=username, password='pw', user_type='head_coach')
        canonical_coach = User.objects.create_user(
            username='045_Coachone', password='pw', user_type='coach',
        )
        canonical_coach.reports_to = canonical_head
        canonical_coach.save(update_fields=['reports_to'])
        for username in ('034_Coachtwo', '088_Coachthree', '013_Coachfour'):
            extra_coach = User.objects.create_user(
                username=username, password='pw', user_type='coach',
            )
            extra_coach.reports_to = canonical_head
            extra_coach.save(update_fields=['reports_to'])
        canonical_athlete = User.objects.create_user(
            username='000_Athlete1', password='pw', user_type='athlete',
        )
        canonical_athlete.primary_coach = canonical_coach
        canonical_athlete.save(update_fields=['primary_coach'])
        for username in DEMO_UNASSIGNED_ATHLETE_USERNAMES:
            User.objects.create_user(username=username, password='pw', user_type='athlete')
        User.objects.create_user(username='docker_UAT_coach_1', password='pw', user_type='coach')
        User.objects.create_user(username='005_dockerUATAthlete1', password='pw', user_type='athlete')
        User.objects.create_user(username='Adminone', password='pw', user_type='head_coach')
        User.objects.create_user(username='future_real_user', password='pw', user_type='athlete')

        call_command(
            'prune_demo_users',
            '--apply',
            '--permanent-clean',
            '--no-ensure-canonical',
            stdout=StringIO(),
        )

        self.assertTrue(User.objects.filter(username='117_HeadcoachGM').exists())
        self.assertTrue(User.objects.filter(username='118_Headcoachtwo').exists())
        self.assertTrue(User.objects.filter(username='119_Headcoachthree').exists())
        self.assertTrue(User.objects.filter(username='120_Headcoachfour').exists())
        self.assertTrue(User.objects.filter(username='121_Headcoachone').exists())
        self.assertTrue(User.objects.filter(username='045_Coachone').exists())
        self.assertTrue(User.objects.filter(username='034_Coachtwo').exists())
        self.assertTrue(User.objects.filter(username='088_Coachthree').exists())
        self.assertTrue(User.objects.filter(username='013_Coachfour').exists())
        self.assertTrue(User.objects.filter(username='000_Athlete1').exists())
        for username in DEMO_UNASSIGNED_ATHLETE_USERNAMES:
            self.assertTrue(User.objects.filter(username=username, primary_coach__isnull=True).exists())
        self.assertFalse(User.objects.filter(username='docker_UAT_coach_1').exists())
        self.assertFalse(User.objects.filter(username='005_dockerUATAthlete1').exists())
        self.assertFalse(User.objects.filter(username='Adminone').exists())
        self.assertTrue(User.objects.filter(username='future_real_user').exists())


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
