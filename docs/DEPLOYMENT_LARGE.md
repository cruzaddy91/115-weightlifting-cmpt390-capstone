# Large-business deployment checklist

## Branch convention (manual Git workflow)

### Integration vs packaging

- **Sandbox / integration:** use **`main`**, topic branches, or **`dev/ssvc-acp-cabinet`** (or similar) — whatever your team already uses for informal work. No separate sandbox branch is prescribed here.
- **`pkg_large`** holds this LARGE deployment path (Compose merge file, env template, tuning below). **`pkg_medium`** and **`pkg_small`** are reserved for future tier-specific layouts.

Nothing here creates or pushes branches. Promote to **`pkg_large`** at **ACP** when SSVC and your LARGE checklist pass.

**Git note:** while **`dev/ssvc-acp-cabinet`** exists, Git cannot also hold a sibling branch named exactly **`dev`** — only rename integration branches if you need that literal name.

When **`pkg_large`** is ready for stakeholders, run **UAT** against your staged environment using keys from **`env.large.example`** (copy to `.env`) and merged Compose — **not** the default `.env.example` demo stack. For regression automation against seeded demos only, use **`scripts/validate_docker_stack.sh`** on the base compose path.

| Branch | Role |
| --- | --- |
| **`pkg_large`** | Large scale — **this document**. Active packaging focus. |
| **`pkg_medium`** | Medium-scale deployment (**planned**). |
| **`pkg_small`** | Small-scale deployment (**planned**). |

## Preconditions

- TLS terminates at a reverse proxy or load balancer that forwards **`X-Forwarded-Proto: https`** to Django.
- Secrets (`SECRET_KEY`, database passwords, SMTP credentials) come from a secrets manager or protected env — not committed files.
- **`ALLOWED_HOSTS`**, **`CORS_ALLOWED_ORIGINS`**, and **`CSRF_TRUSTED_ORIGINS`** list your real public API and app origins (scheme + host; include ports only if non-default).

## Compose and env

1. Base stack: [`docker-compose.yml`](../docker-compose.yml).
2. Large overrides (workers, no demo seed, optional CPU/memory hints): merge [`docker-compose.large.yml`](../docker-compose.large.yml):

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.large.yml up --build
   ```

3. Copy [`env.large.example`](../env.large.example) to `.env` on the deployment host (or inject equivalent keys). Adjust placeholders (`example.invalid`, passwords, SMTP).

## Django production guardrails

Defined in [`115-weightlifting/src/backend/config/settings.py`](../115-weightlifting/src/backend/config/settings.py):

- **`DEBUG=False`** requires a **non-default `SECRET_KEY`**. Django exits at startup if `SECRET_KEY` still matches the insecure default string.
- With **`DEBUG=False`**, session and CSRF cookies are **Secure**; **`SECURE_PROXY_SSL_HEADER`** is set so HTTPS detection works behind your TLS terminator.
- **`SECURE_SSL_REDIRECT`**: default **`True`** when `DEBUG=False`. If you run an HTTP-only local smoke test with LARGE compose, set **`SECURE_SSL_REDIRECT=False`** in `.env` so redirects do not break browser/API checks.

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
