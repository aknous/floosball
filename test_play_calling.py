#!/usr/bin/env python3
"""
test_play_calling.py
Tests the weighted probability play-calling system in specific game situations.

Two parts:
  1. Weight distributions — shows the run/short/medium/long percentages for
     key situations so you can see how the system behaves without running plays.
  2. Clock management — verifies kneel/spike trigger (or don't trigger) in
     the scenarios where they should / shouldn't fire.

Usage:
    python test_play_calling.py
"""

import sys, os, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Break the floosball_game ↔ managers circular import.
# seasonManager.py uses `FloosGame.Game` as a type annotation at class-definition
# time, which fails when floosball_game is only partially initialised.
# Solution: register a stub module first so the annotation resolves, then load
# the real module once managers is fully cached.
_stub = types.ModuleType('floosball_game')
class _GameStub: pass
_stub.Game = _GameStub
sys.modules['floosball_game'] = _stub

import managers.timingManager   # loads managers/__init__ → seasonManager (uses stub) ✓

del sys.modules['floosball_game']   # remove stub; managers is now fully cached
import floosball_game as FloosGame   # real load — managers already in sys.modules ✓

from types import SimpleNamespace
from floosball_game import PlayType

# ─────────────────────────────────────────────────────────────────────────────
# Minimal stubs — only the attributes playCaller() and the weight pipeline need
# ─────────────────────────────────────────────────────────────────────────────

def makeCoach(aggressiveness=80, offensiveMind=80, adaptability=80):
    return SimpleNamespace(
        aggressiveness=aggressiveness,
        offensiveMind=offensiveMind,
        adaptability=adaptability,
    )

def makeTeam(name='TEAM', coach=None, defRunRating=75, defPassRating=75):
    if coach is None:
        coach = makeCoach()
    # NOTE: include `name` so that two teams with same numeric attributes are
    # not accidentally equal under SimpleNamespace value-based __eq__.
    return SimpleNamespace(
        name=name,
        teamName=name,   # used by _callTimeout()
        abbr=name[:3],
        coach=coach,
        rosterDict={'k': SimpleNamespace(maxFgDistance=52)},
        defenseRunCoverageRating=defRunRating,
        defensePassRating=defPassRating,
        elo=1500,
    )

def makeGame(down=1, ytg=10, quarter=1, clock=600, homeScore=0, awayScore=0,
             offIsHome=True, clockRunning=True, homeTOs=3, awayTOs=3,
             yardsToEndzone=50, offCoach=None, defRunRating=75, defPassRating=75):
    """Bypass Game.__init__ and set only the attributes the play-caller touches."""
    g = object.__new__(FloosGame.Game)

    offCoach = offCoach or makeCoach()

    # Unique names ensure SimpleNamespace value-equality doesn't confuse isHome check
    offTeam = makeTeam(name='OFF', coach=offCoach)
    defTeam = makeTeam(name='DEF', defRunRating=defRunRating, defPassRating=defPassRating)

    g.homeTeam  = offTeam if offIsHome else defTeam
    g.awayTeam  = defTeam if offIsHome else offTeam
    g.offensiveTeam = offTeam
    g.defensiveTeam = defTeam

    g.homeScore = homeScore
    g.awayScore = awayScore
    g.homeTimeoutsRemaining = homeTOs
    g.awayTimeoutsRemaining = awayTOs

    g.down            = down
    g.yardsToFirstDown = ytg
    g.yardsToEndzone  = yardsToEndzone
    g.yardsToSafety   = 100 - yardsToEndzone

    g.currentQuarter   = quarter
    g.gameClockSeconds = clock
    g.clockRunning     = clockRunning
    g.twoMinuteWarningShown = True   # suppress mid-test two-minute-warning

    g.totalPlays       = 1
    g.gameFeed         = []
    g.highlights       = []
    g.leagueHighlights = []
    g.homeOffGameplan  = None
    g.awayOffGameplan  = None
    g.homeDefGameplan  = None
    g.awayDefGameplan  = None
    g.timingManager    = None
    g.isRegularSeasonGame = False
    g.isTwoPtConv      = False
    g.play             = None
    return g


# ─────────────────────────────────────────────────────────────────────────────
# Part 1 — Weight distributions
# ─────────────────────────────────────────────────────────────────────────────

def computeWeights(g, coach):
    """Run the full weight pipeline and return normalised percentages."""
    scoreDiff = (g.homeScore - g.awayScore) if g.offensiveTeam is g.homeTeam \
                else (g.awayScore - g.homeScore)
    w = g._computePlayWeights(scoreDiff, coach)
    total = sum(w.values())
    return {k: round(v / total * 100, 1) for k, v in w.items()}


def printWeights(label, w):
    BAR = 28
    print(f"\n  {label}")
    for play in ('run', 'short', 'medium', 'long'):
        pct = w[play]
        bar = '█' * int(pct / 100 * BAR + 0.5)
        print(f"    {play:8s}  {pct:5.1f}%  {bar}")


