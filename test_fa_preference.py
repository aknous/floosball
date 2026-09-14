"""Free agency — per-team draft boards and destination preference.

Two promises this covers:

  1. Teams do NOT share a board. Each GM ranks the pool through their own
     scouting (sharpened by the Scouting Department), so one club's top target
     is another's fifth choice.
  2. Players choose where they'll sign BEFORE the draft, keyed on AGE alone.
     Talent is deliberately not an input — if it were, the best players would
     pool at the best-funded clubs.

The preference curve is tuned against the live league's real Appeal spread
(min 4, median 11, max 20 across 24 teams), so the numbers asserted here are
league-realistic rather than a 0-25 ideal.
"""

from managers.frontOfficeBrain import FrontOfficeBrain
from floosball_player import Position
from constants import (FA_PREF_MAX_DEMAND, FA_PREF_VET_FULL_SEASONS,
                       FACILITY_CATALOG, FACILITY_MAX_LEVEL)


class FakePlayer:
    def __init__(self, name, rating, seasons=0, position=Position.QB,
                 pid=None, ceiling=None, willRetire=False):
        self.name = name
        self.id = pid if pid is not None else abs(hash(name)) % 100000
        self.playerRating = rating
        self.seasonsPlayed = seasons
        self.position = position
        self.willRetire = willRetire
        self._ceiling = ceiling if ceiling is not None else rating

    def computeExpectedRating(self):
        return self.playerRating

    def computeCeilingRating(self):
        return self._ceiling


class FakeCoach:
    def __init__(self, scouting=80, playerDevelopment=80, fanTrust=80):
        self.scouting = scouting
        self.playerDevelopment = playerDevelopment
        self.fanTrust = fanTrust


class FakeTeam:
    """Carries only what the brain reads: an id, facilities, and the
    facilityEffect lookup the Scouting Department rides on."""

    def __init__(self, name, facilities=None, tid=1):
        self.name = name
        self.id = tid
        self.facilities = facilities or {}

    def facilityEffect(self, effectType):
        for key, cfg in FACILITY_CATALOG.items():
            if cfg.get('effect') == effectType:
                level = max(0, min(FACILITY_MAX_LEVEL, self.facilities.get(key, 0)))
                levels = cfg.get('levels') or []
                return levels[level] if level < len(levels) else (levels[-1] if levels else 0)
        return 0


class FakePlayerManager:
    def __init__(self, freeAgents=None):
        self.freeAgents = freeAgents or []

    def computeRetirementOdds(self, player):
        return (0, False, -5)


def _brain(freeAgents=None):
    return FrontOfficeBrain(FakePlayerManager(freeAgents=freeAgents))


def _team(name, level, tid=1):
    """A team with every facility at `level` — Appeal = 5 x level."""
    return FakeTeam(name, {k: level for k in FACILITY_CATALOG}, tid=tid)


# ---------------------------------------------------------------- preference

def test_rookies_sign_anywhere():
    """The floor of the design: a young player takes any job to get on the
    field, however bare the club."""
    brain = _brain()
    bare = _team('Bare', 0)
    for rating in (60, 75, 99):
        rookie = FakePlayer(f'Kid{rating}', rating, seasons=0)
        assert brain.appealDemand(rookie) == 0.0, rating
        assert brain.willSignWith(rookie, bare) is True, rating
    print("PASS a rookie signs anywhere, at any rating")


def test_talent_is_not_an_input():
    """The whole point of keying on age: two players the same age demand the
    same thing regardless of how good they are, so talent can't pool at the
    rich clubs."""
    brain = _brain()
    scrub = FakePlayer('Scrub', 61, seasons=9, pid=4242)
    star = FakePlayer('Star', 99, seasons=9, pid=4242)   # same id => same jitter
    assert brain.appealDemand(scrub) == brain.appealDemand(star)
    print("PASS demand ignores rating entirely")


def test_veterans_demand_more_than_youngsters():
    brain = _brain()
    demands = []
    for seasons in (0, 2, 4, 8, 12):
        # Same id throughout so the per-player jitter is held constant and only
        # the age term moves.
        p = FakePlayer(f'P{seasons}', 80, seasons=seasons, pid=777)
        demands.append(brain.appealDemand(p))
    assert demands == sorted(demands), demands
    assert demands[0] == 0.0
    assert demands[-1] > demands[1]
    print(f"PASS demand rises with service time: "
          f"{[round(d, 1) for d in demands]}")


