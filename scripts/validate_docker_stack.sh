#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/validation-reports"
ENV_FILE="$ROOT_DIR/.env"
ENV_EXAMPLE="$ROOT_DIR/.env.example"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:4173}"
DEMO_PASSWORD="${DEMO_PASSWORD:-Passw0rd!123}"
UAT_COACH_SIGNUP_CODE="${UAT_COACH_SIGNUP_CODE:-docker-uat-coach}"
STRESS_CYCLES="${STRESS_CYCLES:-25}"

mkdir -p "$REPORT_DIR"

ensure_env_file() {
  if [ ! -f "$ENV_FILE" ]; then
    if [ ! -f "$ENV_EXAMPLE" ]; then
      echo "Missing .env and .env.example; cannot bootstrap Docker environment." >&2
      exit 1
    fi
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    echo "Created .env from .env.example"
  fi
}

ensure_env_key() {
  key="$1"
  value="$2"
  if ! grep -q "^${key}=" "$ENV_FILE"; then
    printf '\n%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

env_value() {
  key="$1"
  value="$(grep "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true)"
  printf '%s' "$value"
}

wait_for_url() {
  name="$1"
  url="$2"
  expected="$3"
  attempts="${4:-60}"
  delay="${5:-2}"
  count=1
  while [ "$count" -le "$attempts" ]; do
    code="$(curl -sS -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || true)"
    if [ "$code" = "$expected" ]; then
      echo "$name reachable at $url ($code)"
      return 0
    fi
    echo "Waiting for $name at $url; attempt $count/$attempts returned ${code:-no response}"
    sleep "$delay"
    count=$((count + 1))
  done
  echo "$name did not become reachable at $url with expected status $expected" >&2
  return 1
}

