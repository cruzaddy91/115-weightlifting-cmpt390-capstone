"""Fictional body mass + sex category for demo accounts (weightlifting simulation).

These values exist only to drive IWF-style *display* classes and plausible demo
charts. They are not medical records, casting specs, or open claims about any
performer. Unknown / future roster names fall back to a small rotating default.

The first five Game of Thrones usernames match ``ATHLETE_PROFILES`` in
``src/backend/apps/athletes/long_history_seed.py`` so HTTP seed + Django bulk
history stay aligned. The first five **lord-of-the-rings** names used for
Coachtwo must match the same file's LotR entries.
"""
from __future__ import annotations

# (bodyweight_kg, gender) — gender must be M or F for class labels.
_SIM_BODIES: dict[str, tuple[float, str]] = {
    # --- keep in sync with long_history_seed.ATHLETE_PROFILES (bodyweight, gender)
    "jon_snow": (85.0, "M"),
    "arya_stark": (55.0, "F"),
    "tyrion_lannister": (67.0, "M"),
    "daenerys_targaryen": (64.0, "F"),
    "sansa_stark": (71.0, "F"),
    # --- remainder: plausible stature mixes for sim (rounded kg)
    "bran_stark": (58.0, "M"),
    "cersei_lannister": (58.0, "F"),
    "jaime_lannister": (82.0, "M"),
    "brienne_tarth": (84.0, "F"),
    "sandor_clegane": (98.0, "M"),
    "gregor_clegane": (118.0, "M"),
    "theon_greyjoy": (72.0, "M"),
    "yara_greyjoy": (68.0, "F"),
    "margaery_tyrell": (56.0, "F"),
    "olenna_tyrell": (54.0, "F"),
    "petyr_baelish": (70.0, "M"),
    "varys": (72.0, "M"),
    "davos_seaworth": (76.0, "M"),
    "stannis_baratheon": (79.0, "M"),
    "ned_stark": (84.0, "M"),
    "catelyn_stark": (62.0, "F"),
    "robb_stark": (80.0, "M"),
    "rickon_stark": (52.0, "M"),
    "robert_baratheon": (110.0, "M"),
    "tywin_lannister": (76.0, "M"),
    "khal_drogo": (92.0, "M"),
    "missandei": (50.0, "F"),
    "grey_worm": (78.0, "M"),
    "melisandre": (58.0, "F"),
    "gendry": (82.0, "M"),
    "podrick_payne": (65.0, "M"),
    "bronn": (78.0, "M"),
    "oberyn_martell": (75.0, "M"),
    "ellaria_sand": (58.0, "F"),
    "ramsay_bolton": (74.0, "M"),
    "roose_bolton": (77.0, "M"),
    "samwell_tarly": (108.0, "M"),
    "gilly": (52.0, "F"),
    "jorah_mormont": (88.0, "M"),
    "lyanna_mormont": (48.0, "F"),
    "tormund_giantsbane": (96.0, "M"),
    "ygritte": (58.0, "F"),
    "mance_rayder": (82.0, "M"),
    "beric_dondarrion": (74.0, "M"),
    "thoros_myr": (88.0, "M"),
    "edmure_tully": (78.0, "M"),
    "walder_frey": (72.0, "M"),
    "hodor": (118.0, "M"),
    "osha": (64.0, "F"),
    "shireen_baratheon": (48.0, "F"),
    # Lord of the Rings pool (fiction-appropriate compact / tall / stocky mixes)
    "frodo_baggins": (58.0, "M"),
    "samwise_gamgee": (72.0, "M"),
    "merry_brandybuck": (58.0, "M"),
    "pippin_took": (56.0, "M"),
    "gandalf_grey": (82.0, "M"),
    "aragorn_elessar": (88.0, "M"),
    "legolas": (78.0, "M"),
    "gimli": (95.0, "M"),
    "boromir": (92.0, "M"),
    "arwen": (56.0, "F"),
    "galadriel": (62.0, "F"),
    "elrond": (78.0, "M"),
    "saruman": (80.0, "M"),
    "gollum": (45.0, "M"),
    "bilbo_baggins": (58.0, "M"),
    "eowyn": (62.0, "F"),
    "faramir": (78.0, "M"),
    "theoden": (76.0, "M"),
    "eomer": (86.0, "M"),
    "haldir": (74.0, "M"),
}

_FALLBACK: tuple[tuple[float, str], ...] = (
    (78.0, "M"),
    (60.0, "F"),
    (85.0, "M"),
    (64.0, "F"),
    (72.0, "M"),
)


def resolve_sim_profile(username: str, roster_index: int) -> tuple[float, str]:
    """Return (bodyweight_kg, gender) for simulation seeding."""
    hit = _SIM_BODIES.get(username)
    if hit:
        return hit
    return _FALLBACK[roster_index % len(_FALLBACK)]
