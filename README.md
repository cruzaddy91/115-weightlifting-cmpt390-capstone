# 115 Weightlifting CMPT-390 Capstone

| Field | Detail |
| --- | --- |
| **Instructor** | Dr. Hu Helen |

115 Weightlifting is a full-stack capstone project for Olympic weightlifting coaches and athletes. It supports role-aware dashboards for head coaches, line coaches, and athletes; structured training program creation and assignment; athlete workout completion; personal record tracking; charts; roster analytics; and Sinclair scoring.

This repository is the professor-facing, Docker-ready version of the project. It is intended to be cloned and launched locally with Docker Compose, without requiring a local Python, Node, or PostgreSQL setup.

## Quick Launch

Prerequisite: Docker Desktop or Docker Engine with Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- Frontend: <http://localhost:4173>
- Backend API: <http://localhost:8000>

The first backend startup runs migrations and, by default, seeds demo data because `SEED_DEMO=true` in `.env.example`.

### Deployment tiers by Git branch (convention)

**Sandbox** work stays informal on **`main`**, topic branches, or your integration line (e.g. **`dev/ssvc-acp-cabinet`**). Nothing here defines or creates a separate “sandbox” Git branch — use whatever workflow you already prefer.

**Packaging** branches carry tier-specific deployment layouts:

| Branch | Focus |
| --- | --- |
| **`pkg_large`** | **Large-scale deployment package** — current priority. Uses LARGE Compose merge ([`docker-compose.large.yml`](docker-compose.large.yml)), [`env.large.example`](env.large.example), and [`docs/DEPLOYMENT_LARGE.md`](docs/DEPLOYMENT_LARGE.md). Run stakeholder **UAT** from artifacts committed on **`pkg_large`**. |
| **`pkg_medium`** | Medium-tier deployment layout (**planned**). |
| **`pkg_small`** | Small-tier deployment layout (**planned**). |

Nothing in this repository creates or pushes Git branches automatically.

**Git note:** while **`dev/ssvc-acp-cabinet`** exists, Git cannot also hold a sibling branch named exactly **`dev`** — only rename/move integration branches if you need that literal name.

**Integration baseline:** document whether **`dev/ssvc-acp-cabinet`** or **`main`** is canonical until **`pkg_large`** is promoted — avoid silent divergence.

**Mini-sprint rhythm:** after each sprint on your integration branch (or **`pkg_large`** prep), run [`scripts/validate_docker_stack.sh`](scripts/validate_docker_stack.sh) on `.env.example` plus base **`docker-compose.yml`**. Inspect **`docker_validation_summary_latest.md`** and companion JSON under **`validation-reports/`** (directory is gitignored — fine for local metrics). At **ACP**, point **`pkg_large`** at the commit that passed SSVC and your LARGE checklist in [`docs/DEPLOYMENT_LARGE.md`](docs/DEPLOYMENT_LARGE.md).

### Large-business stack (`pkg_large`)

**Run the LARGE package now (isolated Compose project, does not touch demo `.env`):**

```bash
./scripts/up_pkg_large.sh
```

- Uses `.env.pkg_large` (created from [`env.large.local.example`](env.large.local.example); gitignored).
- **`COMPOSE_PROJECT_NAME=pkg_large`** so Postgres volume/network does not collide with a demo stack on the default project name.
- **Alternate host ports** — UI **http://localhost:4174**, API **http://localhost:8001**, Postgres **localhost:5433** — so you do **not** need to stop the demo stack on **4173 / 8000 / 5432** (change ports via **`PKG_LARGE_HOST_*`** in `.env.pkg_large` if these clash).
- **`DEBUG=False`**, multi-worker Gunicorn, **no demo seed** — database starts empty; register via the UI or `docker compose exec` `createsuperuser` (see [`docs/DEPLOYMENT_LARGE.md`](docs/DEPLOYMENT_LARGE.md)).

Production-shaped hosts/TLS/SMTP: copy [`env.large.example`](env.large.example) into `.env.pkg_large` (or your secrets store), merge the same three Compose files, and place Django behind HTTPS.

See [`docs/DEPLOYMENT_LARGE.md`](docs/DEPLOYMENT_LARGE.md) for TLS, `SECRET_KEY`, `DATABASE_URL`, and email checklist items.

## Demo Credentials

All demo accounts use this password:

```text
Passw0rd!123
```

Suggested walkthrough accounts (canonical shape `{XXX}_{HeadCoach|Coach|Athlete}_{verbal}`; `117_HeadCoachGM` is the only GM exception):

