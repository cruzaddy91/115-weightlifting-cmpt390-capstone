# 115 Weightlifting

A full-stack web application for Olympic weightlifting coaches and athletes to manage structured training plans, log completion, track PR history, and calculate Sinclair scores.

## Project CLI

The app repo is now controlled through a single terminal entrypoint:

```bash
cd 115-weightlifting
./bin/zw help
```

The product name is `115 Weightlifting`. The local directory is `115-weightlifting/`.

Core commands:

- `./bin/zw setup`
- `./bin/zw doctor`
- `./bin/zw clean`
- `./bin/zw status`
- `./bin/zw migrate`
- `./bin/zw seed-demo`
- `./bin/zw reset-demo`
- `./bin/zw make-demo`
- `./bin/zw dev`
- `./bin/zw host-local start`
- `./bin/zw host-local stop`
- `./bin/zw host-local status`
- `./bin/zw logs`
- `./bin/zw backup`
- `./bin/zw export-data`
- `./bin/zw import-data <fixture.json> --yes`
- `./bin/zw restore --sqlite <backup.sqlite3> --yes`
- `./bin/zw report`
- `./bin/zw smoke`
- `./bin/zw test`
- `./bin/zw uat`
- `./bin/zw release`
- `./bin/zw prepare-public`

Report artifacts:

- `var/reports/REPORT.md`
- `var/reports/index.html`
- `var/reports/app_snapshot.json`
- `var/reports/UAT_REPORT.md`
- `var/reports/uat_latest.json`
- `var/reports/events/*.json`

Safe defaults:

- `./bin/zw clean` is preview-only unless you add `--yes`
- `./bin/zw reset-demo` is preview-only unless you add `--yes`
- `./bin/zw prune-demo` trims the database to **Headcoachone** (org head coach), **Coachone + five GoT**, and **Coachtwo + five LotR** (line coaches report to Headcoachone; **Adminone** kept as an extra head account). Preview without `--yes`. Use `--scrub-events` with `--yes` to clear `var/reports/events/*.json`
- `./bin/zw seed-coachtwo-lotr` creates **Coachtwo** and the first five **lord-of-the-rings** usernames, aligns bodyweights with `tools/sim/character_sim_profiles.py`, and bulk-seeds ~3 years of PR + workout logs (add `--with-programs` if the API is running and you want training programs too)
- **`./bin/zw backfill-demo-completion`** (with API up) runs `tools/sim/populate_history.py` for **Coachone+GoT** and **Coachtwo+LotR** so coach program rows get non-zero completion % and “x/y done” (not all zeros). Adds new programs each run; use a fresh DB or clear programs first if you want a clean list
- **`./bin/zw backfill-coach-completion`** (default **Coachtwo**; pass another name as first arg) only **PATCHes `completion_data`** for programs the coach **already** has — use this when you see **0/y** after `build_programs` and do not want extra programs

Quick reference:

- `config/CLI_CHEATSHEET.md`

## Current Feature Set

- JWT authentication with role-aware routing for `coach` and `athlete`
- Structured weekly training programs stored as JSON on each assigned program
- Coach dashboard for creating, editing, and reassigning weekly plans
- Athlete dashboard for completing prescribed exercises, adding logs, tracking PRs, and viewing charts
- Coach program editor shows the same three PR/trend charts for the assigned athlete (read-only; API allows only athletes who already appear on one of your saved programs)
- Coach home (program list) shows **roster-wide averages**: mean of each athlete’s monthly-best PR curves (Snatch, Clean & Jerk, Total) and mean of each athlete’s six-month rolling peak total (`rosterAverageMonthlyBestPrLineData`, `rosterAverageRollingPeakTotalLine` in `trainingCharts.js`)
- Athletes have optional **bodyweight (kg)** and **gender** (`M` / `F`) on the user record; the API exposes an IWF-style **competitive weight class** label (computed from body mass) on `/api/auth/me/`, the coach athlete list, and each program alongside `athlete_username`
- Sinclair score API and frontend calculator
- Django REST backend with SQLite-by-default and PostgreSQL-ready production settings

## Athlete PR charts & next-peak projection

The frontend builds three related series from the PR log in `src/frontend/src/utils/trainingCharts.js` (pure functions; Chart.js only renders the output).

1. **Monthly best (Snatch / Clean & Jerk / Total)** — For each calendar month and each lift, take the maximum logged weight. Missing months are skipped in the line (`spanGaps`) so long macrocycles stay readable.

