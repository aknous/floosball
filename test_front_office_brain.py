"""Autonomous Front Office — GM brain valuation + re-sign decision.

Covers the behaviours the design actually promises, not just that the code
runs: arc classification, scouting gating the forward read, position weighting,
and the comparative re-sign test. See docs/AUTONOMOUS_FRONT_OFFICE_PLAN.md.
"""

import random

from managers.frontOfficeBrain import (
    FrontOfficeBrain, positionValue,
    ARC_DEVELOPING, ARC_PRIME, ARC_REGRESSING,
)
from floosball_player import Position


class FakePlayer:
    """Minimal stand-in exposing exactly what the brain reads."""

    def __init__(self, name, rating, position=Position.QB,
                 expected=None, ceiling=None, willRetire=False):
        self.name = name
        self.playerRating = rating
        self.position = position
        self.willRetire = willRetire
        self._expected = rating if expected is None else expected
        self._ceiling = self._expected if ceiling is None else ceiling

    def computeExpectedRating(self):
        return self._expected

    def computeCeilingRating(self):
        return self._ceiling


class FakeCoach:
    def __init__(self, scouting=80, playerDevelopment=80, fanTrust=80):
        self.scouting = scouting
        self.playerDevelopment = playerDevelopment
        self.fanTrust = fanTrust


class FakePlayerManager:
    """Drives the age clock. yearsPast is keyed by player name so a test can
    make a specific player old without building real attribute objects."""

    def __init__(self, yearsPastByName=None, freeAgents=None):
        self.yearsPastByName = yearsPastByName or {}
        self.freeAgents = freeAgents or []

    def computeRetirementOdds(self, player):
        yearsPast = self.yearsPastByName.get(player.name, -5)
        return (0, False, yearsPast)


def _brain(**kwargs):
    return FrontOfficeBrain(FakePlayerManager(**kwargs))


# --------------------------------------------------------------- arc

def test_arc_classification():
    brain = _brain(yearsPastByName={'Old': 2})
    developing = FakePlayer('Kid', 70, ceiling=82)
    prime = FakePlayer('Now', 88)
    regressing = FakePlayer('Old', 86)

    assert brain.classifyArc(developing) == ARC_DEVELOPING
    assert brain.classifyArc(prime) == ARC_PRIME
    assert brain.classifyArc(regressing) == ARC_REGRESSING
    print("PASS arc classification: developing / prime / regressing")


def test_decline_wins_ties():
    """A vet who never developed in is fading, not developing — the age clock
    must take precedence over an unmet trueSkill."""
    brain = _brain(yearsPastByName={'Vet': 1})
    vet = FakePlayer('Vet', 80, ceiling=90)   # headroom left AND is old
    assert brain.classifyArc(vet) == ARC_REGRESSING
    print("PASS decline outranks remaining potential headroom")


# -------------------------------------------------------- projection

def test_forward_projection_direction():
    """Developing projects UP, regressing projects DOWN, prime holds."""
    brain = _brain(yearsPastByName={'Old': 2})
    developing = FakePlayer('Kid', 70, ceiling=82)
    prime = FakePlayer('Now', 88)
    regressing = FakePlayer('Old', 86)
    coach = FakeCoach()

    assert brain.trueForwardRating(developing, coach) > developing.playerRating
    assert brain.trueForwardRating(prime, coach) == prime.playerRating
    assert brain.trueForwardRating(regressing, coach) < regressing.playerRating
    print("PASS forward projection moves in the right direction per arc")


def test_developer_credits_ceiling():
    """A development-minded GM values raw talent above what it would reach on
    its own; a poor developer only credits the natural trueSkill growth."""
    brain = _brain()
    kid = FakePlayer('Kid', 70, ceiling=95)

    strong = brain.trueForwardRating(kid, FakeCoach(playerDevelopment=100))
    weak = brain.trueForwardRating(kid, FakeCoach(playerDevelopment=60))

    assert strong > weak, f"{strong} !> {weak}"
    assert abs(weak - 70) < 1e-6, weak   # floor developer realises none of the gap
    print(f"PASS developer credits ceiling (dev100={strong:.1f} > dev60={weak:.1f})")


# --------------------------------------------------------- scouting

