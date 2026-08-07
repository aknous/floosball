"""An offense about to score a go-ahead TD should score LAST, not fast.

Reported: a team down less than a touchdown but more than a field goal, goal-to-go with a
minute left. Measured before the fix, at 1st-and-goal from the 3 down 5 with 0:55, the
offense chose a 12-second huddle — scoring almost immediately and handing the opponent
~45 seconds plus all their timeouts to kick a winning field goal.

`_isFgDrainMode` had encoded this idea since forever, but only for a deficit of 0-3 (the
band where a kick settles it). The touchdown band had no equivalent, so a trailing offense
just hurried. Scoring is not the goal late in a one-score game; scoring LAST is.

Run: .venv/bin/python test_td_drain.py   (exits non-zero on any failure)
"""
import managers
import floosball_game as fg
from constants import TD_DRAIN_MIN_SECONDS, TD_DRAIN_MAX_YARDS


class Rules:
    timeoutClockThreshold = 120
    downsPerSeries = 4


class Team:
    def __init__(self, n): self.name = n; self.coach = None


class StubGame:
    _isTdDrainMode = fg.Game._isTdDrainMode
    _classifyTempoIntent = fg.Game._classifyTempoIntent
    _isGarbageTime = fg.Game._isGarbageTime
    _oneScore = fg.Game._oneScore
    _maxPossession = fg.Game._maxPossession
    _fgValue = fg.Game._fgValue

    def __init__(self, *, diff=-5, yte=3, ytg=None, down=1, secs=55, quarter=4):
        self.currentQuarter = quarter
        self.gameClockSeconds = secs
        self.homeTeam = Team('OFFENSE'); self.awayTeam = Team('DEFENSE')
        self.offensiveTeam = self.homeTeam; self.defensiveTeam = self.awayTeam
        self.homeScore = 20 + diff; self.awayScore = 20
        self.yardsToEndzone = yte
        self.yardsToFirstDown = yte if ytg is None else ytg
        self.down = down
        self.gameRules = Rules()
        self.format = None

    def _offenseEffectiveSecs(self): return self.gameClockSeconds
    def _frameDecisionDiff(self): return None
    def _frameEndSoon(self, *a): return False
    def _driveClockActive(self): return False
    def _chessClockLow(self, *a): return False
    def _chessClockCatchUpPossible(self, *a): return True
    def _maxLadderPoints(self): return 2   # the real default two-point conversion
    def _isFgDrainMode(self): return False
    def _targetShouldPush(self): return False
    def _targetDrainMode(self): return False


fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


# ── the reported game ───────────────────────────────────────────────────────
g = StubGame(diff=-5, yte=3, down=1, secs=55)
expect("down 5, 1st-and-goal from the 3, 0:55 -> hold the score", g._isTdDrainMode())
intent, base = g._classifyTempoIntent()
expect(f"...and the tempo drains rather than races ({intent}, {base}s huddle)",
       intent == 'burnClock' and base >= 35)

# ── a tie still wants the clock dead ───────────────────────────────────────
# A TD that only TIES sends the game to overtime; leaving time lets them win in regulation.
expect("down 7 (a TD ties) still holds", StubGame(diff=-7)._isTdDrainMode())
expect("down 8 (a TD + 2 ties) still holds", StubGame(diff=-8)._isTdDrainMode())

# ── where hurrying is still correct ────────────────────────────────────────
expect("down 9 needs two scores, so the clock is the enemy",
       not StubGame(diff=-9)._isTdDrainMode())
expect("down 3 belongs to the FG drain, not this",
       not StubGame(diff=-3)._isTdDrainMode())
expect("tied: scoring at all is the win condition",
       not StubGame(diff=0)._isTdDrainMode())
expect("leading: nothing to chase",
       not StubGame(diff=3)._isTdDrainMode())

# ── the safety rails ───────────────────────────────────────────────────────
expect(f"3rd down: too few cracks left to burn one draining",
       not StubGame(down=3)._isTdDrainMode())
expect(f"4th down: score now or never",
       not StubGame(down=4)._isTdDrainMode())
expect(f"from the {TD_DRAIN_MAX_YARDS + 10}, a score is hoped for rather than near-certain",
       not StubGame(yte=TD_DRAIN_MAX_YARDS + 10)._isTdDrainMode())
expect(f"under {TD_DRAIN_MIN_SECONDS}s there is no room to drain and still snap it",
       not StubGame(secs=TD_DRAIN_MIN_SECONDS - 5)._isTdDrainMode())
# Proximity + spare downs is the condition, NOT a literal goal-to-go test. 2nd-and-1 from
# the 3 (1st-and-10 from the 12, gain 9) is not goal-to-go and is just as good a place to
# hold the score from, so requiring goal-to-go was tried and cut as too strict.
expect("2nd-and-1 from the 3 holds too, though it is not goal-to-go",
       StubGame(yte=3, ytg=1, down=2)._isTdDrainMode())
expect("early in the game the clock is not the deciding factor",
       not StubGame(secs=600)._isTdDrainMode())
expect("Q3 is not an end-game", not StubGame(quarter=3)._isTdDrainMode())

# ── it must not swallow the ordinary two-minute drill ──────────────────────
midfield = StubGame(diff=-5, yte=45, ytg=10, down=1, secs=55)
expect("a normal trailing drive at midfield still hurries",
       not midfield._isTdDrainMode() and midfield._classifyTempoIntent()[0] == 'hurryUp')

print("\nPASS — the offense bleeds the clock before a go-ahead score, and only then."
      if not fails else f"\n{len(fails)} FAILED")
raise SystemExit(1 if fails else 0)
