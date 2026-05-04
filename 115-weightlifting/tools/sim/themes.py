"""Character-name pools for simulation.

Usernames are lowercase + underscore-delimited so they survive Django's
AbstractUser validator (which rejects whitespace and most punctuation).
Lists are intentionally long so large stress-test rosters don't exhaust a
theme.
"""
from __future__ import annotations

from typing import Iterable


GAME_OF_THRONES: list[str] = [
    "jon_snow", "daenerys_targaryen", "tyrion_lannister", "arya_stark",
    "sansa_stark", "bran_stark", "cersei_lannister", "jaime_lannister",
    "brienne_tarth", "sandor_clegane", "gregor_clegane", "theon_greyjoy",
    "yara_greyjoy", "margaery_tyrell", "olenna_tyrell", "petyr_baelish",
    "varys", "davos_seaworth", "stannis_baratheon", "ned_stark",
    "catelyn_stark", "robb_stark", "rickon_stark", "robert_baratheon",
    "tywin_lannister", "khal_drogo", "missandei", "grey_worm", "melisandre",
    "gendry", "podrick_payne", "bronn", "oberyn_martell", "ellaria_sand",
    "ramsay_bolton", "roose_bolton", "samwell_tarly", "gilly",
    "jorah_mormont", "lyanna_mormont", "tormund_giantsbane",
    "ygritte", "mance_rayder", "beric_dondarrion", "thoros_myr",
    "edmure_tully", "walder_frey", "hodor", "osha", "shireen_baratheon",
]

LORD_OF_THE_RINGS: list[str] = [
    "frodo_baggins", "samwise_gamgee", "merry_brandybuck", "pippin_took",
    "gandalf_grey", "aragorn_elessar", "legolas", "gimli", "boromir",
    "arwen", "galadriel", "elrond", "saruman", "gollum", "bilbo_baggins",
    "eowyn", "faramir", "theoden", "eomer", "haldir",
]

THEMES: dict[str, list[str]] = {
    "game-of-thrones": GAME_OF_THRONES,
    "lord-of-the-rings": LORD_OF_THE_RINGS,
}


def roster(theme: str, count: int) -> list[str]:
    """Return the first `count` names from the requested theme.

    Deterministic (not random) so re-running the tool with the same args
    produces the same roster -- important when we later use this for
    predictable stress-test fixtures.
    """
    if theme not in THEMES:
        raise ValueError(
            f"Unknown theme '{theme}'. Options: {sorted(THEMES.keys())}"
        )
    pool = THEMES[theme]
    if count > len(pool):
        raise ValueError(
            f"Theme '{theme}' has {len(pool)} names; {count} requested. "
            "Add more names to themes.py or pick a different theme."
        )
    return pool[:count]


def available_themes() -> Iterable[str]:
    return sorted(THEMES.keys())