def test_demand_maxes_out_and_stays_in_range():
    """No player may demand more than the constant allows, however ancient."""
    brain = _brain()
    for seasons in (FA_PREF_VET_FULL_SEASONS, 20, 40):
        p = FakePlayer('Ancient', 80, seasons=seasons, pid=1)
        d = brain.appealDemand(p)
        assert 0.0 <= d <= FA_PREF_MAX_DEMAND, (seasons, d)
    print(f"PASS demand stays within 0..{FA_PREF_MAX_DEMAND}")


def test_preference_is_stable_across_calls():
    """A board built before the draft has to still be true at pick time."""
    brain = _brain()
    p = FakePlayer('Vet', 85, seasons=10, pid=31337)
    first = brain.appealDemand(p)
    assert all(brain.appealDemand(p) == first for _ in range(50))
    print("PASS a player's demand never changes between calls")


def test_veterans_differ_from_each_other():
    """'Pretty wide' is the requirement: equally old players must not all want
    the same thing, or preference becomes a hard tier gate."""
    brain = _brain()
    demands = {brain.appealDemand(FakePlayer(f'V{i}', 80, seasons=10, pid=i))
               for i in range(1, 200)}
    assert len(demands) > 100, len(demands)
    assert max(demands) - min(demands) > FA_PREF_MAX_DEMAND * 0.3
    print(f"PASS veterans vary: {len(demands)} distinct demands, "
          f"spread {min(demands):.1f}-{max(demands):.1f}")


def test_a_richer_club_is_open_to_more_players():
    """Facilities still open the veteran market -- but as a VALUATION, not a veto.

    ⚠️ THIS TEST USED TO ASSERT THE HARD GATE and locked in the fault that replaced it.
    `willSignWith` became a preference on 2026-09-13 (see `_SOFT_APPEAL`), so it now returns
    True for everybody and a count of who "will sign" is identical at every club -- the
    assertion read (59, 59). The preference did not disappear; it moved into `decisionValue`,
    which is where a club below a player's Appeal demand now values him lower. Testing the
    old location would keep passing while the rule moved out from under it.

    ⚠️ THE HARD GATE REFUSED 53% OF 8-SEASON VETERANS FROM EVERY TEAM IN THE LEAGUE at the
    live Appeal of 8.0, because `appealDemand` was calibrated against a 24-club league whose
    Appeal spanned 4 to 20 and every club now sits on exactly 8.0.
    """
    brain = _brain()
    poor, rich = _team('Poor', 0, tid=1), _team('Rich', 4, tid=2)
    vets = [FakePlayer(f'V{i}', 80, seasons=12, pid=i) for i in range(1, 60)]

    # nobody is locked out of anywhere any more
    assert all(brain.willSignWith(v, poor) for v in vets)
    assert all(brain.willSignWith(v, rich) for v in vets)

    # ...but the richer club rates the veterans it suits more highly
    poorVal = sum(brain.decisionValue(v, None, team=poor) for v in vets)
    richVal = sum(brain.decisionValue(v, None, team=rich) for v in vets)
    assert richVal > poorVal, (poorVal, richVal)
    print(f"PASS facilities price the veteran market rather than closing it: "
          f"poor {poorVal:.0f}, rich {richVal:.0f} over {len(vets)} vets")


def test_a_veteran_is_never_unsignable_league_wide():
    """The failure mode the hard gate actually produced: a player no club may sign.

    Every club sits on the same Appeal today, so a demand above it was a demand above
    EVERY club -- the player was not choosing between suitors, he had none.
    """
    brain = _brain()
    league = [_team(f'T{i}', 2, tid=i) for i in range(1, 33)]   # the live 8.0 Appeal
    vets = [FakePlayer(f'V{i}', 88, seasons=12, pid=i) for i in range(1, 200)]
    homeless = [v for v in vets if not any(brain.willSignWith(v, t) for t in league)]
    assert not homeless, f"{len(homeless)}/{len(vets)} veterans can sign nowhere"
    print(f"PASS no veteran is refused by all 32 clubs (0/{len(vets)})")


