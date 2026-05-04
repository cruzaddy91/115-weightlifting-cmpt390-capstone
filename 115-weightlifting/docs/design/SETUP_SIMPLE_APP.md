# Simple Workout Program App - Setup Guide

This is a simplified version of the weightlifting platform focused on two core functions:
1. **Coach Dashboard**: Create and manage weekly training programs (5-day template)
2. **Athlete Dashboard**: View program and log workout results

## Features

- 5-day workout template (Monday through Friday)
- Each exercise includes: Name, Sets, Reps, Weight %/RPE, Notes
- Coach can create/edit programs
- Athlete can view program and mark exercises as completed with notes
- Data persistence using localStorage (browser-based)
- Clean, modern UI matching the presentation design

## Current Storage Implementation

The app currently uses **localStorage** for data persistence. This means:
- Data persists in the browser where you're using it
- Data is **NOT** shared across different devices/browsers
- Each browser/device has its own separate data

## Setup Instructions

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Run Development Server

```bash
npm run dev
```

The app will be available at `http://localhost:3000` (or the port Vite assigns).

### 3. Build for Production

```bash
npm run build
```

### 4. Deploy to Netlify

1. Push your code to GitHub
2. Connect your repository to Netlify
3. Set build settings:
   - **Build command**: `cd frontend && npm run build`
   - **Publish directory**: `frontend/dist`
4. Deploy

The `netlify.toml` file is already configured for this setup.

## Usage

### Coach Workflow

1. Navigate to `/coach` or click "Coach Dashboard" on the home page
2. Select the week start date
3. For each day (Monday-Friday):
   - Click "+ Add Exercise" to add exercises
   - Fill in: Exercise name, Sets, Reps, Weight %/RPE, Notes
   - Remove exercises as needed
4. Click "Save Program" to save

### Athlete Workflow

1. Navigate to `/athlete` or click "Athlete Dashboard" on the home page
2. View the weekly program created by your coach
3. For each exercise:
   - Check "Completed" when finished
   - Add your workout notes
4. Click "Save Results" to save your progress

## Cross-Device Persistence (Optional)

Currently, data is stored in browser localStorage, which means it's device-specific. To enable cross-device persistence, you have a few options:

### Option 1: Supabase (Recommended for Simple Setup)

1. Create a free Supabase account at https://supabase.com
2. Create a new project
3. Create a table called `programs` with columns:
   - `id` (uuid, primary key)
   - `data` (jsonb)
   - `created_at` (timestamp)
   - `updated_at` (timestamp)
4. Get your Supabase URL and anon key
5. Create a `.env` file in the `frontend` directory:
   ```
   VITE_SUPABASE_URL=your_supabase_url
   VITE_SUPABASE_ANON_KEY=your_anon_key
   ```
6. Update the storage adapter to use Supabase (implementation needed)

### Option 2: Netlify Functions with Database

Use the Netlify Functions provided in `netlify/functions/` and connect them to a database like:
- Supabase (PostgreSQL)
- MongoDB Atlas (free tier)
- Firebase Realtime Database

### Option 3: Simple JSON File Storage

Use a service like JSONBin.io or a similar free JSON storage service for simple key-value storage.

## File Structure

```
frontend/
├── src/
│   ├── components/
│   │   └── WorkoutDay.jsx          # Reusable day component
│   ├── pages/
│   │   ├── CoachDashboard.jsx      # Coach interface
│   │   └── AthleteDashboard.jsx   # Athlete interface
│   ├── services/
│   │   └── api.js                  # API/storage functions
│   ├── utils/
│   │   ├── dataStructure.js        # Data models
│   │   └── storage.js              # Storage adapter
│   ├── App.jsx                     # Main app with routing
│   └── App.css                     # Styles
netlify/
└── functions/                      # Serverless functions (for future use)
    ├── get-program.js
    ├── save-program.js
    └── save-results.js
netlify.toml                        # Netlify configuration
```

## Next Steps

This is a minimal viable version. Future enhancements could include:
- Cross-device data synchronization
- Multiple athletes support
- Historical program tracking
- Export/import functionality
- Mobile-responsive improvements

