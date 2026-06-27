"""Awakened (L4) signature-ability catalog — the mechanical L4 layer of the anomaly system.

Spec: docs/AWAKENED_POWERS_PLAN.md. An awakened player gets ONE fixed signature ability per side,
assigned once at awakening: an OFFENSIVE ability (the broken expression of their best offensive
attribute) and a DEFENSIVE ability (their defensive position's takeaway). Kickers are offense-only.

Ability names are PLACEHOLDERS pending owner finalization. All flavor lines are GENDER-NEUTRAL
(singular they/them/their) — players are any gender.

This module is pure data + lookup helpers (no game effect, no DB). Assignment persistence lives on
AnomalyState; effect resolution (later phases) reads these keys.
"""

# ── Offensive abilities ──────────────────────────────────────────────────────
# position -> {attribute: ability}. Assignment picks the player's HIGHEST attribute among the
# keys for their position and grants the matching ability. The attribute keys ARE the player's
# real offensive attribute names (floosball_player.py).
OFFENSE_ABILITIES = {
    'QB': {
        'armStrength': {'key': 'cannon', 'name': 'Cannon', 'effect': 'deep_bomb', 'flavor': [
            'the ball sprouts wings and soars the length of the field',
            'they wind up and fire a guided missile downfield',
            'the throw breaks the sound barrier and lands 80 yards out',
            'the pass leaves a vapor trail straight to the end zone',
            'they flick their wrist and the ball teleports into waiting hands',
        ]},
        'accuracy': {'key': 'pinpoint', 'name': 'Pinpoint', 'effect': 'sure_completion', 'flavor': [
            'the defenders blur out and a clean lane snaps open',
            'the ball threads a keyhole between three defenders',
            'a glowing target locks onto the receiver and the ball homes in',
            'they draw a line in the air and the pass follows it exactly',
            'the window was an inch wide, so the ball folds itself to fit',
        ]},
        'agility': {'key': 'escape_artist', 'name': 'Escape Artist', 'effect': 'escape_scramble', 'flavor': [
            'they teleport out of the collapsing pocket',
            'the rushers grab a cardboard cutout; the real QB is already gone',
            'the pocket becomes a trampoline and they bounce free',
            'time slows to a crawl while they stroll out of trouble',
            'the sack glitches out and they reappear ten yards downfield',
        ]},
    },
    'RB': {
        'speed': {'key': 'afterburner', 'name': 'Afterburner', 'effect': 'breakaway', 'flavor': [
            'roller skates snap onto their cleats and they are gone',
            'a jetpack flares to life and they rocket through the gap',
            'the turf turns to ice behind them; everyone else wipes out',
            'they hit warp speed and the defenders freeze mid-stride',
            'they run so fast they lap the play and arrive early',
        ]},
        'power': {'key': 'battering_ram', 'name': 'Battering Ram', 'effect': 'truck', 'flavor': [
            'they turn to solid iron and bowl the line over',
            'they double in size and truck the entire pile',
            'tacklers bounce off them like they are made of rubber',
            'they sprout a cattle-catcher and plow everyone aside',
            'they lower a shoulder and the tacklers ragdoll away',
        ]},
        'agility': {'key': 'ghost', 'name': 'Ghost', 'effect': 'phase_through', 'flavor': [
            'they phase clean through the tackle like a ghost',
            'they split into three; the defenders grab the decoys',
            'hands pass right through them as they glide past',
            'they flicker out of existence and reappear past the line',
            'they sidestep into another dimension and back',
        ]},
    },
    'WR': {
        'speed': {'key': 'burner', 'name': 'Burner', 'effect': 'deep_catch', 'flavor': [
            'they leave the corner standing on a pair of roller skates',
            'they shift into a gear the defense does not have',
            'a green streak trails them down the sideline',
            'they blur past the safety before the ball is even thrown',
            'they outrun the spiral and wait for it in the end zone',
        ]},
        'hands': {'key': 'glue_hands', 'name': 'Glue Hands', 'effect': 'sure_catch', 'flavor': [
            'the ball velcros to their palms',
            'their gloves flash and the ball just sticks',
            'they magnetize the ball out of the air',
            'it ricochets off three defenders and glues to them anyway',
            'their hands turn to flypaper; nothing is getting loose',
        ]},
        'reach': {'key': 'stretch', 'name': 'Stretch', 'effect': 'radius_catch', 'flavor': [
            'they conjure a ten-foot net and scoop it in',
            'their arms stretch like taffy across the seam',
            'they sprout a third hand to haul it down',
            'their wingspan triples and they pluck it from the sky',
            'the ball was uncatchable until their arm simply extended to it',
        ]},
    },
    'TE': {
        'hands': {'key': 'glue_hands', 'name': 'Glue Hands', 'effect': 'sure_catch', 'flavor': [
            'the ball velcros to their palms',
            'their gloves flash and the ball just sticks',
            'they magnetize the ball out of the air',
            'it ricochets off three defenders and glues to them anyway',
            'their hands turn to flypaper; nothing is getting loose',
        ]},
        'power': {'key': 'the_wall', 'name': 'The Wall', 'effect': 'contested_catch', 'flavor': [
            'they become an actual brick wall and box everyone out',
            'they expand to fill the entire end zone',
            'defenders bounce off their back as they reel it in',
            'they plant like a redwood; nobody is moving them',
            'the contested catch is not contested — they are just bigger now',
        ]},
        'agility': {'key': 'mismatch', 'name': 'Mismatch', 'effect': 'separation_catch', 'flavor': [
            'they are suddenly too quick for anyone on the field',
            'the linebacker trips over a seam in the turf',
            'the defense covers where they were, not where they are',
            'they run a route that loops back on itself and loses everyone',
            'they shrink to slip the coverage, then pop back open',
        ]},
    },
    'K': {
        'legStrength': {'key': 'howitzer', 'name': 'Howitzer', 'effect': 'fg_range', 'flavor': [
            'the ball turns to a cannonball and booms through from 72',
            'they wind up like a trebuchet and launch it',
            'the kick leaves a crater in the turf and a vapor trail',
            'it clears the uprights and keeps going into the parking lot',
            'the ball sonic-booms through the posts',
        ]},
        'accuracy': {'key': 'dead_center', 'name': 'Dead Center', 'effect': 'fg_sure', 'flavor': [
            'the uprights lean in to catch it',
            'the ball curves on command and splits the middle',
            'a glowing crosshair locks onto the posts',
            'it banks off an invisible wall and drops straight through',
            'the kick cannot miss; the geometry will not allow it',
        ]},
    },
}