def test_scouting_gates_the_forward_read():
    """The headline behaviour: a sharp scout sees the arc, a poor one sees
    today's number. Averaged over many draws so the noise term cancels."""
    brain = _brain(yearsPastByName={'Fading': 2})
    rng = random.Random(1234)

    fading = FakePlayer('Fading', 90)          # looks great, falls off
    sharp = FakeCoach(scouting=100)
    poor = FakeCoach(scouting=60)

    N = 4000
    sharpAvg = sum(brain.perceivedValue(fading, sharp, rng=rng) for _ in range(N)) / N
    poorAvg = sum(brain.perceivedValue(fading, poor, rng=rng) for _ in range(N)) / N

    # The sharp GM marks the fading vet DOWN; the poor one pays today's number.
    assert sharpAvg < poorAvg, f"sharp {sharpAvg:.2f} !< poor {poorAvg:.2f}"
    assert abs(poorAvg - 90 * positionValue(fading)) < 1.0, poorAvg
    print(f"PASS scouting gates the read (sharp={sharpAvg:.1f} < poor={poorAvg:.1f})")


def test_poor_scout_is_wrong_not_just_fuzzy():
    """Zero vision must produce real error, otherwise a bad scout is harmless."""
    brain = _brain()
    rng = random.Random(7)
    player = FakePlayer('Guy', 80)

    poor = [brain.perceivedValue(player, FakeCoach(scouting=60), rng=rng) for _ in range(500)]
    sharp = [brain.perceivedValue(player, FakeCoach(scouting=100), rng=rng) for _ in range(500)]

    spreadPoor = max(poor) - min(poor)
    spreadSharp = max(sharp) - min(sharp)
    assert spreadPoor > 5, spreadPoor
    assert spreadSharp < 1e-6, spreadSharp   # full vision = no error at all
    print(f"PASS poor scout errs (spread={spreadPoor:.1f}), sharp scout is exact")


# --------------------------------------------------------- position

def test_position_weighting():
    """Equal ratings must not be equal value — this is what stops a great
    kicker outranking a QB need."""
    brain = _brain()
    qb = FakePlayer('QB', 85, position=Position.QB)
    k = FakePlayer('K', 85, position=Position.K)
    sharp = FakeCoach(scouting=100)

    assert brain.perceivedValue(qb, sharp) > brain.perceivedValue(k, sharp)
    print("PASS position weighting ranks an 85 QB over an 85 K")


# ---------------------------------------------------------- re-sign

def test_resign_is_comparative_not_best_available():
    """The core re-sign promise: a replaceable good player walks, an
    irreplaceable modest one is kept."""
    # Market is deep at QB (an 88 sits in FA) and empty at TE.
    pool = [FakePlayer('FA QB', 88, position=Position.QB)]
    brain = FrontOfficeBrain(FakePlayerManager(freeAgents=pool))
    sharp = FakeCoach(scouting=100)

    goodButReplaceable = FakePlayer('Starter QB', 85, position=Position.QB)
    modestButIrreplaceable = FakePlayer('Starter TE', 74, position=Position.TE)

    kept = brain.chooseResigns(
        [goodButReplaceable, modestButIrreplaceable], limit=2, coach=sharp)
    keptNames = {p.name for p in kept}

    assert 'Starter TE' in keptNames, keptNames
    assert 'Starter QB' not in keptNames, keptNames
    print("PASS re-sign is comparative (replaceable 85 QB walks, 74 TE kept)")


def test_resign_respects_the_limit():
    """The brain changes WHO fills the slots, never how many exist."""
    brain = _brain()
    sharp = FakeCoach(scouting=100)
    expiring = [FakePlayer(f'P{i}', 80 + i, position=Position.TE) for i in range(5)]

    assert len(brain.chooseResigns(expiring, limit=2, coach=sharp)) == 2
    assert brain.chooseResigns(expiring, limit=0, coach=sharp) == []
    print("PASS re-sign honours the per-offseason limit")


def test_retiring_free_agents_are_not_a_replacement():
    """A retiring FA cannot actually be signed, so he must not scare a team
    into letting its incumbent walk."""
    retiring = FakePlayer('FA', 95, position=Position.TE, willRetire=True)
    brain = FrontOfficeBrain(FakePlayerManager(freeAgents=[retiring]))
    sharp = FakeCoach(scouting=100)
    incumbent = FakePlayer('Starter', 75, position=Position.TE)

    kept = brain.chooseResigns([incumbent], limit=2, coach=sharp)
    assert [p.name for p in kept] == ['Starter']
    print("PASS a retiring FA doesn't count as an available replacement")


