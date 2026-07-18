#!/usr/bin/env python3
"""
test_late_game_decisions.py
Validates the new late-game FG decision logic:
  - Trailing-by-3 desperation FG should DEFER on 1st-3rd down when plays remain
  - Tied + chip-shot FG range late Q4 should KICK or set up the kick

Tests across coach archetypes (aggressive/conservative, smart/dumb clock IQ)
and various clock+timeout combinations.

Usage: python test_late_game_decisions.py
"""

import sys, os, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Break floosball_game ↔ managers circular import
_stub = types.ModuleType('floosball_game')
class _GameStub: pass
_stub.Game = _GameStub
sys.modules['floosball_game'] = _stub

import managers.timingManager
del sys.modules['floosball_game']
import floosball_game as FloosGame

from collections import Counter
from types import SimpleNamespace
from floosball_game import PlayType, Play

# ─────────────────────────────────────────────────────────────────────
# Stub minimal Play methods so we can capture the decision without
# actually executing plays.
# ─────────────────────────────────────────────────────────────────────

_origRunPlay = Play.runPlay
_origPassPlay = Play.passPlay
_origKneel = Play.kneel
_origSpike = Play.spike

def _stubRun(self):
    self.playType = PlayType.Run

def _stubPass(self, playKey=None):
    self.playType = PlayType.Pass

def _stubKneel(self):
    self.playType = PlayType.Kneel

def _stubSpike(self):
    self.playType = PlayType.Spike

Play.runPlay = _stubRun
Play.passPlay = _stubPass
Play.kneel = _stubKneel
Play.spike = _stubSpike


def makeCoach(aggressiveness=80, clockManagement=80, offensiveMind=80, adaptability=80):
    return SimpleNamespace(
        aggressiveness=aggressiveness,
        clockManagement=clockManagement,
        offensiveMind=offensiveMind,
        adaptability=adaptability,
    )


def makeKicker(maxFgDistance=55):
    """Kicker stub with maxFgDistance and minimum gameAttributes for FG-prob estimate."""
    ga = SimpleNamespace(
        overallRating=80,
        accuracy=80,
        kickPower=80,
        confidenceModifier=0.0,
        determinationModifier=0.0,
    )
    return SimpleNamespace(
        maxFgDistance=maxFgDistance,
        gameAttributes=ga,
        gameStatsDict={'kicking': {'fgAtt': 0, 'fgs': 0, 'longest': 0}},
    )


def makeTeam(name='OFF', coach=None, kickerMaxFg=55):
    if coach is None:
        coach = makeCoach()
    return SimpleNamespace(
        name=name,
        teamName=name,
        abbr=name[:3],
        coach=coach,
        rosterDict={'k': makeKicker(maxFgDistance=kickerMaxFg)},
        defenseRunCoverageRating=75,
        defensePassRating=75,
        defensePassCoverageRating=75,
        elo=1500,
    )


def makeGame(*, down=1, ytg=10, quarter=4, clock=20, homeScore=0, awayScore=0,
             offIsHome=True, clockRunning=True, homeTOs=2, awayTOs=2,
             yardsToEndzone=20, offCoach=None, kickerMaxFg=55):
    """Set up a minimal Game state for the play-caller to evaluate."""
    g = object.__new__(FloosGame.Game)

    offCoach = offCoach or makeCoach()
    offTeam = makeTeam(name='OFF', coach=offCoach, kickerMaxFg=kickerMaxFg)
    defTeam = makeTeam(name='DEF')

    g.homeTeam = offTeam if offIsHome else defTeam
    g.awayTeam = defTeam if offIsHome else offTeam
    g.offensiveTeam = offTeam
    g.defensiveTeam = defTeam

    g.homeScore = homeScore
    g.awayScore = awayScore
    g.homeTimeoutsRemaining = homeTOs if offIsHome else awayTOs
    g.awayTimeoutsRemaining = awayTOs if offIsHome else homeTOs

    g.down = down
    g.yardsToFirstDown = ytg
    g.yardsToEndzone = yardsToEndzone
    g.yardsToSafety = 100 - yardsToEndzone

    g.currentQuarter = quarter
    g.gameClockSeconds = clock
    g.clockRunning = clockRunning
    g.twoMinuteWarningShown = True

    g.id = 1
    g.yardLine = yardsToEndzone
    g.totalPlays = 1
    g.gameFeed = []
    g.highlights = []
    g.leagueHighlights = []
    g.homeOffGameplan = None
    g.awayOffGameplan = None
    g.homeDefGameplan = None
    g.awayDefGameplan = None
    g.timingManager = None
    g.isRegularSeasonGame = False
    g.isTwoPtConv = False
    g.momentum = 0.0
    g.gamePressure = 0.5
    g.play = None
    return g


