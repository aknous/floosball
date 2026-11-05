"""Scouting reports for prospects (owner, 2026-11-04): a short, plain read of where a
prospect is projected to stand, shown on the prospect rankings and the profile.

Everything is judged on the PUBLIC projection (`Player.projectionDetail(0)`), never a
team's scouting, and against the current STARTERS at the prospect's position: the
players they would have to beat for a job. A trait in the top quarter of those starters
is a strength, the top tenth "elite", the bottom quarter a weakness. Mental traits do not
train, so they are today's values, compared against every starter. No numbers reach the
text.
"""

POSITION_NOUN = {'QB': 'quarterback', 'RB': 'running back', 'WR': 'receiver',
                 'TE': 'tight end', 'K': 'kicker'}

# The skills the profile shows for each position (`api_response_builders`).
POSITION_SKILLS = {
    'QB': ('armStrength', 'accuracy', 'agility'),
    'RB': ('speed', 'power', 'agility'),
    'WR': ('speed', 'hands', 'reach'),
    'TE': ('hands', 'power', 'agility'),
    'K': ('legStrength', 'accuracy'),
}

MENTAL = ('discipline', 'pressureHandling', 'instinct', 'focus', 'creativity', 'attitude')

# trait: (label, strength phrase, weakness phrase, "with ..." phrase for the summary)
PHRASES = {
    'armStrength': ('Arm strength', 'Big arm', 'Limited arm strength', 'a big arm'),
    'accuracy': ('Accuracy', 'Accurate', 'Inaccurate', 'good accuracy'),
    'agility': ('Agility', 'Agile', 'Not very agile', 'good agility'),
    'speed': ('Speed', 'Fast', 'Lacks speed', 'top speed'),
    'power': ('Power', 'Powerful', 'Lacks power', 'power'),
    'hands': ('Hands', 'Reliable hands', 'Drops too many', 'reliable hands'),
    'reach': ('Reach', 'Big catch radius', 'Small catch radius', 'a big catch radius'),
    'legStrength': ('Leg strength', 'Big leg', 'Limited range', 'a big leg'),
    'playMakingAbility': ('Playmaking', 'Makes plays', 'Rarely makes the big play', 'playmaking'),
    'xFactor': ('X-Factor', 'Rises in big moments', 'Fades in big moments', 'a knack for big moments'),
    'coverage': ('Coverage', 'Covers well', 'Struggles in coverage', None),
    'tackling': ('Tackling', 'Sure tackler', 'Misses tackles', None),
    'playReading': ('Play reading', 'Reads plays well', 'Slow to read plays', None),
    'passRush': ('Pass rush', 'Gets after the quarterback', 'Little pass rush', None),
    'runDefense': ('Run defense', 'Stops the run', 'Gives ground against the run', None),
    'blitzing': ('Blitzing', 'Dangerous blitzer', 'Ineffective blitzer', None),
    'discipline': ('Discipline', 'Disciplined', 'Undisciplined', None),
    'pressureHandling': ('Pressure', 'Composed under pressure', 'Rattled under pressure', None),
    'instinct': ('Instinct', 'Good instincts', 'Slow instincts', None),
    'focus': ('Focus', 'Focused', 'Loses focus', None),
    'creativity': ('Creativity', 'Creative', 'Predictable', None),
    'attitude': ('Attitude', 'Good in the locker room', 'Difficult in the locker room', None),
}

ELITE, STRONG, WEAK = 0.90, 0.75, 0.25
# Which side of the ball a prospect projects to help most (owner, 2026-11-04): a side is the
# lean when its projected rating beats the other by at least half a star tier (the "roughly
# matches" gap the promotion rules use); closer than that, two-way. Kickers have no lean.
LEAN_GAP = 4.0
# Up to two strengths on offense and one each on defense and mental; up to one weakness a side.
STRENGTHS_PER_SIDE = {'offense': 2, 'defense': 1, 'mental': 1}


def _position(player) -> str:
    pos = getattr(player, 'position', None)
    return pos.name if hasattr(pos, 'name') else str(pos)


def _isStarter(p) -> bool:
    return (not getattr(p, 'is_prospect', False) and not getattr(p, 'is_upcoming_rookie', False)
            and getattr(getattr(p, 'team', None), 'name', None) is not None)


def buildPeerTables(players) -> dict:
    """`{(group, trait): sorted values}` over the current starters: position skills,
    playmaking and X-Factor by position, defensive skills by position (each offensive
    position maps to one defensive one), mental traits across everyone. Built once per
    request and shared by every report in it."""
    tables = {}
    for p in players:
        if not _isStarter(p):
            continue
        a = getattr(p, 'attributes', None)
        if a is None:
            continue
        pos = _position(p)
        for t in POSITION_SKILLS.get(pos, ()) + ('playMakingAbility', 'xFactor'):
            v = getattr(a, t, None)
            if v is not None:
                tables.setdefault((pos, t), []).append(float(v))
        try:
            for t, v in (a.getDefensiveAttributes(p.position) or {}).items():
                tables.setdefault((pos, 'def:' + t), []).append(float(v))
        except Exception:
            pass
        for t in MENTAL:
            v = getattr(a, t, None)
            if v is not None:
                tables.setdefault(('all', t), []).append(float(v))
    return {k: sorted(v) for k, v in tables.items()}


def _share(values, value) -> float:
    """The share of `values` below `value` (ties count half)."""
    if not values:
        return 0.5
    below = sum(1 for v in values if v < value)
    equal = sum(1 for v in values if v == value)
    return (below + 0.5 * equal) / len(values)