def test_pick_depth_saves_the_franchise_player():
    """The regression that a full sim exposed: benchmarking every team against
    the single league-best free agent made ALL 24 conclude their starter was
    replaceable, so the whole league shed its incumbents. A team picking late
    must measure against what will actually still be on the board."""
    pool = [FakePlayer(f'FA{i}', r, position=Position.QB)
            for i, r in enumerate([88, 87, 86, 84, 82, 80, 78, 76, 74, 72])]
    brain = FrontOfficeBrain(FakePlayerManager(freeAgents=pool))
    sharp = FakeCoach(scouting=100)

    def keptAt(depth):
        incumbent = FakePlayer('Franchise QB', 85, position=Position.QB)
        kept = brain.chooseResigns([incumbent], limit=2, coach=sharp, pickDepth=depth)
        return bool(kept)

    assert not keptAt(0), "picking first, the 88 is gettable — letting him walk is right"
    assert keptAt(4), "picking deep, only an 82 remains — the 85 must be kept"
    print("PASS pick depth: 85 QB walks at depth 0, is kept at depth 4")


def test_pick_depth_scales_with_fa_order():
    """Early pickers shop the top of the board; late pickers see leftovers."""
    brain = _brain()
    teams = [f'team{i}' for i in range(24)]

    assert brain.faPickDepth(teams[0], teams) == 0
    assert brain.faPickDepth(teams[23], teams) > brain.faPickDepth(teams[5], teams)
    assert brain.faPickDepth('not-in-order', teams) == 0   # degrades safely
    assert brain.faPickDepth(teams[0], None) == 0
    print("PASS FA pick depth scales with worst-first order")


def test_picked_clean_position_keeps_incumbent():
    """If the position is exhausted before a team's turn there is nobody to
    replace the incumbent with, so he must be kept."""
    pool = [FakePlayer('FA0', 95, position=Position.TE)]
    brain = FrontOfficeBrain(FakePlayerManager(freeAgents=pool))
    incumbent = FakePlayer('Starter', 70, position=Position.TE)

    kept = brain.chooseResigns([incumbent], limit=2,
                               coach=FakeCoach(scouting=100), pickDepth=9)
    assert [p.name for p in kept] == ['Starter']
    print("PASS a picked-clean position keeps the incumbent")


def test_developing_needs_real_headroom():
    """A point of slack is not a career arc — without a floor, 'developing'
    would describe nearly the whole league."""
    brain = _brain()
    barely = FakePlayer('Barely', 80, ceiling=81)     # 1 point of room
    genuine = FakePlayer('Genuine', 80, ceiling=90)   # 10 points

    assert brain.classifyArc(barely) == ARC_PRIME
    assert brain.classifyArc(genuine) == ARC_DEVELOPING
    print("PASS developing requires real potential headroom")


def test_arc_survives_trueskill_removal():
    """Part F retires the trueSkill tier. Nothing here may depend on it."""
    import managers.frontOfficeBrain as m, inspect
    src = inspect.getsource(m.FrontOfficeBrain.classifyArc) + inspect.getsource(m.FrontOfficeBrain.trueForwardRating)
    assert '_expectedRating' not in src, "arc logic still reads the retired trueSkill tier"
    print("PASS arc + projection no longer depend on trueSkill")


def test_missing_coach_is_neutral():
    """An unmanaged team must still make middling-sane calls, not crash."""
    brain = _brain()
    player = FakePlayer('Guy', 80)
    assert brain.perceivedValue(player, None) > 0
    print("PASS missing coach reads as neutral")




# ------------------------------------------------------- cut-for-upgrade

def _rosterTeam(players):
    """A team whose rosterDict maps slot -> player."""
    class T:
        name = 'Testers'
        rosterDict = {}
    t = T()
    t.rosterDict = {f'slot{i}': p for i, p in enumerate(players)}
    return t


def _contracted(name, rating, position=Position.TE, term=3):
    p = FakePlayer(name, rating, position=position)
    p.termRemaining = term
    return p


