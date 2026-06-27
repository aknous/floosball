"""Awakened (L4) signature powers — catalog + lookup.

Each awakened player carries ONE power for their career (their identity). When charged and they're
the focal point of a play, the power fires and makes that play succeed hugely — narrated with the
flavor for THAT situation. A power only fires in the situations it covers (Magnet works on a catch,
not a run). docs/AWAKENED_POWERS_PLAN.md.

──────────────────────────────────────────────────────────────────────────────────────────────────
EDITING GUIDE — this file is meant to be edited freely:
  • Change text:  edit the flavor lists. Each string is one narration line, rolled at random on fire.
  • Add a situation to a power:  add e.g.  'kick': ['...'],  to that power's block.
  • Remove a situation:  delete its key (the power just won't fire there).
  • Add a brand-new power:  copy a block, give it a unique key + name + concept + situation flavor.
  • Add a whole new SITUATION TYPE:  add it to SITUATIONS, and (if it needs a defensive mapping or a
    new effect) wire it in P3. _validate() runs at import and flags any unknown/typo situation key.
  All flavor is GENDER-NEUTRAL (singular they/them/their). Names are PLACEHOLDERS pending finalize.
──────────────────────────────────────────────────────────────────────────────────────────────────
"""
import random as _random

# The situations a player can be the focal point of. A power provides flavor only for the ones it
# covers. To add a new situation type, add it here (and wire its effect in P3).
SITUATIONS = ('throw', 'run', 'catch', 'kick', 'defense')

# A player's PRIMARY situation by offensive position. Assignment rolls a power that COVERS this, so
# the power fires regularly. The power also fires in any OTHER situation it covers (incl. defense).
PRIMARY_SITUATION = {'QB': 'throw', 'RB': 'run', 'WR': 'catch', 'TE': 'catch', 'K': 'kick'}

# When a power fires on 'defense', the concrete takeaway is the player's defensive-position effect
# (implemented in P3). QB->S deep pick, RB->LB strip, WR->CB pick, TE->DE collapse, K->no defense.
DEFENSE_EFFECT_BY_POS = {'QB': 'pick', 'RB': 'strip', 'WR': 'pick', 'TE': 'collapse', 'K': None}

