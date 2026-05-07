# UAT 3.0 close (SSVC and ACP) and UAT 4.0 kickoff

Last updated: May 5, 2026

Use this note when you are back from exams: it records **what to capture for a clean UAT 3.0 close** and **where UAT 4.0 planning lives**.

---

## UAT 3.0 close: SSVC

**SSVC** here means the full Docker validation script: `scripts/validate_docker_stack.sh`.

It:

1. Brings up the stack (`docker compose up --build -d`).
2. Waits for backend (`/api/auth/me/` 401) and frontend (200).
3. Runs **`prune_demo_users --apply --permanent-clean`** (before UAT) to reset canonical demo and strip UAT leftovers.
4. Runs **`scripts/docker_uat.py`** and writes **`validation-reports/docker_uat_latest.json`**.
5. Runs auth stress for `008_Coach_eight` and `000_Athlete_zero`.
6. Runs **prune again** (after UAT) and collects compose/log artifacts.

**Artifacts to keep for a formal close** (under `validation-reports/`):

| Artifact | Use |
|----------|-----|
| `docker_uat_latest.json` | Full UAT result list plus summary metrics |
| `docker_validation_summary_latest.md` | Human-readable summary |
| `ssvc_clean_before_uat_latest.txt` | Prune output before UAT |
| `ssvc_clean_after_uat_latest.txt` | Prune output after UAT |
| `auth_stress_*_latest.json` | Token/login stress |
| `compose_ps_latest.txt`, `backend_logs_latest.txt`, … | Environment sanity |

### Metrics to paste into a PR or report (from `docker_uat_latest.json`)

At the **top level** of the JSON (not nested under `results`):

- `started_at`, `finished_at`
- `backend_url`, `frontend_url`
- `total`, `passed`, `failed`, `pass_rate`

Under **`ssvc_metrics`** (subset for dashboards):

- `checks_total`, `checks_passed`, `checks_failed`, `pass_rate`
- `frontend_head_dashboard_bundle`: detail blob for the check **"frontend bundle includes head skill-roster stamp and not stale athlete-table combo"** (catches stale `dist` / wrong bundle)

**Green bar for UAT 3.0 close:** `failed == 0` and `pass_rate == 1.0` (or equivalent: `checks_failed == 0`). Any non-passing row in `results` should be investigated before calling SSVC done.

**Common gotchas:**

- Rebuild **frontend** when Head Dashboard or login/register UI changes so `dist` matches source (stale bundle fails the check above).
- Rebuild **backend** when URL routes or serializers change.
- Registration throttle: UAT script spaces registrations; if you run many manual signups, watch `429`.

---

## UAT 3.0 close: ACP

**ACP** in this repo’s history is **merge/push to the integration branch** used for cabinet/SSVC work (see `docs/UAT_HANDOFF.md`: `dev/ssvc-acp-cabinet`). Adjust the branch name if your team renamed it.

**Minimal ACP checklist after SSVC is green:**

1. `docker compose build` (or `validate_docker_stack.sh` which builds on `up`) with **current** `115-weightlifting` sources.
2. SSVC script completes with `Docker validation passed`.
3. Copy `ssvc_metrics` + pass/fail counts into the PR description.
4. Merge to the agreed integration branch; tag or milestone “UAT 3.0 SSVC green” if your course requires it.

---

## After exams: UAT 4.0

**Rolling backlog (features, education, schedule, POS ideas):**  
`docs/UAT_4_ROLLING_NOTES.md`

**Recent technical notes already merged into UAT 3.x** (so UAT 4 can build on them without re-deriving):

- Docker UAT batch athletes use **canonical handles** `Athlete17`–`Athlete31` (final usernames `NNN_Athlete#`); singles `Athlete32`–`Athlete35`; stress assertions expect **unique, strictly increasing** numeric prefixes (smallest-free behavior).
- **`GET /api/auth/register/coach-prefixes/`** lists free `000` / `005`–`099` prefixes for coach signup UX.
- **`prune_demo_users --permanent-clean`** also removes `NNN_Athlete17`–`NNN_Athlete35` pattern users so canonical-stress accounts do not accumulate.

Add new UAT 4.0 items only in **`UAT_4_ROLLING_NOTES.md`** so one file stays the source of truth for product ideas.

---

## One-liner post-exam smoke

From repo root (with Docker running):

```sh
./scripts/validate_docker_stack.sh
```

Then open `validation-reports/docker_validation_summary_latest.md` and confirm status **PASS**.
