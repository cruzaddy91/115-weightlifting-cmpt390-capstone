from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from unittest.mock import patch

from apps.accounts.weight_class import competitive_weight_class_label
from apps.athletes.models import PersonalRecord, ProgramCompletion
from apps.programs.models import TrainingProgram

from .robi import (
    MEN_CATEGORIES,
    PROGRESSIVITY,
    WOMEN_CATEGORIES,
    classify,
    robi_score,
    world_record_total,
)

User = get_user_model()


class RobiClassifyTests(TestCase):
    """Bodyweight -> IWF category mapping, including boundaries and overflow."""

    def test_exact_boundary_maps_to_that_class(self):
        self.assertEqual(classify(61, 'M'), '61')
        self.assertEqual(classify(49, 'F'), '49')

    def test_just_over_boundary_maps_to_next_class(self):
        self.assertEqual(classify(61.01, 'M'), '73')
        self.assertEqual(classify(49.01, 'F'), '59')

    def test_super_heavyweight_routes_to_open_bucket(self):
        self.assertEqual(classify(115, 'M'), '+109')
        self.assertEqual(classify(250, 'M'), '+109')
        self.assertEqual(classify(90, 'F'), '+87')
        self.assertEqual(classify(150, 'F'), '+87')

    def test_mid_weight_picks_smallest_fitting_class(self):
        self.assertEqual(classify(72, 'M'), '73')
        self.assertEqual(classify(80, 'M'), '89')
        self.assertEqual(classify(75, 'F'), '81')

    def test_robi_class_matches_profile_weight_class_label(self):
        """ROBI routing must stay aligned with athlete roster / nav labels."""
        bw, gender = 58.99, 'F'
        key = classify(bw, gender)
        label = competitive_weight_class_label(bw, gender)
        self.assertEqual(key, '59')
        self.assertEqual(label, '59 kg')

    def test_invalid_gender_raises(self):
        with self.assertRaises(ValueError):
            classify(80, 'X')

    def test_non_positive_bodyweight_raises(self):
        with self.assertRaises(ValueError):
            classify(0, 'M')
        with self.assertRaises(ValueError):
            classify(-5, 'F')


class RobiScoreTests(TestCase):
    """Math of the ROBI score itself: WR hits 1000, power law scales by b."""

    def test_world_record_scores_exactly_1000(self):
        # Men 89 kg Olympic class: WR total 405 (Karlos Nasar, Dec 2024).
        result = robi_score(total_kg=405, bodyweight_kg=88, gender='M')
        self.assertEqual(result['robi'], 1000.0)
        self.assertEqual(result['weight_class'], '89')
        self.assertEqual(result['world_record_total'], 405)

    def test_every_class_WR_scores_1000_for_both_genders(self):
        # Generalized guarantee: update the table in robi.py, this still passes.
        for key, upper, wr in MEN_CATEGORIES:
            bw = upper if upper is not None else 150
            result = robi_score(total_kg=wr, bodyweight_kg=bw, gender='M')
            self.assertEqual(result['robi'], 1000.0, msg=f'men {key}')
        for key, upper, wr in WOMEN_CATEGORIES:
            bw = upper if upper is not None else 120
            result = robi_score(total_kg=wr, bodyweight_kg=bw, gender='F')
            self.assertEqual(result['robi'], 1000.0, msg=f'women {key}')

    def test_half_of_world_record_scores_100(self):
        # With b = log2(10), a total of WR/2 should produce ROBI ~= 100.
        wr = world_record_total('M', '89')
        result = robi_score(total_kg=wr / 2, bodyweight_kg=88, gender='M')
        self.assertAlmostEqual(result['robi'], 100.0, places=1)

    def test_progressivity_constant_matches_expected_value(self):
        # Guard the one bit of magic: b = 3.3219281 = log2(10).
        self.assertAlmostEqual(PROGRESSIVITY, 3.3219281, places=6)

    def test_pro_vs_elite_gap_is_visibly_large(self):
        # Jon_snow-style demo: a strong-national (~340) vs international elite
        # (~380) lifter should produce a visibly different ROBI.
        pro = robi_score(total_kg=340, bodyweight_kg=85, gender='M')
        elite = robi_score(total_kg=380, bodyweight_kg=85, gender='M')
        self.assertGreater(elite['robi'], pro['robi'])
        # The gap should be > 100 points -- tight elite class resolution.
        self.assertGreater(elite['robi'] - pro['robi'], 100)

    def test_bodyweight_alone_does_not_change_robi_if_class_stays_same(self):
        # Two lifters with the same total in the same class should score
        # identically -- ROBI is class-anchored, not bodyweight-continuous.
        a = robi_score(total_kg=300, bodyweight_kg=85, gender='M')
        b = robi_score(total_kg=300, bodyweight_kg=86, gender='M')
        self.assertEqual(a['robi'], b['robi'])
        self.assertEqual(a['weight_class'], b['weight_class'])

    def test_zero_or_negative_total_rejected(self):
        with self.assertRaises(ValueError):
            robi_score(total_kg=0, bodyweight_kg=85, gender='M')
        with self.assertRaises(ValueError):
            robi_score(total_kg=-10, bodyweight_kg=85, gender='M')

    def test_response_shape_has_everything_the_frontend_needs(self):
        r = robi_score(total_kg=380, bodyweight_kg=85, gender='M')
        self.assertIn('robi', r)
        self.assertIn('weight_class', r)
        self.assertIn('world_record_total', r)
        self.assertIn('coefficient_a', r)
        self.assertIn('progressivity_b', r)
        self.assertIn('gender', r)
        self.assertIn('bodyweight_kg', r)
        self.assertIn('total_kg', r)


class RobiEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='robi_athlete', password='longenoughpw1', user_type='athlete',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = '/api/analytics/robi/'

    def test_happy_path_returns_expected_shape(self):
        resp = self.client.post(self.url, {
            'bodyweight_kg': 85,
            'total_kg': 380,
            'gender': 'M',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['gender'], 'M')
        self.assertEqual(body['weight_class'], '89')
        self.assertIsInstance(body['robi'], (int, float))

    def test_world_record_hit_via_endpoint_is_exactly_1000(self):
        resp = self.client.post(self.url, {
            'bodyweight_kg': 88,
            'total_kg': 405,
            'gender': 'M',
        }, format='json')
        self.assertEqual(resp.json()['robi'], 1000.0)

    def test_missing_fields_400(self):
        resp = self.client.post(self.url, {'gender': 'M'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_invalid_gender_400(self):
        resp = self.client.post(self.url, {
            'bodyweight_kg': 85, 'total_kg': 380, 'gender': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_negative_total_400(self):
        resp = self.client.post(self.url, {
            'bodyweight_kg': 85, 'total_kg': -1, 'gender': 'M',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_anonymous_request_rejected(self):
        anon = APIClient()
        resp = anon.post(self.url, {
            'bodyweight_kg': 85, 'total_kg': 380, 'gender': 'M',
        }, format='json')
        self.assertEqual(resp.status_code, 401)


class HeadRecommendationModeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.head = User.objects.create_user(
            username='head_mode',
            password='longenoughpw1',
            user_type='head_coach',
        )
        self.staff = User.objects.create_user(
            username='line_mode',
            password='longenoughpw1',
            user_type='coach',
            reports_to=self.head,
        )
        self.athlete = User.objects.create_user(
            username='athlete_mode',
            password='longenoughpw1',
            user_type='athlete',
            primary_coach=self.staff,
            gender='F',
            bodyweight_kg=59,
        )
        start = timezone.now().date()
        for idx in range(4):
            program = TrainingProgram.objects.create(
                coach=self.staff,
                athlete=self.athlete,
                name=f'Cycle {idx}',
                normalized_name=f'cycle {idx}',
                style_tags=['style:strength'],
                start_date=start,
                end_date=start,
                program_data={'days': [{'day': 'Monday', 'exercises': [{'sets': 4, 'reps': 3}]}]},
            )
            ProgramCompletion.objects.create(
                program=program,
                athlete=self.athlete,
                completion_data={'entries': {'Monday': {'0': {'completed': idx % 2 == 0}}}},
            )
            PersonalRecord.objects.create(
                athlete=self.athlete,
                lift_type='total',
                weight=100 + idx,
                date=start,
            )
        self.client.force_authenticate(user=self.head)

    def test_head_recommendations_include_strategy_metadata(self):
        response = self.client.get('/api/analytics/head/recommendations/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('strategy', payload)
        self.assertIn('generated_at', payload)
        self.assertIn('model_version', payload)
        self.assertIn('fallback_reason', payload)

    @patch('apps.analytics.views.load_latest_model_bundle')
    @patch('apps.analytics.views.settings.HEAD_RECOMMENDER_MODE', 'model')
    def test_model_mode_falls_back_when_artifact_missing(self, mocked_loader):
        mocked_loader.return_value = None
        response = self.client.get('/api/analytics/head/recommendations/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['strategy'], 'rule')
        self.assertTrue(payload['fallback_reason'])

    def test_head_model_status_endpoint_exists(self):
        response = self.client.get('/api/analytics/head/model-status/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('mode', payload)
        self.assertIn('has_model_artifact', payload)
