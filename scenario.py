"""Scenario harness — construct a real Game in a target situation and exercise
the actual decision/predicate code deterministically.

Some game situations (an OT defensive-return TD, a tied team in FG range at
2:40, a punt from deep in opponent territory) are far too rare to hit reliably
in a fast sim — e.g. ~0 OT defensive scores in 850 games. Rather than rely on
chance, build the exact state and call the real engine methods over it.

Unlike the SimpleNamespace stubs in test_play_calling.py, this builds REAL
teams/players/coaches and a REAL `Game`, so the decisions run the genuine code
paths (play-calling weights, FG-range math, clock management, OT rules).

Usage:
    from scenario import Scenario, PlayType
    s = Scenario()
    s.situation(quarter=4, clock=28, offense='home', offScore=21, defScore=20,
                down=4, distance=5, ballOn=67, offTimeouts=0, defTimeouts=1)
    assert s.fourthDownPlay() is not PlayType.Kneel   # don't kneel into a turnover

`ballOn` is yards to the OPPONENT'S end zone (i.e. yardsToEndzone): 67 = your
own 33-yard line, 28 = the opponent's 28. `offense` is 'home' or 'away'; scores
and timeouts are given from the offense's perspective.
"""
import sys, os, types, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Break the floosball_game <-> managers circular import (same trick the headless
# tests use): register a stub so seasonManager's annotations resolve, then load
# the real module once managers is cached.
if 'floosball_game' not in sys.modules:
    _stub = types.ModuleType('floosball_game')
    class _GameStub: pass
    _stub.Game = _GameStub
    sys.modules['floosball_game'] = _stub
    import managers.timingManager  # noqa: F401
    del sys.modules['floosball_game']

import floosball_game as _FG
import floosball_player as _FP
import floosball_team as _FT
import floosball_coach as _FC
from game_rules import GameRules

PlayType = _FG.PlayType
PlayResult = _FG.PlayResult

_SLOTS = [('qb', 'QB'), ('rb', 'RB'), ('wr1', 'WR'), ('wr2', 'WR'),
          ('te', 'TE'), ('k', 'K')]
_POS = {'QB': _FP.PlayerQB, 'RB': _FP.PlayerRB, 'WR': _FP.PlayerWR,
        'TE': _FP.PlayerTE, 'K': _FP.PlayerK}


def _makeTeam(name, abbr, base, phys=80, ment=80, defRun=78, defPass=78):
    t = _FT.Team(name)
    t.abbr = abbr
    t.city = name
    t.coach = _FC.Coach()
    roster = {}
    for slot, pos in _SLOTS:
        p = _POS[pos](phys, ment)
        p.name = '{} {}'.format(name, slot)
        p.id = base
        base += 1
        roster[slot] = p
    t.rosterDict = roster
    t.defenseRunCoverageRating = defRun
    t.defensePassRating = defPass
    t.elo = 1500
    return t


class Scenario:
    """A constructed, replayable game situation over a real `Game`."""

    def __init__(self, *, gameRules=None, homePhys=80, awayPhys=80,
                 homeDefRun=78, homeDefPass=78, awayDefRun=78, awayDefPass=78):
        self.home = _makeTeam('Homers', 'HOM', 100, phys=homePhys,
                              defRun=homeDefRun, defPass=homeDefPass)
        self.away = _makeTeam('Awayers', 'AWY', 200, phys=awayPhys,
                              defRun=awayDefRun, defPass=awayDefPass)
        self.game = _FG.Game(self.home, self.away,
                             gameRules=gameRules or GameRules())
        # Replicate the pregame attribute setup playGame() does, so every
        # method that reads gameAttributes works.
        for t in (self.home, self.away):
            for pl in t.rosterDict.values():
                pl.gameAttributes = copy.deepcopy(pl.attributes)
                pl.reset_game_stats()
            t.gameDefenseStats = copy.deepcopy(_FT.teamStatsDict['Defense'])
        self.game.offensiveTeam = self.home
        self.game.defensiveTeam = self.away
        self._offenseSide = 'home'

    # ── configuration ────────────────────────────────────────────────────
    def setKickerLeg(self, side, maxFgDistance):
        """Override a team's kicker max FG distance (side: 'home'/'away')."""
        team = self.home if side == 'home' else self.away
        team.rosterDict['k'].maxFgDistance = maxFgDistance
        return self

    def situation(self, *, quarter=4, clock=600, offense='home',
                  offScore=0, defScore=0, down=1, distance=10, ballOn=50,
                  offTimeouts=3, defTimeouts=3, clockRunning=True,
                  twoMinuteWarningShown=None, clockStoppedByWarning=False,
                  otPeriod=0, otFirstPossTeam=None,
                  otFirstPossComplete=False, otSecondPossComplete=False):
        """Place the game in a target situation. Returns self for chaining.

        ballOn = yards to the opponent's end zone (yardsToEndzone).
        offense = 'home' or 'away'; scores/timeouts are offense-relative.
        """
        g = self.game
        self._offenseSide = offense
        if offense == 'home':
            g.offensiveTeam, g.defensiveTeam = self.home, self.away
            g.homeScore, g.awayScore = offScore, defScore
            g.homeTimeoutsRemaining, g.awayTimeoutsRemaining = offTimeouts, defTimeouts
        else:
            g.offensiveTeam, g.defensiveTeam = self.away, self.home
            g.awayScore, g.homeScore = offScore, defScore
            g.awayTimeoutsRemaining, g.homeTimeoutsRemaining = offTimeouts, defTimeouts
        g.currentQuarter = quarter
        g.gameClockSeconds = clock
        g.down = down
        g.yardsToFirstDown = distance
        g.yardsToEndzone = ballOn
        g.yardsToSafety = g.gameRules.fieldLength - ballOn
        g.clockRunning = clockRunning
        g.twoMinuteWarningShown = (clock <= g.gameRules.twoMinuteWarningSeconds
                                   if twoMinuteWarningShown is None else twoMinuteWarningShown)
        g._clockStoppedByWarning = clockStoppedByWarning
        # Overtime bookkeeping
        g.otPeriod = otPeriod
        g.otFirstPossTeam = otFirstPossTeam if otFirstPossTeam is not None else g.offensiveTeam
        g.otFirstPossComplete = otFirstPossComplete
        g.otSecondPossComplete = otSecondPossComplete
        g.firstOtPossessionComplete = otSecondPossComplete
        self._newPlay()
        return self

    def _newPlay(self):
        self.game.play = _FG.Play(self.game)

    def _isHome(self):
        return self.game.offensiveTeam is self.game.homeTeam

    def _scoreDiff(self):
        g = self.game
        return (g.homeScore - g.awayScore) if self._isHome() else (g.awayScore - g.homeScore)

    # ── decisions (run the real AI) ──────────────────────────────────────
    def callPlay(self):
        """Run the full play-caller; return the chosen PlayType."""
        self._newPlay()
        self.game.playCaller()
        return self.game.play.playType

    def clockDecision(self):
        """Run the play-caller and return the clock-management decision tag
        ('timeout' / 'spike' / 'kneel') if one fired, else None."""
        self._newPlay()
        self.game.playCaller()
        cm = self.game.play.insights.get('clockMgmt')
        return cm.get('decision') if cm else None

    def fourthDownPlay(self):
        """Run the 4th-down caller; return the chosen PlayType."""
        self._newPlay()
        self.game._fourthDownCaller(self._scoreDiff(), self.game.offensiveTeam.coach, self._isHome())
        return self.game.play.playType

    # ── predicates ───────────────────────────────────────────────────────
    def gameOver(self):
        return self.game.isGameOver()

    def overtimeEnds(self, defensiveScore=False):
        return self.game.checkOvertimeEnd(defensiveScore=defensiveScore)

    # ── direct access ────────────────────────────────────────────────────
    @property
    def g(self):
        return self.game
