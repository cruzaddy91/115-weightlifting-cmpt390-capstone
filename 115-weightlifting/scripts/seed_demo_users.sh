#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

ensure_backend_venv
ensure_backend_env
ensure_runtime_dirs

backend_manage shell -c "
from decimal import Decimal

from django.contrib.auth import get_user_model

User = get_user_model()

for username, user_type in [('coach_smoke', 'coach'), ('athlete_smoke', 'athlete')]:
    user, _ = User.objects.get_or_create(username=username, defaults={'user_type': user_type})
    user.user_type = user_type
    user.set_password('DemoPass123!')
    user.save()

athlete = User.objects.get(username='athlete_smoke')
athlete.bodyweight_kg = Decimal('79.50')
athlete.gender = 'M'
athlete.save(update_fields=['bodyweight_kg', 'gender'])

print(
    'Seeded demo users: coach_smoke, athlete_smoke (same password for both). '
    'Athlete profile: 79.5 kg, M. Password is documented in README; not echoed here.'
)
"

log_event "demo_seed" "success" "seed_demo_users.sh" '{"users":["coach_smoke","athlete_smoke"]}'
"$ROOT_DIR/scripts/report.sh" >/dev/null