2. **Peak rhythm & forecast (competition total only)** — Only `lift_type === 'total'` rows are used.
   - **Monthly envelope:** For every month from the first to the last total PR, store the best total in that month.
   - **Peak detection:** A month is a *peak* if (a) no higher finite total appears within ±2 months, and (b) its value is at least ~1.5 kg above the mean of other finite neighbors in that window (a cheap *prominence* filter to drop flat noise). Adjacent peak months are merged, keeping the higher total.
   - **Inter-peak spacing:** When there are ≥2 peaks, gaps (in months) between consecutive peaks are computed; the forecast uses the mean of the **last up to three** gaps as the expected cadence to the next high window.
   - **Projected month index:** `last_peak_index + round(mean_gap_months)`, extending the label axis with empty trailing months if needed.
   - **Projected kg:** Ordinary least squares (OLS) linear regression on `(month_index, peak_kg)` using the **last four** peak points, evaluated at the projected index. The value is then **clamped** to roughly the neighborhood of the last peak (not below ~94% or above ~106% of last peak) so the dashed segment stays a conservative planning hint rather than an extrapolation fantasy.

This is **not** a physiology or fatigue model; it is a lightweight **cadence + local trend** heuristic for meet planning. Block / mesocycle names are not stored on PR rows, so copy in the UI nudges athletes and coaches to correlate peaks with their own program notes.

3. **Six-month rolling peak total** — For each month end, the maximum competition total observed in that month or the five prior calendar months.

**Coach roster aggregates (home list):** For every assigned athlete on your programs, PRs are fetched in parallel (same `GET /api/athletes/prs/?athlete_id=` authorization as elsewhere). For each calendar month, the roster chart plots the **arithmetic mean** of the per-athlete monthly bests (each athlete contributes at most one value per lift per month—their own monthly max). Athletes with no data in that month are **omitted** from the average for that month (not counted as zero). The rolling chart applies the same idea to each athlete’s six-month rolling peak total series.

Unit tests for the chart builders live in `src/frontend/src/__tests__/trainingCharts.test.js`.

## Tech Stack

- Frontend: React with Vite, React Router, Chart.js
- Backend: Django REST Framework with SimpleJWT
- Database: SQLite locally, PostgreSQL in production
- Data science logic: Python Sinclair calculator reused in the backend analytics layer

## Project Structure

```text
115-weightlifting/   # current local directory name for 115 Weightlifting
├── src/
│   ├── frontend/           # React frontend application
│   ├── backend/            # Django REST API
│   ├── data-science/       # Python analytics scripts
│   └── infrastructure/     # Hosting config (Netlify)
├── docs/                   # App docs only
├── config/                 # Deployment notes
└── assets/                 # Static assets
```

Capstone turn-in documents live in the parent repo under `CMPT-390_CSCapstone/docs/`.

## Local Setup

### Frontend

```bash
cd 115-weightlifting/src/frontend
npm install
cp .env.example .env
npm run dev
```

Frontend runs on `http://localhost:3000`.

### Backend

```bash
cd 115-weightlifting/src/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

Backend runs on `http://localhost:8000`.

## Local Hosting

For a simple self-hosted local stack without Netlify:

```bash
cd 115-weightlifting
./bin/zw seed-demo
./bin/zw host-local start
```

This launches:

- frontend preview on `http://localhost:4173`
- backend on `http://localhost:8000`

See `config/self_hosting.md` for both local and public self-hosting plans.

## Main API Endpoints

- `POST /api/auth/register/`
- `POST /api/auth/token/`
- `GET|PATCH /api/auth/me/` (athletes only: `PATCH` accepts `bodyweight_kg`, `gender` — `M` or `F`; response includes computed `competitive_weight_class`)
- `GET|POST /api/programs/`
- `PATCH /api/programs/<id>/`
- `PATCH /api/programs/<id>/assign/`
- `GET|PATCH /api/athletes/program-completion/<program_id>/`
- `GET|POST /api/athletes/workouts/`
- `GET|POST /api/athletes/prs/` (coaches: `GET ...?athlete_id=<id>` — only athletes on your programs; see `apps/athletes/views.py`)
- `POST /api/analytics/sinclair/`

## Environment Variables

### Frontend

```text
VITE_API_BASE_URL=http://localhost:8000
```

### Backend

```text
SECRET_KEY=change-me
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CSRF_TRUSTED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

See `config/deployment.md` for hosting details.
See `config/self_hosting.md` for local and public self-hosting guidance.