def scoutingReport(player, tables) -> dict:
    """`{summary, lean, strengths, weaknesses, growth}` for a prospect, or None for anyone
    else. `lean` is 'offense', 'defense' or 'two_way' (None for a kicker).
    Strengths and weaknesses are `{trait, label, phrase, tier, side}`; tier is 'elite' or
    'strong' (weaknesses 'weak'), side 'offense', 'defense' or 'mental'."""
    if not (getattr(player, 'is_prospect', False) or getattr(player, 'is_upcoming_rookie', False)):
        return None
    a = getattr(player, 'attributes', None)
    if a is None:
        return None
    pos = _position(player)
    try:
        detail = player.projectionDetail(0.0) or {}
    except Exception:
        detail = {}
    projAttrs = detail.get('attributes', {})
    projDef = detail.get('defensive', {})

    reads = []      # (side, trait, value, peers)
    for t in POSITION_SKILLS.get(pos, ()):
        mid = projAttrs.get(t, (None, getattr(a, t, None), None))[1]
        if mid is not None:
            reads.append(('offense', t, float(mid), tables.get((pos, t), [])))
    # A kicker makes no plays with the ball, so playmaking says nothing about one.
    for t in (('xFactor',) if pos == 'K' else ('playMakingAbility', 'xFactor')):
        v = getattr(a, t, None)
        if v is not None:
            reads.append(('offense', t, float(v), tables.get((pos, t), [])))
    for t, (_lo, mid, _hi) in projDef.items():
        reads.append(('defense', t, float(mid), tables.get((pos, 'def:' + t), [])))
    for t in MENTAL:
        v = getattr(a, t, None)
        if v is not None:
            reads.append(('mental', t, float(v), tables.get(('all', t), [])))

    graded = [(side, t, _share(peers, v)) for side, t, v, peers in reads if peers]
    # ⚠️ PICKED PER SIDE, OFFENSE FIRST. A prospect is billed by his offensive position, and
    # ranked across all traits at once a strong defensive read crowded the position out
    # (the class's top QB came back with three defensive strengths and no word on passing).
    strengths, weaknesses = [], []
    for side in ('offense', 'defense', 'mental'):
        mine = [g for g in graded if g[0] == side]
        strengths += sorted((g for g in mine if g[2] >= STRONG),
                            key=lambda g: -g[2])[:STRENGTHS_PER_SIDE[side]]
        weaknesses += sorted((g for g in mine if g[2] <= WEAK), key=lambda g: g[2])[:1]

    def entry(side, t, share, weak=False):
        label, good, bad, _w = PHRASES[t]
        return {'trait': t, 'label': label, 'phrase': bad if weak else good, 'side': side,
                'tier': 'weak' if weak else ('elite' if share >= ELITE else 'strong')}

    # The trait projected to grow the most: the widest public range above today's value.
    growth = None
    best = 0.0
    for t, (lo, mid, hi) in projAttrs.items():
        if t not in POSITION_SKILLS.get(pos, ()):
            continue
        room = float(hi) - float(getattr(a, t, 0) or 0)
        if room > best + 1e-9:
            best, growth = room, PHRASES[t][0]
    if best < 4:
        growth = None   # under half a star tier is not room worth naming

    lean = None
    if pos != 'K' and detail.get('offense') and detail.get('defense'):
        gap = float(detail['offense'][1]) - float(detail['defense'][1])
        lean = 'offense' if gap >= LEAN_GAP else 'defense' if gap <= -LEAN_GAP else 'two_way'

    return {
        'summary': _summary(player, pos, strengths, detail),
        'lean': lean,
        'strengths': [entry(*g) for g in strengths],
        'weaknesses': [entry(*g, weak=True) for g in weaknesses],
        'growth': growth,
    }


def _stars(rating: float) -> int:
    """The star lines every rating uses: 92 / 84 / 76 / 68."""
    for stars, line in ((5, 92), (4, 84), (3, 76), (2, 68)):
        if rating >= line:
            return stars
    return 1


DEFENSIVE_NOUN = {'QB': 'safety', 'RB': 'linebacker', 'WR': 'cornerback', 'TE': 'defensive end'}


def _starRange(low: float, high: float) -> str:
    a, b = _stars(low), _stars(high)
    return f"{a}-star" if a == b else f"{a} to {b}-star"


def _summary(player, pos, strengths, detail=None) -> str:
    """"Projects as a 4 to 5-star safety and a 3 to 5-star quarterback, with a big arm and
    good accuracy." Each side of the ball gets its own star range (owner, 2026-11-04: the
    overall's range averaged the two and billed a safety's projection as a quarterback's),
    the stronger projected side first; a kicker has one."""
    noun = POSITION_NOUN.get(pos, 'player')
    detail = detail or {}
    off, dfn = detail.get('offense'), detail.get('defense')
    if off and dfn and pos in DEFENSIVE_NOUN:
        sides = [(off[1], _starRange(off[0], off[2]), noun),
                 (dfn[1], _starRange(dfn[0], dfn[2]), DEFENSIVE_NOUN[pos])]
        # The clearly stronger side first, by the same gap as the lean; a two-way prospect
        # keeps the position he is billed as in front.
        if sides[1][0] - sides[0][0] >= LEAN_GAP:
            sides.reverse()
        lead = f"a {sides[0][1]} {sides[0][2]} and a {sides[1][1]} {sides[1][2]}"
    else:
        try:
            low, _mid, high = player.projectionRange(0.0)
        except Exception:
            low = high = float(getattr(player, 'playerRating', 0) or 0)
        if off:
            low, high = off[0], off[2]
        lead = f"a {_starRange(low, high)} {noun}"
    # The skills named are the position's: they are what the player is billed as.
    skills = POSITION_SKILLS.get(pos, ())
    withs = [PHRASES[t][3] for _side, t, _s in strengths if t in skills][:2]
    tail = f", with {' and '.join(withs)}" if withs else ""
    return f"Projects as {lead}{tail}."
