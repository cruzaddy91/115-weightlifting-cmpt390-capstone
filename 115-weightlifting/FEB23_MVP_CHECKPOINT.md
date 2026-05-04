# MVP checkpoint (Feb 23)

This file summarizes what was completed through **Feb 23** (including the Feb 24 items completed early) based on the final proposal sprint schedule.

## Schedule coverage

- **Foundation (Feb 14):** already complete from prior checkpoint.
- **Week of Feb 17 checkpoint:** completed now (program creation + assignment + list).
- **Week of Feb 24 checkpoint:** completed early (athlete workout logging + history + data structure in backend).

## What was implemented

### Backend

- **Programs API (create/list/assign)**
  - `GET /api/programs/` - list programs visible to current user.
  - `POST /api/programs/` - coach creates and assigns a program to an athlete.
  - `PATCH /api/programs/<id>/assign/` - coach reassigns a program athlete.
  - Updated files:
    - `src/backend/apps/programs/serializers.py`
    - `src/backend/apps/programs/views.py`
    - `src/backend/apps/programs/urls.py`

- **Athlete roster endpoint (for assignment UI)**
  - `GET /api/auth/athletes/` - coach-only athlete list.
  - Updated files:
    - `src/backend/apps/accounts/views.py`
    - `src/backend/apps/accounts/urls.py`

- **Workout logbook + PR APIs**
  - `GET /api/athletes/workouts/` - athlete self history (coach can query assigned athlete with `athlete_id`).
  - `POST /api/athletes/workouts/` - athlete workout log entry.
  - `GET /api/athletes/prs/` - athlete PR history (coach can query assigned athlete with `athlete_id`).
  - `POST /api/athletes/prs/` - athlete PR entry.
  - Added/updated files:
    - `src/backend/apps/athletes/serializers.py` (new)
    - `src/backend/apps/athletes/views.py` (new)
    - `src/backend/apps/athletes/urls.py`

### Frontend

- **Coach dashboard API integration**
  - Create program form now writes to backend.
  - Athlete dropdown is populated from backend roster.
  - Existing programs are listed from backend.
  - Reassignment action calls backend assign endpoint.
  - Updated file: `src/frontend/src/pages/CoachDashboard.jsx`

- **Athlete dashboard API integration**
  - Assigned programs are loaded from backend.
  - Workout logs are submitted to backend and displayed in history.
  - Personal records are submitted to backend and displayed in history.
  - Updated file: `src/frontend/src/pages/AthleteDashboard.jsx`

- **Frontend API client**
  - Added functions for create/assign/list program and athlete logbook/PR endpoints.
  - Updated file: `src/frontend/src/services/api.js`

## Verification completed

- **Lint diagnostics:** no linter errors in touched files.
- **Backend health check:** `python3 manage.py check` passed.
- **Frontend compile check:** `npm run build` passed.
- **End-to-end API smoke test:** passed for the core flow:
  - coach login -> list/create/assign program
  - athlete login -> create/list workout log
  - athlete login -> create/list personal record
  - all key responses returned 200/201

## Sprint status as of Feb 23

- [x] Feb 17 checkpoint target: create/assign/list program
- [x] Feb 24 checkpoint target: workout log + history available via backend API and UI
- [x] Full-stack integration for these checkpoints (backend + frontend, not localStorage-only)
