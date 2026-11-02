"""
PROSPECTS ARE A GAMBLE, AND SCOUTING AND FACILITIES DECIDE HOW GOOD A ONE.

docs/PROSPECT_UNCERTAINTY_PLAN.md (owner, 2026-10-30). A prospect's projection used to be
his destiny: every trained attribute climbed to a fixed trueSkill cap that fans and every
GM could read, so a five-season redraft kept the #1 pick 80-85% of the time against the
NFL's 26%. Now:

  - HIDDEN TALENT: a shift drawn at generation, already inside trueSkill/potential, that the
    public consensus takes back out and a team sees `vision` of; revealed over his first
    seasons;
  - DEVELOPMENT LUCK: each season a rising player's cap takes a step, drifting with the
    development environment;
  - the environment and the scouting read are 40% coach, 60% facility;
  - the class is 1.5 per team and the undrafted surplus washes out, keeping what each
    position needs for the supply floor.

The redraft sizing lives in prospect_redraft_check.py; this pins the mechanics.

Run with pytest.
"""
import random
from types import SimpleNamespace

import pytest

import constants
import floosball_player as FP
from floosball_team import Team
from managers.playerManager import PlayerManager
from managers.frontOfficeBrain import FrontOfficeBrain
from player_development import PlayerDevelopment, CareerPhase


def _manager(numTeams=32):
    pm = PlayerManager.__new__(PlayerManager)
    pm.activePlayers = []
    pm.freeAgents = []
    pm.unusedNames = [f'Name {i}' for i in range(5000)]
    pm.db_session = None
    pm.serviceContainer = SimpleNamespace(
        getService=lambda name: SimpleNamespace(teams=[None] * numTeams))
    return pm


_IDS = iter(range(1, 10**6))


def _prospect(pm, pos=FP.Position.WR, shift=0, seed=80):
    p = pm.createPlayer(pos, seed, seed)
    p.id = next(_IDS)
    p.seasonsPlayed = 0
    p.prospect_seasons = 0
    p.applyEntryDiscount(constants.PROSPECT_ENTRY_DISCOUNT)
    if shift:
        p.shiftTalent(shift)
        p.talentShift = shift
    return p


def _team(training=0, scouting=0, coachScouting=80, coachDev=80, teamId=2):
    t = Team.__new__(Team)
    t.id = teamId
    t.facilities = {'training': training, 'scouting': scouting}
    t.coach = SimpleNamespace(scouting=coachScouting, playerDevelopment=coachDev, id=teamId)
    return t


@pytest.fixture(autouse=True)
def _clean(monkeypatch, tmp_path):
    monkeypatch.delenv('FLOOS_FACILITY_FORCE', raising=False)


# ── hidden talent ──────────────────────────────────────────────────────────────────────

def testTheShiftIsTwoSidedFatTailedAndCentered():
    rng = random.Random(4)
    draws = [PlayerManager.drawTalentShift(rng) for _ in range(20000)]
    mean = sum(draws) / len(draws)
    assert abs(mean) < 0.3, mean
    assert sum(d <= -20 for d in draws) > 200, 'busts must exist'
    assert sum(d >= 20 for d in draws) > 200, 'diamonds must exist'
    assert sum(abs(d) <= 5 for d in draws) / len(draws) > 0.4, 'most prospects are close to the consensus'


def testTheConsensusTakesTheUnrevealedShiftBackOut():
    pm = _manager()
    p = _prospect(pm, seed=70)
    before = p.projectionFor(0.0)
    debut = p.playerRating
    p.shiftTalent(12)
    p.talentShift = 12
    # Before any development the public still sees the prospect it saw before the shift.
    # (Seed 70 keeps every potential under 100: a clamped attribute loses part of its shift,
    # which reads a very high-potential diamond's public ceiling a little low.)
    assert p.projectionFor(0.0) == pytest.approx(before, abs=1)
    # A perfect scout sees the truth, which is better.
    assert p.projectionFor(1.0)[0] > before[0] + 4
    # The debut rating does not move.
    assert p.playerRating == debut


def testTheShiftIsRevealedOverHisFirstSeasons():
    pm = _manager()
    p = _prospect(pm, shift=-15)
    assert p.unrevealedShift() == pytest.approx(-15)
    p.seasonsPlayed = 2
    assert -15 < p.unrevealedShift() < 0
    p.seasonsPlayed = len(constants.PROSPECT_TALENT_REVEALED)
    assert p.unrevealedShift() == 0


def testTheClassIsBiggerAndItsMixIsDealt():
    pm = _manager(32)
    rookies = pm._generateRookieClass(1)
    assert len(rookies) == 48
    counts = {}
    for r in rookies:
        counts[r.position] = counts.get(r.position, 0) + 1
    assert counts[FP.Position.K] == 8 and counts[FP.Position.WR] == 16
    assert any(r.talentShift for r in rookies)


# ── what a team sees ───────────────────────────────────────────────────────────────────

def testFacilitiesCarryMoreOfTheScoutingRead():
    brain = FrontOfficeBrain(None)
    v = lambda c, lvl: brain.scoutingVision(SimpleNamespace(scouting=c), _team(scouting=lvl, coachScouting=c))
    assert v(100, 5) == pytest.approx(1.0)
    assert v(60, 5) == pytest.approx(0.70)      # the worst coach with a full department
    assert v(100, 0) == pytest.approx(0.55)     # the best coach with none
    assert v(60, 0) == pytest.approx(constants.SCOUT_VISION_FLOOR)   # nobody is blind
    assert v(60, 5) > v(100, 0)
    assert v(60, 1) > v(60, 0)                  # every level counts


