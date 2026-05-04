# Project Directory Structure

## Overview
115 Weightlifting. Full stack web application for Olympic weightlifting coaches and athletes.

## Root Directory Structure

```
115-weightlifting/          # current local directory name for 115 Weightlifting
├── .gitignore
├── README.md
├── DIRECTORY_STRUCTURE.md
│
├── assets/                    # Static assets
│   └── resumes/
│       └── cruz_addy_profesional_resume.pdf
│
├── config/                    # Project configuration
│   └── deployment.md
│
├── docs/                      # App documentation (setup and design only)
│   └── design/                # Setup and design for the application
│       ├── SETUP_SIMPLE_APP.md
│       └── SUPABASE_SETUP.md
│
d├── scripts/                   # Build and utility scripts
│   ├── setup.sh
│   └── convert_to_pdf.py
│
└── src/                       # Source code
    ├── frontend/              # React frontend application
    │   ├── src/
    │   │   ├── components/    # Reusable UI components
    │   │   │   └── WorkoutDay.jsx
    │   │   ├── pages/         # Page components
    │   │   │   ├── AthleteDashboard.jsx
    │   │   │   └── CoachDashboard.jsx
    │   │   ├── services/     # API service layer
    │   │   │   └── api.js
    │   │   ├── utils/        # Utility functions
    │   │   │   ├── dataStructure.js
    │   │   │   └── storage.js
    │   │   ├── App.jsx
    │   │   ├── App.css
    │   │   ├── main.jsx
    │   │   └── index.css
    │   ├── index.html
    │   ├── package.json
    │   └── vite.config.js
    │
    ├── backend/               # Django REST API
    │   ├── config/            # Django project settings
    │   │   ├── __init__.py
    │   │   ├── settings.py
    │   │   ├── urls.py
    │   │   ├── asgi.py
    │   │   └── wsgi.py
    │   ├── apps/              # Django applications
    │   │   ├── accounts/      # User authentication & management
    │   │   ├── programs/      # Training program management
    │   │   ├── athletes/      # Athlete data & workout logs
    │   │   ├── competitions/   # Competition tracking
    │   │   └── analytics/     # Performance analytics
    │   ├── manage.py
    │   └── requirements.txt
    │
    ├── data-science/          # Python data analysis layer
    │   ├── scripts/
    │   │   ├── __init__.py
    │   │   └── sinclair_calculator.py
    │   └── requirements.txt
    │
    └── infrastructure/        # Deployment configuration
        ├── netlify.toml
        └── netlify/
            └── functions/
                ├── get-program.js
                ├── save-program.js
                └── save-results.js
```

All turn-in deliverables (proposals, reports, transcripts, proof of concept, etc.) live under the parent repo: **CMPT-390_CSCapstone/docs/**.

## Deployment Strategy

### Frontend
- **Primary**: Vercel (free tier)
- **Plan B**: Netlify (free tier)
- Both support automatic GitHub deployments

### Backend
- **Render** (free tier)
- Django REST Framework API

### Database
- **Options**: Supabase or Neon (free tier PostgreSQL)
- Development: SQLite (local)

## Key Files (this repo: code, build, application)

- `docs/design/SETUP_SIMPLE_APP.md` – Frontend/backend setup
- `docs/design/SUPABASE_SETUP.md` – Database setup
- `config/deployment.md` – Deployment configuration
- `README.md` – Project overview and setup instructions

**Turn-in deliverables** (proposals, reports, transcripts, proof of concept, etc.) are in the parent repo under `CMPT-390_CSCapstone/docs/` (assignments, deliverables).
