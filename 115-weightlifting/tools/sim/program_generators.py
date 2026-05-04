"""Template-based training-program generators.

Produces API-ready payloads that match the 115 Weightlifting program_data
schema exactly (including the stable day.id field and the intensity_mode
preference). Built so new templates can be added without touching the CLI.

Currently ships one classic-OWL accumulation-block template. Future templates
(intensification, realization, technique, strength block) will slot in here.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any, Optional


# ----------------------------------------------------------------------------
# Template definitions. Each is a list of day specs; a day spec is a dict
# with 'day' and 'exercises'. Exercise dicts carry the xlsx template fields
# (sets/reps/%1RM/RPE/weight/tempo/rest/notes) -- any omitted key is rendered
# as empty at build time so the payload always matches the schema.
# ----------------------------------------------------------------------------

_CLASSIC_ACCUMULATION_WEEK: list[dict[str, Any]] = [
    {
        "day": "Monday",
        "exercises": [
            {"name": "Snatch",        "sets": "5", "reps": "2",   "percent_1rm": "75%", "rest": "2min",   "notes": "Fast turnover"},
            {"name": "Back Squat",    "sets": "4", "reps": "5",   "percent_1rm": "80%", "tempo": "3-1-X-1", "rest": "3min"},
            {"name": "Snatch Pull",   "sets": "4", "reps": "3",   "percent_1rm": "90%", "rest": "2min"},
        ],
    },
    {
        "day": "Tuesday",
        "exercises": [
            {"name": "Clean & Jerk",  "sets": "5", "reps": "1+1", "percent_1rm": "78%", "rest": "2-3min"},
            {"name": "Front Squat",   "sets": "4", "reps": "3",   "percent_1rm": "82%", "rest": "3min"},
            {"name": "Bent-Over Row", "sets": "3", "reps": "8",   "rest": "90s", "notes": "Pendlay style"},
        ],
    },
    {
        "day": "Wednesday",
        "exercises": [
            {"name": "Power Snatch",  "sets": "5", "reps": "2",   "rpe": "7", "rest": "90s", "notes": "Speed day, stop at RPE 7"},
            {"name": "Push Press",    "sets": "4", "reps": "5",   "percent_1rm": "70%", "rest": "2min"},
        ],
    },
    {
        "day": "Thursday",
        "exercises": [
            {"name": "Snatch",        "sets": "4", "reps": "1",   "percent_1rm": "85%", "rest": "2min", "notes": "Heavy singles"},
            {"name": "Clean & Jerk",  "sets": "4", "reps": "1",   "percent_1rm": "85%", "rest": "2min"},
            {"name": "Deadlift",      "sets": "3", "reps": "5",   "weight": "180kg",    "rest": "3min"},
        ],
    },
    {
        "day": "Friday",
        "exercises": [
            {"name": "Snatch Balance","sets": "3", "reps": "3",   "percent_1rm": "60%", "rest": "2min", "notes": "Technical focus"},
            {"name": "Overhead Squat","sets": "3", "reps": "3",   "percent_1rm": "65%", "tempo": "3-2-X-1", "rest": "2min"},
            {"name": "Good Morning",  "sets": "3", "reps": "8",   "rest": "90s", "notes": "Hamstring work"},
        ],
    },
]


TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "classic-accumulation": _CLASSIC_ACCUMULATION_WEEK,
}


# ----------------------------------------------------------------------------
# Build helpers
# ----------------------------------------------------------------------------

_EXERCISE_FIELDS = ("sets", "reps", "percent_1rm", "rpe", "weight", "tempo", "rest", "notes")


def _derive_intensity(exercise: dict[str, str]) -> str:
    """Match the frontend's legacy-intensity-field convention: pick the first
    non-empty of % 1RM / RPE / weight so older consumers still render."""
    return exercise.get("percent_1rm") or exercise.get("rpe") or exercise.get("weight") or ""


def _vary_percent(pct: str, rng: random.Random) -> str:
    """Lightly randomize a '75%' style intensity by ±2%. Keeps the roster from
    looking copy-pasted without changing the training stimulus meaningfully."""
    if not pct or not pct.endswith("%"):
        return pct
    try:
        base = int(pct.rstrip("%"))
    except ValueError:
        return pct
    return f"{max(50, min(95, base + rng.randint(-2, 2)))}%"


def build_program_payload(
    athlete_id: int,
    athlete_username: str,
    start_date: Optional[date] = None,
    block_weeks: int = 4,
    program_name: Optional[str] = None,
    description: Optional[str] = None,
    template: str = "classic-accumulation",
    intensity_mode: str = "percent_1rm",
    seed: Optional[int] = None,
) -> dict[str, Any]:
    """Return an API-ready program-creation payload for one athlete.

    `seed` controls per-athlete randomness; defaults to a hash of the
    username so the same athlete gets the same program on re-runs (useful
    for reproducible fixtures). Pass an explicit int to override.
    """
    if template not in TEMPLATES:
        raise ValueError(f"Unknown template '{template}'. Options: {sorted(TEMPLATES)}")
    start = start_date or date.today()
    end = start + timedelta(days=block_weeks * 7 - 1)
    rng = random.Random(seed if seed is not None else hash(athlete_username) & 0xFFFFFFFF)

    days: list[dict[str, Any]] = []
    for index, day_template in enumerate(TEMPLATES[template]):
        exercises: list[dict[str, str]] = []
        for source in day_template["exercises"]:
            # Start from full-schema defaults so every exercise payload carries
            # every field the backend normalizer expects.
            exercise = {field: "" for field in _EXERCISE_FIELDS}
            exercise["name"] = source["name"]
            for field in _EXERCISE_FIELDS:
                if field in source:
                    exercise[field] = str(source[field])
            if exercise.get("percent_1rm"):
                exercise["percent_1rm"] = _vary_percent(exercise["percent_1rm"], rng)
            exercise["intensity"] = _derive_intensity(exercise)
            exercises.append(exercise)

        days.append({
            # Stable id -- matches the frontend's d<N> convention so completion
            # records the athlete logs survive day reorder.
            "id": f"d{index}",
            "day": day_template["day"],
            "exercises": exercises,
        })

    name = program_name or f"Accumulation Block — {athlete_username}"
    return {
        "name": name,
        "description": description or (
            "Auto-generated accumulation block. 5-day classical Olympic "
            "weightlifting week, 70-85% intensity band with a speed day "
            "and a deadlift accessory."
        ),
        "athlete_id": athlete_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "program_data": {
            "week_start_date": start.isoformat(),
            "intensity_mode": intensity_mode,
            "days": days,
        },
    }


def available_templates() -> list[str]:
    return sorted(TEMPLATES.keys())
