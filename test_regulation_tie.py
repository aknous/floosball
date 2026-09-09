"""A touchdown is not a finished scoring play until its try is taken.

⚠️ PROD GAME 2141 ENDED 21-21 IN REGULATION. A trailing team scored as the clock hit 0:00 --
one point down, extra point still to come -- and the TOUCHDOWN'S OWN BROADCAST latched
`status = Final`, because at Q4 with an expired clock `isGameOver()` answers "yes, the scores
differ". The extra point then went through and tied it, and the main loop's next
`isGameOver()` short-circuits on `status == Final`. The tying kick landed on a game that had
already been declared over, so overtime never happened.

⚠️ IT COULD ONLY EVER HAPPEN IN PRODUCTION, WHICH IS WHY NO SIM SHOWED IT. The latch sits
BELOW `broadcastGameState`'s `if not BROADCASTING_AVAILABLE or not broadcaster.is_enabled():
return`, so with the broadcaster off -- every local sim, every fitting run, every
`--timing=fast` season -- the line never executes and the same game reaches overtime
correctly. Whether a game ended in a tie depended on whether anybody was watching. **That is
why this suite enables the broadcaster**; without that line it passes vacuously against the
unfixed engine.

⚠️ AND THE WALK-OFF MUST STILL LATCH. The latch exists so the frontend does not show a live
game on the last scoring play, and a scorer who has gone AHEAD owes no meaningful try. Case 3
is what stops the fix being "never latch on a touchdown", which would have left every walk-off
reading live through the pause before the final broadcast.

Run: .venv/bin/python test_regulation_tie.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)
import managers                      # resolve circular import before floosball_game
from scenario import Scenario
import floosball_game as FG
from api.game_broadcaster import broadcaster

fails = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        fails.append(label)


# ⚠️ A DUMMY MANAGER IS ENOUGH. `is_enabled()` only asks that one is set, and every actual
# send is guarded by `_main_loop is not None and _main_loop.is_running()`, which is False
# here -- so the broadcast path runs end to end and dispatches nothing.
broadcaster.enable(object())


def endgame(*, offScore, defScore, td=6, tryPoints=1):
    """A team scores as the clock expires. Returns (latchedOnTd, isGameOverAfterTry)."""
    s = Scenario(); g = s.game
    s.situation(quarter=4, clock=0, offense='away', offScore=offScore, defScore=defScore)
    # broadcastGameState reads the previous WP to compute WPA; a fresh Game has none.
    g.previousHomeWinProbability = g.previousAwayWinProbability = 50.0
    g._addScore(g.awayTeam, td)
    g.play.playResult = FG.PlayResult.Touchdown
    g.play.scoreChange = True
    g.broadcastGameState(includeLastPlay=True)
    latched = g.status == FG.GameStatus.Final
    owed = g._tryStillOwed()
    g._addScore(g.awayTeam, tryPoints)          # the try
    return latched, owed, g.isGameOver(), g.awayScore, g.homeScore


print("\n1. THE REPORTED GAME -- trailing by 7, scores at 0:00, the try ties it")
latched, owed, over, away, home = endgame(offScore=14, defScore=21)
expect('the try is recognised as owed', owed)
expect('the touchdown does NOT end the game', not latched)
expect('the try ties it', away == home == 21)
expect('a tied game at 0:00 is not over -- it goes to overtime', not over)

print("\n2. The same touchdown, but the try is MISSED")
latched, owed, over, away, home = endgame(offScore=14, defScore=21, tryPoints=0)
expect('still not latched on the touchdown itself', not latched)
expect('a one-point game at 0:00 IS over once the try is done', over)
expect('the trailing team lost by one', away == 20 and home == 21)

print("\n3. A WALK-OFF -- the touchdown puts the scorer ahead, so no try matters")
latched, owed, over, away, home = endgame(offScore=16, defScore=21)
expect('no try is owed when the scorer is already ahead', not owed)
expect('the walk-off latches Final immediately, as it always did', latched)
expect('and the game is over', over)

print("\n4. A touchdown that only TIES it -- the try can win it outright")
latched, owed, over, away, home = endgame(offScore=15, defScore=21)
expect('the try is owed', owed)
expect('not latched', not latched)
expect('the try wins it', away == 22 and home == 21 and over)

print("\n5. The predicate is about the TRY, not about touchdowns in general")
s = Scenario(); g = s.game
s.situation(quarter=4, clock=0, offense='away', offScore=20, defScore=21)
expect('a non-scoring play owes nothing', not g._tryStillOwed())
g.play.playResult = FG.PlayResult.FieldGoalGood
expect('a field goal owes nothing', not g._tryStillOwed())

print(f"\n{len(fails)} failed" if fails else "\nall good")
sys.exit(1 if fails else 0)