def test_preference_can_be_switched_off():
    import importlib, constants
    original = constants.FA_PREFERENCE_ENABLED
    try:
        constants.FA_PREFERENCE_ENABLED = False
        import managers.frontOfficeBrain as m
        importlib.reload(m)
        brain = m.FrontOfficeBrain(FakePlayerManager())
        vet = FakePlayer('Vet', 95, seasons=15, pid=9)
        assert brain.willSignWith(vet, _team('Bare', 0)) is True
        print("PASS FA_PREFERENCE_ENABLED=False lets anyone sign anywhere")
    finally:
        constants.FA_PREFERENCE_ENABLED = original
        import managers.frontOfficeBrain as m
        importlib.reload(m)


# ------------------------------------------------------------------- scouting

def test_scouting_department_sharpens_the_read():
    """The facility's whole reason to exist. Level 5 must see more of the arc
    than an unbuilt department under the SAME coach."""
    brain = _brain()
    coach = FakeCoach(scouting=70)
    bare = brain.scoutingVision(coach, _team('Bare', 0))
    maxed = brain.scoutingVision(coach, _team('Maxed', 5))
    assert maxed > bare, (bare, maxed)
    print(f"PASS the Scouting Department buys vision: {bare:.2f} -> {maxed:.2f}")


def test_the_facility_never_replaces_the_gm():
    """A maxed department must not turn a poor evaluator into a good one."""
    brain = _brain()
    poorMaxed = brain.scoutingVision(FakeCoach(scouting=60), _team('A', 5))
    sharpBare = brain.scoutingVision(FakeCoach(scouting=100), _team('B', 0))
    assert poorMaxed < sharpBare, (poorMaxed, sharpBare)
    print(f"PASS a maxed department ({poorMaxed:.2f}) still trails a sharp GM "
          f"({sharpBare:.2f})")


def test_no_team_reads_as_the_old_behavior():
    """Passing no team must value exactly as before the facility existed."""
    brain = _brain()
    coach = FakeCoach(scouting=88)
    assert brain.scoutingVision(coach, None) == brain._attrLean(coach, 'scouting')
    print("PASS team=None is unchanged from the pre-facility read")


# ---------------------------------------------------------------------- board

def test_boards_rank_a_poor_fit_lower_rather_than_dropping_him():
    """⚠️ RENAMED FROM `test_boards_exclude_players_who_will_not_come`, because boards no
    longer exclude anybody (`_SOFT_APPEAL`, 2026-09-13). A bare club still rates a veteran
    who does not suit it BELOW what a club that suits him would -- which is the preference --
    but he is on the board, so he can be signed rather than going unsigned league-wide."""
    brain = _brain()
    bare, plush = _team('Bare', 0, tid=1), _team('Plush', 4, tid=2)
    pool = [FakePlayer('Kid', 70, seasons=0, pid=1),
            FakePlayer('Vet', 95, seasons=14, pid=2)]
    board = brain.buildDraftBoard(bare, pool, coach=FakeCoach())
    assert 1 in board, "the rookie should sign anywhere"
    assert 2 in board, "a veteran must still be signable somewhere"
    plushBoard = brain.buildDraftBoard(plush, pool, coach=FakeCoach())
    assert plushBoard[2] > board[2], (board[2], plushBoard[2])
    # ⚠️ THE ROOKIE MOVES A LITTLE TOO, and that is a different facility doing it: a plush
    # club has a better Scouting Department, so `scoutingVision` sharpens its read of
    # everybody. The Appeal penalty is what must land on the VETERAN and not on the rookie,
    # so compare the two gaps rather than asserting the rookie is untouched.
    vetGap = (plushBoard[2] - board[2]) / board[2]
    kidGap = abs(plushBoard[1] - board[1]) / board[1]
    assert vetGap > kidGap * 3, (kidGap, vetGap)
    print(f"PASS a poor fit is ranked lower, not dropped: bare {board[2]:.1f} "
          f"vs plush {plushBoard[2]:.1f}")


