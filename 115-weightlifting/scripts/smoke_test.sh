#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

ensure_backend_venv
ensure_backend_env

smoke_json="$(backend_manage shell <<'PY'
import json
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework.test import APIClient

from apps.athletes.models import ProgramCompletion
from apps.programs.models import TrainingProgram

if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')

User = get_user_model()
coach, _ = User.objects.get_or_create(username='coach_smoke', defaults={'user_type': 'coach'})
coach.user_type = 'coach'
coach.set_password('DemoPass123!')
coach.save()

athlete, _ = User.objects.get_or_create(username='athlete_smoke', defaults={'user_type': 'athlete'})
athlete.user_type = 'athlete'
athlete.set_password('DemoPass123!')
athlete.bodyweight_kg = Decimal('79.50')
athlete.gender = 'M'
athlete.save()

athlete_b, _ = User.objects.get_or_create(username='athlete_smoke_b', defaults={'user_type': 'athlete'})
athlete_b.user_type = 'athlete'
athlete_b.set_password('DemoPass123!')
athlete_b.save()

program_payload = {
    'name': 'Smoke Test Week',
    'description': 'Structured program created by CLI smoke test.',
    'athlete_id': athlete.id,
    'start_date': str(date.today()),
    'end_date': None,
    'program_data': {
        'week_start_date': str(date.today()),
        'days': [
            {
                'day': 'Monday',
                'exercises': [
                    {
                        'name': 'Snatch',
                        'sets': '5',
                        'reps': '2',
                        'intensity': '75%',
                        'notes': 'Fast turnover',
                    }
                ],
            }
        ],
    },
}

coach_client = APIClient()
coach_login = coach_client.post('/api/auth/token/', {'username': 'coach_smoke', 'password': 'DemoPass123!'}, format='json')
assert coach_login.status_code == 200, coach_login.content
coach_tokens = coach_login.json()
assert 'access' in coach_tokens and 'refresh' in coach_tokens, f"expected access+refresh, got {coach_tokens}"
coach_client.credentials(HTTP_AUTHORIZATION=f"Bearer {coach_tokens['access']}")

unauth_client = APIClient()
anon_me = unauth_client.get('/api/auth/me/')
assert anon_me.status_code == 401, f"unauth /me should be 401, got {anon_me.status_code}"

import os as _os
_prev_coach_code = _os.environ.pop('COACH_SIGNUP_CODE', None)
try:
    open_coach_reg = APIClient().post(
        '/api/auth/register/',
        {'username': 'open_coach_attempt', 'password': 'longenoughpw1', 'user_type': 'coach'},
        format='json',
    )
    assert open_coach_reg.status_code == 400, (
        f'coach signup without env code should 400, got {open_coach_reg.status_code}'
    )
    assert not User.objects.filter(username='open_coach_attempt').exists(), (
        'blocked coach signup still created a user'
    )
finally:
    if _prev_coach_code is not None:
        _os.environ['COACH_SIGNUP_CODE'] = _prev_coach_code

refresh_response = APIClient().post(
    '/api/auth/token/refresh/', {'refresh': coach_tokens['refresh']}, format='json'
)
assert refresh_response.status_code == 200, refresh_response.content
refreshed_access = refresh_response.json()['access']
assert refreshed_access and refreshed_access != coach_tokens['access'], 'refresh did not rotate access token'
rotated_client = APIClient()
rotated_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refreshed_access}")
rotated_me = rotated_client.get('/api/auth/me/')
assert rotated_me.status_code == 200, rotated_me.content

replay_refresh = APIClient().post(
    '/api/auth/token/refresh/', {'refresh': coach_tokens['refresh']}, format='json'
)
assert replay_refresh.status_code == 401, (
    f'blacklisted refresh should 401, got {replay_refresh.status_code}: {replay_refresh.content}'
)

logout_client = APIClient()
logout_login_raw = logout_client.post(
    '/api/auth/token/',
    {'username': 'coach_smoke', 'password': 'DemoPass123!'},
    format='json',
)
refresh_cookie_present = 'wl_refresh' in logout_login_raw.cookies
assert refresh_cookie_present, 'login did not set the httpOnly wl_refresh cookie'
logout_login = logout_login_raw.json()

cookie_only_refresh = logout_client.post('/api/auth/token/refresh/', {}, format='json')
assert cookie_only_refresh.status_code == 200, (
    f'cookie-only refresh should succeed, got {cookie_only_refresh.status_code}: {cookie_only_refresh.content}'
)