def runWeightTests():
    """Expanded weight scenarios organized by situational group."""
    print("=" * 60)
    print("PART 1 — PLAY WEIGHT DISTRIBUTIONS")
    print("  (all % normalised over run+short+medium+long)")
    print("=" * 60)

    avgCoach     = makeCoach(80, 80, 80)
    aggrCoach    = makeCoach(95, 85, 80)
    conservCoach = makeCoach(65, 65, 80)
    adaptCoach   = makeCoach(80, 80, 95)

    def group(title, scenarios):
        print(f"\n── {title} ──")
        for label, gameKwargs, coach in scenarios:
            g = makeGame(offCoach=coach, **gameKwargs)
            w = computeWeights(g, coach)
            printWeights(label, w)

    base = dict(quarter=1, clock=600, homeScore=0, awayScore=0, yardsToEndzone=50)

    group("Down/Distance Baselines  (avg coach, Q1, even, midfield)", [
        ("1st & 10",                    {**base, 'down':1, 'ytg':10}, avgCoach),
        ("2nd &  3  (short yardage)",   {**base, 'down':2, 'ytg':3},  avgCoach),
        ("2nd &  7",                    {**base, 'down':2, 'ytg':7},  avgCoach),
        ("2nd & 10+",                   {**base, 'down':2, 'ytg':10}, avgCoach),
        ("3rd &  2  (QB sneak range)",  {**base, 'down':3, 'ytg':2},  avgCoach),
        ("3rd &  5",                    {**base, 'down':3, 'ytg':5},  avgCoach),
        ("3rd &  8  (money down)",      {**base, 'down':3, 'ytg':8},  avgCoach),
        ("3rd & 15",                    {**base, 'down':3, 'ytg':15}, avgCoach),
        ("3rd & 20+ (Hail Mary range)", {**base, 'down':3, 'ytg':20}, avgCoach),
    ])

    group("Q4 Trailing -7 on 3rd & 8 — Clock Urgency Progression", [
        (">5 min  (5:30)", dict(down=3, ytg=8, quarter=4, clock=330, homeScore=0, awayScore=7), avgCoach),
        ("<5 min  (4:30)", dict(down=3, ytg=8, quarter=4, clock=270, homeScore=0, awayScore=7), avgCoach),
        ("<3 min  (2:30)", dict(down=3, ytg=8, quarter=4, clock=150, homeScore=0, awayScore=7), avgCoach),
        ("<2 min  (1:30)", dict(down=3, ytg=8, quarter=4, clock=90,  homeScore=0, awayScore=7), avgCoach),
        ("<1 min  (0:45)", dict(down=3, ytg=8, quarter=4, clock=45,  homeScore=0, awayScore=7), avgCoach),
    ])

    group("Q4 Leading — Protect the Lead  (avg coach, 1st & 10)", [
        ("+3   leading  4:00", dict(down=1, ytg=10, quarter=4, clock=240, homeScore=3,  awayScore=0), avgCoach),
        ("+7   leading  3:00", dict(down=1, ytg=10, quarter=4, clock=180, homeScore=7,  awayScore=0), avgCoach),
        ("+14  leading  4:00", dict(down=1, ytg=10, quarter=4, clock=240, homeScore=14, awayScore=0), avgCoach),
    ])

    group("Q2 Two-Minute Drill  (trailing -7, 2nd & 8, midfield)", [
        ("Q2  1:45  no TOs  trailing -7",
         dict(down=2, ytg=8, quarter=2, clock=105, homeScore=0, awayScore=7), avgCoach),
    ])

    group("Q3 Comeback Mode  (3rd & 8, 7:30 left)", [
        ("trailing  -7   Q3", dict(down=3, ytg=8, quarter=3, clock=450, homeScore=0, awayScore=7),  avgCoach),
        ("trailing -14   Q3", dict(down=3, ytg=8, quarter=3, clock=450, homeScore=0, awayScore=14), avgCoach),
        ("trailing -21   Q3", dict(down=3, ytg=8, quarter=3, clock=450, homeScore=0, awayScore=21), avgCoach),
    ])

    group("Field Position  (avg coach, Q2, even, 1st & 10)", [
        ("Own  5-yd line  yte=95  (safety risk)", dict(down=1, ytg=10, quarter=2, clock=600, homeScore=0, awayScore=0, yardsToEndzone=95), avgCoach),
        ("Own 20-yd line  yte=80",                dict(down=1, ytg=10, quarter=2, clock=600, homeScore=0, awayScore=0, yardsToEndzone=80), avgCoach),
        ("Midfield        yte=50",                dict(down=1, ytg=10, quarter=2, clock=600, homeScore=0, awayScore=0, yardsToEndzone=50), avgCoach),
        ("Opp 25-yd line  yte=25",                dict(down=1, ytg=10, quarter=2, clock=600, homeScore=0, awayScore=0, yardsToEndzone=25), avgCoach),
        ("Red zone        yte=15",                dict(down=1, ytg=10, quarter=2, clock=600, homeScore=0, awayScore=0, yardsToEndzone=15), avgCoach),
        ("Goal line       yte=5",                 dict(down=1, ytg=10, quarter=2, clock=600, homeScore=0, awayScore=0, yardsToEndzone=5),  avgCoach),
    ])

    group("Coach Personality Matrix  (3rd & 8, Q1, even)", [
        ("aggr=95  offMind=95  (gunslinger)",    dict(down=3, ytg=8, quarter=1, clock=600, homeScore=0, awayScore=0), makeCoach(95, 95, 80)),
        ("aggr=95  offMind=65  (gambler)",       dict(down=3, ytg=8, quarter=1, clock=600, homeScore=0, awayScore=0), makeCoach(95, 65, 80)),
        ("aggr=80  offMind=80  (average)",       dict(down=3, ytg=8, quarter=1, clock=600, homeScore=0, awayScore=0), makeCoach(80, 80, 80)),
        ("aggr=65  offMind=95  (cerebral/safe)", dict(down=3, ytg=8, quarter=1, clock=600, homeScore=0, awayScore=0), makeCoach(65, 95, 80)),
        ("aggr=65  offMind=65  (conservative)",  dict(down=3, ytg=8, quarter=1, clock=600, homeScore=0, awayScore=0), makeCoach(65, 65, 80)),
    ])

    group("Matchup Exploitation  (1st & 10, Q2, even, adaptive coach adapt=95)", [
        ("Weak run-D  (60)  defRun=60  defPass=75", dict(down=1, ytg=10, quarter=2, clock=600, homeScore=0, awayScore=0, defRunRating=60,  defPassRating=75), adaptCoach),
        ("Weak pass-D (60)  defRun=75  defPass=60", dict(down=1, ytg=10, quarter=2, clock=600, homeScore=0, awayScore=0, defRunRating=75,  defPassRating=60), adaptCoach),
        ("Average defense   defRun=75  defPass=75", dict(down=1, ytg=10, quarter=2, clock=600, homeScore=0, awayScore=0, defRunRating=75,  defPassRating=75), adaptCoach),
        ("Strong run-D (90) defRun=90  defPass=75", dict(down=1, ytg=10, quarter=2, clock=600, homeScore=0, awayScore=0, defRunRating=90,  defPassRating=75), adaptCoach),
        ("Iron curtain (90) defRun=90  defPass=90", dict(down=1, ytg=10, quarter=2, clock=600, homeScore=0, awayScore=0, defRunRating=90,  defPassRating=90), adaptCoach),
    ])

    group("Combined Stress Scenarios", [
        ("Q4 -7  1:30  RED ZONE  3rd & 8  (trailing + red zone)",
         dict(down=3, ytg=8,  quarter=4, clock=90,  homeScore=0, awayScore=7,  yardsToEndzone=15), avgCoach),
        ("Q4 +7  3:00  OWN 20   1st & 10  (leading + safety avoidance)",
         dict(down=1, ytg=10, quarter=4, clock=180, homeScore=7, awayScore=0,  yardsToEndzone=80), avgCoach),
        ("Q4 -7  1:30  OWN 5    2nd & 8   (trailing vs safety risk — conflict)",
         dict(down=2, ytg=8,  quarter=4, clock=90,  homeScore=0, awayScore=7,  yardsToEndzone=95), avgCoach),
        ("Q3 -14  gunslinger  3rd & 15   (Q3 comeback + coach personality)",
         dict(down=3, ytg=15, quarter=3, clock=450, homeScore=0, awayScore=14), makeCoach(95, 95, 80)),
        ("Q4 -7  1:30  RED ZONE  gunslinger  3rd & 8  (all mods firing)",
         dict(down=3, ytg=8,  quarter=4, clock=90,  homeScore=0, awayScore=7,  yardsToEndzone=15), makeCoach(95, 95, 80)),
    ])

    print()


