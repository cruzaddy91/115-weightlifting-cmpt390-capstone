# Deployment Configuration

## Target Stack

- Product: `115 Weightlifting`
- Frontend: Vercel or Netlify
- Backend: Render web service
- Database: PostgreSQL on Supabase or Neon

## Required Environment Variables

### Frontend

- `VITE_API_BASE_URL=https://<your-backend-domain>`

### Backend

- `SECRET_KEY=<secure-random-string>`
- `DEBUG=False`
- `ALLOWED_HOSTS=<render-domain>,<custom-domain-if-any>`
- `CORS_ALLOWED_ORIGINS=https://<frontend-domain>`
- `CSRF_TRUSTED_ORIGINS=https://<frontend-domain>`
- `DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<db-name>`

If `DATABASE_URL` is missing, the backend falls back to SQLite or the legacy local PostgreSQL variables in `.env.example`.

## Frontend Deployment

### Vercel

- Root directory: `115-weightlifting/src/frontend`
- Build command: `npm run build`
- Output directory: `dist`
- Environment variable: `VITE_API_BASE_URL`

### Netlify

Use `src/infrastructure/netlify.toml` or configure manually:

- Base directory: `115-weightlifting`
- Build command: `cd src/frontend && npm run build`
- Publish directory: `src/frontend/dist`

## Backend Deployment (Render)

- Root directory: `115-weightlifting/src/backend`
- Build command: `pip install -r requirements.txt`
- Start command: `python manage.py migrate && python manage.py runserver 0.0.0.0:$PORT`
- Add the backend environment variables listed above

For production, replace `runserver` with Gunicorn when you are ready to harden deployment.

## Database

- Create a PostgreSQL database in Supabase or Neon
- Copy its connection string into `DATABASE_URL`
- Run `python manage.py migrate`
- Seed one coach and one athlete account for demo purposes

## Smoke Test Checklist

1. Register or seed one coach account and one athlete account
2. Coach login redirects to `/coach`
3. Athlete login redirects to `/athlete`
4. Coach creates a structured weekly program and assigns it
5. Athlete opens the assigned program and saves completion data
6. Athlete adds a PR entry and confirms the dashboard chart updates
7. Athlete calculates a Sinclair score from the deployed frontend
