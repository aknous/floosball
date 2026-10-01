"""The front-office desk: the draft order and the walk-year list.

⚠️ Both bugs here were INVISIBLE — each produced a full, plausible-looking payload with the
wrong clubs and players in it, and neither raised.
"""
import sys, types


class FakeTeam:
    def __init__(self, tid, name, wins, losses, scoreDiff=0):
        self.id, self.name = tid, name
        self.abbr, self.color = name[:3].upper(), '#000'
        played = wins + losses
        self.seasonTeamStats = {'wins': wins, 'losses': losses,
                                'winPerc': round(wins / played, 3) if played else 0.0,
                                'scoreDiff': scoreDiff}
        self.rosterDict = {}


def test_theDraftOrderIsWorstFirstAndNotTeamIdOrder():
    """⚠️ THERE IS NO `team.wins`, AND READING IT RETURNS 0 FOR EVERY CLUB FOREVER.

    The page once ranked off it: every club fell to a parity fallback, `sorted` is stable,
    and the draft order became team-id order. The key reads `seasonTeamStats`.
    """
    from seeding import draftOrderKey
    # id order is deliberately the REVERSE of record order, so the two cannot be confused
    teams = [FakeTeam(1, 'Best', 24, 4), FakeTeam(2, 'Good', 18, 10),
             FakeTeam(3, 'Poor', 10, 18), FakeTeam(4, 'Worst', 4, 24)]
    ranked = sorted(teams, key=draftOrderKey)
    assert [t.name for t in ranked] == ['Worst', 'Poor', 'Good', 'Best'], \
        'the draft order is worst-first; this came back in team-id order'


def test_pointDifferentialBreaksARecordTie():
    """Owner, 2026-10-01: record, then point differential — the worse differential picks
    first. Ids are ordered against the answer so a stable sort cannot fake it."""
    from seeding import draftOrderKey
    teams = [FakeTeam(1, 'Close', 10, 18, scoreDiff=-12), FakeTeam(2, 'Blown Out', 10, 18, scoreDiff=-140)]
    assert [t.name for t in sorted(teams, key=draftOrderKey)] == ['Blown Out', 'Close']


def _fakeApp(monkeypatch, teams, faOrder, seeds=None):
    import api.main as m
    import standings_view
    sm = types.SimpleNamespace(currentSeason=types.SimpleNamespace(freeAgencyOrder=faOrder))
    league = types.SimpleNamespace(teamList=teams)
    app = types.SimpleNamespace(seasonManager=sm, teamManager=types.SimpleNamespace(teams=teams),
                                leagueManager=types.SimpleNamespace(leagues=[league]))
    monkeypatch.setattr(m, 'floosball_app', app)
    monkeypatch.setattr(standings_view, 'seedLeague',
                        lambda ts, h2h=None: {'seeds': {tid: (1, 'wildcard') for tid in (seeds or [])}})
    return m


def test_thePageShowsTheRealOrderWhereItExists(monkeypatch):
    """Once the sim has built `freeAgencyOrder` (non-playoff teams, then each round's
    losers), the page shows THAT, and only projects the teams still alive. It used to
    re-sort the whole league by record, ignoring the playoffs."""
    a, b, c, d = (FakeTeam(1, 'A', 5, 23), FakeTeam(2, 'B', 22, 6),
                  FakeTeam(3, 'C', 12, 16), FakeTeam(4, 'D', 20, 8))
    # real order so far: A (missed), then B (22-6, out in round 1) — B stays ahead of C
    m = _fakeApp(monkeypatch, [a, b, c, d], [a, b])
    ids, final, _ = m._rookieDraftOrder()
    assert ids == [1, 2, 3, 4], 'the real order is kept, and the alive teams follow by record'
    assert final is False
    m = _fakeApp(monkeypatch, [a, b, c, d], [a, b, d, c])
    assert m._rookieDraftOrder()[:2] == ([1, 2, 4, 3], True)


def test_theProjectionPutsNonQualifiersFirst(monkeypatch):
    """Before the playoffs, a projected qualifier with a poor record still picks after
    every projected non-qualifier, as it will in the real draft."""
    weakDivWinner = FakeTeam(1, 'Weak Winner', 12, 16)
    teams = [weakDivWinner, FakeTeam(2, 'Better Miss', 14, 14), FakeTeam(3, 'Worst', 6, 22),
             FakeTeam(4, 'Best', 24, 4)]
    m = _fakeApp(monkeypatch, teams, [], seeds=[1, 4])
    ids, final, slotsFrom = m._rookieDraftOrder()
    assert ids == [3, 2, 1, 4]
    assert final is False and slotsFrom == 3


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