# ─────────────────────────────────────────────────────────────────────────────
# Analysis — comparative tables and behavioural findings
# ─────────────────────────────────────────────────────────────────────────────

def runAnalysis():
    """Compute targeted comparison tables and surface notable system behaviours."""
    print("=" * 60)
    print("ANALYSIS — COMPARATIVE TABLES & KEY FINDINGS")
    print("=" * 60)

    HDR = f"  {'Scenario':<42} {'run':>5} {'sht':>5} {'med':>5} {'long':>5}"
    ROW = "  {:<42} {:>4.1f}% {:>4.1f}% {:>4.1f}% {:>4.1f}%"

    def wts(down=3, ytg=8, quarter=1, clock=600, homeScore=0, awayScore=0,
            yardsToEndzone=50, offCoach=None, defRunRating=75, defPassRating=75):
        c = offCoach or makeCoach()
        g = makeGame(down=down, ytg=ytg, quarter=quarter, clock=clock,
                     homeScore=homeScore, awayScore=awayScore,
                     yardsToEndzone=yardsToEndzone, offCoach=c,
                     defRunRating=defRunRating, defPassRating=defPassRating)
        return computeWeights(g, c)

    # ── [1] Clock urgency ─────────────────────────────────────────────
    print("\n[1] CLOCK URGENCY — 3rd & 8, trailing -7")
    print("    Thresholds: <300 sec and <120 sec. Steps at those boundaries.")
    print(HDR)
    for label, q, secs in [
        ("Q1 baseline (no pressure)",  1, 600),
        ("Q4 >5 min   (5:30)",         4, 330),
        ("Q4 <5 min   (4:30)",         4, 270),
        ("Q4 <3 min   (2:30)",         4, 150),
        ("Q4 <2 min   (1:30)",         4,  90),
        ("Q4 <1 min   (0:45)",         4,  45),
    ]:
        w = wts(quarter=q, clock=secs, homeScore=0, awayScore=7)
        print(ROW.format(label, w['run'], w['short'], w['medium'], w['long']))

    # ── [2] Deficit magnitude ─────────────────────────────────────────
    print("\n[2] DEFICIT MAGNITUDE — Q4 <2 min (1:30), 3rd & 8")
    print("    The Q4 trailing mod is binary: scoreDiff < 0, no magnitude scaling.")
    print(HDR)
    for label, deficit in [
        ("Even  (0)",      0),
        ("Trailing  -3",   3),
        ("Trailing  -7",   7),
        ("Trailing -14",  14),
        ("Trailing -21",  21),
    ]:
        w = wts(quarter=4, clock=90, homeScore=0, awayScore=deficit)
        print(ROW.format(label, w['run'], w['short'], w['medium'], w['long']))
    print("    FINDING: trailing -3 and -21 produce identical weights in Q4.")
    print("    Q3 is the only place deficit magnitude matters (>10 pt threshold).")

    # ── [3] Field position ────────────────────────────────────────────
    print("\n[3] FIELD POSITION — 1st & 10, Q2, even score")
    print("    yte=yards to endzone; yte≤15: run×1.3 long×0.2; yte≤5: also long×0.1")
    print(HDR)
    for label, yte in [
        ("Own  5-yd line  (safety risk  yte=95)", 95),
        ("Own 20-yd line  (yte=80)",              80),
        ("Midfield        (yte=50)",              50),
        ("Opp 25-yd line  (yte=25)",              25),
        ("Red zone        (yte=15)",              15),
        ("Goal line       (yte=5)",                5),
    ]:
        w = wts(down=1, ytg=10, quarter=2, yardsToEndzone=yte)
        print(ROW.format(label, w['run'], w['short'], w['medium'], w['long']))
    print("    FINDING: goal-line (yte=5) and red zone (yte=15) produce identical weights —")
    print("    only yte≤15 fires (run×1.3, long×0.2). The safety mod (long×0.1) fires on")
    print("    yardsToSafety≤5 (own end zone, yte≥95), not when attacking the goal line.")
    print("    Gap: no extra goal-line differentiation vs mid-red-zone in the current system.")

    # ── [4] Coach personality spread ──────────────────────────────────
    print("\n[4] COACH PERSONALITY — 3rd & 8, Q1, even")
    print("    aggrNorm=(aggressiveness-80)/20; offMindNorm=(offensiveMind-80)/20")
    print(HDR)
    combos = [
        ("Gunslinger    (aggr=95 offMind=95)", 95, 95),
        ("Gambler       (aggr=95 offMind=65)", 95, 65),
        ("Average       (aggr=80 offMind=80)", 80, 80),
        ("Cerebral/safe (aggr=65 offMind=95)", 65, 95),
        ("Conservative  (aggr=65 offMind=65)", 65, 65),
    ]
    longPcts = []
    for label, aggr, offM in combos:
        w = wts(offCoach=makeCoach(aggr, offM, 80))
        longPcts.append(w['long'])
        print(ROW.format(label, w['run'], w['short'], w['medium'], w['long']))
    spread = max(longPcts) - min(longPcts)
    print(f"    Long-pass range: {min(longPcts):.1f}% – {max(longPcts):.1f}%  "
          f"({spread:.1f} ppt spread).")
    print("    aggressiveness drives long%, offensiveMind shifts medium vs long balance.")

    # ── [5] Adaptability threshold ────────────────────────────────────
    print("\n[5] ADAPTABILITY THRESHOLD — 1st & 10, Q2, weak run-D (defRun=60)")
    print("    adaptNorm = max(0, (adaptability-80)/20) — one-directional.")
    print(HDR)
    for adapt in [60, 70, 80, 90, 100]:
        w = wts(down=1, ytg=10, quarter=2, offCoach=makeCoach(80, 80, adapt), defRunRating=60)
        label = f"adaptability = {adapt}"
        print(ROW.format(label, w['run'], w['short'], w['medium'], w['long']))
    print("    FINDING: adapt ≤ 80 gives identical run% — below-80 adaptability")
    print("    has zero effect. Only values above 80 exploit defensive weaknesses.")

    # ── [6] Mod stacking interactions ─────────────────────────────────
    print("\n[6] MOD STACKING — How situational mods combine  (3rd & 8)")
    print("    Mods are multiplicative. Some combinations partially cancel.")
    print(HDR)
    baseW = wts()
    print(ROW.format("Baseline: Q1, 3rd & 8, even, midfield",
                     baseW['run'], baseW['short'], baseW['medium'], baseW['long']))
    for label, kwargs in [
        ("+ Q4 trailing -7  <2min",
         dict(quarter=4, clock=90, homeScore=0, awayScore=7)),
        ("+ Red zone  (yte=15)",
         dict(quarter=2, clock=600, yardsToEndzone=15)),
        ("+ Q4 trailing -7  <2min  + red zone",
         dict(quarter=4, clock=90, homeScore=0, awayScore=7, yardsToEndzone=15)),
        ("+ Q4 trailing -7  <2min  + own 5-yd",
         dict(quarter=4, clock=90, homeScore=0, awayScore=7, yardsToEndzone=95)),
        ("+ Q4 leading  +7  3min   + own 5-yd",
         dict(quarter=4, clock=180, homeScore=7, awayScore=0, yardsToEndzone=95)),
    ]:
        w = wts(down=3, ytg=8, **kwargs)
        print(ROW.format(label, w['run'], w['short'], w['medium'], w['long']))
    print("    Q4 trailing <2min + red zone: long×(2.5×0.2)=×0.5  (mods partially cancel).")
    print("    Q4 trailing <2min + own-5:   run×(0.1×1.4)=×0.14, long×(2.5×0.1)=×0.25.")

    print()


