"""Personality system static data.

Defines the three-layer personality model:
- Archetypes: permanent identity, 12 values on a 3x3 alignment grid
- Demeanors: emotional temperament, 6 values on Composed<->Volatile spectrum
- Quirks: optional behavioral tics, 52 values across 4 rarity tiers

Plus compatibility tables and helper functions used by playerManager
(assignment) and personalityManager (drift, template lookup).
"""

from typing import Optional


# ---------------------------------------------------------------------------
# Demeanors -- emotional temperament spectrum
# ---------------------------------------------------------------------------

# Ordered from Composed (0) to Volatile (5). Drift can only move +/- 1 step.
DEMEANOR_SPECTRUM = [
    'stoic',       # 0  flat, controlled
    'cool',        # 1  smooth, confident calm
    'intense',     # 2  focused energy, bridge state
    'melancholy',  # 3  heavy, brooding
    'fiery',       # 4  hot, explosive
    'dramatic',    # 5  amplified to the extreme
]

DEMEANOR_INDEX = {name: idx for idx, name in enumerate(DEMEANOR_SPECTRUM)}

DEMEANOR_DESCRIPTIONS = {
    'stoic':      'Flat, controlled, nothing gets through',
    'cool':       'Smooth, confident calm',
    'intense':    'Focused energy, could tip either way',
    'melancholy': 'Heavy, brooding, internal storms',
    'fiery':      'Hot, explosive, outward energy',
    'dramatic':   'Everything is amplified to the extreme',
}


# ---------------------------------------------------------------------------
# Archetypes -- permanent identity, 3x3 alignment grid
# ---------------------------------------------------------------------------
#
# Grid axes (used for quirk-swap proximity math):
#   selfAxis:       0 = Selfless, 1 = Neutral, 2 = Selfish
#   disciplineAxis: 0 = Disciplined, 1 = Neutral, 2 = Unhinged
#
# Half-step values capture "slightly" and "selfish-neutral" descriptions.

ARCHETYPES = {
    'leader':       {'label': 'Leader',       'selfAxis': 0.5, 'disciplineAxis': 1.5, 'description': 'The one teammates follow. Vocal, takes blame, rallies.'},
    'guardian':     {'label': 'Guardian',     'selfAxis': 0.0, 'disciplineAxis': 0.0, 'description': 'Protects teammates. Selfless, sacrifices stats for the team.'},
    'grinder':      {'label': 'Grinder',      'selfAxis': 0.0, 'disciplineAxis': 0.0, 'description': 'Outworks everyone, no shortcuts. First in last out.'},
    'technician':   {'label': 'Technician',   'selfAxis': 1.5, 'disciplineAxis': 0.0, 'description': 'Precision, mastery of craft. Film study, exploits edges.'},
    'prodigy':      {'label': 'Prodigy',      'selfAxis': 1.0, 'disciplineAxis': 1.0, 'description': 'Natural talent, effortless. Makes it look easy.'},
    'showman':      {'label': 'Showman',      'selfAxis': 2.0, 'disciplineAxis': 1.5, 'description': 'Lives for the spotlight. Celebrations, crowd interaction.'},
    'competitor':   {'label': 'Competitor',   'selfAxis': 2.0, 'disciplineAxis': 2.0, 'description': 'Hates losing more than loves winning. Grudges, revenge games.'},
    'enforcer':     {'label': 'Enforcer',     'selfAxis': 1.5, 'disciplineAxis': 2.0, 'description': 'Physical, intimidating, dominant. Presence felt.'},
    'maverick':     {'label': 'Maverick',     'selfAxis': 0.5, 'disciplineAxis': 2.0, 'description': 'Does things their own way. Unconventional, surprises everyone.'},
    'wild_card':    {'label': 'Wild Card',    'selfAxis': 2.0, 'disciplineAxis': 2.5, 'description': 'Unpredictable. You never know which version shows up.'},
    'professional': {'label': 'Professional', 'selfAxis': 1.0, 'disciplineAxis': 0.0, 'description': 'Competent, no drama. Does the job, goes home.'},
    'journeyman':   {'label': 'Journeyman',   'selfAxis': 1.0, 'disciplineAxis': 1.0, 'description': 'Solid, dependable, forgettable.'},
}

ARCHETYPE_KEYS = list(ARCHETYPES.keys())

# Rarity weights for archetype assignment at player generation.
# Professional and Journeyman are the "ordinary" archetypes (~10% each).
ARCHETYPE_WEIGHTS = {
    'leader':       10,
    'guardian':     10,
    'grinder':      10,
    'technician':   10,
    'prodigy':       8,
    'showman':      10,
    'competitor':   10,
    'enforcer':     10,
    'maverick':      8,
    'wild_card':     6,
    'professional': 10,
    'journeyman':   10,
}