# ── Defensive abilities ──────────────────────────────────────────────────────
# Keyed by DEFENSIVE position (derived from the offensive position below). Magnitude is later
# flavored by the player's best attribute (Speed -> longer return, Power -> bigger loss, etc.).
DEFENSE_ABILITIES = {
    'CB': {'key': 'pick_six', 'name': 'Pick-Six', 'effect': 'forced_int_return', 'flavor': [
        'they snag it with a giant baseball mitt and zoom back',
        'they read the throw before the QB does and jump it',
        'they pluck it one-handed and the field clears ahead',
        'they intercept it and the turf rolls out a red carpet to the house',
        'they were covering another route, then teleported to the ball',
    ]},
    'S': {'key': 'ballhawk', 'name': 'Ballhawk', 'effect': 'forced_int_deep', 'flavor': [
        'they cover the whole deep field in one stride',
        'the ball drifts off course and into their arms',
        'they were a step late, so they simply rewound to be early',
        'they materialize under the pass like they always knew',
        'they read the code — they were always going to be there',
    ]},
    'LB': {'key': 'strip_score', 'name': 'Strip & Score', 'effect': 'forced_fumble_return', 'flavor': [
        'they rip the ball loose with a magnet and scoop it',
        'they punch it out and it bounces right back to them',
        'the ball-carrier grip just dissolves on contact',
        'the fumble rolls uphill into their waiting hands',
        'they peel the ball away mid-stride and take off',
    ]},
    'DE': {'key': 'blow_up', 'name': 'Blow-Up', 'effect': 'tfl_sack_strip', 'flavor': [
        'the line evaporates and they are in the backfield instantly',
        'they teleport past the tackle before the snap finishes',
        'the play blows up in a puff of pixels',
        'they meet the runner four yards deep like they were waiting there',
        'they fold the pocket inward and the play collapses',
    ]},
}

# Offensive position -> defensive position (mirrors floosball_player's derived defense:
# QB->S, RB->LB, WR->CB, TE->DE, K->none). Kickers get no defensive ability.
OFFENSE_TO_DEFENSE_POS = {'QB': 'S', 'RB': 'LB', 'WR': 'CB', 'TE': 'DE', 'K': None}

# Flat key -> ability detail lookup (both sides), for resolving a persisted key to its name/flavor.
_BY_KEY = {}
for _posMap in OFFENSE_ABILITIES.values():
    for _ab in _posMap.values():
        _BY_KEY[_ab['key']] = {**_ab, 'side': 'offense'}
for _ab in DEFENSE_ABILITIES.values():
    _BY_KEY[_ab['key']] = {**_ab, 'side': 'defense'}


def normalizePosition(position) -> str:
    """Coerce a player's position (enum or string, possibly slot-suffixed like WR1) to a base
    catalog position: QB / RB / WR / TE / K. Returns '' if unknown."""
    p = getattr(position, 'name', position)
    p = str(p or '').upper()
    for base in ('QB', 'RB', 'WR', 'TE', 'K'):
        if p.startswith(base):
            return base
    return ''


def assignAbilities(position, attributes: dict):
    """Pick the signature abilities for a newly-awakened player.

    position    — the player's offensive position (enum/string; WR1/WR2 ok).
    attributes  — {attrName: value} of the player's offensive attributes.
    Returns (offenseAbilityKey, defenseAbilityKey). defenseAbilityKey is None for kickers.
    Ties on the best attribute fall to the position's signature attribute order (dict order:
    QB Arm, RB Speed, WR Speed, TE Hands, K Leg first), since max() keeps the first max.
    """
    base = normalizePosition(position)
    offMap = OFFENSE_ABILITIES.get(base, {})
    offKey = None
    if offMap:
        bestAttr = max(offMap.keys(), key=lambda a: attributes.get(a, 0))
        offKey = offMap[bestAttr]['key']
    defPos = OFFENSE_TO_DEFENSE_POS.get(base)
    defKey = DEFENSE_ABILITIES[defPos]['key'] if defPos else None
    return offKey, defKey


def abilityDetail(key: str) -> dict:
    """Resolve a persisted ability key to {key, name, effect, flavor, side}, or {} if unknown."""
    return _BY_KEY.get(key, {})


def abilityName(key: str) -> str:
    return _BY_KEY.get(key, {}).get('name', '')