# ─────────────────────────────────────────────────────────────────────────────
# Part 2 — Clock management triggers
# ─────────────────────────────────────────────────────────────────────────────

_SHORT_PLAYS  = {'Play8', 'Play10', 'Play11', 'Play12'}
_MEDIUM_PLAYS = {'Play3', 'Play6', 'Play7', 'Play13'}
_LONG_PLAYS   = {'Play1', 'Play2', 'Play4', 'Play5'}


class MockPlay:
    """Records what play was called instead of simulating it."""
    def __init__(self, game):
        self.game = game
        self.playType = None
        self.passType = None
        self.playResult = None
        self.playText = ''
        self.offense  = game.offensiveTeam
        self.defense  = game.defensiveTeam
        self.quarter  = game.currentQuarter
        self.down     = game.down
        self.timeRemaining = '0:00'
        self.yardLine = '50'
        self.yardsTo1st   = game.yardsToFirstDown
        self.yardsToEndzone = game.yardsToEndzone
        self.yardsToSafety  = game.yardsToSafety
        self.yardage  = 0
        self.isTd = self.isFumbleLost = self.isInterception = False
        self.scoreChange = self.isSack = False
        self.homeTeamScore = game.homeScore
        self.awayTeamScore = game.awayScore

    def runPlay(self):
        self.playType = PlayType.Run;  self.yardage = 5

    def passPlay(self, playName):
        self.playType = PlayType.Pass
        if playName in _SHORT_PLAYS:
            self.passType = 'short'
        elif playName in _MEDIUM_PLAYS:
            self.passType = 'medium'
        else:
            self.passType = 'long'
        self.yardage = 10

    def kneel(self):
        from floosball_game import PlayResult
        self.playType = PlayType.Kneel;  self.yardage = -1
        self.game.clockRunning = True
        drain = min(40, self.game.gameClockSeconds)
        self.game.gameClockSeconds -= drain
        if self.game.down == 1:   self.playResult = PlayResult.SecondDown
        elif self.game.down == 2: self.playResult = PlayResult.ThirdDown
        else:                     self.playResult = PlayResult.FourthDown

    def spike(self):
        from floosball_game import PlayResult
        self.playType = PlayType.Spike;  self.yardage = 0
        self.game.clockRunning = False
        if self.game.down == 1:   self.playResult = PlayResult.SecondDown
        elif self.game.down == 2: self.playResult = PlayResult.ThirdDown
        else:                     self.playResult = PlayResult.FourthDown


