"""The free agency market (docs/FREE_AGENCY_MARKET_PLAN.md): players choose.

Pins the pure market (`faMarket.resolve`): held offers, match-or-beat bidding wars,
motive pulls, ties, opportunity players committing early, budgets, and that losing a war
never costs a team its backup.

Run: .venv/bin/python -m pytest -q test_fa_market.py
"""
import math
import random
from types import SimpleNamespace

import pytest

from managers import faMarket
from managers.faMarket import Want, resolve


def _run(asks, wants, motives=None, rank=None, pulls=None, room=None, minRaise=0.05):
    motives = motives or {}
    pulls = pulls or {}
    rank = rank or {}
    signings, events = resolve(asks, motives, wants, rank,
                               lambda pid, tid: pulls.get((pid, tid), 0.0),
                               room or {}, minRaise=minRaise)
    return {pid: (next(w.teamId for w in wants if w.wid == wid), sal)
            for pid, (wid, sal) in signings.items()}, events


def test_aLoneOfferSignsAtTheAsk():
    got, _ = _run({1: 1000}, [Want(0, teamId=10, slot='qb', posVal=1, candidates=[(1, 2000)])])
    assert got == {1: (10, 1000)}


def test_theBiggerWalkAwayPriceWinsTheWarAtAboutTheLosersPrice():
    wants = [Want(0, 10, 'qb', 1, candidates=[(1, 1500), (2, 900)]),
             Want(1, 20, 'qb', 1, candidates=[(1, 2400)])]
    got, events = _run({1: 1000, 2: 800}, wants, rank={10: 0, 20: 1})
    assert got[1][0] == 20
    assert 1500 <= got[1][1] <= 1500 + 50 + 1      # beat the loser's last raise by a step
    assert got[2] == (10, 800)                     # the loser took its backup
    assert any(e['over'] == 10 for e in events)    # it was outbid, and could answer


def test_matchingIsOnTheScoreSoTheHomeTeamPaysLess():
    # Player 1 gives his home team (10) a 200F discount. Team 20 will pay up to 1300.
    wants = [Want(0, 10, 'qb', 1, candidates=[(1, 1200)]),
             Want(1, 20, 'qb', 1, candidates=[(1, 1300)])]
    got, _ = _run({1: 1000}, wants, motives={1: 'hometown'}, pulls={(1, 10): 200.0},
                  rank={10: 1, 20: 0})
    # Team 20 tops out at a score of 1300; the home team matches it at 1100 and wins the tie
    # on the motive, so it never has to reach 1300.
    assert got[1] == (10, 1100)


def test_anExactTieGoesToTheWorseTeam():
    wants = [Want(0, 10, 'qb', 1, candidates=[(1, 1000)]),
             Want(1, 20, 'qb', 1, candidates=[(1, 1000)])]
    got, _ = _run({1: 1000}, wants, rank={10: 5, 20: 2})
    assert got[1] == (20, 1000)


def test_anOpportunityPlayerSignsTheFirstGoodOfferAndCannotBeOutbid():
    wants = [Want(0, 10, 'qb', 1, candidates=[(1, 900)]),
             Want(1, 20, 'qb', 1, candidates=[(1, 5000)])]
    got, _ = _run({1: 1000}, wants, motives={1: 'opportunity'}, rank={10: 0, 20: 1})
    assert got[1] == (10, 850)                     # 85% of his ask, from the team that asked first


def test_anOfferTheBudgetCannotCoverGoesDownTheList():
    wants = [Want(0, 10, 'qb', 1, candidates=[(1, 5000), (2, 900)])]
    got, _ = _run({1: 2000, 2: 600}, wants, room={10: 1000})
    assert got == {2: (10, 600)}


def test_aReleaseFreesItsSalaryForTheUpgrade():
    wants = [Want(0, 10, 'qb', 1, candidates=[(1, 5000)], release=99, releaseSalary=900)]
    got, _ = _run({1: 1500}, wants, room={10: 700})
    assert got == {1: (10, 1500)}                  # net cost 600 fits 700


def test_losingTheStarDoesNotCostTheBackup():
    # Team 10 wants the star (1), else player 2. Team 20 outbids it for the star. Team 30
    # was already holding player 2 when team 10 came back for him: team 10 out-scores it.
    wants = [Want(0, 10, 'qb', 1, candidates=[(1, 1200), (2, 1400)]),
             Want(1, 20, 'qb', 1, candidates=[(1, 3000)]),
             Want(2, 30, 'qb', 1, candidates=[(2, 1000)])]
    got, _ = _run({1: 1000, 2: 900}, wants, rank={10: 0, 20: 1, 30: 2})
    assert got[1][0] == 20
    assert got[2][0] == 10
    # Team 30 raised to 990 (its next raise would pass its 1000 limit); team 10, the worse
    # team, matched it and wins the tie.
    assert got[2][1] == 990


