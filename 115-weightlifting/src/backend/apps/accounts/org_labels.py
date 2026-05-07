import re

from apps.accounts.canonical_usernames import (
    DEMO_ATHLETE_USERNAME,
    DEMO_COACH_USERNAME,
    DEMO_HEAD_COACH_USERNAMES,
    DEMO_LINE_COACH_SLOT_B_USERNAMES,
    DEMO_LINE_COACH_USERNAMES,
    DEMO_UNASSIGNED_ATHLETE_USERNAMES,
    MASTER_HEAD_USERNAME,
)

MASTER_HEAD_LABEL = '117_MASTER_CHIEF'

GM_PREFIX = '117'
AGM_PREFIXES = {'001', '002', '003', '004'}
RESERVED_ORG_PREFIXES = AGM_PREFIXES | {GM_PREFIX}
NORMAL_MEMBER_PREFIXES = {'000'} | {f'{prefix:03d}' for prefix in range(5, 100)}
PREFIX_RE = re.compile(r'^(\d{3})_')

ORG_LABELS = {
    '117': {
        'label': MASTER_HEAD_LABEL,
        'color_key': 'sage-green',
        'color_label': 'Sage Green',
    },
    '001': {
        'label': '001_INFINITY',
        'color_key': 'gun-silver',
        'color_label': 'Gun Silver',
    },
    '002': {
        'label': '002_REACH',
        'color_key': 'shell-copper',
        'color_label': 'Shell Copper',
    },
    '003': {
        'label': '003_FORERUNNER',
        'color_key': 'sand-tan',
        'color_label': 'Sand Tan',
    },
    '004': {
        'label': '004_ODST',
        'color_key': 'steel-blue',
        'color_label': 'Steel Blue',
    },
}

DEFAULT_ORG_META = {
    'org_prefix': None,
    'org_label': 'XXX_UNASSIGNED',
    'org_color_key': 'graphite',
    'org_color_label': 'Graphite',
}


def username_prefix(username):
    match = PREFIX_RE.match(username or '')
    return match.group(1) if match else None


def org_meta_for_prefix(prefix):
    if prefix in ORG_LABELS:
        data = ORG_LABELS[prefix]
        return {
            'org_prefix': prefix,
            'org_label': data['label'],
            'org_color_key': data['color_key'],
            'org_color_label': data['color_label'],
        }
    return dict(DEFAULT_ORG_META)


def is_master_head_user(user):
    return getattr(user, 'user_type', None) == 'head_coach' and username_prefix(getattr(user, 'username', '')) == '117'


def effective_org_source(user):
    if getattr(user, 'user_type', None) == 'athlete':
        coach = getattr(user, 'primary_coach', None)
        if coach is None:
            return None
        if getattr(coach, 'user_type', None) == 'coach':
            return getattr(coach, 'reports_to', None) or coach
        return coach
    if getattr(user, 'user_type', None) == 'coach':
        return getattr(user, 'reports_to', None) or user
    return user


def org_meta_for_user(user):
    explicit_prefix = getattr(user, 'org_lane_prefix', '') or ''
    if explicit_prefix:
        return org_meta_for_prefix(explicit_prefix)
    source = effective_org_source(user)
    source_prefix = getattr(source, 'org_lane_prefix', '') or ''
    if source_prefix:
        return org_meta_for_prefix(source_prefix)
    return org_meta_for_prefix(username_prefix(getattr(source, 'username', '')))