def clockTest(label, game, expectType=None, expectNot=None):
    """Run playCaller() once and report pass/fail."""
    game.play = MockPlay(game)
    game.playCaller()
    actual = game.play.playType

    if expectType is not None:
        passed = (actual == expectType)
        expectStr = expectType.name
    elif expectNot is not None:
        passed = (actual != expectNot)
        expectStr = f"NOT {expectNot.name}"
    else:
        passed = True
        expectStr = "any"

    actualStr = actual.name if actual else "None"
    icon = "✓" if passed else "✗"
    result = "PASS" if passed else f"FAIL  (got {actualStr})"
    print(f"  {icon} {label:<52}  {result}")


def runClockManagementTests():
    print("=" * 60)
    print("PART 2 — CLOCK MANAGEMENT TRIGGERS")
    print("=" * 60)

    # ── KNEEL ─────────────────────────────────────────────────────────────
    print("\n  Kneel:")
    # Leading +10, 1:20 left, 1st, opp has 0 TOs
    # availableKneels=3, effectiveOppTos=0 (>8 pts), drainable=120 >= 80 → KNEEL
    clockTest("Leading +10  1:20  1st  opp 0 TOs    → KNEEL",
              makeGame(down=1, ytg=10, quarter=4, clock=80,
                       homeScore=17, awayScore=7, offIsHome=True,
                       homeTOs=3, awayTOs=0),
              expectType=PlayType.Kneel)

    # Leading +10, 0:55, 2nd, opp has 0 TOs
    # availableKneels=2, drainable=80 >= 55 → KNEEL
    clockTest("Leading +10  0:55  2nd  opp 0 TOs    → KNEEL",
              makeGame(down=2, ytg=10, quarter=4, clock=55,
                       homeScore=17, awayScore=7, offIsHome=True,
                       homeTOs=3, awayTOs=0),
              expectType=PlayType.Kneel)

    # Leading +3, 2:30 left, 1st, opp has 3 TOs (close game → TOs count)
    # effectiveOppTos=3, drainable=max(0,3-3)*40=0 < 150 → NO KNEEL
    clockTest("Leading  +3  2:30  1st  opp 3 TOs    → no kneel",
              makeGame(down=1, ytg=10, quarter=4, clock=150,
                       homeScore=10, awayScore=7, offIsHome=True,
                       homeTOs=3, awayTOs=3),
              expectNot=PlayType.Kneel)

    # Leading +10, 2:30, 1st, opp has 3 TOs but blowout so TOs ignored
    # effectiveOppTos=0, drainable=120 < 150 → NO KNEEL (can't drain clock)
    clockTest("Leading +10  2:30  1st  opp 3 TOs    → no kneel (clock too long)",
              makeGame(down=1, ytg=10, quarter=4, clock=150,
                       homeScore=17, awayScore=7, offIsHome=True,
                       homeTOs=3, awayTOs=3),
              expectNot=PlayType.Kneel)

    # Not Q4 (Q3) → no kneel even if leading
    clockTest("Leading +10  Q3   1st  opp 0 TOs     → no kneel (wrong quarter)",
              makeGame(down=1, ytg=10, quarter=3, clock=80,
                       homeScore=17, awayScore=7, offIsHome=True,
                       homeTOs=3, awayTOs=0),
              expectNot=PlayType.Kneel)

    # ── SPIKE ─────────────────────────────────────────────────────────────
    # Convention for spike tests: offIsHome=False (away team on offense).
    # For away team to be TRAILING: homeScore > awayScore.
    # timeoutsLeft = awayTimeoutsRemaining (the offensive team's TOs).
    print("\n  Spike:")

    # Q4, trailing, 0:10 left, no TOs, clock running → SPIKE
    clockTest("Q4  trailing  0:10  no TOs  running   → SPIKE",
              makeGame(down=2, ytg=15, quarter=4, clock=10,
                       homeScore=14, awayScore=7, offIsHome=False,
                       clockRunning=True, homeTOs=3, awayTOs=0),
              expectType=PlayType.Spike)

    # Q2, trailing, 0:12 left, no TOs, clock running → SPIKE
    clockTest("Q2  trailing  0:12  no TOs  running   → SPIKE",
              makeGame(down=1, ytg=10, quarter=2, clock=12,
                       homeScore=14, awayScore=7, offIsHome=False,
                       clockRunning=True, homeTOs=3, awayTOs=0),
              expectType=PlayType.Spike)

    # Trailing but has 1 TO — spike requires timeoutsLeft==0, so no spike
    clockTest("Q4  trailing  0:10  has 1 TO          → no spike",
              makeGame(down=2, ytg=15, quarter=4, clock=10,
                       homeScore=14, awayScore=7, offIsHome=False,
                       clockRunning=True, homeTOs=3, awayTOs=1),
              expectNot=PlayType.Spike)

    # Leading — kneel fires instead (scoreDiff > 0 on short clock)
    clockTest("Q4  LEADING   0:10  no TOs  running   → no spike (kneel fires)",
              makeGame(down=2, ytg=15, quarter=4, clock=10,
                       homeScore=7, awayScore=14, offIsHome=False,
                       clockRunning=True, homeTOs=3, awayTOs=0),
              expectNot=PlayType.Spike)

    # Clock stopped — spike needs clockRunning=True
    clockTest("Q4  trailing  0:10  no TOs  stopped   → no spike",
              makeGame(down=2, ytg=15, quarter=4, clock=10,
                       homeScore=14, awayScore=7, offIsHome=False,
                       clockRunning=False, homeTOs=3, awayTOs=0),
              expectNot=PlayType.Spike)

    # Q1 — spike only triggers in Q2/Q4
    clockTest("Q1  trailing  0:10  no TOs  running   → no spike (wrong quarter)",
              makeGame(down=2, ytg=15, quarter=1, clock=10,
                       homeScore=14, awayScore=7, offIsHome=False,
                       clockRunning=True, homeTOs=3, awayTOs=0),
              expectNot=PlayType.Spike)

    print()


