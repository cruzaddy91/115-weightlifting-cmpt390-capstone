# Docker Validation Summary

- Status: PASS
- Backend URL: http://localhost:8000
- Frontend URL: http://localhost:4173
- Stress cycles per account: 25
- Generated at UTC: 2026-05-04T22:53:38Z

## Artifacts

- docker_uat_latest.json
- auth_stress_coachone_latest.json
- auth_stress_jonsnow_latest.json
- compose_config_latest.txt
- compose_ps_latest.txt
- backend_logs_latest.txt
- frontend_logs_latest.txt
- postgres_logs_latest.txt

## Pass/Fail Results

- Static validation: PASS
  - `sh -n scripts/validate_docker_stack.sh`
  - `python3 -m py_compile scripts/docker_uat.py scripts/docker_auth_stress.py`
  - `docker compose config`
- Docker startup: PASS
  - PostgreSQL reached healthy state.
  - Backend reachable at `http://localhost:8000`.
  - Frontend reachable at `http://localhost:4173`.
- API UAT: PASS
  - 24 passed, 0 failed.
  - Seeded accounts confirmed: `Headcoachone`, `Coachone`, `jon_snow`.
  - `jon_snow` confirmed to have assigned programs.
  - Temporary coach/athlete flow created, updated, assigned, retrieved, and completed a program.
  - Workout log, PR log, and Sinclair analytics endpoints passed.
- Auth stress: PASS
  - `Coachone`: 25 passed, 0 failed.
  - `jon_snow`: 25 passed, 0 failed.

## Edge Cases / Logical Holes

- The validation uses a warm local Docker volume after the first pass. For a strict professor-style fresh clone test, run `docker compose down -v` before re-running.
- The stress test is intentionally modest at 25 cycles per demo account to avoid false failures from login throttling. It validates repeated auth/logout stability, not high-concurrency load.
- Frontend validation confirms that the built app is served as HTML. It does not drive browser clicks through each dashboard.
- The UAT creates temporary users and records in the Docker database. That is acceptable for validation, but repeated runs will accumulate test data unless the Docker volume is reset.
- Build output reported existing frontend dependency audit warnings and a large bundle warning. They did not block deployment, but they remain follow-up hardening items.
