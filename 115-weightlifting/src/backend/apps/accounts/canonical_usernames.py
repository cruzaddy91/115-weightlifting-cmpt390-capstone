"""Canonical username shapes for demo and pkg_large baseline.

Pattern: ``{XXX}_{Role}_{verbal}`` where ``verbal`` spells the decimal digits of the
numeric prefix (``013`` → ``onethree``, ``008`` → ``eight``).

Exception: ``117_HeadCoachGM`` — GM handle does not verbalize ``117``.

Reserved prefixes: ``117`` (GM), ``001``–``004`` (AGM lane heads), eight line-coach
prefixes (slot A/B). Athletes use the next smallest available normal-member prefixes
from ``000`` then ``005``–``099`` excluding reserved — **32** canonical athlete slots for
the baseline roster.
"""
from __future__ import annotations

_DIGIT_WORDS = ('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine')

LANES = ('001', '002', '003', '004')

MASTER_HEAD_USERNAME = '117_HeadCoachGM'

CANONICAL_LINE_COACH_PREFIXES_SLOT_A = ('008', '013', '048', '088')
CANONICAL_LINE_COACH_PREFIXES_SLOT_B = ('022', '023', '024', '025')

CANONICAL_RESERVED_MEMBER_PREFIXES = frozenset(
    {'117', '001', '002', '003', '004', *CANONICAL_LINE_COACH_PREFIXES_SLOT_A, *CANONICAL_LINE_COACH_PREFIXES_SLOT_B},
)


def verbal_numeric_suffix(prefix_3: str) -> str:
    """Spell ``int(prefix_3)`` digit-by-digit (e.g. ``013`` → ``onethree``)."""
    return ''.join(_DIGIT_WORDS[int(d)] for d in str(int(prefix_3)))


def agm_head_username(lane: str) -> str:
    return f'{lane}_HeadCoach_{verbal_numeric_suffix(lane)}'


def coach_username(prefix: str) -> str:
    return f'{prefix}_Coach_{verbal_numeric_suffix(prefix)}'


def athlete_username(prefix: str) -> str:
    return f'{prefix}_Athlete_{verbal_numeric_suffix(prefix)}'


def _ordered_member_prefixes() -> tuple[str, ...]:
    parts = ['000']
    parts.extend(f'{n:03d}' for n in range(5, 100))
    return tuple(parts)


def canonical_athlete_prefixes_n(count: int = 32) -> tuple[str, ...]:
    out: list[str] = []
    for p in _ordered_member_prefixes():
        if p in CANONICAL_RESERVED_MEMBER_PREFIXES:
            continue
        out.append(p)
        if len(out) >= count:
            return tuple(out)
    raise RuntimeError('insufficient member prefixes for canonical athlete pool')


CANONICAL_ATHLETE_PREFIXES_32 = canonical_athlete_prefixes_n(32)

ALL_DEMO_RESERVED_MEMBER_PREFIXES = CANONICAL_RESERVED_MEMBER_PREFIXES | set(CANONICAL_ATHLETE_PREFIXES_32)

DEMO_HEAD_COACH_USERNAMES = (MASTER_HEAD_USERNAME,) + tuple(agm_head_username(lane) for lane in LANES)

DEMO_LINE_COACH_USERNAMES = tuple(coach_username(p) for p in CANONICAL_LINE_COACH_PREFIXES_SLOT_A)
DEMO_LINE_COACH_SLOT_B_USERNAMES = tuple(coach_username(p) for p in CANONICAL_LINE_COACH_PREFIXES_SLOT_B)

DEMO_COACH_USERNAME = DEMO_LINE_COACH_USERNAMES[0]

DEMO_ATHLETE_USERNAME = athlete_username(CANONICAL_ATHLETE_PREFIXES_32[0])
DEMO_UNASSIGNED_ATHLETE_USERNAMES = tuple(
    athlete_username(p) for p in CANONICAL_ATHLETE_PREFIXES_32[1:]
)

PKG_LARGE_BASELINE_ATHLETE_COUNT = 32
PKG_LARGE_LINE_COACH_COUNT = 8

# Optional inactive skeleton props (none by default).
DEMO_STANDALONE_HEAD_COACH_USERNAMES: tuple[str, ...] = ()

_LEGACY_PRIMARY_ATHLETE = ('000_Athlete1', DEMO_ATHLETE_USERNAME)
_LEGACY_UNASSIGNED_ATHLETES: tuple[tuple[str, str], ...] = tuple(
    zip(
        (
            '005_Athlete2',
            '006_Athlete3',
            '007_Athlete4',
            '009_Athlete5',
            '010_Athlete6',
            '011_Athlete7',
            '012_Athlete8',
            '014_Athlete9',
            '015_Athlete10',
            '016_Athlete11',
            '017_Athlete12',
            '018_Athlete13',
            '019_Athlete14',
            '020_Athlete15',
            '021_Athlete16',
        ),
        DEMO_UNASSIGNED_ATHLETE_USERNAMES[:15],
    ),
)

_LEGACY_HEAD_COACHES: tuple[tuple[str, str], ...] = (
    ('001_Headcoachone', agm_head_username('001')),
    ('002_Headcoachtwo', agm_head_username('002')),
    ('003_Headcoachthree', agm_head_username('003')),
    ('004_Headcoachfour', agm_head_username('004')),
)

_LEGACY_LINE_COACHES: tuple[tuple[str, str], ...] = (
    ('008_Coachone', coach_username('008')),
    ('013_Coachtwo', coach_username('013')),
    ('048_Coachthree', coach_username('048')),
    ('088_Coachtfour', coach_username('088')),
    ('022_CoachB001', coach_username('022')),
    ('023_CoachB002', coach_username('023')),
    ('024_CoachB003', coach_username('024')),
    ('025_CoachB004', coach_username('025')),
)

_LEGACY_GM_ALIASES: tuple[tuple[str, str], ...] = (
    ('117_HeadcoachGM', MASTER_HEAD_USERNAME),
    ('117_Headcoachone', MASTER_HEAD_USERNAME),
)

LEGACY_USERNAME_TO_CANONICAL: tuple[tuple[str, str], ...] = (
    *_LEGACY_GM_ALIASES,
    *_LEGACY_HEAD_COACHES,
    *_LEGACY_LINE_COACHES,
    _LEGACY_PRIMARY_ATHLETE,
    *_LEGACY_UNASSIGNED_ATHLETES,
)