# ─────────────────────────────────────────────────────────────────────────────
# Part 3 — Timeout triggers
# ─────────────────────────────────────────────────────────────────────────────

def timeoutTest(label, game, expectTimeout):
    """Run playCaller() once and check whether a timeout was called.

    Detection: the offensive team's TO count decreases by exactly 1.
    The timeout falls through to normal play selection, so play.playType
    will be Run or Pass — not a special type — when a TO fires.
    """
    isHome = (game.offensiveTeam is game.homeTeam)
    tosBefore = game.homeTimeoutsRemaining if isHome else game.awayTimeoutsRemaining

    game.play = MockPlay(game)
    game.playCaller()

    tosAfter = game.homeTimeoutsRemaining if isHome else game.awayTimeoutsRemaining
    calledTO = (tosAfter == tosBefore - 1)

    passed = (calledTO == expectTimeout)
    icon = "✓" if passed else "✗"
    actualStr = "TO called" if calledTO else "no TO"
    result = "PASS" if passed else f"FAIL  (got {actualStr})"
    print(f"  {icon} {label:<52}  {result}")


def runTimeoutTests():
    print("=" * 60)
    print("PART 3 — TIMEOUT TRIGGERS")
    print("  (Q4, trailing, clockRunning, TOs > 0, clock <= 120 sec)")
    print("=" * 60)

    # Convention: offIsHome=False (away team on offense).
    # Away team is TRAILING when homeScore > awayScore.
    # Offensive TOs = awayTimeoutsRemaining.

    print("\n  Should call timeout:")
    timeoutTest("Q4  trailing -7   1:30  2 TOs  running      → TO",
                makeGame(down=2, ytg=10, quarter=4, clock=90,
                         homeScore=14, awayScore=7, offIsHome=False,
                         clockRunning=True, homeTOs=3, awayTOs=2),
                expectTimeout=True)

    timeoutTest("Q4  trailing -3   0:45  1 TO   running      → TO",
                makeGame(down=1, ytg=10, quarter=4, clock=45,
                         homeScore=10, awayScore=7, offIsHome=False,
                         clockRunning=True, homeTOs=3, awayTOs=1),
                expectTimeout=True)

    timeoutTest("Q4  trailing -14  2:00  3 TOs  running      → TO",
                makeGame(down=3, ytg=8, quarter=4, clock=120,
                         homeScore=21, awayScore=7, offIsHome=False,
                         clockRunning=True, homeTOs=3, awayTOs=3),
                expectTimeout=True)

    print("\n  Should NOT call timeout:")
    timeoutTest("Q3  trailing -7   1:30  2 TOs  running      → no TO (wrong quarter)",
                makeGame(down=2, ytg=10, quarter=3, clock=90,
                         homeScore=14, awayScore=7, offIsHome=False,
                         clockRunning=True, homeTOs=3, awayTOs=2),
                expectTimeout=False)

    timeoutTest("Q4  LEADING  +7   1:30  2 TOs  running      → no TO (leading)",
                makeGame(down=2, ytg=10, quarter=4, clock=90,
                         homeScore=7, awayScore=14, offIsHome=False,
                         clockRunning=True, homeTOs=3, awayTOs=2),
                expectTimeout=False)

    timeoutTest("Q4  trailing -7   1:30  0 TOs  running      → no TO (no TOs left)",
                makeGame(down=2, ytg=10, quarter=4, clock=90,
                         homeScore=14, awayScore=7, offIsHome=False,
                         clockRunning=True, homeTOs=3, awayTOs=0),
                expectTimeout=False)

    timeoutTest("Q4  trailing -7   1:30  2 TOs  stopped      → no TO (clock stopped)",
                makeGame(down=2, ytg=10, quarter=4, clock=90,
                         homeScore=14, awayScore=7, offIsHome=False,
                         clockRunning=False, homeTOs=3, awayTOs=2),
                expectTimeout=False)

    timeoutTest("Q4  trailing -7   2:30  2 TOs  running      → no TO (clock > 120 sec)",
                makeGame(down=2, ytg=10, quarter=4, clock=150,
                         homeScore=14, awayScore=7, offIsHome=False,
                         clockRunning=True, homeTOs=3, awayTOs=2),
                expectTimeout=False)

    print()