logout_client.credentials(HTTP_AUTHORIZATION=f"Bearer {logout_login['access']}")
logout_response = logout_client.post('/api/auth/logout/', {}, format='json')
assert logout_response.status_code == 205, (
    f'expected 205 from logout, got {logout_response.status_code}: {logout_response.content}'
)
post_logout_refresh = APIClient().post(
    '/api/auth/token/refresh/', {'refresh': logout_login['refresh']}, format='json'
)
assert post_logout_refresh.status_code == 401, (
    'logout should blacklist refresh token'
)

# List + prefetch checks need at least one owned program; a cold DB has none
# until the explicit create later, so seed once when empty.
_pre_list = coach_client.get('/api/programs/')
assert _pre_list.status_code == 200, _pre_list.content
if len(_pre_list.data) == 0:
    _seed = coach_client.post('/api/programs/', program_payload, format='json')
    assert _seed.status_code == 201, _seed.content

from django.db import connection as _conn
from django.test.utils import CaptureQueriesContext as _Cap
with _Cap(_conn) as _ctx:
    programs_resp = coach_client.get('/api/programs/')
assert programs_resp.status_code == 200
assert len(programs_resp.data) >= 1
_completion_queries = [q for q in _ctx.captured_queries if 'programcompletion' in q['sql'].lower()]
assert len(_completion_queries) <= 1, (
    f'expected <=1 completion SELECT via prefetch, got {len(_completion_queries)}'
)

me_response = coach_client.get('/api/auth/me/')
assert me_response.status_code == 200, me_response.content

create_program_response = coach_client.post('/api/programs/', program_payload, format='json')
assert create_program_response.status_code == 201, create_program_response.content
program_id = create_program_response.json()['id']

markup_name_payload = {
    **program_payload,
    'name': '<script>smoke-probe</script>',
    'athlete_id': athlete.id,
}
markup_create = coach_client.post('/api/programs/', markup_name_payload, format='json')
assert markup_create.status_code == 400, (
    f'program name with angle brackets must 400, got {markup_create.status_code}: {markup_create.content}'
)

athlete_client = APIClient()
athlete_login = athlete_client.post('/api/auth/token/', {'username': 'athlete_smoke', 'password': 'DemoPass123!'}, format='json')
assert athlete_login.status_code == 200, athlete_login.content
athlete_client.credentials(HTTP_AUTHORIZATION=f"Bearer {athlete_login.json()['access']}")

completion_patch = athlete_client.patch(
    f'/api/athletes/program-completion/{program_id}/',
    {
        'completion_data': {
            'entries': {
                '0': {
                    '0': {
                        'completed': True,
                        'athlete_notes': 'CLI smoke test',
                        'result': '75x2',
                    }
                }
            }
        }
    },
    format='json',
)
assert completion_patch.status_code == 200, completion_patch.content

pr_response = athlete_client.post(
    '/api/athletes/prs/',
    {'lift_type': 'snatch', 'weight': '80.0', 'date': str(date.today())},
    format='json',
)
assert pr_response.status_code == 201, pr_response.content

sinclair_response = athlete_client.post(
    '/api/analytics/sinclair/',
    {'bodyweight_kg': 81.0, 'total_kg': 285.0, 'gender': 'M'},
    format='json',
)
assert sinclair_response.status_code == 200, sinclair_response.content

completion_count_before = ProgramCompletion.objects.filter(program_id=program_id).count()
assert completion_count_before >= 1, 'expected at least 1 completion record before reassignment'

athlete_c_username = f'athlete_smoke_readonly_{program_id}'
athlete_c, _ = User.objects.get_or_create(username=athlete_c_username, defaults={'user_type': 'athlete'})
athlete_c.user_type = 'athlete'
athlete_c.set_password('DemoPass123!')
athlete_c.save()
readonly_program = TrainingProgram.objects.create(
    coach=coach, athlete=athlete_c, name='RO Smoke', start_date=date.today(),
)
ro_client = APIClient()
ro_login = ro_client.post(
    '/api/auth/token/',
    {'username': athlete_c_username, 'password': 'DemoPass123!'},
    format='json',
)
ro_client.credentials(HTTP_AUTHORIZATION=f"Bearer {ro_login.json()['access']}")

ro_before = ProgramCompletion.objects.filter(program=readonly_program).count()
ro_get = ro_client.get(f'/api/athletes/program-completion/{readonly_program.id}/')
assert ro_get.status_code == 404, (
    f'GET on missing completion should 404, got {ro_get.status_code}'
)
ro_after = ProgramCompletion.objects.filter(program=readonly_program).count()
assert ro_after == ro_before, f'GET mutated DB: {ro_before} -> {ro_after}'