def classify(g):
    """Classify the resulting play decision."""
    cm = g.play.insights.get('clockMgmt') if g.play and hasattr(g.play, 'insights') else None
    decision = cm.get('decision') if cm else None

    pt = g.play.playType if g.play else None
    if decision == 'gameWinningFG':
        return 'GAME_WIN_FG'
    if decision == 'setupGameWinningFG':
        return 'SETUP_FG'
    if decision == 'desperationFG':
        return 'DESPERATION_FG'
    if decision == 'deferFG':
        return 'DEFER_FG'
    if pt == PlayType.FieldGoal:
        return 'FG_OTHER'
    if pt == PlayType.Run:
        return 'RUN'
    if pt == PlayType.Pass:
        return 'PASS'
    if pt == PlayType.Kneel:
        return 'KNEEL'
    if pt == PlayType.Spike:
        return 'SPIKE'
    return 'OTHER'


def runScenario(N=1000, **kwargs):
    counts = Counter()
    for _ in range(N):
        g = makeGame(**kwargs)
        g.play = Play(g)
        # Reset kicker stats each iteration
        g.offensiveTeam.rosterDict['k'].gameStatsDict = {
            'kicking': {'fgAtt': 0, 'fgs': 0, 'longest': 0}
        }
        try:
            g.playCaller()
        except Exception as e:
            counts[f'ERROR:{type(e).__name__}'] += 1
            continue
        counts[classify(g)] += 1
    return counts


def fmt(counts, N):
    parts = []
    for k in ['DESPERATION_FG', 'DEFER_FG', 'GAME_WIN_FG', 'SETUP_FG',
              'FG_OTHER', 'RUN', 'PASS', 'SPIKE', 'KNEEL', 'OTHER']:
        v = counts.get(k, 0)
        if v > 0:
            parts.append(f"{k}={v/N*100:.0f}%")
    # Surface unexpected errors
    for k, v in counts.items():
        if k.startswith('ERROR:'):
            parts.append(f"{k}={v/N*100:.0f}%")
    return ' | '.join(parts)


# ─────────────────────────────────────────────────────────────────────
# Helper-only tests (no play caller needed)
# ─────────────────────────────────────────────────────────────────────

def testHelper():
    print("=" * 72)
    print("PART 1 — _estimateAvailablePlays() walkthrough")
    print("=" * 72)
    print(f"{'scenario':<55s} → plays")
    print('-' * 72)

    cases = [
        ('20s, 1st down, 0 TO',  dict(clock=20, down=1, homeTOs=0)),
        ('20s, 1st down, 1 TO',  dict(clock=20, down=1, homeTOs=1)),
        ('20s, 1st down, 2 TO',  dict(clock=20, down=1, homeTOs=2)),
        ('20s, 3rd down, 0 TO',  dict(clock=20, down=3, homeTOs=0)),
        ('20s, 3rd down, 2 TO',  dict(clock=20, down=3, homeTOs=2)),
        ('30s, 1st down, 0 TO',  dict(clock=30, down=1, homeTOs=0)),
        ('30s, 1st down, 1 TO',  dict(clock=30, down=1, homeTOs=1)),
        ('45s, 1st down, 1 TO',  dict(clock=45, down=1, homeTOs=1)),
        ('60s, 1st down, 1 TO',  dict(clock=60, down=1, homeTOs=1)),
        (' 8s, 1st down, 1 TO',  dict(clock=8,  down=1, homeTOs=1)),
        ('10s, 1st down, 0 TO',  dict(clock=10, down=1, homeTOs=0)),
        (' 5s, 1st down, 1 TO',  dict(clock=5,  down=1, homeTOs=1)),
    ]
    for label, kw in cases:
        g = makeGame(**kw)
        n = g._estimateAvailablePlays()
        print(f"  {label:<53s} → {n}")
    print()