# ─────────────────────────────────────────────────────────────────────────────
# Part 4 — 4th down decisions
# ─────────────────────────────────────────────────────────────────────────────
# Stub kicker: maxFgDistance=52, so kickerMaxDistance = 52-17 = 35.
# FG range:  yardsToEndzone <= 35.
# Punt zone: yardsToSafety <= 35  <=>  yardsToEndzone >= 65.
# No-man's-land: 36 <= yte <= 64  (not FG range, not punt zone).

def fourthDownTest(label, game, expectType, expectPassType=None):
    """Assert that _fourthDownCaller() produces the expected play type.

    For deterministic code paths only.  expectPassType may be 'short'/'medium'/'long'.
    """
    game.play = MockPlay(game)
    game.playCaller()
    actual     = game.play.playType
    actualPass = getattr(game.play, 'passType', None)

    passed = (actual == expectType)
    if passed and expectPassType is not None and actual == PlayType.Pass:
        passed = (actualPass == expectPassType)

    icon       = "✓" if passed else "✗"
    expectStr  = expectType.name + (f"/{expectPassType}" if expectPassType else "")
    actualStr  = (actual.name if actual else "None") + (f"/{actualPass}" if actualPass else "")
    result     = "PASS" if passed else f"FAIL  (got {actualStr})"
    print(f"  {icon} {label:<58}  {result}")


def probTest(label, game, n=300):
    """Run playCaller() n times and show distribution of outcomes.

    Game state is not modified between iterations (only game.play is reset).
    """
    counts = {}
    for _ in range(n):
        game.play = MockPlay(game)
        game.playCaller()
        pt = game.play.playType
        passT = getattr(game.play, 'passType', None)
        key = pt.name if pt else "None"
        if passT:
            key += f"/{passT}"
        counts[key] = counts.get(key, 0) + 1

    print(f"\n  {label}  (n={n})")
    for key, count in sorted(counts.items(), key=lambda x: -x[1]):
        pct = count / n * 100
        bar = "█" * int(pct / 100 * 30 + 0.5)
        print(f"    {key:<18}  {pct:5.1f}%  {bar}")