# ---------------------------------------------------------------------------
# Quirks -- optional behavioral tics, 52 total
# ---------------------------------------------------------------------------
#
# Each quirk entry specifies:
#   label:           display name
#   tier:            'common' | 'uncommon' | 'rare' | 'unique'
#   bucket:          'universal' | 'constrained' | 'exclusive'
#   demeanorRange:   (lowIndex, highIndex) inclusive on DEMEANOR_SPECTRUM
#   archetypes:      list of archetype keys this quirk is eligible for
#
# Ranges are contiguous. Assignment intersects archetype AND demeanor filters.

QUIRK_TIERS = ['common', 'uncommon', 'rare', 'unique']

# Rarity roll percentages (see plan: 75 / 20 / 4 / 1)
QUIRK_TIER_WEIGHTS = {
    'common':   75,
    'uncommon': 20,
    'rare':      4,
    'unique':    1,
}

# Soft caps on active quirks per tier (None = uncapped).
QUIRK_TIER_CAPS = {
    'common':   None,
    'uncommon': 8,   # ~5-10 per league
    'rare':     3,   # ~2-3 per league
    'unique':   1,   # exactly 1 active
}

# Per-quirk Common-tier target share of the quirked-player pool (~8-10%).
COMMON_QUIRK_TARGET_SHARE = 0.09

# Probability that a newly generated player gets any quirk.
QUIRKED_PLAYER_RATE = 0.35


def _range(low: str, high: str) -> tuple:
    return (DEMEANOR_INDEX[low], DEMEANOR_INDEX[high])