write_summary() {
  status="$1"
  cat > "$REPORT_DIR/docker_validation_summary_latest.md" <<EOF
# Docker stack validation report

**Semi-automated SSVC** · Compose · Django REST · React · PostgreSQL

*Artifacts directory: \`validation-reports/\`*

| Field | Value |
| ----- | ----- |
| **Overall status** | **$status** |
| **Recorded (UTC)** | $GEN_TS |

---

> **Executive snapshot:** This run exercises the live Compose stack (Postgres, Gunicorn-backed Django API, Vite-built SPA preview), resets canonical demo users, executes the full HTTP acceptance suite, stresses JWT login paths, then cleans up and freezes logs. Detailed checks live in \`docker_uat_latest.json\` (\`results\` plus \`ssvc_metrics\`, including the **head-dashboard bundle fingerprint** guard).

---

## Contents

| # | Section |
| --- | --------- |
| **Fig.** | [Architecture diagram](#architecture-diagram) |
| **1** | [Validation snapshot](#1-validation-snapshot) |
| **2** | [Artifacts (expanded catalog)](#2-artifacts-expanded-catalog) |
| **3** | [Services and networking](#3-services-and-networking) |
| **4** | [Repository layout](#4-repository-layout) |
| **5** | [Languages and runtime fingerprint](#5-languages-and-runtime-fingerprint) |
| **6** | [Pinned dependencies](#6-pinned-dependencies) |
| **7** | [Provisioning sequence](#7-provisioning-sequence) |
| **8** | [HTTP API surface](#8-http-api-surface) |
| **9** | [System summary](#9-system-summary) |
| **10** | [Artifact filenames (index)](#10-artifact-filenames-index) |

---

## Architecture diagram

### SSVC — definition and origin

**What SSVC means here:** Your capstone docs (\`docs/UAT_3_SSV_ACP_CLOSE_AND_UAT4_KICKOFF.md\`) define **SSVC** operationally as the full Docker validation workflow driven by **\`scripts/validate_docker_stack.sh\`**. It is **project shorthand**, not an external certification standard.

**Readable expansion:** *Semi-automated Stack Verification & Cleanup* — **verification** = scripted HTTP/API gates (\`docker_uat.py\`, bundle fingerprinting in \`ssvc_metrics\`, JWT stress loops); **cleanup** = \`prune_demo_users --apply --permanent-clean\` **before and after** the suite so canonical demo users stay sane and UAT-created registrations do not linger.

**Purpose:** The stack is **Docker-first** with repeatable demos and integration merges (**ACP** = merging after SSVC is green). Manual testing alone cannot reproduce identical evidence each run; SSVC freezes **pass/fail**, **versions**, and **logs** under \`validation-reports/\` so a passing stack maps to archived artifacts.

### Runtime topology

Browser plus host-side harness against the Compose stack:

\`\`\`mermaid
flowchart TB
  subgraph HOST["Host machine"]
    direction TB
    BR["Browser / operator"]
    HV["SSVC harness<br/>shell + Python 3<br/>docker_uat.py · docker_auth_stress.py"]
  end

  subgraph COMPOSE["Docker Compose network"]
    direction TB
    FE["frontend · :4173<br/>React SPA · Vite preview"]
    BE["backend · :8000<br/>Gunicorn · Django · DRF · JWT"]
    PG[("postgres · :5432<br/>PostgreSQL 16 · postgres_data volume")]
  end

  BR -->|"loads HTML/CSS/JS"| FE
  BR -->|"REST · /api/* · JWT + refresh cookie"| BE
  HV -->|"health + bundle checks"| FE
  HV -->|"HTTP acceptance suite · evidence JSON"| BE
  BE -->|"DATABASE_URL · psycopg2"| PG
\`\`\`

### Dependency build chain

Manifests → images → running stack:

\`\`\`mermaid
flowchart LR
  subgraph SRC["Declared in repository"]
    DC["docker-compose.yml"]
    REQ["requirements.txt"]
    PKG["package.json<br/>package-lock.json"]
  end

  REQ --> BEIMG["Backend image<br/>Python 3.12 · Django"]
  PKG --> FEIMG["Frontend image<br/>Node 20 · Vite build"]
  DC --> BEIMG
  DC --> FEIMG
  DC --> PGIMG["postgres:16-alpine"]

  BEIMG --> RUN["Compose up:<br/>backend · frontend · postgres"]
  FEIMG --> RUN
  PGIMG --> RUN
\`\`\`

### SSVC pipeline (single closed loop)

Order enforced by \`validate_docker_stack.sh\`:

\`\`\`mermaid
flowchart TB
  A["compose config → validation-reports"] --> B["compose up --build -d"]
  B --> C["Wait: /api/auth/me 401 · frontend 200"]
  C --> D["prune_demo_users · before"]
  D --> E["docker_uat.py → docker_uat_latest.json"]
  E --> F["auth stress coach + athlete"]
  F --> G["prune_demo_users · after"]
  G --> H["compose ps + service logs + this summary"]
\`\`\`

### Optional supplementary diagrams

| Diagram type | Subject matter |
| -------------- | ---------------- |
| \`sequenceDiagram\` | JWT obtain → authenticated requests → refresh rotation (\`httpOnly\` cookie + Bearer access token). |
| \`flowchart\` | Django apps \`accounts\`, \`programs\`, \`athletes\`, \`analytics\`, \`competitions\` mapped to \`/api/\` prefixes. |
| \`erDiagram\` | Core entities (\`User\`, programs, completions, PRs) and their relationships. |
| High-level context (single view) | Client browser → SPA → REST API → database (boundary overview). |

---

## 1. Validation snapshot

| Dimension | Value |
| --------- | ------- |
| Backend API | \`$BACKEND_URL\` |
| Frontend SPA (preview) | \`$FRONTEND_URL\` |
| Auth stress cycles / account | **$STRESS_CYCLES** |
| Evidence bundle | \`docker_uat_latest.json\` |

### Gate counts (\`docker_uat_latest.json\`)

| Metric | Value |
| ------ | ------- |
| Checks total | ${UAT_TOTAL:-n/a} |
| Passed | ${UAT_PASSED:-n/a} |
| Failed | ${UAT_FAILED:-n/a} |
| Pass rate | ${UAT_PASS_RATE:-n/a} |

---

## 2. Artifacts (expanded catalog)

| Artifact | Purpose |
| ---------- | --------- |
| \`docker_uat_latest.json\` | Full SSVC / API acceptance transcript: per-check outcomes, timing, \`ssvc_metrics\`, and \`frontend_head_dashboard_bundle\` (detects stale Vite \`dist\` vs current Head Dashboard sources). |
| \`auth_stress_008_coach_eight_latest.json\` | Repeated obtain / refresh for line coach \`008_Coach_eight\`; surfaces throttle or token rotation defects. |
| \`auth_stress_000_athlete_zero_latest.json\` | Same pattern for athlete \`000_Athlete_zero\`. |
| \`ssvc_clean_before_uat_latest.txt\` | Output of \`prune_demo_users --apply --permanent-clean\` **before** the HTTP suite — canonical roster baseline. |
| \`ssvc_clean_after_uat_latest.txt\` | Same command **after** the suite — removes registrations created during SSVC. |
| \`compose_config_latest.txt\` | Rendered \`docker compose config\` (authoritative merged stack definition). |
| \`compose_ps_latest.txt\` | Container status snapshot after validation. |
| \`backend_logs_latest.txt\` | Tail of backend logs (Gunicorn worker + Django). |
| \`frontend_logs_latest.txt\` | Tail of frontend \`vite preview\` logs. |
| \`postgres_logs_latest.txt\` | Tail of database logs. |

---

## 3. Services and networking

| Service | Definition | Published port | Responsibility |
| --------- | ------------ | ---------------- | ------------------ |
| **postgres** | Image \`postgres:16-alpine\` | **5432** | System of record; volume \`postgres_data\`. |
| **backend** | Build \`115-weightlifting/src/backend\` | **8000** | Django + Gunicorn, JWT, admin, REST surface. |
| **frontend** | Build \`115-weightlifting/src/frontend\` | **4173** | Production build served via \`vite preview\` (not dev HMR). |

Compose network DNS: \`postgres\`, \`backend\`, \`frontend\`. Backend connects with \`DATABASE_URL\`.

---

## 4. Repository layout

| Path | Role |
| ------ | ------ |
| \`docker-compose.yml\` | Orchestrates three services + named volume. |
| \`.env\`, \`.env.example\` | Configuration and secrets (copy example → local \`.env\`; never commit secrets). |
| \`115-weightlifting/src/backend/\` | Django project (\`config/\`), domain apps (\`apps/*\`), \`requirements.txt\`. |
| \`115-weightlifting/src/frontend/\` | React SPA (\`src/pages\`, \`services/api\`, tests). |
| \`scripts/validate_docker_stack.sh\` | **SSVC driver**: compose, health waits, prune, \`docker_uat.py\`, stress scripts, this summary. |
| \`scripts/docker_uat.py\` | Host-side HTTP acceptance harness. |
| \`scripts/docker_auth_stress.py\` | Targeted login / refresh stress helper. |
| \`validation-reports/\` | Generated artifacts for audits (often gitignored). |

---

## 5. Languages and runtime fingerprint

### Stack by layer

| Layer | Technologies |
| ------- | ---------------- |
| Backend | **Python** (\`python:3.12-slim\`; measured **${BACKEND_PY_VER:-unknown}**), Django ORM, Django REST Framework |
| Frontend | **JavaScript**, **React 18**, **Vite 5** (\`npm run build\` → static bundle + preview) |
| Persistence | **PostgreSQL 16**, accessed via **psycopg2** |
| Automation | **POSIX shell** + **Python 3** on the host (Docker CLI orchestration) |

### Measured versions (at summary generation)

| Component | Version |
| --------- | --------- |
| Python (backend container) | ${BACKEND_PY_VER:-unknown} |
| Django | ${DJANGO_VER:-unknown} |
| Gunicorn | ${GUNICORN_VER:-unknown} |
| Node (frontend container) | ${NODE_VER:-unknown} |
| Docker Engine (host) | ${DOCKER_VER:-unknown} |
| Docker Compose (host) | ${COMPOSE_VER:-unknown} |

---

## 6. Pinned dependencies

### Backend (\`115-weightlifting/src/backend/requirements.txt\`)

| Package | Pin |
| --------- | ----- |
| Django | **4.2.7** |
| djangorestframework | **3.14.0** |
| djangorestframework-simplejwt | **5.3.0** |
| django-cors-headers | **4.3.1** |
| psycopg2-binary | **2.9.9** |
| gunicorn | **23.0.0** |
| python-dotenv | **1.0.0** |
| scikit-learn / joblib | **1.8.0** / **1.5.3** |

### Frontend (\`115-weightlifting/src/frontend/package.json\`)

| Package | Range |
| --------- | ------- |
| react / react-dom | **^18.2.0** |
| react-router-dom | **^6.20.0** |
| axios | **^1.6.2** |
| chart.js / react-chartjs-2 | **^4.4.0** / **^5.2.0** |
| xlsx / xlsx-js-style | spreadsheet import/export |

Transitive lockfile: **\`package-lock.json\`** (installed with \`npm ci\` in Docker).

---

## 7. Provisioning sequence

| Step | Action |
| :---: | -------- |
| 1 | Emit resolved Compose YAML → \`compose_config_latest.txt\`. |
| 2 | \`docker compose up --build -d\` (images rebuild when Dockerfiles or deps change). |
| 3 | Wait until \`/api/auth/me/\` → **401** and frontend root → **200**. |
| 4 | Pre-suite **prune** (\`prune_demo_users --apply --permanent-clean\`). |
| 5 | Run \`docker_uat.py\` → writes \`docker_uat_latest.json\`. |
| 6 | Auth stress (coach + athlete JSON artifacts). |
| 7 | Post-suite **prune** again. |
| 8 | Capture \`compose ps\` and service logs into \`validation-reports/\`. |

**Backend container boot** (\`docker-entrypoint.sh\`): wait for Postgres → \`migrate\` → \`collectstatic\` → optional \`provision_uat3_demo\` when \`SEED_DEMO=true\` (\`UAT3_DEMO_SCENARIO\`, default \`preserve_current\`) → **Gunicorn** \`:8000\`.

---

## 8. HTTP API surface

Base URL for JSON: **\`$BACKEND_URL\`**

### Top-level prefixes

| Prefix | Scope |
| ------ | ------- |
| \`/admin/\` | Django administration |
| \`/api/auth/\` | Registration, JWT pair + refresh cookie flow, \`/me/\`, athlete listing, **head org** routes (\`/api/auth/head/...\`), coach-prefix discovery |
| \`/api/programs/\` | Program CRUD + assignment |
| \`/api/athletes/\` | Workouts, PRs, completion payloads |
| \`/api/competitions/\` | Reserved (may be minimal / stub) |
| \`/api/analytics/\` | Sinclair / Robi-style analytics; **head-gated** dashboards under \`/api/analytics/head/...\` |

### Representative routes

| Area | Examples |
| ------ | ---------- |
| Programs | \`GET\`/\`POST\` \`/api/programs/\`, \`/api/programs/<id>/\`, assign |
| Athletes | \`/api/athletes/workouts/\`, \`/api/athletes/prs/\`, \`/api/athletes/program-completion/<id>/\` |
| Analytics | \`/api/analytics/sinclair/\`, \`/api/analytics/head/model-status/\`, … |

**Security vocabulary:** short-lived **JWT access** (Authorization bearer) plus **httpOnly refresh cookie** from the SPA (\`withCredentials\`). Org-facing UX labels (**GMHC**, **AGMHC**, **LC**) map from \`user_type\` and numeric username prefixes — see \`apps.accounts.org_labels\`.

---

## 9. System summary

| Area | Summary |
| ------ | ---------------- |
| Architecture | Three-tier separation: React SPA ↔ REST ↔ Postgres; Compose encodes **CORS** and **CSRF trusted origins** for the preview origin. |
| Verification | SSVC yields repeatable evidence across RBAC, registration flows, analytics endpoints, and **bundle drift** detection (\`frontend_head_dashboard_bundle\`). |
| Identity model | Prefix-scoped org lanes (\`117_\` GM hub, \`001_\`–\`004_\` AGM lanes, normal pools for members); enforced server-side and covered by Docker UAT. |
| Hardening | Throttle limits configured via env; password-reset debug behavior is Docker-oriented; production requires rotated secrets and production-safe cookie and HTTPS policies. |

---

## 10. Artifact filenames (index)

\`\`\`text
docker_uat_latest.json
auth_stress_008_coach_eight_latest.json
auth_stress_000_athlete_zero_latest.json
ssvc_clean_before_uat_latest.txt
ssvc_clean_after_uat_latest.txt
compose_config_latest.txt
compose_ps_latest.txt
backend_logs_latest.txt
frontend_logs_latest.txt
postgres_logs_latest.txt
\`\`\`

---

*This document is generated automatically by \`scripts/validate_docker_stack.sh\`. Re-run SSVC after dependency or Dockerfile changes to refresh versions and gate counts.*
EOF
}

ensure_env_file
ensure_env_key "COACH_SIGNUP_CODE" "$UAT_COACH_SIGNUP_CODE"
ensure_env_key "THROTTLE_LOGIN" "120/min"
ensure_env_key "THROTTLE_REGISTER" "60/min"
ensure_env_key "PASSWORD_RESET_DEBUG_RESPONSE" "True"

DEMO_PASSWORD_FROM_ENV="$(env_value DEMO_PASSWORD)"
if [ -n "$DEMO_PASSWORD_FROM_ENV" ]; then
  DEMO_PASSWORD="$DEMO_PASSWORD_FROM_ENV"
fi
COACH_SIGNUP_CODE_FROM_ENV="$(env_value COACH_SIGNUP_CODE)"
if [ -n "$COACH_SIGNUP_CODE_FROM_ENV" ]; then
  UAT_COACH_SIGNUP_CODE="$COACH_SIGNUP_CODE_FROM_ENV"
fi

cd "$ROOT_DIR"

echo "Validating Compose config..."
docker compose config > "$REPORT_DIR/compose_config_latest.txt"

echo "Starting Docker stack..."
docker compose up --build -d
docker compose ps > "$REPORT_DIR/compose_ps_latest.txt" || true

wait_for_url "backend auth endpoint" "$BACKEND_URL/api/auth/me/" "401"
wait_for_url "frontend" "$FRONTEND_URL/" "200"

export BACKEND_URL FRONTEND_URL DEMO_PASSWORD UAT_COACH_SIGNUP_CODE

echo "Running SSVC cleanup before UAT..."
docker compose exec -T backend python manage.py prune_demo_users \
  --apply \
  --permanent-clean \
  --demo-password "$DEMO_PASSWORD" \
  > "$REPORT_DIR/ssvc_clean_before_uat_latest.txt"

echo "Running Docker API UAT..."
python3 "$ROOT_DIR/scripts/docker_uat.py" \
  --backend-url "$BACKEND_URL" \
  --frontend-url "$FRONTEND_URL" \
  --password "$DEMO_PASSWORD" \
  --coach-signup-code "$UAT_COACH_SIGNUP_CODE" \
  > "$REPORT_DIR/docker_uat_latest.json"

echo "Running auth stress for 008_Coach_eight..."
python3 "$ROOT_DIR/scripts/docker_auth_stress.py" \
  --backend-url "$BACKEND_URL" \
  --username "008_Coach_eight" \
  --password "$DEMO_PASSWORD" \
  --cycles "$STRESS_CYCLES" \
  > "$REPORT_DIR/auth_stress_008_coach_eight_latest.json"

echo "Running auth stress for 000_Athlete_zero..."
python3 "$ROOT_DIR/scripts/docker_auth_stress.py" \
  --backend-url "$BACKEND_URL" \
  --username "000_Athlete_zero" \
  --password "$DEMO_PASSWORD" \
  --cycles "$STRESS_CYCLES" \
  > "$REPORT_DIR/auth_stress_000_athlete_zero_latest.json"

echo "Running SSVC cleanup after UAT..."
docker compose exec -T backend python manage.py prune_demo_users \
  --apply \
  --permanent-clean \
  --demo-password "$DEMO_PASSWORD" \
  > "$REPORT_DIR/ssvc_clean_after_uat_latest.txt"

docker compose ps > "$REPORT_DIR/compose_ps_latest.txt" || true
docker compose logs --no-color --tail=300 backend > "$REPORT_DIR/backend_logs_latest.txt" 2>&1 || true
docker compose logs --no-color --tail=300 frontend > "$REPORT_DIR/frontend_logs_latest.txt" 2>&1 || true
docker compose logs --no-color --tail=300 postgres > "$REPORT_DIR/postgres_logs_latest.txt" 2>&1 || true

GEN_TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
if [ -f "$REPORT_DIR/docker_uat_latest.json" ]; then
  UAT_TOTAL="$(python3 -c "import json; print(json.load(open('$REPORT_DIR/docker_uat_latest.json')).get('total',''))")"
  UAT_PASSED="$(python3 -c "import json; print(json.load(open('$REPORT_DIR/docker_uat_latest.json')).get('passed',''))")"
  UAT_FAILED="$(python3 -c "import json; print(json.load(open('$REPORT_DIR/docker_uat_latest.json')).get('failed',''))")"
  UAT_PASS_RATE="$(python3 -c "import json; print(json.load(open('$REPORT_DIR/docker_uat_latest.json')).get('pass_rate',''))")"
else
  UAT_TOTAL=""
  UAT_PASSED=""
  UAT_FAILED=""
  UAT_PASS_RATE=""
fi
BACKEND_PY_VER="$(docker compose exec -T backend python -c 'import sys; print(sys.version.split()[0])' 2>/dev/null || echo unknown)"
DJANGO_VER="$(docker compose exec -T backend python -c 'import django; print(django.__version__)' 2>/dev/null || echo unknown)"
GUNICORN_VER="$(docker compose exec -T backend python -c 'import importlib.metadata as m; print(m.version("gunicorn"))' 2>/dev/null || echo unknown)"
NODE_VER="$(docker compose exec -T frontend node -v 2>/dev/null || echo unknown)"
DOCKER_VER="$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo unknown)"
COMPOSE_VER="$(docker compose version --short 2>/dev/null || echo unknown)"

export GEN_TS UAT_TOTAL UAT_PASSED UAT_FAILED UAT_PASS_RATE BACKEND_PY_VER DJANGO_VER GUNICORN_VER NODE_VER DOCKER_VER COMPOSE_VER

write_summary "PASS"
echo "Docker validation passed. Reports written to $REPORT_DIR"