# ─────────────────────────────────────────────────────────────────────
# Bug 1 — trailing by 3, FG range, NOT 4th down — should defer FG
# ─────────────────────────────────────────────────────────────────────

def testBug1():
    print("=" * 72)
    print("PART 2 — Bug 1: trailing -3, FG range, not 4th down")
    print("  Expected: defer FG when plays remain; kick when out of plays")
    print("=" * 72)

    avgC      = makeCoach(80, 80)
    aggrC     = makeCoach(95, 85)
    cautiousC = makeCoach(65, 85)
    dumbC     = makeCoach(80, 60)

    base = dict(quarter=4, homeScore=0, awayScore=3, yardsToEndzone=30,
                kickerMaxFg=55)

    print(f"\n{'scenario':<55s} {'distribution'}")
    print('-' * 72)
    scenarios = [
        ('20s 1st&10 1 TO  avg coach',     {**base, 'down':1, 'ytg':10, 'clock':20, 'homeTOs':1, 'offCoach':avgC}),
        ('20s 1st&10 1 TO  aggressive coach',  {**base, 'down':1, 'ytg':10, 'clock':20, 'homeTOs':1, 'offCoach':aggrC}),
        ('20s 1st&10 1 TO  cautious coach',{**base, 'down':1, 'ytg':10, 'clock':20, 'homeTOs':1, 'offCoach':cautiousC}),
        ('20s 1st&10 1 TO  dumb coach',    {**base, 'down':1, 'ytg':10, 'clock':20, 'homeTOs':1, 'offCoach':dumbC}),
        ('20s 1st&10 0 TO  avg coach',     {**base, 'down':1, 'ytg':10, 'clock':20, 'homeTOs':0, 'offCoach':avgC}),
        ('20s 3rd&5  0 TO  avg coach',     {**base, 'down':3, 'ytg':5,  'clock':20, 'homeTOs':0, 'offCoach':avgC}),
        ('15s 1st&10 0 TO  avg coach',     {**base, 'down':1, 'ytg':10, 'clock':15, 'homeTOs':0, 'offCoach':avgC}),
        (' 8s 1st&10 1 TO  avg coach',     {**base, 'down':1, 'ytg':10, 'clock':8,  'homeTOs':1, 'offCoach':avgC}),
        ('25s 2nd&7  2 TO  aggressive coach',  {**base, 'down':2, 'ytg':7,  'clock':25, 'homeTOs':2, 'offCoach':aggrC}),
    ]
    for label, kw in scenarios:
        c = runScenario(N=600, **kw)
        print(f"  {label:<53s} {fmt(c, 600)}")
    print()


# ─────────────────────────────────────────────────────────────────────
# Bug 2 — tied, FG range, late Q4 — should kick or set up FG
# ─────────────────────────────────────────────────────────────────────

