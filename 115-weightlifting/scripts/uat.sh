#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

ensure_runtime_dirs
ensure_backend_env
ensure_frontend_env

if [[ "$(port_status 4173)" != "listening" ]]; then
  echo "Frontend is not listening on port 4173. Start './bin/zw host-local foreground' first." >&2
  exit 1
fi

if [[ "$(port_status 8000)" != "listening" ]]; then
  echo "Backend is not listening on port 8000. Start './bin/zw host-local foreground' first." >&2
  exit 1
fi

# Put the app in a known-good localhost demo state before acceptance checks.
"$ROOT_DIR/scripts/make_demo.sh" >/dev/null
"$ROOT_DIR/scripts/report.sh" >/dev/null

uat_output="$(python3 <<'PY'
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

frontend_base = 'http://localhost:4173'
api_base = 'http://localhost:8000'
report_path = Path('/Users/addycruz/Workspace/CMPT-390_CSCapstone/115-weightlifting/var/reports/index.html')

results = []
state = {}


def record(name, ok, detail):
    results.append({'name': name, 'ok': ok, 'detail': detail})
    if not ok:
        raise AssertionError(f'{name}: {detail}')


def request(method, url, data=None, token=None, expected=(200,), headers=None):
    body = None
    req_headers = {'Accept': 'application/json'}
    if headers:
        req_headers.update(headers)
    if token:
        req_headers['Authorization'] = f'Bearer {token}'
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        req_headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=body, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status = response.getcode()
            payload = response.read().decode('utf-8')
            if status not in expected:
                raise AssertionError(f'{method} {url} returned {status}, expected {expected}')
            return status, payload, response.headers
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode('utf-8', errors='replace')
        raise AssertionError(f'{method} {url} returned {exc.code}: {payload}') from exc


suffix = str(int(time.time()))
coach_username = f'uat_coach_{suffix}'
athlete_username = f'uat_athlete_{suffix}'
password = 'DemoPass123!'

status, payload, _ = request('GET', f'{frontend_base}/', expected=(200,), headers={'Accept': 'text/html'})
record('frontend_root', True, f'HTTP {status}')

record('report_dashboard_exists', report_path.exists(), str(report_path))

request('POST', f'{api_base}/api/auth/register/', {
    'username': coach_username,
    'password': password,
    'user_type': 'coach'
}, expected=(201,))
record('register_coach', True, coach_username)

request('POST', f'{api_base}/api/auth/register/', {
    'username': athlete_username,
    'password': password,
    'user_type': 'athlete'
}, expected=(201,))
record('register_athlete', True, athlete_username)

_, payload, _ = request('POST', f'{api_base}/api/auth/token/', {
    'username': coach_username,
    'password': password
}, expected=(200,))
coach_token = json.loads(payload)['access']
record('login_coach', True, coach_username)

_, payload, _ = request('GET', f'{api_base}/api/auth/me/', token=coach_token, expected=(200,))
coach_me = json.loads(payload)
record('current_user_coach', coach_me.get('username') == coach_username and coach_me.get('user_type') == 'coach', coach_me)
state['coach_me'] = coach_me

_, payload, _ = request('GET', f'{api_base}/api/auth/athletes/', token=coach_token, expected=(200,))
athletes = json.loads(payload)
matched_athlete = next((item for item in athletes if item.get('username') == athlete_username), None)
record('coach_get_athletes', matched_athlete is not None, {'athlete_count': len(athletes)})
athlete_id = matched_athlete['id']

program_payload = {
    'name': f'UAT Week {suffix}',
    'description': 'User acceptance test program created through localhost flow.',
    'athlete_id': athlete_id,
    'start_date': time.strftime('%Y-%m-%d'),
    'end_date': None,
    'program_data': {
        'week_start_date': time.strftime('%Y-%m-%d'),
        'days': [
            {
                'day': 'Monday',
                'exercises': [
                    {
                        'name': 'Snatch',
                        'sets': '5',
                        'reps': '2',
                        'intensity': '78%',
                        'notes': 'Fast finish'
                    },
                    {
                        'name': 'Back Squat',
                        'sets': '4',
                        'reps': '4',
                        'intensity': '80%',
                        'notes': 'Controlled descent'
                    }
                ]
            }
        ]
    }
}
_, payload, _ = request('POST', f'{api_base}/api/programs/', data=program_payload, token=coach_token, expected=(201,))
program = json.loads(payload)
program_id = program['id']
record('coach_create_program', True, {'program_id': program_id})

_, payload, _ = request('PATCH', f'{api_base}/api/programs/{program_id}/', data={'description': 'Updated during localhost UAT.'}, token=coach_token, expected=(200,))
updated_program = json.loads(payload)
record('coach_update_program', updated_program.get('description') == 'Updated during localhost UAT.', {'program_id': program_id})

_, payload, _ = request('POST', f'{api_base}/api/auth/token/', {
    'username': athlete_username,
    'password': password
}, expected=(200,))
athlete_token = json.loads(payload)['access']
record('login_athlete', True, athlete_username)