QUIRKS = {
    # -------------------- Common (11) --------------------
    'wholesome': {
        'label': 'Wholesome', 'tier': 'common', 'bucket': 'constrained',
        'demeanorRange': _range('cool', 'fiery'),
        'archetypes': ['leader', 'guardian', 'grinder', 'maverick', 'prodigy', 'professional', 'journeyman'],
    },
    'paranoid': {
        'label': 'Paranoid', 'tier': 'common', 'bucket': 'constrained',
        'demeanorRange': _range('intense', 'dramatic'),
        'archetypes': ['leader', 'technician', 'prodigy', 'showman', 'competitor', 'enforcer', 'maverick', 'wild_card'],
    },
    'hothead': {
        'label': 'Hothead', 'tier': 'common', 'bucket': 'constrained',
        'demeanorRange': _range('intense', 'dramatic'),
        'archetypes': ['leader', 'showman', 'competitor', 'enforcer', 'maverick', 'wild_card'],
    },
    'goofy': {
        'label': 'Goofy', 'tier': 'common', 'bucket': 'constrained',
        'demeanorRange': _range('cool', 'dramatic'),
        'archetypes': ['leader', 'guardian', 'maverick', 'prodigy', 'showman', 'journeyman'],
    },
    'wallflower': {
        'label': 'Wallflower', 'tier': 'common', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'melancholy'),
        'archetypes': ['grinder', 'technician', 'professional', 'journeyman'],
    },
    'motormouth': {
        'label': 'Motormouth', 'tier': 'common', 'bucket': 'constrained',
        'demeanorRange': _range('cool', 'dramatic'),
        'archetypes': ['leader', 'showman', 'competitor', 'enforcer', 'wild_card'],
    },
    'showboat': {
        'label': 'Showboat', 'tier': 'common', 'bucket': 'constrained',
        'demeanorRange': _range('cool', 'dramatic'),
        'archetypes': ['leader', 'showman', 'competitor', 'wild_card', 'maverick', 'prodigy'],
    },
    'perfectionist': {
        'label': 'Perfectionist', 'tier': 'common', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'dramatic'),
        'archetypes': ['guardian', 'grinder', 'technician', 'professional'],
    },
    'superstitious': {
        'label': 'Superstitious', 'tier': 'common', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'dramatic'),
        'archetypes': ['leader', 'guardian', 'grinder', 'technician', 'prodigy', 'showman', 'competitor', 'enforcer', 'journeyman'],
    },
    'oblivious': {
        'label': 'Oblivious', 'tier': 'common', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'cool'),
        'archetypes': ['grinder', 'prodigy', 'showman', 'competitor', 'enforcer', 'maverick', 'wild_card', 'professional', 'journeyman'],
    },
    'enigmatic': {
        'label': 'Enigmatic', 'tier': 'common', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'melancholy'),
        'archetypes': ['leader', 'guardian', 'technician', 'prodigy', 'showman', 'competitor', 'enforcer', 'maverick', 'wild_card', 'journeyman'],
    },

    # -------------------- Uncommon (19) --------------------
    'hugger': {
        'label': 'Hugger', 'tier': 'uncommon', 'bucket': 'constrained',
        'demeanorRange': _range('cool', 'dramatic'),
        'archetypes': ['leader', 'guardian', 'grinder', 'maverick', 'showman', 'prodigy', 'journeyman'],
    },
    'vain': {
        'label': 'Vain', 'tier': 'uncommon', 'bucket': 'constrained',
        'demeanorRange': _range('cool', 'dramatic'),
        'archetypes': ['showman', 'competitor', 'prodigy', 'wild_card', 'enforcer', 'technician'],
    },
    'bling': {
        'label': 'Bling', 'tier': 'uncommon', 'bucket': 'constrained',
        'demeanorRange': _range('cool', 'dramatic'),
        'archetypes': ['leader', 'showman', 'competitor', 'enforcer', 'wild_card', 'prodigy'],
    },
    'tinfoil': {
        'label': 'Tinfoil', 'tier': 'uncommon', 'bucket': 'constrained',
        'demeanorRange': _range('intense', 'dramatic'),
        'archetypes': ['technician', 'maverick', 'competitor', 'enforcer', 'wild_card'],
    },
    'gym_rat': {
        'label': 'Gym Rat', 'tier': 'uncommon', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'dramatic'),
        'archetypes': ['guardian', 'grinder', 'technician', 'competitor', 'enforcer', 'professional'],
    },
    'prankster': {
        'label': 'Prankster', 'tier': 'uncommon', 'bucket': 'constrained',
        'demeanorRange': _range('cool', 'dramatic'),
        'archetypes': ['leader', 'showman', 'maverick', 'prodigy', 'wild_card'],
    },
    'snacker': {
        'label': 'Snacker', 'tier': 'uncommon', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'dramatic'),
        'archetypes': ['leader', 'technician', 'prodigy', 'showman', 'competitor', 'enforcer', 'maverick', 'wild_card', 'professional', 'journeyman'],
    },
    'trash_talker': {
        'label': 'Trash-Talker', 'tier': 'uncommon', 'bucket': 'constrained',
        'demeanorRange': _range('cool', 'dramatic'),
        'archetypes': ['leader', 'technician', 'showman', 'competitor', 'enforcer', 'maverick', 'wild_card'],
    },
    'ear_buds': {
        'label': 'Ear Buds', 'tier': 'uncommon', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'melancholy'),
        'archetypes': ['guardian', 'grinder', 'technician', 'prodigy', 'enforcer', 'maverick', 'wild_card', 'professional', 'journeyman'],
    },
    'ref_yeller': {
        'label': 'Ref-Yeller', 'tier': 'uncommon', 'bucket': 'constrained',
        'demeanorRange': _range('intense', 'dramatic'),
        'archetypes': ['leader', 'showman', 'competitor', 'enforcer', 'maverick', 'wild_card'],
    },
    'phone_addict': {
        'label': 'Phone Addict', 'tier': 'uncommon', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'dramatic'),
        'archetypes': ['prodigy', 'showman', 'wild_card', 'professional', 'journeyman'],
    },
    'pacer': {
        'label': 'Pacer', 'tier': 'uncommon', 'bucket': 'constrained',
        'demeanorRange': _range('intense', 'dramatic'),
        'archetypes': ['leader', 'competitor', 'enforcer', 'maverick', 'wild_card'],
    },
    'hydrated': {
        'label': 'Hydrated', 'tier': 'uncommon', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'dramatic'),
        'archetypes': ['leader', 'guardian', 'grinder', 'technician', 'prodigy', 'competitor', 'enforcer', 'maverick', 'professional', 'journeyman'],
    },
    'napper': {
        'label': 'Napper', 'tier': 'uncommon', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'cool'),
        'archetypes': ['prodigy', 'maverick', 'wild_card', 'professional', 'journeyman'],
    },
    'gum_chewer': {
        'label': 'Gum Chewer', 'tier': 'uncommon', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'dramatic'),
        'archetypes': ['leader', 'prodigy', 'showman', 'competitor', 'enforcer', 'maverick', 'wild_card', 'professional', 'journeyman'],
    },
    'hype_man': {
        'label': 'Hype Man', 'tier': 'uncommon', 'bucket': 'constrained',
        'demeanorRange': _range('intense', 'dramatic'),
        'archetypes': ['leader', 'guardian', 'grinder', 'showman', 'maverick', 'prodigy', 'professional', 'journeyman'],
    },
    'whistler': {
        'label': 'Whistler', 'tier': 'uncommon', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'fiery'),
        'archetypes': ['prodigy', 'maverick', 'wild_card', 'professional', 'journeyman'],
    },
    'gamer': {
        'label': 'Gamer', 'tier': 'uncommon', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'dramatic'),
        'archetypes': ['technician', 'prodigy', 'maverick', 'wild_card', 'professional', 'journeyman'],
    },
    'reader': {
        'label': 'Reader', 'tier': 'uncommon', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'melancholy'),
        'archetypes': ['guardian', 'technician', 'prodigy', 'maverick', 'professional', 'journeyman'],
    },

    # -------------------- Rare (11) --------------------
    'sleepwalker': {
        'label': 'Sleepwalker', 'tier': 'rare', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'cool'),
        'archetypes': ['prodigy', 'maverick', 'wild_card', 'journeyman'],
    },
    'ghost': {
        'label': 'Ghost', 'tier': 'rare', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'melancholy'),
        'archetypes': ['grinder', 'technician', 'prodigy', 'maverick', 'professional', 'journeyman'],
    },
    'singer': {
        'label': 'Singer', 'tier': 'rare', 'bucket': 'constrained',
        'demeanorRange': _range('cool', 'dramatic'),
        'archetypes': ['leader', 'guardian', 'showman', 'maverick', 'prodigy', 'professional', 'journeyman'],
    },
    'sketcher': {
        'label': 'Sketcher', 'tier': 'rare', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'melancholy'),
        'archetypes': ['grinder', 'technician', 'prodigy', 'maverick', 'professional', 'journeyman'],
    },
    'gambler': {
        'label': 'Gambler', 'tier': 'rare', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'dramatic'),
        'archetypes': ['showman', 'competitor', 'enforcer', 'maverick', 'wild_card'],
    },
    'insomniac': {
        'label': 'Insomniac', 'tier': 'rare', 'bucket': 'constrained',
        'demeanorRange': _range('intense', 'dramatic'),
        'archetypes': ['leader', 'grinder', 'showman', 'competitor', 'wild_card'],
    },
    'stargazer': {
        'label': 'Stargazer', 'tier': 'rare', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'melancholy'),
        'archetypes': ['technician', 'prodigy', 'maverick', 'professional', 'journeyman'],
    },
    'zealot': {
        'label': 'Zealot', 'tier': 'rare', 'bucket': 'exclusive',
        'demeanorRange': _range('stoic', 'dramatic'),
        'archetypes': ['competitor', 'enforcer', 'maverick', 'wild_card'],
    },
    'existential': {
        'label': 'Existential', 'tier': 'rare', 'bucket': 'constrained',
        'demeanorRange': _range('intense', 'dramatic'),
        'archetypes': ['technician', 'prodigy', 'maverick', 'wild_card', 'journeyman'],
    },
    'nihilist': {
        'label': 'Nihilist', 'tier': 'rare', 'bucket': 'constrained',
        'demeanorRange': _range('stoic', 'melancholy'),
        'archetypes': ['technician', 'prodigy', 'maverick', 'wild_card', 'professional', 'journeyman'],
    },
    'streamer': {
        'label': 'Streamer', 'tier': 'rare', 'bucket': 'constrained',
        'demeanorRange': _range('cool', 'dramatic'),
        'archetypes': ['leader', 'showman', 'competitor', 'prodigy', 'maverick', 'wild_card'],
    },

    # -------------------- Unique (11) -- all exclusive, 1 active at a time --------------------
    'fossil': {
        'label': 'Fossil', 'tier': 'unique', 'bucket': 'exclusive',
        'demeanorRange': _range('stoic', 'melancholy'),
        'archetypes': ['guardian', 'grinder', 'technician', 'professional', 'journeyman'],
    },
    'alien': {
        'label': 'Alien', 'tier': 'unique', 'bucket': 'exclusive',
        'demeanorRange': _range('stoic', 'dramatic'),
        'archetypes': ['prodigy', 'maverick', 'wild_card'],
    },
    'prophet': {
        'label': 'Prophet', 'tier': 'unique', 'bucket': 'exclusive',
        'demeanorRange': _range('stoic', 'dramatic'),
        'archetypes': ['technician', 'prodigy', 'maverick', 'wild_card'],
    },
    'relic': {
        'label': 'Relic', 'tier': 'unique', 'bucket': 'exclusive',
        'demeanorRange': _range('stoic', 'fiery'),
        'archetypes': ['guardian', 'grinder', 'technician', 'professional', 'journeyman'],
    },
    'disinterested': {
        'label': 'Disinterested', 'tier': 'unique', 'bucket': 'exclusive',
        'demeanorRange': _range('stoic', 'melancholy'),
        'archetypes': ['prodigy', 'maverick', 'wild_card'],
    },
    'twin': {
        'label': 'Twin', 'tier': 'unique', 'bucket': 'exclusive',
        'demeanorRange': _range('stoic', 'melancholy'),
        'archetypes': ['technician', 'prodigy', 'maverick', 'wild_card', 'journeyman'],
    },
    'nameless': {
        'label': 'Nameless', 'tier': 'unique', 'bucket': 'exclusive',
        'demeanorRange': _range('stoic', 'melancholy'),
        'archetypes': ['enforcer', 'maverick', 'wild_card'],
    },
    'cursed': {
        'label': 'Cursed', 'tier': 'unique', 'bucket': 'exclusive',
        'demeanorRange': _range('intense', 'dramatic'),
        'archetypes': ['competitor', 'enforcer', 'maverick', 'wild_card'],
    },
    'time_traveler': {
        'label': 'Time Traveler', 'tier': 'unique', 'bucket': 'exclusive',
        'demeanorRange': _range('stoic', 'dramatic'),
        'archetypes': ['prodigy', 'maverick', 'wild_card'],
    },
    'silent': {
        'label': 'Silent', 'tier': 'unique', 'bucket': 'exclusive',
        'demeanorRange': _range('stoic', 'melancholy'),
        'archetypes': ['guardian', 'grinder', 'technician', 'enforcer', 'professional'],
    },
    'fourth_wall': {
        'label': '4th Wall', 'tier': 'unique', 'bucket': 'exclusive',
        'demeanorRange': _range('stoic', 'dramatic'),
        'archetypes': ['prodigy', 'showman', 'maverick', 'wild_card'],
    },
}