| Role | Username(s) | URL |
| --- | --- | --- |
| GM head coach | `117_HeadCoachGM` | <http://localhost:4173/head> |
| AGM lane heads (`001`–`004`) | `001_HeadCoach_one`, `002_HeadCoach_two`, `003_HeadCoach_three`, `004_HeadCoach_four` | <http://localhost:4173/head> |
| Line coaches slot A | `008_Coach_eight`, `013_Coach_onethree`, `048_Coach_foureight`, `088_Coach_eighteight` | <http://localhost:4173/coach> |
| Line coaches slot B | `022_Coach_twotwo`, `023_Coach_twothree`, `024_Coach_twofour`, `025_Coach_twofive` | <http://localhost:4173/coach> |
| Primary demo athlete | `000_Athlete_zero` | <http://localhost:4173/athlete> |
| Other seeded canon athletes | **31** accounts using prefixes `005`, `006`, `007`, `009`, …, `041` (normal-member slots only; coach/AGM prefixes are skipped — see `CANONICAL_ATHLETE_PREFIXES_32` in [`canonical_usernames.py`](115-weightlifting/src/backend/apps/accounts/canonical_usernames.py)) | <http://localhost:4173/athlete> |

The **`pkg_large`** local merge (`env.large.local.example` → `.env.pkg_large`) seeds **`pkg_large`** provisioning by default: **1 GM + 4 AGM heads + 8 line coaches + 32 athletes** with the canonical naming rules above.

The `000_Athlete_zero` account is seeded with assigned programs, workout logs, personal records, and completion records so the athlete dashboard has meaningful data (Docker compose defaults still run **`preserve_current`**; LARGE overrides usually run **`pkg_large`**).
The **31** other seeded canon athletes are intentionally active with **no** accountable coach so the GM dashboard can exercise manual assignment to either a head coach or a line coach. They display with the `XXX_UNASSIGNED` organization tag until assigned.

New accounts require a unique email address. Athlete registration accepts a base username and assigns the next available normal member prefix automatically (`000_`, then `005_` through `099_`). Line coaches must select an available normal member prefix from that same pool. Reserved GM/AGM organization prefixes (`001_`, `002_`, `003_`, `004_`, and `117_`) are blocked for normal coach and athlete accounts. Head coaches outside the `117` and `001-004` category lanes display with the `XXX_UNASSIGNED` organization tag until intentionally provisioned. Password reset is available from the login screen; in this Docker/local review build, reset emails are printed to backend logs instead of sent through a real SMTP provider.

## Access Control Expectations

The seeded users are demo accounts for exercising each role. The core access rules are:

- A head coach represents the organization owner/admin for their own organization.
- A line coach can create and manage programming only for athletes assigned to that coach.
- An athlete has one accountable `primary_coach` at a time. That coach can be either a line coach or the head coach.
- Athletes can view and update only their own assigned programs, workout logs, personal records, and completion data.
- Head-coach organization endpoints are blocked for line coaches and athletes.

## Docker Services

`docker-compose.yml` starts three services:

| Service | Purpose |
| --- | --- |
| `postgres` | PostgreSQL 16 database with a persistent Docker volume. |
| `backend` | Django REST backend served by Gunicorn on port `8000` (default worker count is configurable via `GUNICORN_WORKERS`; see `docker-compose.large.yml`). |
| `frontend` | React/Vite frontend served by Vite preview on port `4173`. |

Useful commands:

```bash
# Start/rebuild everything
docker compose up --build

# Start in the background
docker compose up --build -d

# Stop containers
docker compose down

# Stop and remove seeded database volume
docker compose down -v

# View backend logs
docker compose logs -f backend
```

## Smoke / stress validation (Docker SSVC)

From a fresh clone (or anytime dependencies change), run the closed-loop Docker harness:

```bash
./scripts/validate_docker_stack.sh
```

It creates `.env` if needed, validates `docker compose config`, brings up Postgres/backend/frontend, waits for `/api/auth/me/` and the SPA, runs `prune_demo_users` before and after, executes `docker_uat.py` (full HTTP acceptance + RBAC + bundle fingerprint), runs JWT auth stress loops (`STRESS_CYCLES`, default **25**), and writes evidence under `validation-reports/` (usually gitignored).

## Deep SSVC (smoke, stress, validate, clean-audit)

Use this before a major merge or portfolio freeze when you want more than the Docker UAT loop alone:

```bash
chmod +x scripts/run_deep_ssvc.sh scripts/ssvc_clean_audit.sh scripts/ssvc_sync_uat_floor.sh
STRESS_CYCLES=60 ./scripts/run_deep_ssvc.sh
```

Phases:

| Phase | What |
| --- | --- |
| **Smoke** | `docker compose config` parse; `security_gate.py` on tracked files (no running stack). |
| **Stress + stack** | Same as [`scripts/validate_docker_stack.sh`](scripts/validate_docker_stack.sh): compose up, UAT JSON, JWT stress (override `STRESS_CYCLES`, default **60** in `run_deep_ssvc`). |
| **Validate** | `manage.py test` in `backend`, `npm test` (Vitest) in `frontend` (expects the stack still running). |
| **Manifest** | `ssvc_verify_manifest.py`: UAT must be green; **required** check substrings in [`scripts/ssvc_uat_required_names.txt`](scripts/ssvc_uat_required_names.txt). Count floor in [`scripts/ssvc_uat_floor.txt`](scripts/ssvc_uat_floor.txt): **0** disables shrink detection until you lock it. |
| **Clean (audit)** | Writes `validation-reports/ssvc_clean_audit_latest.txt` (deprecation grep hits, sample `pass` stubs); does not delete code. |

**Lock the UAT count bar** after a green `validate_docker_stack` (optional but recommended for regression discipline):

```bash
./scripts/ssvc_sync_uat_floor.sh
```

**When you add a feature**, add at least one new assertion in `scripts/docker_uat.py` and add a stable substring to `scripts/ssvc_uat_required_names.txt` so the manifest fails until the new surface is covered.

```text
scripts/
├── validate_docker_stack.sh   # demo-stack SSVC (compose + UAT + stress + prune)
├── run_deep_ssvc.sh           # smoke + stack + Django tests + Vitest + manifest + clean audit
├── ssvc_verify_manifest.py    # UAT JSON gates
├── ssvc_uat_floor.txt         # 0 = off; sync after green run to lock count
├── ssvc_uat_required_names.txt
├── ssvc_sync_uat_floor.sh     # set floor from docker_uat_latest.json
├── ssvc_clean_audit.sh        # deprecation / stub report only
├── docker_uat.py
├── docker_auth_stress.py
└── security_gate.py
```

## Environment

Copy `.env.example` to `.env` before launch. The defaults are intended for local Docker review only.

Important settings:

- `DATABASE_URL`: points Django to the Postgres container.
- `SECRET_KEY`: replace before any real deployment.
- `DEBUG`: defaults to `True` for local review.
- `CORS_ALLOWED_ORIGINS`: allows the frontend at `http://localhost:4173`.
- `VITE_API_BASE_URL`: points the built React app at `http://localhost:8000`.
- `SEED_DEMO`: set to `false` if you do not want startup demo data.

## Project Layout

```text
115_weightlifting_CMPT390_Capstone/
├── docker-compose.yml
├── docker-compose.large.yml      # LARGE overrides (workers, limits)
├── docker-compose.pkg_large.yml # backend env_file → .env.pkg_large
├── .env.example
├── env.large.example            # production-shaped LARGE env template
├── env.large.local.example      # localhost LARGE template → .env.pkg_large
├── docs/
│   └── DEPLOYMENT_LARGE.md      # checklist + pkg_large bring-up
├── LICENSE
├── README.md
├── assets/                       # Branding (Westminster logo, used by report titlepage)
├── report/                       # Quarto source + rendered PDF for the capstone write-up
├── scripts/
│   ├── validate_docker_stack.sh  # demo-stack SSVC
│   ├── run_deep_ssvc.sh          # full smoke / stress / validate / manifest / clean audit
│   ├── docker_uat.py
│   ├── ssvc_verify_manifest.py
│   ├── ssvc_uat_floor.txt
│   ├── ssvc_uat_required_names.txt
│   ├── ssvc_sync_uat_floor.sh
│   ├── ssvc_clean_audit.sh
│   └── up_pkg_large.sh           # bring up pkg_large Compose project
└── 115-weightlifting/
    ├── src/backend/      # Django REST API, Dockerfile, Docker entrypoint
    ├── src/frontend/     # React/Vite app, Dockerfile
    └── README.md         # Source directory note
```

## Final Report

The capstone write-up lives under [`report/`](report/):

- Source: [`report/CMPT390_115_Report.qmd`](report/CMPT390_115_Report.qmd) (Quarto, two-column scrartcl)
- Rendered: `report/output/CMPT390_115_Report.pdf`
- Re-render with `quarto render report/CMPT390_115_Report.qmd --to pdf`

Brand assets and the Westminster logo used by the report titlepage live under [`assets/png/`](assets/png/).

## Notes On Production

This Docker setup is designed for local evaluation. For a public production deployment, the main follow-up work would be:

- Set `DEBUG=False`.
- Use a strong `SECRET_KEY`.
- Set real `ALLOWED_HOSTS`, CORS, and CSRF origins.
- Put the backend behind HTTPS.
- Serve the built frontend through a production static server such as Nginx or Caddy, or deploy it separately to a static hosting provider.

## License

MIT. See `LICENSE`.