from datetime import timedelta as _td
future_pr = athlete_client.post(
    '/api/athletes/prs/',
    {'lift_type': 'snatch', 'weight': '80', 'date': str(date.today() + _td(days=5))},
    format='json',
)
assert future_pr.status_code == 400, f'future PR should 400, got {future_pr.status_code}'

absurd_pr = athlete_client.post(
    '/api/athletes/prs/',
    {'lift_type': 'snatch', 'weight': '9999', 'date': str(date.today())},
    format='json',
)
assert absurd_pr.status_code == 400, f'absurd weight should 400, got {absurd_pr.status_code}'

unassigned_username = f'athlete_smoke_unassigned_{program_id}'
unassigned_athlete, _ = User.objects.get_or_create(
    username=unassigned_username, defaults={'user_type': 'athlete'}
)
unassigned_athlete.user_type = 'athlete'
unassigned_athlete.set_password('DemoPass123!')
unassigned_athlete.save()

scoped_athletes = coach_client.get('/api/auth/athletes/')
assert scoped_athletes.status_code == 200
scoped_body = scoped_athletes.json()
assert isinstance(scoped_body, dict) and 'results' in scoped_body, (
    f'expected paginated envelope, got {type(scoped_body).__name__}'
)
assert scoped_body['scope'] == 'mine', scoped_body
scoped_usernames = {a['username'] for a in scoped_body['results']}
assert athlete.username in scoped_usernames, scoped_usernames
assert unassigned_username not in scoped_usernames, (
    'scope=mine leaked an athlete the coach has no program for'
)

# Line coaches must not browse scope=all (org-wide roster is head-only).
all_athletes = coach_client.get(
    '/api/auth/athletes/', {'scope': 'all', 'q': unassigned_username},
)
assert all_athletes.status_code == 403, (
    f'line coach scope=all should 403, got {all_athletes.status_code}: {all_athletes.content}'
)

reassign_response = coach_client.patch(
    f'/api/programs/{program_id}/assign/',
    {'athlete_id': athlete_b.id},
    format='json',
)
assert reassign_response.status_code == 200, reassign_response.content
assert reassign_response.json()['athlete_id'] == athlete_b.id, 'athlete swap did not persist'

prior_records = ProgramCompletion.objects.filter(program_id=program_id, athlete=athlete)
assert prior_records.count() == completion_count_before, (
    f'prior athlete history lost: before={completion_count_before}, after={prior_records.count()}'
)

markup_program_qs = TrainingProgram.objects.filter(
    Q(name__contains='<')
    | Q(name__contains='>')
    | Q(description__contains='<')
    | Q(description__contains='>')
)
markup_program_sample = list(markup_program_qs.values_list('id', 'athlete_id', 'name')[:25])
assert not markup_program_sample, (
    'Programs with angle brackets in name/description would show on athlete dashboards for '
    f'whoever owns them; purge or fix: {markup_program_sample!r}'
)

print(json.dumps({
    'program_id': program_id,
    'sinclair': sinclair_response.json(),
    'coach_program_count': TrainingProgram.objects.filter(coach=coach).count(),
    'refresh_rotated': True,
    'refresh_blacklist_enforced': replay_refresh.status_code == 401,
    'unauth_me_status': anon_me.status_code,
    'reassignment_preserved_completions': prior_records.count(),
    'coach_signup_gated': open_coach_reg.status_code == 400,
    'completion_get_is_readonly': ro_get.status_code == 404 and ro_after == ro_before,
    'logout_blacklisted_refresh': post_logout_refresh.status_code == 401,
    'future_date_pr_rejected': future_pr.status_code == 400,
    'absurd_weight_rejected': absurd_pr.status_code == 400,
    'athlete_list_scope_mine_safe': unassigned_username not in scoped_usernames,
    'athlete_list_scope_all_blocked_for_line_coach': all_athletes.status_code == 403,
    'refresh_cookie_set_on_login': refresh_cookie_present,
    'cookie_only_refresh_ok': cookie_only_refresh.status_code == 200,
    'programs_list_is_prefetched': len(_completion_queries) <= 1,
    'program_markup_create_rejected': markup_create.status_code == 400,
    'markup_program_rows_in_db': markup_program_qs.count(),
}))
PY
)"
smoke_json="$(printf '%s\n' "$smoke_json" | tail -n 1)"

echo "$smoke_json"
log_event "smoke" "success" "smoke_test.sh" "$smoke_json"
"$ROOT_DIR/scripts/report.sh" >/dev/null
