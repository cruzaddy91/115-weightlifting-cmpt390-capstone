# 115 Weightlifting CMPT-390 Capstone

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

Day-to-day professor/demo review keeps **`.env.example`** plus base **`docker-compose.yml`** (`DEBUG=True`, demo seed). For the LARGE-shaped Compose stack (more Gunicorn workers, no demo seed, optional resource hints), merge the override file and copy **`env.large.example`** to **`.env`** (then edit secrets and domains):

```bash
cp env.large.example .env   # then edit secrets and domains
docker compose -f docker-compose.yml -f docker-compose.large.yml up --build
```

See [`docs/DEPLOYMENT_LARGE.md`](docs/DEPLOYMENT_LARGE.md) for TLS, `SECRET_KEY`, `DATABASE_URL`, and email checklist items.

## Demo Credentials

All demo accounts use this password:

```text
Passw0rd!123
```

Suggested walkthrough accounts:

| Role | Username | URL |
| --- | --- | --- |
| GM head coach | `117_HeadcoachGM` | <http://localhost:4173/head> |
| Standalone head coaches | `118_Headcoachtwo`, `119_Headcoachthree`, `120_Headcoachfour`, `121_Headcoachone` | <http://localhost:4173/head> |
| Primary line coach | `008_Coachone` | <http://localhost:4173/coach> |
| Demo line coaches | `013_Coachtwo`, `048_Coachthree`, `088_Coachtfour` | <http://localhost:4173/coach> |
| Athlete | `000_Athlete1` | <http://localhost:4173/athlete> |
| Unassigned athletes | `005_Athlete2` through `021_Athlete16`, skipping `008_` and `013_` because those prefixes belong to line coaches | <http://localhost:4173/athlete> |

The `000_Athlete1` account is seeded with assigned programs, workout logs, personal records, and completion records so the athlete dashboard has meaningful data.
The 15 unassigned athlete accounts are intentionally active with no accountable coach so the GM dashboard can exercise manual assignment to either a head coach or a line coach. They display with the `XXX_UNASSIGNED` organization tag until assigned.

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

## Smoke / Stress Validation

After the stack is running, or from a fresh clone, run the Docker-first validation harness:

```bash
scripts/validate_docker_stack.sh
```

The harness:

- creates `.env` from `.env.example` if needed;
- validates `docker compose config`;
- starts the Postgres, backend, and frontend containers;
- waits for backend and frontend readiness;
- verifies the seeded demo accounts;
- runs SSVC cleanup so old Docker/UAT/demo leftovers are permanently removed while canonical demo users remain;
- runs an API UAT flow for program creation, assignment, completion, workout logs, PRs, and Sinclair analytics;
- verifies email uniqueness and the password-reset flow;
- checks RBAC denial paths for cross-coach and cross-athlete access;
- verifies category/color metadata for the head-coach roster;
- runs auth stress cycles for `008_Coachone` and `000_Athlete1`.

Generated validation output is written to `validation-reports/`, which is intentionally ignored by Git.

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
├── docker-compose.large.yml   # optional merge file for large-business Compose
├── .env.example
├── env.large.example         # LARGE-tier env template (copy to .env with merge compose)
├── docs/
│   └── DEPLOYMENT_LARGE.md    # large-business checklist
├── LICENSE
├── README.md
├── scripts/            # Docker smoke/stress validation harness
└── 115-weightlifting/
    ├── src/backend/      # Django REST API, Dockerfile, Docker entrypoint
    ├── src/frontend/     # React/Vite app, Dockerfile
    └── README.md         # Source directory note
```

## Notes On Production

This Docker setup is designed for local evaluation. For a public production deployment, the main follow-up work would be:

- Set `DEBUG=False`.
- Use a strong `SECRET_KEY`.
- Set real `ALLOWED_HOSTS`, CORS, and CSRF origins.
- Put the backend behind HTTPS.
- Serve the built frontend through a production static server such as Nginx or Caddy, or deploy it separately to a static hosting provider.

## License

MIT. See `LICENSE`.