def test_aTeamDoesNotBidAgainstItselfForTwoSlots():
    wants = [Want(0, 10, 'wr1', 3, candidates=[(1, 2000), (2, 2000)]),
             Want(1, 10, 'wr2', 3, candidates=[(1, 2000), (2, 2000)])]
    got, _ = _run({1: 1000, 2: 900}, wants)
    assert got == {1: (10, 1000), 2: (10, 900)}


def test_aCrowdedMarketCloses():
    rng = random.Random(7)
    asks = {p: rng.randint(60, 3000) for p in range(60)}
    wants = []
    for t in range(32):
        cands = rng.sample(range(60), 8)
        wants.append(Want(t, t, 'qb', 1, candidates=[(p, int(asks[p] * rng.uniform(1.0, 2.0))) for p in cands]))
    got, _ = _run(asks, wants, rank={t: t for t in range(32)})
    teams = [tid for tid, _s in got.values()]
    assert len(teams) == len(set(teams))           # one player per want
    for pid, (tid, sal) in got.items():
        assert sal >= asks[pid]


def test_walkAwayPriceGrowsWithTheEdgeOverTheNextOption():
    assert faMarket.walkAwayPrice(1000, 50, 50) == 1000
    assert faMarket.walkAwayPrice(1000, 60, 50) > 1000


def test_aMotiveIsStableAndLeansOnPersonality():
    p = SimpleNamespace(id=4242, faMotive=None, attributes=SimpleNamespace(personality='wholesome'))
    m = faMarket.motiveOf(p)
    assert m in faMarket.MOTIVES and p.faMotive == m
    assert faMarket.motiveOf(SimpleNamespace(id=4242, faMotive=None,
                                             attributes=SimpleNamespace(personality='wholesome'))) == m
    rng = random.Random(1)
    draws = [faMarket.rollMotive('wholesome', rng) for _ in range(4000)]
    assert draws.count('hometown') > 1.5 * draws.count('comfort')


def test_motivePulls():
    assert faMarket.motivePull('hometown', 1000, isHome=True, success=0, comfort=0) == pytest.approx(200)
    assert faMarket.motivePull('hometown', 1000, isHome=False, success=1, comfort=1) == 0
    assert faMarket.motivePull('winner', 1000, isHome=False, success=0.5, comfort=0) == pytest.approx(100)
    assert faMarket.motivePull('comfort', 1000, isHome=False, success=0, comfort=1) == pytest.approx(200)
    assert faMarket.motivePull('opportunity', 1000, isHome=True, success=1, comfort=1) == 0


# ── the re-sign head start (owner, 2026-11-01) ─────────────────────────────────────────

def _walkYear(pid, motive, rating=86, home=None):
    return SimpleNamespace(id=pid, faMotive=motive, homeTeamId=home, playerRating=rating,
                           position=SimpleNamespace(name='WR'),
                           attributes=SimpleNamespace(personality=None))


def test_aPlayersSenseOfHisWorthIsStableAndInHisMotivesRange():
    from managers.payroll import setShareUnit
    setShareUnit(5000)
    p = _walkYear(7, 'winner')
    r = faMarket.reservation(p, 13)
    assert r == faMarket.reservation(p, 13)
    assert 0.95 <= r <= 1.15
    assert faMarket.reservation(_walkYear(8, 'opportunity'), 13) == pytest.approx(0.85)


def test_aHometownPlayerTakesHisDiscountAndAWinnerTestsAWeakTeam():
    from managers.payroll import setShareUnit
    setShareUnit(5000)
    team = SimpleNamespace(id=3)
    weak = ({3: 0.0}, {3: 0.0})          # no success, no facilities to speak of
    homeAccepts = winnerAccepts = 0
    for pid in range(200):
        home = _walkYear(1000 + pid, 'hometown', home=3)
        sal, pull = faMarket.resignOffer(home, team, weak, minimum=50)
        homeAccepts += faMarket.acceptsResign(home, sal, pull, 13)
        win = _walkYear(2000 + pid, 'winner')
        sal, pull = faMarket.resignOffer(win, team, weak, minimum=50)
        winnerAccepts += faMarket.acceptsResign(win, sal, pull, 13)
    assert homeAccepts == 200            # offered his ask less his discount; he settles at 85-100%
    # Wants 95-115% of his ask and this team has no pull: a fair offer lands about a quarter
    # of the time, when he happens to value himself at or under his ask.
    assert 25 <= winnerAccepts <= 80


def test_theOfferIsTheAskLessThePull():
    from managers.payroll import setShareUnit, askingSalary
    setShareUnit(5000)
    p = _walkYear(9, 'hometown', home=3)
    sal, pull = faMarket.resignOffer(p, SimpleNamespace(id=3), ({}, {}), minimum=50)
    assert sal == math.ceil(askingSalary(p) - pull) and pull == pytest.approx(0.2 * askingSalary(p))
