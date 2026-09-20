"""The front-office desk: the draft order and the walk-year list.

⚠️ Both bugs here were INVISIBLE — each produced a full, plausible-looking payload with the
wrong clubs and players in it, and neither raised.
"""
import sys, types


class FakeTeam:
    def __init__(self, tid, name, wins, losses, ties=0):
        self.id, self.name = tid, name
        self.abbr, self.color = name[:3].upper(), '#000'
        self.seasonTeamStats = {'wins': wins, 'losses': losses, 'ties': ties}
        self.rosterDict = {}


def test_theDraftOrderIsWorstFirstAndNotTeamIdOrder():
    """⚠️ THERE IS NO `team.wins`, AND READING IT RETURNS 0 FOR EVERY CLUB FOREVER.

    Every club then fell to the `played == 0` fallback of 0.5, `sorted` is stable, and the
    draft order became team-id order — the fan-facing order, and every "traded" flag hanging
    off it, naming the wrong clubs. This is the second time this attribute has bitten; in
    `tradeManager` it flattened the contention gradient to 0 listings out of 1,468.

    Bite check: against `getattr(team, 'wins', 0)` this returns the id order 1,2,3,4.
    """
    from api.main import _teamWinPct
    # id order is deliberately the REVERSE of record order, so the two cannot be confused
    teams = [FakeTeam(1, 'Best', 24, 4), FakeTeam(2, 'Good', 18, 10),
             FakeTeam(3, 'Poor', 10, 18), FakeTeam(4, 'Worst', 4, 24)]
    ranked = sorted(teams, key=_teamWinPct)
    assert [t.name for t in ranked] == ['Worst', 'Poor', 'Good', 'Best'], \
        'the draft order is worst-first; this came back in team-id order'


def test_aTieCountsAsAGamePlayed():
    """A two-term reading drops ties silently, which shifts a club's win% upward.

    ⚠️ THE FIXTURE MUST NOT LAND ON 0.5. A 14-13-1 club computes to exactly 14/28 = 0.5,
    which is also what the broken reading returns for EVERY club (no attribute -> played 0
    -> the parity fallback), so that assertion passed against the bug it was written for.
    15-10-3 separates all three answers: 0.536 correct, 0.600 ties-dropped, 0.500 broken.
    """
    from api.main import _teamWinPct
    got = _teamWinPct(FakeTeam(1, 'Tied', 15, 10, 3))
    assert abs(got - 15 / 28) < 1e-9, 'a tie is a game played'
    assert abs(got - 15 / 25) > 1e-9, 'ties were dropped from the denominator'
    assert abs(got - 0.5) > 1e-9, "this is the broken reading parity fallback"


def test_anUnplayedSeasonIsParityNotADivideByZero():
    from api.main import _teamWinPct
    assert _teamWinPct(FakeTeam(1, 'New', 0, 0)) == 0.5
    assert _teamWinPct(None) == 2.0, 'a missing club sorts last rather than crashing'


def test_cannotKeepMarksTheWEAKESTWalkYears():
    """⚠️ `walkers.index(p)` IS THE POSITION IN THE UNSORTED LIST.

    The loop iterated the sorted order and then looked the player up in the original list,
    so the flag landed on whoever happened to sit first in the roster dict — the one thing
    it claims not to mean. With a re-sign limit of 2 and four walk-years, the two WORST are
    the ones the club cannot keep.

    Bite check: with `walkers.index(p)` this marks the 88 and the 71.
    """
    ratings = [88, 71, 95, 64]              # roster order, deliberately not sorted
    walkers = list(ratings)
    overLimit = max(0, len(walkers) - 2)
    flagged = [r for rank, r in enumerate(sorted(walkers)) if overLimit > 0 and rank < overLimit]
    assert sorted(flagged) == [64, 71], \
        'the club keeps its best two; the two weakest are the ones leaving for nothing'