def test_cut_requires_a_real_upgrade():
    """A marginally better free agent must not trigger a cut — the hole may not
    get refilled."""
    from constants import FO_CUT_UPGRADE_MARGIN
    incumbent = _contracted('Starter', 75)
    marginal = FakePlayer('FA marginal', 76, position=Position.TE)
    big = FakePlayer('FA big', 95, position=Position.TE)

    sharp = FakeCoach(scouting=100)
    brainSmall = FrontOfficeBrain(FakePlayerManager(freeAgents=[marginal]))
    brainBig = FrontOfficeBrain(FakePlayerManager(freeAgents=[big]))

    assert brainSmall.chooseCuts(_rosterTeam([incumbent]), coach=sharp) == []
    assert len(brainBig.chooseCuts(_rosterTeam([incumbent]), coach=sharp)) == 1
    print(f"PASS cut needs a real upgrade (margin {FO_CUT_UPGRADE_MARGIN} value pts)")


def test_walk_year_and_retiring_players_are_not_cut():
    """Retention already decides walk-year players, and a retiree vacates —
    cutting either would be redundant churn."""
    upgrade = FakePlayer('FA', 99, position=Position.TE)
    brain = FrontOfficeBrain(FakePlayerManager(freeAgents=[upgrade]))
    sharp = FakeCoach(scouting=100)

    walkYear = _contracted('WalkYear', 60, term=1)
    retiring = _contracted('Retiring', 60, term=3)
    retiring.willRetire = True

    assert brain.chooseCuts(_rosterTeam([walkYear]), coach=sharp) == []
    assert brain.chooseCuts(_rosterTeam([retiring]), coach=sharp) == []
    print("PASS walk-year and retiring players are left to their own paths")


def test_cuts_are_capped_and_take_the_biggest_upgrades():
    """A fresh-league sim produced 70 cuts in one offseason without a cap."""
    from constants import FO_CUT_MAX_PER_TEAM
    pool = [FakePlayer(f'FA{i}', 99, position=Position.TE) for i in range(6)]
    brain = FrontOfficeBrain(FakePlayerManager(freeAgents=pool))
    roster = [_contracted('Worst', 55), _contracted('Bad', 60),
              _contracted('Mid', 70), _contracted('Ok', 74)]

    cuts = brain.chooseCuts(_rosterTeam(roster), coach=FakeCoach(scouting=100))
    assert len(cuts) == FO_CUT_MAX_PER_TEAM, cuts
    names = {p.name for p, _slot in cuts}
    assert names == {'Worst', 'Bad'}, names   # biggest upgrades first
    print(f"PASS cuts capped at {FO_CUT_MAX_PER_TEAM}/team, worst players first")


def test_late_picker_cuts_less_than_early_picker():
    """The aggression dial: cutting is a gamble when you pick late."""
    pool = [FakePlayer(f'FA{i}', r, position=Position.TE)
            for i, r in enumerate([95, 92, 88, 84, 80, 76, 72])]
    brain = FrontOfficeBrain(FakePlayerManager(freeAgents=pool))
    sharp = FakeCoach(scouting=100)
    team = _rosterTeam([_contracted('Starter', 78)])

    early = brain.chooseCuts(team, coach=sharp, pickDepth=0)
    late = brain.chooseCuts(team, coach=sharp, pickDepth=6)
    assert len(early) == 1 and len(late) == 0, (early, late)
    print("PASS early picker cuts, late picker holds (same roster, same pool)")


def test_cut_can_be_disabled():
    import constants, importlib
    original = constants.FO_CUT_ENABLED
    try:
        constants.FO_CUT_ENABLED = False
        import managers.frontOfficeBrain as m
        importlib.reload(m)
        pool = [m_p := FakePlayer('FA', 99, position=Position.TE)]
        brain = m.FrontOfficeBrain(FakePlayerManager(freeAgents=pool))
        assert brain.chooseCuts(_rosterTeam([_contracted('Starter', 50)]),
                                coach=FakeCoach(scouting=100)) == []
        print("PASS FO_CUT_ENABLED=False disables cutting")
    finally:
        constants.FO_CUT_ENABLED = original
        import managers.frontOfficeBrain as m
        importlib.reload(m)


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in tests:
        fn()
    print(f"\nAll {len(tests)} front-office brain tests passed.")