def runFourthDownTests():
    print("=" * 60)
    print("PART 4 — 4TH DOWN DECISIONS")
    print("  Stub kicker maxFgDistance=52 → FG range = yte≤35")
    print("  Punt zone = yte≥65  |  No-man's-land = yte 36-64")
    print("=" * 60)

    # ── Deterministic paths ───────────────────────────────────────────
    print("\n  Deterministic (always → expected outcome):")

    # Punt zone — unconditional punt regardless of score
    fourthDownTest("Own 30-yd line  yte=70  even  4th & 5       → Punt (punt zone)",
                   makeGame(down=4, ytg=5, quarter=2, clock=400,
                            homeScore=0, awayScore=0, yardsToEndzone=70),
                   PlayType.Punt)

    # Leading, in FG range, not Q4 → FG
    fourthDownTest("Leading  +7  Q2  4th & 5  yte=28            → FG",
                   makeGame(down=4, ytg=5, quarter=2, clock=400,
                            homeScore=7, awayScore=0, yardsToEndzone=28),
                   PlayType.FieldGoal)

    # Leading, in FG range, Q4 <5min → FG
    fourthDownTest("Leading  +7  Q4  3:20  4th & 5  yte=25      → FG (Q4 protect)",
                   makeGame(down=4, ytg=5, quarter=4, clock=200,
                            homeScore=7, awayScore=0, yardsToEndzone=25),
                   PlayType.FieldGoal)

    # Trailing, in FG range, yte ≤ 25 → FG (unconditional)
    fourthDownTest("Trailing -7  Q2  4th & 5  yte=20             → FG",
                   makeGame(down=4, ytg=5, quarter=2, clock=400,
                            homeScore=0, awayScore=7, yardsToEndzone=20),
                   PlayType.FieldGoal)

    # Trailing Q4 deficit ≤ 8, no-man's-land: route depends on ytg
    fourthDownTest("Trailing -3  Q4  4th & 3  yte=45             → Pass/short",
                   makeGame(down=4, ytg=3, quarter=4, clock=300,
                            homeScore=0, awayScore=3, yardsToEndzone=45),
                   PlayType.Pass, 'short')

    fourthDownTest("Trailing -7  Q4  4th & 7  yte=45             → Pass/medium",
                   makeGame(down=4, ytg=7, quarter=4, clock=300,
                            homeScore=0, awayScore=7, yardsToEndzone=45),
                   PlayType.Pass, 'medium')

    fourthDownTest("Trailing -7  Q4  4th & 10  yte=45            → Pass/long",
                   makeGame(down=4, ytg=10, quarter=4, clock=300,
                            homeScore=0, awayScore=7, yardsToEndzone=45),
                   PlayType.Pass, 'long')

    # Trailing Q4 deficit > 16, clock < 300 → always long
    fourthDownTest("Trailing -21  Q4  4:00  4th & 8  yte=45     → Pass/long (desperation)",
                   makeGame(down=4, ytg=8, quarter=4, clock=200,
                            homeScore=0, awayScore=21, yardsToEndzone=45),
                   PlayType.Pass, 'long')

    # Trailing Q3 deficit ≤ 8, ytg ≤ 2 → short pass
    fourthDownTest("Trailing -3  Q3  4th & 2  yte=45             → Pass/short",
                   makeGame(down=4, ytg=2, quarter=3, clock=400,
                            homeScore=0, awayScore=3, yardsToEndzone=45),
                   PlayType.Pass, 'short')

    # Trailing in Q1, no-man's-land, no desperate condition → Punt
    fourthDownTest("Trailing -7  Q1  4th & 5  yte=45             → Punt (too early)",
                   makeGame(down=4, ytg=5, quarter=1, clock=500,
                            homeScore=0, awayScore=7, yardsToEndzone=45),
                   PlayType.Punt)

    # Even score, in FG range yte≤20, ytg > 1 → always FG
    fourthDownTest("Even  Q2  4th & 5  yte=18                    → FG (yte≤20 ytg>1)",
                   makeGame(down=4, ytg=5, quarter=2, clock=400,
                            homeScore=0, awayScore=0, yardsToEndzone=18),
                   PlayType.FieldGoal)

    # ── Probabilistic paths ───────────────────────────────────────────
    print()

    # Leading, no FG range, 4th & 1 — go-for-it probability depends on aggressiveness
    # avg coach: threshold = round(3 + 0) = 3 → 30% run, 70% punt
    # aggr coach (aggr=95, aggrNorm=0.75): round(3+2.25) = 5 → 50% run, 50% punt
    probTest("Leading +7  Q2  4th & 1  yte=48  avg coach  (expect ~30% run)",
             makeGame(down=4, ytg=1, quarter=2, clock=400,
                      homeScore=7, awayScore=0, yardsToEndzone=48,
                      offCoach=makeCoach(80, 80, 80)))

    probTest("Leading +7  Q2  4th & 1  yte=48  aggressive (expect ~50% run)",
             makeGame(down=4, ytg=1, quarter=2, clock=400,
                      homeScore=7, awayScore=0, yardsToEndzone=48,
                      offCoach=makeCoach(95, 80, 80)))

    # Q4 leading, clock<5min, go-for-it threshold = round(4 + aggrNorm*3)
    # avg: 40% run; aggr: round(4+2.25)=6 → 60% run
    probTest("Leading +7  Q4  4:00  4th & 1  yte=48  avg coach  (expect ~40% run)",
             makeGame(down=4, ytg=1, quarter=4, clock=240,
                      homeScore=7, awayScore=0, yardsToEndzone=48,
                      offCoach=makeCoach(80, 80, 80)))

    # Trailing, in FG range, yte 26-35, Q3 → 90% FG, 10% medium pass
    probTest("Trailing -7  Q3  4th & 5  yte=30  (expect ~90% FG)",
             makeGame(down=4, ytg=5, quarter=3, clock=400,
                      homeScore=0, awayScore=7, yardsToEndzone=30))

    # Even, yte 21-35, ytg > 2 → 85% FG, 15% medium pass
    probTest("Even  Q2  4th & 5  yte=28  (expect ~85% FG)",
             makeGame(down=4, ytg=5, quarter=2, clock=400,
                      homeScore=0, awayScore=0, yardsToEndzone=28))

    # Trailing deficit ≤ 16, Q4 clock<480, ytg 4-8 → 80% medium, 20% punt
    probTest("Trailing -10  Q4  7:30  4th & 7  yte=45  (expect ~80% Pass/medium)",
             makeGame(down=4, ytg=7, quarter=4, clock=400,
                      homeScore=0, awayScore=10, yardsToEndzone=45))

    print()


if __name__ == '__main__':
    runWeightTests()
    runAnalysis()
    runClockManagementTests()
    runTimeoutTests()
    runFourthDownTests()
    print("All tests complete.")