_, payload, _ = request('GET', f'{api_base}/api/auth/me/', token=athlete_token, expected=(200,))
athlete_me = json.loads(payload)
record('current_user_athlete', athlete_me.get('username') == athlete_username and athlete_me.get('user_type') == 'athlete', athlete_me)

_, payload, _ = request('GET', f'{api_base}/api/programs/', token=athlete_token, expected=(200,))
athlete_programs = json.loads(payload)
record('athlete_get_programs', any(item.get('id') == program_id for item in athlete_programs), {'program_count': len(athlete_programs)})

_, payload, _ = request('GET', f'{api_base}/api/athletes/program-completion/{program_id}/', token=athlete_token, expected=(200,))
completion = json.loads(payload)
record('athlete_get_program_completion', 'completion_data' in completion, {'program_id': program_id})

completion_payload = {
    'completion_data': {
        'entries': {
            '0': {
                '0': {
                    'completed': True,
                    'athlete_notes': 'UAT completion pass',
                    'result': '78x2'
                },
                '1': {
                    'completed': True,
                    'athlete_notes': 'Felt stable',
                    'result': '140x4'
                }
            }
        }
    }
}
_, payload, _ = request('PATCH', f'{api_base}/api/athletes/program-completion/{program_id}/', data=completion_payload, token=athlete_token, expected=(200,))
completion_updated = json.loads(payload)
record('athlete_save_program_completion', completion_updated.get('completion_data', {}).get('entries', {}).get('0', {}).get('0', {}).get('completed') is True, {'program_id': program_id})

_, payload, _ = request('POST', f'{api_base}/api/athletes/workouts/', data={
    'date': time.strftime('%Y-%m-%d'),
    'notes': 'Localhost UAT workout log entry.'
}, token=athlete_token, expected=(201,))
workout = json.loads(payload)
record('athlete_create_workout_log', workout.get('notes') == 'Localhost UAT workout log entry.', {'workout_id': workout.get('id')})

_, payload, _ = request('GET', f'{api_base}/api/athletes/workouts/', token=athlete_token, expected=(200,))
workouts = json.loads(payload)
record('athlete_get_workout_logs', any(item.get('id') == workout.get('id') for item in workouts), {'workout_count': len(workouts)})

_, payload, _ = request('POST', f'{api_base}/api/athletes/prs/', data={
    'lift_type': 'snatch',
    'weight': '81.5',
    'date': time.strftime('%Y-%m-%d')
}, token=athlete_token, expected=(201,))
pr = json.loads(payload)
record('athlete_create_pr', str(pr.get('weight')) == '81.50', {'pr_id': pr.get('id')})

_, payload, _ = request('GET', f'{api_base}/api/athletes/prs/', token=athlete_token, expected=(200,))
prs = json.loads(payload)
record('athlete_get_prs', any(item.get('id') == pr.get('id') for item in prs), {'pr_count': len(prs)})

_, payload, _ = request('POST', f'{api_base}/api/analytics/sinclair/', data={
    'bodyweight_kg': 81.0,
    'total_kg': 286.5,
    'gender': 'M'
}, token=athlete_token, expected=(200,))
sinclair = json.loads(payload)
record('athlete_calculate_sinclair', 'sinclair_total' in sinclair and 'coefficient' in sinclair, sinclair)

summary = {
    'status': 'passed',
    'frontend_base': frontend_base,
    'api_base': api_base,
    'checks_passed': len(results),
    'checks': results,
    'artifacts': {
        'program_id': program_id,
        'workout_id': workout.get('id'),
        'pr_id': pr.get('id'),
        'report_path': str(report_path)
    }
}
print(json.dumps(summary))
PY
)"

uat_output="$(printf '%s\n' "$uat_output" | tail -n 1)"

python3 - "$uat_output" "$REPORT_DIR/UAT_REPORT.md" "$REPORT_DIR/uat_latest.json" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

summary = json.loads(sys.argv[1])
markdown_path = Path(sys.argv[2])
json_path = Path(sys.argv[3])
json_path.write_text(json.dumps(summary, indent=2), encoding='utf-8')

lines = [
    '# Localhost UAT Report',
    '',
    f"Generated: {datetime.utcnow().isoformat()}Z",
    '',
    f"- Status: {summary['status']}",
    f"- Frontend: {summary['frontend_base']}",
    f"- API: {summary['api_base']}",
    f"- Checks passed: {summary['checks_passed']}",
    '',
    '## Checks',
    ''
]
for item in summary['checks']:
    lines.append(f"- PASS {item['name']}: {item['detail']}")

lines.extend([
    '',
    '## Artifacts',
    '',
    f"- Program ID: {summary['artifacts']['program_id']}",
    f"- Workout ID: {summary['artifacts']['workout_id']}",
    f"- PR ID: {summary['artifacts']['pr_id']}",
    f"- Report Path: {summary['artifacts']['report_path']}",
    ''
])
markdown_path.write_text('\n'.join(lines), encoding='utf-8')
PY

echo "$uat_output"
log_event "uat" "success" "uat.sh" "$uat_output"
"$ROOT_DIR/scripts/report.sh" >/dev/null
