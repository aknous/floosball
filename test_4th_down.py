"""
Test 4th down decision-making across coach aggressiveness levels and game scenarios.
Runs N iterations per scenario and reports decision percentages.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Avoid circular import: patch managers/__init__.py before importing floosball_game
import managers
managers.SeasonManager = None  # Stub out the circular reference
managers.__all__ = []

from collections import Counter
from floosball_game import Game, Play, PlayType, GameStatus
from floosball_coach import Coach

# ── Monkey-patch Play to record decisions without full execution ─────

_origRunPlay = Play.runPlay
_origPassPlay = Play.passPlay
_origKneel = Play.kneel

def _stubRunPlay(self):
    self.playType = PlayType.Run

def _stubPassPlay(self, playKey=None):
    self.playType = PlayType.Pass

def _stubKneel(self):
    self.playType = PlayType.Kneel

Play.runPlay = _stubRunPlay
Play.passPlay = _stubPassPlay
Play.kneel = _stubKneel

# ── Helpers ──────────────────────────────────────────────────────────

def makeCoach(aggressiveness=80, clockManagement=80):
    c = Coach()
    c.aggressiveness = aggressiveness
    c.clockManagement = clockManagement
    c.offensiveMind = 80
    return c

def makeKicker(rating=75, maxFgDist=55):
    """Minimal kicker stub with the attributes _fourthDownCaller needs."""
    class Kicker:
        pass
    k = Kicker()
    # gameAttributes.overallRating
    class GA:
        overallRating = rating
    k.gameAttributes = GA()
    k.maxFgDistance = maxFgDist
    k.gameStatsDict = {'kicking': {'fgAtt': 0, 'fgs': 0, 'longest': 0}}
    return k

def makeTeam(name="Home", abbr="HME", coach=None):
    """Minimal team stub."""
    class StubTeam:
        pass
    t = StubTeam()
    t.name = name
    t.abbr = abbr
    t.coach = coach or makeCoach()
    t.rosterDict = {'k': makeKicker()}
    t.defensePassCoverageRating = 70  # needed by _selectPassPlay
    return t

def setupGame(homeScore=0, awayScore=0, quarter=2, clock=450,
              down=4, yardsToEndzone=50, yardsToFirstDown=5,
              offenseIsHome=True):
    """Create a game in the specified state without running actual simulation."""
    home = makeTeam("Home", "HME")
    away = makeTeam("Away", "AWY")

    # We can't easily instantiate Game without real teams, so we'll
    # monkey-patch the minimum needed attributes.
    class StubGame(Game):
        def __init__(self):
            # Skip parent __init__ — set everything manually
            pass

    g = StubGame()
    g.homeTeam = home
    g.awayTeam = away
    g.homeScore = homeScore
    g.awayScore = awayScore
    g.currentQuarter = quarter
    g.gameClockSeconds = clock
    g.down = down
    g.yardsToEndzone = yardsToEndzone
    g.yardsToFirstDown = yardsToFirstDown
    g.yardsToSafety = 100 - yardsToEndzone
    g.offensiveTeam = home if offenseIsHome else away
    g.defensiveTeam = away if offenseIsHome else home
    g.homeTimeoutsRemaining = 3
    g.awayTimeoutsRemaining = 3
    g.yardLine = yardsToEndzone
    g.status = GameStatus.Active
    g.id = 1
    g.seasonNumber = 1
    g.week = 1
    g.gameType = 'regular'
    g.play = None  # Will be created per-iteration
    return g

def classifyDecision(play):
    """Return a simple string label for the 4th down decision."""
    pt = play.playType
    if pt == PlayType.Punt:
        return 'PUNT'
    elif pt == PlayType.FieldGoal:
        return 'FG'
    elif pt == PlayType.Kneel:
        return 'KNEEL'
    else:
        return 'GO_FOR_IT'

def runScenario(label, N, homeScore, awayScore, quarter, clock,
                yardsToEndzone, yardsToFirstDown, aggressiveness=80,
                clockMgmt=80, offenseIsHome=True):
    """Run N iterations and return decision distribution."""
    from floosball_game import Play

    g = setupGame(homeScore=homeScore, awayScore=awayScore,
                  quarter=quarter, clock=clock,
                  yardsToEndzone=yardsToEndzone,
                  yardsToFirstDown=yardsToFirstDown,
                  offenseIsHome=offenseIsHome)

    coach = makeCoach(aggressiveness, clockMgmt)
    g.offensiveTeam.coach = coach
    scoreDiff = (homeScore - awayScore) if offenseIsHome else (awayScore - homeScore)
    isHome = offenseIsHome

    counts = Counter()
    for _ in range(N):
        # Reset kicker stats each iteration so they don't accumulate
        g.offensiveTeam.rosterDict['k'].gameStatsDict = {
            'kicking': {'fgAtt': 0, 'fgs': 0, 'longest': 0}
        }
        g.play = Play(g)
        g._fourthDownCaller(scoreDiff, coach, isHome)
        counts[classifyDecision(g.play)] += 1

    return counts

def printResults(label, counts, N):
    """Pretty-print results for a scenario."""
    parts = []
    for decision in ['GO_FOR_IT', 'FG', 'PUNT', 'KNEEL']:
        pct = counts.get(decision, 0) / N * 100
        if pct > 0:
            parts.append(f"{decision}={pct:.1f}%")
    print(f"  {label:55s} {' | '.join(parts)}")


# ── Scenarios ────────────────────────────────────────────────────────

N = 5000

scenarios = [
    # ── LEADING ──
    ("LEADING", [
        # (label, homeScore, awayScore, quarter, clock, yte, ytg)
        ("Leading +7, Q2, 4th & 1, yte=48 (midfield)", 14, 7, 2, 450, 48, 1),
        ("Leading +7, Q2, 4th & 3, yte=38 (opp territory)", 14, 7, 2, 450, 38, 3),
        ("Leading +7, Q2, 4th & 1, yte=30 (FG range)", 14, 7, 2, 450, 30, 1),
        ("Leading +3, Q4, 4th & 1, yte=45, 4:00 left", 10, 7, 4, 240, 45, 1),
        ("Leading +3, Q4, 4th & 2, yte=35, 3:00 left", 10, 7, 4, 180, 35, 2),
        ("Leading +7, Q4, 4th & 3, yte=25, 2:00 left", 14, 7, 4, 120, 25, 3),
    ]),

    # ── TRAILING, IN FG RANGE ──
    ("TRAILING (FG range)", [
        ("Trailing -3, Q4, 4th & 5, yte=25, 1:30 left", 7, 10, 4, 90, 25, 5),
        ("Trailing -3, Q4, 4th & 5, yte=30, 1:30 left", 7, 10, 4, 90, 30, 5),
        ("Trailing -7, Q4, 4th & 5, yte=25, 1:30 left", 7, 14, 4, 90, 25, 5),
        ("Trailing -7, Q4, 4th & 5, yte=25, 1:00 left", 7, 14, 4, 60, 25, 5),
        ("Trailing -10, Q4, 4th & 8, yte=30, 1:30 left", 7, 17, 4, 90, 30, 8),
        ("Trailing -3, Q2, 4th & 3, yte=25", 7, 10, 2, 400, 25, 3),
    ]),

    # ── TRAILING, OUT OF FG RANGE ──
    ("TRAILING (no FG)", [
        ("Trailing -7, Q4, 4th & 3, yte=50, 2:00 left", 7, 14, 4, 120, 50, 3),
        ("Trailing -7, Q4, 4th & 8, yte=50, 2:00 left", 7, 14, 4, 120, 50, 8),
        ("Trailing -7, Q4, 4th & 3, yte=50, 4:00 left", 7, 14, 4, 240, 50, 3),
        ("Trailing -7, Q4, 4th & 8, yte=50, 4:00 left", 7, 14, 4, 240, 50, 8),
        ("Trailing -14, Q4, 4th & 5, yte=50, 4:00 left", 7, 21, 4, 240, 50, 5),
        ("Trailing -21, Q4, 4th & 5, yte=50, 4:00 left", 7, 28, 4, 240, 50, 5),
        ("Trailing -7, Q4, 4th & 2, yte=50, 6:00 left", 7, 14, 4, 360, 50, 2),
    ]),

    # ── TIED ──
    ("TIED", [
        ("Tied, Q2, 4th & 3, yte=25 (FG range)", 7, 7, 2, 400, 25, 3),
        ("Tied, Q2, 4th & 1, yte=15 (red zone)", 7, 7, 2, 400, 15, 1),
        ("Tied, Q2, 4th & 5, yte=3 (goal line)", 7, 7, 2, 400, 3, 5),
        ("Tied, Q2, 4th & 1, yte=50 (midfield, no FG)", 7, 7, 2, 400, 50, 1),
    ]),

    # ── DEEP OWN TERRITORY ──
    ("DEEP OWN TERRITORY", [
        ("Leading +7, Q2, 4th & 5, yte=80 (own 20)", 14, 7, 2, 400, 80, 5),
        ("Trailing -7, Q4, 4th & 5, yte=80, 2:00 left", 7, 14, 4, 120, 80, 5),
        ("Trailing -7, Q4, 4th & 5, yte=80, 0:45 left", 7, 14, 4, 45, 80, 5),
    ]),
]

aggrLevels = [
    ("Conserv (60)", 60),
    ("Neutral (80)", 80),
    ("Aggress (100)", 100),
]

print("=" * 120)
print(f"4th Down Decision Analysis — {N} iterations per scenario")
print("=" * 120)

for groupName, groupScenarios in scenarios:
    print(f"\n{'─' * 120}")
    print(f"  {groupName}")
    print(f"{'─' * 120}")

    for label, hs, aws, qtr, clk, yte, ytg in groupScenarios:
        print(f"\n  {label}")
        for aggrLabel, aggrVal in aggrLevels:
            counts = runScenario(label, N, hs, aws, qtr, clk, yte, ytg,
                                aggressiveness=aggrVal, clockMgmt=80)
            printResults(f"    {aggrLabel}", counts, N)

print(f"\n{'=' * 120}")
print("Done.")
