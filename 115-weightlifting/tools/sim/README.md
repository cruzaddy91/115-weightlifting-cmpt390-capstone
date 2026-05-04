# 115 Weightlifting — simulation toolkit

Python-based tools for seeding demo data, simulating coach + athlete
workflows, and stress-testing the 115 Weightlifting API.

## Layout

```
tools/sim/
├── client.py       # Thin HTTP client wrapper around the API
├── themes.py       # Character-name pools (Game of Thrones, LOTR)
├── seed.py         # CLI: create a coach + N athletes
├── requirements.txt
└── README.md
```

## Setup

From the repository root:

```bash
cd 115-weightlifting/tools/sim
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The backend must be running (`./bin/zw dev` from `115-weightlifting/`), and
`COACH_SIGNUP_CODE=test123` must be set in `src/backend/.env` (or pass a
matching value via `--coach-signup-code`).

## Seed a coach + athletes

```bash
# Default: Coachone + 5 Game of Thrones athletes
python seed.py

# Different coach, bigger roster, different theme
python seed.py --coach Coachtwo --athletes 12 --theme lord-of-the-rings

# Against a remote stage
python seed.py --api https://wl.example.com --coach-signup-code "$PROD_CODE"
```

From the **115-weightlifting** repo root you can also bootstrap Coachtwo + the
first five LotR athletes (bodyweights from `character_sim_profiles.py`) and
~3 years of PR + workout rows via Django (no HTTP register throttling):

```bash
./bin/zw seed-coachtwo-lotr
./bin/zw seed-coachtwo-lotr --with-programs   # optional programs; API must be up
```

All seeded users share the same password (default `Passw0rd!123`, override
with `--password`). Script is idempotent — re-running it logs into existing
users instead of creating duplicates.

After seeding, log in as the coach at `http://localhost:3000/login`. The
athletes will show up under the athlete-search box in the program editor
(`scope=mine` for line coaches; head coaches use `scope=all` for the org pool).
They appear once `primary_coach` matches after program assignment or head setup.

## Create programs for a seeded roster

```bash
# Default: Coachone, 1 classic-accumulation program per GoT athlete
python build_programs.py

# Two back-to-back 4-week blocks per athlete (current + prior)
python build_programs.py --programs-per-athlete 2

# Different coach + theme, bigger roster, 8-week blocks
python build_programs.py --coach Coachtwo --theme lord-of-the-rings \
  --athletes 10 --block-weeks 8
```

Each program ships with the full xlsx schema: 5 days (Mon-Fri), ~14
exercises, realistic % 1RM / RPE / weight / tempo / rest values, and a
saved `intensity_mode = percent_1rm` preference so reopening the program
keeps the coach's display mode.

The generator lightly randomizes intensities per athlete (±2%) so the
roster does not look copy-pasted; randomness is seeded from the athlete
username so re-running the tool produces the same program for the same
athlete (useful for reproducible fixtures).

Note: this script is **additive**. Re-running creates more programs; it
does not upsert. Use the Django admin or a reset script to clear.

## Program completion (coach dashboard % rings) — `populate_history.py`

The per-program **progress ring** and **“x/y exercises done”** on the coach
list view come from `completion_data` (athlete-side checkmarks). `build_programs.py`
creates the week structure only, so those metrics stay at **0%** until
completion is written (the athlete in the app, or this script simulating
them).

Use the same tiered PR/workout/programs logic for **any** coach, but pass a
**theme** so you only backfill the roster that coach owns (mirrors
Coachone+GoT vs Coachtwo+LotR):

```bash
# API must be running. Default password matches seed defaults.
# Coachone + first five GoT (typical `python seed.py` roster)
python populate_history.py --coach Coachone --roster-theme game-of-thrones --roster-size 5

# Coachtwo + first five LotR (e.g. after seed-coachtwo-lotr; distinct tiers / bodyweight)
python populate_history.py --coach Coachtwo --roster-theme lord-of-the-rings --roster-size 5
```

Omitting `--roster-theme` iterates every username in `ATHLETE_PROFILES` (5 GoT
+ 5 LotR) — only use that if **all** those users exist in the database.
Each run **adds** four new programs per athlete; remove duplicate programs
in admin if you already ran `build_programs` and are re-stocking completion.

## What's coming next

- `simulate_completion.py` — athletes "execute" programs over time,
  log actual results + PRs + workout entries
- `stress_test.py` — parallel-client load harness (asyncio + aiohttp)
  to probe throttle limits, connection pool behavior, N+1 at scale

Each new entry point will live in this directory and reuse `client.py`,
`themes.py`, and `program_generators.py`.