# ── Catalog ─────────────────────────────────────────────────────────────────────────────────────
# key: {name, concept, <situation>: [flavor lines], ...}  — omit situations the power can't do.
_POWERS = {
    # ---- Universal (cover every situation) ----
    'no_clip': {'name': 'No-Clip', 'concept': 'phases through solid matter like a glitch in the world',
        'throw': ['the ball phases straight through three defenders untouched',
                  'the pass clips through a linebacker like he is not there'],
        'run':   ['they phase clean through the tackle', 'hands pass right through them as they glide by'],
        'catch': ['the ball passes through the defender and sticks in their hands',
                  'they reach a hand through the corner and pull it in'],
        'kick':  ['the ball phases through the line and the uprights'],
        'defense': ['they phase through the blocker and rip the ball loose',
                    'they clip through the pile and come out the other side with it']},

    'pixelate': {'name': 'Pixelate', 'concept': 'disassembles into pixels and reassembles downfield',
        'throw': ['the throw scatters into pixels, streams past the rush, and reforms in stride'],
        'run':   ['they burst into pixels and reassemble ten yards downfield',
                  'the tackle closes on a cloud of static; they reform past it'],
        'catch': ['they dissolve, drift past the coverage, and rebuild around the ball'],
        'defense': ['they pixel-scatter through the line and reassemble on the ball']},

    'take_flight': {'name': 'Take Flight', 'concept': 'simply takes off and flies',
        'run':   ['they lift off and soar over the defense to the end zone',
                  'cleats leave the turf and they glide the last forty untouched'],
        'catch': ['they launch into the air, hang there, and pluck it from the sky'],
        'defense': ['they take off, track the ball in flight, and snatch it down']},

    # ---- Throw-home (QB) ----
    'railgun': {'name': 'Railgun', 'concept': 'fires the ball like an electromagnetic slug',
        'throw': ['the ball glows white and rifles eighty yards on a flat line',
                  'a crack of electricity and the spiral is gone downfield'],
        'kick':  ['the kick leaves a streak of electric light and splits the posts']},

    'wormhole': {'name': 'Wormhole', 'concept': 'folds the field so the ball threads anything',
        'throw': ['the coverage folds shut and a tunnel opens straight to the receiver',
                  'the throwing window an inch wide folds itself around the ball'],
        'catch': ['a pocket of space opens at their hands and the ball drops out of it'],
        'defense': ['the throw bends into a fold in the air and lands in their lap']},

    'blink': {'name': 'Blink', 'concept': 'teleports a short hop',
        'throw': ['the rush closes on empty air; they blinked clear and let it fly'],
        'run':   ['they blink out of the tackle and in again past the line'],
        'defense': ['they blink to the ball and arrive before the receiver does']},

    # ---- Run-home (RB) ----
    'warp': {'name': 'Warp', 'concept': 'moves at a speed the field cannot track',
        'run':   ['they hit warp speed and the defenders freeze mid-stride',
                  'a smear of motion and they are sixty yards downfield'],
        'catch': ['they warp to the catch point and wait for the ball to arrive'],
        'defense': ['they warp across the field and are under the throw instantly']},

    'earthquake': {'name': 'Earthquake', 'concept': 'a seismic stomp that buckles the field',
        'run':   ['a stomp flattens the entire front and they walk through the crack',
                  'the ground ripples and every tackler loses their footing'],
        'defense': ['the ground bucks and the ball shakes loose into their hands']},

    'juggernaut': {'name': 'Juggernaut', 'concept': 'turns to unstoppable iron',
        'run':   ['they turn to solid iron and bowl the whole pile over',
                  'tacklers ragdoll off them as they grind forward'],
        'defense': ['they become immovable iron and the run dies on contact']},

    'ice_rink': {'name': 'Ice Rink', 'concept': 'freezes the field to a sheet of ice',
        'run':   ['the turf flashes to ice; defenders wipe out as they skate through',
                  'they glide across a frozen field while everyone else slips'],
        'defense': ['the field ices over, the carrier slips, and they collect the ball']},

    'freestyle': {'name': 'Freestyle', 'concept': 'literally swims down the field',
        'run':   ['they dive in and front-crawl through the defense untouched',
                  'they backstroke past a diving tackle like it is open water'],
        'catch': ['they swim up through the coverage and surface with the ball'],
        'defense': ['they stroke through the line and scoop the ball from the current']},

    # ---- Catch-home (WR/TE) ----
    'magnet': {'name': 'Magnet', 'concept': 'turns magnetic to the ball',
        'catch': ['the ball velcros to their palms', 'it ricochets off two defenders and snaps to them anyway'],
        'defense': ['the throw bends off its line and into their hands',
                    'they hold up a palm and the pass drags itself in']},

    'flypaper': {'name': 'Flypaper', 'concept': 'their hands are flypaper; nothing comes loose',
        'catch': ['the ball sticks to their gloves the instant it arrives',
                  'a defender swats it and it just re-sticks to their hand'],
        'defense': ['the pass glances off a hand and flypapers to them for the pick']},

    'rubberband': {'name': 'Rubberband', 'concept': 'arms stretch like taffy',
        'catch': ['their arm stretches ten feet across the seam and reels it in',
                  'their wingspan triples and they pluck the uncatchable'],
        'defense': ['an arm snaps out across the field and yanks the throw down']},

    'octopus': {'name': 'Octopus', 'concept': 'sprouts a tangle of extra arms',
        'catch': ['eight arms unfurl and there is no dropping it now',
                  'a forest of hands swallows the ball out of the air'],
        'defense': ['a dozen arms blanket the route and one of them comes down with it']},

    'colossus': {'name': 'Colossus', 'concept': 'grows to fill the field',
        'catch': ['they expand to fill the end zone and box everyone out for it'],
        'run':   ['they swell to giant size and step over the entire defense'],
        'defense': ['they grow into a wall and the play crashes against them for a loss']},

    # ---- Kick-home (K) — offense only (no defensive position) ----
    'moonshot': {'name': 'Moonshot', 'concept': 'kicks it into orbit',
        'kick': ['it booms through from seventy-two with a vapor trail',
                 'the ball clears the uprights and keeps climbing out of the stadium']},

    'tractor_beam': {'name': 'Tractor Beam', 'concept': 'the target pulls the ball in',
        'kick': ['the uprights lean in and tractor the ball straight through'],
        'catch': ['a beam locks on and drags the ball into their hands'],
        'defense': ['they lock a beam on the throw and reel it in for the pick']},

    'trebuchet': {'name': 'Trebuchet', 'concept': 'launches it like a siege engine',
        'kick': ['they wind up like a trebuchet and the ball rains down through the posts'],
        'throw': ['they crank back and catapult the ball the length of the field']},

    # ---- Defense-rich ----
    'black_hole': {'name': 'Black Hole', 'concept': 'opens a collapsing gravity well',
        'defense': ['the pocket folds inward and the play collapses into the dark',
                    'a well opens behind the line and swallows the runner for a loss'],
        'run':     ['defenders are dragged off their feet toward the gap as they slip through'],
        'catch':   ['the ball falls into a well at their chest and cannot escape']},

    'pickpocket': {'name': 'Pickpocket', 'concept': 'their grip just dissolves the ball away',
        'defense': ['the carrier\'s grip dissolves on contact and they scoop it clean',
                    'they peel the ball away mid-stride and take off'],
        'run':     ['they slip a hand free of the tackle and keep the ball moving']},

    'rewind': {'name': 'Rewind', 'concept': 'rewinds a couple seconds to be where they need to be',
        'defense': ['they were a step late, so they rewind and arrive early for the ball'],
        'catch':   ['they drop it, rewind two seconds, and bring it in clean']},

    # TODO (port the rest of the locked catalog into this same shape — names locked, situations + a
    # couple flavor lines each): Comet, Slingshot, Orbital · Heat-Seeker, Auto-Aim, Telepathy ·
    # Smoke Bomb, Trapdoor, Bullet Time, Decoy, Grease, Jelly · Treadmill, Slipstream, Hyperdrive,
    # Fast-Forward, Conveyor Belt, Moses, Centipede, Big Bad Wolf, Boulder · Afterimage, Origami,
    # Clone, Matrix, Limbo, Heartthrob, Shrink Ray, Skunk, Liquify, Sandman, Photobomb · Avalanche,
    # Stampede, Steamroller, Tank, Cannonball, Bowling Ball · Third Arm, Vacuum, Gravity Well,
    # Web-Shooter, Do-Over, Good Boy, Invisible Ink · Slinky, Telescope, Gumby, Fishing Rod,
    # Butterfly Net · Kaiju, Redwood, Monolith, Hot Air, Eclipse · Mortar, Big Bertha, Autopilot,
    # GPS, Magnet Posts, Laser-Guided · Highway Robbery, Ball Magnet, The Heist, Portal, Telekinesis,
    # Premonition, Insider Trading, The Vacuum, Repo Man, Crowbar, Magnet Hands, Tax Man, Quicksand,
    # Sinkhole, Riptide, Teleport, Implosion, Demolition.
}


