# Large-business deployment checklist

## Branch convention (manual Git workflow)

### Integration vs packaging

- **Sandbox / integration:** use **`main`**, topic branches, or **`dev/ssvc-acp-cabinet`** (or similar) — whatever your team already uses for informal work. No separate sandbox branch is prescribed here.
- **`pkg_large`** holds this LARGE deployment path (Compose merge file, env template, tuning below). **`pkg_medium`** and **`pkg_small`** are reserved for future tier-specific layouts.

Nothing here creates or pushes branches. Promote to **`pkg_large`** at **ACP** when SSVC and your LARGE checklist pass.

**Git note:** while **`dev/ssvc-acp-cabinet`** exists, Git cannot also hold a sibling branch named exactly **`dev`** — only rename integration branches if you need that literal name.

When **`pkg_large`** is ready for stakeholders, run **UAT** against your staged environment using **`.env.pkg_large`** filled from [`env.large.example`](../env.large.example) (HTTPS, SMTP) or [`env.large.local.example`](../env.large.local.example) for localhost — plus the three-file Compose merge — **not** the demo `.env.example` stack. For regression automation against seeded demos only, use [`scripts/validate_docker_stack.sh`](../scripts/validate_docker_stack.sh) on the base compose path.

| Branch | Role |
| --- | --- |
| **`pkg_large`** | Large scale — **this document**. Active packaging focus. |
| **`pkg_medium`** | Medium-scale deployment (**planned**). |
| **`pkg_small`** | Small-scale deployment (**planned**). |

## pkg_large locally (one machine, now)

1. Free host ports **5433**, **8001**, and **4174** (defaults), or set **`PKG_LARGE_HOST_POSTGRES_PORT`**, **`PKG_LARGE_HOST_BACKEND_PORT`**, **`PKG_LARGE_HOST_FRONTEND_PORT`** in **`.env.pkg_large`** and align **`VITE_API_BASE_URL`**, **`CORS_ALLOWED_ORIGINS`**, **`CSRF_TRUSTED_ORIGINS`**, **`PASSWORD_RESET_FRONTEND_URL`**. The demo stack may keep **5432 / 8000 / 4173**.
2. From the repo root:

   ```bash
   ./scripts/up_pkg_large.sh
   ```

   This creates **`.env.pkg_large`** from [`env.large.local.example`](../env.large.local.example) (if missing), replaces the placeholder **`SECRET_KEY`** with **`openssl rand -hex 32`**, then runs Compose with project name **`pkg_large`** using:

   - [`docker-compose.yml`](../docker-compose.yml)
   - [`docker-compose.large.yml`](../docker-compose.large.yml)
   - [`docker-compose.pkg_large.yml`](../docker-compose.pkg_large.yml)

3. Open <http://localhost:4174>. **There are no seeded demo users** (`SEED_DEMO=false`). Register the first head coach / athletes via the app, or:

   ```bash
   docker compose -p pkg_large --env-file .env.pkg_large \
     -f docker-compose.yml -f docker-compose.large.yml -f docker-compose.pkg_large.yml \
     exec backend python manage.py createsuperuser
   ```

4. Tear down (including LARGE Postgres volume):

   ```bash
   docker compose -p pkg_large --env-file .env.pkg_large \
     -f docker-compose.yml -f docker-compose.large.yml -f docker-compose.pkg_large.yml \
     down -v
   ```

## Preconditions

- TLS terminates at a reverse proxy or load balancer that forwards **`X-Forwarded-Proto: https`** to Django.
- Secrets (`SECRET_KEY`, database passwords, SMTP credentials) come from a secrets manager or protected env — not committed files.
- **`ALLOWED_HOSTS`**, **`CORS_ALLOWED_ORIGINS`**, and **`CSRF_TRUSTED_ORIGINS`** list your real public API and app origins (scheme + host; include ports only if non-default).

## Compose and env

### Demo SSVC vs pkg_large

[`scripts/validate_docker_stack.sh`](../scripts/validate_docker_stack.sh) uses `.env.example` and base compose only (seeded demos).

For **pkg_large**, use **`.env.pkg_large`** + three-file merge above — **not** the demo `.env`.

### Production-shaped template

1. Base stack: [`docker-compose.yml`](../docker-compose.yml).
2. Large overrides (workers, no demo seed, optional CPU/memory hints): [`docker-compose.large.yml`](../docker-compose.large.yml).
3. Backend env file override: [`docker-compose.pkg_large.yml`](../docker-compose.pkg_large.yml) (points at `.env.pkg_large`).

```bash
docker compose --env-file .env.pkg_large \
  -f docker-compose.yml -f docker-compose.large.yml -f docker-compose.pkg_large.yml \
  up --build
```

4. For internet-facing deploys, fill **`.env.pkg_large`** from [`env.large.example`](../env.large.example) (HTTPS origins, SMTP, strong secrets). For localhost LARGE bootstrapping, [`env.large.local.example`](../env.large.local.example) + [`scripts/up_pkg_large.sh`](../scripts/up_pkg_large.sh) are sufficient.

## Django production guardrails

Defined in [`115-weightlifting/src/backend/config/settings.py`](../115-weightlifting/src/backend/config/settings.py):

- **`DEBUG=False`** requires a **non-default `SECRET_KEY`**. Django exits at startup if `SECRET_KEY` still matches the insecure default string.
- With **`DEBUG=False`**, session and CSRF cookies are **Secure**; **`SECURE_PROXY_SSL_HEADER`** is set so HTTPS detection works behind your TLS terminator.
- **`SECURE_SSL_REDIRECT`**: default **`True`** when `DEBUG=False`. Local LARGE compose uses **`False`** in **`env.large.local.example`** / **`.env.pkg_large`** so plain HTTP works without a TLS terminator.

## Database

- Point **`DATABASE_URL`** at your Postgres instance (managed RDS/Aurora/Cloud SQL, or the `postgres` service hostname when still using Compose).
- Entrypoint waits on **`DATABASE_URL`** host/port before migrate/collectstatic.

## Demo data

- **`SEED_DEMO=false`** (set by [`docker-compose.large.yml`](../docker-compose.large.yml)) skips demo provisioning. The automated SSVC harness in [`scripts/validate_docker_stack.sh`](../scripts/validate_docker_stack.sh) expects the **default** stack (`.env.example` + base compose only), not LARGE merge.

## API throughput

- Gunicorn worker count: **`GUNICORN_WORKERS`** (default **3** in the backend image; override env sets **`4`** in LARGE compose unless you change it).

## Email

- Set **`EMAIL_BACKEND`** to SMTP and fill **`EMAIL_HOST`**, **`EMAIL_PORT`**, **`EMAIL_HOST_USER`**, **`EMAIL_HOST_PASSWORD`**, **`EMAIL_USE_TLS`** as needed. Keep **`PASSWORD_RESET_DEBUG_RESPONSE=False`**.

## Out of scope here

- Kubernetes manifests, autoscaling, and managed Postgres provisioning are platform-specific — wire them outside this repository if needed.