def testBug2():
    print("=" * 72)
    print("PART 3 — Bug 2: tied, chip-shot FG range, late Q4")
    print("  Expected: kick when out of plays; drain clock with run otherwise")
    print("=" * 72)

    avgC      = makeCoach(80, 80)
    aggrC     = makeCoach(95, 85)
    cautiousC = makeCoach(65, 85)
    dumbC     = makeCoach(80, 60)

    base = dict(quarter=4, homeScore=14, awayScore=14, yardsToEndzone=15,
                kickerMaxFg=55)

    print(f"\n{'scenario':<55s} {'distribution'}")
    print('-' * 72)
    scenarios = [
        (' 8s 1st&10 1 TO  avg coach',     {**base, 'down':1, 'ytg':10, 'clock':8,  'homeTOs':1, 'offCoach':avgC}),
        (' 8s 1st&10 0 TO  avg coach',     {**base, 'down':1, 'ytg':10, 'clock':8,  'homeTOs':0, 'offCoach':avgC}),
        ('15s 1st&10 1 TO  avg coach',     {**base, 'down':1, 'ytg':10, 'clock':15, 'homeTOs':1, 'offCoach':avgC}),
        ('25s 1st&10 1 TO  avg coach',     {**base, 'down':1, 'ytg':10, 'clock':25, 'homeTOs':1, 'offCoach':avgC}),
        ('25s 1st&10 1 TO  aggressive coach',  {**base, 'down':1, 'ytg':10, 'clock':25, 'homeTOs':1, 'offCoach':aggrC}),
        ('25s 1st&10 1 TO  cautious coach',{**base, 'down':1, 'ytg':10, 'clock':25, 'homeTOs':1, 'offCoach':cautiousC}),
        ('25s 1st&10 1 TO  dumb coach',    {**base, 'down':1, 'ytg':10, 'clock':25, 'homeTOs':1, 'offCoach':dumbC}),
        ('30s 1st&10 2 TO  avg coach',     {**base, 'down':1, 'ytg':10, 'clock':30, 'homeTOs':2, 'offCoach':avgC}),
        # Long FG (not chip-shot) — should NOT trigger game-winning branch
        ('25s 1st&10 1 TO  long FG (50yd) avg coach',
         {**base, 'down':1, 'ytg':10, 'clock':25, 'homeTOs':1, 'offCoach':avgC,
          'yardsToEndzone':45}),
    ]
    for label, kw in scenarios:
        c = runScenario(N=600, **kw)
        print(f"  {label:<53s} {fmt(c, 600)}")
    print()


# ─────────────────────────────────────────────────────────────────────
# Sanity — long FG range trailing by 3 should still defer / kick same as before
# ─────────────────────────────────────────────────────────────────────

def testSanity():
    print("=" * 72)
    print("PART 4 — Sanity: out-of-range / leading / non-late-game (no special logic)")
    print("=" * 72)

    avgC = makeCoach(80, 80)

    base = dict(quarter=4, kickerMaxFg=55, offCoach=avgC)

    print(f"\n{'scenario':<55s} {'distribution'}")
    print('-' * 72)
    scenarios = [
        # Trailing -3 but out of FG range (yardsToEndzone > kickerMaxFg)
        ('out of FG range -3  20s 1st&10 1 TO',
         {**base, 'down':1, 'ytg':10, 'clock':20, 'homeTOs':1,
          'homeScore':0, 'awayScore':3, 'yardsToEndzone':60}),
        # Tied but NOT late Q4 (>30s)
        ('tied 90s 1st&10 1 TO',
         {**base, 'down':1, 'ytg':10, 'clock':90, 'homeTOs':1,
          'homeScore':14, 'awayScore':14, 'yardsToEndzone':15}),
        # Tied early Q3 (no special logic)
        ('tied early Q3 30s 1st&10 1 TO',
         {**base, 'quarter':3, 'down':1, 'ytg':10, 'clock':30, 'homeTOs':1,
          'homeScore':14, 'awayScore':14, 'yardsToEndzone':15}),
        # Leading +1 with chip shot (kneel logic should fire)
        ('leading +1 30s 1st&10 1 TO  yardsToSafety>2',
         {**base, 'down':1, 'ytg':10, 'clock':30, 'homeTOs':1,
          'homeScore':15, 'awayScore':14, 'yardsToEndzone':15}),
    ]
    for label, kw in scenarios:
        c = runScenario(N=600, **kw)
        print(f"  {label:<53s} {fmt(c, 600)}")
    print()


if __name__ == '__main__':
    testHelper()
    testBug1()
    testBug2()
    testSanity()
