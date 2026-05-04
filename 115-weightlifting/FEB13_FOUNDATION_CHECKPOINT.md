# Foundation checkpoint (Feb 13)

This file summarizes what was implemented so the **Feb 14 – Foundation complete** milestone is met: auth stable, core API, one end-to-end flow (login + one screen calling the API).

## What was added

### Backend

- **Programs API**
  - `GET /api/programs/` – list programs for the current user (as coach or athlete). Requires JWT.
  - `apps/programs/serializers.py`, `apps/programs/views.py`, `apps/programs/urls.py` updated.
- **Auth**
  - `POST /api/auth/register/` – create user (username, password, user_type: coach | athlete). Body: `{"username":"...","password":"...","user_type":"coach"}`.
  - Token endpoints are explicitly `AllowAny` so login works: `POST /api/auth/token/` (username, password) returns `{ "access": "...", "refresh": "..." }`.

### Frontend

- **Login page** (`/login`)
  - Username/password login; calls `POST /api/auth/token/`, stores access token in localStorage.
  - Register form (toggle): create account with username, password, role (coach/athlete).
- **Protected routes**
  - `/coach` and `/athlete` require auth; if no token, redirect to `/login`.
- **One screen using the API**
  - Coach Dashboard calls `GET /api/programs/` with the stored token and shows “Programs from API: N” (or an error if not authenticated).
- **Log out**
  - Nav shows “Log out” when authenticated; click clears token and goes home.

## How to run (by Feb 13)

1. **Backend**
   ```bash
   cd 115-weightlifting/src/backend
   pip install -r requirements.txt   # if not already
   python manage.py migrate
   python manage.py runserver
   ```
   Backend: http://localhost:8000

2. **Frontend**
   ```bash
   cd 115-weightlifting/src/frontend
   npm install
   npm run dev
   ```
   Frontend: http://localhost:3000 (CORS is set for this origin).

3. **End-to-end flow**
   - Open http://localhost:3000 → click “Log in” → click “Register” → create account (coach) → then “Log in” with same credentials.
   - You should be redirected to Coach Dashboard and see “Programs from API: 0” (no programs yet).
   - That completes: **login + one screen + API call with auth**.

## Checklist (Foundation complete by Feb 14)

- [x] Auth: JWT login and token storage; register endpoint.
- [x] Core API: at least one endpoint (programs list) using DB and auth.
- [x] Frontend–backend: React calls Django with Bearer token; CORS configured.
- [x] One full flow: Login → Coach Dashboard → GET /api/programs/ → display count.