QUIRK_KEYS = list(QUIRKS.keys())


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def getDemeanorIndex(demeanor: str) -> Optional[int]:
    """Return the spectrum index (0-5) of a demeanor, or None if unknown."""
    return DEMEANOR_INDEX.get(demeanor)


def getAdjacentDemeanors(demeanor: str) -> list:
    """Return the demeanors one step away on the spectrum (0, 1, or 2 values)."""
    idx = DEMEANOR_INDEX.get(demeanor)
    if idx is None:
        return []
    neighbors = []
    if idx > 0:
        neighbors.append(DEMEANOR_SPECTRUM[idx - 1])
    if idx < len(DEMEANOR_SPECTRUM) - 1:
        neighbors.append(DEMEANOR_SPECTRUM[idx + 1])
    return neighbors


def isQuirkCompatible(quirkKey: str, archetype: str, demeanor: str) -> bool:
    """True if the quirk fits both the archetype and current demeanor."""
    quirk = QUIRKS.get(quirkKey)
    if not quirk:
        return False
    if archetype not in quirk['archetypes']:
        return False
    idx = DEMEANOR_INDEX.get(demeanor)
    if idx is None:
        return False
    low, high = quirk['demeanorRange']
    return low <= idx <= high


def getEligibleQuirks(archetype: str, demeanor: str, tier: Optional[str] = None) -> list:
    """Return quirk keys compatible with (archetype, demeanor), optionally
    filtered to a specific rarity tier."""
    eligible = []
    for key, quirk in QUIRKS.items():
        if tier is not None and quirk['tier'] != tier:
            continue
        if isQuirkCompatible(key, archetype, demeanor):
            eligible.append(key)
    return eligible


def getArchetypeGridPosition(archetype: str) -> Optional[tuple]:
    """Return (selfAxis, disciplineAxis) for an archetype, or None."""
    entry = ARCHETYPES.get(archetype)
    if not entry:
        return None
    return (entry['selfAxis'], entry['disciplineAxis'])


def getQuirkLabel(quirkKey: str) -> str:
    """Display label for a quirk key, or empty string if missing."""
    quirk = QUIRKS.get(quirkKey)
    return quirk['label'] if quirk else ''


def getArchetypeLabel(archetypeKey: str) -> str:
    """Display label for an archetype key, or empty string if missing."""
    entry = ARCHETYPES.get(archetypeKey)
    return entry['label'] if entry else ''


def getQuirkTier(quirkKey: str) -> Optional[str]:
    quirk = QUIRKS.get(quirkKey)
    return quirk['tier'] if quirk else None