def test_two_teams_rank_the_same_pool_differently():
    """The headline behavior: one club's #1 is another's #5."""
    import random
    brain = _brain()
    pool = [FakePlayer(f'FA{i}', 70 + i, seasons=0, pid=i, ceiling=70 + i + 12)
            for i in range(1, 9)]
    # Same facilities so willingness is identical and only the GM differs.
    a, b = _team('A', 3, tid=1), _team('B', 3, tid=2)
    boardA = brain.buildDraftBoard(a, pool, coach=FakeCoach(scouting=62),
                                   rng=random.Random(1))
    boardB = brain.buildDraftBoard(b, pool, coach=FakeCoach(scouting=62),
                                   rng=random.Random(2))
    orderA = sorted(boardA, key=lambda k: -boardA[k])
    orderB = sorted(boardB, key=lambda k: -boardB[k])
    assert orderA != orderB, (orderA, orderB)
    print(f"PASS two GMs rank the same pool differently:\n"
          f"       A {orderA}\n       B {orderB}")


def test_prospects_are_priced_onto_the_same_board():
    """Cross-position picks compare FAs against prospects, so both have to be
    in one currency. A raw playerRating next to a position-weighted value would
    silently favour whichever side wasn't weighted."""
    brain = _brain()
    team = _team('T', 3)
    pool = [FakePlayer('FA', 80, seasons=0, pid=1)]
    prospect = FakePlayer('Prospect', 80, seasons=0, pid=2)
    # A perfect scout, so the per-call error term is zero and the comparison is
    # of the valuations themselves rather than two noise draws.
    board = brain.buildDraftBoard(team, pool, coach=FakeCoach(scouting=100),
                                  alsoValue=[prospect])
    assert 1 in board and 2 in board
    # Same rating, same position, same GM: the two must price identically.
    assert abs(board[1] - board[2]) < 1e-6, (board[1], board[2])
    print("PASS prospects and free agents share one board currency")


def test_prospects_skip_the_willingness_check():
    """They're already at the club — there's nothing to agree to."""
    brain = _brain()
    bare = _team('Bare', 0)
    oldProspect = FakePlayer('OldProspect', 80, seasons=15, pid=5)
    board = brain.buildDraftBoard(bare, [], coach=FakeCoach(),
                                  alsoValue=[oldProspect])
    assert 5 in board
    print("PASS a team's own prospects are never filtered by preference")


def test_retiring_free_agents_stay_off_the_board():
    brain = _brain()
    pool = [FakePlayer('Done', 90, seasons=1, pid=1, willRetire=True)]
    board = brain.buildDraftBoard(_team('T', 3), pool, coach=FakeCoach())
    assert board == {}
    print("PASS a retiring free agent is never boarded")


# ------------------------------------------------------- replacement value

def test_replacement_value_discounts_a_poor_fit():
    """A club must not plan a cut around an upgrade it cannot realistically land.

    ⚠️ THIS USED TO ASSERT ZERO, which was the hard gate's answer: a poor-fit veteran was
    not a replacement at ALL. Under the preference (`_SOFT_APPEAL`, 2026-09-13) he is a
    replacement the club rates LOWER, because he will actually come if asked. The property
    worth protecting is unchanged and is the one tested here -- a club that suits him values
    him more, so the bare club is the one least likely to cut its starter for him.
    """
    brain = _brain()
    bare = _team('Bare', 0)
    rich = _team('Rich', 5, tid=2)
    incumbent = FakePlayer('Starter', 75, seasons=3, pid=1)
    star = FakePlayer('Star', 99, seasons=14, pid=2)
    bareVal = brain.bestReplacementValue(
        incumbent, coach=FakeCoach(), pool=[star], team=bare)
    richVal = brain.bestReplacementValue(
        incumbent, coach=FakeCoach(), pool=[star], team=rich)
    assert richVal > bareVal > 0.0, (bareVal, richVal)
    print(f"PASS a poor fit is discounted as a replacement: bare {bareVal:.1f} "
          f"vs rich {richVal:.1f}")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in tests:
        fn()
    print(f"\nAll {len(tests)} FA preference / draft board tests passed.")