def testATeamSeesWhatItsScoutingAllows():
    pm = _manager()
    p = _prospect(pm, seed=78, shift=16)
    p.is_upcoming_rookie = True
    brain = FrontOfficeBrain(None)
    brain.season, brain.week = 1, 22
    elite = _team(scouting=5, coachScouting=100)
    blind = _team(scouting=0, coachScouting=60)
    assert brain.expectedFor(p, elite) == pytest.approx(p.projectionFor(1.0)[0])
    # The least-scouted team still reads at the floor, above the public consensus.
    assert brain.expectedFor(p, blind) == pytest.approx(p.projectionFor(constants.SCOUT_VISION_FLOOR)[0])
    assert brain.expectedFor(p, elite) > brain.expectedFor(p, blind) + 5


# ── the development environment ────────────────────────────────────────────────────────

def testFacilitiesCarryMoreOfDevelopment():
    lv = constants.FACILITY_CATALOG['training']['levels']
    assert PlayerDevelopment.developmentBias(60, lv[5]) == pytest.approx(3.6)
    assert PlayerDevelopment.developmentBias(100, lv[0]) == pytest.approx(2.4)
    assert PlayerDevelopment.developmentBias(100, lv[5]) == pytest.approx(6.0)


def testLuckDriftsWithTheEnvironmentAndOnlyWhileRising():
    pm = _manager()
    rng = random.Random(9)
    good = [PlayerDevelopment.applyDevelopmentLuck(_prospect(pm), 6.0, rng) for _ in range(400)]
    poor = [PlayerDevelopment.applyDevelopmentLuck(_prospect(pm), 0.0, rng) for _ in range(400)]
    assert sum(good) / len(good) > 1.0
    assert sum(poor) / len(poor) < -1.0
    vet = _prospect(pm)
    vet.seasonsPlayed = 12
    assert PlayerDevelopment.careerContext(vet, 0).phase != CareerPhase.RISING
    assert PlayerDevelopment.applyDevelopmentLuck(vet, 6.0, rng) == 0


def testLuckIsNeutralAtTheLeaguesOwnAverage(monkeypatch):
    # A league whose facilities are all strong: its average environment drifts nobody.
    pm = _manager()
    monkeypatch.setattr(PlayerDevelopment, 'leagueNeutralBias', 5.0)
    rng = random.Random(3)
    steps = [PlayerDevelopment.applyDevelopmentLuck(_prospect(pm), 5.0, rng) for _ in range(600)]
    assert abs(sum(steps) / len(steps)) < 0.15
    below = [PlayerDevelopment.applyDevelopmentLuck(_prospect(pm), 3.4, rng) for _ in range(600)]
    assert sum(below) / len(below) < -0.6, 'below the league average still costs'


def testFarBelowHisTrueLevelHeGrowsFaster():
    ctx = PlayerDevelopment.careerContext(SimpleNamespace(seasonsPlayed=0, prospect_seasons=0,
                                                          attributes=SimpleNamespace(longevity=10)), 2)
    assert ctx.phase == CareerPhase.RISING
    usual = PlayerDevelopment._settle(70, 3, 81, 90, ctx, 0, False)       # the normal debut gap
    farBelow = PlayerDevelopment._settle(70, 3, 96, 99, ctx, 0, False)    # a diamond
    assert usual == 73
    assert farBelow > usual + 3


# ── the undrafted ──────────────────────────────────────────────────────────────────────

def testOnlyTheSurplusWashesOut(monkeypatch):
    pm = _manager(4)
    monkeypatch.setattr(pm, '_playersWithARecord', lambda ids: set())
    removed = []
    monkeypatch.setattr(pm, '_removeUnsignedPlayer', lambda p: removed.append(p))
    monkeypatch.setattr(pm, 'addToPositionList', lambda p: None)
    # The pool already covers every position except kickers, which are two short.
    monkeypatch.setattr(pm, 'positionSupplyDeficits',
                        lambda n, countProspects=False: {FP.Position.K: 2})
    ks = [_prospect(pm, FP.Position.K, seed=s) for s in (70, 85, 78)]
    wrs = [_prospect(pm, FP.Position.WR, seed=s) for s in (75, 80)]
    out = pm.washOutUndrafted(ks + wrs, 4)
    keptIds = set(out['kept'])
    assert {k.id for k in ks if k.playerRating >= sorted(x.playerRating for x in ks)[1]} <= keptIds
    assert len([k for k in ks if k.id in keptIds]) == 2
    assert all(w in removed for w in wrs)
    assert all(not r.is_upcoming_rookie and r.is_undrafted for r in ks + wrs)


def testAPlayerWithARecordIsNeverWashedOut(monkeypatch):
    pm = _manager(4)
    p = _prospect(pm, FP.Position.WR)
    monkeypatch.setattr(pm, '_playersWithARecord', lambda ids: set(ids))
    monkeypatch.setattr(pm, '_removeUnsignedPlayer', lambda pl: pytest.fail('removed a player with a record'))
    monkeypatch.setattr(pm, 'addToPositionList', lambda pl: None)
    monkeypatch.setattr(pm, 'positionSupplyDeficits', lambda n, countProspects=False: {})
    assert pm.washOutUndrafted([p], 4)['kept'] == [p.id]


# ── what fans see ──────────────────────────────────────────────────────────────────────

def testFansSeeTheConsensus():
    import api.main as M
    pm = _manager()
    p = _prospect(pm, seed=80, shift=-18)
    proj = M._prospectProjection(p)
    assert proj['expected'] == pytest.approx(p.projectionFor(0.0)[0], abs=0.1)
    assert proj['expected'] > p.projectionFor(1.0)[0]      # the touted bust looks better than he is