def _validate():
    for key, p in _POWERS.items():
        unknown = [s for s in p if s not in ('name', 'concept') and s not in SITUATIONS]
        assert not unknown, f"awakened power {key!r} has unknown situation keys {unknown}"
        assert p.get('name') and p.get('concept'), f"awakened power {key!r} missing name/concept"
        assert any(s in p for s in SITUATIONS), f"awakened power {key!r} covers no situations"


_validate()


# ── Lookup / assignment ─────────────────────────────────────────────────────────────────────────
def allPowerKeys():
    return list(_POWERS)


def powerName(key):
    return _POWERS.get(key, {}).get('name', '')


def powerConcept(key):
    return _POWERS.get(key, {}).get('concept', '')


def coveredSituations(key):
    p = _POWERS.get(key, {})
    return [s for s in SITUATIONS if s in p]


def powerCoversSituation(key, situation):
    return situation in _POWERS.get(key, {})


def situationFlavor(key, situation, rng=_random):
    """A random narration line for this power firing in this situation (''. if it doesn't cover it)."""
    lines = _POWERS.get(key, {}).get(situation) or []
    return rng.choice(lines) if lines else ''


def normalizePosition(position):
    p = str(getattr(position, 'name', position) or '').upper()
    for base in ('QB', 'RB', 'WR', 'TE', 'K'):
        if p.startswith(base):
            return base
    return ''


def assignPower(position, rng=_random):
    """Roll ONE career power that covers the player's primary action (so it fires regularly).
    Returns a power key, or None if the position is unknown / no eligible power exists."""
    primary = PRIMARY_SITUATION.get(normalizePosition(position))
    if not primary:
        return None
    pool = [k for k in _POWERS if primary in _POWERS[k]]
    return rng.choice(pool) if pool else None
