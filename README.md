# 115 Weightlifting CMPT-390 Capstone

115 Weightlifting is a full-stack capstone project for Olympic weightlifting coaches and athletes. It supports role-aware dashboards for head coaches, line coaches, and athletes; structured training program creation and assignment; athlete workout completion; personal record tracking; charts; roster analytics; and Sinclair scoring.

This repository is the professor-facing, Docker-ready version of the project. It is intended to be cloned and launched locally with Docker Compose.

## Quick Launch

Prerequisite: Docker Desktop or Docker Engine with Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- Frontend: http://localhost:4173
- Backend API: http://localhost:8000

The first backend startup runs migrations and, by default, seeds demo data because `SEED_DEMO=true` in `.env.example`.

## Demo Credentials

All demo accounts use this password:

```text
Passw0rd!123
```

Suggested walkthrough accounts:

| Role | Username | URL |
| --- | --- | --- |
| Head coach | `Headcoachone` | http://localhost:4173/head |
| Line coach | `Coachone` | http://localhost:4173/coach |
| Athlete | `jon_snow` | http://localhost:4173/athlete |

The `jon_snow` account is seeded with assigned programs, workout logs, personal records, and completion records so the athlete dashboard has meaningful data.

## Docker Services

`docker-compose.yml` starts three services:

| Service | Purpose |
| --- | --- |
| `postgres` | PostgreSQL 16 database with a persistent Docker volume. |
| `backend` | Django REST backend served by Gunicorn on port `8000`. |
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
├── .env.example
├── LICENSE
├── README.md
└── 115-weightlifting/
    ├── src/backend/      # Django REST API, Dockerfile, Docker entrypoint
    ├── src/frontend/     # React/Vite app, Dockerfile
    ├── tools/sim/        # Simulation and demo data tools
    ├── scripts/          # Local development and reporting scripts
    └── README.md         # Application-level details
```

## Local Development Without Docker

The original app-level workflow is still available under `115-weightlifting/`:

```bash
cd 115-weightlifting
./bin/zw help
```

For grading/demo purposes, Docker Compose is the recommended path because it avoids requiring local Python, Node, or PostgreSQL setup.

## Notes On Production

This Docker setup is designed for local evaluation. For a public production deployment, the main follow-up work would be:

- Set `DEBUG=False`.
- Use a strong `SECRET_KEY`.
- Set real `ALLOWED_HOSTS`, CORS, and CSRF origins.
- Put the backend behind HTTPS.
- Serve the built frontend through a production static server such as Nginx or Caddy, or deploy it separately to a static hosting provider.

## License

MIT. See `LICENSE`.
