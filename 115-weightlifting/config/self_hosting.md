# Self-Hosting Plan

This project now supports two non-Netlify paths:

- `Local self-host now`: run both services on your own machine for demos, LAN use, or development support.
- `Public self-host later`: expose the same stack on your own machine or VPS with a reverse proxy, HTTPS, and process management.

Product name: `115 Weightlifting`. Current local checkout directory examples use `115-weightlifting/`.

## 1. Local Self-Host Now

### What you need

- Node.js and npm
- Python virtual environment in `src/backend/venv`
- Backend dependencies installed
- Frontend dependencies installed

### One-time setup

```bash
cd 115-weightlifting/src/backend
cp .env.example .env
./venv/bin/python -m pip install -r requirements.txt

cd ../frontend
cp .env.example .env
npm install
```

### Seed demo users

```bash
cd 115-weightlifting
./bin/zw seed-demo
```

Demo credentials:

- `coach_smoke` / `DemoPass123!`
- `athlete_smoke` / `DemoPass123!`

### Start the local host stack

```bash
cd 115-weightlifting
./bin/zw host-local start
```

Managed commands:

- `./bin/zw host-local start`
- `./bin/zw host-local stop`
- `./bin/zw host-local status`
- `./bin/zw logs`
- `./bin/zw backup`
- `./bin/zw export-data`
- `./bin/zw import-data <fixture.json> --yes`
- `./bin/zw restore --sqlite <backup.sqlite3> --yes`

The start command:

- builds the frontend
- applies backend migrations
- starts Django with Gunicorn on `0.0.0.0:8000`
- starts the frontend preview server on `0.0.0.0:4173`
- writes runtime state into `var/run/` and logs into `var/log/`

Access locally:

- Frontend: `http://localhost:4173`
- Backend: `http://localhost:8000`

### LAN access

If devices are on the same network, use your machine's local IP:

- `http://<your-lan-ip>:4173`

You may need to allow incoming connections in the OS firewall.

### Local support responsibilities

- Keep the machine powered on
- Restart with `./bin/zw host-local start` if the host machine reboots
- Keep `.env` values correct for local URLs
- Rebuild/restart after frontend or backend changes
- Take backups before major data changes

### Data safety commands

Examples:

```bash
./bin/zw backup
./bin/zw export-data
./bin/zw import-data var/backups/export_YYYYMMDD_HHMMSS.json --yes
./bin/zw restore --sqlite var/backups/db_YYYYMMDD_HHMMSS.sqlite3 --yes
```

## 2. Public Self-Host Later

This is the path if you want users outside your home or office network to access the app without Netlify.

### Recommended stack

- `Caddy` as reverse proxy and HTTPS terminator
- `Gunicorn` for Django
- built frontend files served as static assets
- `PostgreSQL`
- `systemd` for automatic restarts

### What you need

- a Linux host or VPS, or a home machine that stays on
- a domain name
- ports `80` and `443` available
- router port forwarding if hosted from home
- PostgreSQL database
- backups for the database

### Recommended architecture

- Caddy serves the frontend build directory
- Caddy proxies `/api/*` to Gunicorn on localhost
- Gunicorn runs the Django backend on localhost only
- PostgreSQL stores app data
- Concrete templates now live in `config/self_hosting/`

### Suggested deployment layout

```text
/srv/weightlifting/
├── app/                 # checked-out repo
├── env/                 # backend .env and secrets
├── logs/
└── releases/            # optional if you want release folders
```

### Suggested systemd service

Template file: `config/self_hosting/weightlifting-backend.service`

Install it as `/etc/systemd/system/weightlifting-backend.service`:

```ini
[Unit]
Description=Weightlifting Django backend
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/srv/weightlifting/app/115-weightlifting/src/backend
EnvironmentFile=/srv/weightlifting/env/backend.env
ExecStart=/srv/weightlifting/app/115-weightlifting/src/backend/venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Suggested Caddyfile

Template file: `config/self_hosting/Caddyfile.example`

```caddy
your-domain.example {
    root * /srv/weightlifting/app/115-weightlifting/src/frontend/dist
    encode gzip zstd
    file_server

    handle /api/* {
        reverse_proxy 127.0.0.1:8000
    }

    try_files {path} /index.html
}
```

### Public-host env requirements

Backend:

- `DEBUG=False`
- `SECRET_KEY=<secure-value>`
- `ALLOWED_HOSTS=your-domain.example`
- `CORS_ALLOWED_ORIGINS=https://your-domain.example`
- `CSRF_TRUSTED_ORIGINS=https://your-domain.example`
- `DATABASE_URL=postgresql://...`

Frontend:

- `VITE_API_BASE_URL=https://your-domain.example`

Template files:

- `config/self_hosting/backend.env.production.example`
- `config/self_hosting/frontend.env.production.example`

### Public-host prep command

Build and migrate the app before switching traffic:

```bash
cd 115-weightlifting
./bin/zw prepare-public
```

This script installs backend deps, runs migrations, installs frontend deps, and builds the production frontend bundle.

### Ongoing support work

- renew or verify TLS certificates
- keep OS packages updated
- update Python/Node dependencies
- monitor logs and restart services if needed
- back up PostgreSQL
- re-run migrations on deploy
- rebuild frontend on deploy

## Netlify Later

If you switch to Netlify later, the frontend side becomes easier:

- Netlify hosts the built frontend
- Render or another backend host runs Django
- you keep PostgreSQL external

The backend and database requirements stay almost the same. Only the frontend hosting and HTTPS burden move off your machine.
